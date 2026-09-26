---
id: emulator-theory
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - cpu-datapath-isa
  - buses-mmio-dma
related:
  - chrisvm-chriscpu
  - virtualization-chrishv
---

# Emulação de máquina: estado arquitetural e interpretação

## Emulador e virtualizador

Emulador implementa em software o comportamento visível de uma máquina alvo e pode rodar em ISA diferente.

Virtualizador assistido por hardware executa grande parte do guest diretamente em hardware compatível e intercepta eventos definidos.

## Estado arquitetural

Emulador x86-64 representa GPRs, RIP, RFLAGS, segmentos, control state, MSRs necessários e ambiente de memória/devices.

Branch predictors e outras estruturas microarquiteturais não são necessárias para semântica funcional.

## Fetch, decode, execute

```text
RIP
 ↓
fetch bytes
 ↓
decode
 ↓
resolve operands
 ↓
execute
 ↓
flags/state
 ↓
exception/interrupt
 ↓
next RIP
```

x86 variável torna comprimento e addressing mode parte crítica do decoder.

## Tradução e faults

Load guest não é dereference de ponteiro host. Emulador aplica paging guest, detecta fault e só então acessa mapa físico virtual, que pode resolver para RAM, framebuffer, MMIO ou unmapped.

## I/O e devices

IN/OUT passam pelo port bus; MMIO pelo mapa físico. Executor não deve conter knowledge hardcoded de cada device.

## Determinismo e desempenho

Controlar relógio, entropia e input externo permite reprodução. Interpreter direto é baseline simples; caches e JIT podem vir depois de semântica validada.

## Testes

Guests mínimos isolam instruções e exceptions; boot completo testa composição entre milhares de contratos. Ambos são necessários.
