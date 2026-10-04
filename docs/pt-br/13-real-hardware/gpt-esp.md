---
id: gpt-esp
lang: pt-br
type: technical-chapter
volume: 13-real-hardware
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/install.c
  - kernel/fs/part.c
  - kernel/fs/part.h
  - kernel/fs/cfs_format.h
  - kernel/fs/storage_limits.h
  - tools/check_install_img.py
  - scripts/qemu.mk
  - iso_root/boot/limine/limine.conf
symbols:
  - write_gpt_backup
  - write_esp
  - gpt_find_cfs
  - part_open
depends_on:
  - installation-real-hardware
related:
  - uefi-disk-boot
  - block-storage
  - validation-evidence
---

# GPT e EFI System Partition

## Escopo

O installer do ChrisOS constrói diretamente em kernel a partition table e a EFI System Partition.

Não há chamada a biblioteca GPT genérica, `sgdisk`, `parted`, `mkfs.fat` ou serviço de firmware para formatar.

A implementação controla todos os bytes on-disk necessários para protective MBR, GPT primária, GPT backup, FAT16 da ESP, fallback path UEFI, configuração Limine e localização do kernel.

Este capítulo documenta esse formato e o parser usado depois para redescobrir ChrisFS.

## Assumptions de geometry

Todos os offsets são expressos em logical sectors de 512 bytes.

A interface `BlockDevice` expõe sector count em 32 bits.

Por isso, embora GPT use fields de 64 bits on-disk, a implementação trabalha com media endereçável dentro do modelo de 32-bit sectors.

Os drivers atuais também rejeitam capacidades que ultrapassem esse modelo.

## Protective MBR

O LBA zero é zerado e recebe uma única partition entry protetora.

Os fields principais são:

```text
partition type = 0xEE
start LBA      = 1
length         = sectors - 1
signature      = 0x55AA
```

O length é saturado em `0xFFFFFFFF` quando necessário.

Não existe active flag.

Também não existe BIOS boot code do ChrisOS no MBR.

O objetivo é compatibilidade/proteção da GPT, não boot legado.

## Array primário de GPT entries

O installer reserva:

```text
128 entries
128 bytes por entry
16.384 bytes total
32 sectors
```

começando em:

```text
LBA 2
```

O array inteiro é zerado e somente as duas primeiras entries são preenchidas.

## Alinhamento das partitions

O GPT header declara first usable LBA 34, porém a ESP começa em:

```text
LBA 2048
```

Isso produz alinhamento convencional de 1 MiB para a primeira partition.

A área entre GPT entries e ESP permanece livre.

Como a ESP atual possui tamanho múltiplo de 2048 sectors, a partition ChrisFS também começa alinhada a 1 MiB.

Esse alinhamento é útil para firmware, SSDs e controllers modernos, embora o installer não execute tuning específico por erase-block size.

## Partition 1

A primeira entry usa o GUID type padrão de EFI System Partition.

Seu range é:

```text
start = 2048
end   = 2048 + esp_sectors - 1
```

Em toda instalação atualmente válida:

```text
esp_sectors = 65536
```

equivalente a 32 MiB.

## Partition 2

A segunda entry usa o GUID type próprio do ChrisOS:

```text
43524653-3100-4000-8000-000000000001
```

Os bytes estão no formato mixed-endian usado pelo GPT.

Esse GUID identifica ChrisFS.

O range instalado é:

```text
start = 2048 + esp_sectors
end   = disk_sectors - 34
```

Os últimos 33 sectors ficam reservados para backup GPT entries e header.

## Compatibilidade com imagens antigas

O parser `part.c` aceita dois partition type GUIDs para localizar ChrisFS:

- GUID específico do ChrisOS;
- GUID padrão Linux filesystem data.

O segundo existe para compatibilidade com installer images mais antigas.

Instalações novas usam o GUID ChrisOS.

## Partition unique GUIDs

Os fields de unique GUID recebem valores simples e fixos:

```text
partition 1 -> byte distintivo 1
partition 2 -> byte distintivo 2
```

O restante fica zerado.

Esses identifiers não são gerados de forma única por instalação.

Portanto, vários disks instalados podem ter partition GUIDs duplicados.

## Disk GUID

O disk GUID do GPT header também é construído a partir de padrão fixo.

Ele não é randomizado em cada install.

Isso funciona em test images isoladas, mas pode gerar ambiguidade quando mais de um disk ChrisOS está conectado.

Ferramentas externas que identificam volumes por GUID podem tratar dois disks ChrisOS como duplicados.

## Primary GPT header

O header primário fica em:

```text
LBA 1
```

com:

```text
signature            "EFI PART"
revision             0x00010000
header size          92 bytes
current LBA          1
backup LBA           último sector
first usable LBA     34
last usable LBA      sectors - 34
entry-array LBA      2
entry count          128
entry size           128
```

O CRC32 das partition entries é gravado no header.

Depois o header CRC32 é calculado com o próprio CRC field zerado.

## CRC32

ChrisOS usa o polynomial reflected padrão:

```text
0xEDB88320
```

iniciando em todos os bits 1 e complementando no final.

`tools/check_install_img.py` repete a verificação de forma independente com `zlib.crc32`.

Isso fornece um segundo parser para o artifact gerado.

## Backup GPT entries

O installer copia os 32 sectors do primary entry array, LBAs 2..33, para:

```text
sectors - 33
até
sectors - 2
```

As entries são copiadas byte-a-byte.

Como os start/end LBAs são absolutos, não precisam ser transformados.

## Backup GPT header

O primary header é lido e ajustado.

O backup recebe:

```text
current LBA      = sectors - 1
alternate LBA    = 1
entry-array LBA  = sectors - 33
```

O CRC é zerado, recalculado e o header final é gravado no último sector.

## Consistência entre primary e backup

O installer constrói o backup a partir da GPT primária recém-gravada, portanto os dois entry arrays nascem equivalentes.

Porém, não existe hoje um passo final que releia ambas as cópias e compare headers, arrays e CRCs antes de declarar instalação concluída.

No gate QEMU, o checker valida os dois header CRCs, mas ainda não compara os entry arrays completos.

Para hardware físico, esse read-back deveria fazer parte da transação de instalação.

## Backup não é usado em recovery runtime

Apesar de o installer criar backup GPT completo, `gpt_find_cfs` lê apenas o primary header no LBA 1.

Se a GPT primária estiver danificada e o backup estiver íntegro, ChrisOS não tenta recovery pelo final do disk.

Esse fallback ainda precisa ser implementado.

Uma política robusta deveria validar primary primeiro, tentar backup em caso de falha e rejeitar o disk se as duas cópias válidas discordarem sobre geometry ou entries críticas.

## O que o checker host valida

Após `test-qemu-install`, `check_install_img.py` checa:

- protective MBR signature;
- type `0xEE`;
- primary GPT signature;
- primary header CRC;
- backup GPT signature;
- backup header CRC;
- GUID type do ChrisFS;
- CFS superblock no LBA declarado.

É uma validação independente útil.

## O que ainda não é validado

O checker atual não testa:

- partition-entry CRC contra o array;
- equivalência primary/backup entries;
- consistência de usable ranges;
- unicidade dos GUIDs;
- overlap entre partitions;
- consistência integral da FAT;
- hashes/conteúdo dos boot files.

Portanto, há classes de corrupção que ainda podem passar pelo checker.

## Parser GPT em runtime

`gpt_find_cfs` lê o header primário e exige:

```text
"EFI PART"
```

Depois copia os primeiros 92 bytes, zera o CRC field e valida o header CRC.

Isso evita aceitar diretamente um primary header obviamente corrompido.

## Gap do partition-entry CRC

O GPT header possui CRC do array completo de entries.

O installer grava esse valor.

Porém, `gpt_find_cfs` não recalcula esse CRC antes de confiar nas entries.

Logo, uma entry ChrisFS corrompida ainda pode ser examinada se o header permanecer válido.

É um gap de integrity no root discovery.

## Limites do parser

O parser lê entry-array LBA, entry count e entry size.

Aceita entry size >= 128 e limita a contagem a 128.

O start LBA do array precisa caber em 32 bits.

Isso acompanha a limitação geral da storage stack.

## Scanning das entries

Para cada entry, o parser calcula sector/offset a partir de:

```text
index * entry_size
```

No formato normal de 128 bytes, quatro entries cabem exatamente em 512 bytes.

O type GUID é então comparado com os GUIDs ChrisFS/Linux aceitos.

## Entry crossing não é geral

O buffer do parser possui apenas um sector de 512 bytes.

Se um GPT externo usar entry size que faça uma entry atravessar boundary de sector, a implementação não recompõe a entry a partir de dois sectors.

ChrisOS sempre grava 128-byte entries, então seu próprio disk layout não sofre esse problema.

Mas o parser não é GPT genérico.

## Validação dos LBAs

Para uma entry compatível:

```text
start != 0
start <= end
end <= 0xFFFFFFFF
```

Depois retorna:

```text
lba   = start
count = end - start + 1
```

O parser não verifica diretamente se `end` cabe dentro do parent device real.

## Clipping em `part_open`

`part_open` rejeita start fora do parent, mas se o count ultrapassar o final do device ele é reduzido ao range restante.

Isso evita out-of-range I/O, mas também pode mascarar uma GPT inconsistente transformando uma partition inválida em view truncada.

Uma validação hardware-grade deve rejeitar geometry inconsistente antes de criar a view.

## Partition view

`part_open` cria um `BlockDevice` sintético.

I/O local vira:

```text
parent_lba = partition_start + local_lba
```

A view reporta sectors de 512 bytes.

CFS não precisa conhecer GPT.

## FAT16 da ESP

O installer gera FAT16 com:

```text
bytes/sector      512
sectors/cluster   4
reserved sectors  1
FAT copies        2
root entries      512
media byte        0xF8
hidden sectors    esp_lba
filesystem        FAT16
```

O volume label é:

```text
CHRISOS ESP
```

## Tamanho da FAT

Na ESP efetiva de 32 MiB:

```text
sectors per FAT = 64
```

A FAT inteira é mantida em:

```text
uint16_t g_fat[16384]
```

Cada entry representa um FAT16 cluster.

## Root directory

FAT16 possui root directory em região fixa.

O installer reserva:

```text
512 entries * 32 bytes
= 16384 bytes
= 32 sectors
```

O root contém directories:

```text
EFI
BOOT
```

## Início da data region

O cálculo é:

```text
root = 1 + 2 * sectors_per_fat
data = root + 32
```

relativo ao início da ESP.

Cluster 2 corresponde ao primeiro cluster de dados de 2 KiB.

O mapping é:

```text
esp_lba + data + (cluster - 2) * 4
```

## Clusters reservados

O layout fixa:

```text
cluster 2 -> /EFI
cluster 3 -> /EFI/BOOT
cluster 4 -> /BOOT
cluster 5 -> /BOOT/LIMINE
```

As FAT entries dessas directories são marcadas end-of-chain.

Files começam no cluster 6.

## UEFI fallback loader

O loader é instalado em:

```text
/EFI/BOOT/BOOTX64.EFI
```

Esse é o fallback path padrão para UEFI x86-64.

Assim o firmware consegue bootar sem depender de uma NVRAM boot entry pré-criada.

## Kernel

O kernel fica em:

```text
/BOOT/KERNEL.ELF
```

com short name FAT:

```text
KERNEL  ELF
```

A configuração Limine referencia:

```text
boot():/boot/kernel.elf
```

## Configuração Limine

O source file em ChrisFS é:

```text
BOOT/LIMINE.CFG
```

Na ESP ele vira:

```text
/BOOT/LIMINE/limine.conf
```

O installer cria uma LFN entry para `limine.conf` e a short entry `LIMINE  CFG`.

## LFN especializado

O helper de long file name grava somente uma LFN entry com sequence:

```text
0x41
```

Isso basta para `limine.conf`, que cabe em um fragmento de 13 caracteres.

Não é um writer LFN genérico para nomes arbitrários.

## Alocação dos files

Os files são copiados em chunks de 2 KiB, um cluster por vez.

Cada FAT entry aponta para o próximo cluster e o último recebe:

```text
0xFFFF
```

A directory entry guarda first cluster e byte size original.

O restante do último cluster é preenchido com zero.

## Limite de file

`require_boot_files` rejeita boot files acima de:

```text
8 MiB
```

O allocator também limita cluster indexes a cerca de 16.000.

Isso protege o array FAT fixo, mas estabelece teto para crescimento de kernel/loader enquanto a implementação permanecer especializada.

## Sem read-back do conteúdo

Após os writes da ESP, sucesso é baseado no retorno do block device.

O installer não relê kernel, BOOTX64.EFI e config para comparar conteúdo.

O checker host confirma nomes de directory entries, mas não hashes completos.

Para hardware físico, read-back verification é desejável antes de declarar install complete.

## Validação pós-write ideal

Um gate mais forte deveria reler a ESP pelo próprio filesystem parser ou por ferramenta independente e verificar:

- duas FATs idênticas;
- chains sem loops;
- first clusters dentro do data region;
- directory sizes coerentes;
- hashes de BOOTX64.EFI, kernel e limine.conf iguais às fontes;
- ausência de sectors gravados fora do range ESP/GPT previsto.

Isso transformaria "os writes retornaram sucesso" em evidência de conteúdo persistido corretamente.

## Prova QEMU

O gate `test-qemu-install` é a evidência mais forte do layout.

Depois da instalação, o host checker inspeciona GPT/ESP.

Em seguida, o mesmo disk boota por OVMF sem usar a ISO ChrisOS como boot source.

O guest alcança:

```text
cfs mounted
desktop 60Hz
```

Isso prova que o layout é suficiente no ambiente UEFI testado.

## Limitações para hardware físico

Embora as estruturas sejam convencionais, o path ainda possui escolhas experimentais:

- GUIDs fixos;
- sem Secure Boot;
- FAT16 writer especializado;
- sem hash read-back;
- sem fallback para backup GPT;
- sem entry-array CRC runtime;
- parser GPT não genérico;
- sector addressing 32-bit;
- sem instalação BIOS legado.

Essas limitações precisam acompanhar qualquer claim de hardware support.

## Hardening recomendado

As prioridades são:

1. gerar disk/partition GUIDs únicos;
2. validar partition-entry CRC em runtime;
3. usar backup GPT quando primary falhar;
4. validar overlap e usable ranges;
5. suportar entries crossing sector boundaries;
6. checar consistência FAT depois da escrita;
7. reler e verificar SHA-256 dos files da ESP;
8. declarar limites oficiais de ESP/kernel;
9. adicionar signing para Secure Boot quando necessário;
10. validar GPT/FAT independentemente nos hardware gates.

Esses passos também facilitam ferramentas externas de recuperação e diagnóstico, tornando o layout mais confiável fora do ambiente controlado do QEMU.

## Nota de revisão

Este capítulo foi escrito contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. ChrisOS atualmente gera GPT primária/backup completa e uma ESP FAT16 especializada de 32 MiB suficiente para o gate QEMU+OVMF. A implementação é deliberadamente estreita e ainda não deve ser tratada como biblioteca geral de GPT/FAT.
