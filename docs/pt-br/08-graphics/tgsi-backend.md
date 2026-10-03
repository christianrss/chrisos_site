---
id: tgsi-backend
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/shader/sh_tgsi.c
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_api.c
  - kernel/gfx/shader/sh_src.h
  - kernel/gfx/gfx3d_virgl.c
  - kernel/gfx/virgl_cmd.c
  - tools/test_shader.c
  - tools/test_gfx3d_abi.c
symbols:
  - sh_emit_tgsi
  - sh_program_tgsi
  - sh_program_link
  - virgl_cmd_shader
depends_on:
  - csir
  - virgl-command-stream
related:
  - shaders-csir
  - shader-frontend
  - software-shader
---

# Backend TGSI

## Escopo

O backend TGSI converte Chris Shader IR verificado para a forma textual TGSI consumida pelo caminho VirGL.

Ele não faz parsing da linguagem, não cria objects públicos Gfx3D e não envia requests VirtIO.

A fronteira é:

    CSIR verificado
         |
         v
    sh_emit_tgsi
         |
         v
    TGSI text
         |
         v
    VirGL shader object
         |
         v
    VirtIO-GPU SUBMIT_3D

O backend software executa o mesmo CSIR diretamente. TGSI é uma representação de backend, não a fonte semântica principal.

## Limite do output

O TGSI é escrito em buffer fixo:

    SH_TGSI_MAX = 3600 bytes

A API guarda um buffer desse tamanho por shader.

Os testes exigem que shaders maiores como MVP, lighting e world permaneçam abaixo de aproximadamente 3500 bytes, deixando margem para o limite duro.

Quando a emissão se aproxima do limite, o emitter registra a mensagem "TGSI exceeds the VirGL command budget" e limpa o output.

Esse limite também combina com o tamanho máximo aceito pelo encoder VirGL de shader text.

## Header por stage

A primeira linha é exatamente VERT ou FRAG.

Somente vertex e fragment são emitidos.

Geometry, tessellation e compute não possuem backend TGSI nesta revisão porque o compiler não os produz.

## High-water marks

A semantic analysis inicializa attr_hi, var_hi, uni_hi e samp_hi em -1.

Esses valores aumentam conforme slots são atribuídos.

O TGSI emitter usa os limites para decidir quais declarations existem.

Shader sem uniforms não recebe DCL CONST.

Shader sem sampler não recebe DCL SAMP e DCL SVIEW.

## Vertex inputs

No vertex shader, todo slot entre zero e attr_hi recebe uma declaration IN.

O emitter percorre a faixa densa do high-water mark.

Como explicit locations podem criar gaps, slots intermediários podem ser declarados mesmo quando o source não usa todos eles.

Isso é consequência do modelo de declaração por faixa, não de uma symbol walk exata.

## Vertex outputs

Position é sempre declarada como OUT[0] com semantic POSITION.

Varyings começam em OUT[1].

Para varying CSIR slot N, o backend usa OUT[N+1] associado a GENERIC[N].

Assim, position fica fora do namespace de generic varyings.

IR_STORE_POS escreve OUT[0] e IR_STORE_VAR escreve OUT[slot+1].

## Fragment varyings

Inputs do fragment são declarados como GENERIC com interpolation PERSPECTIVE.

O frontend reconhece smooth, mas não oferece flat ou noperspective.

Por isso o backend atual usa PERSPECTIVE de forma uniforme.

Esse comportamento corresponde ao interpolation perspective-correct do software programmable path.

## Remap de varyings

Fragment shader é compilado inicialmente com slots locais ao próprio stage.

No link, names e types de fragment inputs são associados aos vertex outputs.

O linker cria uma tabela de remap.

sh_emit_tgsi recebe essa tabela quando gera o TGSI final do fragment shader.

Tanto declarations quanto IR_LOAD_VAR usam o slot remapeado.

Por isso o link precisa regenerar TGSI em vez de simplesmente reaproveitar o texto produzido na compilação isolada.

## gl_FragCoord

Antes de emitir headers, o backend procura IR_LOAD_FCOORD.

Se existir, adiciona uma declaration POSITION em IN[7].

O load correspondente vira MOV do IN[7] para o temporary de destino.

IN[7] é uma convenção desse backend para gl_FragCoord e fica separado dos generic varyings.

## Fragment output

O output fragment é OUT[0] com semantic COLOR.

IR_STORE_COLOR escreve nesse register.

Como o shader language subset só aceita um fragment output, não existe mapping para multiple render targets.

## Samplers

Para cada slot de zero a samp_hi, o emitter gera uma declaration SAMP e outra SVIEW 2D FLOAT.

TGSI descreve sampler e sampler view.

A camada VirGL posteriormente cria e binda state e view reais.

CSIR carrega apenas o slot numérico.

## Uniform constants

Quando uni_hi é pelo menos zero, o TGSI declara CONST buffer zero da posição zero até uni_hi.

Todos os uniforms do stage ficam no constant buffer zero.

IR_LOAD_UNI gera um MOV por vec4 slot.

Mat3 expande para três MOVs e mat4 para quatro.

## Temporaries

Com pelo menos um temporary, o backend declara TEMP[0] ou uma faixa TEMP[0..N].

O índice TGSI é o mesmo índice CSIR.

Não há register allocation ou renaming no backend.

Essa correspondência direta simplifica debugging, embora não minimize o uso de registers.

## Immediates

Cada IR_CONST recebe um IMM TGSI próprio.

Primeiro o emitter numera todas as constant instructions.

Depois emite um record FLT32 com quatro lanes.

Lanes não usadas são zero.

Dois constants CSIR iguais não são deduplicados.

A prioridade atual é simplicidade, não compactação textual.

## Formatação float

Os floats são convertidos pelo formatter pequeno do shader subsystem.

Ele não usa printf host.

O formato escreve seis casas decimais e possui limites próprios para valores grandes.

O objetivo é produzir TGSI consumível pelo parser VirGL, não uma serialização decimal bit-perfect de qualquer IEEE-754.

## Numbering das instructions

Linhas executáveis recebem program counter decimal crescente.

Declarations e IMM não entram nessa contagem.

O final recebe uma linha END numerada.

NOPs CSIR também não consomem program counter porque não geram TGSI.

## MOV e SWZ

IR_MOV vira MOV.

Quando o value tem menos de quatro components, o destination recebe write mask.

IR_SWZ também vira MOV, mas o source recebe swizzle montado a partir da máscara de dois bits por component do CSIR.

Para identity vec4 completo, o suffix pode ser omitido.

Assim, SWZ é opcode explícito em CSIR, mas vira operand modifier no TGSI.

## SETLANE

IR_SETLANE vira MOV para uma única lane do destination.

aux escolhe destination lane e aux2 a source lane.

O source scalar é replicado no textual swizzle, embora somente uma destination lane seja escrita.

Isso preserva a semântica parcial do CSIR não-SSA.

## Arithmetic direto

Os mappings diretos são:

    IR_ADD -> ADD
    IR_SUB -> SUB
    IR_MUL -> MUL
    IR_MIN -> MIN
    IR_MAX -> MAX
    IR_ABS -> ABS

Operações binárias aplicam write mask conforme ncomp.

Os source temporaries são usados diretamente.

Type checking já ocorreu antes no semantic analyzer.

## Dot product

IR_DOT vira DP4 quando aux é 4 e DP3 nos demais casos usados pela implementação.

O resultado vai para lane X do destination.

Não existe mapping DP2 específico no emitter atual.

A semantic layer precisa entregar operações compatíveis com esse contrato.

## RSQ, RCP, SIN, COS e TRUNC

Os mappings são diretos para RSQ, RCP, SIN, COS e TRUNC.

Quando o CSIR indica múltiplos components, o backend emite uma instruction TGSI para cada lane.

A source lane é replicada e cada instruction grava somente a lane correspondente do destination.

Uma instruction CSIR pode, portanto, expandir para até quatro linhas TGSI.

## POW

IR_POW gera uma operação POW scalar usando lane X dos dois sources e escrevendo lane X do destination.

Comportamento vectorial precisaria já ter sido decomposto antes de chegar a essa instruction.

## Comparisons

O mapping é:

    LT -> SLT(a,b)
    GT -> SLT(b,a)
    GE -> SGE(a,b)
    LE -> SGE(b,a)
    EQ -> SEQ(a,b)
    NE -> SNE(a,b)

O resultado vai para lane X.

GT e LE são implementados trocando operands.

A saída segue a convenção CSIR de boolean scalar como 0.0 ou 1.0.

## Matrix-vector

IR_MULMV não vira uma instruction única.

O helper mad_col expande o cálculo column-major em MUL para a primeira column e MAD para cada column seguinte.

Uma mat4 vezes vec4 gera quatro instructions TGSI.

O component do vector é replicado com swizzle correspondente e multiplicado pela column da matrix.

## Matrix-matrix

IR_MULMM aplica a mesma expansão para cada output column.

Mat4 vezes mat4 gera dezesseis MUL/MAD.

Mat3 vezes mat3 gera nove.

Essa expansão é uma das principais causas de crescimento do TGSI textual.

Um shader pode ficar abaixo de 384 CSIR instructions e ainda se aproximar de 3600 bytes depois da expansão.

## Texture sample

IR_SAMPLE vira uma instruction TEX usando TEMP de coordinate, SAMP[N] e target 2D.

O shader referencia sampler slot, não resource ID VirtIO.

Resource e sampler-view binding acontecem mais tarde no backend Gfx3D/VirGL.

Isso permite usar o mesmo shader com textures diferentes entre draws.

## Attribute loads

IR_LOAD_ATTR vira MOV de IN[location] para TEMP.

A camada de draw VirGL precisa montar vertex elements e vertex buffers compatíveis com essas locations.

A metadata pública do program conecta o shader TGSI ao vertex layout Gfx3D.

## Varying loads

IR_LOAD_VAR usa MOV do input TGSI já remapeado.

O mesmo var_remap empregado nas declarations é usado na instruction.

Isso mantém declaration register e instruction register consistentes.

## Stores por stage

Os mappings são:

    IR_STORE_POS   -> OUT[0]
    IR_STORE_VAR   -> OUT[slot+1]
    IR_STORE_COLOR -> OUT[0]

OUT[0] significa POSITION no vertex e COLOR no fragment.

Generic varyings começam em OUT[1].

## Control flow

Os markers CSIR mapeiam diretamente para IF, ELSE e ENDIF.

Como loops já foram unrolled e user functions inlined, não é necessário gerar loop instructions, branch targets ou subroutines.

O backend trata somente structured conditional flow.

## Discard

IR_DISCARD vira KILL.

O teste de shaders exige explicitamente que o TGSI do shader com discard contenha KILL.

É uma evidência direta do mapping CSIR para TGSI.

## NOP

IR_NOP não produz TGSI.

O optimizer substitui dead instructions por NOP sem compactar o array CSIR.

O TGSI emitter simplesmente ignora essas entries.

Assim, os program counters TGSI permanecem densos mesmo com holes no array original.

## Proteção pelo verifier

O switch do emitter possui default que não gera output para opcode desconhecido.

No pipeline correto isso é protegido por sh_verify, que rejeita opcodes inválidos antes da emissão.

O TGSI backend espera IR verificada e não deve ser tratado como sandbox para memória arbitrária.

## Regeneração no linker

A compilação individual gera TGSI preliminar.

Quando vertex e fragment são ligados, a API regenera os dois TGSI a partir dos ShComp retidos.

O fragment recebe o varying remap do linker.

O TGSI pertencente ao ShProgram linked é o texto que deve seguir para Gfx3D/VirGL.

## Integração com Gfx3D

gfx3d_prog_prepare recebe ShProgram linked.

Com VirGL ativo, lê o TGSI vertex e fragment do program e cria os shader objects VirGL.

Gfx3D não precisa entender opcodes CSIR.

Ele trata TGSI como payload específico do backend.

## Fronteira com o command encoder VirGL

O command encoder recebe o texto TGSI.

Ele aceita somente vertex e fragment, limita o texto a 3600 caracteres, inclui NUL terminal e empacota quatro bytes por dword.

O limite SH_TGSI_MAX do compiler está alinhado ao limite downstream.

Essa dependência é intencional.

## Propagação de falha

Se TGSI emission falha durante compile, o shader não é marcado válido.

Se a regeneração no link falha, program link falha.

Um failed relink pode preservar a generation anterior.

Na camada Gfx3D, falha ao criar ou enviar shader VirGL pode marcar o backend como lost e fazer AUTO degradar para software.

O erro possui caminho completo de propagação.

## Evidência em testes

tools/test_shader.c verifica que:

- vertex TGSI contém VERT;
- POSITION aparece;
- END aparece;
- MVP contém CONST[0] e MUL;
- fragment shader de texture contém TEX e SAMP[0];
- shader com discard contém KILL;
- MVP, lighting e world ficam abaixo do budget.

São asserts textuais host-side.

## Evidência de integração

O boot proof VirGL é mais forte.

Shaders gerados por este backend são enviados como VirGL shader objects e usados em workloads de triangle, texture, depth, cube e lighting, com readback de pixels.

Essa é a evidência de que o texto é aceito pelo ambiente VirGL/virglrenderer configurado.

Testes host isolados não provam device acceptance.

## Limite de equivalência com software

TGSI e interpreter software partem do mesmo CSIR, mas não precisam ser bit-identical.

O backend software usa approximations próprias para transcendental math.

TGSI delega essas operações ao host/VirGL.

Floating-point edge cases, precisão de trig/pow e texture sampling podem diferir.

Cross-backend tests devem usar tolerances apropriadas.

## Limitações atuais

O backend suporta apenas vertex/fragment.

Existe um único color output.

Varyings normais sempre usam PERSPECTIVE.

Não há register allocation.

Constants iguais não são deduplicados em IMM.

Matrix operations expandem muito o texto.

TGSI é limitado a 3600 bytes.

O output é textual e específico para o caminho VirGL atual, não uma binary shader ISA geral.

## Testes futuros recomendados

São úteis golden tests para varying remap com slots deliberadamente diferentes, mat3/mat4, todos comparisons, SIN/COS/RCP multicomponent, gl_FragCoord, sampler slot acima de zero e gaps em explicit attribute locations.

Também deve existir teste de boundary logo abaixo e logo acima de 3600 bytes.

Um teste integrado pode comparar resultados software/VirGL do mesmo linked program usando tolerância numérica.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS e05a17fd76333114a3fb5c2452f38ca747d4ac56. Ele documenta o TGSI emitter como tradução limitada de CSIR verificado para a representação de shader consumida pelo VirGL.
