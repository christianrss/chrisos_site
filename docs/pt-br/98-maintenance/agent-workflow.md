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

A documentação do ChrisOS foi desenhada para crescer sem exigir que toda tarefa de manutenção releia o corpus completo ou o source repository inteiro.

O modelo separa três tipos de informação:

1. fatos determinísticos gerados por scripts;
2. contexto de source estreito selecionado por metadata explícita;
3. interpretação técnica autoral que exige julgamento de engenharia.

O objetivo não é apenas reduzir tokens. É tornar manutenção **bounded, reproduzível e revisável**.

Uma página normalmente deve poder ser mantida a partir dela mesma, das source dependencies declaradas, do Git diff relevante e de um pequeno conjunto de prerequisites.

## Por que low-context importa

Em corpus grande, reler tudo a cada mudança cria dois problemas.

Primeiro, o custo cresce com o tamanho total mesmo quando uma mudança de uma linha afeta apenas um chapter.

Segundo, contexto amplo facilita misturar assumptions não relacionadas e dificulta provar por que uma página foi alterada.

ChrisOS evita isso armazenando dependency metadata em frontmatter e gerando impact maps determinísticos.

A unidade normal de manutenção é:

    uma target page
      + source paths declarados
      + diff das sources alteradas
      + dependency context selecionado
      + validation evidence

e não:

    source tree inteiro
      + documentation tree inteira
      + semantic guessing

## Identidade canônica

Maintenance opera pelo `id` do frontmatter, não por filename similarity.

Uma página pode mudar de route preservando identidade semântica.

O par bilíngue é:

    (id, en)
    (id, pt-br)

Isso impede criar duplicate pages apenas porque filename não coincide com manifest ID.

O schema documental define todas as regras de identidade.

## Grafo de dependencies

Os principais campos de manutenção são:

- `sources`;
- `symbols`;
- `depends_on`;
- `related`;
- `reviewed_revision`.

Juntos criam um grafo da implementação para a explicação autoral.

Conceitualmente:

    ChrisOS source file
          |
          v
       sources
          |
          v
    documentation page
       /          \
      v            v
 depends_on      related

Mudança em um source path pode ser mapeada deterministicamente para as pages que o declararam.

Não é necessário semantic search no primeiro impact pass.

## sources

`sources` é a lista autoritativa de dependencies de implementação para source-diff maintenance.

Cada entry é path relativo ao source repository.

A página deve declarar o menor conjunto útil necessário para reconstruir seus implementation claims.

Poucas sources podem esconder uma mudança importante da stale detection.

Sources demais criam review queue ruidosa e reconciliações desnecessárias.

O objetivo é dependency capture documental precisa, não transitive dependency capture exaustiva.

## symbols

`symbols` estreita files grandes para identifiers úteis à revisão.

Context pack pode usar esses nomes para extrair janelas focadas em vez de enviar todo o file.

Symbols são hints.

Não substituem `sources` e não se tornam ABI estável por estarem no frontmatter.

## depends_on

`depends_on` registra prerequisite knowledge.

Suporta:

- curriculum ordering;
- DAG validation;
- bounded prerequisite context;
- orientação do reviewer.

Maintenance agent não deve reescrever automaticamente prerequisite pages porque um dependent mudou.

Dependency é conceitual, não reverse ownership.

## related

`related` registra topics adjacentes que não são prerequisites estritos.

Exemplos:

- implementation/specification;
- subsystem/validation;
- current architecture/history;
- alternate backend.

Related pages ajudam no scope, mas não precisam entrar em todo context pack.

## reviewed_revision

`reviewed_revision` registra a source revision do ChrisOS contra a qual a página foi reconciliada.

É o baseline da stale detection.

Não deve avançar apenas porque a página foi aberta ou porque um workflow precisa ficar verde.

O campo significa:

> esta página foi deliberadamente verificada contra esta revisão de source.

Atualizar sem review destrói o modelo de dependency tracking.

## Reverse source map

`source_map.py` constrói mapping reverso de source path para documentation pages.

Ele responde:

> Quais authored pages declaram este file alterado?

Isso é mais barato e confiável que procurar words parecidas com filename/subsystem em todo o corpus.

O source map é determinístico porque vem do frontmatter.

Se estiver errado, corrija metadata em vez de adicionar heurística de modelo.

## Stale detection

`stale_docs.py` compara cada implementation-facing page do seu `reviewed_revision` até o ChrisOS HEAD atual, mas somente nas `sources` declaradas.

Conceitualmente:

    git diff reviewed_revision..HEAD -- declared/source/path ...

Se nenhuma source declarada mudou, activity não relacionada não torna a página stale.

Se alguma mudou, ela entra na generated review queue.

Maintenance passa a escalar com **documentation afetada**, não com repository total.

## O que stale significa

Página stale significa:

> ao menos uma source dependency declarada mudou após o baseline revisado.

Não significa:

> a prose está definitivamente errada.

Mudanças podem ser implementation-only ou editoriais.

Reviewer precisa inspecionar diff e decidir se contract, examples, limitations, ownership ou validation claims mudaram.

Se o texto continua correto, avançar `reviewed_revision` após inspeção é reconciliação legítima.

## Baseline indisponível

Às vezes reviewed revision histórico não está disponível em shallow checkout ou ambiente podado.

Tooling deve classificar isso como baseline indisponível, não como empty diff.

Ausência de diff não prova ausência de mudança quando o baseline não pode ser resolvido.

A resposta correta é obter Git history suficiente ou executar full reconciliation contra current source.

## Review queue gerada

A review queue é attention list derivada da stale detection.

Entry útil identifica:

- page;
- language;
- reviewed revision;
- declared sources alteradas.

É generated state.

Não deve ser editada manualmente para esconder trabalho.

Para remover entry, reconcilie a página e atualize revision ou corrija source metadata incorreta.

## Context packs

`context_pack.py` cria material bounded para uma target page.

Pode conter:

- target page;
- metadata;
- declared source content;
- symbol-centered excerpts;
- Git diff desde reviewed revision;
- source hashes;
- prerequisite headings;
- instruções curtas.

O pack deve permitir responder:

1. o que a página afirmava?
2. qual source mudou?
3. qual é a implementation atual?
4. quais claims precisam mudar?
5. quais continuam válidos?

## Disciplina de tamanho de contexto

Mais contexto não é automaticamente melhor.

Expanda apenas quando o pacote atual não resolve uma questão material.

Ordem útil:

1. target page;
2. declared symbol window;
3. full declared file;
4. direct caller/callee;
5. relevant test;
6. historical commit;
7. broader subsystem search.

Isso evita repository-wide exploration em toda manutenção.

## Fatos gerados

Scripts calculam fatos que não precisam de model interpretation.

Exemplos:

- path;
- hash;
- line count;
- includes;
- symbol names;
- manifest membership;
- bilingual presence;
- word counts;
- source-to-page mapping.

Esses fatos devem ser gerados deterministicamente.

Agent não deve gastar reasoning reconstruindo o que o repository consegue calcular exatamente.

## Source atlas

O generated source atlas espelha/indexa source para navigation e retrieval.

Seu papel é acesso exato ao source, não authored interpretation.

Não deve ser resumido manualmente.

Quando source muda, regenere atlas a partir do checkout.

Assim generated facts permanecem mecanicamente sincronizados.

## Interpretação autoral

Há propriedades que syntax sozinha não infere com segurança.

Authored pages continuam responsáveis por:

- architecture;
- invariants;
- ownership;
- lifetime;
- concurrency;
- ABI meaning;
- error propagation;
- recovery;
- rationale;
- performance implications;
- security boundaries;
- validation interpretation;
- limitations.

Esses pontos exigem engineering reasoning.

Uma symbol list pode provar que um lock existe.

Não prova por si só qual invariant o lock protege.

## Ownership de artifacts

Cada artifact deve ter owner claro.

| Artifact | Owner |
|---|---|
| implementation code | ChrisOS source repository |
| frontmatter metadata | authored documentation |
| technical prose | authored documentation |
| manifest/curriculum | curated data |
| source map | generator |
| source atlas | generator |
| review queue | generator |
| coverage report | generator |
| static site output | build pipeline |

Editar generated file à mão normalmente é agir na layer errada.

Corrija input ou generator.

## Selecionando próximo trabalho

Depois de structural coverage completa, o trabalho deve vir de maintenance signals gerados, não de capítulos inventados.

Prioridade útil:

1. invalid source/revision metadata;
2. stale pages ligadas a current capability claims;
3. pages abaixo do editorial depth floor;
4. curriculum/navigation quebrados;
5. specification/implementation mismatch;
6. quality improvements mais amplos.

Isso mantém manutenção ligada ao estado mensurável do corpus.

## Structural coverage versus depth

Structural coverage pergunta:

> o planned bilingual chapter existe?

Depth pergunta:

> o authored chapter é substancial para sua função?

São sinais diferentes.

Corpus pode estar 100% estruturalmente completo e ainda possuir pages rasas.

Por isso completion campaign continua depois do último manifest ID usando depth backlog gerado.

## Word floors

Word floors são guardrails, não prova de qualidade.

Página abaixo do target sinaliza que faltam dimensões possivelmente importantes.

Boas dimensões de expansão:

- initialization;
- ownership;
- memory;
- algorithms;
- concurrency;
- error paths;
- validation;
- limitations;
- security;
- performance;
- compatibility.

Não adicione filler apenas para cruzar número.

Cada expansão deve fechar technical gap.

## Manutenção bilíngue

EN e PT-BR com o mesmo ID devem permanecer tecnicamente equivalentes.

Workflow precisa preservar igualdade de:

- source dependencies;
- prerequisite graph;
- reviewed revision.

Prose não precisa ser tradução linha por linha.

Cada idioma deve comunicar independentemente o mesmo contract e as mesmas limitations.

Substantive change em um idioma normalmente exige atualização do par no mesmo batch.

## Failures intermediários de CI

Bilingual validation pode fazer commit EN-only falhar porque PT-BR está temporariamente inconsistente.

O validation target real é o final commit contendo os dois lados.

Pair-incomplete failure intermediário não é necessariamente content regression.

Mas o final bilingual commit precisa passar o workflow completo.

## Workflow de reconciliação

Uma reconciliação normal de stale page:

1. leia target page;
2. inspecione frontmatter sources/symbols;
3. inspecione diff desde `reviewed_revision`;
4. inspecione current source;
5. inspecione tests/specifications relevantes;
6. classifique claims afetados;
7. atualize prose apenas onde contract mudou;
8. preserve limitations;
9. atualize ambos idiomas;
10. avance `reviewed_revision`;
11. execute documentation pipeline;
12. confirme saída da stale queue.

Isso evita reescrita desnecessária e blind revision bump.

## Classificação de claims

Para cada statement potencialmente afetado, classifique como:

- unchanged;
- implementation detail changed;
- contract changed;
- evidence improved;
- limitation removed;
- new limitation;
- historical only;
- roadmap only.

Isso força separar source churn de documentação realmente afetada.

## Validação de mudanças documentais

A sequência local principal é:

    python -m unittest discover -s tests
    python scripts/build_all.py --source .source --docs docs
    mkdocs build --strict

Hosted workflow adiciona:

- contract verifiers;
- source-fact checks;
- JavaScript checks;
- SEO/discovery;
- reader smoke;
- Pages artifact validation.

Batch não termina apenas porque Markdown renderiza localmente.

## Documentation CI não é runtime CI

Workflow verde da documentação prova:

- metadata válida;
- source paths resolvíveis;
- curriculum válido;
- generated artifacts;
- static site;
- reader checks.

Não prova kernel boot ou driver functionality.

Runtime claims continuam exigindo ChrisOS gates.

Essa separação deve permanecer explícita.

## Source revision sem prose change

Se review conclui que prose continua semanticamente correta, pode ser correto alterar apenas `reviewed_revision`.

Mas isso só ocorre depois de inspecionar o diff relevante.

Commit message deve registrar reconciliation intent para evitar metadata churn inexplicável no histórico.

## Adicionando source dependencies

Review pode revelar que a página depende de file não declarado.

Adicione quando ele materialmente sustenta current implementation claim.

Depois disso stale detection passa a acompanhar essa dependency.

Não adicione files sem relação apenas para aumentar context pack.

## Removendo source dependencies

Remova path quando a página não depende mais dele.

Isso ocorre após:

- refactoring;
- ownership transfer;
- API extraction;
- conteúdo histórico migrado para history chapter.

Dependency obsoleta gera stale noise recorrente.

## Páginas históricas

History pages usam revision evidence de forma diferente.

Podem citar commits antigos porque mudança no tempo é o assunto.

Historical SHA no prose não deve ser substituído automaticamente por HEAD.

Apenas frontmatter reviewed baseline acompanha current source usado para reconciliar a página como um todo.

## Specifications

Specification pages exigem cuidado extra.

Source change pode ser implementation-only ou alterar persistent/ABI contract.

Reviewer deve observar:

- magic/version;
- field layout;
- bounds;
- reader acceptance;
- writer output;
- compatibility;
- migration;
- errors.

Specification nunca deve ser atualizada apenas olhando struct diff sem decidir se serialized behavior mudou.

## Validation pages

Validation docs também ficam stale quando gate definitions mudam.

Novo dependency, marker, timeout ou skip behavior altera o que o projeto pode afirmar mesmo que kernel code permaneça.

Por isso makefiles/test harnesses podem legitimamente ser sources de validation chapters.

## Developer guides

Operational guides devem permanecer próximos dos commands reais do repository.

Quando build/setup muda, source-repository docs e site guide podem exigir atualização.

Agent deve diferenciar:

- repository-local command truth;
- long-form architectural explanation.

Duplicated commands devem ser minimizados, mas operational accuracy tem prioridade.

## Falha durante manutenção

Se documentation build falha, classifique a falha antes de editar prose.

Categorias comuns:

- bilingual mismatch;
- invalid source path;
- duplicate ID;
- curriculum cycle;
- generated drift;
- static-site warning;
- JavaScript/reader regression;
- unrelated infrastructure failure.

Corrija a layer real.

Não altere conteúdo técnico para silenciar infraestrutura.

## Preserve a primeira falha

Quando CI falha, preserve o primeiro meaningful error e o commit correspondente.

Commits repetidos podem cancelar workflows anteriores ou sobrescrever artifacts.

Um failure record curto diferencia:

- pair-incomplete failure esperado;
- final-content regression real;
- environment/infrastructure failure.

O princípio é o mesmo usado nos runtime gates do ChrisOS.

## Regras de custo

O modelo usa controles de custo:

1. cache de source inalterada por Git identity;
2. dependency metadata explícita;
3. diff antes de full file;
4. expansão de contexto apenas quando necessário;
5. fatos gerados sem modelo;
6. não regenerar prose não afetada;
7. reviewed revisions como baselines estáveis;
8. deterministic queues em vez de rediscovery ampla.

Isso reduz computation e editorial churn.

## Propriedade de escala

Considere:

- (D) = tamanho total da documentação;
- (S) = tamanho total do source;
- (A) = source paths afetados;
- (P) = pages que declaram esses paths.

Estratégia ingênua tende a custo:

    O(D + S)

O modelo metadata-driven tende a:

    O(A + P)

mais o bounded source context necessário.

Essa é a razão principal para o modelo escalar.

## Papel de scripts e agents

Automation e agents devem se complementar.

Scripts determinísticos possuem:

- indexing;
- counting;
- hashing;
- graph checks;
- stale detection;
- source extraction.

Engineering review possui:

- significado;
- architecture boundaries;
- trade-offs;
- evidence interpretation;
- compatibility;
- limitations.

Um workflow bom não pede a language model para calcular algo que o repository consegue determinar exatamente.

## Critério de conclusão de um batch

Maintenance batch termina quando:

1. target pages estão tecnicamente reconciliadas;
2. EN/PT-BR permanecem equivalentes;
3. frontmatter está correto;
4. reviewed revision é verdadeiro;
5. generated queues refletem o novo estado;
6. depth warnings alvo realmente desaparecem;
7. full documentation CI passa;
8. Pages/static artifact é produzido.

Isso cria endpoint auditável.

## Nota de revisão

Este workflow foi reconciliado contra o baseline atual da documentação na source revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

Princípio central: **use metadata determinística para decidir o que ler, use source evidence para decidir o que mudou e reserve authored reasoning para o significado técnico que scripts não conseguem inferir.**
