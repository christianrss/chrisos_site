---
id: virtual-memory
lang: pt-br
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/pmm.h
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/tlb_proto.c
  - kernel/metal/tlb_proto.h
symbols:
  - mm_init
  - mm_map_cr3
  - map_4k
  - map_4k_nosync
  - mm_translate
  - mm_virt_to_phys
  - mm_switch
  - mm_clone_kernel_space
  - mm_unmap_cr3
  - unmap_4k
  - mm_free_user_space
  - mm_flush_tlb
  - mm_tlb_quarantine
depends_on:
  - physical-memory
  - hhdm
  - x86-64-memory-privilege
related:
  - page-table-layout
  - page-faults
  - address-spaces
  - tlb
  - tlb-shootdown
  - processes-syscalls
---

# Memória virtual e gerenciamento de page tables

## Escopo

Memória virtual separa os endereços usados pelo software das posições físicas que armazenam os bytes. Em x86-64, CR3 seleciona a hierarquia de tradução atual; a CPU combina essa hierarquia com permissões das page tables e estado do TLB para transformar endereço virtual em endereço físico ou gerar uma exception.

O ChrisOS usa memória virtual para funções distintas:

- preservar mappings compartilhados do kernel no higher half;
- criar address spaces privados de processo;
- mapear páginas de processo sob demanda;
- criar aliases de kernel;
- reservar uma janela MMIO dedicada;
- traduzir endereços para validação e diagnóstico;
- separar acesso user/supervisor;
- coordenar teardown de mappings com invalidação de TLB e reuso físico atrasado.

A separação arquitetural central é:

~~~text
PMM controla ownership de frames físicos.
MM controla traduções virtual -> físico.
O protocolo de TLB determina quando traduções antigas não podem mais ser usadas.
~~~

Essas três responsabilidades precisam permanecer separadas para teardown correto.

![Relação entre ownership do PMM, page tables, CR3, invalidação de TLB e reuso físico](../../assets/diagrams/virtual-memory-mapping-pt-br.svg)

## Modelo de tradução

Uma instrução da CPU emite endereço virtual.

Conceitualmente:

~~~text
endereço virtual
   -> consulta TLB
      -> hit: tradução e permissões em cache
      -> miss: page-table walk por hardware a partir de CR3
            -> presente e permitido: endereço físico
            -> ausente ou proibido: page fault
~~~

Software altera page tables em memória, mas outra CPU ou a própria CPU pode manter tradução antiga no TLB.

Logo alterar uma PTE não significa que toda execução passe imediatamente a observar o novo estado.

Essa diferença explica por que unmap e reuso de frame exigem sincronização adicional.

## Estrutura x86-64 em quatro níveis

O ChrisOS usa o esquema convencional:

~~~text
PML4 -> PDPT -> PD -> PT -> frame de 4 KiB
~~~

Para página comum de 4 KiB:

~~~text
bits 47..39 -> índice PML4
bits 38..30 -> índice PDPT
bits 29..21 -> índice PD
bits 20..12 -> índice PT
bits 11..0  -> offset dentro da página
~~~

Cada tabela possui 512 entradas de 64 bits:

~~~text
4096 bytes / 8 bytes por entrada = 512
~~~

Assim cada índice possui 9 bits.

Os helpers do ChrisOS extraem cada índice por shifts e máscara 0x1ff.

A geometria detalhada das entradas fica em page-table-layout; aqui o foco é lifecycle e ownership de mappings.

## CR3 e raiz do kernel

Durante mm_init, o ChrisOS lê CR3:

~~~text
mm_cr3_phys = CR3 & MM_ADDR_MASK
~~~

O kernel adota a raiz já ativa quando chega nessa etapa, em vez de construir primeiro uma hierarquia completamente nova.

mm_kernel_cr3 expõe essa raiz física.

mm_switch escreve nova raiz física em CR3.

CR3 espera endereço físico. Usar ponteiro virtual HHDM no lugar da raiz física estaria errado.

## Ordem de inicialização

O fluxo atual é:

~~~text
Limine cria mappings de boot
    -> bootinfo_init valida HHDM e memory map
    -> pmm_init controla frames físicos
    -> mm_init adota CR3 atual
    -> heap e processos inicializam
~~~

mm_init inicializa mm_lock e o runtime de TLB, captura CR3, posiciona o cursor da janela MMIO e marca a camada MM como pronta.

Depois traduz o endereço virtual do framebuffer fornecido pelo Limine usando mm_virt_to_phys.

Se a tradução não existe, o boot entra em panic.

Esse check confirma que o walker consegue resolver um mapping pré-existente importante.

## Páginas de page table vêm do PMM

Quando falta uma tabela intermediária, o ChrisOS aloca um frame de 4 KiB via PMM.

alloc_zero_table_try:

1. chama pmm_alloc;
2. converte o físico em ponteiro HHDM;
3. zera as 512 entradas;
4. retorna o endereço físico.

O zeroing é obrigatório porque tabela nova precisa iniciar com todas as entradas não-presentes.

Usar RAM antiga sem zerar poderia interpretar lixo como mapping válido.

A direção de dependência é:

~~~text
MM -> PMM
~~~

O PMM não depende da MM para bookkeeping comum.

## Mapping no address space ativo do kernel

map_4k associa um frame físico alinhado de 4 KiB a uma página virtual alinhada no root atual do kernel.

Ele valida alinhamento, adquire mm_lock e percorre PML4, PDPT, PD e PT.

Tabelas intermediárias ausentes são criadas por ensure_table.

Uma entrada intermediária nova recebe PRESENT e WRITE.

Na leaf:

~~~text
PTE = base_física | flags | PRESENT
~~~

Após liberar o lock, map_4k executa invlpg no endereço virtual.

map_4k_nosync altera a PTE sem essa invalidação local.

A versão nosync é primitive especializada; o caller precisa conhecer o motivo pelo qual a invalidação imediata não é necessária ou será coordenada em outra etapa.

## Mapping em CR3 arbitrário

mm_map_cr3 instala uma página de 4 KiB em uma raiz fornecida.

Diferenças relevantes:

- estado/alinhamento inválido retorna -1 em vez de panic;
- alocação de tabelas intermediárias é fallible;
- mappings user propagam USER pelas entradas intermediárias;
- a função não troca o CR3 ativo;
- a função não executa por si só shootdown remoto.

A propagação do bit USER é essencial.

Leaf user-accessible não basta se algum parent bloquear ring 3.

Permissão user é propriedade do caminho inteiro.

## Falha parcial na criação de tabelas

ensure_table_flags cria níveis gradualmente.

Se faltar memória em nível posterior, mm_map_cr3 retorna -1.

Tabelas intermediárias já instaladas em níveis superiores podem permanecer.

Não existe leaf mapping para o frame pedido, porém a operação não faz rollback transacional de toda estrutura criada antes da falha.

Essas páginas intermediárias continuam pertencendo ao address space e são recuperadas no teardown.

Logo seria incorreto afirmar que “falha de map não altera nenhuma estrutura”.

## Mapping versus ownership físico

PTE apontar para um frame não significa que MM seja owner desse frame.

Exemplos:

- páginas user pertencem ao estado do processo;
- páginas de page table pertencem à hierarquia MM;
- endereço MMIO não é alocação PMM;
- framebuffer não é frame comum do PMM;
- um frame pode ter vários aliases virtuais.

Portanto:

~~~text
remover PTE != liberar frame físico
liberar frame físico != remover todas as PTEs
~~~

As duas camadas precisam ser coordenadas.

## Address spaces de processo

mm_clone_kernel_space aloca um novo PML4 e copia as entradas 256 a 511 do PML4 do kernel.

A metade inferior começa vazia.

Conceitualmente:

~~~text
CR3 de processo
  metade inferior: mappings privados/user
  metade superior: mappings compartilhados do kernel
~~~

Assim kernel, HHDM e outras regiões privilegiadas continuam acessíveis quando o CR3 de processo está ativo.

A cópia é apenas das entradas do PML4, não uma deep copy de todas as árvores do higher half.

Os roots de processo compartilham as estruturas superiores apontadas por essas entradas.

## Separação de privilégio

Endereço alto versus baixo não é suficiente para segurança.

Os bits de permissão nas page tables determinam acesso.

Páginas user recebem USER e as entradas intermediárias também precisam desse bit.

Mappings compartilhados do kernel permanecem supervisor-only.

Para acesso ring 3 funcionar, todo o caminho precisa permitir user e a leaf precisa autorizar write/execute conforme a operação.

Essa é parte da fronteira de isolamento fornecida pelo hardware.

## Estado writable e executable

O ChrisOS expõe flags como:

~~~text
WRITE
USER
PWT
PCD
NX
~~~

NX utiliza o bit 63.

Uma página de dados pode ser marcada non-executable quando o ambiente está configurado para NX.

A API atual é de baixo nível: caller escolhe os flags.

Não existe objeto de política W^X de alto nível nessa camada.

Logo segurança depende da escolha de flags pelos consumidores.

## Janela MMIO

map_mmio_page cria mappings para device memory.

A janela começa em:

~~~text
0xffffffff90000000
~~~

e possui 256 slots de 4 KiB, totalizando 1 MiB.

Os flags usados são:

~~~text
PRESENT | WRITE | PWT | PCD | NX
~~~

Isso diferencia MMIO de RAM comum/HHDM.

mmio_next avança monotonically.

Não existe free/reuse da janela MMIO.

Ao esgotar os 256 slots, o kernel entra em panic.

## Tradução virtual -> físico

Existem dois helpers relacionados.

mm_translate percorre um CR3 fornecido e retorna endereço físico e flags da leaf.

Ele reconhece:

- páginas de 4 KiB;
- páginas grandes de 2 MiB no PD;
- páginas de 1 GiB no PDPT.

mm_virt_to_phys percorre o root atual do kernel e retorna zero quando não encontra mapping.

Uma API é explícita em address space e retorna flags; a outra é conveniência para o kernel atual.

## Awareness de huge pages

map_4k não divide huge page existente.

Se uma entrada intermediária possui PS, ensure_table entra em panic porque o path de 4 KiB não pode descer através daquela leaf.

Por outro lado, os walkers de tradução entendem leaves de 1 GiB e 2 MiB.

Assim o ChrisOS consegue observar huge mappings herdados do ambiente de boot, mas não oferece API genérica para editar uma subpágina de 4 KiB dentro deles.

## Unmap no kernel

unmap_4k percorre a hierarquia do kernel.

Se nível necessário está ausente ou é huge leaf, retorna sem alterar.

Para leaf de 4 KiB, zera a PTE e executa invlpg local.

Não libera o frame físico.

O caller decide quando o frame pode voltar ao PMM.

## Unmap em address space específico

mm_unmap_cr3 zera uma leaf de 4 KiB na raiz fornecida.

Depois lê o CR3 atual.

Somente quando o root alterado está ativo nesta CPU executa invlpg local.

Se outra CPU ou contexto posterior ainda possuir a tradução no TLB, sincronização mais ampla continua necessária.

Modificar a tabela não é protocolo completo de teardown SMP.

## Coerência de TLB e reuso físico

Considere uma PTE removida e o frame imediatamente devolvido ao PMM.

Outra CPU pode manter virtual -> físico antigo no TLB.

Ela então poderia escrever no frame já entregue a outro owner.

A ordem segura é:

~~~text
remover mapping
    -> invalidar e obter acknowledgement das traduções antigas
    -> provar que reuso é seguro
    -> liberar/reap frame físico
~~~

O ChrisOS possui runtime de TLB/shootdown e quarantine física para casos em que reuso ainda não é seguro.

O protocolo detalhado fica em tlb-shootdown.

## Quarantine

mm_tlb_quarantine:

- libera imediatamente quando o runtime diz que reuso é seguro; ou
- adiciona o range a uma lista fixa de quarantine.

A capacidade é 128 ranges.

mm_tlb_reap devolve os frames ao PMM somente quando o runtime confirma estado seguro.

Quarantine é mecanismo de lifetime, não mecanismo de tradução.

Ela conecta sincronização de TLB a ownership físico.

## Lock da MM

Manipulação de page tables usa mm_lock.

mm_enter não é spin simples: enquanto espera, chama mm_tlb_poll.

Isso permite que CPU esperando o lock ainda processe trabalho pendente de TLB e não impeça progresso distribuído.

Depois tenta CAS no lock e usa pause entre tentativas.

É integração deliberada entre locking e protocolo de TLB.

## Por que shootdown não mantém mm_lock

O source alerta contra esperar acknowledgements remotos com mm_lock adquirido.

Um handler ou path remoto pode precisar de progresso de memory management para responder.

Segurar lock durante toda espera pode criar ciclo.

O ChrisOS separa:

1. mutation da page table sob mm_lock;
2. sincronização distribuída de TLB em estado separado.

Scope de lock faz parte da correção.

## Destruição de address space

mm_free_user_space percorre as 256 entradas inferiores do PML4 de um address space que não seja o kernel.

Para árvores sem huge leaves, libera recursivamente páginas de tabelas intermediárias e limpa as entradas.

Depois libera o próprio PML4.

A metade superior não é percorrida nem liberada porque referencia estruturas compartilhadas do kernel.

Frames user de leaf também não são liberados por essa função.

O contrato do source afirma que esses frames pertencem à page list do processo.

Isso evita double free entre processo e MM.

## Divisão de ownership no teardown

A camada de processo controla frames de dados user.

No teardown ela pode unmapear cada página e devolver o físico.

Separadamente mm_free_user_space recupera páginas estruturais das page tables.

Assim:

~~~text
page list do processo -> frames de dados leaf
hierarquia MM         -> frames intermediários de page table
kernel compartilhado  -> não é liberado com processo
~~~

Esse split é invariante central do sistema atual.

## Troca de CR3 e flush local

Escrever CR3 muda o root ativo.

mm_flush_tlb lê e reescreve o CR3 atual para obter o comportamento convencional de flush local associado ao reload.

Efeitos exatos dependem de recursos como PCID e global pages, mas a implementação atual trata o reload como primitive coarse-grained.

Para uma página, invlpg é mais direcionado.

## Self-test

mm_selftest valida propriedades de integração.

Ele:

1. aloca página física via PMM;
2. mapeia em endereço virtual fixo;
3. escreve 0x00c0ffee por esse alias;
4. verifica valor pelo HHDM;
5. mapeia o LAPIC físico pela janela MMIO;
6. lê LAPIC ID;
7. compara/loga com bootinfo.

O primeiro teste demonstra aliases diferentes para o mesmo frame.

O segundo valida mapping MMIO real.

Não cobre exaustivamente privilege user, edição de huge pages, shootdown multi-CPU ou destruição de address space.

## Políticas de falha

A camada mistura panic e retorno de erro.

Exemplos:

- map_4k antes de mm_init: panic;
- map_4k desalinhado: panic;
- falta de página para tabela no path kernel: panic;
- mm_map_cr3 fallible: -1;
- tradução ausente: falha/zero;
- janela MMIO esgotada: panic;
- huge page no caminho de 4 KiB: panic.

Callers precisam conhecer o contrato de cada API.

## Complexidade

Walk de 4 níveis tem quantidade fixa de lookups.

Ignorando alocação PMM:

~~~text
map/translate/unmap = O(níveis) = O(1)
~~~

Criar mapping novo pode exigir até três páginas intermediárias sob um PML4 existente.

Destruir address space é diferente: custo cresce com número de páginas de page table existentes.

Shootdown de TLB depende de número/responsividade de CPUs, não apenas de profundidade da árvore.

## Segurança

Memória virtual é principal fronteira de isolamento hardware entre processos e kernel.

Falhas críticas incluem:

- propagar USER para mapping supervisor;
- deixar WRITE ou execução mais amplos que necessário;
- reutilizar frame antes de eliminar aliases stale;
- tratar MMIO como RAM;
- aceitar ponteiro user sem validar tradução/permissões.

A MM fornece mecanismos.

A política correta depende das camadas superiores.

## Limitações atuais

A implementação atual possui:

- suposição de quatro níveis;
- sem suporte genérico a five-level paging;
- sem API genérica de criação/split de huge pages;
- janela MMIO fixa de 1 MiB;
- sem free/reuse da janela MMIO;
- sem copy-on-write;
- sem refcount de page tables;
- sem rollback transacional de tabelas intermediárias em falha;
- estruturas do upper half compartilhadas exigem sincronização cuidadosa;
- APIs expõem flags baixos;
- teardown depende de ownership das leafs pela camada de processo;
- coerência distribuída de TLB pertence a protocolo separado.

Essas limitações são fatos da implementação, não exigências do x86-64.

## Mapa de fonte

kernel/metal/mm.c implementa walks, alocação de tabelas, mappings de kernel/processo, MMIO, clone de address space, unmap, tradução e quarantine ligada a TLB.

kernel/metal/mm.h define flags e contratos públicos.

kernel/metal/pmm.c fornece frames físicos para page tables.

kernel/metal/proc.c controla leaf frames e lifecycle de CR3 dos processos.

kernel/metal/tlb_proto.c e tlb_proto.h implementam o protocolo distribuído usado em teardown sensível a reuso.

As afirmações foram reconciliadas com ChrisOS e05a17fd76333114a3fb5c2452f38ca747d4ac56.
