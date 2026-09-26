---
id: volume-02-computer-architecture
lang: pt-br
type: volume-index
volume: 02-computer-architecture
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Arquitetura de computadores

<div class="abstract">Datapaths, controle, conjuntos de instruções, execução x86-64, privilégio, caches, hierarquia de memória, barramentos, MMIO e DMA.</div>

## Escopo

O volume define a terminologia e as relações necessárias antes de entrar em detalhes de implementação. Conceitos gerais são tratados separadamente das decisões específicas do ChrisOS; quando o texto passa para a implementação, a revisão de fonte e os arquivos relevantes são declarados no frontmatter.

## Capítulos centrais

- CPU datapath and ISA
- x86-64 memory and privilege
- Buses, MMIO and DMA

## Regra de leitura

Não é necessário memorizar todos os detalhes das camadas inferiores, mas os termos utilizados pelas camadas superiores são definidos antes do primeiro uso técnico. Diagramas mostram fluxo e responsabilidade; tabelas registram contratos, layouts e estados.
