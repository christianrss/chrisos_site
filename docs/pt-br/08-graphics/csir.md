---
id: csir
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_sem.c
  - kernel/gfx/shader/sh_ir.c
  - kernel/gfx/shader/sh_exec.c
  - kernel/gfx/shader/sh_tgsi.c
  - kernel/gfx/shader/sh_api.c
  - tools/test_shader.c
  - tools/test_gfx3d_abi.c
symbols:
  - sh_sem
  - sh_opt
  - sh_verify
  - sh_dump_ir_buf
  - sh_exec_ir
  - sh_shader_save_csi
  - sh_shader_load_csi
depends_on:
  - shader-frontend
related:
  - shaders-csir
  - tgsi-backend
  - software-shader
---

# Chris Shader IR

## Escopo

Chris Shader IR, ou CSIR, é a representação intermediária compacta compartilhada pelos dois caminhos de execução do compiler de shaders do ChrisOS.

Depois que o frontend semelhante a GLSL resolve scopes, types, interface slots, constructors, built-ins e control flow limitado, o lowering semântico produz CSIR.

A mesma sequência de instructions é consumida por:

- emitter textual TGSI usado por VirGL;
- interpreter software usado na execução CPU.

CSIR é, portanto, a fronteira semântica central do subsystem de shaders.

```text
semântica tipada do shader
        |
        v
      CSIR
      /  \
     /    \
    v      v
  TGSI   interpreter
 VirGL      CPU
```

A IR é pequena, linear e limitada. Não é SSA e não é uma IR geral de compilador.

## Capacidades fixas

O compiler mantém CSIR dentro de `ShComp`.

Os limites principais são:

```text
SH_IR_MAX   = 384 instructions
SH_IMM_MAX  = 160 floats immediatos
SH_TEMP_MAX = 96 temporaries
```

Não existe crescimento dinâmico acima desses valores.

Se o lowering precisar exceder um pool, a compilação produz erro e deixa de gerar shader válido.

Isso mantém memória e custo previsíveis no kernel.

## Formato da instruction

Cada instruction é:

```c
typedef struct Ir {
    uint8_t op;
    uint8_t ty;
    uint8_t ncomp;
    uint8_t pad;
    int16_t dst;
    int16_t a, b, c;
    int16_t aux;
    int16_t aux2;
} Ir;
```

Com esse layout, cada record ocupa 16 bytes.

O array máximo de 384 entries ocupa 6144 bytes dentro de `ShComp`.

Os campos `aux` e `aux2` têm significado diferente conforme o opcode.

## Não é SSA

Temporaries são índices inteiros de um register file fixo.

Não existem versions SSA, phi nodes ou ownership por basic block.

Uma instruction pode escrever em temporary já existente.

`IR_SETLANE`, por exemplo, modifica somente uma lane de um destination vector existente.

Por isso o optimizer precisa ser conservador: pressupostos comuns de SSA não se aplicam.

## Modelo de temporaries

O interpreter materializa:

```text
float tmp[96][4]
```

Cada temporary comum se comporta como register float de quatro lanes.

Scalars usam lane zero.

Vectors usam uma a quatro lanes.

Matrices usam temporaries consecutivos, uma column por temporary.

Mat3 consome três temporaries; mat4 consome quatro.

O type field mantém semântica de tipo, mas o storage físico do interpreter é baseado em float.

## Integers e booleans

Integers e booleans também usam o mesmo storage float no backend software.

`IR_TRUNC` faz conversão para integer sem criar outro register file.

Comparisons produzem 1.0 para true e 0.0 para false.

Control flow consulta lane zero contra zero.

A IR é tipada semanticamente, mas não possui register files físicos separados para int e float.

## Pool de immediates

Literals ficam em:

```text
float imm[160]
```

`IR_CONST` usa `aux` como índice inicial e `ncomp` como quantidade de values.

A execução copia os immediates para o destination e zera lanes não usadas.

Separar os constants mantém o record de instruction com tamanho fixo.

## Constant lowering

A semantic analysis já faz parte do constant folding antes de emitir IR.

Arithmetic com values conhecidos pode produzir novo temporary backed por immediate em vez de arithmetic runtime.

Loop bounds são avaliados estaticamente.

Constructors também podem materializar vectors e matrix columns constantes.

Assim, CSIR recebe programa parcialmente simplificado, não tradução literal da AST.

## Movimento de dados

A família básica contém:

```text
IR_CONST
IR_MOV
IR_SWZ
IR_SETLANE
```

`IR_MOV` copia o número indicado de components.

`IR_SWZ` usa dois bits por lane em `aux` para escolher components.

`IR_SETLANE` grava uma lane do destination a partir de uma lane do source; `aux` seleciona destino e `aux2` seleciona origem.

Essas operações sustentam constructors, assignments e montagem de vectors.

## Arithmetic

Os principais opcodes são:

```text
IR_ADD
IR_SUB
IR_MUL
IR_MAX
IR_MIN
IR_ABS
IR_DOT
IR_RSQ
IR_RCP
IR_SIN
IR_COS
IR_POW
IR_TRUNC
IR_CMP
```

Operações component-wise usam `ncomp`.

`IR_DOT` usa `aux` como largura.

`IR_CMP` usa:

```text
CMP_LT
CMP_GT
CMP_LE
CMP_GE
CMP_EQ
CMP_NE
```

O resultado software é boolean scalar representado como 0.0 ou 1.0.

## Divisão por reciprocal

Não existe opcode separado de divide.

Division é lowered para reciprocal seguido de multiply.

Isso reduz o conjunto da IR e combina bem com backends que já oferecem reciprocal.

No interpreter software, reciprocal de zero produz zero.

Divisão por scalar constant zero é rejeitada antes, durante semantic analysis.

Casos excepcionais de floating point devem ser testados explicitamente entre backends.

## Built-ins como composição de IR

Vários built-ins do source não possuem opcode próprio.

Exemplos:

- `normalize`: dot + reciprocal square root + multiply;
- `length`: dot + RSQ + reciprocal;
- `clamp`: max + min;
- `mix`: arithmetic;
- `reflect`: dot + vector arithmetic;
- `cross`: swizzles + multiplies + subtracts.

O instruction set CSIR é menor que o conjunto de built-ins da linguagem.

## Matrices

Existem dois opcodes dedicados:

```text
IR_MULMV
IR_MULMM
```

Matrices seguem semântica column-major no shader subsystem.

Em matrix-vector multiply, `aux` carrega a quantidade de columns, normalmente três ou quatro.

Matrix-matrix grava temporaries consecutivos, uma column de output por temporary.

O verifier aceita largura 3 ou 4 para `IR_MULMM`.

## Texture sampling

`IR_SAMPLE` representa sample 2D.

`aux` é o sampler slot.

O coordinate vem do temporary `a`.

O destination recebe quatro components.

A IR não codifica texture object, filtering ou addressing completos; isso pertence ao runtime/backend.

O interpreter software recebe um único CPU texture pointer e aplica seu sampling nearest/clamp.

O TGSI backend usa o sampler slot para declarations e instruction correspondente.

## Loads de interface

Os loads são:

```text
IR_LOAD_ATTR
IR_LOAD_VAR
IR_LOAD_UNI
IR_LOAD_FCOORD
```

`IR_LOAD_ATTR` usa `aux` como attribute location.

`IR_LOAD_VAR` usa `aux` como varying slot.

`IR_LOAD_UNI` usa `aux` como base vec4 constant slot e `aux2` como quantidade de vec4 slots consecutivos.

Isso permite carregar mat3 e mat4 em temporaries consecutivos.

`IR_LOAD_FCOORD` carrega fragment coordinate fornecida pelo backend.

## Stores de interface

Outputs usam:

```text
IR_STORE_POS
IR_STORE_VAR
IR_STORE_COLOR
```

`IR_STORE_POS` só é válido em vertex shader.

`IR_STORE_VAR` grava varying indicado por `aux`.

`IR_STORE_COLOR` só é válido em fragment shader.

Como a linguagem atual possui apenas um color output, não existe render-target index nessa instruction.

## Remap de varying

Fragment shader compilado inicialmente usa seus próprios varying slots.

No link, inputs do fragment são associados aos outputs do vertex por name e type.

TGSI emitter e software executor podem receber `var_remap`.

Para `IR_LOAD_VAR`, o slot remapeado substitui o slot local do fragment shader.

Isso permite compilar cada stage isoladamente e resolver a interface final somente no link.

## Control flow linear

CSIR possui apenas:

```text
IR_IF
IR_ELSE
IR_ENDIF
```

Não existem branch targets, labels, jumps, runtime loops, phi nodes ou function calls.

O `for` da linguagem é unrolled antes.

User functions são semanticamente inlined.

A IR final é uma lista linear com conditionals estruturados aninhados.

## Semântica de IF

`IR_IF` lê lane zero do temporary `a`.

Zero é false; qualquer valor diferente é true.

O interpreter mantém stacks fixas de 32 entries para skip e branch state.

Branches aninhados dentro de branch já skipped permanecem skipped até o ENDIF correto.

O verifier checa balanceamento antes da execução.

## ELSE e ENDIF

O verifier rejeita:

- ELSE sem IF;
- segundo ELSE no mesmo IF;
- ENDIF sem IF;
- nesting acima de 32;
- control-flow depth não zero no fim.

O interpreter também possui checks defensivos.

Assim, malformed flow é rejeitado estruturalmente e também possui proteção runtime.

## Discard

`IR_DISCARD` é válido somente em fragment shader.

No interpreter ele marca `discarded` quando o pointer existe e termina imediatamente a execução do shader.

No backend TGSI vira a operação de kill/discard correspondente.

Não existe discard no vertex stage.

## Emissão de instructions

O lowering usa um helper `emit`.

Quando `nir` chega a 384, o compiler registra:

```text
shader exceeds the instruction limit
```

Temporary allocation também falha acima de 96.

Immediate allocation falha acima de 160 floats.

Os limites são impostos já durante construção, antes do verifier.

## Prologue semântico

Antes de lowering de `main`, o compiler emite um prologue com base nas interfaces registradas.

Ele aloca temporaries e produz:

- uniform loads;
- vertex attribute loads;
- fragment varying loads;
- fragment-coordinate load;
- inicialização zero dos stage outputs e de `gl_Position`.

O body do main trabalha sobre esses temporaries.

Por isso a IR já contém interface traffic explícito em vez de nomes de variables.

## Desaparecimento dos nomes locais

A maior parte da identidade dos symbols não aparece na instruction stream.

Uniforms, attributes, varyings e samplers viram numeric slots.

Locals viram temporaries.

Functions são inlined.

A symbol table ainda existe em `ShComp` para dumps, linking e metadata, mas o stream não depende dos names locais.

## Otimização

`sh_opt` executa quatro passes.

Cada pass primeiro conta uses dos temporaries.

Depois, para um conjunto de instructions puras, se o destination possui zero uses, o opcode vira `IR_NOP`.

Entram nessa classe constants, moves, swizzles, arithmetic básica, min/max, abs, dot, reciprocal, trig, pow, trunc, compare e matrix-vector multiply.

O conjunto é deliberadamente conservador.

## Limitações do optimizer

Não é dead-code elimination completo.

Não remove branches unreachable inteiros.

Não compacta o array depois de converter instructions para NOP.

Não há constant-propagation dataflow geral, CSE, register allocation, SSA conversion ou análise de live intervals.

Os quatro passes permitem que remover um resultado revele producer anterior também sem uso.

## Particularidade de SETLANE

`IR_SETLANE` modifica somente parte do destination.

O optimizer trata destination como use além de write durante a contagem.

Sem essa regra, values anteriores em lanes não alteradas poderiam ser considerados mortos de forma incorreta.

É uma consequência direta do modelo não-SSA.

## Verificação

Depois da otimização, `sh_verify` valida a IR antes do TGSI ou da aceitação final.

Primeiro verifica stage, temporary count e instruction count.

Depois percorre cada non-NOP instruction.

A verificação é estrutural e baseada em ranges; não é prova formal da semântica completa do programa.

## Validação de temporary

Temporary válido precisa obedecer:

```text
0 <= t < ntmp
t < SH_TEMP_MAX
```

Destinations e operands comuns são validados.

Operações multi-temporary, como uniform loads e matrix multiply, também validam a última posição consecutiva.

Isso impede acesso fora do register file alocado.

## Regras por stage

O verifier exige:

- `IR_STORE_POS` somente em vertex;
- `IR_STORE_COLOR` somente em fragment;
- `IR_DISCARD` somente em fragment.

Essa defesa também é aplicada a blobs CSI carregados, não apenas a source compilado.

## Validação de slots

`IR_SAMPLE` precisa apontar sampler entre zero e `samp_hi`.

`IR_LOAD_ATTR` precisa ficar até `attr_hi`.

Varying load/store precisa estar em 0..7.

`IR_LOAD_UNI` valida destination span e quantidade de vectors.

O caminho normal do compiler controla o limite de 32 slots durante semantic allocation.

## Constants

Para `IR_CONST`, o verifier exige:

- destination válido;
- `aux >= 0`;
- `aux + ncomp <= nimm`.

Isso protege o pool de immediate.

O conteúdo floating-point não é autenticado.

NaN ou outros values são dados, não structural corruption.

## Matrix verification

`IR_MULMM` aceita `aux` igual a 3 ou 4.

Destination span e source temporaries iniciais precisam ser válidos.

O normal lowering já aloca columns contíguas.

O verifier protege shape/range, mas não reconstrói toda a proveniência de types da matrix.

## Dump textual

`sh_dump_ir_buf` gera representação legível.

O output começa com shader name e stage e lista interfaces como uniforms, inputs e outputs.

Depois aparece:

```text
block 0:
```

e cada instruction não-NOP com destination, mnemonic, operands selecionados e alguns campos aux.

O nome `block 0` não significa que exista CFG geral com vários basic blocks; a IR continua linear.

## Inspeção pública

`sh_shader_ir` expõe o dump armazenado no shader compilado.

Os testes usam essa interface para verificar que stores e outras operações apareceram.

É formato de debug, não interchange format estável.

A persistência binária usa CSI.

## Execução software

`sh_exec_ir` executa CSIR diretamente.

O register file é zerado e outputs recebem defaults.

Depois cada instruction é percorrida em ordem.

Control markers atualizam a skip stack.

Instructions comuns dentro de branch skipped são ignoradas.

Arithmetic e interface operations manipulam o temporary array.

O interpreter serve como backend CPU e referência executável da semântica da IR.

## Execução versus verification

O interpreter contém checks defensivos, mas espera normalmente CSIR previamente verificado.

Alguns handlers checam indices diretamente; outros dependem mais dos invariants estabelecidos por `sh_verify`.

O contrato arquitetural é:

```text
construct/load
  -> optimize quando vem de source
  -> verify
  -> backend
```

Blob binário não confiável não deve pular o verifier.

## Consumo pelo TGSI

O TGSI emitter percorre a mesma lista linear.

Ele converte CSIR em declarations e textual TGSI instructions.

Alguns opcodes CSIR se expandem em várias instructions TGSI.

Por isso instruction count entre as duas representações não precisa coincidir.

O capítulo seguinte trata desse mapping em detalhe.

## Formato CSI

`sh_shader_save_csi` serializa CSIR como:

```text
header de 32 bytes
N * sizeof(Ir)
M * sizeof(float)
```

O header contém oito words de 32 bits:

```text
0 magic      0x52495343
1 version    1
2 stage
3 nir
4 nimm
5 ntmp
6 checksum
7 reserved
```

O magic forma os bytes "CSIR" em little-endian.

## Portabilidade do CSI

O corpo das instructions é cópia direta dos bytes do array `Ir`.

Diferente dos encoders VirtIO, os fields não são serializados um por um para um wire format canônico.

Logo, o formato pressupõe mesmo layout de `Ir`, endianness e ABI compatível entre writer e reader.

Deve ser considerado formato interno experimental, não padrão portátil cross-architecture.

## Checksum CSI

O checksum é soma simples dos bytes dos records de IR.

O immediate pool não entra.

Modificar immediate pode deixar checksum igual.

O loader ainda valida tamanho e estrutura, mas não autentica os literal values.

Uma versão futura deveria proteger o payload completo e versionar explicitamente seu wire layout.

## Loading de CSI

O loader valida:

- header mínimo;
- magic/version;
- stage vertex ou fragment;
- contagens dentro dos limites;
- tamanho total exatamente igual ao esperado;
- checksum;
- `sh_verify`.

Depois tenta emitir TGSI.

Se o TGSI falhar, pode retornar shader object com `ok = 0`.

## Lacuna de metadata do CSI

CSI salva apenas stage, IR, immediates e temporary count.

Não salva symbol table, uniform names/high-water metadata, attribute metadata, sampler metadata, varying declarations ou source.

Ao carregar, o novo `ShComp` é zerado e essa metadata não é reconstruída.

Isso torna roundtrip geral incompleto.

## Consequência no verifier

A lacuna é observável.

Um shader carregado que use attribute slot acima de zero pode falhar porque `attr_hi` não foi restaurado.

Sampler slot acima de zero pode falhar porque `samp_hi` também não foi reconstruído.

O teste atual usa vertex shader constante sem interfaces complexas e, portanto, não cobre esse caso.

CSI ainda não deve ser tratado como production shader cache geral.

## Evidência de testes

`tools/test_shader.c` verifica que shaders compilados expõem IR e que o mesmo CSIR executa pelo software backend.

A suite cobre matrices, texture sampling, lighting, conditionals, unrolled loops, functions, discard e trig.

Também salva shader simples, recarrega, altera um byte da região IR e exige rejeição da corrupção.

Ela não cobre roundtrip de metadata CSI complexa.

## Evidência cross-backend

A mesma IR semântica alimenta software e TGSI.

`tools/test_gfx3d_abi.c` compara expectativas CPU com execução de vertex shader para identity, translation, rotations, scale, view e projection.

Isso ajuda a validar convenções de matrix antes da geração backend-specific.

Não prova bit-equivalence de todas as funções transcendentes entre CPU e VirGL.

## Complexidade

Verification e dump são lineares no número de instructions.

Optimizer faz quatro scans de use counting e quatro de elimination, permanecendo O(IR) com multiplicador fixo pequeno.

Software execution é O(IR) por shader invocation, além de custo de sampling e frequência de pixels/vertices.

Com máximo de 384 instructions, o foco é previsibilidade.

## Fronteira de robustez

Durante compile normal CSIR é memória do kernel controlada pelo compiler.

CSI introduz uma boundary de binary input.

Limites fixos, length checks e structural verification reduzem riscos de blobs malformados.

Porém, gaps de portabilidade, checksum e metadata significam que CSI não deve ser visto como interchange format endurecido para input não confiável sem trabalho adicional.

## Limitações atuais

CSIR é linear, não-SSA e single-function depois do lowering.

Não possui runtime loops, calls, labels, jumps ou phi nodes.

O register file físico software é float-based mesmo para int/bool.

Optimization é mínima.

A serialização depende do ABI e não preserva interfaces completas.

A IR foi desenhada para o subset atual, não como IR universal.

## Testes futuros recomendados

São úteis unit tests diretos do verifier para opcode inválido, flow desbalanceado, sampler/attribute fora da faixa, matrix spans inválidos e immediate overflow.

CSI deve ser testado com attribute location 3, vários uniforms, sampler slot 1 e varyings, exigindo reconstrução correta ou rejeição explícita.

Depois de fortalecer o formato, mutation de bytes do immediate pool também deve ser detectada.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele documenta CSIR como interface semântica limitada compartilhada pelo interpreter software e pelo backend TGSI, incluindo optimizer, verifier e limitações da persistência CSI.
