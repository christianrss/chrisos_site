---
id: desktop-applications
lang: pt-br
type: technical-chapter
volume: 11-desktop
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/wm/desktop.c
  - kernel/wm/task.c
  - kernel/wm/ui.c
  - APPS/EDITOR/EDITOR.CC
  - APPS/SHELL/SHELL.CC
  - APPS/EXPLORER/EXPLORER.CC
symbols: []
depends_on:
  - pixels-framebuffer
  - chrisc-clvm
related:
  - kernel-model
---

# Desktop, janelas e aplicações

## Desktop como integração

Desktop gráfico depende simultaneamente de timer/input, gráficos, lifecycle de tasks, filesystem, runtime e ownership. Por isso open/close repetido de aplicações é workload de integração mais forte que screenshot estático.

## Estado de janela

Task/window guarda geometria, lifecycle, focus/z-order e backing. `task.c` usa tabela finita; slot reutilizado precisa estar completamente limpo.

## Composição

`ui.c` e primitives desenham background, taskbar, ícones, janelas e cursor pelo caminho comum. A arquitetura atual não é um compositor GPU com surfaces independentes por janela; é um modelo menor coerente com o estágio do projeto.

## Focus e input

Keyboard/mouse precisam chegar à task correta. Focus e capture fazem parte do contrato. Fechar owner não pode deixar captura global presa.

## Aplicações ChrisC

Editor, shell, explorer e task manager exercitam interfaces públicas do runtime. Editor é particularmente relevante para self-hosting porque conecta fonte, filesystem, compile/run e debugger.

## Contenção

Fault de processo nativo e fault CLVM são contidos por mecanismos diferentes. Desktop precisa lidar com ambos sem assumir um único modelo de processo.

## Responsividade

I/O longo ou compilação no path interativo produz latência visível mesmo sem falha lógica. Avaliação de desktop precisa de latência/frame timing além de throughput.

## Aplicações como testes

Apps complexas exercitam filesystem, renderização, input, VM memory, ABI, lifecycle de janelas e cleanup em combinações que testes unitários não cobrem.
