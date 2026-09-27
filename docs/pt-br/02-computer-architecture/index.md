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

<div class="abstract">Esta coleção conecta lógica digital ao contrato de máquina consumido pelo ChrisOS e emulado pelo ChrisCPU. Estado arquitetural é separado da implementação microarquitetural; o modelo é então estendido por hierarquia de memória, barramentos e descoberta da plataforma.</div>

## Cadeia de dependências

~~~text
lógica digital e estado armazenado
    ↓
datapath e controle
    ↓
estado visível pela ISA
    ↓
pipeline e tratamento de hazards
    ↓
prediction, speculation e retirement
    ↓
machine-code encoding
    ↓
registradores, flags e addressing x86-64
    ↓
privilégio e proteção
    ↓
organização de DRAM e memory controller
    ↓
cache hierarchy
    ↓
coerência e memory ordering
    ↓
MMIO / DMA / buses
    ↓
PCI Express
    ↓
descrição ACPI
    ↓
boot e kernel
~~~

## Arquitetura e microarquitetura

A ISA define estado e transições observáveis por software. A microarquitetura define uma estratégia de implementação dessas transições.

O currículo separa:

1. datapath da CPU e ISA;
2. organização de pipeline;
3. hazards e forwarding;
4. branch prediction e speculation;
5. register renaming, execução out-of-order e retirement.

O ChrisCPU atual modela semântica arquitetural, não um pipeline físico especulativo.

## Camada de código de máquina

A sequência seguinte define o contrato binário exigido por assemblers, compilers, emulators e kernel:

1. código de máquina;
2. aliases de registradores e flags x86-64;
3. instruction encoding e addressing modes;
4. memória e privilégio;
5. transições controladas entre níveis de privilégio.

## Camada do sistema de memória

A sequência distingue:

1. organização física de DRAM e política do memory controller;
2. cache hierarchy;
3. cache coherence;
4. atomics e memory ordering.

Célula DRAM, posição de memória arquitetural, cache line e virtual page são abstrações distintas.

## Camada de plataforma

A interação com dispositivos segue:

1. buses, port I/O, MMIO e DMA;
2. PCI e PCI Express;
3. descrição de plataforma ACPI.

Esses tópicos estabelecem os pré-requisitos de plataforma para boot, routing de interrupts, storage, graphics e networking.

## Fronteiras de evidência

Mecanismos de processadores físicos são documentados a partir de especificações de arquitetura/vendor e teoria de arquitetura de computadores.

O source do ChrisCPU comprova somente o comportamento implementado pelo emulator. O comportamento da CPU hospedeira não é atribuído ao modelo guest sem implementação explícita.
