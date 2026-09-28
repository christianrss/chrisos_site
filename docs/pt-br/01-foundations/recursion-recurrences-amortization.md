---
id: recursion-recurrences-amortization
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_parse.c
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
symbols:
  - ShComp
  - Ast
  - enter
  - leave
  - parse_primary
  - parse_unary
  - parse_bin
  - parse_expr
  - node_new
  - clvm_vm_push64
  - clvm_vm_pop64
  - ClvmVm
depends_on:
  - algorithmic-complexity
  - proof-invariants-induction
related:
  - data-structures
  - arrays-lists-stacks-queues
  - parsing
  - shader-frontend
---

# Recursão, recorrências e análise amortizada

<div class="abstract">
Recursão define uma computação em termos de instâncias menores da mesma computação. Recorrências modelam o custo dessa autorreferência, enquanto análise amortizada distribui operações ocasionalmente caras por uma sequência inteira, em vez de tratar cada operação isoladamente. Essas ferramentas são especialmente importantes em software de sistemas porque controle recursivo consome stack, nesting de parser pode ser controlado por entrada hostil e uma operação com bom custo amortizado ainda pode apresentar latência de pior caso inaceitável. Este capítulo desenvolve correção recursiva, resolução de recorrências e métodos agregado, contábil e de potencial, reconciliando-os com o source atual do ChrisOS: o parser de shaders usa recursive descent com limite explícito de nesting 32, criação de AST é limitada a 512 nodes e CLVM mantém stacks de operandos e chamadas de capacidade fixa com checks explícitos de overflow e underflow.
</div>

## Pré-requisitos e escopo

Este capítulo depende de complexidade algorítmica e prova por indução.

Indução demonstra uma propriedade sobre objetos construídos recursivamente. Recursão usa a mesma estrutura operacionalmente.

Um algoritmo recursivo exige:

- domínio de instâncias;
- um ou mais casos base;
- casos recursivos que reduzam o problema;
- medida de progresso que prove terminação;
- modelo de recursos para tempo e espaço.

Recorrências descrevem como o custo varia com o tamanho da entrada.

Análise amortizada é relacionada, porém distinta: raciocina sobre sequência de operações com custos individuais variáveis.

~~~text
definição recursiva
      ↓
argumento de terminação
      ↓
recorrência de custo
      ↓
bound assintótico

sequência de operações
      ↓
passos caros e baratos
      ↓
agregado/contábil/potencial
      ↓
bound amortizado
~~~

## Definições recursivas

Uma definição recursiva faz referência a si mesma em estrutura menor.

Fatorial é o exemplo clássico:

~~~text
0! = 1
n! = n · (n-1)! para n > 0
~~~

O caso base interrompe a expansão. O caso recursivo diminui n.

Sem medida decrescente, uma definição recursiva pode não terminar.

Em estruturas de dados, a forma recursiva pode substituir o tamanho numérico. Um algoritmo sobre árvore pode recursar em subárvores filhas, cada uma com menos nodes que a árvore original.

## Recursão operacional

Em runtime, uma chamada recursiva normalmente cria outro activation record.

Um activation pode conter:

- return address;
- registradores salvos;
- variáveis locais;
- argumentos ou valores spilled;
- alignment e padding exigidos pela ABI.

Para profundidade d e frame size f, o consumo de stack é aproximadamente:

~~~text
O(d · f)
~~~

mais overhead específico de ABI e compilador.

Esse espaço é concreto. Em kernels, bootloaders, firmware e sistemas embarcados, stack normalmente é fixa e relativamente pequena.

Uma recursão matematicamente terminante ainda pode falhar operacionalmente por esgotar stack antes de alcançar o caso base.

## Correção do caso base

Uma prova recursiva normalmente espelha o código recursivo.

Para função F(n):

1. demonstrar que o caso base retorna o resultado exigido;
2. assumir que a chamada recursiva está correta para argumento menor;
3. demonstrar que o frame atual transforma esse resultado no resultado correto para n.

A hipótese indutiva só é válida quando as chamadas recursivas são feitas sobre instâncias cobertas pela medida.

Uma função que às vezes recursa sobre o mesmo tamanho não satisfaz o argumento padrão de terminação.

## Medidas de progresso

Uma medida de progresso mapeia um estado para um conjunto bem fundado ordenado.

Medidas comuns incluem:

- inteiro n diminuindo até zero;
- quantidade de tokens não processados;
- altura restante de árvore;
- quantidade de nodes ainda não visitados;
- comprimento de intervalo;
- profundidade de nesting em relação a um limite fixo.

Todo passo recursivo válido precisa mover a medida em direção à terminação.

Para funções mutuamente recursivas, a medida pode precisar cobrir o sistema combinado de transições.

## Recursão direta e mútua

Recursão direta ocorre quando F chama F.

Recursão mútua ocorre quando:

~~~text
F → G → H → F
~~~

Parsers recursive descent costumam usar recursão mútua porque nonterminals da gramática chamam uns aos outros.

O parser de shaders atual do ChrisOS usa ambas:

- parse_unary pode chamar a si mesma;
- parse_bin pode chamar a si mesma em precedência mais forte;
- parse_primary pode chamar parse_expr em expressões entre parênteses ou indexadas;
- parsing de expressões chama helpers de níveis inferiores.

A recursão segue a estrutura da gramática em vez de uma única recorrência de livro-texto.

## Parsing por recursive descent

Um parser recursive descent associa funções de parsing a camadas da gramática.

Conceitualmente:

~~~text
expressão
  └─ precedência binária
       └─ unary
            └─ primary
                 ├─ literal
                 ├─ identifier
                 ├─ call
                 ├─ constructor
                 └─ expressão entre parênteses
~~~

Essa organização torna precedência e nesting sintático explícitos.

Também torna a profundidade de stack do parser proporcional ao nesting sintático e à estrutura recursiva de operadores, salvo transformação em iteração.

## Contrato de profundidade no parser de shaders

O sh_int.h atual define:

~~~text
SH_NEST_MAX = 32
SH_AST_MAX  = 512
~~~

ShComp contém:

~~~text
int depth;
Ast ast[SH_AST_MAX];
int nast;
~~~

O helper enter rejeita outro nível quando:

~~~text
depth >= SH_NEST_MAX
~~~

e registra erro de nesting.

Somente depois do check incrementa depth.

leave decrementa depth quando positivo.

Esse é um bound explícito de recurso ao redor da recursão do parser. É mais forte do que confiar em falha natural da stack do host ou kernel.

## Invariante de profundidade

Para pares enter/leave bem-sucedidos, um invariante útil é:

~~~text
0 <= depth <= SH_NEST_MAX
~~~

Um enter bem-sucedido a partir de depth < SH_NEST_MAX produz:

~~~text
depth' = depth + 1
~~~

Um leave correspondente reduz o valor novamente.

O source não demonstra automaticamente que edits futuros jamais omitirão leave em qualquer failure path; isso exigiria análise path-sensitive ou testes.

Os helpers atuais, porém, codificam diretamente o bound pretendido.

## Capacidade da AST como segundo bound

Profundidade recursiva e tamanho total de sintaxe são recursos diferentes.

Uma expressão rasa ainda pode gerar muitos nodes.

node_new verifica:

~~~text
nast >= SH_AST_MAX
~~~

e rejeita nodes adicionais antes de indexar o array de AST.

O parser possui portanto pelo menos duas restrições independentes:

| Recurso | Limite |
|---|---:|
| nesting recursivo | 32 |
| nodes da AST | 512 |

Um parser seguro precisa de ambos quando tamanho e nesting da entrada podem ser externos.

## Parsing recursivo por precedência

parse_bin recebe uma precedência mínima e:

1. faz parse do operando esquerdo unary/primary;
2. inspeciona o próximo operador;
3. encerra se a precedência for inferior ao mínimo;
4. consome o operador;
5. faz parse recursivo do lado direito com precedência mínima mais forte;
6. cria node binário da AST.

Essa forma é um parser recursivo de precedence climbing.

Para token stream de comprimento n, parsing comum bem-sucedido foi estruturado para consumir tokens monotonicamente em vez de reiniciar do início.

O custo de alto nível é portanto linear no número de tokens consumidos para a gramática suportada, sujeito a scans limitados como lookup na pequena tabela de operadores e error recovery.

A profundidade recursiva não precisa ser igual a n porque precedência e limites de nesting restringem a estrutura.

## Recursão e associatividade

A escolha do threshold recursivo influencia associatividade.

Chamar o lado direito com:

~~~text
prec + 1
~~~

faz operadores da mesma precedência permanecerem no loop externo em vez de serem absorvidos pela chamada recursiva da direita.

Esse é o mecanismo usual para operadores left-associative em precedence climbing.

A recursão codifica semântica, não apenas estilo de implementação.

Alterar a estrutura recursiva pode alterar a parse tree.

## Bounds de stack no CLVM

CLVM mantém dois arrays de capacidade fixa:

~~~text
stack[CLVM_STACK_MAX]   com CLVM_STACK_MAX = 256
calls[CLVM_CALL_MAX]    com CLVM_CALL_MAX = 64
~~~

e stack pointers sp e csp.

A operand stack não é a C stack do host. É estado da VM.

Ainda assim, o mesmo raciocínio de recurso limitado se aplica.

clvm_vm_push64 rejeita push quando:

~~~text
sp == CLVM_STACK_MAX
~~~

e clvm_vm_pop64 rejeita pop quando:

~~~text
sp == 0
~~~

O caminho atual de restauração de longjmp também valida sp e csp restaurados contra os dois máximos.

## Execução recursiva do guest e recursão do host

Uma virtual machine pode representar nesting de calls do guest sem chamar recursivamente o interpretador do host.

Essa distinção é importante.

Uma call do guest pode empilhar return PC em stack gerenciada pela VM e continuar em dispatch loop iterativo.

Benefícios incluem:

- check explícito de overflow;
- limite previsível de profundidade do guest;
- serialização mais simples do estado da VM;
- separação do tamanho da stack da thread host.

Assim, “o programa guest é recursivo” não implica “o host interpreter chama a si mesmo para cada guest frame.”

O modelo atual do CLVM possui armazenamento explícito e limitado de calls.

## Relações de recorrência

Uma recorrência define uma quantidade usando instâncias menores.

Exemplos:

Recursão linear:

~~~text
T(n) = T(n-1) + c
~~~

Divide and conquer binário:

~~~text
T(n) = 2T(n/2) + cn
~~~

Recursão por metade:

~~~text
T(n) = T(n/2) + c
~~~

Uma recorrência precisa de base como T(1) = c0.

Sem o caso base, não define completamente o custo finito.

## Resolução de recorrência linear

Considere:

~~~text
T(n) = T(n-1) + c
T(0) = d
~~~

Expandindo:

~~~text
T(n)
= T(n-1) + c
= T(n-2) + 2c
...
= T(0) + nc
= d + nc
~~~

Portanto:

~~~text
T(n) = Θ(n)
~~~

Esse padrão descreve muitas traversals lineares recursivas.

Implementações recursiva e iterativa podem ter a mesma complexidade de tempo e diferir no espaço de stack.

## Recorrências por metade

Para:

~~~text
T(n) = T(n/2) + c
~~~

o argumento pode ser dividido por dois aproximadamente log2(n) vezes até chegar a 1.

Portanto:

~~~text
T(n) = Θ(log n)
~~~

Binary search é o exemplo clássico.

O resultado assume trabalho adicional constante em cada nível.

Se cada nível percorre região de tamanho n, a recorrência é diferente.

## Recorrências divide and conquer

Para:

~~~text
T(n) = aT(n/b) + f(n)
~~~

o custo total combina:

- quantidade de subproblemas a;
- fator de redução b;
- trabalho não recursivo f(n).

O Master Theorem classifica muitas recorrências regulares comparando f(n) com:

~~~text
n^(log_b a)
~~~

Ele não se aplica a qualquer recorrência.

Splits irregulares, coeficientes variáveis ou recursão dependente de dados podem exigir substitution, recursion trees ou outros métodos.

## Árvores de recursão

Uma recursion tree expande o trabalho por nível.

Para recorrência semelhante a merge sort:

~~~text
T(n) = 2T(n/2) + n
~~~

cada nível realiza Θ(n) de trabalho total e a árvore possui Θ(log n) níveis.

Logo:

~~~text
T(n) = Θ(n log n)
~~~

O método evidencia onde o trabalho se acumula.

Também ajuda a analisar paralelismo porque subárvores independentes podem executar concorrentemente.

## Recorrências de espaço

Recorrências de tempo não são suficientes para código recursivo de sistemas.

Para depth-first recursion com um único filho ativo por vez:

~~~text
S(n) = S(smaller(n)) + frame_space
~~~

Espaço depende da profundidade máxima ativa, e não da quantidade total de calls.

Uma recursão binária completa pode executar número exponencial de calls e ainda usar apenas O(depth) frames ativos quando subcalls retornam antes dos siblings.

Tempo e peak space precisam de modelos separados.

## Tail recursion

Uma call está em tail position quando seu resultado se torna diretamente o resultado do caller, sem trabalho restante.

Alguns compiladores podem transformar tail recursion em jump, eliminando frames adicionais.

Essa otimização não é garantida pela linguagem C em código arbitrário, e um kernel não deve depender dela a menos que o comportamento do toolchain faça parte do contrato validado.

Um loop explícito comunica intenção de stack constante de forma mais robusta entre compiladores.

## Recursão versus stacks explícitas

Traversal recursiva:

~~~text
visit(node):
    para child em children(node):
        visit(child)
~~~

pode ser transformada em stack explícita:

~~~text
push(root)
while stack não vazia:
    node = pop()
    push children
~~~

A forma iterativa move o estado de controle dos call frames para uma estrutura de dados.

Vantagens podem incluir:

- capacidade explícita;
- crescimento via heap quando permitido;
- possibilidade de pausar e retomar;
- serialização;
- controle da ordem de traversal.

O custo é mais gerenciamento manual de estado.

## Análise amortizada

Análise amortizada limita o custo médio por operação sobre uma sequência de pior caso.

Não é average-case probabilístico.

Se m operações custam no total no máximo:

~~~text
C(m)
~~~

então o custo amortizado é:

~~~text
C(m) / m
~~~

Uma única operação ainda pode ser muito mais cara que o bound amortizado.

Isso importa para interrupt latency e real-time.

## Método agregado

O método agregado calcula diretamente o custo total da sequência.

Considere stack com PUSH, POP e MULTIPOP(k), onde MULTIPOP remove até k itens.

Um MULTIPOP individual pode custar Θ(n).

Ao longo de m operações iniciadas com stack vazia, cada elemento pode ser removido no máximo uma vez após ter sido inserido.

Logo o total de pops é limitado pelo total de pushes.

A sequência possui Θ(m) primitive stack operations, resultando em O(1) amortizado por operação de alto nível no modelo padrão.

## Método contábil

O método contábil atribui cobrança artificial a cada operação.

Operações baratas podem receber cobrança maior que o custo imediato; o excedente paga operações caras futuras.

Para dynamic array com capacidade duplicada:

- cobrar append acima do write imediato;
- manter crédito nos elementos existentes;
- usar o crédito quando resize precisar copiá-los.

O invariante contábil exige crédito nunca negativo.

É uma técnica de prova, não um mecanismo bancário em runtime.

## Método do potencial

O método do potencial associa potencial não negativo Φ(state) a cada estado da estrutura.

O custo amortizado é:

~~~text
custo real
+ Φ(depois)
- Φ(antes)
~~~

Somando uma sequência, os potenciais intermediários telescopam:

~~~text
Σ amortizado
=
Σ real
+ Φ(final)
- Φ(inicial)
~~~

Se o potencial possui lower bound e começa em valor conhecido, seguem bounds amortizados.

Potencial é útil quando um escalar representa o trabalho adiado acumulado no estado atual.

## Prova do doubling em dynamic array

Considere capacidade inicial 1 e doubling sempre que append encontra array cheio.

Resizes copiam:

~~~text
1 + 2 + 4 + ... + 2^k
~~~

elementos antes de chegar a capacidade próxima de n.

A soma geométrica é:

~~~text
2^(k+1) - 1 < 2n
~~~

Assim, n appends realizam:

- n writes dos novos elementos;
- menos de 2n cópias causadas pelos resizes.

O trabalho total é O(n), logo append custa O(1) amortizado.

O append individual que dispara resize continua O(n).

## Trade-offs do fator de crescimento

Doubling não é a única política geométrica.

Para fator g > 1:

- g maior reduz frequência de resize;
- g maior aumenta capacidade ociosa após crescimento;
- g menor reduz slack, mas copia mais vezes.

O resultado O(1) amortizado depende de crescimento geométrico, não especificamente do fator 2.

Crescimento linear como “aumentar capacidade em 1 toda vez” produz:

~~~text
1 + 2 + ... + n = Θ(n²)
~~~

de cópias em n appends.

## Complexidade amortizada em software de sistemas

Uma garantia amortizada é insuficiente quando a operação cara não pode ocorrer em certo caminho.

Exemplos:

- hard interrupt paths;
- critical sections sob spinlock;
- hot paths do scheduler;
- caminhos de device submission com orçamento rígido de latência.

Designs de sistemas frequentemente preferem:

- arrays de capacidade fixa;
- pools preallocated;
- rings;
- rehashing incremental;
- manutenção em batches;
- reclamation em background.

O objetivo pode ser bound mais forte por operação, mesmo com menor eficiência média de memória.

## Falha e saturação

Algoritmos recursivos falham de forma diferente de estruturas dinâmicas amortizadas.

Falhas recursivas incluem:

- ausência de base case;
- argumento que não diminui;
- estrutura cíclica quando se assumia acíclica;
- stack overflow do host;
- rejeição explícita por nesting limit.

Estruturas dinâmicas/amortizadas podem falhar por:

- allocation failure;
- capacity overflow;
- integer overflow no cálculo de crescimento;
- pointer invalidation após relocation;
- latency spike durante resize.

Contratos corretos declaram essas falhas separadamente do custo assintótico.

## Implicações de segurança

Recursão controlada por input é uma fronteira de denial of service.

Input adversarial pode tentar maximizar:

- nesting depth;
- quantidade de AST nodes;
- backtracking;
- custo de error recovery;
- pressão de alocação.

O parser de shaders revisado limita nesting e tamanho da AST.

Esses limites reduzem risco de resource exhaustion, mas este capítulo não declara proteção completa contra toda sequência malformada de tokens.

Da mesma forma, limites das stacks da VM convertem nesting guest excessivo em faults explícitos em vez de permitir que estado guest ultrapasse arrays fixos.

## Concorrência

Análise por recorrências normalmente assume uma execução lógica.

Algoritmos recursivos paralelos precisam de modelos adicionais:

- work: operações totais;
- span: maior cadeia de dependências;
- overhead de scheduling;
- sincronização;
- contenção de bandwidth de memória.

Análise amortizada sob concorrência também é mais difícil porque créditos ou potencial podem pertencer a estado compartilhado.

Uma prova amortizada sequencial não pode ser reutilizada silenciosamente para estrutura lock-free concorrente.

## Evidência de validação

O checker determinístico específico valida:

- expansão de recorrências lineares e por metade;
- soma geométrica do custo de doubling;
- contabilização agregada de stack;
- potencial não negativo em modelo simples de growable array;
- transições limitadas de recursion depth;
- push/pop de stack explícita limitada;
- âncoras atuais de source para SH_NEST_MAX, SH_AST_MAX, enter, leave, recursão de parse_unary/parse_bin, CLVM_STACK_MAX e CLVM_CALL_MAX.

O checker valida os modelos documentados e a fronteira com o source. Não constitui prova formal completa do parser ou da VM.

## Limitações atuais

Este capítulo não cobre integralmente:

- análise de recorrências por Akra-Bazzi;
- generating functions;
- recorrências randomized;
- schedulers paralelos por work/span;
- memoization e dynamic programming em profundidade;
- continuation-passing style;
- verificação formal de uso de stack;
- análise de response time real-time.

Esses temas podem ser adicionados quando subsistemas posteriores do ChrisOS exigirem.

## Fronteira do roadmap

A transição curricular é:

~~~text
complexidade e prova
      ↓
recursão e recorrências
      ↓
análise amortizada de sequências
      ↓
arrays, lists, stacks e queues concretos
      ↓
estruturas especializadas e algoritmos de sistemas
~~~

O próximo capítulo aplica esses modelos a estruturas lineares e separa operações abstratas de suas representações reais no ChrisOS.

## Proveniência da revisão

As afirmações ligadas à implementação foram conciliadas contra ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

Fontes revisadas:

- kernel/gfx/shader/sh_int.h;
- kernel/gfx/shader/sh_parse.c;
- compiler/clvm/clvm_vm.h;
- compiler/clvm/clvm_vm.c.

Símbolos revisados:

- ShComp;
- Ast;
- enter;
- leave;
- parse_primary;
- parse_unary;
- parse_bin;
- parse_expr;
- node_new;
- ClvmVm;
- clvm_vm_push64;
- clvm_vm_pop64.

O source demonstra bounds explícitos de nesting/AST no parser e limites de stacks gerenciadas pela VM. Os resultados gerais de recorrência e análise amortizada são fundamentos matemáticos e não são apresentados como se todo subsistema do ChrisOS utilizasse essas estratégias específicas.
