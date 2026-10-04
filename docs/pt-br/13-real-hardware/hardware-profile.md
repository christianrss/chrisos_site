---
id: hardware-profile
lang: pt-br
type: technical-chapter
volume: 13-real-hardware
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/start.c
  - kernel/metal/bootinfo.c
  - kernel/metal/pci.c
  - kernel/metal/ps2.c
  - kernel/metal/acpi.c
  - kernel/metal/smp.c
  - kernel/fs/storage.c
  - kernel/fs/ata_pio.c
  - kernel/fs/ahci.c
  - kernel/fs/nvme.c
  - kernel/fs/virtio_blk.c
  - kernel/fs/usb_msc.c
  - kernel/fs/xhci.c
  - kernel/gfx/graphics.c
  - kernel/gfx/vgpu.c
  - kernel/gfx/ac97.c
  - kernel/net/virtio_net.c
  - SYS/DRV/HWDISC.CC
  - scripts/qemu.mk
symbols:
  - kstart
  - bootinfo_init
  - storage_init
  - ps2_init
  - smp_init
  - virtio_gpu_boot
  - ac97_init
  - xhci_hid_probe
  - virtio_net_init
depends_on:
  - uefi-disk-boot
  - installation-real-hardware
  - x86-64-memory-privilege
related:
  - bringup-diagnostics
  - driver-compatibility
  - qemu-gates
  - hardware-gates
---

# Perfil de hardware do ChrisOS e fronteira de evidência

## Escopo

O ChrisOS possui drivers x86-64 nativos suficientes para definir um alvo de hardware significativo, mas a existência de um driver não equivale a suporte comprovado em hardware físico.

Este capítulo define o perfil atual como um **modelo de evidência**, não como uma lista comercial de compatibilidade.

Quatro estados precisam permanecer separados:

1. **implementado** — existe um caminho executável no código atual;
2. **testado no host** — algoritmos ou lógica relacionada são exercitados por host tests;
3. **validado em QEMU** — um gate QEMU alcança markers explícitos com um device modelado;
4. **validado em hardware físico** — o mesmo caminho foi reproduzido em uma máquina/controlador/device real identificado e com evidência registrada.

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, boa parte da plataforma prática está implementada e validada em QEMU.

Ainda não existe uma matriz geral de compatibilidade física.

Essa distinção é a principal regra deste capítulo.

## Alvo prático atual

O alvo físico mais estreito e defensável para bring-up é aproximadamente:

    máquina x86-64
    firmware UEFI
    Secure Boot desabilitado
    boot via Limine
    framebuffer de firmware 32 bpp
    premissas convencionais de PC para serial/PIT/PIC
    um controller de storage alcançável pela descoberta atual
    setores lógicos de 512 bytes
    input por PS/2 ou xHCI HID atualmente suportado
    rede opcional
    áudio opcional

Esse é um **perfil candidato de bring-up**, não uma promessa de que qualquer máquina com esses rótulos irá bootar.

Topologia PCI, firmware, roteamento de interrupts, ACPI, framebuffer e detalhes do controller ainda variam entre sistemas reais.

## Níveis de evidência

### Nível 0 — caminho no source

Um subsistema é Nível 0 quando existe implementação concreta.

Exemplos:

- AHCI;
- NVMe;
- ATA PIO;
- VirtIO block;
- USB mass storage;
- xHCI HID;
- PS/2;
- VirtIO GPU;
- AC97;
- VirtIO network.

Isso prova que o código existe.

Não prova que ele executou corretamente em emulação ou hardware.

### Nível 1 — teste host/determinístico

Host tests podem validar:

- estruturas;
- encoding de protocolos;
- aritmética;
- formatos de filesystem;
- queues;
- parsers;
- invariantes de state machine.

É evidência superior à simples leitura de source, mas ainda não prova comunicação com um controller real.

### Nível 2 — gate de hardware virtual

Um gate QEMU prova que um driver conversa com um device modelado dentro de topologia conhecida.

Hoje há gates para classes como:

- ATA;
- AHCI;
- NVMe;
- VirtIO block;
- USB mass storage;
- xHCI HID;
- VirtIO GPU;
- SMP;
- instalação e reboot UEFI pelo disco.

Isso é evidência de integração.

Não estabelece compatibilidade física.

### Nível 3 — registro de hardware físico

Um caminho só chega a Nível 3 quando o projeto registra ao menos:

- modelo da máquina/placa-mãe;
- vendor/versão do firmware;
- IDs PCI;
- modo do controller;
- modelo do disco/input/device;
- revisão do ChrisOS;
- configuração de boot;
- log serial/boot;
- marker esperado;
- resultado repetido/reboot.

Sem isso, "funciona em hardware" continua sendo evidência anedótica.

## Arquitetura de CPU

O kernel principal é x86-64.

bootinfo exige respostas Limine para:

- framebuffer;
- HHDM;
- memory map;
- multiprocessor.

O kernel começa em ambiente 64-bit já estabelecido pelo loader.

Portanto, o perfil atual é melhor descrito como:

    x86-64 + handoff Limine

e não genericamente como "qualquer PC x86".

## Multiprocessamento

ChrisOS possui SMP baseado na resposta MP do Limine.

O kernel mantém:

    cpu_online_count

e cria stacks dedicadas para APs.

Os limites atuais incluem:

    SMP_MAX_APS = 8
    SMP_CPU_CAP = 16

O loop de inicialização interrompe quando o próximo índice alcança SMP_MAX_APS.

Isso não implica escalabilidade arbitrária de CPU count.

## Evidência SMP em QEMU

O gate padrão usa:

    QEMU_SMP = 4

e exige:

    cpu_online_count=4

Isso é evidência real de SMP dentro de QEMU.

Não prova AP startup, roteamento APIC ou TLB shootdown em todos os sistemas multiprocessados físicos.

## Safe mode

O token de boot:

    safe

ativa:

- nosmp;
- noapic;
- noac97;
- nonet;
- nojit.

O gate de safe mode exige:

    safe mode
    smp off
    desktop 60Hz

Esse modo é particularmente útil em hardware físico porque reduz subsistemas opcionais e áreas de alta variabilidade.

Primeiros boots físicos devem manter safe mode disponível como fallback de diagnóstico.

## Perfil de firmware

O caminho de disco instalado mais forte é UEFI.

O instalador grava BOOTX64.EFI e o disco resultante boota em OVMF.

A compatibilidade física ainda depende de:

- drivers de storage do firmware;
- aceitação GPT/ESP;
- policy de fallback;
- framebuffer;
- Secure Boot.

Não há cadeia Secure Boot atual.

## Dependência do Limine

Limine faz parte do contrato atual.

O kernel consome diretamente requests revision 3 para:

- framebuffer;
- HHDM;
- memory map;
- multiprocessamento;
- command line.

O hardware profile atual, portanto, depende do comportamento de handoff do Limine.

## Framebuffer obrigatório

Framebuffer é obrigatório no boot normal.

bootinfo_init chama panic quando não existe framebuffer ou quando não é 32 bpp.

kstart também recusa:

    boot->fb_bpp != 32

Logo, um candidato físico precisa de um caminho firmware/bootloader que entregue framebuffer 32-bpp utilizável.

## GPU física

O baseline de display é framebuffer linear fornecido pelo firmware.

ChrisOS possui VirtIO GPU e VirGL, mas são devices voltados a virtualização e validados em ambientes QEMU.

Não existe driver geral físico para GPUs Intel/AMD/NVIDIA no kernel revisado.

A classificação correta é:

    framebuffer de firmware = baseline físico candidato
    VirtIO GPU/VirGL        = caminho virtualizado
    GPU física moderna      = não estabelecida

## Resolução gráfica

A configuração Limine solicita:

    1920x1080x32

mas firmware pode entregar outro modo utilizável.

O requisito real é:

- framebuffer Limine;
- 32 bpp;
- width/height válidos;
- pitch válido;
- memória acessível pelo handoff.

O hardware record deve guardar o modo realmente entregue.

## Configuração PCI

O acesso PCI genérico atual usa configuration mechanism #1:

    0xCF8
    0xCFC

Isso funciona em PCs convencionais que expõem esse mecanismo.

Não equivale a implementação PCIe ECAM completa.

O probe ACPI pode encontrar assinatura MCFG, mas a camada PCI revisada não usa MCFG para enumeration.

Isso limita portabilidade.

## Limites de topologia PCI

A policy de discovery varia entre subsistemas.

Alguns helpers em kernel/metal/pci.c examinam apenas:

    bus 0
    slots 0..31
    functions 0..7

Drivers mais novos de storage/GPU examinam:

    buses 0..7
    devices 0..31
    functions 0..7

Não há bridge traversal genérico e recursivo para encontrar qualquer downstream PCIe bus.

Assim, uma classe implementada pode continuar invisível atrás de bridge/topologia não varrida.

Esse é um dos maiores limites de hardware físico atual.

## Aplicação HWDISC

SYS/DRV/HWDISC.CC fornece uma visão simples de PCI.

Classifica:

- IDE/ATA;
- AHCI/SATA;
- NVMe;
- USB;
- display;
- network;
- audio.

Também testa BARs selecionados para AHCI/NVMe e reconhece alguns IDs VirtIO.

Mas o app examina bus 0 e function 0 por slot.

É útil para diagnóstico, não como enumerador PCI completo.

## Perfil de storage

A camada de storage tenta:

- ATA PIO;
- AHCI;
- NVMe;
- VirtIO block;
- USB mass storage.

Isso torna storage a área de hardware mais ampla da implementação e também a mais coberta por gates QEMU.

## ATA PIO

ATA PIO atende comportamento IDE legado.

É útil em VMs simples e máquinas antigas.

Sistemas modernos podem não expor IDE legado.

Deve ser visto como caminho de compatibilidade, não alvo físico moderno preferencial.

## AHCI

AHCI é um dos melhores candidatos para primeira validação SATA física.

Existe gate QEMU que exige:

    ahci disk sectors=
    bdev rw ok ahci

O teste de instalação também grava target em controller AHCI modelado.

Ainda é necessário registrar controladores SATA reais antes de declarar suporte físico.

## NVMe

O driver NVMe existe e possui gate QEMU:

    nvme disk sectors=
    bdev rw ok nvme

O modelo atual espera setores lógicos de 512 bytes.

Namespaces incompatíveis com essa premissa são rejeitados.

Um NVMe físico em formato LBA 512-byte é um candidato plausível, porém ainda precisa de validação por controller/device.

## Tamanho de setor

Filesystem, block layer e installer são centrados em:

    512-byte logical sectors

Discos somente 4Kn ficam fora do perfil atual validado.

O physical sector interno pode ser diferente; o que importa ao contrato atual é o logical block size visto pelo driver.

## Capacidade

sector_count do BlockDevice é 32-bit.

Com setores de 512 bytes, isso coloca o modelo prático próximo de 2 TiB.

Não se deve assumir que drives maiores são suportados só porque GPT consegue representar LBAs maiores.

A block layer precisa evoluir antes dessa claim.

## VirtIO block

VirtIO block é implementado e validado em QEMU.

Não é um controller físico típico de PC bare metal.

Sua existência aumenta cobertura sob hypervisors, não a matriz de storage físico.

## USB mass storage

Existe USB mass-storage e gate QEMU.

Isso demonstra o caminho contra um ambiente USB modelado.

Compatibilidade física depende também de host controller, hubs e comportamento concreto do dispositivo.

Ainda não é certificação de pendrives em geral.

## xHCI HID

Há probe/poll para HID sobre xHCI.

O gate QEMU exige:

    xhci hid ready

com teclado e mouse USB no controller xHCI virtual.

É progresso importante para PCs modernos, mas um modelo QEMU é muito mais estreito que a diversidade real de chipsets xHCI.

## PS/2

O caminho PS/2 implementa sequência do controller estilo 8042 e inicialização de teclado/mouse.

Quando falha, o ChrisOS registra:

    PS/2 unavailable (keyboard/mouse disabled)

e continua o boot.

PS/2 não é requisito absoluto do kernel.

Ainda é um fallback útil em máquinas que o expõem.

## Matriz de input

O estado atual pode ser classificado como:

    teclado/mouse PS/2     implementado
    xHCI HID               implementado + gate QEMU
    USB tablet QEMU        helper virtualizado
    USB HID genérico       não estabelecido
    Bluetooth              fora do baseline
    touchpad específico    não estabelecido

Uma máquina física precisa de pelo menos um input path funcional para validação interativa do desktop.

## Rede

A inicialização de rede revisada chama:

    virtio_net_init()

e falha graciosamente quando não existe.

Portanto, o caminho implementado de rede é VirtIO.

Não há conjunto geral de drivers físicos para NICs comuns como:

- Intel e1000/e1000e/igc;
- Realtek RTL81xx;
- Intel ixgbe;
- Broadcom;
- Wi-Fi.

Rede deve ser considerada **opcional e normalmente indisponível em bare metal** no perfil atual.

O boot flag:

    nonet

desativa rede.

## Áudio

ChrisOS possui:

- PC speaker;
- AC97.

AC97 procura PCI multimedia audio com BARs I/O e é opcional no boot.

O flag:

    noac97

desativa o caminho.

A maioria dos PCs atuais usa Intel HD Audio ou outros controllers/codecs.

Não há HDA geral no baseline.

Áudio não deve ser requisito para bring-up físico.

## Arquitetura de interrupts

O kernel inicializa:

- PIC;
- PIT;
- código de local APIC;
- camada IOAPIC;
- SMP.

Existem fallback flags:

    noapic
    nosmp

e safe mode ativa ambos.

Isso mostra que interrupt/topology permanece uma área sensível de bring-up.

Sucesso em QEMU não implica roteamento correto em qualquer placa-mãe.

## PIT

kstart exige:

    pit_init(60)

O desktop anuncia:

    desktop 60Hz

depois da inicialização.

O sistema atual possui, portanto, forte dependência do timer convencional de PC.

HPET/APIC timer pode ser uma evolução futura, mas o boot presente ainda depende de PIT.

## Estado de ACPI

O probe ACPI atual é diagnóstico, não uma platform layer completa.

Ele procura RSDP na região física:

    0xE0000 .. 0x100000

e reconhece no XSDT assinaturas como:

- APIC;
- MCFG;
- FACP.

Isso não equivale a consumir a UEFI configuration table nem a parsear AML.

Firmware físico que não exponha RSDP conforme as premissas atuais pode parecer sem ACPI mesmo sendo válido.

## Gap MCFG

O probe pode registrar MCFG, mas enumeration PCI ainda usa CF8/CFC.

Assim, encontrar MCFG não amplia a topologia PCIe acessível hoje.

Um milestone físico importante é conectar MCFG a ECAM real.

## SMP e APIC

SMP usa informação MP do Limine.

O código mantém LAPIC IDs e inicia APs por records do loader.

Local APIC e coordenação TLB se tornam mais críticos com CPUs adicionais.

Se uma máquina funciona em safe mode e falha com SMP, a evidência correta é:

    BSP-only funciona
    SMP falha

e não "hardware incompatível".

## Memória

O kernel consome memory map do Limine e soma regiões utilizáveis.

Não assume RAM totalmente contígua.

O map também traz categorias reserved, ACPI e framebuffer.

Mesmo assim, boot depende da interação correta do resto do kernel com o layout real.

Quantidade de RAM isoladamente não define compatibilidade.

## Handoff obrigatório

O kernel faz panic se faltar:

- framebuffer;
- HHDM;
- memory map;
- MP response.

Isso é um contrato mais forte que um boot mínimo text-only single CPU.

Validação física precisa verificar os quatro elementos.

## Perfil candidato para primeira máquina

Para um primeiro experimento real deliberado, o candidato de menor risco é:

    arquitetura:
        x86-64

    firmware:
        UEFI
        Secure Boot desabilitado
        sem dependência de CSM

    boot:
        Limine BOOTX64.EFI
        fallback disponível

    vídeo:
        framebuffer 32 bpp do firmware

    CPU:
        começar com safe/nosmp quando necessário

    storage:
        setores lógicos 512 bytes
        SATA AHCI simples ou NVMe previamente identificado
        capacidade dentro do limite atual

    input:
        PS/2 quando disponível
        caso contrário xHCI HID como candidato

    rede:
        desabilitada em bare metal

    áudio:
        desabilitado salvo teste AC97 deliberado

Isso é alvo de pesquisa/bring-up, não especificação certificada.

## Fora do perfil atual

Categorias de alto risco ou não suportadas:

- Secure Boot enforcement;
- storage apenas 4Kn;
- pressupor >2 TiB no block model atual;
- PCIe escondido atrás de bridges arbitrárias;
- sistemas que dependem de ECAM-only enumeration;
- GPU física moderna Intel/AMD/NVIDIA;
- NICs físicos comuns;
- Wi-Fi;
- Bluetooth;
- Intel HD Audio;
- USB hubs/controllers arbitrários;
- platform management dependente de ACPI/AML complexo;
- suspend/resume;
- bateria/power management;
- IOMMU/passthrough;
- hardware específico de laptops.

Uma máquina pode possuir esses componentes e ainda bootar se eles não forem essenciais.

Eles apenas não contam como devices suportados.

## Matriz de evidência QEMU

| Subsistema | Evidência atual |
|---|---|
| ATA root | gate QEMU |
| AHCI | gate QEMU read/write |
| NVMe | gate QEMU read/write |
| VirtIO block | gate QEMU read/write |
| USB mass storage | gate QEMU read/write |
| xHCI HID | gate QEMU |
| VirtIO GPU | gate QEMU |
| VirGL | gate condicional QEMU/host |
| SMP | marker QEMU 4-vCPU |
| safe mode | gate QEMU |
| disco UEFI instalado | gate QEMU + OVMF |

Essa tabela é deliberadamente de QEMU.

Não é uma matriz física.

## Valor da emulação

Gates QEMU fornecem:

- topologia determinística;
- IDs conhecidos;
- reprodução;
- logs seriais;
- CI;
- localização de falhas.

São a etapa correta antes de hardware real.

O erro seria tratá-los como último nível de validação.

## Schema para matriz física

Uma matriz futura pode registrar:

    system:
      manufacturer:
      model:
      board:
      firmware:
      firmware_version:

    cpu:
      model:
      cpu_count_seen:
      smp_enabled:

    pci:
      controller_ids:

    display:
      framebuffer_mode:
      pitch:
      bpp:

    storage:
      controller:
      device:
      logical_sector_size:
      root_mount:

    input:
      ps2:
      xhci:

    audio:
      controller:
      result:

    network:
      controller:
      result:

    result:
      boot:
      reboot:
      install:
      persistence:

    revision:
      ChrisOS commit:

Isso transforma compatibilidade em evidência auditável e regressável.

## Markers de sucesso físicos

Um boot físico completo deveria guardar em sequência markers como:

- ChrisOS selfhost;
- build identity;
- bootinfo revision;
- framebuffer;
- memory map;
- CPU count;
- storage detection;
- root device;
- cfs mounted;
- desktop 60Hz.

Depois, subsistemas opcionais adicionam seus próprios markers.

## Serial como canal primário

O kernel inicializa serial antes de quase tudo.

Se serial_init falha, kstart desabilita interrupts e entra em halt.

Isso torna early serial diagnostics parte importante da arquitetura atual.

Máquinas com serial acessível são muito melhores para bring-up.

Sistemas sem serial precisam de outro caminho de logging precoce antes de se tornarem targets fáceis de depurar.

## Classificação de falha por camada

Uma máquina deve ser classificada pelo primeiro layer que falha:

1. firmware não inicia BOOTX64.EFI;
2. Limine inicia, mas não chega ao kernel;
3. bootinfo falha;
4. framebuffer falha;
5. CPU/interrupt/SMP falha;
6. storage discovery falha;
7. root filesystem falha;
8. input falha;
9. desktop falha;
10. network/audio/GPU opcional falha.

Isso impede que periféricos opcionais sejam confundidos com incompatibilidade da plataforma central.

## Implementação versus suporte

A documentação deve preferir:

    "driver NVMe implementado; gate QEMU passa"

em vez de:

    "NVMe suportado"

até controladores físicos aparecerem na hardware matrix.

Da mesma forma:

    "xHCI HID passa em QEMU"

é mais preciso que:

    "teclados USB são suportados em PCs."

Essa regra editorial deve valer para todo o corpus.

## Suporte preso à revisão

Compatibilidade de hardware depende da revisão.

Mudanças em:

- PCI enumeration;
- memória;
- APIC;
- storage DMA;
- interrupts;
- Limine;

podem mudar se uma máquina funciona.

Cada registro físico deve fixar o commit exato.

Sem provenance, uma compatibility matrix envelhece rapidamente.

## Prioridades para hardware real

Os próximos trabalhos de maior valor são:

1. enumerador PCI/PCIe real com bridge traversal;
2. consumir ACPI MCFG e implementar ECAM;
3. melhorar aquisição de RSDP/tabelas via bootloader/UEFI;
4. criar primeiro gate físico AHCI;
5. criar primeiro gate físico NVMe;
6. criar primeiro gate físico xHCI;
7. formalizar hardware evidence record;
8. tornar disk probing não destrutivo sem autorização;
9. migrar ESP para FAT32 conservador para firmware físico;
10. adicionar NICs físicos comuns somente depois de estabilizar core boot/storage;
11. adicionar HDA como expansão opcional;
12. preservar safe mode como fallback de primeira linha.

## Classificação atual

Na revisão analisada:

    boot x86-64 Limine         implementado + validado QEMU
    UEFI pelo disco instalado validado QEMU/OVMF
    framebuffer 32 bpp        obrigatório + validado QEMU
    SMP                       implementado + validado QEMU
    ATA                       implementado + validado QEMU
    AHCI                      implementado + validado QEMU
    NVMe                      implementado + validado QEMU
    VirtIO block              implementado + validado QEMU
    USB mass storage          implementado + validado QEMU
    PS/2                      implementado
    xHCI HID                  implementado + validado QEMU
    VirtIO GPU                implementado + validado QEMU
    VirGL                     implementado + validação QEMU condicional
    AC97                      implementado
    VirtIO network            implementado
    NICs físicos gerais       não implementados
    GPUs modernas nativas     não implementadas
    HDA                       não implementado
    ACPI amplo                não implementado
    topologia PCIe geral      não implementada
    matriz de hardware físico ainda não estabelecida

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, o ChrisOS possui uma plataforma x86-64 coerente e amplamente validada em QEMU, com vários caminhos de storage, SMP, framebuffer e devices virtualizados. O projeto já está no estágio em que suporte físico deve ser definido por perfis de máquinas registrados, e não inferido apenas do source. Os principais limites físicos atuais são enumeration PCI restrita, premissas de firmware/framebuffer, setores de 512 bytes, ACPI/PCIe incompleto e ausência de drivers nativos para rede, GPU moderna e áudio HDA.
