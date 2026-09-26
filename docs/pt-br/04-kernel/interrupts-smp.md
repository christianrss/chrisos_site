---
id: interrupts-smp
lang: pt-br
type: technical-chapter
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/idt.c
  - kernel/metal/irq.c
  - kernel/metal/apic.c
  - kernel/metal/ioapic.c
  - kernel/metal/smp.c
  - kernel/metal/job.c
symbols: []
depends_on:
  - x86-64-memory-privilege
  - kernel-model
related:
  - tlb-shootdown
---

# Exceções, interrupções e multiprocessamento simétrico

## Exceções e interrupções

Exceção é causada pelo fluxo atual: divide error, invalid opcode, general protection ou page fault. Interrupção externa vem de timer ou dispositivo.

Ambas desviam controle, mas a diferença importa. Page fault possui relação direta com um acesso; IRQ de rede pode surgir entre instruções sem relação com a rede.

## IDT

A Interrupt Descriptor Table x86-64 associa vetores a gates contendo endereço do handler, selector e propriedades de controle. A CPU consulta a IDT segundo vetor e regras de privilégio.

Stubs em assembly normalmente salvam registradores e normalizam o frame antes de chamar C, porque o hardware não entra segundo a ABI de uma função C comum.

## Controladores

```text
device
  ↓
roteamento de interrupção
  ↓
local APIC da CPU alvo
  ↓
vector
  ↓
IDT
  ↓
handler
```

End-of-interrupt faz parte do protocolo. Omiti-lo pode impedir novas entregas.

## BSP e APs

Uma CPU inicia como bootstrap processor. Application processors precisam receber stacks, address-space state e entry code.

`smp.c` registra CR3 do kernel, aloca stacks por AP e utiliza a resposta multiprocessador do Limine para configurar entradas. O AP carrega estado necessário e entra no job worker.

## Identidade por CPU

SMP exige saber "em qual CPU estou" para locks, acknowledgements de TLB, LAPIC e estado per-CPU. ChrisOS usa o layout das stacks de AP como parte da identificação atual. É uma técnica do projeto, não requisito x86.

## Memória compartilhada e races

Com várias CPUs, loads/stores podem intercalar. Uma expressão C não é automaticamente uma operação atômica.

Spinlocks protegem invariantes quando a seção crítica deve ser curta. O ChrisOS documenta ordem entre locks de JIT, MM, heap e PMM para reduzir deadlocks.

## IRQ e locks

Interrupções criam reentrância mesmo em uma CPU. Se código normal mantém um lock e o handler local tenta adquirir o mesmo lock, ocorre deadlock. Por isso alguns locks salvam/desabilitam estado de interrupção ou proíbem uso em IRQ.

## Ordenação de memória

Sincronização não é só exclusão. Compilador e CPU podem reordenar operações conforme seus modelos. Locks precisam de atomics/barriers adequados para publicar estado corretamente.

## APs durante boot

O código atual mantém restrições sobre quando APs passam a receber interrupções durante instalação. Comentários em `smp.c` registram um problema histórico no caminho ATA quando atividade assíncrona foi liberada cedo. Boot order e concorrência, portanto, formam um único contrato.

## Jobs e processos

APs atuais executam trabalho de kernel pelo mecanismo de jobs. Processos nativos têm uma regra mais restritiva: `proc_switch` rejeita troca em AP e mantém scheduling de user process no BSP.

Assim, "SMP" não significa automaticamente scheduler de processos em todas as CPUs.
