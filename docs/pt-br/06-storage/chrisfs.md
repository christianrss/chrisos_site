---
id: chrisfs
lang: pt-br
type: technical-chapter
volume: 06-storage
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/fs/cfs.c
  - kernel/fs/cfs.h
  - kernel/fs/cfs_format.h
  - kernel/fs/storage_limits.h
symbols:
  - cfs_format
  - cfs_mount
  - cfs_read
  - cfs_write
  - cfs_fsck
depends_on:
  - block-storage
related:
  - installation-real-hardware
---

# ChrisFS: estruturas on-disk, alocação e journal

## Papel do filesystem

Filesystem transforma um array de blocos em objetos persistentes nomeados, diretórios, metadata e regras de alocação. Correção precisa sobreviver aos limites de shutdown e às falhas cobertas pelo modelo de consistência.

ChrisFS é o filesystem nativo do workspace e instalação.

## Superbloco

Superblock descreve geometria e versão. A fonte atual possui generation, clean flag, journal, total sectors, bitmap, inode region e data region.

Encoder grava campos little-endian de largura fixa e checksum. Decoder valida magic, versão, sector size, checksum e geometria antes de confiar nos offsets.

## Geometria dinâmica

`cfs_geom_for_count` calcula bitmap conforme total de setores mantendo inode/journal fixos. Volume de 512 MiB preserva posições compatíveis com v4, enquanto volumes maiores suportados podem ampliar bitmap.

## Inodes

Inode guarda tipo, tamanho, generation, ponteiros de dados, identidade/permissões e tempo.

O formato atual contém direct, indirect, double-indirect e triple-indirect.

```text
inode
 ├── direct
 ├── indirect -> pointers
 ├── double -> pointers -> pointers
 └── triple -> três níveis
```

## Diretórios e paths

Dirent associa nome a inode e tipo. Path resolution divide componentes e os procura em diretórios. Validação de nomes e profundidade é parte da segurança do parser de caminho.

## Bitmap e alloc_hint

Bitmap registra unidades livres/ocupadas. `alloc_hint` evita reiniciar toda busca no começo, o que anteriormente tornava cópias grandes muito caras durante instalação.

## Cache e journal

`Cfs` contém cache de setores com contadores de hit/miss. Journal fornece begin/log/commit/replay. Journal define uma política de transação; não significa ausência universal de corrupção.

A ordem entre escrita do log, commit e aplicação final determina recuperação após mount não limpo.

## Locking

ChrisFS usa lock yielding e reentrante, com identidade por CPU no kernel. Não deve ser tomado em interrupt handler.

## Permissões e fsck

O formato define bits read/write/execute/walk. `cfs_fsck` verifica invariantes cruzadas de metadata, ranges, alocação e estrutura.

## Evolução de formato

Formato de filesystem é ABI persistente. Alterar struct C não basta. Encode/decode explícitos evitam depender de padding, alinhamento ou layout do compilador e tornam compatibilidade/migração decisões conscientes.
