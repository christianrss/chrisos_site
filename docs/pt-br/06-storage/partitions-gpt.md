---
id: partitions-gpt
lang: pt-br
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/part.h
  - kernel/fs/part.c
  - kernel/fs/install.c
  - kernel/fs/storage.c
  - kernel/fs/block_device.h
  - kernel/fs/bdev.h
  - kernel/fs/bdev.c
  - kernel/fs/storage_limits.h
  - tools/check_install_img.py
  - scripts/qemu.mk
symbols:
  - PartView
  - gpt_find_cfs
  - part_open
  - part_read
  - part_write
  - install_device
  - write_gpt_backup
  - crc32
  - gpt_crc
  - discover_root
  - check_install_img.py
depends_on:
  - block-storage
  - ata
  - ahci
  - nvme
  - virtio-block
  - usb-storage
related:
  - chrisfs
  - uefi
  - installation-real-hardware
  - resource-lifetime
---

# Tabelas de partição e GPT

## Escopo

O ChrisOS usa GPT em duas direções diferentes:

1. **descoberta no boot**: lê a GPT primária de um disk e procura uma partição adequada para ChrisFS;
2. **instalação**: cria de forma destrutiva protective MBR, GPT primária, GPT de backup, EFI System Partition e partição ChrisFS.

A implementação é compacta e cobre exatamente as estruturas necessárias ao instalador e ao caminho atual de descoberta de root. Ela ainda não é um gerenciador genérico de partições.

O leitor aceita tanto o type GUID dedicado do ChrisFS quanto o GUID padrão de Linux filesystem data, mantido por compatibilidade com imagens antigas. O instalador escreve o GUID dedicado do ChrisFS e o GUID padrão de EFI System Partition.

Este capítulo documenta a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![Descoberta GPT e caminho de instalação no ChrisOS](../../assets/diagrams/partitions-gpt-pt-br.svg)

## Por que existe uma partition view

Os drivers de storage expõem discos inteiros através de `BlockDevice`. Um filesystem, porém, pode ocupar apenas uma faixa de LBAs.

O ChrisOS usa `PartView`:

~~~c
typedef struct PartView {
    BlockDevice *parent;
    uint32_t start;
    uint32_t count;
    BlockDevice dev;
} PartView;
~~~

A partition view não representa hardware novo. Ela traduz endereços:

~~~text
LBA x da partição
    -> LBA start + x do disk pai
~~~

O `BlockDevice` virtual usa:

- sector size de 512 bytes;
- sector count igual ao tamanho da partição;
- writable herdado do pai.

Reads e writes adicionam o offset inicial e chamam diretamente o backend pai.

## Limites da partição

`part_open` rejeita:

- ponteiro de saída nulo;
- parent nulo;
- count zero;
- start fora do disk.

Se o range pedido ultrapassar o final do pai, o count é reduzido:

~~~text
count = parent.sector_count - start
~~~

No caminho normal, os callers usam `bd_read` e `bd_write` no `BlockDevice` da partição. Esses helpers validam o range relativo antes de chegar a `part_read` ou `part_write`.

A camada de tradução em si não repete a validação. Portanto a segurança depende de não chamar os function pointers diretamente com coordenadas arbitrárias.

## Semântica de flush

A partition view registra:

~~~text
flush = 0
~~~

em vez de encaminhar o callback de flush do parent.

Se um backend futuro oferecer flush real, essa garantia será perdida ao passar pela partição.

Hoje vários backends também possuem `flush = 0`, então a limitação é principalmente arquitetural no estado atual.

## Layout GPT usado pelo ChrisOS

Com setores de 512 bytes, o instalador grava:

~~~text
LBA 0                  protective MBR
LBA 1                  header GPT primário
LBA 2..33              array primário de entries
...
LBA N-33..N-2          array de entries de backup
LBA N-1                header GPT de backup
~~~

O array possui:

~~~text
128 entries × 128 bytes = 16384 bytes = 32 setores
~~~

O header criado usa GPT revision 1.0 e header size de 92 bytes.

## Protective MBR

O instalador grava um MBR legado no LBA 0.

Campos principais:

~~~text
partition type = 0xEE
start LBA      = 1
length         = disk sectors - 1
signature      = 0x55AA
~~~

A entry 0xEE sinaliza para ferramentas antigas que o disk pertence a GPT.

O leitor GPT usado no boot não valida o protective MBR. Ele começa diretamente no LBA 1.

Já `check_install_img.py` verifica assinatura 0x55AA e type 0xEE.

## Type GUIDs

O ChrisOS define um GUID específico para ChrisFS:

~~~text
43524653-3100-4000-8000-000000000001
~~~

A representação on-disk em mixed endian é:

~~~text
53 46 52 43 00 31 00 40 80 00 00 00 00 00 00 01
~~~

O leitor também aceita Linux filesystem data:

~~~text
0FC63DAF-8483-4772-8E79-3D69D8477DE4
~~~

Isso existe para que imagens antigas continuem montando.

Como o GUID Linux é genérico, o ChrisOS não confia apenas nele. Depois de abrir a partition view, ainda exige um superblock ChrisFS válido.

## Leitura do header GPT primário

`gpt_find_cfs` lê o setor 1 e procura exatamente:

~~~text
EFI PART
~~~

Depois copia os primeiros 92 bytes do header, zera bytes 16 a 19 e calcula CRC-32.

O algoritmo usa o polinômio refletido:

~~~text
0xEDB88320
~~~

com estado inicial `0xFFFFFFFF` e complemento final.

O resultado precisa coincidir com o header CRC armazenado.

## Campos do header consumidos

Depois da validação de CRC, o leitor usa:

- partition-entry-array LBA no offset 72;
- number of entries no offset 80;
- entry size no offset 84.

Ele exige:

~~~text
entry_array_lba != 0
entry_array_lba <= 0xFFFFFFFF
entry_size >= 128
entry_count >= 1
~~~

O número de entries é limitado a 128.

O leitor atual não valida:

- revision;
- campo header size;
- current LBA;
- backup LBA;
- first/last usable LBA;
- disk GUID;
- CRC do partition-entry array;
- consistência entre posição real do header e current LBA.

Além disso, o CRC é calculado sempre sobre 92 bytes, em vez de obedecer ao header-size declarado pelo próprio GPT.

## Scan das partition entries

Para cada entry:

~~~text
offset = (index * entry_size) % 512
sector = entry_array_lba + (index * entry_size) / 512
~~~

Quando `offset == 0`, o setor correspondente é carregado no buffer de 512 bytes.

O primeiro campo comparado é o type GUID.

Com entries de 128 bytes — formato criado pelo instalador — quatro entries cabem exatamente por setor e o parser funciona como esperado.

### Limitação com entry sizes incomuns

O parser aceita qualquer `entry_size >= 128`.

Entretanto, ele não rejeita tamanhos que façam uma entry cruzar o limite de um setor de 512 bytes.

Como só existe um buffer de setor e não há montagem de entry multi-sector, GPTs válidas porém incomuns podem fazer o parser acessar dados que não representam a entry completa.

As imagens geradas pelo próprio ChrisOS usam 128 bytes e não entram nesse caso.

## Campos usados de cada entry

Para uma entry cujo type GUID é aceito, o código lê:

~~~text
first LBA  em entry + 32
last LBA   em entry + 40
~~~

Os dois são little-endian de 64 bits.

O candidato é rejeitado se:

~~~text
start == 0
start > end
end > 0xFFFFFFFF
~~~

Isso expõe diretamente a fronteira da block layer atual: GPT é 64-bit, mas `BlockDevice` ainda usa LBAs de 32 bits.

O count calculado é:

~~~text
end - start + 1
~~~

e retorna como `uint32_t`.

## Campos ignorados

O leitor não usa:

- unique partition GUID;
- attributes;
- nome UTF-16 da partição.

Ele retorna o primeiro type GUID aceito.

Não existe API para enumerar todas as partições ou criar múltiplos child devices no registry.

O suporte GPT atual é orientado principalmente a encontrar o root.

## Ordem de descoberta do root

`discover_root` trabalha em três fases.

### Fase 1 — ChrisFS em disk inteiro

Para cada block device não-RAM, o ChrisOS verifica se o setor 0 já contém um superblock ChrisFS.

Se sim, o disk inteiro vira root.

### Fase 2 — ChrisFS em GPT

Se não houver root whole-disk, chama `gpt_find_cfs`.

Quando encontra uma entry, abre `PartView` e valida novamente o setor 0 relativo da partição com o decoder de superblock ChrisFS.

Somente então a partição é usada como `g_disk`.

### Fase 3 — disk vazio

Se não existir filesystem conhecido, um disk writable suficientemente grande e com início zerado pode ser formatado diretamente.

Esse fluxo preserva compatibilidade com imagens antigas sem GPT e com instalações mais novas.

## Por que o filesystem ainda é validado depois do GUID

O type GUID Linux é aceito por compatibilidade.

Se o GUID sozinho bastasse, qualquer ext4 ou outro filesystem Linux poderia ser interpretado incorretamente como ChrisFS.

Por isso, depois de `part_open`, o código chama `disk_has_cfs`.

A partição só é aceita quando o decoder reconhece realmente o superblock ChrisFS.

## Geometria criada pelo instalador

`install_device` escreve duas entries.

### Partição 1 — EFI System Partition

Type GUID:

~~~text
C12A7328-F81F-11D2-BA4B-00A0C93EC93B
~~~

Início:

~~~text
LBA 2048
~~~

Tamanho:

~~~text
16384 setores   em disks menores
65536 setores   se disk sectors > 200000
~~~

Com 512 bytes por setor, são 8 MiB ou 32 MiB.

Essa partição é formatada em FAT16 e recebe bootloader EFI, kernel e configuração Limine.

### Partição 2 — ChrisFS

Início:

~~~text
2048 + tamanho da ESP
~~~

Fim:

~~~text
disk sectors - 34
~~~

Os últimos 33 setores ficam reservados para GPT backup.

## Alinhamento

A ESP começa no LBA 2048:

~~~text
2048 × 512 = 1 MiB
~~~

Os dois tamanhos possíveis da ESP são múltiplos de 2048 setores.

Consequentemente, a partição ChrisFS também começa alinhada a 1 MiB.

## Tamanho mínimo do target

O instalador exige pelo menos:

~~~text
2048
+ ESP sectors
+ STOR_DISK_SECTORS
+ 64
~~~

e:

~~~text
STOR_DISK_SECTORS = 1048576
~~~

Isso reflete a geometria fixa atual do ChrisFS e ainda deixa margem para GPT backup.

## Construção do array de entries

O instalador mantém um buffer estático de:

~~~text
128 × 128 bytes
~~~

Somente entries 0 e 1 são utilizadas.

Entry 0:

- ESP type GUID;
- unique GUID simplificado, com primeiro byte 1;
- start/end da ESP.

Entry 1:

- ChrisFS type GUID;
- unique GUID simplificado, com primeiro byte 2;
- start/end do ChrisFS.

As outras 126 ficam zeradas.

## Qualidade dos unique GUIDs

Os unique partition GUIDs não são gerados aleatoriamente nem por um mecanismo de unicidade global.

Cada um recebe apenas um byte diferente.

O disk GUID também é mínimo: apenas o primeiro byte é preenchido com `0x43`.

Isso mantém os campos não zerados para as imagens atuais, mas não entrega a propriedade de unicidade global esperada por GPT.

## CRC do partition-entry array

O instalador calcula CRC-32 sobre:

~~~text
16384 bytes
~~~

e grava o resultado no offset 88 do header GPT.

Esse CRC cobre exatamente 128 entries de 128 bytes.

O leitor de boot, porém, **não verifica esse CRC**.

O checker host-side também foca header CRC e estruturas selecionadas, sem validar atualmente o CRC do array.

## Header GPT primário

O instalador grava:

~~~text
signature             "EFI PART"
revision              0x00010000
header size           92
current LBA           1
backup LBA            sectors - 1
first usable LBA      34
last usable LBA       sectors - 34
entry-array LBA       2
entry count           128
entry size            128
entry-array CRC       CRC calculado
~~~

Depois zera o header-CRC field, calcula CRC dos 92 bytes e armazena o resultado.

## GPT de backup

`write_gpt_backup` copia os 32 setores do array primário:

~~~text
LBA 2..33
~~~

para:

~~~text
LBA sectors-33 .. sectors-2
~~~

Depois reutiliza o header primário e modifica:

~~~text
current LBA      = sectors - 1
backup LBA       = 1
entry-array LBA  = sectors - 33
~~~

O CRC do header é recalculado.

Como o array de entries é copiado byte a byte, o mesmo entry-array CRC continua válido.

## Modelo de falha da instalação

A criação da GPT é destrutiva.

Antes disso, o target precisa passar `bd_installable`. O modo automático exige um nome explícito de disk e imprime:

~~~text
WARNING: ALL DATA ON THIS DISK WILL BE LOST
~~~

Não há transaction ou rollback de partition table.

Uma falha após escrever protective MBR, entries ou header primário pode deixar o disk parcialmente reconfigurado.

O backup é escrito antes da ESP e do ChrisFS, o que aumenta a redundância depois dessa etapa, mas não torna a instalação atômica.

## Ordem das escritas

A sequência é:

~~~text
protective MBR
-> primary entries
-> primary GPT header
-> backup entries/header
-> ESP + boot files
-> ChrisFS
-> system tree opcional
-> cfs_sync
~~~

Não existem durable flush barriers explícitas entre os estágios porque a block layer atual geralmente não possui flush real.

Logo, crash consistency é mais fraca do que a ordem lógica por si só sugere.

## Backup GPT não é usado no boot

Apesar de o instalador criar backup GPT e o checker validar sua assinatura e CRC, `gpt_find_cfs` nunca tenta recuperá-la.

Se o header primário no LBA 1 estiver corrompido, o boot não usa automaticamente o backup no final do disk.

Recovery por backup ainda é roadmap.

## Implementação de CRC

`part.c` e `install.c` possuem implementações separadas do mesmo CRC-32 refletido.

O checker Python usa `zlib.crc32`.

Atualmente os resultados são compatíveis.

A complexidade é linear:

~~~text
O(bytes do header + bytes do array de entries)
~~~

e é irrelevante em custo para o tamanho fixo atual.

## Fronteira de 32 bits

GPT possui endereços de 64 bits, mas o `BlockDevice` atual declara:

~~~text
uint32_t lba
uint32_t sector_count
~~~

O leitor rejeita partitions cujo final ultrapasse `0xFFFFFFFF`.

O instalador também só conhece `sector_count` de 32 bits.

Com setores de 512 bytes, isso mantém o limite prático próximo de 2 TiB.

Suporte pleno a GPT em disks maiores exige uma block ABI de 64 bits.

## Evidência de validação

O principal gate é `test-qemu-install`.

Ele:

1. prepara um disk fonte do ChrisOS;
2. cria um target AHCI vazio de 560 MiB;
3. solicita instalação automática no device `ahci`;
4. exige logs:
   - `install auto`;
   - `install tree copied`;
   - `install gpt+esp+cfs disk=ahci`;
5. executa `tools/check_install_img.py`;
6. reinicia a imagem instalada através de OVMF;
7. exige `cfs mounted` e `desktop 60Hz`.

O checker valida:

- protective MBR;
- assinatura do GPT primário;
- CRC do header primário;
- assinatura do GPT backup;
- CRC do header backup;
- ChrisFS type GUID na segunda entry;
- superblock ChrisFS no LBA da partição;
- estruturas esperadas da ESP.

Existe também o installer self-test em RAM, que verifica criação de GPT e conteúdo selecionado da ESP.

## Limitações atuais

Na revisão documentada, o suporte a partições possui:

- descoberta apenas pelo GPT primário;
- sem fallback para GPT backup no boot;
- sem parser de MBR partitions;
- sem hybrid MBR;
- no máximo 128 entries escaneadas;
- retorno do primeiro ChrisFS/Linux-data type aceito;
- sem enumeração genérica de partitions;
- sem partition names;
- sem attributes;
- sem lookup por unique GUID;
- sem validação de revision;
- sem validação do header-size field;
- CRC do header fixo em 92 bytes;
- sem validação das relações current/backup LBA;
- sem validação de usable-LBA range;
- sem validação de disk GUID;
- sem CRC do partition-entry array no leitor;
- handling incompleto de entries que cruzam setores;
- LBAs e counts de 32 bits;
- partition view sem forward de flush;
- sem hotplug lifecycle;
- GUIDs do instalador sem unicidade global;
- instalação destrutiva e não transacional;
- sem flush barriers duráveis entre metadados.

## Fronteira de roadmap

Uma camada mais completa deve oferecer LBAs de 64 bits, enumeração genérica, validação rigorosa de headers, CRC do entry array, suporte seguro a entry sizes arbitrários válidos, recovery pelo backup GPT, names/attributes/unique GUIDs, validação do protective MBR, eventual compatibilidade MBR, propagação de flush e melhor recovery da instalação.

O instalador também deveria gerar GUIDs realmente únicos e usar write barriers quando os backends de storage passarem a expor flush durável.

Esses itens continuam futuros até estarem no source e em testes reproduzíveis.

## Mapa de source e revisão

`kernel/fs/part.c` implementa descoberta GPT e a partition view. `kernel/fs/part.h` define `PartView`. `kernel/fs/storage.c` utiliza GPT na seleção de root. `kernel/fs/install.c` cria protective MBR, GPT primária/backup, ESP e partição ChrisFS. `tools/check_install_img.py` valida imagens produzidas pelo instalador. `scripts/qemu.mk` contém o gate completo de instalação e reboot.

Todas as afirmações sobre comportamento atual neste capítulo foram reconciliadas com ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
