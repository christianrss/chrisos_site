---
id: chrisfs-superblock
lang: pt-br
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/cfs_format.h
  - kernel/fs/cfs.c
  - kernel/fs/cfs_fsck.c
  - kernel/fs/storage.c
  - kernel/fs/storage_limits.h
  - kernel/fs/block_device.h
  - tools/test_cfs_v5.c
  - tools/test_cfs_host.c
symbols:
  - CfsSuper
  - cfs_get16
  - cfs_get32
  - cfs_put16
  - cfs_put32
  - cfs_checksum
  - cfs_super_legacy
  - cfs_geom_for_count
  - cfs_super_geom_ok
  - cfs_super_encode
  - cfs_super_decode
  - cfs_format
  - cfs_mount
  - storage_format_if_empty
  - disk_has_cfs
  - cfs_fsck
depends_on:
  - chrisfs
  - block-storage
  - partitions-gpt
related:
  - chrisfs-inodes
  - chrisfs-journal
  - chrisfs-fsck
  - installation-real-hardware
---

# Superblock e geometria de volume do ChrisFS

## Escopo

O superblock do ChrisFS é a primeira fronteira de confiança entre um block device bruto e o filesystem. Ele identifica o volume, seleciona a versão do formato on-disk e descreve posição e tamanho do bitmap, inode table, journal e data region.

ChrisFS grava o superblock no logical block address 0 do device visível ao filesystem. Em uma instalação GPT isso significa LBA 0 da `PartView` da partição ChrisFS, e não necessariamente o LBA físico 0 do disk.

A implementação atual monta três versões on-disk:

~~~text
v3  formato de compatibilidade
v4  geometria fixa de 512 MiB
v5  formato atual com geometria dinâmica
~~~

Versões 1 e 2 não são montadas diretamente pelo decoder atual. Existem ferramentas históricas de migração para formatos mais antigos.

Este capítulo documenta ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![Fluxo de validação e geometria do superblock ChrisFS](../../assets/diagrams/chrisfs-superblock-pt-br.svg)

## Por que o superblock é sensível

Quase todos os endereços posteriores do filesystem derivam de campos do superblock.

Um valor corrompido como:

~~~text
inode_lba
journal_lba
data_lba
bitmap_sectors
~~~

pode redirecionar reads e writes posteriores para setores errados.

Por isso ChrisFS não converte o setor 0 diretamente em uma struct C. Ele interpreta campos little-endian de largura definida, verifica checksum e aplica invariantes de geometria antes do mount.

O decoder faz parte da superfície de corrupção e segurança do filesystem.

## Layout persistente de bytes

O encoder grava os primeiros 64 bytes do setor de 512 bytes assim:

| Offset | Tamanho | Campo | Significado |
|---:|---:|---|---|
| 0 | 4 | magic | `CFS_MAGIC` |
| 4 | 2 | version | v3, v4 ou v5 |
| 6 | 2 | sector size | precisa ser 512 |
| 8 | 4 | total sectors | sector count visível ao filesystem |
| 12 | 4 | bitmap LBA | primeiro setor do bitmap |
| 16 | 4 | bitmap sectors | comprimento do bitmap |
| 20 | 4 | inode LBA | primeiro setor da inode table |
| 24 | 4 | inode count | atualmente precisa ser 2048 |
| 28 | 4 | inode size | precisa ser 128 |
| 32 | 4 | data LBA | primeiro data sector |
| 36 | 4 | data sectors | tamanho da data region |
| 40 | 4 | root inode | precisa ser 0 |
| 44 | 4 | clean | estado clean/dirty |
| 48 | 4 | generation | contador de geração |
| 52 | 4 | journal LBA | primeiro setor do journal |
| 56 | 4 | journal sectors | comprimento do journal |
| 60 | 4 | checksum | checksum dos bytes 0..59 |

Bytes 64 a 511 são zerados por `cfs_super_encode`, mas o decoder não os inspeciona nem inclui no checksum.

Eles funcionam hoje como espaço reservado, não como metadata protegida por integridade.

## Magic

A constante de magic é:

~~~text
0x31534643
~~~

Em little-endian, os bytes são:

~~~text
43 46 53 31
 C  F  S  1
~~~

ou:

~~~text
CFS1
~~~

O mesmo magic é mantido nas versões atuais; a versão é indicada separadamente pelo campo de 16 bits.

## Codificação little-endian

ChrisFS usa helpers explícitos:

~~~text
cfs_get16
cfs_get32
cfs_put16
cfs_put32
~~~

Isso torna o ABI persistente independente de packing de struct e alinhamento do compilador.

Todos os campos multibyte atuais do superblock são little-endian.

Não existem campos de 64 bits no superblock. Capacidade e coordenadas de região ficam, portanto, limitadas pelo block ABI de 32 bits.

## Checksum do superblock

`cfs_checksum` inicia com:

~~~text
2166136261
~~~

e para cada byte executa:

~~~text
hash ^= byte
hash *= 16777619
~~~

É a mesma estrutura aritmética do FNV-1a de 32 bits.

O encoder calcula sobre exatamente:

~~~text
bytes 0..59
~~~

e armazena o resultado no offset 60.

O decoder recalcula esses 60 bytes antes de aceitar a geometria.

### O que o checksum cobre

Ele cobre:

- magic;
- version;
- sector size;
- todos os campos de geometria;
- root inode;
- clean flag;
- generation;
- geometria do journal.

Ele não cobre:

- o próprio campo de checksum;
- bytes 64..511;
- qualquer outro setor do filesystem.

É detecção de corrupção, não autenticação criptográfica. Quem pode regravar o setor também pode recalcular o checksum.

## Seleção de versão

`cfs_super_decode` aceita exatamente:

~~~text
CFS_VERSION         = 5
CFS_VERSION_V4      = 4
CFS_VERSION_COMPAT  = 3
~~~

Qualquer outro valor falha.

No mount, qualquer falha interna do decoder é convertida em:

~~~text
CFS_EFORMAT
~~~

em vez de expor seus códigos negativos internos.

## Geometria legada v3/v4

Para v3 e v4, o decoder não aceita geometria arbitrária do disk.

Ele exige exatamente:

~~~text
total sectors      1.048.576
bitmap LBA         1
bitmap sectors     256
inode LBA          257
inode count        2.048
inode size         128
journal LBA        769
journal sectors    64
data LBA           833
data sectors       1.047.743
root inode         0
~~~

Com setores de 512 bytes:

~~~text
1.048.576 setores = 512 MiB
~~~

Depois da validação, `cfs_super_legacy` reconstrói esses valores em `CfsSuper`.

Os campos on-disk `clean` e `generation` são preservados.

## Por que v3/v4 são fixos

O contrato antigo assume endereços conhecidos de metadata.

Isso oferece duas propriedades:

- imagens antigas são determinísticas;
- geometria corrompida não pode redirecionar metadata nessas versões.

O custo é que um filesystem antigo não cresce automaticamente se for colocado em um block device maior.

`cfs_mount` aceita backing device maior que o total registrado, mas o filesystem continua limitado à geometria de 512 MiB.

## Geometria dinâmica v5

A versão 5 move a geometria principal para campos validados do superblock.

`cfs_geom_for_count` deriva o layout usando `sector_count` do block device.

Partes fixas:

~~~text
superblock          1 setor
inode table       512 setores
journal            64 setores
~~~

O bitmap é a parte variável.

Cada setor de bitmap contém:

~~~text
512 bytes × 8 bits = 4096 allocation bits
~~~

e consegue representar até 4096 data sectors.

## Equação da geometria

Defina:

~~~text
T = total sectors
B = bitmap sectors
F = 1 + 512 + 64 = 577 setores fixos
D = data sectors
~~~

O layout v5 gerado satisfaz:

~~~text
D = T - F - B
B × 4096 >= D
~~~

O algoritmo itera até o bitmap escolhido ser suficiente para a data region que sobra depois de reservar esse próprio bitmap.

As posições geradas são:

~~~text
bitmap_lba  = 1
inode_lba   = 1 + B
journal_lba = inode_lba + 512
data_lba    = journal_lba + 64
~~~

e:

~~~text
data_lba + data_sectors = total_sectors
~~~

para volumes criados por `cfs_format`.

## Exemplo: tamanho histórico de 512 MiB

Para:

~~~text
T = 1.048.576
~~~

o cálculo produz:

~~~text
B             = 256
bitmap_lba    = 1
inode_lba     = 257
journal_lba   = 769
data_lba      = 833
data_sectors  = 1.047.743
~~~

Assim, v5 preserva os endereços físicos antigos quando o volume tem o tamanho histórico.

Isso é verificado por `test_cfs_v5.c`.

## Exemplo: device um pouco maior

O teste v5 usa:

~~~text
T = 1.048.576 + 8.192
  = 1.056.768 setores
~~~

A geometria derivada é:

~~~text
bitmap sectors  258
inode LBA       259
journal LBA     771
data LBA        835
data sectors    1.055.933
~~~

O teste marca blocks iniciais como ocupados e confirma que um novo arquivo consegue alocar além da antiga fronteira de 512 MiB.

Isso prova que a geometria dinâmica é operacional.

## Menor geometria v5 representável

A função rejeita:

~~~text
total <= 578 setores
~~~

Com 579 setores ela consegue construir:

~~~text
bitmap         1 setor
inode table  512 setores
journal        64 setores
data            1 setor
~~~

Esse único data sector é consumido imediatamente pelo root directory durante format.

Logo, o volume é estruturalmente formatável, mas praticamente não possui espaço para arquivos.

O caminho normal de auto-format no boot é mais conservador: root discovery só considera blank writable disks com pelo menos o tamanho histórico `STOR_DISK_SECTORS`.

## Escala máxima no ABI atual

`BlockDevice.sector_count` é `uint32_t`.

Com setores de 512 bytes, a capacidade teórica endereçável fica pouco abaixo de:

~~~text
2 TiB
~~~

Os campos de geometria do v5 também são de 32 bits.

Próximo do máximo de sector count, o bitmap sozinho fica com aproximadamente 512 MiB.

Como `cfs_format` zera metadata um setor de 512 bytes por vez até `data_lba`, formatar um volume desse tamanho exige da ordem de um milhão de writes de metadata antes da data region.

O limite não é apenas de endereço; o método atual de inicialização também pesa.

## Validator de geometria v5

`cfs_super_geom_ok` exige hoje:

- bitmap sector count diferente de zero;
- data sector count diferente de zero;
- inode count exatamente 2048;
- journal sector count pelo menos 2;
- bitmap LBA diferente de zero;
- inode LBA maior que bitmap LBA;
- bitmap sem sobrepor a inode table;
- inode table sem sobrepor o journal;
- data region não começando antes do fim do journal;
- fim da data region não ultrapassando `total_sectors`;
- capacidade em bits do bitmap suficiente para todos os data sectors.

Isso é mais flexível que `cfs_geom_for_count`.

Um volume v5 não precisa usar exatamente o layout criado pelo ChrisOS, desde que satisfaça esses invariantes.

## Gaps são permitidos

O validator impede overlap, mas não exige adjacência.

Ele não exige:

~~~text
inode_lba   == bitmap_lba + bitmap_sectors
journal_lba == inode_lba + 512
data_lba    == journal_lba + journal_sectors
~~~

Também aceita:

~~~text
data_lba + data_sectors < total_sectors
~~~

deixando setores não usados no final do device visível.

Essa flexibilidade poderia suportar layouts futuros, mas hoje não há feature field que explique esses gaps.

## Lacuna crítica de validação do journal

A geometria criada pelo ChrisOS reserva:

~~~text
CFS_JOURNAL_SECTORS = 64
~~~

Porém `cfs_super_geom_ok` só verifica:

~~~text
journal_sectors >= 2
~~~

O journal atual permite:

~~~text
JNL_MAX_REC = 30
~~~

Cada record ocupa dois setores, além do setor de header.

Uma transação cheia pode acessar até:

~~~text
1 + 30 × 2 = 61 setores de journal
~~~

a partir do início da região.

Um superblock v5 artificial pode declarar journal muito menor e ainda passar pelo validator.

Atividade posterior do journal pode então acessar setores além da região declarada.

Filesystems gerados por `cfs_format` não sofrem esse caso porque sempre reservam 64 setores, mas o decoder deveria validar a capacidade exigida pelo journal real.

## Lacunas de overflow nos checks

Dois checks atuais fazem soma diretamente em 32 bits:

~~~text
bitmap_lba + bitmap_sectors
journal_lba + journal_sectors
~~~

antes da comparação.

Como os campos são unsigned de 32 bits, valores malformados próximos de `UINT32_MAX` podem fazer wrap modulo 2^32.

Outros checks já ampliam antes da soma:

~~~text
(uint64_t)inode_lba + CFS_INODE_SECTORS
(uint64_t)data_lba + data_sectors
~~~

Todos os cálculos de fim de região deveriam usar aritmética ampliada por consistência e hardening.

## Campos fixos mesmo no v5

Geometria dinâmica não significa formato totalmente variável.

O decoder ainda exige:

~~~text
inode size   = 128
root inode   = 0
inode count  = 2048
sector size  = 512
~~~

Assim, v5 permite redimensionar e reposicionar regiões, mas não descreve inodes arbitrários ou outros sector sizes.

Mudar essas propriedades requer novo contrato de formato compatível.

## Clean flag

`clean` fica no offset 44 e participa do checksum.

Format inicializa:

~~~text
1
~~~

Journal begin grava zero.

Commit bem-sucedido volta para um.

O boot usa o valor como booleano:

- não zero: fsck pode ser pulado;
- zero: executar fsck após mount.

O decoder não restringe a exatamente 0 ou 1. Qualquer valor de 32 bits diferente de zero acaba tratado como clean.

## Generation

`generation` começa em 1 após format.

Caminhos de mutação incrementam o valor, e journal begin usa a geração atual como sequence.

O campo também participa do checksum.

Ele é de 32 bits e não há política explícita de wrap. Após incrementos suficientes, o comportamento é o wrap normal de unsigned arithmetic.

No tamanho atual do projeto isso não é um limite próximo, mas faz parte do ABI persistente.

## Ordem de formatação

`cfs_format` calcula a geometria antes de escrever.

Depois:

1. zera todos os metadata sectors do superblock até o setor anterior a `data_lba`;
2. marca bit 0 do bitmap como ocupado;
3. inicializa a inode table fixa;
4. cria root inode 0;
5. zera o data sector do root directory;
6. grava o superblock;
7. grava header EMPTY do journal;
8. chama `bd_flush`.

O superblock é gravado relativamente tarde, depois da inicialização da maior parte da metadata.

Se a formatação for interrompida antes disso, setor 0 tende a permanecer zerado porque o primeiro passo de clearing começa nele.

Isso interage com a detecção de mídia vazia.

## Auto-format de mídia vazia

`storage_format_if_empty` lê o setor 0.

A decisão é:

~~~text
superblock ChrisFS válido -> não altera
inválido + primeiros 8 bytes todos zero -> format
inválido + algum dos 8 bytes não zero -> CFS_EFORMAT
~~~

É uma política conservadora.

Uma assinatura desconhecida ou danificada não é destruída automaticamente.

O host test verifica que um setor iniciado com `0xFF` é rejeitado e preservado.

## Consequência do teste de oito bytes

Somente os oito primeiros bytes determinam se um superblock inválido é considerado vazio o suficiente para format.

Esses bytes contêm:

~~~text
magic
version
sector size
~~~

Um setor com esses oito bytes zero e conteúdo arbitrário depois deles é considerado blank por esse helper.

O restante do setor 0 não é inspecionado antes da formatação.

É uma heurística simples, não um detector completo de disk vazio.

## Descoberta do root

`disk_has_cfs` usa a mesma identificação fundamental para whole-disk e GPT partition:

1. lê LBA 0 relativo ao filesystem;
2. executa `cfs_super_decode`;
3. decode bem-sucedido indica volume ChrisFS candidato.

Em GPT, isso ocorre depois de `PartView` transformar o início da partição em LBA lógico 0.

Depois, o filesystem é realmente montado, journal replay é executado e inode 0 precisa ser directory.

## Relação entre mount e capacidade do backing device

Depois do decode, `cfs_mount` exige:

~~~text
dev->sector_count >= super.total_sectors
~~~

Backing device menor é rejeitado.

Um maior é aceito.

Assim é possível colocar uma imagem ChrisFS existente em uma partição maior sem expandi-la automaticamente.

Não existe hoje operação online de grow que reescreva a geometria para consumir setores extras.

## O que o validator não prova

Superblock válido não garante consistência do restante do filesystem.

O decoder não verifica:

- conteúdo do bitmap;
- checksums de inode;
- type do root inode;
- journal records;
- ownership de blocks;
- graph de diretórios;
- allocation leaks.

Mount valida depois o root inode e executa journal replay.

`cfs_fsck` faz os checks cruzados mais profundos.

O decoder deve ser entendido como validação de geometria, não certificação completa do filesystem.

## fsck e superblock

`cfs_fsck` relê diretamente LBA 0 e decodifica novamente.

Se falhar, reporta genericamente:

~~~text
super checksum
~~~

Depois usa a geometria para dimensionar mapas de bitmap/seen e encontrar inode, journal e data regions.

Logo, correção do superblock é pré-requisito para todos os invariantes mais profundos do fsck.

## Evidência de validação

### Compatibilidade v4

`test_cfs_v5` primeiro formata filesystem atual, altera o version field para v4, recalcula checksum e confirma:

- mount bem-sucedido;
- versão em memória v4;
- fsck bem-sucedido;
- arquivo pode ser escrito e lido.

Como a geometria v5 de 512 MiB coincide com endereços fixos v4, o teste é uma verificação direta de compatibilidade.

### Crescimento v5

O mesmo teste cria block device sparse maior que 512 MiB.

Ele verifica:

- version v5 no setor 0;
- total sector count armazenado;
- data geometry indo além do limite legado;
- mount;
- allocation real além da fronteira antiga.

### Corrupção e proteção contra auto-format

`test_cfs_host` verifica:

- erro de I/O lendo o superblock vira `CFS_EIO`;
- superblock válido não é reformatado;
- prefixo não zero desconhecido retorna `CFS_EFORMAT`;
- os bytes desconhecidos não são alterados.

## Complexidade

Encode/decode do superblock é:

~~~text
O(1)
~~~

porque trabalha com um setor de tamanho fixo e poucos campos.

O cálculo de geometria também é efetivamente O(1): itera até estabilizar o bitmap e possui guard pequeno.

Format não é O(1). Ele limpa:

~~~text
data_lba setores de metadata
~~~

antes de inicializar root.

Como bitmap cresce com o volume, o custo de inicialização da metadata também cresce.

## Limitações atuais

Na revisão documentada:

- apenas setores de 512 bytes;
- todos os campos de geometria têm 32 bits;
- espaço prático abaixo de 2 TiB;
- 2048 inodes fixos;
- inode size fixo em 128 bytes;
- root inode fixo em 0;
- v3/v4 fixos em 512 MiB;
- sem online grow/shrink;
- bytes 64..511 ignorados e fora do checksum;
- checksum não criptográfico;
- `clean` aceita qualquer valor não zero;
- generation sem política explícita de wrap;
- v5 aceita gaps sem feature descriptor;
- v5 não exige data region consumindo todo `total_sectors`;
- validação do tamanho do journal é mais fraca que a necessidade do implementation;
- alguns region-end checks usam soma de 32 bits sujeita a wrap;
- decode de superblock não prova consistência do filesystem;
- format de volumes grandes pode exigir enorme quantidade de writes single-sector de metadata.

## Fronteira de roadmap

Um contrato futuro mais forte deveria considerar:

- sector counts e LBAs de 64 bits;
- feature/incompatibility flags explícitos;
- validação exata da capacidade do journal;
- aritmética ampliada em todos os cálculos de região;
- adjacência obrigatória ou descriptors explícitos de gaps;
- política definida para bytes reservados;
- checksums mais fortes ou metadata autenticada quando necessário;
- superblocks redundantes;
- online grow;
- inicialização mais eficiente de grandes regiões de metadata;
- validação de enum para clean state;
- test vectors com geometrias v5 malformadas, porém com checksum correto.

Esses itens permanecem roadmap até existirem no source e em testes reproduzíveis.

## Mapa de source e revisão

`kernel/fs/storage_limits.h` define constantes e geometria histórica. `kernel/fs/cfs_format.h` define formato persistente, checksum, reconstrução legada, geometria dinâmica e validação. `kernel/fs/cfs.c` consome a geometria em format e mount. `kernel/fs/storage.c` usa o decoder em root discovery e na política conservadora de auto-format. `kernel/fs/cfs_fsck.c` valida novamente o superblock antes de checks de consistência. `tools/test_cfs_v5.c` e `tools/test_cfs_host.c` fornecem a evidência host-side principal.

Todas as afirmações sobre comportamento atual neste capítulo foram reconciliadas com ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
