---
id: linker-script
lang: pt-br
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/linker.ld
  - kernel/metal/start.c
  - kernel/metal/pmm.c
  - kernel/metal/mm.c
  - kernel/metal/bootinfo.c
  - makefile
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chrisld.h
  - compiler/chrisld/chriso.h
  - docs/CHRISLD_STATUS.md
  - docs/CURRENT_SELFHOST_AUDIT.md
symbols:
  - kstart
  - __kernel_start
  - __kernel_end
  - __stack_bottom
  - __stack_top
depends_on:
  - elf-linking
related:
  - higher-half-kernel
  - power-on-kstart
  - limine
  - boot-information
  - physical-memory
  - virtual-memory
  - chrisld
---

# GNU ld linker scripts e o layout do kernel ChrisOS

## Escopo

Um linker script é uma descrição executável de como vários objetos compilados separadamente se transformam em um único espaço de endereçamento.

Compiler e assembler geram code, data, symbols e relocations. Eles não determinam o mapa completo do kernel. O linker decide:

- onde o kernel começa;
- onde cada classe de input section será posicionada;
- como serão criados os ELF program headers;
- quais permissions cada segmento terá;
- quais metadados precisam sobreviver a garbage collection;
- onde existe memória zero-filled sem bytes equivalentes no arquivo;
- quais limites devem virar symbols visíveis ao kernel.

O linker script de produção atual é:

~~~text
OUTPUT_FORMAT(elf64-x86-64)
OUTPUT_ARCH(i386:x86-64)
ENTRY(kstart)

PHDRS {
    requests PT_LOAD FLAGS(6);
    text     PT_LOAD FLAGS(5);
    data     PT_LOAD FLAGS(6);
}

SECTIONS {
    . = 0xffffffff80000000;
    __kernel_start = .;

    .limine_requests : ALIGN(4K) {
        KEEP(*(.limine_requests_start))
        KEEP(*(.limine_requests))
        KEEP(*(.limine_requests_end))
    } :requests

    .text : ALIGN(4K) {
        *(.text .text.*)
    } :text

    .rodata : ALIGN(4K) {
        *(.rodata .rodata.*)
    } :text

    .data : ALIGN(4K) {
        *(.data .data.*)
    } :data

    .bss (NOLOAD) : ALIGN(4K) {
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(16);
        __stack_bottom = .;
        . += 1024K;
        __stack_top = .;
        . = ALIGN(4K);
        __kernel_end = .;
    } :data

    /DISCARD/ : {
        *(.eh_frame*)
        *(.note*)
        *(.comment*)
    }
}
~~~

Apesar de curto, esse arquivo define o layout virtual de produção, o modelo de proteção dos segmentos, o placement dos requests Limine, a semântica de BSS, a reserva da stack e os symbols de fronteira.

![Avaliação do linker script do ChrisOS](../../assets/diagrams/linker-script-pt-br.svg)

## Todo link utiliza um linker script

GNU ld sempre opera sob alguma política de linker script.

Se nenhum script for fornecido, existe um default interno.

O ChrisOS não usa esse default.

O makefile passa:

~~~text
-T kernel/metal/linker.ld
~~~

portanto o layout é controlado pelo próprio projeto.

Isso é essencial para um kernel, porque um layout genérico não saberia nada sobre:

- higher-half;
- Limine request sections;
- stack do kernel;
- symbols __kernel_*;
- segments RX/RW desejados.

## Linker script é uma linguagem

GNU ld utiliza uma linguagem com comandos, assignments e expressions.

O ChrisOS usa:

- OUTPUT_FORMAT;
- OUTPUT_ARCH;
- ENTRY;
- PHDRS;
- SECTIONS;
- wildcards;
- location counter;
- symbol assignment;
- ALIGN;
- KEEP;
- NOLOAD;
- /DISCARD/.

O arquivo deve ser lido como um programa de construção de espaço de endereçamento.

## Input sections

Objetos de compiler/assembler carregam input sections.

Exemplos:

~~~text
.text
.text.kstart
.text.serial_init
.rodata
.rodata.str1.1
.data
.data.some_global
.bss
.bss.some_buffer
~~~

Cada objeto pode contribuir com várias sections.

## Output sections

O linker script cria output sections.

Exemplo:

~~~text
.text : ALIGN(4K) {
    *(.text .text.*)
} :text
~~~

Isso cria uma output section chamada .text a partir de inputs que correspondem aos patterns.

Output section possui:

- endereço;
- tamanho;
- alignment;
- conteúdo;
- attributes;
- program-header assignment.

## Wildcards

A expressão:

~~~text
*(.text .text.*)
~~~

significa:

~~~text
em todos os input files:
    coletar .text
    coletar .text.*
~~~

O primeiro star seleciona qualquer arquivo.

Os patterns entre parênteses selecionam sections.

## Por que .text.* importa

Compilers podem produzir sections por função:

~~~text
.text.kstart
.text.foo
.text.bar
~~~

O pattern .text.* garante que o linker não perca essas contribuições.

A mesma lógica aparece em rodata, data e BSS.

## Ordem dos objetos

O linker script controla a ordem macro.

O makefile e o linker influenciam a ordem dos inputs dentro de cada categoria.

Alterar a ordem dos objetos pode alterar:

- addresses;
- relocation displacements;
- padding;
- hash do kernel.

Portanto linker.ld e object list compõem juntos o layout final.

## OUTPUT_FORMAT

O script inicia com:

~~~text
OUTPUT_FORMAT(elf64-x86-64)
~~~

Isso seleciona o formato de saída GNU BFD.

O container final é ELF x86-64.

OUTPUT_FORMAT não gera machine code.

O compiler/assembler precisam produzir objetos compatíveis.

## OUTPUT_ARCH

A linha:

~~~text
OUTPUT_ARCH(i386:x86-64)
~~~

seleciona x86-64 na nomenclatura GNU BFD.

O prefixo i386 pertence à taxonomia BFD e não transforma o kernel em 32 bits.

## ENTRY

A linha:

~~~text
ENTRY(kstart)
~~~

faz kstart definir o executable entry.

A cadeia é:

~~~text
kstart symbol
    |
symbol resolution
    |
virtual address final
    |
ELF e_entry
    |
handoff do Limine
~~~

ENTRY não executa a função.

Ele define metadata ELF.

## Entry precisa estar em memória executável

O script coleta funções em .text e associa .text ao PHDR RX.

Portanto kstart deve terminar em PT_LOAD executável.

Essa propriedade deve ser validada no ELF final.

## PHDRS

O ChrisOS declara explicitamente:

~~~text
PHDRS {
    requests PT_LOAD FLAGS(6);
    text     PT_LOAD FLAGS(5);
    data     PT_LOAD FLAGS(6);
}
~~~

PHDRS controla o program-header table ELF.

Os nomes requests, text e data são nomes internos do linker script.

Eles são depois referenciados por:

~~~text
:requests
:text
:data
~~~

## Nomes de PHDR não são symbols

requests, text e data não viram globals do kernel.

São labels do script para ligar output sections a segments ELF.

## Por que controlar PHDRS explicitamente

GNU ld pode gerar program headers automaticamente.

O ChrisOS não deixa o contrato de boot implícito.

Ele fixa três classes com permissions conhecidas.

Isso torna o ELF layout parte da arquitetura versionada em source.

## PT_LOAD

Os três PHDRS são PT_LOAD.

Cada um participa da imagem runtime:

~~~text
requests
    metadata de boot

text
    código + constants

data
    data + BSS + stack
~~~

## FLAGS

ELF define:

~~~text
PF_X = 1
PF_W = 2
PF_R = 4
~~~

Então:

~~~text
FLAGS(5) = R | X
FLAGS(6) = R | W
~~~

A política é:

| PHDR | Flags | Conteúdo |
|---|---|---|
| requests | RW | requests Limine |
| text | RX | code + rodata |
| data | RW | data + BSS + stack |

Não existe PT_LOAD W+X declarado.

## W^X começa no link

W^X não é apenas uma decisão do MM.

As flags ELF nascem durante a linkedição.

O bootloader utiliza essas flags para construir o ambiente inicial.

Alterar linker.ld pode alterar a security posture antes de qualquer função C executar.

## SECTIONS

SECTIONS descreve o layout.

O início é:

~~~text
. = 0xffffffff80000000;
__kernel_start = .;
~~~

Dot é o location counter.

## Location counter

O symbol especial:

~~~text
.
~~~

representa a posição atual no output.

O ChrisOS faz:

~~~text
. = 0xffffffff80000000;
~~~

para definir a base.

Depois:

~~~text
__kernel_start = .;
~~~

captura essa posição.

Mais tarde:

~~~text
. = ALIGN(16);
~~~

alinha a posição.

E:

~~~text
. += 1024K;
~~~

reserva address space.

## Alterar dot altera endereços reais

O comando:

~~~text
. += 1024K;
~~~

não é apenas aritmética.

Ele move a posição do output em 1 MiB.

Todos os symbols e sections posteriores passam a ter endereços maiores.

## Base higher-half

O valor:

~~~text
0xffffffff80000000
~~~

é o VMA inicial do kernel.

Não é o physical address do kernel em RAM.

Limine escolhe physical backing e cria mappings compatíveis.

## __kernel_start

A assignment:

~~~text
__kernel_start = .;
~~~

cria um linker-defined symbol com o valor do location counter naquele instante.

Ela não aloca storage.

## Linker symbol como endereço

Um linker symbol de boundary deve ser tratado conceitualmente como endereço.

Não como uma variável normal que contém outro endereço.

Essa diferença é importante quando C referencia __kernel_start, __kernel_end e stack symbols.

## ALIGN

As principais output sections usam 4 KiB.

Para power-of-two A:

~~~text
align_up(x, A)
=
(x + A - 1) & ~(A - 1)
~~~

Exemplos:

~~~text
ALIGN_4K(0x1000) = 0x1000
ALIGN_4K(0x1001) = 0x2000
ALIGN_4K(0x1fff) = 0x2000
~~~

O checker valida esses cálculos.

## ALIGN não é sempre assignment

ALIGN calcula um endereço alinhado.

Quando usado como expressão de início de uma output section, determina seu placement.

Quando usado em:

~~~text
. = ALIGN(16);
~~~

o resultado é atribuído ao location counter.

É o contexto que altera o layout.

## Por que alinhar a página

Requests, text, rodata, data e BSS começam em boundary de 4 KiB.

Isso facilita:

- permissions;
- page tables;
- memory accounting;
- ELF inspection;
- remapping futuro.

Pode também criar padding.

## Output section Limine

O primeiro bloco é:

~~~text
.limine_requests : ALIGN(4K) {
    KEEP(*(.limine_requests_start))
    KEEP(*(.limine_requests))
    KEEP(*(.limine_requests_end))
} :requests
~~~

Essa região contém metadata observada pelo bootloader.

## Pipeline do request

A cadeia completa é:

~~~text
section attribute no bootinfo.c
        |
special input section
        |
wildcard no linker
        |
KEEP
        |
output .limine_requests
        |
PHDR requests RW
        |
scanner Limine
~~~

Cada estágio é necessário.

## KEEP

KEEP protege input sections de linker garbage collection.

Requests podem não ter referências normais no graph de symbols.

Mesmo assim o Limine precisa encontrá-los.

KEEP representa explicitamente essa dependência externa.

## Uso externo e garbage collection

O linker não consegue inferir que outro programa examinará bytes da imagem.

Sem root explícito, metadata aparentemente não referenciada pode ser candidata à remoção em builds com section GC.

Esse padrão também aparece em:

- initcall tables;
- interrupt vectors;
- firmware descriptors;
- registration arrays.

## Ordem dos markers

O ChrisOS coloca:

~~~text
start marker
request objects
end marker
~~~

A ordem é parte do contrato de request discovery.

Um ChrisLd futuro precisa preservar o ordering, não apenas os bytes.

## :requests

O suffix:

~~~text
:requests
~~~

atribui a output section ao PHDR requests.

A section chama .limine_requests.

O PHDR chama requests.

São conceitos diferentes.

## .text

A regra:

~~~text
.text : ALIGN(4K) {
    *(.text .text.*)
} :text
~~~

coleta executable code em output section page-aligned e envia ao segmento RX.

## .rodata

A regra:

~~~text
.rodata : ALIGN(4K) {
    *(.rodata .rodata.*)
} :text
~~~

cria output section distinta, mas compartilha o PHDR text.

Portanto output section e segment não são sinônimos.

## Consequência para rodata

Constants read-only ficam no mesmo mapping RX do code.

Não são graváveis, porém são executable no nível de page permission.

Uma evolução pode criar PHDR apenas R para rodata.

O source atual não faz isso.

## .data

A regra:

~~~text
.data : ALIGN(4K) {
    *(.data .data.*)
} :data
~~~

coleta globals mutáveis inicializados.

Esses bytes existem no kernel.elf e são mapeados RW.

## .bss

A definição começa:

~~~text
.bss (NOLOAD) : ALIGN(4K) {
    *(.bss .bss.*)
    *(COMMON)
~~~

BSS ocupa runtime memory e pertence ao data PHDR, mas não exige payload equivalente no arquivo.

## NOLOAD

NOLOAD indica que a output section não é carregada como initialized file content.

No ELF, a consequência prática se relaciona ao fato de a memória runtime poder ser maior que o file-backed region.

~~~text
p_memsz > p_filesz
~~~

é o padrão fundamental de BSS/zero-fill.

## NOLOAD não significa inexistente

BSS contém endereços reais e memória real.

Inclui:

- zero globals;
- COMMON;
- stack reservation;
- padding.

ChrisLd precisa contabilizar o memsz mesmo sem emitir bytes correspondentes.

## COMMON

~~~text
*(COMMON)
~~~

coloca common symbols na política BSS.

Isso dá comportamento explícito para tentative definitions que apareçam nesse formato de objeto.

## Alinhamento da stack

Dentro de BSS:

~~~text
. = ALIGN(16);
__stack_bottom = .;
~~~

A boundary é ajustada para 16 bytes.

Isso é coerente com o System V AMD64 ABI usado pelo kernel.

## Reserva da stack

O script executa:

~~~text
. += 1024K;
~~~

O próprio linker aumenta o runtime extent em um MiB.

Essa memória não veio de input BSS.

É memória sintética criada pela política de layout.

## Symbols da stack

A sequência:

~~~text
__stack_bottom = .;
. += 1024K;
__stack_top = .;
~~~

garante:

~~~text
__stack_top - __stack_bottom
=
1048576 bytes
~~~

A stack x86-64 cresce para endereços menores a partir de uma região alta.

## Reservar stack não altera RSP

O linker cria espaço e symbols.

Ele não executa:

~~~text
mov rsp, ...
~~~

O bootloader fornece uma stack inicial.

A transição para stack própria é responsabilidade do código de boot/runtime.

## Final alignment

Depois da stack:

~~~text
. = ALIGN(4K);
__kernel_end = .;
~~~

__kernel_end fica page-aligned.

## Significado de __kernel_end

Ele representa o fim de:

- protocol metadata;
- code;
- rodata;
- data;
- BSS;
- stack reservation;
- padding final.

Não representa apenas o último byte armazenado no arquivo ELF.

## File size versus runtime extent

É possível:

~~~text
runtime kernel memory
>
kernel.elf file bytes
~~~

porque BSS e stack reservation consomem memsz sem payload equivalente.

PMM não deve inferir o tamanho ocupado pelo kernel apenas pelo file size.

## /DISCARD/

O script remove:

~~~text
.eh_frame*
.note*
.comment*
~~~

por meio de /DISCARD/.

Essa é uma exclusão explícita.

## .eh_frame

Normalmente contém unwind metadata.

O kernel atual não depende de runtime de unwind hospedado.

Se um kernel unwinder futuro utilizar esse padrão, essa política deverá mudar.

## .note

ELF notes podem conter build IDs e properties.

O wildcard atual remove toda .note*.

É uma política ampla.

Uma futura feature pode exigir retenção seletiva.

## .comment

Normalmente contém identificação do compiler.

Não é necessária para execução.

## /DISCARD/ versus GC

~~~text
/DISCARD/
    exclusão explícita

section GC
    remoção por reachability

KEEP
    proteção contra GC
~~~

São mecanismos distintos.

## VMA

VMA é Virtual Memory Address.

O kernel é construído para executar no higher-half começando em:

~~~text
0xffffffff80000000
~~~

## LMA

LMA é Load Memory Address.

VMA e LMA podem divergir.

Em firmware/embedded é comum:

~~~text
.data stored in ROM
.data runs in RAM
~~~

A ROM é LMA e RAM é VMA.

## AT e AT>

GNU ld permite:

~~~text
AT(address)
AT>region
~~~

para controlar LMA.

O ChrisOS atual não usa AT nem AT>.

Portanto não existe hoje um ROM/RAM split explícito definido pelo linker script.

## LMA não é physical placement do Limine

A posição física escolhida pelo Limine é outra camada.

~~~text
linker:
    virtual layout

ELF:
    load description

Limine:
    physical allocation + mappings
~~~

Não confundir esses conceitos.

## MEMORY

GNU ld suporta:

~~~text
MEMORY {
    ROM (...) : ORIGIN = ..., LENGTH = ...
    RAM (...) : ORIGIN = ..., LENGTH = ...
}
~~~

O ChrisOS não usa MEMORY.

O modelo atual não precisa declarar fixed physical regions ao linker.

## ADDR, SIZEOF e LOADADDR

GNU ld pode consultar:

~~~text
ADDR(.text)
SIZEOF(.text)
LOADADDR(.data)
~~~

O linker.ld atual não usa esses recursos.

LOADADDR torna-se especialmente útil quando LMA difere de VMA.

## PROVIDE

PROVIDE pode criar default symbols de forma condicional.

O ChrisOS utiliza assignments diretos.

Logo __kernel_start/end e stack symbols são sempre controlados pelo script.

## ASSERT

GNU ld suporta assertions de link.

O script atual não contém ASSERT.

Poderia futuramente verificar:

- stack size;
- section alignment;
- request presence;
- size ceilings;
- canonical address assumptions.

## SORT

O ChrisOS não usa SORT.

O ordering crítico dos requests é expresso listando os categories em sequência.

## SUBALIGN

Não é usado.

Input-section alignment normal permanece, enquanto output sections principais recebem 4 KiB.

## ALIGN_WITH_INPUT

Também não é usado.

É mais relevante quando VMA/LMA possuem delta explícito.

## FILL

Nenhum custom fill pattern é definido.

Kernel code não deve depender do valor de padding sem política explícita.

## PHDR assignment explícito

Cada major allocated output section termina com:

~~~text
:requests
:text
:data
~~~

Isso evita depender de inheritance implícita e facilita auditoria.

## Por que três PHDRS

A divisão é:

~~~text
boot protocol    RW
code/constants   RX
mutable state    RW
~~~

Isso fornece separação de protection classes.

## Por que requests não compartilham data

Seria possível colocar requests RW no data segment.

O ChrisOS usa segment separado para obter:

- identidade clara;
- placement previsível;
- inspeção simples;
- verificação isolada;
- menor acoplamento com mutable state normal.

## Relação com segurança

linker.ld participa diretamente de:

- W^X;
- zero initialization;
- section retention;
- section exclusion;
- executable boundaries;
- stack memory extent.

É parte do security model do kernel.

## Relação com PMM/MM

linker.ld conhece o virtual extent.

Limine conhece physical backing e memory map.

PMM/MM precisam reconciliar essas duas visões.

Isso conecta linker symbols com BootSnapshot e future page-table ownership.

## Relação com higher-half

A sequência é:

~~~text
linker.ld:
    gera endereços virtuais altos

Limine:
    cria mappings para eles

ELF e_entry:
    aponta para kstart alto

CPU:
    executa kstart
~~~

Se layout e boot mappings divergirem, o kernel falha antes de inicialização normal.

## Compiler code model

O makefile usa:

~~~text
-mcmodel=kernel
-fno-pic
-fno-pie
~~~

e linker.ld fixa a base higher-half.

Compiler code model e linker placement são decisões coordenadas.

## Symbols sintéticos participam de relocations

Se C referencia __kernel_end, o objeto pode possuir relocation para esse symbol.

O linker resolve a referência mesmo sem um input object definir o symbol.

Por isso ChrisLd precisa de symbols criados pelo layout.

## ChrisLd atual

O ChrisLd não interpreta kernel/metal/linker.ld.

A policy está hardcoded em C.

Hoje ele:

- packa text;
- coloca rodata depois de text;
- gera RX PT_LOAD;
- opcionalmente gera RW data/BSS;
- resolve relocations;
- encontra kstart/main;
- valida ELF básico.

Isso não é ainda equivalência com produção.

## Duas estratégias para ChrisLd

### Parser de linker-script

Implementar subset de GNU ld:

- OUTPUT_FORMAT;
- OUTPUT_ARCH;
- ENTRY;
- PHDRS;
- SECTIONS;
- wildcard;
- dot;
- symbol assignment;
- ALIGN;
- KEEP;
- NOLOAD;
- /DISCARD/.

Vantagem principal: uma única fonte de verdade.

### Policy específica do kernel

Codificar o layout do ChrisOS diretamente em structures do ChrisLd.

Mais simples para bootstrap.

Porém duplica policy e pode divergir.

No longo prazo, duas definições silenciosamente diferentes de kernel layout são um risco.

## Paridade mínima necessária

Um ChrisLd capaz de produzir o kernel precisa reproduzir ao menos:

~~~text
ELF64 x86-64
ENTRY(kstart)

higher-half base
__kernel_start

Limine special sections
start/body/end ordering
retention semantics
requests RW PT_LOAD

text/text.*
RX protection

rodata/rodata.*
protection policy

data/data.*
RW protection

BSS/bss.*
zero-fill
COMMON semantics if needed

ALIGN(16)
1 MiB synthetic stack extent
__stack_bottom
__stack_top

ALIGN(4K)
__kernel_end

discard/ignore unwanted metadata
~~~

## ChrisO ainda não representa Limine requests

ChrisO v2 possui:

~~~text
TEXT
RODATA
DATA
BSS
~~~

Não possui class dedicada para Limine request sections.

Portanto a evolução precisa atravessar todo o toolchain.

## Pipeline de section attribute nativo

Para preservar Limine:

~~~text
source attribute
    |
KCC
    |
ChrisO section identity
    |
ChrisLd grouping
    |
requests PT_LOAD
~~~

Qualquer perda de informação quebra o protocolo.

## KEEP no toolchain nativo

Como ChrisLd ainda não faz dead-section GC, ele não remove inputs por reachability.

Mesmo assim a architecture deve representar retenção.

Caso GC seja implementado depois, requests precisam permanecer roots.

## BSS sintético

ChrisLd já contabiliza BSS originado dos objetos.

Mas linker.ld também cria memory extent por:

~~~text
. += 1024K
~~~

Isso exige uma primitive de synthetic zero-fill reservation.

## Symbols sintéticos

ChrisLd precisa criar:

~~~text
__kernel_start
__stack_bottom
__stack_top
__kernel_end
~~~

e disponibilizá-los durante symbol resolution.

## Timing dos symbols

Os valores dependem do momento no layout:

~~~text
__kernel_start
    antes dos requests

__stack_bottom
    após input BSS + ALIGN(16)

__stack_top
    após 1 MiB

__kernel_end
    após ALIGN(4K)
~~~

Não podem ser calculados genericamente sem respeitar a sequência.

## Subset de expressions necessário

O script atual usa apenas um núcleo relativamente pequeno:

~~~text
dot = constant
symbol = dot
dot = ALIGN(power_of_two)
dot += constant
~~~

Isso torna possível começar com interpreter limitado sem implementar todo GNU ld.

## Caminho de implementação sugerido

### Estágio 1

Criar structures para:

~~~text
segments
output sections
synthetic symbols
zero-fill reservations
retention rules
discard rules
~~~

### Estágio 2

Preservar arbitrary/special sections em ChrisO.

### Estágio 3

Implementar synthetic BSS reservations.

### Estágio 4

Implementar linker-created symbols.

### Estágio 5

Emitir três PT_LOAD equivalentes.

### Estágio 6

Comparar semanticamente com host ld.

### Estágio 7

Opcionalmente interpretar o subset real de linker.ld.

## Differential verification

Comparar host ld e ChrisLd por:

- ELF class;
- machine;
- entry;
- PHDR count;
- PHDR flags;
- VMA;
- filesz;
- memsz;
- synthetic symbols;
- stack size;
- kernel extent;
- request ordering;
- BSS semantics.

Byte-for-byte equality não é obrigatória.

## Gate com readelf

Um CI futuro pode verificar o kernel final com:

~~~text
readelf -h
readelf -l
readelf -S
readelf -s
~~~

Isso valida o ELF produzido, não apenas a source policy.

## Link map

Um map file de ld permitiria acompanhar:

- section sizes;
- symbol addresses;
- object contributions;
- layout regressions;
- comparação host/native.

## Invariantes atuais

No commit revisado:

1. output ELF64 x86-64;
2. arch x86-64;
3. ENTRY(kstart);
4. base 0xffffffff80000000;
5. __kernel_start na base;
6. três PT_LOADs nomeados;
7. requests RW;
8. text RX;
9. data RW;
10. nenhum W+X;
11. requests page-aligned;
12. start/body/end ordered;
13. KEEP em todos os requests;
14. text page-aligned;
15. .text e .text.* coletados;
16. rodata page-aligned;
17. .rodata e .rodata.* coletados;
18. rodata dentro do PHDR text;
19. data page-aligned;
20. .data e .data.* coletados;
21. BSS NOLOAD e page-aligned;
22. .bss e .bss.* coletados;
23. COMMON em BSS;
24. stack bottom 16-byte aligned;
25. reserva exatamente 1024 KiB;
26. stack top após reserva;
27. kernel end page-aligned;
28. .eh_frame* descartado;
29. .note* descartado;
30. .comment* descartado.

O checker desta rodada codifica essas regras.

## Recursos GNU ld não usados hoje

O script atual não usa:

- MEMORY;
- AT;
- AT>;
- explicit LMA;
- LOADADDR;
- PROVIDE;
- ASSERT;
- SORT;
- SUBALIGN;
- ALIGN_WITH_INPUT;
- OVERLAY;
- custom FILL;
- dynamic-link policy;
- PIE layout.

Esses recursos fazem parte da teoria de linker scripts, não da implementação corrente do ChrisOS.

## Checker reproduzível

scripts/check_linker_script_examples.py valida:

- linker.ld completo;
- location-counter arithmetic;
- ALIGN 4K/16;
- stack de 1 MiB;
- PHDR permissions;
- assignments requests/text/data;
- KEEP ordering;
- NOLOAD;
- /DISCARD/;
- ausência de MEMORY/AT;
- ausência, no ChrisLd atual, de Limine requests e synthetic production symbols.

Não substitui a inspeção do ELF final.

## Limite de validação

Capítulo reconciliado com:

~~~text
ChrisOS main
da3df29cb397932c43d32373871fb9380e688ade
~~~

e com a documentação atual do GNU Binutils ld.

Features genéricas do GNU ld são separadas das features realmente utilizadas pelo ChrisOS.

Execute:

~~~text
python scripts/check_linker_script_examples.py --source .source
~~~

## Gatilhos de revisão

Revisar quando:

- linker.ld mudar;
- base higher-half mudar;
- PHDRs ou permissions mudarem;
- rodata ganhar PHDR R;
- stack mudar;
- synthetic symbols mudarem;
- novas special sections surgirem;
- section GC for ativado;
- MEMORY/AT forem introduzidos;
- ChrisO ganhar arbitrary named sections;
- ChrisLd implementar kernel layout;
- ChrisLd interpretar scripts;
- kernel linkado nativamente bootar.

## Referências primárias

- GNU Binutils ld manual, Linker Scripts.
- System V ABI, modelo ELF.
- kernel/metal/linker.ld.
- makefile, ChrisO e ChrisLd do ChrisOS.
