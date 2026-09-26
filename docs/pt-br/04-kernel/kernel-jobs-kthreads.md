---
id: kernel-jobs-kthreads
lang: pt-br
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/job.c
  - kernel/metal/job.h
  - kernel/metal/kthread.c
  - kernel/metal/kthread.h
  - kernel/metal/spin.c
  - kernel/metal/spin.h
  - kernel/metal/smp.c
  - kernel/metal/smp.h
  - kernel/metal/tlb_proto.c
  - kernel/metal/tlb_proto.h
symbols:
  - job_init
  - job_submit
  - job_worker_once
  - job_worker_forever
  - job_wait_idle
  - kthread_create
  - kthread_join
  - kt_run
  - spin_lock
  - spin_unlock
depends_on:
  - interrupts-smp
  - atomics-memory-model
related:
  - tlb-shootdown
  - process-lifecycle
---

# Jobs de kernel e kthreads cooperativas

## Escopo

O ChrisOS possui dois mecanismos relacionados de execução que não devem ser confundidos com um scheduler tradicional de kernel threads preemptivas. A camada de jobs implementa uma fila limitada consumida pelo BSP e pelos application processors. A camada kthread adiciona uma stack privada e identidade por slot, executando um callback até o retorno sobre um worker do sistema de jobs.

Isso permite paralelismo de trabalho do kernel mantendo simples o scheduler de processos. O contrato, porém, é específico: callback de kthread precisa retornar; não existe preempção por timer de kthreads; identidade é um slot fixo; condition variables usam um contador de sequência com espera ativa; e troca de processo de usuário continua restrita ao BSP.

## Estrutura da fila

A camada define:

```c
#define JOB_QUEUE_CAP 1024u

typedef void (*JobFn)(void *arg, uint32_t cpu_index);

typedef struct {
    JobFn fn;
    void *arg;
} Job;
```

A fila é um ring estático de 1.024 entradas. Head, tail e count são globais protegidos por `Spinlock`. Há ainda contadores atômicos de completed e in-flight.

`job_submit` não aloca heap. Ele copia function pointer e argumento opaco. Isso elimina falha de alocação dentro da fila, mas não transfere ownership do objeto apontado por `arg`.

O chamador precisa manter o argumento vivo até a execução. Colocar endereço de variável local e retornar antes do worker consumi-la criaria use-after-scope.

## Spinlock e atomics

`Spinlock` contém um `volatile uint32_t`. `spin_lock` tenta CAS 0→1 e executa `pause` quando falha. `spin_unlock` usa builtin de release. `atomic_add_u32` usa `__sync_fetch_and_add`.

A fila usa o lock para sua estrutura circular e atomics para accounting. Assim a callback não roda segurando o lock global.

`spin.h` também fornece `irq_save` e `irq_restore`, mas `spin_lock` não desliga interrupções automaticamente. Isso significa que a segurança contra deadlock com interrupt context depende do uso específico de cada lock.

## Inicialização

`job_init` inicializa lock, índices, count e contadores.

`kstart` chama a função antes de `smp_init`. APs entram em `job_worker_forever` durante seu bring-up, logo a fila precisa existir antes que qualquer AP tente consumi-la.

## Submission

`job_submit(fn,arg)` retorna 0 para function pointer nulo. Sob lock, verifica se count já alcançou 1.024. Se cheia, libera e retorna 0.

Se houver espaço, escreve no tail, avança modulo capacidade, incrementa count e `g_inflight`. O lock é liberado antes da execução.

Retorno 1 significa “aceito na fila”; 0 significa “não foi enfileirado”. Queue-full é backpressure, não panic.

Esse contrato permite que kthread tenha fallback síncrono e que self-tests drenem jobs enquanto tentam reenviar.

## Consumo

`job_worker_once(cpu_index)` verifica primeiro se o TLB protocol cercou essa CPU. Em caso positivo, processa o estado de TLB, marca halted e não pega trabalho novo.

Se não estiver fenced, ainda executa polling de invalidação antes de acessar a fila. Correção de memória tem prioridade sobre trabalho comum.

O worker cria um Job local vazio, adquire lock, remove uma entrada do head se houver, atualiza count e solta lock. Só então chama a callback.

Depois do retorno incrementa completed e decrementa in-flight atomicamente.

Executar fora do lock é indispensável: callback pode ser longa, usar outros locks ou enviar jobs. Manter o lock durante callback serializaria todos os workers e abriria ciclos de deadlock.

## Loop dos APs

`job_worker_forever` executa continuamente. A cada iteração:
- verifica fencing;
- se fenced, trata TLB, marca halted e entra em `cli`/`hlt` permanente;
- quando o BSP libera IRQs de AP, habilita LAPIC local se permitido e executa `sti` uma única vez;
- consome um job;
- executa `pause`.

Não há wait queue de jobs nem wakeup IPI. AP ocioso permanece polling com `pause`. Isso reduz agressividade do spin, mas não é equivalente a dormir até trabalho chegar.

## Habilitação tardia de interrupções em AP

`smp_release_ap_irqs` só altera um flag. Cada worker observa o flag e ativa LAPIC/IF no seu próprio contexto.

O comentário da fonte registra por que essa etapa foi separada: permitir interrupções no AP durante uma cópia ATA impedia a cópia de terminar. AP pode, portanto, estar online para trabalho cooperativo antes de aceitar interrupções mascaráveis normais.

Essa diferença deve aparecer na documentação do boot e de SMP.

## Barreira global de idle

`job_wait_idle` espera `g_inflight == 0`. Enquanto espera, o BSP chama `job_worker_once(0)` e executa `pause`.

Assim o BSP ajuda a drenar a fila em vez de depender exclusivamente de APs. Em uniprocessador, isso é o que permite progresso.

In-flight incrementa no submit aceito e decrementa apenas após retorno da callback. Ele contabiliza tanto queued quanto executing.

A barreira é global para a fila inteira; não representa uma future associada a um conjunto específico de jobs.

## Self-test SMP

`smp_job_selftest` ignora o teste quando somente BSP está online. Primeiro envia 16 increments e verifica soma. Depois executa 32 waves de 128 jobs.

Quando a fila está cheia durante o teste, BSP consome um item e tenta novamente, com limite de spins que leva a panic se o sistema não progride.

O teste demonstra consumo concorrente básico e accounting. Não demonstra automaticamente fairness, ausência de starvation ou segurança de callbacks arbitrárias.

## Objeto kthread

Existem 32 slots estáticos. Cada `KT` contém used, done, callback, argument, oito TLS pointers, stack alocada e saved RSP.

Cada stack tem 32 KiB.

Kthread aqui não é processo nem hardware thread. É um callback do kernel com armazenamento de stack independente.

## Estado current por CPU

Um único `g_cur` global seria incorreto em SMP: duas CPUs poderiam sobrescrever identidade e saved stack uma da outra.

O código usa:
- `g_cur_cpu[SMP_CPU_CAP]` para id da kthread atual por CPU;
- `g_run_cpu[SMP_CPU_CAP]` para o objeto acessado pelo trampoline.

`kt_cpu` usa `smp_current_cpu` e aplica bounds. `smp_current_cpu` deriva índice do endereço da stack do AP.

O princípio é simples: estado necessário para restaurar RSP de uma CPU nunca pode ser compartilhado como se houvesse somente uma execução simultânea.

## Troca para stack privada

`kt_run` calcula o topo alinhado da stack, salva RSP atual, move RSP para a stack da kthread, chama `kt_trampoline` e restaura o RSP original depois que a callback retorna.

A asm declara clobbers e memory effect.

O trampoline busca a kthread pelo array per-CPU e chama sua função.

Não existe ponto de suspensão que salve contexto para retomar depois. A callback precisa retornar normalmente para `kt_run` concluir.

## Criação

`kthread_create` procura slot livre sob `g_slot_lock`, marca used e inicializa campos. A alocação de 32 KiB ocorre depois de liberar o lock.

Se `kmalloc` falhar, o slot é devolvido.

Com stack válida, o código tenta enviar `kt_job`. Se a fila estiver cheia, ele executa a kthread imediatamente na CPU chamadora, usando a mesma stack privada, marca done e retorna id.

Assim criação não é garantidamente assíncrona. Sob saturação, todo o callback pode executar antes de `kthread_create` retornar.

Essa propriedade precisa ser considerada por código que espera determinada ordem entre “criar” e “continuar”.

## Completion e join

`kt_job` instala current id, executa callback, marca `done=1` e restaura a identidade anterior.

`kthread_join` espera done. Em sistema com somente BSP, ele chama `job_worker_once` para que o job que está esperando possa ser executado. Com APs online, apenas usa `pause`; não puxa jobs arbitrários para o waiter.

O comentário explica que executar trabalho não relacionado dentro de um joiner em SMP provoca reentrância inesperada.

Ao terminar, join retira a stack e limpa o slot sob lock; `kfree` ocorre depois. O id pode ser reutilizado depois do join e não é uma identidade permanente.

## TLS

Cada kthread oferece oito slots de ponteiro. Fora de uma kthread, `kthread_tls` retorna zero; índices inválidos são rejeitados.

Esse mecanismo não é ELF TLS, não usa FS/GS base e não equivale ao thread-local storage completo de uma runtime de linguagem. É um array fixo controlado diretamente pelo kernel.

## KMutex

`KMutex` encapsula `Spinlock`. Lock gira; não existe sleep da kthread.

Critical section longa ou operação bloqueante sob KMutex desperdiça CPU e pode impedir progresso de trabalho dependente. O primitivo pressupõe regiões curtas.

Não há owner tracking, recursive mutex nem priority inheritance.

## KCond

`KCond` contém um sequence counter. Wait lê a sequência, libera mutex e gira até o contador mudar. Em UP, chama `job_worker_once`; em SMP, executa `pause`. Depois recupera mutex.

Signal apenas incrementa a sequência.

Não há lista de waiters, estacionamento de thread ou wake-one. Todos os pollers podem observar a mudança.

A aplicação continua obrigada a testar seu predicado protegido pelo mutex; uma mudança de sequence significa “houve sinal”, não “o predicado está garantidamente verdadeiro”.

## Integração com TLB fencing

Workers consultam o protocolo de TLB antes de trabalho normal. O protocolo classifica CPU como absent, online ou fenced. Um fenced CPU deixa de contar como online para futuras gerações, mas frames não podem ser reutilizados até existir evidência de invalidation e halt.

Se fenced, o worker deixa de executar callbacks.

Assim memory management pode impedir que código arbitrário continue em uma CPU cuja participação na coerência de traduções foi considerada insegura.

## Separação de process scheduling

`proc_switch` faz panic quando executado fora do BSP. Portanto, paralelismo de jobs em AP não é scheduler de processos de usuário em múltiplos cores.

APs executam kernel jobs/kthreads; address-space scheduling de processos permanece outro mecanismo e outro conjunto de invariantes.

## Ownership de memória

A fila possui cópias dos valores fn/arg, mas não possui o objeto apontado por arg. O slot de kthread possui sua stack desde criação bem-sucedida até cleanup do join.

Reserva de slot e alocação são separadas para não manter spinlock durante `kmalloc`. Falha desfaz o slot. Join também desassocia stack sob lock e libera memória fora.

Recursos internos da callback seguem o contrato da própria callback; framework não os coleta automaticamente.

## Deadlocks e falhas

Riscos centrais:
- argumento expirar antes do worker;
- esperar job segurando lock que o próprio job precisa;
- callback nunca retornar;
- lock-order cycle entre APs;
- critical section longa em KMutex;
- assumir assíncrono quando queue-full provoca execução síncrona;
- kthread tentar join de si mesma;
- reusar id/TLS após join;
- CPU fenced continuar participando indevidamente de trabalho normal.

Os primitivos são transparentes e simples, não possuem prevenção automática de deadlock. Lock ordering deve ser projetado por subsistema.

## Desempenho

Enqueue/dequeue são O(1), mas há um lock global; alta concorrência pode tornar esse lock hotspot. Depois do dequeue, callbacks rodam em paralelo.

Com 32 stacks de 32 KiB, o limite superior nominal para stacks ativas é cerca de 1 MiB, fora overhead.

AP ocioso faz polling; não há work stealing hierárquico, NUMA, prioridades ou affinity.

## Validação

O self-test SMP é evidência concreta do ring e execução multi-CPU. Testes adicionais devem cobrir wraparound, full/empty exatos, múltiplos produtores, nested submit, fallback síncrono, join UP/SMP, isolamento de TLS, signaling, alinhamento de stack, contenção de lock e fencing durante workload.

O Source Atlas publica integralmente job, kthread, spin, SMP e TLB protocol na revisão.

## Limitações atuais

É um modelo cooperativo de kernel work, não scheduler preemptivo de kernel threads. Não há yield/resume arbitrário, prioridade, affinity pública, sleep queues, cancelamento nem run state completo por thread.

Ainda assim é mais que uma fila de funções: stacks privadas e estado current por CPU permitem callbacks de kernel complexas em paralelo com isolamento de stack.

## Mapa de fonte

Fila: `kernel/metal/job.c`/`job.h`. Kthreads e wrappers: `kernel/metal/kthread.c`/`kthread.h`. Spin/atomics: `kernel/metal/spin.c`/`spin.h`. Lifecycle dos APs: `kernel/metal/smp.c`/`smp.h`. Fencing: `kernel/metal/tlb_proto.c`/`tlb_proto.h`. O Source Atlas preserva a íntegra na revisão `da3df29cb397932c43d32373871fb9380e688ade`.
