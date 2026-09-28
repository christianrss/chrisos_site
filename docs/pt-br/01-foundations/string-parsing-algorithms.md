---
id: string-parsing-algorithms
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: 92fb561574bd929522ea005b9fd433138bea3236
sources:
  - kernel/metal/string.c
  - LIB/STRING.CC
  - kernel/gfx/shader/sh_lex.c
  - kernel/gfx/shader/sh_parse.c
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_pub.h
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.c
  - tools/test_shader.c
symbols:
  - strstr
  - sh_lex
  - push_tok
  - sync_stmt
  - parse_primary
  - parse_unary
  - parse_bin
  - parse_expr
  - parse_binary
  - parse_ident
  - parse_u64
depends_on:
  - data-representation-layout
  - algorithmic-complexity
  - recursion-recurrences-amortization
  - sorting-searching
related:
  - systems-algorithms
  - compiler-pipeline
  - lexical-analysis
  - parsing
  - shaders-csir
---

# Algoritmos de strings e parsing

<div class="abstract">
Strings, fluxos de tokens e árvores sintáticas são representações diferentes do mesmo problema fundamental: interpretar símbolos ordenados segundo regras explícitas. Este capítulo desenvolve busca em strings de bytes, funções de prefixo, hashes deslizantes, análise léxica, reconhecimento por estados finitos, gramáticas livres de contexto, descida recursiva, precedence climbing, associatividade e recuperação de erros. Em seguida, essas ideias são reconciliadas com o código atual do ChrisOS. As bibliotecas de strings do kernel e do ChrisC implementam varredura direta de substring, e não KMP ou Boyer-Moore; o frontend de shaders utiliza um lexer linear e limitado seguido de parsing por descida recursiva e precedence climbing; o KCC contém um parser separado de expressões baseado em precedência com geração de curto-circuito; e o ChrisASM interpreta sua gramática textual compacta diretamente por auxiliares de varredura de ponteiros. A distinção entre teoria geral e implementação comprovada pelo código é mantida em todo o capítulo.
</div>

## Strings são representações, não texto abstrato por padrão

Um algoritmo de strings opera sobre uma sequência

~~~text
S = s[0], s[1], ..., s[n-1]
~~~

cujos elementos pertencem a um alfabeto. O alfabeto pode ser formado por bytes, code points Unicode, tokens ou outro conjunto discreto de símbolos. Afirmações de complexidade somente são precisas quando a representação é conhecida.

As rotinas de baixo nível do ChrisOS analisadas neste capítulo trabalham com strings de bytes terminadas em zero. Elas não executam normalização Unicode, segmentação de grafemas ou ordenação dependente de locale. Portanto, uma operação de igualdade significa igualdade da sequência de bytes representada, e não equivalência linguística.

Essa distinção é relevante para nomes de arquivos, identificadores, campos de protocolos e formatos persistentes. Cada subsistema precisa declarar a semântica de comparação que realmente exige.

## Igualdade, prefixos e busca de substring

Três contratos frequentes são diferentes.

Igualdade exata pergunta se:

~~~text
|A| = |B|
e
A[i] = B[i] para todo i válido
~~~

Comparação de prefixo determina a ordem das sequências a partir do início. Busca de substring pergunta se um padrão P de comprimento m aparece em alguma posição de um texto T de comprimento n:

~~~text
T[i + j] = P[j] para todo j em [0, m)
~~~

para pelo menos um candidato i.

O algoritmo direto tenta cada posição inicial e compara os símbolos do padrão até ocorrer divergência ou correspondência completa.

~~~text
para i = 0 .. n-m:
    j = 0
    enquanto j < m e T[i+j] == P[j]:
        j++
    se j == m:
        retornar i
retornar não_encontrado
~~~

O pior caso é O(nm), com O(1) de estado auxiliar.

Textos e padrões com prefixos repetidos podem aproximar esse limite porque partes do padrão são comparadas novamente em posições candidatas adjacentes.

## strstr atual do kernel

O <code>kernel/metal/string.c::strstr</code> atual segue o algoritmo direto.

Primeiro trata o padrão vazio, calcula o comprimento do padrão e então avança o haystack um byte por vez. Em cada posição candidata, compara bytes sucessivos até encontrar uma divergência ou atingir todo o comprimento do padrão.

A forma essencial do fluxo é:

~~~text
enquanto haystack não chegou ao NUL:
    i = 0
    enquanto i < comprimento_padrão e haystack[i] == padrão[i]:
        i++
    se i == comprimento_padrão:
        retornar haystack atual
    haystack++
~~~

O estado auxiliar é constante. Se o texto restante contiver muitos prefixos do padrão, os mesmos bytes podem participar de comparações repetidas.

Nenhuma tabela de prefixos, tabela de bad-character, autômato de sufixos ou rolling hash é construída nessa rotina. O código comprova matching direto, não KMP, Boyer-Moore ou Rabin-Karp.

## strstr atual da biblioteca ChrisC

<code>LIB/STRING.CC::strstr</code> implementa a mesma estratégia assintótica com decomposição diferente.

A função calcula o comprimento do needle, percorre o offset candidato <code>i</code> e chama <code>strncmp(h + i, n, ln)</code> em cada candidato.

Conceitualmente:

~~~text
i = 0
enquanto h[i] != NUL:
    se prefixo_igual(h+i, needle, comprimento_needle):
        retornar h+i
    i++
~~~

A comparação aninhada de prefixo produz o mesmo limite O(nm) no pior caso. Separar a comparação em uma função auxiliar não altera a classe algorítmica.

## Função de prefixo e KMP

Knuth-Morris-Pratt evita reexaminar caracteres do texto após uma divergência por meio de uma estrutura pré-computada do padrão.

Para cada posição do padrão, a função de prefixo registra o comprimento do maior prefixo próprio que também é sufixo do prefixo considerado. Quando ocorre mismatch, a transição de falha indica qual parte da correspondência anterior ainda pode ser aproveitada.

Para padrão de comprimento m:

~~~text
pré-processamento = O(m)
busca             = O(n)
total             = O(n + m)
memória auxiliar  = O(m)
~~~

O invariante central é que, após processar o texto até uma posição, o estado representa o maior prefixo do padrão que também é sufixo do texto já consumido.

KMP é apropriado quando o limite linear de pior caso é importante. Para strings pequenas ou caminhos raros, o custo da tabela e a maior complexidade de implementação podem não se justificar.

As rotinas <code>strstr</code> analisadas no ChrisOS não implementam KMP atualmente. O algoritmo é apresentado como fundamento e alternativa de projeto.

## Boyer-Moore e Horspool

Boyer-Moore compara a partir do fim do padrão e utiliza informação da divergência para saltar posições candidatas. A versão completa combina regras de bad-character e good-suffix. Horspool preserva uma tabela de deslocamento mais simples.

Esses métodos podem pular grandes trechos de textos comuns e apresentar excelente desempenho prático para padrões maiores e alfabetos razoavelmente grandes. As garantias de pior caso dependem da variante exata.

Eles também exigem pré-processamento e tabelas que podem custar mais que a busca direta em strings muito pequenas. O código atual de <code>strstr</code> não contém essas estruturas.

## Rabin-Karp e rolling hash

Rabin-Karp associa uma janela a um hash que pode ser atualizado quando a janela avança um símbolo, sem recalcular todos os elementos.

Uma igualdade de hash apenas produz um candidato. A menos que a aritmética usada seja comprovadamente livre de colisões no domínio em questão, os bytes precisam ser comparados antes de aceitar igualdade.

Esse método pode ser útil para buscas repetidas ou múltiplos padrões, mas introduz raciocínio sobre colisões, aritmética e possivelmente módulo. Igualdade de hash não deve ser confundida com igualdade semântica.

## Tokenização altera o alfabeto

Um compilador normalmente não aplica todas as produções da gramática diretamente sobre os caracteres brutos. A análise léxica transforma caracteres em tokens:

~~~text
bytes do fonte
    |
    v
lexer
    |
    v
IDENT  PLUS  INT  SEMI  ...
~~~

Um token pode carregar:

- tipo;
- offset no fonte;
- comprimento;
- linha e coluna;
- valor numérico decodificado;
- spelling referenciado ou internado.

O parser passa a consumir tipos de tokens em vez de redescobrir classes de caracteres em cada produção.

Essa separação centraliza regras de identificadores, literais, comentários, whitespace e operadores.

## Varredura léxica determinística

Um lexer convencional pode ser interpretado como uma máquina de estados finitos determinística. Para cada símbolo de entrada, o estado léxico atual e o símbolo definem o próximo estado.

Para fonte com n bytes, um lexer que avança monotonicamente e realiza trabalho limitado por byte é O(n). Alguns tokens exigem lookahead local, mas o scanner total permanece linear se não houver retrocesso ilimitado.

A regra de maximal munch normalmente escolhe o token válido mais longo iniciado na posição atual. Por isso, quando <code>>=</code> e <code>></code> compartilham o primeiro byte, o lexer precisa reconhecer corretamente a forma mais longa.

A correção léxica possui ao menos três componentes:

1. cada entrada aceita recebe a tokenização prevista;
2. entrada inválida gera diagnóstico em vez de token acidental;
3. posições do fonte permanecem precisas para diagnósticos posteriores.

## Lexer de shaders do ChrisOS

O frontend atual de shaders contém um lexer limitado em <code>kernel/gfx/shader/sh_lex.c</code>.

<code>sh_lex</code> percorre o fonte com um offset inteiro e acompanha linha e coluna. Ele reconhece whitespace, quebras de linha, diretivas suportadas, identificadores e palavras-chave, formas numéricas, pontuação e operadores com mais de um caractere.

O reconhecimento de palavras-chave usa uma tabela fixa. Entre os nomes presentes no código estão:

~~~text
in
out
uniform
const
layout
void
bool
int
float
vec2
vec3
vec4
mat3
mat4
sampler2D
if
else
for
return
discard
true
false
~~~

Caracteres desconhecidos produzem <code>TK_BAD</code>, registram o diagnóstico "invalid token" e o scanner continua. Essa estratégia preserva a possibilidade de diagnósticos úteis sem tratar o estado inválido como token normal.

Ao final, o lexer acrescenta um token EOF explícito.

## Recursos léxicos limitados

O frontend de shaders é deliberadamente limitado.

Os headers revisados estabelecem:

| Recurso | Limite |
|---|---:|
| fonte do shader | 4096 bytes |
| vetor de tokens | 768 tokens |
| AST | 512 nós |
| nesting do parser | 32 níveis |

A verificação do comprimento do fonte ocorre antes da varredura léxica. <code>push_tok</code> recusa novo token quando <code>SH_TOK_MAX</code> seria ultrapassado.

Esses limites são contratos de recursos. Eles limitam consumo de memória e reduzem exposição a denial-of-service em um parser residente no kernel.

Arrays fixos também alteram o comportamento de falha: esgotamento precisa produzir erro explícito em vez de sobrescrever estado adjacente.

## De tokens para gramática

Lexing responde "quais símbolos existem?". Parsing responde "como esses símbolos se relacionam estruturalmente?".

Uma gramática livre de contexto pode conter produções como:

~~~text
expr    -> expr + term | term
term    -> term * unary | unary
unary   -> - unary | primary
primary -> IDENT | NUMBER | ( expr )
~~~

Essa forma é left-recursive. Uma implementação ingênua por descida recursiva não pode implementar diretamente <code>expr -> expr + term</code>, pois chamaria a si mesma antes de consumir entrada.

Parsers escritos manualmente refatoram a gramática ou usam um algoritmo específico de precedência.

## Descida recursiva

Descida recursiva representa a estrutura da gramática por procedimentos.

Funções típicas incluem:

~~~text
parse_primary
parse_unary
parse_statement
parse_block
parse_function
~~~

O invariante central é progresso: parsing bem-sucedido consome os tokens do construct aceito; em falha, a rotina precisa deixar uma posição de recuperação documentada ou avançar até uma fronteira de sincronização.

Recursão sem limite sobre nesting controlado pela entrada pode esgotar a stack. Em software de baixo nível, limitar nesting faz parte da correção e robustez do parser.

## Precedência e associatividade

O parser de expressões precisa representar que:

~~~text
a + b * c
~~~

significa:

~~~text
a + (b * c)
~~~

e não:

~~~text
(a + b) * c
~~~

Operadores recebem níveis de precedência. Associatividade determina o agrupamento entre operadores do mesmo nível.

Para um operador binário left-associative:

~~~text
a - b - c
~~~

significa:

~~~text
(a - b) - c
~~~

Precedence climbing recebe uma precedência mínima e analisa recursivamente o operando da direita com uma precedência mínima mais estrita para operadores left-associative.

## Precedence climbing dos shaders

O parser de shaders em <code>kernel/gfx/shader/sh_parse.c</code> implementa esse padrão em <code>parse_bin</code>.

A tabela ordena:

- OR lógico;
- AND lógico;
- igualdade;
- comparações relacionais;
- soma e subtração;
- multiplicação, divisão e resto.

A função primeiro analisa uma expressão unary. Em seguida observa o próximo operador binário. Se sua precedência for menor que o mínimo atual, o loop termina. Caso contrário, consome o operador e chama:

~~~text
parse_bin(right, precedência + 1)
~~~

antes de construir o nó binário da AST.

A regra <code>+1</code> torna os operadores atuais left-associative. Operadores de precedência maior são agrupados dentro do operando direito recursivo antes que o nó de menor precedência seja concluído.

<code>parse_expr</code> inicia o processo com precedência mínima 1.

Isso é precedence climbing. Não deve ser descrito como um parser Pratt genérico, pois o código atual não contém tabelas de dispatch no estilo null-denotation/left-denotation.

## Estrutura primary, postfix e unary

O mesmo parser separa as camadas.

<code>parse_primary</code> processa literais, identificadores, chamadas, construtores e expressões entre parênteses.

Uma etapa postfix trata operações que ligam fortemente após um primary. <code>parse_unary</code> trata operadores prefixos como mais, menos, NOT lógico e incremento/decremento antes de delegar ao primary.

O resultado é uma hierarquia efetiva:

~~~text
primary / postfix
        |
      unary
        |
 níveis de precedência binária
        |
     expression
~~~

A separação evita concentrar todas as regras de binding em uma única máquina condicional difícil de provar.

## Alocação da AST como invariante

O parser não cria nós arbitrários no heap durante a análise. <code>node_new</code> usa o vetor limitado de AST dentro do contexto de compilação.

Antes de criar um nó, verifica <code>SH_AST_MAX</code>. Cada nó novo recebe links de filhos e metadata inicializados.

Um invariante resultante é:

~~~text
0 <= nast <= SH_AST_MAX
~~~

e nenhum índice válido da AST pode apontar para além do prefixo inicializado.

Quando a capacidade termina, o parser registra erro em vez de corromper memória.

## Controle de nesting

<code>enter</code> verifica se a profundidade chegou a <code>SH_NEST_MAX</code>. O limite atual é 32.

Isso limita caminhos recursivos por expressões e construções aninhadas. O consumo exato da stack nativa por nível depende do compilador, mas a profundidade lógica do parser é explicitamente limitada.

Validar a sintaxe sem limitar nesting não é suficiente quando uma entrada não confiável pode controlar a profundidade.

## Recuperação de erros e sincronização

Abortar no primeiro erro é simples, mas limita diagnósticos. Continuar sem regra de recuperação é pior porque um token inválido pode produzir cascatas arbitrárias.

O parser de shaders utiliza <code>sync_stmt</code> como rotina de sincronização. Ela avança até uma fronteira plausível de statement, acompanhando profundidade de chaves.

As fronteiras incluem:

- ponto e vírgula na profundidade atual;
- chave de fechamento pertencente ao contexto externo;
- EOF.

Esse mecanismo é uma forma de panic-mode recovery.

O objetivo não é tornar código inválido em código válido, mas restaurar um estado do parser em que os próximos diagnósticos ainda façam sentido.

## Parser de expressões do KCC

O KCC possui uma implementação distinta em <code>compiler/kcc/kcc.c</code>.

<code>parse_expr</code> chama <code>parse_binary(out, 0)</code>. O parser binário mantém tabelas explícitas de operadores e precedências para operadores lógicos, bitwise, igualdade, relacionais, shifts, aditivos e multiplicativos.

Primeiro analisa uma expressão unary. Depois seleciona um operador cuja precedência atende ao threshold atual e analisa recursivamente o operando direito com <code>prec_of[matched] + 1</code>.

No KCC, o parsing também está integrado à geração de código. AND e OR lógicos recebem fluxo de curto-circuito: o operando esquerdo pode determinar o resultado sem avaliar o direito.

Isso demonstra por que parsing em compiladores não pode ser documentado apenas como reconhecimento de gramática. Associatividade e estratégia de avaliação influenciam diretamente o control flow gerado.

Os parsers de shader e KCC são implementações separadas. Semelhança algorítmica não significa compartilhamento de código.

## Parsing direto no ChrisASM

O ChrisASM demonstra outra escolha válida.

Sua sintaxe é compacta o suficiente para <code>compiler/chrisasm/chrisasm.c</code> usar auxiliares que avançam ponteiros em vez de materializar primeiro um vetor geral de tokens.

<code>skip_ws</code> avança sobre whitespace. <code>parse_ident</code> copia um campo até delimitadores como vírgula, dois-pontos, ponto e vírgula, colchetes ou sinais. <code>parse_u64</code> reconhece inteiros decimais e hexadecimais.

O parser numérico verifica overflow antes de executar:

~~~text
valor = valor * base + dígito
~~~

por meio da condição equivalente:

~~~text
valor <= (UINT64_MAX - dígito) / base
~~~

Assim, wraparound não transforma um literal inválido em outro valor aceito.

Um vetor separado de tokens poderia oferecer mais estrutura, mas não é automaticamente superior para uma gramática pequena. A representação adequada depende da complexidade da linguagem, qualidade de diagnóstico, reuso e pressão por extensões.

## Propriedades de correção do parser

Um parser de sistemas precisa ser analisado por propriedades explícitas.

### Progresso

Toda iteração bem-sucedida de um loop precisa consumir entrada ou caminhar para terminação. Caso contrário, uma entrada malformada pode causar loop infinito.

### Acesso limitado

Lookahead precisa provar que o byte ou token inspecionado existe. Um token sentinela EOF simplifica parte desse raciocínio, mas não elimina requisitos de bounds.

### Determinismo

Para gramática e estado determinísticos, a mesma sequência de tokens deve produzir o mesmo resultado. Mutação global oculta pode violar essa propriedade.

### Consumo completo

Um parser de unidade completa normalmente deve recusar tokens finais inexplicados em vez de aceitar silenciosamente apenas um prefixo válido.

### Limites de recursos

Comprimento da entrada, número de tokens, número de nós e profundidade recursiva precisam ter comportamento de saturação definido.

### Localidade de diagnóstico

Erros devem preservar posição do fonte e indicar a expectativa violada sem acessar nós já inválidos.

## Modelo de complexidade

Para um lexer bem projetado sobre n bytes:

~~~text
tempo = O(n)
espaço = O(número_de_tokens)
~~~

Para descida recursiva determinística sobre t tokens, parsing frequentemente é O(t), desde que as produções não revarram repetidamente grandes prefixos.

Precedence climbing visita cada token da expressão um número limitado de vezes, resultando em O(t) para a expressão quando a tabela de operadores tem tamanho fixo.

Recuperação de erro altera o custo prático, mas uma sincronização que apenas avança permanece linear na região descartada.

Busca ingênua de substring, por outro lado, continua O(nm) no pior caso por repetir comparações entre candidatos sobrepostos.

Esses custos não devem ser condensados em uma afirmação genérica de que "parsing é linear". Representação e política de recuperação determinam o limite efetivo.

## Propriedade e lifetime

Código de strings e parsers precisa de ownership claro mesmo quando não usa alocação dinâmica.

Uma view de um source buffer é válida apenas enquanto o buffer de backing permanecer vivo e não for modificado de forma que invalide offsets.

O frontend de shaders copia o fonte para um contexto limitado e registra offsets nessa representação. Tokens e nós da AST vivem no mesmo contexto, simplificando as relações de lifetime.

Os auxiliares de ChrisASM avançam diretamente sobre a representação textual fornecida pelo chamador e copiam campos selecionados para buffers locais fixos.

Os dois projetos têm riscos de lifetime diferentes mesmo quando ambos evitam alocação geral.

## Concorrência

Um parser é naturalmente reentrant somente quando todo estado mutável pertence à invocação ou a um contexto explicitamente possuído por ela.

O modelo <code>ShComp</code> concentra tokens, AST e contadores do parser no contexto da compilação, o que permite raciocinar sobre o estado por compilação.

KCC e ChrisASM também contêm estado global mais amplo de compilador. Portanto, este capítulo não afirma que esses compiladores completos sejam reentrant ou possam compilar em paralelo de forma segura apenas porque funções individuais possuem variáveis locais.

Afirmações de concorrência exigem evidência de código sobre globals, sincronização e lifetime; teoria de parsing não é suficiente.

## Fronteiras de segurança

Parsers processam estrutura controlada pela entrada e fazem parte da superfície de ataque quando essa entrada não é confiável.

Classes relevantes de falha incluem:

- buffer overflow ao armazenar spelling de token;
- overflow inteiro na conversão de literais;
- exhaustion de recursão por nesting profundo;
- overflow da capacidade de tokens ou AST;
- comportamento quadrático ou pior sob entrada adversarial;
- aceitação de trailing input inválido;
- recovery malformado que não progride;
- use-after-free de slices referenciando o fonte;
- ambiguidade que produz interpretação dependente da implementação.

Os limites do shader e a verificação de overflow numérico do ChrisASM tratam membros específicos dessa lista.

Eles não provam ausência de todas as vulnerabilidades de parsing.

## Estratégia de validação

Validação algorítmica precisa verificar invariantes independentes e não apenas alguns happy paths.

Para busca de substring:

- padrão vazio;
- texto vazio;
- match na primeira posição;
- match na última posição;
- ausência de match;
- texto adversarial com prefixos repetidos;
- padrão maior que o texto.

Para análise léxica:

- cada operador suportado;
- prefixos ambíguos de operadores;
- whitespace e mudanças de linha;
- bytes inválidos;
- fronteiras de capacidade;
- coordenadas do fonte.

Para parsing de expressões:

- cada fronteira de precedência;
- associatividade à esquerda;
- override por parênteses;
- binding unary versus binary;
- operando malformado;
- delimitador ausente;
- limite de nesting.

Para parsing numérico:

- zero;
- maior valor válido;
- primeiro valor que causa overflow;
- dígito inválido para a base;
- prefixo sem dígitos.

O checker determinístico da documentação deste capítulo verifica, adicionalmente, modelos de busca direta/KMP e anchors no código fonte. O <code>tools/test_shader.c</code> existente fornece cobertura executável do frontend de shaders, inclusive casos rejeitados e diagnósticos.

## Fronteira da implementação atual

Na revisão ChrisOS 92fb561574bd929522ea005b9fd433138bea3236, o código inspecionado comprova:

- substring matching direto com pior caso O(nm) no <code>strstr</code> do kernel;
- comparação direta de prefixo em cada posição no <code>strstr</code> do ChrisC;
- lexer de shaders limitado com coordenadas, EOF explícito e verificação de capacidade;
- AST de shader e profundidade de nesting limitadas;
- descida recursiva para estrutura primary/unary/statements;
- precedence climbing para expressões binárias de shaders;
- sincronização de statements em estilo panic por <code>sync_stmt</code>;
- parser binário separado e baseado em precedência no KCC;
- curto-circuito de AND/OR lógico no KCC;
- auxiliares de varredura direta de ponteiro no ChrisASM;
- rejeição explícita de overflow em literais unsigned de 64 bits no ChrisASM.

O código inspecionado não estabelece:

- KMP nas bibliotecas de string do runtime;
- Boyer-Moore/Horspool nessas bibliotecas;
- Rabin-Karp para busca geral de substring;
- suffix tree, suffix array ou suffix automaton para texto geral;
- parser generator controlando os parsers de shader ou ChrisASM;
- parser GLSL completo e ilimitado;
- compilação paralela segura de todos os frontends.

Essas distinções evitam atribuir ao ChrisOS algoritmos de livro que não aparecem na implementação atual.

## Proveniência da revisão

As afirmações de implementação deste capítulo foram conciliadas com ChrisOS <code>main</code> na revisão 92fb561574bd929522ea005b9fd433138bea3236.

Os arquivos primários inspecionados são:

- <code>kernel/metal/string.c</code>;
- <code>LIB/STRING.CC</code>;
- <code>kernel/gfx/shader/sh_lex.c</code>;
- <code>kernel/gfx/shader/sh_parse.c</code>;
- <code>kernel/gfx/shader/sh_int.h</code>;
- <code>kernel/gfx/shader/sh_pub.h</code>;
- <code>compiler/kcc/kcc.c</code>;
- <code>compiler/chrisasm/chrisasm.c</code>;
- <code>tools/test_shader.c</code>.

O capítulo separa fundamentos algorítmicos gerais de mecanismos comprovados pelo source e trata limites de recursos, recuperação e comportamento de falha como partes do contrato do parser.
