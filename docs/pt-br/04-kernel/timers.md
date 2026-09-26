---
id: timers
lang: pt-br
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/pit.c
  - kernel/metal/pit.h
  - kernel/metal/irq.c
  - kernel/metal/proc.c
  - kernel/metal/start.c
symbols:
  - pit_init
  - pit_ticks
  - proc_on_tick
  - proc_slice_due
  - proc_slice_ack
depends_on:
  - pic-apic-ioapic
  - idt-exceptions
related:
  - process-lifecycle
  - interrupts-smp
---

# PIT, temporização e semântica do scheduler tick

## Escopo

Uma interrupção periódica converte passagem de tempo físico ou virtualizado em eventos discretos observáveis pelo kernel. Esses eventos podem alimentar contabilidade, sleep, timeouts, preempção, animação, retransmissões e profiling, mas cada função é conceitualmente distinta. O ChrisOS programa atualmente o Programmable Interval Timer legado para 60 Hz. O handler incrementa um contador global e marca que um slice de processo venceu. Ele não realiza uma troca completa de contexto dentro da IRQ.

Este capítulo separa programação do PIT, roteamento, aritmética de ticks, sinalização do scheduler e limitações de um timer legado fixo.

## Modelo do PIT

O PIT 8253/8254 compatível recebe clock de aproximadamente 1,193182 MHz. O canal 0 é tradicionalmente ligado à IRQ0. Software programa um divisor:

```text
f_saida = 1.193.182 / divisor
```

O ChrisOS define `PIT_INPUT_HZ = 1193182` e usa divisão inteira.

O divisor precisa caber em 16 bits. Se a frequência pedida for tão alta que o divisor inteiro vire zero, ou tão baixa que o divisor ultrapasse `0xffff`, `pit_init` falha. Frequência zero é rejeitada antes da divisão.

## Sequência de programação

`pit_init(frequency_hz)`:

1. valida frequência;
2. calcula divisor;
3. zera `ticks`;
4. registra `pit_irq` na IRQ0;
5. grava `0x36` no control port `0x43`;
6. grava low byte e high byte do divisor no canal 0, porta `0x40`;
7. desmascara IRQ0 no PIC.

`0x36` seleciona canal 0, acesso low/high, modo 3 e contagem binária. O modo 3 é o square-wave generator tradicional para ticks periódicos.

O handler é instalado antes da linha ser liberada, garantindo que a primeira interrupção já tenha callback válido.

## Frequência usada no boot

`kstart` executa `pit_init(60)` e entra em panic se o valor for inválido.

O período nominal é:

```text
T = 1 / 60 s ≈ 16,6667 ms
```

Como `1193182 / 60` é divisão inteira, o divisor gravado é 19.886. A frequência real é a frequência de entrada dividida por 19.886, próxima de 60 Hz mas não exatamente 60,000000. Um relógio de longo prazo baseado somente nesses ticks acumularia erro de quantização e erro do oscilador.

No ChrisOS atual, o tick serve principalmente como cadência/sinal de scheduler, não como clocksource de alta precisão.

## Caminho da interrupção

Canal 0 afirma IRQ0. O PIC remapeado entrega IRQ0 como vetor 32. O stub comum da IDT cria `irq_frame` e chama `irq_dispatch`. Para vetores 32–47, o dispatcher obtém o número da IRQ; IRQ0 encontra `pit_irq` na tabela.

Depois do callback, `irq_dispatch` envia EOI via `irq_eoi`. O driver PIT não programa diretamente o command port do PIC.

Essa separação mantém “semântica do tempo” no driver e “finalização no controlador” na camada genérica de IRQ.

## Contador de ticks

`ticks` é `volatile uint64_t`. O handler executa incremento; `pit_ticks()` retorna o valor.

`volatile` informa ao compilador que o objeto pode mudar de forma assíncrona e evita certas otimizações de código single-thread. Ele não transforma read-modify-write em operação atomicamente correta para múltiplas CPUs nem estabelece memory ordering completo.

No modelo atual, IRQ0 está ligada ao caminho legado orientado ao BSP. Se futuramente o timer for entregue em vários CPUs, ownership e atomicidade precisarão ser redefinidos.

Overflow de 64 bits a 60 Hz está muito além da vida prática do sistema. O problema relevante é interpretação temporal e sincronização, não wrap iminente.

## Sinalização do scheduler

`pit_irq` executa apenas:

```text
++ticks;
proc_on_tick();
```

`proc_on_tick` faz `g_slice = 1`. Ele não salva contexto completo, não escolhe processo, não muda CR3 e não salta para outra tarefa dentro do handler.

Outras partes podem consultar `proc_slice_due()` e limpar com `proc_slice_ack()`. O modelo é de decisão adiada: a IRQ sinaliza que existe um boundary de scheduling pendente; um ponto seguro posterior decide como consumir o sinal.

Isso mantém o handler pequeno e separa mecanismo de timer da política de scheduling.

## O que falta para preempção geral

Um scheduler preemptivo completo precisa preservar todo o contexto da tarefa interrompida, atualizar estado, escolher runnable target, possivelmente trocar address space, definir stack de kernel/user apropriada, restaurar registradores e retornar para o novo contexto.

Em SMP, run queues, current task e context switches precisam ter ownership por CPU e sincronização. Processos em CPUs diferentes adicionam requisitos de TLB e page-table lifecycle.

O `g_slice` global é deliberadamente mais simples. Não deve ser descrito como “scheduler preemptivo completo” apenas por ser disparado por timer.

## Relação com a cadência do desktop

O boot imprime “desktop 60Hz” antes de `desktop_run`. PIT e desktop compartilham uma cadência nominal, mas não são o mesmo mecanismo. A IRQ periódica fornece eventos de tempo/slice; o loop gráfico tem suas próprias operações de update/present.

Documentação técnica não deve confundir refresh físico do monitor, taxa de apresentação, taxa de simulação e frequência de IRQ sem uma ligação explícita no código.

## Unidades e conversões

Com 60 Hz fixos:

```text
segundos ≈ ticks / 60
milissegundos ≈ ticks * 1000 / 60
```

Conversões inteiras truncam. Para deadlines, comparar diferenças diretamente no domínio de ticks costuma ser mais seguro do que converter repetidamente.

A API atual expõe ticks crus. Política de unidade e timeout pertence às camadas superiores.

## Latência e jitter

O PIT gera eventos periódicos, mas execução do handler pode atrasar. IF pode estar zero, outra atividade privilegiada pode ocupar CPU, uma NMI pode intervir, o host de uma VM pode desagendar a vCPU e critical sections podem ampliar latência.

Portanto, um tick significa “uma interrupção periódica foi atendida”, não “exatamente 16,6667 ms se passaram desde o último handler” em todas as circunstâncias.

Qualquer afirmação de real-time precisaria de medidas de worst-case latency e de limites para interrupções desabilitadas. O código atual não estabelece hard real-time guarantees.

## PIC mask versus IF

`pic_init` mascara todas as IRQs. `pit_init` remove a máscara da IRQ0. Mais tarde `sti` habilita interrupções mascaráveis na CPU.

São camadas independentes. IRQ0 desmascarada ainda não entra se IF estiver zero. IF=1 também não faz uma linha mascarada no PIC ser entregue.

O ChrisOS usa isso durante o boot para configurar controladores e handlers com interrupções globais ainda desabilitadas e escolher explicitamente o momento de permitir entrada assíncrona.

## Política de storm

O dispatcher possui limite cumulativo de 10.000 hits para IRQs maiores que zero. IRQ0 é excluída. Um PIT normal a 60 Hz alcançaria 10.000 ticks em aproximadamente 166,7 segundos; aplicar a mesma política interromperia o relógio depois de poucos minutos.

A exceção demonstra que IRQ0 é esperada como fluxo permanente e de alta contagem.

## Concorrência e ordering

Tick e slice flag são globais simples. Dentro do modelo atual de processo preso ao BSP isso atende ao papel limitado. Não constitui framework de accounting SMP.

Se outra CPU depender de ordering forte sobre `ticks` ou `g_slice`, `volatile` não basta; seriam necessários atomics, locks ou desenho per-CPU. Um scheduler SMP também não deveria normalmente depender de um único slice flag global para decisões independentes por CPU.

A distinção correta é “adequado ao execution model atual”, não “abstração universal de timer”.

## Modos de falha

`pit_init` falha para frequência zero, divisor zero ou divisor > 16 bits. `kstart` considera a ausência do timer esperado uma falha fatal.

Control word incorreto ou bytes do divisor fora de ordem alteram o período. IRQ0 esquecida em mask produz contador parado. Linha liberada antes do handler arrisca entrada sem callback correto. EOI ausente pode bloquear interrupções seguintes. IF permanentemente zero impede entrega embora PIT continue contando no hardware/emulador.

Em máquina virtual, emulação do PIT e scheduling do host podem introduzir jitter adicional.

## Evolução arquitetural

x86 moderno oferece LAPIC timer, HPET e TSC invariável. Uma arquitetura madura pode separar clocksource preciso de clock event per-CPU.

O ChrisOS já possui LAPIC para EOI/IPI, mas a revisão analisada não contém implementação documentada de LAPIC timer. Isso não deve ser apresentado como concluído.

Uma futura camada temporal deveria separar explicitamente:
- clocksource monotônico;
- dispositivo de clock event;
- accounting do scheduler;
- filas de sleep/timeout;
- wall clock exposto ao usuário.

O PIT atual cobre somente evento periódico, tick cru e sinal de slice.

## Validação

O código fornece evidência direta do clock de entrada, checks do divisor, `0x36`, escrita low/high, registro do handler, unmask de IRQ0, incremento de tick e marcação de slice.

Testes de runtime podem contar ticks contra intervalo conhecido, verificar monotonicidade, confirmar continuidade depois de 10.000 IRQs, observar comportamento com IF temporariamente zero e medir jitter sob I/O/SMP. A validação de scheduler deve demonstrar separadamente onde `proc_slice_due` é consumido.

## Limitações atuais

Timer fixado em 60 Hz no boot, entrega PIT/PIC, contador cru e slice flag global. Não há clocksource calibrado em nanossegundos nem clock events per-CPU neste caminho. É um mecanismo suficiente para a cadência atual, não um subsistema temporal moderno completo.

## Mapa de fonte

`kernel/metal/pit.c`/`pit.h` implementam PIT e ticks. `kernel/metal/irq.c` faz dispatch/EOI. `kernel/metal/proc.c` mantém o slice flag. `kernel/metal/start.c` escolhe 60 Hz e define a ordem do boot. O Source Atlas contém todos esses arquivos integralmente na revisão `da3df29cb397932c43d32373871fb9380e688ade`.
