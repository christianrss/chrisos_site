---
id: installation-real-hardware
lang: pt-br
type: technical-chapter
volume: 13-real-hardware
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/install.c
  - kernel/fs/install.h
  - kernel/fs/bdev.c
  - kernel/fs/bdev.h
  - kernel/fs/storage.c
  - kernel/fs/storage_limits.h
  - kernel/fs/cfs_format.h
  - kernel/metal/bootinfo.c
  - kernel/lang/clvm_sys.c
  - SYS/DRV/INSTALL.CC
  - scripts/qemu.mk
  - tools/check_install_img.py
  - iso_root/boot/limine/limine.conf
symbols:
  - install_disk
  - install_auto
  - install_selftest
  - install_device
  - write_gpt_backup
  - write_esp
  - bd_installable
  - storage_init
depends_on:
  - block-storage
  - power-on-kstart
related:
  - gpt-esp
  - uefi-disk-boot
  - hardware-profile
  - bringup-diagnostics
  - driver-compatibility
  - validation-evidence
---

# Instalação e hardware físico

## Escopo

ChrisOS já possui um instalador destrutivo real de disco e um gate QEMU que prova que um disco produzido por esse installer consegue bootar por UEFI.

Isso é mais forte que uma arquitetura apenas planejada, mas ainda não equivale a um instalador de hardware físico suportado genericamente.

A implementação atual deve ser entendida como:

- installer de disco x86-64 UEFI;
- operando sobre block devices do ChrisOS;
- exigindo uma árvore de sistema ChrisFS como origem;
- criando GPT, EFI System Partition e partição ChrisFS novas;
- validado end-to-end em QEMU com OVMF;
- ainda não validado como installer seguro para discos físicos arbitrários.

A distinção importa porque instalação é uma das poucas operações do sistema que deliberadamente destrói estado persistente existente.

## Fronteira da operação destrutiva

`install_disk(index)` aceita somente um slot de block device aprovado por `bd_installable`.

O target precisa:

- existir;
- ser gravável;
- não estar marcado como boot, root ou test;
- não ser RAM;
- não ser uma partition view.

Depois disso, o installer reescreve sector zero, metadata GPT, ESP e região ChrisFS.

Não existe modo de instalação in-place nem preservação de partitions existentes.

Todo conteúdo anterior do target deve ser considerado perdido.

## Registry de block devices

ChrisOS mantém um registry global com:

```text
BD_SLOTS = 8
```

Os kinds incluem:

```text
ATA
AHCI
NVMe
VirtIO
USB
RAM
partition
other
```

O installer usa a interface comum `BlockDevice`, em vez de falar diretamente com cada controller.

Isso separa bem o problema de GPT/FAT16/CFS da implementação ATA, AHCI ou NVMe.

## Caminhos de storage atualmente possíveis

Durante boot, `storage_init` tenta detectar:

- ATA/IDE legado;
- AHCI;
- NVMe;
- VirtIO block;
- USB mass storage.

Um device gravável pode se tornar target se não for o root/boot atual.

Essa lista representa paths implementados em software, não uma garantia de compatibilidade com qualquer hardware daquela categoria.

Cada driver possui assumptions mais estreitas que o nome genérico sugere.

## Requisito de sectors de 512 bytes

A storage stack e o installer trabalham com:

```text
512 bytes por sector
```

CFS rejeita sector size diferente.

No NVMe, o namespace só é aceito quando o LBA data size é 2^9 bytes, também 512.

Logo, devices com logical sector nativo de 4 KiB não são targets suportados pela implementação atual.

## Limite de capacidade

`BlockDevice.sector_count` é 32-bit.

Os drivers ATA, AHCI e NVMe também rejeitam capacidades cuja contagem de sectors exige os 32 bits superiores.

Com sectors de 512 bytes, o limite prático fica em torno de 2 TiB.

Discos maiores não devem ser tratados como suportados sem evidência específica.

## Limitações de descoberta PCI

AHCI e NVMe percorrem PCI buses 0 a 7, devices 0 a 31 e functions 0 a 7.

Isso cobre QEMU e topologias simples, mas não equivale a enumeração recursiva completa por bridges PCIe.

Um controller atrás de uma topologia não alcançada pelo scan pode simplesmente não aparecer.

O hardware profile precisa registrar descoberta real, não apenas dizer "possui NVMe" ou "possui AHCI".

## Tamanho mínimo do target

O installer exige espaço para:

- 2048 sectors antes da ESP;
- ESP;
- pelo menos `STOR_DISK_SECTORS = 1.048.576` sectors na condição mínima;
- metadata GPT final e guards.

Para qualquer disco grande o bastante para passar essa condição, a implementação seleciona:

```text
ESP = 65.536 sectors = 32 MiB
```

O mínimo efetivo é:

```text
1.116.224 sectors
545,03125 MiB
```

O target usado pelo gate QEMU possui 560 MiB.

## Branch menor da ESP é na prática inalcançável

O source começa com ESP de 16.384 sectors para disks com no máximo 200.000 sectors e muda para 65.536 acima disso.

Porém, o requisito mínimo de CFS já exige muito mais que 200.000 sectors.

Portanto, toda instalação válida na revisão atual usa o caminho de ESP de 32 MiB.

A branch de ESP menor existe no source, mas não participa de um install válido.

## Layout físico do disco

O disco resultante é:

```text
LBA 0             protective MBR
LBA 1             primary GPT header
LBA 2..33         primary GPT entries
LBA 2048..        EFI System Partition
após a ESP        partição ChrisFS
últimos 33 LBAs   backup GPT entries + header
```

A tabela GPT primária possui 128 entries de 128 bytes.

Somente as duas primeiras são usadas.

## Partition 1: EFI System Partition

A primeira partition usa o GUID type padrão de EFI System Partition.

Começa em:

```text
LBA 2048
```

e, em um install válido atual, possui 65.536 sectors.

O próprio kernel formata FAT16 manualmente.

Não há chamada a firmware, mtools, mkfs.fat ou ferramenta host.

## Partition 2: ChrisFS

A segunda partition começa em:

```text
cfs_lba = 2048 + esp_sectors
```

e vai até:

```text
disk_sectors - 34
```

O installer abre esse range como partition view e executa `cfs_format`.

CFS v5 calcula geometry a partir do tamanho real da partition, portanto o filesystem já não está preso a exatamente 512 MiB.

## Protective MBR

O LBA zero contém uma entrada protective MBR do tipo:

```text
0xEE
```

cobrindo o restante do disco, limitada pelo field de tamanho MBR de 32 bits.

Esse MBR não contém boot code legado do ChrisOS.

Esse detalhe muda a expectativa para BIOS físico.

## Disco instalado é UEFI-only

A ISO do projeto é híbrida BIOS+UEFI porque recebe post-processing do Limine para BIOS.

O installer de disco não executa etapa equivalente.

Ele cria GPT/ESP e coloca:

```text
EFI/BOOT/BOOTX64.EFI
```

na ESP.

Logo, o disk resultante deve ser tratado como **x86-64 UEFI**, não como instalação BIOS legado.

## Secure Boot

Não existe no source inspecionado workflow de signing para Secure Boot, integração com shim, enrollment de keys ou chain assinada do ChrisOS.

O gate atual usa OVMF sem estabelecer Secure Boot.

Em hardware físico, a expectativa deve ser Secure Boot desabilitado até existir um caminho de assinatura testado.

## Construção da GPT

O installer grava:

- GPT signature;
- revision 1.0;
- header de 92 bytes;
- primary e backup LBAs;
- usable range;
- 128 entries × 128 bytes;
- CRC32 das entries;
- CRC32 do header.

A tabela de entries também é copiada para o final do disk e o backup header recebe current/alternate LBA e endereço da própria tabela.

Isso é mais completo que gravar apenas GPT primária.

## Identificadores GPT fixos

Disk GUID e partition unique GUIDs são montados a partir de padrões fixos no source.

Eles não são randomizados por instalação.

Dois disks instalados pelo ChrisOS podem, portanto, carregar identidades GPT duplicadas.

Isso é aceitável nos test images controlados, mas não é desejável em deployment físico com múltiplos discos.

## FAT16 da ESP

A ESP é gerada manualmente com:

```text
512 bytes/sector
4 sectors/cluster
2 FATs
512 root entries
FAT16
```

Cada cluster possui 2 KiB.

A FAT é mantida em array fixo de 16.384 entries.

A ESP atual de 32 MiB permanece dentro dessa envelope.

## Boot files necessários na origem

Antes de qualquer instalação destrutiva, `require_boot_files` exige no filesystem corrente:

```text
BOOT/KERNEL.ELF
EFI/BOOT/BOOTX64.EFI
BOOT/LIMINE.CFG
```

Todos precisam ser não vazios e menores ou iguais a 8 MiB.

O installer copia os conteúdos para a ESP como:

```text
/EFI/BOOT/BOOTX64.EFI
/BOOT/KERNEL.ELF
/BOOT/LIMINE/limine.conf
```

O nome de origem da config e o path final da ESP não são iguais.

## Configuração Limine

A config atual contém:

```text
/ChrisOS
    protocol: limine
    path: boot():/boot/kernel.elf
    resolution: 1920x1080x32
```

Limine continua sendo bootloader externo.

ChrisOS depende do protocolo Limine revision 3 para framebuffer, memory map, HHDM, multiprocessor info e command line.

Self-hosting do kernel não elimina essa dependência.

## Requisito de framebuffer

O boot exige um framebuffer fornecido pelo Limine.

ChrisOS entra em panic se framebuffer não existir ou se:

```text
bpp != 32
```

A config pede 1920×1080×32.

Firmware físico não precisa necessariamente fornecer exatamente esse mode, mas o boot precisa terminar com framebuffer Limine utilizável de 32 bpp.

Não há fallback text-only no path inspecionado.

## Installer exige source system ChrisFS

O fluxo atual não é um installer convencional do tipo "bootar ISO e instalar no único disco".

`storage_init` roda antes de `install_auto`.

O sistema precisa primeiro ter um root filesystem, e o installer copia a tree a partir do ChrisFS já montado.

No gate QEMU existe um segundo artifact:

```text
install-src.img
```

com a árvore do sistema e payload de boot.

Esse disk vira root enquanto outro AHCI vazio é o target.

Uma instalação física precisa reproduzir essa ideia de source ChrisFS, não apenas carregar a ISO.

## Tree copiada para o novo CFS

Com `copy_os`, o installer copia recursivamente:

```text
SYS
APPS
LIB
GAMES
BOOT
SRC
BIN
```

da origem para a partition ChrisFS nova.

A ESP é tratada separadamente.

A pasta `EFI` não é clonada para o ChrisFS target porque o payload EFI já foi escrito na ESP.

## Markers de instalação automática

O path automático é habilitado por:

```text
BOOT/INSTALL.AUTO
```

Também exige:

```text
BOOT/INSTALL.TARGET
```

O primeiro token deve coincidir exatamente com o nome de um block device installable.

Sem target válido, a instalação é recusada e o sistema lista nomes e sector counts disponíveis.

Se mais de um target installable tiver o mesmo nome, a seleção é tratada como ambígua e recusada.

## Marker de dry-run

Se existir:

```text
BOOT/INSTALL.DRY
```

o auto installer resolve o target e registra a seleção, mas não chama o path destrutivo.

É o modo atual mais seguro para verificar target resolution.

Ele ainda não mostra um plano completo de GPT ranges, hashes ou payloads que seriam copiados.

## Device names não são identidades físicas

Os nomes usados pelo registry são genéricos:

```text
ata
ahci
nvme
virtio-blk
usb
```

Não são model, serial, PCI path ou WWN.

Selecionar por string exata ainda é muito mais fraco que identificar um disco físico unicamente.

Um installer físico robusto precisa mostrar e confirmar identidade estável e capacidade.

## Installer gráfico

`SYS/DRV/INSTALL.CC` implementa uma UI de instalação.

Ela lista kinds de disks e marca aqueles com flags de system.

A tela mostra:

```text
keys 1-9 pick target
```

mas o code atual trata diretamente somente três seleções numéricas e chama `disk_install(index)`.

A syscall exige `CAP_DISK_ADMIN`.

## Gap de segurança da UI gráfica

A interface gráfica não mostra:

- model;
- serial;
- capacidade;
- layout previsto;
- confirmação destrutiva adicional;
- dry-run.

Uma única key pode chegar ao `install_disk`.

`bd_installable` continua impedindo root/boot/test, mas isso não basta em uma máquina real com vários disks de usuário.

Essa UI deve continuar classificada como experimental.

## Escrita temporária antes da instalação explícita

Durante `storage_init`, ChrisOS executa `bdev_rw_tests`.

Para cada disk gravável não-root e não-RAM:

1. lê o último sector;
2. grava um pattern;
3. lê de volta;
4. tenta restaurar o conteúdo original.

Isso ocorre antes de `install_auto`.

Em GPT, o último sector normalmente contém o backup GPT header.

Embora o code tente restaurar os bytes, power failure, controller error ou restore failure durante esse teste pode corromper metadata existente.

Para hardware físico, um disk não aprovado pelo usuário não deveria receber write probe algum.

## Formatação automática durante descoberta do root

Root discovery também possui um path de escrita anterior ao installer.

Se não houver CFS conhecido, o sistema procura devices graváveis.

Quando encontra um device grande o suficiente cujo início do sector zero é zerado, `storage_format_if_empty` pode formatá-lo como CFS e usá-lo como root.

Isso é conveniente em test disks controlados, mas significa que a descoberta de um blank disk não é puramente read-only.

Um live environment físico deveria desabilitar essa política por default.

## Self-test do installer

`install_selftest` cria um fake block device em RAM e executa o installer sem copiar toda a tree.

Ele valida pelo menos:

- sucesso da operação;
- primary GPT signature;
- sector de directory da ESP.

É uma cobertura barata da lógica básica.

Não substitui teste em storage persistente.

## Checker independente no host

Depois da instalação QEMU, `tools/check_install_img.py` verifica:

- protective MBR signature/type;
- primary GPT signature e CRC;
- backup GPT signature e CRC;
- partition type GUID do ChrisFS;
- CFS superblock no LBA declarado;
- entry BOOTX64.EFI na ESP;
- entry de kernel;
- long filename `limine.conf`.

Isso fornece validação estrutural fora do guest.

## Gate QEMU de instalação

`make test-qemu-install` executa uma sequência end-to-end:

1. copia uma source ChrisFS image;
2. injeta kernel, BOOTX64.EFI, Limine config e markers;
3. cria target novo de 560 MiB;
4. conecta o target via QEMU AHCI;
5. espera logs de instalação;
6. executa o checker host;
7. inicia outro QEMU usando OVMF;
8. boota apenas pelo disk instalado;
9. exige `cfs mounted` e `desktop 60Hz`.

É evidência de integração real.

## Classificação da evidência

O estado atual pode ser resumido como:

```text
algoritmos do installer       host/QEMU validados
GPT + FAT16 + CFS             checados no host
disk-only UEFI boot           validado em QEMU + OVMF
instalação AHCI física        não estabelecida
instalação NVMe física        não estabelecida
instalação USB física         não estabelecida
legacy BIOS disk boot         não implementado pelo installer
Secure Boot                   não estabelecido
```

"Real-hardware installer" deve indicar o domínio pretendido, não um claim de compatibility concluída.

## Gate necessário para hardware físico

Antes de considerar uma máquina suportada, o projeto deveria registrar:

1. system/motherboard model;
2. firmware vendor/version;
3. UEFI mode e estado de Secure Boot;
4. PCI identity do controller;
5. model, serial, sector size e capacidade do target;
6. discovery logs antes de qualquer write;
7. dry-run com identidade do target;
8. logs do install;
9. inspeção GPT/ESP independente após install;
10. cold reboot do disk instalado;
11. build/hash identity do ChrisOS após boot;
12. ciclos repetidos de read/write e reboot limpo.

Um boot isolado é evidência, mas não uma hardware support matrix.

## Prioridades imediatas de segurança

Antes de uso físico rotineiro, as mudanças de maior impacto são:

1. remover write probes em disks não aprovados;
2. desabilitar auto-format de blank disks no modo live/físico;
3. expor model/serial/capacity e identidade estável;
4. adicionar segunda confirmação destrutiva;
5. fazer dry-run mostrar ranges GPT e artifacts;
6. gerar GUIDs únicos por instalação;
7. verificar conteúdo dos files da ESP depois da escrita;
8. verificar GPT/ESP/CFS do target antes de declarar complete;
9. documentar rollback/recovery;
10. criar gates físicos separados por classe de controller.

## Nota de revisão

Este capítulo foi reconciliado contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. O installer atual é um installer GPT/FAT16/CFS x86-64 UEFI real, com gate de disk-only boot bem-sucedido em QEMU+OVMF. Ele ainda não deve ser tratado como installer físico genericamente seguro porque a identidade do target é fraca e a inicialização normal de storage pode gravar em disks não-root antes de aprovação explícita.
