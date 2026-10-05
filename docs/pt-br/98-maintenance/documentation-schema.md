---
id: documentation-schema
lang: pt-br
type: technical-chapter
volume: 98-maintenance
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources: []
symbols: []
depends_on:
  - agent-workflow
related:
  - source-policy
  - contribution-workflow
---

# Schema da documentação e templates

## Propósito

Este capítulo define o contrato estrutural da documentação autoral do ChrisOS.

O schema não é apenas convenção de formatação. Ele controla:

- identidade bilíngue;
- posição no curriculum;
- validação de dependencies;
- source-impact analysis;
- stale detection;
- coverage;
- generated navigation;
- context packs;
- static-site routes;
- review queues.

Uma página pode parecer correta em Markdown e ainda assim quebrar o sistema documental se a metadata estiver errada.

## A identidade canônica é o id do frontmatter

A regra mais importante é:

> A identidade canônica de um capítulo é o `id` do frontmatter, não o nome do arquivo.

Exemplo:

    docs/pt-br/17-developer-guide/linux-development-environment.md

pode possuir:

    id: development-environment-linux

Coverage, curriculum e bilingual pairing operam sobre o ID.

O filename define route e localização física; não define identidade semântica.

## Por que contagem por filename está errada

Um inventário baseado em filenames pode marcar capítulos falsamente como missing quando route name e manifest ID são diferentes.

O structural check correto é:

    manifest chapter id
          |
          v
    frontmatter id em EN
          +
    frontmatter id em PT-BR

Se os dois authored pages possuem o mesmo planned ID, o capítulo está estruturalmente presente mesmo que nenhum filename seja igual ao ID.

Essa regra impede criação de duplicates apenas para satisfazer audit baseado em path.

## Boundary de frontmatter

Páginas Markdown autorais começam com YAML frontmatter:

    ---
    id: example-chapter
    lang: pt-br
    type: technical-chapter
    volume: 04-kernel
    status: maintained
    reviewed_revision: <git-sha>
    sources:
      - kernel/example.c
    symbols:
      - example_init
    depends_on:
      - prerequisite-id
    related:
      - adjacent-topic
    ---

O body começa depois do delimiter final.

Tooling lê metadata de forma determinística; ela não é inferida de headings.

## Campos obrigatórios

`validate_docs.py` exige:

- `id`;
- `lang`;
- `type`.

A ausência de qualquer um causa validation failure.

Outros campos são exigidos por policy em implementation pages mesmo quando o parser genérico não os exige sintaticamente.

## id

`id` é a identidade semântica estável.

Regras:

- use lowercase kebab-case;
- mantenha estável através de file moves;
- use o mesmo ID em EN/PT-BR;
- não reutilize ID para outro conceito;
- não codifique idioma no ID;
- não altere ID apenas para melhorar URL.

Trocar ID é schema/curriculum migration, não cosmetic edit.

## lang

As árvores autorais usam:

    en
    pt-br

Directory também carrega language identity.

`frontmatter.py` consegue normalizar `lang` ausente a partir do path por compatibilidade, mas authored pages devem declarar explicitamente.

Metadata explícita facilita review e processing isolado.

## type

`type` classifica a página para coverage e generation behavior.

Types autorais comuns:

- `concept`;
- `technical-chapter`;
- `subsystem`;
- `specification`;
- `source-commentary`;
- `guide`;
- `volume-index`;
- `landing`.

Generated pages usam types iniciados com `generated`.

Type também influencia depth accounting.

Não escolha type apenas para obter word floor menor.

## volume

`volume` registra o volume físico/semântico.

Exemplo:

    volume: 08-graphics

Para pages planejadas, deve corresponder à organização do manifest.

Volume indexes possuem identidade própria e ficam fora da normal chapter coverage.

## status

O corpus usa principalmente:

    status: maintained

Generated pages normalmente:

    status: generated

Status descreve lifecycle, não correctness.

Uma page maintained pode ainda exigir review após source change.

## reviewed_revision

`reviewed_revision` registra o commit ChrisOS contra o qual a página foi reconciliada.

Deve ser igual em EN/PT-BR para o mesmo ID.

Não deve ser atualizado apenas para silenciar stale detection.

Páginas sem source dependency podem registrar o baseline de projeto usado na autoria e usar `sources: []`.

## sources

`sources` é lista YAML de paths relativos ao source repository do ChrisOS.

Exemplo:

    sources:
      - kernel/mm/pmm.c
      - kernel/mm/vmm.c

`validate_docs.py` verifica esses paths no checkout fornecido ao build.

Use lista vazia quando o assunto não documenta implementation source do ChrisOS.

Não coloque scripts do documentation repository nesse campo, porque a validação ocorre contra o source tree do ChrisOS.

## symbols

`symbols` lista identifiers importantes para context tooling.

Exemplo:

    symbols:
      - pmm_alloc
      - vmm_map_page

Symbols são hints, não dependencies independentes.

Symbol sem source path não cria source dependency.

## depends_on

`depends_on` define prerequisite edges no learning DAG.

Exemplo:

    depends_on:
      - paging
      - physical-memory-manager

Significa que o target assume conceitos/contratos definidos nos prerequisites.

Regras:

- todo prerequisite ID precisa estar planejado no manifest;
- dependencies não podem formar cycles;
- metadata EN/PT-BR precisa ser equivalente;
- não use reciprocal dependency apenas porque subsystems interagem.

Prerequisite é directional.

## related

`related` registra relação útil que não é prerequisite.

Exemplos:

- implementation/specification pair;
- adjacent subsystem;
- validation chapter;
- history chapter;
- alternative backend.

`related` pode apontar para conteúdo posterior porque não participa do prerequisite DAG.

Não deve esconder prerequisite real.

## Bilingual identity invariant

Para authored pages não geradas, `validate_docs.py` exige os dois idiomas:

    en
    pt-br

Página unilateral falha no pipeline.

Por isso commit intermediário apenas com EN pode falhar até o PT-BR ser adicionado.

O commit final bilíngue é o validation target real.

## Duplicate identity é proibida

Dentro de um idioma, duas pages não podem compartilhar o mesmo `id`.

O validator reporta:

    duplicate id/lang

Portanto criar:

    docs/en/17-developer-guide/index.md
    docs/en/17-developer-guide/developer-guide.md

com `id: developer-guide` em ambos seria inválido.

Relatório missing por filename nunca deve ser "corrigido" criando canonical duplicate.

## Bilingual metadata equality

Para um par de ID, validator exige igualdade exata de:

- `sources`;
- `depends_on`;
- `reviewed_revision`.

Isso mantém as duas language trees tecnicamente equivalentes.

O prose pode ser idiomático; source scope e prerequisite graph não podem divergir.

## Manifest contract

`data/documentation-manifest.yml` define o corpus planejado.

Cada chapter possui:

- ID;
- title;
- volume;
- priority.

O manifest responde:

> Quais capítulos deveriam existir?

Não determina file path.

Coverage junta manifest e authored pages pelo frontmatter ID.

## Curriculum contract

`data/curriculum.yml` atribui todo planned ID exatamente uma vez ao learning path.

`curriculum.py` exige partition exata:

- nenhum planned ID omitido;
- nenhum unknown ID;
- nenhuma duplicate assignment.

Assim navigation e prerequisites usam as mesmas semantic identities da coverage.

## Physical path versus semantic identity

O sistema separa:

    physical path
    semantic ID
    curriculum position

Essas dimensões podem mudar independentemente, dentro das constraints.

Page pode mudar de directory sem trocar ID.

Chapter pode mudar de curriculum module sem mover arquivo.

Isso reduz churn desnecessário.

## Route stability

Embora ID seja canônico no data model, path ainda define URL.

Mover file muda static-site route salvo existência de redirect.

Portanto:

- não renomeie files casualmente;
- prefira stable routes;
- mude ID apenas por razão semântica;
- trate path move e ID migration como operações diferentes.

## Coverage model

`coverage.py` carrega authored pages e constrói mapa por:

    (id, lang)

Exclui:

- generated types;
- `volume-index`;
- `landing`.

Depois faz join com o manifest.

Structural presence é baseada em canonical ID, não filename.

## Structural coverage

Para cada idioma:

[
C_s = rac{N_{present}}{N_{planned}}
]

onde:

- (N_{present}) é número de manifest IDs com authored page;
- (N_{planned}) é número de capítulos planejados.

Structural coverage responde somente:

> Existe authored page com este ID?

Não prova technical completeness.

## Editorial depth floors

`coverage.py` calcula também word-floor signal.

Targets atuais:

| Type | Minimum words |
|---|---:|
| `concept` | 1800 |
| `technical-chapter` | 1800 |
| `subsystem` | 2200 |
| `specification` | 1600 |
| `source-commentary` | 1200 |
| other authored technical page | 900 |

São guardrails, não proof de correctness/completeness.

## Por que word count não é completion

Capítulo de 3.000 palavras pode continuar incompleto se omite:

- ownership;
- concurrency;
- error paths;
- source evidence;
- validation;
- limitations.

Uma specification de 1.500 palavras pode ser suficiente para contract realmente pequeno.

O floor encontra páginas suspeitamente curtas; não substitui technical review.

## Generated pages

Generated pages são build outputs, não authored truth.

Exemplos:

- coverage;
- learning path;
- review queue;
- source atlas;
- generated metadata indexes.

Não edite generated files manualmente quando script/data é owner.

Corrija generator/input.

## Exceção do source atlas

O generated source atlas é mirror/index determinístico.

Pode reproduzir source text completo.

Não possui o mesmo papel de authored technical prose.

Não deve ser resumido manualmente apenas para reduzir tamanho, porque exact reproduction faz parte da finalidade.

## Frontmatter parser behavior

`frontmatter.py`:

1. verifica YAML delimiter inicial;
2. encontra closing delimiter;
3. parseia YAML;
4. normaliza language pelo path se ausente;
5. devolve metadata e body.

Frontmatter malformed/ausente falha em validators superiores devido required fields.

## Page discovery

`iter_pages()` descobre Markdown recursivamente em `docs/`.

Ignora arquivos gerados abaixo de:

    /99-source-atlas/generated/

porque eles são gerenciados separadamente e podem ser numerosos.

Outras generated pages participam conforme seu type.

## Validation contract

`validate_docs.py` verifica:

- required metadata;
- duplicate `id/lang`;
- declared ChrisOS source paths;
- placeholder tokens;
- bilingual authored identities;
- paired metadata equivalence.

Errors bloqueiam publication.

## Placeholder protection

Authored pages não podem conter scaffold ou replacement markers não resolvidos reconhecidos pelo validator.

Isso impede que resíduos de template sejam publicados como prose final.

Se future work precisa ser descrito, use roadmap ou limitation prose explícito em vez de deixar placeholder marker.

## Short-body warning

Validator avisa quando authored non-index body é pequeno.

Coverage faz word-floor classification mais precisa.

Warning nem sempre falha CI, mas sinaliza possível shallow page.

## Curriculum DAG

Prerequisites formam directed acyclic graph.

Exemplo:

    depends_on:
      - prerequisite-a
      - prerequisite-b

significa que ambos devem conceitualmente preceder target.

`curriculum.py` rejeita cycles.

Cycle indica que o corpus não definiu ordem de aprendizado utilizável.

## Dependency semantics

Use `depends_on` quando leitor realmente precisa conhecer o conteúdo antes.

Use `related` quando a relação é útil, mas não prerequisite.

Bad pattern:

    A depends_on B
    B depends_on A

apenas porque interagem.

Melhor:

    A depends_on foundational-C
    B depends_on foundational-C
    A related B
    B related A

quando nenhum precede o outro.

## Source-impact graph

`source_map.py` constrói reverse graph determinístico a partir de `sources`.

Para cada page registra:

- ID;
- language;
- path;
- type;
- reviewed revision;
- sources;
- symbols;
- dependencies;
- related.

Depois produz:

    source path -> documentation paths

Esse mapping habilita low-context maintenance.

## Stale detection schema

Uma page entra em source-diff stale detection quando possui:

- `sources` não vazio;
- `reviewed_revision`.

`stale_docs.py` calcula paths alterados entre revision e source HEAD.

A generated review queue lista somente pages cujas dependencies declaradas mudaram.

## Context-pack schema

`context_pack.py` usa frontmatter para gerar bounded package com:

- target page;
- full/symbol-centered source;
- Git diff;
- source hashes;
- dependency headings;
- metadata;
- instructions.

Metadata correta reduz manutenção.

Metadata ruim produz contexto ruim.

## Template de implementation chapter

Novo substantive implementation chapter normalmente começa com:

    ---
    id: stable-id
    lang: en
    type: technical-chapter
    volume: NN-volume
    status: maintained
    reviewed_revision: <source-commit>
    sources:
      - real/source/path.c
    symbols:
      - important_symbol
    depends_on:
      - prerequisite-id
    related:
      - adjacent-id
    ---

PT-BR usa metadata técnica idêntica, alterando:

    lang: pt-br

O body deve ser bem escrito em português, não tradução abreviada.

## Concept template

Theory-first page pode usar:

    type: concept
    sources: []

quando não faz implementation claims.

Ao cruzar para implementation, deve declarar paths relevantes.

Concept page ainda requer evidence/bibliography para claims externos.

## Specification template

Contract próprio pode usar:

    type: specification

e deve definir explicitamente:

- scope/version;
- layout;
- invariants;
- state transitions;
- validity constraints;
- errors;
- compatibility;
- implementation binding;
- tests.

Normative contract e implementation notes devem permanecer separados.

## Guide template

Operational developer documentation pode usar:

    type: guide

Guide prioriza commands reproduzíveis, environment assumptions, failure classification e workflow.

Procedural instructions não devem fingir ser architecture specification.

## Volume-index template

Volume index usa:

    type: volume-index

Seu papel é navigation/scope.

É excluído de normal planned chapter coverage e pode ser conciso.

Volume index não deve usar planned chapter ID salvo quando isso é intencional e o comportamento do tooling foi verificado.

No developer guide existente, o index é o próprio planned `developer-guide` porque seu type é `guide`, não `volume-index`.

## Landing template

Landing page usa:

    type: landing

Fica fora de ordinary planned depth/coverage.

Landing organiza entry points; não substitui technical chapter.

## Procedimento de ID migration

Trocar ID exige mudanças coordenadas.

No mínimo:

1. atualizar manifest;
2. atualizar curriculum;
3. atualizar frontmatter EN/PT-BR;
4. atualizar `depends_on`;
5. atualizar `related` relevante;
6. atualizar data inputs;
7. validar curriculum;
8. executar full documentation build;
9. tratar route compatibility separadamente.

Não faça partial migration.

## Procedimento de file move

Mover file mantendo ID é mais simples, mas ainda pode alterar links/routes.

Passos:

1. mover os dois idiomas coerentemente;
2. preservar IDs;
3. atualizar relative links;
4. verificar navigation;
5. executar reader-navigation tests;
6. executar `mkdocs build --strict`;
7. considerar redirects se public URLs mudaram.

## Adicionando planned chapter

Para novo planned chapter real:

1. adicionar ID estável ao manifest;
2. atribuir exatamente uma vez no curriculum;
3. definir prerequisites;
4. criar EN/PT-BR;
5. manter metadata técnica equivalente;
6. adicionar real source dependencies quando implementation-facing;
7. executar pipeline completo.

Commit intermediário unilateral pode falhar por design.

## Removendo planned chapter

Removal é schema change.

Antes:

- confirme que está realmente obsoleto;
- atualize manifest/curriculum;
- remova/redirecione dependencies;
- preserve historical material quando apropriado;
- trate URL compatibility;
- remova os dois idiomas.

Coverage nunca deve melhorar apagando planned work apenas porque está incompleto.

## Generated versus authored ownership

Cada file deve possuir owner claro.

| File class | Owner |
|---|---|
| technical prose | human/agent authored |
| manifest/curriculum | curated data |
| coverage/review queue | generator |
| source atlas | generator |
| static site output | build |
| source code | ChrisOS repository |

Editar layer errada cria drift.

## Publication pipeline

Sequência determinística principal:

    python -m unittest discover -s tests
    python scripts/build_all.py --source .source --docs docs
    mkdocs build --strict

Hosted workflow adiciona validators, SEO, reader smoke e Pages artifact.

Final content commit só deve ser considerado validado depois do pipeline completo.

## Concorrência e commits intermediários

CI pode falhar/cancelar commits intermediários durante publicação bilíngue.

Sequência comum:

    EN commit
      -> validator encontra PT-BR ausente
      -> failure

    PT-BR commit
      -> pair completo
      -> final workflow success

O final paired commit é o estado publicável.

Failure intermediário causado apenas por pair incompleto não é content regression.

## Schema anti-patterns

Evite:

- contar filenames em vez de IDs;
- criar duplicate IDs para satisfazer path-based report;
- trocar IDs por URLs mais bonitas;
- colocar documentation scripts em ChrisOS `sources`;
- bump de reviewed revision sem reconciliation;
- usar `related` para esconder prerequisite;
- editar generated files manualmente;
- reduzir escopo técnico do PT-BR;
- apresentar roadmap como implemented;
- usar word count como proof de completeness.

## Algoritmo canônico de chapter presence

Structural inventory correto equivale a:

    planned = IDs de documentation-manifest.yml

    authored[(id, lang)] =
        cada page não gerada,
        não volume-index,
        não landing
        indexada pelo frontmatter id

    present(id) =
        authored[(id, en)] existe
        and
        authored[(id, pt-br)] existe

Filename matching não participa desse algoritmo.

Essa é a regra que audits, dashboards e completion reports devem usar.

## Invariante do schema

O invariante central é:

> Semantic identity, language pairing, curriculum placement, source dependencies e revision metadata são dados explícitos; nenhum deles deve ser inferido por similaridade de filename ou prose.

Isso permite que centenas de chapters permaneçam machine-verifiable.

## Nota de revisão

Este capítulo reflete o tooling documental e o baseline ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

Como documenta comportamento do documentation repository e não implementation internals do ChrisOS, declara deliberadamente `sources: []`.
