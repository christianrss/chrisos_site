---
id: shaders-csir
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/shader/sh_pub.h
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_src.h
  - kernel/gfx/shader/sh_lex.c
  - kernel/gfx/shader/sh_parse.c
  - kernel/gfx/shader/sh_sem.c
  - kernel/gfx/shader/sh_ir.c
  - kernel/gfx/shader/sh_tgsi.c
  - kernel/gfx/shader/sh_exec.c
  - kernel/gfx/shader/sh_api.c
  - tools/test_shader.c
  - tools/test_gfx3d_abi.c
symbols:
  - sh_compile
  - sh_program_create
  - sh_program_attach
  - sh_program_link
  - sh_uniform_set
  - sh_soft_vs
  - sh_soft_fs
  - sh_soft_triangle
  - sh_shader_save_csi
  - sh_shader_load_csi
depends_on:
  - compiler-pipeline
  - software-3d
  - virtio-gpu-virgl
related:
  - shader-frontend
  - csir
  - tgsi-backend
  - software-shader
---

# Shaders programáveis e Chris Shader IR

## Escopo

O ChrisOS possui um pequeno compilador e runtime de shaders desenhado especificamente para a própria pilha gráfica.

Ele não implementa GLSL 3.30 completo. O header público declara isso explicitamente.

A arquitetura implementada é:

```text
subset GLSL do ChrisOS
        |
        v
lexer
        |
        v
parser recursive-descent / AST
        |
        v
semantic analysis + lowering
        |
        v
Chris Shader IR (CSIR)
       / \
      /   \
     v     v
TGSI text  interpretador software
     |             |
     v             v
VirGL          rendering CPU
```

A propriedade central é que a semântica da linguagem não fica acoplada diretamente ao encoder VirGL.

## Stages suportados

A API pública define valores para vertex, fragment, geometry e compute.

O compiler, porém, aceita somente:

- vertex;
- fragment.

`sh_compile` rejeita explicitamente geometry, tessellation e compute.

Os demais stage IDs indicam namespace e evolução futura, não suporte atual.

## Limites do compilador

A implementação usa estruturas de capacidade fixa.

Os principais limites são:

```text
SH_SRC_MAX   = 4096 bytes
SH_TOK_MAX   = 768 tokens
SH_AST_MAX   = 512 nodes
SH_SYM_MAX   = 64 symbols
SH_IR_MAX    = 384 instructions
SH_IMM_MAX   = 160 immediates
SH_TEMP_MAX  = 96 temporaries
SH_NEST_MAX  = 32 níveis
SH_SCOPE_MAX = 48 scopes
SH_ERR_MAX   = 8 errors
SH_TGSI_MAX  = 3600 bytes
SH_LOG_MAX   = 1536 bytes
```

Ultrapassar esses limites deve falhar de forma explícita em vez de expandir estado do compilador indefinidamente.

## Entry point de compilação

`sh_compile(stage,name,src)` aloca um `ShShader` e um `ShComp`.

O source precisa ter tamanho maior que zero e estritamente menor que 4096 bytes.

Quando não existe cache hit, as fases são medidas com `RDTSC`:

1. lexing;
2. parsing;
3. semantic analysis/lowering;
4. optimization + verification do IR;
5. TGSI emission.

Os ciclos podem ser consultados por `sh_shader_cycles`.

## Cache de compilação

Existe um cache global de oito objetos `ShComp`.

A key combina stage, versão do compilador e bytes do source em um hash 32-bit estilo FNV.

Um hit ainda compara:

- hash;
- stage;
- source length;
- source bytes.

Os oito primeiros shaders válidos ocupam slots sequenciais.

Depois, novas compilações substituem o slot `hash & 7`.

O cache guarda uma cópia completa do estado compilado.

Não existe um protocolo geral de locking; ele não deve ser considerado cache thread-safe.

## Política de preprocessor

O lexer entende apenas um subconjunto de preprocessor.

`#version` é aceito quando aparece no início de uma linha.

Versões numéricas entre 110 e 330 são aceitas.

Outras directives, como `#extension`, são rejeitadas com erro explícito.

Aceitar `#version 330` não significa compatibilidade completa com GLSL 3.30.

## Léxico

Entre os keywords reconhecidos estão:

- `in`, `out`, `uniform`, `const`, `layout`, `smooth`;
- tipos scalar/vector/matrix;
- `sampler2D`;
- `if`, `else`, `for`, `return`, `discard`;
- `true` e `false`.

Qualifiers como `attribute`, `varying`, precision qualifiers, `flat`, `noperspective`, `invariant` e vários memory qualifiers são classificados como não suportados.

O lexer preserva line/column para diagnostics.

## Diagnostics

Erros incluem:

- nome do shader;
- linha;
- coluna;
- mensagem;
- linha do source;
- caret apontando a posição.

O log possui capacidade fixa e o compiler mantém no máximo oito erros estruturados por compilação.

Isso permite diagnostics úteis mesmo em ambiente freestanding.

## Parser e AST

O parser é recursive-descent e grava os nodes num array fixo.

Kinds de AST incluem:

- declarations;
- functions;
- blocks;
- return;
- if;
- for;
- assignment;
- discard;
- literals;
- identifiers;
- unary/binary;
- calls;
- swizzles;
- indexing;
- constructors.

A profundidade de parsing é limitada a 32 níveis.

`sh_shader_ast` pode expor uma representação textual do AST.

## Sistema de tipos

Os tipos internos são:

- void;
- bool;
- int;
- float;
- vec2/vec3/vec4;
- ivec2/ivec3/ivec4;
- mat3/mat4;
- sampler2D.

Matrices usam múltiplos temporaries por coluna e seguem a semântica column-major do subsystem de shaders.

Isso explica por que matrices CPU precisam ser convertidas corretamente antes de serem usadas como uniforms.

## Symbol table

Cada symbol contém name, kind, type, location, slot, scope, temporary, metadata de function, const state e limited compile-time value.

Kinds incluem:

- stage input;
- stage output;
- uniform;
- local;
- function;
- `gl_Position`;
- `gl_FragCoord`.

A tabela suporta no máximo 64 symbols.

## Attributes e varyings

Vertex attributes e varyings possuem no máximo oito locations.

`layout(location=...)` é respeitado quando válido.

Sem location explícita, o compiler escolhe o próximo slot livre.

Conflict ou excesso gera erro.

O linker também remapeia varying slots do fragment shader para os slots efetivamente produzidos pelo vertex shader.

## Uniforms e samplers

Uniforms normais consomem vec4 slots.

Mat4 consome quatro slots.

Mat3 consome três.

O limite total é 32 vec4 slots.

Sampler2D usa namespace separado com no máximo quatro sampler slots.

Samplers não consomem o mesmo storage de uniform vectors.

## Fragment output

A revisão atual permite somente um output de fragment shader.

O tipo precisa ser vec4.

Múltiplos outputs ou tipo diferente falham na semantic analysis.

Multiple render targets não fazem parte do contrato atual.

## Builtins de stage

`gl_Position` só existe no vertex stage e precisa receber vec4.

`gl_FragCoord` só existe no fragment stage.

No link, vertex shader sem write em `gl_Position` é rejeitado.

Fragment shader sem output também é rejeitado.

## Loops

O parser reconhece `for`, mas CSIR não possui loop dinâmico.

O lowering exige:

- initializer como declaração int;
- valor inicial conhecido em compile time;
- condition suportada e avaliável;
- step reconhecível;
- loop variable não modificada dentro do body.

O body é unrolled durante a compilação.

O limite é oito iterações.

Se a condição continuar verdadeira após o limite, o compiler gera `loop bound exceeds the unroll limit`.

Isso controla o crescimento do IR.

## Funções definidas pelo usuário

Functions do usuário são expandidas durante semantic lowering.

Arguments são copiados para temporaries locais e o body é processado no call site.

Recursion é rejeitada.

A call stack interna aceita profundidade máxima de oito.

Uma função usada como value precisa produzir return.

A implementação exige que return esteja no final do body relevante.

Na prática, é uma forma de bounded inlining.

## Builtins implementados

A semantic layer reconhece, entre outros:

- `texture`;
- `dot`;
- `cross`;
- `length`;
- `normalize`;
- `abs`;
- `sin`;
- `cos`;
- `min`;
- `max`;
- `clamp`;
- `mix`;
- `pow`;
- `reflect`.

Vários builtins viram combinações de operações CSIR menores.

`normalize`, por exemplo, usa dot, reciprocal square root e multiply.

## Restrições de expressão

Indexing exige índice inteiro constante.

Operador `%` só funciona quando ambos operands são integers constants.

Increment/decrement fora do loop step é rejeitado.

Uniforms e stage inputs não são assignable.

Sampler values também não funcionam como variables normais.

Essas restrições mantêm lowering previsível.

## Estrutura do CSIR

Cada instruction contém:

- opcode;
- type;
- component count;
- destination temporary;
- até três source temporaries;
- dois campos auxiliares.

O conjunto inclui:

```text
CONST MOV SWZ SETLANE
ADD SUB MUL MIN MAX ABS
DOT RSQ RCP SIN COS POW TRUNC CMP
MULMV MULMM SAMPLE
LOAD_ATTR LOAD_VAR LOAD_UNI LOAD_FCOORD
STORE_POS STORE_VAR STORE_COLOR
IF ELSE ENDIF DISCARD
```

Não há opcode de loop runtime.

## Temporaries e immediates

Valores usam até 96 temporary registers de quatro lanes.

Matrices ocupam temporaries consecutivos.

Literals são armazenados no immediate pool de até 160 floats.

`IR_CONST` referencia regiões desse pool.

Esses limites são checados antes do shader ser aceito.

## Otimização

`sh_opt` executa quatro passes simples de dead-result elimination.

Para um conjunto de operações consideradas pure, se o destination temporary não tem uso, a instruction vira `IR_NOP`.

Stores, sampling e control flow não entram nesse descarte simplificado.

Não é um optimizer SSA geral.

## Verificação do IR

`sh_verify` checa invariantes estruturais, entre eles:

- stage válido;
- contagens dentro dos limites;
- opcode válido;
- IF/ELSE/ENDIF balanceados;
- STORE_POS apenas em vertex;
- STORE_COLOR/DISCARD apenas em fragment;
- ranges de sampler/attribute/varying;
- uniform loads válidos;
- matrix multiply válido;
- constant ranges;
- temporaries válidos.

IR inconsistente não segue para backend.

## Linker

Um `ShProgram` liga exatamente um vertex shader e um fragment shader.

Fragment inputs são comparados com vertex outputs por nome.

Types precisam ser iguais.

O linker cria o remap de varyings e coleta metadata de attributes, varyings, uniforms e samplers.

Depois regenera TGSI para os dois stages já com o remap correto no fragment shader.

## Relink e generation

Program possui generation counter.

Link bem-sucedido incrementa generation e nunca usa zero.

Se um program já estava linked e um relink posterior falha, o program anterior continua válido.

O log registra `kept previous program`.

Gfx3D usa a generation para saber quando precisa recriar shader objects VirGL.

## Storage de uniforms

Há arrays float separados para vertex e fragment stages.

Mat4 ocupa 16 floats.

Mat3 é expandido para três vec4 slots, deixando o quarto lane em zero.

Scalar/vector usa até quatro lanes.

`sh_uniform_set` atualiza todas as ocorrências de mesmo nome nos dois stages.

Esses arrays alimentam constant buffers do backend VirGL.

## Samplers

Sampler2D recebe slot separado, de zero a três.

`sh_sampler_find` procura primeiro no fragment shader e depois no vertex shader.

O compiler consegue representar mais de um sampler, embora o Gfx3D público atualmente tenha apenas um binding efetivo de texture.

## TGSI

Shader válido produz TGSI em buffer fixo de 3600 bytes.

No link, TGSI é gerado novamente para aplicar o varying remap.

O backend VirGL cria shader objects usando esse texto.

TGSI é, portanto, um backend artifact e não a linguagem pública.

## Interpreter software

`sh_exec_ir` executa o mesmo CSIR.

Ele usa um array fixo `SH_TEMP_MAX × 4` e percorre as instructions em ordem.

IF/ELSE/ENDIF usam uma stack de até 32 níveis.

DISCARD encerra o fragment e sinaliza descarte.

Arithmetic, matrix, sampling, loads e stores seguem a mesma IR usada pelo TGSI backend.

## Math aproximada no software

O interpreter contém implementações próprias e compactas de sine, cosine, exp, log e pow.

Vários inputs são limitados internamente.

Não são implementações libm e não devem ser consideradas bit-identical ao backend GPU/host.

Testes cross-backend de transcendental devem usar tolerância.

## Texture sampling no interpreter

O sampler do shader software é separado do antigo `tex_sample`.

Aqui U/V são clampados para 0..1.

O lookup é nearest.

Pixels em memória são convertidos para RGBA float normalizado.

O renderer procedural antigo usa repeat em atlas fixo; são contratos diferentes.

## Software triangle

`sh_soft_triangle` é um proof renderer programável.

Aceita superfícies no máximo 128×128.

Ele executa vertex shader nos três vertices, faz perspective divide, rasteriza bounding box, mantém depth float e interpola varyings com reciprocal W.

Depois executa fragment shader por pixel aceito.

Isso prova semantics de shader sem depender de VirGL.

## Formato CSI

`sh_shader_save_csi` serializa shader compilado.

O header possui oito words de 32 bits:

- magic `0x52495343`;
- version 1;
- stage;
- IR count;
- immediate count;
- temporary count;
- checksum;
- reservado.

Depois vêm os records de IR e os floats immediates.

## Limitação do checksum CSI

O checksum atual soma apenas bytes do IR.

O immediate pool não entra no checksum.

Logo, corrupção de uma constante pode não alterar o checksum.

O loader ainda valida length e roda `sh_verify`, mas verification estrutural não autentica o valor literal.

Um formato futuro deveria proteger o payload completo.

## Limitação de metadata CSI

O blob não salva symbol table, attribute/varying/uniform metadata nem high-water marks de interfaces.

O loader restaura stage, IR, immediates e temporary count, nomeia o shader como `csi`, verifica o IR e tenta gerar TGSI.

O teste atual usa um vertex shader constante simples.

Portanto CSI ainda deve ser tratado como persistência experimental de IR, não shader cache geral completo.

## API guest

O registry guest suporta:

```text
16 shaders
8 programs
```

Cada slot tem owner.

Outro owner não consegue acessar/drop normalmente o object.

A API oferece compile, status/log, create/attach/link, uniform lookup/update, sampler lookup e cleanup total do owner.

`sh_guest_drop_owner` libera todos os objects do owner.

## Evidência em test_shader

`tools/test_shader.c` cobre:

- shader constante;
- diagnostics;
- invalid swizzle;
- preprocessor não suportado;
- geometry shader rejeitado;
- MVP e column-major;
- texture;
- diffuse lighting;
- world shaders;
- mismatch de varying;
- IF/ELSE;
- loop unroll de quatro iterações;
- user function;
- discard;
- sine;
- software raster;
- CSI save/load e corrupção;
- 1000 ciclos compile/free;
- inputs malformados;
- guest ownership e cleanup.

Ao final, o live count precisa voltar ao baseline.

## Evidência em Gfx3D

`tools/test_gfx3d_abi.c` compara transformações CPU com execução do vertex shader para identity, translation, rotations, scale, camera, perspective e ortho.

Também verifica que relink inválido preserva o program anterior.

Isso conecta o shader subsystem ao contrato público Gfx3D.

## Limitações atuais

A linguagem é um subset deliberado.

Só vertex e fragment compile.

Não há dynamic loops nem recursion.

Existe somente um fragment color output.

Attributes/varyings são limitados a oito, samplers a quatro e uniform storage a 32 vec4 slots.

Source, AST, IR e temporary pools são fixos.

Cache e registries são globals sem thread-safety geral.

CSI não preserva interfaces completas.

TGSI é limitado a 3600 bytes.

São limites concretos da implementação atual, não compatibilidade desktop GLSL.

## Nota de revisão

Este capítulo foi reconciliado com a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. CSIR é tratado como representação semântica central compartilhada pelo backend TGSI/VirGL e pelo interpreter software, com fronteiras explícitas de compiler, linker e persistência.
