---
id: volume-09-emulation
lang: pt-br
type: volume-index
volume: 09-emulation
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Emulação de máquina e virtualização

<div class="abstract">Interpretação de instruções, estado arquitetural, buses e dispositivos, ChrisVM/ChrisCPU e a fronteira para virtualização assistida por hardware.</div>

## Escopo

O volume define a terminologia e as relações necessárias antes de entrar em detalhes de implementação. Conceitos gerais são tratados separadamente das decisões específicas do ChrisOS; quando o texto passa para a implementação, a revisão de fonte e os arquivos relevantes são declarados no frontmatter.

## Capítulos centrais

- Emulator theory
- ChrisVM and ChrisCPU
- Virtualization and ChrisHV boundary

## Regra de leitura

Não é necessário memorizar todos os detalhes das camadas inferiores, mas os termos utilizados pelas camadas superiores são definidos antes do primeiro uso técnico. Diagramas mostram fluxo e responsabilidade; tabelas registram contratos, layouts e estados.
