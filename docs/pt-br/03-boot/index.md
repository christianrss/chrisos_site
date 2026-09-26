---
id: volume-03-boot
lang: pt-br
type: volume-index
volume: 03-boot
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Boot e formatos executáveis

<div class="abstract">Estado após energização, firmware, UEFI, Limine, carregamento ELF, layout de linkedição e transição para o entry point do ChrisOS.</div>

## Escopo

O volume define a terminologia e as relações necessárias antes de entrar em detalhes de implementação. Conceitos gerais são tratados separadamente das decisões específicas do ChrisOS; quando o texto passa para a implementação, a revisão de fonte e os arquivos relevantes são declarados no frontmatter.

## Capítulos centrais

- Power-on to kstart
- ELF and kernel linking

## Regra de leitura

Não é necessário memorizar todos os detalhes das camadas inferiores, mas os termos utilizados pelas camadas superiores são definidos antes do primeiro uso técnico. Diagramas mostram fluxo e responsabilidade; tabelas registram contratos, layouts e estados.
