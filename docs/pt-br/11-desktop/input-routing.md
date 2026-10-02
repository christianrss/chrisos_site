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
  - input_mouse_delta_for
  - input_mouse_axis
  - ps2_init
  - ps2_mouse_poll
depends_on:
  - window-manager
  - desktop-applications
  - interrupts-smp
---

# Roteamento de entrada: das interrupções de dispositivo à aplicação em foco

Entrada é uma fronteira entre hardware assíncrono e lógica síncrona de aplicações. Um teclado pode interromper o processador em qualquer instrução, um mouse PS/2 chega como um pacote de três bytes e um tablet USB pode informar coordenadas absolutas. Aplicações, porém, precisam de conceitos estáveis como **texto**, **teclas especiais**, **posição do ponteiro**, **transições de botões** e, para jogos, movimento relativo pertencente a uma tarefa.

O ChrisOS implementa essa fronteira em camadas. Drivers normalizam relatórios de hardware para o subsistema compartilhado de entrada; esse subsistema mantém estado de teclado e ponteiro, além de uma fila limitada de eventos; desktop e tarefas consomem essas abstrações segundo regras de foco e captura. Este capítulo descreve a implementação na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele não atribui ao sistema um servidor de eventos futuro nem um modelo POSIX que ainda não existe.

## 1. O problema de roteamento

Um caminho de entrada útil precisa preservar tipos diferentes de informação:

1. **estado** — se uma tecla ou botão está pressionado agora;
2. **transições** — uma pressão que ocorreu desde a última observação do consumidor;
3. **texto** — caracteres após interpretação de layout e modificadores;
4. **comandos** — setas, Enter, Escape e teclas de função que não são texto comum;
5. **movimento** — coordenadas absolutas no desktop e deltas relativos;
6. **propriedade** — qual tarefa pode consumir movimento relativo capturado.

Esses conceitos não são representados por uma única variável. Consultar apenas o estado atual perde transições curtas. Manter somente eventos torna movimento contínuo inconveniente. Tratar texto como scan codes brutos força cada aplicação a implementar política de layout. Por isso, o ChrisOS mantém representações complementares.

O fluxo de alto nível é:

```text
PS/2 IRQ 1 -------------------> input_keyboard_irq(scancode)
teclado USB HID -------------> input_keyboard_irq(código Set-1 normalizado)
                                  |-- tabela de estado das teclas
                                  |-- estado de modificadores/layout
                                  `-- fila limitada de InputEvent

PS/2 IRQ 12 / polling --------> input_mouse_irq_byte(byte)
                                  `-- decodificador de 3 bytes --+
ponteiro USB absoluto --------> input_pointer_absolute(...) ----+--> estado do mouse
                                                                |    + deltas relativos
                                                                `--> sequência de pressão

aplicação / desktop ----------> input_next_event()
                             --> input_mouse_snapshot()
                             --> input_key_down()
                             --> API de captura/deltas
```

A decisão arquitetural importante é que PS/2 e USB não expõem APIs independentes às aplicações. Ambos convergem em `kernel/gfx/input.c`.

## 2. Modelo público de dados

`kernel/gfx/input.h` define duas classes de evento. `INPUT_EVENT_TEXT` transporta um caractere; `INPUT_EVENT_KEY` transporta um `InputKey` para ações que não são texto. A enumeração de teclas especiais inclui atualmente Backspace, Tab, Enter, Escape, movimento do cursor, Home, End, Delete e algumas teclas de função.

O estado do ponteiro é representado por `InputMouse`:

```c
typedef struct {
    int x;
    int y;
    bool left_down;
    bool right_down;
    bool middle_down;
    uint32_t left_press_sequence;
} InputMouse;
```

A sequência de pressão é relevante. Um booleano responde “o botão está pressionado agora?”, mas não prova que uma pressão completa ocorreu entre dois frames. Incrementar `left_press_sequence` na borda de subida fornece ao desktop um marcador monotônico de transição.

O teclado também possui uma tabela de estado com 256 posições. O make code Set-1 comum `N` usa o índice `N`; um make code precedido por `E0` usa `128 + N`. Assim, por exemplo, uma seta estendida não colide com uma tecla do teclado numérico que tenha o mesmo código baixo.

## 3. Inicialização e layout persistente

`input_init(width, height)` reinicia índices da fila, estado das teclas, contagem de eventos perdidos, estado do ponteiro e modificadores. O ponteiro começa no centro de uma tela cujas dimensões são limitadas a no mínimo um pixel. A rotina também tenta carregar `SYS/KB.CFG`.

Dois layouts são modelados atualmente: US e ABNT2. `input_load_layout_file()` reconhece uma configuração textual pequena, enquanto `input_save_layout_file()` persiste `us` ou `abnt2`. É um mecanismo propositalmente simples para o estágio atual do kernel, e não uma infraestrutura geral de métodos de entrada Unicode.

As tabelas atuais são orientadas a bytes. Portanto, o roteamento atende às aplicações atuais do ChrisOS, mas ainda não constitui um sistema internacional completo de texto. Dead keys, composição Unicode, IMEs e pacotes arbitrários de layout permanecem fora do contrato implementado.

## 4. Caminho do teclado

### 4.1 Entrada PS/2

`ps2_init()` configura o controlador compatível com i8042, testa a primeira porta, habilita opcionalmente a porta auxiliar do mouse, ativa o scanning dos dispositivos e registra handlers de IRQ. A IRQ 1 do teclado lê a porta `0x60` apenas quando há dado de saída e chama `input_keyboard_irq(value)`.

O handler é deliberadamente pequeno: aquisição do byte e interação com hardware permanecem na camada de dispositivo; a interpretação semântica pertence à camada compartilhada de entrada.

### 4.2 Convergência USB

O caminho xHCI/HID também emite transições normalizadas por `input_keyboard_irq()`. Para uma tecla estendida, emite primeiro `0xE0` e depois o código make ou break. Consequentemente, aplicações do desktop não precisam saber se a tecla veio de PS/2 ou USB.

### 4.3 Make, break e códigos estendidos

`input_keyboard_irq()` trata primeiro o prefixo `0xE0`. `input_keystate_note()` registra a transição seguinte na tabela de 256 posições. O bit alto diferencia liberação de pressão nos códigos Set-1.

O tratamento de modificadores mantém estado:

- Shift esquerdo e direito acompanham pressão/liberação;
- Caps Lock alterna no pressionamento;
- Alt estendido é usado como AltGr;
- Escape libera a captura do mouse antes de o despacho normal continuar.

Teclas estendidas são traduzidas por `extended_key()`. Teclas comuns de controle são traduzidas por `plain_key()`. Uma tecla especial reconhecida gera `INPUT_EVENT_KEY`; entrada imprimível gera `INPUT_EVENT_TEXT` após aplicação de layout, Shift, Caps Lock e das regras ABNT2/AltGr atualmente implementadas.

Essa separação é importante para editores e shells. Seta para a esquerda não deve ser um byte imprimível, enquanto digitar `a` não deveria obrigar cada aplicação a decodificar o scan code `0x1E`.

## 5. Fila limitada de eventos do teclado

A fila contém 64 posições e usa índices de cabeça e cauda. O produtor calcula a próxima posição da cabeça; se ela colidir com a cauda, o evento é descartado e `g_lost_events` é incrementado. Caso contrário, o evento é copiado e a cabeça avança.

Para capacidade `C = 64`, o anel deixa propositalmente uma posição livre para distinguir cheio de vazio. Logo, o máximo de eventos pendentes é:

\[
N_{max} = C - 1 = 63.
\]

Inserção e remoção são operações **O(1)** e o armazenamento é **O(C)** com limite fixo. Não há alocação no caminho de interrupção.

`input_next_event()` é a interface do consumidor. `input_clear_events()` descarta eventos pendentes avançando a cauda para a cabeça atual. `input_lost_events()` expõe evidência de overflow em vez de fingir entrega sem perdas.

A implementação usa índices `volatile` e barreiras de compilador. Trata-se de um desenho freestanding pequeno, não de uma fila lock-free multi-produtor com prova formal de ordenação atômica C11. Se produtores simultâneos em CPUs diferentes forem introduzidos, esse contrato deverá ser revisado com operações atômicas explícitas ou locking.

## 6. Caminho do ponteiro

### 6.1 Pacotes PS/2

Um relatório padrão de mouse PS/2 é montado em três bytes. O primeiro deve conter o bit de sincronização (`0x08`); caso contrário, o decodificador espera um início válido. Flags de overflow fazem o pacote completo ser rejeitado.

O segundo e o terceiro bytes são deltas X e Y com sinal. PS/2 define Y positivo para cima, enquanto coordenadas de tela crescem para baixo. Assim, o ChrisOS aplica:

\[
\Delta x_{tela} = \Delta x_{ps2}, \qquad
\Delta y_{tela} = -\Delta y_{ps2}.
\]

O ponteiro é limitado às bordas do framebuffer. Bits de botão atualizam os estados esquerdo, direito e central, e uma borda de subida do botão esquerdo incrementa a sequência de pressão.

`ps2_mouse_poll()` fornece um caminho adicional para drenar bytes auxiliares. O próprio código registra a motivação: a IRQ 12 pode estar mascarada ou interagir com atividade da GPU, então o desktop pode consultar bytes AUX pendentes para manter o ponteiro responsivo. Interrupções são temporariamente desabilitadas enquanto o loop drena até 16 bytes, evitando que o handler de IRQ consuma o mesmo byte simultaneamente.

### 6.2 Ponteiro USB absoluto

`input_pointer_absolute(x, y, xmax, ymax, buttons)` converte o intervalo de coordenadas do dispositivo para coordenadas de tela. Desconsiderando arredondamento inteiro:

\[
x_s = x \frac{W-1}{x_{max}}, \qquad
y_s = y \frac{H-1}{y_{max}}.
\]

Os valores são limitados ao intervalo anunciado pelo dispositivo antes da escala. Quando uma tarefa possui captura, o deslocamento entre posições absolutas sucessivas também é acumulado como delta relativo. Isso permite que um tablet absoluto participe de APIs usadas por aplicações interativas sem afirmar que o hardware fornece movimento relativo nativamente.

## 7. Snapshots coerentes durante atualizações por interrupção

O estado do ponteiro pode mudar de forma assíncrona. Sem proteção, o código poderia copiar `x`, sofrer uma interrupção e depois copiar `y`, produzindo um snapshot misturado de dois relatórios.

O ChrisOS usa um pequeno protocolo de leitura versionada. Escritores incrementam `g_mouse.version` antes e depois de alterar a estrutura, com barreiras de compilador ao redor dos campos. `input_mouse_snapshot()` repete a leitura se a primeira versão for ímpar ou se a versão mudar durante a cópia.

Conceitualmente:

```text
escritor: version++ -> escreve campos -> version++
leitor: lê v1 -> copia campos -> lê v2 -> aceita se v1 == v2 e par
```

O mecanismo se aproxima de um sequence counter e evita um lock bloqueante para um snapshot pequeno. Ainda assim, deve ser interpretado dentro do modelo atual de execução do ChrisOS: barreiras de compilador isoladas não substituem operações atômicas adequadas em qualquer arquitetura SMP futura.

## 8. Foco, roteamento e captura

Foco de janela e captura do ponteiro resolvem problemas diferentes.

**Foco** determina qual tarefa do desktop é o alvo ativo da interação comum. O gerenciador de janelas mantém empilhamento e foco. O desktop pode fazer hit testing, elevar e focar uma tarefa quando o usuário interage com sua janela.

**Captura** é a propriedade explícita do movimento relativo. `input_capture_set(task_id)` registra um único proprietário e limpa deltas acumulados. `input_mouse_delta_for(task_id, ...)` entrega movimento somente ao proprietário. `input_capture_release_task(task_id)` libera a propriedade quando a tarefa termina. Escape também libera a captura no caminho do teclado.

Isso é especialmente importante em uma aplicação 3D. O ponteiro do desktop é naturalmente absoluto e limitado pelas bordas da tela. Uma câmera em primeira pessoa precisa de um fluxo de movimento relativo que não seja limitado pelas bordas. A captura cria essa fronteira sem obrigar todas as aplicações do desktop a consumir deltas.

`input_mouse_axis()` fornece ainda uma amostra pareada para runtimes que consultam X e Y separadamente. A primeira consulta captura o movimento acumulado; a segunda recebe a mesma amostra, evitando combinar X de um frame com Y de outro.

## 9. Concorrência, propriedade e modos de falha

O subsistema evita alocação dinâmica nos caminhos próximos ao hardware. Seus recursos limitados principais são o anel de 64 posições e os estados fixos de teclado/ponteiro.

| Falha | Comportamento atual | Consequência observável |
|---|---|---|
| fila de teclado cheia | descarta o evento novo | `input_lost_events()` aumenta |
| início inválido de pacote PS/2 | ignora até sincronizar | fluxo volta a alinhar |
| overflow X/Y do PS/2 | rejeita pacote | uma amostra de movimento é perdida |
| ponteiro fora do intervalo | aplica clamp | ponteiro permanece na tela |
| chamador não possui captura | retorna zero/sem amostra | tarefa não rouba movimento relativo |
| configuração de teclado ausente/inválida | mantém layout padrão | US continua utilizável |
| IRQ do mouse PS/2 não confiável | drena AUX por polling | movimento pode continuar chegando |

O desenho prefere dano limitado a bloqueio em contexto de interrupção. Uma fila cheia não aloca memória nem espera o consumidor. Um fluxo de mouse malformado não desloca o ponteiro usando bytes arbitrários.

## 10. Fronteira de segurança e privilégio

Hoje o subsistema reside no kernel e o modelo de tarefas ainda está evoluindo. Captura é uma verificação de propriedade por identificador de tarefa, não uma fronteira de segurança madura equivalente à de um desktop multiusuário de produção.

Uma futura separação em modo usuário precisará responder outras questões: quem pode observar estado global de teclas, se tarefas em segundo plano podem ler eventos de texto, como entrada sintética é autorizada, o que ocorre quando o processo em foco falha e se a captura é revogada em toda mudança de foco. Esses são requisitos de roadmap, não propriedades da implementação atual.

## 11. Evidência de validação

A árvore de código contém testes host-side do comportamento de entrada. `tools/test_input.c` inicializa o subsistema, injeta scan codes e verifica produção de eventos. `tools/test_keystate.c` verifica identidade de estado, inclusive a distinção entre setas estendidas e códigos do teclado numérico, além de transições de modificadores e teclas.

Uma matriz de validação útil para esta camada é:

1. injetar pares make/break e verificar `input_key_down()`;
2. validar mapeamentos US e ABNT2 com Shift/Caps/AltGr;
3. preencher o anel e verificar contabilização determinística de overflow;
4. alimentar pacotes PS/2 válidos, dessincronizados e com overflow;
5. verificar clamp em todas as bordas da tela;
6. atualizar o ponteiro enquanto snapshots são lidos repetidamente;
7. transferir/liberar captura e confirmar que não proprietários não recebem deltas;
8. executar o mesmo caminho de aplicação com entrada originada de PS/2 e USB.

A validação em hardware deve cobrir também teclados, mouses e tablets USB em máquinas reais, pois emuladores normalmente apresentam temporização mais limpa e controladores mais simples que firmware e hardware físicos.

## 12. Limitações atuais

Na revisão analisada, a implementação é deliberadamente compacta. Limitações importantes incluem:

- eventos de texto carregam um único `char`, não um escalar Unicode ou sequência composta;
- apenas US e um mapeamento ABNT2 limitado estão embutidos;
- a fila é limitada e pode perder eventos sob pressão sustentada;
- a sincronização da fila não é um desenho SMP multi-produtor geral;
- PS/2 concentra-se no pacote padrão de mouse de três bytes;
- captura usa propriedade por ID de tarefa, não um sistema completo de capabilities/segurança;
- `keyboard_pop()` e `mouse_pop()` na interface de compatibilidade PS/2 são stubs; consumidores devem usar a API compartilhada descrita neste capítulo;
- o roteamento de alto nível permanece acoplado à arquitetura atual de desktop/tarefas do kernel.

Essas limitações fazem parte da arquitetura observada. A documentação não deve substituí-las por um desenho mais avançado que ainda não foi implementado.

## 13. Limites do roadmap

Trabalho futuro razoável inclui composição de texto Unicode, parsing HID mais amplo, layouts configuráveis, semântica atômica/SMP explícita, canais de eventos por tarefa, revogação mais forte de foco/captura, eventos de roda e uma ABI de entrada mais clara entre kernel e user space. Essas mudanças devem preservar a separação já útil: decodificação de hardware abaixo, estado/eventos normalizados no meio e política de desktop/aplicação acima.

## 14. O que deve ser retido

A principal ideia é que roteamento de entrada não é simplesmente “ler uma tecla e enviá-la à janela”. O ChrisOS combina mecanismos porque cada um preserva informações diferentes:

- **tabela de estado de teclas** para estado contínuo;
- **anel limitado de eventos** para texto e comandos discretos;
- **snapshot versionado do ponteiro** para leituras coerentes diante de atualizações assíncronas;
- **sequência de pressão** para detectar bordas;
- **acumuladores relativos e propriedade de captura** para aplicações interativas;
- código específico de PS/2/USB convergindo na mesma API compartilhada.

Essa estrutura é a ponte entre hardware dirigido por interrupções e o modelo de janelas/aplicações descrito nos capítulos vizinhos do desktop.