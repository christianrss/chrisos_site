---
id: chrisshell
lang: pt-br
type: technical-chapter
volume: 11-desktop
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - APPS/SHELL/SHELL.CC
  - APPS/SHELL/SHELL.LST
  - APPS/SHELL/Makefile
  - LIB/WIN.CC
  - LIB/UI.CC
  - LIB/APP.CC
depends_on:
  - input-routing
  - window-manager
  - desktop-applications
  - chrisc-clvm
  - chrisfs
---

# ChrisShell: o ambiente gráfico de comandos

O ChrisShell é a aplicação orientada a comandos do desktop ChrisOS. É escrito em ChrisC, combinado com as bibliotecas comuns de janela, UI e aplicação, compilado para bytecode CLVM e instalado na imagem como `APPS/SHELL/SHELL.CLV`.

Seu papel vai além de exibir um prompt. O shell expõe operações de sistema de arquivos, execução de programas, compilação, builds, lançamento de aplicações, diagnóstico do runtime e recarga de bibliotecas por meio de uma interface interativa pequena. Ele é, portanto, uma das principais superfícies de controle que conectam o desktop à pilha de desenvolvimento self-hosted.

## Arquitetura

```text
entrada do teclado
      |
      v
buffer da linha de comando
      |
      v
dispatcher run_line()
      |
      +--> ChrisFS: pwd/cd/ls/cat/mkdir/rm
      +--> compilador: cc
      +--> build: make
      +--> runtime: run/app_spawn
      +--> diagnóstico: heap/fps
      +--> bibliotecas dinâmicas: reload
      |
      v
log de saída com scroll
```

O shell é uma aplicação, não o interpretador de comandos do kernel. Os comandos são reconhecidos em `APPS/SHELL/SHELL.CC` e traduzidos para interfaces de biblioteca ou syscalls disponíveis a ChrisC/CLVM.

## Estado da linha de comando

A linha atual fica no array fixo de 160 bytes `g_line` e seu comprimento lógico em `g_n`. É uma interface deliberadamente limitada. Ela não implementa uma linguagem de comandos arbitrariamente grande nem um parser compatível com POSIX.

`starts_word()` reconhece um comando somente quando o byte seguinte é zero ou espaço. `arg_after()` avança além do prefixo e dos espaços para localizar o restante dos argumentos.

A gramática atual é, portanto, intencionalmente simples: comando mais restante da linha. A documentação não deve atribuir ao shell quoting, pipelines, redirecionamentos, expansão de variáveis, globbing ou job control enquanto esses mecanismos não estiverem implementados.

## Histórico

`g_hist` reserva 1280 bytes divididos em oito slots de 160 bytes. `hist_save()` armazena comandos em um histórico circular de oito entradas e `hist_load()` reconstrói uma entrada selecionada no buffer ativo.

É um projeto pequeno, porém útil para desenvolvimento de sistema operacional: comandos recentes de compilação, execução e diagnóstico podem ser recuperados sem exigir banco persistente de histórico.

## Modelo de diretório atual

O shell mantém sua própria string de diretório atual em `g_cwd`, atualmente com 96 bytes. `cwd_init()` começa na representação da raiz e `set_cwd()` altera o caminho armazenado. `join_cwd()` combina argumentos relativos com o diretório atual e aceita `/` inicial como caminho absoluto.

Na implementação revisada, `cd ..` retorna à raiz em vez de implementar uma travessia geral componente por componente. O modelo de caminhos é, portanto, mais simples que o de um shell Unix maduro.

## Comandos de sistema de arquivos

A superfície embutida inclui `pwd`, `cd`, `ls`, `cat`, `mkdir`, `rm` e `clear`. `pwd` mostra o diretório atual; `cd` verifica `isdir()`; `ls` enumera entradas com `readdir()`; `cat` abre e lê um arquivo em blocos limitados; `mkdir` cria diretórios; `rm` utiliza `unlink()`; e `clear` reinicializa o log visual.

`cmd_ls()` limita a enumeração a 512 iterações e filtra nomes para ASCII imprimível antes de registrá-los. `cmd_cat()` lê até 180 bytes por iteração e limita a operação a 64 iterações. Esses limites fazem parte do comportamento atual e impedem que uma operação da UI se transforme em loop ilimitado.

## Integração com o compilador

O comando `cc` resolve seu argumento contra o diretório atual e chama `sys_cc()`. O parser aceita a forma `cc -c`, ignorando `-c` antes de resolver o caminho do fonte.

Em caso de falha, o shell obtém o diagnóstico por `sys_err()` e o acrescenta ao log. Em sucesso, registra `cc ok`.

Isso cria uma rota interativa direta entre código-fonte armazenado no ChrisFS e o compilador ChrisC dentro do próprio ChrisOS.

## Integração com build

O comando `make` chama a interface de build do sistema em vez de iniciar um processo do host. Junto de `cc`, isso torna o ChrisShell parte do caminho de self-hosting: edição de fonte pode ser seguida de compilação/build sem sair do ambiente do sistema operacional.

ChrisShell e ChrisEditor são, portanto, complementares. O editor oferece interação orientada ao fonte; o shell fornece orquestração orientada a comandos.

## Execução de programas e aplicações

`run` resolve um caminho relativo a `g_cwd` e o envia para `sys_run()`. Diagnósticos de falha são obtidos por `sys_err()`.

O shell também possui atalhos explícitos para aplicações. No fonte revisado, `doom` inicia `GAMES/DOOM/ENGINE.CLV` por `app_spawn()`, enquanto `world` inicia `GAMES/WORLD.CLV`. Esses comandos funcionam como testes de integração porque atravessam carregamento de aplicações, execução CLVM, gráficos e gerenciamento de janelas.

Eles não constituem, por si, um gerenciador de pacotes ou linguagem geral de controle de processos.

## Diagnóstico do runtime

`heap` mostra valores retornados por `sys_heap_used_kb()` e `sys_heap_free_kb()`. `fps` informa taxa atual de frames junto de `sys_frame_p50()` e `sys_frame_p95()`.

Esses comandos transformam o shell em uma interface leve de observabilidade. Isso é particularmente útil no ChrisOS, onde aplicação, gráficos e runtime evoluem em conjunto e regressões podem ser difíceis de localizar.

## Recarga de bibliotecas

`reload` chama `lib_reload()`. Sem argumento, a implementação revisada utiliza `LIB/WIN.CLS` como padrão. Existe assim um caminho experimental para recarregar material de biblioteca do runtime sem expressar a operação como reboot completo.

A existência do comando não estabelece hot code replacement genérico. Sua semântica é exatamente aquela fornecida pela implementação atual de `lib_reload()`.

## Log de saída

A saída não é escrita em um fluxo de terminal ilimitado. `log_init()` tenta alocar 49152 bytes e recua para 8192 bytes se necessário. Quando o log se aproxima da capacidade, `log_trim()` descarta conteúdo antigo, normalmente removendo 4096 bytes antes de compactar o restante.

`log_line()` aceita ASCII imprimível e newline e limita a quantidade copiada de uma única mensagem. A UI pode assim renderizar histórico com scroll sem consumir heap indefinidamente.

Esse é um modelo de log de aplicação, não um emulador completo de terminal. O fonte revisado não estabelece emulação ANSI/VT, pseudo-terminais ou disciplina de linha TTY.

## Tratamento de erros

A maioria dos comandos registra um resultado compacto de sucesso ou falha. Erros de runtime/compilador podem acrescentar o texto retornado por `sys_err()`. Falha ao alocar o log grande degrada para uma alocação menor; se nenhum log existir, as rotinas retornam sem acessar ponteiro inválido.

A implementação é propositalmente direta. Não existem transações ou rollback no nível do shell para operações de sistema de arquivos.

## Fronteira de segurança

Do ponto de vista do usuário, ChrisShell parece uma interface privilegiada porque pode compilar, remover arquivos, iniciar aplicações e recarregar bibliotecas. Arquiteturalmente, porém, a autoridade real é determinada pelas syscalls e interfaces de runtime expostas pelo ChrisOS à aplicação CLVM.

Um futuro modelo de capabilities ou permissões deve, portanto, ser aplicado abaixo do parser de comandos. Ocultar um comando na UI não constitui fronteira de segurança.

## Limitações atuais

O shell revisado não é POSIX `sh`, Bash nem um ambiente TTY Unix. Seu parser é pequeno; o histórico é limitado a oito comandos; caminhos e linhas de comando possuem buffers fixos; enumeração de diretórios e `cat` utilizam loops limitados; a saída é um log gráfico próprio; e construções avançadas de linguagem de shell não são estabelecidas pelo fonte.

Essas restrições são pedagogicamente úteis porque deixam os mecanismos essenciais visíveis sem escondê-los sob uma grande camada de compatibilidade.

## Importância arquitetural

O ChrisShell ajuda a fechar o ciclo de desenvolvimento do ChrisOS:

```text
ChrisEditor -> fonte no ChrisFS
     |
     v
ChrisShell -> cc / make
     |
     v
programa CLVM
     |
     v
run / app_spawn
     |
     v
observar com heap / fps / erros
```

Um playground de sistema operacional self-hosted precisa de mais que um compilador isolado. Precisa de uma rota utilizável para chamar esse compilador, manipular fontes, iniciar programas gerados e inspecionar falhas. O ChrisShell fornece essa rota orientada a comandos na arquitetura atual do desktop.
