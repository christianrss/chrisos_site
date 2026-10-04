---
id: performance-measurement
lang: pt-br
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/bench.c
  - kernel/gfx/bench.h
  - kernel/metal/pit.c
  - kernel/metal/start.c
  - kernel/wm/main.c
  - compiler/lang_pipeline.c
  - kernel/lang/clvm_sys.c
  - kernel/tools/shell.c
  - APPS/SHELL/SHELL.CC
  - APPS/TASKMGR/TASKMGR.CC
  - tools/test_jit_bench.c
  - kernel/fs/cfs.c
  - kernel/fs/storage_limits.h
  - kernel/gfx/vgpu.c
  - kernel/gfx/shader/sh_api.c
  - makefile
symbols:
  - bench_frame_tick
  - bench_fps_estimate
  - bench_frame_ms
  - bench_frame_p50_ms
  - bench_frame_p95_ms
  - pit_ticks
  - lang_tick
  - cfs_cache_hits
  - cfs_cache_misses
depends_on:
  - host-tests
  - qemu-gates
  - hardware-gates
related:
  - fuzzing
  - fault-injection
  - jit
  - chrisfs-cache
  - virtio-gpu-virgl
---

# Medição de desempenho

## Escopo

Trabalho de performance só é válido quando a grandeza medida está definida com precisão.

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, o ChrisOS possui mecanismos reais de medição:

- cadência de desktop/frame derivada do PIT;
- amostras de frame time e valores p50/p95;
- benchmark host comparando interpretação CLVM com execução JIT;
- contadores de cache hit/miss do ChrisFS;
- telemetria de heap/PMM exposta a aplicações;
- contadores internos de ciclos no shader compiler;
- contadores internos do VirtIO-GPU e budgets baseados em TSC.

Esses mecanismos são úteis, mas não formam um único subsistema de profiling.

O ChrisOS atual **não** possui profiler geral de CPU, abstração de PMU, pipeline de flame graph, accounting de CPU por processo, tracing system-wide, relógio monotônico calibrado em alta resolução ou banco automatizado de performance regressions.

Este capítulo separa três classes:

1. telemetria de runtime;
2. regression benchmarks;
3. contadores diagnósticos internos.

## Modelo de medição

Todo resultado de performance deve ser tratado como uma tupla:

[
P = (R, E, W, M, S)
]

onde:

- (R) é a revisão exata do ChrisOS;
- (E) é o ambiente de execução;
- (W) é o workload;
- (M) é o método de medição;
- (S) é o conjunto de samples.

Um número sem essas dimensões não é evidência reproduzível.

"60 FPS", por exemplo, é incompleto sem saber se a execução ocorreu em QEMU TCG, KVM ou hardware físico, qual resolução estava ativa, qual workload existia e o que o contador de FPS realmente conta.

## Fontes de tempo atuais

O ChrisOS usa mais de uma fonte de tempo.

### PIT

O kernel inicializa o programmable interval timer com:

    pit_init(60)

A IRQ do PIT incrementa o contador global `ticks`.

O desktop espera avanço desse tick entre frames.

Assim o PIT é a principal fonte de cadência do desktop atual.

### Relógio monotônico do host

`tools/test_jit_bench.c` usa uma fonte monotônica de alta resolução do host:

- `clock_gettime(CLOCK_MONOTONIC)` em POSIX;
- `QueryPerformanceCounter` em Windows.

É adequado para o benchmark host porque mede elapsed time real em torno do interpreter e do JIT.

### RDTSC

O shader compiler e o VirtIO-GPU usam `rdtsc` internamente.

RDTSC fornece um timestamp counter semelhante a ciclos, mas diferenças brutas não são automaticamente unidades portáveis de tempo.

Sem calibração, verificação de invariant TSC e disciplina de serialização, esses valores devem ser tratados como deltas diagnósticos locais, não nanosegundos.

## Desktop loop e cadência

O loop atual executa:

    net_poll()
    clvm_sys_frame(ticks)
    lang_tick(ticks)
    desktop_frame(ticks)
    gfx_present()

e depois espera o PIT avançar.

Com timer configurado a 60 Hz, o loop é ritmado para aproximadamente uma iteração por intervalo.

Por isso o kernel reporta:

    ChrisOS: desktop 60Hz

Isso descreve a cadência configurada, não prova que todo frame termina exatamente em 16,67 ms.

Um frame lento pode consumir mais de um tick.

## Estimador de FPS

`bench_frame_tick` é chamado por `lang_tick`.

A função incrementa um frame counter e, quando pelo menos 60 PIT ticks se passaram, salva a contagem acumulada como estimativa de FPS.

Conceitualmente:

[
FPS approx rac{frames}{Delta ticks / 60}
]

Quando a janela é exatamente 60 ticks, o valor salvo equivale ao número de frame ticks observados em aproximadamente um segundo.

O shell nativo oferece:

    bench

que imprime esse valor.

O shell ChrisC/CLVM oferece:

    fps

e também imprime p50/p95.

## O que o FPS realmente mede

O contador atual não é hardware counter de GPU.

Ele não vem de scanout completion, vblank ou refresh físico do monitor.

Ele conta chamadas a `bench_frame_tick`, executadas em `lang_tick` dentro do desktop loop.

Logo, a interpretação correta é:

> cadência observada do desktop loop do ChrisOS no ponto de tick do runtime de linguagem.

É útil para regressions, mas não deve ser vendido como medição direta de throughput da GPU.

## Frame-time samples

A camada de benchmark registra ticks decorridos entre chamadas consecutivas.

A conversão atual é:

[
ms = rac{ticks cdot 1000 + 30}{60}
]

com aritmética inteira.

São mantidas as últimas 64 amostras.

É uma janela rolling de tamanho fixo, sem dynamic allocation.

## Resolução temporal

Como a medição usa PIT de 60 Hz:

[
T = rac{1}{60}s approx 16,67ms
]

A conversão quantiza os resultados aproximadamente nessa escala.

Um frame de 4 ms e outro de 14 ms podem ser indistinguíveis se ocorrerem dentro do mesmo intervalo do PIT.

Por isso p50/p95 atuais detectam stalls grosseiros e perda da cadência de 60 Hz, mas não são latency measurements de alta resolução.

## p50 e p95

Quando um percentile é solicitado, as amostras são copiadas e ordenadas.

Para (N) amostras:

[
index = rac{(N-1)cdot percentile}{100}
]

Para p50:

[
index_{50} = leftlfloorrac{(N-1)50}{100}ightfloor
]

Para p95:

[
index_{95} = leftlfloorrac{(N-1)95}{100}ightfloor
]

Com no máximo 64 samples, o selection sort é (O(N^2)), mas o custo absoluto permanece limitado.

Essas funções servem para telemetria, não para inner loop de alta frequência.

## Telemetria visível ao usuário

O Task Manager mostra:

- heap used KB;
- heap free KB;
- PMM free pages;
- frame p50;
- frame p95.

O shell das aplicações mostra FPS e percentis.

O dispatcher CLVM fornece essas métricas via runtime services.

Portanto a telemetria não existe apenas como debug kernel; aplicações conseguem consultar recursos e frame behavior por interfaces definidas.

## Recursos não são tempo

Heap e PMM medem capacity/pressure, não velocidade.

Ainda assim são métricas relevantes para performance porque pressão de memória pode explicar latency, allocation failure e scaling.

Um registro útil pode combinar:

[
Latency, Throughput, Memory, Cache
]

em vez de reportar apenas elapsed time.

## Contadores de cache ChrisFS

O ChrisFS mantém:

    cache_hits
    cache_misses

O cache possui 64 linhas.

Hit ocorre quando o LBA solicitado já está em memória.

Miss é incrementado antes de ler do block device.

Os contadores são acessíveis por:

    cfs_cache_hits()
    cfs_cache_misses()

e expostos ao runtime CLVM.

A taxa básica é:

[
H = rac{hits}{hits + misses}
]

quando o denominador é diferente de zero.

## Interpretando hit ratio

Hit ratio alto não significa automaticamente filesystem rápido.

Pode indicar:

- workload muito repetitivo;
- working set pequeno;
- metadata lida várias vezes;
- benchmark que nunca supera 64 cache lines.

Um workload streaming pode naturalmente ter ratio menor.

Assim a análise precisa registrar formato do workload, bytes e operações, não apenas o ratio.

## Reset dos contadores

Os contadores reiniciam quando o cache é resetado.

Depois disso são cumulativos.

Comparações corretas devem usar:

- filesystem recém-montado/resetado;
- ou diferenças entre snapshots.

Comparar um total antigo com workload curto gera conclusão enganosa.

## Benchmark JIT

O regression gate explícito é:

    host-jit-bench-test

Ele compila um pequeno programa ChrisC com loop contínuo de pixels.

São criados estados equivalentes para interpreter e JIT.

Os dois caminhos passam por warm-up.

Depois executam workload limitado com:

    BENCH_ROUNDS = 400
    BENCH_BUDGET = 12000

O elapsed time do host é medido para cada caminho.

## Métrica de speedup

A métrica é:

[
speedup = rac{T_{interp}}{T_{jit}}
]

O gate exige:

    MIN_SPEEDUP = 5.0

Se:

[
speedup < 5
]

o teste falha.

O output imprime segundos do interpreter, segundos do JIT e ratio.

Performance, nesse caso, é condição executável de regressão.

## O que o threshold 5x prova

O threshold prova algo estreito:

> para esse programa, build flags e host representados pelo teste, o JIT medido deve ser pelo menos cinco vezes mais rápido que o interpreter.

Não prova:

- todo programa ChrisC obtém 5x;
- o kernel é 5x mais rápido;
- aplicações físicas do ChrisOS sempre obtêm o mesmo ratio;
- compile latency e cache effects são desprezíveis em qualquer workload.

É regression guard, não afirmação universal.

## Condições de compilação

O benchmark é compilado no host com `-O2` e sources do projeto.

Resultados dependem de:

- CPU do host;
- compiler/version;
- otimização;
- sistema operacional;
- frequency scaling;
- background load;
- thermal state.

O ratio tende a ser mais comparável que segundos absolutos entre máquinas diferentes, mas ainda pode variar.

## Warm-up

Interpreter e JIT executam algumas rodadas antes da medição.

Isso reduz efeitos de:

- instruction/data cache frio;
- initialization one-time;
- lazy allocation;
- scheduling transients.

Não elimina toda variância.

Resultados publicados devem usar múltiplas repetições.

## Disciplina estatística

Uma única medição não é distribuição.

Para comparação séria, colete várias execuções independentes.

Resumos úteis:

- median;
- p95;
- mínimo/máximo;
- interquartile range;
- coefficient of variation quando aplicável.

Para revisões A e B:

[
Delta% = rac{B-A}{A}	imes100
]

O ambiente precisa permanecer controlado antes de atribuir diferença ao código.

## Caveat do QEMU

A maioria dos gates usa TCG.

TCG é adequado para validação funcional, mas é proxy ruim para performance física.

O timing depende de:

- dynamic translation;
- host scheduler;
- emulated timers;
- device models;
- ausência de latency física real.

Duração de gate QEMU não deve ser publicada como benchmark de hardware.

Pode detectar regressions relativas grandes em ambiente controlado, mas deve ser classificada separadamente.

## Caveat do KVM

KVM aproxima melhor a velocidade da CPU real, porém devices virtuais continuam diferentes dos físicos.

Benchmark KVM deve registrar:

- host CPU;
- vCPU count;
- CPU model exposto;
- memória;
- versão QEMU;
- device models;
- host kernel/hypervisor;
- affinity/frequency policy quando relevante.

## Benchmark em hardware físico

Hardware real acrescenta firmware, buses, controllers e devices reais.

Também acrescenta variância.

Um registro físico deve incluir:

- machine profile;
- firmware;
- power/governor mode;
- temperatura quando relevante;
- memory configuration;
- storage device;
- framebuffer resolution;
- boot mode;
- ChrisOS revision;
- image hash;
- número de repetições.

Sem esses dados, diferenças são difíceis de atribuir.

## Cycles do shader compiler

O shader compiler registra deltas RDTSC para fases como:

- lexing;
- parsing;
- semantic analysis;
- IR optimization/verification;
- TGSI emission.

Os valores ficam nas estruturas internas do compiler.

Servem para atribuição de custo por fase.

Na revisão atual devem ser classificados como diagnóstico interno, não ABI pública estável.

## Efeito do shader cache

O subsistema mantém pequeno cache de compilação.

Cache hit pode evitar fases caras.

Um benchmark deve dizer se mede:

- cold compile;
- warm cached compile;
- repeated same-source;
- workload misto.

Caso contrário, pode medir cache behavior em vez da velocidade do compiler.

## Contadores VirtIO-GPU

O VirtIO-GPU mantém contadores internos como:

- rectangles;
- pixels;
- bytes;
- full updates;
- partial updates;
- waits;
- interrupt count.

Também usa budgets baseados em RDTSC nos caminhos de espera.

Eles ajudam a identificar se o workload é dominado por:

- full-frame transfer;
- partial updates;
- synchronization waits;
- command/interrupt behavior.

São instrumentação interna e ainda não uma interface estável de statistics.

## Throughput

A forma genérica é:

[
Throughput = rac{work}{time}
]

Em storage, work pode ser bytes ou IOPS.

Em rendering, frames, pixels ou triangles.

Em compilation, source bytes ou compilation units.

O benchmark precisa definir work.

"Mais rápido" sem denominador não é throughput.

## Latency versus throughput

Latency e throughput respondem perguntas diferentes.

É possível aumentar throughput total e piorar tail latency.

Em workload interativo do ChrisOS, p95 de frame pode importar mais que FPS médio, pois stutter é evento de cauda.

Para storage bulk ou compilation, throughput pode dominar.

A métrica precisa seguir o objetivo do usuário/subsistema.

## Tail performance

O p95 existente é importante porque average esconde stalls.

Se 95 frames levam um tick e cinco levam seis ticks, a média pode parecer aceitável enquanto a interação é instável.

Instrumentação futura deve estender histogramas/percentis para:

- scheduler wake latency;
- storage I/O;
- syscalls;
- JIT compile;
- graphics submit/present.

## Overhead da medição

Instrumentação altera o sistema medido.

Exemplos:

- serial logging custa tempo;
- RDTSC não é gratuito;
- sorting de percentile consome CPU;
- debug builds mudam code layout;
- tracing perturba scheduler timing.

Deve-se usar a menor instrumentação capaz de responder à pergunta.

Entre revisões, o método precisa permanecer igual.

## Baseline e orçamento de regressão

Performance fica acionável quando há baseline e limite aceitável.

Para métrica (m):

[
Regression = rac{m_{new}-m_{base}}{m_{base}}
]

Para latency, onde menor é melhor, valor positivo é regressão.

Para throughput, a convenção precisa ser invertida ou explicitada.

O JIT já aplica esse princípio pelo mínimo de speedup.

Outros subsistemas ainda não possuem budgets automatizados equivalentes.

## Facilities ausentes

Na revisão analisada ainda faltam:

- monotonic clock calibrado em micro/nanosegundos;
- camada de calibração/invariant TSC;
- CPU accounting por process;
- scheduler latency histogram;
- syscall latency histogram;
- benchmark de storage latency/IOPS;
- network throughput/latency;
- timestamps nativos de GPU;
- PMU counters para instructions/cache misses/branches;
- histórico contínuo de benchmarks por commit;
- detecção estatística automática de regressions.

São roadmap, não features atuais.

## Protocolo recomendado

Para qualquer resultado publicável:

1. registrar revision e image hash;
2. registrar hardware/QEMU environment;
3. definir workload exatamente;
4. indicar cold/warm state;
5. definir métrica/unidade antes do teste;
6. repetir o suficiente para observar variância;
7. preservar raw samples;
8. reportar median e tail/dispersion;
9. comparar com baseline presa à revisão;
10. não misturar TCG, KVM e hardware físico em série sem identificação.

## Próximos passos

Prioridades:

1. clock monotônico calibrado em micro/nanosegundos;
2. separar desktop-loop, render-submit e present real;
3. expor snapshots estáveis de graphics/cache/resource stats;
4. adicionar storage throughput/latency microbenchmarks;
5. adicionar scheduler/syscall latency histograms;
6. usar classes de CI reproduzíveis para benchmarks;
7. preservar resultados como artifacts;
8. acompanhar performance entre commits;
9. introduzir thresholds apenas depois de entender variance;
10. futuramente adicionar PMU/performance counters em x86-64 físico.

## Nota de revisão

Este capítulo foi reconciliado contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

Nesta revisão já existe evidência real de performance: cadence/percentis de frame, regression gate de speedup JIT, cache counters do filesystem e diagnósticos de subsistemas. A principal limitação é precisão e unificação: os instrumentos atuais respondem perguntas locais, mas ainda não formam um framework geral de profiling e benchmarking.
