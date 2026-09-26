---
id: volume-04-kernel
lang: pt-br
type: volume-index
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Arquitetura do kernel

<div class="abstract">Fronteiras de privilégio, organização monolítica modular, exceções, interrupções, SMP, processos, execução ELF em user mode e syscalls.</div>

## Escopo

O volume define a terminologia e as relações necessárias antes de entrar em detalhes de implementação. Conceitos gerais são tratados separadamente das decisões específicas do ChrisOS; quando o texto passa para a implementação, a revisão de fonte e os arquivos relevantes são declarados no frontmatter.

## Capítulos centrais

- Kernel model and trust boundaries
- Interrupts and SMP
- Processes and system calls

## Regra de leitura

Não é necessário memorizar todos os detalhes das camadas inferiores, mas os termos utilizados pelas camadas superiores são definidos antes do primeiro uso técnico. Diagramas mostram fluxo e responsabilidade; tabelas registram contratos, layouts e estados.
