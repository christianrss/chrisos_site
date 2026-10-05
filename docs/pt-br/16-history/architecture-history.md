---
id: architecture-history
lang: pt-br
type: technical-chapter
volume: 16-history
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - README.md
  - docs/README.md
symbols: []
depends_on: []
related:
  - validation-evidence
  - graphics-history
  - toolchain-history
  - chrisvm-history
  - source-policy
---

# História da arquitetura e evidência substituída

## Propósito

Architecture history registra **quando uma afirmação arquitetural era verdadeira**, por que mudou e qual evidência posterior a substituiu.

ChrisOS evolui rápido o suficiente para que uma frase seja correta em uma revisão e falsa para a `main` atual.

A resposta correta não é apagar história.

É vincular historical claims a commit ou intervalo e manter current implementation claims ancorados em source atual.

## Regra de evidência atual

Para comportamento presente, use source atual e gates reproduzíveis.

Para comportamento histórico, use:

- Git commits;
- commit diffs;
- audits vinculadas a revisão;
- test results com revisão conhecida;
- documentação arquivada naquela revisão.

Audit antiga nunca sobrepõe source novo.

Da mesma forma, source atual não apaga o fato histórico de que um subsystem ainda não existia em commit antigo.

## Arquitetura não é tamanho do diff

File move pode gerar diff enorme sem mudar comportamento.

Uma pequena mudança em ownership, synchronization ou ABI pode ser muito mais arquitetural.

História deve classificar semantic effect, não line count.

Categorias úteis:

- **extension** — contrato existente ganha capability;
- **replacement** — mecanismo novo substitui anterior;
- **refactoring** — responsibility muda sem semantic change pretendida;
- **hardening** — failure, synchronization ou ownership fica mais estrito;
- **evidence upgrade** — implementation permanece, mas gate fica mais forte;
- **boundary extraction** — experimento vira reusable subsystem/API;
- **canonicalization** — authority sai de prose duplicada e passa a uma fonte mantida.

## Snapshot histórico

Um snapshot útil registra:

| Campo | Papel |
|---|---|
| commit | identidade exata |
| data | ordering |
| subsystem | área afetada |
| contrato anterior | comportamento antes |
| novo contrato | mudança semântica |
| evidência | tests/gates disponíveis |
| superseded by | revisão posterior quando aplicável |

Assim história fica auditável, não apenas narrativa.

## Consolidação inicial de desktop e subsystems

Em 18 de setembro de 2026, a organização atual de `kernel/gfx` e `kernel/wm` ficou reconhecível por uma reorganização que também introduziu Gfx2D.

Esse marco mistura refactoring e extension.

Parte do graphics/desktop já existia e foi movida para boundaries mais claras.

A mudança arquitetural não foi "graphics surgiu naquele dia"; foi a separação mais explícita entre low-level drawing/rendering e window-manager responsibilities.

A história detalhada permanece no capítulo `graphics-history`.

## Software 3D como path independente

Em 20 de setembro, ChrisOS já havia expandido para 3D software com triangle rasterization, z-buffer, textures, meshes e voxels.

Isso importa porque o trabalho posterior de GPU não chegou em um vazio.

VirGL foi adicionado depois que já existia CPU rendering architecture.

O software path depois continuou útil como:

- fallback;
- host-testable reference;
- semantic comparison para shaders.

Uma timeline simplista "2D -> GPU" apagaria essa arquitetura intermediária.

## Integration pressure muda contratos

Applications maiores podem obrigar boundaries a ficarem explícitas mesmo sem adicionar novo subsystem.

Doom, desktop apps e Mine Chris pressionaram:

- framebuffer presentation;
- input;
- resource ownership;
- process/application lifetime;
- filesystem;
- compiler/runtime.

São integration milestones.

Eles revelam contracts que demos pequenas conseguem evitar.

## 24 de setembro — stability vira preocupação arquitetural

Uma sequência forte em 24 de setembro tornou reliability explícita.

A stability campaign incluiu mudanças em:

- ChrisFS locking/serialization;
- graphics context ownership;
- driver timeouts;
- QEMU gates;
- parser fuzzing;
- install/SMP behavior;
- TLB shootdown acknowledgement.

Uma correção importante fez timeout de QEMU deixar de significar pass incondicional.

Isso é ao mesmo tempo **evidence upgrade** e mudança na reliability architecture.

## Failure behavior também é arquitetura

Mudanças como:

- retornar storage timeout em vez de esperar para sempre;
- impedir reuse de frame antes do TLB-safe point;
- preservar volatile MMIO no output KCC;
- serializar ChrisFS com lock explícito

não são meramente bug fixes locais.

Elas definem comportamento quando assumptions falham.

História que registra apenas features novas perde parte importante do amadurecimento.

## Hardening de TLB ownership

A sequência de 24–25 de setembro em torno de TLB shootdown reforçou acknowledgement/fencing antes de frames poderem ser reutilizados.

O invariante histórico relevante é:

> physical frame não pode ser reutilizada enquanto outra CPU ainda puder alcançar a antiga translation.

Esse tipo de mudança altera o contract de reclamation/ownership entre CPUs e pertence à architecture history.

## Developer tooling amadurece

Em 24 de setembro a campaign de ferramentas adicionou/hardened:

- editor path bounds;
- text model;
- debug sessions;
- stepping;
- host gates.

Ao mesmo tempo, KCC passou a fail closed fora do subset suportado.

As duas linhas refletem uma regra comum:

> operação unsupported ou inválida deve falhar explicitamente em vez de produzir ambiguous success.

A mesma filosofia aparece depois no ChrisHV.

## Evolução do native toolchain

O toolchain nativo avançou rapidamente de KCC/ChrisAsm/ChrisLd limitados para compilation de real kernel source.

Milestones de 25 de setembro incluíram:

- kernel log;
- volatile MMIO;
- expansão de C/assembler;
- quatorze `kernel/metal` files;
- depois todos os C files de `kernel/metal`.

Isso ampliou fortemente a boundary de self-hosting.

Não significou full self-hosted production kernel.

A limitation continuou sendo parte do contract histórico.

## Self-hosting é staged

Self-hosting possui estágios distintos:

1. edição dentro do OS;
2. compilation de applications;
3. object/link formats próprios;
4. native linking;
5. compiler cobrindo real kernel subsets;
6. construção do kernel completo;
7. boot desse artifact;
8. rebuild reproduzível usando o toolchain próprio.

História precisa dizer qual estágio existia em cada revisão.

Chamar estágio 5 de "fully self-hosted" destruiria a utilidade da cronologia.

## 25 de setembro — VirGL e programmable graphics

Uma branch importante de graphics entrou em 25 de setembro.

A sequência adicionou:

- VirtIO queue/resource handling;
- bounded VirGL command encoding;
- VirtIO-GPU/VirGL proof;
- QEMU targets;
- compiler de GLSL-like subset;
- shader IR próprio;
- TGSI generation;
- compiled shaders alimentando proof scenes.

Isso alterou o rendering boundary: código fixo deixou de ser o único modo e surgiu programmable shader pipeline com representação interna independente do backend.

## Proof versus reusable subsystem

O primeiro VirGL era proof scene.

Depois:

    011dfb25e41ac37db483216c0364923292035d39

extraiu reusable Gfx3D backend.

Isso é **boundary extraction**.

Proof responde:

> o mecanismo funciona?

Reusable subsystem responde:

> callers comuns conseguem usar por meio de ownership/resources estáveis?

Não são o mesmo milestone.

## Cursor como integration evidence

Os fixes posteriores de cursor/scanout em 26 de setembro mostram a distância entre protocol support e integration madura.

Capability de device pode existir e ainda interagir mal com:

- scanout;
- DMA visibility;
- input;
- hypervisor display.

Architecture amadurece quando esses cross-layer contracts ficam explícitos.

## 25 de setembro — surge ChrisVM

Commit:

    86f08da720c24ec6ee0b0179d6a97b3dbf0ca0f6

introduziu machine foundation do ChrisVM e ChrisCPU interpreter.

Menos de uma hora depois:

    be4307a28afb9b923549243d0f85a7358fcbf1b2

adicionou framebuffer/splash.

ChrisVM não substituiu QEMU.

Ele criou path próprio para:

- CPU state;
- decoding;
- execution;
- paging;
- exceptions;
- I/O/MMIO simples;
- deterministic host tests.

O production-kernel path em QEMU permaneceu explicitamente.

É uma **parallel architecture**, não replacement.

## Backend seam antes de acceleration

ChrisVM também introduziu identidade ChrisHV enquanto deixava implementation não funcional.

É um pattern útil:

- definir interface;
- recusar unsupported backend explicitamente;
- implementar software/reference path;
- adicionar acceleration depois que shared state está claro.

A existência do nome ChrisHV nunca deve ser reinterpretada como evidência de hardware virtualization.

## Evidence architecture também evolui

Entre 24 e 26 de setembro cresceram:

- aggregate host gates;
- orphan-test audit;
- fuzz-style tests;
- sanitizer paths;
- structured QEMU markers;
- device-specific QEMU gates;
- installer validation;
- safe-mode testing;
- ChrisVM tests.

Isso muda o maturity level do projeto.

Subsystem com gate forte possui evidence status diferente de demo visual isolada.

## Baseline de 26 de setembro

Commit:

    da3df29cb397932c43d32373871fb9380e688ade

virou baseline documental importante.

Muitas pages foram inicialmente reconciliadas contra esse state.

Mudanças posteriores não invalidaram tudo de uma vez; apenas pages cujas dependencies declaradas mudaram precisaram de source reconciliation.

Esse princípio virou a base do low-context maintenance atual.

## 28 de setembro — muda a autoridade documental

Commit:

    92fb561574bd929522ea005b9fd433138bea3236

tornou `chrisos_site` a canonical technical documentation.

O source repository deixou de carregar technical docs duplicadas como authorities paralelas.

Isso é **canonicalization**.

Não muda kernel execution, mas muda engineering workflow.

O source repo mantém operational instructions próximas aos comandos; o site mantém architecture, contracts, history e long-form technical corpus.

## Developer Guide canônico

Commit:

    e05a17fd76333114a3fb5c2452f38ca747d4ac56

ligou o canonical Developer Guide a partir do source repository.

A authority split fica:

    ChrisOS repository
        -> source
        -> build/run/test mechanics
        -> contribution/security operations

    chrisos_site
        -> canonical architecture
        -> specifications
        -> history
        -> validation interpretation
        -> developer guide

Isso reduz prose duplicada que ficaria stale.

## Evidência superseded

Evidence é superseded quando fato mais novo/forte substitui seu valor para current claims.

Exemplos:

- audit antiga sem VirGL é superada, para comportamento atual, pelo source/gates posteriores;
- early KCC limitation continua historical truth, mas não descreve kernel/metal gate posterior;
- overview pre-ChrisVM não é completo depois do emulator surgir;
- duplicated source docs viram artifacts históricos depois da canonicalization.

Superseded não significa inútil.

Significa apenas que não deve ser primary evidence do estado presente.

## Resolvendo conflitos históricos

Quando dois documentos divergem, pergunte:

1. Qual revisão cada um descreve?
2. Quais sources existiam naquele ponto?
3. Um texto é roadmap e outro implementation?
4. Qual evidence class sustenta cada claim?

Muitas contradições desaparecem quando revision identity é recuperada.

## Architecture epochs

Uma leitura de alto nível pode dividir a história em epochs sobrepostas.

### Desktop/software epoch

Framebuffer, 2D desktop e software graphics tornam-se development surfaces.

### Systems expansion epoch

Storage, filesystem, runtime, applications e software 3D aumentam integration pressure.

### Hardening epoch

Locks, timeouts, TLB, parser, installer e validation contracts ficam mais fortes.

### Native-toolchain epoch

KCC/ChrisAsm/ChrisLd avançam de bootstrap limitado para real kernel-source coverage.

### Accelerated-graphics epoch

VirtIO-GPU/VirGL e shaders adicionam segundo backend 3D.

### Project-owned emulation epoch

ChrisVM/ChrisCPU adicionam x86-64-subset machine controlada pelo projeto ao lado de QEMU.

### Canonical-documentation epoch

Technical authority passa para corpus bilíngue revision-bound com source-impact e stale detection.

Não são releases formais; são agrupamentos explicativos.

## Por que histories ficam separadas

Este capítulo não deve duplicar todas as timelines de subsystem.

Há histories próprias para:

- graphics;
- native toolchain;
- ChrisVM.

Aqui o foco é interação entre linhas e evolução da evidence/authority.

Detalhe commit-by-commit pertence aos chapters especializados.

## Desenvolvimento não linear

ChrisOS evoluiu em linhas paralelas:

    kernel hardening
    graphics
    compiler/runtime
    self-hosting
    installation
    validation
    emulation
    documentation

Mudança em uma linha pode expor assumptions em outra.

Compiler progress revela volatile-MMIO needs; graphics expõe DMA/ownership; installation revela storage/filesystem assumptions.

História deve preservar essas causal interactions, não apenas ordenar datas.

## O que merece entrar na architecture history

Commit futuro deve entrar aqui quando mudar durable boundary como:

- ownership;
- ABI/format;
- privilege;
- concurrency;
- boot contract;
- device model;
- backend architecture;
- recovery semantics;
- validation/evidence class;
- documentation authority.

Code cleanup e optimization isolada normalmente não precisam de top-level milestone.

## Current architecture statement

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, current behavior deve ser reconstruído de current source e current specifications.

Historical commits explicam como o projeto chegou até ali.

Regra:

> current chapters descrevem current contract; history chapters preservam contracts anteriores e transition evidence; nenhum deve fingir ser o outro.

## Nota de revisão

Este capítulo foi reconciliado contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56` e o Git history atual.

A principal lição é que maturidade veio de três tipos de mudança simultaneamente: novas capabilities, boundaries de failure/ownership mais estritas e evidence mais forte para justificar os claims.
