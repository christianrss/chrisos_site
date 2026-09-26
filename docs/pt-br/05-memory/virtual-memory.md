---
id: virtual-memory
lang: pt-br
type: technical-chapter
volume: 05-memory
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/proc.c
symbols:
  - mm_init
  - mm_map_cr3
  - map_4k
  - mm_translate
  - mm_switch
depends_on:
  - physical-memory
  - x86-64-memory-privilege
related:
  - tlb-shootdown
  - processes-syscalls
---

# Memória virtual e page tables x86-64

## Tradução de endereços

Memória virtual insere tradução entre endereços usados por software e endereços físicos.

Uma instrução acessa endereço virtual `V`. A CPU consulta estruturas selecionadas por CR3 e obtém endereço físico `P` com permissões ou gera fault.

<figure class="figure">
<img src="../../assets/diagrams/memory.svg" alt="Tradução de páginas com TLB">
<figcaption>A tradução consulta primeiro o TLB e, em miss, percorre as page tables.</figcaption>
</figure>

## Quatro níveis

Para páginas de 4 KiB no esquema convencional:

```text
63                         48 47    39 38    30 29    21 20    12 11      0
+----------------------------+--------+--------+--------+--------+----------+
| extensão canônica          | PML4   | PDPT   | PD     | PT     | offset   |
+----------------------------+--------+--------+--------+--------+----------+
```

Cada entrada aponta para o próximo nível e contém flags. O PTE final identifica a frame física.

## CR3

CR3 seleciona a raiz da tradução atual. Trocar CR3 é, portanto, operação fundamental de isolamento. `mm_switch` escreve a raiz física escolhida.

## Entradas

PTE combina endereço físico alinhado e flags: present, writable, user/supervisor, NX quando disponível e outros estados definidos pela arquitetura.

## Construção

Mapear uma página pode exigir criar PML4/PDPT/PD/PT intermediários. `mm_map_cr3` percorre a hierarquia e aloca tabelas ausentes via PMM, criando dependência MM → PMM.

Falha no meio precisa preservar ownership claro e retornar erro.

## Kernel high-half compartilhado

Address space de processo pode ter região de usuário privada e mappings altos do kernel compartilhados. Isso evita replicar estruturas e permite entrada controlada no kernel.

O compartilhamento cria obrigação de sincronização quando mappings de kernel mudam.

## Tradução explícita

`mm_translate` permite verificar mapping e recuperar endereço físico/flags sem tocar cegamente o endereço. User-copy utiliza esse tipo de mecanismo para validar ponteiros.

## Page fault

Fault ocorre quando tradução não atende o acesso: mapping ausente, write proibida, violação de privilégio ou outra regra. CR2 recebe o endereço linear e o frame de exceção fornece contexto.

## Mapping não é alocação

```text
PMM: "esta frame pertence a alguém"
MM : "este endereço virtual referencia aquela frame com estas permissões"
```

Separar os conceitos permite aliases e evita double-free.

## Concorrência

Page tables são estruturas compartilhadas protegidas pelo MM lock. Unmap possui um problema adicional: outra CPU pode manter tradução antiga no TLB mesmo depois da alteração em memória. Correção exige coerência de TLB.
