---
id: volume-05-memory
lang: pt-br
type: volume-index
volume: 05-memory
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Sistemas de memória

<div class="abstract">Alocação de memória física, endereçamento virtual, paginação de quatro níveis, CR3, TLBs, heaps, ownership e invalidação multiprocessador.</div>

## Escopo

O volume define a terminologia e as relações necessárias antes de entrar em detalhes de implementação. Conceitos gerais são tratados separadamente das decisões específicas do ChrisOS; quando o texto passa para a implementação, a revisão de fonte e os arquivos relevantes são declarados no frontmatter.

## Capítulos centrais

- Physical memory
- Virtual memory
- Heap and ownership
- TLB shootdown

## Regra de leitura

Não é necessário memorizar todos os detalhes das camadas inferiores, mas os termos utilizados pelas camadas superiores são definidos antes do primeiro uso técnico. Diagramas mostram fluxo e responsabilidade; tabelas registram contratos, layouts e estados.
