---
id: chrisfs-inodes
lang: pt-br
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/cfs_format.h
  - kernel/fs/cfs.c
  - kernel/fs/cfs_fsck.c
  - kernel/fs/storage_limits.h
  - tools/test_cfs_indirect.c
  - tools/test_cfs_maxwrite.c
  - tools/test_cfs_fsck.c
symbols:
  - CfsInode
  - cfs_inode_encode
  - cfs_inode_decode
  - inode_read
  - inode_write
  - inode_alloc
  - inode_release
  - inode_ptr_free
  - inode_ptr_prune
  - free_ptr_levels
  - block_alloc
  - block_free
  - ptr_block_get
  - ptr_block_set
  - file_lba
  - cfs_write
  - cfs_write_at
  - cfs_truncate
  - cfs_unlink
  - cfs_fsck
depends_on:
  - chrisfs
  - chrisfs-superblock
related:
  - chrisfs-directories
  - chrisfs-journal
  - chrisfs-cache
  - chrisfs-fsck
---

# Inodes e block indirection do ChrisFS

## Escopo

Os inodes do ChrisFS são os objetos persistentes que ligam nomes e directory entries à metadata e aos data blocks de arquivos.

O formato atual usa ABI fixa de inode com 128 bytes, tabela fixa de 2048 slots e quatro níveis de endereçamento:

~~~text
12 direct pointers
1 single-indirect pointer
1 double-indirect pointer
1 triple-indirect pointer
~~~

Todos os block pointers armazenados são LBAs absolutos de 32 bits relativos ao `BlockDevice` visível ao filesystem. Eles não são índices relativos à data region.

Este capítulo acompanha o inode desde sua representação on-disk até allocation, lookup, crescimento, shrink, release e validação pelo fsck.

O comportamento atual foi reconciliado com ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![Endereçamento de blocos por inode no ChrisFS](../../assets/diagrams/chrisfs-inodes-pt-br.svg)

## Geometria fixa da inode table

Constantes atuais:

~~~text
inode size       128 bytes
inode count      2048
inode sectors    512
sector size      512 bytes
~~~

Logo:

~~~text
4 inodes por setor
2048 × 128 = 512 × 512 = 262.144 bytes
~~~

Um compile-time assertion em `storage_limits.h` garante que a inode table configurada corresponde exatamente a esses valores.

No v5, a inode table pode mudar de posição porque o bitmap cresce, mas seu tamanho e número de slots continuam fixos.

## Identificadores de inode

IDs de inode são índices da tabela:

~~~text
0 .. 2047
~~~

Inode 0 é reservado permanentemente como:

~~~text
CFS_ROOT_INODE = 0
~~~

Allocation normal começa em 1.

Restam, portanto:

~~~text
2047 slots não-root
~~~

para arquivos e diretórios em conjunto.

Não existe crescimento dinâmico da inode table.

## Layout on-disk do inode

Cada inode ocupa exatamente 128 bytes.

| Offset | Tamanho | Campo |
|---:|---:|---|
| 0 | 2 | type |
| 2 | 2 | flags |
| 4 | 4 | size |
| 8 | 4 | generation |
| 12 | 48 | 12 direct pointers |
| 60 | 4 | single-indirect pointer |
| 64 | 4 | double-indirect pointer |
| 68 | 4 | uid |
| 72 | 4 | gid |
| 76 | 4 | mode |
| 80 | 4 | triple-indirect pointer |
| 84 | 4 | mtime low |
| 88 | 4 | mtime high |
| 92 | 32 | reservado/zero no encode |
| 124 | 4 | checksum |

O encoder zera explicitamente os 128 bytes antes de preencher campos.

Por isso bytes 92..123 são reservados e emitidos hoje como zero.

O decoder valida o checksum, mas não atribui significado a esses bytes. Um inode gerado manualmente pode conter valores não zero nessa região e ainda ser aceito se o checksum for recalculado.

## Tipos de inode

Valores atuais:

~~~text
0 = free
1 = file
2 = directory
~~~

Runtime e fsck rejeitam tipos não zero fora desse conjunto.

Um inode livre é representado logicamente por uma struct zerada, porém codificada com checksum válido.

Isso significa que um slot livre no disk não é simplesmente 128 bytes zero: o campo final de checksum possui valor calculado por `cfs_inode_encode`.

## Checksum do inode

O checksum usa a mesma função de 32 bits semelhante a FNV-1a usada no superblock.

Ele cobre:

~~~text
bytes 0..123
~~~

e é armazenado nos bytes 124..127.

Portanto protege:

- type;
- flags;
- size;
- generation;
- todos os block pointers;
- uid/gid/mode;
- mtime;
- bytes reservados 92..123.

`inode_read` transforma mismatch em:

~~~text
CFS_ECORRUPT
~~~

O teste host de fsck altera explicitamente o checksum do inode 1 e verifica que o checker reporta:

~~~text
inode checksum
~~~

sem escrever no disk.

## Mapeamento de leitura e escrita

Quatro inodes compartilham um setor.

Para inode ID `id`:

~~~text
sector = inode_lba + id / 4
offset = (id % 4) × 128
~~~

`inode_read`:

1. verifica ID contra `super.inode_count`;
2. lê o setor pelo cache;
3. decodifica e valida o record selecionado.

`inode_write`:

1. lê o setor de 512 bytes;
2. re-encoda somente o slot desejado;
3. grava o setor inteiro pelo cache.

Updates de inode são, portanto, read-modify-write no nível de setor.

## Política de allocation

`inode_alloc` faz scan linear:

~~~text
ID 1 -> 2047
~~~

e para no primeiro inode cujo type é `CFS_INODE_FREE`.

Ao encontrar slot livre, inicializa inicialmente como file:

~~~text
type       = FILE
generation = fs.super.generation + 1
uid        = 0
gid        = 0
mode       = READ|WRITE|EXEC|WALK
flags      = mesmos quatro bits de compatibilidade
~~~

Criação de diretório primeiro obtém esse inode file-like e depois altera o type para directory antes de ligá-lo ao parent.

Não existe inode bitmap nem allocation hint.

Pior caso:

~~~text
O(2048)
~~~

inode reads por allocation.

Com tabela fixa atual, o custo é limitado, mas não escala para namespace grande.

## Falhas durante allocation

O próprio `inode_alloc` persiste o inode novo antes de devolver seu ID.

Depois, a operação de alto nível precisa inserir a directory entry.

Se essa inserção falha, `cfs_create` e `cfs_mkdir` tentam zerar novamente o inode.

Isso é rollback local, não transação geral de recursos.

Crash ou falha de I/O entre allocation e linkage ainda pode exigir análise posterior por fsck.

## Permissões persistidas no inode

Campos atuais:

~~~text
uid
gid
mode
flags
~~~

Novos objetos recebem:

~~~text
uid = 0
gid = 0
mode = 15
flags = 15
~~~

Bits:

~~~text
READ  = 1
WRITE = 2
EXEC  = 4
WALK  = 8
~~~

Para compatibilidade, effective mode é escolhido assim:

1. usa `mode` se não zero;
2. usa os permission bits de `flags` se existirem;
3. se ambos forem zero em inode não-free, assume todas as permissões.

O runtime atual também rejeita objetos cujo uid não seja zero.

Logo, o formato tem uid/gid, mas ainda não implementa ownership Unix completo.

## Generation e modification time

Um inode recém-alocado recebe generation derivada da geração atual do filesystem.

Whole-file writes executam:

~~~text
inode.generation++
~~~

Modification time é armazenado em:

~~~text
mtime_lo
mtime_hi
~~~

que juntos formam 64 bits.

`inode_stamp` incrementa o relógio lógico global do ChrisFS e grava o valor nesses campos.

O timestamp depende do clock do filesystem, não é consultado diretamente do hardware dentro da inode layer.

## Block pointers são LBAs absolutos

Os pointers contêm logical block addresses dentro do device do filesystem.

Em filesystem GPT, são LBAs dentro da `PartView`, não LBAs físicos do disk inteiro.

Pointer não zero deve satisfazer:

~~~text
super.data_lba <= lba < super.data_lba + super.data_sectors
~~~

O bitmap representa os mesmos blocks por índice relativo:

~~~text
bitmap index = lba - data_lba
~~~

Data blocks e pointer-table blocks usam o mesmo allocator e bitmap.

## Formato dos pointer blocks

Cada setor de pointer table contém:

~~~text
512 / 4 = 128
~~~

LBAs little-endian de 32 bits.

Não há header, magic, checksum ou tag de nível no pointer block.

Sua interpretação depende somente de qual campo do inode o referencia e da profundidade do traversal.

Pointer zero significa “não alocado”.

## Endereçamento direto

Os primeiros:

~~~text
12 blocks
~~~

vêm de:

~~~text
direct[0..11]
~~~

Capacidade:

~~~text
12 × 512 = 6144 bytes
~~~

Não exige metadata block adicional além do inode.

## Single indirection

Depois dos direct blocks, `indirect` aponta para um pointer block com 128 LBAs de data.

Capacidade adicional:

~~~text
128 × 512 = 65.536 bytes
~~~

Capacidade acumulada direct + single:

~~~text
140 blocks
71.680 bytes
~~~

A implementação de diretórios para propositalmente nesse nível, por isso também possui ceiling estrutural de 140 blocks.

## Double indirection

`double_indirect` aponta para tabela com até 128 pointer blocks intermediários.

Cada um pode apontar para 128 data blocks.

Capacidade adicional:

~~~text
128 × 128 = 16.384 blocks
16.384 × 512 = 8.388.608 bytes
~~~

Acumulado direct + single + double:

~~~text
16.524 blocks
8.460.288 bytes
~~~

Esse valor é:

~~~text
CFS_MAX_FILE_SIZE
~~~

e funciona como hard limit de `cfs_write` e `cfs_truncate`.

## Triple indirection

Após a faixa double-indirect, `file_lba` usa `triple_indirect`.

Estrutura:

~~~text
inode.triple_indirect
    -> tabela nivel 1
        -> tabela nivel 2
            -> data block
~~~

A região triple contribui:

~~~text
128³ = 2.097.152 blocks
~~~

Árvore completa:

~~~text
12 + 128 + 16.384 + 2.097.152
= 2.113.676 blocks
= 1.082.202.112 bytes
≈ 1,008 GiB
~~~

Esse é o ceiling estrutural da árvore de pointers, não o tamanho efetivo exposto pelas APIs públicas.

## Limites efetivos de tamanho de arquivo

Existem três ceilings distintos no código atual.

### APIs whole-file

`cfs_write` e `cfs_truncate` limitam:

~~~text
CFS_MAX_FILE_SIZE
= 8.460.288 bytes
≈ 8,07 MiB
~~~

Exatamente até o final de double indirection.

### APIs incrementais

`cfs_write_at` e `cfs_read_at` usam:

~~~text
CFS_MAX_FILE_BYTES
= CFS_DATA_SECTORS × 512
= 536.444.416 bytes
≈ 511,6 MiB
~~~

O detalhe importante é que `CFS_DATA_SECTORS` aqui é a **constante compile-time da geometria legada de 512 MiB**, e não `fs->super.data_sectors`.

Portanto, aumentar um filesystem v5 não aumenta esse ceiling de API.

Writes incrementais podem atingir triple indirection, mas somente até o limite legado de ~511,6 MiB.

### Limite da pointer tree

`file_lba` permite até:

~~~text
CFS_MAX_BLOCKS_V4 = 2.113.676 blocks
~~~

desde que também:

~~~text
block < fs->super.data_sectors
~~~

Esse limite é maior que o exposto pela API incremental em volumes normais.

O nome `CFS_MAX_BLOCKS_V4` é histórico e pouco intuitivo, porque o valor inclui triple indirection usada pelo código atual.

## Allocation de blocks

`file_lba(..., alloc=1)` cria estruturas ausentes sob demanda.

Data ou pointer block novo vem de `block_alloc`.

`block_alloc`:

1. procura bit livre no bitmap começando em `alloc_hint`;
2. marca como usado;
3. zera os 512 bytes do block;
4. se o zero write falhar, tenta limpar o bit;
5. avança `alloc_hint`;
6. retorna o LBA absoluto.

Assim, blocks reutilizados são zerados antes de serem expostos por um inode.

## Construção lazy da árvore

A árvore indireta só cresce quando necessário.

No primeiro block single-indirect:

1. aloca `inode.indirect`;
2. consulta a entry correspondente;
3. aloca data block se zero;
4. grava o LBA novo no pointer block.

Double indirection adiciona um nível intermediário.

Triple pode adicionar dois níveis intermediários antes do data block.

Pointer-table writes passam pelo mesmo cache write-through da metadata comum.

## Lacunas de rollback

Crescimento da árvore não é uma transação all-or-nothing.

Exemplos:

- data block pode ser alocado e `ptr_block_set` falhar depois;
- intermediate pointer table pode ser alocada sem conseguir ser ligada ao parent;
- inode em memória pode receber novo root pointer e falhar antes de persistir o inode.

Nessas janelas, bitmap pode continuar marcando blocks que não são mais alcançáveis por metadata persistente.

fsck reporta isso como:

~~~text
bitmap leak
~~~

mas não corrige automaticamente.

## Invariante não-sparse

O fsck atual espera que arquivos normais possuam blocks para a faixa implicada por `inode.size`.

Para direct blocks, ausência de pointer necessário vira:

~~~text
size vs blocks
~~~

ChrisFS não define representação on-disk de sparse holes.

## `write_at` distante pode quebrar esse invariante

Ao estender um arquivo, `cfs_write_at` executa:

~~~text
inode.size = offset + size
~~~

e aloca apenas blocks realmente tocados a partir de `offset`.

Ele não aloca nem zera todos os blocks entre EOF antigo e um offset novo distante.

Exemplo: escrever um byte no block 8 de arquivo vazio pode deixar direct blocks 0..7 como zero enquanto o inode size declara que esses bytes existem.

Leitura sequencial posterior pode encontrar pointer ausente e retornar:

~~~text
CFS_ECORRUPT
~~~

e fsck pode reportar:

~~~text
size vs blocks
~~~

Isso não é sparse-file support funcional; é uma lacuna atual no caminho de extensão.

Caller seguro deve evitar extensão que salte full blocks ainda não alocados.

## Shrink por `cfs_write`

Ao substituir por conteúdo menor, `cfs_write`:

1. calcula old/new block counts;
2. reescreve/aloca os blocks que permanecem;
3. libera bitmap bits dos blocks além do novo EOF;
4. chama `inode_ptr_prune`;
5. persiste o inode menor.

Para arquivos que já estão dentro de `CFS_MAX_FILE_SIZE`, o pruning cobre direct/single/double conforme o novo count.

## Pruning de pointer structures

`inode_ptr_prune` consegue:

- limpar direct pointers não usados;
- limpar entries não usadas do single-indirect;
- liberar double-indirect inteiro quando deixa de ser necessário;
- liberar intermediate tables excedentes;
- limpar leaves excedentes em double-indirect.

Quando o arquivo passa a precisar no máximo de 12 blocks, chama `inode_ptr_free`, que também libera metadata da árvore triple-indirect.

## Triple-size files e whole-file rewrite

Arquivo ampliado por `cfs_write_at` acima de:

~~~text
CFS_MAX_FILE_SIZE
~~~

não pode depois ser substituído por `cfs_write`.

Antes de começar a escrita, `cfs_write` considera:

~~~text
inode.size > CFS_MAX_FILE_SIZE
~~~

como:

~~~text
CFS_ECORRUPT
~~~

`cfs_truncate` termina delegando para `cfs_write`, portanto sofre a mesma limitação.

Assim, triple-indirect files podem ser criados por writes incrementais, mas whole-file rewrite/truncate não os suporta.

Unlink continua sendo o caminho prático de liberação.

## Release de inode de arquivo

`inode_release` em regular file calcula o block count a partir de size e:

1. resolve cada block via `file_lba(..., alloc=0)`;
2. libera cada data block;
3. libera pointer-table structures com `inode_ptr_free`;
4. zera o inode;
5. persiste-o como free.

Para triple-indirect file, folhas de dados são liberadas primeiro e a hierarquia de pointer tables depois.

## Teardown de pointer tables

`inode_ptr_free` libera diretamente:

- single-indirect table;
- todas as second-level tables e o root double-indirect;
- estrutura triple-indirect via `free_ptr_levels`.

No triple case, `free_ptr_levels` libera recursivamente pointer-table blocks.

Ele não libera por si só os data leaves do triple tree; `inode_release` de regular file já percorreu e liberou essas folhas antes.

Essa separação só é correta quando o caller já tratou os data blocks.

## Leak no release de diretório acima de direct blocks

Diretórios podem crescer para:

~~~text
12 direct + 128 single-indirect data blocks
~~~

`dir_remove` zera dirents, mas não libera directory blocks vazios nem reduz a pointer tree.

Quando o diretório finalmente fica vazio e é removido, `inode_release` entra no branch de objeto não-file e libera somente:

~~~text
direct[0..11]
~~~

antes de chamar `inode_ptr_free`.

Para `n->indirect`, `inode_ptr_free` libera o pointer-table block, porém **não percorre os directory data blocks apontados por ele**.

Logo, diretório que no passado cresceu além de 12 blocks pode deixar seus single-indirect directory blocks alocados após `rmdir`.

Esses blocks ficam inalcançáveis, mas continuam marcados no bitmap, podendo aparecer no fsck como leak.

É bug atual de resource lifetime, não semântica planejada.

## Comportamento de `block_free`

Free de block apenas limpa o bit correspondente no bitmap.

Os 512 bytes antigos não são zerados imediatamente.

Eles são zerados se o block for selecionado novamente por `block_alloc`.

Consequências:

- reallocation comum não entrega conteúdo antigo ao novo arquivo;
- análise raw do disk ainda pode recuperar bytes do block free antes da reutilização;
- corrupção de metadata que referencia block livre pode expor conteúdo residual.

Não existe garantia de secure delete.

## Modelo de ownership do fsck

fsck mantém bitmap “seen” separado do allocation bitmap.

Para cada data/pointer block referenciado verifica:

1. LBA dentro da data region;
2. block ainda não referenciado por outro owner;
3. allocation bitmap marcando o block como usado.

Erros:

~~~text
block lba
duplicate block
bitmap missing
~~~

Depois de visitar todos os inodes, procura bits usados no bitmap que nunca apareceram em “seen”.

Isso gera:

~~~text
bitmap leak
~~~

e captura várias falhas de lifetime, embora não faça repair.

## Traversal das árvores no fsck

Para:

~~~text
inode.indirect
~~~

fsck percorre um nível.

Para:

~~~text
inode.double_indirect
~~~

percorre dois.

Para:

~~~text
inode.triple_indirect
~~~

percorre três.

Pointer tables e data blocks contam como blocks possuídos.

Logo, metadata indireta também consome capacidade normal da data region e precisa de bitmap bit.

## Validação de file size no fsck

Para files, fsck calcula máximo pelo volume montado:

~~~text
max_bytes = super.data_sectors × 512
~~~

limitado a:

~~~text
0xFFFFFFFF
~~~

porque `inode.size` é de 32 bits.

Também verifica os direct pointers contra o block count exigido por size.

Entretanto, essa checagem explícita de presença não é reproduzida com a mesma completude para cada posição single/double/triple; as árvores profundas são principalmente percorridas por range/ownership.

Assim, a validação de completude de large-file pointers é menos rigorosa que a de direct blocks.

## Evidência de validação

### Single indirection

`test_cfs_indirect.c` grava e lê:

~~~text
70.000 bytes
~~~

valor maior que direct-only e que exige single indirection.

Depois executa fsck.

### Whole-file maximum

`test_cfs_maxwrite.c` testa exatamente:

~~~text
CFS_MAX_FILE_SIZE
CFS_MAX_FILE_SIZE + 1
~~~

e confirma sucesso no primeiro e `CFS_EFBIG` no segundo.

O caso máximo percorre double indirection.

### Inode checksum

`test_cfs_fsck.c` corrompe checksum do inode 1 e confirma detecção read-only.

### Ausência de teste dedicado para triple

Não existe hoje `test_cfs_triple`, teste de boundary grande de `write_at` ou teste de sparse-gap no source tree.

Triple indirection está implementada, mas possui menos evidência explícita que single/double.

## Complexidade

### Inode allocation

~~~text
O(numero de inode slots)
~~~

com máximo atual fixo em 2048.

### Direct lookup

~~~text
O(1)
~~~

sem pointer-block read.

### Single indirection

O(1) conceitual, com um pointer-table access.

### Double indirection

O(1) conceitual, com até dois pointer-table accesses.

### Triple indirection

O(1) conceitual, com até três pointer-table accesses.

A profundidade fixa mantém lookup assintoticamente constante, mas o custo de I/O cresce por nível e depende do cache.

### File release

Release de regular file é:

~~~text
O(numero de file blocks)
~~~

porque `inode_release` resolve e libera cada data block antes de desmontar pointer tables.

## Limitações atuais

Na revisão documentada:

- inode table fixa em 2048 entries;
- apenas 2047 objetos não-root;
- inode allocation linear;
- inode size fixo em 128 bytes;
- file size do inode em 32 bits;
- block pointers absolutos de 32 bits;
- pointer blocks sem checksum/tag próprios;
- dados e pointer metadata compartilham o mesmo bitmap;
- rollback incompleto em crescimento multi-block;
- não existe sparse-file representation;
- `write_at` distante pode criar blocks intermediários ausentes;
- whole-file APIs param em ~8,07 MiB;
- APIs incrementais usam limite legado de ~511,6 MiB, não a capacidade v5 dinâmica;
- triple-indirect files não podem ser reescritos/truncados pela whole-file API;
- triple indirection não tem boundary test dedicado;
- block free não zera dados imediatamente;
- release de diretório pode vazar single-indirect data blocks;
- fsck não valida presença obrigatória com igual rigor em todas as posições profundas.

## Fronteira de roadmap

Uma camada de inode/blocos mais forte deveria considerar:

- inode allocation indexada ou por bitmap;
- contrato unificado de file size baseado no volume montado;
- file sizes e LBAs de 64 bits;
- sparse holes explícitos ou rejeição de extensão distante;
- rollback completo em falhas de crescimento da árvore;
- pointer blocks protegidos por checksum ou outro mecanismo;
- traversal genérico compartilhado por allocation, pruning, fsck e release;
- liberação correta de todos os directory indirect blocks;
- truncate para triple-indirect files;
- validação exata de occupancy em árvores profundas;
- testes dedicados nas fronteiras direct/single/double/triple;
- failure injection em cada estágio de pointer allocation.

Esses itens permanecem roadmap até serem implementados e validados de forma reproduzível.

## Mapa de source e revisão

`kernel/fs/cfs_format.h` define ABI persistente de inode e checksum. `kernel/fs/storage_limits.h` define inode count, fan-out e size constants. `kernel/fs/cfs.c` implementa inode I/O, allocation, block mapping, growth, pruning e release. `kernel/fs/cfs_fsck.c` valida checksums, block ranges, duplicate ownership e bitmap leaks. `tools/test_cfs_indirect.c`, `test_cfs_maxwrite.c` e `test_cfs_fsck.c` são a evidência host-side principal.

Todas as afirmações sobre comportamento atual neste capítulo foram reconciliadas com ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
