---
id: ahci
lang: pt-br
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/ahci.h
  - kernel/fs/ahci.c
  - kernel/fs/block_device.h
  - kernel/fs/bdev.c
  - kernel/fs/storage.c
  - kernel/gfx/hwgate.h
  - kernel/gfx/hwgate.c
  - kernel/metal/pci.c
  - scripts/qemu.mk
symbols:
  - AhciPort
  - ahci_probe
  - start_port
  - issue
  - ahci_rw
  - ahci_read
  - ahci_write
  - wait_bit
  - hw_bar_map
  - hw_dma_alloc
  - hw_dma_lo
  - hw_dma_hi
  - hw_dma_w32
  - hw_dma_r32
  - bd_add_kind
depends_on:
  - block-storage
  - buses-mmio-dma
  - pci-pcie
  - physical-memory
related:
  - ata
  - nvme
  - partitions-gpt
  - chrisfs
---

# AHCI e SATA

## Escopo

O ChrisOS implementa um caminho AHCI compacto para discos SATA expostos por um controlador PCI AHCI. A implementação é deliberadamente menor que o padrão AHCI completo: descobre um controlador utilizável e um port utilizável, configura um único command slot, aloca uma página para estruturas de comando e uma página para dados, monta manualmente Register FIS Host-to-Device, emite comandos DMA EXT e acompanha a conclusão por polling do command-issue register do port.

O driver atual é síncrono e processa um único request por vez. Não implementa Native Command Queuing, múltiplos slots ativos, completion orientada a interrupção, hotplug, port multipliers, ATAPI, reset completo de controlador nem cache flush explícito. Seu objetivo é fornecer um caminho SATA DMA simples atrás do contrato comum `BlockDevice` do ChrisOS.

Este capítulo descreve a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![Caminho AHCI do ChrisOS desde a descoberta PCI até a conclusão SATA DMA](../../assets/diagrams/ahci-io-path-pt-br.svg)

## AHCI na arquitetura de armazenamento

A block layer enxerga AHCI como um device comum de setores de 512 bytes:

~~~text
ChrisFS / camada de partições
        -> BlockDevice
        -> ahci_read / ahci_write
        -> ahci_rw
        -> issue
        -> registradores AHCI + estruturas DMA
        -> device SATA
~~~

`storage_init` testa ATA legado primeiro e AHCI logo depois. Um device AHCI encontrado é registrado como `BD_AHCI`. A seleção de root não depende apenas da tecnologia de transporte: a camada de storage percorre os devices registrados em busca de ChrisFS ou de uma partição adequada e pode escolher AHCI como root quando houver um filesystem correspondente.

O gate `test-qemu-ahci` normalmente mantém o disco IDE comum como root e adiciona um segundo disco AHCI, permitindo que o teste genérico de read/write exercite AHCI como device não-root. Um segundo gate, `test-qemu-noata`, mostra o cenário em que o disco AHCI se torna root porque ATA legado está ausente.

## Modelo AHCI

AHCI substitui o acesso legado via task-file ports por uma interface host-controller mapeada em memória. O HBA expõe registradores globais e um bloco de registradores para cada port implementado. O sistema operacional fornece ao controlador endereços físicos para:

- command list;
- região de FIS recebidos;
- command tables;
- PRDTs que descrevem buffers DMA.

Um command slot na command list aponta para uma command table. A command table contém o FIS do comando e os descriptors de regiões físicas. Em seguida, o driver marca um bit em `PxCI`, o register de command issue do port. O hardware busca as estruturas por DMA, transfere dados, atualiza status e limpa o bit correspondente quando o slot deixa de estar ativo.

O ChrisOS usa somente o slot 0.

## Estado do driver

A estrutura privada `AhciPort` contém:

| Campo | Significado |
|---|---|
| `win` | janela MMIO correspondente ao BAR AHCI |
| `base` | offset do bloco de registradores do port selecionado |
| `ctl` | ID da alocação DMA das estruturas de controle |
| `data` | ID da alocação DMA do buffer de dados |
| `sectors` | quantidade de setores lógicos exposta |

Há uma única instância global, `g_port`, e uma flag global de ready. Depois que um disco utilizável é registrado, chamadas posteriores de `ahci_probe` retornam imediatamente.

Esse desenho reduz alocação de objetos, mas também significa que o driver representa somente um disco AHCI.

## Descoberta PCI

`ahci_probe` percorre PCI buses 0 a 7, devices 0 a 31 e functions 0 a 7. A informação de classe é lida no offset 8; o driver aceita funções cujo class/subclass seja `0x0106`, correspondente a SATA AHCI.

Ao encontrar um candidato, o ChrisOS atualiza o PCI command register com:

~~~text
old_command | 6
~~~

habilitando memory space e bus mastering.

Depois, BAR5 é mapeado por `hw_bar_map`. Em hardware AHCI convencional, BAR5 é o AHCI Base Address Register, normalmente chamado ABAR. `hw_bar_map` aceita memory BARs, trata BARs de 64 bits quando necessário, mede temporariamente o tamanho do BAR, mapeia páginas MMIO no kernel e retorna um identificador interno de janela.

A abstração genérica limita uma janela a 64 páginas, ou 256 KiB. AHCI normalmente precisa de muito menos.

## Habilitação do modo AHCI

Depois de mapear BAR5, o driver seta o bit 31 do Global Host Control register no offset MMIO `0x04`:

~~~text
GHC.AE = 1
~~~

Esse bit habilita o modo AHCI.

Em seguida, lê `PI`, Ports Implemented, no offset `0x0c`. Cada bit ativo representa um port implementado. O driver percorre ports 0 a 31 em ordem crescente.

O bloco de registradores de um port começa em:

~~~text
0x100 + port_number * 0x80
~~~

Somente ports indicados por `PI` são avaliados.

## Detecção de link

Para cada port implementado, o ChrisOS lê `PxSSTS` no offset `0x28` do port. O driver avalia apenas os quatro bits inferiores DET e exige:

~~~text
DET == 3
~~~

o que representa presença de device com comunicação estabelecida.

O código atual não valida adicionalmente o campo de power management nem `PxSIG`. Portanto, ele não distingue explicitamente um disco SATA de um ATAPI device pelo signature register antes de emitir IDENTIFY. Um candidato incompatível é simplesmente descartado quando etapas posteriores falham.

## Topologia de memória DMA

Para cada candidato, o driver aloca duas páginas físicas contíguas por `hw_dma_alloc(1)`:

- `ctl`: uma página de 4096 bytes para command list, received-FIS area e command table;
- `data`: uma página de 4096 bytes para o payload.

Diferentemente do caminho ATA Bus Master legado, essas páginas não precisam ficar abaixo de 4 GiB. As estruturas AHCI carregam os 32 bits baixos e altos dos endereços físicos, preenchidos por `hw_dma_lo` e `hw_dma_hi`.

A página de controle é particionada com offsets fixos:

~~~text
0x000  command list; header do slot 0
0x400  região de FIS recebidos
0x500  command table do slot 0
0x580  primeira entrada PRDT da command table
~~~

Somente o slot 0 é usado, então grande parte da command list permanece sem uso.

A página de dados comporta 4096 bytes. Com setores de 512 bytes, cada comando transporta no máximo oito setores.

## Sequência de start do port

`start_port` lê `PxCMD` no offset `0x18`. Em seguida limpa:

- bit 0, `ST`, command-list running;
- bit 4, `FRE`, FIS receive enable.

O novo valor é escrito e o driver espera ambos os bits de estado do engine ficarem limpos:

- bit 15, `CR`, command-list running;
- bit 14, `FR`, FIS receive running.

`wait_bit` faz polling por no máximo 200000 iterações. Se falhar, o probe desse candidato é abandonado.

Depois que os engines param, o ChrisOS grava o endereço físico de 64 bits da página de controle em `PxCLB/PxCLBU`. A área de FIS recebidos é colocada em `control_page + 0x400` e seu endereço vai para `PxFB/PxFBU`.

`PxSERR` é limpo escrevendo todos os bits em 1 no offset `0x30`. Por fim, `FRE` e `ST` são reativados.

Essa sequência reinicia os engines do port, mas não corresponde a um HBA reset completo nem a um SATA COMRESET.

## Construção do command header

Antes de cada comando, `issue` zera os 4096 bytes da página de controle. Assim são apagados command header, received-FIS area e command table anteriores.

O primeiro dword do header do slot 0 recebe:

~~~text
5
| (write ? (1 << 6) : 0)
| (1 << 16)
~~~

Os campos representam:

- command-FIS length = 5 dwords = 20 bytes;
- flag de direção de write quando o host envia dados ao device;
- PRDT length = 1.

O endereço físico da command table é escrito nos offsets 8 e 12 do header como partes baixa e alta. Ele aponta para `control_page + 0x500`.

Logo, a implementação usa um command header e exatamente uma entrada PRDT por request.

## Register FIS Host-to-Device

A command table começa com um Register FIS Host-to-Device. O ChrisOS escreve o primeiro dword como:

~~~text
0x00008027 | (command << 16)
~~~

Isso codifica:

- FIS type `0x27`;
- bit command/control no byte 1;
- opcode ATA no byte 2.

O dword seguinte recebe os 24 bits inferiores do LBA mais o device byte `0x40`, selecionando endereçamento LBA. O próximo dword recebe os bits 24 a 47. Sector count é gravado nos bytes 12-13 do FIS.

O source registra explicitamente uma correção importante: sector count pertence aos bytes 12-13, e não ao byte expanded-features. Um FIS com campo deslocado pode parecer plausível e ainda produzir tamanho incorreto de transferência.

## Comandos de dados e endereçamento

Reads usam opcode ATA `0x25`, `READ DMA EXT`. Writes usam `0x35`, `WRITE DMA EXT`. Ambos são comandos LBA48.

Isso difere do driver ATA legado documentado no capítulo anterior, que atualmente usa opcodes de dados LBA28.

Embora o FIS consiga carregar 48 bits de LBA, o ChrisOS passa `lba` como `uint32_t`, e `BlockDevice.sector_count` também é 32-bit. Assim, a capacidade visível pelo software continua limitada a no máximo `2^32` setores. Com setores de 512 bytes, isso equivale a aproximadamente 2 TiB, apesar de AHCI/SATA suportarem endereçamento maior.

## Construção da PRDT

A única entrada PRDT fica no offset `0x80` da command table, correspondente ao offset `0x580` da página de controle.

O ChrisOS grava:

- 32 bits baixos do endereço físico do data buffer;
- 32 bits altos;
- byte count menos um;
- bit interrupt-on-completion no bit mais alto do campo de contagem.

Conceitualmente:

~~~text
DBA/DBAU = endereço físico da página de dados
DBC      = count * 512 - 1
IOC      = 1
~~~

Apesar de IOC estar habilitado, o driver atual não usa handler de interrupção AHCI para completion. O acompanhamento continua sendo feito por polling de `PxCI`.

A PRDT possui uma única região física contígua; não há scatter/gather.

## Emissão do comando

Antes de ativar o slot, o driver escreve todos os bits em 1 em `PxIS` no offset `0x10`, limpando interrupt status pendente.

Depois escreve `1` em `PxCI`, offset `0x38`, ativando slot 0.

O código faz polling por até 500000 iterações. A cada 128 iterações executa `io_wait`. A conclusão é reconhecida quando o bit 0 de `PxCI` volta a zero.

Quando o slot é limpo pelo hardware, o ChrisOS lê:

- `PxTFD` no offset `0x20`;
- `PxIS` no offset `0x10`.

Se bit 0 de `PxTFD` estiver ativo, o driver imprime ambos os valores e retorna falha de I/O. Caso contrário, considera o comando concluído.

Se o limite de polling termina com `PxCI` ainda ativo, `issue` retorna timeout.

## Caminho síncrono de leitura

`ahci_read` delega a `ahci_rw` com write desativado.

O loop divide requests em blocos de até oito setores. Para cada bloco, chama `issue` com `READ DMA EXT`. Depois da completion, a página interna de dados é copiada para o buffer do caller em palavras de 32 bits.

`hw_dma_r32` lê cada palavra e o driver distribui os quatro bytes no destino.

O custo de cópia da CPU é linear no volume de dados, `O(n)`. A transferência SATA em si ocorre por DMA, mas o driver não é zero-copy porque cada read passa pela página intermediária.

## Caminho síncrono de escrita

No write, a cópia ocorre antes do comando. Os bytes do caller são combinados em palavras de 32 bits e gravados na página interna com `hw_dma_w32`. Em seguida, o driver emite `WRITE DMA EXT`.

Depois da completion, a operação retorna `BD_OK` sem enviar um comando ATA FLUSH CACHE explícito.

O `BlockDevice` registrado usa:

~~~text
flush = 0
~~~

e o `bd_flush` genérico trata callback ausente como sucesso. Portanto, o backend AHCI atual **não** expõe uma fronteira explícita de flush do cache do device. A completion do write mostra que o comando terminou no controlador/device, mas a API atual não força separadamente dados possivelmente voláteis do cache do disco para mídia estável.

Essa diferença é importante para qualquer afirmação de crash consistency do filesystem.

## Normalização de erros

`issue` possui duas classes internas de falha:

- erro comum, incluindo task-file error;
- timeout esperando `PxCI` limpar.

`ahci_rw` converte para o domínio comum:

| Resultado interno | Resultado BlockDevice |
|---|---|
| sucesso | `BD_OK` |
| timeout | `BD_ETIMEOUT` |
| outra falha | `BD_EIO` |

Argumentos inválidos e requests fora de range são normalmente bloqueados antes por `bd_read` e `bd_write`.

O driver não decodifica detalhadamente erros do SATA error register, do received D2H FIS ou de `PxSERR` depois de uma falha. O diagnóstico atual imprime `PxTFD` e `PxIS` quando o bit de erro do task file aparece.

## IDENTIFY durante o probe

Depois de iniciar um port candidato, o ChrisOS reutiliza a mesma infraestrutura para emitir `IDENTIFY DEVICE` (`0xec`) com um setor.

O payload de 512 bytes é interpretado como 128 valores de 32 bits. Como cada valor contém duas ATA identify words:

- elemento 50 representa ATA words 100-101, os 32 bits baixos da capacidade LBA48;
- elemento 51 representa words 102-103, os 32 bits altos;
- elemento 30 representa words 60-61, a capacidade LBA28.

Se o elemento 51 for diferente de zero, o driver imprime `ahci disk too large` e rejeita o device porque a block interface atual não representa essa capacidade completa.

Caso contrário, usa inicialmente elemento 50. Se ele for menor que 2048 setores, tenta elemento 30. Devices ainda menores que 2048 são ignorados.

É um parser pragmático de capacidade, não um decoder completo das capabilities de IDENTIFY.

## Registro e seleção de root

Um device aceito vira `BlockDevice` writable de 512 bytes, com callbacks AHCI e sem callback de flush. É registrado com nome `ahci` e kind `BD_AHCI`, e o driver imprime:

~~~text
ahci disk sectors=<count>
~~~

Nesse ponto o probe termina. Ports adicionais e outros controladores AHCI não são registrados.

A seleção do root acontece depois na camada genérica de storage. Assim, AHCI pode ser:

- disco secundário não-root;
- disco root quando contém o ChrisFS escolhido;
- target de instalação quando o registry o considera elegível.

## Concorrência e ownership

O padrão AHCI suporta vários command slots e, com NCQ, paralelismo substancial. O ChrisOS não expõe isso.

Existe um único objeto global de port, uma página de controle, uma página de dados e somente slot 0. Cada comando apaga e reescreve as mesmas estruturas. Não há mutex ou spinlock dentro do driver AHCI.

O invariante necessário é um caller por vez. Requests concorrentes poderiam corromper:

- command header;
- H2D FIS;
- PRDT;
- data bounce page;
- estado de completion em `PxCI`.

A stack síncrona atual tende a preservar esse pressuposto, mas o próprio driver não o garante explicitamente.

## Timeout e recovery

O polling finito impede espera eterna, mas o recovery após timeout é incompleto.

Quando um comando expira, o driver retorna `BD_ETIMEOUT`. Ele não:

- limpa ou aborta o slot ativo;
- para e reinicia o command engine;
- executa port reset;
- executa COMRESET;
- reseta o HBA;
- prova que o controlador deixou de poder fazer DMA sobre a página de dados.

Esse último item é um problema de ownership. Depois de timeout, um recovery robusto deve provar que o comando antigo parou antes de reutilizar o buffer. O código atual não estabelece essa garantia explicitamente.

É uma das principais lacunas de hardening do driver.

## Lifetime de recursos no probe

Duas páginas DMA são alocadas para cada port que chega à fase de preparação.

Se a alocação em si falha, os IDs obtidos são liberados. Entretanto, depois que ambas as páginas existem, alguns rejection paths posteriores — falha em `start_port`, falha em IDENTIFY, capacidade grande demais ou pequena demais — continuam a busca sem liberar essas páginas.

Isso cria um leak real, embora limitado, durante o probe de ports rejeitados. Como o allocator de DMA possui número finito de slots, esse comportamento precisa ser corrigido antes de ampliar a descoberta para muitos controladores e devices.

## Privilégio e safety

AHCI exige acesso privilegiado à configuração PCI, MMIO e bus-master DMA. O driver roda inteiramente no kernel.

As proteções atuais incluem:

- bounds check de LBA na block layer;
- polling com limites;
- acesso MMIO por janela mapeada com bounds;
- buffers DMA em memória física contígua pertencente ao kernel;
- endereços físicos completos de 64 bits nas estruturas AHCI;
- tamanho de request limitado à página de dados.

Faltam IOMMU, mapeamento DMA por request, teardown robusto em timeout e locks por controlador.

Uma command table corrompida ou endereço físico errado pode instruir o HBA a acessar memória física indevida.

## Características de desempenho

O hardware usa SATA DMA, mas a arquitetura de software impõe vários limites:

- payload máximo de 4 KiB por comando;
- uma única entrada PRDT;
- um command slot;
- sem NCQ;
- polling em vez de sleep/wakeup por IRQ;
- cópia completa para/de um buffer DMA intermediário;
- zeragem da página de controle inteira a cada comando.

Para um request sequencial maior que oito setores, `ahci_rw` submete múltiplos comandos. A quantidade de submissões é aproximadamente:

~~~text
ceil(sector_count / 8)
~~~

O desenho favorece simplicidade, depuração e ownership determinístico em vez do throughput que AHCI poderia alcançar.

## Evidência de validação

Há dois gates QEMU especialmente relevantes.

### Gate de disco secundário

`test-qemu-ahci` cria uma imagem zeroed de 32 MiB e a conecta ao modelo ICH9 AHCI do QEMU. O gate exige:

~~~text
ahci disk sectors=
bdev rw ok ahci
~~~

`bdev_rw_tests` lê o último setor, salva seu conteúdo, escreve um pattern determinístico, lê de volta, compara cada byte e restaura o setor original. Como o disco IDE comum continua como root nesse cenário, o disco AHCI é elegível para esse teste destrutivo com restauração.

Isso valida discovery e um round trip completo de write/read pela block layer.

### Gate com AHCI como root

`test-qemu-noata` conecta o disco root via AHCI e exige:

~~~text
ata missing
root ahci
cfs mounted
install selftest ok
desktop 60Hz
~~~

Esse cenário fornece evidência mais forte de integração: AHCI se torna o block device root, ChrisFS monta sobre ele e o sistema continua para fases posteriores de boot.

Esses testes validam o modelo ICH9 AHCI do QEMU na configuração testada. Não representam certificação ampla de controladores SATA físicos.

## Limitações atuais

Na revisão documentada, o caminho AHCI possui os seguintes limites:

- somente um disco AHCI registrado;
- somente um port selecionado;
- somente command slot 0;
- uma entrada PRDT;
- no máximo oito setores por comando;
- buffer interno de dados de 4 KiB;
- completion por polling;
- sem handler de interrupção AHCI;
- sem NCQ;
- sem queue de múltiplos requests;
- sem ATAPI;
- sem port multipliers;
- sem hotplug;
- sem validação explícita de tipo pelo `PxSIG`;
- sem comando explícito de flush de cache;
- sem suporte a setores lógicos de 4 KiB;
- sem abort/recovery robusto em timeout;
- sem reset de HBA ou COMRESET;
- sem lock do driver para callers SMP;
- sem continuar registrando ports úteis depois do primeiro disco;
- sector count de 32 bits, limitando a capacidade exposta a aproximadamente 2 TiB com setores de 512 bytes;
- cleanup incompleto de páginas DMA em candidatos rejeitados.

Esses limites pertencem à implementação ChrisOS atual, não ao padrão AHCI/SATA.

## Fronteira de roadmap

Uma implementação mais completa pode adicionar objetos por port, alocação de slots, PRDT scatter/gather, completion por interrupção, NCQ, `FLUSH CACHE EXT`, validação de signature, hotplug, decoding de error FIS, cancellation robusta, HBA/port reset, cleanup consistente no probe, locking e validação em hardware SATA físico.

Esses recursos permanecem futuros até existirem no source e terem evidência reproduzível.

## Mapa de source e nota de revisão

`kernel/fs/ahci.c` implementa discovery, configuração do port, montagem de comandos, transferências DMA e adaptação à block layer. `kernel/fs/ahci.h` expõe o probe. `kernel/gfx/hwgate.c` fornece as abstrações de MMIO e DMA físico usadas pelo driver. `kernel/fs/block_device.h` e `kernel/fs/bdev.c` definem contrato e registro de devices. `kernel/fs/storage.c` integra AHCI à descoberta de root, formatação e validação de block I/O. `scripts/qemu.mk` define os gates AHCI.

Todas as afirmações sobre comportamento atual neste capítulo foram reconciliadas com ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
