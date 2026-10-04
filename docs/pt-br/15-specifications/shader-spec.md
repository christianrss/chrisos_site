---
id: shader-spec
lang: pt-br
type: specification
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/shader/sh_pub.h
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_lex.c
  - kernel/gfx/shader/sh_parse.c
  - kernel/gfx/shader/sh_sem.c
  - kernel/gfx/shader/sh_ir.c
  - kernel/gfx/shader/sh_api.c
  - kernel/gfx/shader/sh_src.h
  - kernel/gfx/gfx3d.c
  - kernel/gfx/gfx3d_dev.h
  - tools/cshader.c
  - tools/test_shader.c
symbols:
  - sh_compile
  - sh_shader_ok
  - sh_program_create
  - sh_program_attach
  - sh_program_link
  - sh_uniform_set
  - sh_soft_vs
  - sh_soft_fs
  - sh_soft_triangle
  - sh_shader_save_csi
  - sh_shader_load_csi
  - sh_guest_compile
depends_on:
  - specifications-policy
  - shader-frontend
  - shaders-csir
  - gfx3d-api
related:
  - virtio-gpu-virgl
  - virgl-command-stream
  - software-shader
  - triangle-rasterization
---

# Especificação da linguagem de shaders e do CSIR do ChrisOS

## Status

O ChrisOS possui um pequeno compilador e runtime de shaders para sua própria pilha gráfica.

O próprio source é explícito:

> trata-se de um subconjunto GLSL do ChrisOS, não de uma implementação GLSL 3.30.

Esta especificação descreve o subconjunto, o pipeline de compilação, o modelo de link de programas, a representação intermediária, o caminho de execução em software, a saída TGSI, o formato CSIR serializado e o ownership de objetos guest implementados na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

## Escopo

O subsistema possui cinco camadas distintas:

1. source text semelhante a GLSL;
2. lexer/parser/semantic frontend;
3. IR de shader do ChrisOS;
4. execução do IR em software ou geração de TGSI;
5. integração do program com os backends software/VirGL.

Um arquivo iniciado com `#version 330` **não** comprova suporte completo a GLSL 3.30.

A directive é apenas sintaxe aceita dentro de uma linguagem propositalmente restrita.

## Stages suportados

A API pública define:

    vertex   = 0
    fragment = 1
    geometry = 2
    compute  = 3

Entretanto `sh_compile()` aceita atualmente somente:

- vertex;
- fragment.

Geometry, tessellation e compute-style compilation são rejeitados.

As constants extras reservam vocabulário; não implicam implementação.

## Limite de source

O source deve satisfazer:

    0 < source_length < 4096

pois:

    SH_SRC_MAX = 4096

Uma fonte com exatamente 4096 bytes já excede o limite.

## Versão do compilador

A constant pública é:

    SH_COMPILER_VERSION = 1

Ela descreve a família de implementação do compiler ChrisOS.

Não representa uma versão GLSL.

## Directive de version

O lexer reconhece no início de linha:

    #version N

com:

    110 <= N <= 330

O número é registrado no compiler state.

Outras preprocessor directives são rejeitadas.

`#extension`, por exemplo, não é suportado.

Aceitar um número de versão não habilita o conjunto completo de features daquela especificação GLSL.

## Comentários

São aceitos:

- `//` line comments;
- `/* ... */` block comments.

Block comment não terminado gera compile error.

## Limite de identifiers

Names internos usam:

    SH_NAME_MAX = 40

Identifier que alcance esse limite é rejeitado.

As estruturas de reflection também usam fields fixos de 40 bytes.

## Limite de tokens

O compiler possui:

    SH_TOK_MAX = 768

tokens.

Ultrapassar esse limite é compile error.

## AST e nesting

O frontend usa:

    SH_AST_MAX  = 512
    SH_NEST_MAX = 32

Esgotamento de AST nodes ou nesting excessivo gera erro.

A scope table possui:

    SH_SCOPE_MAX = 48

entries.

## Symbols e temporaries

Limites:

    SH_SYM_MAX  = 64
    SH_TEMP_MAX = 96

São hard bounds da implementação atual.

## Error budget

O compilador retém no máximo aproximadamente os primeiros:

    SH_ERR_MAX = 8

erros antes de os stages posteriores deixarem de prosseguir de forma útil.

Diagnostics incluem shader name, line, column, source line e caret quando possível.

## Types suportados

O sistema de tipos cobre:

- `void`;
- `bool`;
- `int`;
- `float`;
- `vec2`, `vec3`, `vec4`;
- `ivec2`, `ivec3`, `ivec4`;
- `mat3`, `mat4`;
- `sampler2D`.

Não fazem parte do subset atual double precision, unsigned vectors, image types, SSBO types ou user-defined structs.

## Qualifiers reconhecidos

O lexer reconhece:

    in
    out
    uniform
    const
    layout
    smooth

O compiler rejeita explicitamente diversos qualifiers GLSL, entre eles:

    attribute
    varying
    highp
    mediump
    lowp
    inout
    centroid
    flat
    noperspective
    invariant
    precise
    readonly
    writeonly
    coherent
    volatile
    restrict
    shared
    patch
    sample

Portabilidade deve ser avaliada contra esse subset, não contra GLSL desktop genérico.

## Restrição de global scope

`in`, `out` e `uniform` são válidos apenas em global scope.

Usá-los em local declarations é rejeitado.

`sampler2D` precisa ser uniform.

## Layout locations

É suportada sintaxe como:

    layout(location = 0) in vec4 position;

Vertex attributes e stage-interface variables podem receber explicit locations.

O binder atual suporta no máximo oito attribute locations e oito varying/interface slots.

Conflitos são rejeitados.

## Vertex inputs

Um vertex shader expõe no máximo:

    8 attributes

no model atual de program/reflection.

Locations podem ser explícitas ou autoassigned ao próximo slot livre.

Reflection informa name, type, location e component count.

## Varyings

Vertex outputs e fragment inputs são ligados por **name** e depois validados por type.

O linker constrói remap de fragment-input slot para vertex-output slot.

Fragment input sem matching vertex output falha.

Mesmo nome com type diferente também falha.

Há no máximo oito varying slots.

## Fragment output

Um fragment shader precisa possuir output para que o program linke.

A semantic layer atual exige:

- exatamente um fragment output;
- type `vec4`.

Multiple render targets não fazem parte do subset.

## Built-in variables

A semantic layer introduz:

    gl_Position : vec4
    gl_FragCoord : vec4

`gl_Position` só está disponível no vertex stage.

`gl_FragCoord` só está disponível no fragment stage.

Um vertex shader linkável precisa escrever `gl_Position`.

## Statements

O subset suporta:

- declarations;
- assignments;
- expression statements;
- blocks;
- `if` / `else`;
- `for` restrito;
- `return`;
- `discard` em fragment shader;
- empty statements.

Outras forms são compile errors.

## If/else

A condition precisa ser scalar-compatible.

O IR usa:

    IR_IF
    IR_ELSE
    IR_ENDIF

O verifier verifica nesting e balance.

Não existem arbitrary branch labels no shader IR.

## For é unrolled em compile time

O `for` atual é propositalmente restrito.

O initializer precisa declarar integer induction variable com initial value avaliável em compile time.

A condition deve poder ser avaliada estaticamente em função dessa variável.

O step precisa ser uma das integer-step forms suportadas.

O body é então emitido semanticamente repetidas vezes.

O guard de implementação é:

    8 iterações

Se a condition continuar verdadeira além desse limite, compilation falha com:

    loop bound exceeds the unroll limit

A loop variable não pode ser atribuída dentro do body.

Logo não existe dynamic loop geral no IR atual.

## Increment/decrement

Pre/post increment não é um recurso geral de expression.

Ele só é aceito no contexto restrito de loop step.

Uso em expression comum é rejeitado.

## Functions

User functions são suportadas com restrições.

Há no máximo quatro parameters por function.

Função non-void precisa produzir return value.

O `return` deve ser o último statement conforme as regras atuais.

## Calls são expandidos semanticamente

User-function calls são processados durante semantic analysis; não há runtime call instruction correspondente no IR final.

O compiler mantém call depth máximo de:

    8

e rejeita recursion.

Logo não existe recursive shader execution.

## Arithmetic

O frontend cobre operators como:

    + - * /
    < > <= >= == !=
    && ||
    unary - and !

Compatibilidade scalar/vector segue os helpers do compiler, não toda overload resolution de GLSL.

Algumas operações são lowered a identidades simples no IR.

## Modulo

`%` só é suportado quando ambos operands resolvem como constant integers e divisor é nonzero.

Não existe runtime integer remainder geral no shader IR.

## Indexing

Vector indexing exige constant integer index.

Dynamic indexing é rejeitado.

O index precisa estar dentro do component count.

## Swizzles

Swizzles são parsed e semanticamente verificados.

Component inválido é rejeitado.

Os tests verificam explicitamente que selecionar `z` de um `vec2` produz diagnostic.

## Matrix operations

O subset implementa:

- `mat3`;
- `mat4`;
- matrix × vector;
- matrix × matrix.

Matrix × scalar é rejeitado.

Uniform matrices usam column-oriented vec4 slots.

A test suite confirma a convenção efetiva por execução de MVP.

## Constructors

Scalar/vector/matrix constructors são aceitos nas forms reconhecidas pela semantic layer.

Component count é verificado.

Scalar pode ser broadcast nos contexts suportados.

Não se deve presumir toda conversion behavior de GLSL.

## Built-in functions

A lista implementada nesta revisão é:

    texture
    dot
    cross
    length
    normalize
    abs
    sin
    cos
    min
    max
    clamp
    mix
    pow
    reflect

Calls fora dessa lista podem resolver para user functions suportadas.

Name não resolvido gera erro.

## texture()

`texture()` requer:

- `sampler2D`;
- coordinate vector com pelo menos duas components.

É lowered para:

    IR_SAMPLE

e retorna `vec4`.

O compiler atual permite sampling em vertex ou fragment, sujeito ao backend.

## Limite de samplers

No máximo:

    4 samplers

são atribuídos pelo semantic binder.

Sampler slots são separados dos ordinary uniform vec4 slots.

## Uniform slots

Non-sampler uniforms consomem array de vec4-like constant slots.

O limite é:

    32 uniform vectors por stage

`mat4` consome quatro.

`mat3` consome três.

Scalar/vector usa um.

## Reflection de uniforms

O linked program expõe no máximo 32 uniform entries refletidas.

Same-name uniform presente nos dois stages vira um logical program uniform quando types coincidem.

Set desse uniform atualiza storage correspondente nos dois stages.

Type mismatch de same-name uniform faz o link falhar.

## Layout de uniform

O program mantém:

    128 floats para vertex
    128 floats para fragment

equivalentes a 32 vec4 slots por stage.

`mat4` usa 16 floats consecutivos.

`mat3` é expandida em três slots de quatro floats, com padding na quarta lane.

## Pipeline de compilação

Para source não cached:

    lex
      -> parse
      -> semantic analysis
      -> IR optimization
      -> IR verification
      -> TGSI emission

Cada stage principal mede cycle count.

A API fornece timings de lex, parse, semantic, IR e TGSI.

## Compiler cache

Compiler state bem-sucedido é cached por:

- hash do source;
- stage;
- bytes exatos do source.

O cache atual possui oito entries efetivas.

Depois do fill inicial, hashed slot pode ser substituído.

Esse cache guarda compiler representation, não GPU binary.

## Dumps

A API expõe dumps textuais de:

- AST;
- IR;
- TGSI;
- compiler log.

São interfaces de diagnóstico e desenvolvimento, não ABIs serializados estáveis.

## ChrisOS shader IR

As instructions atuais são:

    NOP
    CONST
    MOV
    SWZ
    SETLANE
    ADD
    SUB
    MUL
    MAX
    MIN
    ABS
    DOT
    RSQ
    RCP
    SIN
    COS
    POW
    TRUNC
    CMP
    MULMV
    MULMM
    SAMPLE
    LOAD_ATTR
    LOAD_VAR
    LOAD_UNI
    LOAD_FCOORD
    STORE_POS
    STORE_VAR
    STORE_COLOR
    IF
    ELSE
    ENDIF
    DISCARD

O IR é pequeno e estruturado exatamente em torno do subset do frontend.

## Limites de IR

    SH_IR_MAX   = 384 instructions
    SH_IMM_MAX  = 160 float immediates
    SH_TEMP_MAX = 96 temporaries

IR acima desses bounds é inválido.

## IR verifier

O verifier checa, entre outros:

- stage válido;
- opcode válido;
- temporary indexes;
- constant ranges;
- structured control flow balanceado;
- duplicate `else`;
- `STORE_POS` só em vertex;
- `STORE_COLOR` só em fragment;
- `DISCARD` só em fragment;
- sampler indexes;
- attribute indexes;
- varying indexes;
- uniform-load ranges;
- matrix dimensions.

Ele é usado tanto após frontend compilation quanto no load de CSIR serializado.

## IR optimizer

O optimizer atual executa quatro passes simples de dead-result elimination para operations puras que produzem temporaries.

Results não usados viram `IR_NOP`.

Não é um optimizer SSA geral.

Não há global value numbering, loop optimization ou register-allocation framework.

## TGSI

Shader compilado com sucesso é convertido de ChrisOS IR para TGSI text.

Buffer máximo:

    SH_TGSI_MAX = 3600

Esse TGSI é consumível pelo device path VirGL.

O compiler não gera native machine code NVIDIA/AMD/Intel.

## Program linking

Um `ShProgram` normalmente contém um vertex shader e um fragment shader.

Link exige:

- ambos compilados;
- vertex escreve `gl_Position`;
- fragment possui output válido;
- fragment inputs combinam com vertex outputs;
- varying types iguais;
- sem conflicts de uniforms;
- TGSI emitível para os dois stages.

Successful link incrementa generation.

## Relink com falha

Se o program já estava linked e um relink posterior falha, a implementation mantém o program anterior ativo e registra:

    kept previous program

Isso permite hot development sem destruir o último shader válido.

## Execução em software

O mesmo IR possui CPU path:

    sh_soft_vs()
    sh_soft_fs()
    sh_soft_triangle()

Vertex e fragment functions executam o IR diretamente.

Isso fornece reference path independente de VirGL.

## Software triangle rasterizer

`sh_soft_triangle()` combina:

- software vertex execution;
- raster setup;
- varying interpolation;
- fragment execution;
- depth buffer;
- color packing.

O helper restringe dimensions a:

    width  <= 128
    height <= 128

É principalmente facility de correctness/reference, não o full desktop renderer.

## Paridade software/VirGL

Para uma feature ser realmente portable dentro da graphics stack ChrisOS, importam dois paths:

    IR -> software executor
    IR -> TGSI -> VirGL

Compilar para TGSI não prova software parity, e vice-versa.

Os host shader tests exercitam semantics de IR e TGSI generation.

## Integração VirGL

A device API recebe:

    gfx3d_dev_shader(ctx, stage, tgsi, &handle)

A camada gfx3d opera em software, mock ou VirGL.

Quando VirGL não está disponível e não foi forced, a camada superior pode degradar para software.

O design portanto é source/IR backend-independent com execução específica abaixo.

## Shader sources embutidos

O tree contém exemplos para:

- triangle color;
- varying color;
- MVP;
- texturing;
- lighting;
- world transform/normal/texturing.

Muitos usam:

    #version 330

mas continuam escritos para o subset ChrisOS.

São regression inputs, não GLSL 330 conformance suite.

## Formato CSIR serializado

Shader compilado pode ser salvo com:

    sh_shader_save_csi()

e carregado com:

    sh_shader_load_csi()

O formato armazena IR verificado e immediates, não o GLSL source original.

## CSIR header

O record inicia com oito 32-bit words, total de 32 bytes.

Fields:

| Word | Significado |
|---:|---|
| 0 | magic = `0x52495343` |
| 1 | format version = 1 |
| 2 | stage |
| 3 | IR instruction count |
| 4 | immediate-float count |
| 5 | temporary count |
| 6 | additive checksum dos raw IR bytes |
| 7 | reserved/zero |

Em host little-endian os magic bytes são:

    C S I R

## CSIR payload

Após o header:

    raw Ir[nir]
    raw float[nimm]

são copiados diretamente.

O size deve ser exatamente:

[
32 + nir cdot sizeof(Ir) + nimm cdot sizeof(float)
]

Trailing data não é aceito.

## Portabilidade do CSIR

CSIR v1 copia diretamente:

- native `uint32_t` header words;
- native `Ir` structs;
- native C `float` arrays.

Logo é um **artefato de implementação ChrisOS**, não interchange format architecture-neutral.

O layout C little-endian atual faz parte da compatibilidade prática.

Um formato futuro portável deve serializar fields explicitamente.

## Checksum CSIR

O checksum é simple 32-bit sum de cada raw byte no IR array.

Bytes dos float immediates não entram no checksum.

É corruption detection, não integrity criptográfica.

## Load de CSIR

O loader valida:

- minimum size;
- magic;
- version 1;
- stage vertex/fragment;
- IR count <=384;
- immediate count <=160;
- temp count <=96;
- exact size;
- raw-IR checksum;
- IR verifier.

Depois regenera TGSI.

Os tests corrompem deliberadamente a image e exigem rejeição.

## Guest shader objects

A guest API mantém bounded tables:

    16 guest shaders
    8 guest programs

Cada handle possui owner.

Operações de outro owner são rejeitadas.

Drop de owner libera todos os shader/program objects associados.

Esse boundary importa quando compilation é exposta a CLVM/user apps.

## Resource lifetime

Shaders e programs são heap-backed.

A implementation mantém live-object counter.

Os tests compile/free repetidamente e confirmam retorno ao count original.

Isso fornece evidência direta contra lifecycle leaks simples.

## Segurança e robustez

Shader source é tratado com bounds e verification.

Defesas incluem:

- source/token/AST/symbol/IR/temp limits;
- bounded diagnostics;
- bounded function expansion;
- static loop-unroll limit;
- stage-specific verifier;
- exact CSIR size check;
- owner checks em guest handles.

Essas medidas reduzem attack surface, mas não tornam o compiler formalmente verificado.

## Semânticas que não são GLSL completo

Diferenças materiais incluem:

- apenas vertex/fragment;
- sem full preprocessor;
- sem dynamic loops;
- recursion proibida;
- no máximo quatro function parameters;
- vector indexing apenas constante;
- integer modulo apenas constante;
- qualifiers restritos;
- um único fragment color output;
- apenas quatro samplers;
- pequenos fixed resource limits;
- fixed compiler storage;
- built-in set incompleto.

Apps precisam targetar o subset explicitamente.

## Requisitos de compatibilidade

Não devem mudar silenciosamente para assets persistidos/gerados:

- CSIR magic/version/layout;
- IR opcode meanings;
- type IDs serializados;
- numeric stage values;
- uniform/varying/attribute slot interpretation;
- matrix packing convention;
- TGSI semantic mapping quando driver objects dependem dela.

Extensões de source language podem ser aditivas, mas alterar semantics existentes pode quebrar software e VirGL.

## Próximos trabalhos

Uma revisão futura deveria considerar:

1. language profile/version explícito independente de `#version`;
2. CSIR architecture-neutral;
3. checksum/hash mais forte;
4. grammar e builtin catalogue machine-readable;
5. resource-limit query API;
6. loops/control flow mais amplos com verified IR;
7. integer semantics mais completas;
8. differential software-vs-VirGL tests;
9. fuzzing de lexer/parser/CSIR loader;
10. compatibility suite separando comportamento ChrisOS do GLSL geral.

## Resumo de conformidade

Uma implementação conforme precisa preservar:

- source <4096 bytes;
- somente vertex/fragment stages;
- type/resource limits documentados;
- restricted loop/function semantics;
- stage link por name/type;
- `gl_Position` obrigatório no vertex;
- um `vec4` fragment output;
- verified ChrisOS IR;
- meanings dos IR opcodes;
- software execution semantics;
- TGSI generation para VirGL;
- CSIR v1 serialization/load quando o formato é usado.

## Nota de revisão

Esta especificação foi reconciliada contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

A afirmação correta de compatibilidade não é "ChrisOS suporta GLSL 3.30". É: **ChrisOS implementa um subconjunto GLSL-like com limites explícitos, reduz esse source a IR próprio verificado e executa o IR em software ou via TGSI/VirGL.**
