---
id: desktop-applications
lang: pt-br
type: technical-chapter
volume: 11-desktop
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/wm/desktop.c
  - kernel/wm/task.c
  - kernel/wm/task.h
  - kernel/wm/ui.c
  - kernel/tools/app_window.c
  - compiler/lang_pipeline.c
  - compiler/lang_pipeline.h
  - kernel/lang/clvm_sys.c
  - APPS/DESKTOP/DESKTOP.CC
  - APPS/TASKBAR/TASKBAR.CC
  - APPS/EDITOR/EDITOR.CC
  - APPS/SHELL/SHELL.CC
  - APPS/EXPLORER/EXPLORER.CC
  - LIB/WIN.CC
  - LIB/UI.CC
  - LIB/APP.CC
  - tools/test_task_window.c
symbols:
  - desktop_init
  - desktop_boot_apps
  - desktop_frame
  - task_spawn
  - task_close
  - task_raise
  - task_run_all
  - task_focus_at
  - app_window_open
  - lang_bind_task
  - lang_slot_push_key
  - lang_slot_push_text
  - lang_slot_request_close
depends_on:
  - pixels-framebuffer
  - chrisc-clvm
related:
  - window-manager
  - input-routing
  - chrisfs
  - chriseditor
  - chrisshell
  - file-manager
---

# Desktop, janelas e aplicações

## Escopo

O desktop do ChrisOS não é uma única função gráfica monolítica. A arquitetura atual é híbrida: o kernel mantém a infraestrutura autoritativa de tasks/janelas, enquanto aplicações CLVM implementam lógica de aplicação e também componentes visíveis do próprio desktop.

O kernel controla tabela de tasks, z-order, foco, polling dos dispositivos, roteamento de teclado/texto, posicionamento de janelas e o blit final para o caminho gráfico do sistema. Programas CLVM desenham em superfícies próprias. O wallpaper/launcher e a taskbar são aplicações CLVM iniciadas durante o boot do desktop, enquanto o kernel ainda fornece chrome de janela, pintura de fallback e primitivas comuns.

Essa divisão é fundamental para ownership. Fechar uma `Task` não é exatamente o mesmo que destruir um slot CLVM. Desenhar na superfície da aplicação não equivale a escrever diretamente no framebuffer físico. Eventos de teclado/texto usam filas por slot; o ponteiro é predominantemente consultado por polling.

## Camadas arquiteturais

O caminho simplificado é:

```text
USB tablet / xHCI HID / PS/2
          |
          v
      input subsystem
          |
          v
   desktop_frame()
          |
          +--> foco / z-order
          +--> key/text -> filas do slot CLVM
          |
          v
      tabela Task (32)
          |
          v
 runner da aplicação / surface
          |
          v
 blit kernel + chrome da janela
          |
          v
 graphics dirty/present
```

Do lado da aplicação:

```text
fonte ChrisC
   -> compilador / imagem CLVM
   -> LangSlot
   -> contexto gráfico CLVM
   -> pixels/front buffer
   -> vínculo TASK_APP
   -> blit do desktop
```

O capítulo de window manager detalha mecânica das janelas; aqui o foco é a integração dessa mecânica com runtime e aplicações.

## Inicialização do desktop

`desktop_init` reinicializa o sistema de tasks, configura input com as dimensões atuais do framebuffer, ativa ponteiro absoluto quando o USB tablet está disponível e limpa o alvo gráfico para a cor do desktop.

`task_system_init` limpa todos os slots, reinicia o contador de z e define foco como -1.

Assim, o desktop parte de estado conhecido e não herda geometria, foco ou lifecycle de uma execução anterior.

## Boot das aplicações do desktop

`desktop_boot_apps` tenta carregar `LIB/WIN.CLS` e depois inicia:

- `APPS/DESKTOP/DESKTOP.CLV`;
- `APPS/TASKBAR/TASKBAR.CLV`.

O helper `boot_one` primeiro sonda o arquivo CLV compilado. Se existir, tenta executá-lo. Se estiver ausente ou inutilizável, compila o `.LST` correspondente e então executa o CLV resultante.

Esse comportamento é relevante para a direção de self-hosting: o boot pode consumir binários já produzidos, mas possui fallback compile-and-run.

Flags opcionais em ChrisFS podem iniciar Doom ou World como smoke workloads. Elas não fazem parte dos componentes obrigatórios do desktop.

## Desktop e taskbar como aplicações CLVM

`APPS/DESKTOP/DESKTOP.CC` cria uma superfície do tamanho do display, posiciona-a na origem e mantém um loop que desenha background e ícones.

O launcher atual expõe Shell, Files, Edit, Tasks, Ball, Doom, Preferences e Mine Chris. Uma borda de clique chama `app_launch`, wrapper simples sobre `app_spawn`.

`APPS/TASKBAR/TASKBAR.CC` cria uma superfície de 40 pixels na borda inferior, oferece botões de lançamento e um relógio MM:SS calculado a partir de ticks.

Portanto, parte importante da interface visível já executa pelo mesmo runtime usado pelas demais aplicações, em vez de existir somente como desenho privilegiado em C.

## Representação de Task

O kernel define `TASK_MAX = 32`. Cada `Task` possui:

- ID e flag active;
- valor de z;
- tipo;
- retângulo;
- `WindowState`;
- callback runner;
- título de 24 caracteres;
- union com estado específico do tipo.

Os tipos atuais incluem Shell, Ball, Editor, Explorer, Task Manager e `TASK_APP`.

Uma aplicação gráfica CLVM normalmente aparece como `TASK_APP`, e o ID do slot do runtime é armazenado em `task->state.app.lang_slot`.

## Criação e reutilização de slots

`task_spawn` recusa tipo inválido, runner nulo e geometria não positiva. Depois procura linearmente o primeiro slot inativo.

Antes de reutilizar o slot, `clear_task` zera toda a estrutura, preserva apenas o ID e volta o tipo a `TASK_NONE`. A criação então configura modo Normal, retângulo de restore, callback, novo z e estado inicial específico do tipo.

A task recém-criada se torna a task focada.

Essa limpeza impede que um slot reutilizado herde dragging, título, lang slot ou estado de outra aplicação.

## Vínculo entre LangSlot e Task

Quando um programa CLVM inicia, o pipeline de linguagem prepara um `LangSlot` e chama `app_window_open`.

A função primeiro procura se o mesmo slot já possui `TASK_APP`. Nesse caso apenas atualiza título e traz a janela para frente.

Para uma janela nova, lê largura/altura do contexto gráfico, escolhe tamanho/posição, cria `TASK_APP`, grava o lang slot na task e chama `lang_bind_task(slot, task_id)`.

Se `task_spawn` falhar, o slot CLVM é encerrado em vez de permanecer como aplicação ativa sem owner no desktop.

O vínculo é explícito:

```text
Task.state.app.lang_slot  <-->  LangSlot.task_id
```

## Z-order

Task nova ou elevada recebe `z = g_next_z++`.

`task_id_at(x,y)` percorre as tasks ativas e não minimizadas que contêm o ponto e escolhe o maior z.

`task_run_all` desenha do fundo para a frente. Em cada passo procura a menor task com z acima do último valor emitido e executa seu runner.

Com limite de 32 tasks esse algoritmo permanece pequeno, mas o pior caso é O(TASK_MAX²) por frame porque há scans repetidos.

A escolha privilegia simplicidade em vez de manter uma coleção ordenada separada.

## Foco

Em uma borda de clique esquerdo, `desktop_frame` chama `task_focus_at`.

Para janela comum, focar também chama raise, gerando novo z. Uma task que cobre o display como wallpaper é tratada especialmente para não saltar acima das janelas comuns de forma inadequada.

Fechar ou minimizar a task focada limpa o foco.

Assim, foco influencia tanto input quanto stacking.

## Modos de janela

Os modos são Normal, Minimized e Maximized.

Minimizar apaga o frame anterior, grava o modo, cancela dragging e remove foco quando necessário. Tasks minimizadas não entram em `task_run_all`.

Raise de task minimizada volta o modo para Normal e marca a região para redraw.

Maximize salva o retângulo anterior em `window.restore` e instala novos bounds. Restore recupera esse retângulo.

Move e resize apagam a área antiga, alteram a geometria e marcam a região nova como dirty.

Lifecycle de janela está, portanto, ligado ao modelo de damage do renderer.

## Ciclo de um frame

`desktop_frame(ticks)` executa:

1. poll do USB tablet;
2. poll de xHCI HID;
3. poll do mouse PS/2;
4. snapshot do ponteiro;
5. atualização de foco numa borda do botão esquerdo;
6. resolução do slot da aplicação focada;
7. drain dos eventos de input;
8. envio de key/text para o slot;
9. remoção visual do cursor;
10. execução das tasks visíveis em z-order;
11. desenho do cursor.

Essa ordem centraliza o roteamento antes da execução das aplicações e evita que a superfície redesenhada incorpore uma imagem antiga do cursor.

## Filas de teclado e texto

O runtime possui `LANG_VM_SLOTS = 16`. Cada slot mantém duas filas circulares independentes, key e text, com `LANG_EVQ = 8`.

`lang_slot_push_key` e `lang_slot_push_text` calculam o índice pela soma de read-index e count módulo 8. O consumo avança o índice de leitura pelo mesmo módulo.

Se a fila já possui oito eventos, o evento novo é descartado.

Esse é o comportamento real de backpressure. Não há expansão dinâmica, bloqueio do desktop ou substituição do evento mais antigo.

## Restrições de roteamento

Eventos de teclado/texto são encaminhados somente quando a task focada é `TASK_APP` e não está em dragging ou resizing.

Quando não existe slot elegível, `desktop_frame` ainda drena a fila global, mas não entrega esses eventos a uma aplicação.

O ponteiro usa outro modelo. Aplicações CLVM consultam posição/botões pela interface de sistema, enquanto `LIB/WIN.CC` e o código de janela executam hit testing, drag e resize.

Portanto não existe uma única fila universal para todos os tipos de input.

## Superfícies das aplicações

Cada lang slot possui contexto gráfico próprio. A aplicação desenha nessa memória, não diretamente no framebuffer do sistema.

O runtime pode publicar um front buffer. `lang_slot_publish` cria ou redimensiona um buffer kernel e copia os pixels atuais. `lang_slot_pixels` prefere esse front buffer quando dimensões coincidem; caso contrário devolve os pixels correntes do contexto.

Depois, o runner da task realiza o blit para a apresentação do desktop.

Isso cria uma fronteira explícita entre memória de desenho da aplicação e composição/apresentação do sistema.

## UI versus superfícies de jogos

`app_run` diferencia superfícies classificadas como jogo de aplicações UI comuns.

Jogos podem ser escalados para um client rectangle abaixo de chrome controlado pelo kernel. Assim resolução lógica e tamanho da janela não precisam coincidir.

Aplicações UI são mantidas em relação 1:1 com o frame da task. A superfície é blitada na posição da janela e o kernel preserva título/bordas e convenções comuns.

Superfícies fullscreen e taskbar-like recebem tratamentos especiais para manter as convenções do desktop.

Ainda é um modelo muito menor que um compositor GPU moderno, mas a separação entre superfície lógica e placement já existe.

## Fechamento e teardown

Fechar aplicação envolve dois owners.

A task pertence ao window manager. O `LangSlot` pertence ao runtime.

Nos caminhos de close da janela, o código fecha a task e chama `lang_slot_request_close`, marcando o slot como dying para teardown posterior do runtime.

No sentido inverso, `app_run` fecha a task se detectar que o slot já não está usado.

O syscall CLVM de surface close também conecta os dois lados.

Isso evita tanto uma VM morta com janela órfã quanto uma janela fechada deixando um programa ativo sem apresentação.

## Contenção de falhas

Fault de aplicação CLVM pertence principalmente ao slot/VM. Fault de processo nativo usa o mecanismo de processos nativos documentado nos capítulos do kernel.

A tabela `Task` não é uma tabela universal de processos.

O runner consulta `lang_slot_used` antes de blit; uma janela não é tratada como prova de que o contexto de execução ainda existe.

Por isso análise de contenção do desktop precisa combinar lifetime de Task, LangSlot, processo e recursos gráficos.

## Custos algorítmicos

| Operação | Estrutura | Custo |
|---|---|---|
| spawn | scan dos 32 slots | O(TASK_MAX) |
| hit test da janela superior | scan total | O(TASK_MAX) |
| task_count | scan total | O(TASK_MAX) |
| task_iter(n) | scan dos slots | O(TASK_MAX) |
| render em z-order | seleções repetidas | O(TASK_MAX²) no pior caso |
| push/take key ou text | ring fixo | O(1) |
| close | acesso indexado + zeragem de Task | O(sizeof(Task)) |
| ícone do launcher | lista fixa atual | O(1) prático |

Os limites atuais tornam scans lineares aceitáveis; centenas de janelas exigiriam estruturas diferentes.

## Fronteiras de segurança

Kernel controla foco e vínculo Task↔slot. Aplicações CLVM não modificam diretamente a tabela kernel de tasks.

Syscalls do runtime mediam placement, resize, close e lançamento de aplicações. O pipeline também possui capability flags para programas de driver; aplicações comuns usam a interface normal.

Ainda assim, CLVM isolation não deve ser descrita como política GUI multiusuário endurecida. Quotas, flooding de eventos, visibilidade global do ponteiro e capability policy mais granular continuam sendo áreas de evolução.

## Responsividade

O frame do desktop coordena vários subsistemas. Execução CLVM longa, filesystem lento ou renderização excessiva podem aparecer como latência de input/frame mesmo quando o kernel continua funcional.

O runtime possui budgets diferentes para workloads comuns, UI e jogos, mas responsividade end-to-end depende da quantidade de trabalho realizada entre apresentações.

Avaliação deve incluir frame percentiles, input-to-paint latency e stress repetido de lifecycle, não apenas throughput de pixels.

## Aplicações como workloads de integração

As aplicações exercitam combinações distintas:

- Shell: comandos, launch e serviços do runtime;
- Explorer: readdir, paths e handoff para outras aplicações;
- ChrisEditor: filesystem, texto, compile/run/debug;
- Task Manager: introspecção e encerramento;
- Ball: animação e timing;
- Doom/Mine Chris: render/input mais pesado.

Nenhuma aplicação isolada prova toda a pilha, mas o conjunto expõe defeitos de interface que testes unitários separados podem não revelar.

## Evidência executável

`tools/test_task_window.c` fornece regressão host do núcleo de task/window.

Ele verifica:

- spawn e modo Normal inicial;
- task minimizada não executa;
- raise restaura uma task minimizada;
- maximize/restore preservam geometria;
- move/resize atualizam frame e registram damage;
- hit testing escolhe a janela sobreposta de maior z;
- 1.000 ciclos spawn/close reutilizam slots sem aumentar a contagem de tasks vivas.

Essa evidência é forte para lifecycle de Task e mecânica de janela. Ela não executa o desktop CLVM completo, HID real, filas de eventos por slot ou apresentação final.

Esses caminhos ainda exigem gates em QEMU/hardware.

## Limitações atuais

A tabela de tasks possui 32 entradas; o runtime CLVM possui 16 slots. Filas de eventos comportam oito keys e oito textos por slot e descartam eventos novos quando cheias.

Render em z-order usa scans repetidos. O valor de z cresce monotonicamente sem uma estrutura ordenada separada. Layout de launcher/taskbar é majoritariamente fixo. Não existe compositor GPU por surface, multi-seat ou política de desktop multiusuário endurecida.

São limites da implementação atual do ChrisOS, não limites de desktops em geral.

## Reconciliação de revisão

A página foi reconciliada com a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Os arquivos de implementação descritos permanecem compatíveis com o baseline anterior; a atualização de revisão registra inspeção da fonte, não uma capacidade inferida.

## Mapa de fonte

Integração kernel fica em `kernel/wm/desktop.c`; estado de task/janela em `kernel/wm/task.c` e `task.h`; desenho UI comum em `kernel/wm/ui.c`.

A ponte para aplicações CLVM está em `kernel/tools/app_window.c`, `compiler/lang_pipeline.c` e `kernel/lang/clvm_sys.c`. Desktop e taskbar visíveis vivem em `APPS/DESKTOP/DESKTOP.CC` e `APPS/TASKBAR/TASKBAR.CC`. Helpers de janela/UI/launch ficam em `LIB/`.
