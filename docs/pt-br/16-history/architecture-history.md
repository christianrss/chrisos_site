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
---

# História da arquitetura e evidência substituída

## Por que história é técnica

Sistemas experimentais mudam contratos rapidamente. Uma afirmação pode ser correta em um commit e falsa depois.

História registra quando um design existiu, por que mudou e qual evidência nova o substitui.

## Audits como snapshots

O repositório possui auditorias de campaigns antigas e status atuais. Audit antiga pode afirmar que VirGL não existe ou que KCC é mínimo enquanto a main já avançou.

O registro histórico não deve ser apagado; precisa ser vinculado à revisão e subordinado à evidência atual.

## Categorias

- **extension** — contrato ganha capacidade;
- **replacement** — mecanismo substitui outro;
- **refactoring** — responsabilidade move sem mudança semântica pretendida;
- **hardening** — contratos de falha/ownership/concorrência ficam mais fortes;
- **evidence upgrade** — implementação permanece, gate fica mais forte.

## Gráficos, toolchain e ChrisVM

Gráficos evoluíram de software/VirtIO 2D para Gfx3D/VirGL e shaders, enquanto Mine Chris ainda está no path software.

KCC saiu de sketch muito limitado para host gate capaz de compilar `kernel/metal`, sem ainda construir kernel completo.

ChrisVM/ChrisCPU é uma nova linha arquitetural ausente de snapshots antigos.

## Regra

Capítulos atuais descrevem comportamento atual. História preserva designs anteriores. Claim atual nunca deve depender de audit antiga sem verificar se a fonte relacionada mudou.
