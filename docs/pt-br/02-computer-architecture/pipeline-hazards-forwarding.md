---
id: pipeline-hazards-forwarding
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
  - cpu_run
  - chris_decode
  - chris_execute
  - chris_read_gpr
  - chris_write_gpr
depends_on:
  - microarchitecture-pipeline
  - cpu-datapath-isa
related:
  - branch-prediction-speculation
  - out-of-order-renaming-retirement
  - atomics-memory-model
---

# Hazards de pipeline, interlocks e forwarding

## Por que hazards existem

Pipelining sobrepõe instruções que seriam separadas em uma máquina sequencial. A sobreposição melhora throughput somente se o processador impedir que uma instrução observe estado no momento errado ou concorra por um recurso indisponível.

Um **pipeline hazard** é uma condição em que o avanço ingênuo da próxima instrução violaria a correção ou o contrato de recursos do pipeline. Hazards normalmente são classificados como:

- **structural hazards** — duas operações exigem o mesmo recurso não duplicado ao mesmo tempo;
- **data hazards** — uma instrução depende de dados produzidos ou consumidos por outra;
- **control hazards** — o próximo endereço correto de instrução ainda não é conhecido.

Este capítulo trata principalmente de hazards estruturais e de dados, além dos mecanismos usados para resolvê-los. Hazards de controle, prediction e speculation são tratados no capítulo seguinte.

![Detecção de dependência, forwarding e controle de stall em um pipeline didático](../../assets/diagrams/pipeline-hazards-forwarding-pt-br.svg)

## O problema de correção criado pela sobreposição

Considere:

    add rax, rbx
    sub rcx, rax

A segunda instrução precisa do valor de RAX produzido pela primeira. Em um interpretador sequencial, essa dependência é naturalmente respeitada porque ADD termina antes de SUB começar. Em um pipeline didático de cinco estágios, porém, SUB pode tentar ler RAX em ID enquanto ADD só escreverá o novo valor no banco arquitetural de registradores em WB.

Se o pipeline ler o RAX antigo e continuar, o resultado estará errado. O processador precisa:

1. tornar o valor novo disponível antecipadamente por **forwarding/bypassing**; ou
2. atrasar a instrução dependente com um **stall/interlock** até o valor estar disponível.

O mecanismo de hazard, portanto, não é apenas uma otimização de desempenho. Sua primeira responsabilidade é preservar correção.

## Terminologia de dependências

Considere uma instrução A anterior à instrução B em ordem de programa.

### Read after write — RAW

B lê um local que A escreve.

    A: r1 <- ...
    B: ... <- r1

RAW é uma dependência verdadeira de dados. B precisa do valor produzido por A.

Em um pipeline escalar in-order simples, RAW é a principal dependência entre registradores capaz de produzir um hazard temporal.

### Write after read — WAR

A lê um local e B posteriormente escreve nele.

    A: ... <- r1
    B: r1 <- ...

WAR é uma anti-dependência. O programa exige que A observe o valor antigo antes de B substituí-lo.

Um pipeline in-order básico, que lê operandos antes de instruções posteriores poderem escrevê-los, preserva essa ordem naturalmente. WAR se torna importante quando a execução pode ocorrer fora de ordem. Register renaming remove muitas restrições WAR ao fornecer armazenamento físico diferente para usos lógicos distintos.

### Write after write — WAW

A escreve um local e B posteriormente escreve o mesmo local.

    A: r1 <- ...
    B: r1 <- ...

O valor final visível deve ser o de B. Um pipeline in-order que faz commit de writes em ordem geralmente preserva WAW automaticamente. Conclusão fora de ordem pode violar essa propriedade se retirement ou renaming não preservar a ordem arquitetural.

A distinção é importante: RAW representa fluxo verdadeiro de valor. WAR e WAW surgem da reutilização de nomes arquiteturais.

## Equações de hazard em um pipeline simples

Suponha que a instrução em ID possua registradores-fonte Rs1 e Rs2. Instruções mais antigas em EX/MEM e MEM/WB podem possuir destinos Rd_EXMEM e Rd_MEMWB. Um detector RAW simples pergunta se uma instrução válida anterior escreverá um registrador que a instrução mais nova precisa.

Conceitualmente:

    hazard_EXMEM =
        EXMEM.valid
        and EXMEM.reg_write
        and EXMEM.rd != NONE
        and (EXMEM.rd == ID.rs1 or EXMEM.rd == ID.rs2)

    hazard_MEMWB =
        MEMWB.valid
        and MEMWB.reg_write
        and MEMWB.rd != NONE
        and (MEMWB.rd == ID.rs1 or MEMWB.rd == ID.rs2)

Essa é apenas uma equação didática. Em x86 real é necessário considerar operandos implícitos, registradores parciais, flags, dependências de memória, estado vetorial, registradores de controle e semântica específica de cada operação.

Por exemplo, ADC lê carry além dos operandos explícitos. Um branch pode ler condition flags. PUSH e CALL interagem com RSP. Operações de string com REP usam registradores implícitos. Um modelo que acompanha apenas registradores explícitos de ModR/M é incompleto.

## Forwarding: usar o valor antes do writeback arquitetural

Forwarding encaminha um valor recém-produzido diretamente de um estágio posterior para um consumidor anterior, sem esperar que o banco de registradores seja atualizado.

Considere:

    add rax, rbx
    sub rcx, rax

Se ADD calcula o resultado em EX durante o ciclo 3 e SUB precisa desse operando em EX no ciclo 4, o valor pode ser encaminhado do registrador EX/MEM para a entrada da ALU usada por SUB.

Um seletor de forwarding para um operando pode seguir a prioridade:

    se EXMEM escreve a fonte necessária:
        usar EXMEM.result
    senão, se MEMWB escreve a fonte necessária:
        usar MEMWB.result
    senão:
        usar register_file_value

O produtor correspondente mais novo deve vencer. Se duas instruções anteriores escrevem o mesmo registrador arquitetural, a mais nova delas contém o valor correto para o consumidor.

Exemplo:

    mov rax, 1
    mov rax, 2
    add rcx, rax

Se as duas definições mais antigas estiverem em estágios relevantes, forwarding deve selecionar 2, não 1.

## Forwarding é uma rede, não uma simples cópia

Em hardware, forwarding exige:

- comparadores entre identificadores de fontes e destinos;
- muxes nas entradas das unidades de execução;
- lógica de controle para selecionar o produtor correto;
- fios atravessando regiões físicas do core;
- metadados indicando se o resultado é válido e disponível.

Com largura multi-issue e várias unidades de execução, a rede de bypass pode se tornar cara em área, roteamento e temporização. Uma regra conceitualmente simples como "encaminhar o valor mais novo" pode se tornar um dos limites físicos de um processador largo.

Um simulador temporal em software possui custo diferente. Normalmente ele realiza comparações explicitamente e seleciona valores de modo algorítmico. Para S operandos-fonte e P produtores possíveis, uma implementação direta realiza O(S*P) comparações por instrução. Hardware pode realizar várias comparações em paralelo; no simulador isso vira trabalho sequencial da CPU hospedeira.

## O hazard load-use

Forwarding não elimina todo atraso RAW.

Considere um pipeline clássico de cinco estágios:

    load rax, [rbx]
    add  rcx, rax

O dado do load só fica disponível após MEM. O ADD dependente normalmente precisa do operando no início de EX um ciclo cedo demais.

Uma solução comum insere uma bubble:

| Ciclo | IF | ID | EX | MEM | WB |
|---:|---|---|---|---|---|
| 1 | LOAD | — | — | — | — |
| 2 | ADD | LOAD | — | — | — |
| 3 | next | ADD | LOAD | — | — |
| 4 | stalled | ADD | bubble | LOAD | — |
| 5 | ... | next | ADD | bubble | LOAD |

O resultado do load pode então ser encaminhado de MEM/WB ou ponto equivalente para o consumidor.

Um detector didático pode usar:

    se IDEX.is_load
       e IDEX.rd != NONE
       e (IDEX.rd == IFID.rs1 ou IDEX.rd == IFID.rs2):
        stall_fetch = true
        stall_decode = true
        inject_bubble_into_execute = true

A temporização exata depende da organização. Alguns projetos conseguem encaminhar do caminho de cache mais cedo; outros precisam de stalls maiores em cache miss.

## Stalls e interlocks

Um **interlock** é lógica de controle que detecta uma condição de atraso e impede que o pipeline avance incorretamente.

Um stall precisa preservar a instrução bloqueada. Se decode aguarda um operando:

- PC/fetch pode precisar parar;
- IF/ID deve manter a mesma instrução;
- uma bubble pode ser inserida em ID/EX;
- instruções mais antigas continuam progredindo.

A ordem dessas ações importa. Permitir que IF/ID avance enquanto ID está parado faz a instrução bloqueada ser perdida. Reexecutar um estágio antigo com efeito colateral pode duplicar writes em memória ou dispositivos.

Para um simulador, a abordagem mais segura é derivar todo o estado do próximo ciclo a partir de um snapshot somente-leitura do ciclo atual. O controle de stall então escolhe quais registros são copiados, mantidos, invalidados ou substituídos por bubbles.

## Structural hazards

Um structural hazard ocorre quando instruções concorrentes precisam do mesmo recurso finito.

O exemplo clássico é uma máquina com uma única porta de memória compartilhada por fetch de instruções e acesso a dados. Durante um ciclo em que um load usa memória em MEM, IF não consegue buscar uma nova instrução pela mesma porta.

Resoluções possíveis:

- stall de um solicitante;
- duplicação ou multi-port do recurso;
- caches separados de instrução e dados;
- enfileiramento de requisições;
- arbitragem por prioridade ou justiça.

Outros exemplos:

- um multiplicador compartilhado por vários slots de issue;
- poucas portas de leitura/escrita no register file;
- load/store queue cheia;
- reorder buffer cheio;
- largura de decoder insuficiente;
- estruturas de acompanhamento de cache miss saturadas.

Um stall estrutural não implica dependência de dados. Duas instruções independentes podem conflitar apenas porque a implementação não possui capacidade simultânea.

## Ocupação de recursos e latência variável

Para unidades de execução fixas de um ciclo, um busy bit pode bastar. Unidades de vários ciclos ou latência variável precisam de estado mais rico.

Um divisor poderia expor:

| Campo | Significado |
|---|---|
| valid | há operação ativa |
| remaining | ciclos até conclusão nominal |
| destination | destino arquitetural ou físico |
| operands/result | estado interno da operação |
| exception | divide error ou outro fault |
| owner age | identidade/ordem da instrução |

Se a unidade não for internamente pipelined, nenhum novo divide pode começar enquanto ela estiver ocupada. Se for pipelined, pode aceitar nova operação a cada ciclo apesar de cada resultado levar vários ciclos.

Assim, **latência** e **initiation interval** são propriedades diferentes. Um multiplicador pode ter latência 4 e initiation interval 1.

## Dependências de memória não são dependências de registradores

Considere:

    store [rax], rbx
    load  rcx, [rdx]

A dependência do load em relação ao store depende dos endereços, não apenas dos nomes de registradores. Se RAX e RDX resolverem para o mesmo endereço, executar o load cedo demais pode ler dado antigo.

Um pipeline in-order simples pode evitar parte dessa complexidade mantendo operações de memória em ordem de programa. Processadores mais avançados usam load/store queues e lógica de address disambiguation para permitir que loads independentes avancem preservando as regras de ordenação.

O problema fica mais difícil porque o endereço efetivo pode não ser conhecido até execute, e um store pode ter endereço conhecido sem os dados prontos, ou o inverso.

Isso é uma razão para um futuro modelo temporal introduzir hazards de registradores antes de tentar speculation agressiva de memória.

## Flags e dependências arquiteturais implícitas em x86

x86-64 possui dependências fáceis de omitir em um modelo simplificado.

Exemplos:

- ADD escreve status flags.
- ADC lê carry e escreve flags.
- CMP escreve flags sem destino GPR.
- Jcc lê flags.
- INC/DEC possuem comportamento de flags diferente de ADD/SUB.
- CALL e PUSH leem e escrevem RSP.
- RET lê memória da stack e altera RSP e RIP.
- instruções de string usam RSI, RDI, RCX e flags de forma implícita conforme a operação.

Um modelo correto de dependências x86 precisa de uma descrição normalizada do conjunto de recursos lidos e escritos por cada instrução.

Uma representação útil para simulador é:

    ReadSet  = {recursos arquiteturais consumidos}
    WriteSet = {recursos arquiteturais produzidos}

Existe RAW quando o ReadSet da instrução mais nova intersecta o WriteSet pendente de uma instrução anterior. Modelos out-of-order também precisam lidar com conflitos write/write e write/read até que renaming os remova.

A estrutura atual <code>ChrisInsn</code> registra campos da instrução decodificada, mas não expõe uma abstração genérica completa de read/write set. Criar essa camada seria útil antes de implementar um pipeline temporal.

## Registradores parciais complicam o rastreamento

Nomes de registradores x86 se sobrepõem. AL, AX, EAX e RAX são visões de larguras diferentes da mesma família arquitetural. Writes também podem ter comportamento especial: um write de 32 bits em EAX faz zero-extension para RAX.

Um modelo de hazard que trate cada nome textual como independente estaria errado.

Uma representação normalizada prática pode acompanhar:

- identificador da família, como RAX;
- máscara de bytes/bits lidos;
- máscara de bytes/bits escritos;
- se o write define os bits superiores.

Verificações de sobreposição passam então a operar sobre máscaras, não nomes.

Para um primeiro pipeline educacional, uma escolha defensável é uma dependência conservadora por família: qualquer acesso a AL/AX/EAX/RAX conflita com qualquer write pendente na família RAX. Isso pode gerar stalls desnecessários, mas preserva correção. Otimização pode vir depois da validação.

## Semântica de bubble e supressão de efeitos colaterais

Uma bubble não pode produzir efeitos colaterais. Isso parece simples, mas todo caminho de side effect deve respeitar validade.

Um bit de validade deve controlar:

- writeback em registradores;
- stores em memória;
- writes em portas de I/O;
- writes de MMIO;
- entrega de exceção;
- branch redirect;
- eventos de contador associados a instruções comprometidas.

Se um slot eliminado ainda alcançar store com bits de controle antigos, um write de caminho errado pode escapar. Em hardware isso é falha de correção; em simulador é um bug com a mesma consequência arquitetural.

O padrão mais robusto é fazer funções de efeito colateral exigirem um registro de instrução explicitamente válido e autorizado a fazer commit.

## Prioridade entre stall, flush e exceção

Várias condições podem ocorrer no mesmo ciclo. O controle deve definir precedência.

Uma política didática razoável:

1. reset/shutdown da máquina;
2. exceção síncrona mais antiga;
3. branch ou control redirect da instrução válida mais antiga que o exige;
4. stalls estruturais/de dados;
5. avanço comum e fetch.

A política exata depende do estágio onde as condições são descobertas, mas precisa ser determinística e consistente com a idade das instruções.

Por exemplo, um branch misprediction que limpa um load mais novo normalmente torna irrelevante o stall de dependência desse load. Uma instrução de caminho errado não deve impedir redirecionamento.

## Control hazards como fronteira para o próximo capítulo

Um branch cria incerteza sobre o próximo endereço de fetch. Sem prediction, um pipeline in-order pode parar fetch até o branch resolver. Com prediction, pode avançar por um caminho previsto e limpar a máquina se estiver errado.

A lógica descrita neste capítulo continua necessária:

- operandos do branch podem precisar de forwarding;
- condition flags podem possuir dependências RAW;
- um branch pode aguardar um load;
- flush precisa invalidar operações mais novas.

Prediction altera comportamento de desempenho, não as regras fundamentais de correção das dependências.

## ChrisCPU: por que esses hazards estão ausentes hoje

Na revisão <code>e05a17fd76333114a3fb5c2452f38ca747d4ac56</code>, <code>cpu_run</code> processa uma instrução completamente antes de iniciar a próxima.

O caminho revisado é:

    fetch_insn
        -> chris_decode
        -> chris_execute
        -> atualização de RIP quando necessária
        -> maybe_irq
        -> contabilização de step/TSC
        -> próxima instrução

Helpers como <code>chris_read_gpr</code> e <code>chris_write_gpr</code> operam sobre o estado arquitetural usado pela instrução atual. Quando <code>chris_execute</code> retorna, a próxima iteração observa o estado resultante.

Consequências:

- não há instrução antiga e nova simultaneamente concorrendo por um recurso simulado de pipeline;
- uma instrução dependente naturalmente lê o estado produzido por sua predecessora;
- não existe gap temporal load-use porque a memória é síncrona do ponto de vista do interpretador;
- não há necessidade de rede de forwarding;
- não existem bubbles ou estado de interlock.

Essa é uma propriedade da abstração atual, não do hardware x86.

## Dependências arquiteturais ainda importam no interpretador funcional

Embora hazards temporais estejam ausentes, dependências continuam semanticamente importantes.

Exemplo:

    add rax, rbx
    adc rcx, rdx

ADC depende da carry flag produzida por ADD. O interpretador preserva isso porque ADD atualiza <code>arch.rflags</code> antes da próxima instrução executar.

Da mesma forma:

    mov eax, 1
    add rbx, rax

depende do comportamento arquitetural de zero-extension do write em EAX antes de ADD ler RAX. A emulação funcional consegue validar a semântica das dependências mesmo sem modelar o mecanismo temporal usado por hardware.

Isso torna o interpretador um bom oráculo para um futuro backend pipelined.

## Metadados de hazard para um futuro pipeline do ChrisCPU

Antes de implementar forwarding, o decoder deveria expor metadados normalizados de dependências.

Um registro interno possível:

| Campo | Função |
|---|---|
| src[] | identificadores dos recursos-fonte |
| src_mask[] | cobertura de bits/bytes de cada fonte |
| dst[] | identificadores dos recursos-destino |
| dst_mask[] | cobertura escrita |
| reads_flags | subconjunto de RFLAGS requerido |
| writes_flags | subconjunto de RFLAGS produzido |
| mem_read | pode ler memória |
| mem_write | pode escrever memória |
| serializing | exige controle mais forte |
| variable_latency | disponibilidade do resultado não é fixa |

Esse registro pode ser derivado de <code>ChrisInsn</code> após decode. Ele não substitui a semântica da instrução; é metadata de scheduling.

Uma implementação escalar mínima pode então calcular:

    para cada fonte da instrução em decode:
        localizar o produtor mais novo entre as instruções anteriores
        se o resultado estiver disponível para forwarding:
            selecionar bypass
        senão, se ainda não estiver disponível:
            stall

A regra do produtor mais novo preserva o fluxo de valores em ordem de programa.

## Invariante de prioridade de forwarding

Considere três instruções em voo:

    I1: rax <- 1
    I2: rax <- 2
    I3: rcx <- rax + 3

I3 deve consumir o valor de I2. Portanto a busca por produtores precisa percorrer das instruções anteriores mais novas para as mais antigas, ou dar prioridade explícita ao estágio que contém a definição mais recente.

Invariante:

> Para cada operando-fonte, o produtor selecionado deve ser a instrução válida mais nova, porém anterior ao consumidor, cujo write pendente sobreponha essa fonte.

Se não existir produtor pendente, a fonte vem do estado arquitetural.

Esse invariante generaliza além de um pipeline fixo de cinco estágios.

## Invariante de correção de stall

Quando uma instrução dependente não pode avançar:

- sua identidade permanece igual;
- metadados de fontes e destinos permanecem iguais;
- instruções mais antigas continuam, salvo bloqueio independente;
- nenhuma cópia duplicada da instrução é criada abaixo;
- fetch não sobrescreve estado upstream que precisa ser repetido.

Um teste útil é associar a cada instrução interna um sequence number monotônico. Após cada ciclo, um sequence number válido deve existir em no máximo um slot de pipeline, salvo se a implementação duplicar apenas referências de metadata sem duplicar propriedade de execução.

## Interação com exceções

A lógica de hazard não pode esconder nem duplicar exceções.

Se uma instrução está parada antes de execute, ela não deve levantar repetidamente uma exceção de execução porque execute ainda não ocorreu. Se um fault é descoberto em estágio anterior, instruções mais novas paradas precisam ser limpas quando o fault redirecionar o controle.

Um valor encaminhado por uma instrução que posteriormente será squashada não pode se tornar estado arquitetural através do consumidor. Isso é simples em um pipeline in-order não especulativo se forwarding vier apenas de instruções anteriores válidas que certamente farão commit. Fica mais sutil com speculation e out-of-order.

## Interação com stores e I/O de dispositivos

Stores, MMIO e port I/O são efeitos externamente visíveis. Um modelo temporal não deve executá-los simplesmente porque a instrução chegou cedo ao estágio de execução.

Um projeto didático seguro posterga efeitos irreversíveis até saber que a instrução não será eliminada por um evento anterior. Outra opção é registrar a operação em um store/output buffer e liberá-la em commit.

Isso importa no ChrisVM porque os device models vivem no mesmo processo. Executar MMIO de caminho errado pode alterar o estado do dispositivo mesmo que o estado da CPU seja posteriormente descartado.

Um futuro pipeline precisa, portanto, definir commit para:

- stores em RAM;
- MMIO;
- port I/O;
- reconhecimento de interrupção;
- efeitos de shutdown e halt.

## Complexidade e escalabilidade

Em um pipeline escalar com dois operandos e poucos estágios produtores, a detecção de dependências é pequena e determinística.

Para largura W com H grupos anteriores relevantes, uma implementação ingênua pode crescer aproximadamente como:

    O(W * fontes_por_instrucao * H * W)

dependendo da organização. Implementações físicas usam comparadores paralelos, banking, clusters e outras técnicas para reduzir pressão de temporização e roteamento.

Um simulador de software pode escolher estruturas mais apropriadas à execução sequencial. Um scoreboard que mapeie cada recurso arquitetural para seu produtor pendente mais recente reduz buscas repetidas. Porém os updates do scoreboard precisam tratar flushes e múltiplas definições corretamente.

Isso cria uma troca entre simplicidade de implementação e velocidade do simulador.

## Plano de verificação para um futuro modelo de hazards

Testes dirigidos devem começar com kernels de dependência cujo resultado seja evidente.

### Forwarding de ALU

    mov rax, 4
    add rax, 3
    add rbx, rax

Esperado: RBX consome 7 sem stall longo desnecessário.

### Produtor mais novo vence

    mov rax, 1
    mov rax, 9
    add rbx, rax

Esperado: consumidor vê 9.

### Load-use

    load rax, [address]
    add  rbx, rax

Esperado: pipeline insere o atraso exigido pelo modelo de memória escolhido e produz o mesmo estado arquitetural do interpretador funcional.

### Dependência de flags

    cmp rax, rbx
    je  target

Esperado: branch consome as flags produzidas por CMP.

### Flush com dependência

Construir um branch tomado/mispredicted em que uma instrução dependente do caminho errado já entrou no pipeline. Esperado: nenhum efeito em registrador ou memória dessa instrução.

### Exceção com store mais novo

Fazer uma instrução antiga gerar fault enquanto um store mais novo reside no pipeline. Esperado: o store nunca alcança memória ou estado de dispositivo arquitetural.

Validação diferencial deve comparar estado comprometido com o backend funcional do ChrisCPU após cada instrução retirada.

## Limitações atuais

A implementação atual do ChrisCPU não modela:

- stalls RAW de pipeline;
- contenção estrutural de recursos;
- muxes de forwarding;
- temporização load-use;
- scoreboards de registradores;
- estado de validade/bubble por estágio;
- speculation de dependência de memória;
- detecção de hazards superscalar.

Esses mecanismos aparecem neste capítulo como teoria e material para evolução futura.

O código também ainda não expõe um read/write set normalizado e completo por instrução. Um futuro pipeline deveria derivar essa metadata da semântica decodificada em vez de inferir dependências apenas pelo nome do opcode.

## Fronteira de roadmap

Uma sequência disciplinada de implementação é:

1. adicionar metadata normalizada de read/write para instruções decodificadas;
2. implementar pipeline escalar sem forwarding, com stall conservador em todo RAW pendente;
3. validar equivalência arquitetural contra o interpretador funcional;
4. adicionar forwarding de EX/MEM e MEM/WB;
5. adicionar um interlock load-use explicitamente definido;
6. modelar ocupação estrutural para unidades selecionadas de vários ciclos;
7. definir semântica de commit para stores/MMIO;
8. adicionar prediction de controle somente após provar a precedência entre stall e flush;
9. introduzir scheduling mais agressivo apenas após estabilizar o modelo in-order.

Essa sequência mantém evidência de correção à frente de sofisticação de desempenho.

## Registro de revisão

Este capítulo foi reconciliado com a revisão <code>e05a17fd76333114a3fb5c2452f38ca747d4ac56</code> da branch <code>main</code> do ChrisOS. Afirmações sobre o emulador atual se limitam aos arquivos declarados no frontmatter. Equações de hazards, redes de forwarding e temporização de pipeline são teoria arquitetural e estrutura proposta de validação, não alegações de que esses mecanismos já existem no ChrisCPU.
