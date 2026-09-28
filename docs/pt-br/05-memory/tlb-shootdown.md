---
id: tlb-shootdown
lang: pt-br
type: technical-chapter
volume: 05-memory
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/mm.c
  - kernel/metal/tlb_proto.c
  - kernel/metal/tlb_proto.h
  - kernel/metal/smp.c
symbols: []
depends_on:
  - virtual-memory
  - interrupts-smp
related:
  - heap-ownership
---

# Coerência de TLB e shootdown

## Alterar a page table não basta

Processadores armazenam traduções recentes no Translation Lookaside Buffer. Alterar um PTE em RAM não garante que outra CPU abandone imediatamente uma tradução antiga.

```text
CPU 0                     CPU 1
-----                     -----
remove PTE
free frame                ainda possui TLB antigo
reutiliza frame           acessa endereço antigo
                          corrompe a frame reutilizada
```

A page table em memória pode estar correta e o sistema ainda assim corromper dados.

## Invalidação local e SMP

Uma CPU possui operações arquiteturais para invalidar traduções locais. Em SMP, toda CPU que possa ter cacheado o mapping precisa participar antes de a frame ser reutilizada.

## Protocolo

ChrisOS modela shootdown em `tlb_proto.c`. O protocolo acompanha estado das CPUs, geração observada, heartbeat/progresso e se reuse é seguro.

MM pode enviar IPI aos CPUs online; o handler remoto realiza o caminho de invalidação e ack.

## Gerações

Cada invalidação publicada recebe uma geração. CPU está atual quando `seen` coincide com a geração global.

```text
publica geração N
       │
       ├── CPU0 seen=N
       ├── CPU1 seen=N
       └── CPU2 seen=N
              │
              ▼
        reuse permitido
```

Uma CPU online atrasada torna reuse inseguro.

## CPU não responsiva

Se uma CPU não responde, esperar indefinidamente pode travar o kernel; reutilizar sem ack pode corromper memória. O protocolo ChrisOS possui estado fenced e exige evidência adicional de halt/flush antes de liberar reuse.

Isso é mais seguro que simplesmente estourar timeout e continuar.

## Poll e IPI

Durante early boot, APs podem ainda não ter caminho de interrupções operacional. O projeto mantém polling além de IPI para certos estágios. Um mecanismo válido depois de `sti`/APIC pode não existir durante construção do próprio subsistema.

## Interação com locks

MM lock protege page tables. O handler remoto não pode tentar adquirir o mesmo lock enquanto o initiator espera sob ele, ou ocorreria deadlock. O caminho documentado de ack não toma MM lock.

## Quarentena

Se ainda não é possível provar que uma tradução desapareceu, a memória não deve voltar ao allocator geral. Quarentena adia reuse até o protocolo declarar segurança.

O princípio geral é que reclamation concorrente exige provar não apenas que o objeto saiu da estrutura central, mas que nenhum contexto retém referência utilizável.
