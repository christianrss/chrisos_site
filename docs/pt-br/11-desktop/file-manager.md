---
id: file-manager
lang: pt-br
type: technical-chapter
volume: 11-desktop
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - APPS/EXPLORER/EXPLORER.CC
  - APPS/EXPLORER/EXPLORER.LST
  - APPS/EXPLORER/Makefile
  - LIB/WIN.CC
  - LIB/UI.CC
  - LIB/APP.CC
  - compiler/lang_pipeline.c
  - kernel/lang/clvm_sys.c
  - kernel/fs/cfs.h
  - tools/test_cfs_paths.c
symbols:
  - cwd_set
  - name_ok
  - copy_show
  - is_clv
  - is_textish
  - join_path
  - parent_cwd
  - open_entry
  - count_entries
  - entry_at
depends_on:
  - input-routing
  - window-manager
  - desktop-applications
  - chriseditor
  - chrisfs
---

# Gerenciador de arquivos: Explorer do ChrisOS

O gerenciador de arquivos do ChrisOS é implementado pela aplicação Explorer em `APPS/EXPLORER`. É um programa ChrisC compilado para bytecode CLVM e combinado, no source list, com as bibliotecas comuns de janela, UI e aplicação. Ele oferece uma visão gráfica dos diretórios do ChrisFS e conecta tipos de arquivo ao restante do desktop.

A implementação é intencionalmente pequena. Seu valor principal é arquitetural: demonstra enumeração de diretórios, navegação, seleção, scrolling e despacho de aplicações usando as mesmas interfaces disponíveis para outras aplicações ChrisC.

## Caminho de execução

```text
diretório ChrisFS
      |
      v
readdir()
      |
      v
filtro de entradas do Explorer
      |
      v
seleção + scrolling
      |
      +--> diretório -> altera cwd
      +--> .CLV      -> inicia aplicação
      +--> texto     -> inicia ChrisEditor
      |
      v
gerenciador de janelas / aplicações CLVM
```

O gerenciador de arquivos funciona, portanto, como ponte entre o estado persistente do sistema de arquivos e as aplicações do desktop.

## Construção da aplicação

`APPS/EXPLORER/EXPLORER.LST` inclui `LIB/WIN.CC`, `LIB/UI.CC`, `LIB/APP.CC` e `APPS/EXPLORER/EXPLORER.CC`. O Makefile compila esse conjunto em `APPS/EXPLORER/EXPLORER.CLV`.

É o mesmo modelo utilizado por ChrisEditor e ChrisShell: comportamento escrito em ChrisC, serviços comuns fornecidos por bibliotecas e programa CLVM resultante executado no ambiente de aplicações do ChrisOS.

## Modelo de estado

O diretório atual fica em `g_cwd[96]`. Entradas utilizam `g_ent[64]`, caminhos montados usam `g_path[160]` e `g_show[64]` guarda a porção visível de caminhos longos.

Seleção e viewport são representadas explicitamente: `g_sel` identifica a entrada selecionada, `g_scroll` é o deslocamento vertical e `g_hscroll` é o deslocamento horizontal do caminho. `g_ntotal` registra o total de entradas aceitas e `g_nshow` acompanha as linhas renderizadas no frame atual.

Esses buffers fixos e contadores são parte da implementação atual, não uma abstração genérica de UI de filesystem com tamanho variável.

## Complexidade da enumeração

O Explorer não mantém um vetor persistente de directory entries.

`count_entries` percorre desde o índice zero até `readdir` terminar ou chegar a 512 tentativas. Durante rendering, `entry_at(i)` é chamado para cada entrada lógica visível e cada chamada recomeça do índice zero.

Com D entradas escaneadas/aceitas e V linhas visíveis, um frame pode realizar aproximadamente O(D + V*D) trabalho de enumeração no pior caso, com D <= 512.

Para o filesystem atual isso é simples e previsível, mas diretórios maiores podem produzir latência. Cachear entries reduziria chamadas repetidas ao custo de memória e invalidação.

## Enumeração de diretórios

`count_entries()` e `entry_at()` utilizam `readdir(g_cwd, index, g_ent)`. A enumeração é limitada a 512 tentativas. Uma entrada só é aceita quando `name_ok()` retorna sucesso.

`name_ok()` rejeita nomes vazios e bytes fora do intervalo ASCII imprimível, atualmente 32 a 126. O Explorer possui, portanto, um modelo de nomes exibíveis mais restrito que um gerenciador de arquivos com Unicode.

O projeto atual enumera novamente o diretório para contar entradas e para localizar determinada entrada selecionada/visível. Isso mantém pouco estado na aplicação, ao custo de repetir travessias do filesystem.

## Buffers da aplicação versus ChrisFS

Explorer utiliza `g_cwd[96]`, `g_ent[64]` e `g_path[160]`. A camada ChrisFS, por outro lado, define `CFS_PATH_MAX = 512`.

`cwd_set` e `join_path` copiam bytes até o zero terminal sem receber capacidade do destino. A representação da aplicação é, portanto, menor que o contrato do filesystem e os helpers não impõem esse limite menor.

Um caminho profundo mas válido em ChrisFS pode ultrapassar os buffers do Explorer. Isso é dívida de segurança de memória na camada de aplicação.

A evolução correta é usar cópia capacity-aware e retornar erro explícito de path longo, não depender de callers sempre produzirem strings menores.

## Construção de caminhos

`join_path()` concatena diretório atual, uma barra quando necessária e nome da entrada em `g_path`. `cwd_set()` substitui o diretório ativo e reinicializa scroll vertical, horizontal e seleção.

`parent_cwd()` procura a última barra no caminho e o trunca nesse ponto. Diferentemente do comportamento simplificado de `cd ..` no ChrisShell atual, o Explorer consegue subir progressivamente por componentes de caminhos aninhados.

A implementação revisada utiliza arrays fixos e cópias diretas de bytes. Essas rotinas não devem ser descritas como uma biblioteca geral de caminhos dinamicamente dimensionados.

## Despacho por tipo de arquivo

`open_entry()` determina o significado da ativação.

Um nome reconhecido por `is_clv()` é iniciado com `app_launch(g_path)`. Um arquivo textual reconhecido por `is_textish()` inicia `APPS/EDITOR/EDITOR.CLV` através de `app_spawn_arg()`, passando o caminho selecionado ao ChrisEditor. Se nenhuma classificação de arquivo for aplicada, mas `isdir(g_path)` tiver sucesso, o Explorer entra no diretório.

É uma forma compacta de associação:

```text
.CLV        -> launcher de aplicação CLVM
texto/fonte -> ChrisEditor
diretório   -> navegação do Explorer
```

A lógica de associação está codificada diretamente na aplicação. A revisão analisada não estabelece registry, banco MIME ou camada configurável de associações.

## Bordas do reconhecimento de extensão

Os predicates de associação são pequenos, mas seu comportamento exato é mais permissivo que o nome sugere.

`is_clv` exige pelo menos quatro bytes, ponto em `n-4` e verifica apenas se o último byte é `V` ou `v`. Os dois bytes intermediários não são comparados com `C` e `L`. Assim, um nome com formato `.XXV` pode ser classificado como CLV.

No ramo de extensões de quatro caracteres de `is_textish`, o código confere ponto e `TX`/`tx`, mas não valida o último `T/t`. O ramo `.CC/.cc` é mais estrito.

Como `open_entry` testa CLV antes de text e antes de `isdir`, esses predicates influenciam diretamente o dispatch.

O hardening deve usar comparação exata case-insensitive e testes dedicados.

## Reconhecimento de CLV

`is_clv()` verifica o formato da extensão e aceita `V`/`v` final. A implementação é propositalmente leve, não um parser completo de extensões case-insensitive.

Abrir um `.CLV` atravessa uma fronteira importante: um objeto do sistema de arquivos se torna entrada executável para a pilha desktop/runtime.

## Reconhecimento de arquivos de texto

`is_textish()` contém verificações pequenas para extensões orientadas a texto/código-fonte. Arquivos reconhecidos são encaminhados ao ChrisEditor, e não renderizados pelo próprio Explorer.

Essa separação mantém o gerenciador focado em navegação e despacho. Semântica de edição, gerenciamento de buffers, integração com compilador e renderização de código permanecem responsabilidades do ChrisEditor.

## Layout gráfico

O loop principal cria uma janela de 520×380 chamada `Files` através de `win_begin()`. O diretório atual aparece na parte superior, seguido pela linha de diretório pai e pela listagem.

A lista usa linhas de 18 pixels. A altura disponível determina `view`, o número de entradas visíveis. A linha selecionada é mantida dentro da viewport ajustando `g_scroll`. `win_vscroll()` fornece a barra vertical e `win_hscroll()` controla o deslocamento usado para exibir caminhos atuais longos.

A aplicação demonstra, assim, scrolling lógico e widgets reutilizáveis da biblioteca de janelas.

## Entrega de input

Explorer lê teclado com `ev_key()`, portanto herda os limites das filas de eventos do runtime CLVM documentados no capítulo de desktop.

O loop drena todas as keys pendentes. Up/down alteram `g_sel`; Enter chama `entry_at(g_sel)` e depois `open_entry`.

Mouse é edge-triggered por `g_prev`, evitando múltiplas ativações enquanto o botão fica pressionado. Coordenadas globais são convertidas para a área local usando `win_ox` e `win_oy`.

Overflow da fila de keyboard/text é, portanto, condição do runtime, não algo tratado por um buffer adicional do Explorer.

## Seleção e teclado

Eventos de teclado são lidos com `ev_key()`. No fonte revisado, código 7 move a seleção para cima, código 8 para baixo e código 3 ativa a entrada selecionada.

A seleção é limitada novamente sempre que o conteúdo do diretório muda, garantindo que `g_sel` permaneça válido. Quando o diretório está vazio, a seleção retorna a zero e a interface mostra `(empty dir)`.

Os códigos numéricos são uma convenção da interface de aplicação/input atual, e não scan codes de hardware.

## Interação com ponteiro

O estado do ponteiro vem de `mouse_btn()`, `mouse_x()`, `mouse_y()` e `win_mouse_in()`. A aplicação converte coordenadas globais para coordenadas locais da janela usando `win_ox()` e `win_oy()`.

Uma transição de pressionamento é detectada por `g_prev`, evitando ativações repetidas enquanto o botão permanece pressionado. Clicar na primeira linha visível chama `parent_cwd()`. Clicar em uma entrada calcula seu índice, atualiza `g_sel` e executa `open_entry()`.

Esse fluxo é um exemplo concreto de consumo das camadas de input routing e coordenadas de janela por uma aplicação desktop escrita em ChrisC.

## Exibição horizontal de caminhos

Caminhos longos não podem ultrapassar a área visual. `copy_show()` recebe um deslocamento em bytes e copia no máximo 46 bytes visíveis para `g_show`. A barra horizontal altera esse deslocamento.

Isso é clipping de apresentação, não truncamento do caminho no sistema de arquivos. O caminho atual permanece armazenado separadamente da string abreviada de exibição.

## Dispatch e fronteira de confiança

Ativar um objeto pode atravessar a fronteira entre namespace persistente e execução.

Nome classificado como CLV chama `app_launch(g_path)`. Nome text-like inicia `APPS/EDITOR/EDITOR.CLV` com `app_spawn_arg`, passando o path. Caso contrário, se for diretório, o Explorer altera o cwd.

Explorer não interpreta bytecode nem valida semântica do executável. Isso pertence ao loader/runtime.

Da mesma forma, associação de arquivo é política de UI, não fronteira de segurança. O runtime precisa manter validação e capabilities próprias mesmo se a UI classificar um nome incorretamente.

## Diretórios vazios e trabalho limitado

O loop acompanha explicitamente `g_empty`. Quando nenhuma entrada válida é retornada, o Explorer mostra `(empty dir)` em vez de uma lista vazia ambígua.

As varreduras param após no máximo 512 índices de `readdir()`. A renderização também termina ao esgotar o número de linhas visíveis. Esses limites são importantes em um ambiente gráfico porque evitam que um único frame percorra intencionalmente uma quantidade ilimitada de entradas.

## Relação com ChrisEditor e ChrisShell

As três aplicações apresentam visões diferentes do mesmo sistema:

```text
Explorer    -> navegação gráfica do filesystem
ChrisEditor -> manipulação de texto/código-fonte
ChrisShell  -> controle do filesystem/build/runtime por comandos
```

Explorer entrega arquivos textuais ao ChrisEditor. ChrisShell manipula o mesmo filesystem com comandos como `ls`, `cat`, `mkdir` e `rm`. Juntos, formam o ambiente atual de desenvolvimento voltado ao usuário sobre ChrisFS.

## Evidência executável e lacunas

Não há host test dedicado a `APPS/EXPLORER/EXPLORER.CC` no conjunto inspecionado.

A camada inferior possui `tools/test_cfs_paths.c`, que verifica diretórios aninhados, listagem, rename entre diretórios, remoção de arquivo/diretório e regras de path. Isso sustenta as primitivas ChrisFS usadas pelo Explorer.

O teste não cobre buffers 96/160 da aplicação, limite de 512 posições, invariantes de seleção/scroll ou predicates de extensão.

Gates de alto valor: classificação exata de extensões, diretórios sintéticos perto/acima de 512 posições, seleção após shrink do diretório, paths aninhados acima de 95/159 bytes e equivalência entre ativação por mouse e teclado.

## Resumo de complexidade

| Operação | Algoritmo atual | Custo |
|---|---|---|
| contar entries | `readdir` sequencial | O(D), D <= 512 |
| localizar entry n | rescan desde zero | O(D) |
| renderizar V entries | V rescans | O(V*D) |
| subir diretório | scan pela última barra | O(P) |
| montar path | copiar cwd + nome | O(P + N) |
| classificar extensão | probes após calcular length | O(tamanho do nome) |
| mover seleção | atualização de inteiro | O(1) |

## Limitações atuais

O Explorer revisado não pretende equivaler a um gerenciador de arquivos maduro. O fonte não estabelece diálogos de copiar/mover, drag-and-drop, thumbnails, painel de propriedades/metadados, busca recursiva, navegação por mounts, interface de permissões, lixeira, associações configuráveis ou nomes Unicode.

A enumeração é limitada, associações ficam embutidas no fonte e caminhos/nomes utilizam arrays fixos de bytes. Essas restrições devem ser tratadas como fatos da implementação.

## Importância arquitetural

O Explorer demonstra que o ChrisOS pode expor objetos do sistema de arquivos a aplicações gráficas sem colocar política de gerenciamento de arquivos dentro do kernel. ChrisFS fornece operações de arquivo/diretório; a aplicação decide como enumerar, apresentar e ativar objetos; bibliotecas de janela/input fornecem interação; e o runtime inicia a aplicação CLVM selecionada.

Essa separação é importante para o objetivo educacional do projeto: mecanismo de filesystem, política de aplicação, comportamento da GUI e carregamento de executáveis permanecem observáveis como camadas distintas.
