---
id: software-3d
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/gfx/math3d.c
  - kernel/gfx/tri.c
  - kernel/gfx/scene.c
  - kernel/gfx/gfx3d_ctx.c
symbols: []
depends_on:
  - pixels-framebuffer
related:
  - virtio-gpu-virgl
  - shaders-csir
---

# 3D por software: transforms, rasterização e depth

## Pipeline geométrica

```text
model
  ↓
world
  ↓ view
camera
  ↓ projection
clip
  ↓ divide / viewport
screen
  ↓ rasterização
pixels
```

Coordenadas homogêneas permitem representar translation e perspective com matrizes. Clipping precisa acontecer no espaço correto antes de divisões problemáticas.

## Triângulos

Barycentric coordinates determinam cobertura e interpolação:

```text
λ0 + λ1 + λ2 = 1
P = λ0 V0 + λ1 V1 + λ2 V2
```

Depth, cor e varyings podem ser interpolados. Texturas sob perspectiva exigem interpolação perspective-correct.

## Z-buffer

Cada pixel guarda depth mais próximo. Fragmento novo compara e atualiza conforme depth function. Paralelização precisa impedir races de color/depth no mesmo tile.

## Renderer do ChrisOS

Software 3D continua como referência/fallback. `math3d.c` implementa matrizes; `tri.c` e unidades relacionadas rasterizam; `scene.c` organiza cenas. Mine Chris ainda utiliza esse caminho na revisão documentada.

## Convenção de matrizes

`Mat4f` usa armazenamento row-major e vetores coluna. GLSL/CSIR usam layout column-major para uniforms, então `mat4f_to_glsl` converte antes do upload.

Erros de convenção podem produzir transformações plausíveis porém erradas; por isso testes de ABI comparam CPU e shader.

## Software como oracle

Renderer por CPU fornece referência independente de GPU, testes determinísticos e fallback. Desempenho máximo e função de oracle são objetivos diferentes.
