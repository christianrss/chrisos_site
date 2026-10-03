---
id: virgl-command-stream
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/virgl_proto.h
  - kernel/gfx/virgl_cmd.c
  - kernel/gfx/virgl_cmd.h
  - kernel/gfx/virgl_obj.c
  - kernel/gfx/virgl_obj.h
  - kernel/gfx/gfx3d_batch.c
  - kernel/gfx/gfx3d_batch.h
  - kernel/gfx/gfx3d_virgl.c
  - kernel/gfx/gfx3d_dev.h
  - kernel/gfx/virtgpu_enc.c
  - tools/test_virgl_cmd.c
  - tools/test_gfx3d_abi.c
symbols:
  - virgl_cmd_init
  - virgl_cmd_begin
  - virgl_cmd_u32
  - virgl_cmd_end
  - virgl_cmd_shader
  - virgl_cmd_link
  - virgl_cmd_draw
  - virgl_cmd_consts
  - gfx3d_batch_open
  - gfx3d_batch_reserve
  - gfx3d_batch_flush
depends_on:
  - gfx3d-api
  - virtio-gpu-transport
related:
  - virtio-gpu-virgl
  - shaders-csir
  - tgsi-backend
---

# Command stream VirGL

## Escopo

O ChrisOS não envia chamadas Gfx3D de alto nível diretamente ao VirtIO-GPU. O backend VirGL converte essas operações em uma sequência de words Gallium/VirGL de 32 bits e, depois, envolve esse stream em uma request VirtIO-GPU `SUBMIT_3D`.

A camada é:

```text
estado/draw Gfx3D
     |
     v
gfx3d_virgl.c
     |
     v
encoder VirglCmd
     |
     v
Gfx3DBatch
     |
     v
VirtIO-GPU SUBMIT_3D
```

O capítulo de transport explica como `SUBMIT_3D` chega ao device. Os capítulos de shaders explicam como o source vira TGSI. Aqui o foco é o encoding de state, shaders, resources e draws em dwords VirGL.

## Subconjunto do protocolo

`virgl_proto.h` define deliberadamente apenas o subconjunto necessário ao renderer atual.

Os opcodes presentes incluem:

- create, bind e destroy de object;
- viewport state;
- framebuffer state;
- vertex buffers;
- clear;
- draw VBO;
- sampler views;
- index buffer;
- constant buffer;
- sampler-state binding;
- shader binding;
- shader link.

Não é uma implementação completa de todos os commands Gallium/VirGL.

## Header do command

Todo command estruturado começa com um dword criado por:

```text
VIRGL_CMD0(cmd, obj, len)
```

O layout é:

```text
bits  7..0  : command opcode
bits 15..8  : object type
bits 31..16 : payload length em dwords
```

O tamanho não inclui o próprio header.

Um command com payload de oito dwords ocupa nove dwords no stream.

## Estado de VirglCmd

`VirglCmd` mantém:

- pointer para output;
- capacidade total;
- quantidade já gravada;
- posição esperada para o fim do command aberto;
- error state sticky;
- context ID VirGL.

O context ID serve à submission externa e não é automaticamente inserido no header de cada command.

## Inicialização

`virgl_cmd_init` exige object, buffer, capacidade não zero e context ID não zero.

Inicialização válida zera count, expected position e error.

Inicialização inválida coloca o object em erro quando possível.

Reinicializar é, portanto, a fronteira de recuperação após falha de encoding.

## Erro sticky

Depois que `err` se torna diferente de zero, writes seguintes falham.

O encoder não tenta consertar um command parcialmente construído.

A política é descartar ou reinitialize o stream.

`virgl_cmd_ok` exige:

```text
err == 0
n > 0
```

Builder vazio não é considerado stream pronto para submit.

## Disciplina begin/write/end

`virgl_cmd_begin` verifica:

- ausência de erro prévio;
- payload length não zero;
- espaço para header + payload completo;
- término exato de qualquer command anterior.

Depois grava o header e calcula a posição exata esperada ao final.

`virgl_cmd_u32` recusa overflow da capacidade e também recusa ultrapassar o payload declarado de um command aberto.

`virgl_cmd_end` só aceita quando `n == expect`.

Assim, underfill e overfill de commands estruturados são detectados.

## Dwords raw

Quando nenhum command está aberto, `virgl_cmd_u32` permite gravar words raw porque `expect == 0`.

O teste de batch usa isso para preencher artificialmente o buffer e forçar rollover.

Por isso `VirglCmd` é um builder de baixo nível, não um parser formal capaz de provar que todo word pertence a um command válido.

O backend de produção normalmente usa os helpers estruturados.

## Capacidade máxima

O encoder define:

```text
VIRGL_CMD_MAX = 1024 dwords
```

São 4096 bytes de command stream por batch.

Esse limite é menor que o máximo aceito pelo encoder inferior de `SUBMIT_3D`.

Gfx3D adota o limite mais restrito para storage previsível e rollover controlado.

## CLEAR

`virgl_cmd_clear` emite oito payload words:

- buffer mask;
- quatro color words;
- low/high do depth de 64 bits;
- stencil.

O backend atual usa COLOR0 e adiciona depth quando necessário.

Colors float são bit-cast para `uint32_t`.

O depth usado no clear device corresponde ao bit pattern de double 1.0.

## Surface objects

`virgl_cmd_surface` cria um SURFACE.

Handle zero e resource ID zero são rejeitados.

O payload leva:

- VirGL surface handle;
- VirtIO resource ID;
- format;
- dois zeros para campos não usados neste path.

O backend cria B8G8R8A8 para color e Z32_FLOAT para depth.

É um ponto claro em que o namespace de objects VirGL referencia o namespace separado de resources VirtIO.

## Framebuffer state

`virgl_cmd_framebuffer` suporta atualmente exatamente um color buffer.

Exige:

```text
nr == 1
color != 0
```

O depth/stencil surface pode ser zero quando depth está desligado.

O backend mantém cache das surfaces color/depth e as recria quando o target muda.

## Viewport

O command de viewport leva sete payload words.

O backend atual envia:

```text
scale x = width / 2
scale y = height / 2
scale z = 0.5
translate x = width / 2
translate y = height / 2
translate z = 0.5
```

Os floats são enviados como bits IEEE-754.

Width/height anteriores são cacheados para evitar command redundante.

Isso corresponde à limitação atual da API pública, que usa o target completo como viewport efetivo.

## Handles VirGL

VirGL handles não são handles públicos Gfx3D e não são resource IDs VirtIO.

Cada device context possui um `VirglObjPool` de:

```text
VIRGL_OBJ_POOL_MAX = 256
```

entries.

O pool guarda handle, type e live state.

Allocation evita zero e evita handle ainda live.

Contadores live/peak aparecem nas estatísticas Gfx3D.

## Tipos de objects

A implementação atual trabalha com:

- blend;
- rasterizer;
- depth/stencil/alpha;
- shader;
- vertex elements;
- sampler view;
- sampler state;
- surface.

Os helpers de create codificam payloads fixos para o subconjunto suportado.

Bindings são commands separados quando exigidos pelo protocolo.

## Destroy

`virgl_cmd_destroy` emite DESTROY_OBJECT com um payload contendo o handle.

Ao contrário de vários helpers de create/bind, ele não rejeita handle zero por conta própria.

O código superior normalmente filtra zero antes de chamá-lo.

A validação é, portanto, parcialmente dividida entre encoder e callers.

## Blend opaco

`virgl_cmd_blend_opaque` cria um blend object fixo para writes opacos.

Não existe ainda uma API pública completa de equations/factors de blending.

O object é criado em `ensure_pipe` e reutilizado nos draws.

A pipeline VirGL atual é intencionalmente menor que uma API OpenGL genérica.

## Depth/stencil

`virgl_cmd_dsa` exige handle não zero e comparison function <=7.

Com depth ligado, o state word ativa test, write e codifica a comparison function.

O backend cria duas variantes:

- depth enabled;
- depth disabled.

Cada draw escolhe uma delas conforme o estado Gfx3D.

## Rasterizer

`virgl_cmd_raster` aceita cull mode entre 0 e 3.

Ele combina bits fixos do rasterizer com o modo selecionado.

O backend cria um object sem culling e outro com culling.

Novamente, Gfx3D expõe apenas uma política reduzida, não o state space completo.

## Vertex elements

`virgl_cmd_velems` aceita de um a oito elements.

Cada element adiciona quatro dwords:

```text
source offset
0
0
format
```

O payload começa pelo handle do object.

O backend cacheia layouts por quantidade, offsets e formats.

Quando existe match, não cria novo vertex-element object.

## Vertex buffer

`virgl_cmd_vbuffers` exige stride e resource ID não zero.

O payload é:

- stride;
- byte offset;
- resource ID.

O backend atual liga um vertex buffer por draw, normalmente com offset zero.

Criação do resource e backing DMA pertencem à camada VirtIO.

## Index buffer

`virgl_cmd_ib` exige resource não zero e index size exatamente 2 ou 4.

O Gfx3D público usa indices `uint16_t`, então o path VirGL usa tamanho 2.

O command atual usa offset zero.

Draws não indexados simplesmente não emitem index-buffer state.

## DRAW_VBO

`virgl_cmd_draw` rejeita count zero.

O payload atual fixa:

```text
primitive = TRIANGLES
instance count = 1
```

Além disso leva start, count, indexed flag, min/max index e vários campos zero.

Draw indexado do Gfx3D usa max index 65535.

Draw não indexado usa o count no campo max.

Não há suporte público atual a topologias arbitrárias ou instancing geral.

## Shader objects

`virgl_cmd_shader` cria shader a partir de texto.

Só aceita vertex e fragment stages.

O encoder percorre a string e falha se encontrar mais de 3600 caracteres antes do NUL.

O NUL terminal é incluído no comprimento.

Quantidade de payload dwords para o texto:

```text
ceil(length_with_NUL / 4)
```

O command usa cinco metadata words antes dos dwords do source.

## Packing do texto

Quatro bytes são colocados em cada dword:

```text
word =
  byte0
  | byte1 << 8
  | byte2 << 16
  | byte3 << 24
```

Bytes restantes depois do NUL ficam zero.

Isso torna o encoding independente do alinhamento de pointer do source.

O texto enviado aqui é TGSI produzido pelo shader subsystem, não GLSL original.

## Metadata do shader

O payload contém handle, stage, comprimento exato, um segundo campo derivado do comprimento e um zero antes do source.

Esse campo derivado fica entre 128 e 2048 na implementação atual.

Ele pertence ao encoding VirGL usado aqui e não deve ser apresentado como configuração pública Gfx3D.

## Bind e link

`virgl_cmd_link` produz três commands, não um só:

1. BIND_SHADER vertex;
2. BIND_SHADER fragment;
3. LINK_SHADER com os dois handles.

Ambos precisam ser diferentes de zero.

O backend executa essa sequência no setup de cada draw.

A criação dos shader objects normalmente já ocorreu antes por immediate submission.

## Relação com generation dos programs

A camada Gfx3D pública acompanha generation do `ShProgram`.

Quando o program muda, o backend recria os objects VirGL correspondentes.

O command encoder não conhece generation.

Ele recebe somente handles e TGSI.

Assim, policy de versionamento do shader permanece acima da camada de protocolo.

## Constant buffers

`virgl_cmd_consts` aceita de 1 a 64 dwords.

Ele grava:

- shader stage;
- constant-buffer slot zero;
- words.

O helper não valida sozinho se stage é vertex ou fragment.

O backend fornece somente esses stages e converte uniforms float para raw bits antes de emitir.

64 dwords correspondem a no máximo dezesseis vec4 em uma submission desse tipo.

## Sampler state

`virgl_cmd_sampler` cria um sampler object fixo.

O state word codifica o addressing/filter escolhido pela implementação.

O payload inclui valores zero e um bit pattern fixo para max LOD.

A API Gfx3D não permite selecionar filtros e addressing arbitrários nesta revisão.

Um sampler é criado por device context e reutilizado.

## Sampler view

`virgl_cmd_sview` cria uma view para um resource e format.

Handle e resource precisam ser não zero.

O swizzle atual preserva a ordem natural 0,1,2,3.

Uma texture Gfx3D possui, portanto, resource VirtIO e sampler-view VirGL distintos.

## Binding de texture

Draw texturizado emite:

- BIND_SAMPLER_STATES no fragment stage;
- SET_SAMPLER_VIEWS no fragment stage.

Os helpers exigem handle não zero, mas não validam o stage por conta própria.

O backend sempre fornece fragment stage.

Como a API pública possui apenas um binding efetivo, somente uma sampler view é configurada.

## Immediate submissions

Nem todo command espera pelo final do frame.

O backend possui `emit_now`, que usa buffer temporário de `VIRGL_CMD_MAX`, executa uma callback de preenchimento, verifica `virgl_cmd_ok` e faz submit imediatamente.

Objetos de pipeline e shaders podem ser criados assim.

Isso garante que state futuro possa depender de objects já criados remotamente.

## Gfx3DBatch

State e draws de frame usam `Gfx3DBatch`.

Ele contém:

- array de 1024 dwords;
- `VirglCmd`;
- context ID;
- submit callback;
- contadores de submissions/dwords;
- error state do batch.

`gfx3d_batch_open` prepara o batch e inicializa o builder.

## Reserve e rollover

Antes de adicionar um grupo, o backend chama `gfx3d_batch_reserve(need)`.

Se não houver espaço, o batch atual é enviado e o builder é reinicializado.

Se `need > 1024`, a função falha e marca error.

Uma operação lógica pode, portanto, provocar boundary de `SUBMIT_3D` quando não cabe no restante do buffer.

## Invariante do flush

Flush de batch vazio retorna sucesso.

Stream não vazio é rejeitado quando:

- o batch já tem erro;
- existe command aberto (`expect != 0`);
- `virgl_cmd_ok` é falso;
- a submit callback falha.

Somente stream estruturalmente fechado chega ao transport.

Após submit com sucesso, os contadores são atualizados e o command builder é reinicializado.

## Ordem de montagem de um draw

O draw VirGL atual segue aproximadamente:

1. garantir objects base da pipeline;
2. garantir framebuffer surfaces;
3. garantir viewport;
4. bind blend;
5. bind DSA;
6. bind rasterizer;
7. bind/link shaders;
8. upload constants de vertex e fragment;
9. bind sampler/view quando há texture;
10. garantir e bind vertex-elements;
11. set vertex buffer;
12. set index buffer quando indexado;
13. emitir DRAW_VBO.

Essa ordem é o contrato concreto implementado em `gfx3d_virgl.c`.

## Caches de objects/state

O backend evita recriar state em todo draw.

Surfaces acompanham color/depth resources atuais.

Viewport acompanha width/height.

Vertex-element layouts são cacheados por offsets/formats.

Blend, DSA, rasterizer e sampler são criados uma vez por device context.

Isso reduz dwords e submissions, mas aumenta a responsabilidade de invalidar cache quando resources mudam.

## Destruição do context

Destroy do device context primeiro faz flush do batch pendente.

Depois percorre objects VirGL live e codifica DESTROY_OBJECT em buffers temporários.

Quando o buffer se aproxima do limite, envia o conjunto de destroys e reinicializa o encoder.

Em seguida libera tracked resources e destrói o context VirtIO.

Batching também é usado, portanto, no teardown.

## Evidência de test_virgl_cmd

`tools/test_virgl_cmd.c` fixa vários detalhes exatos.

Ele verifica:

- init com capacidade zero falha;
- buffer pequeno detecta overflow de CLEAR;
- CLEAR produz header `VIRGL_CMD0` correto e nove dwords totais;
- surface com handle zero falha;
- encoders VirtIO de 3D/context/SUBMIT têm campos esperados;
- DESTROY_OBJECT produz header e handle corretos.

É evidência host em nível de bytes/dwords.

## Evidência do batch

`tools/test_gfx3d_abi.c` preenche quase todo o buffer de 1024 dwords e pede uma reserva maior.

A operação precisa provocar exatamente uma fake submission e resetar o command length para zero.

Também verifica que reservar mais que o batch inteiro falha.

Isso fixa o rollover sem depender de VirtIO-GPU.

## O que os testes host não provam

Os testes de encoder não provam que virglrenderer aceita todo state emitido.

Também não validam visualmente os bits do rasterizer, sampler, DSA, shader metadata ou framebuffer.

Essa evidência vem do gate QEMU/VirGL com readback de pixels.

Forma do protocolo e correção visual são camadas de validação diferentes.

## Contenção de erros

A camada prefere fail-closed.

Handle inválido, falta de capacidade, index size ilegal, shader text grande demais ou payload com tamanho incorreto envenena o builder.

O batch então se recusa a enviar aquele stream.

O backend propaga erro ao Gfx3D, que pode marcar VirGL lost e degradar para software quando a policy permite.

Um stream sabidamente parcial não é submetido.

## Limitações atuais

O protocol subset é reduzido.

Draw topology é somente triangles.

Stages são somente vertex e fragment.

Constant buffer usa slot zero e no máximo 64 dwords por emission.

Sampler configuration é fixa.

Framebuffer suporta um color target.

Vertex elements são limitados a oito.

O builder aceita raw dwords e, por isso, não é validator semântico de streams arbitrários.

Não existe decoder/disassembler VirGL no tree atual.

## Testes recomendados

São úteis golden-word tests para viewport, framebuffer, DSA, rasterizer, vertex elements, indexed draw, sampler/view e shader text packing.

Também devem existir testes que underfill e overfill um command, iniciem um segundo command antes de terminar o primeiro e confirmem que o sticky error bloqueia submit.

Um teste de integração pode capturar o batch completo de um triângulo simples e comparar a sequência contra um golden stream revisado antes de enviá-lo ao QEMU.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele documenta o encoder de dwords VirGL e a semântica de batch como a camada de protocolo entre Gfx3D e `SUBMIT_3D` do VirtIO-GPU.
