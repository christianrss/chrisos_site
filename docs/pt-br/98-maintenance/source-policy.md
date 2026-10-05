---
id: source-policy
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
  - documentation-schema
  - validation-evidence
  - bibliography
---

# Política de fontes e revisões

## Propósito

Este capítulo define como a documentação do ChrisOS decide o que conta como evidência, como claims de implementação ficam vinculados a revisões de source e como uma página permanece revisável à medida que o codebase muda.

A política existe para evitar três falhas recorrentes:

1. descrever roadmap como comportamento implementado;
2. manter como atual uma afirmação que era correta em uma revisão anterior, mas deixou de ser após mudança de source;
3. tratar build bem-sucedido da documentação como evidência de que o sistema operacional funciona.

O corpus é revision-aware por design. Todo claim atual de implementação deve ser rastreável à evidência mais forte disponível para exatamente o comportamento descrito.

## Hierarquia de evidência

Para claims sobre comportamento atual do ChrisOS, use esta ordem:

1. source atual do ChrisOS em `main`;
2. testes e gates reproduzíveis na mesma revisão;
3. specifications atuais mantidas no projeto;
4. audits e status records vinculados a revisão;
5. README;
6. roadmap, sempre identificado como futuro.

A ordem é intencional.

README pode resumir arquitetura, mas não substitui source.

Roadmap explica direção, mas não prova implementação.

Testes demonstram paths executados, mas não provam hardware, configurações ou variantes de protocolo que não foram exercitadas.

## Source atual é autoridade de implementação

Quando a pergunta é:

> O que esta revisão do ChrisOS realmente faz?

o source atual é a autoridade primária.

A documentação deve separar:

- fato de implementação;
- interpretação arquitetural;
- design pretendido;
- trabalho futuro.

Fato de implementação precisa ser recuperável de source ou evidência executável.

Interpretação pode explicar rationale e boundaries, mas não pode criar comportamento ausente do código.

## Identidade de revisão

Páginas que documentam implementação usam `reviewed_revision` para registrar a revisão contra a qual foram reconciliadas.

Essa identidade normalmente é um commit SHA.

Ela responde:

> Em qual estado do source esta página foi revisada pela última vez contra suas dependencies declaradas?

Ela não significa:

> Todo texto da página é garantidamente verdadeiro para qualquer revisão futura.

É uma âncora de revisão, não certificação eterna.

## Dependencies de source declaradas

O campo `sources` do frontmatter lista paths concretos dentro do checkout do ChrisOS.

Exemplo:

    sources:
      - kernel/gfx/gfx3d.c
      - kernel/gfx/gfx3d_virgl.c

Esses paths são interpretados a partir da raiz do source repository fornecido ao build da documentação.

`validate_docs.py` rejeita qualquer path declarado que não exista no checkout usado pelo CI.

Invariante:

> source dependency é path real de repository, não label textual.

## O que deve entrar em sources

Um path deve ser declarado quando algum claim substantivo depende dele.

Exemplos comuns:

- implementation files;
- public headers;
- readers/writers de on-disk ou wire formats;
- boot code;
- drivers;
- tests que definem contrato executável relevante;
- build files quando o comportamento de build é parte do assunto.

Não liste todo include transitivo.

O objetivo é o menor source set suficiente para reconstruir o mecanismo documentado.

## O que não deve entrar em sources

Não use `sources` para:

- standards externos;
- textbooks;
- scripts do repository de documentação;
- referências conceituais que não são source do ChrisOS;
- arquivos sem relação adicionados apenas para manipular stale detection;
- paths inferidos por semelhança de nome.

Standards externos pertencem à bibliografia e ao prose do chapter.

Páginas de manutenção, como esta, podem legitimamente usar `sources: []`, pois documentam o sistema documental, não uma implementação ChrisOS.

## Symbols estreitam o contexto

O campo opcional `symbols` identifica nomes especialmente importantes dentro dos sources.

Exemplo:

    symbols:
      - gfx3d_boot
      - gfx3d_mark_lost

Symbols não substituem paths.

Eles são hints usados por tooling de baixo contexto para extrair janelas relevantes de files grandes.

Só devem ser listados quando realmente ajudam a reconstruir o mecanismo.

## reviewed_revision e sources funcionam juntos

O stale-document workflow usa os dois campos.

Conceitualmente:

    page
      |
      +-- reviewed_revision = R
      |
      +-- sources = {s1, s2, ...}
              |
              v
        git diff R..HEAD -- s1 s2 ...

Se nenhum source declarado mudou, a página não fica stale só porque código não relacionado mudou.

Se algum source mudou, a página entra na review queue gerada.

Isso mantém o custo proporcional às dependencies reais.

## Empty source sets

Página com `sources: []` fica propositalmente fora do source-diff stale detection.

Isso é adequado para:

- documentation process;
- external standards mapping;
- teoria conceitual;
- história derivada de commits identificados;
- navigation/maintenance policy.

Não deve ser usado para escapar de manutenção em página implementation-facing.

Se há claim de comportamento atual vindo do code, o code precisa ser declarado.

## Source changed não significa prose necessariamente errado

Um file declarado pode mudar sem invalidar todo o capítulo.

A queue significa:

> requer reconciliação.

Não:

> está certamente incorreto.

O reviewer precisa analisar diff e verificar se contract, invariant, error path, limitation ou behavior documentado mudou.

## Baseline indisponível não é baseline unchanged

`context_pack.py` registra `diff_status`.

Estados possíveis incluem:

- `changed`;
- `unchanged`;
- `unavailable-baseline`;
- not applicable quando não há source dependency.

Se o `reviewed_revision` histórico não pode ser resolvido no checkout, uma ausência de diff não pode ser interpretada como estabilidade.

`unavailable-baseline` exige mais Git history ou full reconciliation.

## Quando atualizar reviewed_revision

Atualize `reviewed_revision` somente depois da reconciliação real.

Sequência correta:

1. ler a página atual;
2. ler sources declarados;
3. inspecionar diff desde a revisão anterior quando disponível;
4. verificar tests/specifications relevantes;
5. corrigir prose e limitations;
6. definir o novo reviewed revision;
7. executar validação documental.

Não altere SHA apenas para limpar a stale queue.

Isso destruiria o significado do campo.

## Integridade bilíngue

Páginas EN e PT-BR com o mesmo `id` devem carregar metadata técnica equivalente.

`validate_docs.py` exige igualdade de:

- `sources`;
- `depends_on`;
- `reviewed_revision`.

Assim um idioma não pode silenciosamente apontar para source baseline ou prerequisite graph diferente.

O prose pode diferir linguisticamente; o escopo técnico não.

## Tests como evidência

Source inspection mostra que code existe.

Test mostra comportamento exercitado.

São camadas distintas.

Um claim útil pode ser modelado como:

[
C = (R,; S,; T,; E)
]

onde:

- (R) é a revisão ChrisOS;
- (S) é o source set;
- (T) é o conjunto de tests/gates;
- (E) é o execution environment.

"NVMe funciona" é fraco.

Mais forte é registrar que o driver na revisão (R) passou um gate nomeado sob uma controller configuration específica.

## Host tests não são guest tests

Host unit test prova lógica executada no host.

Não prova:

- boot;
- guest interrupt delivery;
- DMA dentro do guest;
- firmware real;
- hardware físico.

Host tests são valiosos porque são narrow e rápidos, mas sua evidence class deve permanecer explícita.

## Evidência QEMU

QEMU gate prova um path sob uma configuração virtual declarada.

É integração mais ampla que unit test.

Ainda assim não prova automaticamente:

- hardware físico;
- diversidade de firmware;
- timing real;
- performance física;
- todas as protocol variants.

QEMU é integration environment controlado, não sinônimo de hardware proof.

## Evidência ChrisVM

ChrisVM tests exercitam o emulator/machine model do próprio projeto.

São úteis para:

- CPU state;
- decode;
- execution semantics;
- paging;
- exceptions;
- devices simples;
- direct boot.

Eles não provam equivalência com QEMU ou x86 físico sem differential/conformance evidence separada.

## Evidência de hardware

Claim físico deve carregar contexto suficiente para reprodução.

Registre, quando relevante:

- machine/model;
- CPU;
- firmware mode/version;
- storage controller/device;
- GPU/display path;
- network adapter;
- boot medium;
- ChrisOS revision;
- command/image;
- markers observados;
- failure/recovery behavior.

"Works on hardware" sem profile é evidência fraca.

## External specifications

Standards externos definem comportamento que ChrisOS consome, mas não controla.

Exemplos:

- x86 manuals;
- UEFI;
- ACPI;
- PCIe;
- VirtIO;
- NVMe;
- USB/xHCI;
- RFCs;
- OpenGL/GLSL.

A bibliografia registra essas authorities.

Quando revision importa, o implementation chapter deve identificar a edition/protocol revision relevante.

O standard define o contrato externo; o source ChrisOS define o subset implementado.

## Internal specifications

Formats e ABIs próprios devem possuir specifications próprias.

Exemplos:

- ChrisO;
- ChrisFS;
- CLVM;
- ChrisVM direct-boot protocol;
- shader/CSIR.

Se implementation e specification divergem, há um defect que precisa ser reconciliado.

Não se deve escolher silenciosamente o lado mais conveniente.

## Evidência histórica

History chapters podem citar commits antigos porque mudança ao longo do tempo é o próprio assunto.

Claim histórico deve identificar commit ou intervalo em que era verdadeiro.

Implementation chapter atual não deve usar commit antigo para provar behavior atual.

História preserva design substituído; não sobrepõe source atual.

## README e status snapshots

README e status records ajudam na orientação.

Ficam abaixo na evidence hierarchy porque podem atrasar em relação ao code.

Use-os para descobrir intent, command, boundary e nomenclature, mas verifique behavior técnico com fontes mais fortes.

## Disciplina de roadmap

Roadmap precisa ser explicitamente futuro.

Formulações adequadas:

- planned;
- proposed;
- target;
- future backend;
- not implemented;
- intended direction.

Transformação incorreta:

    roadmap: add hardware virtualization

em:

    current claim: ChrisHV provides hardware virtualization

Em sistema experimental, nomes futuros e atuais podem ser muito próximos; por isso a distinção precisa ser explícita.

## Generated source atlas

O source atlas gerado é mirror/index determinístico.

Pode registrar:

- paths;
- hashes;
- line counts;
- includes;
- detected symbols;
- mirrors completos de textual source.

Não é architectural interpretation.

Fato gerado não deve ser apresentado como se um modelo tivesse verificado runtime behavior.

## Source map

`source_map.py` constrói mapping reverso:

    ChrisOS source path
        -> documentation pages

Isso permite impact analysis.

O mapping vem de metadata, não semantic similarity.

Um file não aparece como dependency apenas porque o nome parece relacionado.

## Review queue

`stale_docs.py` compara sources desde `reviewed_revision` até HEAD e gera queue bilíngue.

A queue é um **attention mechanism**.

Não é verdict de correctness.

Uma página stale pode continuar correta.

Uma página também pode estar errada mesmo sem source change, caso a revisão original tenha sido incompleta.

## Documentation build como evidência

Pipeline documental bem-sucedido estabelece propriedades da documentação:

- frontmatter parses;
- bilingual identity é válida;
- source paths declarados existem;
- curriculum constraints passam;
- generated artifacts são produzidos;
- static site builds;
- reader/SEO checks passam.

Não estabelece:

- kernel boot;
- driver functionality;
- protocol conformance;
- physical hardware support.

Documentation CI e runtime validation são classes diferentes.

## Negative evidence e limitations

Capítulo de qualidade registra também o que não está provado.

Exemplos:

- "host-tested only";
- "QEMU verified; hardware unverified";
- "parser implements subset X";
- "ChrisHV intentionally refused";
- "production kernel not booted by ChrisVM".

Limitations explícitas impedem que evidência cresça além do escopo real.

## Checklist de source policy

Antes de marcar implementation page como revisada:

1. confirme source revision;
2. verifique cada declared path;
3. leia source relevante;
4. leia diff desde reviewed revision quando disponível;
5. confira symbols importantes;
6. identifique tests mais fortes;
7. registre environments não testados;
8. separe current behavior de roadmap;
9. preserve limitations;
10. sincronize metadata EN/PT-BR;
11. execute pipeline documental.

## Invariante central

O invariante é:

> Todo claim atual de implementação deve ser atribuível a uma revisão de source e nunca pode declarar uma evidence class mais forte que os tests realmente executados.

Isso é mais importante que manter SHAs visualmente recentes.

Página stale, mas honesta, pode ser reconciliada.

Página que silenciosamente superestima evidência perde rastreabilidade.

## Nota de revisão

Esta política reflete o tooling documental e o baseline ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

Como o assunto é policy da documentação e não um subsystem de implementação, a página declara deliberadamente `sources: []`.
