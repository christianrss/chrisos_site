---
id: virtio-gpu-transport
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/vgpu.c
  - kernel/gfx/vgpu.h
  - kernel/gfx/virtq.c
  - kernel/gfx/virtq.h
  - kernel/gfx/virtgpu_enc.c
  - kernel/gfx/virtgpu_enc.h
  - kernel/gfx/gpures.c
  - kernel/gfx/gpures.h
  - kernel/gfx/hwgate.c
  - kernel/gfx/hwgate.h
  - SYS/DRV/VIRTIOGPU.CC
  - tools/test_virtq.c
  - tools/test_gpures.c
  - tools/test_virgl_cmd.c
symbols:
  - virtq_init
  - virtq_alloc
  - virtq_publish
  - virtq_take
  - virtq_reclaim
  - vgpu_boot
  - vgpu_submit
  - vgpu_res_create_2d
  - vgpu_res_attach
  - vgpu_res_detach
  - vgpu_res_unref
  - vgpu_set_scanout
  - vgpu_flush_rect
depends_on:
  - buses-mmio-dma
related:
  - virtio-gpu-virgl
  - gfx3d-api
  - virgl-command-stream
---

# Transporte VirtIO-GPU e resources

## Escopo

Este capítulo isola a camada de transporte e gerenciamento de resources abaixo da pilha gráfica do ChrisOS.

O foco aqui não é a linguagem de comandos VirGL. O foco é o mecanismo que descobre o dispositivo VirtIO GPU no PCI, mapeia regiões de configuração, negocia features, constrói split virtqueues, envia commands por DMA, valida completions e gerencia IDs de resources VirtIO.

Essa separação é importante porque o mesmo transport carrega tanto operações 2D comuns quanto requests 3D/VirGL opcionais.

Uma visão útil é:

```text
PCI / MMIO / DMA
      |
      v
VirtIO PCI capabilities
      |
      v
split virtqueue transport
      |
      v
protocolo de controle VirtIO-GPU
      |
      +--> 2D resources / scanout / cursor
      |
      +--> 3D resources / contexts / SUBMIT_3D
```

VirGL fica acima do ramo 3D final.

## Descoberta do dispositivo

O driver kernel percorre PCI buses 0 a 7 e devices 0 a 31, function zero.

O match aceito atualmente é:

```text
vendor 0x1AF4
device 0x1050
```

A busca é, portanto, mais estreita que um enumerador PCI geral.

Depois de localizar o device, o código habilita PCI memory-space access e bus mastering.

Bus mastering é necessário porque o device consome endereços físicos do guest encontrados nos descriptors e nos backings de resources.

## Parsing das VirtIO PCI capabilities

A lista de PCI capabilities começa pelo offset 0x34.

O driver procura vendor-specific capability ID 9 e interpreta o tipo VirtIO no byte alto.

O caminho atual registra:

- type 1: common configuration;
- type 2: notify configuration;
- type 3: ISR configuration;
- type 4: device-specific configuration.

Common e notify são obrigatórios.

ISR e device-specific são usados quando existem, oferecendo acknowledge de interrupt e metadata do dispositivo.

## Fronteira de BAR mapping

`hw_bar_map` lê o BAR, detecta formato 64-bit, sonda temporariamente o tamanho, restaura o valor original e mapeia as páginas por MMIO.

A hardware gate mantém no máximo oito janelas MMIO.

Cada janela é limitada a 64 páginas, ou 256 KiB.

Esse limite é uma política do ChrisOS, não uma regra do VirtIO.

O transport gráfico depende, portanto, de disponibilidade da infraestrutura genérica MMIO antes de iniciar.

## State machine da negociação

O GPU driver reseta device status para zero e avança pelos estados ACKNOWLEDGE e DRIVER.

Os dois words de features são lidos.

O bit zero do word alto é obrigatório, correspondendo ao feature bit 32 do VirtIO moderno.

Se esse bit não estiver presente, a inicialização falha.

Quando 3D é desejado e o device suporta, o guest também solicita `VGPU_F_VIRGL`.

Se VirGL foi selecionado e `VGPU_F_CONTEXT_INIT` existe, essa feature também é solicitada.

## Retry de FEATURES_OK

Os feature words escolhidos são gravados e FEATURES_OK é definido.

Depois o driver lê o status novamente.

Se o device rejeitar o conjunto, o ChrisOS reinicia a negociação e tenta novamente apenas com o requisito moderno de VirtIO, sem as optional GPU features do word baixo.

Assim, uma combinação VirGL incompatível ainda pode resultar em VirtIO-GPU 2D funcional.

Se a segunda tentativa também falhar, a inicialização termina.

## Implementação de split virtqueue

O ChrisOS possui helper próprio em `kernel/gfx/virtq.c`.

A implementação genérica suporta:

```text
VQ_MAX = 128
```

descriptors.

O queue size precisa:

- ser pelo menos 2;
- ser no máximo 128;
- ser potência de dois.

Valor não power-of-two faz `virtq_bytes` retornar zero e é rejeitado por `virtq_init`.

## Layout da memória da queue

Para tamanho N, o ChrisOS organiza:

1. N descriptors de 16 bytes;
2. available ring;
3. padding até alinhamento de quatro bytes;
4. used ring.

A tabela de descriptors começa no offset zero.

Avail fica imediatamente após os descriptors.

Used começa depois de avail, alinhado em quatro bytes.

`virtq_bytes` calcula o footprint total antes da inicialização.

## Metadata local da virtqueue

A memória visível ao device não contém toda a bookkeeping usada pelo kernel.

`Virtq` também mantém:

- pointer e capacidade da memória;
- queue size;
- freelist head;
- quantidade de descriptors livres;
- último índice used consumido;
- next links por descriptor;
- flags locais por descriptor;
- offsets de desc, avail e used.

A freelist existe na estrutura C, não como linked list visível ao device.

## Inicialização

`virtq_init` zera os bytes visíveis ao dispositivo e monta a freelist.

No início:

```text
free_head = 0
nfree = qsz
last_used = 0
```

Cada `link_next[i]` aponta para o próximo index.

O descriptor final aponta para 0xffff.

Essa estrutura é usada pelo allocator das chains de requests.

## Alocação de descriptors

`virtq_alloc(q,n,&head)` exige descriptors livres suficientes.

Ela remove N entries da freelist e marca NEXT nos descriptors intermediários.

O head retornado é o primeiro elemento da chain.

Na control queue do GPU, uma request comum usa exatamente dois descriptors:

- command/request;
- response.

Uma queue com 16 descriptors comportaria, em teoria, oito requests de dois descriptors simultâneas.

O driver atual serializa submissions e normalmente mantém apenas uma chain outstanding.

## Preenchimento do descriptor

`virtq_set` grava:

```text
address : 64 bits
length  : 32 bits
flags   : 16 bits
next    : 16 bits
```

Command descriptors são legíveis pelo device.

Response descriptors usam `VQ_DESC_F_WRITE`, permitindo que o device escreva no guest.

O next selecionado pelo allocator vira o campo next do descriptor.

## Publish no available ring

`virtq_publish` executa memory barrier antes de modificar avail.

Ele lê o avail index, escolhe o slot por módulo do queue size, escreve o head da chain, executa outro barrier, incrementa avail index e executa um barrier final.

Em x86, a implementação usa `mfence`.

O objetivo é impedir que o device observe um novo avail index antes de descriptors e ring entry estarem globalmente visíveis.

## Consumo do used ring

`virtq_take` lê used index depois de barrier.

Se o valor for igual a `last_used`, não há completion nova.

Caso contrário, lê o próximo used element, valida que o descriptor ID está abaixo de qsz, copia used length, incrementa `last_used` e retorna uma completion.

Used ID inválido é tratado como corrupção do transport.

## Reclaim de descriptors

`virtq_reclaim` percorre a chain usando os links salvos localmente.

Cada descriptor volta para a freelist e `nfree` é incrementado.

A travessia termina quando NEXT deixa de estar presente.

Flags locais são limpas durante o reclaim.

Cada chain aceita deve, portanto, ser reclamada exatamente uma vez.

## Queue size específico do GPU

O setup do GPU começa com:

```text
VGPU_QSZ = 16
```

Se o device oferece menos, o driver escolhe a maior opção suportada entre:

```text
16, 8, 4, 2
```

Abaixo de dois, falha.

Embora o helper genérico aceite 128, o GPU deliberadamente limita sua queue a 16 descriptors.

Uma página DMA de 4 KiB é mais do que suficiente para esse layout.

## Programação da queue

Após `virtq_init`, o setup grava no common config:

- queue size;
- endereço da descriptor table;
- endereço de avail;
- endereço de used.

O caminho atual seleciona 0xffff para MSI-X vector e habilita a queue.

Depois lê o queue notify index e calcula o MMIO notify address usando o multiplier.

Tudo isso é armazenado em `VqBind`.

## Control queue e cursor queue

Queue 0 é usada para controle.

Queue 1 é configurada apenas se o device anuncia pelo menos duas filas.

Commands de cursor usam a cursor queue.

Resources, scanout, contexts e SUBMIT_3D usam a control queue.

Falha no setup do cursor não impede que o restante do VirtIO-GPU funcione.

A aceleração de cursor é opcional.

## Staging compartilhado de command e response

O transport aloca quatro páginas DMA para command staging e quatro para response staging.

Antes da submission, o command codificado é copiado para o command DMA compartilhado.

O começo da área de resposta é zerado.

A chain aponta diretamente para esses buffers.

Como os buffers são reutilizados, existe serialização global com `g_busy`.

## Contrato de serialização

`vgpu_submit_vq` rejeita nova control request enquanto `g_busy` está ativo.

O desenho atual é síncrono do ponto de vista do driver.

A queue não é preenchida com dezenas de commands outstanding.

Isso reduz complexidade de lifetime e de associar responses, mas também limita command-level parallelism.

A maior parte da profundidade da queue atua hoje como margem de robustez.

## Notification e completion

Depois do publish, o driver escreve o queue index no notify MMIO calculado.

A completion é observada por polling de `virtq_take`.

Existe IRQ handler para contar interrupts e fazer ISR acknowledge, mas o caminho síncrono normal ainda espera a used ring diretamente.

Assim, interrupt accounting é suporte/diagnóstico, não o mecanismo principal de completion.

## Budgets de polling

Existem perfis fast e slow.

O wait loop combina limite de spins com budget baseado em TSC.

Periodicamente executa `pause`.

Operações potencialmente mais lentas, como 3D resources, context operations e SUBMIT_3D, usam o budget maior.

Timeout marca o GPU como dead, desativa live/online e retorna erro.

O transport atual não tenta reset/replay automático depois do timeout.

## Requests com fence

A sequência global `g_fence_seq` começa em 1.

Quando uma operação usa fence, o driver grava FENCE flag e o valor 64-bit no header.

A response precisa devolver o mesmo fence.

Mismatch é registrado e rejeitado.

Isso reduz o risco de aceitar uma response velha ou inesperada como completion da request atual.

## Validação de response

Completion de transport e sucesso do protocolo são checks diferentes.

O driver valida:

- descriptor usado;
- fence;
- response type não zero;
- absence de error response VirtIO-GPU;
- response específica esperada, quando definida.

Portanto, aparecer uma entry na used ring não prova que CREATE_2D, DISPLAY_INFO ou outro command foi aceito.

## Boundary do encoder

`virtgpu_enc.c` serializa structs do protocolo em byte arrays.

Ele usa writes little-endian explícitos, não layout de struct C.

Isso evita depender de padding do compilador.

O header comum ocupa:

```text
VGPU_HDR_SIZE = 24 bytes
```

e contém type, flags, fence e context, com os demais bytes zerados.

## Validação dos encoders

Os encoders rejeitam zero IDs quando a operação exige objeto, dimensões zero, destination buffer pequeno e certos parâmetros fora da faixa.

RESOURCE_CREATE_2D rejeita width/height acima de 8192.

RESOURCE_CREATE_3D rejeita dimensões acima de 8192, array size acima de 256 e sample count acima de 16.

`vgpu_enc_submit3d` limita uma submission codificada a 4096 dwords.

A camada Gfx3D usa batches menores, de 1024 dwords.

## Lifecycle de resource 2D

`vgpu_res_create_2d` primeiro aloca um ID local.

Depois emite RESOURCE_CREATE_2D e registra type, state, dimensões, format e backing metadata.

Se DMA backing foi fornecido, `vgpu_res_attach` envia RESOURCE_ATTACH_BACKING.

Attach verifica se offset e size cabem dentro da DMA allocation.

O encoder atual usa uma backing entry por resource.

## Resource pool

O transport mantém:

```text
GPU_RES_MAX = 96
GPU_CTX_MAX = 16
```

Resource pool e DMA pool são conceitos separados.

Um resource pode referenciar uma allocation DMA inteira ou uma região iniciando em `backing_off`.

O limite de 96 considera chunk meshes cacheados, window targets, atlas, scanout, cursor e headroom.

Se acabar, o caller recebe falha em vez de kernel panic.

## IDs de resource

ID zero é inválido.

O allocator incrementa `next_res` e pula zero em wrap.

Antes de usar um ID, verifica se ainda existe resource live com o mesmo valor.

Em situação patológica de wrap/collision, procura até 100000 candidatos antes de falhar.

Ao liberar, a entry vira FREE e o ID é zerado.

## Ownership

Cada resource possui owner inteiro.

Release de resource pertencente a outro owner retorna erro distinto.

Attach context/resource também exige owners iguais.

Esse mecanismo é isolamento lógico da pilha gráfica, não isolamento de hardware via IOMMU.

Os DMA buffers continuam sendo memória gerenciada pelo kernel.

## Estados do resource

O enum contém:

```text
FREE
ALLOC
CREATED
BACKED
ATTACHED
SCANOUT
```

O código atual usa os principais estados, mas o enum ainda não funciona como state machine formal completa.

Por exemplo, context attach incrementa `ctx_attached` sem necessariamente trocar `state` para ATTACHED.

Portanto, a semântica real precisa ser lida nas operações, e não inferida apenas pelo nome do enum.

## Detach e unref

`vgpu_res_detach` envia RESOURCE_DETACH_BACKING.

Se o estado local era BACKED, volta para CREATED.

`vgpu_res_unref` envia RESOURCE_UNREF e depois libera a entrada no pool.

`vgpu_res_drop` também libera o DMA quando não se trata de uma allocation global protegida, como framebuffer principal, command/response queue ou cursor.

O objetivo é manter device lifecycle e local lifecycle sincronizados.

## Scanout

`vgpu_set_scanout` envia SET_SCANOUT.

Se o resource existe no pool local, seu state passa para SCANOUT.

Trocar scanout também incrementa a geração do cursor porque QEMU pode descartar o cursor sprite ao mudar o resource apresentado.

Logo, presentation e cursor lifecycle têm acoplamento nessa camada.

## Caminho de transferência 2D

Durante um update normal do desktop, pixels CPU-rendered são copiados para o backing DMA do scanout.

TRANSFER_TO_HOST_2D sincroniza a região do backing com o resource no host.

RESOURCE_FLUSH faz a atualização chegar à apresentação.

São funções diferentes: transfer atualiza o conteúdo do resource; flush solicita que a mudança seja exibida.

## Reuso do transport para 3D

A mesma control queue carrega:

- CTX_CREATE e CTX_DESTROY;
- CTX_ATTACH_RESOURCE e CTX_DETACH_RESOURCE;
- RESOURCE_CREATE_3D;
- TRANSFER_TO_HOST_3D e TRANSFER_FROM_HOST_3D;
- SUBMIT_3D.

A camada de transport não interpreta os dwords VirGL dentro de SUBMIT_3D.

Ela apenas empacota byte count, context e payload e valida a completion VirtIO-GPU.

Essa é a fronteira entre transport e command stream VirGL.

## Stress no boot

Antes de depender do 3D, `vgpu_boot` executa stress de lifecycle 2D.

Um pequeno resource 8×8 é repetidamente criado, transferido, flushed, detached e unreferenced usando uma página DMA.

Boot normal faz quatro ciclos.

Com graphics stress flag, são 1000 ciclos.

No final, live-resource count e free-descriptor count precisam retornar exatamente ao baseline.

Isso detecta leak de resources e descriptors.

## Teste de virtqueue

`tools/test_virtq.c` cria queue de oito descriptors e repete 1000 vezes o ciclo alloc de dois descriptors, publish, completion sintética e reclaim.

O teste escreve entries diretamente na used ring.

Após cada iteração, os oito descriptors precisam estar livres.

Também valida rejeição de queue size não power-of-two e de over-allocation.

É evidência forte do bookkeeping local independente de QEMU.

## Teste do resource pool

`tools/test_gpures.c` verifica IDs distintos, rejeição por owner incorreto, release e 1000 ciclos de resource/context alloc/free.

Os contadores finais precisam ser zero.

Isso valida bookkeeping local, não execução real do device.

## Driver educacional em ChrisC

`SYS/DRV/VIRTIOGPU.CC` contém uma versão menor escrita em ChrisC.

Ela localiza o mesmo PCI device e monta manualmente uma queue de quatro entries em DMA.

Cria resource 1, liga framebuffer backing, configura scanout e depois entrega o device à hardware gate.

É útil para estudar o protocolo com menos abstrações.

Porém, não é a implementação autoritativa do transport kernel atual.

O driver C possui queue management mais robusto, ownership, capsets, stress tests, cursor e error handling mais completo.

## Limitações de concorrência

Resource pools e transport globals não formam um subsistema multi-client totalmente concorrente.

Submission de control command é serializada por `g_busy`, mas o pool local não possui um protocolo amplo de locks para arbitrary parallel callers.

O uso esperado é sequência controlada pelo kernel/Gfx3D.

Um driver assíncrono futuro precisará locks explícitos, storage por request e dispatcher de completions por descriptor/fence.

## Contenção de falhas

Falha de encoder ocorre antes da submission.

Falha de descriptor, MMIO notify, used ID inválido, device error, fence mismatch e timeout retornam erro.

Algumas falhas graves marcam o transport como dead e fazem work futuro ser rejeitado.

Camadas superiores podem então degradar para software rendering.

O transport não trata timeout como sucesso.

## Limitações atuais

A busca PCI cobre faixa restrita.

A GPU queue é limitada a 16 descriptors apesar do helper permitir 128.

Control traffic usa um único par de staging command/response.

Completion é síncrona e baseada em polling.

Não há cancelamento de request, reset/recovery completo ou dispatcher assíncrono geral.

Pools de resources e contexts têm tamanho fixo.

Essas restrições são aceitáveis no kernel experimental atual, mas precisam estar explícitas antes de escalar a pilha.

## Testes futuros recomendados

São úteis testes para used IDs inválidos, wrap de avail/used além de 16 bits, falha forçada de MMIO notify, fence mismatch, queue sizes 2/4/16/128, conflitos de owner, boundaries de backing offset, troca repetida de scanout e timeout/recovery.

Um teste QEMU prolongado também deve confirmar que partial updates repetidos preservam descriptor count e resource count sem leak.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Split virtqueues, encoding do protocolo VirtIO-GPU e resource ownership são tratados como uma camada de transport abaixo de VirGL e da API Gfx3D.
