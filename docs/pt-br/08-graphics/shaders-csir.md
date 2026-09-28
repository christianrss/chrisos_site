---
id: shaders-csir
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/gfx/shader/sh_lex.c
  - kernel/gfx/shader/sh_parse.c
  - kernel/gfx/shader/sh_sem.c
  - kernel/gfx/shader/sh_ir.c
  - kernel/gfx/shader/sh_tgsi.c
  - kernel/gfx/shader/sh_exec.c
  - kernel/gfx/shader/sh_api.c
symbols: []
depends_on:
  - compiler-pipeline
  - software-3d
  - virtio-gpu-virgl
related:
  - chrisc-clvm
---

# Shaders programáveis, subset GLSL e CSIR

## Pipeline programável

Renderer fixed-function oferece operações predefinidas; pipeline programável executa programas de vertex/fragment.

ChrisOS implementa subset definido de GLSL, não compatibilidade total.

## Frontend

Compiler possui lexer, recursive-descent parser, AST e semantic analysis com tipos e interfaces de shader. Diagnostics carregam posição de fonte.

## CSIR

```text
subset GLSL
  ↓
AST / semântica
  ↓
CSIR
  ├── TGSI → VirGL
  └── interpreter → software
```

IR independente impede que semântica da linguagem fique presa a strings hardcoded do driver.

## Interfaces e tipos

Stages usam inputs/outputs, uniforms, samplers e temps. Link verifica correspondência de varyings. Matrizes seguem semântica column-major do GLSL e exigem conversão coerente da representação CPU.

## Control flow

O subset pode restringir loops e funções deliberadamente. Constructs fora do suporte precisam falhar explicitamente, não produzir shader errado silenciosamente.

## TGSI e backend software

VirGL consome TGSI emitido de CSIR verificado. `sh_exec.c` interpreta o mesmo CSIR. Dois backends sobre uma IR comum permitem testes diferenciais.

## API ChrisC

Funções de linguagem criam/dropam shaders/programs, linkam, consultam diagnostics e atualizam uniforms/samplers. Handles pertencem ao slot e são destruídos no teardown.

## Mine Chris

Shaders de world já participam de proof draw VirGL, mas voxel renderer do jogo continua no caminho software. Compiler de shader pronto e migração do jogo são milestones diferentes.
