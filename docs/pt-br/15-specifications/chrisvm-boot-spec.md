---
id: chrisvm-boot-spec
lang: pt-br
type: specification
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/boot.c
  - chrisvm/devices/serial/serial.c
  - chrisvm/devices/fb/fb.c
  - chrisvm/guests/link.ld
  - chrisvm/guests/arith.asm
  - chrisvm/guests/splash.asm
  - chrisvm/tests/test_chrisvm.c
symbols:
  - chris_load_elf
  - chris_boot
  - chris_arch_reset
depends_on:
  - chrisvm-spec
  - chrisvm-boot
  - elf-linking
  - x86-64-memory-privilege
related:
  - higher-half-kernel
  - linker-script
  - reset-firmware
  - limine
---

# Protocolo de boot do ChrisVM v1

## Escopo

O ChrisVM boot protocol versão 1 é um **contrato de direct ELF boot**.

Ele não emula BIOS, UEFI, Limine nem reset vector x86.

O host carrega um guest ELF64 diretamente na RAM guest, constrói estado mínimo de long mode x86-64, cria page tables identity-mapped e inicia o guest no ELF entry point.

A constante de versão é:

    CHRIS_BOOT_PROTOCOL = 1

Esta especificação descreve o contrato exato implementado na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

## Sequência de boot

O fluxo normal do host é:

    chris_config_init()
    chris_machine_create()
    chris_load_elf()
    chris_boot()
    chris_run()

O frontend passa entry `0` para `chris_boot`.

Nesse caso, o boot usa o ELF entry armazenado por `chris_load_elf`.

O stack pointer padrão é:

    CHRIS_STACK_RSP = 0x0000000000080000

## Intenção do protocolo

O v1 é propositalmente simples.

Ele existe para validar:

- execução ChrisCPU;
- ELF loading;
- long-mode paging;
- stack/control flow;
- serial;
- framebuffer;
- exceptions e comportamento de memória.

Firmware discovery é intencionalmente omitido.

Isso mantém o primeiro contrato pequeno e testável independentemente de uma plataforma PC completa.

## Classe ELF obrigatória

O loader aceita somente:

    ELF class:      ELF64
    endianness:     little-endian
    machine:        EM_X86_64 (62)

O header precisa conter ao menos um program header.

O tamanho de cada program-header entry precisa ser igual à estrutura `Elf64Phdr` usada pelo loader.

A tabela inteira deve caber dentro do input.

## Política de ELF type e section table

O loader é orientado por program headers.

Section headers não são usados para load.

Também não existe rejeição atual baseada em `e_type`.

Portanto o contrato normativo depende de PT_LOAD válidos e do entry point, não de section-table content nem de uma checagem estrita ET_EXEC/ET_DYN.

Mesmo assim, guests devem ser linkados como executáveis simples e não depender de comportamento implícito de ELF type.

## Tratamento de PT_LOAD

Somente program headers com:

    p_type == PT_LOAD

são copiados.

Outros tipos são ignorados.

Para cada PT_LOAD:

[
p_memsz ge p_filesz
]

e o range:

[
[p_offset, p_offset+p_filesz)
]

precisa estar completamente dentro do ELF buffer.

## Endereço de destino

O v1 carrega cada PT_LOAD em:

    destino físico/linear guest = p_vaddr

`p_paddr` não é utilizado.

Isso é uma propriedade definidora do protocolo.

Como o paging inicial é identity-mapped, o mesmo valor numérico funciona como virtual address e physical RAM address para code/data comuns.

## Zero-fill de BSS

Se:

[
p_memsz > p_filesz
]

os bytes após o file data até `p_memsz` são zerados.

O protocolo fornece, portanto, semantics usuais de BSS.

## Restrição lower-half

O v1 rejeita qualquer PT_LOAD com `p_vaddr` igual ou superior a:

    0xffff800000000000

O erro explícito é:

    higher-half ELF is outside boot protocol v1

O entry point também sofre a mesma restrição.

Logo, v1 é um **lower-half direct-boot protocol**.

## Limites da RAM

Cada segmento precisa caber totalmente em guest RAM:

[
p_vaddr < ram_size
]

e:

[
p_memsz le ram_size - p_vaddr
]

O ELF entry também deve estar abaixo de `ram_size`.

Assim PT_LOAD não pode ser carregado diretamente no framebuffer ou MMIO durante o load.

## Memória reservada do protocolo

O v1 reserva alguns ranges de RAM.

### Página da GDT

    0x00070000 .. 0x00070fff

PT_LOAD não pode sobrepor essa página de 4 KiB.

### Página inicial de stack

    0x0007f000 .. 0x0007ffff

O stack pointer inicial é:

    0x00080000

e o stack cresce para baixo dentro da página reservada.

PT_LOAD não pode sobrepô-la.

### Reserva das page tables

Os últimos 16 KiB da RAM são reservados:

    [ram_size - 0x4000, ram_size)

PT_LOAD não pode sobrepor esse range.

## Posicionamento das page tables

Dentro dos últimos 16 KiB:

    PML4 = ram_size - 0x4000
    PDPT = ram_size - 0x3000
    PD   = ram_size - 0x2000

A última página em:

    ram_size - 0x1000

continua dentro da reserva, embora `install_tables` não a utilize atualmente.

O guest deve tratar os 16 KiB completos como reservados.

## Alinhamento de RAM

Machine e protocolo exigem RAM:

- de pelo menos 2 MiB;
- alinhada a 2 MiB.

Formalmente:

[
ram_size ge 2MiB
]

e:

[
ram_size mod 2MiB = 0
]

O default é 16 MiB.

A topologia de framebuffer fixo limita a machine atual a no máximo 32 MiB de RAM.

## Identity mapping inicial

O boot identity-mapeia toda a guest RAM com páginas de 2 MiB.

Para índice (i):

[
VA = PA = i cdot 2MiB
]

Cada PDE recebe:

    physical_base | 0x83

Os bits relevantes são:

- Present;
- Read/Write;
- Page Size.

Assim a RAM inicial é supervisor-writable e usa large pages de 2 MiB.

## Hierarquia inicial

A estrutura criada é:

    PML4[0] -> PDPT
    PDPT[0] -> PD
    PD[i]   -> 2 MiB identity page

Isso cobre o low canonical region necessário aos guests atuais.

O código suporta no máximo 512 PDEs nesse setup.

Os limites atuais de RAM são muito menores.

## Mapeamento do framebuffer

A base física do framebuffer é:

    0x02000000

Geometria:

    640 x 480
    32 bits/pixel
    pitch 2560 bytes

Se o framebuffer existe, o boot mapeia o range com PDEs de 2 MiB no mesmo PD.

O mapping é identity-based:

    framebuffer VA == framebuffer PA

O framebuffer atual ocupa menos de uma página de 2 MiB, mas o algoritmo cobre todos os chunks necessários ao tamanho declarado.

## Regra de colisão do framebuffer

Ao adicionar PDE para framebuffer, `install_tables` exige que o slot correspondente esteja zerado.

Se identity mapping de RAM já ocupou o slot, o boot falha.

A machine evita a colisão normal rejeitando RAM acima da framebuffer base.

É por isso que o endereço fixo de 32 MiB afeta o limite de RAM.

## Conteúdo da GDT

O protocolo instala três descriptors de 8 bytes em:

    0x00070000

Entradas:

    GDT[0] = null
    GDT[1] = 64-bit code descriptor
    GDT[2] = data descriptor

Valores atuais:

    0x0000000000000000
    0x00af9a000000ffff
    0x00cf92000000ffff

O GDTR limit é:

    sizeof(descriptors) - 1

ou 23 bytes.

## Segment selectors

Selectors iniciais:

    CS = 0x08
    SS = 0x10

DS e ES recebem o mesmo estado de data segment de SS.

Code-segment base é zero.

CPL inicial:

    0

O v1 inicia diretamente em kernel privilege.

## CR0 inicial

Bits setados:

    PE
    NE
    WP
    PG

Conceitualmente:

[
CR0 = PE | NE | WP | PG
]

Protected mode e paging já estão ativos.

O guest não executa a transição histórica de real mode para protected/long mode.

## CR3 inicial

CR3 aponta para:

    ram_size - 0x4000

a PML4 criada pelo protocolo.

O guest pode depois substituir CR3 e construir seus próprios mappings dentro do subset implementado pelo ChrisCPU.

## CR4 inicial

CR4 contém:

    PAE

Outras facilities não são habilitadas pelo protocolo.

## EFER inicial

EFER contém:

    LME
    LMA

Long mode já está ativo.

NXE não é habilitado por default.

SCE também não é uma facility do boot v1.

O protocolo entrega uma CPU já em long mode.

## RFLAGS inicial

RFLAGS começa em:

    0x2

O bit arquitetural fixo 1 está setado.

Interrupt Flag começa limpo.

Guest que queira interrupts precisa configurar o state necessário e habilitá-los.

A machine atual não fornece uma plataforma PC completa de interrupts.

## RIP inicial

Se o caller fornece `entry` não zero, ele vira RIP.

Se fornece zero, o ELF entry armazenado é usado.

Depois da resolução, entry precisa ser:

- diferente de zero;
- menor que `ram_size`.

Caso contrário, boot falha.

## RSP inicial

Se caller passa `rsp` não zero, o valor é usado.

Se passa zero:

    0x80000

O frontend padrão já passa `0x80000` explicitamente.

A validação de overlap reserva apenas a página de 4 KiB imediatamente abaixo.

Guest que precise de stack maior é responsável por reservar RAM adequada.

## Outros registers

`chris_boot` começa com `chris_arch_reset`, que zera o state arquitetural antes de instalar o boot state.

Assim GPRs fora RSP começam em zero salvo alteração posterior do boot.

Control/segment fields não inicializados permanecem nos defaults de reset.

O guest não deve inferir conventions de firmware além das especificadas aqui.

## Estado da IDT

O v1 não instala IDT.

IDTR continua zero após reset salvo alteração pelo guest.

Uma exception antes da instalação da IDT resulta em:

    CHRIS_EXIT_EXCEPTION

reportado ao monitor, em vez de guest handler.

A test suite usa esse comportamento extensivamente.

## TSS e privilege transition

O v1 não cria TSS nem configura user-mode transition.

A execução começa em CPL0.

Guest que queira rings, TSS stack switching ou privilege transitions precisa construir isso sozinho dentro do subset suportado pelo ChrisCPU.

## Firmware services

Não existem no v1:

- BIOS interrupts;
- UEFI boot services;
- UEFI runtime services;
- ACPI discovery;
- SMBIOS;
- Limine requests/responses;
- multiboot structures;
- firmware memory map;
- PCI firmware enumeration.

Guest dependente dessas interfaces não é compatível com v1.

## Devices disponíveis no entry

Antes do entry, a criação da machine já anexou:

- serial em `0x3f8..0x3ff`;
- ChrisVM shutdown port em `0x501`;
- linear framebuffer em `0x02000000`.

Não existe disk device no baseline do protocolo.

A image guest já está na RAM porque o host loader a colocou lá.

## Contrato serial

A serial é suficientemente compatível com o subset 16550 usado pelos guests atuais.

O guest pode escrever characters em:

    0x3f8

respeitando line-control/divisor-latch emulado.

O arithmetic guest emite:

    OK

antes de HLT.

## Shutdown ABI

Guest pode solicitar shutdown escrevendo low byte `1` em:

    0x501

A machine termina em:

    CHRIS_EXIT_SHUTDOWN

É device específico do ChrisVM, não interface ACPI padrão.

## Exemplo de linker contract

Os guests bundled usam:

    OUTPUT_FORMAT(elf64-x86-64)
    ENTRY(_start)

e posicionam code em:

    0x1000

O linker cria PT_LOAD de text.

Esse layout fica abaixo das áreas reservadas e já está identity-addressable no entry.

## Arithmetic guest

O guest de referência:

1. escreve `OK\n` em COM1;
2. faz integer arithmetic;
3. faz RAM round trip em `0x4000`;
4. exercita CALL/RET;
5. executa HLT.

O test exige:

- `CHRIS_EXIT_HLT`;
- RAX igual a 31;
- serial exatamente `OK\n`.

É evidência executável do contrato.

## Splash guest

O splash escreve diretamente em:

    0x02000000

usando framebuffer 640x480 de 32 bits.

Exercita REP STOS e memory writes no framebuffer identity-mapped.

Emite:

    splash

na serial e executa HLT.

Os tests validam serial e selected framebuffer pixels.

## Casos de rejeição ELF

O loader rejeita, entre outros:

- header ausente/truncado;
- bad magic;
- classe diferente de 64-bit;
- endianness diferente de little-endian;
- machine diferente de x86-64;
- ausência de program headers;
- program-header size incorreto;
- tabela fora do input;
- file range PT_LOAD fora do input;
- `p_memsz < p_filesz`;
- segment fora da RAM;
- higher-half segment;
- overlap com GDT;
- overlap com stack page;
- overlap com os últimos 16 KiB;
- entry higher-half ou fora da RAM.

São host-loader failures, não CPU exceptions do guest.

## Segment flags

O loader atual não converte `p_flags` dos PT_LOAD em permissões das page tables iniciais.

As identity pages da RAM são supervisor read/write e efetivamente executable porque NXE não está ativo.

Logo, `p_flags` não estabelece W^X nem read-only code protection no boot.

O guest pode criar mappings mais restritos depois.

## Política de relocation

O v1 não faz dynamic linking nem relocations ELF gerais.

O guest deve estar previamente linkado para os endereços representados em `p_vaddr`.

Não existe symbol resolver, PLT/GOT loader ou relocation engine no boot.

## Incompatibilidade com higher-half ChrisOS

O kernel de produção do ChrisOS é higher-half.

O v1 rejeita PT_LOAD higher-half explicitamente.

Portanto o kernel real não pode ser bootado pelo v1 simplesmente apontando ChrisVM para o ELF existente.

É limitação explícita do protocolo, não apenas lacuna de testes.

Um protocolo futuro capaz de substituir QEMU/Limine precisa definir higher-half loading e o boot-information contract esperado por `kstart`.

## Por que v1 não deve special-case kstart

Um atalho tentador seria detectar o kernel ChrisOS e saltar diretamente para `kstart` com host-created state ad hoc.

Isso esconderia contracts de plataforma ainda ausentes.

O v1 permanece arquiteturalmente honesto: suporta o direct-boot ABI realmente implementado.

Boot completo do ChrisOS deve surgir em versão explícita seguinte da machine/protocolo.

## Regra de versionamento

Mudança incompatível em qualquer item abaixo exige nova versão do boot protocol ou compatibility layer documentada:

- reserved physical addresses;
- page-table layout inicial;
- segment selectors;
- stack contract;
- framebuffer address/geometry;
- shutdown port;
- ELF address policy;
- register state;
- firmware/boot-information handoff.

Alteração silenciosa tornaria guest binaries antigos ambíguos.

## Trabalho candidato para v2

Uma versão voltada ao kernel real provavelmente precisa definir:

- higher-half PT_LOAD;
- HHDM;
- framebuffer boot information;
- memory-map handoff;
- SMP information;
- ACPI/firmware information;
- virtual/physical ownership do kernel;
- assumptions do linker script ChrisOS;
- device topology;
- transição para `kstart`.

Esses itens são roadmap, não comportamento v1.

## Checklist de conformidade

Guest v1 pode contar com:

- ELF64 little-endian x86-64 direct load;
- PT_LOAD copiado para lower-half `p_vaddr`;
- BSS zeroing;
- RAM identity-mapped;
- long mode ativo;
- CPL0;
- stack inicial em `0x80000`;
- COM1 em `0x3f8`;
- shutdown port em `0x501`;
- framebuffer em `0x02000000`;
- ausência de firmware services;
- nenhuma IDT inicial;
- nenhum SMP;
- nenhum disk boot.

Tudo além disso precisa ser demonstrado pela especificação revisionada da machine, não presumido de um PC físico.

## Nota de revisão

Esta especificação foi reconciliada contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

O v1 é propositalmente pequeno e testável. A fronteira de compatibilidade mais importante é que ele boota direct ELF guests lower-half, não o kernel ChrisOS higher-half de produção.
