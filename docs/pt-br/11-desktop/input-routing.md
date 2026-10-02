---
id: input-routing
lang: pt-br
type: technical-chapter
volume: 11-desktop
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/input.h
  - kernel/gfx/input.c
  - kernel/metal/ps2.h
  - kernel/metal/ps2.c
  - kernel/fs/xhci.c
  - kernel/wm/task.h
  - kernel/wm/task.c
  - kernel/wm/desktop.c
  - kernel/wm/ui.c
  - kernel/tools/editor_window.c
  - kernel/tools/explorer.c
  - kernel/tools/taskmgr.c
  - compiler/lang_pipeline.c
  - compiler/lang_pipeline.h
  - kernel/lang/clvm_sys.c
  - compiler/chrisc/chrisc.c
  - tools/test_input.c
  - tools/test_keystate.c
symbols:
  - input_init
  - input_keyboard_irq
  - input_mouse_irq_byte
  - input_pointer_absolute
  - input_next_event
  - input_mouse_snapshot
  - input_key_down
  - input_capture_set
  - input_capture_release_task
  - input_mouse_axis
  - input_mouse_delta_for
  - ps2_init
  - ps2_mouse_poll
  - task_focus_at
  - task_focused_id
  - task_is_focused
  - lang_slot_push_key
  - lang_slot_push_text
  - lang_slot_take_key
  - lang_slot_take_text
depends_on:
  - window-manager
  - desktop-applications
  - interrupts-smp
related:
  - desktop-applications
  - chriseditor
  - chrisshell
  - mine-chris
  - clvm-syscalls
---

# Roteamento de input, foco e capture

## Escopo

O input do ChrisOS não é uma única fila entregue diretamente do hardware para as aplicações.

O caminho implementado possui várias camadas:

    hardware de teclado/mouse
        -> decoding de IRQ ou USB report
        -> global input state + global event queue
        -> seleção de focus por window/task
        -> desktop routing
        -> native task consumers ou filas por CLVM
        -> APIs da aplicação

Keyboard input possui duas representações paralelas:

- **key state**, para polling de scan-code atualmente pressionado;
- **event stream**, para key/text events discretos.

Pointer input possui três representações:

- screen position/buttons absolutos;
- relative deltas acumulados;
- left-press sequence para edge detection.

Aplicações CLVM adicionam outra camada de queueing para `ev_key()` e `ev_text()`.

Este capítulo documenta esses contratos e as limitações atuais do routing.

![Camadas do roteamento de input do ChrisOS](../../assets/diagrams/input-routing-pt-br.svg)

## Tipos de input event

A core event queue carrega somente:

    INPUT_EVENT_TEXT
    INPUT_EVENT_KEY

`InputEvent` contém:

    type
    key
    character

Special/navigation keys usam `InputKey`, incluindo:

- Backspace;
- Tab;
- Enter;
- Escape;
- arrows;
- Home/End/Delete;
- function keys selecionadas.

Printable characters usam TEXT events, não KEY events.

Isso permite que editor distinga semantic navigation keys de character input dependente do layout.

## Global event queue

A core queue tem:

    INPUT_QUEUE_CAPACITY = 64

É um ring com global head/tail.

IRQ-side producers adicionam por `queue_push`.

Se next head coincidir com tail, o novo event é descartado e:

    g_lost_events++

é incrementado.

Queue não sobrescreve o evento mais antigo.

`input_lost_events()` expõe o contador cumulativo.

Não existe per-task event queue nessa camada mais baixa.

## Sincronização IRQ/main loop

Event queue e mouse state são compartilhados entre interrupt/device paths e desktop/main execution.

A implementação usa volatile fields e compiler barriers, não um lock geral.

No event ring, producer grava payload antes de publicar novo head.

Consumer observa head/tail, copia event e avança tail.

É um design de uma global bounded queue.

Não deve ser generalizado como fila MPMC lock-free: ele depende do producer/consumer pattern atual de interrupt/main loop.

## Identidade de keyboard scan code

ChrisOS preserva identidade Set-1 para polling.

Ordinary make code N usa índice N.

E0-prefixed make code N usa:

    128 + N

Isso evita colisão entre keypad e navigation keys.

Por exemplo:

    Up    = 200
    Left  = 203
    Right = 205
    Down  = 208

`g_keys[256]` guarda estado down/up.

`input_key_down(scancode)` consulta essa table.

## Geração de keyboard events

`input_keyboard_irq` primeiro atualiza key state, depois trata modifiers e event generation.

Modifiers acompanhados:

- left Shift;
- right Shift;
- Caps Lock;
- AltGr.

Release events atualizam state, mas normalmente não produzem application events.

Special key make vira KEY event.

Printable make vira TEXT event após layout/modifier translation.

Portanto:

    physical identity -> key state
    semantic special key -> KEY event
    printable result -> TEXT event

são outputs separados do mesmo keyboard path.

## Keyboard layouts

Layouts atuais:

    INPUT_LAYOUT_US
    INPUT_LAYOUT_ABNT2

Layout default é US, exceto quando `SYS/KB.CFG` seleciona outro valor válido.

Configuration parser reconhece formas textuais de US/ABNT2.

`input_save_layout_file` grava escolha no filesystem.

ABNT2 possui normal/shifted tables próprias e handling específico de AltGr.

Ainda é compact explicit table, não framework geral de Unicode/IME.

TEXT events contêm um único `char`.

## Regra Caps/Shift

Para letras:

    shifted != caps_lock

determina uppercase.

Para símbolos, shifted table é usada quando Shift está ativo e mapping existe.

É regra XOR esperada para letras latinas.

## Escape e pointer capture

Um keyboard make de Escape tem side effect global:

    g_capture_task = -1

antes do KEY event normal.

Escape portanto funciona como emergency release do relative pointer capture independentemente de qual app CLVM capturou.

Isso é útil em game modes.

Ao mesmo tempo, Escape continua sendo INPUT_KEY_ESCAPE.

## Mouse snapshot

`InputMouse` contém:

    x
    y
    left_down
    right_down
    middle_down
    left_press_sequence

O IRQ-facing state possui `version` monotonicamente alterado.

Writer incrementa version antes e depois de atualizar fields.

`input_mouse_snapshot()` repete até observar:

- version par;
- mesmo version antes/depois da cópia.

É um read pattern semelhante a seqlock.

Evita snapshot formado por duas device updates distintas sem heavyweight lock.

## Input relativo PS/2

PS/2 decoder monta packets de três bytes.

Packet inicial sem synchronization bit é ignorado.

Packets com overflow flags são descartados.

PS/2 Y positivo aponta para cima; screen Y do ChrisOS cresce para baixo.

Logo:

    screen_dx = packet_dx
    screen_dy = -packet_dy

Cursor position é clamped aos screen bounds.

Button bits atualizam left/right/middle.

Transição left-up -> left-down incrementa `left_press_sequence`.

## Absolute pointer

`input_pointer_absolute` recebe:

    0..xmax
    0..ymax

e escala para screen coordinates.

É usado para USB tablet-style device.

Com capture ativo, successive absolute positions também contribuem para accumulated relative deltas.

Assim aplicação capturada pode usar delta mesmo com device absoluto.

## Press-edge detection

Global UI pode chamar:

    input_left_pressed()

Ela compara latest `left_press_sequence` com global consumed sequence.

`input_consume_left_press()` avança a sequência consumida.

Isso é diferente de `left_down`: detecta edge desde último consume.

Como consumed sequence é global, não é namespaced por task.

## Focus model

Window focus é mantido por:

    g_focused_id

`task_id_at(x,y)` escolhe task ativa/non-minimized sob o ponto com maior z.

`task_focus_at(x,y)` dá foco.

Para normal window, chama `task_raise`, que também estabelece top/focus.

Wallpaper-sized task tem tratamento especial e pode ganhar foco sem ordinary raise.

Clique em espaço vazio define focus -1.

## Click-to-focus no desktop

No desktop update:

1. mouse state é amostrado;
2. se existe novo left press, `task_focus_at(mouse.x, mouse.y)`;
3. focused task é obtida;
4. routing usa essa decisão de focus.

Logo o próprio clique que muda foco já influencia keyboard/text routing da mesma iteração.

## Problema de ownership da global keyboard queue

A low-level keyboard event queue é global.

`input_next_event()` remove permanentemente um event.

Não existe peek por owner, cursor por task ou fan-out.

Assim deveria haver exatamente um authoritative consumer que distribui events ao destino.

O source atual não segue esse modelo de forma consistente.

## Routing para CLVM

`desktop.c` atua como central router para application tasks CLVM.

Se a focused task:

- existe;
- é `TASK_APP`;
- não está dragging;
- não está resizing;

seu language slot é escolhido.

Desktop drena global input queue.

Para cada event:

    KEY  -> lang_slot_push_key(slot, key)
    TEXT -> lang_slot_push_text(slot, character)

Cada `LangSlot` possui key/text rings separados.

## Filas per-CLVM

Language slot contém:

    ev_key_q[LANG_EVQ]
    ev_text_q[LANG_EVQ]

com read/count indexes independentes.

`lang_slot_push_key/text` append enquanto houver capacidade.

Quando cheia, new routed event é silently dropped.

Diferentemente da core queue, per-slot queue não possui lost-event counter.

`lang_slot_take_key/text` remove um entry e devolve zero quando vazia.

## API CLVM de events

Builtins ChrisC:

    ev_key()   -> syscall 83
    ev_text()  -> syscall 84

Dispatcher chama diretamente:

    lang_slot_take_key
    lang_slot_take_text

Apps normalmente drenam em loop.

É poll-based do ponto de vista do app, embora eventos sejam produzidos de forma assíncrona.

## Restrição de foco em events CLVM

Somente focused `TASK_APP` recebe novos key/text events.

Se focus muda, old events já presentes no LangSlot permanecem até consumo.

Não há queue flush automático em focus loss no path inspecionado.

Isso evita perder input já entregue, mas pode fazer app processar stale keystrokes quando volta a executar.

## Supressão durante drag/resize

Quando application window focada está dragging/resizing, desktop routing não escolhe seu LangSlot.

Porém o desktop atual continua drenando global event queue.

Key/text events durante drag/resize são portanto descartados em vez de deferred.

Esse é current behavior.

## Conflito com native tasks

Várias native task implementations consomem `input_next_event()` diretamente.

Exemplos:

- native editor window;
- explorer;
- task manager.

Fazem isso apenas quando focadas.

Entretanto `desktop.c` drena global queue **antes** de `task_run_all()`.

Quando focused task não é `TASK_APP`:

    slot = -1

mas desktop ainda faz:

    while (input_next_event(&event)) {
        if (slot < 0)
            continue;
    }

Todos os events são removidos e descartados.

Depois, quando native task executa `run` e chama `input_next_event()`, queue já está vazia.

É bug concreto de routing.

Central router precisa distribuir também para native tasks ou não drenar quando não possui destination.

## Camadas de event loss

Há dois pontos independentes de overflow.

### Core queue

Ring de 64 entries descarta new event e incrementa `g_lost_events`.

### CLVM slot queue

LANG_EVQ cheia descarta new event silenciosamente.

Além disso, o desktop/native routing bug descarta events mesmo sem overflow.

Logo ausência de low-level queue overflow não implica entrega completa.

## Key-state polling

CLVM expõe `key(scancode)` pelo syscall ID 10.

Dispatcher verifica application focus antes de devolver `input_key_down`.

Task CLVM sem foco recebe zero.

É diferente de `ev_key`:

- `key()` responde physical current state;
- `ev_key()` devolve semantic queued event.

Games usam state polling para movimento e queue para one-shot actions.

## Mouse position/buttons

Builtins CLVM:

    mouse_x()
    mouse_y()
    mouse_btn()

Dispatcher amostra global mouse state.

Aplica task/window checks para evitar que app receba active button state de outra topmost task.

Para game/content-sized windows também verifica se pointer está no body, não title/chrome.

Coordinates continuam baseadas no screen pointer global, salvo transformação feita por app/library.

## Pointer capture

Relative-input API:

    mouse_cap()
    mouse_rel()
    mouse_dx()
    mouse_dy()

Capture pertence a task ID:

    g_capture_task

Somente capture owner pode consumir accumulated relative deltas.

Dispatcher só permite `mouse_cap()` se task estiver focada.

Caller sem foco recebe -1.

## Shared delta snapshot

`mouse_dx()` e `mouse_dy()` precisam representar o mesmo movement sample apesar de serem calls separadas.

`input_mouse_axis` snapshotta:

    g_acc_dx
    g_acc_dy

na primeira axis call, limpa source accumulator e lembra quais axes já foram lidas.

Quando ambas são consumidas, snapshot é invalidado.

Sem isso, IRQ entre X/Y reads poderia combinar deltas de momentos diferentes.

## Gap de lifecycle entre capture e focus

Header afirma que unfocused owners perdem capture.

Mas `input_capture_set` e focus functions não impõem isso diretamente.

Mudança de focus não limpa imediatamente `g_capture_task`.

Em vez disso, paths de `mouse_dx/mouse_dy` no dispatcher verificam focus; se owner deixou de estar focado, chamam:

    input_capture_release_task(t->id)

Capture também é liberado por:

- Escape;
- `mouse_rel()`;
- teardown do CLVM slot.

Portanto capture pode permanecer nominalmente pertencendo a task sem foco até um desses paths rodar.

É lifecycle gap em relação ao contrato do header.

A própria transição de foco deveria revogar capture do owner antigo.

## Efeito do stale capture nos deltas

Enquanto stale capture owner permanece configurado, PS/2 movement continua sendo acumulado em:

    g_acc_dx
    g_acc_dy

porque packet handling relativo acumula independentemente de focus.

Release posterior remove owner, mas não universalmente limpa accumulated deltas.

`input_capture_set` zera accumulator ao mudar owner, reduzindo stale movement quando novo owner captura.

Revogação imediata no focus loss tornaria o lifecycle mais previsível.

## Absolute device e capture

Em reports absolutos, deltas só são acumulados quando existe capture.

Absolute current position sempre é atualizada.

Isso evita construir relative movement history no desktop normal quando ninguém solicitou capture.

## Capture é task-scoped

Input subsystem armazena task ID, não language-slot ID.

CLVM mapeia gfx/language context para task owner antes das capture operations.

Esse é ownership level correto para focus semantics.

Teardown traduz language slot para task e libera capture.

## Focus checks na native UI

UI helper layer chama `task_is_focused(owner)` para interactions como rows/buttons.

Isso impede background windows de agir sobre global mouse click apenas porque pointer sobrepõe seu rectangle.

Window manager cuida de z/focus, enquanto widgets reforçam policy localmente.

## Concorrência e memory ordering

Input data é alterado por interrupt/device paths e lido por normal kernel execution.

Mouse snapshot version protocol oferece coherent multi-field read.

Event ring usa compiler barriers e volatile indexes.

Key state é volatile byte table.

Não há CPU memory-order primitives explícitos ou locks nessas paths.

No x86 atual, design depende bastante do ordering da plataforma e simple producer-consumer behavior.

Em architectures com memory ordering mais fraco ou múltiplos producers concorrentes, contratos precisam de atomics/locks mais fortes.

## Complexidade

Maioria das operações é O(1):

- key state update/lookup;
- queue push/pop;
- mouse snapshot sem contention;
- CLVM queue push/pop;
- capture checks.

`task_id_at` varre no máximo:

    TASK_MAX = 32

logo focus selection é O(TASK_MAX), pequeno e bounded.

Mouse seqlock pode retry durante update concorrente, mas expected cost é baixo.

## Segurança e isolamento

Input routing é security boundary porque keyboard events podem carregar dados sensíveis.

Controles positivos:

- CLVM key-state polling é focus-gated;
- CLVM event routing escolhe apenas focused app slot;
- capture acquisition exige focus;
- relative deltas só chegam ao capture owner;
- mouse button state é filtrado por topmost/window ownership;
- slot teardown libera capture.

Fraquezas atuais:

- global event consumers não são ownership-safe;
- event loss pode ser silencioso no LangSlot;
- stale queues sobrevivem a focus transitions;
- focus change não revoga capture imediatamente;
- global keyboard queue não expressa per-task provenance.

O conflito de drain de native tasks é tanto bug de usabilidade quanto problema de ownership arquitetural.

## Evidência de validação

`tools/test_keystate.c` verifica:

- keypad identity;
- E0 extended arrows sem collision;
- make/break key state;
- Shift lifetime;
- Ctrl/Alt/AltGr distintos;
- keyboard layout;
- PS/2 relative delta sign;
- capture ownership;
- rejection de delta por outra task;
- Escape release;
- absolute-device delta sob capture.

`tools/test_input.c` exercita keyboard event generation e queue consumption.

Sources de Editor, Shell, Explorer, Task Manager, Paint e Mine Chris fornecem integration evidence das APIs.

Test set atual não cobre diretamente o desktop/native-task drain bug.

## Focused tests ausentes

Testes de alto valor:

- focar native editor task, enfileirar key event, rodar desktop update e provar entrega;
- focar CLVM task e provar entrega somente ao LangSlot correspondente;
- mudar focus com queued events e definir preserve/flush policy;
- digitar durante drag/resize e definir deferred versus discarded;
- overflow da core queue com lost counter;
- overflow do LangSlot com loss reporting;
- capture pointer, trocar focus sem novas input calls e verificar revogação imediata;
- task destruction com capture ativo;
- absolute-pointer update concorrente a snapshot.

## Limitações atuais

Na revisão documentada:

- lowest event queue é global;
- desktop routing drena queue mesmo quando não há CLVM owner;
- focused native consumers podem perder todos events antes do run callback;
- drag/resize de CLVM window drena e descarta key/text;
- per-CLVM queue overflow é silencioso;
- events já roteados permanecem após focus loss;
- pointer capture não é revogado sincronicamente pelo focus change;
- TEXT events são single-byte chars, não Unicode code points;
- keyboard mapping é US/ABNT2 compacto, não general layout/IME framework;
- synchronization low-level depende de volatile/compiler barriers e assumptions atuais;
- global left-press consumed sequence não é per-task.

## Fronteira de roadmap

Uma arquitetura de routing mais forte deve ter um authoritative dispatcher:

    hardware event
      -> global ingress queue
      -> focus/capture router
      -> per-task queue
      -> native ou CLVM adapter

Então:

- cada task recebe queue própria;
- native e CLVM apps usam a mesma routed abstraction;
- loss pode ser contado por destination;
- focus transition define policy explícita de preserve/flush/synthetic events;
- capture revoke ocorre na mesma transação de focus;
- drag/resize desvia apenas mouse/chrome input e preserva keyboard;
- Unicode text input fica separado de physical keys;
- futuros USB/HID devices alimentam normalized event model único.

As APIs atuais já oferecem boa parte dos low-level primitives, mas a regra central de ownership ainda não está implementada de forma consistente.

## Mapa de source e revisão

`kernel/gfx/input.c` e `input.h` implementam device normalization, global event queue, key state, layouts, mouse snapshots, deltas e capture.

`kernel/wm/task.c` e `task.h` implementam hit testing, z selection e focus.

`kernel/wm/desktop.c` faz current global event drain e CLVM routing.

`compiler/lang_pipeline.c` possui as per-CLVM key/text queues.

`kernel/lang/clvm_sys.c` expõe focus-gated key/mouse state, event dequeue e capture syscalls.

Native tasks como `editor_window.c`, `explorer.c` e `taskmgr.c` consomem diretamente a global queue e tornam visível o conflito de routing atual.

`tools/test_input.c` e `tools/test_keystate.c` fornecem host-side validation.

Todas as afirmações de comportamento atual deste capítulo foram reconciliadas com ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
