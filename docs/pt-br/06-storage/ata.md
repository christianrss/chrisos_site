---
id: ata
lang: pt-br
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/ata_pio.h
  - kernel/fs/ata_pio.c
  - kernel/fs/block_device.h
  - kernel/fs/storage.c
  - kernel/metal/pci.h
  - kernel/metal/pci.c
  - scripts/qemu.mk
symbols:
  - AtaPio
  - ata_pio_configure
  - ata_pio_identify
  - ata_try_identify
  - ata_program
  - ata_poll
  - ata_read_chunk
  - ata_write_chunk
  - ata_dma_acquire
  - ata_dma_xfer
  - ata_dma_wait
  - ata_dma_abort
  - ata_pio_make_device
  - pci_find_ide
  - storage_init
depends_on:
  - block-storage
  - buses-mmio-dma
  - pci-pcie
  - interrupts-smp
  - physical-memory
related:
  - ahci
  - partitions-gpt
  - chrisfs
---

# ATA PIO e Bus Master IDE DMA

## Escopo

O caminho ATA do ChrisOS é um driver de armazenamento em blocos orientado à compatibilidade com interfaces IDE baseadas no task file clássico. Ele oferece dois mecanismos de transferência sob o mesmo `BlockDevice`: I/O programado pelo data port ATA e PCI Bus Master IDE DMA por meio de uma Physical Region Descriptor Table. O driver descobre devices com `IDENTIFY DEVICE`, converte erros do controlador para o domínio comum `BD_*` e, quando DMA falha, aborta e reseta o canal antes de tentar o mesmo request por PIO.

Este capítulo descreve o comportamento presente na revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Recursos previstos por versões posteriores do padrão ATA não são tratados como implementados por analogia. Os comandos de dados atuais são os opcodes de 28 bits `READ SECTORS`, `WRITE SECTORS`, `READ DMA` e `WRITE DMA`; os comandos extended de 48 bits não são emitidos.

![Caminho de request ATA no ChrisOS por DMA ou PIO](../../assets/diagrams/ata-io-path-pt-br.svg)

## Posição na stack de armazenamento

`storage_init` mantém uma instância global de `AtaPio`, configura-a, faz o probe, converte-a em `BlockDevice` e a registra como `BD_ATA`. ChrisFS e a camada de partições, portanto, consomem a mesma interface orientada a setores usada para AHCI, NVMe e VirtIO Block.

O fluxo conceitual é:

~~~text
ChrisFS / view de partição
        -> BlockDevice
        -> ata_bd_read / ata_bd_write / ata_bd_flush
        -> Bus Master IDE DMA quando disponível
              ou
           fallback ATA PIO
        -> registradores IDE task file
        -> device ATA físico ou virtual
~~~

A block layer genérica valida que o request permaneça dentro de `sector_count` e exige setores lógicos de 512 bytes. O driver ATA usa a mesma unidade nos loops PIO, nos cálculos de tamanho DMA e no avanço dos buffers.

## Interface ATA task file

O driver usa o conjunto de registradores clássico relativo a `AtaPio.io`:

| Offset | Registrador | Uso atual |
|---:|---|---|
| 0 | DATA | payload PIO em palavras de 16 bits |
| 2 | SECTOR COUNT | quantidade de setores |
| 3 | LBA0 | bits 0-7 do LBA |
| 4 | LBA1 | bits 8-15 |
| 5 | LBA2 | bits 16-23 |
| 6 | DRIVE/HEAD | master/slave, modo LBA e bits 24-27 |
| 7 | STATUS / COMMAND | leitura de status e escrita de comandos |

O alternate-status/control port fica em `AtaPio.ctrl`. O ChrisOS testa o canal primário em `0x1f0/0x3f6` e o secundário em `0x170/0x376`.

Quatro bits de status participam diretamente da state machine:

- `ERR` (`0x01`) indica erro de comando;
- `DRQ` (`0x08`) informa que a fase de dados está pronta;
- `DF` (`0x20`) indica device fault;
- `BSY` (`0x80`) informa que o comando ainda está ativo.

`ERR` ou `DF` tornam-se `BD_EIO`; espera finita esgotada vira `BD_ETIMEOUT`; bus ausente ou vazio é traduzido para `BD_ENODEV`.

## Estado do driver e ownership

`AtaPio` contém `io`, `ctrl`, `drive`, `sectors`, `poll_limit`, `bm` e `dma`. `ata_pio_configure` começa no primary master, atribui uma capacidade provisória, configura um limite de um milhão de iterações para polling e mantém DMA desabilitado até a descoberta PCI confirmar seu uso.

O caminho DMA adiciona estado global. `g_ide_irq` registra uma interrupção observada, `g_bm_io` guarda a base do Bus Master usada pelo handler, e duas alocações físicas persistentes mantêm bounce buffer e PRDT. Os registradores de comando também são estado compartilhado do controlador.

Não existe request object por operação, queue nem lock por controlador. O invariante prático é, portanto, execução com owner único. Calls simultâneas em CPUs diferentes poderiam sobrescrever o task file, reutilizar a mesma PRDT, alterar o bounce buffer, limpar a flag de interrupção de outro comando ou resetar o canal durante outra transferência. O caminho atual deve ser entendido como serializado, mesmo sem um lock explícito no driver.

## Descoberta e IDENTIFY

`ata_pio_identify` testa dois canais e dois drives por canal. São permitidas até oito tentativas. A partir da segunda, o código faz software reset nos dois control ports legados, restaura o estado de trabalho para primary master, espera `BSY` limpar, adiciona um delay e repete a matriz canal/drive.

Para cada candidato, `ata_try_identify`:

1. seleciona o drive;
2. espera o device deixar de estar busy;
3. zera sector count e registradores LBA;
4. emite opcode `0xec`, `IDENTIFY DEVICE`;
5. espera `DRQ`, com detecção de erro e timeout;
6. lê 256 palavras de 16 bits pelo data register.

O bit 9 da word 49 precisa indicar suporte a LBA. Sem isso, o candidato é rejeitado.

As words 60-61 produzem a capacidade inicial. Se o bit 10 da word 83 anuncia LBA48, o código também lê as words 100-103. Quando 102-103 são diferentes de zero, o disco é rejeitado como grande demais para o `sector_count` de 32 bits atual. Se a metade superior for zero e o valor baixo de 32 bits tiver pelo menos 2048 setores, esse valor substitui a capacidade de 60-61.

Isso **não** significa suporte completo a I/O LBA48. Descobrir capacidade e codificar comandos são problemas separados. `ata_program` ainda grava somente três bytes de LBA e quatro bits no DRIVE/HEAD; os opcodes permanecem `0x20`, `0x30`, `0xc8` e `0xca`. Assim, um device pode anunciar uma capacidade superior ao espaço realmente alcançável pelos comandos atuais. Essa diferença é uma fronteira de correção da implementação presente.

## Programação de comandos

`ata_select` escreve:

~~~text
0xe0 | (drive << 4) | ((lba >> 24) & 0x0f)
~~~

em DRIVE/HEAD. Isso seleciona modo LBA, master/slave e transporta os bits 24-27 do LBA. Em seguida, o driver lê o alternate-status port quatro vezes para produzir o atraso tradicional após a seleção.

`ata_program` escreve sector count, LBA0, LBA1, LBA2 e por último o opcode. Como sector count é um byte, o helper PIO limita um chunk explícito a no máximo 255 setores. O helper DMA trabalha com apenas 16 setores porque o bounce buffer fixo possui 8192 bytes.

## Polling e falhas limitadas

`ata_poll` evita espera infinita. Status `0xff` é interpretado como device ausente. Um bus que retorna zero repetidamente antes de `BSY` ter sido observado também é classificado como vazio depois de 256 amostras. Isso impede que um canal sem disco consuma todo o orçamento de polling.

Se `ERR` ou `DF` aparece, o resultado é `BD_EIO`. Caso contrário, a conclusão exige `BSY` limpo e, para comandos de dados, `DRQ` ativo. Esgotar `poll_limit` retorna `BD_ETIMEOUT`.

`ata_wait_not_busy` é um helper menor usado em reset e IDENTIFY. Ele lê o alternate-status port, reconhece `0xff` e usa a mesma ideia de limite finito. Essas esperas limitadas fazem parte da contenção de falhas: um device ausente ou travado pode atrasar o boot, mas não deve gerar intencionalmente um loop infinito nesses caminhos.

## Leitura PIO

`ata_read_chunk` programa `READ SECTORS` (`0x20`). Para cada setor, espera `DRQ` e executa exatamente 256 operações `inw` de 16 bits. Cada palavra é separada em dois bytes no buffer do caller.

Para `n` setores, a fase de payload executa `256n` leituras de porta e armazena `512n` bytes. O custo é linear no volume transferido, `O(n)` em setores, com a CPU movimentando diretamente cada palavra. Esse caminho não precisa de alocação dinâmica temporária.

## Escrita PIO e persistência

`ata_write_chunk` espelha a leitura usando `WRITE SECTORS` (`0x30`). Dois bytes do buffer são combinados em uma palavra de 16 bits e enviados por `outw` depois que o device anuncia `DRQ`.

Uma escrita de alto nível bem-sucedida é seguida por `ata_flush_raw`. O helper emite `CACHE FLUSH` (`0xe7`) e espera a conclusão. O callback `BlockDevice.flush` usa a mesma operação. Portanto, o backend ATA não trata flush como no-op: existe uma fronteira explícita de persistência, ainda dependente de o device físico ou virtual cumprir a semântica ATA correspondente.

## Descoberta de Bus Master IDE

DMA só é habilitado quando duas condições são verdadeiras. O bit 8 da word 49 de IDENTIFY precisa anunciar capacidade DMA, e `pci_find_ide` precisa localizar uma função PCI IDE.

A busca PCI atual é estreita: bus 0, slots 0-31 e functions 0-7. O candidato deve ter class/subclass `0x0101`. O ChrisOS ativa bits `0x0005` do PCI command para permitir I/O space e bus mastering, lê BAR4, exige que seja um I/O BAR, remove os bits de flags e usa a base resultante nos registradores Bus Master.

Quando isso funciona, o driver armazena a base, marca `dma = 1`, instala `ide_irq` em IRQ14, desmascara a linha no PIC e salva a base global usada pelo handler. Esse comportamento não é um sistema geral de roteamento PCI/IRQ e não deve ser extrapolado para qualquer controlador IDE ou topologia de plataforma.

## Modelo de memória DMA e PRDT

`ata_dma_acquire` aloca sob demanda uma região física contígua de 8192 bytes e uma página adicional para a PRDT. Ambos os endereços físicos precisam ser menores ou iguais a `0xffffffff`; caso contrário, as alocações são liberadas e a preparação DMA falha.

A restrição decorre do formato legado Bus Master IDE, cuja entrada PRDT usa base física de 32 bits. O CPU acessa essas páginas pelo mapeamento físico-virtual provido pelo boot, enquanto o controlador recebe os endereços físicos.

A PRDT atual contém uma única entrada efetiva:

~~~text
word 0: endereço físico do bounce buffer
word 1: tamanho em bytes | 0x80000000
~~~

O bit alto marca end-of-table. Com somente 8 KiB, uma operação DMA aceita no máximo 16 setores. É um design com bounce buffer, não scatter/gather zero-copy: em writes o payload é copiado do caller para a área DMA; em reads ele é copiado da área DMA para o caller depois da completion.

## Sequência de transferência DMA

`ata_dma_xfer` rejeita DMA se o modo estiver desabilitado, a base Bus Master for zero, count for zero ou houver mais de 16 setores. Em seguida prepara bounce buffer e PRDT.

Para write, o payload é copiado para o bounce buffer antes de armar o hardware. O driver para o engine, escreve o endereço da PRDT, limpa bits de status com `0x06`, escolhe a direção, zera `g_ide_irq`, programa o opcode ATA DMA e só então liga o bit start do Bus Master.

Os comandos usados são `READ DMA` (`0xc8`) e `WRITE DMA` (`0xca`). `ata_dma_wait` acompanha a conclusão; depois o engine é parado. Em read bem-sucedido, os bytes do bounce buffer são copiados para o destino do caller.

A cópia adicional reduz a vantagem de DMA para requests muito pequenos, mas oferece um alvo físico contíguo simples para um engine legado de 32 bits e evita expor diretamente memória arbitrária do caller ao controlador.

## Completion, IRQ e timeout

O handler de IRQ14 marca `g_ide_irq`. Quando existe base Bus Master, lê o status do controlador e escreve o valor de volta para reconhecer os bits de status.

`ata_dma_wait` não depende apenas da interrupção. Ele também faz polling do status Bus Master. Tanto `g_ide_irq` quanto o bit de completion `0x04` podem indicar progresso. O helper ainda exige que o drive deixe `BSY`; o bit de erro Bus Master `0x02` gera `BD_EIO`.

O loop possui teto fixo de 200000 iterações. A cada 64 iterações há uma leitura da porta `0x80` como pequeno delay. Esgotar o limite gera `BD_ETIMEOUT`.

A implementação deliberadamente não exige observar o bit de completion em zero antes de vê-lo em um. O comentário no source registra a razão: uma transferência muito rápida pode terminar antes do primeiro poll. Exigir a transição visível transformaria completions válidas em timeouts completos.

## Falha DMA e fallback PIO

Os callbacks de read/write tentam DMA primeiro. Qualquer resultado diferente de `BD_OK` chama `ata_dma_abort`: o engine Bus Master é parado quando existe, o canal recebe software reset e o código espera o device deixar de estar busy. O mesmo request é então repetido por PIO.

Essa política tem duas consequências úteis. Uma falha transitória do caminho DMA ainda pode terminar pelo mecanismo PIO mais simples, e o reset cria uma fronteira de ownership antes de reutilizar estado DMA compartilhado ou buffers. A operação DMA anterior não deve continuar acessando memória enquanto o fallback avança.

Há também um detalhe de implementação relevante: quando DMA não está configurado, `ata_dma_xfer` retorna `BD_ENODEV`, e o caminho de alto nível ainda executa abort/reset antes de cair para PIO. Esse é o comportamento literal atual, porém adiciona overhead desnecessário ao caso PIO-only e é um candidato plausível a refatoração futura.

O loop usa chunks DMA de até 16 setores. Se ocorrer fallback, pode escolher um chunk PIO de até 255 setores; depois avança LBA, count restante e ponteiro do payload.

## Modelo de erros e limites de recovery

As condições principais são normalizadas assim:

| Condição | Resultado |
|---|---|
| device ausente ou bus vazio | `BD_ENODEV` |
| espera de busy/completion esgotada | `BD_ETIMEOUT` |
| ATA ERR/DF ou erro Bus Master | `BD_EIO` |
| transferência concluída | `BD_OK` |

Erros de range normalmente não chegam ao driver porque `bd_read` e `bd_write` os rejeitam antes.

A recuperação atual é deliberadamente pequena: software reset seguido por retry em PIO. Não há decoding detalhado do ATA error register, SMART, política própria de bad sectors, classificação de retries por tipo de erro, hotplug lifecycle ou state machine completa de reinicialização do controlador.

## Limites de endereçamento

Vários limites se cruzam:

- `BlockDevice.sector_count` tem 32 bits;
- a codificação ATA atual usa LBA28;
- descriptors DMA usam endereços físicos de 32 bits;
- um request DMA aceita no máximo 16 setores;
- um comando PIO do helper aceita no máximo 255 setores;
- setor lógico é fixo em 512 bytes.

LBA28 alcança no máximo `2^28` setores. Com 512 bytes por setor isso equivale a 128 GiB. Como IDENTIFY pode hoje adotar uma capacidade LBA48 baixa de 32 bits superior a esse valor sem trocar para comandos extended, a fronteira significativa de endereçamento seguro dos comandos atuais continua sendo a faixa LBA28 de 128 GiB.

## Privilégio e safety

Programar ATA usa instruções privilegiadas de port I/O em x86 e pode armar hardware com acesso DMA. O código pertence ao domínio de privilégio do kernel; software em user mode só deve chegar ao armazenamento por interfaces superiores.

Propriedades atuais de safety incluem bounds check genérico de LBA, polling finito, verificação de endereços físicos das alocações DMA, reset antes do recovery PIO e flush explícito após writes. Isso reduz hangs e corrupção acidental, mas não constitui sandbox IOMMU. Uma PRDT incorreta ainda poderia direcionar um Bus Master legado para uma região física indevida.

## Trade-offs de desempenho

PIO tem setup simples, porém consome CPU em cada palavra de 16 bits. Bus Master DMA remove grande parte das instruções de data-port, mas o bounce buffer ainda exige uma cópia completa em writes e outra após reads. O controlador não executa múltiplos requests independentes em paralelo e a PRDT de uma entrada elimina scatter/gather útil.

Outros custos são transações DMA pequenas de 8 KiB, polling mesmo com IRQ14 habilitada e cache flush ao final de cada write de alto nível. O desenho atual prioriza determinismo, fallback e simplicidade de integração em vez de throughput máximo.

AHCI e NVMe usam modelos de filas diferentes e são documentados separadamente; as propriedades desses drivers não devem ser projetadas sobre este caminho IDE legado.

## Evidência de validação

O ChrisOS define o gate dedicado `test-qemu-ata`. Ele inicia QEMU com a imagem normal de disco conectada por IDE e exige, dentro de 40 segundos, markers seriais para a contagem configurada de CPUs, `root ata` e `cfs mounted`.

Isso é evidência end-to-end de que a topologia QEMU testada consegue descobrir um block device ATA como root e montar ChrisFS através dele. Não é certificação de compatibilidade ampla com hardware ATA físico.

Existe uma limitação adicional na evidência: `bdev_rw_tests` ignora o device selecionado como root para não executar um teste destrutivo sobre o filesystem ativo. Portanto, esse gate ATA não executa isoladamente o round trip de write/read/restore de um disco ATA não-root. A evidência explícita mais forte é discovery do root, mount e uso normal subsequente do filesystem.

## Limitações atuais

Nesta revisão, a implementação ATA não fornece:

- comandos de read/write LBA48;
- suporte a ATAPI packet devices;
- Native Command Queuing;
- múltiplos comandos em flight;
- PRDT scatter/gather com várias entradas;
- DMA acima de 4 GiB;
- setores lógicos de 4 KiB;
- descoberta completa da topologia PCI;
- roteamento dinâmico de interrupções para plataformas arbitrárias;
- hotplug;
- diagnóstico detalhado pelo ATA error register;
- locking por controlador para callers SMP;
- política separada de retry DMA antes do fallback PIO.

A interpretação correta é um caminho experimental robustecido de IDE legado para a storage stack atual do ChrisOS, e não uma implementação completa da família de padrões ATA.

## Fronteira de roadmap

Trabalho futuro plausível inclui comandos LBA48 explícitos, serialização por controlador, PRDT multi-entry, scatter/gather, separação mais clara entre operação PIO-only e recovery de DMA, descoberta de controladores mais geral e matrizes de validação em hardware físico. Esses itens são futuros e não devem ser descritos como presentes antes de existirem no source e nos testes.

## Mapa de source e nota de revisão

`kernel/fs/ata_pio.h` define `AtaPio` e a interface pública. `kernel/fs/ata_pio.c` implementa discovery, PIO, Bus Master DMA, timeouts, reset e adaptação para `BlockDevice`. `kernel/fs/block_device.h` define o contrato de setores normalizado. `kernel/fs/storage.c` integra ATA à descoberta de armazenamento e seleção do root. `kernel/metal/pci.c` implementa a descoberta estreita de Bus Master IDE usada pelo DMA. `scripts/qemu.mk` define o gate QEMU para ATA.

Todas as afirmações sobre implementação neste capítulo foram reconciliadas com ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
