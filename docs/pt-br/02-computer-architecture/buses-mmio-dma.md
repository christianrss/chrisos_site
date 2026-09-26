---
id: buses-mmio-dma
lang: pt-br
type: technical-chapter
volume: 02-computer-architecture
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/pci.c
  - kernel/metal/port.c
  - kernel/gfx/hwgate.c
  - chrisvm/machine/machine.c
symbols: []
depends_on:
  - cpu-datapath-isa
related:
  - block-storage
  - virtio-gpu-virgl
  - chrisvm-chriscpu
---

# Barramentos, port I/O, MMIO e DMA

## Por que dispositivos exigem modelo de endereçamento

A CPU precisa comunicar-se com controladores que não são RAM comum: storage, rede, timers, controladores de interrupção e GPUs. A arquitetura expõe esses dispositivos por espaços de endereço e protocolos definidos.

O contrato de software costuma ser orientado a registradores. O driver escreve configuração/comandos e lê status. O transporte elétrico pode ser PCI Express, mas o kernel normalmente enxerga dispositivos enumerados e janelas endereçáveis.

## Port-mapped I/O

x86 mantém um espaço separado de portas acessado por `IN` e `OUT`. `kernel/metal/port.c` é a fronteira de baixo nível do ChrisOS.

Uma porta, como a faixa serial em torno de 0x3F8, não é um ponteiro de RAM.

ChrisVM modela um I/O bus separado. Quando ChrisCPU executa uma instrução de I/O, a operação é despachada ao dispositivo registrado em vez de acessar RAM guest.

## Memory-mapped I/O

MMIO coloca registradores de dispositivos no espaço de endereços físicos. Load/store em determinada faixa é tratado pelo dispositivo em vez da DRAM.

Isso exige disciplina:

- descobrir ou atribuir a faixa física correta;
- mapeá-la nas page tables com atributos apropriados;
- evitar que o compilador remova acessos volatile semanticamente necessários;
- respeitar ordering e barriers;
- não aplicar automaticamente políticas de cache de RAM.

Um tipo de ponteiro isoladamente não representa esses contratos.

## PCI

PCI/PCIe padroniza identificação, configuration space e recursos. O kernel enumera devices, verifica vendor/device/class e descobre BARs que descrevem janelas MMIO ou de portas.

Drivers não devem depender de um endereço casual fornecido por uma configuração específica do QEMU.

## DMA

Programmed I/O faz a CPU mover valores explicitamente. Direct Memory Access permite que o dispositivo leia ou escreva memória após receber descritores ou endereços de buffers.

```text
CPU
 │ aloca buffer
 │ programa endereço físico
 ▼
controlador
 │
 ├──────── DMA ───────────────────┐
 │                                ▼
 │                            memória
 │
 └── completion/IRQ ─────────> CPU
```

DMA altera ownership: o buffer precisa permanecer vivo, estável e endereçável durante a operação. Liberá-lo cedo produz corrupção mesmo que o ponteiro C não seja mais usado pela CPU.

## Limites de endereçamento

Nem todos os dispositivos alcançam toda a memória física. O PMM do ChrisOS possui caminho de alocação DMA32 para controladores restritos abaixo de 4 GiB. Isso é materialmente relevante para hardware legado como UHCI.

## VirtIO

VirtIO define dispositivos paravirtuais para VMs. Guest e host trocam descritores por virtqueues e protocolos específicos, evitando parte da complexidade de emular hardware físico legado.

Ainda existe ownership semelhante a DMA: memória guest apontada por descritores precisa permanecer válida até a conclusão.

## Perspectiva do emulador

ChrisVM separa RAM, I/O bus e MMIO bus. O executor da CPU não deve conhecer cada dispositivo. Ele executa o acesso arquitetural; machine/bus resolve o alvo e chama o device registrado.

A mesma separação é desejável em kernel: mecanismo do processador, enumeração do bus, transporte do dispositivo e política do subsistema devem permanecer camadas distintas.
