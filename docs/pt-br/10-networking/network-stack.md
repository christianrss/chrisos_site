---
id: network-stack
lang: pt-br
type: technical-chapter
volume: 10-networking
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/net/net.c
  - kernel/net/net_xfer.c
  - kernel/net/sock.c
  - kernel/net/virtio_net.c
symbols: []
depends_on:
  - buses-mmio-dma
  - interrupts-smp
related:
  - kernel-model
---

# Stack de rede e VirtIO networking

## Processamento em camadas

```text
aplicação / socket
        ↓
transporte
        ↓
protocolo de rede
        ↓
link
        ↓
driver da interface
        ↓
device queues
```

Cada camada resolve endereçamento e entrega em nível diferente. Ethernet atua no link local; IP fornece endereçamento roteável; transporte identifica endpoints e semântica de entrega.

## Interface de rede

Driver movimenta buffers entre memória e device. VirtIO-net usa descriptor chains em virtqueues.

RX buffers precisam permanecer vivos enquanto host puder preenchê-los; TX não pode ser reciclado antes de completion.

## Pacotes são entrada não confiável

Lengths, offsets e headers devem ser validados antes do uso. Checksum ou validade de protocolo não substituem bounds checking de memória.

## Sockets

Socket é endpoint voltado ao processo/aplicação. Estado atual possui ownership por processo/slot. A auditoria de locking registra que a socket table ainda não possui lock geral para concorrência arbitrária de AP; portanto a documentação não deve afirmar stack de rede plenamente SMP.

## Transferência

`net_xfer.c` adiciona protocolo de transferência do projeto acima das camadas de rede. Protocolo de aplicação e transporte são responsabilidades distintas.

## IRQ

Completion pode chegar assincronamente. Handoff entre ISR e consumidores é uma fronteira de sincronização.

## Validação

Testes devem separar parser, lifecycle de fila, device virtual, QEMU end-to-end e hardware físico. VirtIO-net prova o caminho paravirtual, não suporte a NIC física arbitrária.
