---
id: virtio-net
lang: pt-br
type: technical-chapter
volume: 10-networking
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/net/virtio_net.c
  - kernel/net/virtio_net.h
  - kernel/metal/pci.c
  - kernel/metal/pci.h
  - kernel/metal/pmm.h
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/port.c
  - kernel/metal/port.h
  - kernel/metal/start.c
  - makefile
symbols:
  - virtio_net_init
  - virtio_net_poll
  - virtio_net_tx
  - virtio_process_rx
  - virtio_setup_rx
  - virtio_setup_tx
  - vq_setup_page
  - pci_find_virtio_net
depends_on:
  - buses-mmio-dma
related:
  - network-stack
  - ethernet
  - interrupts-smp
---

# VirtIO-net

## Escopo

ChrisOS usa atualmente um único transporte PCI VirtIO-net em estilo legacy como seu único caminho de device de rede implementado.

O driver é deliberadamente pequeno. Ele executa:

- descoberta PCI por configuration I/O ports;
- negociação legacy de features VirtIO;
- alocação e attach de uma receive virtqueue e uma transmit virtqueue;
- oito receive buffers postados;
- um transmit buffer reutilizável;
- polling dos used rings;
- entrega síncrona de frames Ethernet para `net_rx_ethernet`.

Não há modern VirtIO PCI capability transport, multiqueue, mergeable receive buffers, checksum offload, segmentation offload, MSI/MSI-X, controle de filtros ou ownership TX assíncrono.

Este capítulo documenta o transporte e o modelo de memória exatamente como implementados.

## Descoberta PCI

`pci_find_virtio_net` percorre somente o PCI bus zero:

```text
bus  0
slot 0..31
func 0..7
```

Configuration space é lido pelo mecanismo clássico 0xCF8/0xCFC.

O vendor precisa ser:

```text
0x1AF4
```

e o device ID precisa ser:

```text
0x1000
0x1041
```

O match do ID, por si só, não significa suporte a qualquer variante de transporte associada a esses IDs.

## Requisito de I/O legacy

Depois de encontrar vendor/device compatível, o helper PCI habilita:

```text
PCI command bit 0 -> I/O space
PCI command bit 2 -> bus master
```

Depois lê BAR0 e exige bit zero indicando I/O BAR.

O I/O base é:

```text
BAR0 & 0xFFFC
```

Memory BAR é rejeitado.

Portanto, o driver real depende do layout legacy por port I/O mesmo aceitando dois device IDs.

Um device modern capability-only sem I/O BAR compatível não é suportado.

## Limitações do scan PCI

A busca não percorre buses além do zero.

Também interrompe o loop de functions quando encontra vendor 0xFFFF.

Não existe bridge traversal, ECAM, capability walk PCIe ou enumeração geral reutilizada por esse driver.

Isso atende a topologia QEMU atual, não PCI arbitrário.

## Mapa de registradores legacy

O driver usa offsets relativos ao I/O base:

```text
+0   host features
+4   guest features
+8   queue PFN
+12  queue size
+14  queue select
+16  queue notify
+18  device status
+19  ISR
+20  device-specific configuration
```

Todos os accesses usam `inb/inw/inl` e `outb/outw/outl`.

Não há MMIO nesse path.

## Sequência de status

A negociação começa escrevendo zero em device status.

Depois adiciona:

```text
ACKNOWLEDGE
DRIVER
```

Após escolher features, configura FEATURES_OK e lê o status de volta.

Se FEATURES_OK não permanecer setado, grava VIRTIO_FAILED e aborta.

Depois de RX/TX queues prontas, adiciona DRIVER_OK.

A flag interna `ready` só vira um ao fim dessa sequência.

## Features negociadas

ChrisOS lê os 32 bits de host features e aceita somente:

```text
VIRTIO_NET_F_MAC
VIRTIO_NET_F_STATUS
```

Todas as demais são descartadas.

Não negocia checksum offload, guest checksum, mergeable buffers, indirect descriptors, event index, multiqueue, TSO/UFO, MAC control ou VERSION_1.

O conjunto pequeno mantém o packet format simples.

## Assumption sobre MAC

Depois da negociação, `virtio_read_mac` lê incondicionalmente seis bytes da configuração do device começando em +20.

Isso acontece mesmo se o host não tiver anunciado `VIRTIO_NET_F_MAC`.

No QEMU atual espera-se que a feature esteja presente.

Como contrato genérico, ausência da feature deveria ser tratada explicitamente.

## Link status

Se o host anuncia `VIRTIO_NET_F_STATUS`, o código escreve `VIRTIO_NET_S_LINK_UP` no field em +26.

A implementação atual trata esse campo como algo configurável.

Depois do init não existe state machine que use mudanças de link para bloquear TX/RX ou notificar sockets.

Não há tratamento de carrier down/up.

## Seleção das queues

Queue zero é RX.

Queue um é TX.

Para cada queue:

1. escreve queue index em QUEUE_SEL;
2. lê QUEUE_NUM;
3. exige ao menos oito entries;
4. aloca páginas físicas contíguas suficientes para o ring;
5. grava PFN físico em QUEUE_PFN.

A camada de software só provisiona oito RX descriptors mesmo quando o device anuncia queue maior.

## Layout do ring

Cada queue contém:

- descriptor table;
- available ring;
- used ring.

Cada descriptor possui:

```text
64-bit address
32-bit length
16-bit flags
16-bit next
```

O cálculo é:

```text
desc_bytes  = queue_size * 16
avail_bytes = 4 + queue_size * 2
used_offset = align_up(desc_bytes + avail_bytes, 4096)
used_bytes  = 4 + queue_size * 8
```

O used ring começa no próximo boundary de 4 KiB depois de desc+avail.

## Alocação dos rings

`vq_setup_page` calcula bytes totais, arredonda para pages de 4096 e chama:

```text
pmm_alloc_contig(pages)
```

O physical run é convertido para virtual address via HHDM do Limine:

```text
virtual = physical + hhdm_offset
```

Toda a memória do ring é zerada antes do attach.

Não há cleanup dedicado dos rings se um passo posterior do init falhar.

## Modelo de endereço físico

Descriptors VirtIO recebem physical addresses retornados pelo PMM.

O PMM do projeto suporta memória física até 32 GiB.

QUEUE_PFN é escrito como:

```text
page_phys >> 12
```

em registrador 32-bit.

Dentro do range atual do PMM esse PFN cabe.

RX/TX packet buffers também são apresentados ao device por physical address direto.

## População do RX

ChrisOS aloca oito packet pages por `pmm_alloc`.

Cada descriptor anuncia:

```text
2048 bytes
```

e flag:

```text
VRING_DESC_F_WRITE
```

porque o device grava no buffer.

Descriptors 0..7 entram no available ring e `avail->idx` é inicializado em 8.

Depois a queue é attached e notified.

## RX buffer versus page

Cada RX buffer consome uma page de 4096 bytes, porém expõe apenas 2048 bytes ao device.

Metade da page fica inutilizada pelo driver.

Isso simplifica alignment/allocation, mas dobra o consumo físico em relação à capacidade RX anunciada.

Oito buffers reservam oito pages para 16 KiB efetivamente utilizáveis.

## Header VirtIO-net

Cada RX packet começa com header VirtIO-net legacy de 10 bytes.

ChrisOS não interpreta fields desse header.

Como não negocia offload, simplesmente ignora esses dez bytes e trata o restante como Ethernet.

No TX, os dez bytes são zerados.

A camada Ethernet fica independente do transport header.

## Processamento RX

`virtio_process_rx` lê o used index e processa até:

```text
last_used == used->idx
```

Para cada entry, lê:

- descriptor ID;
- total length.

O ID deve ser menor que oito.

Packets com length total <= 10 são descartados/repostados.

Os demais são entregues a:

```text
net_rx_ethernet(buf + 10, total_len - 10)
```

e o descriptor é repostado após o retorno.

## Lifetime do descriptor RX

O network stack recebe pointer direto para a page DMA-backed.

Não existe cópia genérica.

O descriptor só é devolvido ao device depois que `net_rx_ethernet` e toda a cadeia de protocolo terminam.

O frame pointer é válido somente nesse trecho síncrono.

Se no futuro houver dispatch assíncrono, será necessário manter ownership/refcount ou copiar o packet antes do repost.

## Repost do RX

`rx_repost` calcula:

```text
slot = avail->idx % queue_max
```

grava o descriptor ID, incrementa `avail->idx`, executa memory barrier de compilador e notifica queue zero.

Há uma notificação de device para cada buffer repostado.

Não existe batching de reposts.

## Queue size e arrays C

As structs `vring_avail` e `vring_used` declaram arrays de ring com tamanho `NET_QUEUE_SIZE`, igual a oito.

Porém, indexing e modulo usam o queue size completo reportado pelo device.

A backing allocation é calculada para esse tamanho maior, então fisicamente há espaço, mas o tipo C declara apenas oito elements.

Indexar além do array declarado não representa de forma limpa um ring variável no modelo de objetos de C.

Uma implementação mais segura deve usar offsets/arrays flexíveis/accessors próprios.

## Gap de RX completion length

O driver verifica somente:

```text
total_len > 10
```

antes de passar `total_len - 10` às camadas superiores.

Não exige:

```text
total_len <= 2048
```

embora o descriptor postado tenha 2048 bytes.

Um device correto respeita isso, mas um completion impossível produzido por device defeituoso ou hostil pode fazer parsers superiores confiarem em length maior que a allocation real.

É um gap direto de hardening de device boundary.

## Storage de TX

TX possui uma única page física.

Somente um packet é staged por vez.

O layout é:

```text
header virtio-net zerado de 10 bytes
frame Ethernet
```

O driver aceita Ethernet frame de 1 até 1514 bytes.

O total máximo é 1524 bytes, bem abaixo da page de 4096.

## Descriptor TX

Somente descriptor zero é usado.

Em cada send:

- addr = physical do TX buffer;
- len = total;
- flags = 0;
- next = 0.

O available ring avança normalmente, mas o descriptor ID publicado é sempre zero.

Não existem chains nem scatter/gather.

## Cópia no TX

O caller fornece frame Ethernet comum.

`virtio_net_tx` copia byte a byte para a page privada do driver.

Depois da cópia, o upper layer pode reutilizar seu buffer.

O custo é uma cópia completa de cada frame.

## Completion TX

Antes de montar um packet novo, `virtio_net_tx` chama `virtio_drain_tx`.

Depois da notify chama novamente.

`virtio_drain_tx` lê `used->idx` e incrementa `last_used` quando há completion.

O loop é limitado a 200000 iterações.

A porta ISR também é lida dentro do loop.

Não há erro explícito se o limite acabar com descriptor ainda pendente.

## Semântica TX síncrona

Como há um único TX buffer e o driver drena antes/depois de cada submit, o comportamento visto pelo upper layer é síncrono.

Não há múltiplos packets in-flight, object queue ou callback por packet.

Isso simplifica ownership mas reduz throughput e paralelismo.

## Polling

`virtio_net_poll`:

1. retorna se não ready;
2. lê ISR;
3. processa RX;
4. drena TX.

O progresso de networking depende de `net_poll`, que chama essa função.

O caminho é orientado a polling mesmo com ISR disponível.

## Modelo de interrupção

O driver não configura MSI/MSI-X nem handler dedicado de queue.

Ler ISR observa/acknowledges device state, mas parsing de protocolos roda em polling context.

Isso mantém parsing fora do interrupt handler.

A latência de RX passa a depender da frequência de `net_poll`.

## Memory barrier

`vio_mb` é:

```text
asm volatile("" ::: "memory")
```

Isso é compiler barrier, não uma CPU fence explícita.

Evita reorder do compilador, mas não emite instrução de hardware.

No target x86 atual, o design depende da ordenação forte da arquitetura para ordinary memory operations.

Essa assumption não é portable automaticamente.

## Falhas de inicialização

O init pode falhar se:

- PCI device não for encontrado;
- feature negotiation for rejeitada;
- ring RX não puder ser alocado;
- alguma RX page falhar;
- ring TX falhar;
- TX page falhar.

Quando queue setup falha, VIRTIO_FAILED é escrito.

Memória já alocada em passos anteriores não é liberada.

Retry após partial failure não possui lifecycle limpo.

## Estado ready

`g_vnet.ready` começa em zero.

Vira um somente após:

- discovery;
- negotiation;
- MAC read;
- RX setup;
- TX setup;
- DRIVER_OK;
- notify do RX.

`virtio_net_tx` rejeita chamada enquanto não ready.

`virtio_net_poll` vira no-op.

## Disable no boot

O startup só chama `net_init` quando boot flag `nonet` não está ativo.

O boot mode `safe` também ativa `nonet`.

Isso permite iniciar o sistema sem qualquer network stack para diagnóstico ou modo reduzido.

## Configuração QEMU

O run padrão adiciona:

```text
-device virtio-net-pci,netdev=n0
-netdev user,id=n0,...
```

com host forwarding para os services do guest.

Esse é o ambiente principal de exercício do driver.

Serviços funcionando sob essa configuração fornecem evidência integrada de discovery, queue setup, RX/TX e protocol handoff.

## Cobertura de testes

Não existe `test_virtio_net.c` dedicado na árvore inspecionada.

O projeto possui `virtq.c` genérico no subsystem gráfico e testes próprios para ele, mas o driver de rede não reutiliza esse helper.

Logo, esses testes não validam diretamente `kernel/net/virtio_net.c`.

A evidência atual é principalmente boot/QEMU integration.

## Features ausentes

Não há:

- modern VirtIO PCI capabilities;
- VERSION_1;
- indirect descriptors;
- event index;
- mergeable RX;
- multiqueue;
- control virtqueue;
- filtros/promiscuous configuráveis;
- checksum offload;
- TSO/UFO/GSO;
- MSI/MSI-X;
- link-state notifications completas;
- TX assíncrono multi-packet.

O driver é propositalmente pequeno.

## Concorrência

`g_vnet`, índices RX/TX e a única TX page são globals sem lock.

O design presume acesso serializado no polling atual.

Dois CPUs chamando `virtio_net_tx` simultaneamente podem sobrescrever TX buffer e queue state.

Polling RX por múltiplos CPUs também pode disputar `last_used` e repost indexes.

O driver não é SMP-safe geral.

## Hardening recomendado

As mudanças prioritárias são:

1. limitar used RX length ao descriptor size postado;
2. representar rings variáveis sem arrays fixos de oito no tipo C;
3. tratar explicitamente ausência de MAC feature;
4. separar claramente legacy e modern transports;
5. liberar partial allocations quando init falhar;
6. propagar timeout/failure de TX;
7. adicionar ownership/locking ou confinement a um único network context;
8. batch de RX repost notifications;
9. criar host tests para ring math e used entries malformadas;
10. eventualmente reutilizar uma abstração VirtIO queue comum e testada.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele documenta o transporte VirtIO-net legacy por port I/O, o modelo DMA/ring, o receive com oito buffers, o TX síncrono single-buffer e os gaps de hardening visíveis no source.
