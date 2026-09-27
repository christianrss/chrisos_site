---
id: elf-linking
lang: pt-br
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/linker.ld
  - makefile
  - kernel/metal/elf.c
  - kernel/metal/elf.h
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chrisld.h
  - compiler/chrisasm/chrisasm.c
  - tools/test_chrisld.c
  - docs/CHRISLD_STATUS.md
  - docs/CURRENT_SELFHOST_AUDIT.md
  - docs/NATIVE_TOOLCHAIN_AUDIT.md
symbols:
  - kstart
  - __kernel_start
  - __kernel_end
  - __stack_bottom
  - __stack_top
  - elf_load
  - chrisld_link
  - chrisld_link_objects
  - chrisld_validate
depends_on:
  - boot-information
  - machine-code
  - x86-64-memory-privilege
related:
  - linker-script
  - higher-half-kernel
  - power-on-kstart
  - native-toolchain
  - chrisld
  - chriso
  - kcc
---

# ELF64, linkedição e a imagem do kernel ChrisOS

## Escopo

O kernel do ChrisOS não é apenas uma sequência crua de instruções x86-64. Ele é um executável ELF64 cuja estrutura informa ao bootloader qual arquitetura deve executar a imagem, onde está o entry point, quais bytes precisam ser carregados, quais endereços virtuais devem receber esses bytes, quais regiões existem apenas em memória e quais permissões de leitura, escrita e execução cada região deve possuir.

Antes do ELF final existir, o toolchain trabalha com seções, símbolos, referências indefinidas, relocations, alinhamentos e endereços que ainda não foram definidos.

O pipeline de produção atual é:

~~~text
fontes C / assembly
        |
        +-- GCC do host
        +-- assembler
        |
        v
objetos relocáveis
        |
        v
ld do host
  -static
  -nostdlib
  -T kernel/metal/linker.ld
        |
        v
kernel.elf
  ELF64
  ET_EXEC
  EM_X86_64
  higher-half
  ENTRY(kstart)
  segmento de requests Limine
        |
        v
Limine
        |
        v
imagem do kernel mapeada
~~~

![Pipeline de linkedição ELF](../../assets/diagrams/elf-linking-pt-br.svg)

O ChrisLd nativo está evoluindo em direção a esse alvo, mas ainda não gera uma imagem equivalente ao kernel de produção.

## Visão de link e visão de carregamento

ELF possui duas visões relacionadas.

Durante a linkedição, os elementos centrais são sections, symbols e relocations.

Durante o carregamento, os elementos centrais são program headers, segments e o entry point.

A distinção essencial é:

~~~text
sections
    servem principalmente ao linker,
    debugger e ferramentas de análise

program headers
    servem principalmente ao loader
~~~

O bootloader não precisa reconstruir cada seção fonte. Ele precisa criar a imagem de memória descrita pelos program headers.

## Tipos de arquivo ELF

Tipos importantes são:

| Tipo | Significado |
|---|---|
| ET_REL | objeto relocável |
| ET_EXEC | executável |
| ET_DYN | shared object ou executável position-independent |
| ET_CORE | core dump |

O kernel final do ChrisOS é ET_EXEC.

Objetos intermediários produzidos pelo compilador são relocáveis porque vários endereços só podem ser conhecidos quando todo o conjunto de objetos for combinado.

## Por que objetos relocáveis existem

Se uma unidade de compilação chama uma função definida em outro arquivo, o compiler consegue emitir a instrução de chamada, mas ainda não conhece o endereço final do destino.

O objeto registra:

- bytes de machine code;
- referência a um symbol;
- local da relocation;
- tipo da relocation;
- addend quando aplicável.

O linker determina o layout, resolve o símbolo e corrige os bytes.

## Identificação ELF

Todo ELF começa com:

~~~text
0x7f 'E' 'L' 'F'
~~~

No ChrisOS:

~~~text
EI_CLASS = ELFCLASS64
EI_DATA  = ELFDATA2LSB
~~~

Portanto as estruturas são ELF de 64 bits e os inteiros são little-endian.

## ELF64 header

O header ELF64 possui 64 bytes.

Campos importantes:

| Campo | Finalidade |
|---|---|
| e_ident | identificação |
| e_type | tipo do objeto |
| e_machine | arquitetura |
| e_version | versão ELF |
| e_entry | endereço virtual de entrada |
| e_phoff | offset dos program headers |
| e_shoff | offset dos section headers |
| e_flags | flags de arquitetura |
| e_ehsize | tamanho do header |
| e_phentsize | tamanho de cada program header |
| e_phnum | quantidade de program headers |
| e_shentsize | tamanho de cada section header |
| e_shnum | quantidade de sections |
| e_shstrndx | índice da tabela de nomes |

Para x86-64:

~~~text
e_ehsize    = 64
e_phentsize = 56
e_machine   = 62
~~~

62 corresponde a EM_X86_64.

## Entry point

e_entry contém o endereço virtual da primeira instrução.

O linker script de produção declara:

~~~text
ENTRY(kstart)
~~~

O linker resolve o endereço final de kstart e o grava no ELF header.

O Limine entra nesse endereço porque o ChrisOS não utiliza um Entry Point request separado.

## Program headers

Cada program header ELF64 contém:

- p_type;
- p_flags;
- p_offset;
- p_vaddr;
- p_paddr;
- p_filesz;
- p_memsz;
- p_align.

PT_LOAD é o tipo central para o kernel.

## PT_LOAD

Um PT_LOAD determina:

~~~text
copiar p_filesz bytes
do offset p_offset no arquivo

para o endereço virtual p_vaddr

reservando p_memsz bytes em memória
~~~

Se p_memsz for maior que p_filesz, a diferença deve ser zerada.

## Imagem no arquivo versus imagem em memória

Para um segmento:

~~~text
arquivo:
[p_offset, p_offset + p_filesz)

memória:
[p_vaddr, p_vaddr + p_memsz)
~~~

O loader copia o prefixo presente no arquivo e zera o restante.

O executável em disco pode assim ser muito menor que a imagem runtime.

## BSS

Variáveis globais/static não inicializadas ou inicializadas com zero normalmente ficam em BSS.

O script atual contém:

~~~text
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
~~~

Isso:

- coleta BSS;
- inclui COMMON;
- reserva 1 MiB para a região de stack;
- cria os symbols da stack;
- cria __kernel_end;
- aumenta o tamanho em memória do segmento RW sem gravar 1 MiB de zeros no ELF.

## p_filesz versus p_memsz

Se um segmento tiver 12 KiB de data inicializado, 40 KiB de BSS e stack reservada de 1024 KiB:

~~~text
p_filesz = data inicializado
p_memsz  = data + BSS + stack
~~~

Alinhamentos podem adicionar gaps.

A diferença é memória zerada criada pelo loader.

## Permissões de segmentos

As flags ELF são:

~~~text
PF_X = 1
PF_W = 2
PF_R = 4
~~~

O linker script define:

~~~text
requests PT_LOAD FLAGS(6)  -> R | W
text     PT_LOAD FLAGS(5)  -> R | X
data     PT_LOAD FLAGS(6)  -> R | W
~~~

Nenhum PT_LOAD de produção é simultaneamente gravável e executável.

## Segmento de requests Limine

Esse segmento contém:

~~~text
.limine_requests_start
.limine_requests
.limine_requests_end
~~~

Ele precisa ser RW porque o Limine escreve response pointers nas estruturas antes de entrar no kernel.

Não precisa ser executável.

As permissões ELF representam diretamente o contrato do protocolo de boot.

## Text e rodata

.text e .rodata são atribuídas ao mesmo program header text.

Logo constantes read-only ficam hoje no mesmo segmento RX do código.

Elas não são graváveis, mas o mapping é executável.

Um layout futuro mais estrito poderia separar:

~~~text
RX text
R  rodata
RW data
~~~

além do segmento de requests.

O desenho atual ainda evita W+X.

## Data

.data e .bss pertencem ao segmento RW.

A stack reservada pelo linker também amplia esse segmento em memória.

Bytes inicializados existem no arquivo; BSS e stack são representados principalmente por p_memsz.

## Alinhamento

O link host utiliza:

~~~text
-z max-page-size=0x1000
~~~

e as principais sections de saída são alinhadas a 4 KiB.

A relação necessária para PT_LOAD é:

~~~text
p_vaddr mod p_align
=
p_offset mod p_align
~~~

Isso permite mappings orientados a páginas.

## p_paddr

ELF também possui p_paddr.

No caminho do ChrisOS, o Limine controla o backing físico real enquanto respeita o layout virtual.

O p_vaddr higher-half não é o endereço físico do kernel em RAM.

Accounting físico não deve derivar o endereço físico do link address.

## Sections

Sections comuns incluem:

~~~text
.text
.rodata
.data
.bss
.symtab
.strtab
.rela.text
.rela.data
~~~

O section header descreve propriedades como:

- nome;
- tipo;
- flags;
- endereço;
- offset;
- tamanho;
- alignment;
- relações com outras sections.

## Section versus segment

Várias sections podem ocupar um único segmento.

No ChrisOS:

~~~text
PT_LOAD text
  .text
  .rodata
~~~

e:

~~~text
PT_LOAD data
  .data
  .bss
  stack reservada
~~~

O linker organiza sections. O loader mapeia segments.

## Section headers e boot

O Limine usa principalmente os program headers para construir a imagem runtime.

Muitos section headers poderiam ser removidos sem impedir o carregamento, desde que program headers e entry continuem válidos.

Mesmo assim, sections permanecem úteis para:

- debug;
- disassembly;
- symbolization;
- inspeção;
- linking.

## Symbols

Um symbol descreve uma entidade nomeada.

Atributos relevantes:

- name;
- value ou offset;
- size;
- binding;
- kind;
- section.

Bindings comuns incluem local, global e weak.

Kinds comuns incluem function, object, section e no-type.

## Symbols locais e globais

Local não participa da resolução global entre objetos.

Global pode satisfazer referências externas.

Duas definições globais incompatíveis do mesmo nome normalmente devem gerar erro.

O ChrisLd atual rejeita duplicate globals.

## Undefined symbols

Um undefined symbol representa uma dependência.

O objeto usa o nome, mas não o define.

Durante static linking, o linker precisa encontrar uma definição válida.

Se não existir, a linkedição precisa falhar.

## Endereço final de um symbol

Após o layout:

~~~text
S =
base da output section
+ offset do objeto dentro dela
+ offset do symbol
~~~

O ChrisLd atual calcula essa relação para text, rodata, data e BSS.

## Relocations

Relocation instrui o linker a calcular os bytes finais de uma referência.

A notação usual é:

~~~text
S = endereço final do symbol
A = addend
P = endereço do local da relocation
~~~

Exemplos:

~~~text
R_X86_64_64:
S + A

R_X86_64_PC32:
S + A - P

R_X86_64_PLT32:
S + A - P
~~~

no modelo de binding estático usado pelo ChrisLd atual.

## REL e RELA

REL mantém o addend implicitamente nos bytes do target.

RELA possui addend explícito no próprio record.

x86-64 usa amplamente relocations no estilo RELA.

ChrisoRel v2 possui addend assinado explícito.

## R_X86_64_64

Grava um endereço absoluto de 64 bits.

É útil para ponteiros cujo endereço final só é conhecido no link.

## R_X86_64_PC32

Grava deslocamento relativo de 32 bits:

~~~text
S + A - P
~~~

O resultado precisa caber em int32:

~~~text
-2147483648 .. 2147483647
~~~

O ChrisLd atual rejeita overflow.

## R_X86_64_PLT32

Compilers frequentemente usam PLT32 em calls externas.

Em static linking, quando o destino é conhecido, o linker pode ligar a call diretamente.

O ChrisLd usa a mesma fórmula PC-relative.

## R_X86_64_32

É uma relocation absoluta de 32 bits.

O ChrisLd rejeita valores acima de 0xffffffff.

## Limitação atual de R_X86_64_32S

R_X86_64_32S possui semântica signed de 32 bits no ABI x86-64.

O ChrisLd atual aplica a mesma verificação superior usada por R_X86_64_32.

Portanto sua implementação de 32S ainda não reproduz completamente a regra signed do ABI.

## Overflow de relocation

Truncar um PC-relative displacement inválido produziria branch para endereço incorreto.

O linker deve rejeitar relocation não representável ou usar outra estratégia de code generation.

Linking é uma transformação semântica, não concatenação de bytes.

## Kernel code model

O GCC de produção usa:

~~~text
-mcmodel=kernel
~~~

Isso seleciona suposições de endereçamento apropriadas ao kernel x86-64 localizado na região canônica alta.

Compiler e linker precisam concordar sobre esse modelo.

## Kernel fixo, não PIE

As flags também incluem:

~~~text
-fno-pic
-fno-pie
~~~

e o linker fixa:

~~~text
0xffffffff80000000
~~~

O kernel atual é ET_EXEC em endereço virtual fixo.

Ainda não é um kernel PIE/KASLR.

## Static e nostdlib

O link usa:

~~~text
-nostdlib
-static
~~~

O kernel não recebe automaticamente startup files, libc ou dynamic loader do host.

Todos os symbols necessários precisam vir dos objetos fornecidos explicitamente.

## Linker script como política

ELF fornece mecanismos genéricos.

kernel/metal/linker.ld determina a política do ChrisOS:

- formato;
- arquitetura;
- entry;
- base virtual;
- segments;
- ordem das sections;
- alinhamento;
- metadata Limine;
- stack;
- symbols de fronteira;
- sections descartadas.

O próximo capítulo trata essa política isoladamente.

## Symbols criados pelo linker

O script cria:

~~~text
__kernel_start
__kernel_end
__stack_bottom
__stack_top
~~~

Eles não precisam ser definidos por um arquivo C.

O linker transforma fronteiras de layout em symbols consumíveis pelo kernel.

## __kernel_start e __kernel_end

__kernel_start é atribuído antes das sections na base higher-half.

__kernel_end aparece depois de BSS, stack e alinhamento final.

Eles delimitam o espaço virtual linkado do kernel.

## __stack_bottom e __stack_top

O linker alinha a 16 bytes, marca bottom, avança 1024 KiB, marca top e então alinha a página.

Isso reserva memória sem gravar um MiB de zeros no arquivo.

## COMMON

O BSS inclui:

~~~text
*(COMMON)
~~~

para acomodar tentative definitions que eventualmente apareçam como common symbols em objetos.

## Sections descartadas

O script descarta:

~~~text
.eh_frame*
.note*
.comment*
~~~

O runtime atual não depende de unwind metadata do host, notes genéricas ou strings de comentário do compiler.

Se unwind avançado for implementado, essa política precisa ser revista.

## Ordem das sections

O layout é:

~~~text
0xffffffff80000000
    |
    +-- requests Limine
    +-- text
    +-- rodata
    +-- data
    +-- bss
    +-- stack reservada
    |
__kernel_end
~~~

A ordem influencia endereços, relocations e o hash do executável.
