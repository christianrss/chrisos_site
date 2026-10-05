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
  - documentation-schema
  - source-policy
---

# Manutenção documental de baixo contexto

## Propósito

O corpus foi desenhado para crescer além da quantidade de material que um revisor humano ou um agente de IA deveria carregar em uma tarefa comum.

A estratégia não é comprimir o projeto inteiro em um único resumo. É fazer cada página autoral declarar dependências suficientes para que um contexto estreito e reproduzível possa ser montado automaticamente.

O modelo operacional é:

1. identificar uma página ou uma mudança de source;
2. resolver o conjunto de dependências declarado;
3. inspecionar apenas source e diff afetados;
4. reconciliar a interpretação autoral;
5. executar validação determinística global;
6. publicar somente quando os contratos do corpus continuarem passando.

Isso mantém reasoning local bounded sem perder consistência global.

## Dois repositórios, duas autoridades

O workflow atravessa dois repositories.

O repositório ChrisOS é autoridade para comportamento de implementação, build targets, executable gates e source history.

O repositório de documentação é autoridade para corpus técnico bilíngue, curriculum, specifications, architecture history, interpretação de validação e source atlas gerado.

A CI faz checkout dos dois.

Logo o agente precisa distinguir:

- implementation evidence do ChrisOS;
- comportamento das ferramentas documentais no chrisos_site;
- fatos gerados;
- interpretação autoral.

O field `sources` aponta para paths no checkout do ChrisOS. Páginas de manutenção que descrevem a própria infraestrutura documental podem legitimamente ter `sources: []`.

## Identidade de página

Toda página autoral possui `id` e `lang`.

O par:

    (id, lang)

é a identidade usada pela validação.

Conteúdo bilíngue deve existir com o mesmo `id` em:

- `en`;
- `pt-br`.

O validator rejeita identidade autoral que exista em apenas uma língua.

Isso evita que English evolua e Portuguese desapareça silenciosamente do corpus mantido.

## Frontmatter como grafo de dependências

Frontmatter não é metadata decorativa.

Fields relevantes:

- `id` — identidade conceitual estável;
- `lang` — idioma;
- `type` — classe editorial/depth;
- `reviewed_revision` — revisão ChrisOS reconciliada;
- `sources` — files concretos do ChrisOS que sustentam a página;
- `symbols` — identifiers importantes em sources grandes;
- `depends_on` — prerequisites documentais;
- `related` — relações conceituais não obrigatórias.

Esses fields formam um grafo entre source e interpretação e outro entre páginas.

## Invariantes bilíngues

`validate_docs.py` exige igualdade de alguns metadados entre EN/PT-BR.

Para uma mesma identidade, os dois idiomas precisam concordar em:

- `sources`;
- `depends_on`;
- `reviewed_revision`.

A estrutura linguística pode variar, mas evidence boundary e prerequisite graph precisam ser os mesmos.

Assim uma tradução não descreve outra revisão do projeto sem que isso seja detectado.

## IDs estáveis importam mais que filenames

Uma página pode ser movida ou renomeada preservando o mesmo conceito.

O `id` estável permite ao curriculum e aos links conceituais referirem-se ao conceito em vez do path incidental.

Trocar `id` pode afetar:

- curriculum;
- `depends_on`;
- `related`;
- generated metadata;
- navigation.

Por isso mudança de ID deve ser tratada como schema migration, não cosmetic rename.

## Stale detection

`scripts/stale_docs.py` compara cada página com o HEAD atual do ChrisOS.

Para páginas que possuem `sources` e `reviewed_revision`, o script pergunta ao Git quais declared files mudaram entre:

    reviewed_revision .. HEAD

Somente os paths declarados participam.

Se nenhum mudou, a página não fica stale apenas porque outras partes do source foram alteradas.

Se algum mudou, a página entra na review queue com:

- path da página;
- revisão revisada;
- sources alteradas.

Esse é o mecanismo principal de baixo contexto.

## Revisão inválida

O detector também verifica se `reviewed_revision` resolve para um commit no checkout de source.

Se não resolve, a página entra numa seção separada de invalid revision.

Baseline inválida não pode ser interpretada como "source unchanged".

Sem um ancestor válido, não há prova de que as sources declaradas foram reconciliadas.

## Reconciliação de source

Página stale não deve ser corrigida apenas substituindo o hash.

A tarefa é:

1. ler o diff;
2. determinar se o documented contract mudou;
3. atualizar prose quando necessário;
4. preservar statements históricos quando continuam historicamente verdadeiros;
5. avançar `reviewed_revision` somente após a revisão.

Às vezes o diff muda implementação interna sem alterar o contrato.

Nesse caso a prose pode permanecer e apenas a revisão avança.

Essa decisão exige análise técnica.

## Context packs

`scripts/context_pack.py` cria um working directory bounded para uma página.

O pack contém:

- cópia da página;
- declared source material;
- Git diff desde o baseline;
- metadata;
- source hashes;
- dependency summaries;
- instruções de manutenção.

Esse é o unit normal de contexto para um agente trabalhando em uma página.

## Sources grandes

O context pack não precisa copiar todo source grande.

A implementação atual usa threshold de 24.000 characters.

Acima disso, `symbols` pode direcionar extraction para trechos em torno dos identifiers relevantes.

O extractor mantém regiões bounded em torno de hits e une ranges sobrepostos.

Isso reduz custo sem esconder o fato de que o arquivo foi parcialmente empacotado.

Se o excerpt não resolver a questão, o maintainer pode solicitar pack completo.

Truncation precisa ser explícita, nunca silenciosa.

## Resumo de dependencies

O pack não copia recursivamente todo o documentation graph.

Para `depends_on` e `related`, ele registra summaries no mesmo idioma com:

- id;
- path;
- reviewed revision;
- headings.

Assim uma página não arrasta o transitive closure inteiro do corpus para cada task.

Se uma dependency estiver ausente, o state é registrado explicitamente.

## Diff status

O pack registra se o diff está:

- changed;
- unchanged;
- unavailable por falta de baseline válida;
- not applicable quando não há source dependency.

Unavailable baseline não equivale a unchanged.

Essa distinção evita confiança falsa quando a revisão não existe no checkout.

## Source hashes

Cada source empacotada recebe SHA-256 no metadata.

O hash identifica exatamente os bytes analisados.

Isso ajuda quando o mesmo path muda várias vezes ou quando o review artifact é retido fora do checkout.

Git revision continua sendo a identidade global; hash fornece file-level identity.

## Inventário de source

`scripts/inventory.py` varre textual files do ChrisOS e produz o source atlas.

O scanner ignora directories de trabalho como:

- `.git`;
- `build`;
- `site`;
- virtual environments;
- Python cache.

Para candidates textuais ele registra:

- path;
- line count;
- byte count;
- SHA-256;
- includes detectados;
- C-like function definitions detectadas;
- conteúdo textual completo.

Isso é evidence determinística gerada, não architectural interpretation.

## Papel do source atlas

O atlas garante rastreabilidade para o conteúdo exato dos files.

Ele deve responder:

> O que exatamente existia neste arquivo nessa revisão?

Não deve tentar responder sozinho:

> Qual papel arquitetural esse arquivo possui?

Ownership, invariants, concurrency, failure behavior e rationale ficam em authored chapters.

## Fatos gerados versus interpretação autoral

A separação é central.

Automation é apropriada para:

- inventories;
- hashes;
- counts;
- dependency tables;
- symbol lists;
- navigation;
- stale queues;
- coverage statistics.

Authored pages continuam responsáveis por:

- architectural boundaries;
- ownership;
- lifetime;
- concurrency;
- algorithms;
- complexity;
- security;
- failure/recovery;
- validation meaning;
- limitations;
- roadmap separation.

Gerar fatos economiza tokens e evita repetição.

Interpretação autoral impede o site de virar apenas source dump.

## Structural coverage

`scripts/coverage.py` compara o corpus autoral com o chapter manifest.

Structural coverage pergunta se cada planned chapter existe.

Não prova technical completeness.

Uma página curta pode satisfazer presença estrutural e ainda falhar no depth target.

Por isso structural coverage e text-floor coverage são métricas distintas.

## Pisos textuais

O coverage script define thresholds por page type.

Exemplos atuais:

- concept: 1.800 palavras;
- technical chapter: 1.800;
- subsystem: 2.200;
- specification: 1.600;
- source commentary: 1.200;
- outras authored technical pages: 900.

O contador remove fenced code e HTML markup.

Esses valores são editorial signals.

Atingir o piso não comprova correção nem completude técnica.

## Código não conta como profundidade

Página não deve alcançar o target colando source ou command transcript.

O contador remove fenced code antes da contagem.

Isso cria a separação correta:

- source integral pertence ao atlas;
- excerpts ajudam a explicar;
- prose depth precisa vir de technical reasoning.

É possível ter muito código e ainda ficar abaixo do piso quando o modelo explicativo é raso.

## Curriculum graph

`scripts/curriculum.py` valida o learning path planejado.

O curriculum precisa particionar o manifest exatamente:

- todo planned chapter aparece;
- nenhum chapter desconhecido aparece;
- nenhum ID fica duplicado.

O script também valida prerequisites e detecta cycles.

Assim `depends_on` participa de um learning DAG executável, não apenas de hyperlinks.

## Estado de leitura

O learning path gerado distingue:

- chapter ausente;
- presente mas requer expansão;
- piso textual atingido, revisão técnica ainda necessária.

A redação é intencional.

Cruzar o word floor nunca muda automaticamente o estado para "complete".

Editorial length e technical review continuam separados.

## Validação documental

`scripts/validate_docs.py` aplica os contratos estruturais.

Ele verifica:

- required frontmatter;
- duplicate `id/lang`;
- declared source paths;
- placeholder tokens;
- presença bilíngue;
- metadata alignment entre idiomas.

Também emite warning para technical body muito curto.

Isso bloqueia várias formas de corruption antes do MkDocs.

## Reverse source map

`scripts/source_map.py` gera índice reverso de source paths para docs.

Em vez de perguntar:

> quais sources sustentam esta página?

o map também permite responder:

> quais páginas declararam dependência deste source file?

Esse reverse index é base útil para impact analysis e future automation disparada por code changes.

## Build orchestration

`scripts/build_all.py` é o entry point principal da geração documental.

A sequência atual inclui:

- unit tests da documentação;
- diagrams;
- figures;
- source inventory;
- coverage;
- curriculum;
- reader navigation;
- stale detection;
- documentation validation;
- editorial-style checks;
- source map.

Executar tudo sobre um único checkout torna o resultado coerente.

## CI como consistência global

O GitHub Pages workflow roda em:

- pushes para `main`;
- pull requests contra `main`;
- manual dispatch;
- schedule semanal.

Ele faz checkout da documentação e do ChrisOS, instala dependencies, executa o pipeline e depois vários verification scripts especializados.

No final executa:

- JavaScript syntax checks;
- strict MkDocs build;
- SEO/discovery checks;
- generated-reader smoke;
- Pages artifact upload;
- deploy para runs que não são pull request.

Essa é a rede global de segurança depois da edição local.

## Concurrency do workflow

Pages usa shared concurrency group com cancel-in-progress.

Quando vários commits chegam rapidamente, um run antigo pode ser cancelled pelo run mais novo.

Cancellation intermediária não significa necessariamente content failure.

O resultado autoritativo é o workflow mais novo que corresponde ao repository state final.

Relatórios de manutenção devem registrar final commit SHA e final workflow conclusion.

## Reasoning local, validation global

Low-context maintenance só é seguro porque a edição local é seguida por global deterministic checks.

O modelo combina:

    contexto estreito para reasoning
    +
    contracts automáticos no corpus inteiro

Contexto estreito sem validação global pode esconder regressões cross-page.

Contexto global em toda tarefa desperdiça recursos e reduz precisão.

A combinação fornece escala e integridade.

## Algoritmo de atualização

Um ciclo prático:

1. identificar source revision;
2. gerar stale queue;
3. escolher stale/thin page prioritária;
4. montar ou emular context pack;
5. ler diff e dependencies;
6. atualizar EN/PT-BR;
7. validar metadata e sources;
8. executar pipeline;
9. verificar final workflow;
10. publicar somente com final state verde.

Sem stale pages, o foco passa para missing chapters ou below-floor chapters.

Com structural coverage completa, manutenção vira reconciliação e aprofundamento.

## Workflow para página thin

Página below-floor não deve receber filler.

Expansões úteis acrescentam:

- prerequisites;
- formal model;
- source-backed implementation;
- data structures;
- algorithms;
- complexity;
- ownership/lifetime;
- concurrency;
- failure behavior;
- security;
- performance;
- validation;
- limitations;
- history;
- roadmap.

A boa expansão reduz ambiguidade para quem precisa implementar, depurar ou revisar.

## Workflow para página stale

Página stale exige source reconciliation, não rewrite automático.

Classifique o diff.

### Sem contract change

Implementation mudou internamente e a prose continua correta. Avance a revisão após conferir os dois idiomas.

### Contract extension

Comportamento existente permanece, mas nova capability surgiu. Documente contrato e evidence novos.

### Contract change

Regra existente mudou. Atualize current/normative prose e pages dependentes.

### Efeito apenas histórico

Source atual mudou, mas o chapter é histórico. Preserve o historical statement e ajuste apenas o framing necessário para não parecer current behavior.

Essa classificação evita apagar história ao atualizar hashes.

## Workflow bilíngue

EN/PT-BR devem ser tratados como uma transação conceitual.

Sequência segura:

1. reconciliar evidence uma vez;
2. atualizar English;
3. atualizar Portuguese com claims equivalentes;
4. comparar frontmatter;
5. rodar bilingual validation;
6. tratar o commit do segundo idioma como estado final que precisa passar na CI.

Commits intermediários de apenas um idioma podem falhar ou ser cancelled, porque o repository rejeita bilingual pairs incompletos.

O final state precisa sempre restaurar equivalência.

## Evitando pesquisa duplicada

Se uma página possui reviewed revision válida e nenhuma source declarada mudou, não há motivo para repetir toda a investigação em uma atualização unrelated.

Reuse o dependency graph.

Reabra research quando:

- source declarada muda;
- dependency muda a interpretação;
- validation failure contradiz a página;
- a página está sendo aprofundada;
- claim sobre standard externo precisa de refresh.

Fora desses casos, o último estado reconciliado continua válido.

## Controle de escopo

Agent não deve corrigir tudo que perceber no caminho.

Registre o problema e mantenha o patch ligado a um claim reviewable, salvo quando o defeito bloqueia validation.

Scope control torna failures atribuíveis e evita que uma documentação simples vire refactor amplo.

Em campaigns maiores, agrupe pages por uma mesma área de source ou objetivo editorial e valide cada lote coerente.

## Tratamento de failures

Quando CI falha, classifique antes de editar.

Classes comuns:

- malformed frontmatter;
- bilingual metadata mismatch;
- missing source;
- curriculum/DAG error;
- navigation generation;
- contract verifier;
- JavaScript syntax;
- MkDocs strict-build;
- discovery/reader smoke;
- deployment/infrastructure.

Não altere prose para "corrigir" outage de infraestrutura.

Não ignore source-contract verifier como irrelevante se o chapter fez o claim verificado.

## Generated files

Generated outputs devem ser regenerados, não curados manualmente.

Exemplos:

- source inventory;
- source atlas;
- coverage status;
- learning path;
- review queue;
- source map;
- diagrams/figures produzidos por scripts.

Editar output gerado cria drift porque o próximo build sobrescreve.

A correção pertence ao source data, generation script ou authored page, conforme a causa.

## Retenção de evidência

Para batches importantes, retenha pelo menos:

- final documentation commit;
- ChrisOS source revision;
- final workflow run ID;
- build/deploy conclusion;
- structural coverage;
- stale count;
- remaining thin-page count.

Esse registro compacto permite continuar outra sessão sem replay do campaign inteiro.

Também reduz dependência de conversational memory quando o repository possui fatos autoritativos.

## Critérios de checkpoint

Uma campaign não termina apenas porque files foram editados.

Um checkpoint forte exige:

- planned structural coverage satisfeita;
- nenhuma stale page inesperada;
- nenhuma invalid reviewed revision;
- thin pages alvo acima do piso;
- bilingual contracts passando;
- curriculum/navigation gerados com sucesso;
- strict site build verde;
- discovery e reader smoke verdes;
- final Pages deploy verde.

O corpus ainda pode continuar evoluindo.

Esses critérios definem um state estável de manutenção, não o fim da documentação técnica.

## Nota de revisão

Este workflow descreve a arquitetura atual de manutenção do site enquanto usa ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56` como shared source baseline para authored technical pages.

O princípio central é: **ler pouco e com precisão, declarar dependências, gerar fatos mecânicos deterministicamente, preservar boundaries bilíngues e validar o corpus inteiro antes de publicar.**
