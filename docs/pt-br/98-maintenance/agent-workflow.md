---
id: agent-workflow
lang: pt-br
type: technical-chapter
volume: 98-maintenance
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources: []
symbols: []
depends_on: []
related:
  - validation-evidence
  - source-policy
  - documentation-schema
---

# Manutenção documental de baixo contexto

## Objetivo

O corpus do ChrisOS foi desenhado para crescer muito além do que uma única tarefa de manutenção deveria carregar em contexto.

O modelo não presume que um agente precise reler todos os capítulos, todos os source files ou o repositório inteiro antes de atualizar uma página.

A unidade normal de trabalho é:

    uma página autoral
    + seus sources declarados
    + o diff relevante
    + pequeno resumo de dependencies
    + comandos explícitos de validação

Assim o custo cresce com a boundary alterada, não com o tamanho total do corpus.

## Princípio central

A regra principal é:

> O contexto deve ser selecionado por dependency declarada e evidência de revisão, não por busca semântica ampla em todo o corpus.

Semantic search continua útil quando a dependency é realmente desconhecida.

Mas não deve ser default quando o frontmatter já identifica o contract relevante.

Isso reduz custo e diminui o risco de misturar assumptions de subsystems não relacionados.

## Identidade canônica

Ferramentas de manutenção usam `id` e `lang` do frontmatter como identidade canônica.

Filename não define sozinho a identidade.

Exemplo:

    linux-development-environment.md

pode representar:

    id: development-environment-linux

A mesma regra vale para source map, curriculum, coverage e bilingual pairing.

Antes de concluir que um capítulo está ausente, o agente precisa ler o frontmatter.

## Grafo de dependências

Os campos principais são:

- `sources`;
- `symbols`;
- `depends_on`;
- `related`;
- `reviewed_revision`.

Cada um responde a uma pergunta diferente.

### sources

Paths concretos no repository ChrisOS cujo implementation suporta materialmente a página.

### symbols

Identifiers importantes dentro dos sources. Ajudam a reduzir large-file context.

### depends_on

Prerequisites conceituais no curriculum DAG.

### related

Páginas adjacentes úteis, mas não prerequisites.

### reviewed_revision

Commit do ChrisOS contra o qual a página foi reconciliada.

Juntos, esses campos formam o bounded maintenance graph.

## Reverse source map

`scripts/source_map.py` lê authored pages e gera duas estruturas determinísticas:

    page path -> metadata
    source path -> affected pages

Se:

    kernel/mm/pmm.c

muda, o tooling identifica as páginas que declararam esse source sem pedir a um modelo que adivinhe quais títulos "parecem relacionados".

Isso é mais confiável que filename similarity.

## Por que dependencies explícitas importam

Sem metadata explícita, as opções seriam ruins:

1. reler o corpus inteiro após cada mudança; ou
2. depender de guesses semânticos.

O metadata graph permite uma terceira opção:

> revisar exatamente as páginas que declararam o contract alterado.

A metadata pode estar incompleta, mas a incompletude se torna visível e corrigível.

## Detecção de stale pages

`scripts/stale_docs.py` compara cada página source-backed com o HEAD atual.

Conceitualmente:

    reviewed revision R
        |
        +-- source A
        +-- source B
        |
        v
    git diff R..HEAD -- A B

Se nenhum source declarado mudou, a página não fica stale apenas porque código não relacionado mudou.

Se algum source mudou, a página entra na generated review queue.

## Stale não significa incorreto

Uma página stale significa:

> alguma dependency declarada mudou desde a revisão analisada.

Não significa automaticamente:

> o prose está errado.

Refactor pode alterar linhas sem mudar contract.

Bug fix pode fortalecer behavior sem exigir rewrite.

Interface change pode exigir revisão grande.

O agente precisa ler o diff antes de decidir.

## Baseline indisponível

Stale detection e context pack dependem do `reviewed_revision` antigo existir no checkout.

Se o commit não puder ser resolvido, o estado correto é:

    unavailable-baseline

Nunca "unchanged".

Nesse caso, opções corretas incluem:

- obter Git history mais profunda;
- ler integralmente os sources atuais;
- fazer full reconciliation;
- atualizar reviewed revision somente depois.

Bumpar SHA apenas para limpar queue destrói o valor da ferramenta.

## Invalid revision

`stale_docs.py` separa páginas com revision inválida.

Isso importa porque:

    stale
    !=
    invalid baseline

Stale possui old point conhecido e diff conhecido.

Invalid baseline não possui anchor histórica suficiente.

## Context packs

`scripts/context_pack.py` cria um package bounded para uma página.

Inclui:

- `PAGE.md`;
- source material declarado;
- `DIFF.patch`;
- `META.json`;
- `DEPENDENCIES.json`;
- `INSTRUCTIONS.md`.

Esse package é o input preferencial para uma manutenção focada.

## Metadata do context pack

`META.json` registra:

- page path;
- ID;
- reviewed revision;
- source HEAD;
- sources;
- symbols;
- source hashes;
- dependencies;
- related IDs;
- diff status;
- packing mode.

Assim o agente consegue verificar provenance antes de interpretar o conteúdo.

O primeiro passo deve ser olhar `diff_status`.

## Full source versus symbol context

Large files podem ultrapassar um contexto útil.

Quando source é pequeno, o file completo é copiado.

Quando é grande e existem symbols, `context_pack.py` extrai janelas bounded ao redor desses identifiers.

O implementation atual usa aproximadamente 100 lines de contexto ao redor de cada hit e combina intervals sobrepostos.

Isso preserva locality sem copiar file inteiro.

## Quando symbol context basta

Symbol-centered context costuma bastar quando o claim depende de:

- initializer específico;
- parser;
- state transition;
- error path;
- resource lifecycle function.

Se semantics dependem de macros, tables, file-wide invariants ou helpers distantes, leia o source completo.

Bounded context é otimização, não proibição.

## Escape hatch --full

`context_pack.py --full` força sources completos.

Use quando:

- symbol windows omitiram helper necessário;
- file-level invariant importa;
- macro distante altera semantics;
- global table define comportamento;
- existe contradição não resolvida pelo pack estreito.

Não use `--full` automaticamente.

Isso anularia a arquitetura de baixo contexto.

## Dependency summaries

Context pack não copia recursivamente todo prerequisite e related page.

Ele grava summaries com:

- dependency ID;
- path;
- reviewed revision;
- headings.

Isso evita explosão recursiva.

Se um heading indicar que determinada definição é necessária, então leia explicitamente aquela page.

## Generated source atlas

`scripts/inventory.py` indexa textual source do ChrisOS.

Para cada file registra:

- path;
- line count;
- byte count;
- SHA-256;
- includes detectados;
- C-like symbols;
- source textual completo.

O atlas é deterministic source evidence.

Não é authored architecture.

## Por que o atlas reproduz source completo

Authored docs devem interpretar.

O atlas possui outra função: rastreabilidade exata.

Por isso generated pages preservam o file textual completo em uma revisão conhecida.

Não edite manualmente generated atlas pages.

Corrija source ou generator.

## Fatos gerados versus interpretação autoral

Automation é boa para fatos como:

- file existence;
- path;
- hash;
- size;
- include list;
- symbol position;
- manifest membership;
- word count;
- diff status.

Mas invariants e architectural meaning continuam em authored chapters.

Eles precisam explicar:

- ownership;
- concurrency;
- ABI;
- failure semantics;
- security;
- performance;
- subsystem boundaries;
- evidence limitations;
- roadmap.

## Coverage generation

`scripts/coverage.py` mede duas dimensões.

### Structural coverage

Existe authored page com o planned ID naquele idioma?

### Text-floor coverage

A page atinge o minimum word target do seu type?

O segundo indicador mede extensão textual, não correctness.

Targets atuais:

- concept: 1800;
- technical-chapter: 1800;
- subsystem: 2200;
- specification: 1600;
- source-commentary: 1200;
- demais authored technical pages: 900.

## Por que existe depth floor

Páginas muito curtas costumam omitir dimensões importantes como:

- ownership;
- error paths;
- validation;
- limitations;
- performance;
- concurrency.

O floor serve como trigger de review.

Não deve ser vencido com filler.

Expanda technical dimensions faltantes.

## next_work

`scripts/next_work.py` percorre curriculum order e reporta pages missing ou abaixo do target.

Assim a seleção de trabalho é determinística.

O script evita escolher sempre os chapters mais visíveis enquanto early curriculum permanece thin.

Também informa total restante.

## Curriculum versus source urgency

Curriculum order é adequado para expansion work.

Source staleness pode ser mais urgente.

Uma priority prática é:

1. invalid reviewed revision;
2. stale page com implementation change;
3. missing planned page;
4. thin page em curriculum order;
5. refinamento editorial opcional.

## Manutenção bilíngue

Identidades authored exigem EN e PT-BR.

Quando metadata source-backed muda, os pares devem permanecer equivalentes.

Campos técnicos importantes:

- `sources`;
- `depends_on`;
- `reviewed_revision`.

O prose precisa ser idiomático em cada idioma, não uma tradução abreviada.

O par deve ser tratado como uma unidade técnica.

## CI intermediário

Validator pode falhar em commit temporariamente EN-only.

Workflow concurrency pode cancelar runs anteriores quando chega commit mais novo.

Esses estados não são automaticamente content failures.

O validation target importante é o commit mais novo que contém o pair completo.

Se esse run falhar, aí sim examine o erro real.

## Build-all pipeline

`scripts/build_all.py` executa a cadeia determinística:

- unit tests;
- diagrams;
- figures;
- source inventory;
- coverage;
- curriculum;
- reader navigation;
- stale detection;
- docs validation;
- editorial style;
- source map.

Hosted CI adiciona checks adicionais e publication stages.

Markdown committed ainda não significa published/validated.

## Revision bump correto

Uma source-backed page deve avançar `reviewed_revision` somente após reconciliation.

Sequência:

1. ler metadata;
2. ler source diff;
3. ler current source;
4. decidir se prose muda;
5. verificar tests/specs;
6. atualizar page;
7. atualizar reviewed revision;
8. rodar validation;
9. confirmar final bilingual workflow.

Bump cego destrói stale detection.

## Source hashes e cache

Context pack registra SHA-256 dos sources.

Git também fornece content identity.

Isso permite reutilizar análise de source não alterado.

Um cache futuro pode usar hash como key.

Se content identity não mudou, normalmente não há motivo para repetir análise completa.

## Modelo de custo

Considere:

- (D) = tamanho total da documentação;
- (S) = tamanho total do source;
- (k) = número de sources declarados;
- (d) = tamanho do diff relevante.

Workflow ingênuo tende a ler grande parte de (D + S).

Low-context workflow busca custo proporcional a:

    page + k bounded sources + d + small dependency metadata

À medida que o corpus cresce, a diferença fica maior.

## Evitando context explosion

Causas comuns:

- ler recursivamente todas related pages;
- copiar includes transitivos;
- pedir full large file antes de checar symbols;
- varrer repository inteiro para termos já mapeados;
- regenerar prose não afetado.

O tooling existe justamente para evitar esses padrões.

## Quando busca ampla é apropriada

Metadata explícita não resolve tudo.

Busca mais ampla é justificável quando:

- page depende de code não declarado;
- source move quebrou metadata;
- novo subsystem não possui mapping;
- diff revela hidden cross-subsystem dependency;
- concept precisa de external primary references;
- frontmatter está incompleto.

Ao descobrir dependency durável, adicione-a ao metadata para reduzir custo futuro.

## Failure mode: metadata stale

Uma falha perigosa é dependency metadata incompleta.

Se chapter depende de B mas declara apenas A, mudança em B não entra na queue.

Durante reconciliation substantiva, pergunte:

> Estes ainda são os menores sources completos necessários para os claims desta page?

Metadata faz parte do technical contract.

## Failure mode: source set grande demais

O extremo oposto é declarar muitos files irrelevantes.

Isso marca page stale por qualquer mudança menor e aumenta context pack sem necessidade.

Prefira o menor source set que reconstrói o mecanismo.

Se contracts são independentes, considere pages menores e focadas.

## Generated versus authored ownership

Generated files não devem ser editados como authored source.

Exemplos:

- coverage;
- review queue;
- source atlas;
- source map;
- learning path.

Se generated output estiver errado, corrija:

- metadata;
- manifest/curriculum;
- generator;
- underlying ChrisOS source.

Manual patch será sobrescrito.

## Decision record do agente

Para manutenção não trivial, o agente deve conseguir registrar:

- por que a page foi selecionada;
- qual revision mudou;
- qual source mudou;
- que contract difference foi observada;
- se prose precisou mudar;
- limitations restantes;
- validation executada.

O registro pode ser curto.

Seu objetivo é traceability, não expor raciocínio interno.

## Review queue zero não significa finalidade

Stale queue zerada significa:

> toda source-backed page está reconciliada contra suas dependencies declaradas.

Não significa:

- dependency metadata perfeita;
- todas pages acima do depth floor;
- completude técnica absoluta;
- hardware universalmente validado;
- ausência de melhorias editoriais.

Métricas são independentes.

## Maintenance loop recomendado

Fluxo source-driven:

    atualizar ChrisOS
        |
        v
    rodar build_all
        |
        v
    inspecionar review queue
        |
        v
    escolher stale page
        |
        v
    criar context pack
        |
        v
    reconciliar diff/source
        |
        v
    atualizar par bilíngue
        |
        v
    validar
        |
        v
    repetir até stale=0

Depois, use `next_work.py` para missing/thin work.

## Expansion loop recomendado

Para depth work:

1. execute `next_work.py`;
2. escolha a primeira thin page útil;
3. leia frontmatter/body;
4. reconcilie sources;
5. adicione technical dimensions, não filler;
6. atualize EN/PT-BR;
7. meça com canonical word counter;
8. execute pipeline;
9. continue em curriculum order.

## Invariantes de custo

A arquitetura segue regras práticas:

1. reutilizar análise de source unchanged por content identity;
2. trabalhar por Git diff quando baseline existe;
3. não regenerar authored prose não afetado;
4. gerar indexes e source facts deterministicamente;
5. ler full large files só quando bounded context não basta;
6. manter dependency metadata explícita;
7. validar bilingual pair como unidade;
8. separar structural coverage, text depth e source freshness.

Essas regras permitem o crescimento do site sem tornar cada atualização uma leitura global.

## Nota de revisão

Este capítulo descreve o low-context documentation tooling atual de `chrisos_site` e usa ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56` como baseline do projeto.

Como documenta o sistema de manutenção do repositório de documentação, e não um subsystem de implementation ChrisOS, declara `sources: []`. O tooling correspondente é propriedade do próprio documentation repository e é validado pelo CI dele.
