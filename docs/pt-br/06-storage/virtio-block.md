---
id: virtio-block
lang: pt-br
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/virtio_blk.h
  - kernel/fs/virtio_blk.c
  - kernel/fs/block_device.h
  - kernel/fs/bdev.h
  - kernel/fs/bdev.c
  - kernel/fs/storage.c
  - kernel/gfx/hwgate.h
  - kernel/gfx/hwgate.c
  - kernel/metal/pci.c
  - scripts/qemu.mk
symbols:
  - Vblk
  - virtio_blk_probe
  - kick
  - vblk_rw
  - vblk_read
  - vblk_write
  - hw_bar_map
  - hw_dma_alloc
  - hw_dma_w32
  - hw_dma_r32
  - bd_add_kind
depends_on:
  - block-storage
  - buses-mmio-dma
  - pci-pcie
  - physical-memory
related:
  - nvme
  - usb-storage
  - partitions-gpt
  - chrisfs
---

# VirtIO Block

## Escopo

O ChrisOS implementa um driver VirtIO Block compacto para devices PCI. O caminho atual usa o modelo moderno de capabilities VirtIO PCI, negocia somente `VIRTIO_F_VERSION_1`, configura uma split virtqueue com quatro descriptors, monta uma cadeia fixa de três descriptors, transfere dados por uma única página DMA de 4 KiB, notifica a queue 0 pela capability de notification e faz polling do used ring para detectar completion.

A implementação foi mantida pequena para deixar os mecanismos do transporte visíveis: descoberta de capabilities PCI, common configuration, feature negotiation, layout da split ring, direção dos descriptors, índices avail/used, device configuration, request status e ownership de DMA.

Ela não é uma stack VirtIO Block completa. Há um único device global, uma queue, um request in-flight, sem completion por interrupção, sem packed ring, sem indirect descriptors, sem discard/write-zeroes, sem flush explícito, sem multiqueue, sem queue reset e sem recovery robusto depois de timeout ambíguo.

Este capítulo documenta a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![Capabilities PCI, split virtqueue e cadeia de request VirtIO Block no ChrisOS](../../assets/diagrams/virtio-block-path-pt-br.svg)

## Posição na stack de armazenamento

VirtIO Block é registrado pelo mesmo contrato `BlockDevice` usado por ATA, AHCI, NVMe e USB storage:

~~~text
ChrisFS / GPT / storage genérico
        -> BlockDevice
        -> vblk_read / vblk_write
        -> vblk_rw
        -> kick
        -> cadeia de descriptors da split virtqueue
        -> device VirtIO Block
        -> used ring + status byte
~~~

`storage_init` testa VirtIO Block depois de NVMe e antes de USB mass storage. Um probe bem-sucedido registra um device writable chamado `virtio-blk` com kind `BD_VIRTIO`.

A seleção de root ocorre posteriormente na lógica genérica de storage. O transporte não escolhe diretamente o filesystem root.

## Identificação do device

O probe percorre PCI buses 0 a 7, devices 0 a 31 e functions 0 a 7.

Ele exige o vendor ID VirtIO:

~~~text
0x1AF4
~~~

e aceita dois device IDs de block device:

~~~text
0x1042
0x1001
~~~

`0x1042` corresponde ao device ID moderno de VirtIO Block PCI. `0x1001` é o ID histórico transitional.

Entretanto, a implementação **não** contém um transporte VirtIO PCI legacy baseado em I/O ports. Mesmo quando o ID transitional é aceito, o driver continua exigindo as capabilities modernas vendor-specific do VirtIO PCI. Um device transitional sem essas capabilities não inicializa por este caminho.

O PCI command register recebe `| 6`, habilitando memory decoding e bus mastering.

## Capabilities modernas VirtIO PCI

O driver inicia no ponteiro da PCI capability list, no offset `0x34`.

Ele percorre a lista encadeada de capabilities e procura PCI capability ID 9, a capability vendor-specific usada pelo transporte VirtIO PCI moderno.

Para cada capability VirtIO, o byte 3 do header é interpretado como `cfg_type`. O ChrisOS reconhece:

| cfg_type | Significado | Necessário no driver atual |
|---:|---|---|
| 1 | Common configuration | sim |
| 2 | Notification configuration | sim |
| 3 | ISR status | opcional |
| 4 | Device-specific configuration | sim |

Para cada capability reconhecida, o código lê o BAR, o configuration offset, mapeia o BAR correspondente com `hw_bar_map` e guarda a janela MMIO mais o offset.

Na capability de notification, tipo 2, também é lido `notify_off_multiplier`.

O driver exige common, notify e device configuration. A capability ISR é opcional.

### Limites do parser de capabilities

O parser atual é pragmático e não defensivo. Ele não valida completamente o tamanho da capability VirtIO nem o tamanho da região anunciada, e não possui limite explícito de iterações ou cycle detection para uma PCI capability list malformada.

Os acessos MMIO continuam passando pela abstração limitada de `hw_bar_map`, mas os metadados da capability VirtIO não são completamente validados.

## Reset e sequência de status

O byte `device_status` da common configuration fica no offset 20.

O ChrisOS grava a sequência:

~~~text
0   RESET
1   ACKNOWLEDGE
3   ACKNOWLEDGE | DRIVER
~~~

Depois negocia features, grava:

~~~text
11  ACKNOWLEDGE | DRIVER | FEATURES_OK
~~~

e verifica se o bit 3, `FEATURES_OK`, continua ativo.

Depois da configuração da queue, grava:

~~~text
15  ACKNOWLEDGE | DRIVER | FEATURES_OK | DRIVER_OK
~~~

Essa é a progressão esperada de alto nível para inicialização VirtIO.

O driver não seta `FAILED` quando uma etapa posterior falha, e alguns rejection paths continuam o scan PCI sem resetar completamente o device candidato.

## Feature negotiation

O driver seleciona a feature page 1:

~~~text
device_feature_select = 1
driver_feature_select = 1
~~~

e grava um único bit no driver feature field:

~~~text
driver_feature = 1
~~~

Na page 1, bit 0 representa feature bit 32:

~~~text
VIRTIO_F_VERSION_1
~~~

Nenhuma feature específica de VirtIO Block da low page é negociada.

Um detalhe importante é que o ChrisOS não lê `device_feature` antes de escrever a feature escolhida. Em vez disso, depende do retorno de `FEATURES_OK` para rejeitar uma negociação incompatível. Devices VirtIO modernos devem oferecer VERSION_1, então isso funciona no QEMU validado, mas fazer a interseção explícita das features oferecidas seria mais correto e claro.

Como nenhuma feature específica de bloco é negociada, o driver não ativa flush, discard, write zeroes, topology, configurable block size, size/segment limits ou multiqueue.

## Seleção e tamanho da queue

O ChrisOS usa queue 0, a request queue do VirtIO Block em configuração single-queue:

~~~text
queue_select = 0
~~~

O código lê `queue_size` e exige pelo menos quatro entries.

Depois programa:

~~~text
queue_size = 4
~~~

A cadeia fixa precisa de três descriptors, mas queue size quatro mantém uma ring pequena e válida.

O driver não verifica se a queue já estava enabled, não oferece queue reset e não configura MSI-X vector.

## Layout da split ring em uma página

Toda a virtqueue fica em uma única página DMA de 4096 bytes, referenciada por `g_blk.q`.

O ChrisOS usa offsets fixos:

~~~text
0x000  descriptor table
0x040  available ring
0x800  used ring
~~~

Para queue size quatro:

- descriptor table consome 4 × 16 = 64 bytes;
- available ring começa no byte 64;
- used ring é colocado no byte 2048.

Os endereços físicos programados na common configuration são:

~~~text
queue_desc   = q + 0
queue_driver = q + 64
queue_device = q + 2048
~~~

As partes altas de 32 bits também são escritas.

Depois, o driver seta:

~~~text
queue_enable = 1
~~~

O layout é intencionalmente esparso. Ele desperdiça parte da página, mas deixa descriptor table, avail e used rings claramente separados e fáceis de inspecionar.

## Endereço de notification

Depois de selecionar queue 0, o driver lê `queue_notify_off`.

O endereço efetivo de notification é:

~~~text
notify_cfg_offset
+ queue_notify_off * notify_off_multiplier
~~~

O resultado é guardado em `g_blk.noff`.

Cada request é submetido por uma escrita de 16 bits com queue index 0 nesse endereço.

O driver não negocia `VIRTIO_F_NOTIFICATION_DATA`, portanto o formato simples baseado no índice da queue é o utilizado.

## Capability ISR opcional

Quando existe uma capability tipo 3, o ChrisOS guarda a janela MMIO e o offset do ISR.

Mesmo assim, o request path continua baseado em polling. O byte ISR é lido somente depois de sucesso ou timeout. A leitura do VirtIO ISR status limpa o estado pendente, funcionando como acknowledge.

Os bits do ISR não são interpretados e não dirigem a completion.

## Device configuration e capacidade

A device-specific configuration do VirtIO Block começa com uma capacidade de 64 bits expressa em setores de 512 bytes.

O ChrisOS lê:

~~~text
capacity_low
capacity_high
~~~

Se os 32 bits altos forem diferentes de zero, imprime:

~~~text
virtio-blk too large
~~~

e rejeita o device.

Assim, a capacidade exposta fica limitada ao sector count de 32 bits do `BlockDevice`. Com setores de 512 bytes, o limite é aproximadamente 2 TiB.

O driver também rejeita devices menores que 2048 setores.

A leitura da device config não usa um loop com `config_generation`. Se uma mudança de configuração ocorrer entre as duas leituras de 32 bits da capacidade, o snapshot pode ficar inconsistente.

## Estado do driver

A estrutura global `Vblk` contém:

| Campo | Significado |
|---|---|
| `cwin`, `coff` | localização MMIO da common configuration |
| `nwin`, `noff` | localização MMIO de notification |
| `isr_win`, `isr_off` | localização opcional do ISR |
| `isr_ok` | informa se capability ISR existe |
| `q` | página DMA com a split virtqueue |
| `cmd` | página DMA com request header e status |
| `data` | página DMA do payload |
| `avail` | índice available de 16 bits |
| `sectors` | capacidade exposta |

Existe um único `g_blk` global e uma flag global de ready. Depois do primeiro registro bem-sucedido, probes posteriores retornam imediatamente.

## Alocações DMA

Três páginas físicas contíguas são usadas:

- `q`: estruturas da virtqueue;
- `cmd`: request header e status byte;
- `data`: bounce buffer do payload.

Todas são alocadas por `hw_dma_alloc(1)`, podendo ficar acima de 4 GiB. Os descriptors e registradores da common config usam os 64 bits completos dos endereços físicos.

Se uma das três alocações iniciais falha, o driver tenta liberar os IDs já obtidos.

Falhas posteriores não executam cleanup de forma consistente.

## Header do request VirtIO Block

Cada operação usa o request header no offset 0 da página `cmd`.

O ChrisOS grava quatro valores de 32 bits:

~~~text
offset 0   type
offset 4   reserved = 0
offset 8   sector low 32 bits
offset 12  sector high 32 bits = 0
~~~

O tipo é:

~~~text
0  VIRTIO_BLK_T_IN   // read
1  VIRTIO_BLK_T_OUT  // write
~~~

O campo sector do protocolo VirtIO Block usa unidades de 512 bytes.

Os 32 bits altos ficam zero porque a block API do ChrisOS usa LBA de 32 bits.

## Cadeia fixa de três descriptors

Cada request usa descriptor IDs 0, 1 e 2.

### Descriptor 0 — request header

Descriptor 0 aponta para os 16 bytes do header na página `cmd`.

As flags contêm:

~~~text
VRING_DESC_F_NEXT
~~~

e `next = 1`.

O device lê esse descriptor.

### Descriptor 1 — data buffer

Descriptor 1 aponta para a página `data`.

Em write, o device lê memória do guest, então as flags contêm apenas:

~~~text
VRING_DESC_F_NEXT
~~~

Em read, o device precisa escrever no guest, então:

~~~text
VRING_DESC_F_NEXT | VRING_DESC_F_WRITE
~~~

Nos dois casos, `next = 2`.

### Descriptor 2 — status byte

Descriptor 2 aponta para `cmd + 32`, com tamanho de um byte.

A flag é:

~~~text
VRING_DESC_F_WRITE
~~~

porque o device escreve o status da operação.

O driver inicializa o status com `0xFF`.

O valor esperado para sucesso é zero.

## Publicação no available ring

O available ring começa no offset 64 da página da queue.

O driver sempre publica descriptor head 0. As ring entries começam zeradas pela alocação da página e o código também grava zero no offset 68.

A cada request:

1. `g_blk.avail` é incrementado como valor de 16 bits;
2. o novo índice é copiado para `idx`;
3. flags/index do avail ring no offset 64 recebem `idx` nos 16 bits altos;
4. queue 0 é notificada.

Como todas as entries da avail ring apontam para descriptor head 0, a cadeia fixa pode ser reutilizada após cada completion síncrona.

O driver não usa `EVENT_IDX`, indirect descriptors, packed ring nem mecanismos avançados de suppression.

## Completion pelo used ring

O used ring começa no offset 2048.

O ChrisOS lê o primeiro dword e interpreta os 16 bits altos como `used.idx`.

Um request só é considerado concluído com sucesso quando:

~~~text
used.idx == submitted_idx
and
status_byte == 0
~~~

Com apenas um request outstanding, esse critério funciona para o happy path atual.

O driver não valida o descriptor ID contido no used element e também não usa o length do used element em sucesso normal.

## Problema concreto de classificação de erro

VirtIO Block possui status não zero para erros, incluindo I/O error e unsupported.

O loop atual de `kick` espera especificamente:

~~~text
used.idx == idx && status == 0
~~~

Se o device avança `used.idx` mas grava status não zero, o ChrisOS **não** retorna erro de I/O imediatamente. Ele continua esperando até terminar o orçamento finito de polling e então retorna timeout.

Consequentemente alguns erros reais do device são classificados como:

~~~text
BD_ETIMEOUT
~~~

em vez de:

~~~text
BD_EIO
~~~

Embora `vblk_rw` contenha uma branch genérica para erro diferente de timeout, o `kick` atual retorna na prática apenas sucesso ou timeout.

O tratamento correto deve separar "request completou" de "request completou com sucesso" e mapear o status explicitamente.

## Estratégia de polling e yield específico do QEMU

A completion possui duas fases de espera.

Primeiro são feitas até 2000 iterações de polling apertado.

Se a completion ainda não chegou, o código executa até 4096 iterações adicionais. Em cada uma chama:

~~~text
serial_putc(0)
~~~

antes de verificar novamente o used ring.

O comentário no source explica a motivação: writes no QEMU terminam em uma I/O thread e a operação serial força saída do caminho TCG tempo suficiente para essa thread executar. Um orçamento menor de yields falhava quando o host estava ocupado.

Esse comportamento é um workaround específico do ambiente QEMU/TCG validado. Não é um mecanismo portátil de sincronização VirtIO.

Em hardware físico ou em outro hypervisor, atividade serial não deveria ser requisito para progresso de block I/O.

## Diagnóstico de timeout

Se as duas fases de polling expirarem, o driver opcionalmente lê o ISR, imprime diagnóstico e retorna `-2`.

O log inclui:

- valor bruto do header do used ring;
- length do primeiro used element;
- status byte atual.

`vblk_rw` converte `-2` para `BD_ETIMEOUT`.

O timeout não reseta o device, não reseta a queue, não revoga endereços DMA e não prova que o request antigo deixou de poder concluir depois.

Assim, reutilizar a cadeia fixa e a página de dados após timeout ambíguo não possui um protocolo completo de recovery de ownership.

## Tamanho de transferência

A página de payload tem 4096 bytes.

Com setores de 512 bytes:

~~~text
4096 / 512 = 8 setores
~~~

`vblk_rw` limita cada request a oito setores. Operações maiores são divididas em múltiplas submissões sequenciais.

Para `N` setores:

~~~text
ceil(N / 8)
~~~

submissões são necessárias aproximadamente.

Não há scatter/gather adicional para expandir o payload além da página única.

## Caminho de read

Em read, descriptor 1 é marcado como device-writable.

Depois de completion com sucesso, `vblk_rw` copia a página DMA para o buffer do caller com `hw_dma_r32` e separação em bytes.

A transferência do device é DMA, mas o caminho não é zero-copy. O custo de cópia da CPU continua `O(n)`.

## Caminho de write

Em write, bytes do caller são primeiro empacotados em palavras de 32 bits e copiados para a página DMA.

Descriptor 1 é somente device-readable, a queue é notificada e o driver espera sincronamente.

O `BlockDevice` é registrado com:

~~~text
flush = 0
~~~

Nenhum `VIRTIO_BLK_T_FLUSH` é emitido e a feature correspondente não é negociada. O helper genérico `bd_flush` trata callback ausente como sucesso.

Portanto, o backend atual não fornece uma persistence barrier explícita para garantias de durability do filesystem.

## Read-only e outras features de bloco

Como somente VERSION_1 é negociada, o ChrisOS não examina nem aceita features específicas do block device.

Uma consequência é que o driver registra sempre:

~~~text
writable = 1
~~~

sem avaliar a feature de read-only.

Um device efetivamente read-only pode aparecer como writable para o block registry e rejeitar a operação somente quando o request for enviado.

Outros comportamentos ausentes por falta de feature negotiation incluem:

- flush;
- configurable block size;
- limites de segmentos/request;
- topology;
- discard;
- write zeroes;
- multiqueue.

## Ordenação de memória

A operação de virtqueue requer ordering entre:

1. escrita dos descriptors e buffers;
2. publicação do available index;
3. notification do device;
4. observação do used index e do status.

O driver atual não contém memory barriers VirtIO explícitas entre essas etapas.

O ambiente x86/QEMU validado é relativamente tolerante devido a DMA coerente e ordering mais forte da CPU. Esse resultado não deve ser extrapolado para arquiteturas weakly ordered ou ambientes não coerentes.

Uma implementação portátil deve tornar explícitas as producer/consumer barriers exigidas pelo protocolo.

## Concorrência e ownership

O driver possui um único:

- queue page;
- request page;
- data page;
- avail index.

Não há lock no driver.

Callers concorrentes poderiam sobrescrever descriptors, request header, payload e índices enquanto uma operação anterior ainda estivesse ativa.

O invariante necessário é, portanto, um request por vez.

VirtIO suporta muito mais concorrência; essa restrição pertence ao driver atual.

## Lifetime de recursos durante o probe

Falha de alocação inicial é tratada liberando as páginas queue, command e data.

Depois que as alocações existem, alguns rejection paths continuam sem cleanup. Exemplos:

- queue size inferior a quatro;
- capacity acima do limite de 32 bits;
- capacity abaixo do mínimo aceito.

O device também pode já ter chegado a `FEATURES_OK` ou possuir queue configurada quando o probe é abandonado.

Não há reset completo do device nem liberação consistente de DMA em todos esses caminhos.

Hoje o leak é limitado, mas deve ser corrigido antes de suportar vários devices ou probes repetidos.

## Outras limitações do transporte

A implementação atual não:

- valida completamente lengths das capabilities;
- protege contra PCI capability list cíclica;
- negocia features da low page;
- lê features oferecidas antes de escrever as escolhidas;
- usa MSI-X;
- faz completion orientada a interrupção;
- interpreta bits do ISR;
- trata device configuration change;
- usa `config_generation` para snapshot consistente;
- usa indirect descriptors;
- usa packed virtqueues;
- negocia `EVENT_IDX`;
- suporta múltiplas request queues;
- suporta queue reset;
- seta `FAILED` ao abandonar inicialização;
- implementa teardown completo.

São limites do ChrisOS atual, não do protocolo VirtIO.

## Segurança e privilégio

VirtIO PCI exige configuração PCI privilegiada, MMIO e bus-master DMA.

O device recebe endereços físicos da queue, do request header e do data buffer. O ChrisOS atual não restringe o device em um domínio IOMMU.

Proteções presentes:

- MMIO por janelas com bounds;
- páginas DMA pertencentes ao kernel;
- endereços DMA de 64 bits;
- bounds de LBA na block layer;
- payload máximo de uma página;
- polling finito.

Faltam isolamento por IOMMU, mapping DMA por request, memory barriers explícitas, locking e teardown robusto após timeout.

## Características de desempenho

O driver privilegia transparência do protocolo, não throughput.

Principais limitações:

- uma request queue;
- queue size quatro;
- um request outstanding;
- payload máximo 4 KiB;
- polling síncrono;
- bounce copies pela CPU;
- sem indirect descriptors;
- sem multiqueue;
- sem batching;
- sem sleep/wakeup por IRQ;
- yield por serial no slow path de QEMU.

VirtIO Block pode escalar muito além desse desenho com multiqueue e cadeias maiores.

## Evidência de validação

`scripts/qemu.mk` define o gate `test-qemu-vblk`.

O teste cria uma imagem de 32 MiB e conecta:

~~~text
-device virtio-blk-pci,drive=vblk
~~~

O gate exige:

~~~text
virtio-blk sectors=
bdev rw ok virtio-blk
~~~

`bdev_rw_tests` exercita o último setor de cada block device writable que não seja root:

1. lê o setor original;
2. escreve um pattern determinístico;
3. lê novamente;
4. compara os 512 bytes;
5. restaura os dados originais.

Como o disco IDE comum permanece root, o VirtIO Block participa diretamente desse round trip.

Esse teste valida, no device PCI do QEMU usado pelo projeto, discovery de capabilities, feature negotiation, configuração de queue, notification, direção dos descriptors, DMA de payload, completion no used ring e status de request em read e write.

O source também contém gate RISC-V usando `virtio-blk-device`, mas isso por si só não prova que exatamente este transporte PCI seja o código exercitado naquele caso. A evidência direta para o driver deste capítulo é `test-qemu-vblk`.

## Limitações atuais

Na revisão documentada, o VirtIO Block do ChrisOS possui:

- um único device registrado;
- transporte baseado em capabilities modernas PCI, apesar de aceitar IDs modern e transitional;
- somente queue 0;
- somente split ring;
- queue size quatro;
- um request outstanding;
- cadeia fixa 0 → 1 → 2;
- um payload buffer de 4 KiB;
- máximo de oito setores de 512 bytes por request;
- polling síncrono;
- ISR opcional apenas para acknowledge, não para completion;
- somente `VIRTIO_F_VERSION_1` negociada;
- nenhuma feature específica de bloco;
- sem flush explícito;
- writable flag sem tratamento da feature read-only;
- sem discard e write zeroes;
- sem multiqueue;
- sem indirect descriptors;
- sem packed ring;
- sem VirtIO memory barriers explícitas;
- status de erro do device podendo ser classificado como timeout;
- sem recovery robusto após timeout;
- sem locking;
- sector count de 32 bits, limitando a capacidade a aproximadamente 2 TiB;
- sem consistency loop com config generation;
- cleanup/reset incompleto em failed probes;
- validação centrada no QEMU em vez de múltiplos hypervisors ou ambientes físicos.

## Fronteira de roadmap

Uma implementação mais completa pode negociar a interseção real de features, mapear status não zero imediatamente para block errors, adicionar memory barriers explícitas, implementar `FLUSH`, respeitar read-only e block-size features, usar indirect descriptors e requests maiores, adicionar multiqueue, MSI-X e completion orientada a interrupção, aplicar config-generation retry loops, implementar queue reset/teardown completo, isolar DMA com IOMMU e validar em outros hypervisors.

Esses recursos permanecem roadmap até existirem no source e possuírem testes reproduzíveis.

## Mapa de source e revisão

`kernel/fs/virtio_blk.c` implementa discovery PCI, status/feature setup VirtIO, configuração da queue, construção de requests, notification, polling e adaptação à block layer. `kernel/fs/virtio_blk.h` expõe o probe. `kernel/gfx/hwgate.c` fornece MMIO e DMA. `kernel/fs/block_device.h`, `kernel/fs/bdev.h` e `kernel/fs/bdev.c` definem e registram a interface comum. `kernel/fs/storage.c` integra o device à descoberta genérica e aos testes de I/O. `scripts/qemu.mk` define o gate QEMU dedicado.

Todas as afirmações sobre comportamento atual neste capítulo foram reconciliadas com ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
