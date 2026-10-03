---
id: virtio-gpu-virgl
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/vgpu.c
  - kernel/gfx/vgpu.h
  - kernel/gfx/virtgpu_enc.c
  - kernel/gfx/virtgpu_enc.h
  - kernel/gfx/gpures.c
  - kernel/gfx/gpures.h
  - kernel/gfx/gfx3d.c
  - kernel/gfx/gfx3d.h
  - kernel/gfx/gfx3d_virgl.c
  - kernel/gfx/gfx3d_dev.h
  - kernel/gfx/gfx3d_batch.c
  - kernel/gfx/gfx3d_batch.h
  - kernel/gfx/virgl_cmd.c
  - kernel/gfx/virgl_cmd.h
  - kernel/gfx/virgl_obj.c
  - kernel/gfx/virgl_obj.h
  - kernel/gfx/virgl_demo.c
  - kernel/gfx/hwgate.c
  - tools/test_virgl_cmd.c
  - tools/test_gpures.c
  - tools/test_gfx3d_abi.c
  - tools/test_gfx3d_ctx.c
symbols:
  - vgpu_boot
  - vgpu_submit3d
  - vgpu_res_create_2d
  - vgpu_res_create_3d
  - vgpu_ctx_create
  - gfx3d_boot
  - gfx3d_mark_lost
  - gfx3d_dev_available
  - virgl_cmd_begin
  - virgl_cmd_end
  - virgl_demo_run
depends_on:
  - buses-mmio-dma
  - software-3d
related:
  - virtio-gpu-transport
  - gfx3d-api
  - virgl-command-stream
  - shaders-csir
---

# VirtIO-GPU e VirGL

## Escopo

O ChrisOS usa VirtIO-GPU como dispositivo gráfico paravirtual e VirGL como uma camada 3D opcional acima dele.

As duas camadas precisam ser tratadas separadamente.

VirtIO-GPU consegue fornecer scanout 2D, transferência de framebuffer e hardware cursor sem VirGL. VirGL exige negociação adicional de features, capsets, contexts, resources e command streams 3D.

A pilha atual pode ser representada por:

```text
applications / Gfx3D
        |
        v
API Gfx3D neutra de backend
        |
        +--> software backend
        |
        +--> VirGL backend
                 |
                 v
          VirGL command stream
                 |
                 v
          VirtIO-GPU SUBMIT_3D
                 |
                 v
        dispositivo virtual / host renderer
```

Esse caminho não é um driver físico para GPUs Intel, AMD ou NVIDIA.

## Descoberta do dispositivo

`vgpu_boot` percorre PCI buses 0 a 7 e devices 0 a 31, function zero.

O match atual é:

```text
vendor = 0x1AF4
device = 0x1050
```

que corresponde ao dispositivo VirtIO GPU PCI moderno esperado por esta implementação.

A busca é deliberadamente limitada. Ela não percorre toda topologia PCI possível nem todos os transports VirtIO.

Após encontrar o device, o ChrisOS habilita PCI memory space e bus mastering antes de processar as VirtIO PCI capabilities.

## VirtIO PCI capabilities

O driver percorre a lista de capabilities e procura vendor-specific capability ID 9.

Ele identifica regiões para:

- common configuration;
- notification configuration;
- ISR status;
- device-specific configuration.

Common e notify são obrigatórias neste caminho.

ISR e device-specific são usadas quando disponíveis.

Os BARs MMIO são mapeados pela camada genérica de hardware, ligando o driver às abstrações PCI/MMIO/DMA do kernel.

## Negociação de features

O device status é resetado e passa por ACKNOWLEDGE e DRIVER.

O driver lê os dois words de 32 bits de features.

O bit zero do word alto é obrigatório, correspondendo ao feature bit 32 do VirtIO moderno.

Sem ele, a negociação falha.

No word baixo, o driver pode solicitar:

```text
VGPU_F_VIRGL
VGPU_F_CONTEXT_INIT
```

VirGL só é pedido quando o boot permite 3D e o device anuncia a feature.

CONTEXT_INIT só é pedido quando VirGL já foi selecionado e a feature também existe no device.

## Fallback de FEATURES_OK

Depois de escrever as guest features, o driver marca FEATURES_OK.

Se o device não mantiver esse bit no status, o ChrisOS repete a negociação mantendo apenas o requisito moderno do VirtIO, sem features gráficas do word baixo.

Assim, uma combinação de VirGL rejeitada pode ainda resultar em um VirtIO-GPU 2D funcional.

Se a segunda tentativa também falhar, a inicialização do device termina.

## Configuração das virtqueues

A control queue usa índice 0.

A cursor queue usa índice 1 quando o common config informa pelo menos duas filas.

O driver tenta inicialmente:

```text
VGPU_QSZ = 16
```

descriptors.

Se o device oferece menos, escolhe uma das capacidades:

```text
16, 8, 4, 2
```

Menos de dois descriptors é rejeitado.

Cada fila é colocada em uma página DMA de 4 KiB.

Endereços de descriptors, avail e used são escritos no common config e a fila é então habilitada.

## Endereço de notification

O notify offset é calculado a partir do queue notification index e do notification multiplier do device.

Esse mecanismo pertence ao transport VirtIO, não ao formato VirGL.

VirGL não notifica o PCI BAR diretamente; seus comandos acabam passando pelo mesmo mecanismo de submission da control queue.

## Alocações DMA

Durante o boot são alocados buffers DMA dedicados para:

- command staging;
- response staging;
- backing do scanout principal.

Command e response usam quatro páginas cada.

O scanout usa:

```text
width * height * 4
```

bytes arredondados para páginas.

O caminho atual clampa width em 1920 e height em 1080.

## Resource 2D principal

Depois de configurar as filas, o driver cria um VirtIO-GPU 2D resource no formato B8G8R8A8.

Esse resource recebe backing no DMA do framebuffer e é configurado como scanout zero.

Isso estabelece uma distinção arquitetural importante: um desktop funcionando sobre VirtIO-GPU não prova que VirGL está ativo.

O scanout 2D é configurado antes da leitura de capsets VirGL e antes dos gates 3D.

## Flush 2D

`vgpu_flush_rect` limita o retângulo ao tamanho do framebuffer VirtIO e ao front buffer do ChrisOS.

Os pixels são copiados do front buffer software para o backing DMA.

O alpha é forçado para opaco.

Depois são enviados:

```text
TRANSFER_TO_HOST_2D
RESOURCE_FLUSH
```

para a região modificada.

A implementação mantém contadores de rectangles, pixels, bytes, full updates e partial updates.

## Hardware cursor

Quando a queue 1 existe, o driver pode usar um resource dedicado para o cursor.

O tamanho usado é 64×64, correspondente ao comportamento esperado no caminho QEMU atual.

O resource precisa passar por TRANSFER_TO_HOST_2D antes de UPDATE_CURSOR.

Quando o scanout muda, a geração do cursor é incrementada porque o host pode descartar o sprite anterior.

Se hardware cursor não funcionar, camadas superiores podem continuar com software cursor.

## Serialização de commands

O transport atual não mantém várias control submissions simultâneas do guest.

A flag global `g_busy` serializa commands.

Os bytes do command são copiados para um DMA compartilhado, um fence é criado e a request é enviada.

Esse desenho simplifica lifetime de DMA porque há um único par command/response reutilizado.

A consequência é que callers independentes não conseguem encher a virtqueue com várias requests concorrentes.

## Estrutura de descriptors

Uma submission normal usa dois descriptors:

1. command buffer legível pelo device;
2. response buffer gravável pelo device.

O primeiro aponta para o segundo.

Depois de publicar o head, o driver notifica o device e espera uma entry correspondente na used ring.

Os descriptors são reclamados após completion.

Falha ao obter a cadeia é considerada erro grave de queue.

## Fences

A pilha mantém `g_fence_seq`, incrementado a cada operação fenced.

Quando há fence, flag e valor de 64 bits são escritos no header.

A resposta precisa carregar o mesmo fence.

Mismatch de fence é erro explícito.

A camada de submission baixa controla a sequência efetiva usada pelo transport.

## Espera por completion

Existe handler de IRQ que contabiliza interrupts e faz acknowledge do ISR.

Mesmo assim, o completion normal dos commands é esperado por polling da used ring.

O loop usa limites de iteração e budgets baseados em TSC.

Há budgets fast e slow.

Criação de 3D resources, operações de context e SUBMIT_3D usam o caminho mais lento.

Se ocorrer timeout, o driver marca o device como dead, desativa live/online e registra erro.

## Validação da response

O driver verifica:

- descriptor usado correspondente;
- fence correto;
- response type diferente de zero;
- ausência de códigos de erro VirtIO-GPU;
- response type esperado para o command.

Os tipos esperados incluem OK_NODATA, OK_DISPLAY_INFO, OK_CAPSET_INFO e OK_CAPSET.

Portanto, completion de virtqueue sozinho não é considerado sucesso suficiente.

## Namespace de resources

IDs de VirtIO GPU resources são controlados por `GpuPool`.

Os limites atuais são:

```text
GPU_RES_MAX = 96
GPU_CTX_MAX = 16
```

Cada resource registra ID, owner, tipo 2D/3D, state, dimensões, format, bind flags, DMA backing e quantidade de contexts attached.

Cada context registra owner, capset e estado live.

As verificações de owner impedem que outro owner destrua um objeto através da API normal.

## Lifecycle de resource

Um resource com backing segue aproximadamente:

```text
alocar ID
  -> RESOURCE_CREATE_2D / RESOURCE_CREATE_3D
  -> RESOURCE_ATTACH_BACKING
  -> opcionalmente CTX_ATTACH_RESOURCE
  -> transfer / draw / scanout
  -> CTX_DETACH_RESOURCE
  -> RESOURCE_DETACH_BACKING quando aplicável
  -> RESOURCE_UNREF
  -> liberar entrada local
```

As etapas variam conforme o uso.

Alocação local e criação no device são tratadas como estados distintos.

## Criação de resource 3D

`vgpu_res_create_3d` codifica RESOURCE_CREATE_3D a partir de target, format, bind flags, dimensões e demais campos.

O resource recebe um ID local do pool.

Backing DMA pode ser ligado depois.

`vgpu_res_create_3d_off` permite que o backing comece em um offset dentro de um slab DMA compartilhado.

Isso é útil para buffers persistentes e caches.

## Criação de context

`vgpu_ctx_create` reserva um context ID e emite CTX_CREATE.

Se CONTEXT_INIT foi negociado e solicitado, os oito bits baixos do capset escolhido são usados no campo de context init.

O nome de debug enviado é "chrisos".

Destroy envia CTX_DESTROY antes de liberar a entrada local.

## Attach de resource ao context

CTX_ATTACH_RESOURCE exige que context e resource existam e tenham o mesmo owner.

Ao sucesso, um contador local de attachments é incrementado.

CTX_DETACH_RESOURCE faz a operação inversa e reduz o contador quando positivo.

Resource ID e context ID pertencem a namespaces separados.

## Capability sets

VirGL só é considerado utilizável quando a feature foi negociada e pelo menos um capset aceitável foi carregado.

O driver lê a quantidade de capsets anunciada no device config.

Valores acima de 16 são tratados defensivamente como inválidos neste caminho.

Somente:

```text
VGPU_CAPSET_VIRGL
VGPU_CAPSET_VIRGL2
```

são mantidos.

O cache local aceita até quatro capsets, cada um com no máximo 8192 bytes.

## Política de versão de capset

Capset com size acima de 8192 ou version zero é rejeitado.

Ao pedir os dados completos, o driver solicita no máximo version 2, mesmo se o device anunciar versão maior.

Isso limita explicitamente a superfície do protocolo ao que o código atual espera.

`vgpu_virgl_on` exige feature negociada e ao menos um capset local.

## Handles de objetos VirGL

Handles de VirGL são outro namespace.

Eles não são VirtIO resource IDs nem handles públicos do Gfx3D.

`VirglObjPool` suporta:

```text
VIRGL_OBJ_POOL_MAX = 256
```

objetos live.

Os tipos incluem surfaces, shaders, blend, depth/stencil, rasterizer, vertex elements, sampler state e sampler views.

O allocator evita zero e evita reutilizar um handle ainda live.

## Builder do command stream

`VirglCmd` grava dwords em storage fornecido pelo caller.

O header empacota opcode, object type e payload length.

`virgl_cmd_begin` registra o tamanho esperado.

`virgl_cmd_u32` recusa gravação além da capacidade ou além do tamanho declarado.

`virgl_cmd_end` exige que a quantidade exata de dwords tenha sido produzida.

Erro de size accounting não vira overflow silencioso do buffer.

## Famílias de commands implementadas

O builder suporta atualmente:

- create/destroy/bind de objects;
- framebuffer state;
- viewport;
- clear;
- blend state;
- depth/stencil state;
- rasterizer;
- vertex elements e vertex buffers;
- index buffer;
- draw VBO;
- shader create/bind/link;
- constant buffers;
- sampler state e sampler views.

É um subconjunto escolhido de VirGL/Gallium, não uma implementação completa de todos os commands possíveis.

## Batches

Um batch VirGL aceita:

```text
VIRGL_CMD_MAX = 1024 dwords
```

`Gfx3DBatch` usa o mesmo limite.

Quando um command futuro não cabe no espaço restante, a camada de batch pode fazer flush do stream atual com SUBMIT_3D e continuar em um buffer vazio.

Uma única operação que exigisse mais que o batch inteiro é rejeitada.

Assim, overflow não é resolvido escrevendo além do array.

## SUBMIT_3D

`vgpu_submit3d` envolve o array de dwords dentro de um command VirtIO-GPU SUBMIT_3D.

Ele exige context não zero, buffer de dwords válido, device online e transport não busy.

A operação usa fence e o budget lento de completion.

A response esperada é OK_NODATA.

Timeout ou response inesperada geram erro.

## Abstração Gfx3D

`gfx3d.c` fornece a API neutra acima dos backends.

Os modos incluem:

```text
GFX3D_SOFTWARE
GFX3D_VIRGL
GFX3D_MOCK
GFX3D_AUTO
```

AUTO escolhe VirGL apenas quando `gfx3d_dev_available` confirma o backend.

A disponibilidade exige VirtIO-GPU ready, VirGL/capsets ativos e capset aceitável.

Caso contrário, AUTO usa software.

## Recuperação quando VirGL é perdido

`gfx3d_mark_lost` marca VirGL como perdido e grava diagnóstico.

Se VirGL não foi explicitamente forçado, Gfx3D muda para software e atualiza estatística de degraded mode.

Se o modo foi forçado para VirGL, o estado permanece como virgl-lost, em vez de esconder o problema trocando silenciosamente de backend.

Isso diferencia operação automática de modo diagnóstico.

## Backend VirGL do Gfx3D

`gfx3d_virgl.c` converte operações da API neutra em VirtIO/VirGL.

Ele gerencia contexts de device, color/depth targets, buffers, textures, shader objects e batches por frame.

Targets possuem resources 3D separados para color e depth.

Buffers podem usar backing compartilhado.

Uma texture possui resource e sampler-view object.

## Readback

Para validar pixels no CPU, o backend usa TRANSFER_FROM_HOST_3D sobre o color resource.

Depois o backing é copiado para o destination CPU.

Readback é mais caro que manter o resultado no caminho GPU/host, mas permite validar de fato a imagem.

Uma response OK_NODATA sem pixels corretos não basta como prova de rendering.

## Apresentação por scanout

Para apresentar sem readback, o color resource renderizado pode ser configurado diretamente como scanout zero via SET_SCANOUT, seguido de RESOURCE_FLUSH.

Assim, readback não precisa ser o caminho de presentation final.

Trocar o scanout pode exigir reenvio do cursor, comportamento acompanhado pela geração de cursor da camada inferior.

O desktop pode depois restaurar o resource 2D principal.

## Política de boot

`vgpu_boot` monta primeiro o caminho 2D.

Depois executa um stress test de lifecycle de 2D resources.

Sem o boot flag de stress, são quatro ciclos.

Com stress habilitado, são 1000.

Se VirGL não foi negociado ou software 3D foi explicitamente solicitado, VirtIO-GPU 2D continua ativo e o backend 3D é software.

## Gate VirGL no boot

Quando VirGL é permitido, o boot lê capsets, inicia Gfx3D e executa `virgl_demo_run`.

Esse demo é um gate de validação, não apenas uma cena visual.

Ele executa cycles de contexts/resources, cria objetos persistentes, compila e linka shaders e verifica pixels resultantes.

Falha marca VirGL como lost e faz fallback automático para software quando o modo não foi forçado.

## Workloads de prova

O gate cobre, entre outros:

- create/destroy de contexts;
- attach/detach/unref de 3D resources;
- clear;
- triangle;
- depth;
- indexed cube;
- textured cube;
- varying interpolation;
- lighting;
- troca de shader/program;
- persistência de mesh;
- lit textured mesh;
- presentation por scanout.

Com stress boot flag, quantidades de lifecycle cycles são aumentadas.

A validação é mais forte que apenas aceitar commands porque também inspeciona pixels após readback.

## Testes host

`tools/test_virgl_cmd.c` valida encoders sem um GPU virtual.

Ele testa overflow do command buffer, words exatos de clear, handles inválidos, RESOURCE_CREATE_3D, CTX_CREATE, CTX_ATTACH_RESOURCE, SUBMIT_3D e destroy de objeto.

`tools/test_gpures.c` testa ownership e ciclos repetidos de alloc/free de resources e contexts.

`tools/test_gfx3d_abi.c` cobre gerações de public handles, exaustão/liberação do pool VirGL, batch rollover, ABI de shaders/matrizes, software fallback e lifecycle repetido de objetos Gfx3D.

São testes host de protocolo e ABI. Eles não provam que QEMU e virglrenderer executaram os commands 3D.

## Fronteira da evidência em QEMU

O gate de boot VirGL só roda quando o device virtual e seu caminho VirGL estão presentes.

Isso valida o caminho ChrisOS -> VirtIO-GPU -> VirGL/virglrenderer no ambiente virtual configurado.

Se o OpenGL do host estiver usando llvmpipe, a evidência continua sendo válida para o caminho virtual VirGL, mas não prova aceleração por GPU física.

Essa distinção deve permanecer explícita.

## Limitações atuais

A busca PCI é restrita.

As control submissions são serializadas globalmente por um único command/response staging.

Completion é esperado por polling mesmo existindo contabilidade de interrupts.

Somente um subconjunto de commands VirGL e versões de capset é aceito.

Pools possuem capacidade fixa.

O alvo é VirtIO-GPU/VirGL virtual, não hardware gráfico vendor-specific físico.

Mine Chris não deve ser descrito como GPU accelerated apenas porque o boot proof VirGL passa, a menos que seu caminho real de renderização esteja usando Gfx3D/VirGL.

## Ordem de debugging

Se 2D falha, investigue PCI capabilities, feature negotiation, virtqueue, DMA backing e scanout antes de VirGL.

Se 2D funciona mas o backend 3D cai para software, verifique VIRGL feature, capsets e o gate de boot.

Se SUBMIT_3D responde com sucesso mas os pixels estão errados, investigue attachments, framebuffer/depth resources, shaders, uniforms, viewport e readback.

Se o transport entra em timeout, trate o device como lost e use o log da última operação, context, resource, fence e response para localizar o ponto de falha.

## Nota de revisão

Este capítulo foi reconciliado com a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. VirtIO-GPU 2D e VirGL 3D são documentados como camadas separadas, com a API Gfx3D e o gate de validação acima delas.
