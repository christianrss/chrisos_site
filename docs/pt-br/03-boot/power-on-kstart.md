---
id: power-on-kstart
lang: pt-br
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/start.c
  - kernel/metal/serial.c
  - kernel/metal/bootinfo.c
  - kernel/metal/gdt.c
  - kernel/metal/idt.c
  - kernel/metal/irq.c
  - kernel/metal/pit.c
  - kernel/metal/pmm.c
  - kernel/metal/mm.c
  - kernel/metal/apic.c
  - kernel/metal/ioapic.c
  - kernel/metal/smp.c
  - kernel/gfx/sse_init.c
  - kernel/metal/proc.c
  - kernel/metal/linker.ld
  - makefile
symbols:
  - kstart
  - serial_init
  - bootinfo_init
  - gdt_init
  - idt_init
  - syscall_init
  - pic_init
  - pit_init
  - pmm_init
  - mm_init
  - heap_init
  - proc_init
  - apic_init
  - smp_init
depends_on:
  - reset-firmware
  - uefi
  - limine
  - boot-information
  - elf-linking
  - linker-script
  - higher-half-kernel
related:
  - kernel-model
  - gdt-tss
  - idt-exceptions
  - physical-memory
  - virtual-memory
  - interrupts-smp
---

# Da energização ao kstart: o handoff completo do ChrisOS

## Escopo

kstart é a primeira função C do kernel ChrisOS, mas não é o início da história da máquina.

Antes da primeira instrução dessa função, vários ambientes de execução com ownership diferente já existiram:

~~~text
reset de hardware
    ↓
firmware
    ↓
caminho UEFI ou BIOS
    ↓
Limine
    ↓
carregamento ELF
    ↓
mappings higher-half
    ↓
GDT / stack / page tables do bootloader
    ↓
RIP = kstart
    ↓
inicialização do ChrisOS
~~~

Este capítulo reconstrói o caminho cronologicamente e acompanha a sequência real de kstart até a entrada no loop permanente do desktop.

O problema central é ownership. Parte do estado vem do hardware ou firmware. Parte é criada pelo Limine e apenas emprestada ao ChrisOS. Outra parte é substituída, adotada ou criada pelo próprio kernel.

![Linha do tempo da energização ao kstart](../../assets/diagrams/power-on-kstart-pt-br.svg)

## Boot é transferência de ownership

Boot não é apenas uma sequência de funções.

Cada estágio cria recursos e assumptions consumidos pelo próximo.

Exemplos:

- CPU mode;
- page tables;
- stack;
- descriptor tables;
- framebuffer;
- memory map;
- HHDM;
- AP descriptors;
- estado de interrupt controllers.

Um kernel robusto precisa distinguir o que já possui, o que adotou e o que ainda está apenas emprestado.

## Estágio 0: reset arquitetural

No reset físico, a CPU ainda não está executando ChrisOS.

O firmware controla a máquina.

Ainda não existem:

- page tables do ChrisOS;
- GDT do ChrisOS;
- IDT do ChrisOS;
- heap;
- process table;
- scheduler;
- filesystem.

O capítulo reset-firmware detalha a arquitetura de reset e o caminho histórico necessário até long mode.

## Estágio 1: firmware

O firmware inicializa estado suficiente para localizar e executar o próximo componente de boot.

Em UEFI, isso inclui serviços padronizados para storage, executable loading, graphics, memory allocation e memory-map discovery.

Em BIOS, o caminho interno é muito diferente.

O ChrisOS não carrega essa diferença para dentro de kstart. Limine normaliza ambos os caminhos.

## Estágio 2: Limine

Firmware ou um estágio anterior carrega o Limine.

A partir daí, Limine passa a:

- interpretar kernel.elf;
- localizar requests;
- alocar physical backing;
- criar mappings;
- preparar stack e descriptor state;
- publicar boot responses;
- transferir controle para o entry point ELF.

O ChrisOS portanto começa a partir de um boot protocol e não diretamente de uma ABI de firmware.

## Base revision atual

O source atual pede:

~~~text
LIMINE_BASE_REVISION(3)
~~~

bootinfo_init verifica suporte.

A especificação atual do Limine considera as base revisions 0 a 5 deprecated, embora continue definindo sua semântica.

Logo o ChrisOS usa deliberadamente um contrato mais antigo, mas ainda definido.

Isso significa que guarantees adicionadas nas revisions 5 ou 6 não podem ser atribuídas ao kernel atual.

## Regra HHDM da revision 3

Base revision 3 tornou o HHDM restritivo.

Ele cobre classes específicas do memory map, incluindo:

- usable;
- bootloader reclaimable;
- executable/modules;
- framebuffer.

Não significa que qualquer physical address possa ser acessado por:

~~~text
phys + hhdm_offset
~~~

O próprio bootinfo.c atual avisa explicitamente que LAPIC não deve ser acessado dessa forma.

## Estágio 3: requests embutidos

O kernel contém:

~~~text
request start marker
base revision 3

framebuffer request
HHDM request
memory-map request
MP request
executable command-line request

request end marker
~~~

O linker script preserva e ordena essas estruturas.

Limine escreve response pointers nelas antes do handoff.

## Requests são um canal pré-entry

A região de requests é gravável porque o bootloader altera os campos response.

O estado observado pelo kernel na entrada é portanto resultado de:

~~~text
imagem ELF
+
execução do bootloader
~~~

e não apenas do que foi compilado.

## Estágio 4: carregamento ELF

A imagem de produção é:

~~~text
ELF64
ET_EXEC
EM_X86_64
ENTRY(kstart)
~~~

linkada em:

~~~text
0xffffffff80000000
~~~

com três classes principais:

~~~text
requests  RW
text      RX
data      RW
~~~

Limine mapeia os PT_LOADs no higher-half de acordo com os permissions do ELF.

## VMA não é physical placement

0xffffffff80000000 é virtual address.

Limine escolhe physical pages e cria page tables para que o virtual address esperado pelo linker traduza para o backing correto.

Essa distinção é essencial para entender o boot inteiro.

## Estágio 5: HHDM

Limine constrói o Higher Half Direct Map e retorna seu offset.

bootinfo_init guarda:

~~~text
info.hhdm_offset = hhdm->offset
~~~

Esse offset é runtime state.

Não é definido pelo linker script.

## Estágio 6: page tables

Antes de kstart executar em endereço canônico alto, paging já precisa estar ativo.

A hierarchy inicial é criada pelo Limine e reside em bootloader-reclaimable memory.

O layout interno dessas tables não faz parte do ABI.

O contrato são os mappings oferecidos.

## Estágio 7: estado x86-64 na entrada

Para o contrato atual relevante ao ChrisOS, as guarantees importantes incluem:

~~~text
RIP
    executable entry point

64-bit execution
    ativa

CR0.PE
CR0.WP
CR0.PG
    habilitados

CR4.PAE
    habilitado

EFER.LME
EFER.LMA
    habilitados

EFER.NXE
    habilitado se suportado

RFLAGS.IF
direction flag
VM flag
    limpos

A20
    aberto
~~~

O ChrisOS não solicita five-level paging, então a documentação atual trabalha com o default de four-level paging.

## Não importar guarantees de revisions novas

A base revision 5 tornou várias partes do machine state mais estritamente definidas.

O ChrisOS pede revision 3.

Portanto não se pode assumir, por exemplo, que todos os outros bits de CR0/CR4/EFER, task register, LDTR ou IDTR tenham o estado adicional garantido somente em revision 5.

A regra correta é:

~~~text
usar apenas guarantees da revision 3
ou estabelecer explicitamente o estado no ChrisOS
~~~

## GDT de entrada

Limine fornece ambiente de segmentação 64-bit válido e uma GDT própria.

Essa GDT está em bootloader-reclaimable memory.

Por isso o ChrisOS instala uma GDT própria muito cedo.

## IDT de entrada

Para a revision atual, a IDT é descrita como undefined e o executable precisa carregar a sua própria.

O source atual faz:

~~~text
kstart
  serial_init
  build_info_log
  bootinfo_init
  gdt_init
  idt_init
~~~

Logo várias operações acontecem antes da IDT do ChrisOS existir.

## Janela inicial de exceções

Antes de idt_init:

- COM1 é programada;
- loopback serial é testado;
- build metadata é impressa;
- responses Limine são validadas;
- memory map é percorrido;
- command line é interpretada;
- GDT/TSS são construídas e recarregadas.

Maskable interrupts estão desabilitados, mas synchronous exceptions continuam possíveis.

CLI não impede #PF, #GP, #UD ou outras exceções síncronas.

Essa é uma fronteira de risco real.

## Stack inicial

Limine fornece RSP apontando para uma stack em bootloader-reclaimable memory com pelo menos 64 KiB, salvo se uma Stack Size feature maior tiver sido solicitada.

O ChrisOS atual não faz esse request.

Portanto o BSP começa kstart usando stack do bootloader.

O protocolo coloca um return address inválido zero na stack.

kstart não deve retornar.

## Registradores gerais

Os demais GPRs entram zerados pelo contrato x86-64 do Limine.

Isso tem impacto pequeno depois que código C começa a executar.

Os estados realmente persistentes são stack, page tables, descriptor state e boot responses.

## UEFI Boot Services já terminaram

Se Limine foi executado via EFI, Boot Services são encerrados antes do entry do kernel.

kstart não roda como uma UEFI application normal.

Qualquer uso posterior de firmware exige tables persistentes, runtime services adequados ou drivers próprios.

## IF na entrada

IF entra limpo.

Isso permite inicializar a maior parte do sistema sem maskable interrupts assíncronos.

O STI perto do final de kstart é portanto uma transição arquitetural importante.

## kstart é diretamente o entry ELF

linker.ld declara:

~~~text
ENTRY(kstart)
~~~

e start.c possui:

~~~text
void kstart(void)
~~~

Não existe um assembly trampoline próprio do ChrisOS no caminho de produção entre Limine e essa função C.

A ABI do compiler importa imediatamente.

## Fase A: diagnostics

A primeira operação é serial_init.

Se falhar:

~~~text
CLI
HLT para sempre
~~~

O kernel não continua sem seu primeiro canal de diagnóstico.

## O que serial_init faz

A função:

1. inicia kernel log;
2. desabilita UART interrupts;
3. programa divisor COM1;
4. seleciona 8N1;
5. configura FIFO;
6. ativa loopback;
7. envia 0xae;
8. lê o mesmo valor;
9. encerra loopback;
10. marca serial disponível;
11. inicializa spinlock.

Não depende de heap, PMM, APIC ou scheduler.

## Por que serial polling funciona cedo

O driver usa port I/O e polling.

Não depende de IRQ delivery.

Por isso é adequado antes da IDT e do runtime de interrupts estarem prontos.

## Build identity vem em seguida

Depois da serial:

~~~text
ChrisOS selfhost=1
build_info_log
~~~

A proveniência do build aparece antes dos subsistemas complexos.

Isso ajuda a correlacionar uma falha com o kernel exato que foi executado.

## Fase B: bootinfo_init

O próximo boundary é bootinfo_init.

Ele valida o contrato Limine e monta a primeira estrutura ChrisOS de boot information.

## Responses obrigatórias

O source exige:

- base revision suportada;
- pelo menos um framebuffer;
- HHDM;
- memory map;
- MP;
- pelo menos uma CPU;
- framebuffer 32 bpp.

Falha em qualquer item é fatal.

## Normalização ainda parcial

Vários scalars são copiados para struct bootinfo.

Porém o raw memory-map response continua armazenado.

O SMP também usa o raw MP response.

Logo o kernel ainda não fez deep-copy completo do estado necessário.

## Boot flags

A command line suporta:

~~~text
safe
nosmp
noapic
noac97
nonet
nojit
gfx.backend=...
gfx.3d=...
gfx.stress
gfx.virgl.debug
~~~

safe ativa várias opções conservadoras ao mesmo tempo.

## Diagnóstico LAPIC

bootinfo_init calcula e imprime HHDM + LAPIC apenas como diagnóstico e avisa para não desreferenciar como MMIO.

Depois verifica a classificação do endereço físico 0xfee00000 no memory map.

Isso mantém separadas RAM e device memory.

## Fase C: GDT própria

gdt_init cria uma GDT e TSS pertencentes ao ChrisOS.

A GDT possui descriptors de kernel code/data, user code/data e TSS64.

Depois disso a GDT do Limine deixa de ser necessária ao funcionamento normal.

## TSS RSP0

A função configura:

~~~text
tss.rsp0 = __stack_top
~~~

__stack_top vem da stack de 1 MiB reservada em linker.ld.

Isso define a stack de transição de privilégio.

Não prova que o RSP corrente do BSP já foi mudado para ela.

## Reload da GDT

gdt_init executa:

~~~text
LGDT
far control transfer para recarregar CS
reload DS / ES / SS
limpeza de FS / GS selectors
LTR
~~~

e verifica o task register.

Essa é uma transição clara de descriptor state do bootloader para descriptor state do kernel.

## Fase D: IDT própria

idt_init cria 256 gates, instala NMI entry na vector 2 e executa LIDT.

A partir daqui synchronous faults podem chegar aos handlers do ChrisOS.

## Por que GDT antes da IDT

IDT gates contêm code selector.

Os gates usam o selector do kernel code da GDT do ChrisOS.

Logo a GDT precisa existir primeiro.

## syscall_init

Depois da IDT, syscall_init transforma vector 0x80 em um user-accessible interrupt gate.

A ABI atual de syscall passa pelo caminho da IDT.

## Fase E: PIC legado

pic_init executa CLI novamente e remapeia o PIC:

~~~text
master = 0x20
slave  = 0x28
~~~

Todos os IRQs terminam masked.

Isso evita conflito entre exceptions e hardware IRQ vectors.

## Fase F: PIT em 60 Hz

pit_init(60) instala handler de IRQ0 e programa o PIT.

O divisor é calculado a partir de:

~~~text
1193182 / 60
~~~

IRQ0 é unmasked no PIC.

Mas IF continua 0.

## PIC mask e IF são controles diferentes

Timer delivery normal exige:

~~~text
IRQ0 unmasked no PIC
e
RFLAGS.IF = 1
~~~

pit_init resolve a primeira condição.

O STI final resolve a segunda.

## PS/2

ps2_init vem em seguida.

Falha não é fatal.

O sistema continua sem keyboard/mouse.

## Fase G: PMM

Depois:

~~~text
pmm_init
pmm_selftest
~~~

PMM depende do memory map validado em bootinfo_init.

## Política conservadora do PMM

O allocator libera apenas USABLE e volta a reservar classes importantes:

- low memory;
- reserved;
- ACPI NVS;
- bad memory;
- bootloader reclaimable;
- executable/modules;
- framebuffer.

## Por que bootloader-reclaimable continua reservado

Stack e page tables iniciais ainda pertencem ao bootloader e continuam sendo usados.

Logo essa classe não pode ser devolvida ao allocator em massa.

## PMM self-test

O teste aloca physical pages, acessa via HHDM, grava signatures e verifica reuse.

Isso testa allocator e direct map de ordinary RAM ao mesmo tempo.

## Fase H: MM

Depois:

~~~text
mm_init
mm_selftest
~~~

mm_init lê CR3 e adota a hierarchy criada pelo Limine.

Não existe ainda nova root própria do kernel.

## Hierarchy adotada

Após mm_init o ChrisOS:

- percorre tables;
- cria mappings;
- aloca child tables;
- cria MMIO aliases;
- copia upper-half mappings para process roots.

As page tables herdadas viram estado mutável do kernel.

## Verificação do framebuffer

mm_init traduz o virtual address do framebuffer para physical.

Se não existir mapping, o boot para.

## MM self-test

O teste:

1. aloca uma physical page;
2. mapeia em MM_TEST_VIRT;
3. obtém HHDM alias;
4. escreve por um alias;
5. valida pelo outro;
6. mapeia LAPIC MMIO explicitamente;
7. lê LAPIC ID.

Isso testa aliases de RAM e mapping de device memory.

## Fase I: heap, SSE e processos

A sequência:

~~~text
heap_init
sse_bsp_init
heap_selftest
proc_init
~~~

acontece somente depois de PMM e MM funcionarem.

## Fase J: graphics

ChrisOS usa o framebuffer fornecido pelo Limine, com address, width, height, pitch e 32 bpp.

Depois tenta virtio_gpu_boot como caminho adicional.

## Primeiro frame intencional

O kernel limpa com:

~~~text
0x00101828
~~~

e apresenta.

Esse é o primeiro estado gráfico deliberado da sequência atual depois do gfx_init.

## Fase K: APIC, jobs e SMP

A sequência é:

~~~text
apic_init
ioapic_init
job_init
smp_init
smp_job_selftest
~~~

Isso ocorre após memory management estar operacional.

## IOAPIC ainda não está completo

ioapic_init apenas registra que o PIC continua roteando IRQs.

Full IOAPIC routing ainda não é implementado por essa função.

O nome do init não deve ser interpretado como feature concluída.

## SMP ainda usa raw MP response

smp_init consome o MP response retornado por bootinfo_mp_response.

Esse conteúdo continua em bootloader-owned memory.

Uma BootSnapshot futura deve copiar a topologia necessária.

## Fase L: CLI e subsistemas

Depois do SMP self-test, kstart executa CLI e inicializa:

~~~text
ACPI
storage
filesystem
installer
language runtime
audio
AC97
compiler preparation
~~~

O source explica que compiler preparation deve ocorrer sem timer preemption.

## ACPI depois de MM

acpi_probe só ocorre quando primitives de virtual memory e MMIO já existem.

Isso é particularmente importante com HHDM restritivo da revision 3.

## Storage e filesystem

storage_init e fs_init vêm antes dos testes/automação do installer.

Quando CFS está ativo, o kernel persiste o log em:

~~~text
SYS/BOOT.LOG
~~~

A observabilidade de boot passa a sobreviver ao runtime.

## Language runtime

lang_init prepara o subsistema de linguagens.

lang_make_cc ocorre ainda com interrupts off.

## Fase M: STI final

Perto do fim:

~~~text
STI
~~~

habilita maskable interrupts no BSP.

É a transição entre boot serializado e runtime assíncrono.

Nesse ponto já existem:

- GDT própria;
- IDT própria;
- syscall gate;
- IRQ handlers;
- PIT;
- PMM/MM;
- heap;
- process layer;
- graphics;
- APIC/SMP;
- filesystem;
- language runtime.

## AP interrupt release

Logo depois:

~~~text
smp_release_ap_irqs
~~~

libera AP workers para participação na política de interrupts.

CPU online e interrupt-enabled não são o mesmo milestone.

## Desktop

O final é:

~~~text
desktop_init
desktop_boot_apps
gfx_present
optional net_init
desktop marker
desktop_run
~~~

desktop_run é o loop persistente e uma fronteira prática de boot concluído.

## Networking é opcional

net_init pode falhar sem derrubar o boot.

O desktop continua.

## Ordem atual completa

~~~text
serial_init
build_info_log

bootinfo_init
boot flags

gdt_init
idt_init
syscall_init
pic_init
pit_init
ps2_init

pmm_init
pmm_selftest
mm_init
mm_selftest
heap_init
sse_bsp_init
heap_selftest
proc_init

gfx_init
virtio_gpu_boot
gfx_clear
gfx_present

apic_init
ioapic_init
job_init
smp_init
smp_job_selftest

CLI
acpi_probe
storage_init
fs_init
install_selftest
install_auto
persistent boot log
lang_init
speaker_off
optional ac97_init

gfx_clear
gfx_present
lang_make_cc

STI
smp_release_ap_irqs
desktop_init
desktop_boot_apps
gfx_present
optional net_init
desktop_run
~~~

O checker desta rodada fixa os principais anchors diretamente a partir de start.c.

## Dependency graph

~~~text
bootinfo_init
    -> pmm_init
    -> mm_init
    -> heap_init
    -> proc_init

gdt_init
    -> idt_init
    -> syscall_init

pic_init
    -> pit_init

mm_init
    -> explicit MMIO
    -> APIC/SMP

job_init
    -> smp_init

fs_init
    -> persistent boot log

lang_init
    -> lang_make_cc

runtime initialization
    -> STI
~~~

## Estado emprestado na entrada

| Recurso | Owner inicial | Ação atual |
|---|---|---|
| GDT | Limine | substituída por gdt_init |
| stack inicial | Limine | inicialmente mantida |
| page tables / CR3 | Limine | adotadas por mm_init |
| HHDM | Limine | usado pelo kernel |
| framebuffer mapping | Limine | usado pelo graphics |
| memory-map response | Limine | referenciado após normalização |
| MP response | Limine | usado pelo SMP |

Isso explica a reserva conservadora de bootloader-reclaimable.

## Transição da GDT

~~~text
GDT Limine
    ↓
gdt_init
    ↓
GDT ChrisOS
    ↓
reload de selectors
    ↓
TSS loaded
~~~

Essa transição de ownership é relativamente completa.

## Transição da IDT

~~~text
IDT undefined na entrada
    ↓
idt_init
    ↓
ChrisOS controla vectors 0..255
~~~

É uma das fronteiras mais nítidas do boot.

## Transição de stack incompleta

linker.ld reserva 1 MiB e gdt_init usa __stack_top em TSS.RSP0.

Mas start.c não muda explicitamente o RSP do BSP para __stack_top.

Logo TSS stack e current BSP stack não devem ser tratadas como a mesma coisa.

## Transição de page tables incompleta

Hoje:

~~~text
Limine cria CR3
    ↓
mm_init lê
    ↓
ChrisOS modifica
~~~

Não há ainda:

~~~text
nova root própria
switch CR3
liberação da root herdada
~~~

As page tables são adotadas.

## Transição de bootinfo incompleta

Scalars são copiados, mas raw memory-map e MP responses continuam referenciados.

Uma BootSnapshot completa precisa realizar deep-copy.

## Três gaps principais de ownership

~~~text
stack
    borrowed -> kernel-owned

page tables
    adopted -> kernel-owned

boot responses
    borrowed -> deep-copied snapshot
~~~

Fechar esses pontos tornaria muito mais bootloader-reclaimable memory realmente liberável.

## Hardening de IDT cedo

serial, build log, bootinfo e GDT rodam antes de idt_init.

Uma evolução possível é instalar emergency IDT mínima imediatamente na entrada.

Isso não existe hoje.

## Hardening de stack cedo

Outra melhoria é trocar o BSP para stack própria do kernel logo no início.

Isso encurta a dependência de memória do bootloader.

O source atual não faz esse switch explicitamente.

## Modernização de base revision

A especificação atual do Limine considera revision 3 deprecated.

Migrar não é apenas mudar um número.

As guarantees de entry state, HHDM, firmware tables e reclaim precisam ser revisadas em conjunto.

## Convergência BIOS/UEFI

Antes do Limine, BIOS e UEFI são diferentes.

Depois do handoff:

~~~text
mesmo kernel ELF
mesma request section
mesmo kstart
mesmo bootinfo_init
mesma sequência de subsistemas
~~~

Essa normalização é uma vantagem central do boot protocol.

## ChrisVM precisa reproduzir o handoff

ChrisVM v1 executa um contrato guest mais simples e low-address, mas rejeita o kernel higher-half real.

Uma versão futura precisa reproduzir estado suficiente para o mesmo kstart executar sem atalhos específicos do emulator.

## Contrato mínimo para ChrisVM

Precisa existir:

- higher-half PT_LOAD;
- long mode;
- initial stack válida;
- GDT adequada;
- comportamento seguro antes da IDT própria;
- HHDM ou abstração equivalente;
- memory map;
- framebuffer;
- MP metadata;
- command line;
- CR3 correto;
- semântica equivalente de requests/responses.

Forçar RIP para kstart não basta.

## Classes de falha por estágio

Antes da serial: hang, reset, triple fault e nenhuma mensagem.

Depois da serial mas antes da IDT: último marker serial pode localizar o ponto, mas ainda sem panic confiável.

Depois da IDT: exceptions podem produzir diagnóstico controlado.

Depois de PMM/MM: self-tests ajudam a isolar allocation/translation.

Depois de filesystem: boot logs podem ser persistidos.

## Boot markers estáveis

Uma evolução útil é formalizar markers como:

~~~text
entry
serial-ok
bootinfo-ok
gdt-ok
idt-ok
pmm-ok
mm-ok
heap-ok
gfx-ok
smp-ok
fs-ok
runtime-ok
desktop
~~~

O source já possui muitos logs, mas ainda não um protocolo formal de milestones.

Isso seria útil em QEMU, ChrisVM e hardware real.

## Checker reproduzível

scripts/check_power_on_kstart_examples.py valida:

1. ENTRY(kstart);
2. Limine base revision 3;
3. ordem dos request delimiters;
4. validação das responses obrigatórias;
5. ordering crítico de start.c;
6. gdt_init antes de idt_init;
7. idt_init antes de syscall_init;
8. pic_init antes de pit_init;
9. PMM antes de MM;
10. MM antes de heap/process/SMP;
11. CLI antes da fase ACPI/storage/lang;
12. lang_make_cc antes de STI;
13. STI antes do desktop;
14. PIC em 0x20/0x28;
15. pit_init(60);
16. adoption de CR3;
17. TSS.RSP0 = __stack_top;
18. ausência de switch explícito de RSP BSP;
19. IOAPIC ainda stub;
20. ChrisVM v1 rejeitando o higher-half ELF real.

O checker valida source contracts, não substitui boot em hardware.

## Findings atuais

~~~text
Limine base revision
    3

BSP stack inicial
    bootloader-reclaimable

GDT inicial
    bootloader-reclaimable

IDT inicial
    undefined pela revision 3

CR3 inicial
    hierarchy do Limine

GDT ChrisOS
    instalada cedo

IDT ChrisOS
    depois de serial + bootinfo + GDT

PMM
    mantém bootloader-reclaimable reservado

MM
    adota CR3 herdado

BSP interrupts
    STI apenas perto do fim

IOAPIC
    routing incompleto

desktop_run
    destino steady-state
~~~

## Timeline de ownership

~~~text
RESET
  firmware controla a máquina
        ↓

LIMINE
  bootloader possui:
    page tables
    stack
    GDT
    responses
        ↓

KSTART EARLY
  serial
  bootinfo
  GDT ChrisOS
  IDT ChrisOS
        ↓

MEMORY
  PMM assume allocator state
  MM adota CR3 Limine
        ↓

RUNTIME BUILD
  heap/process/graphics/SMP/fs/lang
        ↓

STI
  runtime assíncrono
        ↓

DESKTOP
~~~

## Limite de validação

Capítulo reconciliado com:

~~~text
ChrisOS main
da3df29cb397932c43d32373871fb9380e688ade
~~~

e com a especificação atual do Limine.

Como o ChrisOS pede base revision 3, guarantees exclusivas de revisions posteriores não são tratadas como facts atuais.

Execute:

~~~text
python scripts/check_power_on_kstart_examples.py --source .source
~~~

## Gatilhos de revisão

Revisar quando:

- kstart mudar de ordem;
- Limine base revision mudar;
- requests mudarem;
- emergency IDT for adicionada;
- BSP trocar cedo para stack própria;
- page tables do bootloader forem substituídas;
- BootSnapshot virar deep-copy;
- PIC/PIT mudarem;
- IOAPIC ficar completo;
- SMP release mudar;
- interrupts forem habilitados antes;
- ChrisVM ganhar handoff higher-half equivalente;
- ChrisCPU/ChrisHV bootarem o kernel real via kstart.

## Referências primárias

- Limine boot protocol, especificação atual.
- AMD64 architecture documentation.
- Sources ChrisOS listados no front matter.
