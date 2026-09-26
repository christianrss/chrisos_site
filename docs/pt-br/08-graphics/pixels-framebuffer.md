---
id: pixels-framebuffer
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/gfx/graphics.c
  - kernel/gfx/gfx2d.c
  - kernel/wm/ui.c
symbols: []
depends_on:
  - buses-mmio-dma
related:
  - software-3d
  - virtio-gpu-virgl
---

# Pixels, framebuffer, scanout e composição

## Representação

Pixel é uma amostra de cor em uma posição. Software usa canais inteiros como RGB e às vezes alpha. Formatos ARGB, RGBA e XRGB são contratos diferentes.

## Framebuffer linear

```text
address(x,y) = base + y * pitch + x * bytes_per_pixel
```

Pitch é distância em bytes entre inícios de linhas e pode incluir padding. `gfx_init` recebe address, width, height e pitch do boot info.

## Backbuffer e dirty rectangles

Backbuffer permite construir imagem fora da área visível e apresentar depois. Dirty tracking limita cópia às regiões alteradas.

O algoritmo precisa ser conservador: perder uma região modificada deixa pixels antigos; copiar região extra custa apenas desempenho.

## Scanout

Scanout é o mecanismo que lê buffer para exibição. Framebuffer de firmware e recurso VirtIO-GPU são mecanismos distintos. Aplicações não devem conhecer virtqueues para desenhar retângulo.

## Composição

Compositor combina background, windows, decorações, cursor e surfaces. O ChrisOS atual ainda usa caminho de tela comum em vez de um grafo completo de surfaces GPU independentes.

## Cursor e input

Coordenadas de mouse e recurso exibido precisam concordar. O projeto possui caminhos de cursor VirtIO-GPU e fallback software.

## 2D continua fundamental

Mesmo com VirGL, desktop, diagnóstico e recovery precisam de caminho 2D simples e confiável.
