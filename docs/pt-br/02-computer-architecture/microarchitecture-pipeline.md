---
id: microarchitecture-pipeline
lang: pt-br
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.h
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/cpu/emulator/execute.c
symbols:
  - ChrisArchitectureState
  - ChrisInsn
  - ChrisCpu
  - fetch_insn
  - cpu_run
  - chris_decode
  - chris_execute
depends_on:
  - cpu-datapath-isa
  - clock-timing
  - registers-counters
related:
  - pipeline-hazards-forwarding
  - branch-prediction-speculation
  - out-of-order-renaming-retirement
  - cache-hierarchy
---

# Microarquitetura da CPU e pipelining

## Escopo: a ISA é o contrato; a microarquitetura é a implementação

Uma arquitetura de conjunto de instruções define o estado visível ao software e as regras pelas quais instruções transformam esse estado. A microarquitetura é um mecanismo concreto que realiza essas regras. Dois processadores podem implementar a mesma ISA x86-64 usando larguras de fetch, profundidades de pipeline, unidades de execução, hierarquias de cache, preditores de desvio, estruturas de renomeação e mecanismos de retirement muito diferentes.

Essa distinção é essencial no ChrisOS porque o projeto toca os dois lados do contrato. O kernel consome a interface arquitetural x86-64. O ChrisCPU, dentro do ChrisVM, produz um modelo executável de parte dessa interface. A implementação atual do ChrisCPU é um interpretador de instruções: busca bytes, decodifica uma instrução, executa sua semântica, avança ou substitui RIP, trata uma fronteira de interrupção, incrementa contadores e então inicia a próxima iteração. Ela não modela um pipeline de hardware sincronizado por clock, registradores de pipeline, ocupação por estágio, caminhos de forwarding, largura de issue ou contenção de recursos ciclo a ciclo.

Isso não torna a teoria de pipeline irrelevante. O sistema operacional roda em processadores reais com pipeline, e um futuro modelo temporal do ChrisCPU exigiria estado microarquitetural explícito. O objetivo deste capítulo é, portanto, duplo:

1. explicar como pipelining transforma um datapath sequencial em uma implementação sobreposta; e
2. estabelecer exatamente onde termina a abstração atual do ChrisCPU, para que conceitos de temporização não sejam confundidos com comportamento implementado.

![Pipeline in-order conceitual e fronteira de retirement arquitetural](../../assets/diagrams/microarchitecture-pipeline-pt-br.svg)

## De um caminho combinacional longo para execução em estágios

Considere um processador simples que realiza todo o trabalho de uma instrução entre duas atualizações de estado arquitetural. Um caminho conceitual pode incluir:

1. seleção do endereço da instrução;
2. leitura dos bytes da instrução;
3. decodificação de opcode e operandos;
4. leitura dos operandos em registradores;
5. geração de endereço efetivo;
6. operação aritmética ou lógica;
7. acesso à memória de dados;
8. seleção de resultado;
9. escrita do destino e das flags;
10. seleção do próximo endereço de instrução.

Se todo esse caminho precisa ser concluído dentro de um único período de clock, o período mínimo deve exceder o pior atraso do caminho completo mais as margens de temporização dos registradores:

    Tclock >= Tcomb,max + Tsetup + Tskew

em que Tcomb,max é o maior atraso combinacional entre elementos de estado, Tsetup é o requisito de setup do registrador de destino e Tskew representa margem da distribuição de clock.

A frequência máxima é aproximadamente:

    fmax <= 1 / Tclock

Dividir o caminho em k estágios insere registradores entre grupos de lógica. O período idealizado passa a ser limitado pelo estágio mais lento em vez da soma de todos os atrasos:

    Tclock,pipeline >= max(Tstage,1 ... Tstage,k) + Treg-overhead

O termo "idealizado" é importante. Os estágios raramente ficam perfeitamente balanceados, registradores de pipeline têm custo de tempo e energia, e novos estágios aumentam penalidades de controle e dependência. Pipelining pode aumentar **throughput** ao sobrepor instruções; ele não implica que a **latência** de uma instrução individual fique k vezes menor.

## Latência, throughput e ocupação

Três grandezas precisam ser mantidas separadas:

| Grandeza | Significado | Exemplo em um pipeline escalar de cinco estágios |
|---|---|---|
| Latência da instrução | Tempo desde a entrada da instrução no primeiro estágio até seu resultado se tornar arquiteturalmente utilizável | aproximadamente cinco tempos de estágio para uma instrução simples |
| Throughput | Taxa de conclusão em regime permanente quando o pipeline está cheio | idealmente uma instrução por ciclo |
| Ocupação | Número de instruções simultaneamente presentes no estado do pipeline | até aproximadamente cinco no modelo simples |

Para n instruções independentes atravessando k estágios de mesma latência, um pipeline ideal exige aproximadamente:

    ciclos = k + n - 1

O primeiro resultado aparece após k ciclos; depois disso pode surgir um resultado a cada ciclo. Uma máquina sem pipeline que precise de k intervalos equivalentes por instrução usaria aproximadamente n*k intervalos. O ganho de throughput se aproxima de k apenas em condições ideais e para n grande.

Execução real se afasta dessa fórmula devido a stalls, flushes, acessos de memória de latência variável, unidades funcionais de vários ciclos, interrupções, exceções e conflitos de recursos.

Uma identidade comum de desempenho é:

    tempo de execução = contagem de instruções * CPI * período de clock

em que CPI é ciclos por instrução. Um pipeline mais profundo pode reduzir o período de clock e, ao mesmo tempo, aumentar CPI por penalidades maiores de branch misprediction ou maior desequilíbrio entre estágios. Frequência isolada não é uma métrica completa de desempenho.

## Um modelo didático de cinco estágios

Um pipeline escalar clássico divide o processamento em cinco estágios conceituais:

| Estágio | Nome convencional | Trabalho típico |
|---|---|---|
| 1 | IF — instruction fetch | escolher PC/RIP e obter bytes da instrução |
| 2 | ID — decode/register read | interpretar encoding, identificar operandos e ler registradores |
| 3 | EX — execute/address generation | operação da ALU, comparação de branch e cálculo de endereço efetivo |
| 4 | MEM — memory | acesso de load/store |
| 5 | WB — writeback | publicar um resultado em registrador |

Esse modelo é pedagógico, não uma descrição de cores x86 modernos. Instruções x86 têm tamanho variável e frequentemente são transformadas internamente em micro-operações específicas da implementação. Processadores de alto desempenho podem incluir filas separadas no front end, decodificadores múltiplos, micro-op cache, estágios de renomeação, schedulers, vários clusters de execução, load/store queues e estruturas de retirement.

O modelo de cinco estágios continua útil porque expõe o invariante central do pipeline: cada estágio opera sobre uma instrução diferente durante o mesmo intervalo de clock, e registradores de pipeline preservam as informações necessárias para os estágios posteriores.

## Registradores de pipeline são estado, não fios

Sem registradores entre estágios, os valores intermediários de uma instrução seriam sobrescritos pela instrução seguinte. Um registrador conceitual IF/ID pode manter:

- a instrução buscada ou informações sobre sua fronteira;
- o endereço da instrução;
- metadados de predição;
- informação de fault associada ao fetch.

Um registrador ID/EX pode manter:

- classe da operação decodificada;
- valores ou identificadores dos operandos;
- imediato;
- identificador do registrador de destino;
- bits de controle para memória e writeback.

Um EX/MEM pode manter:

- resultado da ALU ou endereço efetivo;
- dados de store;
- resultado do branch;
- metadados do destino;
- informação de exceção pendente.

Um MEM/WB pode manter:

- dado carregado ou resultado da execução;
- registrador de destino;
- enable de writeback;
- estado de fault/validade.

Essas estruturas não são visíveis pela arquitetura. Software não consegue ler um registrador IF/ID. Elas são estado de implementação usado para garantir que a transformação arquitetural final permaneça correta.

O bit de validade é especialmente importante. Um slot do pipeline pode conter bits antigos, tanto em hardware quanto em simulação, e ainda assim estar marcado como inválido. Uma bubble deve ser representada conceitualmente como "não há instrução válida neste slot", e não necessariamente como uma instrução NOP física.

## Fluxo de instruções pelo pipeline

Suponha instruções I1 até I5 independentes, todas usando os cinco estágios. Uma agenda ideal é:

| Ciclo | IF | ID | EX | MEM | WB |
|---:|---|---|---|---|---|
| 1 | I1 | — | — | — | — |
| 2 | I2 | I1 | — | — | — |
| 3 | I3 | I2 | I1 | — | — |
| 4 | I4 | I3 | I2 | I1 | — |
| 5 | I5 | I4 | I3 | I2 | I1 |
| 6 | I6 | I5 | I4 | I3 | I2 |

Várias instruções estão ativas simultaneamente, mas cada uma ocupa um estágio diferente. Essa sobreposição é a fonte do throughput.

A tabela também mostra por que a correção fica mais difícil. A máquina agora contém instruções mais novas parcialmente processadas atrás de instruções mais antigas. Se I2 gerar fault quando I3 e I4 já começaram a ser processadas, o processador precisa impedir que trabalho mais novo ou especulativo se torne arquiteturalmente visível antes da entrega da exceção.

## Estado arquitetural e retirement

Estado arquitetural é o que a ISA permite ao software observar: registradores gerais, RIP, RFLAGS, registradores de controle, efeitos na memória e demais estado definido da máquina. Estado microarquitetural inclui slots do pipeline, tabelas de predição, filas e resultados transitórios.

Um pipeline in-order simples pode atualizar estado arquitetural em ordem de programa no writeback. Projetos mais avançados separam **execução** de **retirement**. Instruções podem executar fora de ordem, mas seus resultados visíveis são comprometidos em ordem por estruturas de reordenação. Esse assunto é desenvolvido no capítulo de execução out-of-order.

A regra fundamental é:

> O trabalho interno pode ser sobreposto ou especulativo, mas o estado arquitetural precisa corresponder a uma execução válida da ISA.

Essa regra também conecta o tema ao projeto do emulador. Um interpretador por instruções pode atualizar a arquitetura diretamente porque não possui instruções mais novas em voo. Um modelo de pipeline ciclo a ciclo não pode tratar todo resultado intermediário como já comprometido.

## Stalls, bubbles e flushes

Um pipeline precisa interromper seu avanço normal em algumas condições.

Um **stall** impede um ou mais estágios ou registradores de pipeline de aceitarem novo trabalho durante um ciclo. Estágios anteriores também podem precisar parar para não sobrescrever a instrução bloqueada.

Uma **bubble** é um slot inválido inserido intencionalmente para permitir que estágios posteriores continuem enquanto nenhuma nova instrução entra naquela posição.

Um **flush** invalida trabalho mais novo que não deve mais concluir. Causas típicas:

- branch tomado descoberto depois de instruções sequenciais já terem sido buscadas;
- branch misprediction;
- exceção ou fault;
- transferência de controle que muda o fluxo;
- reset ou redirecionamento da máquina.

As operações são diferentes. Uma dependência load-use pode exigir um stall de um ciclo e uma bubble sem limpar o pipeline inteiro. Um erro de predição de branch normalmente exige redirecionar fetch e invalidar instruções do caminho incorreto.

## Balanceamento de estágios e caminho crítico

Pipelining é limitado pelo estágio mais lento. Considere atrasos nominais:

| Estágio | Atraso lógico |
|---|---:|
| IF | 320 ps |
| ID | 250 ps |
| EX | 410 ps |
| MEM | 500 ps |
| WB | 180 ps |

Com overhead de 40 ps nos registradores de pipeline, o período idealizado mínimo é de pelo menos 540 ps, porque MEM é o estágio crítico. Dividir ainda mais um estágio de 180 ps não melhora o período enquanto o estágio de 500 ps permanecer igual.

Isso cria um problema de otimização. Projetistas podem:

- redistribuir lógica entre fronteiras;
- duplicar recursos;
- pipelinear internamente unidades funcionais longas;
- usar caches para reduzir a latência comum de memória;
- permitir operações de latência variável fora do caminho fixo;
- usar filas para que uma operação atrasada não congele a máquina inteira.

Cada técnica adiciona área, energia, complexidade de verificação ou novos hazards.

## Instruções x86 de tamanho variável e o front end

Uma ISA de largura fixa normalmente identifica fronteiras de instruções diretamente a partir de palavras alinhadas. x86-64 não. Instruções podem ter de um a quinze bytes e conter prefixes, opcode, ModR/M, SIB, displacement e immediate.

Um front end em hardware precisa resolver diversos problemas antes da execução comum:

- localizar fronteiras de instruções no fluxo de bytes;
- buscar através de fronteiras de cache line ou página;
- tratar quantidade variável de prefixes;
- identificar alvos de branches;
- alimentar um ou mais decodificadores;
- eventualmente traduzir instruções complexas em micro-operações;
- preservar faults associados à instrução arquitetural original.

O ChrisCPU expõe uma versão de software mais simples do mesmo problema de fronteiras. A função atual <code>fetch_insn</code> tenta ler até quinze bytes a partir do endereço virtual em <code>arch.rip</code>. <code>chris_decode</code> interpreta prefixes e campos e produz uma estrutura <code>ChrisInsn</code>. Isso é um pipeline no sentido comum de uma sequência de etapas de software, mas não é um pipeline de CPU sincronizado por clock.

Essa distinção precisa permanecer explícita na documentação.

## Exceções e estado arquitetural preciso

Um processador precisa entregar faults com contexto arquitetural coerente. Para muitas exceções síncronas, software espera que RIP e registradores visíveis correspondam a um ponto definido em relação à instrução que falhou.

Em um pipeline, uma instrução mais nova pode já ter alcançado a lógica de execução quando uma instrução mais antiga descobre um fault. Mecanismos de exceção precisa impedem o commit do trabalho mais novo e organizam a entrega como se a máquina tivesse alcançado a instrução problemática em ordem de programa.

Um projeto didático in-order pode usar idade dos estágios e bits de validade:

1. registrar a exceção junto da instrução mais antiga afetada;
2. interromper ou invalidar instruções mais novas;
3. permitir que instruções anteriores seguras terminem, quando exigido pela arquitetura;
4. redirecionar para o handler;
5. fornecer endereço de reinício e informações de erro.

Implementações reais podem ser muito mais complexas, especialmente com execução fora de ordem.

## Fronteiras de interrupção

Interrupções externas diferem de faults síncronos porque não são causadas pela instrução atual. O hardware escolhe fronteiras arquiteturalmente permitidas para reconhecê-las.

O interpretador atual do ChrisCPU expõe uma fronteira de software clara. Em <code>cpu_run</code> ele:

1. busca os bytes da instrução no RIP atual;
2. decodifica a instrução;
3. executa a semântica;
4. avança RIP quando a execução não o substituiu;
5. chama <code>maybe_irq</code>;
6. incrementa os contadores de step e TSC.

Essa ordem significa que o interpretador verifica interrupções pendentes entre iterações de instruções completas, respeitando enable de interrupção e a lógica de atraso de STI existente. Isso é um contrato do interpretador, não um modelo de um estágio físico.

Um futuro modelo de pipeline precisa definir explicitamente em que ponto uma interrupção assíncrona se torna arquiteturalmente visível e como instruções mais novas em voo são descartadas ou drenadas.

## Latência de memória e backpressure

O modelo simples de cinco estágios atribui um ciclo a MEM. Memória real não possui latência constante. Um load pode acertar na L1, errar para outro nível de cache, disparar page walk, alcançar DRAM ou gerar fault. Stores podem entrar em buffers e se tornar globalmente visíveis mais tarde.

Um pipeline escalar sem estruturas non-blocking pode congelar enquanto uma requisição de memória estiver pendente. Máquinas mais avançadas usam:

- estruturas para misses de cache;
- load queues e store queues;
- store buffers;
- mecanismos de replay;
- múltiplas requisições de memória pendentes;
- predição de dependência;
- verificações de ordenação de memória.

Essas estruturas desacoplam execução da latência bruta da memória, mas aumentam o volume de estado microarquitetural que precisa ser invalidado, repetido ou validado.

O ChrisCPU atual chama helpers de memória virtual de forma síncrona durante a execução da instrução. Um acesso conclui pelo caminho de tradução/leitura/escrita do emulador ou retorna erro que participa do tratamento de exceção. Não há latência simulada de cache miss nem paralelismo de memória no loop de instruções.

## Profundidade do pipeline é uma troca, não um objetivo

Aumentar a profundidade pode reduzir a quantidade de lógica por estágio e potencialmente encurtar o período de clock. Isso também produz custos:

- mais registradores de pipeline e energia de clock;
- penalidades maiores de redirecionamento de branch;
- mais estado a ser limpo;
- maior complexidade da rede de bypass;
- maior superfície de verificação;
- mais sensibilidade a desequilíbrio entre estágios;
- possível aumento da latência de instrução.

A profundidade adequada depende de tecnologia de fabricação, frequência alvo, workload, comportamento de branches, recursos de execução e restrições de energia. Não existe um número universal de estágios que defina um processador "moderno".

## Execução escalar, superscalar e multi-issue

Um pipeline escalar aceita no máximo uma instrução nova em um estágio por ciclo. Um front end superscalar pode decodificar ou emitir várias operações por ciclo. Largura muda fortemente o problema de recursos.

Se uma máquina pode emitir W operações por ciclo, precisa de portas suficientes no banco de registradores, largura de rename, capacidade de scheduler, unidades funcionais, portas de cache e largura de retirement para usar esse W. A largura de pico é apenas um limite superior. Dependências e mistura de instruções frequentemente reduzem as instruções por ciclo observadas.

Os próximos capítulos separam três mecanismos frequentemente agrupados de forma incorreta sob a palavra "pipeline":

- **detecção de hazards e forwarding**, que preservam correção quando instruções sobrepostas dependem entre si;
- **branch prediction e speculation**, que mantêm o front end alimentado diante de controle incerto;
- **execução out-of-order e register renaming**, que deixam trabalho mais novo e independente prosseguir preservando retirement arquitetural ordenado.

## Implementação atual do ChrisCPU

Na revisão <code>e05a17fd76333114a3fb5c2452f38ca747d4ac56</code>, o estado relevante de execução é representado por <code>ChrisCpu</code> e <code>ChrisArchitectureState</code>.

<code>ChrisArchitectureState</code> contém registradores arquiteturais e estado visível à máquina, incluindo:

- dezesseis registradores de propósito geral;
- RIP e RFLAGS;
- CR0, CR2, CR3, CR4 e CR8;
- estado de segmentos;
- GDTR e IDTR;
- EFER e MSRs selecionados;
- armazenamento XMM;
- nível de privilégio atual.

<code>ChrisCpu</code> envolve essa arquitetura com estado de controle do emulador, incluindo:

- contagem de steps;
- estado de halt e razão de saída;
- informações de exceção e IRQ pendentes;
- atraso de STI;
- <code>rip_dirty</code>;
- geração de TLB;
- configuração de tracing e ring de trace.

Nos arquivos revisados não existem campos representando registradores IF/ID, ID/EX, EX/MEM ou MEM/WB. Não há vetor de validade por estágio, reorder buffer ou rede de forwarding.

O loop central pode ser resumido assim:

    enquanto houver orçamento de execução:
        buscar bytes no RIP arquitetural
        decodificar bytes em ChrisInsn
        registrar informações de trace
        executar a semântica da instrução
        se a execução não redirecionou RIP:
            RIP += comprimento da instrução
        verificar fronteira de interrupção pendente
        incrementar contadores de step e TSC

Isso é intencionalmente útil para emulação funcional. Cada iteração forma uma transição arquitetural clara. É mais simples validar semântica de instruções, exceções e comportamento do sistema sem antes reproduzir temporização de um core físico.

## O que um futuro modo pipelined do ChrisCPU exigiria

Um modo temporal não deve ser criado apenas adicionando um contador de "ciclos" ao redor do loop atual. Ele exigiria novo estado com semântica explícita.

No mínimo, um pipeline in-order didático precisaria de:

| Estrutura | Informação necessária |
|---|---|
| Estado de fetch | RIP de fetch, bytes, fault de fetch, validade |
| Estado de decode | <code>ChrisInsn</code> decodificada, identificadores de fonte/destino, imediato, validade |
| Estado de execute | valores de operandos, resultado ALU/endereço, resultado de branch, exceção |
| Estado de memory | endereço efetivo, dados de load/store, fault de memória, validade |
| Estado de writeback | resultado, destino, enable de commit arquitetural |
| Controle | stall, flush, redirect e prioridade de interrupção/exceção |

O modelo também precisaria separar claramente estado arquitetural de estado especulativo. Se <code>ChrisArchitectureState</code> continuar representando o estado comprometido, resultados intermediários precisam permanecer em outra estrutura até o ponto de retirement escolhido.

Uma API determinística por ciclo poderia ser conceitualmente:

    chris_pipeline_cycle(cpu):
        retire_or_writeback()
        advance_memory()
        advance_execute()
        advance_decode()
        advance_fetch()
        resolve_flush_and_stall_priority()
        account_cycle()

A ordem real no software deve garantir que todas as atualizações usem um snapshot consistente do ciclo anterior, e não valores já modificados no novo ciclo. Uma técnica comum em simuladores é double buffering: calcular o estado <code>next</code> a partir de <code>current</code> e trocar o conjunto inteiro no edge lógico do clock.

## Invariantes para um modelo de pipeline correto

Uma futura implementação deve preservar pelo menos:

1. **Equivalência arquitetural em ordem de programa.** Para código sem dispositivos sensíveis a tempo, resultados comprometidos precisam coincidir com o interpretador funcional.
2. **Sem efeitos de slots inválidos.** Uma bubble nunca pode atualizar registradores, memória ou controle.
3. **Sem commit mais novo após fault antigo.** Instruções de caminho errado ou mais novas podem calcular valores transitórios, mas não podem ficar visíveis quando uma exceção anterior redireciona a execução.
4. **Propriedade única do estado de estágio.** Cada instância de instrução em voo possui um estágio ou entrada de fila bem definido.
5. **Metadados estáveis durante stalls.** Identidade, exceções e operandos de um estágio bloqueado não podem mudar acidentalmente.
6. **Flush domina trabalho mais novo.** Instruções redirecionadas devem ser invalidadas antes de publicar resultados.
7. **Atualizações por ciclo simulam edges.** Valores do novo ciclo derivam de um snapshot coerente do ciclo anterior.

Esses invariantes são mais importantes que reproduzir o pipeline de qualquer CPU comercial específica.

## Complexidade e custo de armazenamento

Para um pipeline escalar de largura fixa com k estágios, avançar metadados custa O(k) em um simulador de software direto, ou efetivamente O(1) quando k é constante de compilação. Armazenamento é proporcional à soma dos registros mantidos pelos estágios.

Detecção de hazard aumenta o trabalho. Comparar D operandos-fonte contra metadados de destino de H estágios anteriores custa O(D*H) comparações em um modelo simples. Em uma máquina superscalar de largura W, comparações e requisitos de portas crescem rapidamente; uma implementação ingênua de dependências entre várias instruções pode se aproximar de comportamento quadrático em W.

Hardware realiza muitas dessas comparações em paralelo, portanto a complexidade algorítmica de um simulador não prediz diretamente a latência do circuito. Ela ainda importa para desempenho do emulador.

## Estratégia de validação

Um modelo pipelined deve ser validado contra o interpretador funcional existente em vez de substituí-lo imediatamente.

Uma estratégia diferencial forte:

1. inicializa ambos os backends com o mesmo <code>ChrisArchitectureState</code> e a mesma memória;
2. executa até uma instrução arquitetural fazer commit no pipeline;
3. executa uma instrução no interpretador funcional;
4. compara estado arquitetural comprometido e efeitos definidos em memória;
5. repete através de branches, faults, interrupções e acessos de memória.

Testes direcionados também devem cobrir:

- enchimento e drenagem do pipeline;
- retenção durante stall;
- propagação de bubbles;
- flush de caminho incorreto;
- prioridade de exceções;
- RIP em faults;
- reconhecimento de interrupções;
- resultados idênticos após sequências longas.

Contadores de ciclo, stalls e bubbles podem diferir por projeto; estado arquitetural não.

## Limitações atuais

O código atual do ChrisCPU revisado para este capítulo **não** fornece:

- temporização ciclo a ciclo de pipeline;
- registradores explícitos de pipeline;
- ocupação simulada de unidades funcionais;
- lógica de forwarding ou interlock;
- temporização de branch predictor;
- estruturas de reorder/retirement;
- temporização de caches;
- memory-level parallelism;
- correspondência medida com uma microarquitetura física específica da Intel, AMD ou outro fabricante.

Afirmar que o ChrisCPU atualmente possui esses mecanismos seria incorreto.

## Fronteira de roadmap

Um ChrisCPU temporal ou pipelined pode ser uma extensão educacional valiosa porque o ChrisOS já fornece workloads que exercitam privilégio, paging, interrupções, syscalls e dispositivos. O caminho adequado é aditivo:

1. manter o backend funcional atual como oráculo de correção;
2. definir uma estrutura separada de estado microarquitetural;
3. implementar um modelo escalar in-order mínimo;
4. adicionar hazards e forwarding;
5. adicionar branch prediction somente depois de provar a semântica de flush;
6. adicionar caches e memória de latência variável por interfaces explícitas;
7. considerar mecanismos superscalar ou out-of-order somente após validação diferencial estável.

ChrisHV segue outra abordagem: usa virtualização por hardware, não simulação de pipeline. O estado arquitetural compartilhado pode conectar os backends, mas o comportamento microarquitetural de ambos não deve ser confundido.

## Registro de revisão

Este capítulo foi reconciliado com a revisão <code>e05a17fd76333114a3fb5c2452f38ca747d4ac56</code> da branch <code>main</code> do ChrisOS. Afirmações sobre implementação se limitam aos arquivos declarados no frontmatter. Temporização de pipeline, estruturas de estágios e equações de desempenho são teoria de arquitetura, salvo quando explicitamente descritas como comportamento atual do ChrisCPU.
