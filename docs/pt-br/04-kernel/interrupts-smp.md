---
id: interrupts-smp
lang: pt-br
type: technical-chapter
volume: 04-kernel
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/start.c
  - kernel/metal/idt.c
  - kernel/metal/idt_stubs.asm
  - kernel/metal/irq.c
  - kernel/metal/irq.h
  - kernel/metal/pit.c
  - kernel/metal/apic.c
  - kernel/metal/apic.h
  - kernel/metal/ioapic.c
  - kernel/metal/smp.c
  - kernel/metal/smp.h
  - kernel/metal/job.c
  - kernel/metal/job.h
  - kernel/metal/spin.c
  - kernel/metal/spin.h
  - kernel/metal/proc.c
  - kernel/metal/syscall.c
  - kernel/metal/tlb_proto.c
  - kernel/metal/mm.c
  - tools/test_job_saturate.c
symbols:
  - idt_init
  - idt_load
  - irq_dispatch
  - pic_init
  - pic_set_mask
  - irq_set_handler
  - irq_eoi
  - apic_enable_local
  - apic_ipi
  - smp_init
  - smp_current_cpu
  - smp_lapic_of
  - smp_retire_cpu
  - ap_entry
  - ap_c_entry
  - job_worker_forever
  - job_worker_once
  - smp_release_ap_irqs
  - smp_job_selftest
depends_on:
  - x86-64-memory-privilege
  - kernel-model
  - idt-exceptions
related:
  - pic-apic-ioapic
  - timers
  - kernel-jobs-kthreads
  - tlb
  - tlb-shootdown
  - spinlocks
  - process-lifecycle
---

# Interrupções e multiprocessamento simétrico

## Escopo

Interrupções e SMP estão diretamente ligados porque um kernel multiprocessado precisa responder a eventos assíncronos enquanto vários processadores executam código de kernel e acessam estado compartilhado ao mesmo tempo.

O ChrisOS atual possui uma arquitetura deliberadamente híbrida:

- IRQs externas de dispositivos continuam roteadas pelo PIC 8259 legado;
- essas linhas permanecem orientadas ao BSP;
- cada CPU pode habilitar por software seu LAPIC local;
- LAPIC é usado para IPIs, incluindo o vetor 0xF0 do protocolo de TLB;
- IOAPIC ainda não possui programação de redirection table e é apenas um estágio futuro;
- APs executam jobs de kernel, mas process switching nativo e syscalls de usuário permanecem restritos ao BSP.

Portanto existe execução multicore real no kernel, mas ainda não um sistema operacional com scheduler de user processes distribuído entre todos os CPUs.

![Fluxos de IRQ externa e IPI de TLB](../../assets/diagrams/interrupts-smp-flow-pt-br.svg)

## Classes de interrupção

Diferentes eventos arquiteturais entram em código privilegiado pelo mecanismo de vetores.

### Exceptions

Exceptions são síncronas à instrução executada.

Exemplos:

- divide error;
- invalid opcode;
- general protection;
- page fault.

A causa normalmente está diretamente associada ao fluxo atual da CPU.

### Hardware IRQs

IRQs de dispositivos são assíncronas em relação à instrução interrompida.

No ChrisOS atual o PIC remapeia:

~~~text
IRQ 0..7  -> vetores 0x20..0x27
IRQ 8..15 -> vetores 0x28..0x2f
~~~

### Inter-processor interrupts

IPI é uma interrupção iniciada intencionalmente por outra CPU e entregue pelo LAPIC.

O caso concreto atualmente usado pelo ChrisOS é o vetor 0xF0 para progresso de TLB shootdown.

### NMI

O vetor 2 usa nmi_entry dedicado.

NMI não é bloqueada pelo bit IF normal.

O ChrisOS possui suporte para um caminho NMI de parada relacionado ao TLB e também implementa apic_ipi_nmi. Entretanto, o fencing ativo do TLB nesta revisão **não chama apic_ipi_nmi**. O retirement atual depende de o worker do AP perceber que foi marcado como FENCED.

Essa distinção é importante ao avaliar recovery de CPUs não responsivas.

## Construção da IDT

idt_init cria 256 gates em uma IDT estática alinhada.

Gates comuns usam:

~~~text
0x8e
~~~

correspondendo ao interrupt gate presente e acessível a ring 0.

O vetor 2 é substituído por nmi_entry.

Posteriormente syscall_init altera o vetor 0x80 usando idt_set_user_gate, com:

~~~text
0xee
~~~

permitindo entrada a partir de ring 3.

Todos os gates atuais possuem:

~~~text
ist = 0
~~~

Logo, o código atual não utiliza Interrupt Stack Table para troca automática de stack em exceptions, IRQs ou NMI.

A tabela IDT em memória é compartilhada, mas IDTR é estado arquitetural local de cada CPU. O BSP carrega IDTR em idt_init; cada AP executa idt_load dentro de ap_c_entry.

## Normalização dos stubs

idt_stubs.asm gera stubs para todos os 256 vetores.

Algumas exceptions x86 empilham error code automaticamente; outras não.

Para vetor sem hardware error code, o stub empilha:

~~~text
error sintético = 0
número do vetor
~~~

Quando o CPU já empilhou um error code, o stub adiciona somente o número do vetor.

Na revisão atual, os vetores classificados como contendo hardware error code incluem 8, 10, 11, 12, 13, 14, 17, 21, 29 e 30.

Isso cria um prefixo comum para irq_frame em C.

## Preservação de registradores e SIMD

isr_common salva os registradores gerais antes de chamar irq_dispatch.

O layout usado por C começa com:

~~~text
r15 ... rax
vector
error
rip
cs
rflags
~~~

O stub também reserva espaço para FXSAVE, alinha a área de salvamento, executa fxsave antes de chamar C e fxrstor antes do retorno.

Assim, uma interrupção não deve destruir silenciosamente o estado x87/MMX/SSE do código interrompido.

CLD também é executado na entrada, garantindo direction flag limpa para os handlers C.

No final os registradores são restaurados, os slots de vector/error são removidos e IRETQ retorna.

A entrada de interrupção é, portanto, uma ABI entre assembly e C: layout da stack, alinhamento e estado preservado precisam permanecer coerentes.

## Inicialização do PIC

pic_init começa executando CLI e reprograma os dois controladores 8259.

O master é remapeado para 0x20 e o slave para 0x28.

A relação de cascata é configurada e todas as linhas começam mascaradas.

A tabela de handlers também é zerada.

Subsistemas individuais instalam seu handler e liberam as linhas necessárias.

Exemplos atuais:

- PIT em IRQ 0;
- teclado em IRQ 1;
- mouse PS/2 em IRQ 12;
- ATA DMA em IRQ 14;
- AC97 na IRQ legado detectada;
- VirtIO-GPU quando usa o caminho de IRQ legado.

O modelo de interrupção externa ainda é explicitamente baseado no PIC.

## Dispatch de IRQ

irq_dispatch trata primeiro os casos especiais que não pertencem ao intervalo PIC normal.

A ordem atual inclui:

1. syscall 0x80;
2. page fault 14;
3. demais exceptions arquiteturais abaixo de 32;
4. IPI de TLB 0xF0;
5. vetores altos genéricos;
6. vetores PIC 32..47.

Para vetor PIC:

~~~text
irq = vector - 32
~~~

O function pointer instalado é executado se não for nulo e depois irq_eoi é chamado.

A tabela possui somente 16 slots correspondentes às linhas legado.

Não existe ainda um framework geral de interrupt domains ou vector allocation dinâmica.

## End-of-interrupt

irq_eoi atualmente executa duas famílias de acknowledge.

Se apic_ready() retorna verdadeiro, envia LAPIC EOI.

Depois envia EOI ao PIC:

- slave e master para IRQ >= 8;
- apenas master para IRQ < 8.

Como o sistema está em estado híbrido, o caminho reconhece LAPIC quando habilitado e continua concluindo o protocolo legado do PIC.

IOAPIC ainda não substituiu o roteamento externo.

## Proteção contra IRQ storm

irq_dispatch mantém irq_hits para as linhas legadas.

IRQ 0 é excluída propositalmente porque representa o timer de 60 Hz e mascará-la interromperia o ritmo do desktop.

Para outra IRQ, quando o contador acumulado chega a 10.000, o kernel mascara a linha e registra mensagem irq storm.

Esse mecanismo evita que uma linha permanentemente assertada mantenha o kernel em um loop de interrupções.

Não é um detector de taxa por janela temporal: o limiar é acumulado e não há reativação automática da linha.

## PIT e sinal de scheduling

pit_init programa o canal 0 usando a frequência-base de 1.193.182 Hz.

O boot atual solicita 60 Hz.

O handler:

1. incrementa ticks;
2. chama proc_on_tick.

proc_on_tick apenas marca o slice de processo como devido.

Ele não executa arbitrariamente um context switch de user process em um AP.

O timer participa do estado de scheduling sem criar um scheduler user SMP.

## Papel do LAPIC

apic_init obtém a virtual address do LAPIC mapeada por MM, mas mantém inicialmente o estado de software desabilitado.

apic_enable_local escreve no Spurious Interrupt Vector Register:

~~~text
0x100 | 0xff
~~~

habilitando o LAPIC local e usando 0xFF como spurious vector.

O comentário no código é explícito: isso não altera IMCR nem move as linhas do i8259 para IOAPIC.

Hoje o LAPIC é importante para:

- estado local de APIC;
- EOI quando ativo;
- IPIs fixed-delivery;
- suporte disponível para NMI delivery.

## Envio de IPI fixed-delivery

apic_ipi recebe LAPIC ID de destino e vetor.

Ele programa ICR high com o destino e ICR low com vetor e level-assert.

Depois espera delivery status limpar, limitado a 100.000 spins.

Retorna 0 em sucesso ou -1 se LAPIC não estiver disponível ou o status não completar.

O caller de TLB atualmente ignora esse retorno e depende do protocolo superior de geração/ack para decidir segurança.

## Estado do IOAPIC

ioapic_init não programa redirection entries.

Sua implementação apenas registra que o PIC ainda roteia IRQs e que IOAPIC completo pertence a uma etapa futura.

Logo, não é correto descrever o ChrisOS atual como um sistema SMP com device IRQs roteadas por IOAPIC.

LAPIC e SMP funcionam dentro do modelo híbrido sem essa afirmação.

## Limites atuais de SMP

smp.h define:

~~~text
AP_STACK_PAGES     = 4
AP_STACK_VIRT_BASE = 0xffffffff92000000
AP_STACK_STRIDE    = 0x10000
SMP_MAX_APS        = 8
SMP_CPU_CAP        = 16
~~~

Existe uma sutileza importante no nome SMP_MAX_APS.

Os índices válidos são testados como:

~~~text
index > 0 && index < SMP_MAX_APS
~~~

e smp_init interrompe a criação quando next >= SMP_MAX_APS.

Com SMP_MAX_APS igual a 8, os índices efetivamente usados para AP são 1..7.

Portanto o código admite **até sete APs além do BSP**, e não oito APs além do BSP.

SMP_CPU_CAP é maior porque arrays por CPU, inclusive o protocolo TLB, possuem 16 slots.

Esses dois limites não representam a mesma coisa.

## Sequência de boot do BSP

kstart configura as dependências de interrupção e memória antes de iniciar SMP.

Uma sequência simplificada é:

~~~text
GDT
IDT
syscall gate
PIC
PIT
PS/2
PMM
MM
heap
SSE
process subsystem
graphics
LAPIC init
IOAPIC placeholder
job queue
SMP
SMP job self-test
~~~

Depois o kernel executa CLI explicitamente antes das fases de ACPI, storage, filesystem, instalação e inicialização de linguagem.

Somente depois:

~~~text
STI no BSP
smp_release_ap_irqs()
desktop
~~~

Essa liberação atrasada é intencional.

O source registra que interrupções de AP liberadas cedo demais interferiram com cópia ATA durante instalação.

## Handoff MP do Limine

smp_init lê o CR3 corrente e salva em kernel_cr3.

cpu_online_count é resetado para 1.

Com bootflag nosmp, AP startup é ignorado; LAPIC do BSP ainda pode ser habilitado.

No caminho SMP, o kernel lê a resposta MP do Limine.

Primeiro limpa goto_address e extra_argument de descritores não-BSP.

Depois cria os mappings de índice lógico para LAPIC ID e prepara cada AP aceito.

Para cada AP:

1. atribui o próximo software index;
2. preserva LAPIC ID publicado pelo Limine;
3. aloca a stack;
4. grava index em extra_argument;
5. executa compiler barrier;
6. publica ap_entry em goto_address.

ChrisOS usa, portanto, o handoff MP do Limine e não implementa diretamente a sequência INIT/SIPI de startup dos APs.

![Sequência atual de inicialização dos APs](../../assets/diagrams/smp-bringup-pt-br.svg)

## Stack dos APs

Cada AP aceito recebe quatro frames físicas mapeadas em uma faixa virtual exclusiva.

São 16 KiB efetivamente mapeados.

O stride virtual é 64 KiB, deixando espaço não mapeado entre regiões.

Falha no PMM ao construir a stack provoca panic.

A stack não é somente armazenamento de chamadas: sua posição também é usada pelo mecanismo atual de identificação da CPU.

## Entrada do AP e CR3

ap_entry começa escrevendo kernel_cr3.

Assim o AP passa a usar a raiz de tradução esperada pelo kernel inicializado.

Depois obtém index/LAPIC do descriptor Limine, com fallback de lookup caso necessário.

Índice inválido ou stack inexistente coloca o AP em HLT permanente.

Em seguida RSP é movido para a stack privada e ap_c_entry é chamado.

## Risco ABI durante troca de stack

O assembly dentro de ap_entry recarrega o software index em EDI depois de trocar RSP.

Um comentário de source registra bug anterior: estado local/frame pointer associado à stack antiga resultou em index corrompido, e APs acabavam respondendo operações TLB como CPU 0.

Isso mostra que escrever RSP no meio de uma função compilada não é simples alteração de ponteiro.

A implementação trata a troca como fronteira one-way e evita usar locals antigos depois dela.

## Inicialização local do AP

ap_c_entry executa:

- idt_load;
- inicialização SSE/FPU via sse_bsp_init;
- reavaliação da identidade via stack;
- fallback de metadata LAPIC quando necessário;
- tlb_runtime_online(index);
- incremento atômico de cpu_online_count;
- entrada em job_worker_forever.

O AP não entra em um scheduler de processo de usuário.

## Identidade da CPU atual

smp_current_cpu lê RSP.

Se RSP estiver abaixo de AP_STACK_VIRT_BASE, retorna CPU 0.

Caso contrário calcula:

~~~text
index = (rsp - AP_STACK_VIRT_BASE) / AP_STACK_STRIDE
~~~

e valida o resultado.

Isso funciona hoje porque execução normal de AP, interrupt entry comum e NMI usam a stack interrompida: os gates atuais têm IST=0.

O mecanismo é, portanto, acoplado à geometria das stacks.

Se o projeto introduzir IST, scheduler stacks, stacks temporárias ou migração de stack, a identificação precisa migrar para mecanismo CPU-local explícito ou preservar metadata equivalente.

## Índice lógico versus LAPIC ID

Software index não é o destino físico de APIC.

g_lapic_of_cpu mantém a associação e smp_lapic_of devolve LAPIC ID com uma flag known.

A separação é necessária porque:

- arrays internos usam índices compactos;
- ICR precisa do LAPIC destination ID.

Comentário no source registra falha anterior em que uma leitura de LAPIC compartilhada podia aparentar o ID do BSP e causar destino incorreto.

A implementação atual prefere IDs publicados pelo Limine durante o boot.

## Espera por CPUs online

Depois de publicar os APs, smp_init define:

~~~text
want = next
~~~

O BSP gira enquanto cpu_online_count < want, com PAUSE, limitado a 100.000.000 de iterações.

Depois registra o contador e continua.

Não existe panic automático apenas porque o limite expirou com menos CPUs que o desejado.

Portanto o fluxo admite, em princípio, bring-up parcial.

O log é necessário para distinguir CPUs solicitadas das que realmente chegaram ao estado online.

## Habilitação de interrupções nos APs

Os workers entram inicialmente com IF zero.

job_worker_forever observa g_ap_irq_enable.

Depois de o BSP chamar smp_release_ap_irqs, cada AP, numa iteração posterior:

1. chama apic_enable_local se APIC não estiver desabilitado;
2. executa STI;
3. marca localmente que já realizou essa transição.

Existem, portanto, dois estados distintos:

- AP online para jobs/polling;
- AP com interrupções mascaráveis habilitadas.

Eles não acontecem simultaneamente durante o boot.

## Fila de jobs

O principal workload dos APs vem do job subsystem.

JOB_QUEUE_CAP vale 1024.

A ring global armazena:

~~~text
function pointer
argument pointer
~~~

A estrutura da fila é protegida por g_q_lock.

g_inflight e g_completed são atualizados atomicamente.

Um AP em loop:

1. verifica fencing TLB;
2. processa TLB polling;
3. habilita interrupções após release;
4. retira um job sob lock;
5. executa o callback fora do lock;
6. atualiza contadores;
7. executa PAUSE;
8. repete.

O BSP também pode executar job_worker_once enquanto espera a fila ficar idle.

É um motor de trabalho cooperativo de kernel, não um scheduler geral preemptivo.

## Self-test SMP de jobs

smp_job_selftest roda quando existem pelo menos dois CPUs online.

Primeiro envia 16 jobs simples e exige resultado 16.

Depois executa 32 ondas de 128 jobs e verifica a soma ao fim de cada onda.

Se submit não consegue progredir dentro do limite ou a soma diverge, o kernel entra em panic.

Esse teste valida:

- fila compartilhada;
- lock;
- execução pelos workers;
- accounting atômico.

Não prova sozinho todas as propriedades de IRQ, cache coherence ou memory ordering.

## User processes continuam BSP-only

proc_switch exige:

~~~text
smp_current_cpu() == 0
~~~

e entra em panic caso seja chamado num AP.

syscall_dispatch também rejeita entrada off-BSP.

Portanto aplicações nativas não são atualmente distribuídas entre APs.

O paralelismo existente concentra-se nos jobs de kernel e mecanismos construídos sobre esses workers.

## Sincronização de memória compartilhada

Depois que APs entram online, objetos comuns em C podem ser acessados simultaneamente.

O ChrisOS fornece Spinlock simples:

- CAS para acquire;
- PAUSE durante contenção;
- __sync_lock_release no unlock.

Também existe atomic_add_u32.

Essas primitivas não resolvem automaticamente lock ordering, reentrância ou lifetime.

Cada subsistema ainda precisa de política explícita.

## Exclusão local de IRQ versus exclusão SMP

Um spinlock pode deadlockar se uma IRQ na mesma CPU interromper o código que segura o lock e o handler tentar adquirir o mesmo lock.

spin.h fornece irq_save e irq_restore.

irq_save salva RFLAGS e executa CLI.

irq_restore executa STI apenas quando IF estava ativo anteriormente.

PMM é um exemplo concreto:

~~~text
salva IF e desabilita IRQ local
adquire pmm_lock
opera no bitmap
libera pmm_lock
restaura IF
~~~

CLI impede reentrada por interrupção na CPU local.

Ele não impede outra CPU de tocar o estado.

O spinlock fornece a exclusão entre CPUs.

## Integração com TLB

SMP correctness não termina em locks comuns.

Uma CPU pode manter tradução stale depois que outra remove mapping compartilhado.

Por isso cada AP é registrado no TLB runtime e workers processam TLB polling. O vetor 0xF0 oferece aceleração via IPI.

O protocolo completo está no capítulo TLB shootdown.

Um fato importante: o fencing ativo é cooperativo.

Quando um AP marcado FENCED volta ao topo de job_worker_forever:

1. faz mm_tlb_poll_cpu;
2. registra halted;
3. executa CLI;
4. entra em HLT permanente.

Apesar de existir suporte NMI, o código de shootdown atual não envia NMI durante esse retirement.

## Contador de CPUs versus membership exato

smp_retire_cpu reduz cpu_online_count atomicamente, nunca abaixo de 1.

O parâmetro cpu não é usado para atualizar bitmap SMP exato.

Assim, cpu_online_count é contador agregado de estado.

Ele não constitui prova suficiente para segurança de TLB reclamation.

O protocolo TLB possui estados independentes ONLINE/FENCED/ABSENT por slot.

Essa separação impede que uma simples redução do contador seja interpretada como desaparecimento garantido de stale translation.

## Caminho NMI

idt_init instala nmi_entry em vector 2.

O stub usa a stack interrompida porque IST=0.

Ele chama mm_tlb_nmi_stop.

Essa função:

1. processa TLB pending;
2. marca halted;
3. deixa CPU 0 retornar;
4. para AP em CLI/HLT quando o retorno indica stop.

apic.c possui apic_ipi_nmi capaz de gerar NMI por ICR.

No entanto, não há chamada ativa a esse helper no caminho de TLB fencing atual.

A infraestrutura existe, mas não deve ser descrita como mecanismo normal de escalation desta revisão.

## Concorrência e memory ordering

O source usa:

- builtins __sync;
- estado volatile;
- compiler barriers;
- PAUSE;
- CLI/STI;
- instruções específicas de x86.

x86-64 oferece memory ordering relativamente forte, porém compiler ordering, atomicity e publication continuam relevantes.

“x86 não reordena” não representa uma prova suficiente.

O ChrisOS possui hoje sincronização orientada à implementação x86, não um modelo abstrato multiplataforma formal.

## Modos de falha

Falhas relevantes incluem:

- ausência da resposta MP do Limine;
- CPUs além do limite de índices admitidos;
- PMM sem memória para stack AP;
- software index corrompido;
- erro de ABI na troca de stack;
- associação CPU/LAPIC incorreta;
- AP que não incrementa online count;
- interrupções de AP liberadas cedo;
- IRQ legado permanentemente assertada;
- reentrância de lock por interrupt;
- ciclos de lock entre CPUs;
- stale TLB depois de reclamation;
- timeout de entrega IPI;
- CPU fenced que nunca retorna ao worker.

Comentários no source registram bugs anteriores particularmente em identity por stack, LAPIC destination e timing de release das interrupções.

## Evidência de validação

A evidência atual inclui:

- smp_job_selftest em boot multicore;
- tools/test_job_saturate.c para fila cheia, drain e reutilização;
- host tests do protocolo TLB;
- logs de MM/TLB;
- wait limitado e online count durante startup;
- PIT real dirigindo o ritmo do desktop;
- handlers PIC reais para dispositivos.

Testes adicionais úteis:

- verificar índices e LAPIC IDs em máquinas com IDs esparsos;
- injetar falha de startup de AP;
- forçar falha de IPI;
- stress do mesmo lock em contexto normal e IRQ;
- provocar storm de IRQ não-timer e confirmar masking;
- validar ordem de release de IF durante install/storage;
- saturar workers durante churn de TLB;
- validar mecanismo de identidade antes de adicionar IST.

## Limitações atuais

Na revisão analisada:

- no máximo sete APs são admitidos além do BSP;
- capacidade de arrays e quantidade admitida de APs são limites diferentes;
- user processes e syscalls permanecem BSP-only;
- hardware IRQs externas continuam roteadas pelo PIC;
- redirection via IOAPIC não está implementado;
- identificação de CPU depende da faixa de stack do AP;
- APs executam polling de uma fila global, não scheduler SMP geral;
- cpu_online_count não é um mapa exato de membership;
- suporte NMI de stop existe, mas fencing ativo continua cooperativo;
- panic não coordena parada global de todas as CPUs;
- não existe lifecycle de CPU hotplug/rejoin.

Esses limites descrevem com precisão o estágio SMP atual.

## Fronteira de revisão

Este capítulo foi reconciliado com ChrisOS main na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

O modelo atual comprovado pelo source é:

1. IDT compartilhada em memória com IDTR carregado em cada AP;
2. IRQs legado roteadas pelo PIC;
3. LAPIC habilitado localmente e usado para IPIs;
4. até sete índices AP além do BSP pelos checks atuais;
5. stack privada por AP usada também para identidade;
6. habilitação tardia de IF nos APs;
7. fila global de jobs protegida por lock;
8. execução nativa de usuário restrita ao BSP;
9. membership/coerência de TLB independente de cpu_online_count;
10. suporte NMI disponível, mas envio NMI não usado no fencing ativo.

Mudanças futuras em IOAPIC, migração de processos, IST, identidade CPU-local ou scheduler exigem nova reconciliação source-level.
