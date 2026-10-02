---
id: window-manager
lang: pt-br
type: technical-chapter
volume: 11-desktop
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/wm/task.h
  - kernel/wm/task.c
  - kernel/wm/ui.h
  - kernel/wm/ui.c
  - kernel/wm/desktop.c
  - kernel/tools/app_window.h
  - kernel/tools/app_window.c
  - compiler/lang_pipeline.c
  - kernel/lang/clvm_sys.c
  - LIB/WIN.CC
  - APPS/TASKBAR/TASKBAR.CC
  - tools/test_chrisc_apps.c
symbols:
  - task_system_init
  - task_spawn
  - task_close
  - task_raise
  - task_move
  - task_resize
  - task_minimize
  - task_maximize
  - task_restore
  - task_id_at
  - task_focus_at
  - task_focused_id
  - task_run_all
  - app_window_open
  - desktop_frame
depends_on:
  - desktop-applications
  - gfx2d
  - desktop-compositor
related:
  - input-routing
  - chriseditor
  - chrisshell
  - file-manager
  - clvm-syscalls
---

# Window manager e modelo de tasks

## Escopo

ChrisOS usa um modelo compacto de task/window dentro do kernel para composição do desktop.

A implementação não é um window server privilegiado separado. Metadata de janelas, focus, z-order, native task runners e surfaces de aplicações CLVM são coordenados dentro do kernel e do language runtime.

O sistema é dividido em duas camadas:

1. **estado kernel de window/task** em `kernel/wm/task.c`;
2. **comportamento de chrome das aplicações** em `kernel/tools/app_window.c` e `LIB/WIN.CC`.

A distinção é essencial.

O kernel possui task identity, active state, frame geometry, focus, z-order, minimize/maximize mode e execution ordering. Aplicações ChrisC podem desenhar o próprio chrome e solicitar operações de surface via CLVM syscalls.

![Fluxo do window manager](../../assets/diagrams/window-manager-pt-br.svg)

## Task table

Kernel mantém uma tabela global fixa:

    Task g_tasks[TASK_MAX]

com:

    TASK_MAX = 32

Uma Task contém ID, active flag, z de 32 bits, TaskType, TaskRect, WindowState, runner callback, title limitado e union de estado específica do tipo.

Task ID é o índice da tabela.

IDs permanecem estáveis enquanto a entry está ativa, mas podem ser reutilizados depois do close.

Não há object Task dinamicamente alocado por janela.

## Geometry

TaskRect contém:

    x
    y
    width
    body_height

O nome `body_height` é histórico.

Em application windows, vários paths usam o valor como altura total da surface/window, inclusive chrome.

Para kernel game chrome, client area começa abaixo de:

    APP_CHROME_H = 20

e sua altura é:

    frame.body_height - APP_CHROME_H

Código que usa TaskRect deve seguir a convention do owning path e não assumir que `body_height` sempre exclui title chrome.

## Window state

WindowState guarda interaction/lifecycle state: dragging, offsets de drag, resizing, mouse/start frame de resize, mode e restore frame.

Modes:

    TASK_WINDOW_NORMAL
    TASK_WINDOW_MINIMIZED
    TASK_WINDOW_MAXIMIZED

`restore` preserva o frame anterior usado ao sair de maximized.

Drag/resize state é per-task.

## Initialization

`task_system_init` limpa as 32 task entries e inicializa:

    g_next_z = 1
    g_focused_id = -1

`desktop_init` chama a inicialização antes do input setup e desktop clear.

Aplicações desktop são iniciadas separadamente por `desktop_boot_apps`, incluindo desktop e taskbar CLVM, além de workloads opcionais.

## Spawning

`task_spawn` exige TaskType não nulo, TaskRunner válido e dimensões positivas.

Procura o primeiro slot inativo e falha com -1 quando os 32 estão ocupados.

Spawn bem-sucedido limpa a entry, ativa task, instala type/frame/runner, configura NORMAL, salva restore frame, recebe novo z, inicializa defaults específicos e vira focused task.

Assim novas janelas entram logicamente no topo.

## Z-order

A fonte de ordenação é:

    static uint32_t g_next_z

Spawn/raise executam:

    task->z = g_next_z++

Maior z significa janela acima.

Não existe linked z-list.

`task_id_at` encontra o top task em um ponto varrendo a tabela e escolhendo maior z.

`task_run_all` desenha na ordem oposta, encontrando sucessivamente o menor z maior que o já emitido, produzindo back-to-front rendering.

## Rendering complexity

Com no máximo 32 tasks, `task_run_all` usa buscas repetidas pela tabela inteira.

Worst case é O(TASK_MAX²) por frame.

Como TASK_MAX é fixo em 32, o bound prático é pequeno. Um desktop maior normalmente usaria ordered list/tree ou array previamente ordenado.

## Z-counter overflow

O contador z é uint32 monotônico sem renormalização.

Após wraparound, uma task recém-raised pode receber z baixo e deixar de aparecer como top window.

É improvável em uso normal, mas é correctness boundary. Uma implementação robusta deve renormalizar active tasks preservando ordem antes do overflow.

## Focus

Focus global é um único integer:

    g_focused_id

Somente uma task fica focused.

`task_is_focused` exige task válida/ativa e ID igual a g_focused_id.

Spawn e raise comuns focam a task, acoplando fortemente focus e z-order.

## Hit testing

`task_id_at(x,y)` varre todas tasks.

Participam apenas active, não minimized e contendo o ponto.

Entre matches, maior z vence.

Geometry check é half-open: left/top inclusivos, right/bottom exclusivos, evitando disputa exata no pixel de borda compartilhada.

## Focus on pointer press

A cada desktop frame, `desktop_frame` lê pointer state.

Em novo left press chama:

    task_focus_at(mouse.x, mouse.y)

A função escolhe a window de maior z no ponto.

Ordinary windows são raised ao receber focus.

Uma window reconhecida como wallpaper full-screen recebe focus sem novo z.

Sem hit, g_focused_id vira -1.

O capítulo input-routing documenta forwarding de keyboard/text.

## Wallpaper special case

`task_focus_at` reconhece wallpaper por geometry: frame começa na origem ou antes e cobre pelo menos toda a área gráfica.

Esse task pode receber focus sem raise.

`surf_raise` usa heurística semelhante.

Não existe dedicated desktop role; uma aplicação full-screen pode parecer wallpaper para essa policy conforme seu frame.

## Raise semantics

`task_raise` ignora IDs inválidos, restaura MINIMIZED para NORMAL, marca frame dirty, atribui novo z e foca.

Não restaura MAXIMIZED para normal.

Raise e restore são operações distintas.

## Closing

`task_close` apaga old frame com desktop color, limpa a Task entry e, se era focused, define focus como -1.

Não escolhe automaticamente a visible task de maior z como novo focus.

Novo pointer focus ou explicit raise seleciona o próximo target.

## Focus fallback limitation

Close e minimize podem remover a focused task sem escolher fallback.

É policy simples e determinística, mas cria períodos sem keyboard focus.

Uma policy futura deveria centralizar transições e escolher deterministic fallback.

## Move

`task_move` salva old frame, apaga-o com desktop color, atualiza x/y e marca new frame dirty.

Mover task maximized retorna mode para NORMAL.

A primitive não faz clamp ao display.

Clamping ocorre em camadas superiores como `app_game_chrome` e `LIB/WIN.CC`.

O syscall `surf_move` apenas limita y a zero; x pode permanecer negativo.

## Resize

`task_resize` rejeita dimensões não positivas, apaga old frame, atualiza width/body_height, sai de maximized se necessário e marca frame dirty.

A primitive também não impõe display bounds.

Chrome de nível superior define minimum sizes e limites contra display/taskbar.

## Minimize

`task_minimize` apaga frame, muda para MINIMIZED, cancela dragging e limpa focus se necessário.

O frame permanece armazenado.

Raise posterior retorna para NORMAL com a mesma geometry.

Minimized tasks ficam fora de hit testing e `task_run_all`.

## Maximize

`task_maximize` recebe bounds explícitos.

Se não estava maximized, salva old frame em `window.restore`.

Depois aplica bounds, muda mode e cancela dragging.

A primitive não calcula usable desktop area; caller decide.

No kernel game chrome, o padrão usa display inteiro menos `UI_TASKBAR_HEIGHT`.

## Restore

`task_restore` retorna a NORMAL.

Se vinha de MAXIMIZED restaura saved frame.

Se vinha apenas de MINIMIZED mantém current frame.

O resulting frame é marcado dirty.

## Dois modelos de chrome

ChrisOS possui dois paths principais.

### Kernel game chrome

`kernel/tools/app_window.c` desenha chrome para game-style CLVM apps e implementa close, maximize/restore, minimize, title drag, resize handle, display-bound clamping e scaled framebuffer blit.

### ChrisC library chrome

UI-style ChrisC apps podem usar `LIB/WIN.CC`.

A library desenha title/body/buttons dentro da própria surface e chama:

    surf_place
    surf_move
    surf_raise
    surf_close
    surf_resize
    surf_minimize
    surf_maximize
    surf_restore

É arquitetura híbrida: visual chrome pode ser application-side, enquanto authoritative task geometry e z/focus permanecem kernel-side.

## Por que existe essa divisão

A divisão permite que apps ChrisC implementem UI sem exigir kernel function para cada widget/style.

O kernel continua owner de task entries, execution lifetime, focus, z-order, placement e close requests.

O trade-off é duplicação de interaction logic entre `app_window.c` e `LIB/WIN.CC`: minimum sizes, edge-resize e button handling não vêm de uma única state machine.

## CLVM surface ABI

ChrisC expõe operações por CLVM syscalls:

| ID | Builtin | Efeito |
|---:|---|---|
| 88 | surf_place(x,y,w,h) | move e resize da task atual |
| 89 | surf_move(x,y) | move task atual |
| 90 | surf_raise() | raise salvo heuristic wallpaper |
| 91 | surf_close() | fecha task, solicita close do LangSlot e HALT |
| 113 | surf_resize(w,h) | resize viewport + task |
| 114 | surf_minimize() | minimize |
| 115 | surf_maximize(x,y,w,h) | viewport resize + maximize |
| 116 | surf_restore(x,y,w,h) | viewport resize + restore/move/resize |

A current CLVM task é encontrada indiretamente pelo syscall graphics context.

App não fornece arbitrary task ID para essas surface operations, o que cria ownership binding ao próprio runtime context.

## Close lifecycle

Fechar CLVM app não é apenas limpar pixels.

Syscall path fecha Task, solicita language-slot close e muda VM para HALTED.

Kernel game chrome usa a mesma ideia com:

    task_close(task->id)
    lang_slot_request_close(slot)

Language runtime libera depois VM/JIT/process/graphics resources.

Task table não possui toda runtime memory.

## Task versus language slot

TASK_APP guarda:

    state.app.lang_slot

Task possui desktop identity/geometry.

LangSlot possui ClvmVm, code/image, process ID, graphics buffers/context, JIT, guest memory e debug state.

A association precisa permanecer válida.

Se `app_run` detecta slot não usado, fecha a task automaticamente.

## Application rendering

`app_run` diferencia game-like viewport de ordinary UI app.

Game recebe kernel chrome e scaled blit no client rectangle.

UI app desenha o próprio chrome, Task frame é sincronizado às viewport dimensions e pixels são blitados 1:1 em x/y.

Por isso window behavior não pode ser entendido apenas por task.c.

## Dirty-region interaction

Move/resize chamam:

    erase_task_frame(old)
    mark_task_frame(new)

Old rectangle recebe desktop color imediatamente e new rectangle fica dirty.

Back-to-front task rendering reconstrói windows visíveis.

É compositor simples, sem retained damage history completo por window.

## Input ownership

Focus afeta input delivery.

`desktop_frame` encaminha keyboard/text somente para focused TASK_APP que não está dragging/resizing.

Isso evita disputa entre application input e window manipulation.

Native tools também usam `task_is_focused` antes de consumir events.

Pointer state pode ser globalmente consultado por UI paths, então focus/press-consumption continuam importantes.

## Draw order e focus são conceitos separados

Normalmente raise altera z e focus, mas são fields distintos.

Wallpaper pode receber focus sem raise; close pode zerar focus sem alterar z de outras windows; `task_run_all` usa z/mode, não focus.

Isso é conceitualmente correto, embora APIs comuns ainda acoplem os dois.

## Taskbar interaction

Taskbar é uma CLVM application comum no boot.

Kernel reserva:

    UI_TASKBAR_HEIGHT = 40

Window chrome usa essa altura em movimento/maximização.

Taskbar consegue enumerar/raise apps por services do kernel.

Ela não é owner da task table; é cliente das informações de task/runtime.

## Capacidades fixas e ownership

Task metadata não usa dynamic allocation.

Vantagens: memória bounded, storage estável, IDs simples e ausência de allocator failure após escolher slot.

Trade-off: máximo de 32 active tasks; IDs são reciclados e não são globally unique ao longo do tempo.

Resources externos à Task exigem cleanup separado; para CLVM apps isso ocorre no LangSlot teardown.

## Concurrency model

Task table não tem internal lock.

O modelo normal serializa mutations pelo UI/runtime kernel path.

Não há atomics em g_tasks/g_next_z/g_focused_id.

Se futuros SMP workers manipularem tasks em paralelo, será necessário locking ou message serialization explícita.

## Failure behavior

API prefere safe no-op para invalid IDs.

task_get retorna null; move/resize/raise/close simplesmente não operam; invalid spawn retorna -1.

Não existe window-manager error object separado.

Syscall wrappers podem transformar invalid arguments em syscall failure, enquanto ausência de associated task em alguns paths é successful no-op.

## Geometry overflow considerations

Coordinates/dimensions são signed int.

Hit tests calculam expressões como:

    frame.x + frame.width

sem widening overflow-safe.

Desktop geometry normal fica muito abaixo de INT_MAX, mas callers internos extremos podem provocar signed overflow.

Boundary mais hardened deveria usar checked geometry arithmetic e central normalization.

## Validation evidence

Evidência atual inclui host compilation das app lists em `tools/test_chrisc_apps.c`, uso real no QEMU desktop path, chrome em `LIB/WIN.CC`, game-window lifecycle e CLVM surface syscall integration.

O source inspecionado não contém dedicated host-side `test_task.c` cobrindo state transitions.

É gap relevante.

## High-value missing tests

Uma suite focada deve cobrir capacity 32, overlap/z selection, raise/focus, minimize hit-test exclusion, maximize/restore, close focused task, focus fallback, z wrap/renormalization, back-to-front order, wallpaper special case, extreme geometry, syscall ownership, Task/LangSlot close synchronization e drag/resize edge cases.

## Limitações atuais

Na revisão documentada:

- task metadata usa fixed table de 32;
- z é uint32 monotônico sem renormalização;
- close/minimize da focused task não focam automaticamente próxima visible task;
- hit test/render order varrem tabela fixa;
- geometry clamping fica distribuído entre callers;
- signed coordinate arithmetic não é overflow hardened;
- desktop/wallpaper exception é heuristic geometry, não explicit role;
- kernel game chrome e `LIB/WIN.CC` duplicam drag/resize/button policy;
- não há internal locking em task/focus/z globals;
- não há dedicated host unit-test suite evidente;
- task IDs são reutilizáveis e não generation-tagged handles.

## Fronteira de roadmap

Window manager futuro pode adicionar generation-tagged handles, z renormalization, explicit desktop/taskbar roles, centralized geometry constraints, deterministic focus fallback, unified chrome state policy, per-window damage, SMP-safe mutation, pointer capture explícito, compositor-facing ordered list e dedicated host tests.

São mudanças futuras até existirem no source.

## Mapa de source e revisão

`kernel/wm/task.h` define Task, TaskRect, WindowState, modes e API pública.

`kernel/wm/task.c` possui task table, z-order, focus, geometry state e back-to-front ordering.

`kernel/wm/desktop.c` inicializa desktop, escolhe focus no pointer press, encaminha focused input e executa tasks por frame.

`kernel/tools/app_window.c` implementa kernel chrome e scaled game presentation.

`LIB/WIN.CC` implementa ChrisC-side UI window chrome.

`kernel/lang/clvm_sys.c` traduz surface builtins em authoritative Task operations.

`compiler/lang_pipeline.c` possui os CLVM LangSlots associados a TASK_APP.

Todas as afirmações de comportamento atual foram reconciliadas com ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
