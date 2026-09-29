---
id: nvme
lang: pt-br
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/nvme.c
  - kernel/fs/nvme.h
  - kernel/fs/block_device.h
  - kernel/fs/bdev.c
  - kernel/gfx/hwgate.c
  - kernel/gfx/hwgate.h
  - kernel/metal/pci.c
symbols:
  - Nvme
  - nvme_probe
  - admin_cmd
  - io_rw
  - nvme_rw
  - wait_cq
  - ring_sq
  - ring_cq
  - hw_bar_map
  - hw_dma_alloc
depends_on:
  - block-storage
  - pci-pcie
  - buses-mmio-dma
related:
  - ahci
  - virtio-block
  - partitions-gpt
---

# NVMe: queues e namespaces

## Escopo

NVMe expõe storage por submission/completion queues em memória, em vez de task-file SATA. O driver atual do ChrisOS reduz esse modelo a um controller, namespace 1, queues de duas entries e um data buffer DMA de 4 KiB por trás da API síncrona BlockDevice.

O caminho é:

~~~text
request BlockDevice
  -> copiar até 8 setores pela página DMA
  -> gravar comando de 64 bytes na SQ
  -> tocar doorbell da SQ
  -> fazer poll da CQ usando phase bit
  -> avançar CQ head e tocar doorbell
  -> retornar BD_OK / BD_EIO / BD_ETIMEOUT
~~~

![Caminho atual de queues NVMe no ChrisOS](../../assets/diagrams/nvme-queue-path-pt-br.svg)

O driver demonstra o protocolo fundamental de queues, mas ainda não explora paralelismo ou recovery avançado.

## Estado do controller

Nvme armazena:

- janela MMIO;
- doorbell stride;
- admin SQ/CQ;
- I/O SQ/CQ;
- página DMA de dados;
- heads/tails;
- contador CID;
- phase bits separados;
- sector count.

Existe uma única instância global.

Depois do primeiro controller registrado, g_ready impede nova descoberta.

## Descoberta PCI

nvme_probe percorre buses 0..7, 32 devices e oito functions.

Exige class/subclass:

~~~text
0x0108
~~~

Habilita memory space e bus mastering e mapeia BAR0 via hw_bar_map.

Acesso aos registradores ocorre por hw_mmio_*.

## CAP e doorbell stride

CAP é lido como 64 bits.

DSTRD gera:

~~~text
stride = 4 << DSTRD
~~~

Doorbells começam em 0x1000.

Os offsets de SQ/CQ são calculados usando esse stride, portanto o driver não assume sempre espaçamento mínimo de quatro bytes.

## Desabilitação do controller

O driver lê CC e limpa EN.

Depois espera CSTS.RDY ficar zero por até 200.000 iterações.

Existe uma limitação: ao terminar o loop por orçamento, o código não testa explicitamente se RDY realmente ficou zero.

Ele segue com setup.

Na habilitação acontece padrão semelhante: espera RDY=1, mas não transforma expiração em falha explícita.

Um driver mais robusto precisa tratar essas transições como gates.

## Alocações DMA

São alocadas cinco páginas:

- admin SQ;
- admin CQ;
- I/O SQ;
- I/O CQ;
- data.

Se qualquer allocation inicial falha, todas são passadas a hw_dma_free e o probe continua.

Os físicos high/low podem ser fornecidos ao NVMe; não existe limitação intencional a 32 bits como no IDE DMA legado.

## Geometria das admin queues

AQA recebe:

~~~text
1 | (1 << 16)
~~~

Como queue size é codificado como entries - 1, SQ e CQ possuem duas entries.

ASQ/ACQ recebem os endereços físicos.

CC configura:

~~~text
IOSQES = 6 -> 64 bytes
IOCQES = 4 -> 16 bytes
~~~

coincidindo com o layout usado pelo código.

## Command ID

Cada comando incrementa cid de 16 bits.

CID entra nos bits superiores de dword0.

wait_cq não compara o CID retornado.

No modelo atual existe apenas um comando síncrono esperado por queue, então head/phase são usados como identificação implícita.

Essa suposição não serviria para vários comandos simultâneos.

## Phase bit

CQ é circular e entries antigas continuam contendo dados.

O driver mantém phase esperado, inicialmente 1.

wait_cq lê dword3 e testa bit16.

Ao encontrar phase correto:

1. extrai status;
2. avança head com &1;
3. ao voltar a zero, inverte phase;
4. atualiza doorbell da CQ;
5. retorna sucesso se status zero.

Esse mecanismo distingue completion nova de conteúdo antigo numa queue de duas entries.

## Wait limitado

A CQ é polled por até 400.000 iterações.

Sem phase esperado, retorna -2, convertido em BD_ETIMEOUT.

Status NVMe diferente de zero retorna erro e vira BD_EIO.

Não existe completion por MSI/MSI-X no driver atual.

## Admin command

admin_cmd zera uma entry de 64 bytes e grava:

- opcode + CID;
- NSID;
- PRP1;
- CDW10;
- CDW11.

Depois avança tail modulo dois, toca doorbell e espera completion.

Somente campos usados pelo probe atual são modelados.

## Identify Controller

Opcode 0x06 com CNS=1 grava resposta na página data.

O driver lê NN em offset 516 e exige pelo menos um namespace.

Ele não enumera os namespace IDs ativos.

Depois assume namespace 1.

Logo controller com namespace relevante em outro NSID fica fora da policy atual.

## Criação da I/O CQ

Opcode admin 0x05 cria CQ id1.

CDW10 usa queue size field 1, portanto duas entries.

A CQ usa a página io_cq já alocada.

## Criação da I/O SQ

Opcode 0x01 cria SQ id1 associada a CQ1.

Novamente o tamanho é duas entries.

Depois desse setup o driver possui um único queue pair de I/O.

## Identify Namespace

Identify com NSID 1 e CNS=0 lê NSZE.

A implementação aceita apenas quando os 32 bits altos são zero.

Assim a capacidade fica limitada pelo sector_count uint32_t do BlockDevice, aproximadamente 2 TiB com setores de 512 bytes.

## Restrição do LBA format

O driver extrai LBADS e exige:

~~~text
LBADS = 9
2^9 = 512 bytes
~~~

Namespace com outro logical block size é rejeitado.

Não existe negociação para trocar o formato.

## Comando de I/O

io_rw grava:

- opcode 0x02 read ou 0x01 write;
- CID;
- NSID=1;
- PRP1 apontando para a página data;
- LBA inicial em CDW10;
- count-1 em CDW12.

Só PRP1 é usado.

Não existe PRP2/list.

Isso funciona porque o payload nunca passa de uma página.

## Limite de oito setores

nvme_rw divide a request:

~~~text
8 * 512 = 4096 bytes
~~~

Write copia caller -> data.

Read copia data -> caller após completion.

Requests maiores viram vários comandos.

O limite é do bounce buffer, não do protocolo NVMe.

## Doorbells e ownership

Depois de preencher SQ, tail é avançado e publicado no doorbell.

Depois de consumir CQ, head é publicado.

Essas operações marcam mudança de ownership das entries entre software e controller.

O driver usa MMIO volatile através do hwgate.

## Modelo síncrono

Apesar de duas slots, a implementação espera cada completion antes do próximo comando.

Queue depth efetivo é um.

A segunda entry serve ao ciclo circular/phase.

Não existe table de comandos outstanding.

Isso simplifica lifetime, mas elimina o paralelismo característico do NVMe.

## Timeout e ownership incompleto

Se wait_cq expira, BlockDevice retorna BD_ETIMEOUT.

O código não:

- envia Abort;
- reseta controller;
- recria queues;
- prova que o comando antigo parou de fazer DMA.

A próxima request reutiliza data e queues.

Logo timeout não fecha o lifetime do comando anterior.

Recovery hardened precisa quiescer/resetar antes do reuso.

## Erro de completion

Status não-zero vira BD_EIO.

O driver não decodifica SCT/SC em classes detalhadas nem faz recovery específico.

É suficiente para bring-up, mas limitado para diagnóstico.

## Lifetime em falhas de probe

Cleanup completo das cinco páginas ocorre somente se uma allocation inicial falha.

Depois que todas existem, vários failures fazem continue sem free:

- admin command;
- ausência de namespace;
- criação de I/O queues;
- disk grande demais;
- sector size rejeitado;
- namespace pequeno.

Um candidato posterior sobrescreve g_nv.

Assim podem ocorrer leaks de DMA no probe.

## Verificação incompleta de RDY

Os loops de enable/disable são finitos, evitando hang infinito.

Porém não há check pós-loop que transforme expiração em erro imediato.

Um controller stuck pode gerar timeout só mais tarde em admin command, obscurecendo a causa.

## Flush

O BlockDevice NVMe registra flush=null.

bd_flush genérico retorna BD_OK sem emitir opcode NVMe Flush 0x00.

Write + flush genérico não prova commit de volatile write cache.

Esse gap importa para crash consistency.

## Concorrência

Todo estado é global:

- queues;
- data page;
- heads/tails;
- CID.

Não há lock.

Calls concorrentes podem reutilizar slot, sobrescrever data ou corromper índices.

A arquitetura atual pressupõe serialização externa.

Queue depth real exige ownership por request.

## Desempenho

O driver não busca performance NVMe:

- um controller;
- namespace 1;
- queue depth efetivo 1;
- queues de 2 entries;
- um queue pair;
- bounce page de 4 KiB;
- máximo 8 setores;
- polling;
- sem interrupts;
- sem multi-core queues;
- sem PRP list.

O objetivo atual é funcionalidade e entendimento do protocolo.

## Validação

Casos importantes:

- controller ausente;
- timeout RDY;
- falha de queue creation;
- namespaces sem NSID1;
- LBA format diferente de 512;
- NSZE >32 bits;
- crossing de 8 setores;
- wrap/phase da CQ;
- completion error;
- timeout com reset seguro;
- probes falhos repetidos para detectar leaks;
- Flush real;
- submissions concorrentes;
- hardware físico além de emulação.

O bdev test genérico valida success path, não essas fronteiras.

## Limitações atuais

O driver atual possui:

- scan PCI 0..7;
- primeiro controller apenas;
- namespace 1;
- admin/I/O queues de 2 entries;
- um request em flight;
- um queue pair;
- uma página data compartilhada;
- apenas PRP1;
- até 8 setores de 512 bytes;
- capacidade uint32_t;
- apenas LBADS 9;
- polling;
- sem Flush;
- recovery incompleto de timeout;
- validação incompleta de RDY;
- leaks após falhas posteriores do probe;
- status pouco detalhado;
- sem multi-queue/multi-core.

São limites do ChrisOS, não do NVMe.

## Mapa de fonte

kernel/fs/nvme.c implementa descoberta, setup do controller, admin/I/O queues, phase polling, Identify e I/O BlockDevice.

kernel/gfx/hwgate.c fornece BAR, MMIO e DMA.

kernel/fs/block_device.h e bdev.c publicam o namespace como device comum.

As afirmações foram reconciliadas com ChrisOS e05a17fd76333114a3fb5c2452f38ca747d4ac56.
