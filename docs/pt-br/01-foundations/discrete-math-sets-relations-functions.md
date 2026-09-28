---
id: discrete-math-sets-relations-functions
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - chrisvm/chris_arch.h
  - compiler/chrisld/chriso.h
  - compiler/chrisasm/chrisasm.c
  - chrisvm/cpu/emulator/flags.c
  - kernel/gfx/graphics.c
symbols:
  - ChrisArchitectureState
  - ChrisoImage
  - ChrisoRel
  - reg_index
  - add_sym
  - chris_cc_true
  - point_in_clip
depends_on:
  - boolean-algebra
  - number-systems-binary-arithmetic
related:
  - proof-invariants-induction
  - data-representation-layout
  - data-structures
  - graphs-union-find
---

# Matemática discreta: conjuntos, relações e funções

<div class="abstract">
Sistemas discretos são construídos a partir de coleções finitas ou contáveis, relações explícitas e transformações de estado. Conjuntos descrevem domínios de objetos, produtos cartesianos constroem espaços de estados, relações expressam conectividade ou ordenação e funções modelam mapeamentos determinísticos entre domínios. Essas ideias aparecem diretamente em código de sistemas operacionais e toolchains: índices de registradores formam conjuntos finitos, seções e símbolos de arquivos-objeto ocupam domínios limitados, registros de relocação relacionam objetos, parsers implementam funções parciais de texto para valores e predicados classificam pontos ou estados da máquina. Este capítulo desenvolve a linguagem matemática necessária para declarar esses contratos com precisão antes de introduzir algoritmos, invariantes e provas.
</div>

## Pré-requisitos e escopo

Álgebra booleana fornece predicados e conectivos lógicos. Sistemas numéricos fornecem domínios inteiros finitos e vetores de bits indexados.

Matemática discreta acrescenta uma linguagem para coleções e mapeamentos.

~~~text
objetos
  ↓
conjuntos e pertinência
  ↓
produtos e relações
  ↓
funções e composição
  ↓
espaços de estado, grafos, tabelas e interfaces
~~~

O objetivo não é usar notação abstrata por si só. Uma implementação de sistemas se torna mais fácil de raciocinar quando estão claros quais valores pertencem a um domínio, quais pares são permitidos, se um mapeamento é total e quais propriedades sobrevivem à composição.

## Conjuntos e pertinência

Um conjunto é uma coleção de elementos distintos.

Se x pertence ao conjunto A:

~~~text
x ∈ A
~~~

Se não pertence:

~~~text
x ∉ A
~~~

Dois conjuntos são iguais quando possuem exatamente os mesmos membros, independentemente da ordem da enumeração.

Por exemplo:

~~~text
A = {0, 1, 2}
B = {2, 1, 0}
~~~

implica A = B.

Multiplicidade não importa em um conjunto comum. Isso diferencia conjuntos de sequências, arrays e multiconjuntos.

## Domínios finitos

Software de sistemas opera frequentemente sobre conjuntos finitos.

Exemplos incluem:

- índices de registradores;
- IDs de CPU;
- valores de enum;
- file descriptors alocados;
- seções de arquivos-objeto;
- page-frame numbers dentro de um limite de memória física;
- índices de tabelas de capacidade fixa.

Um conjunto finito A possui cardinalidade |A| igual ao número de elementos.

Se:

~~~text
G = {0, 1, ..., 15}
~~~

então:

~~~text
|G| = 16
~~~

ChrisArchitectureState armazena atualmente dezesseis slots de registradores gerais em gpr[16]. O array fornece um domínio indexado finito concreto. Isso não implica que qualquer inteiro arbitrário seja um índice de registrador válido.

## Subconjuntos

A é subconjunto de B quando todo elemento de A também pertence a B:

~~~text
A ⊆ B
~~~

Um subconjunto próprio também exige A ≠ B.

Raciocínio por subconjuntos aparece sempre que um domínio é restringido por permissões ou estado.

Por exemplo, o conjunto de capabilities habilitadas deve ser subconjunto de todas as capabilities definidas pela ABI. O conjunto de índices de objetos atualmente válidos deve permanecer dentro da faixa alocada da tabela.

O conjunto vazio:

~~~text
∅
~~~

é subconjunto de qualquer conjunto.

## Operações com conjuntos

Para conjuntos A e B:

União contém elementos pertencentes a pelo menos um deles:

~~~text
A ∪ B
~~~

Interseção contém elementos pertencentes a ambos:

~~~text
A ∩ B
~~~

Diferença contém elementos de A que não pertencem a B:

~~~text
A \ B
~~~

Quando um universo U é fixado, complemento contém os elementos de U que não pertencem a A:

~~~text
U \ A
~~~

Essas operações correspondem a OR, AND e NOT booleanos quando conjuntos são representados por bit masks.

## Conjuntos como bit masks

Para um universo finito pequeno, membership pode ser representado por um bit para cada elemento possível.

Se U = {0,1,2,3}, o subconjunto {0,2} pode ser representado como:

~~~text
0101₂
~~~

quando o bit i representa membership de i.

Então:

~~~text
união         ↔ OR bitwise
interseção    ↔ AND bitwise
diferença     ↔ AND com complemento
~~~

Essa correspondência explica por que conjuntos de flags e capabilities são frequentemente codificados em bit fields.

A codificação só é válida quando o mapeamento entre elementos e posições de bit é explícito.

## Conjunto das partes

O conjunto das partes P(A) contém todos os subconjuntos de A.

Para um conjunto finito com n elementos:

~~~text
|P(A)| = 2^n
~~~

Isso se conecta diretamente a bit masks: uma máscara de n bits codifica 2^n subconjuntos possíveis de um universo com n elementos.

Quatro opções booleanas independentes produzem dezesseis conjuntos de opções possíveis.

Espaços de estado crescem exponencialmente quando dimensões binárias independentes são combinadas.

## Pares ordenados e tuplas

Conjuntos são não ordenados, mas estado de sistemas normalmente possui posição.

Um par ordenado:

~~~text
(a, b)
~~~

difere de (b, a), salvo quando a = b.

Tuplas generalizam essa ideia.

Um estado de CPU pode ser visto matematicamente como uma tupla contendo valores de registradores, control registers, segmentos, flags e outros campos.

ChrisArchitectureState é uma representação C concreta de um estado-produto desse tipo. A matemática não exige que a implementação armazene a tupla com um layout de memória específico.

## Produtos cartesianos

O produto cartesiano de A e B é:

~~~text
A × B = {(a,b) | a ∈ A e b ∈ B}
~~~

Se A e B são finitos:

~~~text
|A × B| = |A|·|B|
~~~

Produtos constroem espaços de estado.

Se um seletor de operação possui 8 valores e um seletor de tamanho de operando possui 4 valores, o produto irrestrito contém 32 pares. A implementação pode suportar apenas um subconjunto desses pares.

A distinção entre o produto completo e o subconjunto válido aparece diretamente em regras de validação de entrada.

## Relações

Uma relação binária R de A para B é um subconjunto de A × B.

Escreve-se:

~~~text
a R b
~~~

quando (a,b) pertence a R.

Relações modelam:

- arestas de grafos;
- “símbolo refere-se a uma seção”;
- “relocação refere-se a um símbolo”;
- “processo possui handle”;
- “página mapeia para frame”;
- “instrução pode transicionar para estado”.

Uma relação não precisa atribuir exatamente uma saída para cada entrada. Essa propriedade caracteriza funções.

## Relações no ChrisO

ChrisoImage contém um array limitado de símbolos e outro de relocações.

ChrisoRel armazena sym_index. Sob um contrato válido de imagem de objeto, uma relocação estabelece uma relação entre um registro de relocação e uma entrada de símbolo.

Matematicamente, se:

~~~text
R = conjunto de índices ativos de relocação
S = conjunto de índices ativos de símbolos
~~~

então a relação válida deve satisfazer:

~~~text
relates ⊆ R × S
~~~

e cada relocação ativa deve indicar um índice de símbolo admissível segundo as regras de validação do formato.

O campo C é apenas um número. Seu significado matemático é uma relação entre objetos indexados.

## Propriedades de relações

Para uma relação R sobre um conjunto A, algumas propriedades são fundamentais.

Reflexiva:

~~~text
para todo a ∈ A, a R a
~~~

Simétrica:

~~~text
a R b implica b R a
~~~

Antissimétrica:

~~~text
a R b e b R a implicam a = b
~~~

Transitiva:

~~~text
a R b e b R c implicam a R c
~~~

Essas propriedades classificam estruturas comuns.

Elas precisam ser demonstradas pela definição da relação; chamar uma relação de “ordem” ou “equivalência” não garante as leis necessárias.

## Relações de equivalência

Uma relação de equivalência é reflexiva, simétrica e transitiva.

Ela particiona um conjunto em classes de equivalência.

Exemplos em computação podem incluir:

- identificadores considerados iguais após normalização;
- endereços equivalentes segundo uma relação de offset de página;
- estados equivalentes segundo uma observação específica.

Equivalência depende do que é observado.

Dois estados de máquina podem ser equivalentes para um teste específico mesmo quando contadores internos diferem.

## Ordens parciais

Uma ordem parcial é reflexiva, antissimétrica e transitiva.

Inclusão de conjuntos é uma ordem parcial:

~~~text
A ⊆ B
~~~

Nem todo par precisa ser comparável.

Isso é relevante em sistemas de dependências. Dois pré-requisitos independentes podem anteceder um capítulo posterior sem que um tenha de anteceder o outro.

Uma ordem total adiciona comparabilidade para todo par.

Índices de arrays e a ordenação usual de inteiros formam ordens totais em seus domínios válidos.

## Grafos dirigidos como relações

Um grafo dirigido G = (V,E) possui um conjunto de vértices V e uma relação de arestas:

~~~text
E ⊆ V × V
~~~

Isso transforma teoria de grafos em teoria de relações.

Reachability não é o mesmo que adjacência direta. Se E contém as arestas diretas, reachability corresponde ao fecho transitivo de E.

Grafos de dependência, call graphs, control-flow graphs e ownership graphs usam essa distinção.

Um ciclo significa que algum elemento pode voltar a ser alcançado por uma sequência não vazia de arestas dirigidas.

O validador curricular usa exatamente esse tipo de raciocínio: pré-requisitos formam arestas dirigidas e ciclos são inválidos.

## Funções

Uma função f de A para B associa exatamente um elemento de B a cada elemento de seu domínio A:

~~~text
f : A → B
~~~

Para todo a ∈ A existe exatamente um f(a) ∈ B.

O codomínio B pode conter valores nunca produzidos.

Uma função difere de uma relação geral porque cada entrada do domínio possui uma única saída.

## Funções totais e parciais

Uma função total é definida para todo elemento do domínio declarado.

Uma função parcial é definida apenas para algumas entradas.

Muitas interfaces C são naturalmente modeladas como funções parciais, mesmo quando a implementação expressa falha por sentinel ou código de erro.

O reg_index atual do ChrisASM mapeia nomes de registradores reconhecidos para índices de 0 a 15. Para strings não reconhecidas retorna -1.

Matematicamente, o mapeamento de sucesso é uma função parcial:

~~~text
nomes reconhecidos ⇀ {0,...,15}
~~~

O wrapper em C estende o resultado com uma representação de falha.

Essa distinção deixa explícito que strings arbitrárias não fazem parte do domínio de sucesso.

## Predicados como funções

Um predicado sobre conjunto A é uma função:

~~~text
P : A → {false,true}
~~~

point_in_clip é um exemplo concreto.

Sua entrada inclui um ponto e parâmetros de um retângulo. O resultado Boolean classifica se o ponto pertence ao retângulo segundo a convenção de fronteira implementada.

A implementação revisada exige:

~~~text
clip_w > 0
clip_h > 0
x >= clip_x
y >= clip_y
x < clip_x + clip_w
y < clip_y + clip_h
~~~

Esse é um predicado de membership em um retângulo alinhado aos eixos e semiaberto.

## chris_cc_true como função finita

chris_cc_true mascara cc com 15.

Logo a seleção da condição depende apenas de:

~~~text
cc mod 16
~~~

nos quatro bits baixos.

Para um word de flags fixo, a função mapeia uma entre dezesseis classes de condição para valor Boolean.

A implementação extrai CF, PF, ZF, SF e OF e avalia a condição selecionada.

É uma função finita concreta sobre atributos do estado da máquina.

## Funções injetivas

Uma função é injetiva quando entradas distintas nunca produzem a mesma saída:

~~~text
f(a1) = f(a2) implica a1 = a2
~~~

Um mapeamento injetivo preserva distinção.

O mapeamento de índice de array para slot de armazenamento deve ser injetivo dentro do array: índices válidos diferentes identificam elementos distintos.

Uma hash function, ao contrário, normalmente não é injetiva quando o domínio é maior que o espaço de saída; colisões são inevitáveis.

## Funções sobrejetivas

Uma função f : A → B é sobrejetiva quando todo elemento de B é produzido por pelo menos uma entrada.

Sobrejetividade depende do codomínio declarado.

Uma função pode ser sobrejetiva sobre sua imagem e não ser sobrejetiva sobre um codomínio maior.

Isso é relevante quando um enum reserva valores que nenhum caminho atual produz.

## Bijeções

Uma função é bijetiva quando é injetiva e sobrejetiva.

Uma bijeção possui inversa bem definida.

Codificações binárias finitas frequentemente buscam bijeções entre bit patterns válidos e valores semânticos.

Para inteiros unsigned de n bits:

~~~text
{padrões de n bits}
↔
{0,...,2^n-1}
~~~

é uma bijeção.

A interpretação signed em complemento de dois é outra bijeção dos mesmos padrões para uma faixa inteira diferente.

## Composição de funções

Se:

~~~text
f : A → B
g : B → C
~~~

então:

~~~text
g ∘ f : A → C
~~~

é definida por:

~~~text
(g ∘ f)(a) = g(f(a))
~~~

Pipelines de sistemas são composições.

Por exemplo:

~~~text
token de source
  ↓ parse
valor numérico
  ↓ encode
sequência de bytes
~~~

Composição correta exige que o contrato de saída do primeiro estágio satisfaça o contrato de entrada do segundo.

Um sentinel de erro não é automaticamente membro válido do domínio do próximo estágio.

## Inversas

Uma função bijetiva f possui inversa f^-1 tal que:

~~~text
f^-1(f(a)) = a
~~~

Pares encode/decode normalmente buscam comportamento inverso sobre o subconjunto válido de representações.

Serialização pode não ser globalmente bijetiva quando múltiplas sequências de bytes são aceitas como equivalentes ou existem encodings reservados.

Portanto, afirmar que “decode desfaz encode” exige especificar domínio válido e regras de normalização.

## Imagem e pré-imagem

Para S ⊆ A, a imagem é:

~~~text
f(S) = {f(x) | x ∈ S}
~~~

Para T ⊆ B, a pré-imagem é:

~~~text
f^-1(T) = {x ∈ A | f(x) ∈ T}
~~~

Pré-imagens são úteis em validação.

Uma permission check pode ser entendida como seleção da pré-imagem de estados permitidos sob uma função de classificação.

Não é necessária uma função inversa real.

## Cardinalidade e princípio da casa dos pombos

Se mais de n objetos são colocados em n caixas, pelo menos uma caixa contém mais de um objeto.

Esse resultado elementar explica colisões inevitáveis.

Se uma tabela possui 256 slots distintos, mais de 256 objetos simultaneamente distintos não podem ocupar slots exclusivos sem mudar a representação ou rejeitar uma inserção.

ChrisO define CHRISO_SYM_MAX como 256 e CHRISO_REL_MAX como 512.

O add_sym atual testa nsym contra CHRISO_SYM_MAX antes de criar novo símbolo. O limite é capacidade da implementação, não uma afirmação de que o universo matemático de nomes de símbolos contém apenas 256 elementos.

## Espaços de estado finitos

Um estado representado por componentes finitos independentes pertence a um produto cartesiano.

Considere um estado didático com:

- 4 valores de operação;
- 2 níveis de privilégio;
- 8 seletores de registrador.

A contagem irrestrita é:

~~~text
4·2·8 = 64
~~~

Estado real de máquina é muito maior porque registradores contêm bit vectors largos.

Finito não significa pequeno.

Raciocínio explícito sobre state space ainda é útil porque validação normalmente restringe um produto grande a um subconjunto legal menor.

## Conjuntos versus sequências e arrays

Um array C é ordenado e pode conter valores duplicados.

Um conjunto matemático é não ordenado e possui membros únicos.

Assim:

~~~text
[3,3,5]
~~~

como array possui tamanho 3, enquanto o conjunto de seus valores é:

~~~text
{3,5}
~~~

com cardinalidade 2.

Confundir essas abstrações causa erros em detecção de duplicidade, capacidade e testes de igualdade.

## Relações versus pointers

Um pointer pode representar uma relação, mas os conceitos são distintos.

O next pointer de uma linked list representa uma aresta entre dois nodes.

Um índice de array pode representar a mesma relação.

O sym_index de ChrisoRel representa uma relação sem armazenar host pointer.

A relação matemática sobrevive a mudanças de representação.

Essa separação é fundamental em formatos persistentes, emuladores e estruturas entre address spaces.

## Tratamento de erros como restrição de domínio

Validação frequentemente converte um universo grande de entradas brutas em um domínio aceito menor.

Conceitualmente:

~~~text
entradas brutas
   ↓ validator
domínio válido ∪ erro
~~~

Uma implementação segura deve rejeitar valores fora das hipóteses exigidas pelas funções seguintes.

add_sym rejeita inserção quando nsym alcança CHRISO_SYM_MAX.

reg_index rejeita nomes fora do conjunto reconhecido retornando -1.

Essas verificações preservam fronteiras de domínio.

## Ownership de memória e concorrência

Conjuntos, relações e funções são objetos matemáticos e não possuem memória.

Suas representações em software possuem.

Uma relação armazenada em array pertence ao subsistema que controla esse array. Modificação concorrente exige sincronização apropriada para a representação.

Duas threads podem raciocinar sobre o mesmo conjunto abstrato e ainda assim disputar uma tabela concreta sem sincronização.

Determinismo matemático não fornece atomicidade de memória.

## Fronteira de segurança

Muitos bugs de segurança podem ser descritos como erros de domínio:

- usar índice fora do conjunto válido;
- tratar mapeamento parcial como total;
- aceitar aresta de relação para objeto fora do conjunto autorizado;
- compor interfaces com domínios incompatíveis;
- assumir unicidade onde a representação permite colisão;
- deixar de validar que uma referência pertence ao conjunto de objetos ativos.

Domínios explícitos tornam esses erros visíveis antes de detalhes de implementação obscurecê-los.

## Considerações de desempenho

Notação de conjuntos e relações não determina representação.

O mesmo conjunto abstrato pode ser implementado como:

- bitset;
- array ordenado;
- hash table;
- tree;
- estrutura encadeada.

Complexidade assintótica e localidade de cache variam.

Da mesma forma, uma relação pode ser armazenada como adjacency matrix, listas de adjacência, edge array ou predicado implícito.

A escolha de representação pertence aos capítulos de estruturas de dados e algoritmos.

Este capítulo fornece o contrato semântico que essas representações devem preservar.

## Evidência de validação

O checker determinístico deste capítulo valida:

- união, interseção e diferença em exemplos finitos;
- cardinalidade 2^n do conjunto das partes;
- cardinalidade de produto cartesiano;
- predicados de reflexividade, simetria e transitividade;
- uma relação de equivalência;
- inclusão como ordem parcial;
- exemplos injetivos, sobrejetivos e bijetivos;
- composição de funções;
- cardinalidade do domínio de índices de registradores;
- âncoras atuais do ChrisOS para gpr[16], CHRISO_SEC_MAX, CHRISO_SYM_MAX, ChrisoRel.sym_index, reg_index e point_in_clip.

O checker testa os exemplos documentados e a fronteira de source. Ele não é um theorem prover para código arbitrário do ChrisOS.

## Limitações atuais

Este capítulo não cobre integralmente:

- algoritmos de grafos;
- cálculos formais de lógica;
- combinatória além de contagem básica;
- probabilidade;
- estruturas algébricas como grupos e anéis;
- category theory;
- model checking;
- linguagens de formal verification.

Esses assuntos são introduzidos apenas quando material posterior de sistemas exigir.

## Fronteira do roadmap

A transição curricular é:

~~~text
lógica booleana e numérica finita
    ↓
conjuntos, produtos, relações e funções
    ↓
provas, invariantes e indução
    ↓
representação e algoritmos
~~~

O próximo capítulo usa os domínios definidos aqui para formular proposições sobre estado de programa e demonstrar que operações preservam propriedades necessárias.

## Proveniência da revisão

As afirmações ligadas à implementação foram conciliadas contra ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

Fontes revisadas:

- chrisvm/chris_arch.h;
- compiler/chrisld/chriso.h;
- compiler/chrisasm/chrisasm.c;
- chrisvm/cpu/emulator/flags.c;
- kernel/gfx/graphics.c.

Símbolos revisados:

- ChrisArchitectureState;
- ChrisoImage;
- ChrisoRel;
- reg_index;
- add_sym;
- chris_cc_true;
- point_in_clip.

As definições matemáticas são independentes da implementação. Os exemplos do ChrisOS são usados apenas quando o source revisado fornece domínio finito, relação ou mapeamento concreto.
