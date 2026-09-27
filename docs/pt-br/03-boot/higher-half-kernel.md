---
id: higher-half-kernel
lang: pt-br
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/linker.ld
  - kernel/metal/start.c
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/gdt.c
  - kernel/metal/smp.c
  - compiler/jit/jit.c
  - compiler/chrisld/chrisld.c
  - docs/chrisvm-boot-protocol.md
  - makefile
symbols:
  - kstart
  - __kernel_start
  - __kernel_end
  - __stack_top
  - bootinfo_phys_to_virt
  - mm_init
  - mm_virt_to_phys
  - mm_kernel_cr3
  - mm_clone_kernel_space
  - mm_switch
depends_on:
  - linker-script
  - x86-64-memory-privilege
  - limine
  - boot-information
related:
  - page-table-layout
  - hhdm
  - virtual-memory
  - physical-memory
  - address-spaces
  - tlb
  - power-on-kstart
---

# Higher-half kernel, endereços canônicos e ChrisOS

## Escopo

O ChrisOS é linkado para executar em:

~~~text
0xffffffff80000000
~~~

Esse endereço não foi escolhido porque existe RAM física nesse valor.

Ele é um **endereço virtual** localizado na parte canônica superior do espaço de endereçamento x86-64.

O kernel de produção depende de várias camadas concordando:

~~~text
compiler
    gera code compatível com kernel code model

linker
    atribui virtual addresses altos

ELF
    registra esses endereços em PT_LOAD e e_entry

Limine
    aloca physical pages
    cria page tables
    mapeia as pages nos VMAs do ELF

CPU
    entra em long mode com paging ativo
    e executa kstart no higher-half
~~~

Se essas camadas divergirem, o kernel pode falhar já no primeiro instruction fetch ou no primeiro acesso a global data.

![Relações de endereço do higher-half kernel](../../assets/diagrams/higher-half-kernel-pt-br.svg)

## Physical e virtual address são identidades diferentes

Physical address identifica uma posição no espaço físico visível pelo processador/plataforma.

Virtual ou linear address é o endereço usado pelo software antes da tradução de páginas.

Com paging ativo:

~~~text
virtual address
      |
      v
page-table walk
      |
      v
physical address
~~~

Uma mesma physical page pode possuir múltiplos aliases virtuais.

O mesmo virtual address pode apontar para pages físicas diferentes sob CR3 diferentes.

Portanto o endereço produzido pelo linker não é automaticamente um physical address.

## Endereço linkado do kernel

kernel/metal/linker.ld inicia:

~~~text
. = 0xffffffff80000000;
__kernel_start = .;
~~~

Esse valor estabelece o VMA do kernel.

Functions, constants, mutable data e BSS recebem endereços acima dessa base conforme linker.ld.

O entry kstart também é um endereço virtual alto.

## Interpretação signed

Como uint64:

~~~text
0xffffffff80000000
=
18446744071562067968
~~~

Como int64 em complemento de dois:

~~~text
0xffffffff80000000
=
-2147483648
=
-2 GiB
~~~

Ele é exatamente o início dos 2 GiB superiores do espaço de 64 bits.

Isso se conecta diretamente ao GCC kernel code model.

## GCC kernel code model

O build de produção usa:

~~~text
-mcmodel=kernel
~~~

O GCC define esse modelo para kernels executando nos 2 GiB negativos do espaço x86-64.

O ChrisOS escolhe justamente a fronteira inferior desse intervalo:

~~~text
0xffffffff80000000
~~~

e cresce para endereços maiores.

Isso permite ao compiler utilizar formas de endereçamento adequadas a esse modelo.

## Code model não é paging mode

São conceitos diferentes:

~~~text
-mcmodel=kernel
    suposição do compiler sobre endereços

4-level paging
    estrutura de tradução da CPU

higher-half mapping
    conteúdo das page tables
~~~

O code model não cria mappings.

O linker não cria page tables.

Bootloader ou kernel MM criam as traduções.

## fno-pic e fno-pie

O build também usa:

~~~text
-fno-pic
-fno-pie
~~~

e gera ET_EXEC em endereço fixo.

O kernel atual não é um PIE que pode ser arbitrariamente relocacionado no boot.

Os virtual addresses linkados são os virtual addresses pretendidos em runtime.

## Virtual addresses em long mode

Em x86-64, nem todo padrão de 64 bits é um linear address válido.

A arquitetura implementa certo número de bits de virtual address.

As referências precisam estar em **canonical form**.

Os caminhos atuais do ChrisOS utilizam 4-level paging, portanto este capítulo trabalha com a forma canônica tradicional de 48 bits.

## Forma canônica de 48 bits

No modelo de 48 bits:

~~~text
bit 47
    |
    +-- se 0:
    |      bits 63:48 = 0
    |
    +-- se 1:
           bits 63:48 = 1
~~~

Ou seja, os bits superiores são sign-extension do bit 47.

## Lower canonical half

A metade inferior canônica é:

~~~text
0x0000000000000000
até
0x00007fffffffffff
~~~

O bit 47 é zero.

O user-space atual do ChrisOS ocupa apenas uma pequena região dessa metade.

## Upper canonical half

A região superior é:

~~~text
0xffff800000000000
até
0xffffffffffffffff
~~~

O bit 47 é um e os bits 63:48 são todos um.

A base do ChrisOS:

~~~text
0xffffffff80000000
~~~

está dentro dessa região.

## Canonical hole

Para 48 bits, os patterns entre:

~~~text
0x0000800000000000
e
0xffff7fffffffffff
~~~

não são canônicos.

Eles não devem ser tratados como simples addresses não mapeados.

Uma referência non-canonical falha em uma classe arquitetural diferente de um page-table miss comum.

## Caveat LA57

x86-64 também suporta five-level paging em CPUs com LA57.

Nesse caso o número de bits implementados cresce e o split canônico muda.

O ChrisOS atual discutido aqui usa **four-level paging**:

- Limine não recebe paging-mode request alternativo;
- ChrisVM v1 constrói explicitamente 4 níveis.

Portanto os cálculos deste capítulo são de 48-bit canonical addressing.

## Teste conceitual de canonicality

Para o modelo atual:

~~~text
top = address >> 48
sign = bit 47

canonical quando:
    sign == 0 e top == 0x0000
ou
    sign == 1 e top == 0xffff
~~~

Esse modelo é usado pelo checker da documentação.

## Decomposição de virtual address

Com 4-KiB pages:

~~~text
63                         48 47       39 38       30 29       21 20       12 11        0
+----------------------------+-----------+-----------+-----------+-----------+------------+
| sign extension canônica    | PML4 idx  | PDPT idx  | PD idx    | PT idx    | page off   |
+----------------------------+-----------+-----------+-----------+-----------+------------+
                              9 bits      9 bits      9 bits      9 bits      12 bits
~~~

Cada nível possui 512 entries porque cada índice possui 9 bits.

## Índices da base do kernel

Para:

~~~text
0xffffffff80000000
~~~

os índices reais são:

~~~text
PML4 = 511
PDPT = 510
PD   = 0
PT   = 0
offset = 0
~~~

Logo a base está no último PML4 slot e no penúltimo PDPT slot dentro dessa subtree.

## Janelas de 1 GiB

Cada PDPT entry cobre 1 GiB de virtual address space.

Assim:

~~~text
0xffffffff80000000
até
0xffffffffbfffffff
~~~

fica em:

~~~text
PDPT[510]
~~~

e:

~~~text
0xffffffffc0000000
até
0xffffffffffffffff
~~~

fica em:

~~~text
PDPT[511]
~~~

## Janelas virtuais atuais

O source possui:

~~~text
kernel base
0xffffffff80000000

MMIO window
0xffffffff90000000

MM self-test
0xffffffff91000000

região histórica citada pelo JIT
0xffffffff92000000

JIT executable base atual
0xffffffffc0000000
~~~

Os primeiros quatro pertencem a:

~~~text
PML4[511] / PDPT[510]
~~~

O JIT atual começa em:

~~~text
PML4[511] / PDPT[511]
~~~

## Inconsistência do comentário em jit.c

compiler/jit/jit.c atualmente comenta:

~~~text
0xffffffff80000000 (PDPT[2])
...
PDPT[3] is empty
~~~

Mas extraindo os bits arquiteturais do virtual address:

~~~text
0xffffffff80000000 -> PDPT[510]
0xffffffffc0000000 -> PDPT[511]
~~~

O comentário aparenta usar numbering relativo/local ou estar desatualizado.

Os constants executáveis não mudam por causa disso.

Esta documentação usa os índices arquiteturais reais.

## Split do PML4

mm_clone_kernel_space cria um PML4 e copia:

~~~text
i = 256 .. 511
~~~

da raiz atual.

Isso implementa um modelo convencional:

~~~text
PML4[0..255]
    lower half / user-specific

PML4[256..511]
    upper half / kernel
~~~

## Kernel compartilhado entre address spaces

Conceitualmente:

~~~text
kernel root
  lower half
  upper kernel half

new process root
  lower half initially empty/process-specific
  upper half copied from kernel root
~~~

O kernel continua virtualmente disponível mesmo quando CR3 troca para um process address space.

## Copiar PML4 entries não deep-copy page tables

A função copia os valores das entries superiores.

Ela não duplica toda a hierarchy abaixo delas.

Logo os novos address spaces apontam para as mesmas subtrees de kernel.

Modificações de mapping e synchronization precisam considerar esse compartilhamento.

## CR3

CR3 referencia fisicamente a top-level page table ativa.

Ao entrar em ChrisOS, essas page tables já foram construídas pelo Limine.

mm_init lê:

~~~text
mov %cr3
~~~

e guarda:

~~~text
mm_cr3_phys = cr3 & MM_ADDR_MASK
~~~

Ou seja, o kernel **adota** a root criada pelo bootloader.

## Adoption versus ownership

Após adotar CR3, o ChrisOS:

- percorre as tables;
- escreve novas entries;
- cria MMIO mappings;
- cria JIT mappings;
- aloca child tables;
- clona o upper half para process roots.

Isso já é estado operacional do kernel.

Porém a origem ainda é o bootloader.

## Problema de ownership atual

Como a hierarchy herdada continua ativa e é modificada pelo ChrisOS, as páginas correspondentes não podem ser tratadas simplesmente como memória descartável de boot.

O Boot Information chapter classifica esse estado como **adopted**.

A transição limpa exige nova root própria e switch de CR3.

## table_from_phys

Uma page-table entry contém physical address.

A CPU acessa essas tables através do mecanismo físico de paging.

Mas código C precisa de pointer virtual para editar bytes.

O ChrisOS usa:

~~~text
table_from_phys(phys)
    ->
bootinfo_phys_to_virt(phys)
~~~

ou seja, HHDM.

## HHDM

HHDM significa Higher Half Direct Map.

Limine fornece um offset.

Para physical memory elegível:

~~~text
virtual = physical + hhdm_offset
~~~

O offset é armazenado em bootinfo.

## Kernel mapping e HHDM não são a mesma coisa

O kernel ELF é mapeado de acordo com:

~~~text
0xffffffff80000000 + layout
~~~

Já HHDM mapeia physical memory usando:

~~~text
phys + runtime hhdm offset
~~~

As duas regiões existem por razões diferentes.

## Aliases virtuais

Uma physical page P que contém kernel data pode ser alcançada por:

~~~text
linked kernel VMA K
    -> P

HHDM(P)
    -> P
~~~

São dois pointers virtuais para os mesmos bytes físicos.

Isso é aliasing intencional.

## HHDM não é cast universal

bootinfo_phys_to_virt é simples, mas o contrato Limine determina quais classes físicas são garantidamente direct-mapped.

Os capítulos anteriores mostram que o source atual é permissivo demais em alguns caminhos de firmware/ACPI.

Portanto:

~~~text
phys + hhdm_offset
~~~

não deve ser tratado como mapeamento universal de qualquer endereço de dispositivo/firmware.

## Por que page tables usam HHDM

Quando PMM aloca uma page-table page:

~~~text
physical identity
    necessária para a PTE/CR3

virtual HHDM alias
    necessário para o código C zerar e escrever a table
~~~

Isso evita temporary mappings apenas para editar page tables.

## mm_virt_to_phys

Essa função percorre a hierarchy atual.

Para 4-KiB:

~~~text
PML4
  -> PDPT
     -> PD
        -> PT
           -> physical page
~~~

Ela também verifica large-page leaves.

## Large pages

O source reconhece PS em:

~~~text
PDPT
    1-GiB leaf

PD
    2-MiB leaf
~~~

e PT normal de 4 KiB.

Isso é relevante porque mappings fornecidos pelo bootloader não precisam ter todos a mesma granularidade.

## Estado antes de mm_init

Quando kstart recebe controle:

- long mode já está ativo;
- paging já está ativo;
- ELF higher-half já está mapped;
- HHDM já existe;
- framebuffer mapping existe;
- CR3 já aponta para uma hierarchy válida.

Caso contrário o próprio kstart não poderia executar no VMA alto.

## RIP já começa alto

ELF e_entry contém o virtual address de kstart.

Limine configura execução nesse endereço.

A CPU traduz instruction fetch via page tables existentes.

Portanto mm_init não cria o higher-half boot mapping.

Ele apenas descobre/adota o estado já ativo.

## Diferença para kernels que sobem paging sozinhos

Outro design possível seria:

~~~text
entry low
    |
build page tables
    |
enable paging
    |
jump high
~~~

Esse não é o caminho Limine atual do ChrisOS.

ChrisOS entra diretamente no kernel higher-half já paginado.

## Caminho de produção

~~~text
firmware
    |
Limine
    |
parse kernel.elf
    |
allocate physical backing
    |
map higher-half PT_LOADs
    |
map HHDM
    |
prepare long mode/paging
    |
CR3 ready
    |
RIP = kstart
    |
ChrisOS
~~~

## Framebuffer como exemplo

bootinfo recebe um framebuffer virtual pointer.

mm_init faz:

~~~text
fb_phys = mm_virt_to_phys(boot->fb_addr)
~~~

Isso demonstra concretamente:

~~~text
framebuffer virtual address
!=
framebuffer physical address
~~~

## Por que preservar fb_phys

Ao trocar page tables herdadas, um pointer virtual do bootloader pode deixar de ser válido.

Para recriar o mapping é necessário conhecer backing físico e geometry.

Por isso BootSnapshot futuro deve preservar ambas identidades.

## MMIO window

mm.c define:

~~~text
MMIO_WINDOW = 0xffffffff90000000
~~~

Essa região é usada para mappings explícitos de device memory.

Ela está no higher-half, mas não faz parte conceitualmente do kernel ELF nem do HHDM.

## MMIO explícito

map_mmio_page cria mapping controlado para physical MMIO.

Isso é melhor que:

~~~text
device_phys + hhdm_offset
~~~

porque device memory requer política deliberada de mapping e cacheability.

## Higher-half é namespace, não mapping único

O ChrisOS usa endereços altos para:

- kernel image;
- HHDM;
- MMIO;
- MM self-test;
- JIT;
- AP stacks;
- outras janelas futuras.

Higher-half descreve o espaço virtual, não uma única regra de tradução.

## JIT atual

JIT_VIRT_BASE é:

~~~text
0xffffffffc0000000
~~~

Esse address começa em PDPT[511].

O JIT usa:

~~~text
HHDM alias
    writable

JIT alias
    executable
~~~

para o mesmo physical backing.

## Dual mapping e W^X

Conceptualmente:

~~~text
physical code pages
      |
      +-- HHDM writable alias for emission
      |
      +-- JIT executable alias for execution
~~~

Isso permite separar write e execute pointers.

O JIT chapter trata synchronization e lifecycle.

## Collision management

Existem várias janelas fixas no upper address space.

Mesmo com espaço virtual enorme, constants dispersos podem se sobrepor.

Uma arquitetura madura deveria manter um mapa central de reservas virtuais.

## Checklist para novos high addresses

Ao criar nova janela:

- verificar canonical form;
- verificar alignment;
- calcular índices PML4/PDPT/PD/PT;
- verificar collisions;
- decidir U/S;
- decidir W/NX;
- decidir cache policy;
- decidir ownership;
- verificar relação com code model se symbols linkados forem envolvidos.

## Kernel/user split é política do OS

A arquitetura x86-64 não obriga:

~~~text
low = user
high = kernel
~~~

O ChrisOS escolhe esse modelo.

A protection real vem do U/S bit das page tables.

## High address não implica supervisor

Uma page alta ainda poderia ser marcada user-accessible.

Da mesma forma uma low page pode ser supervisor-only.

O numerical split simplifica design, mas não substitui permission bits.

## NX

Higher-half não significa executable.

NX decide instruction fetch.

Current source usa MM_NX em mappings que não devem executar.

O executable image e o MM precisam manter políticas coerentes.

## CR0.WP

A proteção de read-only pages para supervisor também depende de CR0.WP.

O modelo completo inclui:

- R/W page bit;
- U/S;
- NX;
- CR0.WP;
- ELF permissions.

Higher-half por si só não fornece write protection.

## Canonical não significa mapped

Um address pode ser canônico e ainda falhar porque:

- PML4 absent;
- PDPT absent;
- PD absent;
- PT absent;
- permission denied;
- NX;
- reserved bits.

Canonicality só valida o formato arquitetural do linear address.

## Non-canonical versus page fault

Um pointer alto inválido pode ser:

~~~text
non-canonical

canonical but unmapped

canonical and mapped but forbidden
~~~

Diagnóstico correto depende de distinguir essas classes.

## Higher-half e relocations

Compiler gera relocations com assumptions de code model.

Linker resolve symbols perto de:

~~~text
0xffffffff80000000
~~~

Em PC-relative:

~~~text
S + A - P
~~~

a diferença pode continuar pequena mesmo com S e P numericamente altos.

## Absolute relocations

Relocations absolutas podem carregar o full 64-bit canonical address.

Um native linker não pode truncar endereços apenas porque testes low-address funcionaram.

Higher-half expõe rapidamente esse tipo de bug.

## Base -2 GiB

Escolher:

~~~text
0xffffffff80000000
~~~

é escolher exatamente:

~~~text
-2^31
~~~

em signed 64-bit.

Isso é compatível com o region model documentado pelo GCC para -mcmodel=kernel.

## Linker symbols são virtuais

__kernel_start, __kernel_end e __stack_top recebem high virtual addresses.

Eles não indicam diretamente physical backing.

Se PMM precisa saber quais physical pages estão ocupadas pelo kernel, deve consultar bootloader memory information.

## PMM atual

pmm_init apenas imprime:

~~~text
pmm kernel_virt __kernel_start..__kernel_end
~~~

como diagnóstico.

Para physical reservation ele usa o Limine memory map.

LIMINE_MEMMAP_EXECUTABLE_AND_MODULES é marcado used.

Essa separação é conceitualmente correta.

## Loop redundante de executable reservation

O source atual reserva EXECUTABLE_AND_MODULES dentro do loop de types reservados e depois percorre novamente as mesmas entries marcando-as used.

Como pmm_reserve_page testa se a bitmap bit já está used, isso não double-count pages.

É redundância de código, não mapeamento extra.

## PMM trabalha em physical identity

Allocator retorna physical pages.

Quando precisa acessar bytes:

~~~text
bootinfo_phys_to_virt(phys)
~~~

produz HHDM alias.

A identidade allocator continua sendo physical.

## Process page-table root

mm_clone_kernel_space:

1. PMM aloca uma physical page;
2. HHDM fornece pointer C para essa page;
3. PML4[256..511] é copiado;
4. physical address da root pode ser carregado em CR3.

Três identidades coexistem:

~~~text
CR3 physical address
HHDM editing pointer
virtual mappings described inside the table
~~~

## CR3 é physical

mm_switch recebe:

~~~text
cr3_phys
~~~

e escreve diretamente em CR3.

Não recebe HHDM pointer.

Essa nomenclatura ajuda a evitar confusão de address domains.

## Acesso C à root

Para editar CR3 root:

~~~text
table_from_phys(mm_cr3_phys)
~~~

retorna o HHDM virtual alias.

Assim:

~~~text
CPU page walker
    physical P

C code
    HHDM(P)
~~~

## Stack inicial

Limine entrega stack válida no entry.

linker.ld também reserva 1 MiB e define __stack_top.

gdt.c usa:

~~~text
tss.rsp0 = __stack_top
~~~

mas isso não prova que o BSP mudou imediatamente o RSP corrente para essa stack.

Esse lifetime permanece parte da transição de ownership de boot.

## AP stacks

AP startup aloca stacks próprias.

Isso adiciona outras high virtual regions fora do main ELF image.

O SMP chapter documenta o handoff completo.

## HHDM offset é runtime state

A kernel base é fixa no linker.

HHDM offset vem do Limine:

~~~text
info.hhdm_offset = hhdm->offset
~~~

Portanto subsystems não devem hard-code uma direct-map base sem necessidade.

## Benefício do HHDM runtime

Isso desacopla:

~~~text
kernel layout
    fixed by link

direct map
    supplied by boot environment
~~~

e oferece uma forma uniforme de acessar ordinary physical RAM.

## BootSnapshot futuro

Um BootSnapshot completo deve preservar:

- HHDM offset;
- direct-map validity/ranges;
- kernel virtual range;
- physical backing/provenance;
- framebuffer physical/virtual;
- initial CR3 provenance;
- paging mode.

Assim ownership de address-space deixa de ficar implícito.

## Transição para page tables próprias

Uma evolução limpa é:

1. normalizar boot data;
2. inicializar PMM;
3. alocar nova PML4;
4. mapear ELF kernel;
5. construir HHDM desejado;
6. mapear framebuffer;
7. mapear MMIO necessário;
8. garantir stack própria;
9. trocar CR3;
10. validar translations;
11. liberar hierarchy herdada quando seguro.

Esse é o fechamento real do ownership de higher-half.

## Executing RIP durante CR3 switch

Antes de escrever novo CR3, a nova hierarchy precisa mapear a página que contém o instruction pointer atual.

Caso contrário a CPU não consegue buscar a próxima instrução.

Como RIP já está higher-half, o mapping higher-half deve existir antes do switch.

## RSP durante o switch

A stack atual também precisa permanecer válida.

Um design seguro precisa garantir que RSP aponte para memória presente na nova hierarchy ou realizar uma transição controlada para kernel-owned stack.

## GDT, IDT, TSS e globals

Outros live pointers precisam continuar válidos:

- GDTR base;
- IDTR base;
- handlers;
- TSS references;
- kernel globals;
- serial state;
- MM state.

Trocar CR3 é uma operação sobre todo o address-space runtime, não apenas code pages.

## SMP complica a troca

Depois de APs estarem ativos, vários CPUs podem usar CR3/TLB state.

Uma transição de root então exige coordination.

Por isso a troca para page tables próprias é mais simples antes de liberar SMP geral.

## TLB

Escrever CR3 altera translation context e invalida TLB state conforme regras da arquitetura.

O ChrisOS já possui runtime shootdown para mapping changes.

Boot-time root replacement pode ser mais simples se ocorrer antes da concorrência normal.

## Global pages

x86-64 possui global-page mechanisms.

Eles podem otimizar shared kernel mappings entre CR3 switches.

Este capítulo não assume que o ChrisOS já tenha uma política completa de global pages sem evidência explícita no source.

## Process CR3 mantém upper kernel half

Ao rodar process address spaces, copiar upper-half PML4 entries mantém kernel code/data reachable.

Isso permite transições de user para kernel sem necessariamente trocar para uma root totalmente separada a cada syscall/interrupt.

## User accessibility precisa ser auditada

Shared high entries devem continuar supervisor-only.

O número alto não impõe essa proteção.

U/S bits ao longo do walk são a autoridade.

## Vantagens do higher-half

Higher-half oferece:

- separação visual/estrutural de user e kernel;
- virtual addresses estáveis do kernel;
- mappings compartilháveis entre process roots;
- low half disponível ao user-space;
- namespace grande para HHDM/MMIO/JIT;
- menor chance de null/low pointer coincidir diretamente com kernel text.

Essas são vantagens de layout, não garantias de segurança automáticas.

## Higher-half não é ASLR

O kernel base atual é fixo.

Qualquer código conhece:

~~~text
0xffffffff80000000
~~~

como base de link.

Isso não esconde endereço do kernel.

## KASLR não está implementado

Com fixed ET_EXEC, fno-pie e base fixa:

~~~text
KASLR
    não faz parte do design atual
~~~

Implementá-lo exige outra estratégia de relocation/loading.

## Canonical arithmetic da base

A base possui:

~~~text
bit 47 = 1
bits 63:48 = 0xffff
~~~

Logo é canonical no modelo atual.

Como signed:

~~~text
-2147483648
~~~

O checker fixa essas invariantes.

## Decomposição das janelas

| Virtual address | PML4 | PDPT | PD | Uso |
|---|---:|---:|---:|---|
| 0xffffffff80000000 | 511 | 510 | 0 | kernel base |
| 0xffffffff90000000 | 511 | 510 | 128 | MMIO |
| 0xffffffff91000000 | 511 | 510 | 136 | MM self-test |
| 0xffffffff92000000 | 511 | 510 | 144 | região histórica JIT |
| 0xffffffffc0000000 | 511 | 511 | 0 | JIT atual |

O checker reproduz a tabela mecanicamente.

## PD index do MMIO

A diferença entre base e MMIO é:

~~~text
0x10000000
=
256 MiB
~~~

Cada PD entry cobre 2 MiB.

Logo:

~~~text
256 / 2
=
128 entries
~~~

por isso MMIO_WINDOW cai em PD index 128.

## Boundary do JIT

A diferença:

~~~text
0xffffffffc0000000
-
0xffffffff80000000
=
1 GiB
~~~

Logo o PDPT index avança de 510 para 511.

## ChrisVM v1 não suporta o kernel real

O boot protocol v1 do ChrisVM cria identity mappings para guest RAM baixa.

Ele rejeita ELF com:

~~~text
p_vaddr = 0xffffffff80000000
~~~

e documenta:

~~~text
higher-half ELF is outside boot protocol v1
~~~

Isso é capability gap do boot protocol.

Não é bug específico de kstart.

## Não basta setar RIP alto

Para executar ChrisOS, ChrisVM precisa também:

- mapear PT_LOADs higher-half;
- publicar boot info;
- fornecer HHDM ou abstraction equivalente;
- mapear framebuffer;
- montar page tables compatíveis;
- estabelecer CR3 correto.

Só alterar RIP produziria fetch fault.

## Meta do ChrisVM v2

O próprio repositório define que protocol v2 precisa:

~~~text
load higher-half ELF
publish explicit boot info
preserve architectural state
~~~

A meta é o guest kernel não precisar saber se backend é ChrisCPU ou ChrisHV.

## ChrisLd e high p_vaddr

ChrisLd consegue receber:

~~~text
0xffffffff80000000
~~~

como load_addr e emitir esse p_vaddr.

Isso prova apenas que ele consegue escrever um VMA alto no ELF.

Não prova:

- kernel code model completo;
- linker.ld parity;
- Limine section;
- synthetic symbols;
- stack;
- boot.

## KCC também precisa suportar higher-half

Self-host não é apenas problema do linker.

KCC precisa gerar addressing forms e relocations compatíveis com high addresses.

ChrisO precisa preservar metadata.

ChrisLd precisa resolver corretamente.

Bootloader precisa mapear.

Higher-half é um problema cross-toolchain.

## Testes diferenciais

Um gate útil deve compilar/linkar código que referencia:

- functions próximas;
- global data;
- linker symbols altos;
- cross-section references;
- 64-bit absolute values;
- PC-relative references.

Depois deve inspecionar o ELF produzido.

## Checker reproduzível

scripts/check_higher_half_examples.py valida:

1. canonicality de 48 bits;
2. lower/upper boundaries;
3. base signed = -2 GiB;
4. índices da base;
5. índices de MMIO/test/JIT;
6. transition PDPT[510] -> PDPT[511];
7. linker base;
8. -mcmodel=kernel;
9. -fno-pic/-fno-pie;
10. adoption de inherited CR3;
11. uso de HHDM para page tables;
12. copy PML4[256..511];
13. ChrisVM v1 higher-half rejection;
14. mismatch do comentário PDPT[2]/PDPT[3].

É um checker matemático e de source contracts.

Não prova todas as page tables reais criadas por Limine em cada máquina.

## Findings atuais

No commit revisado:

~~~text
kernel base
    0xffffffff80000000

compiler
    -mcmodel=kernel
    -fno-pic
    -fno-pie

initial CR3
    herdado do Limine

page-table editing
    via HHDM

process roots
    copy PML4[256..511]

MMIO
    0xffffffff90000000

JIT
    0xffffffffc0000000

ChrisVM v1
    rejeita production higher-half ELF
~~~

A arquitetura funciona, mas ownership de paging ainda depende da hierarchy inicial do bootloader.

## Limite de validação

Capítulo reconciliado com:

~~~text
ChrisOS main
da3df29cb397932c43d32373871fb9380e688ade
~~~

A teoria externa usa AMD64 architecture rules e GCC x86 code-model documentation.

Execute:

~~~text
python scripts/check_higher_half_examples.py --source .source
~~~

## Gatilhos de revisão

Revisar quando:

- kernel base mudar;
- code model mudar;
- PIE/KASLR entrar;
- paging-mode request for adicionado;
- LA57 for habilitado;
- HHDM mudar;
- CR3 herdado for substituído;
- mm_clone_kernel_space mudar;
- MMIO/JIT/AP-stack windows mudarem;
- comentário de jit.c for corrigido;
- ChrisVM v2 suportar higher-half;
- ChrisCPU bootar production kernel;
- KCC/ChrisLd produzirem kernel higher-half bootável.

## Referências primárias

- AMD64 Architecture Programmer's Manual.
- GCC x86 Options, kernel code model.
- Limine boot protocol.
- Sources ChrisOS listados no front matter.
