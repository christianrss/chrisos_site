---
id: volume-02-computer-architecture
lang: pt-br
type: volume-index
volume: 02-computer-architecture
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Arquitetura de computadores

<div class="abstract">Este volume faz a ponte entre lógica digital e o comportamento de máquina visível ao sistema operacional: datapaths, pipelines, especulação, ISA, execução x86-64, privilégio, hierarquia de memória, barramentos, MMIO, DMA e descoberta da plataforma.</div>

## Escopo

O volume explica tanto o contrato arquitetural consumido pelo ChrisOS quanto as ideias de implementação necessárias para compreender CPUs físicas e o ChrisCPU.

A cadeia pretendida é:

~~~text
lógica combinacional + sequencial
    ↓
datapath e controle
    ↓
pipeline
    ↓
hazards / forwarding
    ↓
branch prediction / speculation
    ↓
renaming / out-of-order / retirement
    ↓
ISA
    ↓
machine-code encoding
    ↓
registradores / privilégio / memória
    ↓
controlador DRAM + caches
    ↓
coerência + atomics
    ↓
buses / PCIe / MMIO / DMA
    ↓
ACPI
    ↓
ChrisOS
~~~

## Datapath e microarquitetura

O currículo passa a tratar separadamente:

1. Datapath da CPU e ISA.
2. Estrutura de pipeline.
3. Hazards de dados/controle e forwarding.
4. Branch prediction e speculation.
5. Register renaming, execução out-of-order e retirement.

ISA é contrato externamente visível. Pipeline e OoO são mecanismos internos possíveis para realizá-lo.

O ChrisCPU atual busca equivalência arquitetural, não reprodução de uma microarquitetura especulativa física. Essa diferença deve permanecer explícita.

## Código de máquina e x86-64

A sequência seguinte cobre:

1. Código de máquina e relocations.
2. Registradores, aliases e flags x86-64.
3. Encoding e decoding de instruções.
4. Memória e privilégio x86-64.
5. Rings e controlled entry.

Essa é a cadeia direta para ChrisAsm, KCC, ChrisCPU e o kernel ChrisOS.

## Sistema de memória

A sequência é:

1. Organização de DRAM e função do memory controller.
2. Cache hierarchy e locality.
3. Coerência multiprocessador.
4. Atomics e memory ordering.

Isso mantém separadas células DRAM físicas, memória arquitetural e semântica SMP cache-coherent.

## Dispositivos e plataforma

A rota de plataforma cobre:

1. buses, port I/O, MMIO e DMA;
2. PCI/PCIe e device discovery;
3. ACPI e descrição de plataforma.

Esses capítulos fazem a ponte entre execução de instruções e os dispositivos controlados pelo ChrisOS.

## Regra de leitura

Teoria geral e comportamento atual do ChrisOS/ChrisCPU são sempre separados.

Uma CPU física pode usar pipeline e OoO enquanto expõe as mesmas transições arquiteturais que o ChrisCPU atualmente interpreta sequencialmente.

Uma página existente não é automaticamente considerada concluída; coverage e depth gates continuam sendo a autoridade.
