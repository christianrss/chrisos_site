---
id: boolean-algebra
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- chrisvm/cpu/emulator/flags.c
symbols:
- chris_cc_true
- write_status
depends_on:
  - logic-levels-noise-margins
related:
- combinational-logic
---

# Álgebra booleana e representação lógica

<div class="abstract">
Álgebra booleana é a camada matemática que separa o raciocínio digital das tensões dos transistores. Ela define operações sobre dois valores lógicos, identidades para transformar expressões, representações canônicas e a diferença entre equivalência lógica e implementação física. O objetivo deste capítulo é desenvolver a álgebra até o ponto necessário para compreender portas, decoders, circuitos aritméticos, decodificação de instruções e máquinas de estados.
</div>

## Valores lógicos são uma abstração

Os símbolos 0 e 1 da álgebra booleana são valores matemáticos. No hardware eles podem ser representados por faixas de tensão, estados de carga, orientação magnética ou outros mecanismos físicos. A álgebra deliberadamente ignora esses detalhes.

Uma variável booleana assume um entre dois valores. Operações comuns são:

| Nome | Notação | Significado |
|---|---|---|
| NOT | ¬A | complemento |
| AND | A ∧ B | verdadeiro somente quando ambos são verdadeiros |
| OR | A ∨ B | verdadeiro quando ao menos um é verdadeiro |
| XOR | A ⊕ B | verdadeiro quando entradas diferem |
| NAND | ¬(A ∧ B) | complemento do AND |
| NOR | ¬(A ∨ B) | complemento do OR |

Uma porta implementa fisicamente uma dessas relações, mas a relação lógica independe da topologia de transistores utilizada.

## Tabelas-verdade

Uma tabela-verdade enumera a saída para cada combinação de entradas. Para duas entradas existem quatro combinações.

| A | B | A ∧ B | A ∨ B | A ⊕ B |
|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 |
| 0 | 1 | 0 | 1 | 1 |
| 1 | 0 | 0 | 1 | 1 |
| 1 | 1 | 1 | 1 | 0 |

Tabelas-verdade são completas, porém escalam exponencialmente. Uma função de n variáveis independentes possui 2^n combinações. Sistemas grandes exigem representações algébricas, estruturais e algorítmicas em vez de enumeração explícita.

## Identidades fundamentais

Várias identidades permitem simplificar expressões sem alterar sua função.

| Identidade | Expressão |
|---|---|
| identidade | A ∧ 1 = A; A ∨ 0 = A |
| dominação | A ∧ 0 = 0; A ∨ 1 = 1 |
| idempotência | A ∧ A = A; A ∨ A = A |
| complemento | A ∧ ¬A = 0; A ∨ ¬A = 1 |
| involução | ¬(¬A) = A |
| comutativa | A ∧ B = B ∧ A; A ∨ B = B ∨ A |
| associativa | (A ∧ B) ∧ C = A ∧ (B ∧ C) |
| distributiva | A ∧ (B ∨ C) = (A ∧ B) ∨ (A ∧ C) |

A álgebra booleana também possui a forma dual em que OR distribui sobre AND, diferente da álgebra aritmética comum.

Essas leis não servem apenas para manipulação simbólica. Ferramentas de síntese aplicam transformações equivalentes para alterar área, profundidade lógica, consumo e fan-out preservando comportamento.

## Leis de De Morgan

As leis de De Morgan relacionam complemento de conjunção e disjunção:

¬(A ∧ B) = ¬A ∨ ¬B

¬(A ∨ B) = ¬A ∧ ¬B

Elas explicam por que redes NAND e NOR podem substituir redes AND/OR com sinais invertidos. Também são úteis ao interpretar sinais ativos em nível baixo. Um sinal RESET_N, por exemplo, pode solicitar reset quando eletricamente vale 0.

## Princípio da dualidade

A álgebra booleana possui dualidade: trocar AND por OR e 0 por 1 em uma identidade válida produz outra identidade válida.

A identidade:

A ∨ 0 = A

tem como dual:

A ∧ 1 = A

A dualidade ajuda a reconhecer simetrias e também está relacionada à estrutura complementar das redes de pull-up e pull-down em CMOS.

## Soma de produtos e produto de somas

Toda função booleana pode ser representada em formas canônicas.

Um **mintermo** é um termo AND que contém cada variável ou seu complemento. Fazer OR dos mintermos correspondentes às linhas em que a função vale 1 produz uma soma de produtos.

Um **maxtermo** é um termo OR contendo cada variável ou seu complemento. Fazer AND dos maxtermos associados às linhas em que a função vale 0 produz um produto de somas.

As formas canônicas geralmente são maiores que circuitos otimizados, mas demonstram completude: qualquer tabela-verdade finita pode ser transformada mecanicamente em expressão lógica.

## Exemplo de mintermos

Considere F(A,B) verdadeiro apenas para 01 e 10. Os mintermos são:

¬A ∧ B

A ∧ ¬B

Logo:

F = (¬A ∧ B) ∨ (A ∧ ¬B)

Essa é exatamente a função XOR. O exemplo mostra como converter uma tabela em expressão sem precisar “adivinhar” a porta correspondente.

## Completude funcional

Um conjunto de operações é funcionalmente completo quando qualquer função booleana pode ser expressa usando apenas operações desse conjunto.

NOT + AND é completo porque OR pode ser obtido por De Morgan. NOT + OR também. NAND sozinho é completo, assim como NOR.

Usando apenas NAND:

¬A = A NAND A

A ∧ B = ¬(A NAND B)

A ∨ B = (¬A) NAND (¬B)

Isso possui consequência física: uma biblioteca de células não precisa de um elemento lógico primitivo independente para cada função. Células complexas são introduzidas por eficiência de área, energia ou timing, e não por necessidade de expressividade lógica.

## XOR e paridade

XOR merece tratamento especial porque representa soma módulo 2:

0 ⊕ 0 = 0
0 ⊕ 1 = 1
1 ⊕ 0 = 1
1 ⊕ 1 = 0

Por isso aparece em somadores, geração de paridade, checksums, estruturas de realimentação linear e diversas operações bit a bit.

Para múltiplas entradas, XOR vale 1 quando uma quantidade ímpar de entradas vale 1. Esse é o comportamento de paridade.

## Implicação e equivalência

Condições digitais também podem ser expressas por implicação e equivalência.

A → B é falso somente para A = 1 e B = 0. Algebricamente:

A → B = ¬A ∨ B

Equivalência lógica é verdadeira quando operandos coincidem:

A ↔ B = ¬(A ⊕ B)

Comparadores e lógica de controle implementam esses conceitos mesmo quando esquemas usam XOR, XNOR, AND e OR em vez dos símbolos matemáticos.

## Vetores de bits

Hardware raramente manipula apenas variáveis isoladas. Bits são agrupados em vetores.

Um vetor de 8 bits contém b7 até b0. Conforme a interpretação pode representar inteiro sem sinal, inteiro em complemento de dois, caractere, conjunto de flags, parte de um endereço ou dados binários opacos.

A camada booleana não atribui significado ao vetor. O significado vem da codificação usada pela camada seguinte.

Essa distinção é central em sistemas operacionais. O mesmo padrão de 64 bits pode ser interpretado como endereço, inteiro, entrada de page table ou coleção de flags, dependendo do contrato de uso.

## Álgebra booleana e álgebra aritmética

O uso dos símbolos 0 e 1 pode causar confusão. Em álgebra booleana:

1 ∨ 1 = 1

Em aritmética inteira:

1 + 1 = 2

XOR se comporta como soma de um bit sem carry. AND participa da geração de carry. Circuitos aritméticos combinam operações booleanas para realizar aritmética comum.

Compreender a diferença evita erros ao alternar entre operadores de linguagem, instruções de máquina e expressões matemáticas.

## Minimização lógica

Expressões booleanas equivalentes podem ter custos físicos muito diferentes. Minimização procura reduzir número de portas, profundidade ou outra métrica.

Para funções pequenas, mapas de Karnaugh fornecem método geométrico. Para funções maiores, algoritmos como Quine-McCluskey e heurísticas de síntese trabalham sobre representações simbólicas.

Otimização real é limitada por fatores físicos. Uma expressão com menos termos pode criar fan-out maior ou caminho mais lento. Síntese moderna trabalha com bibliotecas caracterizadas e restrições de timing, não apenas com contagem abstrata de portas.

## Condições don't-care

Algumas combinações de entrada podem ser impossíveis ou irrelevantes. Um decoder de dígitos decimais codificados em quatro bits, por exemplo, utiliza apenas 0000 a 1001. Combinações restantes podem ser marcadas como don't-care e usadas para simplificação.

Don't-care é um contrato. Se um estado considerado impossível aparecer por falha, transição assíncrona ou futura extensão, o circuito otimizado pode produzir qualquer saída.

O mesmo princípio aparece em software: estados “inalcançáveis” permitem otimização, mas tornam-se perigosos quando as premissas são quebradas.

## Álgebra booleana no controle de uma CPU

Decodificadores de instrução, verificações de privilégio e sinais de controle são grandes funções booleanas de bits de opcode, modo e estado atual.

Conceitualmente:

decode_ADD = opcode_match ∧ valid_mode ∧ ¬fault

select_result = operation_valid ∧ destination_enabled

take_exception = fault_present ∧ exception_enabled

CPUs reais usam estruturas muito mais complexas, porém composição booleana continua sendo o fundamento do controle.

## Da álgebra ao circuito

Álgebra booleana define qual relação deve existir. Lógica combinacional determina como essa relação será realizada por portas, caminhos de propagação e recursos físicos.

O próximo capítulo introduz decoders, multiplexadores, encoders, comparadores e blocos aritméticos, transformando expressões simbólicas em datapaths conectados.

## Decomposição de Shannon transforma uma função em seleção

Fixe uma variável X de uma função booleana F. Defina F_0 como a função restante quando X = 0 e F_1 quando X = 1. Então F = (NOT X AND F_0) OR (X AND F_1). Exatamente um ramo é habilitado para cada valor booleano de X. A equação é uma prova de equivalência, não uma heurística: substituir qualquer valor reproduz o subconjunto correspondente das linhas da função original.

Para F = A XOR B, escolher X = A dá F_0 = B e F_1 = NOT B. Um multiplexador que selecione B ou seu complemento implementa XOR. Repetir a decomposição cria uma árvore de decisão. Compartilhar funções residuais idênticas pode comprimi-la em um grafo, embora a ordem das variáveis possa alterar drasticamente seu tamanho. Uma expressão booleana compacta e um grafo compacto não necessariamente coincidem.

A decomposição também esclarece por que um multiplexador físico não significa “executar um ramo de software”. Os dois circuitos de entrada podem avaliar fisicamente, enquanto o seletor controla o valor que chega à saída. Em C, uma expressão condicional avalia apenas a expressão de valor selecionada. Concordância funcional em entradas booleanas puras não implica concordância em efeitos colaterais, exceções, tráfego de barramento ou custo de avaliação.

## Máscaras vetoriais e provas de preservação

Para substituir bits selecionados, defina uma máscara M com uns exatamente nas posições a substituir. Então novo = (antigo AND NOT M) OR (valor AND M). Onde M é zero, a expressão reduz-se a antigo; onde M é um, reduz-se a valor. Essa prova por posição estabelece tanto a atualização quanto a preservação dos demais bits. É mais forte que conferir um exemplo hexadecimal.

`write_status`, em `flags.c` do ChrisCPU, utiliza esse princípio limpando o conjunto de bits de estado antes de inserir as novas flags. O bit 1 é depois forçado explicitamente para um. A distinção entre bits preservados, substituídos e forçados integra a interface. Uma máscara com um bit extra acidental poderia alterar silenciosamente controle de interrupções ou outro campo mesmo com resultado aritmético correto.

Os operadores lógicos `&&` e `||` de C normalizam valores de verdade e utilizam curto-circuito. Os operadores bit a bit `&` e `|` atuam em todas as posições e não fornecem esse contrato de curto-circuito. Assim, `pointer && pointer->field` pode proteger a desreferência, enquanto substituir `&&` por `&` não preserva a segurança. Reescritas algébricas de proposições puras não podem ser aplicadas cegamente a expressões que acessam memória ou alteram estado.

## Condições implementadas pelo ChrisCPU

`chris_cc_true` extrai CF, PF, ZF, SF e OF de uma palavra de flags e seleciona um predicado com `cc & 15`. Condições complementares formam pares adjacentes. Por exemplo, menor-ou-igual sem sinal é CF OR ZF, enquanto maior sem sinal é NOT CF AND NOT ZF. De Morgan demonstra a complementaridade para todas as combinações de flags, inclusive combinações não produzidas normalmente por uma instrução aritmética específica.

| Relação após comparação | Predicado | Oposto |
|---|---|---|
| Menor sem sinal | CF | NOT CF |
| Igual | ZF | NOT ZF |
| Menor ou igual sem sinal | CF OR ZF | NOT CF AND NOT ZF |
| Menor com sinal | SF XOR OF | SF igual a OF |
| Menor ou igual com sinal | ZF OR (SF XOR OF) | NOT ZF AND (SF igual a OF) |

São predicados concretos da função inspecionada, não uma política completa de permissões ou exceções. Comparação com sinal precisa de OF porque o sinal da subtração modular isolado é insuficiente. A derivação está em [Circuitos aritméticos](arithmetic-circuits.md). A verificação aritmética reproduzível cobre as 32 combinações das cinco flags contra as dezesseis condições, incluindo a seleção pelos quatro bits baixos. Isso estabelece esse mapeamento booleano finito; não estabelece a correção do decodificador que escolhe a condição nem do executor que aplica o destino do salto.
