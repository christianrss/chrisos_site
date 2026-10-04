---
id: chrisfs-spec
lang: pt-br
type: specification
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/storage_limits.h
  - kernel/fs/cfs_format.h
  - kernel/fs/cfs.h
  - kernel/fs/cfs.c
  - kernel/fs/cfs_fsck.c
  - tools/cfs_mkdisk.c
  - tools/cfs_migrate_v1v2.c
  - tools/cfs_migrate_v2v3.c
  - tools/test_cfs_v5.c
  - tools/test_cfs_fsck.c
  - tools/test_cfs_indirect.c
  - tools/test_cfs_journal.c
  - tools/test_cfs_maxwrite.c
  - tools/test_cfs_chmod.c
  - tools/test_cfs_paths.c
symbols:
  - cfs_format
  - cfs_mount
  - cfs_super_encode
  - cfs_super_decode
  - cfs_inode_encode
  - cfs_inode_decode
  - cfs_dirent_encode
  - cfs_dirent_decode
  - jnl_begin
  - jnl_log
  - jnl_commit
  - jnl_replay
  - cfs_fsck
depends_on:
  - specifications-policy
  - chrisfs
  - block-storage
related:
  - chrisfs-cache
  - chrisfs-inodes
  - chrisfs-fsck
  - chrisfs-journal
  - fault-injection
---

# Formato on-disk do ChrisFS

## Status

ChrisFS é o filesystem nativo do ChrisOS.

Este documento especifica o **ChrisFS versão 5** implementado na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

O mounter atual também aceita superblocks versão 4 e versão de compatibilidade 3.

Versões 1 e 2 não são montadas diretamente pelo decoder atual; ferramentas separadas contêm readers para esses layouts históricos.

## Unidade fundamental

O filesystem usa logical sector fixo de:

    512 bytes

A geometria default continua sendo:

    1.048.576 sectors
    536.870.912 bytes
    512 MiB

A versão 5 não fica restrita exatamente a esse tamanho.

O formatter deriva a geometria de bitmap/data a partir do `sector_count` real do block device.

## Magic e versões

Constantes:

    CFS_MAGIC          = 0x31534643
    CFS_VERSION        = 5
    CFS_VERSION_V4     = 4
    CFS_VERSION_COMPAT = 3

Em little-endian, os bytes do magic são:

    C F S 1

O identificador permanece `CFS1` embora o formato tenha evoluído para versões posteriores.

## Endianness

Todos os integer fields on-disk são codificados por helpers little-endian explícitos.

Logo ChrisFS possui formato de disco explicitamente little-endian e não depende de layout nativo de struct.

Isso vale para superblock, inode, dirent, pointer blocks e journal metadata.

## Layout geral do volume

As regiões lógicas são:

    LBA 0                superblock
    bitmap_lba...        allocation bitmap
    inode_lba...         inode table
    journal_lba...       metadata journal
    data_lba...          data/pointer blocks

A versão 5 armazena posições e comprimentos no superblock.

O formatter atual normalmente posiciona as regiões de forma contígua nessa ordem.

## Geometria legada de 512 MiB

Para a image tradicional de 512 MiB:

    superblock        LBA 0
    bitmap            LBA 1..256
    inode table       LBA 257..768
    journal           LBA 769..832
    data              LBA 833..

Constantes:

    CFS_BITMAP_LBA      = 1
    CFS_BITMAP_SECTORS  = 256
    CFS_INODE_LBA       = 257
    CFS_INODE_SECTORS   = 512
    CFS_JOURNAL_LBA     = 769
    CFS_JOURNAL_SECTORS = 64
    CFS_DATA_LBA        = 833

Com 1.048.576 sectors restam:

    1.047.743 data sectors

ou 536.444.416 bytes de address space de data region.

## Geometria dinâmica da v5

A v5 calcula o tamanho do bitmap a partir do sector count real.

A inode table continua fixa em 512 sectors e o journal em 64.

O bitmap cresce até possuir ao menos um bit para cada data sector.

Se (B) é bitmap sectors e (D) é data sectors:

[
B cdot 512 cdot 8 ge D
]

e:

[
1 + B + 512 + 64 + D = total_sectors
]

O formatter itera até convergir.

Isso permite usar sectors além do antigo limite de 512 MiB.

## Compatibilidade v4/v3

Para versões 4 e 3, o decoder exige a geometria histórica fixa.

Ele valida:

- total sectors;
- bitmap location/size;
- inode location/count/size;
- data location/size;
- root inode;
- journal location/size.

Assim uma image antiga não é reinterpretada silenciosamente sob nova geometria.

Os tests alteram um superblock v5 de 512 MiB para v4 e confirmam mount, fsck, read e write.

## Localização do superblock

O superblock ocupa:

    LBA 0

Os fields significativos ocupam os primeiros 64 bytes.

O restante do sector de 512 bytes é zerado pelo encoder atual.

## Layout do superblock

| Offset | Tamanho | Campo |
|---:|---:|---|
| 0 | 4 | magic |
| 4 | 2 | version |
| 6 | 2 | sector size |
| 8 | 4 | total sectors |
| 12 | 4 | bitmap LBA |
| 16 | 4 | bitmap sectors |
| 20 | 4 | inode-table LBA |
| 24 | 4 | inode count |
| 28 | 4 | inode size |
| 32 | 4 | data LBA |
| 36 | 4 | data sectors |
| 40 | 4 | root inode |
| 44 | 4 | clean flag |
| 48 | 4 | generation |
| 52 | 4 | journal LBA |
| 56 | 4 | journal sectors |
| 60 | 4 | checksum |

Checksum cobre bytes 0 a 59.

## Checksum do superblock

ChrisFS usa checksum estilo FNV-1a de 32 bits:

    initial = 2166136261
    hash ^= byte
    hash *= 16777619

Formalmente:

[
checksum = FNV1a32(bytes[0..59])
]

Mismatch causa falha de decode.

## Validação de geometria

Para v5 o decoder verifica:

- bitmap presente;
- data region presente;
- inode count igual a 2048;
- journal com ao menos dois sectors;
- metadata regions ordenadas e não sobrepostas;
- data end dentro de total sectors;
- bitmap com bits suficientes para data region.

Também exige:

    inode_size = 128
    root_inode = 0

## Inode table

A tabela contém:

    CFS_INODE_COUNT = 2048

records fixos.

Cada record tem:

    CFS_INODE_SIZE = 128 bytes

Quatro inodes cabem em cada sector de 512 bytes.

Portanto são usados exatamente 512 sectors.

## Tipos de inode

Valores persistidos:

    0 = free
    1 = file
    2 = directory

Outros valores são inválidos segundo fsck atual.

## Layout do inode

| Offset | Tamanho | Campo |
|---:|---:|---|
| 0 | 2 | type |
| 2 | 2 | flags |
| 4 | 4 | file size |
| 8 | 4 | generation |
| 12 | 48 | 12 direct block LBAs |
| 60 | 4 | single-indirect LBA |
| 64 | 4 | double-indirect LBA |
| 68 | 4 | uid |
| 72 | 4 | gid |
| 76 | 4 | mode |
| 80 | 4 | triple-indirect LBA |
| 84 | 4 | mtime low |
| 88 | 4 | mtime high |
| 92 | 32 | reserved/zero no encoder atual |
| 124 | 4 | checksum |

O checksum cobre bytes 0 a 123.

## Checksum do inode

O mesmo helper FNV-1a-style é aplicado aos primeiros 124 bytes.

Se falhar, `cfs_inode_decode` rejeita o record.

Fsck classifica esse caso como:

    inode checksum

O host test corrompe um byte de checksum propositalmente e confirma detecção sem escrita no disco.

## Root inode

O root inode é:

    0

Na formatação, inode 0 vira directory.

Seu primeiro direct pointer referencia o primeiro data sector.

O formatter também marca o primeiro bit do bitmap porque esse bloco já pertence ao root.

## Allocation bitmap

O bitmap descreve **sectors da data region**, não LBAs absolutos.

O índice é:

[
i = lba - data_lba
]

Bit 1 significa sector alocado.

Cada bitmap sector contém:

[
512 cdot 8 = 4096
]

bits.

## Data blocks

A unidade de allocation é um sector de 512 bytes.

Sectors de data podem armazenar:

- file data;
- directory entries;
- single-indirect pointer tables;
- double-indirect tables;
- triple-indirect tables.

Pointer blocks contêm LBAs little-endian de 32 bits.

## Direct pointers

Cada inode possui 12 direct LBAs.

Capacidade direta:

[
12 cdot 512 = 6144
]

bytes.

## Single indirect

Um pointer block contém:

    512 / 4 = 128

pointers.

Logo single-indirect acrescenta 128 data blocks.

## Double indirect

O root double-indirect pode apontar para 128 single-indirect tables.

Capacidade:

[
128^2 = 16.384
]

data blocks.

## Triple indirect

Triple-indirect acrescenta:

[
128^3 = 2.097.152
]

possible data-block pointers.

Somando direct/single/double/triple, a árvore possui capacidade estrutural teórica de:

    2.113.676 blocks

antes de outros limites.

Na prática disk size e o field de file size de 32 bits impõem limites menores.

## Limite da API whole-file

`cfs_write()` e `cfs_truncate()` continuam usando o teto direct+single+double:

    CFS_MAX_BLOCKS = 16.524
    CFS_MAX_FILE_SIZE = 8.460.288 bytes

aproximadamente 8,06 MiB.

`tools/test_cfs_maxwrite.c` comprova que exatamente esse tamanho funciona e um byte a mais retorna `CFS_EFBIG`.

É limite da API, não do pointer tree inteiro.

## Limite de write_at

`cfs_write_at()` usa o caminho mais profundo e verifica:

    CFS_MAX_FILE_BYTES = data_sectors * 512

também sujeito ao arithmetic de 32 bits e ao file-size field de 32 bits do inode.

As APIs de escrita não possuem portanto o mesmo maximum-size contract.

## Formato de dirent

Cada directory entry ocupa:

    CFS_DIRENT_SIZE = 80 bytes

Layout:

| Offset | Tamanho | Campo |
|---:|---:|---|
| 0 | 4 | inode number |
| 4 | 1 | type |
| 5 | 1 | name length |
| 6 | 2 | flags |
| 8 | 64 | name bytes |
| 72 | 8 | reserved/zero |

O nome fica inline.

Não existe string table.

## Densidade de directory

Com records de 80 bytes em sector de 512:

    CFS_DIRENTS_PER_SECTOR = 6

por integer division.

Os 32 bytes restantes não formam uma sétima entry.

## Slots vazios

Uma entry é tratada como vazia quando inode ou name length é zero.

Como root inode é 0, dirents comuns não usam inode 0 como child target.

O root é alcançado pelas semantics do filesystem.

## Names e paths

Maximum component/name:

    64 bytes

Maximum path:

    512 bytes

Maximum depth:

    32 components

Comparação de names é byte-for-byte, logo case-sensitive.

Os tests demonstram que:

    foo
    Foo

são distintos.

## Sintaxe de path

O parser atual:

- permite leading `/`;
- rejeita empty interior components;
- rejeita trailing slash em path não-root;
- rejeita backslash;
- rejeita `.`;
- rejeita `..`;
- rejeita component >64 bytes;
- rejeita depth >32.

Root pode ser representado por path vazio ou `/` nas APIs que aceitam root.

## Limite de directory blocks

Directory traversal usa:

    CFS_DIR_MAX_BLOCKS =
    CFS_DIRECT_COUNT + CFS_PTRS_PER_BLOCK

isto é:

    12 + 128 = 140 blocks

É um limite de runtime para directories, embora files possam usar árvores mais profundas.

Com seis entries por sector, o teto simples de slots é 840 entries.

## Permission bits

Bits atuais:

    READ  = 1
    WRITE = 2
    EXEC  = 4
    WALK  = 8

e:

    CFS_PERM_ALL = 15

O inode contém `mode` e também os permission bits compatíveis em `flags`.

## Compatibilidade de permissions

O effective mode é escolhido nesta ordem:

1. `mode` se não zero;
2. low permission bits de `flags`;
3. para inode non-free legado, default all permissions.

Isso mantém compatibilidade com records anteriores.

## UID/GID

Novos inodes começam com:

    uid = 0
    gid = 0

O permission checker atual rejeita acesso quando `uid != 0`.

Portanto os fields uid/gid existem no formato, mas o runtime não implementa um modelo multi-user UNIX geral.

Na prática opera em torno de owner 0 e dos quatro permission bits ChrisFS.

## Modification time

O mtime é armazenado em:

    mtime_lo
    mtime_hi

formando:

[
mtime = lo | (hi << 32)
]

O clock atual é um valor interno monotonicamente incrementado, salvo quando caller define um valor não zero por `cfs_set_now()`.

O formato não define um epoch externo nesta revisão.

## Journal

ChrisFS reserva um metadata journal.

Constantes:

    JNL_MAGIC   = 0x4C4E4A43
    JNL_EMPTY   = 0
    JNL_BEGIN   = 1
    JNL_COMMIT  = 2
    JNL_MAX_REC = 30

O journal default ocupa 64 sectors.

## Header do journal

Primeiro sector:

| Offset | Tamanho | Campo |
|---:|---:|---|
| 0 | 4 | journal magic |
| 4 | 4 | sequence |
| 8 | 4 | state |
| 12 | 4 | record count |
| 16 | 4 | checksum |

Checksum cobre bytes 0 a 15.

O restante é zerado nas writes normais.

## Records do journal

Cada record usa dois sectors.

Em:

[
journal_lba + 1 + 2i
]

o metadata sector contém:

| Offset | Tamanho | Campo |
|---:|---:|---|
| 0 | 4 | target LBA |
| 4 | 4 | checksum do payload de 512 bytes |

O sector seguinte contém os 512 bytes completos de replacement data.

Com 30 records:

    1 + 30*2 = 61 sectors

são usados dentro da região default de 64.

## Semântica do journal

`jnl_begin` marca o superblock dirty e grava BEGIN.

Em metadata write, `jnl_log` salva replacement sector no journal antes de escrever o target metadata sector.

`jnl_commit` grava COMMIT, depois muda para EMPTY e finalmente marca o superblock clean.

No mount:

- EMPTY não exige replay;
- BEGIN é descartado como transaction incompleta;
- COMMIT reaplica os replacement sectors e depois limpa o journal.

É um pequeno **redo-oriented metadata journal**.

Não é undo log nem full data journal.

## Política para file data

Durante writes de file data, `jnl_data` faz com que sectors de conteúdo não sejam individualmente journaled.

Metadata é a parte protegida pelo journal.

Por isso journal saudável não deve ser interpretado como prova de atomicidade total diante de power loss.

Crash-consistency continua sendo área explícita de validação futura.

## Clean flag e generation

O superblock possui:

    clean
    generation

Transactions marcam dirty no início e clean após commit.

Operações também avançam generation conforme metadata muda.

Os fields ajudam a identificar state, mas não substituem checksums e journal validation.

## Mount

Mount bem-sucedido exige:

1. block device com sectors de 512 bytes;
2. superblock legível/válido;
3. versão suportada;
4. checksum e geometria válidos;
5. backing device grande o suficiente;
6. journal handling bem-sucedido;
7. root inode válido;
8. root sendo directory.

`cfs_mount` não reformata silenciosamente mídia inválida.

## Format

`cfs_format` exige block device writable de 512-byte sectors.

Ele:

1. deriva geometry v5;
2. zera metadata até o início de data;
3. marca bitmap bit 0;
4. inicializa todos os inode records com checksum válido;
5. inicializa root inode 0;
6. aponta root direct[0] ao primeiro data sector;
7. inicializa permissions do root;
8. zera o root data block;
9. grava superblock;
10. cria EMPTY journal;
11. flush.

## Fsck

`cfs_fsck` funciona como verificador read-only de invariants.

Verifica, entre outros:

- superblock checksum;
- journal state;
- inode checksums/types;
- block ranges;
- duplicate block ownership;
- missing bitmap bits;
- bitmap leaks;
- direct/indirect/double/triple trees;
- root type;
- directory cycles;
- duplicate names;
- invalid dirents;
- file size versus allocated blocks.

O host test confirma que corrupção é detectada e que fsck não escreve no disk.

## Modelo de resultado do fsck

Filesystem limpo retorna:

    CFS_OK

com reason:

    clean

Problemas estruturais retornam positive error count quando aplicável.

I/O/setup failures podem retornar negative ChrisFS error codes.

`cfs_fsck_reason()` fornece a primeira classificação.

## Error codes

A API expõe erros para:

- invalid argument;
- I/O;
- format;
- not found;
- already exists;
- no space;
- file too large;
- name too long;
- corruption;
- not mounted;
- not directory;
- not empty;
- is directory;
- cross-device;
- permission denied.

Esses numeric runtime codes não fazem parte automaticamente do on-disk format.

## Cache não é estado on-disk

O cache de 64 lines, hit/miss counters e age values pertencem ao runtime.

Não são serializados na image.

Uma disk image bruta não contém cache metadata.

## Histórico de migração

Existem readers explícitos para layouts v1 e v2 em:

    tools/cfs_migrate_v1v2.c
    tools/cfs_migrate_v2v3.c

Apesar dos filenames históricos, o destination path chama o `cfs_format()` atual.

Nesta revisão, portanto, media recém-criada pelo destination segue a implementação corrente, não necessariamente a versão histórica sugerida pelo nome da ferramenta.

Ferramentas novas devem declarar source/destination version de forma explícita.

## Evidência da v5

A suite v5 confirma que:

- image v5 de 512 MiB preserva addresses históricos;
- o mesmo superblock marcado como v4 monta;
- v4 read/write/fsck funciona;
- volume v5 maior registra sector count maior;
- data region ultrapassa antigo fim do disco;
- allocation pode ocorrer além do limite histórico de 512 MiB.

É evidência direta da principal mudança v5: dynamic volume geometry.

## Limitações atuais

ChrisFS v5 ainda não possui:

- extent trees;
- sparse-file contract formal;
- symbolic links;
- hard links;
- rich timestamps;
- general multi-user permissions;
- ACL lists;
- xattrs;
- checksums de ordinary data sectors;
- copy-on-write;
- snapshots;
- inode allocation acima de 2048 inodes;
- indexed large directories;
- full data journaling.

Esses recursos estão fora do formato atual.

## Regra de versionamento

Mudança incompatível precisa de nova filesystem version quando altera interpretação persistida de:

- superblock;
- inode;
- dirent;
- pointer tree;
- permission fields;
- journal records;
- checksum rules;
- bitmap semantics;
- geometry rules.

Compatibilidade antiga deve ser explícita, não inferida.

## Resumo de conformidade

Implementação v5 conforme precisa preservar:

- logical sector de 512 bytes;
- little-endian;
- magic `CFS1`;
- offsets/checksum do superblock v5;
- inode de 128 bytes com checksum;
- dirent de 80 bytes;
- names de até 64 bytes;
- bitmap por data sector;
- direct/single/double/triple pointers;
- root inode 0;
- journal header/record layout;
- dynamic geometry invariants.

Limites de API, como o whole-file ceiling de 8,06 MiB, devem ser separados da capacidade do formato on-disk.

## Nota de revisão

Esta especificação foi reconciliada contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

A mudança central da v5 é a geometria dinâmica de volume mantendo compatibilidade com images v4/v3 de geometria fixa. O formato já possui fields e pointer depth mais ricos que algumas APIs de alto nível, por isso capacidade do formato e capacidade da API precisam continuar claramente separadas.
