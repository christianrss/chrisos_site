---
id: ata
lang: pt-br
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/ata_pio.c
  - kernel/fs/ata_pio.h
  - kernel/fs/block_device.h
  - kernel/fs/storage.c
  - kernel/metal/pci.c
  - kernel/metal/pci.h
  - kernel/metal/irq.c
  - kernel/metal/pmm.c
  - kernel/metal/bootinfo.c
symbols:
  - AtaPio
  - ata_pio_configure
  - ata_pio_identify
  - ata_pio_make_device
  - ata_try_identify
  - ata_program
  - ata_poll
  - ata_dma_xfer
  - ata_dma_wait
  - ata_dma_abort
  - ata_read_chunk
  - ata_write_chunk
  - ata_flush_raw
  - pci_find_ide
depends_on:
  - block-storage
  - pci-pcie
  - pic-apic-ioapic
  - physical-memory
related:
  - ahci
  - buses-mmio-dma
  - partitions-gpt
---

# ATA PIO e IDE bus-master DMA

## Escopo

O driver ATA atual do ChrisOS suporta task-file I/O legado através dos ranges de portas IDE primário e secundário e pode acelerar transferências por PCI IDE bus-master DMA. O mesmo driver mantém fallback PIO, de modo que uma falha no caminho DMA não torna automaticamente o disco inutilizável.

A arquitetura efetiva é:

~~~text
request BlockDevice
    -> tentar IDE bus-master DMA, no máximo 16 setores
        -> sucesso: concluir chunk
        -> falha: parar DMA e fazer soft reset
            -> repetir por PIO, no máximo 255 setores
~~~

![Caminho ATA com DMA, completion por IRQ/status, abort/reset e fallback PIO](../../assets/diagrams/ata-io-path-pt-br.svg)

Este capítulo descreve a implementação existente, não toda a especificação ATA. Em particular, o path de comandos continua usando endereçamento LBA28 mesmo que IDENTIFY consiga ler o campo de capacidade LBA48.

## Estado do driver

AtaPio armazena:

- base das portas de command block;
- porta de control/alternate status;
- drive selecionado;
- sector count exposto ao BlockDevice;
- orçamento de polling;
- base I/O do IDE bus master;
- flag indicando disponibilidade de DMA.

ata_pio_configure inicia com o canal primário:

~~~text
I/O base = 0x1f0
control  = 0x3f6
drive    = 0
poll limit = 1.000.000 iterações
DMA desabilitado
~~~

storage_init chama ata_pio_identify e, no sucesso, transforma esse estado em BlockDevice.

## Registradores task-file

O código usa os offsets tradicionais:

~~~text
+0 data
+2 sector count
+3 LBA low
+4 LBA mid
+5 LBA high
+6 drive/head
+7 status ou command
~~~

O control/alternate-status usa uma base separada, normalmente 0x3f6 ou 0x376.

PIO movimenta dados em palavras de 16 bits.

Um setor de 512 bytes contém:

~~~text
512 / 2 = 256 palavras
~~~

Os loops de read/write realizam exatamente 256 inw/outw por setor.

## Canais primário e secundário

ata_pio_identify procura:

~~~text
primário:   0x1f0 / 0x3f6
secundário: 0x170 / 0x376
~~~

Em cada canal tenta drive 0 e drive 1.

O scan pode repetir até oito tentativas. Depois da primeira, o código faz soft reset nos dois control ports legados e espera antes de tentar novamente.

Isso ajuda devices ou emuladores que ainda estão estabilizando depois do boot.

A função retorna no primeiro IDENTIFY bem-sucedido.

A camada atual, portanto, publica no máximo o primeiro ATA encontrado por essa instância.

## Seleção de drive e delay de 400 ns

ata_select grava o drive/head register:

~~~text
0xe0
| drive << 4
| bits LBA 27..24
~~~

Depois executa quatro leituras no control port.

Essas leituras de alternate status implementam o delay curto tradicional depois da seleção.

O nibble de LBA inserido no drive/head também evidencia um limite atual: apenas bits 24..27 entram nesse registrador.

## Sequência IDENTIFY

ata_try_identify:

1. seleciona o drive;
2. espera BSY limpar;
3. zera sector-count e registradores LBA;
4. envia comando 0xEC;
5. espera DRQ;
6. lê 256 words de identificação.

O driver rejeita o device se word 49 não indicar suporte a LBA.

A capacidade inicial vem dos words 60-61, o campo clássico LBA28.

Se word 83 bit 10 indica LBA48, o código também lê words 100-103.

Os 32 bits superiores precisam ser zero porque sector_count do BlockDevice é uint32_t.

Se a parte inferior possui valor aceitável, ela substitui a contagem LBA28.

## Capacidade descoberta versus capacidade de endereçamento

O parser IDENTIFY pode expor mais de 2^28 setores quando o campo LBA48 existe.

Porém o caminho real de comandos ainda programa:

- LBA0, LBA1 e LBA2;
- apenas quatro bits superiores no drive/head;
- READ SECTORS 0x20 e WRITE SECTORS 0x30 no PIO;
- READ DMA 0xC8 e WRITE DMA 0xCA no DMA.

Ele não emite READ/WRITE *_EXT nem executa a sequência expandida de registradores LBA48.

Logo o data path atual continua efetivamente limitado a LBA28.

Esse é um limite importante da implementação.

Um disco pode ser identificado com capacidade maior, mas LBAs acima de 0x0fffffff não são representados integralmente por ata_program porque bits 28..31 do LBA uint32_t são ignorados.

A documentação não deve afirmar suporte completo a LBA48 enquanto o command path permanecer assim.

## Polling de status

ata_poll lê repetidamente status.

Ele reconhece:

- 0xff como ausência de device;
- BSY;
- ERR;
- DF;
- DRQ quando dados são esperados.

Existe uma otimização para barramento vazio: status zero repetido antes de BSY ter sido observado retorna ENODEV depois de um limite menor.

Isso evita gastar todo o poll_limit quando não existe disco ATA.

Esgotar o orçamento retorna BD_ETIMEOUT.

## Leitura PIO

ata_read_chunk envia comando 0x20.

Para cada setor:

1. espera device não-busy com DRQ;
2. lê 256 words;
3. separa cada word em dois bytes no buffer.

O caller limita o chunk PIO a 255 setores, cabendo no sector-count de um byte sem usar a semântica especial de zero = 256.

O caminho é totalmente síncrono e CPU-driven.

## Escrita PIO

ata_write_chunk envia 0x30.

Para cada setor:

1. espera DRQ;
2. combina dois bytes da origem em um word;
3. escreve 256 words no data port.

Depois de todos os chunks de uma chamada de alto nível, ata_bd_write executa flush.

ata_flush_raw envia FLUSH CACHE 0xE7 e espera completion.

Isso dá ao caminho ATA uma operação de flush explícita, diferente de outros BlockDevices atuais que não possuem callback de flush.

## Descoberta do IDE bus master

IDENTIFY word 49 bit 8 indica capacidade DMA do device.

Se ativo, pci_find_ide procura na PCI bus zero um controller class 0x0101.

No sucesso:

- habilita I/O space e bus mastering;
- lê BAR4;
- exige BAR do tipo I/O;
- extrai base do bus master.

O driver ativa DMA.

Também registra ide_irq em IRQ14 e desmascara essa linha no PIC.

O desenho atual usa uma base bus-master global e uma flag global de completion.

## Fronteira da IRQ

ide_irq define g_ide_irq = 1.

Se há bus-master base, lê status e grava o mesmo valor para acknowledgement dos bits do controller.

ata_dma_wait não depende exclusivamente da IRQ.

Ele considera completion quando observa:

- g_ide_irq; ou
- o interrupt-status bit do bus master.

Depois ainda espera BSY limpar e verifica o error bit do bus master.

A combinação de IRQ e polling reduz dependência da ordem exata de eventos.

## Limite atual da IRQ

O código sempre instala o handler em IRQ14.

O canal IDE secundário legado normalmente usa IRQ15, mas o driver não escolhe dinamicamente a linha conforme o canal identificado.

Como ata_pio_identify pode encontrar device no secundário e o estado da IRQ é global, o DMA desse cenário não deve ser documentado como plenamente coberto.

É uma limitação concreta da implementação atual.

## Lifetime dos buffers DMA

O driver mantém duas alocações globais persistentes:

- data buffer contíguo;
- página PRDT.

A área de dados possui 8192 bytes:

~~~text
16 setores * 512 = 8192 bytes
~~~

As alocações são lazy, feitas no primeiro transfer DMA e mantidas pelo lifetime do driver.

Isso evita alocar PMM para cada I/O de filesystem/installer.

Também significa que existe um único estado DMA compartilhado, não buffers independentes por request.

## Addressability de 32 bits

O IDE bus master atual exige data e PRDT abaixo de 4 GiB.

ata_dma_acquire usa PMM normal e depois rejeita endereço físico acima de 0xffffffff.

Se falhar, devolve as páginas ao PMM.

O path ATA não usa diretamente pmm_alloc_dma32 para esses buffers.

Logo o sucesso depende do allocator geral entregar frames suficientemente baixos.

Esse detalhe fica mais relevante em máquinas com layouts físicos maiores.

## PRDT

O driver usa uma única entry.

~~~text
endereço = físico do bounce buffer
count    = bytes
EOT      = 1
~~~

prdt[0] recebe a base física.

prdt[1] recebe bytes OR bit 31, usado como end-of-table.

Como um transfer DMA tem no máximo 16 setores, o máximo é 8192 bytes.

Não existe scatter/gather com múltiplas regions nesse path.

## Sequência de DMA

ata_dma_xfer:

1. valida DMA e count de 1..16;
2. garante buffer/PRDT persistentes;
3. copia source para bounce buffer em write;
4. monta PRDT;
5. para o bus master;
6. programa endereço da PRDT;
7. limpa status;
8. configura direção;
9. zera flag da IRQ;
10. programa comando ATA DMA;
11. inicia engine;
12. espera completion;
13. para engine;
14. em read, copia bounce buffer para destino.

O controller nunca recebe diretamente um ponteiro arbitrário do caller.

## Função do bounce buffer

O buffer fixo resolve vários problemas:

- caller pode ser virtualmente contíguo mas fisicamente fragmentado;
- memória pode estar acima do limite de 32 bits;
- a implementação usa apenas uma PRDT entry.

O custo é uma cópia extra em cada DMA read/write.

O ganho é um contrato de hardware muito menor e previsível.

## Wait DMA limitado

ata_dma_wait possui 200.000 iterações.

Ele observa:

- status do bus master;
- status ATA;
- flag da IRQ.

Completion com BSY ainda ativo não é aceita.

Error do bus master retorna BD_EIO.

Esgotar loop retorna BD_ETIMEOUT.

O código faz leituras ocasionais de port 0x80 para espaçar polling.

Não existe espera infinita nessa rotina.

## Abort e fallback

Quando ata_dma_xfer falha, o path de alto nível chama ata_dma_abort.

A rotina:

- para bus master;
- faz soft reset no control port selecionado;
- espera not-busy.

Somente depois tenta PIO.

Essa ordem protege ownership do bounce buffer.

Fazer fallback enquanto o engine antigo ainda pudesse escrever seria uma race de DMA.

## Chunking

Em cada request:

~~~text
tentativa DMA: <= 16 setores
fallback PIO:  <= 255 setores
~~~

LBA, count restante e ponteiro avançam pelo tamanho do chunk efetivamente concluído.

Requests BlockDevice grandes viram vários comandos.

A camada genérica não conhece esses limites.

## Flush da escrita

Depois de todos os chunks, ata_bd_write chama ata_flush_raw.

Se o flush falhar, a operação inteira retorna falha.

Assim “bytes enviados” não é a fronteira final de sucesso da escrita ATA.

O BlockDevice ATA também registra ata_bd_flush, permitindo que callers peçam flush explicitamente.

## Modelo de concorrência

Não existe lock por device no driver.

Estado compartilhado inclui:

- task-file ports;
- drive;
- bounce buffer;
- PRDT;
- flag IRQ;
- bus-master base.

Requests simultâneos podem sobrescrever descriptors, data e completion state.

A arquitetura atual precisa serializar acesso ao ATA.

O padrão síncrono do BlockDevice ajuda, mas ata_pio.c não impõe sozinho essa exclusão.

## Mapeamento de erros

O driver normaliza:

- barramento/device ausente -> BD_ENODEV;
- orçamento excedido -> BD_ETIMEOUT;
- ERR, DF ou BM error -> BD_EIO;
- sucesso -> BD_OK.

storage.c e ChrisFS não precisam interpretar bits ATA.

## Desempenho

PIO custa 256 operações programadas de 16 bits por setor.

DMA reduz data movement feito diretamente pela CPU, mas continua usando bounce copy e wait síncrono.

O máximo DMA é apenas 8 KiB.

Não há command queue, merge de requests ou I/O sobreposto.

O desenho prioriza compreensibilidade e recovery simples.

## Validação necessária

Uma validação forte deve incluir:

- primary master/slave;
- secondary master/slave;
- ausência de disco;
- timeout de IDENTIFY;
- PIO read/write/flush;
- DMA read/write;
- erro DMA forçado com fallback PIO;
- integridade na fronteira de 16 setores;
- requests acima de 255 setores;
- capacidade próxima do limite LBA28;
- acesso acima de 0x0fffffff;
- buffer físico acima de 4 GiB;
- completion IRQ14;
- comportamento no canal secundário;
- persistência após reboot/flush.

Os testes genéricos do boot dão evidência end-to-end, mas não isolam todos esses casos.

## Limitações atuais

O driver possui:

- task-file legado;
- apenas o primeiro ATA identificado;
- command path LBA28;
- possibilidade de IDENTIFY expor capacidade LBA48 maior que o path consegue endereçar;
- sem READ/WRITE *_EXT;
- IRQ global 14 sem modelagem de IRQ15 secundária;
- buffers DMA abaixo de 4 GiB;
- uso do PMM geral em vez de zone DMA32 garantida;
- uma PRDT entry;
- um bounce buffer persistente;
- chunk DMA máximo de 16 setores;
- sem lock interno para requests concorrentes;
- sem NCQ;
- completion ainda baseada em polling finito mesmo com IRQ.

Essas são limitações do ChrisOS atual, não do ATA como padrão.

## Mapa de fonte

kernel/fs/ata_pio.c implementa task-file, IDENTIFY, PIO, DMA, completion, reset/fallback e callbacks BlockDevice.

kernel/fs/ata_pio.h define AtaPio.

kernel/metal/pci.c fornece pci_find_ide e descoberta do BAR bus-master.

kernel/metal/irq.c fornece registro da IRQ/PIC.

kernel/metal/pmm.c e bootinfo.c fornecem memória física e HHDM para os buffers.

As afirmações foram reconciliadas com ChrisOS e05a17fd76333114a3fb5c2452f38ca747d4ac56.
