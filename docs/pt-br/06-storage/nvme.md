---
id: nvme
lang: pt-br
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/nvme.h
  - kernel/fs/nvme.c
  - kernel/fs/block_device.h
  - kernel/fs/bdev.h
  - kernel/fs/bdev.c
  - kernel/fs/storage.c
  - kernel/gfx/hwgate.h
  - kernel/gfx/hwgate.c
  - kernel/metal/pci.c
  - scripts/qemu.mk
symbols:
  - Nvme
  - nvme_probe
  - admin_cmd
  - io_rw
  - nvme_rw
  - nvme_read
  - nvme_write
  - ring_sq
  - ring_cq
  - wait_cq
  - hw_bar_map
  - hw_dma_alloc
  - bd_add_kind
depends_on:
  - block-storage
  - buses-mmio-dma
  - pci-pcie
  - physical-memory
related:
  - ahci
  - virtio-block
  - partitions-gpt
  - chrisfs
---

# Filas e namespaces NVMe

## Escopo

O ChrisOS possui um driver NVMe compacto que descobre um controlador PCI NVMe, cria uma Admin Submission Queue e uma Admin Completion Queue com duas entradas, cria uma I/O Submission Queue e uma I/O Completion Queue também com duas entradas, identifica a quantidade de namespaces do controlador, identifica o namespace 1 e expõe esse namespace como um `BlockDevice` writable com blocos de 512 bytes.

A implementação exercita diretamente o modelo de filas e doorbells do NVMe. O driver programa registradores MMIO, aloca memória física contígua para as queues, constrói comandos de 64 bytes, observa completions de 16 bytes usando phase tags e transfere payload por um único buffer PRP de 4 KiB.

O caminho atual é muito menor que o padrão NVMe completo. Ele suporta um controlador, apenas namespace 1, uma única I/O queue de ID 1, um comando outstanding por vez, um único PRP de dados, polling em vez de MSI/MSI-X e nenhum comando explícito de Flush. Não há enumeração completa de namespaces, múltiplas I/O queues, PRP lists, SGLs, reset robusto, asynchronous events, power management ou multipath.

Este capítulo documenta a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![Configuração do controlador, filas e caminho de I/O NVMe no ChrisOS](../../assets/diagrams/nvme-queues-pt-br.svg)

## Posição na stack de armazenamento

A camada de storage enxerga NVMe pelo mesmo contrato usado por ATA, AHCI, VirtIO Block e USB mass storage:

~~~text
ChrisFS / GPT / storage genérico
        -> BlockDevice
        -> nvme_read / nvme_write
        -> nvme_rw
        -> entrada da I/O SQ
        -> controlador NVMe
        -> entrada da I/O CQ
        -> página interna de dados de 4 KiB
~~~

`storage_init` testa NVMe depois de ATA e AHCI e antes de VirtIO Block e USB mass storage. Um probe bem-sucedido registra um device chamado `nvme` com kind `BD_NVME`.

A escolha do root ocorre depois, no código genérico de storage. O transporte NVMe não decide sozinho se seu namespace será o disco root.

## Modelo de queues do NVMe

NVMe é estruturado em pares de filas. O host escreve comandos em uma Submission Queue (SQ). O controlador grava completions em uma Completion Queue (CQ). Host e controlador coordenam posições por índices, phase tags e doorbells MMIO.

O ChrisOS cria dois pares:

| Par | Queue ID | Entradas | Tamanho das entradas | Função |
|---|---:|---:|---|---|
| Admin SQ/CQ | 0 | 2 | SQ 64 B, CQ 16 B | Identify e criação das I/O queues |
| I/O SQ/CQ | 1 | 2 | SQ 64 B, CQ 16 B | Read e write do namespace 1 |

Os campos de queue size usados pelo NVMe são zero-based. Portanto, o valor 1 representa duas entradas.

Apesar de cada queue ter duas posições, o ChrisOS espera a completion imediatamente após cada submission. O queue depth efetivamente usado é um.

## Estado do driver

O objeto global `Nvme` mantém:

| Campo | Função |
|---|---|
| `win` | janela MMIO correspondente ao BAR0 |
| `stride` | espaçamento em bytes entre doorbells |
| `admin_sq`, `admin_cq` | IDs DMA das filas administrativas |
| `io_sq`, `io_cq` | IDs DMA das filas de I/O |
| `data` | página de dados e buffers de Identify |
| `asq_tail`, `acq_head` | tail da Admin SQ e head da Admin CQ |
| `isq_tail`, `icq_head` | tail da I/O SQ e head da I/O CQ |
| `cid` | Command Identifier de 16 bits |
| `admin_phase`, `io_phase` | phase bits esperados nas CQs |
| `sectors` | quantidade de setores lógicos expostos |

Existe apenas uma instância global, `g_nv`, e uma flag de ready. Depois que um namespace é registrado, probes posteriores retornam sucesso sem nova enumeração.

## Descoberta PCI

`nvme_probe` percorre PCI buses 0 a 7, devices 0 a 31 e functions 0 a 7.

A função é aceita quando class/subclass corresponde a:

~~~text
0x0108
~~~

que identifica um controlador NVM Express.

O PCI command register recebe `| 6`, habilitando memory space e bus mastering. Em seguida, BAR0 é mapeado por `hw_bar_map`.

O driver atual assume que o conjunto de registradores NVMe do controlador está acessível por BAR0.

## CAP e doorbell stride

O registrador `CAP`, de 64 bits, é lido nos offsets `0x00` e `0x04`.

O ChrisOS extrai `DSTRD` dos bits 35:32 de CAP e calcula:

~~~text
stride = 4 << DSTRD
~~~

Esse valor é o espaçamento em bytes entre doorbells sucessivos.

As doorbells começam no offset `0x1000`. Para queue ID 0 e queue ID 1, o driver usa:

~~~text
Admin SQ tail: 0x1000 + 0 * stride
Admin CQ head: 0x1000 + 1 * stride
I/O SQ tail:   0x1000 + 2 * stride
I/O CQ head:   0x1000 + 3 * stride
~~~

`ring_sq` e `ring_cq` encapsulam essas escritas.

Outros campos relevantes de CAP ainda não são utilizados, como quantidade máxima de entradas, timeout do controlador, page sizes aceitos e outras capabilities.

## Desabilitação inicial do controlador

Antes de configurar as filas, o driver lê `CC` no offset `0x14` e limpa o bit `CC.EN`.

Em seguida faz polling de `CSTS` no offset `0x1c` por no máximo 200000 iterações, esperando:

~~~text
CSTS.RDY == 0
~~~

Essa condição é necessária antes de reprogramar Admin Queue Attributes e os endereços das queues administrativas.

Há uma limitação importante: depois do loop, o código não verifica se `RDY` realmente chegou a zero. Se o limite terminar com o controlador ainda ready, a inicialização continua.

A mesma lacuna existe no caminho de enable.

## Alocações DMA

São alocadas cinco páginas físicas contíguas:

- Admin Submission Queue;
- Admin Completion Queue;
- I/O Submission Queue;
- I/O Completion Queue;
- buffer de dados/Identify.

Cada alocação tem 4096 bytes. Isso é muito maior que o necessário para queues de duas entradas, mas mantém a implementação simples e evita packing entre estruturas.

`hw_dma_alloc` pode devolver memória acima de 4 GiB. NVMe aceita endereços físicos de 64 bits para queues e PRPs, e o ChrisOS grava as partes low/high.

Se alguma alocação falhar, o probe tenta liberar os cinco IDs e continua para o próximo candidato PCI.

## Admin Queue Attributes

O driver grava `AQA` no offset `0x24` com:

~~~text
1 | (1 << 16)
~~~

Os campos ASQS e ACQS são zero-based. Assim, cada admin queue tem duas entradas.

O endereço físico da Admin Submission Queue vai para `ASQ`, offsets `0x28/0x2c`. O da Admin Completion Queue vai para `ACQ`, offsets `0x30/0x34`.

Apesar do queue depth 2, cada fila ocupa uma página inteira.

## Habilitação do controlador

`CC` recebe:

~~~text
1 | (6 << 16) | (4 << 20)
~~~

Isso configura:

- `EN = 1`;
- `IOSQES = 6`, logo entradas de SQ com 2^6 = 64 bytes;
- `IOCQES = 4`, logo entries de CQ com 2^4 = 16 bytes.

Os outros campos ficam zero, inclusive MPS, o que implica a suposição de page size padrão de 4 KiB.

Depois da escrita, o driver faz polling por `CSTS.RDY == 1`.

Novamente, se o loop de 200000 iterações expirar sem `RDY` mudar, não existe um check final explícito; o código segue para os Admin commands.

## Índices e phase tags

Os tails e heads começam em zero porque `g_nv` está em armazenamento estático.

Os phase bits esperados das CQs são inicializados em 1. Como as páginas recém-alocadas estão zeradas, completions não utilizadas começam com phase 0 e não são confundidas com uma completion válida.

Quando `wait_cq` encontra o phase esperado em DW3, consome a entry, avança o head módulo dois e alterna a phase quando o head volta de 1 para 0:

~~~text
head = (head + 1) mod 2
if head == 0:
    phase ^= 1
~~~

Depois, a CQ head doorbell é atualizada.

Esse mecanismo é coerente com o uso de phase tags em uma pequena fila circular.

## Construção de Admin commands

`admin_cmd` escolhe a posição atual da Admin SQ por:

~~~text
offset = asq_tail * 64
~~~

Os 64 bytes são zerados. O `cid` global é incrementado e o driver escreve:

- opcode e CID em command dword 0;
- NSID em dword 1;
- PRP1 low/high em dwords 6-7;
- CDW10;
- CDW11.

O tail avança módulo dois e a doorbell da Admin SQ é tocada.

A função chama `wait_cq` imediatamente, então nunca existem dois Admin commands simultâneos.

A completion não é validada contra o CID enviado. Com apenas um request outstanding isso normalmente funciona, mas reduz a capacidade de detectar completions antigas, corrompidas ou fora de ordem.

## Processamento da Completion Queue

Cada CQ entry tem 16 bytes. `wait_cq` lê DW3 em:

~~~text
cq + head * 16 + 12
~~~

O bit 16 é comparado com a phase esperada. Quando coincide, o status é obtido dos bits 31:17.

Status zero retorna sucesso; qualquer valor diferente de zero vira falha genérica.

O código atual ignora:

- result dword 0;
- SQ head informado pela completion;
- SQ identifier;
- Command Identifier;
- decodificação detalhada de Status Code Type e Status Code.

Se nenhuma completion com phase correta aparece em 400000 iterações, `wait_cq` retorna timeout.

## Identify Controller

O primeiro Admin command após o enable usa opcode `0x06`, Identify, com:

~~~text
NSID = 0
CNS  = 1
PRP1 = página de dados
~~~

CNS 1 solicita Identify Controller.

O ChrisOS lê o campo `NN` no offset 516 da página retornada. Esse campo informa o número de namespaces.

A única exigência atual é:

~~~text
NN >= 1
~~~

O valor não é usado para enumerar namespaces; serve apenas para rejeitar um controlador que reporte zero.

## Criação da I/O Completion Queue

O driver envia Admin opcode `0x05`, Create I/O Completion Queue.

PRP1 aponta para a página física de `io_cq`.

CDW10 recebe:

~~~text
1 | (1 << 16)
~~~

selecionando queue ID 1 e queue size field 1, equivalente a duas entries.

CDW11 vale `1`, marcando a queue como physically contiguous. Interrupt Enable fica desativado, coerente com polling.

## Criação da I/O Submission Queue

Depois, Admin opcode `0x01`, Create I/O Submission Queue, cria SQ 1.

CDW10 seleciona novamente queue ID 1 com duas entries.

CDW11 recebe:

~~~text
1 | (1 << 16)
~~~

O bit inferior indica physically contiguous. O campo iniciado no bit 16 seleciona Completion Queue ID 1, associando SQ 1 à CQ criada anteriormente.

Nenhuma política especial de prioridade é configurada.

## Identify Namespace

O driver emite outro Identify:

~~~text
opcode = 0x06
NSID   = 1
CNS    = 0
~~~

CNS 0 solicita Identify Namespace para namespace 1.

`NSZE` é um valor de 64 bits no início da estrutura. O ChrisOS lê os 32 bits inferiores e rejeita o namespace se os 32 bits superiores forem diferentes de zero.

Essa é uma limitação do software, não do NVMe. O contrato `BlockDevice` usa `uint32_t` para LBA e sector count.

Com blocos de 512 bytes, esse modelo representa aproximadamente até 2 TiB.

## Suposição sobre LBA format

A estrutura Identify Namespace pode descrever vários LBA formats, e o formato ativo é selecionado por `FLBAS`.

O ChrisOS lê apenas o primeiro LBA Format Data Structure, no offset 128, e verifica:

~~~text
LBADS == 9
~~~

Como o tamanho lógico é `2^LBADS`, isso representa 512 bytes.

O driver **não** lê `FLBAS` para saber qual LBAF está realmente ativo. Na prática, ele assume que LBAF0 é o formato em uso.

Assim, um namespace cujo LBAF0 seja 512 bytes, mas que esteja formatado usando outro LBAF, pode ser interpretado incorretamente.

Uma implementação mais completa deve ler FLBAS, selecionar a entrada correta e também analisar metadata e protection information.

## Política de namespace

Somente namespace 1 é anexado.

Mesmo quando Identify Controller informa vários namespaces, o driver não:

- solicita lista de namespace IDs ativos;
- percorre namespaces adicionais;
- registra múltiplos BlockDevices;
- trata namespace management.

Isso é suficiente para o modelo QEMU usado nos testes, mas não representa uma implementação geral de namespaces NVMe.

## Formato dos comandos de I/O

`io_rw` monta uma entry de 64 bytes na I/O SQ.

Para read:

~~~text
opcode = 0x02
~~~

Para write:

~~~text
opcode = 0x01
~~~

O comando usa sempre:

~~~text
NSID = 1
PRP1 = endereço físico da página interna
SLBA low 32 bits = lba
NLB = count - 1
~~~

Os 32 bits superiores de SLBA permanecem zero, compatível com a block layer de 32 bits.

PRP2 não é preenchido e não existe PRP list.

## Limite de transferência de uma página

O data buffer possui 4096 bytes e o block size aceito é 512 bytes:

~~~text
4096 / 512 = 8 setores
~~~

Por isso, `nvme_rw` limita cada command a oito setores. Requests maiores são divididos em várias submissões sequenciais.

Para `N` setores:

~~~text
ceil(N / 8)
~~~

comandos são necessários aproximadamente.

Esse desenho elimina PRP chaining e page-boundary handling, ao custo de throughput.

## Caminho de leitura

Para cada chunk, `nvme_rw` submete um Read command e espera sua completion.

Depois do sucesso, a página DMA interna é copiada para o buffer do caller em unidades de 32 bits usando `hw_dma_r32`.

A transferência entre controller e página é DMA, mas existe bounce copy na CPU. Logo, o custo de cópia continua `O(n)` no volume de dados.

## Caminho de escrita

No write, bytes do caller são primeiro empacotados na página DMA interna usando `hw_dma_w32`.

O driver submete o NVMe Write, atualiza a SQ tail doorbell e faz polling da I/O CQ.

O `BlockDevice` registrado possui:

~~~text
flush = 0
~~~

Nenhum NVMe Flush command é emitido, e `bd_flush` trata callback ausente como sucesso.

Portanto, um write concluído pelo driver não fornece atualmente uma operação explícita que force conteúdo de write cache volátil do controlador/device para mídia não volátil. Isso limita garantias de durability do filesystem.

## Concorrência

NVMe foi projetado para grande paralelismo, múltiplas queues e deep queueing. O ChrisOS atual usa o protocolo de forma essencialmente serial.

Existe:

- uma única página de dados;
- uma I/O SQ;
- uma I/O CQ;
- um conjunto global de índices;
- nenhum lock do driver;
- nenhuma completion por interrupção.

Dois callers simultâneos poderiam disputar tail/head, phase, CID e buffer DMA.

O invariante prático é um request ativo por vez.

## Timeout

`wait_cq` faz polling por no máximo 400000 iterações. Se não aparecer completion com a phase esperada, retorna `-2`.

A block layer traduz isso para `BD_ETIMEOUT`. Outros erros viram `BD_EIO`.

O timeout não dispara recovery do controlador. O código não:

- deleta e recria queues;
- desabilita o controlador confirmando `RDY=0`;
- reseta índices;
- garante que o comando antigo não fará mais DMA;
- determina se o comando terminou tardiamente;
- coloca a página de dados em quarentena.

Isso cria ambiguidade de ownership após timeout, porque queue e buffer podem ser reutilizados sem uma prova explícita de que a operação anterior parou.

## Cleanup em falhas do probe

Se uma das cinco alocações DMA falha inicialmente, o código tenta liberar todas.

Porém, depois que as cinco páginas existem, diversos failure paths fazem `continue` sem cleanup:

- falha em Identify Controller;
- NN igual a zero;
- falha em Create I/O CQ;
- falha em Create I/O SQ;
- falha em Identify Namespace;
- namespace grande demais;
- sector size rejeitado;
- namespace pequeno demais.

Esses caminhos não liberam as páginas e também não removem queues já criadas no controlador.

É uma lacuna real de resource lifetime, ainda que limitada no cenário atual de probe único.

## Lacunas no lifecycle do controlador

O probe atual não modela todo o state machine NVMe.

Entre os pontos ausentes estão:

- teste de `CSTS.CFS`;
- uso de CAP.TO para timeout específico do controlador;
- validação de CAP.MQES;
- validação de CAP.MPSMIN/MPSMAX;
- Delete I/O SQ/CQ no teardown;
- subsystem reset;
- recovery após fatal status;
- MSI/MSI-X.

São limites da implementação ChrisOS atual.

## Segurança e privilégio

O driver roda em kernel mode e habilita PCI bus mastering.

Queues e PRP buffers são passados ao controlador como endereços físicos. Atualmente não existe um domínio IOMMU dedicado ao device.

Proteções presentes:

- MMIO por janela com bounds;
- páginas DMA físicas pertencentes ao kernel;
- endereços de 64 bits para queues/PRP;
- bounds de LBA na block layer;
- payload fixo de uma página;
- loops de polling limitados.

Faltam isolamento via IOMMU, mapping DMA por request e recovery forte após timeout.

## Características de desempenho

O driver demonstra o protocolo NVMe, mas não busca throughput próximo ao potencial do hardware.

Os principais limitadores são:

- queue depth efetivo 1;
- uma única I/O queue pair;
- apenas duas entries por queue;
- máximo de 4 KiB por command;
- somente PRP1;
- polling síncrono;
- bounce copies na CPU;
- sem batching;
- sem per-CPU queues;
- sem MSI-X;
- sem agregação de I/O maior.

Controladores NVMe modernos foram projetados para muito mais paralelismo. O ChrisOS atual privilegia estado explícito e simplicidade.

## Evidência de validação

`scripts/qemu.mk` define `test-qemu-nvme`.

O gate cria uma imagem de 32 MiB e conecta o arquivo ao device NVMe do QEMU:

~~~text
-device nvme,serial=chris,drive=nvmedisk
~~~

O teste exige:

~~~text
nvme disk sectors=
bdev rw ok nvme
~~~

`bdev_rw_tests` exercita o último setor de cada block device writable que não seja o root:

1. lê o conteúdo original;
2. escreve um pattern determinístico;
3. lê novamente;
4. compara os 512 bytes;
5. restaura o setor original.

Como o disco IDE permanece root nesse gate, o NVMe é testado diretamente.

Essa evidência cobre, no modelo QEMU utilizado, discovery PCI, enable do controller, Admin commands, criação das I/O queues, Identify Namespace, PRP DMA, write completion e read completion.

Ela não constitui validação ampla em hardware NVMe físico.

## Limitações atuais

Na revisão documentada, o driver possui:

- um controlador/device NVMe registrado;
- somente namespace 1;
- sem enumeração de namespaces;
- Admin queues com depth 2;
- uma I/O queue pair com depth 2;
- apenas um command outstanding na prática;
- completion por polling;
- sem MSI/MSI-X;
- um único buffer PRP de 4 KiB;
- somente PRP1;
- sem PRP2, PRP lists ou SGL;
- no máximo oito setores de 512 bytes por command;
- somente logical blocks de 512 bytes;
- LBAF0 assumido ativo sem leitura de FLBAS;
- LBA e sector count de 32 bits, limitando capacidade exposta a aproximadamente 2 TiB;
- sem NVMe Flush explícito;
- sem decoding detalhado de status;
- sem validação de CID na completion;
- sem checks de CAP.MQES/MPS/TO;
- sem tratamento de `CSTS.CFS`;
- loops de RDY que não verificam explicitamente expiração;
- sem recovery robusto de controller/queues após timeout;
- sem locks para callers concorrentes;
- cleanup incompleto em falhas posteriores à alocação DMA;
- sem teardown e Delete I/O Queues;
- sem evidência de compatibilidade em hardware físico no gate documentado.

## Fronteira de roadmap

Uma implementação mais completa pode adicionar namespace-list discovery, seleção de LBAF por FLBAS, múltiplos namespaces, validação de capabilities do controller, checks robustos de RDY, MSI-X, queue pairs por CPU, deep queues, tracking por CID, PRP2/PRP lists, transfers maiores, Flush explícito, decoding detalhado de completions, reset recovery, isolamento IOMMU e testes em dispositivos físicos.

Esses recursos permanecem futuros até existirem no source e terem evidência reproduzível.

## Mapa de source e revisão

`kernel/fs/nvme.c` contém discovery PCI, setup do controlador, Admin commands, gerenciamento de queues, Identify Namespace e block I/O. `kernel/fs/nvme.h` expõe o probe. `kernel/gfx/hwgate.c` fornece MMIO e DMA físico contíguo. `kernel/fs/block_device.h` define o contrato genérico. `kernel/fs/bdev.h` e `kernel/fs/bdev.c` registram o device como `BD_NVME`. `kernel/fs/storage.c` integra NVMe à descoberta de root e aos testes genéricos. `scripts/qemu.mk` define o gate QEMU específico.

Todas as afirmações sobre comportamento atual foram reconciliadas com ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
