---
id: heap-ownership
lang: pt-br
type: technical-chapter
volume: 05-memory
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/heap.c
  - kernel/metal/pmm.c
  - docs/RESOURCE_OWNERSHIP.md
  - docs/LOCKING.md
symbols:
  - heap_init
  - kmalloc
  - kfree
depends_on:
  - physical-memory
related:
  - tlb-shootdown
---

# Heap do kernel, ownership e ciclo de vida

## Por que existe heap acima do PMM

PMM aloca recursos físicos em páginas. Código do kernel precisa de objetos menores: estruturas, buffers, strings e tabelas.

Heap obtém regiões grandes e as subdivide. Arenas do ChrisOS usam páginas físicas contíguas acessadas pelo direct map. Headers registram tamanho e estado do bloco.

```text
+-------------+-------------------------+
| header      | alocação do usuário     |
| size, used  | payload alinhado         |
+-------------+-------------------------+
```

## Alinhamento, split e coalesce

Pedidos são arredondados para alinhamento compatível com CPU/ABI. Bloco livre grande pode ser dividido em parte usada e remainder livre. Blocos livres adjacentes podem ser fundidos para reduzir fragmentação.

Adjacência lógica de heap é diferente de contiguidade física do sistema inteiro; cada arena fornece seu próprio intervalo.

## Crescimento

Quando nenhuma arena atende, heap pede novas páginas ao PMM. ChrisOS preserva uma reserva e limita a quantidade de arenas. Isso estabelece a dependência e ordem de locks heap → PMM.

## Ownership

Alocação responde quem pode usar memória agora; lifetime responde quem deve liberá-la.

O documento de ownership do projeto atribui destroy paths para page tables de processo, frames de usuário, JIT, file descriptors, sockets, stacks de kthreads, contextos gráficos e buffers de devices.

Leak normalmente nasce de responsabilidade ambígua, não da inexistência de uma função `free`.

## Destruição como arquitetura

Subsystem não está completo apenas com create. Precisa de destroy simétrico ou política explícita de lifetime até o reboot.

```text
create
  ↓
initialize
  ↓
publish / use
  ↓
detach
  ↓
parar acesso assíncrono
  ↓
unmap / release
  ↓
free
```

Para DMA e TLB a ordem é crítica: não se libera memória enquanto hardware ou outra CPU ainda puder acessá-la.

## Ordem de locks

A ordem documentada entre JIT, MM, heap e PMM evita ciclos de espera. Portanto locking faz parte da arquitetura de memória.

## Caminhos de falha

Alocação multi-etapas deve ser revisada como transação. Se a etapa 4 falha, recursos 1–3 precisam ser revertidos em ordem coerente, salvo se ownership já foi transferido. Caminhos de low-memory são fontes clássicas de leaks e dangling references.
