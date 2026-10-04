---
id: determinism-replay
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/chris_arch.h
  - chrisvm/machine/config.c
  - chrisvm/machine/machine.c
  - chrisvm/cpu/common/cpuid.c
  - chrisvm/cpu/common/state.c
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/devices/serial/serial.c
  - chrisvm/devices/fb/fb.c
  - chrisvm/frontend/view.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - ChrisConfig
  - ChrisArchitectureState
  - chris_config_init
  - chris_cpuid
  - chris_run
  - chris_trace_push
depends_on:
  - chrisvm-debugger
  - chris-architecture-state
  - chrisvm-devices
related:
  - chrisvm-machine
  - chrisvm-boot
  - emulator-theory
---

# Determinismo e replay no ChrisVM

## Escopo

Execução determinística e replay determinístico são propriedades relacionadas, mas diferentes.

Uma máquina virtual determinística produz o mesmo resultado arquiteturalmente relevante quando parte do mesmo estado completo e recebe a mesma sequência ordenada de entradas externas.

Replay determinístico exige algo adicional: o sistema registra informação suficiente sobre entradas não determinísticas e decisões de scheduling de uma execução para reproduzi-la depois.

Na revisão inspecionada do ChrisOS, o ChrisVM possui diversos componentes determinísticos por construção, mas **ainda não implementa um subsistema completo de record/replay**.

O campo de configuração:

    cfg.deterministic

existe e inicia com valor um, porém nenhum caminho de execução inspecionado altera comportamento com base nesse campo. Portanto, ele ainda não funciona como seletor real de modo.

A descrição correta do estado atual é:

    propriedades determinísticas em um interpretador pequeno e síncrono
    !=
    arquitetura de deterministic replay implementada

Essa distinção evita confundir intenção de projeto com comportamento existente.

## Por que determinismo importa

O ChrisVM é um ambiente controlado para desenvolvimento de sistema operacional e CPU.

Determinismo é especialmente útil para:

- reproduzir falhas de decoder ou execução;
- comparar revisões do emulador;
- validar exception delivery;
- executar regression tests;
- depurar falhas de boot;
- preservar evidência de resultados de pesquisa;
- futuramente comparar os backends ChrisCPU e ChrisHV.

Sem um contrato determinístico, uma falha dependente de timing, input assíncrono ou estado do host pode desaparecer na execução seguinte.

Com um contrato forte, uma execução pode ser identificada pelo estado inicial, stream de eventos e revisão da implementação.

## Modelo necessário

Um modelo simples de execução determinística pode ser escrito como:

    S_(n+1) = F(S_n, I_n, V)

onde:

- S_n é o estado completo da máquina antes do passo n;
- I_n é a entrada externa ordenada consumida nesse passo;
- V identifica a semântica versionada da máquina/CPU;
- F é a função de transição.

Replay exige registrar cada I_n que não possa ser derivado novamente de S_n e V.

Se wall clock, input de dispositivos, scheduling do host ou características da CPU física entrarem em F sem registro, o replay é incompleto.

## Superfície atual de configuração

ChrisConfig contém:

    int deterministic;

chris_config_init inicializa esse campo com:

    1

e o parser da linha de comando aceita:

    --deterministic

que também define o campo como um.

Não existe a opção oposta --nondeterministic.

Mais importante: os caminhos de machine, CPU, buses e devices inspecionados não usam cfg.deterministic para escolher uma semântica diferente.

Hoje o campo expressa política/intenção, não modo operacional.

## Flag ativada por padrão não é garantia

Um campo chamado deterministic com valor padrão um pode sugerir que já existe uma engine formal de execução determinística.

Não existe.

Uma configuração só representa um modo real quando controla comportamento observável ou uma política de validação.

Enquanto isso não ocorrer, cfg.deterministic não deve ser usado como evidência de que uma execução é replayable.

## Vantagem do interpretador single-thread

ChrisCPU executa uma única CPU virtual dentro de um único control loop do host.

ChrisMachine mantém exatamente um ponteiro ChrisCpu, e cpu_run avança uma instrução decodificada por vez.

Não existe scheduler SMP de múltiplas vCPUs no ChrisVM atual nem thread concorrente de device alterando estado guest-visible.

Isso remove uma importante fonte de não determinismo: interleaving entre vCPUs.

A ordem das instruções fica diretamente determinada pelo fluxo do interpretador, branches, exceptions e eventos injetados.

Essa propriedade é útil, mas não basta para provar determinismo completo.

## Instruction budget como fronteira reproduzível

chris_run recebe um max_steps explícito.

ChrisCPU mantém:

    cpu->steps

e incrementa o contador uma vez por iteração do interpretador depois de execução e arbitragem de IRQ.

Se nenhum outro stop reason ocorrer antes do orçamento terminar, a VM retorna:

    CHRIS_EXIT_STEP_LIMIT

Assim, instruction count forma uma fronteira reproduzível para workloads síncronos.

Um teste pode registrar que um guest executou N passos em vez de depender de tempo real do host.

## Progressão do TSC virtual

ChrisArchitectureState contém:

    uint64_t tsc

e o interpretador faz:

    cpu->arch.tsc++;

uma vez ao fim de cada iteração executada.

O valor está, portanto, ligado ao progresso lógico do interpretador e não ao wall clock.

Para paths de execução idênticos, a progressão é determinística.

Esse valor não representa ciclos físicos, frequência real ou nanossegundos.

É mais próximo de um contador lógico de tempo de instruções.

## Gap de exposição do TSC

O CPUID virtual anuncia o bit de feature TSC.

Entretanto, o modelo de operações do ChrisCPU inspecionado não define uma operação RDTSC dedicada no enum público de opcodes, e nenhum caminho de execução RDTSC do ChrisVM foi encontrado nas fontes revisadas.

Isso cria um gap de contrato:

- o estado arquitetural contém tsc;
- CPUID anuncia TSC;
- o bookkeeping do interpretador incrementa tsc;
- acesso guest via instrução não está estabelecido na implementação revisada.

Uma futura especificação determinística precisa resolver essa inconsistência antes de tratar o TSC virtual como ABI estável do guest.

## CPUID determinístico

chris_cpuid deliberadamente não encaminha o CPUID da CPU host.

Em vez disso, devolve identidade virtual fixa, incluindo o vendor string:

    "ChrisCPU    "

e um conjunto restrito de features.

Essa é uma decisão diretamente favorável a determinismo.

Se o host CPUID fosse exposto, o mesmo guest poderia observar features diferentes em máquinas de desenvolvimento diferentes.

O CPUID virtual atual remove essa fonte de variação.

## CPUID também precisa de proveniência

A saída atual do CPUID é fixa para a revisão, mas replay ainda depende de provenance.

Uma versão futura pode alterar:

- vendor;
- family/model;
- feature bits;
- extended leaves.

O mesmo guest poderia então escolher outro path de execução.

Logo, um replay record deve identificar a revisão do ChrisVM ou um virtual CPU model versionado, além de registrar eventos externos.

## Estado inicial da máquina

chris_machine_create usa allocations zeradas para a estrutura de machine e guest RAM.

O framebuffer também usa allocation zerada.

O serial é limpo durante attach.

chris_arch_reset zera o estado arquitetural e depois estabelece valores baseline conhecidos.

Para uma máquina recém-criada e uma configuração fixa, isso fornece estado inicial amplamente reproduzível.

O protocolo de boot então grava page tables, GDT e registradores iniciais de forma determinística.

## Estado inicial completo

Um futuro replay snapshot não pode conter apenas ChrisArchitectureState.

Reprodução completa também depende de:

- guest RAM;
- pixels e dirty state do framebuffer;
- registers e output buffer do serial;
- shutdown state;
- estado de devices I/O/MMIO;
- IRQ pendente;
- estado de debugger/runtime quando necessário.

Registradores de CPU são necessários, mas não suficientes.

## Serial síncrono

O device serial atual não possui input assíncrono do host nem timing engine.

Writes normais do guest executam sincronicamente e:

- adicionam byte ao TX buffer se houver capacidade;
- chamam o hook host opcional.

Não existe baud delay, RX thread ou clock de transmissão.

Portanto, a saída guest-visible é determinada pelo path de execução atual.

O callback host pode ter efeitos externos arbitrários, mas esses efeitos não pertencem ao estado arquitetural do guest.

## Fronteira do callback serial

O serial hook armazena function pointer e context do processo host.

Esses ponteiros nunca devem ser serializados como estado de replay.

O sistema deve registrar eventos e estado do hardware virtual, não endereços locais do processo.

Durante replay, uma frontend nova pode instalar outro output sink sem modificar a execução gravada do guest.

## Framebuffer

Writes do guest no framebuffer alteram sincronicamente o backing host e definem o dirty flag.

Não existem scanout clock, vblank, refresh assíncrono ou interrupt de vídeo.

Assim, stores guest idênticos produzem pixels idênticos.

O viewer SDL é apresentação host e deve permanecer fora do contrato de estado determinístico do guest.

## Tempo do SDL não é tempo da VM

chris_view_show usa SDL_GetTicks e SDL_PollEvent para apresentar um snapshot.

Essas chamadas dependem do tempo do host e de eventos da janela.

No desenho atual elas não controlam execução da CPU nem timing guest-visible.

São comportamento host não determinístico, mas não fazem parte da função de transição do guest atual.

A introdução futura de teclado/mouse mudaria essa fronteira e exigiria event recording.

## MMIO e port I/O

Callbacks de I/O e MMIO executam sincronicamente na mesma thread do interpretador.

Isso favorece reprodução porque seus efeitos ocorrem em program order direto.

Entretanto, as APIs genéricas aceitam contexts/callbacks definidos pelo host.

O ChrisVM não pode garantir determinismo para callbacks arbitrários externos sem exigir o mesmo contrato deles.

A built-in machine é mais restrita que a API genérica.

## Injeção de interrupts

A interface de backend inclui:

    inject_irq(cpu, vector)

ChrisCPU mantém uma única IRQ pendente em irq_pending/irq_vector.

O run loop verifica esse estado em um ponto definido após a execução da instrução.

Com o mesmo ponto de injeção, o comportamento é reproduzível.

O que ainda não existe é uma regra para transformar timing assíncrono do host em um ponto lógico determinístico.

Um replay system deveria registrar algo como:

    injetar vector V antes/depois do logical step N

em vez de depender de thread timing.

## STI delay e ordem de eventos

ChrisCPU modela atraso de uma iteração após STI por meio de cpu->sti_delay.

A arbitragem de IRQ ocorre depois da instrução e antes do incremento de steps/TSC.

Esses detalhes fazem parte da semântica determinística.

Se o log usar número de step, precisa especificar com precisão se o evento ocorre:

- antes de fetch;
- antes de execute;
- depois de execute;
- antes da arbitragem;
- depois do incremento do contador.

Coordenada ambígua causa divergência de um passo no replay.

## Wall clock do host

Nenhuma consulta de wall clock do host foi encontrada no core do run loop, criação de machine, serial ou framebuffer.

Isso é favorável à reprodução.

Existem usos de tempo no tooling e em UI fora desse núcleo, mas eles não são automaticamente guest time.

A fronteira precisa continuar explícita quando novos devices forem adicionados.

## Randomness

Nenhuma fonte de random foi encontrada no caminho principal revisado do ChrisVM.

Não existe RDRAND/RDSEED modelado nem RNG host conectado aos devices atuais.

Se randomness for adicionado, replay exigirá:

- geração determinística com seed registrado;
- ou gravação exata dos valores consumidos.

Encaminhar random do host sem registro quebraria replay.

## ELF como entrada externa

O ELF do guest é uma entrada externa.

Para reprodução, o registro deve identificar os bytes exatos, preferencialmente por cryptographic hash.

Apenas o path do arquivo é insuficiente porque seu conteúdo pode mudar.

A mesma regra vale para futuros disk images, firmware blobs e capture files de rede.

## Testes atuais

test_chrisvm.c executa vários workloads favoráveis a determinismo:

- byte sequences fixas;
- arithmetic;
- exceptions;
- serial loopback;
- shutdown;
- CPUID/MSR;
- MMIO;
- framebuffer;
- splash;
- fuzz de decoder gerado por sequência aritmética fixa.

Esses testes fornecem regression evidence porque controlam os inputs.

Eles não constituem teste de replay, pois nenhuma execução grava um log para ser consumido por uma segunda execução.

## O que um replay deveria registrar

Um formato mínimo futuro deveria conter:

- versão do formato;
- versão do virtual machine model;
- revisão/build;
- hash do guest image;
- RAM size e configuração;
- snapshot inicial ou identificador dele;
- toda entrada externa;
- coordenada de ordem de cada evento;
- IRQs injetadas;
- futuros eventos de teclado/mouse;
- dados recebidos de rede;
- completions de storage quando o timing puder variar;
- valores de random/time não determinísticos;
- digest do estado terminal.

Process-local pointers não podem fazer parte do formato.

## State digest

Validar replay não significa apenas obter o mesmo exit reason.

Um digest útil pode incluir:

- GPRs e control registers;
- RIP/RFLAGS;
- MSRs relevantes;
- hash da RAM;
- hash do estado de devices;
- hash do framebuffer;
- hash da saída serial;
- step count;
- virtual TSC;
- exit reason e exception metadata.

Esses valores ajudam a classificar onde a divergência apareceu.

## Checkpoints

Execuções longas se beneficiam de checkpoints.

Um checkpoint pode conter snapshot completo da VM e offset atual no event log.

O replay pode começar em K em vez de executar tudo desde o início.

O ChrisVM ainda não possui formato completo de machine snapshot; ChrisArchitectureState representa somente uma parte dele.

## Reverse debugging

Reverse execution ainda não existe.

Replay determinístico pode futuramente oferecer reverse debugging restaurando um checkpoint anterior e reexecutando até um step alvo.

Isso é mais prático que tentar inverter cada instrução e mutação de device.

O step counter e trace ring atuais são componentes úteis, mas insuficientes isoladamente.

## ChrisCPU e ChrisHV

O ideal é que o contrato de replay fique acima do CPU backend.

Se ChrisCPU e ChrisHV consumirem o mesmo estado versionado e o mesmo stream de eventos, replay poderá servir também para differential testing.

Hardware-assisted execution, porém, adiciona outras fontes de variabilidade:

- timing de interrupts do host;
- VM exits;
- hardware timers;
- timing de virtualização de devices;
- scheduling do host.

ChrisHV precisará de interceptação e controle explícitos; não pode simplesmente herdar as propriedades atuais do interpretador.

## SMP

O modelo single-vCPU atual evita scheduling nondeterminism.

SMP torna o problema muito mais difícil.

Um sistema SMP replayable precisa controlar ou registrar:

- ordem de scheduling das vCPUs;
- instruction/event quanta;
- ordem e destino de interrupts;
- interleavings de atomics;
- visibilidade de device completions;
- memory-order effects.

Registrar somente I/O externo não basta quando interleaving interno pode mudar.

## Memory model

Replay determinístico é mais estrito que simplesmente obedecer ao memory model.

Com múltiplas CPUs, várias execuções podem ser arquiteturalmente legais para o mesmo programa.

Replay precisa reproduzir a execução específica escolhida anteriormente.

Com a única vCPU atual, essa fonte de variação praticamente não existe.

## Semântica de falhas

Falhas também precisam ser reproduzíveis.

Se a execução termina com:

- CHRIS_EXIT_EXCEPTION;
- CHRIS_EXIT_TRIPLE;
- CHRIS_EXIT_UNMAPPED;
- CHRIS_EXIT_BREAK;
- CHRIS_EXIT_STEP_LIMIT;

o event log e o estado final devem permitir reconstruir o mesmo ponto de parada.

O ring de instruções recentes auxilia diagnóstico, mas não substitui event log completo.

## Observability não é determinismo

Trace não cria determinismo.

Instruction trace e recent-instruction ring mostram o que foi executado depois que as escolhas já ocorreram.

Replay log precisa registrar as escolhas que não poderiam ser recalculadas a partir do estado determinístico.

As responsabilidades devem permanecer separadas:

    trace = explicar o que executou
    replay log = reproduzir entradas/decisões não determinísticas

Ambos podem compartilhar step coordinate e metadata de revisão.

## Segurança dos replay artifacts

Um futuro event log poderá conter payloads e inputs do guest.

Packets de rede, teclado, disk data ou secrets podem aparecer em capturas.

Arquivos de replay devem ser tratados como potencialmente sensíveis.

A implementação atual ainda não possui replay artifact nem política de storage/encryption.

## Trade-offs de desempenho

O desenho atual síncrono possui baixo overhead conceitual.

Uma engine completa adicionará custo por:

- serialização de eventos;
- state hashing;
- memória de snapshots;
- checkpoint I/O;
- captura opcional de payloads.

O custo pode ser reduzido registrando somente inputs realmente não determinísticos e usando checkpoints periódicos em vez de copiar o estado a cada instrução.

## Validação necessária para um modo determinístico real

Antes de cfg.deterministic representar garantia operacional, testes automatizados deveriam provar ao menos:

1. duas execuções independentes com os mesmos inputs geram state digests iguais;
2. CPUID não depende da CPU host;
3. virtual time progride de modo idêntico;
4. serial e framebuffer terminam iguais;
5. IRQs gravadas em coordenadas lógicas reproduzem o mesmo path;
6. um event stream gravado conduz uma nova execução;
7. alteração ou ausência de evento é detectada como divergence;
8. replay é estável nos hosts suportados para a mesma versão do modelo;
9. mudanças incompatíveis de modelo/revisão são rejeitadas ou migradas explicitamente.

## Prioridades de implementação

Os próximos passos de maior valor são:

1. tornar cfg.deterministic operacional ou remover temporariamente a aparência de mode switch;
2. definir identificador versionado do virtual machine model;
3. definir ownership de snapshot completo além de ChrisArchitectureState;
4. formalizar coordenadas de evento em relação aos interpreter steps;
5. criar state hashing determinístico;
6. definir um event-log format pequeno;
7. implementar record/replay de IRQ como primeiro evento assíncrono;
8. registrar hash do ELF;
9. manter CPUID determinístico como contrato explícito;
10. resolver anúncio de TSC versus suporte guest-visible;
11. manter callbacks/UI do host fora do estado serializado;
12. criar replay tests antes de introduzir devices assíncronos;
13. estender deliberadamente o modelo para SMP e ChrisHV em vez de assumir que as propriedades atuais escalam.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, o ChrisVM é um interpretador single-vCPU síncrono com várias propriedades favoráveis à reprodução: CPUID virtual fixo, allocations iniciais zeradas, step counter lógico, TSC virtual incrementado pelo progresso do interpretador, devices integrados síncronos e ausência de dependência de wall clock/RNG no core revisado. Contudo, cfg.deterministic não é consumido como switch de execução e não existem event recorder, replay reader, snapshot completo da máquina, checkpoints ou reverse execution. O ChrisVM possui fundamentos determinísticos, não um subsistema completo de deterministic replay.
