---
id: uefi-disk-boot
lang: pt-br
type: technical-chapter
volume: 13-real-hardware
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/install.c
  - kernel/fs/storage.c
  - kernel/fs/part.c
  - kernel/metal/bootinfo.c
  - scripts/qemu.mk
  - tools/check_install_img.py
  - iso_root/boot/limine/limine.conf
symbols:
  - install_device
  - write_esp
  - write_gpt_backup
  - storage_init
depends_on:
  - installation-real-hardware
  - gpt-esp
  - uefi
  - limine
related:
  - hardware-profile
  - bringup-diagnostics
  - driver-compatibility
  - validation-evidence
---

# Boot UEFI pelo disco instalado: do firmware ao sistema ChrisOS

## Escopo

O ChrisOS possui agora um gate end-to-end que prova que um disco produzido pelo instalador do kernel consegue iniciar sem a ISO de instalação em QEMU com OVMF.

A cadeia validada é:

    disco alvo vazio
        ↓ instalador ChrisOS
    GPT + EFI System Partition + ChrisFS
        ↓
    firmware UEFI OVMF
        ↓
    EFI/BOOT/BOOTX64.EFI
        ↓
    Limine
        ↓
    /boot/kernel.elf
        ↓
    kernel ChrisOS
        ↓
    descoberta de storage nativa
        ↓
    mount da root ChrisFS
        ↓
    desktop 60Hz

Essa evidência é relevante porque o segundo boot usa somente o disco instalado e o firmware UEFI.

Ainda não prova que qualquer firmware UEFI físico irá descobrir e iniciar o mesmo disco.

Este capítulo documenta a cadeia real atual, a evidência QEMU/OVMF e as fronteiras restantes de compatibilidade.

## Evidência atual

O alvo de integração autoritativo é:

    make test-qemu-install

Ele primeiro inicia um source system com um target AHCI vazio e exige markers de instalação.

Depois executa:

    tools/check_install_img.py

sobre a imagem de destino.

Finalmente abre uma nova instância QEMU com OVMF e o target instalado como único disco de sistema.

O segundo boot precisa emitir:

    cfs mounted
    desktop 60Hz

Isso estabelece um gate real de boot UEFI somente pelo disco no modelo de CI/tooling atual.

## O que o segundo boot exclui

A segunda execução QEMU não anexa a ISO do ChrisOS.

Ela fornece:

- máquina QEMU PC;
- flash de código OVMF;
- flash copiável de variáveis OVMF;
- imagem instalada como IDE disk;
- serial log.

Logo, o sucesso não depende de El Torito nem das estruturas específicas da ISO.

O próprio disco contém a cadeia necessária.

## Layout do disco instalado

O instalador grava:

    LBA 0             protective MBR
    LBA 1             primary GPT header
    LBA 2..33         primary GPT entries
    LBA 2048..        EFI System Partition
    após ESP           partição ChrisFS
    setores finais     backup GPT entries/header

O checker host valida GPT primária e backup.

O boot instalado é, portanto, baseado em GPT e não em bootstrap MBR.

## Sem boot legacy BIOS

O protective MBR existe apenas para identificar o disco GPT a software MBR-aware.

O instalador não grava bootloader BIOS no código de boot do MBR.

O disco deve ser classificado como:

    disco de boot x86-64 UEFI

e não como:

    disco instalado híbrido BIOS + UEFI

A ISO continua sendo artefato separado com suporte de boot mais amplo.

## EFI System Partition

A primeira partição usa o GUID padrão de EFI System Partition e começa no LBA 2048.

O instalador constrói o filesystem e grava os payloads diretamente.

A hierarquia relevante é:

    EFI/
      BOOT/
        BOOTX64.EFI

    BOOT/
      KERNEL.ELF
      LIMINE/
        limine.conf

O EFI application é o binário UEFI x86-64 do Limine.

## Por que BOOTX64.EFI importa

UEFI define nomes default por arquitetura para descoberta estilo removable-media.

Em x86-64 o caminho convencional é:

    EFIBOOTBOOTX64.EFI

O instalador atual usa deliberadamente esse fallback path.

Assim não precisa criar ou modificar variáveis NVRAM Boot#### durante a instalação.

## Fixed disk e fallback

O fallback é útil, porém firmware policy para non-removable media é mais variável que a regra simples de removable media.

Firmware UEFI pode iniciar fixed disk por um Boot#### explícito.

Na ausência de opção utilizável, alguns firmwares também pesquisam filesystems candidatos usando default boot behavior.

OVMF encontra com sucesso o disco ChrisOS atual no gate.

Isso não deve ser presumido para qualquer firmware físico.

Um instalador futuro de produção deveria considerar registrar Boot#### explicitamente e manter BOOTX64.EFI como recovery/fallback.

## Sem Boot####

O ChrisOS atual não cria:

- Boot####;
- BootOrder;
- BootNext.

O instalador modifica apenas o disco.

Vantagens:

- não depende de UEFI Runtime Services depois do boot;
- evita falhas de permissão em firmware variables;
- evita records NVRAM obsoletos;
- simplifica imagens de teste.

Trade-off: firmware que não procura o fallback em fixed disk pode não iniciar automaticamente.

## BOOTX64.EFI não é o kernel

BOOTX64.EFI é um UEFI executable.

O kernel ChrisOS continua sendo ELF.

O firmware não carrega KERNEL.ELF diretamente como EFI application.

As etapas são:

    firmware
        ↓ PE32+ EFI
    BOOTX64.EFI / Limine
        ↓ limine.conf
    KERNEL.ELF
        ↓ Limine protocol
    ChrisOS kstart

Essa distinção é importante para diagnostics.

Falha antes do Limine difere de falha depois do ELF carregado.

## Configuração Limine

A configuração instalada contém:

    /ChrisOS
        protocol: limine
        path: boot():/boot/kernel.elf
        resolution: 1920x1080x32

Limine permanece como bootloader e implementa o handoff firmware → kernel.

ChrisOS depende de boot information do Limine e não implementa um loader UEFI próprio.

## Significado de boot()

A configuração pede ao Limine que resolva o kernel no boot volume visível ao bootloader.

Assim BOOTX64.EFI, config e kernel precisam formar um filesystem de boot internamente consistente.

O checker valida presença das directory entries.

Ainda não valida hashes criptográficos de todos os arquivos instalados.

## Filesystem atual da ESP

O writer atual cria filesystem estilo FAT16.

Evidências:

- FAT entries uint16_t;
- root directory fixo;
- label FAT16;
- cluster-chain encoding de FAT16.

Isso importa porque a meta de hardware físico normalmente é descrita como ESP FAT32.

O gate OVMF prova aceitação da imagem atual por OVMF.

Não prova aceitação equivalente por todo firmware físico.

## Limite de compatibilidade FAT16

A claim correta hoje é:

    ESP estilo FAT16 + BOOTX64.EFI:
    validado no gate OVMF atual

e não:

    ESP UEFI físico universalmente validado

Uma melhoria de alto valor é substituir o ESP FAT16 escrito à mão por FAT32 orientado ao padrão e repetir gates QEMU e hardware.

## Estágio de firmware

No segundo boot de integração, OVMF atua como firmware UEFI.

Conceitualmente o firmware precisa:

1. inicializar plataforma;
2. descobrir controller/disk;
3. interpretar GPT/partitions;
4. expor ESP via protocols de storage/filesystem;
5. localizar EFI image de acordo com boot policy;
6. autenticar a image se Secure Boot exigir;
7. carregar e iniciar o EFI image.

ChrisOS não está rodando durante essas etapas.

## Estágio Limine

Após BOOTX64.EFI iniciar, Limine possui o loader stage.

Responsabilidades incluem:

- localizar configuration;
- localizar KERNEL.ELF;
- carregar ELF;
- construir ambiente de execução;
- obter dados de firmware/plataforma;
- preparar framebuffer;
- produzir responses do Limine protocol;
- transferir controle ao kernel.

O kernel começa depois dessas responsabilidades.

## Fronteira ExitBootServices

O kernel ChrisOS não chama UEFI Boot Services.

Limine possui a transição de firmware e ExitBootServices.

Portanto, um failure anterior nessa etapa não aparece em logs comuns do kernel se o kernel nunca for chamado.

A fronteira de diagnóstico é:

    sem serial do kernel
        pode ser firmware/bootloader

enquanto:

    início de kstart
        prova que firmware + loader chegaram ao kernel

## Estágio do kernel

Depois do handoff, ChrisOS consome o boot protocol e inicializa:

- memory management;
- interrupts;
- storage drivers;
- filesystem;
- graphics/desktop;
- outros subsistemas.

UEFI Block I/O deixa de ser o mecanismo normal de storage.

## Storage de firmware versus storage nativo

O mesmo disco pode ser acessado por duas stacks totalmente diferentes no mesmo boot:

    antes do kernel:
        driver de storage/filesystem UEFI

    depois do kernel:
        driver ChrisOS ATA/AHCI/NVMe/VirtIO/USB

Assim, firmware pode conseguir carregar Limine e o kernel posteriormente falhar ao montar a root.

O inverso também pode ocorrer em ambientes de desenvolvimento.

Boot completo exige compatibilidade nos dois estágios.

## Transição para root filesystem

O disco instalado contém ChrisFS depois da ESP.

Após kernel entry, discovery nativo precisa localizar block device e partition.

A camada storage/partition identifica e monta ChrisFS.

O gate exige:

    cfs mounted

Esse marker prova que o boot passou de firmware/Limine para acesso nativo ChrisOS ao disco.

## Força da evidência cfs mounted

Se somente BOOTX64.EFI e KERNEL.ELF funcionassem, o kernel poderia iniciar e ainda falhar ao usar o sistema instalado.

Exigir ChrisFS mount demonstra:

- controller nativo funcionando;
- partition discovery;
- ChrisFS superblock legível;
- root filesystem aceito.

O marker do desktop demonstra progresso posterior adicional.

## Assimetria de controller no gate

A fase de instalação grava o target pelo caminho AHCI:

    -device ich9-ahci
    -device ide-hd,drive=target,bus=ahci.0

O segundo boot disk-only anexa a imagem instalada usando o path IDE do QEMU.

Então o gate prova:

- instalação via target AHCI do ChrisOS;
- boot UEFI da imagem produzida;
- root boot no controller usado pela segunda execução.

Não é a mesma topologia/controller nas duas fases.

## Checker host-side

Antes do segundo boot, tools/check_install_img.py verifica:

- protective MBR;
- GPT primary signature/CRC;
- GPT backup signature/CRC;
- GUID da partição ChrisFS;
- superblock ChrisFS;
- directory entry BOOTX64.EFI;
- entry KERNEL.ELF;
- LFN limine.conf.

Isso captura vários bugs do formatter antes do firmware rodar.

## O que o checker não prova

Não prova ainda:

- identidade byte-for-byte do BOOTX64.EFI;
- hash criptográfico do kernel;
- consistência completa de FAT;
- todos os vínculos de CRC da GPT;
- conformidade FAT32;
- Secure Boot;
- portabilidade de firmware.

O segundo boot acrescenta evidência comportamental.

## OVMF variable store

O teste copia:

    /usr/share/OVMF/OVMF_VARS_4M.fd

para uma imagem de variáveis gravável no build.

Assim OVMF possui NVRAM persistível sem modificar o template do sistema.

A instalação não depende de um Boot#### ChrisOS pré-existente nessa store.

## Secure Boot

O gate atual não estabelece Secure Boot.

Não há workflow de signing/enrollment ChrisOS nesse caminho.

Um sistema físico com Secure Boot enforcement pode rejeitar BOOTX64.EFI.

A claim segura é:

    UEFI validado sem cadeia Secure Boot estabelecida

Hardware bring-up precisa registrar explicitamente o estado de Secure Boot.

## Dependência gráfica

A configuração Limine pede:

    1920x1080x32

O boot ChrisOS espera framebuffer utilizável de 32 bpp.

Firmware físico pode oferecer modos diferentes.

Logo, disk boot depende também do graphics handoff.

Hardware profile deve registrar:

- width/height;
- pitch;
- pixel layout;
- mode escolhido.

## Device paths UEFI

Firmware real pode identificar boot device com device paths contendo:

- PCI;
- SATA;
- NVMe;
- USB;
- partition nodes;
- vendor-specific nodes.

Como a instalação atual não cria Boot####, ChrisOS evita gerar esses paths.

Se NVRAM registration for adicionada, device-path construction passa a fazer parte do instalador.

## Instalação em USB

BOOTX64.EFI torna o layout conceitualmente compatível com fallback x86-64 de removable media.

Mas boot físico USB depende de:

- caminho write do USB mass storage no ChrisOS;
- ESP gerada ser aceita;
- policy USB do firmware;
- driver USB do kernel depois da entrada.

O gate AHCI/QEMU atual não prova isso.

## Cold boot

Validação física deve incluir power-on ou reset limpo, não apenas warm reboot após instalação.

Cold boot elimina dependência de estado transitório.

A mídia de instalação também deve ser removida.

## Boot order

Firmware físico pode preferir outro disco.

É necessário separar:

    disco é bootável
    versus
    firmware selecionou esse disco

Falha de auto-boot pode ser somente BootOrder.

## Recovery fallback

Mesmo com futuro Boot#### explícito, vale manter:

    EFI/BOOT/BOOTX64.EFI

Se NVRAM resetar ou a entry for perdida, o fallback pode recuperar o boot.

Registration e fallback são mecanismos complementares.

## Classificação de falhas

### EFI loader não inicia

Sintomas:

- sem Limine;
- sem serial ChrisOS.

Domínios prováveis:

- storage discovery do firmware;
- GPT/ESP;
- FAT compatibility;
- Boot####/fallback policy;
- Secure Boot;
- BOOTX64.EFI inválido.

### Limine inicia, kernel não

Domínios:

- limine.conf;
- localização KERNEL.ELF;
- ELF loading;
- framebuffer request;
- protocol setup.

### Kernel inicia, ChrisFS não monta

Domínios:

- driver de storage nativo;
- partition discovery;
- ChrisFS;
- controller topology.

### ChrisFS monta, desktop não

Domínios:

- subsistemas posteriores;
- graphics/input/apps.

Essa classificação é melhor que tratar tudo como "UEFI não bootou".

## Registro de validação física

Um registro real deveria conter:

- system/motherboard model;
- firmware vendor/version;
- UEFI mode;
- CSM;
- Secure Boot;
- disk/controller model e PCI identity;
- ESP start/size/filesystem;
- Boot#### presente ou não;
- boot path selecionado;
- primeiro estágio visível do Limine;
- primeiro marker serial do ChrisOS;
- framebuffer;
- root-controller detection;
- ChrisFS mount;
- desktop;
- resultado de cold reboot.

Assim sucesso deixa de ser anedótico e vira evidência reutilizável.

## Melhorias antes de claims amplas

Prioridades:

1. implementar ESP FAT32 orientada à compatibilidade física;
2. verificar hashes dos boot files gravados;
3. opcionalmente registrar Boot#### mantendo fallback;
4. melhorar diagnostics de estágio firmware;
5. definir formato de evidence para physical boot;
6. testar SATA/AHCI, NVMe e USB separadamente;
7. testar Secure Boot somente após signing chain real;
8. testar múltiplos vendors de firmware;
9. remover writes pré-instalação em discos não aprovados;
10. publicar matriz firmware/controller em vez de claim binária.

## Classificação atual da evidência

Na revisão analisada:

    installer cria GPT + ESP + ChrisFS        implementado
    BOOTX64.EFI fallback                      implementado
    Limine config/kernel payload              implementado
    checker da imagem instalada               implementado
    disk-only UEFI boot                       validado QEMU + OVMF
    native ChrisFS mount após disk boot       validado QEMU
    compatibilidade com firmware físico       não estabelecida
    Boot#### explícito                         não implementado
    Secure Boot                               não implementado
    ESP FAT32 amplamente orientada ao padrão  não implementada

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, o ChrisOS atingiu um milestone real de UEFI disk boot: o instalador do kernel cria GPT com BOOTX64.EFI, configuração Limine, kernel e ChrisFS; a imagem passa por checks estruturais e inicia sem ISO em OVMF até mount da ChrisFS e desktop. A lacuna restante é transportar essa evidência do ambiente controlado OVMF para firmwares físicos diversos, especialmente porque a ESP atual é estilo FAT16, não existe Boot#### criado pelo instalador e não há cadeia Secure Boot.
