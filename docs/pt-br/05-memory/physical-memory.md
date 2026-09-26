---
id: physical-memory
lang: pt-br
type: technical-chapter
volume: 05-memory
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/pmm.c
  - kernel/metal/pmm.h
  - kernel/metal/bootinfo.c
symbols:
  - pmm_init
  - pmm_alloc
  - pmm_alloc_contig
  - pmm_alloc_dma32
  - pmm_free
depends_on:
  - atom-semiconductor
  - x86-64-memory-privilege
related:
  - virtual-memory
  - heap-ownership
---

# Gerenciamento de memória física

## De capacidade DRAM a frames alocáveis

Firmware e bootloader informam ranges físicos com significados diferentes: RAM utilizável, regiões reservadas, ACPI, framebuffer/devices e outras categorias. Kernel não pode tratar todo endereço físico numérico como DRAM livre.

O physical memory manager converte a parte utilizável em unidades de alocação. ChrisOS usa páginas de 4 KiB, alinhadas ao tamanho comum das page tables x86-64.

## Alocação de frames

PMM responde uma pergunta diferente de `malloc`:

> qual frame físico pode ser entregue com segurança a um owner?

O resultado é endereço físico, não necessariamente ponteiro C dereferenciável. ChrisOS utiliza o higher-half direct map para obter endereço virtual correspondente a RAM física quando necessário.

## Estado por bitmap

Representações de PMM costumam registrar um bit ou pequeno estado por frame. O allocator precisa reservar imagem do kernel, page tables, regiões de firmware/bootloader, memória de dispositivo e alocações precoces.

Alocação dupla é catastrófica porque dois owners passam a escrever a mesma frame.

## Contiguidade

`pmm_alloc_contig` procura sequência de páginas para DMA, arenas ou buffers específicos. Contiguidade física fica mais difícil com fragmentação.

## DMA32

`pmm_alloc_dma32` atende devices que não conseguem endereçar qualquer endereço físico de 64 bits.

```text
RAM acessível pela CPU ≠ RAM acessível por todo dispositivo
```

## Locking

Estado PMM é compartilhado entre CPUs e protegido por spinlock. A implementação documentada permite reentrada na mesma CPU em caminhos específicos e preserva estado de interrupção na aquisição externa.

Sem exclusão, duas CPUs poderiam observar a mesma página livre e alocá-la simultaneamente.

## PMM e heap

Heap obtém backing físico do PMM. PMM não deve depender do heap, pois isso criaria ciclo na base do gerenciamento de memória. A ordem atual permite heap → PMM.

## Contabilidade e validação

PMM precisa contabilizar free/used e detectar operações inválidas como double free. Testes host podem estressar duplicidade e concorrência, mas não equivalem ao caminho real de IRQ/SMP.

## Ownership físico e mapping

Frame pode continuar alocada enquanto mappings mudam. Remover mapping não implica liberar a frame. Essa separação é central para páginas compartilhadas, MMIO, page tables, JIT e teardown de processos.
