---
id: bringup-diagnostics
lang: pt-br
type: technical-chapter
volume: 13-real-hardware
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/start.c
  - kernel/metal/serial.c
  - kernel/metal/klog.c
  - kernel/metal/panic.c
  - kernel/metal/buildid.c
  - kernel/metal/bootinfo.c
  - kernel/metal/smp.c
  - kernel/metal/acpi.c
  - kernel/fs/storage.c
  - tools/qemu_gate.py
  - scripts/qemu.mk
symbols:
  - kstart
  - serial_init
  - klog_copy
  - panic
  - panic_exception
  - build_info_log
  - bootinfo_init
  - smp_init
  - storage_init
depends_on:
  - hardware-profile
  - validation-evidence
related:
  - driver-compatibility
  - qemu-gates
  - hardware-gates
  - fault-injection
---

# Diagnóstico de bring-up e localização de falhas

## Escopo

Bring-up de hardware é o problema de localizar a primeira etapa cujas invariantes deixam de ser verdadeiras.

O ChrisOS já oferece mecanismos úteis:

- serial COM1 antes da maior parte do kernel;
- kernel log circular em memória;
- identidade de build, Git e hash do kernel;
- dump detalhado do handoff Limine;
- markers explícitos de subsistemas;
- registros de panic e exception;
- CPU, CR3 e RSP em falhas fatais;
- persistência do log inicial em ChrisFS;
- gates QEMU julgados por markers positivos e fatais.

A regra de diagnóstico é:

    registrar a última invariável confirmada
    investigar a próxima transição

em vez de tratar todo boot quebrado como uma única falha.

## Linha do tempo

A sequência prática é:

    firmware
      -> Limine
      -> kstart
      -> serial e build identity
      -> bootinfo
      -> GDT / IDT / syscall / PIC / PIT / PS2
      -> PMM / MM / heap / processos
      -> framebuffer
      -> APIC / SMP / jobs
      -> ACPI probe
      -> storage
      -> filesystem / installer
      -> runtime
      -> áudio
      -> desktop
      -> rede

O último marker serial observado reduz drasticamente o próximo componente a investigar.

## Estágio 0: firmware e loader

Se nenhum byte serial do ChrisOS aparece, causas possíveis incluem:

- UEFI não descobriu o disco;
- BOOTX64.EFI não foi iniciado;
- Secure Boot recusou a image;
- Limine não encontrou config/kernel;
- handoff do loader falhou;
- o kernel entrou, mas COM1 não está acessível.

Ausência de serial não prova isoladamente que o kernel nunca executou.

É necessário correlacionar com output do firmware/Limine ou outro canal precoce.

## Estágio 1: serial

kstart começa por:

    serial_init()

O driver configura COM1 em:

    0x3f8

e executa loopback gravando/lendo:

    0xae

Se esse teste falha, kstart executa cli e permanece em hlt.

O ChrisOS atual possui, portanto, uma dependência precoce forte de COM1 compatível.

Isso facilita diagnóstico em máquinas compatíveis, mas reduz compatibilidade em sistemas sem essa interface.

## Serial e klog

Cada serial_putc grava primeiro no klog.

Se o UART está disponível, transmite depois para COM1.

Assim, o log em memória espelha o output textual serial depois da inicialização.

## Stall na transmissão

O path de transmissão espera o bit transmitter-ready sem timeout.

Um UART que passe o loopback e depois deixe de reportar ready pode travar o kernel dentro do próprio logging.

Logo, um hang logo após um marker não prova que o próximo subsistema é o culpado.

## Identidade do build

Após serial, kstart emite:

    ChrisOS selfhost=1

e build_info_log registra:

- Build ID;
- revisão Git;
- data;
- compiler;
- SHA-256 do kernel linkado.

Todo resultado de hardware deve preservar esse bloco.

Sem identidade da image, o log não pode ser relacionado com segurança ao source.

## Hash do kernel

A image contém um stamp CHRISOSHASH populado com SHA-256 do kernel linkado.

Panic também imprime esse hash.

Isso fornece provenance mais forte que version string manual.

## Estágio 2: bootinfo

bootinfo_init valida respostas do Limine.

Faz panic se faltar:

- framebuffer;
- HHDM;
- memory map;
- MP response.

Também rejeita CPU topology vazia e framebuffer diferente de 32 bpp.

Qualquer boot que passa desse ponto já provou um contrato considerável entre firmware, loader e kernel.

## Output de bootinfo

A inicialização bem-sucedida registra:

    ChrisOS: bootinfo revision 3
    HHDM offset=...
    fb WIDTHxHEIGHT pitch=... bpp=... addr=...
    mmap[...] type=... base=... len=...
    usable_bytes=...
    memmap_entries=...
    cpu_count=...
    bsp_lapic_id=...

Esse bloco deve ser a primeira evidência importante de um teste físico.

Ele mostra o que o kernel realmente recebeu.

## Memory map

O dump detalhado ajuda a encontrar:

- holes reservados;
- regiões ACPI;
- framebuffer;
- bootloader reclaimable;
- memória incorretamente marcada USABLE.

O kernel também verifica a área física de LAPIC para não tratá-la como RAM normal.

## Estágio 3: arquitetura inicial

Depois de bootinfo são inicializados:

- GDT;
- IDT;
- syscall;
- PIC;
- PIT.

PIT a 60 Hz é obrigatório.

Falha após bootinfo e antes dos markers de memória/device deve concentrar investigação nessa transição.

## Contrato de panic

panic imprime:

    PANIC: MESSAGE

e:

- CPU atual;
- CR3;
- RSP;
- Build ID;
- Git;
- SHA-256.

panic_exception acrescenta:

- vector;
- error code;
- RIP;
- CR2.

É um registro fatal compacto e preso à revisão.

## CR2

CR2 é principalmente significativo para page fault.

Em outras exceptions pode conter endereço antigo.

Deve ser interpretado junto com o vector.

## RIP e symbols

RIP precisa ser resolvido contra a mesma image identificada pelo panic.

Usar symbols de outra build pode gerar diagnóstico convincente e errado.

## Estágio 4: PS/2

Falha de PS/2 não é fatal.

O kernel registra:

    ChrisOS: PS/2 unavailable (keyboard/mouse disabled)

e continua.

Isso é degradação opcional, não falha da plataforma.

## Estágio 5: memória

O kernel inicializa e testa:

- PMM;
- virtual memory;
- heap.

A policy dos gates considera markers como:

    PMM corruption
    heap corruption

fatais.

Quando corrupção de memória já foi detectada, sintomas posteriores de storage ou graphics devem ser tratados como secundários.

## Estágio 6: framebuffer

Depois da memória, kstart inicializa graphics usando o framebuffer.

Contrato incompatível leva a panic.

O relatório físico deve guardar:

- address;
- width;
- height;
- pitch;
- bpp.

Pitch não precisa ser width vezes quatro.

## Estágio 7: VirtIO GPU opcional

virtio_gpu_boot é chamado depois do framebuffer.

O framebuffer continua sendo o base path.

Ausência de VirtIO GPU em bare metal não é falha central.

## Estágio 8: SMP

O caminho SMP emite:

    cpu_online_count=N (BSP+AP)

ou:

    smp off

Uma máquina que chega ao desktop apenas com nosmp ou safe já fornece boa localização da falha.

O caminho BSP funciona; o problema está em SMP/APIC ou em outra feature desabilitada por safe mode.

## APs parciais

smp_init aguarda APs até um limite de spins e depois registra o número observado.

Valor menor que a topologia esperada é evidência de startup parcial.

Topologia esperada e cpu_online_count observado devem ser preservados.

## Safe mode como teste diferencial

safe desabilita:

- SMP;
- APIC;
- AC97;
- rede;
- JIT.

Se normal falha e safe funciona, reative uma categoria por vez.

Alterar várias dimensões simultaneamente destrói causalidade.

## Estágio 9: ACPI

O probe pode emitir:

    acpi rsdp oem=...
    acpi xsdt
    acpi APIC
    acpi MCFG
    acpi FACP

ou:

    acpi rsdp missing

O probe é diagnóstico e ausência de RSDP não produz panic.

Esse marker deve ser registrado como limitação de discovery, não automaticamente como causa da próxima falha.

## Estágio 10: storage

storage_init atravessa:

- PCI discovery;
- controller init;
- block I/O;
- device registration;
- partition discovery;
- root selection;
- ChrisFS.

Essa etapa precisa ser analisada em subcamadas.

## Root e filesystem

Root selecionada produz:

    root DEVICE

Mount bem-sucedido produz:

    cfs mounted

São invariantes diferentes.

Controller e root podem funcionar enquanto filesystem mount falha.

## Classes de falha de storage

Classificação útil:

1. controller não descoberto;
2. controller encontrado, init falha;
3. block device registrado, I/O falha;
4. root não encontrada;
5. GPT/partition falha;
6. superblock ChrisFS inválido;
7. mount falha;
8. filesystem corrompe depois.

Isso é muito mais informativo que "disco não funciona".

## Diagnóstico destrutivo

Testes físicos não devem fazer writes especulativos em discos valiosos.

Use mídia descartável, clone ou target dedicado.

Um modo futuro de discovery read-only é prioridade alta.

## Boot log persistido

Depois que ChrisFS está disponível, kstart copia klog para:

    SYS/BOOT.LOG

A capacidade do ring é:

    8192 bytes

O kernel registra:

    boot log SYS/BOOT.LOG

ou:

    boot log write failed

Isso fornece artifact pós-boot quando não houve captura serial externa.

## Semântica do ring

klog guarda os 8192 bytes mais recentes.

Após wrap, os mais antigos desaparecem.

Para evidência completa, serial externo continua preferível.

## Estágio 11: runtime/JIT

Depois de storage entra o runtime.

A flag nojit separa falhas do JIT do restante.

Uma máquina que monta ChrisFS e só falha com JIT habilitado já possui uma superfície de investigação muito menor.

## Estágio 12: áudio

AC97 é opcional.

noac97 oferece isolamento direto.

Falha de áudio moderno não deve classificar a máquina como incapaz de bootar.

## Estágio 13: desktop

Mais tarde kstart habilita interrupts e inicializa o desktop.

O marker principal é:

    ChrisOS: desktop 60Hz

É o marker de whole-system mais usado nos gates atuais.

Não prova devices opcionais.

## Estágio 14: rede

Rede é inicializada depois do desktop.

Falha registra:

    ChrisOS: net unavailable

e o sistema continua.

Como o path atual é VirtIO, isso é esperado na maioria das máquinas físicas.

## Filosofia dos gates

tools/qemu_gate.py julga boot por evidência explícita.

Ele:

- roda QEMU com timeout;
- lê serial;
- rejeita exits inesperados;
- rejeita fatal markers;
- exige cada positive marker.

Gate físico deve seguir a mesma lógica.

Tempo decorrido sozinho não é sucesso.

## Fatal markers

A policy atual considera strings como:

    PANIC:
    EXCEPTION vector=
    double fault
    general protection
    heap corruption
    PMM corruption

fatais.

Automação física deve ter vocabulário equivalente.

## Markers positivos por escopo

Exemplos:

    bootinfo:
        ChrisOS: bootinfo revision 3

    SMP:
        cpu_online_count=4

    storage:
        root ahci
        cfs mounted

    xHCI:
        xhci hid ready

    desktop:
        ChrisOS: desktop 60Hz

O marker esperado precisa provar o subsistema sob teste.

## Método do último marker

Se o log termina em:

    cpu_online_count=4 (BSP+AP)

e não mostra storage, já estão confirmados:

- kernel entry;
- serial;
- build identity;
- bootinfo;
- memória;
- framebuffer;
- SMP.

A investigação começa na transição ACPI/storage, não em UEFI ou linker.

## Ordem dos markers

A ordem importa.

Um parser futuro deve tratar boot como state machine e associar markers ao mesmo build/session.

Isso evita misturar registros de dois reboots.

## Identidade da sessão

Uma chave útil é:

    Git revision
    Build ID
    kernel SHA-256

O banco de hardware deve armazenar esse trio com machine identity e flags.

## Informação fatal ainda ausente

Panic ainda não registra:

- todos GPRs;
- RFLAGS;
- segments;
- APIC state;
- stack trace;
- page-table walk para #PF.

São melhorias de alto valor.

CR3/RSP/RIP/CR2 já ajudam, mas não resolvem faults complexos.

## Sem stack unwinder

Não há unwinder geral no panic path revisado.

Um unwinder confiável precisa de symbols exatos, memory reads seguros e estratégia estável.

Enquanto isso, RIP preso à revisão e stage markers explícitos são evidência mais segura.

## Registro estruturado

Um artifact futuro deve conter:

    machine:
        vendor/model
        firmware/version

    build:
        git
        build_id
        kernel_sha256

    boot:
        command_line
        secure_boot_state

    bootinfo:
        framebuffer
        cpu_count
        memory_map_summary

    devices:
        pci ids
        storage
        input

    markers:
        ordered list

    fatal:
        vector/error/rip/cr2/cr3/rsp

    result:
        last_successful_stage

Isso é muito mais útil que "travou nessa tela".

## Máquinas sem COM1

Sistemas sem legacy COM1 são hoje targets ruins para diagnóstico porque falha em serial_init interrompe kstart.

Roadmap físico deve adicionar outro early channel:

- text console no framebuffer;
- debug port;
- USB debug;
- crash record recuperável.

Até lá, serial acessível é característica importante de uma primeira máquina de desenvolvimento.

## Flags para feature bisect

Flags úteis:

- safe;
- nosmp;
- noapic;
- noac97;
- nonet;
- nojit;
- gfx.backend=framebuffer;
- gfx.3d=software;
- gfx.3d=virgl;
- gfx.3d=auto.

Mude uma dimensão por experimento.

## Procedimento reproduzível

Para uma falha física:

1. identificar máquina/controller;
2. registrar build identity;
3. capturar serial completo;
4. repetir boot normal;
5. repetir safe;
6. reduzir diferença a uma feature;
7. reproduzir ao menos duas vezes;
8. registrar último marker;
9. corrigir apenas o subsistema suspeito;
10. repetir o mesmo teste com nova build.

Isso gera evidência adequada para regression gate.

## Converter fix em hardware gate

Após corrigir uma falha física, defina gate repetível com:

- reset/power action;
- image;
- serial capture;
- timeout;
- positive markers;
- fatal markers;
- reboot quando relevante;
- artifacts retidos.

Um sucesso pontual vira capacidade permanente do projeto.

## Melhorias prioritárias

Próximos passos de maior valor:

1. não hard-halt quando COM1 faltar; fornecer early console alternativo;
2. timeout/error handling na transmissão serial;
3. stage IDs machine-readable em torno dos principais passos de kstart;
4. dump completo de GPRs/RFLAGS no panic;
5. page-table diagnostics em #PF;
6. build identity em todo artifact;
7. klog maior/configurável;
8. modo read-only de hardware discovery;
9. export sistemático de PCI vendor/device/BAR/IRQ;
10. summaries estruturados de BootInfo/ACPI;
11. transformar máquinas físicas validadas em hardware gates.

## Classificação atual

Na revisão analisada:

    logging COM1 precoce             implementado
    klog circular                    implementado
    identidade build/git/hash        implementado
    bootinfo detalhado               implementado
    panic RIP/CR2/CR3/RSP            implementado
    SYS/BOOT.LOG                     implementado após ChrisFS
    validação QEMU por markers       implementada
    safe mode diferencial            implementado
    hardware gate automatizado       não estabelecido
    early console sem serial         não implementado
    panic full-register              não implementado
    stack unwinder                   não implementado
    hardware record estruturado      não implementado

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, o ChrisOS já possui base séria para bring-up: serial começa na primeira etapa do kernel, identidade de build aparece no log, bootinfo é detalhado, fatal exceptions preservam contexto arquitetural central, output é copiado para ring de 8 KiB e depois persistido em ChrisFS, e gates QEMU usam markers positivos/fatais. A maior fraqueza física é a dependência rígida de legacy COM1 e a ausência de um pipeline estruturado de evidência/hardware gate.
