---
id: block-storage
lang: pt-br
type: technical-chapter
volume: 06-storage
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/fs/block_device.h
  - kernel/fs/storage.c
  - kernel/fs/ata_pio.c
  - kernel/fs/ahci.c
  - kernel/fs/nvme.c
  - kernel/fs/virtio_blk.c
symbols: []
depends_on:
  - buses-mmio-dma
related:
  - chrisfs
---

# Stack de armazenamento em blocos

## Dispositivos orientados a setores

Storage persistente expõe blocos endereçáveis, não objetos C. A camada de block device transforma protocolos específicos em contrato comum de leitura, escrita, flush e capacidade.

ChrisFS não deve precisar saber se a operação termina em ATA, AHCI, NVMe ou VirtIO Block.

```text
ChrisFS / installer
       │
       ▼
  BlockDevice
   /  |  |  \
 ATA AHCI NVMe VirtIO
```

## LBA

Software moderno usa Logical Block Address. Pedido contém LBA e quantidade. ChrisOS atualmente trabalha com contrato de setor de 512 bytes. Driver não pode alterar essa unidade silenciosamente porque offsets do filesystem e cálculos GPT dependem da geometria exata.

## ATA e AHCI

ATA PIO usa registradores de I/O e movimentação comandada pela CPU. Caminhos DMA acrescentam descritores e completion.

AHCI organiza controladores SATA em ports e command structures residentes em memória com DMA. Mesmo falando com mídia semelhante, o modelo de programação é diferente; a abstração BlockDevice esconde isso do filesystem.

## NVMe

NVMe foi projetado para storage não volátil em PCIe. Submission/completion queues ficam em memória, comandos apontam namespace/LBA e o controlador realiza DMA.

Descriptors não podem ser reciclados antes de completion provar que o controlador terminou.

## VirtIO Block

VirtIO Block usa descriptor chains em virtqueues. É excelente para testes em VM, mas não prova suporte a NVMe/AHCI físico. Evidência QEMU e hardware são categorias diferentes.

## Timeout e falha

Esperar indefinidamente pode travar o kernel. Vários paths do ChrisOS distinguem timeout de I/O genérico. Mesmo após timeout, ownership precisa ser seguro: se hardware ainda puder fazer DMA, liberar o buffer cedo é corrupção.

## Descoberta e root

`storage.c` descobre devices e seleciona fonte de filesystem conforme a política atual. Existir um driver no repositório não significa suporte universal a controladores reais.

## Instalação

```text
política do installer
  ↓
geometria de partição
  ↓
filesystem
  ↓
BlockDevice
  ↓
protocolo do controlador
  ↓
DMA / IRQ
```

Diagnóstico correto identifica a camada cujo contrato falhou.
