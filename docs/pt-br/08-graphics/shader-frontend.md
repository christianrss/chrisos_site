---
id: shader-frontend
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/shader/sh_pub.h
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_lex.c
  - kernel/gfx/shader/sh_parse.c
  - kernel/gfx/shader/sh_sem.c
  - kernel/gfx/shader/sh_api.c
  - tools/test_shader.c
symbols:
  - sh_lex
  - sh_parse
  - sh_sem
  - sh_err
  - sh_compile
depends_on:
  - shaders-csir
  - compiler-pipeline
related:
  - csir
  - tgsi-backend
  - software-shader
---

# Frontend do subset GLSL

## Escopo

Este capítulo isola o frontend da linguagem de shaders do ChrisOS.

O frontend começa com source text e termina depois da análise semântica, quando tipos, symbols, scopes e slots já estão definidos para o lowering em CSIR.

A sequência é:

```text
source
  -> tokens
  -> AST
  -> scopes e symbols
  -> type/interface checks
  -> shader semanticamente válido
```

O capítulo seguinte trata do CSIR. Aqui o foco é quais programas semelhantes a GLSL são aceitos, rejeitados ou normalizados antes da IR.

## Um subset deliberado

A sintaxe lembra GLSL e os shaders do tree usam `#version 330`, mas o compiler não declara compatibilidade completa com GLSL 3.30.

A linguagem foi reduzida às necessidades do ChrisOS. Features fora desse conjunto devem produzir diagnostic em vez de assumir silenciosamente a semântica de um compiler desktop.

Somente vertex e fragment stages são aceitos por `sh_compile`.

## Limites do frontend

As estruturas possuem capacidade fixa:

```text
source bytes     < 4096
tokens           <= 768
AST nodes        <= 512
symbols          <= 64
scope records    <= 48
parser nesting   <= 32
reported errors  <= 8
symbol names     < 40 caracteres
```

Esses valores são hard limits da implementação atual. O desenho mantém custo e memória previsíveis dentro do kernel.

## Tokens

Cada token guarda kind, offset no source, length, line, column, integer value e float value.

O lexer preserva, portanto, informação suficiente para diagnostics sem depender de source map externo.

O source original continua armazenado em `ShComp`, permitindo reconstruir a linha de erro.

## Literals numéricos

O lexer distingue integer e floating-point tokens e já armazena valores convertidos dentro do token.

A implementação possui conversão decimal própria, inclusive suporte interno a potência de dez usada para notação numérica.

Essa conversão ocorre no frontend; stages posteriores recebem o valor numérico, não precisam reanalisar o texto literal.

Esse desenho também facilita constant folding no semantic analyzer.

## Preprocessor

Somente um formato estreito de `#version` é implementado.

A directive precisa estar no começo de uma linha lógica.

Versões entre 110 e 330 são aceitas. Número ausente ou fora da faixa é erro.

Qualquer outra directive é rejeitada.

Não há macros, `#include`, conditional compilation ou extensions.

Aceitar `#version 330` apenas seleciona uma versão aceita pelo subset; não habilita toda a especificação GLSL 3.30.

## Comments e whitespace

Espaços, tabs, carriage returns e newlines são ignorados com atualização de line/column.

São reconhecidos:

```text
// comment
/* block comment */
```

Block comment sem fechamento produz erro explícito.

Newline também restaura o estado usado para reconhecer directive no início da linha.

## Keywords

O conjunto inclui:

- `in`, `out`, `uniform`, `const`;
- `layout`, `smooth`;
- `if`, `else`, `for`, `return`, `discard`;
- tipos scalar/vector/matrix;
- `sampler2D`;
- `true`, `false`.

Outros nomes permanecem identifiers comuns.

## Qualifiers não suportados

O lexer possui uma lista específica de palavras GLSL reconhecidas como unsupported.

Entre elas estão `attribute`, `varying`, precision qualifiers, `inout`, `centroid`, `flat`, `noperspective`, `invariant`, `precise` e qualifiers de memória como `readonly`, `coherent` e `shared`.

Isso ajuda a distinguir feature não suportada de identifier normal.

## Operadores

O parser reconhece:

```text
+ - * / %
== != < > <= >=
&& ||
!
++ --
=
```

Assignment é tratado no nível de statement, não como expression geral right-associative. Isso limita onde uma atribuição pode aparecer.

## Precedência

A precedência binária, da menor para a maior, é:

1. OR lógico;
2. AND lógico;
3. igualdade;
4. comparação relacional;
5. soma/subtração;
6. multiplicação/divisão/módulo.

Unary plus/minus, not e pre-increment/decrement têm precedência maior.

Postfix inclui swizzle, indexing e post-increment/decrement.

## Swizzles

Swizzle aceita de um a quatro components.

Os conjuntos permitidos são:

```text
xyzw
rgba
```

Misturar os conjuntos, como `xg`, é erro.

O parser compacta o swizzle em máscara de dois bits por lane.

A análise semântica ainda verifica se cada component existe no value original. Matrices não podem ser swizzled.

## Indexing

O parser aceita `value[index]`.

A semantic layer restringe o índice a integer constant conhecido em compile time e verifica range.

Indexing dinâmico de vector não existe nesta revisão. Na prática, a operação vira seleção de lane.

## Constructors

Types seguidos por parênteses viram constructor nodes.

A semantic layer aceita somente as combinações que sabe compor.

Vector constructors exigem quantidade compatível de components, com alguns casos de scalar broadcast.

Matrix constructors suportam constant scalar na diagonal ou uma column por column da matrix.

Outras formas são rejeitadas.

## Global declarations

Uma declaração global pode começar por:

```text
layout(location = N)
smooth
in | out | uniform | const
```

seguido de type e name.

O parser não implementa todas as combinações legais do GLSL desktop.

Há um qualifier principal do grupo e um `const` adicional em posição limitada.

## layout

Somente:

```glsl
layout(location = N)
```

é aceito.

O identifier precisa ser literalmente `location` e o valor precisa ser integer literal.

Não existem listas de layout, `binding`, format qualifiers ou outras keys.

A location é gravada no AST e validada posteriormente.

## smooth

`smooth` é reconhecido e armazenado nos qualifier flags.

Não existe outra política de interpolation implementada para contrastar com ele: `flat` e `noperspective` são unsupported.

Nesta revisão, aceitar `smooth` não cria múltiplos modos de interpolation no backend.

## Functions

Uma function exige return type, name, parameters tipados e body obrigatório.

Não há prototype sem body.

Parameter qualifiers não são implementados.

A semantic registration armazena no máximo quatro parameter types. Um quinto parameter gera `too many parameters`.

## main

O compiler procura uma function chamada `main`.

A assinatura obrigatória é:

```glsl
void main()
```

sem parâmetros.

Main ausente ou com outra assinatura falha. O entry point não é inferido pela posição da function.

## Statements

O parser suporta empty statement, block, declaration, expression statement, assignment, return, if/else, for e discard.

Não existem tokens/grammar implementados para `while`, `do`, `switch`, `break` ou `continue`.

O `for` forma AST normalmente, mas a semantic layer impõe regras bem mais estreitas para unrolling.

## Assignment

O parser consegue construir assignment depois de uma expression na esquerda.

Na análise semântica, porém, o target válido precisa ser um identifier simples.

Assignment direto a swizzle ou indexed lane é rejeitado com `assignment target must be a name`.

Uniforms, inputs, functions, samplers e `gl_FragCoord` também não são assignable.

`gl_Position` só aceita vec4.

## Local declarations

Declarations simples são permitidas dentro de blocks.

Qualifiers de interface em escopo local são rejeitados com `qualifiers are only valid at global scope`.

Local variable pode ter initializer. Local `const` fica immutable depois do initializer ser processado.

## Limitação dos global initializers

O parser aceita sintaticamente initializer em global declaration.

Porém, `reg_globals` registra os symbols/interfaces e não executa o lowering geral desses initializers.

O prologue inicializa uniforms, stage inputs/outputs e builtins, não ordinary global variables.

Portanto general initialized globals/global const expressions não devem ser considerados suportados sem teste específico nesta revisão.

Essa é uma diferença concreta entre aceitação sintática e aceitação semântica útil.

## Scopes

A semantic analysis mantém current scope e tabela de parent scopes.

Cada symbol guarda o scope em que foi declarado.

Lookup segue a cadeia de parents.

Dois symbols iguais no mesmo scope são rejeitados como duplicate symbol.

Nested blocks criam scopes adicionais. A capacidade é de 48 scope records.

## Builtins

Antes dos globals do usuário são registrados:

```text
gl_Position : vec4
gl_FragCoord: vec4
```

Vertex shader precisa efetivamente escrever `gl_Position`.

`gl_FragCoord` pertence ao fragment stage.

O semantic analyzer rejeita uso de builtin no stage incorreto.

## Registro dos globals

Declarations globais viram symbols antes de main ser lowered.

Qualifiers definem input, output, uniform ou ordinary symbol.

Functions recebem referências para body e parameters.

Essa fase permite resolver user functions e organizar interfaces antes da execução semântica do main.

## Attribute locations

Vertex inputs usam no máximo oito locations.

Location explícita precisa estar abaixo de 8 e ser única.

Sem `layout`, o próximo slot livre é escolhido.

O high-water mark é guardado para verification posterior.

## Varying locations

Vertex outputs e fragment inputs usam até oito varying slots.

Locations explícitas precisam estar dentro da faixa e sem conflict.

Slots ausentes são alocados automaticamente.

No link do program, fragment inputs ainda são associados aos vertex outputs por name e type.

Slot assignment local e cross-stage linking são etapas diferentes.

## Uniform allocation

Uniform comum usa vec4 slots:

- scalar/vector: 1 slot;
- mat3: 3 slots;
- mat4: 4 slots.

O limite agregado é 32 vec4 slots.

Sampler2D tem contador separado de até quatro slots.

Sampler fora de `uniform` é rejeitado.

## Fragment output

Fragment `out` precisa ser vec4.

Somente um output é permitido.

A semantic layer conta outputs e rejeita o segundo.

Multiple render targets não fazem parte do frontend atual.

## Chamadas de functions

User function é resolvida pela symbol table.

Argument count precisa coincidir.

Types precisam coincidir, com apenas a compatibilidade scalar restrita implementada.

Recursion é detectada pela function stack.

Call depth máximo é oito.

A function é expandida semanticamente no call site; não vira call instruction runtime.

## Return

Uma function não-void usada como value precisa retornar valor.

A implementação atual também exige return na posição final do body semanticamente processado.

É mais restritivo que GLSL geral e simplifica o inlining para uma IR pequena.

## If/else

Condition precisa ser scalar-like.

O lowering cria IR_IF, IR_ELSE e IR_ENDIF.

Logical AND/OR não implementam short-circuit control flow completo; o semantic layer os reduz por operações aritméticas/booleanas.

Esse detalhe diferencia o subset de uma implementação C-like completa.

## for: parser versus semantic

O parser permite initializer, condition e step opcionais.

O semantic analyzer exige um formato específico:

- initializer deve acabar sendo declaração int;
- initial value conhecido em compile time;
- condition avaliável estaticamente;
- step reconhecido;
- loop variable não pode ser alterada no body.

O loop é unrolled até oito vezes.

Parse success não significa dynamic loop support.

## discard

`discard;` possui node próprio.

Só é válido no fragment stage.

Em vertex shader gera erro.

Não existe expression-form de discard.

## Type compatibility

Assignments exigem types compatíveis, salvo conversões scalar limitadas.

Matrix/vector multiply tem rules dedicadas.

Vector comparisons são rejeitadas.

Division é lowered como reciprocal + multiply.

Divisor scalar constant zero gera diagnostic.

Modulo só funciona para integer constants.

## Separação entre parser e semantic analyzer

É importante distinguir duas classes de aceitação.

O parser verifica se a sequência de tokens possui uma forma reconhecida.

O semantic analyzer verifica se essa forma é válida para o subset e para o stage.

Por isso um construct pode formar AST e ainda ser rejeitado depois: loop dinâmico, assignment a target inadequado, qualifier em scope local, sampler fora de uniform ou builtin no stage errado.

Essa separação evita colocar toda regra de linguagem dentro da grammar.

## Error recovery

O parser tenta continuar após syntax error.

`sync_stmt` avança até semicolon ou boundary de braces.

Depois o parser retoma enquanto não alcançar o máximo de errors.

É recuperação orientada a statement, não um algoritmo completo de grammar repair.

O objetivo é produzir vários diagnostics úteis sem complexidade excessiva.

## Limite de AST e nesting

Todo novo node passa por `node_new`.

Ao atingir 512 nodes, o parser produz `shader exceeds the AST node limit`.

Chamadas recursivas de parsing usam `enter/leave`.

Quando a profundidade chega a 32, o erro é `nesting limit exceeded`.

Essas duas barreiras evitam crescimento não controlado causado por source adversarial ou excessivamente complexo.

## AST dump

`sh_shader_ast` expõe um dump textual.

Cada linha mostra node index, kind, type quando presente e pequeno fragmento do token original.

Serve para debugging e testes.

Não é formato estável de serialização.

## Evidência em testes

`tools/test_shader.c` cobre diretamente vários pontos do frontend:

- invalid swizzle;
- shader name nos diagnostics;
- unsupported preprocessor;
- geometry stage rejeitado;
- varying mismatch;
- if/else;
- loop unroll;
- user function;
- discard;
- malformed source fuzz;
- lifecycle sem leaks.

Os testes passam pelo compiler real, não por parser mocks isolados.

## Limitações atuais

O grammar omite muitas construções GLSL.

Não há macro preprocessor.

Só existe `layout(location=N)`.

Functions têm no máximo quatro parameters e não possuem prototypes.

Assignment target é somente name.

Dynamic indexing é unsupported.

Global initializers gerais não são fully lowered.

Há apenas um fragment output.

Attributes/varyings são limitados a oito.

O frontend e seus caches não possuem modelo geral de compilação concorrente.

Esses limites formam a linguagem real desta revisão.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele documenta grammar, parsing, scopes e semantic checks do subset GLSL antes do lowering em CSIR.
