---
id: desktop-compositor
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/wm/desktop.c
  - kernel/wm/main.c
  - kernel/wm/task.h
  - kernel/wm/task.c
  - kernel/wm/ui.h
  - kernel/wm/ui.c
  - kernel/tools/app_window.c
  - kernel/gfx/graphics.h
  - kernel/gfx/graphics.c
  - kernel/lang/clvm_sys.c
  - compiler/lang_pipeline.h
  - compiler/lang_pipeline.c
  - APPS/DESKTOP/DESKTOP.CC
  - APPS/TASKBAR/TASKBAR.CC
  - tools/test_task_window.c
  - tools/test_graphics_present.c
symbols:
  - desktop_frame
  - desktop_run
  - task_run_all
  - task_raise
  - task_move
  - task_resize
  - app_window_open
  - app_run
  - lang_slot_pixels
  - lang_slot_publish
  - clvm_sys_blit_to
  - clvm_sys_blit_scaled
  - ui_draw_cursor
  - ui_undraw_cursor
  - gfx_mark_dirty
  - gfx_present
depends_on:
  - pixels-framebuffer
  - color-formats
  - gfx2d
related:
  - desktop-applications
  - window-manager
  - input-routing
  - chrisc-clvm
---

# Composição do desktop

## Escopo

O desktop do ChrisOS é composto por software no backbuffer gráfico global e depois copiado para o framebuffer frontal por meio do caminho de apresentação com damage tracking.

A cadeia atual é aproximadamente:

    superfície da aplicação/CLVM
        -> superfície publicada do slot
        -> Task ordenada por z
        -> renderização da aplicação/janela
        -> backbuffer gráfico global
        -> dirty rectangles
        -> gfx_present()
        -> framebuffer frontal / flush do dispositivo

É um compositor real no sentido amplo: múltiplas superfícies renderizadas independentemente são ordenadas e combinadas em uma única imagem visível.

Não é um compositor GPU moderno com texturas por janela, transações assíncronas de superfícies, regiões de oclusão, page flipping, planos de scanout ou composição por hardware.

A distinção é importante porque correção, desempenho e sincronização atuais decorrem de redraw e cópias em software.

## Composição e apresentação são etapas diferentes

Duas operações não devem ser confundidas.

Composição decide quais pixels devem existir no backbuffer do desktop.

Apresentação transfere as partes alteradas desse backbuffer para o framebuffer frontal e, em builds freestanding, solicita ao caminho de GPU/dispositivo que faça flush da região afetada.

O loop do desktop executa as duas etapas em ordem.

desktop_run repete:

    net_poll()
    clvm_sys_frame(...)
    lang_tick(...)
    desktop_frame(...)
    gfx_present()

Portanto o compositor atualiza primeiro a imagem de software e somente depois gfx_present copia as regiões sujas.

Composição correta não comprova, sozinha, que o dispositivo concluiu o scanout.

Da mesma forma, apresentação correta do framebuffer não comprova que as janelas foram ordenadas corretamente antes da cópia.

## Superfície global de destino

O destino final em software é g_gfx.back, pertencente ao subsistema gráfico geral.

Esse backbuffer é compacto segundo a largura lógica.

O framebuffer frontal pode possuir pitch diferente.

Código de renderização escreve no backbuffer.

gfx_present copia depois somente os dirty rectangles para g_gfx.front, respeitando o pitch do framebuffer frontal linha a linha.

Assim, a composição do desktop pode usar endereçamento x/y simples sem carregar o stride de hardware por todas as operações de UI.

O stride específico do dispositivo fica concentrado na fronteira de apresentação.

## Superfícies de aplicações são separadas do backbuffer

Aplicações CLVM normalmente não desenham diretamente em g_gfx.back.

Cada slot da linguagem possui um contexto gráfico com sua própria superfície de pixels.

Builtins como fillrgb, text, glyph e operações 2D/3D modificam essa superfície do slot.

O compositor posteriormente obtém o ponteiro através de:

    lang_slot_pixels(slot)

Existe assim uma separação útil:

- a aplicação altera sua superfície;
- o compositor copia essa superfície para o backbuffer;
- a apresentação copia o backbuffer para o framebuffer frontal.

Essa separação reduz o acoplamento entre desenho da aplicação e layout físico do framebuffer.

## Superfícies publicadas

O runtime da linguagem adiciona um mecanismo de publicação.

lang_slot_publish copia os pixels gráficos ativos do slot para front_pixels.

Se a alocação publicada não existir ou não corresponder às dimensões atuais, a função realoca:

    width * height * sizeof(uint32_t)

e copia a superfície com gfx_fast_copy_u32.

lang_slot_pixels prefere a superfície publicada quando as dimensões coincidem.

Caso contrário retorna a superfície gráfica ativa.

No caminho de syscalls CLVM, o builtin wait publica o slot antes de colocar a VM em espera.

Isso fornece ao compositor uma espécie de snapshot para aplicações que cedem execução regularmente.

Não é um sistema transacional atômico de buffers: alocação, cópia e composição continuam sendo operações comuns de software.

Mesmo assim, reduz a chance de o compositor ler exatamente o mesmo buffer enquanto a aplicação desenha o próximo frame.

## Ownership e ciclo de vida das superfícies

Um slot da linguagem possui seu estado gráfico e sua cópia publicada opcional.

Uma Task do tipo TASK_APP armazena o ID do slot associado.

app_window_open liga os dois:

    task->state.app.lang_slot = slot
    lang_bind_task(slot, task_id)

A Task representa o objeto visível no desktop, enquanto o slot mantém execução e pixels da aplicação.

Se app_run descobre que o slot não é mais usado, fecha a Task.

No sentido inverso, caminhos de fechamento da janela solicitam encerramento do slot.

Essa associação bidirecional é importante: uma VM morta não deve deixar janela obsoleta, e uma janela fechada não deve deixar uma VM invisível consumindo recursos.

## Tabela de tasks e z-order

A camada de janelas usa um array fixo de no máximo 32 tasks.

Cada task ativa recebe um valor z crescente.

task_raise faz:

    task->z = g_next_z++

e também torna a task focada.

A implementação não normaliza os valores z a cada raise.

Para a escala atual e um contador uint32_t isso é simples, embora um overflow teórico não seja tratado explicitamente.

A regra de composição efetiva aparece em task_run_all.

## Renderização de baixo para cima

task_run_all não percorre simplesmente o array.

A função busca repetidamente a task ativa e não minimizada com o menor z acima do último z emitido.

Logo a ordem é:

    menor z primeiro
    maior z depois

Como renderizações posteriores sobrescrevem pixels anteriores no backbuffer comum, tasks com z maior aparecem por cima.

Com no máximo 32 slots, essa seleção é simples e limitada.

O custo de metadados no pior caso é O(T²), onde T é a quantidade de slots.

Com T <= 32, esse custo é pequeno em comparação com cópias grandes de pixels.

Um compositor maior normalmente manteria uma estrutura ordenada explícita.

## Sem eliminação geral de oclusão

O compositor atual renderiza tasks ativas em z-order mesmo quando uma janela opaca superior cobre completamente uma inferior.

Não há uma etapa genérica de subtração de regiões visíveis.

Por isso o sistema pode desenhar pixels que serão imediatamente sobrescritos.

Isso é correto, mas não ideal em desempenho.

Compositores de desktop maduros costumam calcular oclusão ou manter superfícies retidas em GPU.

O ChrisOS atual prioriza simplicidade e capacidade de inspeção.

## Dois modos principais de janela

app_run distingue superfícies parecidas com jogos de aplicações comuns de UI.

Para superfícies de jogo:

- o kernel desenha o chrome;
- a imagem da aplicação é escalada para a área de conteúdo;
- a aplicação pode continuar renderizando em resolução própria.

Para aplicações de UI comuns:

- a superfície é copiada 1:1;
- a geometria da Task é ajustada às dimensões do slot;
- depois o kernel desenha título e bordas.

É uma arquitetura híbrida.

A aplicação possui o conteúdo; o kernel possui partes importantes do chrome do desktop.

## Superfícies de jogos

app_is_game classifica a superfície parcialmente por suas dimensões.

Tamanhos HD entre 640x480 e 1024x768 são aceitos, além de dimensões menores próximas ao padrão de jogos CLVM.

app_game_chrome desenha:

- barra de título;
- minimizar;
- maximizar/restaurar;
- fechar;
- handle de resize.

A área de conteúdo começa abaixo do chrome.

clvm_sys_blit_scaled delega a gfx_blit_scaled, permitindo dimensionar o conteúdo da aplicação ao retângulo da janela.

O scaler atual é nearest-neighbor.

Isso desacopla a resolução do render da aplicação do tamanho visível da janela.

## Superfícies comuns de UI

Aplicações CLVM que não são classificadas como jogo são compostas com clvm_sys_blit_to.

A função faz cópia 1:1 apenas da interseção superior esquerda.

Não existe scaling.

Ela recorta aos limites do desktop, marca a região copiada como dirty e faz cópias por linha com gfx_fast_copy_u32.

Após a cópia, app_run normalmente pinta barra de título e bordas do kernel.

Assim, os pixels finais são combinação de conteúdo da aplicação e chrome controlado pelo kernel.

## Casos especiais do desktop e taskbar

Duas aplicações CLVM recebem tratamento especial.

APPS/DESKTOP/DESKTOP.CC cria uma superfície com tamanho da tela e solicita posição na origem.

APPS/TASKBAR/TASKBAR.CC cria uma superfície curta de largura total na parte inferior.

app_run reconhece essas geometrias depois de copiar os pixels do slot.

Para uma task cobrindo a tela inteira desde a origem, chama:

    ui_paint_desktop()

Para uma superfície parecida com taskbar, chama:

    ui_paint_taskbar_strip(...)

Essas funções do kernel repintam desktop ou taskbar depois que a superfície CLVM já foi copiada.

Portanto existe ownership duplicado ou sobreposto: programas CLVM de desktop/taskbar geram seu próprio conteúdo visual e o kernel possui código especial que pinta visuais equivalentes novamente.

A implementação atual não deve ser descrita como shell puramente controlado pelas aplicações.

É uma arquitetura híbrida de transição.

## Consequências dos casos especiais

Essa duplicação produz efeitos concretos.

Primeiro, o desktop visível pode diferir dos pixels produzidos por DESKTOP.CC porque o kernel repinta depois.

Segundo, alterar apenas o código CLVM do desktop pode não alterar todos os elementos observados.

Terceiro, políticas conceituais de taskbar existem simultaneamente em aplicação e kernel.

Isso aumenta o risco de divergência.

Uma arquitetura futura deveria escolher uma autoridade mais clara:

- superfícies do shell totalmente controladas pelas aplicações; ou
- shell inteiramente controlado pelo window manager/kernel.

Ambas são viáveis; ownership misto exige reconciliação constante.

## Movimento e resize de janelas

Alterações de geometria produzem damage.

task_move:

1. guarda o frame antigo;
2. apaga a região antiga usando a cor do desktop;
3. altera x/y;
4. marca o novo frame como dirty.

task_resize segue estratégia semelhante.

Essa abordagem é simples, mas não reconstrói imediatamente uma janela inferior que estava coberta pela janela movida.

A recuperação correta depende do frame normal redesenhar novamente todas as tasks em z-order.

Portanto mover janela não é apenas mover um bitmap.

É uma alteração de estado seguida por reconstrução da cena.

## Fechamento e minimização

task_close apaga o frame, limpa o slot da task e remove o foco se necessário.

task_minimize apaga o frame, muda o modo, interrompe dragging e perde o foco quando aplicável.

task_run_all ignora tasks minimizadas.

Novamente, pintar a cor do desktop no lugar antigo é apenas estado intermediário.

Janelas inferiores precisam redesenhar no frame seguinte para restaurar seu conteúdo.

O modelo é baseado em redraw, não em restauração automática dos pixels ocultos.

## Maximização e restauração

Uma task maximizada preserva o frame anterior em WindowState.restore.

task_maximize apaga o frame antigo, salva a geometria de restauração quando necessário, aplica os novos bounds e marca a região.

task_restore apaga o frame atual, recupera a geometria anterior e marca o resultado.

A máquina de estados separa, portanto, geometria lógica de pixels desenhados.

O compositor produz novamente a imagem a partir do estado.

## Damage tracking

A maior parte das primitivas gráficas chama gfx_mark_dirty.

Blits de superfícies também marcam sua área de destino.

Movimento e resize marcam regiões afetadas.

gfx_mark_dirty recorta os retângulos aos limites da tela e combina regiões que se tocam.

A lista global guarda no máximo 32 regiões.

Se essa capacidade for excedida, o sistema substitui a lista por um único retângulo de tela inteira.

Assim, saturação dos metadados não causa perda de correção.

A troca é maior volume de cópia.

## Composição e damage são contratos separados

Desenhar no backbuffer altera pixels.

Damage tracking registra quais pixels precisam chegar ao framebuffer frontal.

Um bug de composição pode produzir backbuffer errado mesmo com dirty tracking perfeito.

Um bug de dirty tracking pode deixar o frontbuffer desatualizado mesmo que o backbuffer esteja correto.

Por isso os dois mecanismos possuem evidências de teste separadas.

## Composição do cursor

O cursor do mouse é desenhado por software no mesmo backbuffer.

desktop_frame executa:

    ui_undraw_cursor()
    task_run_all(ticks)
    ui_draw_cursor()

ui_draw_cursor primeiro salva os pixels 12x12 que estão sob o ponteiro em um buffer estático.

Depois desenha o cursor.

No frame seguinte, ui_undraw_cursor restaura os pixels salvos antes que as tasks sejam redesenhadas.

É a técnica clássica de save-under.

Ela é separada do z-order das aplicações: o cursor é desenhado depois das tasks, portanto aparece acima delas.

## Por que o cursor é desenhado em software

Comentários do código registram que o caminho de cursor por virtio-gpu é aceito na configuração QEMU testada, mas a sprite não aparece visualmente como esperado.

O código ainda chama vgpu_cursor_move quando o cursor virtual está ativo, porém sempre desenha um cursor em software no framebuffer para garantir visibilidade.

É um workaround baseado no comportamento observado do backend.

Não deve ser generalizado como exigência de que cursores de hardware sejam sempre inviáveis.

## Fronteiras de correção do cursor

A estratégia save-under exige sequência disciplinada.

O cursor antigo precisa ser removido antes do redraw das tasks.

Os novos pixels sob o cursor só devem ser salvos depois que o desktop foi composto.

A região do cursor é marcada dirty tanto na restauração quanto no novo desenho.

Se outro código modificasse o backbuffer sob o cursor fora dessa sequência, restaurar g_cur_under poderia reintroduzir pixels antigos.

O pipeline atual evita isso centralizando as operações de cursor no frame do desktop.

## Cadência de frames

desktop_run aguarda o tick global avançar após cada frame.

Durante a espera, o processador atende polling de TLB e executa hlt.

A cadência fica ligada ao timer do sistema, e não a um evento de vertical blank do display.

Não existe protocolo explícito de sincronização compositor/display que garanta apresentação sem tearing.

Um backbuffer de software evita desenhar diretamente no scanout, mas gfx_present ainda copia enquanto o dispositivo pode estar lendo o frontbuffer.

Portanto a arquitetura atual não deve ser descrita como sincronizada por vsync.

## Ordem entre input e composição

desktop_frame faz polling dos dispositivos de ponteiro antes de decidir foco.

Um clique esquerdo pode elevar e focar a task sob o cursor.

Depois eventos de teclado/texto são enviados ao slot da aplicação focada.

Somente então o frame remove o cursor, executa tasks em z-order e desenha o novo cursor.

Isso permite que o clique altere o z-order no mesmo frame em que o redraw ocorre.

task_run_all já verá os novos valores z.

## Foco e wallpaper

task_focus_at normalmente chama task_raise na janela escolhida.

Há uma exceção para uma task que cobre o framebuffer inteiro desde a origem.

Essa task de wallpaper pode ganhar foco sem ser elevada.

Isso evita que o desktop de fundo passe acima de janelas normais quando o usuário clica numa área vazia.

Da mesma forma, a operação CLVM surf_raise não eleva uma task reconhecida como wallpaper de tela inteira.

São invariantes pequenos, mas importantes.

## Largura de banda de memória

Composição em software pode copiar o mesmo pixel várias vezes num frame.

Uma aplicação inferior pode escrever no backbuffer, outra superior sobrescrever a mesma área e gfx_present finalmente copiar o resultado para o frontbuffer.

Superfícies CLVM publicadas ainda podem adicionar outra cópia integral quando a aplicação chama wait.

Para uma superfície W por H, uma cópia completa de pixels de 32 bits movimenta:

    4 * W * H bytes

de payload de imagem entre origem e destino.

Em resoluções de desktop, cópias redundantes de janelas inteiras podem dominar CPU e memória.

O damage tracking limita a cópia final para o frontbuffer, mas não elimina overdraw durante composição.

## Modelo de concorrência

O caminho principal é serializado pelo frame loop.

task_run_all e o backbuffer global não são protegidos aqui por um lock de compositor.

As superfícies publicadas ajudam a separar escrita da aplicação da leitura pelo compositor, mas a arquitetura não é um compositor transacional multithreaded geral.

Estruturas compartilhadas incluem:

- tabela de tasks;
- ID da task focada;
- contador de z;
- dirty rectangles;
- estado save-under do cursor.

Qualquer evolução com renderização concorrente precisa definir ownership e sincronização desses objetos.

## Complexidade

Considere T como quantidade de tasks ativas e P_i como quantidade de pixels desenhados/copiedos pela task i.

A ordenação atual custa no máximo O(T²).

O trabalho em pixels é aproximadamente:

    O(sum(P_i))

mais o custo da apresentação das regiões dirty.

Sem occlusion culling, P_i pode incluir áreas totalmente cobertas.

O merge de damage permanece limitado porque a lista possui no máximo 32 registros.

Na escala atual, largura de banda de pixels normalmente pesa mais que a ordenação de metadados.

## Evidência de validação

tools/test_task_window.c verifica contratos relacionados à composição:

- task minimizada não é executada;
- raise restaura task minimizada para renderização normal;
- maximize/restore preservam geometria;
- move/resize produzem damage;
- hit testing escolhe a janela sobreposta com maior z;
- ciclos repetidos de abrir/fechar reutilizam slots sem deixar tasks vivas.

O stress test abre e fecha 1000 tasks e compara a contagem de tasks ativas.

tools/test_graphics_present.c cobre a etapa de apresentação:

- pitch do frontbuffer é respeitado;
- dirty rectangle parcial copia somente a área esperada;
- alteração não marcada do backbuffer não é apresentada;
- saturação da lista dirty cai para cópia de tela inteira.

Em conjunto, os testes cobrem invariantes importantes de estado, ordenação e apresentação.

## Lacunas de validação

Não existe atualmente um teste host dedicado que monte várias janelas e compare a imagem compositada completa pixel a pixel.

Também não há cobertura integral para:

- janelas semitransparentes sobrepostas;
- equivalência visual dos casos especiais de desktop/taskbar;
- save-under do cursor em todos os padrões de movimento;
- overflow do contador z;
- writers concorrentes;
- desempenho de oclusão;
- timing real de vsync/scanout;
- conclusão física da GPU.

Esses itens permanecem alvos separados de validação.

## Comportamento de falhas

As APIs do caminho são defensivas, porém com poucos diagnósticos estruturados.

Se a superfície de aplicação não existe, app_run retorna sem desenhar.

Se o slot da aplicação desaparece, a Task é fechada.

Se app_window_open não encontra slot livre na tabela de tasks, encerra o slot da aplicação.

Falha de alocação em lang_slot_publish limpa as dimensões da cópia publicada; depois lang_slot_pixels pode voltar a fornecer a superfície gráfica ativa.

Isso preserva funcionalidade, mas reduz o isolamento entre produtor e consumidor daquele frame.

O compositor não fornece relatório estruturado por frame.

## Segurança e isolamento

A composição do desktop não é, por si só, uma fronteira de segurança para memória nativa arbitrária.

O window manager confia em estruturas Task do kernel e ponteiros obtidos do runtime da linguagem.

Operações de desenho CLVM escrevem em superfícies do próprio slot dentro do modelo pretendido, e não em endereços arbitrários do desktop.

O foco determina qual aplicação recebe eventos de teclado/texto.

Assim, estado de foco faz parte do contrato de isolamento do desktop.

Entretanto, a arquitetura gráfica sozinha não comprova isolamento de processo; isso depende também de memória CLVM/processos, validação de syscalls e ciclo de vida documentados em outros capítulos.

## Limitações atuais

As principais fronteiras são:

- composição por software em um único backbuffer global;
- máximo de 32 tasks;
- traversal O(T²) de z-order;
- ausência de occlusion culling geral;
- ausência de texturas GPU por janela ou hardware planes;
- ausência de protocolo atômico de transações de superfície;
- ausência de sincronização explícita com vblank;
- ausência de garantia de tear-free;
- ownership híbrido entre desktop/taskbar CLVM e repaint do kernel;
- scaling nearest-neighbor para janelas de jogos;
- cursor em software com save-under;
- lista de damage de capacidade fixa;
- diagnósticos estruturados limitados;
- ausência de teste end-to-end da composição completa.

Essas são propriedades da arquitetura atual, não exigências do futuro do ChrisOS.

## Limite entre estado atual e roadmap

Evoluções naturais incluem:

- uma única autoridade para desktop/taskbar;
- superfícies retidas com metadados explícitos de formato;
- cálculo de regiões de oclusão;
- damage por superfície;
- publicação de superfícies com generation IDs ou transações atômicas;
- estrutura ordenada específica do compositor;
- composição opcional por texturas GPU;
- cursor de hardware quando confiável;
- frame pacing sincronizado ao display;
- presentation fences explícitas;
- testes de regressão por screenshots;
- telemetria de overdraw e largura de banda.

Esses recursos devem ser tratados como roadmap até haver código e testes que os comprovem.

## Proveniência da revisão

Este capítulo documenta a composição do desktop conforme observada no main do ChrisOS na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

kernel/tools/app_window.c é a principal ponte entre superfícies dos slots da linguagem e Tasks de janela. compiler/lang_pipeline.c define publicação e ownership dos slots. kernel/wm/task.c define ordenação e estado das janelas. kernel/wm/ui.c define chrome, desktop e cursor. kernel/gfx/graphics.c define damage tracking e apresentação final. kernel/wm/main.c estabelece a ordem do frame. tools/test_task_window.c e tools/test_graphics_present.c fornecem evidência executável direta para os contratos de estado e apresentação descritos.
