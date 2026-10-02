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

## Máquina de estados modal

O próprio fonte descreve o editor como um pequeno editor semelhante ao VI. Seus modos principais são Normal, Insert, Command, Visual e Visual-line. Escape retorna ao modo Normal. Os comandos incluem inserção com `i`, `a` e `o`, seleção visual com `v`/`V`, yank de linha com `yy`, paste com `p`/`P`, remoção com `dd` e `x`, busca com `/`, repetição da busca com `n`/`N` e movimentação com `h`, `j`, `k`, `l`, `0`, `$`, `gg` e `G`.

O modo de comando também conecta edição ao ambiente de desenvolvimento. O conjunto atual inclui `:w`, `:e`, `:n`, `:q`, `:wq`, `:cc` e `:make`. Assim, compilação não é apenas um fluxo externo no host: o editor possui caminhos explícitos para chamar o compilador e o sistema de build do ChrisOS.

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

## Navegação e viewport

O editor separa posição no documento da posição da viewport. `g_cur` acompanha o cursor, enquanto os estados de scroll vertical e horizontal são independentes. Valores em cache (`g_seen_*`) e `g_view_gen` permitem identificar mudanças da visão sem tratar cada frame como estado completamente novo.

`jump_line()` garante o índice de linhas por meio de `ensure_line_index()`, limita a linha solicitada ao intervalo conhecido, converte-a em deslocamento de bytes e depois ajusta a visualização para manter o cursor visível.

## Seleção e estado semelhante a clipboard

A seleção visual utiliza `g_sel_anchor`. Dados copiados ficam separados por meio de `g_yank`, `g_yank_len`, `g_yank_cap` e `g_yank_linewise`. Assim, o ChrisEditor possui seu próprio modelo semântico de seleção/yank em vez de depender de um clipboard global do desktop.

A distinção é arquiteturalmente importante: foco de entrada pertence ao sistema de janelas/tasks, enquanto o significado de uma sequência como `yy` pertence à máquina de estados do editor.

## Comportamento orientado a código-fonte

O editor reconhece nomes de arquivos associados a fonte e contém um pequeno modelo de palavras-chave ChrisC. Entre as palavras visíveis na implementação revisada estão `int`, `void`, `char`, `if`, `else`, `while`, `for`, `return`, `break` e `continue`. Dessa forma, o editor pode realizar renderização orientada a fonte sem depender de um language server separado.

Trata-se de um mecanismo lexical pequeno, não de um parser ChrisC completo. Coloração sintática não deve ser confundida com análise semântica do compilador.

## Integração com compilação e build

`do_compile()` verifica primeiro se o caminho atual corresponde a um arquivo-fonte reconhecido e então chama `sys_cc(g_path)`. Diagnósticos do compilador são copiados para um painel de erros por `capture_err()`. A rotina também procura um padrão `:<dígitos>` no diagnóstico e guarda a linha encontrada em `g_err_line`, permitindo navegação do erro para o código.

`do_make()` chama `sys_make("Makefile", "all")` e encaminha falhas ao mesmo painel de diagnóstico. Esses caminhos tornam o ChrisEditor uma interface inicial de self-hosting: editar, salvar, compilar, examinar diagnósticos e executar build podem ocorrer dentro do ambiente do sistema operacional.

## Navegação de arquivos

O editor possui estado de diretório e navegação em `g_dir`, `g_browse`, `g_scroll`, `g_hscroll`, `g_nshow` e `g_ntotal`. `join_path()` constrói o caminho de um filho respeitando a capacidade do destino, enquanto `parent_dir()` sobe um nível localizando a última barra.

Isso não substitui o gerenciador de arquivos dedicado. É uma navegação local ao editor, voltada a selecionar documentos sem abandonar o fluxo de edição.

## Memória e propriedade

O texto principal e a área de yank são alocações explícitas da aplicação. Arrays fixos armazenam caminhos, comandos, diagnósticos, índices de linha e estado transitório de renderização. A arquitetura é adequada ao modelo atual de aplicações CLVM porque deixa a propriedade dos dados explícita e evita depender de um grafo sofisticado de objetos de runtime.

A contrapartida são limites rígidos. No fonte revisado aparecem, por exemplo, caminhos de 512 bytes, índice de 8192 linhas, campos de comando/status de 80 bytes e painel de diagnóstico limitado. Chamadores e futuras extensões devem tratar esses limites como parte do comportamento atual.

## Comportamento em falhas

Falha de alocação é tratada com tentativas progressivamente menores para o buffer de texto; se todas falharem, operações do editor informam a ausência do buffer em vez de assumir memória válida. Falhas ao abrir ou salvar arquivos atualizam o status. Erros de compilação e make preservam texto de diagnóstico para o usuário.

A implementação continua experimental. Uma operação bem-sucedida do editor não implica semântica transacional do sistema de arquivos, recuperação após crash ou preservação automática de alterações não salvas. Essas capacidades exigiriam mecanismos de persistência próprios.

## Validação

A evidência de regressão dedicada mais forte na revisão analisada é `tools/test_editor_path.c`. O teste compila e executa sob CLVM um algoritmo ChrisC de cópia limitada, verifica fronteiras da capacidade dos caminhos e bytes sentinela e confirma que o fonte real do editor continua utilizando cópias limitadas para caminho, diretório e status.

O editor também funciona como carga de integração quando o corpus de aplicações é compilado para a imagem ChrisOS. Seu `EDITOR.LST` depende explicitamente de `LIB/WIN.CC`, `LIB/UI.CC`, `LIB/APP.CC` e `EDITOR.CC`.

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
