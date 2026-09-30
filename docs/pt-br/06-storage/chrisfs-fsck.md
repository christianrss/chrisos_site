---
id: chrisfs-fsck
lang: pt-br
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/cfs.h
  - kernel/fs/cfs.c
  - kernel/fs/cfs_format.h
  - kernel/fs/cfs_fsck.c
  - kernel/fs/fs_lock.h
  - kernel/fs/storage_limits.h
  - tools/test_cfs_fsck.c
  - tools/test_cfs_journal.c
  - tools/test_cfs_paths.c
  - tools/test_cfs_v5.c
  - tools/test_fuzz_cfs.c
symbols:
  - cfs_fsck
  - cfs_fsck_reason
  - fsck_maps_reset
  - note_block
  - note_ptr_table
  - check_dirents
  - walk_dir
  - cfs_super_decode
  - cfs_inode_decode
depends_on:
  - chrisfs
  - chrisfs-superblock
  - chrisfs-inodes
  - chrisfs-directories
  - chrisfs-journal
  - chrisfs-cache
related:
  - block-storage
  - resource-lifetime
  - testing-validation
---

# Verificação de consistência e detecção de corrupção no ChrisFS

## Escopo

`cfs_fsck` é o consistency checker atual do ChrisFS.

Ele é principalmente um **validador read-only**. Não reconstrói metadata, não corrige bitmap, não reconecta arquivos órfãos, não reescreve checksums e não escolhe automaticamente qual estrutura deve vencer quando duas discordam.

O checker procura inconsistências entre:

- superblock;
- estado do journal;
- allocation bitmap;
- inode table;
- ownership de direct/indirect blocks;
- type do root inode;
- graph de diretórios alcançável;
- blocks alocados mas não referenciados.

Ele executa sobre um `Cfs` já montado e entra no mesmo lock global usado pelas operações normais do filesystem.

Este capítulo documenta ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![Fluxo de validação do fsck do ChrisFS](../../assets/diagrams/chrisfs-fsck-pt-br.svg)

## Contrato de retorno

Filesystem limpo retorna:

~~~text
CFS_OK = 0
~~~

Quando encontra inconsistências estruturais, `cfs_fsck` normalmente retorna uma **contagem positiva de erros detectados**.

Falhas operacionais fatais retornam códigos negativos comuns do ChrisFS, como:

~~~text
CFS_EIO
CFS_EINVAL
CFS_ENOSPC
CFS_ENOTMOUNTED
CFS_ECORRUPT
~~~

Assim existem três classes:

~~~text
0       limpo
> 0     inconsistências detectadas
< 0     checker não conseguiu completar normalmente
~~~

## Reason string

`cfs_fsck_reason()` expõe uma string estática.

`set_reason` só grava quando o buffer ainda está vazio.

Logo:

~~~text
cfs_fsck_reason()
~~~

mostra o **primeiro motivo detectado**, não necessariamente o único nem o mais grave.

O retorno numérico positivo pode contar problemas adicionais que não aparecem na reason string.

Resultado limpo termina com:

~~~text
clean
~~~

## Design read-only

O checker faz reads do block device e altera apenas mapas/estado em memória.

Não chama writers normais de metadata nem `bd_write`.

`tools/test_cfs_fsck.c` registra o número de writes, corrompe checksum de inode, executa fsck e confirma que a contagem não aumenta.

A propriedade atual é:

~~~text
fsck detecta, mas não repara
~~~

## Serialização global

`cfs_fsck` começa com:

~~~text
CFS_LOCK()
~~~

Logo, executa sob o mesmo lock reentrante global das demais APIs ChrisFS.

Isso protege suas premissas contra mutações concorrentes feitas pelas APIs públicas.

O custo é bloquear operações normais enquanto o checker faz scans potencialmente grandes.

## Requisito de filesystem montado

fsck exige:

- `Cfs` não nulo;
- `fs->mounted != 0`;
- backing device não nulo.

Caso contrário retorna:

~~~text
CFS_ENOTMOUNTED
~~~

com reason:

~~~text
not mounted
~~~

Não é hoje uma ferramenta standalone para raw device desmontado.

## Etapa do superblock

O checker lê LBA 0 diretamente e chama:

~~~text
cfs_super_decode
~~~

Esse decoder valida:

- magic;
- versão suportada;
- sector size de 512 bytes;
- checksum do superblock;
- geometria fixa de v3/v4;
- inode count/root number em v5;
- ordering/capacidade das regiões v5.

Se o decode falha, fsck retorna:

~~~text
CFS_ECORRUPT
~~~

com reason:

~~~text
super checksum
~~~

Essa reason é mais ampla que a causa real: versão incompatível, geometria inválida e checksum ruim acabam agrupados nela.

## Relação com o tamanho do device

`cfs_mount` já verifica:

~~~text
dev->sector_count >= super.total_sectors
~~~

antes de marcar o filesystem como mounted.

fsck depende dessa pré-condição e não repete o mesmo teste explicitamente.

Se o device mudar depois do mount, reads posteriores ainda podem falhar com I/O error.

## Geometria copiada para globals do checker

Após decode, fsck guarda:

~~~text
data_lba
data_sectors
inode_lba
bitmap_lba
bitmap_sectors
journal_lba
~~~

em globals usados por:

- range checks;
- ownership;
- inode reads;
- directory traversal.

Como o checker usa scratch state global, o lock global faz parte do modelo de correção atual.

## Dois mapas de bitmap

fsck usa dois mapas.

### Allocation bitmap

~~~text
g_bitmap
~~~

recebe uma cópia completa do bitmap on-disk.

### Seen map

~~~text
g_seen
~~~

começa zerado e recebe bits conforme blocks aparecem em inodes e pointer trees.

No fim, os mapas são comparados.

O invariante principal é:

~~~text
block referenciado <=> block marcado allocated
~~~

dentro das limitações de cobertura do checker.

## Mapas fixos e dinâmicos

Para bitmaps até:

~~~text
CFS_BITMAP_SECTORS = 256
~~~

são usados arrays estáticos.

Para volumes v5 maiores, o checker aloca dinamicamente os dois mapas.

Memória aproximada:

~~~text
2 × bitmap_sectors × 512 bytes
~~~

além dos outros buffers.

Se a alocação falha, retorna:

~~~text
CFS_ENOSPC
~~~

com:

~~~text
bitmap size
~~~

Nesse caso ENOSPC significa falta de memória de trabalho do checker, não necessariamente falta de espaço no filesystem.

## Proteção aritmética do bitmap

Antes de alocar, fsck rejeita:

~~~text
bitmap_sectors == 0
~~~

e protege:

~~~text
bitmap_sectors × 512
~~~

contra overflow de 32 bits.

O decoder do superblock já cobre outros invariantes geométricos.

## Estado do journal

Antes de carregar o bitmap, fsck lê o header do journal diretamente.

Ele examina:

~~~text
magic
state
~~~

e pode reportar:

~~~text
journal magic
journal dirty
journal pending replay
~~~

Magic zero e CJNL EMPTY são aceitos.

## Check de journal é superficial

O fsck não recalcula o checksum do journal header.

Também não valida:

- sequence;
- nrec;
- payload checksums;
- target LBAs;
- bounds dos record slots.

`jnl_replay` no mount é mais estrito em parte desses pontos.

Logo, fsck faz um state precheck, não uma auditoria completa do journal.

## Clean flag não é erro por si só

Embora o superblock tenha:

~~~text
clean
~~~

`cfs_fsck` não incrementa error count somente porque:

~~~text
super.clean == 0
~~~

Um volume com dirty flag, journal EMPTY e todas as estruturas coerentes pode retornar:

~~~text
CFS_OK
reason = "clean"
~~~

Camadas superiores podem usar o dirty flag como motivo para executar fsck; o próprio checker decide com base nas estruturas que verifica.

## Leitura do bitmap

Todos os bitmap sectors declarados são lidos por `bd_read`.

Falha retorna:

~~~text
CFS_EIO
~~~

com:

~~~text
bitmap io
~~~

O cache normal do ChrisFS é bypassado.

## Scan de inodes

O checker percorre:

~~~text
id = 0 .. 2047
~~~

Para cada inode ele lê o setor correspondente e decodifica o record de 128 bytes.

Há quatro inodes por setor, mas a implementação faz um device read para cada inode ID.

Assim, os 512 setores da inode table podem ser lidos 2048 vezes.

É correto, porém ineficiente.

## Checksum de inode

Todo inode passa por:

~~~text
cfs_inode_decode
~~~

que valida checksum do payload de 124 bytes.

Falha incrementa errors e registra:

~~~text
inode checksum
~~~

Depois o checker pula os checks mais profundos daquele inode.

## Inodes livres

Se o inode é checksum-valid e:

~~~text
type == CFS_INODE_FREE
~~~

fsck o ignora.

Não exige que todos os demais campos estejam zerados.

Portanto um free inode com stale pointers e checksum válido não é automaticamente reportado.

Se os blocks ainda estiverem allocated e não forem referenciados por inode vivo, o leak scan final pode detectá-los.

## Type de inode

Todo inode não-free deve ser:

~~~text
CFS_INODE_FILE
CFS_INODE_DIR
~~~

Outro valor produz:

~~~text
inode type
~~~

e o checker não percorre sua block tree.

## Limite de size

Para inode vivo:

~~~text
max_bytes = data_sectors × 512
~~~

limitado a:

~~~text
0xFFFFFFFF
~~~

porque inode.size é 32-bit.

Se size ultrapassa esse teto:

~~~text
size vs blocks
~~~

é registrado.

## Validação rigorosa dos direct pointers

Para files:

~~~text
need = ceil(size / 512)
~~~

Nos 12 direct pointers:

- posição exigida por size deve ser não zero;
- posição além do EOF deve ser zero.

Violação gera:

~~~text
size vs blocks
~~~

É a parte mais rigorosa do contrato size-versus-blocks atual.

## Indirect occupancy é menos rigorosa

Depois dos direct checks, fsck percorre qualquer:

- single-indirect;
- double-indirect;
- triple-indirect.

Mas não calcula exatamente quais leaves deveriam existir com base em file size.

Assim, podem passar sem `size vs blocks`:

- arquivo cujo size exige indirect blocks, mas algumas leaves necessárias faltam;
- arquivo com indirect blocks extras além do EOF.

Os blocks existentes ainda são validados quanto a range/ownership/bitmap.

## Ownership de blocks

Todo data block válido passa por:

~~~text
note_block
~~~

que verifica:

1. LBA dentro da data region;
2. block ainda não visto;
3. bitmap marcando allocated.

Erros:

~~~text
block lba
duplicate block
bitmap missing
~~~

## Duplicate block

O seen map trata cada setor da data region como single-owner.

Se dois pointers de arquivos, diretórios ou pointer tables referenciam o mesmo block, o segundo produz:

~~~text
duplicate block
~~~

ChrisFS não possui reflink/shared-block model.

## Bitmap missing

Se metadata aponta para LBA válido mas o bitmap diz free:

~~~text
bitmap missing
~~~

é reportado.

É uma condição perigosa porque allocator posterior pode reutilizar block ainda referenciado.

## Traversal de pointer tables

`note_ptr_table` percorre árvores recursivamente.

Depth:

~~~text
1 single
2 double
3 triple
~~~

O próprio pointer-table block passa primeiro por `note_block`.

Depois os children de 32 bits são percorridos.

Em depth 1, children são data blocks.

Em depths maiores, são pointer tables intermediárias.

## I/O em pointer table

Falha de leitura retorna:

~~~text
CFS_EIO
~~~

com:

~~~text
indirect io
~~~

É fatal para aquela execução do checker.

## Preservação do scratch buffer

Traversal usa um scratch sector global.

Antes de recursão, copia os 512 bytes para buffer local na stack, desce e depois restaura.

Como a profundidade máxima é fixa em 3, o uso de stack é limitado.

## Diretórios com double/triple pointers

Runtime de diretórios usa somente:

~~~text
12 direct + 128 single-indirect blocks
~~~

Porém o ownership scan genérico também aceita e percorre double/triple pointers não zero em inode DIR.

Esses blocks podem ser marcados como legitimamente seen mesmo que lookup normal nunca os use.

fsck não rejeita essa divergência entre semântica de runtime e block ownership genérico.

## Invariante do root

Inode 0 deve ser:

~~~text
CFS_INODE_DIR
~~~

Caso contrário:

~~~text
root type
~~~

é registrado.

O directory walk verifica root novamente, então um root inválido pode contribuir mais de um erro numérico com a mesma first reason.

## Directory graph walk

Depois do scan global de blocks, fsck chama:

~~~text
walk_dir(root)
~~~

Ele usa:

~~~text
g_anc[2048]
~~~

como ancestor set.

Ao entrar em diretório marca 1; ao sair volta para 0.

## Detecção de cycles

Se traversal chega em inode DIR já marcado como ancestor:

~~~text
dir cycle
~~~

é reportado.

Isso detecta referência a ancestral no path atual.

## Sem visited set permanente

`g_anc` registra apenas ancestry corrente.

Depois que a subtree termina, o bit é limpo.

Portanto dois parents diferentes podem apontar para o mesmo directory inode e o fsck percorre a subtree duas vezes sem reportar “multiple parents”.

ChrisFS não define directory hard links como feature, então esse é um invariante ausente.

Um graph corrompido acíclico com muitas referências compartilhadas também pode gerar traversal repetido.

## Cobertura de blocks de diretório

`check_dirents` percorre somente:

~~~text
CFS_DIRECT_COUNT = 12
~~~

direct blocks.

Runtime permite:

~~~text
12 direct + 128 single-indirect
= 140 blocks
~~~

Portanto dirents armazenados na parte single-indirect ficam fora do namespace validation.

Os blocks ainda entram no ownership scan genérico, mas names e inode references não são verificados.

## Checks de dirent

Para cada dirent ativo nos direct blocks, fsck verifica:

- inode ID menor que 2048;
- name_len até 64;
- checksum do child inode;
- recursão em child directories.

ID inválido ou nome grande gera:

~~~text
dirent
~~~

## Validação de nome incompleta

O checker não aplica toda a sintaxe do path parser aos dirents corrompidos.

Não rejeita explicitamente nomes contendo:

- slash;
- backslash;
- NUL embutido dentro de name_len;
- `.`;
- `..`.

Entries com inode zero ou name_len zero são tratadas como vazias.

Assim, a validação de namespace é mais estreita que a validade aceita pelas APIs de path.

## Duplicate names só dentro do mesmo block

O name table local é resetado a cada setor de diretório.

Então duplicatas entre as seis entries do mesmo block podem ser detectadas.

O mesmo nome em dois directory blocks diferentes pode passar.

Runtime lookup retorna o primeiro match na ordem do scan.

## Type do dirent não é comparado

Dirent tem byte type redundante.

fsck carrega o child inode, mas não exige:

~~~text
dirent.type == inode.type
~~~

Metadata stale/corrompida nesse campo passa.

## Directory size não é reconciliado

O `size` de directory deveria acompanhar aproximadamente:

~~~text
live dirents × 80
~~~

O checker não reconta entries e compara com inode.size.

Assim, directory size stale pode passar se o resto estiver consistente.

## Reachability de inodes

O scan global valida todos os inodes vivos e seus blocks.

O graph walk cobre somente o namespace alcançável pela parte que ele percorre.

Não existe um mapa exigindo:

~~~text
todo inode allocated não-root
deve ser alcançável do root
~~~

Um orphan inode estruturalmente válido pode passar sem erro de reachability.

## Múltiplas referências ao mesmo file inode

Não existe link-count field.

fsck também não conta quantos dirents apontam para cada file inode.

Dois nomes para o mesmo inode file não são reportados como violação específica.

## Leak scan final

Ao fim, percorre todos os data-sector bits.

Se:

~~~text
bitmap = allocated
seen = 0
~~~

reporta:

~~~text
bitmap leak
~~~

Isso encontra, por exemplo:

- rollback de allocation falho;
- alguns bugs de release;
- blocks alocados que perderam linkage.

## Leak scan para no primeiro leak

O loop faz:

~~~text
errors++
break
~~~

no primeiro leak.

Múltiplos leaked blocks somam apenas um erro nessa etapa.

A reason continua sendo o primeiro problema detectado em toda a execução.

## Clean flag versus consistência real

Dirty flag pode coexistir com estrutura coerente.

Da mesma forma, clean flag pode estar setado mesmo com bitmap/inodes inconsistentes.

fsck prioriza o conteúdo real das estruturas verificadas, mas não cruza formalmente clean flag com journal state.

## Memória e escala

O maior custo de memória é:

~~~text
bitmap copy + seen bitmap
~~~

Há também:

~~~text
2048 × 65 bytes
≈ 130 KiB
~~~

para tabela de nomes, além de ancestor map e sector buffers.

Em volumes v5 maiores, memória dos mapas cresce junto do bitmap.

## Complexidade de I/O

Aproximadamente:

- 1 read de superblock;
- 1 read de journal header;
- todos os bitmap sectors;
- 2048 inode reads;
- todos os pointer-table blocks referenciados;
- direct directory blocks no namespace walk;
- child inode reads adicionais.

Como inode table tem 512 setores, os 2048 reads atuais representam fator de quatro evitável.

## Sem aceleração pelo cache normal

fsck usa `bd_read` direto.

Vantagens:

- vê conteúdo do device diretamente;
- não depende do replacement state do cache.

Custo:

- repeated inode/namespace reads não são absorvidos pelo cache.

## Evidência de validação

### `test_cfs_fsck.c`

Verifica:

- filesystem limpo;
- corrupção de inode checksum;
- reason exata `inode checksum`;
- ausência de writes pelo fsck.

### `test_cfs_journal.c`

Verifica:

- journal limpo;
- BEGIN forçado;
- resultado positivo;
- reason `journal dirty`.

### `test_cfs_paths.c`

Executa várias operações de namespace e exige fsck limpo antes e depois de remount.

### `test_cfs_v5.c`

Confirma compatibilidade v4 e fsck limpo em imagem legacy-sized.

O caso v5 maior testa principalmente geometry/allocation.

### `test_fuzz_cfs.c`

Executa 200 sequências pseudo-random determinísticas de operações de path e exige fsck limpo no fim.

É fuzz de API, não fuzz de corrupção raw on-disk.

## Casos sem teste dedicado

Não há testes específicos para várias reasons/invariantes:

- `block lba`;
- `duplicate block`;
- `bitmap missing`;
- `bitmap leak`;
- `inode type`;
- `root type`;
- `dir cycle`;
- duplicate names entre blocks;
- pointer corruption;
- orphan inode;
- dirent corrompido em single-indirect directory block;
- dirent type inválido;
- stale directory size;
- required indirect block ausente;
- indirect block extra além de EOF;
- combinações clean/journal;
- falha de alocação dos mapas dinâmicos.

## Limitações atuais

Na revisão documentada:

- validator only, sem repair;
- exige filesystem montado;
- first reason oculta categorias posteriores;
- positive error count não enumera necessariamente cada block corrompido;
- clean flag não é erro por si só;
- journal check não valida checksum/records;
- inode table é relida 4× mais que o necessário;
- free inode fields não são normalizados;
- file size é estritamente cruzado apenas com direct pointers;
- indirect occupancy obrigatória não é validada completamente;
- indirect blocks além de EOF podem ser aceitos;
- double/triple pointers em diretórios não são rejeitados;
- namespace scan cobre apenas direct directory blocks;
- name syntax check é incompleto;
- duplicate names só são detectados dentro do mesmo block;
- dirent type não é comparado ao inode type;
- directory size não é reconciliado;
- orphan inodes não são rejeitados;
- multiple parents de directory não são rejeitados;
- múltiplos nomes para o mesmo file inode não possuem link-count check;
- leak scan para no primeiro leak;
- memória cresce com bitmap size;
- não existe raw corruption fuzz suite cobrindo os invariantes.

## Fronteira de roadmap

Um fsck mais forte deveria considerar:

- execução standalone em raw device;
- modos validate-only e repair;
- relatório estruturado de múltiplos erros;
- inode/LBA/contexto por erro;
- batching de inode sectors;
- ocupação exata direct/single/double/triple baseada em file size;
- constraints específicos para pointers de diretório;
- traversal de todos os directory blocks suportados pelo runtime;
- full name validation;
- duplicate-name check global por diretório;
- consistency entre dirent type e inode type;
- reachability de todo inode allocated;
- link-count/parent-count invariants;
- validação completa de journal header/records;
- cruzamento clean flag/journal state;
- enumeração de todos os leaks;
- políticas de repair;
- corruption injection determinístico para cada reason;
- fuzzing de imagens de block para superblock, inode, pointers e dirents.

Esses itens permanecem roadmap até implementação e validação.

## Mapa de source e revisão

`kernel/fs/cfs_fsck.c` contém checker state, ownership maps, pointer traversal, directory graph walk e leak comparison. `kernel/fs/cfs_format.h` fornece decoders e geometry validation. `kernel/fs/cfs.h` define status codes e API pública do fsck. `kernel/fs/fs_lock.h` fornece serialização global. A evidência principal vem de `test_cfs_fsck.c`, `test_cfs_journal.c`, `test_cfs_paths.c`, `test_cfs_v5.c` e `test_fuzz_cfs.c`.

Todas as afirmações sobre comportamento atual foram reconciliadas com ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
