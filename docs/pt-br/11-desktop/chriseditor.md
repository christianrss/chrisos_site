---
id: chriseditor
lang: pt-br
type: technical-chapter
volume: 11-desktop
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - APPS/EDITOR/EDITOR.CC
  - APPS/EDITOR/EDITOR.LST
  - APPS/EDITOR/Makefile
  - LIB/WIN.CC
  - LIB/UI.CC
  - LIB/APP.CC
  - tools/test_editor_path.c
  - kernel/wm/desktop.c
  - compiler/lang_pipeline.c
  - compiler/lang_pipeline.h
  - kernel/lang/clvm_sys.c
symbols:
  - buf_init
  - rebuild_line_index
  - line_for_pos
  - insert_at
  - delete_range
  - insert_block
  - find_from
  - handle_key
  - handle_text
  - draw_text_view
  - do_compile
  - do_debug
  - do_step
  - do_over
  - do_out
  - do_cont
  - do_bp
  - do_watch
depends_on:
  - input-routing
  - window-manager
  - desktop-applications
  - chrisc-clvm
  - chrisfs
---

# ChrisEditor: um editor modal self-hosted

O ChrisEditor é o editor gráfico de texto e código-fonte do ChrisOS. Sua importância vai além da usabilidade do desktop: a aplicação faz parte do caminho entre um sistema que apenas executa programas e um sistema capaz de inspecionar, modificar, compilar e construir seu próprio software dentro do ambiente ChrisOS.

A implementação atual é escrita em ChrisC e compilada para bytecode CLVM. O código principal está em `APPS/EDITOR/EDITOR.CC`; `EDITOR.LST` combina o editor com as bibliotecas de janela, UI e aplicação, e o Makefile da aplicação produz `APPS/EDITOR/EDITOR.CLV`.

## Caminho de execução

A aplicação atravessa várias camadas do ChrisOS:

```text
teclado / ponteiro
       |
       v
roteamento de entrada
       |
       v
bibliotecas de janela + UI
       |
       v
máquina de estados do ChrisEditor
       |
       +--> E/S de arquivos ChrisFS
       |
       +--> syscalls de compilador / make
       |
       v
execução CLVM
```

Isso torna o editor uma carga de integração útil: falhas podem revelar defeitos no roteamento de entrada, foco de janelas, compilador ChrisC, CLVM, chamadas do sistema de arquivos, gerenciamento de memória ou repaint do desktop.

## Entrega de eventos pelo desktop

O ChrisEditor não lê diretamente a fila global de teclado do kernel. `desktop_frame` identifica a `TASK_APP` focada e envia key/text ao lang slot correspondente. O runtime mantém duas filas circulares independentes.

A capacidade atual é `LANG_EVQ = 8` para cada fila. Quando já existem oito keys ou oito textos pendentes, o próximo evento é descartado; o desktop não bloqueia nem aumenta a fila.

No loop principal do editor, `ev_key()` é drenado até retornar zero e depois `ev_text()` é drenado do mesmo modo. Key representa controles como setas, escape, enter e shortcuts; text representa caracteres imprimíveis.

Durante dragging ou resizing da janela, o desktop não seleciona o slot para entrega de key/text. A fila global ainda é drenada. Isso evita que interação de window management vire comando do editor, mas eventos produzidos nesse intervalo podem ser perdidos.

Mouse segue outro caminho: a biblioteca de janela consulta estado por polling e executa hit testing local de botões, scrollbars e regiões do editor.

## Máquina de estados modal

O próprio fonte descreve o editor como um pequeno editor semelhante ao VI. Seus modos principais são Normal, Insert, Command, Visual e Visual-line. Escape retorna ao modo Normal. Os comandos incluem inserção com `i`, `a` e `o`, seleção visual com `v`/`V`, yank de linha com `yy`, paste com `p`/`P`, remoção com `dd` e `x`, busca com `/`, repetição da busca com `n`/`N` e movimentação com `h`, `j`, `k`, `l`, `0`, `$`, `gg` e `G`.

O modo de comando também conecta edição ao ambiente de desenvolvimento. O conjunto atual inclui `:w`, `:e`, `:n`, `:q`, `:wq`, `:cc` e `:make`. Assim, compilação não é apenas um fluxo externo no host: o editor possui caminhos explícitos para chamar o compilador e o sistema de build do ChrisOS.

## Algoritmos de edição

O buffer contíguo deixa os custos explícitos.

`insert_at` desloca para a direita todos os bytes posteriores ao cursor. Inserir perto do início de um arquivo de n bytes é O(n). `delete_range` desloca o sufixo para a esquerda e também pode custar O(n). `insert_block` desloca o sufixo uma vez e depois copia o bloco inserido.

Esse desenho é adequado ao editor limitado atual, mas difere de rope ou piece table voltados a documentos muito maiores.

A busca também é simples. `find_from` percorre posições para frente ou para trás e compara o padrão em cada candidato. Com documento n e padrão m, o pior caso é O(n*m).

Esses custos são importantes porque responsividade do editor também funciona como sinal da eficiência conjunta de CLVM, memória e desenho.

## Modelo do buffer

O documento fica em um buffer de bytes alocado dinamicamente e referenciado por `g_buf`. `buf_init()` tenta inicialmente alocar 262144 bytes, depois reduz para 65536 e finalmente 8192 bytes. O comprimento atual fica em `g_len`, a capacidade em `g_cap` e o cursor é um deslocamento em bytes armazenado em `g_cur`.

Esse modelo é deliberadamente mais simples que rope, piece table ou árvores balanceadas. O armazenamento direto simplifica indexação e implementação sobre CLVM, mas uma inserção ou remoção no meio de um documento grande pode exigir o deslocamento de todo um sufixo do buffer. Para comprimento `n`, essas operações podem portanto atingir O(n).

A implementação mantém separadamente metadados de linhas em `g_line_starts` e `g_line_states`, com espaço para 8192 linhas indexadas. `g_line_index_dirty` informa quando o índice precisa ser reconstruído. Isso evita redescobrir todos os limites de linha em operações expressas em coordenadas de linha.

## Caminhos e cópia limitada

Os caminhos ficam nos arrays de 512 bytes `g_path` e `g_dir`. A rotina `copy_cap()` copia no máximo `cap - 1` bytes e sempre termina o destino. `path_set()`, `dir_set()` e `status_set()` utilizam essa operação limitada em vez de inserir um terminador em um índice não validado derivado do tamanho da origem.

Esse comportamento possui teste de regressão no host em `tools/test_editor_path.c`. O teste exercita comprimentos próximos ao limite do caminho e verifica bytes sentinela depois dos buffers de destino. Ele também inspeciona `EDITOR.CC` para garantir que a implementação de cópia limitada continue sendo utilizada. Isso constitui evidência concreta de validação para uma classe de corrupção de memória.

## Carregamento e salvamento

`load_file()` abre `g_path`, lê no máximo `g_cap - 1` bytes, acrescenta zero terminal e reinicializa cursor, scroll, dirty state e modo. `save_file()` escreve exatamente `g_len` bytes e limpa o indicador de modificação após a operação.

O editor atual trata, portanto, o documento principalmente como uma sequência de bytes. O fonte revisado não estabelece um modelo geral de texto Unicode; a documentação não deve sugerir essa capacidade.

## Índice de linhas e estado lexical

O editor mantém índice de linhas para evitar percorrer o texto desde o início em toda operação vertical.

`rebuild_line_index` faz um scan completo, grava offsets de início e um pequeno estado lexical para cada linha indexada. O estado permite saber se a linha começa dentro de comentário de bloco e acompanha string/comentário durante o scan.

A tabela comporta 8192 linhas. O rebuild é O(n) em bytes do documento.

`line_for_pos` usa busca binária em `g_line_starts`, reduzindo a conversão de byte-offset para linha a O(log L) depois que o índice está válido. Edições marcam `g_line_index_dirty`, então a próxima operação dependente do índice paga o rebuild.

É um meio-termo entre rescans frequentes e uma árvore incremental de parsing mais complexa.

## Navegação e viewport

O editor separa posição no documento da posição da viewport. `g_cur` acompanha o cursor, enquanto os estados de scroll vertical e horizontal são independentes. Valores em cache (`g_seen_*`) e `g_view_gen` permitem identificar mudanças da visão sem tratar cada frame como estado completamente novo.

`jump_line()` garante o índice de linhas por meio de `ensure_line_index()`, limita a linha solicitada ao intervalo conhecido, converte-a em deslocamento de bytes e depois ajusta a visualização para manter o cursor visível.

## Seleção e estado semelhante a clipboard

A seleção visual utiliza `g_sel_anchor`. Dados copiados ficam separados por meio de `g_yank`, `g_yank_len`, `g_yank_cap` e `g_yank_linewise`. Assim, o ChrisEditor possui seu próprio modelo semântico de seleção/yank em vez de depender de um clipboard global do desktop.

A distinção é arquiteturalmente importante: foco de entrada pertence ao sistema de janelas/tasks, enquanto o significado de uma sequência como `yy` pertence à máquina de estados do editor.

## Pipeline de renderização

`draw_text_view` desenha apenas a parte visível do documento. A primeira posição vem do índice de linhas; o renderer desenha gutter, acompanha estado lexical de string/comentário e escolhe cores simples de sintaxe.

Para reduzir chamadas individuais, o editor acumula runs de texto e chama `textruns`. O código faz flush quando a quantidade de runs se aproxima de 80 ou quando a área temporária de strings se aproxima de 1600 bytes.

Scroll vertical e horizontal são fornecidos pela biblioteca de janela. O caret é pintado separadamente por `paint_caret`, que converte cursor em linha/coluna usando o índice e o scroll horizontal.

O modelo continua byte/character oriented. Não estabelece layout de grafemas Unicode, shaping proporcional para código ou uma widget tree retida geral.

## Comportamento orientado a código-fonte

O editor reconhece nomes de arquivos associados a fonte e contém um pequeno modelo de palavras-chave ChrisC. Entre as palavras visíveis na implementação revisada estão `int`, `void`, `char`, `if`, `else`, `while`, `for`, `return`, `break` e `continue`. Dessa forma, o editor pode realizar renderização orientada a fonte sem depender de um language server separado.

Trata-se de um mecanismo lexical pequeno, não de um parser ChrisC completo. Coloração sintática não deve ser confundida com análise semântica do compilador.

## Integração com debugger

O ChrisEditor vai além de compile/run. O fonte possui controles de debugger baseados em `dbg_ctl`.

`do_debug` salva conteúdo dirty, arma debugging, compila, deriva o CLV de saída e inicia o programa. Quando o runtime informa uma linha de fonte, `dbg_follow` atualiza `g_dbg_line` e move a viewport para essa linha.

A interface possui caminhos para:

- step into;
- step over;
- step out;
- continue;
- stop/detach;
- toggle de breakpoint na linha atual;
- watch de endereço informado em decimal ou hexadecimal.

O painel exibe texto do debugger e o gutter destaca a linha ativa.

Isso é uma interface inicial de debugging source-level, não afirma a existência de debugger simbólico completo. Mapeamento e inspeção dependem das capacidades atuais do compilador/CLVM.

## Integração com compilação e build

`do_compile()` verifica primeiro se o caminho atual corresponde a um arquivo-fonte reconhecido e então chama `sys_cc(g_path)`. Diagnósticos do compilador são copiados para um painel de erros por `capture_err()`. A rotina também procura um padrão `:<dígitos>` no diagnóstico e guarda a linha encontrada em `g_err_line`, permitindo navegação do erro para o código.

`do_make()` chama `sys_make("Makefile", "all")` e encaminha falhas ao mesmo painel de diagnóstico. Esses caminhos tornam o ChrisEditor uma interface inicial de self-hosting: editar, salvar, compilar, examinar diagnósticos e executar build podem ocorrer dentro do ambiente do sistema operacional.

## Algoritmo do file browser interno

O browser local percorre entradas de diretório com `readdir` usando índices de 0 a 511.

`rebuild_index` conta nomes aceitáveis refazendo o scan desde o início. `entry_at(want)` faz outro scan desde o início até encontrar a entrada lógica solicitada. O modelo privilegia simplicidade em vez de manter um vetor cacheado de directory entries.

Arquivos considerados text-like podem ser carregados/salvos; diretórios são navegáveis. `join_path` monta caminhos respeitando capacidade.

Diretórios que exijam mais de 512 posições de scan ficam fora do modelo atual do browser, independentemente da capacidade teórica do ChrisFS.

## Navegação de arquivos

O editor possui estado de diretório e navegação em `g_dir`, `g_browse`, `g_scroll`, `g_hscroll`, `g_nshow` e `g_ntotal`. `join_path()` constrói o caminho de um filho respeitando a capacidade do destino, enquanto `parent_dir()` sobe um nível localizando a última barra.

Isso não substitui o gerenciador de arquivos dedicado. É uma navegação local ao editor, voltada a selecionar documentos sem abandonar o fluxo de edição.

## Memória e propriedade

O texto principal e a área de yank são alocações explícitas da aplicação. Arrays fixos armazenam caminhos, comandos, diagnósticos, índices de linha e estado transitório de renderização. A arquitetura é adequada ao modelo atual de aplicações CLVM porque deixa a propriedade dos dados explícita e evita depender de um grafo sofisticado de objetos de runtime.

A contrapartida são limites rígidos. No fonte revisado aparecem, por exemplo, caminhos de 512 bytes, índice de 8192 linhas, campos de comando/status de 80 bytes e painel de diagnóstico limitado. Chamadores e futuras extensões devem tratar esses limites como parte do comportamento atual.

## Comportamento em falhas

Falha de alocação é tratada com tentativas progressivamente menores para o buffer de texto; se todas falharem, operações do editor informam a ausência do buffer em vez de assumir memória válida. Falhas ao abrir ou salvar arquivos atualizam o status. Erros de compilação e make preservam texto de diagnóstico para o usuário.

A implementação continua experimental. Uma operação bem-sucedida do editor não implica semântica transacional do sistema de arquivos, recuperação após crash ou preservação automática de alterações não salvas. Essas capacidades exigiriam mecanismos de persistência próprios.

## Resumo de complexidade

| Operação | Algoritmo atual | Custo |
|---|---|---|
| inserir byte | deslocar sufixo | O(n) |
| remover range | deslocar sufixo | O(n) |
| paste de bloco | shift + cópia | O(n + k) |
| rebuild do índice | scan linear | O(n) |
| posição -> linha | busca binária após rebuild | O(log L) |
| busca textual | comparação ingênua | O(n*m) no pior caso |
| contar directory entries | até 512 readdir | O(D), D <= 512 |
| obter entrada n | novo scan desde zero | O(D) |
| enqueue/dequeue de key/text | ring fixo | O(1) |

A tabela descreve algoritmos observados no fonte, não resultados de benchmark. Latência real inclui execução CLVM e rendering.

## Validação

A evidência de regressão dedicada mais forte na revisão analisada é `tools/test_editor_path.c`. O teste compila e executa sob CLVM um algoritmo ChrisC de cópia limitada, verifica fronteiras da capacidade dos caminhos e bytes sentinela e confirma que o fonte real do editor continua utilizando cópias limitadas para caminho, diretório e status.

O editor também funciona como carga de integração quando o corpus de aplicações é compilado para a imagem ChrisOS. Seu `EDITOR.LST` depende explicitamente de `LIB/WIN.CC`, `LIB/UI.CC`, `LIB/APP.CC` e `EDITOR.CC`.

## Lacunas adicionais de validação

`tools/test_editor_path.c` é evidência forte e específica para bounded path copying: executa o algoritmo sob CLVM e verifica canários.

Não existe no conjunto inspecionado um teste dedicado equivalente para todas as operações editoriais. A existência do código não prova automaticamente índice de linhas em todas as combinações de comentário/string, comportamento em burst de eventos, grandes inserções ou sincronização da UI do debugger.

Gates úteis seriam: sequências aleatórias de edição comparadas a um buffer de referência host, comparação do line index com parser simples, testes na borda de 8192 linhas, bursts acima de `LANG_EVQ` e verificação de source mapping do debugger.

## Limitações atuais

A implementação revisada utiliza buffer de texto contíguo e estruturas auxiliares de tamanho fixo. Sua lógica orientada a código-fonte é deliberadamente pequena. A documentação não atribui ao sistema language server, edição por grafemas Unicode, arquitetura de múltiplos buffers, journal persistente de undo, edição colaborativa ou recuperação crash-safe porque essas propriedades não são estabelecidas pelo fonte revisado.

## Importância arquitetural

O ChrisEditor fecha um ciclo importante no ChrisOS:

```text
fonte ChrisC
   -> ChrisEditor modifica o fonte
   -> ChrisFS persiste o fonte
   -> sys_cc / sys_make constroem o programa
   -> CLVM executa os programas gerados
   -> desktop hospeda as aplicações resultantes
```

Para um sistema cujo objetivo é servir como playground de kernels, compiladores, máquinas virtuais e ferramentas de baixo nível, esse ciclo é mais importante que a quantidade de funcionalidades do editor. Ele demonstra que a pilha linguagem/runtime/filesystem/desktop começa a funcionar como ambiente de desenvolvimento, e não apenas como demonstração inicializável.
