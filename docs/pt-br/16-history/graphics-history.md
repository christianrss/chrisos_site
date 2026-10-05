---
id: graphics-history
lang: pt-br
type: technical-chapter
volume: 16-history
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/graphics.c
  - kernel/gfx/gfx2d.c
  - kernel/gfx/tri.c
  - kernel/gfx/zbuf.c
  - kernel/gfx/tex.c
  - kernel/gfx/voxel.c
  - kernel/gfx/gfx3d.c
  - kernel/gfx/gfx3d_virgl.c
  - kernel/gfx/vgpu.c
  - kernel/gfx/virgl_cmd.c
  - kernel/gfx/virgl_demo.c
  - kernel/gfx/shader/sh_api.c
  - kernel/gfx/shader/sh_ir.c
  - kernel/wm/desktop.c
  - kernel/wm/ui.c
symbols:
  - gfx_present
  - gfx3d_boot
  - gfx3d_mark_lost
  - vgpu_boot
  - sh_compile
  - sh_program_link
depends_on:
  - architecture-history
related:
  - pixels-framebuffer
  - gfx2d
  - triangle-rasterization
  - virtio-gpu-virgl
  - gfx3d-api
  - shader-spec
  - mine-graphics
---

# História da arquitetura gráfica

## Escopo

Este capítulo reconstrói como a pilha gráfica do ChrisOS chegou à arquitetura atual.

O texto é propositalmente preso a revisões. Nem todo commit gráfico é tratado como uma nova arquitetura; o foco está nos pontos que alteraram limites de subsistema, ownership, backend de execução ou qualidade da evidência.

A história foi reconstruída a partir do Git e reconciliada com o source atual na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

## Como ler a cronologia

O primeiro marco descrito aqui, em 18 de setembro de 2026, **não** é o nascimento absoluto dos gráficos no ChrisOS.

O commit:

    13b8aa216065b85f7f50a9b1fe1bd758c7caaab8

moveu ou renomeou arquivos já existentes como `graphics.c`, `font.c`, `input.c`, `desktop.c` e outros arquivos de window manager, ao mesmo tempo em que adicionou a organização atual sob `kernel/gfx` e o novo `gfx2d.c`.

Assim, 18 de setembro deve ser interpretado como o momento em que a estrutura atual de diretórios e responsabilidades se torna claramente reconhecível, não como prova de que não existia framebuffer ou desktop antes.

## Modelo de fases

A evolução pode ser dividida em seis fases:

1. consolidação de framebuffer, 2D e desktop;
2. expansão para renderer 3D em software;
3. pressão de aplicações e integração de scanout;
4. prova VirtIO-GPU/VirGL;
5. shader pipeline programável;
6. extração de backend reutilizável com fallback para software.

As fases se sobrepõem porque o desenvolvimento ocorreu rapidamente.

## 18 de setembro de 2026 — consolidação da estrutura atual

Commit:

    13b8aa216065b85f7f50a9b1fe1bd758c7caaab8

Mensagem:

    feat:PASSO W01 — pastas do kernel e Makefile

O commit adicionou `kernel/gfx/gfx2d.c` e `gfx2d.h`, enquanto componentes existentes de font, graphics, input e desktop foram movidos ou renomeados para a estrutura atual.

A separação resultante permanece visível hoje:

    kernel/gfx/
        drawing e rendering de baixo nível

    kernel/wm/
        desktop, windows, tasks e interação

Essa fronteira permitiu que o desktop evoluísse como consumidor de primitives gráficas em vez de incorporar a implementação gráfica inteira.

## 18 de setembro — o desktop cresce sobre o 2D

No mesmo dia, outros commits ampliaram a UI:

- `0a790e6b59a4f0ddaf2a32f4f47404791f6e2b2b` — taskbar, texto, relógio e windows;
- `641c23af9d70e14d5333823f457d24693daa456a` — desktop icons;
- `2032cb8f5cb70419fb8ea088a8f66cd02a5a5a20` — explorer com pastas;
- `6fd3e42b27c8eadabb49a6bd5300720467096539` — task manager.

Esses commits são relevantes à história gráfica mesmo sendo principalmente UI.

Eles transformaram framebuffer e primitives 2D em uma plataforma de desktop com múltiplas aplicações independentes.

A conclusão histórica é que o ChrisOS não começou com abstração de GPU: o primeiro amadurecimento foi como desktop software-rendered.

## A arquitetura 2D que permaneceu

O `graphics.c` atual ainda carrega essa linhagem.

O ChrisOS desenha em back buffer, registra dirty rectangles, copia regiões alteradas para front buffer em `gfx_present()` e, no build freestanding, chama o path de hardware flush para a união das regiões dirty.

Conceitualmente:

    application/window paint
          |
          v
      software back buffer
          |
          v
       dirty regions
          |
          v
      front framebuffer
          |
          v
    optional hardware scanout flush

Isso não é um desktop compositor totalmente executado na GPU.

O path 2D CPU-owned continua sendo first-class mesmo depois de VirtIO-GPU e VirGL.

## 20 de setembro de 2026 — surge o 3D em software

A grande expansão 3D chegou no commit:

    89e3587422ab34eceb1054abf14de06717f93db6

com mensagem:

    feat: JIT, 3D, Float, etc.

Foram adicionados:

- `math3d.c`;
- `mesh.c`;
- `shade.c`;
- `tex.c`;
- `tile.c`;
- `tri.c`;
- `tri_bin.c`;
- `voxel.c`;
- `zbuf.c`;
- inicialização SSE;
- benchmark gráfico;
- suporte a slots/resources.

Não era apenas um "draw triangle".

A mudança criou os principais blocos conceituais de um pipeline 3D CPU-based.

## Modelo do rasterizer em software

O `tri.c` atual ainda contém o descendente direto daquele renderer.

Coverage de triângulo é calculada por edge functions.

Para um triângulo com orientação consistente, o teste simplificado é:

[
w_0 ge 0 land w_1 ge 0 land w_2 ge 0
]

Depth é interpolado pelos pesos barycentric e testado contra o z-buffer antes de escrever a cor.

Paths posteriores adicionam texture coordinates, normals e lighting.

Isso teve duas consequências.

Primeiro: ChrisOS possuía 3D funcional antes do backend de GPU virtual.

Segundo: quando VirGL chegou, não era necessário apagar o software renderer; ele podia permanecer como referência e fallback.

## 20 de setembro — otimização imediata

Poucos minutos depois veio:

    158d0c7a13c3986a4a13e743c19b00533baec1a2

Mensagem:

    feat: gfx optimization

Foram alterados fast-copy, mesh, shade e triangle code.

Isso evidencia os gargalos naturais de rasterização em CPU:

- framebuffer bandwidth;
- per-pixel work;
- shading;
- mesh traversal;
- clipping e redraw.

O stack gráfico já estava sendo otimizado por pressão de performance antes de qualquer GPU offload.

## Software 3D vira subsistema, não demo

O renderer foi ligado a mesh e voxel systems.

O tree atual ainda possui:

- voxel state em chunks;
- dirty-chunk rebuild;
- face lists dinâmicas;
- textures;
- z-buffered triangles;
- lighting.

Por isso a transição histórica correta não é:

    sem 3D -> VirGL

e sim:

    software 3D existente -> software + backend acelerado

## 22 de setembro — Doom pressiona a integração

O commit:

    9e26685723513e7145231b5a301dd833c74eb0c1

foi o grande "Porting Doom".

Entre os files gráficos alterados estavam `gfx_slot`, input, mesh e desktop.

O significado histórico não é uma nova arquitetura gráfica.

Doom aumentou a pressão para que a graphics stack se comportasse como plataforma:

- surfaces disponíveis a applications;
- responsive input;
- desktop integration;
- framebuffer update correto;
- compatibilidade com uma codebase externa substancial.

É um **marco de integração**, não uma substituição de backend.

## 23 de setembro — scanout do desktop se torna explícito

Commit:

    794dec7a1ae8c5a34cc61690a45f3e1a39ab7eb3

Mensagem:

    feat: scan out the desktop, install real disks, and boot RISC-V

A parte gráfica alterou `graphics.c` e hardware gates.

Essa etapa reforçou a fronteira entre:

    software composition

e:

    device scanout/presentation

A distinção permanece em `gfx_present()`.

O desktop pode continuar pintando via software mesmo que o mecanismo de apresentação seja trocado.

## Scanout e aceleração 3D são problemas diferentes

Uma graphics device pode ajudar em pelo menos duas tarefas independentes:

1. mostrar um framebuffer;
2. executar comandos 3D.

ChrisOS encontrou essas duas dimensões em momentos diferentes.

O scanout do desktop não produziu VirGL automaticamente.

E a prova VirGL não converteu instantaneamente o desktop inteiro em GPU compositor.

Essa separação continua arquiteturalmente útil.

## 25 de setembro — prova VirtIO-GPU/VirGL

O marco decisivo foi:

    a894bf7de6ef6dcfaa8fe217ce003f32914f99aa

Mensagem:

    Drive VirtIO-GPU and a native VirGL proof scene.

O commit adicionou o grande `vgpu.c` e `virgl_demo.c`.

O próprio registro do commit informa que o boot path:

- negociou VirtIO version 1 e VirGL;
- descobriu capsets;
- enviou `SUBMIT_3D` real;
- renderizou clear, triangle, depth, cube e textured cube;
- realizou readback;
- fazia fallback para software 3D em failure.

Essa foi a transição principal de "software renderer + scanout" para "device gráfico como backend de rendering".

## Por que ainda era apenas uma prova

O primeiro código VirGL ficava concentrado em um proof/demo path.

Uma prova responde:

> ChrisOS consegue negociar o device e enviar workload 3D real?

Mas não responde:

> applications comuns conseguem criar contexts, targets, meshes, textures e programs de maneira reutilizável?

A refatoração do dia seguinte resolveu exatamente essa segunda pergunta.

## Command encoding vira camada própria

O path VirGL introduziu:

    high-level draw intent
          |
          v
      VirGL command encoding
          |
          v
    VirtIO-GPU submission
          |
          v
        host renderer

Essa camada precisa gerenciar bounds, object identifiers, command-buffer capacity e protocol details.

Por isso o source atual separa `virgl_cmd.c`, `virgl_obj.c`, `gfx3d_batch.c` e `gfx3d_virgl.c`.

Backend de device não é apenas "chamar GPU draw".

## 25 de setembro — chega o shader compiler

Commit:

    4f911d18fc366815fc39b5849680b03afd3f38bb

adicionou o compiler de shaders ChrisOS.

O commit descreve:

    GLSL subset
        -> AST
        -> CSIR
        -> verification
        -> TGSI ou CPU interpretation

Entraram lexer, parser, semantic analysis, IR, executor, TGSI generation, API pública e host tests.

Foi uma mudança arquitetural importante.

Antes desse ponto, 3D existia sem linguagem programável própria.

Depois, ChrisOS passou a controlar também a fronteira source-language/IR.

## Importância histórica do shader compiler

O compiler não serviu apenas para melhorar demos.

Ele criou uma representação backend-independent.

A mesma intenção de shader passou a alimentar:

- software shader executor;
- TGSI para VirGL.

Assim o software renderer passou a servir também como semantic reference para programmable graphics.

A especificação atual `shader-spec` formaliza esse contrato.

## Mesmo dia — shaders compilados passam a dirigir VirGL

Commit:

    90e0176830b47fafd81377df33ddaba006c54ccd

conectou source compilado ao proof scene.

O commit registra que:

- triangle;
- depth;
- cube;
- texture;
- varyings;
- lighting

passaram a usar TGSI produzido pelo compiler ChrisOS.

Também registra que os world shaders do Mine Chris eram linked no mesmo boot, **sem desenhar voxels através de VirGL**.

Essa frase é historicamente importante.

Ela mostra que integração de shader language avançou antes da migração total de aplicações para o backend acelerado.

## 26 de setembro — proof vira Gfx3D reutilizável

A refatoração central foi:

    011dfb25e41ac37db483216c0364923292035d39

Mensagem:

    gfx3d: reusable VirGL backend behind the boot proof (#20)

Foram adicionados:

- `gfx3d.c`;
- `gfx3d.h`;
- `gfx3d_dev.h`;
- `gfx3d_virgl.c`;
- batching;
- VirGL object management;
- abstrações de context/target/mesh/texture/program.

Esse é o ponto em que o path acelerado deixa de ser somente um boot demo e se torna subsistema reutilizável.

## Public handles e device handles são separados

A refatoração separou:

- handles públicos Gfx3D;
- VirtIO resource IDs;
- VirGL object handles.

Essa separação é sinal de maturidade arquitetural.

Sem ela, identidade visível à application fica acoplada à identidade do protocol/device, dificultando recovery, cleanup e fallback.

O `gfx3d.c` atual continua mantendo objetos de projeto separados dos objetos de device.

## Ownership explícito

O reusable backend introduziu bounded tables para:

- contexts;
- targets;
- meshes;
- textures;
- programs.

Objetos possuem owner e generation.

O lado VirGL controla separadamente DMA-backed resources e handles.

A stack deixa de ser "proof command stream" e passa a ser resource-lifetime architecture.

Isso também torna possíveis host tests de create/destroy.

## DMA passa a fazer parte da arquitetura

O atual `gfx3d_virgl.c` documenta um persistent DMA slab para buffers e textures, além de backing dedicado para alguns render targets.

O backend rastreia slices, resources, ownership e submissions.

Essa é uma preocupação que não existia no renderer inicial:

    software renderer:
        CPU memory é diretamente o meio de rendering

    VirGL:
        guest objects precisam ser traduzidos em device resources,
        command objects e DMA ownership

Portanto a transição também foi uma mudança de memory ownership.

## Fallback para software vira policy

O atual `gfx3d_boot()` suporta:

- mock forçado;
- software forçado;
- VirGL forçado;
- auto mode.

Em auto:

- se device existe, VirGL;
- caso contrário, software.

Se VirGL é posteriormente marcado como lost e não foi explicitamente forced, o backend degrada para software.

Essa policy é descendente direta da prova de 25/09, que já fazia fallback para software em failure.

## Software não ficou obsoleto

Seria incorreto tratar software graphics como código antigo mantido por acaso.

Ele ainda fornece:

- fallback;
- comportamento host-testable;
- semantic reference para shaders;
- rendering simples para componentes não migrados;
- path independente da complexidade de VirtIO/VirGL.

A arquitetura virou multi-backend, não GPU-only.

## Cursor expõe edge cases de scanout

Depois do reusable backend, cursor behavior revelou integration bugs.

Commit:

    7c1937f70d0be58ba7f0ad66653f3bf384dbfe29

tentou garantir que o cursor resource VirtIO-GPU fosse copiado para host-visible backing antes de ser exibido.

Mais tarde no mesmo dia:

    40c69bb2c9c5466e4ef81dbe8dcfe59b0427ee0b

mudou novamente o approach:

    Draw the pointer in the scanout and keep it under the QEMU cursor.

O registro explica que constraints de input/DMA e visibility exigiram software cursor painting.

Esse episódio mostra que "hardware cursor" não é capability binária.

Depende de:

- resource format;
- DMA visibility;
- scanout transitions;
- input device;
- comportamento do hypervisor.

## Path 2D atual

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, o desktop continua sendo pintado pela software graphics layer.

`gfx_present()`:

1. percorre dirty regions;
2. copia changed lines do back buffer para front buffer;
3. une região para hardware notification;
4. chama `hw_gpu_flush_rect()` no freestanding build;
5. limpa a dirty list.

Essa é a arquitetura de desktop sobrevivente após a chegada de VirGL.

VirGL não substituiu o compositor 2D básico.

## Modelo Gfx3D atual

A camada 3D possui pools para:

- contexts;
- targets;
- meshes;
- textures;
- programs.

Backend selecionado pode ser:

    software
    VirGL
    mock

A API de alto nível não precisa saber como cada backend representa recursos.

Isso também permite backend loss e substituição por mock em tests.

## Device model VirGL atual

O backend atual rastreia device contexts, surfaces, resources, DMA slices, object pools e command batches.

O source separa explicitamente:

- VirtIO resource IDs;
- VirGL object handles;
- ChrisOS public handles.

Submissions são síncronas no design atual.

Há frame fence registrado, mas staging memory não é reutilizada antes do retorno do submit.

É um ownership model mais forte que o proof original.

## Shader model atual

O pipeline continua dividido:

    shader source
        |
        v
    ChrisOS shader IR
       /       \
      v         v
 software      TGSI
 executor      VirGL

Compiler cache, verifier, linker e serialized CSIR cresceram em torno dessa estrutura.

Historicamente, a decisão foi manter semantic layer própria em vez de expor TGSI diretamente a applications.

TGSI permanece backend format.

## Mine Chris como fronteira de transição

Mine Chris ajuda a entender a evolução.

O voxel renderer em software existia antes de VirGL.

Quando shaders compilados foram conectados ao proof VirGL, o próprio commit registrou que world shaders eram linked, mas voxels ainda não eram desenhados via VirGL.

O tree atual continua mantendo software voxel/triangle stack ao lado de Gfx3D.

Logo Mine Chris não é evidência de que toda graphics stack virou hardware-accelerated em 25–26 de setembro.

É uma boundary application de eras mistas.

## A arquitetura não evoluiu linearmente

A narrativa simplificada seria:

    framebuffer -> software 3D -> GPU -> shaders

A história real é:

    framebuffer/desktop
          |
          +---- software 3D ------+
          |                       |
          +---- scanout ----------+---- sistema atual
                                  |
                           VirtIO-GPU/VirGL
                                  |
                            shader compiler
                                  |
                          reusable Gfx3D API

Software paths foram preservados enquanto paths acelerados eram adicionados.

Algumas applications demoraram mais para migrar que os subsistemas inferiores.

## A qualidade da evidência também evoluiu

A história gráfica é também uma história da evidência.

Estágios iniciais dependiam mais de resultado visível.

Depois surgiram:

- host-testable shader compilation;
- IR verification;
- VirGL command tests;
- resource-lifetime checks;
- matrix ABI comparisons;
- backend fallback;
- QEMU graphics gates;
- specifications atuais.

Uma capability se torna muito mais confiável quando pode ser verificada sem depender apenas de inspeção visual.

## Milestones históricos

| Data | Commit | Significado |
|---|---|---|
| 2026-09-18 | `13b8aa2` | consolida gfx/wm atuais; Gfx2D é adicionado |
| 2026-09-18 | commits W03–W09 | desktop se torna consumidor mais rico de 2D |
| 2026-09-20 | `89e3587` | software 3D/voxel/z-buffer amplo |
| 2026-09-20 | `158d0c7` | optimization pass imediato |
| 2026-09-22 | `9e26685` | Doom aumenta pressão de integração |
| 2026-09-23 | `794dec7` | scanout do desktop é reforçado |
| 2026-09-25 | `a894bf7` | proof VirtIO-GPU/VirGL com submits 3D reais |
| 2026-09-25 | `4f911d1` | GLSL-subset compiler e CSIR |
| 2026-09-25 | `90e0176` | TGSI gerado pelo compiler dirige proofs |
| 2026-09-26 | `011dfb2` | Gfx3D/VirGL reutilizável |
| 2026-09-26 | `7c1937f`, `40c69bb` | cursor/scanout corrigidos |

A tabela é um mapa, não substitui os diffs.

## Lições arquiteturais

### Preserve um software reference path

O software renderer permitiu desenvolver 3D antes do device backend e continua útil depois.

### Separe presentation de rendering

Framebuffer scanout e aceleração 3D evoluíram independentemente.

### Esconda formato de transport atrás de backend

Applications usam Gfx3D e shader programs, não VirtIO descriptors ou TGSI bruto.

### Torne ownership explícito antes de escalar objetos

A abstraction reusable surgiu depois da prova técnica, quando resource lifetime passou a importar.

### Testes mudam o nível de maturidade

Host tests de shader e de VirGL objects fortalecem muito mais uma claim que uma demo visual isolada.

## Suposições históricas superadas

Snapshots antigos podem induzir erro se lidos sem revisão.

Afirmações que já foram verdadeiras ou parcialmente verdadeiras:

- graphics é software-only;
- VirtIO-GPU serve apenas para scanout;
- VirGL só existe como boot demo;
- shaders são backend strings hard-coded;
- Gfx3D não tem fallback;
- hardware cursor é sempre o pointer visível;
- Mine Chris usar shaders implica voxel rendering via VirGL.

Documentação atual deve usar source atual; este capítulo preserva quando as interpretações antigas faziam sentido.

## Resumo da arquitetura atual

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`:

    desktop/apps
        |
        +--> software 2D compositor
        |       |
        |       +--> framebuffer/scanout flush
        |
        +--> Gfx3D
                |
                +--> software backend
                |
                +--> VirGL backend
                        |
                        +--> VirtIO-GPU

    shader source
        |
        v
    ChrisOS shader IR
       /       \
      v         v
 software      TGSI -> VirGL

Esse é o endpoint da cronologia, não a arquitetura presente em todos os commits históricos.

## Nota de revisão

Este capítulo foi reconciliado contra a revisão atual `e05a17fd76333114a3fb5c2452f38ca747d4ac56` e os milestones Git listados acima.

Mudanças gráficas futuras só devem ampliar esta timeline quando alterarem uma boundary arquitetural real: ownership de backend, separação rendering/presentation, shader contract, resource model, recovery policy ou validation evidence.
