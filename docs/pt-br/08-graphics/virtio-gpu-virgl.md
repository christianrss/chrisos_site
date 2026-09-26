---
id: virtio-gpu-virgl
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/gfx/hwgate.c
  - kernel/gfx/gfx3d.c
  - kernel/gfx/gfx3d_virgl.c
  - kernel/gfx/virgl_cmd.c
  - kernel/gfx/virgl_obj.c
  - docs/VIRTIO_GPU.md
  - docs/VIRGL.md
  - docs/GFX3D.md
symbols: []
depends_on:
  - buses-mmio-dma
  - software-3d
related:
  - shaders-csir
---

# VirtIO-GPU e VirGL

## Duas camadas

VirtIO-GPU fornece device gráfico paravirtual. Operações 2D/scanout existem sem VirGL.

VirGL adiciona command stream 3D: guest envia comandos, QEMU GL encaminha a virglrenderer e este usa OpenGL do host.

```text
Gfx3D
  ↓
encoder VirGL
  ↓
VirtIO-GPU SUBMIT_3D
  ↓
QEMU
  ↓
virglrenderer
  ↓
host OpenGL
```

Isso não é driver físico Intel/AMD/NVIDIA.

## Features e virtqueues

Guest negocia apenas features compreendidas e configura filas/estruturas. ChrisOS pode negociar VIRGL e context-init quando disponível no contrato suportado.

## Resources e ownership

Resource IDs VirtIO e handles VirGL são namespaces diferentes. Lifecycle correto exige create, attach, use, detach e destroy. Stress repetido é mais significativo que uma cena que funciona uma vez.

## Backend Gfx3D

A main recente extraiu context, target, mesh, texture e program reutilizáveis do boot proof. `gfx3d_virgl.c` implementa backend VirGL atrás da API neutra.

Isso cria fronteira para scenes usarem backends sem conhecer opcodes.

## Command buffers

`virgl_cmd.c` monta dwords e valida capacidade. Overflow precisa flush/continue sem escrever fora do buffer.

## Readback e scanout

`TRANSFER_FROM_HOST_3D` traz pixels para validação CPU. Scanout pode apontar para target renderizado e depois restaurar o desktop 2D.

## Estado atual

Documentação do projeto registra gates de lifecycle, clear, triangle, depth, cube, texture e present. Mine Chris ainda chama software scene; VirGL boot proof não significa aceleração do jogo.

## Evidência

Host test valida lógica local; QEMU VirGL valida device/virglrenderer. llvmpipe continua sendo prova QEMU, não hardware GPU físico.
