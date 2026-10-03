---
id: gfx3d-api
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/gfx3d.c
  - kernel/gfx/gfx3d.h
  - kernel/gfx/gfx3d_dev.h
  - kernel/gfx/gfx3d_virgl.c
  - kernel/gfx/gfx3d_batch.c
  - kernel/gfx/gfx3d_batch.h
  - kernel/gfx/gfx3d_ctx.c
  - kernel/gfx/gfx3d_ctx.h
  - kernel/gfx/shader/sh_pub.h
  - tools/test_gfx3d_abi.c
  - tools/test_gfx3d_ctx.c
symbols:
  - gfx3d_boot
  - gfx3d_context_create
  - gfx3d_target_create
  - gfx3d_mesh_create
  - gfx3d_mesh_upload
  - gfx3d_tex_create
  - gfx3d_prog_prepare
  - gfx3d_begin
  - gfx3d_draw
  - gfx3d_end
  - gfx3d_present_scanout
  - gfx3d_drop_owner
depends_on:
  - software-3d
  - virtio-gpu-transport
related:
  - virtio-gpu-virgl
  - virgl-command-stream
  - shaders-csir
---

# API Gfx3D neutra de backend

## Escopo

Gfx3D é a abstração 3D pública acima do renderer software do ChrisOS e do backend VirtIO-GPU/VirGL.

A regra principal aparece diretamente em `gfx3d.h`: os handles públicos pertencem ao ChrisOS, enquanto IDs de resources VirtIO e handles de objetos VirGL não atravessam essa fronteira.

A API tem, portanto, duas responsabilidades:

1. oferecer um modelo estável de objects/frame para callers;
2. traduzir esse modelo para rendering CPU ou para trabalho VirGL no device.

Este capítulo descreve esse contrato, e não repete o transport VirtIO nem o formato do command stream VirGL.

## Backends

Existem quatro modos de boot:

```text
GFX3D_AUTO
GFX3D_SOFTWARE
GFX3D_VIRGL
GFX3D_MOCK
```

SOFTWARE força o backend CPU.

VIRGL exige `gfx3d_dev_available()`. Se não estiver disponível, boot retorna erro, registra `virgl unavailable` e o nome visível fica `virgl-lost`.

AUTO escolhe VirGL quando o device backend está disponível; caso contrário usa software.

MOCK não renderiza pixels. Ele registra operações de alto nível em um log para testes de ABI e ordering.

## Política de device lost

`gfx3d_mark_lost` marca o caminho VirGL como perdido.

Se o caller forçou VirGL, Gfx3D mantém a escolha e expõe o estado lost, sem alterar silenciosamente a política.

Se AUTO havia escolhido VirGL, Gfx3D troca para SOFTWARE e marca a estatística `degraded`.

Assim, AUTO prioriza continuidade; forced VirGL prioriza diagnóstico explícito.

## Formato dos handles públicos

Um handle é empacotado como:

```text
16 bits altos : generation
16 bits baixos: slot index + 1
```

Zero nunca é válido.

Cada slot possui um generation counter. Quando um slot liberado é reutilizado, generation é incrementado, mantendo-se em 1..65535 e pulando zero.

Um stale handle falha quando sua geração deixa de coincidir com a do slot atual.

Isso evita que uma referência antiga acesse acidentalmente um objeto novo que reutilizou o mesmo index.

## Ownership

Context, target, mesh, texture e program instance guardam um owner inteiro.

Os lookup helpers podem exigir um owner específico e rejeitam objects de outro caller.

`GFX3D_OWNER_KERNEL` vale zero, mas outros owners podem representar apps/subsystems.

Isso é isolamento de bookkeeping, não uma barreira de segurança MMU/IOMMU.

## Tabelas fixas

Os limites atuais são:

```text
contexts : 8
targets  : 8
meshes   : 48
textures : 24
programs : 16
```

Cada tipo usa array global fixo.

Creation procura um slot livre.

Quando a tabela está cheia, retorna handle zero e grava uma mensagem de erro.

Os limites simplificam lifecycle e lookup, mas são capacidades reais da API atual.

## Estado do context

Um context armazena:

- owner e generation;
- device context opcional;
- flag de frame;
- target ativo;
- program ativo;
- texture ativa;
- depth enable;
- cull enable;
- viewport width/height;
- matrices model/view/projection;
- parâmetros da câmera.

Novo context começa com depth ligado, FOV 60°, near 0.1 e far 200.

As matrices começam como identity.

Com VirGL ativo, creation também tenta abrir um device context.

## Falha ao criar device context

Sob forced VirGL, falha no device context faz a criação pública retornar zero.

Sob AUTO, a mesma falha chama `gfx3d_mark_lost`, degrada para software e mantém o public context.

Assim, o object público pode sobreviver à perda do backend em AUTO.

Essa política também aparece em targets e outros resources.

## Destroy do context

Ao destruir um context, a API primeiro destrói targets e program instances ligados àquele context.

Depois remove o device context, quando existe.

Meshes e textures são owner-scoped e não são eliminados somente porque um context desapareceu.

Cleanup completo por owner usa `gfx3d_drop_owner`.

## Render targets

Target pertence a um context e aceita dimensões de 1×1 até 1920×1080.

Todo target sempre aloca storage CPU para:

- pixels color de 32 bits;
- depth float.

Isso ocorre mesmo com VirGL.

Quando o device backend existe, são criados também resources device color/depth e DMA correspondente.

O target público é, portanto, um objeto cross-backend.

## Custo de memória do target

Para W×H:

```text
color = W * H * 4
depth = W * H * sizeof(float)
```

Em Full HD, são aproximadamente 8,29 MB de color e mais 8,29 MB de float depth antes do backing do device.

As estatísticas separam target bytes e depth bytes.

O backing VirGL é consultado na camada device.

## Resize

Resize para o mesmo tamanho retorna sucesso imediatamente.

Resize real destrói resources VirGL existentes, libera os arrays CPU, aloca arrays novos e recria resources device se VirGL ainda estiver ativo.

Se a recriação falha em AUTO, Gfx3D marca VirGL lost e preserva o target CPU.

Em forced VirGL, a operação retorna erro.

Conteúdo anterior não é preservado.

## Readback

`gfx3d_target_read` exige destination capaz de receber o target completo.

No software backend, copia diretamente o color buffer CPU.

Com VirGL, primeiro faz readback do device color resource para o CPU buffer do target, incrementa a estatística de readbacks e depois copia para o caller.

A semântica pública fica uniforme, embora o custo seja muito diferente.

## Meshes e usage

Meshes aceitam:

```text
STATIC
DYNAMIC
STREAM
```

Valor inválido vira STATIC.

A implementação guarda o usage, mas ainda não existe uma política sofisticada de residency/streaming por backend baseada nele.

No estado atual, usage é mais uma intenção de API do que um contrato completo de memória.

## Vertex layout

`Gfx3DLayout` contém:

- stride em bytes;
- até oito elements;
- location;
- component count;
- byte offset.

O shader informa os attributes necessários.

`gfx3d_layout_ok` exige que cada shader attribute esteja presente e que o element tenha pelo menos a quantidade de componentes requerida.

A função não prova sozinha que offset+components cabe dentro do stride.

Upload também faz apenas validações estruturais amplas.

Esse é um ponto para validação futura mais estrita.

## Ownership do mesh upload

`gfx3d_mesh_upload` copia os vertex bytes para memória pertencente ao Gfx3D.

Indices opcionais são copiados para array `uint16_t`.

Assim, os buffers originais do caller podem ser liberados depois do retorno.

As estatísticas contam CPU mesh bytes.

Com VirGL ativo, o código procura o primeiro device context live do mesmo owner e envia VBO/IBO para ele.

## Afinidade de device context

Mesh é owner-scoped, não explicitamente context-scoped.

O upload escolhe o primeiro context do owner com device context.

Isso funciona para os workloads atuais, mas não constitui um modelo geral de residency entre múltiplos contexts independentes.

Uma evolução deve tornar essa afinidade explícita ou implementar compartilhamento backend conscientemente.

## Mesh builder incremental

Além do upload raw, existe `gfx3d_mesh_vert`.

Ele acumula no máximo:

```text
ACC_MAX = 8192
```

vertices.

Cada entrada guarda position XYZ, normal XYZ e UV: oito floats.

A capacidade temporária começa em 64 e dobra até o teto.

`gfx3d_mesh_finish` converte esse accumulator para um vertex format de 40 bytes.

## Layout gerado por mesh_finish

O formato contém:

- location 0: position com quatro componentes em offset 0;
- location 1: normal com quatro slots em offset 16;
- location 2: UV com dois componentes em offset 32.

W da posição é 1.

O quarto componente da normal permanece zero porque o accumulator contém apenas XYZ.

Após o upload, o buffer temporário convertido é liberado.

## Textures públicas

Textures aceitam dimensões de 1 a 1024 em cada eixo.

Creation aloca pixel array CPU `uint32_t`.

Upload exige exatamente as mesmas dimensões.

Cada pixel recebido sofre OR com:

```text
0xFF000000
```

Portanto o upload público força alpha opaco.

Com VirGL, o backend cria resource de textura e sampler view no primeiro device context adequado do owner.

## Um único binding efetivo

`gfx3d_bind_tex(owner,ctx,unit,tex)` atualmente ignora o argumento `unit`.

O context guarda apenas um texture handle.

A assinatura antecipa texture units, mas a implementação atual efetivamente oferece apenas uma texture bound.

Não se deve inferir suporte multi-texture a partir do parâmetro.

## Solid texture

`gfx3d_tex_solid` cria texture 1×1, força alpha opaco e faz upload de um pixel.

Se o upload falha, o helper destrói a texture recém-criada antes de retornar.

É útil para materiais constantes que querem manter o mesmo shader path.

## Program instances

Gfx3D não compila shader source diretamente.

Ele recebe um `ShProgram` já linked.

`gfx3d_prog_prepare` valida o program e cria uma public program instance associada a um context específico.

No backend VirGL, o código obtém TGSI vertex/fragment do shader subsystem e cria os objetos de shader no device.

## Generation do shader program

A program instance guarda o generation stamp do `ShProgram`.

Antes do uso/draw, Gfx3D compara `sh_program_gen` atual com o stamp.

Se o shader foi relinkado com sucesso e a geração mudou, os shaders VirGL são recriados.

Assim, um program pode ser atualizado sem exigir que o caller crie uma nova instance pública.

## Lifecycle do frame

Um frame explícito típico é:

```text
gfx3d_begin
  -> clear / state / uniforms
  -> use program
  -> bind texture
  -> draw...
gfx3d_end
```

`gfx3d_begin` exige que target pertença ao context.

Ele marca frame ativo, guarda o target e inicializa viewport width/height com as dimensões do target.

Com VirGL, abre também o frame/batch device.

## Gate de forced VirGL

Se VirGL foi explicitamente forçado e o backend está lost ou não está mais VirGL, `gfx3d_begin` retorna erro com `forced virgl unavailable`.

Em AUTO, a API pode já ter degradado para software e continuar usando as mesmas chamadas públicas.

## Clear

`gfx3d_clear` sempre limpa os arrays CPU color e float depth.

Valores de color abaixo de zero são clampados para zero.

Valores acima de 1 não passam por clamp explícito antes da conversão para inteiro.

Depth é preenchido com 1.0.

O parâmetro `depth` liga depth quando não zero, mas zero não desliga um estado já ligado.

Para desligar, o caller precisa usar `gfx3d_depth(ctx,0)`.

Com VirGL, um clear equivalente também é emitido ao device.

## Limitação do viewport

`gfx3d_viewport` valida width/height positivos e os guarda no context.

X e Y são explicitamente ignorados.

Além disso, o software raster usa as dimensões do target diretamente, e o path VirGL inspecionado também prepara draw state usando width/height do target.

Logo, a API de viewport ainda não implementa um viewport completo.

## Diferença depth/cull entre backends

`gfx3d_depth` e `gfx3d_cull` armazenam flags no context.

O backend VirGL recebe ambas no draw descriptor.

O software path atual, porém, sempre faz o depth compare/update em `soft_tri` e não consulta `cull`.

Portanto essas operações não são semanticamente equivalentes entre software e VirGL nesta revisão.

É uma lacuna concreta para testes cross-backend.

## Câmera e matrices

`gfx3d_camera` altera a câmera global de math3d, calcula view para o context e gera projection perspective usando aspect ratio do target.

FOV, near e far ficam armazenados.

Se já existe program ativo, uniforms chamados `view` e `projection` são atualizados quando presentes.

`gfx3d_model` guarda model e atualiza uniform `model`.

Se houver `normalMatrix`, calcula a matrix 3×3 correspondente.

## Uniforms

`gfx3d_uniform_mat4` converte o layout da matrix para ordenação GLSL antes de chamar o shader subsystem.

`gfx3d_uniform_f` envia vetor de floats com count arbitrário aceito pelo shader.

As duas funções operam sobre o program atualmente bound.

Sem program ativo, retornam erro.

Os valores residem no `ShProgram` e depois são serializados pelo backend VirGL quando necessário.

## Preconditions do draw

`gfx3d_draw` exige:

- frame ativo;
- mesh uploaded;
- program linked e bound;
- target válido;
- layout compatível com shader;
- pelo menos um triângulo.

Mesh indexado usa grupos de três indices `uint16_t`.

Mesh não indexado usa grupos sequenciais de três vertices.

Índice fora da faixa causa erro.

## Backend software

O backend software executa vertex e fragment shader pela implementação CPU do shader subsystem.

Os vertex outputs são divididos por W.

Varyings são interpolados com correção perspectiva usando reciprocal W.

Depth é float dentro do target público.

Fragment com depth maior ou igual ao armazenado é rejeitado.

Se uma texture pública está bound, o pixel buffer CPU é passado ao fragment shader software.

Esse caminho é separado do rasterizador legado `tri.c`.

## Backend VirGL

No path VirGL, Gfx3D monta `Gfx3DDevDraw` com shader handles, VBO/IBO, stride, count, indexed flag, depth/cull, texture resource/view, layout offsets/formats e color/depth resources.

Elementos de dois componentes recebem um format code; os demais tamanhos atuais usam outro code.

O backend device converte esse descriptor em state e commands VirGL.

O caller público nunca vê esses IDs.

## Backend MOCK

MOCK registra tokens como:

```text
begin
clear
use
tex
draw
end
```

em um log global limitado a 1024 bytes.

Ele é usado para validar ownership e ordem das chamadas sem device e sem rendering de pixels.

Não é um renderer.

## End do frame

`gfx3d_end` exige frame ativo.

Com VirGL, faz flush/submit do frame device.

Depois coleta deltas dos contadores acumulados de submissions e dwords e os adiciona às estatísticas públicas.

Também atualiza GPU backing bytes e quantidade live/peak de objetos VirGL.

Finalmente limpa o flag de frame.

Chamar end sem begin retorna erro.

## Presentation

Existem dois caminhos explícitos.

`gfx3d_present_scanout` exige target VirGL com device color resource e o coloca diretamente no scanout.

`gfx3d_scanout_primary` restaura o resource 2D principal do VirtIO-GPU.

Em host builds, direct scanout retorna erro.

Essas APIs pertencem ao ambiente freestanding/device.

## Cleanup por owner

`gfx3d_drop_owner` percorre e destrói, nessa ordem:

- meshes;
- textures;
- program instances;
- targets;
- contexts

do owner informado.

Também cancela ownership de frame implícito associado.

É o mecanismo de teardown em massa para apps/subsystems.

## Estatísticas

`Gfx3DStats` expõe:

- submits/dwords;
- draws/triangles;
- uploads/bytes;
- readbacks;
- CPU mesh bytes;
- GPU backing;
- target/depth bytes;
- live object counts;
- VirGL live/peak object counts;
- backend, forced mode e degraded.

Campos como `frame_cycles`, `visible_chunks` e `chunk_rebuilds` existem na struct pública, mas não são atualizados pelo caminho `gfx3d.c` inspecionado.

Não devem ser tratados como telemetry completa nesta revisão.

## Reset de estatísticas

`gfx3d_stats_reset` zera contadores de evento, mas preserva contagens de objects live e totais persistentes de memória CPU para meshes, targets e depth.

Assim, reset não produz a impressão de que resources existentes deixaram de existir.

Dados device-derived podem ser atualizados novamente em chamadas futuras de stats.

## Teste principal de ABI

`tools/test_gfx3d_abi.c` cobre uma parte ampla da API.

Ele verifica equivalência de matrices CPU/shader, exaustão e release de handles VirGL, batch rollover, shader layout, sequência MOCK, rejeição de owner estrangeiro, rendering software, target resize, generation de handle após destroy/recreate e 1000 ciclos de create/destroy de mesh/texture.

Ao final, `gfx3d_drop_owner` precisa zerar os live counts.

## Teste de context state

`tools/test_gfx3d_ctx.c` testa uma camada inferior/mais antiga de snapshot de câmera, light e texture procedural em `Gfx3DCtx`.

O primeiro load deve inicializar defaults, sem copiar globals estrangeiros.

Depois são salvos dois contexts e verificada a separação entre eles.

O teste também cobre ownership do voxel world.

Essa evidência complementa, mas não é idêntica à API pública de handles em `gfx3d.c`.

## Limitações atuais

A API usa tabelas globais e não é genericamente thread-safe.

Capacidades são fixas.

Residency do mesh no backend é ligada de forma frouxa ao primeiro device context do owner.

Texture unit é ignorado.

Viewport X/Y são ignorados e as dimensões não são honradas completamente em todos os backends.

Depth/cull software não correspondem integralmente ao VirGL.

Textures são limitadas a 1024×1024 e alpha é forçado opaco.

São fronteiras concretas da revisão atual, não a semântica final desejada.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Gfx3D é tratado como uma camada de ownership, handles e frame acima tanto da execução CPU de shaders quanto do backend VirGL, sem expor IDs VirtIO/VirGL na API pública.
