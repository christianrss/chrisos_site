---
id: interrupts-smp
lang: pt-br
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/idt.c
  - kernel/metal/idt_stubs.asm
  - kernel/metal/irq.c
  - kernel/metal/apic.c
  - kernel/metal/ioapic.c
  - kernel/metal/smp.c
  - kernel/metal/smp.h
  - kernel/metal/job.c
  - kernel/metal/tlb_proto.c
  - kernel/metal/mm.c
symbols:
  - irq_dispatch
  - smp_init
  - smp_current_cpu
  - ap_entry
  - ap_c_entry
  - smp_lapic_of
  - job_worker_forever
depends_on:
  - x86-64-memory-privilege
  - kernel-model
  - idt-exceptions
related:
  - pic-apic-ioapic
  - kernel-jobs-kthreads
  - tlb-shootdown
---

# Interrupções e multiprocessamento simétrico

## Escopo

SMP transforma execução de kernel em vários fluxos que podem alterar estado compartilhado simultaneamente. O ChrisOS inicializa processadores adicionais via protocolo MP do Limine, mapeia stacks privadas, coloca APs em workers de jobs, registra LAPIC IDs e os integra ao protocolo de coerência de TLB.

Nem tudo, porém, é distribuído. Process switching user continua BSP-only, IRQ externa ainda usa PIC e interrupções de AP são liberadas tardiamente. “Suporta multicore” precisa ser descrito por esses limites concretos.

## Tipos de entrada assíncrona

Exception é síncrona à instrução atual. Hardware IRQ não é relacionada ao fluxo interrompido. IPI é evento enviado por outra CPU. NMI não é bloqueada por IF.

Todos podem desviar para código privilegiado, mas têm semânticas diferentes: page fault pode ser recuperável; timer marca tempo; TLB IPI exige coerência; NMI de fencing indica falha do caminho comum.

## BSP e AP

BSP executa boot principal. APs são processadores adicionais.

`cpu_online_count` começa em 1. `smp_init` consome resposta MP do Limine.

Constantes atuais:
- `SMP_MAX_APS = 8`;
- `SMP_CPU_CAP = 16`;
- quatro páginas por stack AP;
- base virtual `0xffffffff92000000`;
- stride `0x10000`.

Esses limites são do código, independentes do número anunciado pelo firmware.

## CR3 do kernel

`smp_init` lê CR3 para `kernel_cr3`.

`ap_entry` escreve esse CR3 antes de usar o ambiente do kernel. O AP precisa das mesmas traduções high-half, stacks e mappings de MMIO esperados pelo código.

## Resposta MP do Limine

Cada descriptor possui LAPIC ID e campos para entry/argument.

O BSP limpa handoff de APs, inicializa mapas e registra LAPIC do BSP. Para cada AP dentro do cap:
- atribui índice lógico;
- relaciona LAPIC e índice;
- aloca stack;
- escreve `extra_argument`;
- publica `ap_entry`.

Compiler barriers protegem a ordem de publicação dos campos de handoff.

## Stack de AP

`alloc_ap_stack` calcula VA a partir de base + index*stride, chama PMM para quatro páginas e mapeia writable.

Falha é fatal.

O stride deixa separação maior que os 16 KiB mapeados. Depois essa geometria também serve para identificar CPU através de RSP.

## Entrada e switch de stack

`ap_entry` instala CR3, resolve o pointer MP para virtual quando necessário e extrai index/LAPIC.

Valida índice e stack. Então move RSP para stack do AP e chama `ap_c_entry`.

O comentário proíbe usar locals antigos depois do switch. Um bug anterior com frame pointer/spilled index fazia AP responder como CPU0 em TLB shootdown.

Troca de stack é, portanto, fronteira ABI real.

## Inicialização local

`ap_c_entry` carrega IDTR via `idt_load` e inicializa SSE.

Depois confirma identidade pelo stack layout, registra LAPIC se necessário, marca CPU online no TLB runtime e incrementa `cpu_online_count`.

O destino final é `job_worker_forever`, não scheduler user.

## Estado por CPU

IDTR, CR3 e controle SSE são registradores por processador. Uma tabela IDT compartilhada em memória não “instala” IDTR automaticamente nos APs.

Documentação precisa distinguir objeto compartilhado de registrador local.

## Identidade da CPU

`smp_current_cpu` lê RSP.

Abaixo da faixa de stacks AP, retorna BSP=0. Dentro da faixa calcula offset/stride e valida index.

É técnica específica. Se futuramente AP executar sobre outra stack fora dessa geometria, identidade precisará de mecanismo diferente ou preservado.

## Índice lógico versus LAPIC ID

Arrays de software usam índice compacto. Hardware IPI precisa LAPIC ID.

`g_lapic_of_cpu` guarda relação, e `smp_lapic_of` expõe com flag known.

Comentário registra bug anterior em que leitura compartilhada do LAPIC levava NMI ao BSP. Preservar ID publicado no boot evita confundir identidade lógica e destination ID.

## Espera pelos APs

BSP calcula quantidade desejada e gira com `pause` até `cpu_online_count` alcançar valor ou 100 milhões de spins.

Depois loga count e habilita LAPIC do BSP salvo `noapic`.

O wait é limitado. Código não transforma necessariamente partial online em panic nesse ponto.

## IF nos APs

AP entra no worker com IF zero.

`smp_release_ap_irqs` publica um flag. Cada AP então habilita LAPIC e executa `sti` uma vez.

Fonte registra problema real: IRQ de AP cedo demais interferia em ATA copy.

Há dois marcos distintos: online para jobs e liberado para IRQ mascarável.

## Jobs

AP consome ring global de jobs; BSP também pode consumir.

Kthreads são callbacks com stack privada sobre a mesma infraestrutura.

Isso fornece paralelismo de kernel sem scheduler user distribuído.

## User process continua no BSP

`proc_switch` causa panic fora CPU0. `syscall_dispatch` rejeita off-BSP.

Logo, ChrisOS não agenda aplicações nativas arbitrariamente em todos os cores nesta revisão.

## Races

Com APs, C loads/stores compartilhados podem intercalar.

Spinlocks CAS e atomics existem, mas cada subsistema precisa declarar ownership, lock order, IRQ safety e lifetime.

Lock não corrige use-after-free de recurso que outro CPU ainda referencia.

## Reentrância por IRQ

Mesmo em uma CPU, interrupt pode tentar lock já mantido pelo contexto interrompido. Isso deadlocka.

`irq_save`/`irq_restore` permitem local interrupt exclusion quando necessário. Desligar IRQ local não sincroniza outro CPU.

## TLB coherence

CPU pode manter tradução stale depois que outra altera page tables.

`TlbWorld` representa CPUs ABSENT/ONLINE/FENCED, geração publicada, faixa, seen generation, heartbeat, halted/flushed e reuse_ok.

Reutilizar frame físico antes de todos invalidarem ou um CPU fenced parar cria memory corruption.

Por isso TLB shootdown é protocolo de lifetime, não “só limpar cache”.

## IPI e NMI

Notificação normal usa fixed IPI.

CPU silencioso pode ultrapassar quiet budget e virar FENCED. NMI força path que não depende de IF.

`mm_tlb_nmi_stop` pode fazer AP invalidar/parar. BSP retorna porque halta-lo congelava desktop em uma versão anterior.

## Retirement

`smp_retire_cpu` reduz online count, nunca abaixo de 1.

Comentário ressalta que TLB membership, não online count, determina ack necessário. Isso impede usar um contador de scheduler como prova falsa de segurança de reclamation.

## Ordering

Código usa builtins atômicos, compiler barriers e instruções x86.

x86 tem modelo relativamente forte, mas compilador também reordena. “x86 não reordena” não é explicação suficiente.

## Modos de falha

Incluem resposta MP ausente, PMM sem stack, índice publicado errado, stack ABI incorreta, mapa CPU↔LAPIC errado, AP que não online, IRQ cedo, lock cycles, TLB stale e IPI/NMI ao destino errado.

Vários já aparecem em comentários por terem causado bugs reais.

## Validação

Precisa testar online count real, job self-test, identidade, shootdown sob churn, fencing forçado, destino de IPI, boot/install com release tardio, lock stress e manutenção da regra user BSP-only.

Boot multicore sozinho não prova correção de TLB ou locks.

## Limitações atuais

AP cap estático, identidade por faixa de stack, userspace BSP-only, IOAPIC pendente, worker polling e panic sem coordenador SMP global.

Esses limites definem exatamente o estágio SMP.

## Mapa de fonte

`smp.c`/`smp.h`: lifecycle/stack/identity. `job.c`: workload. `tlb_proto.c` + MM: coerência. `apic.c`: IPI/NMI. `idt*`/`irq.c`: entry. `ioapic.c`: status ainda não implementado. Source Atlas contém os arquivos completos.
