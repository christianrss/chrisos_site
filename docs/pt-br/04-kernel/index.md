---
id: volume-04-kernel
lang: pt-br
type: volume-index
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Arquitetura do kernel

<div class="abstract">Privilégio, entrada de exceções, roteamento de interrupções, SMP, workers de kernel, processos nativos, passagem de memória user/kernel e diagnóstico fatal.</div>

O volume é uma cadeia de dependências, não uma visão geral curta. Cada capítulo de implementação está vinculado à revisão do `main` e registra também os limites atuais.

## Arquitetura e privilégio

- [Modelo de kernel e fronteiras de confiança](kernel-model.md)
- [GDT e TSS](gdt-tss.md)
- [IDT e entrada de exceções](idt-exceptions.md)

## Interrupções, tempo e execução paralela

- [Interrupções e SMP](interrupts-smp.md)
- [PIC, LAPIC e IOAPIC](pic-apic-ioapic.md)
- [PIT, temporização e scheduler tick](timers.md)
- [Jobs de kernel e kthreads cooperativas](kernel-jobs-kthreads.md)

## Userspace nativo

- [Processos nativos e system calls](processes-syscalls.md)
- [Entrada em user mode e retorno controlado](user-mode-entry.md)
- [Acesso seguro à memória de usuário](user-copy.md)
- [Ciclo de vida e estado de processos](process-lifecycle.md)

## Falha e observabilidade

- [Panic, diagnóstico serial e kernel log](panic-logging.md)

## Dependências de leitura

Privilégio e exceções antecedem userspace nativo. SMP pressupõe o modelo de interrupt entry. User-copy pressupõe tradução de memória virtual. Lifecycle depende dos detalhes de PMM/MM do Volume 05.

O [Source Atlas](../99-source-atlas/index.md) é a camada de evidência arquivo-a-arquivo; os capítulos autorais explicam arquitetura, invariantes, ownership, fluxo, falhas e limitações sem substituir a fonte por trechos.
