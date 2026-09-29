---
id: chrisfs-directories
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
  - kernel/fs/storage_limits.h
  - tools/test_cfs_paths.c
symbols:
  - PathParts
  - CfsDirent
  - parse_path
  - walk_parent
  - walk_full
  - name_equal
  - dir_find
  - dir_count
  - dir_add
  - dir_remove
  - list_dir_inode
  - cfs_list
  - cfs_list_at
  - cfs_create
  - cfs_mkdir
  - cfs_rmdir
  - cfs_unlink
  - cfs_rename
depends_on:
  - chrisfs
  - chrisfs-inodes
related:
  - chrisfs-journal
  - chrisfs-cache
  - chrisfs-fsck
---

# Diretórios e resolução de paths no ChrisFS

## Escopo

Diretórios do ChrisFS são inodes do tipo directory cujos data blocks contêm directory entries de tamanho fixo.

Não existe B-tree separado, hash table de nomes, formato especial de inode para diretório ou índice de diretórios. Lookup de nomes é scan linear sobre blocks e entries.

A camada atual combina quatro responsabilidades:

- codificação persistente de dirents;
- parsing de path;
- traversal enraizado em root;
- mutação do namespace.

A implementação é compacta, mas essa simplicidade faz a correção depender de ordem de scan, estado dos inodes e serialização de nível superior.

Este capítulo documenta ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![Traversal de paths e lookup de diretórios no ChrisFS](../../assets/diagrams/chrisfs-directories-pt-br.svg)

## Modelo de inode de diretório

Diretório usa a mesma `CfsInode` de arquivo.

O campo que o distingue é:

~~~text
type = CFS_INODE_DIR
~~~

Os dados vivem em blocks normais da data region alocados por `file_lba`.

A implementação limita diretórios a:

~~~text
CFS_DIR_MAX_BLOCKS
= CFS_DIRECT_COUNT + CFS_PTRS_PER_BLOCK
= 12 + 128
= 140 blocks
~~~

Logo, diretórios usam apenas direct e single-indirect addressing.

Double e triple indirection não fazem parte do contrato de traversal de diretório.

## ABI persistente de dirent

Cada `CfsDirent` ocupa:

~~~text
80 bytes
~~~

Layout on-disk:

| Offset | Tamanho | Campo |
|---:|---:|---|
| 0 | 4 | inode |
| 4 | 1 | type |
| 5 | 1 | name_len |
| 6 | 2 | flags |
| 8 | 64 | name |
| 72 | 8 | padding reservado zerado |

O encoder zera os 80 bytes antes de gravar os campos.

A área persistente do nome possui exatamente:

~~~text
CFS_NAME_MAX = 64 bytes
~~~

Nomes são byte sequences delimitadas por tamanho, não strings NUL-terminated no disk.

## Entries por block

Com setores de 512 bytes:

~~~text
512 / 80 = 6 dirents completos
~~~

Seis entries consomem:

~~~text
6 × 80 = 480 bytes
~~~

restando:

~~~text
32 bytes sem uso
~~~

em cada setor de diretório.

Esses 32 bytes finais não pertencem a nenhum dirent.

## Capacidade estrutural máxima

Com 140 blocks e seis entries por block:

~~~text
140 × 6 = 840 entries
~~~

Esse é um ceiling estrutural.

O filesystem inteiro possui somente 2047 inode slots não-root, então o total global de objetos também limita a capacidade prática.

## Representação de entry vazia

O runtime considera uma entry ativa quando:

~~~text
e.inode != 0
&& e.name_len != 0
~~~

Dirent removido é totalmente zerado.

Como inode 0 é reservado para root e root não aparece como child dirent, usar inode zero como marcador de vazio é compatível com o namespace atual.

## Campo type redundante

Cada dirent grava um byte de type.

`dir_add` coloca nele o tipo do inode filho.

Porém lookup e listing não o tratam como autoridade:

- `dir_find` devolve o inode number;
- callers carregam o inode;
- `list_dir_inode` usa `inode.type`.

O fsck também não compara hoje:

~~~text
dirent.type
~~~

com:

~~~text
child inode.type
~~~

Logo, esse type pode ficar stale sem detecção.

## Flags do dirent

O campo `flags` de 16 bits é codificado e decodificado, mas não possui semântica ativa no namespace atual.

Entries novas são zeradas e normalmente ficam com flags zero.

Não há feature negotiation para flags não zero.

## Comparação de nomes

`name_equal` executa:

1. comparação exata de tamanho;
2. comparação byte a byte.

Assim, nomes são:

- case-sensitive;
- byte-sensitive;
- sem Unicode normalization;
- sem locale.

Os testes verificam explicitamente que:

~~~text
foo
Foo
~~~

são nomes diferentes.

## Estrutura de path

O parser preenche `PathParts`:

~~~text
ncomp
start[32]
len[32]
s
total
~~~

Ele não aloca memória nem copia os componentes.

Offsets e tamanhos apontam diretamente para a string original do caller.

Portanto a string precisa permanecer válida durante a operação.

## Tamanho máximo do path

O máximo aceito é:

~~~text
CFS_PATH_MAX = 512 bytes
~~~

Um path com exatamente 512 bytes não-NUL é aceito se os componentes também forem válidos.

513 bytes retornam:

~~~text
CFS_ENAMETOOLONG
~~~

O terminador NUL não conta no limite.

## Limite por componente

O máximo é:

~~~text
CFS_COMP_MAX
= CFS_NAME_MAX
= 64 bytes
~~~

64 bytes são aceitos.

65 retornam:

~~~text
CFS_ENAMETOOLONG
~~~

## Profundidade máxima

O número máximo de componentes é:

~~~text
CFS_PATH_DEPTH = 32
~~~

Um path com 33 componentes retorna:

~~~text
CFS_EINVAL
~~~

O teste host cobre esse caso.

## Sintaxe de root

O parser aceita:

~~~text
""
"/"
~~~

como root.

Paths comuns podem ser:

~~~text
GAMES/A.TXT
~~~

ou:

~~~text
/GAMES/A.TXT
~~~

Ambos começam em root.

ChrisFS não possui current working directory nesta camada.

Path sem slash inicial continua sendo root-relative.

## Sintaxe rejeitada

O parser rejeita:

- separadores repetidos, como `A//B`;
- trailing slash, como `A/B/`;
- backslash;
- `.`;
- `..`;
- componentes em excesso;
- componentes maiores que 64 bytes.

Depois de remover um slash inicial, outro slash imediato é visto como componente vazio.

Logo:

~~~text
//A
~~~

é inválido.

## Sem entries dot

Diretórios não contêm:

~~~text
.
..
~~~

O parser rejeita esses componentes.

Também não existe parent pointer persistido no inode de diretório.

Isso simplifica o formato, mas relações de ancestralidade precisam ser inferidas percorrendo entries a partir do root.

## Traversal enraizado

Todo lookup começa em:

~~~text
CFS_ROOT_INODE
= 0
~~~

`walk_full` resolve todos os componentes.

`walk_parent` resolve todos exceto o leaf e devolve:

- parent inode ID;
- índice do componente final.

Create, unlink, mkdir, rmdir e rename usam parent traversal porque o leaf pode ainda não existir.

## Permissão WALK

Em componentes intermediários, traversal exige:

~~~text
CFS_PERM_WALK
~~~

no diretório filho que será atravessado.

Para:

~~~text
A/B/C
~~~

WALK é testado em A e B.

Não há teste explícito de WALK em root antes do primeiro lookup.

O objeto final não precisa de WALK se nenhum componente vier depois.

## Lookup de diretório

`dir_find`:

1. carrega o directory inode;
2. verifica type;
3. percorre block numbers 0..139;
4. resolve cada block por `file_lba(..., alloc=0)`;
5. lê cada block existente;
6. percorre seis dirents;
7. compara name length e bytes;
8. devolve o primeiro inode correspondente.

Se o inode ID armazenado ultrapassa a tabela fixa, retorna:

~~~text
CFS_ECORRUPT
~~~

## Mascaramento de erro durante scan

Vários scans fazem:

~~~text
if (file_lba(...) != CFS_OK)
    continue;
~~~

Isso ocorre em helpers como:

- `dir_find`;
- `dir_count`;
- `dir_add`;
- `dir_remove`;
- `list_dir_inode`.

O problema é que `file_lba(..., alloc=0)` pode falhar não apenas porque o logical block não está alocado, mas também por corrupção ou falha de I/O em pointer table.

Assim, alguns erros podem ser transformados em:

- `CFS_ENOENT`;
- contagem menor;
- listing incompleto;
- tentativas posteriores de allocation.

A camada precisaria distinguir explicitamente “logical block ausente” de erro de corrupção/I/O.

## Complexidade de lookup

Não existe índice de nomes.

Pior caso:

~~~text
140 blocks × 6 entries
= 840 dirents
~~~

Para path de profundidade `d`:

~~~text
O(d × entries_por_diretorio)
~~~

no pior caso simples.

O limite fixo mantém o custo limitado, mas continua linear.

## Campo size do diretório

O `size` do inode não representa bytes de storage alocados.

`dir_add` soma:

~~~text
CFS_DIRENT_SIZE = 80
~~~

por entry adicionada.

`dir_remove` subtrai 80 quando possível.

Portanto é essencialmente:

~~~text
numero logico de entries vivas × 80
~~~

e não o tamanho físico do diretório.

Lookup, listing e emptiness scan não usam esse campo como única autoridade.

## Inserção

`dir_add` primeiro procura um slot vazio em todos os blocks existentes.

Guarda o primeiro encontrado.

Se não houver slot, faz novo scan 0..139 e chama `file_lba(..., alloc=1)` no primeiro block ausente.

Ao alocar block novo:

1. persiste o inode do diretório para salvar o pointer novo;
2. escolhe slot 0 como destino.

O dirent recebe:

- inode ID;
- inode type;
- name length;
- name bytes.

Depois o parent size aumenta em 80 e o inode é persistido.

## Reuso de slots

Entries removidas são zeradas, mas o block permanece alocado.

Uma inserção futura reutiliza o primeiro slot vazio.

Isso reduz churn, mas significa que blocks de diretório só crescem até o inode inteiro ser removido.

Não há compaction.

## Remoção

`dir_remove` procura linearmente o nome.

Ao encontrar:

1. zera os 80 bytes do dirent;
2. grava o setor;
3. reduz directory size em 80 quando possível;
4. grava o inode.

Ele não:

- desloca entries;
- libera block que ficou vazio;
- poda pointer block que deixou de ser necessário.

Por isso diretório pode manter vários blocks alocados mesmo depois de perder quase todas as entries.

## Teste de vazio

`dir_count` percorre os blocks e conta entries com:

~~~text
e.inode != 0
&& e.name_len != 0
~~~

`cfs_rmdir` exige count zero.

É mais robusto que confiar somente em:

~~~text
inode.size == 0
~~~

quando size e contents divergirem.

## Criação de diretório

`cfs_mkdir`:

1. parseia path;
2. resolve parent;
3. exige WRITE no parent;
4. garante que destino não existe;
5. inicia journal;
6. aloca inode;
7. muda type de FILE para DIR;
8. adiciona entry no parent;
9. incrementa filesystem generation;
10. faz commit.

Se inserir no parent falha, tenta zerar o inode recém-alocado.

Diretório novo começa sem data block; o primeiro só é alocado quando aparece o primeiro filho.

## Criação de arquivo

`cfs_create` segue lógica semelhante, mas atualmente não envolve inode allocation + dirent insertion em `jnl_begin`/`jnl_commit`.

Assim, create possui cobertura de crash mais fraca que mkdir.

Há rollback local tentando zerar o inode se `dir_add` falhar.

## Listing

`cfs_list` chama:

~~~text
cfs_list_at(fs, "", ...)
~~~

para listar root.

`cfs_list_at` resolve o path e chama `list_dir_inode`.

Para cada dirent ativo:

1. copia o nome para buffer temporário NUL-terminated;
2. carrega child inode;
3. chama callback com:
   - name;
   - inode size;
   - inode type.

Se callback retorna não zero, esse valor é propagado imediatamente.

Isso permite interrupção antecipada da listagem.

## Lacuna de permissão no diretório alvo

Traversal exige WALK apenas nos diretórios intermediários.

Depois de resolver o target, `list_dir_inode` não chama:

~~~text
cfs_perm_need
~~~

no diretório listado.

Logo, listing não exige explicitamente READ ou WALK no próprio target, desde que o path até ele possa ser resolvido.

É uma lacuna na política de permissões.

## Semântica de rename

`cfs_rename` suporta rename no mesmo diretório e move entre diretórios dentro do mesmo ChrisFS.

O fluxo:

1. resolve source/destination parents;
2. verifica WRITE no source parent;
3. verifica WRITE no destination parent se for diferente;
4. resolve source;
5. rejeita destination existente;
6. carrega source inode;
7. adiciona dirent no destino apontando para o mesmo inode;
8. remove dirent original;
9. incrementa generation.

Dados e block tree do inode não são copiados.

## Rename é add-then-remove

A ordem é:

~~~text
dir_add(destination)
dir_remove(source)
~~~

Não há journal envolvendo a operação e não há rollback se a remoção falhar.

Falha após o destination add pode deixar dois nomes apontando para o mesmo inode.

Como ChrisFS não define hard links como feature normal, isso é estado parcial de rename.

## Bug de ciclo em rename de diretório

Não existe ancestor check antes de mover diretório.

Considere:

~~~text
A/
A/B/
~~~

Um rename como:

~~~text
A -> A/B/C
~~~

pode resolver destination parent `A/B`, inserir em B uma entry para inode A e então remover A do root.

O resultado cria ciclo:

~~~text
A -> B -> A
~~~

Como não existe parent pointer persistido, prevenção exige teste explícito de descendência antes do move.

Esse check não existe atualmente.

## Unlink

`cfs_unlink` aceita somente regular file.

Exige:

- WRITE no parent;
- WRITE no target file.

Inicia journal, remove dirent, libera inode e blocks, incrementa generation e commit.

Aplicado a diretório retorna:

~~~text
CFS_EISDIR
~~~

## rmdir

`cfs_rmdir` exige:

- target diferente de root;
- target type DIR;
- WRITE no parent;
- WRITE no diretório alvo;
- `dir_count == 0`.

Depois remove o dirent e libera o inode.

Diferente de unlink/mkdir, rmdir não está dentro de journal begin/commit.

A limitação de release de diretórios que já chegaram ao single-indirect está documentada no capítulo de inodes: data blocks indiretos podem permanecer leaked após rmdir.

## Traversal de diretórios no fsck

O fsck executa um graph walk separado.

Ele valida:

- inode ID de dirent;
- name length;
- checksum do child inode;
- ciclos de diretório;
- nomes duplicados em parte do namespace percorrido.

Porém há lacunas importantes.

## fsck percorre apenas direct directory blocks

`check_dirents` usa:

~~~text
for (b = 0; b < CFS_DIRECT_COUNT; b++)
~~~

ou seja:

~~~text
12 blocks
72 dirents no máximo
~~~

Runtime permite 140 blocks por diretório.

Entries no single-indirect não passam pelo namespace walk do fsck.

Os blocks em si ainda podem aparecer no traversal genérico de ownership, mas seus dirents não são verificados quanto a:

- inode ID inválido;
- erro de nome;
- recursão;
- cycle.

## Duplicate-name check reinicia por block

Dentro de cada direct block, fsck reseta o contador local de nomes.

Assim, duplicatas dentro do mesmo setor podem ser encontradas.

Porém o conjunto não é mantido entre blocks.

Dois nomes iguais em blocks diferentes podem escapar desse check.

No runtime, `dir_find` devolverá o primeiro encontrado na ordem de scan.

## Sem cross-check de type

fsck carrega o inode referenciado, mas não compara seu type com o byte type do dirent.

Dirent pode dizer FILE e apontar para DIR, ou vice-versa, sem esse mismatch ser reportado.

Listing usa o inode type real, ocultando o stale type do dirent para callers.

## Sem accounting completo de reachability

fsck percorre todos os inodes para ownership de blocks e separadamente percorre diretórios a partir do root.

Ele não mantém um mapa completo exigindo que todo inode alocado não-root seja alcançável do namespace.

Um inode válido, alocado e sem dirent pode não ser reportado diretamente como orphan.

Da mesma forma, múltiplos dirents podem apontar para um mesmo file inode sem existir um link-count invariant, porque ChrisFS não tem link-count field.

## Evidência de validação

`tools/test_cfs_paths.c` cobre:

- root directories;
- nested paths;
- slash inicial opcional;
- nomes case-sensitive;
- root/nested listing;
- rename no mesmo diretório;
- rename entre diretórios;
- unlink;
- rejeição de rmdir não-vazio;
- rmdir vazio;
- rejeição de `.`;
- rejeição de `..`;
- rejeição de 33 componentes;
- persistência após remount;
- fsck final.

Não cobre hoje:

- boundary 64/65 de componente;
- boundary 512/513 de path;
- repeated slash;
- trailing slash;
- capacidade perto de 840 entries;
- diretórios usando blocks acima dos 12 direct;
- nomes duplicados entre blocks após corrupção;
- rename de diretório para seu próprio descendente;
- permissão do diretório alvo em listing;
- falha de I/O injetada em pointer table durante scan.

## Perfil de complexidade

### Lookup

~~~text
O(blocks alocados × 6)
~~~

com ceiling estrutural de 840 entries.

### Add

No pior caso faz um scan por slots livres e outro por block ausente:

~~~text
O(capacidade do diretorio)
~~~

com constante maior que lookup.

### Remove

~~~text
O(capacidade do diretorio)
~~~

### Path resolution

Para profundidade `d`:

~~~text
O(d × scan_do_diretorio)
~~~

Não existe dentry/path cache na camada ChrisFS.

## Limitações atuais

Na revisão documentada:

- nomes são bytes case-sensitive;
- sem Unicode normalization;
- sem `.` ou `..`;
- sem current working directory;
- sem parent pointer;
- componente máximo de 64 bytes;
- path máximo de 512 bytes;
- profundidade máxima de 32;
- lookup linear;
- ceiling estrutural de 840 entries;
- dirent type e flags com semântica fraca/redundante;
- sem checksum por block de diretório;
- sem índice;
- sem compaction/shrink de blocks;
- alguns erros de `file_lba` são mascarados durante scans;
- listing não exige permissão explícita no target dir;
- create/rmdir/rename não são journaled uniformemente;
- rename pode deixar links duplicados em falha parcial;
- rename pode criar cycle ao mover diretório para descendente;
- fsck valida namespace somente nos 12 direct blocks;
- duplicate-name detection do fsck é local a cada block;
- fsck não compara dirent type com inode type;
- fsck não exige reachability completa de todos os inodes a partir do root;
- rmdir pode vazar indirect directory blocks, como descrito no capítulo de inodes.

## Fronteira de roadmap

Uma camada de diretórios mais forte deveria considerar:

- resultado distinto para “logical block não alocado” em vez de mascarar erros;
- lookup indexado ou hash;
- permission checks explícitos no target directory;
- create/rmdir/rename transacionais;
- rollback de rename;
- prevenção de descendant cycle;
- compaction/pruning de directory blocks;
- fsck cobrindo single-indirect directory blocks;
- validação de nomes duplicados no diretório inteiro;
- consistency check entre dirent type e inode type;
- reachability de inodes alocados;
- link-count explícito se múltiplos nomes vierem a ser suportados;
- testes de boundary/corruption para parser e diretórios grandes.

Esses itens permanecem roadmap até serem implementados e cobertos por testes reproduzíveis.

## Mapa de source e revisão

`kernel/fs/cfs_format.h` define ABI persistente do dirent de 80 bytes. `kernel/fs/cfs.h` define limites de path e `PathParts`. `kernel/fs/cfs.c` implementa parsing, traversal, lookup, listing e mutações do namespace. `kernel/fs/cfs_fsck.c` implementa a validação atual do graph de diretórios. `tools/test_cfs_paths.c` fornece a principal evidência host-side.

Todas as afirmações sobre comportamento atual neste capítulo foram reconciliadas com ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
