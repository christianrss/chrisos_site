---
id: ahci
lang: pt-br
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/ahci.c
  - kernel/fs/ahci.h
  - kernel/fs/block_device.h
  - kernel/fs/bdev.c
  - kernel/gfx/hwgate.c
  - kernel/gfx/hwgate.h
  - kernel/metal/pci.c
  - kernel/metal/mm.c
  - kernel/metal/pmm.c
symbols:
  - ahci_probe
  - start_port
  - issue
  - ahci_rw
  - ahci_read
  - ahci_write
  - hw_bar_map
  - hw_dma_alloc
  - hw_mmio_r32
  - hw_mmio_w32
depends_on:
  - block-storage
  - pci-pcie
  - buses-mmio-dma
  - physical-memory
related:
  - ata
  - nvme
  - partitions-gpt
---

# AHCI e SATA DMA

## Escopo

AHCI é a interface memory-mapped comum para controladores SATA. Diferentemente de ATA PIO legado, a CPU não transfere cada word por uma data port. Software monta estruturas de comando em memória visível ao DMA, aponta o port AHCI para elas, marca um command slot como issued e espera o controller concluir.

O driver atual do ChrisOS implementa um subconjunto deliberadamente pequeno:

- descoberta PCI por class code AHCI;
- mapping MMIO do BAR5;
- um único port/device ativo;
- um command slot;
- uma PRDT entry;
- um data buffer DMA de 4 KiB;
- IDENTIFY DEVICE;
- READ DMA EXT e WRITE DMA EXT;
- polling síncrono de completion;
- setores BlockDevice de 512 bytes.

![Caminho AHCI atual do ChrisOS da descoberta PCI até estruturas DMA e BlockDevice](../../assets/diagrams/ahci-command-path-pt-br.svg)

Não há ainda NCQ, I/O dirigido por interrupção, hotplug, registro de múltiplos ports, ATAPI, recovery completo após timeout ou flush explícito de cache.

## Descoberta PCI

ahci_probe percorre:

~~~text
bus      0..7
device   0..31
function 0..7
~~~

Functions ausentes são ignoradas.

O driver exige class/subclass:

~~~text
0x0106
~~~

correspondente a SATA AHCI.

Ao encontrar controller, OR 6 no PCI command register.

Isso habilita:

- memory space para o BAR;
- bus mastering para DMA.

## BAR5 e MMIO

O ABAR AHCI vem do BAR5.

O ChrisOS chama hw_bar_map.

Esse helper:

- lê o BAR;
- entende memory BAR de 64 bits;
- mede o tamanho;
- cria mappings pela janela MMIO do kernel;
- registra a região numa tabela limitada de hardware windows.

O hardware gate garante pelo menos 64 KiB e limita uma window a 64 páginas, isto é, 256 KiB.

Depois o driver usa hw_mmio_r32/hw_mmio_w32 com offsets.

O físico do BAR não é dereferenciado diretamente.

## Habilitação do modo AHCI

Após mapear BAR5, o probe ativa bit 31 do Global Host Control em offset 0x04.

É o AHCI Enable.

Depois lê Ports Implemented em offset 0x0c.

Somente ports cujo bit PI está setado são examinados.

Isso evita operar blocks que o HBA declara não implementados.

## Layout dos registradores do port

Para port p:

~~~text
port_base = 0x100 + p * 0x80
~~~

O driver usa:

~~~text
+0x00 CLB
+0x04 CLBU
+0x08 FB
+0x0c FBU
+0x10 PxIS
+0x18 PxCMD
+0x20 PxTFD
+0x28 PxSSTS
+0x30 PxSERR
+0x38 PxCI
~~~

Somente parte do modelo completo AHCI é necessária no código atual.

## Check de device presente

O probe lê PxSSTS.

Exige:

~~~text
PxSSTS.DET == 3
~~~

indicando device presente com comunicação estabelecida.

O código atual não classifica o device via PxSIG antes de enviar IDENTIFY DEVICE.

Assim o path efetivo suporta devices ATA SATA que respondem a 0xec.

ATAPI não possui caminho separado.

## Estado estático de um port

Existe um único AhciPort global e um g_ready.

Ao registrar o primeiro disco funcional, ahci_probe retorna.

Chamadas seguintes retornam sucesso sem scan adicional.

Portanto a implementação expõe no máximo um BlockDevice AHCI.

Mesmo que existam vários ports, eles não são todos registrados.

## Alocações DMA

Para cada candidato, o driver pede duas páginas via hw_dma_alloc:

- ctl para command/control structures;
- data para payload.

Cada região possui 4 KiB.

hw_dma_alloc usa PMM contíguo, cria alias HHDM e registra físico/virtual no hardware gate.

AHCI recebe low e high 32 bits dos endereços, portanto não está deliberadamente preso abaixo de 4 GiB como o bus-master IDE legado.

## Layout da página de controle

A mesma página de 4 KiB contém:

~~~text
0x000: command list
0x400: received-FIS area
0x500: command table do slot 0
0x580: PRDT entry
~~~

Os primeiros 1024 bytes comportam as 32 command headers previstas pelo AHCI.

Mas o driver usa apenas slot zero.

A received-FIS area começa em 0x400.

A command table corrente começa em 0x500.

O desenho cabe em uma página porque existe somente um command table/PRDT em uso.

## Inicialização do port

start_port lê PxCMD.

Primeiro limpa:

- ST;
- FRE.

Depois espera command-list-running e FIS-receive-running ficarem zero.

Só então programa:

- CLB/CLBU com a base física de ctl;
- FB/FBU com ctl + 0x400.

PxSERR é limpo escrevendo 0xffffffff.

Em seguida FRE e ST são ligados novamente.

Parar os engines antes de trocar as bases é uma transição importante do controller.

## Wait limitado para parar engines

wait_bit usa no máximo 200.000 iterações.

start_port usa a rotina para esperar os bits de running limparem.

Se o estado não chega ao esperado, o candidato é rejeitado.

Não existe HBA reset completo nesse path.

O probe tenta seguir para outro port/controller.

## Command header

issue aceita de um a oito setores.

Ele zera os 4 KiB da página ctl a cada comando.

A header do slot zero recebe:

- FIS length = 5 dwords;
- write bit quando necessário;
- PRDT length = 1;
- command-table address = ctl + 0x500.

Existe apenas uma PRDT entry e um buffer contíguo.

## Register FIS H2D

A command table começa com Register Host-to-Device FIS.

O primeiro dword contém:

- FIS type 0x27;
- command/control bit;
- opcode ATA.

O driver usa:

~~~text
0xec IDENTIFY DEVICE
0x25 READ DMA EXT
0x35 WRITE DMA EXT
~~~

Diferentemente do path ATA task-file atual, o AHCI usa a família DMA EXT.

## Codificação do LBA

O FIS recebe 24 bits baixos do LBA em um dword e 24 bits seguintes em outro.

O device byte contém o LBA-mode bit.

O formato suporta 48 bits.

Porém issue recebe lba como uint32_t.

Logo apenas até 32 bits significativos chegam do BlockDevice atual.

Isso coincide com sector_count uint32_t.

## Sector count e limite de oito

O count do FIS é de 16 bits.

Mesmo assim issue limita o request a oito setores.

O motivo é o data buffer:

~~~text
8 * 512 = 4096 bytes
~~~

Uma página comporta todo o payload.

O limite não vem do AHCI.

## PRDT

A PRDT entry em 0x580 recebe:

- base física low;
- base física high;
- byte count minus one;
- interrupt-on-completion.

Para n setores:

~~~text
DBC = n * 512 - 1
~~~

IOC é setado.

Apesar disso, completion normal não usa um handler AHCI.

O driver faz polling de PxCI.

## Clear de status e issue do slot zero

Antes de iniciar, issue escreve 0xffffffff em PxIS.

Depois grava bit zero em PxCI.

Isso marca command slot 0 como issued.

Nenhum outro slot é usado.

Não existe gerenciamento de queue depth.

## Polling de completion

issue executa até 500.000 iterações.

A cada 128 chama io_wait.

A condição principal é:

~~~text
PxCI bit 0 == 0
~~~

Quando o HBA limpa o bit, o código lê PxTFD e PxIS.

Se o ERR bit do task-file estiver setado, retorna erro.

Caso contrário, sucesso.

Se o bit nunca limpar no orçamento, retorna timeout.

ahci_rw converte:

- timeout -> BD_ETIMEOUT;
- outro erro -> BD_EIO.

## Decodificação limitada de erro

PxIS é lido para diagnóstico, mas o driver não possui decoder completo dos error bits AHCI.

A decisão principal usa ERR do PxTFD.

Não existe recovery detalhado baseado em SATA error register, TFES, interface fatal errors ou transições de link.

Isso reduz a complexidade, mas limita diagnóstico e recuperação.

## Bounce buffer de read/write

ahci_rw divide request em chunks de até oito setores.

Em write:

1. copia bytes para a página data;
2. envia WRITE DMA EXT;
3. espera completion.

Em read:

1. envia READ DMA EXT;
2. espera completion;
3. copia data para o buffer do caller.

O HBA nunca recebe ponteiro arbitrário do caller.

DMA usa uma página persistente do driver.

Há custo de cópia, mas o layout físico e lifetime ficam simples.

## IDENTIFY DEVICE

O probe executa issue com 0xec e um setor.

Os 512 bytes são lidos como 128 dwords.

O código usa:

- dword 50 como 32 bits baixos de sector count LBA48;
- dword 51 como parte alta;
- dword 30 como fallback words 60-61 do LBA28.

Se dword 51 não é zero, o disk é rejeitado como grande demais para sector_count uint32_t.

Se a capacidade final é menor que 2048 setores, o port não é aceito.

## Suposição de setor lógico 512

O BlockDevice registrado sempre possui:

~~~text
sector_size = 512
~~~

O driver não interpreta extensões IDENTIFY para logical sector size diferente.

Portanto device SATA com 4Kn ou outra geometria lógica não deve ser considerado suportado pelo path atual.

## Registro do BlockDevice

No sucesso:

- ctx = AhciPort global;
- sector_size = 512;
- sector_count = capacidade;
- read = ahci_read;
- write = ahci_write;
- flush = null;
- writable = true.

bd_add_kind registra como BD_AHCI.

Como flush é null, bd_flush genérico retorna BD_OK sem enviar ATA FLUSH CACHE.

## Fronteira de durabilidade

Write AHCI retorna sucesso quando o comando DMA termina.

Não existe FLUSH CACHE explícito em ahci.c.

Assim write bem-sucedido seguido de bd_flush também não prova que um cache volátil do device foi drenado por esse driver.

Isso difere do ATA legado, que executa comando 0xe7.

Claims de crash consistency precisam reconhecer essa diferença.

## Problema de ownership após timeout

Se PxCI não limpa, issue retorna timeout.

ahci_rw propaga BD_ETIMEOUT.

O código atual não:

- para o port;
- cancela o slot;
- reseta o controller;
- prova que DMA terminou.

A próxima request pode reutilizar ctl e data.

Logo o recovery de timeout não fecha o lifetime do comando antigo.

Um driver hardened deve quiescer/resetar o port antes de reutilizar memória que o HBA ainda possa acessar.

## Leaks durante probe

Para cada port candidato, ctl e data são alocados antes de start_port/IDENTIFY.

Vários failures posteriores fazem continue sem chamar hw_dma_free.

Exemplos:

- start_port falha;
- IDENTIFY falha;
- capacidade alta rejeitada;
- device pequeno.

Como os fields globais são sobrescritos no próximo candidato, esses DMA slots/pages podem ficar inalcançáveis.

É um defeito atual de resource lifetime e não deve ser escondido pela documentação.

## Design de um slot

AHCI suporta vários slots e SATA pode usar NCQ.

O ChrisOS atual usa somente slot zero.

Consequências:

- um comando em flight;
- sem NCQ;
- sem scheduling paralelo;
- sem completions fora de ordem;
- ownership simples de um buffer.

Isso combina com BlockDevice síncrono, mas deixa grande parte do modelo AHCI sem uso.

## Polling versus interrupção

A PRDT pede IOC, mas o driver não registra handler AHCI para completion normal.

PxCI é polled.

Isso simplifica implementação, porém consome CPU e impede overlap natural de I/O com outras tarefas por uma API assíncrona.

Interrupt-driven I/O exigiria IDs de requests e sincronização que a interface atual não possui.

## Fronteira hwgate

ahci.c não chama PMM/MM diretamente.

Ele usa:

~~~text
BAR PCI -> hw_bar_map -> janela MMIO
DMA -> hw_dma_alloc -> PMM + HHDM
registradores -> hw_mmio_*
memória DMA -> hw_dma_*
~~~

Isso centraliza mapping e bounds.

Também herda limites globais do hwgate, como número finito de windows e DMA slots.

## Concorrência

O driver usa estado global e não possui lock de requests.

ctl e data são reutilizados.

Chamadas simultâneas poderiam:

- zerar control page durante comando ativo;
- sobrescrever payload;
- alterar PxCI;
- confundir completion.

O design pressupõe serialização externa.

Uma futura block layer paralela precisa fornecer locks e storage por request.

## Desempenho

A implementação prioriza simplicidade:

- uma página de dados;
- oito setores por comando;
- um slot;
- uma PRDT;
- bounce copies;
- polling;
- sem NCQ.

Requests grandes viram vários comandos de 4 KiB.

Há DMA, então controller movimenta dados para RAM sem PIO palavra a palavra, mas software ainda copia entre buffer do caller e bounce page.

## Validação necessária

Uma matriz forte inclui:

- controller ausente;
- múltiplos controllers;
- vários ports;
- DET diferente de 3;
- IDENTIFY;
- integridade read/write;
- crossing da fronteira de 8 setores;
- disco próximo do limite uint32;
- setor lógico diferente de 512;
- PxTFD ERR forçado;
- timeout forçado;
- prova de quiesce antes de reusar DMA após timeout;
- repetição de probes falhos para detectar leak;
- teste explícito de flush/durabilidade;
- callers concorrentes;
- hardware físico além de QEMU.

Os testes genéricos do block layer cobrem caminho de sucesso, não todas essas invariantes.

## Limitações atuais

O driver atual:

- escaneia somente buses PCI 0..7;
- registra apenas o primeiro disco AHCI funcional;
- não suporta ATAPI;
- não suporta port multiplier;
- assume setor lógico de 512 bytes;
- usa sector_count uint32_t;
- usa um command slot;
- usa uma PRDT entry;
- limita a oito setores por comando;
- possui uma página data compartilhada;
- usa polling síncrono;
- não implementa NCQ;
- não envia FLUSH CACHE;
- possui recovery incompleto de timeout;
- pode vazar DMA em failures de probe;
- não implementa hotplug/power management;
- possui decodificação limitada de erros AHCI/SATA.

São propriedades do ChrisOS atual, não limitações do AHCI/SATA em geral.

## Mapa de fonte

kernel/fs/ahci.c implementa scan PCI, seleção de port, startup, construção FIS/PRDT, IDENTIFY, read/write e registro BlockDevice.

kernel/gfx/hwgate.c/h fornece BAR mapping, MMIO e DMA.

kernel/metal/mm.c sustenta a janela MMIO.

kernel/metal/pmm.c fornece frames DMA.

kernel/fs/block_device.h e bdev.c expõem o disk ao stack comum.

As afirmações foram reconciliadas com ChrisOS e05a17fd76333114a3fb5c2452f38ca747d4ac56.
