---
id: combinational-logic
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- chrisvm/cpu/emulator/decode.c
symbols:
- read_modrm
depends_on:
- boolean-algebra
related:
- arithmetic-circuits
- logic-sequential
---

# Circuitos combinacionais

<div class="abstract">
Lógica combinacional transforma funções booleanas em hardware conectado cujas saídas dependem das entradas presentes, mas não possuem memória intencional do estado anterior. As estruturas mais importantes não são portas isoladas, e sim redes reutilizáveis: multiplexadores, decoders, encoders, comparadores, shifters e blocos aritméticos. Essas estruturas formam o tecido de roteamento e transformação de dados a partir do qual datapaths de processadores são construídos.
</div>

## Definição e hipóteses

Um circuito combinacional implementa uma função:

Y = F(X)

onde X é o vetor de entrada atual e Y é o vetor de saída correspondente. Não existe elemento de armazenamento intencional na definição da função.

Circuitos físicos ainda possuem atraso de propagação. Durante uma mudança de entrada, nós intermediários podem refletir valores antigos e novos em instantes distintos. Portanto, “depender apenas das entradas atuais” é uma afirmação lógica de regime estável, não uma afirmação de resposta física instantânea.

Um bloco combinacional é normalmente caracterizado por:

- função lógica;
- largura de entradas e saídas;
- atraso de propagação;
- capacitância de entrada e capacidade de drive;
- potência;
- carregamento e condições operacionais permitidas.

## Portas como redes, não como entidades fundamentais

AND, OR, XOR e NOT formam vocabulário simbólico conveniente. Em uma implementação baseada em bibliotecas de células, funções maiores podem estar disponíveis diretamente. Ferramentas de síntese mapeiam a rede booleana para um conjunto específico de células tecnológicas.

Um símbolo XOR em um diagrama pode, portanto, abstrair muitos transistores. No sentido oposto, uma biblioteca pode possuir uma célula AOI ou OAI que realiza múltiplas operações em uma estrutura física única e caracterizada.

A unidade de engenharia desta camada é a **função lógica com timing**, não uma preferência por determinado conjunto de símbolos de portas.

## Multiplexadores

Um multiplexador seleciona uma entre várias entradas conforme um sinal de seleção.

Para um multiplexador de duas entradas e um bit:

Y = (¬S ∧ A) ∨ (S ∧ B)

Se S = 0, Y = A. Se S = 1, Y = B.

Multiplexadores largos aplicam a mesma seleção sobre vetores. Eles são fundamentais em CPUs porque um datapath precisa constantemente escolher fontes:

- registrador ou imediato;
- RIP sequencial ou alvo de branch;
- resultado da ALU ou dado carregado da memória;
- writeback normal ou estado de exceção;
- resultado entre diferentes unidades de execução.

Um crossbar pode ser entendido como uma rede de roteamento muito maior construída a partir de princípios semelhantes.

## Decoders

Um decoder converte uma entrada codificada em uma seleção one-hot. Um decoder 2-para-4 transforma dois bits em quatro saídas mutuamente exclusivas.

| A1 | A0 | D0 | D1 | D2 | D3 |
|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 1 | 0 | 0 | 0 |
| 0 | 1 | 0 | 1 | 0 | 0 |
| 1 | 0 | 0 | 0 | 1 | 0 |
| 1 | 1 | 0 | 0 | 0 | 1 |

Decoders selecionam registradores, linhas de memória, casos de execução e caminhos de controle. Decodificação de instruções é uma forma muito mais complexa em que opcode, prefixos, modo e privilégio atual influenciam os sinais resultantes.

## Encoders e priority encoders

Um encoder executa a abstração inversa: várias linhas de entrada são representadas por um código binário menor.

Um encoder simples pressupõe que no máximo uma entrada esteja ativa. Um **priority encoder** define qual código prevalece quando múltiplas entradas são ativadas.

Codificação por prioridade aparece em controladores de interrupção, arbitração e seleção de exceções. A prioridade faz parte do comportamento arquitetural: se dois eventos ocorrem ao mesmo tempo, a máquina precisa de uma regra determinística para escolher qual será tratado primeiro.

## Comparadores

Igualdade entre vetores de n bits pode ser obtida verificando cada par correspondente:

equal = AND de todos os i de NOT(Ai XOR Bi)

Comparação de magnitude pode percorrer logicamente os bits do mais significativo para o menos significativo: o primeiro bit diferente determina qual valor sem sinal é maior.

Comparação com sinal precisa interpretar o bit de sinal e as regras de complemento de dois. CPUs expõem essas diferenças por flags e instruções condicionais.

## Shifters

Shift lógico move posições e insere zeros. Shift aritmético à direita preserva o bit de sinal para números em complemento de dois. Rotates fazem os bits reaparecerem do outro lado.

Deslocamento fixo por uma posição pode ser conectado diretamente. Deslocamentos variáveis exigem seleção entre diferentes distâncias. Um **barrel shifter** usa normalmente estágios de multiplexação para deslocar um valor por quantidade arbitrária com profundidade aproximadamente logarítmica.

Essa estrutura demonstra uma ideia recorrente: uma operação aparentemente atômica na ISA pode ser implementada por uma rede combinacional cuidadosamente organizada.

## Somadores como redes combinacionais

Um half adder produz:

sum = A XOR B

carry = A AND B

Um full adder adiciona carry-in:

sum = A XOR B XOR Cin

carry-out = (A AND B) OR (Cin AND (A XOR B))

Encadear full adders produz um ripple-carry adder. Seu pior atraso cresce com a largura porque o carry pode precisar atravessar todos os estágios.

Somadores mais rápidos reorganizam o problema. Carry-lookahead, prefix adders e estruturas relacionadas calculam sinais de geração e propagação para resolver carries distantes com menor profundidade lógica.

## Subtração em complemento de dois

Em largura fixa:

A − B = A + (¬B + 1)

O datapath pode reutilizar o somador invertendo B e definindo carry-in como 1. A mesma unidade física passa a apoiar soma, subtração, incremento, geração de condições para comparação e cálculo de endereços.

Reuso de blocos é típico em datapaths: multiplexação ao redor de uma unidade poderosa reduz área, embora aumente exigências de roteamento e controle.

## Conceito de ALU

Uma unidade aritmética e lógica combina funções aritméticas e booleanas selecionadas por sinais de controle.

Uma fatia conceitual de um bit pode calcular resultados candidatos para AND, OR, XOR e soma e escolher um deles por multiplexador. ALUs largas repetem ou reorganizam essas fatias e tratam carry e flags.

A instrução arquitetural “ADD RAX,RBX” está várias abstrações acima disso: decode produz controle, armazenamento de registradores fornece operandos, a ALU transforma os valores e o writeback captura o resultado.

## Atraso de propagação

Toda porta possui atraso finito. Em uma rede de vários níveis, o caminho relevante mais lento entre mudança de entrada e saída estável é o caminho crítico combinacional.

Se um caminho possui muitos estágios dependentes, a frequência de clock pode precisar ser reduzida ou o cálculo repartido entre estágios de pipeline.

Atraso não depende apenas da quantidade de portas. Fan-out, capacitância de interconexão, tamanho de célula, posicionamento físico e slew dos sinais interferem no resultado. Por isso uma expressão booleana mínima não é automaticamente a implementação mais rápida.

## Hazards e glitches

Caminhos lógicos diferentes possuem atrasos diferentes. Quando entradas mudam, a saída pode assumir por curto intervalo um valor incorreto, mesmo que os estados inicial e final estejam corretos. Esses pulsos temporários são hazards ou glitches.

Sistemas síncronos frequentemente toleram glitches internos desde que a saída se estabilize antes da captura e que o pulso não atinja controles assíncronos. Alguns circuitos, porém, exigem projeto livre de hazards porque um pulso curto já pode acionar um evento.

A distinção entre correção lógica e correção temporal é fundamental.

## Fan-out e buffers

Uma saída precisa carregar capacitância de gates e fios dos destinos. Fan-out grande torna transições mais lentas e pode violar timing.

Buffers formam árvores de drive em estágios. Redes de clock são um exemplo extremo: uma única referência lógica precisa alcançar grande quantidade de elementos de estado com skew controlado, exigindo estrutura especializada de distribuição.

Sinais de reset e enable também podem exigir distribuição cuidadosa.

## Lógica tri-state e barramentos

Barramentos compartilhados tradicionais podem usar saídas tri-state, capazes de dirigir 0, dirigir 1 ou entrar em alta impedância. Apenas uma fonte deve dirigir uma linha compartilhada por vez.

Dentro de circuitos integrados modernos, multiplexadores frequentemente substituem grandes barramentos tri-state internos porque são mais fáceis de sintetizar e analisar temporalmente. Interfaces externas específicas ainda podem usar tri-state.

Um barramento, por si só, não é um protocolo. Ele é um conjunto de caminhos de sinal; regras de protocolo definem ownership, timing e significado.

## Feedback combinacional é um caso especial

Uma rede combinacional normalmente deve ser acíclica. Realimentação não controlada pode oscilar ou estabilizar de maneira imprevisível. Inserir feedback deliberado muda o problema para comportamento sequencial ou assíncrono com armazenamento de estado.

Essa fronteira é importante em linguagens de descrição de hardware. Um loop em software é perfeitamente normal; um loop de atraso zero em uma netlist combinacional é normalmente erro, salvo quando modela estrutura assíncrona específica.

## Relação com datapaths de CPU

Um processador simples pode ser decomposto em armazenamento e blocos combinacionais:

    banco de registradores
        ↓
    multiplexadores de operandos
        ↓
    ALU / shifter / comparador
        ↓
    seleção de endereço ou resultado
        ↓
    multiplexador de writeback
        ↓
    banco de registradores

O tecido combinacional responde “quais devem ser os próximos valores?”. Armazenamento sequencial responde “quando esses valores se tornam o estado da máquina?”.

Os próximos capítulos aprofundam as duas direções: circuitos aritméticos detalham os blocos de transformação; latches e flip-flops explicam como valores calculados são capturados e preservados.

## Uma saída logicamente constante ainda pode apresentar glitch

Considere F = AB OR (NOT A)C, implementada por dois caminhos AND que alimentam OR. Com B = C = 1, a álgebra dá F = A OR NOT A = 1. Porém, se A cair, o caminho AB pode cair antes de o inversor e o segundo AND subirem. A saída pode tornar-se zero brevemente. Esse é um hazard estático de um: a saída estabilizada desejada permanece um, mas a propagação desigual cria um zero transitório.

Adicionar o termo de consenso BC produz F = AB OR (NOT A)C OR BC, logicamente equivalente. Com B = C = 1, BC mantém a saída alta durante a transição de A. O hardware adicional é redundante para a tabela verdade, mas útil nesse caso temporal de mudança de uma entrada. Não é uma solução universal para entradas simultâneas arbitrárias, travessias de clock ou qualquer tecnologia de portas.

O exemplo demonstra por que minimização booleana e correção física são tarefas separadas. Uma ferramenta de síntese pode remover termos logicamente redundantes se o fluxo não preservar o tratamento temporal pretendido. Um receptor síncrono pode tolerar glitches internos quando a entrada estabiliza durante setup e hold; uma entrada de controle assíncrona pode reagir imediatamente. A interface consumidora determina se o transitório é inofensivo.

## Profundidade de seleção e custo físico

Um multiplexador de oito entradas pode ser construído como árvore balanceada de sete multiplexadores de duas entradas, com três estágios em cada caminho de dados. Uma cascata serial pode usar a mesma quantidade de elementos e ainda expor algumas entradas a mais estágios. Contagem de portas isolada não captura o desequilíbrio. Tempo de chegada e fanout do seletor também importam: um seletor atrasado pode dominar mesmo quando o caminho de dados parece curto.

Um barrel shifter de 32 bits para deslocamentos de zero a 31 pode usar cinco estágios que selecionam deslocamentos de 1, 2, 4, 8 e 16 posições. Cada estágio escolhe entre a palavra intermediária inalterada e sua versão deslocada. Os cinco bits de controle codificam a quantidade em binário. A construção utiliza O(w log w) seleções elementares de bits para largura variável w, com profundidade O(log w). Um laço que desloca um bit por vez modela o mesmo resultado matemático sob regras adequadas, mas tem custo de execução diferente.

## Extração de campos como decodificador de software

Em `read_modrm` do ChrisCPU, um byte m é dividido em `mod = m >> 6`, `digit = (m >> 3) & 7` e `rm_field = m & 7`. As expressões selecionam campos disjuntos. Para m = `0xd9`, binário `11011001`, resultam mod = 3, digit = 3 e rm_field = 1. Bits de extensão REX são depois combinados com os campos de registrador; não devem ser confundidos com os três bits existentes no próprio m.

| Posições no byte | Campo extraído | Faixa antes das extensões |
|---|---|---|
| 7:6 | mod | 0–3 |
| 5:3 | digit | 0–7 |
| 2:0 | rm_field | 0–7 |

A função verifica bytes disponíveis antes de ler ModR/M e antes de consumir SIB ou deslocamento opcionais. Sua saída depende, portanto, de seleção de bits e limites do parser. Diferentemente de uma função combinacional pura, essa rotina C avança por um buffer e modifica uma estrutura de instrução decodificada. O vocabulário de circuitos explica os seletores; o contrato de software acrescenta segurança de memória, estado dos prefixos e retornos de falha.

O código revisado implementa essas operações em C; disso não decorre decodificação em nível de portas ou temporização fiel ao hardware. Uma instrução válida também exige regras de opcode, modo e operandos além dessa separação. O exemplo de byte é intencionalmente mais restrito que afirmar suporte a toda instrução que contenha esses bits.
