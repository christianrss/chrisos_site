---
id: usb-storage
lang: pt-br
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/usb.h
  - kernel/fs/usb_msc.h
  - kernel/fs/usb_msc.c
  - kernel/fs/xhci.h
  - kernel/fs/xhci.c
  - kernel/fs/block_device.h
  - kernel/fs/bdev.h
  - kernel/fs/bdev.c
  - kernel/fs/storage.c
  - kernel/gfx/hwgate.h
  - kernel/gfx/hwgate.c
  - kernel/metal/pci.c
  - scripts/qemu.mk
symbols:
  - UsbMsc
  - UsbHid
  - usb_msc_probe
  - port_reset
  - control
  - bulk
  - scsi
  - usb_rw
  - usb_read
  - usb_write
  - run_qh
  - td_write
  - td_wait
  - xhci_hid_probe
  - hw_dma_alloc_low
  - bd_add_kind
depends_on:
  - block-storage
  - buses-mmio-dma
  - pci-pcie
  - physical-memory
related:
  - virtio-block
  - partitions-gpt
  - chrisfs
  - interrupts-smp
---

# USB mass storage e host controllers

## Escopo

O ChrisOS ainda não possui uma stack USB genérica. O caminho de armazenamento atual é uma implementação deliberadamente estreita construída sobre **UHCI + USB Mass Storage Bulk-Only Transport (BOT) + comandos SCSI de bloco**. Existe também uma implementação xHCI separada, porém atualmente limitada a dispositivos HID boot em polling e sem suporte a Mass Storage.

A arquitetura real, portanto, não é:

~~~text
USB core genérico
    -> qualquer host controller
    -> qualquer class driver
~~~

Ela é mais próxima de:

~~~text
enumeração e scheduling específicos de UHCI
    -> um device USB com bulk IN/OUT
    -> BOT
    -> SCSI READ(10) / WRITE(10)
    -> BlockDevice
~~~

O próprio `usb.h` registra essa fronteira: storage usa UHCI; EHCI ainda é futuro; xHCI é um caminho separado para HID.

Este capítulo documenta a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![Caminho USB storage do ChrisOS, de UHCI até BOT/SCSI e BlockDevice](../../assets/diagrams/usb-storage-path-pt-br.svg)

## Posição na stack de armazenamento

O disk USB entra na block layer comum:

~~~text
ChrisFS / GPT / descoberta de storage
        -> BlockDevice
        -> usb_read / usb_write
        -> usb_rw
        -> SCSI READ(10) / WRITE(10)
        -> USB BOT
        -> bulk OUT / bulk IN
        -> UHCI transfer descriptors
        -> USB mass-storage device
~~~

`storage_init` chama o probe de USB Mass Storage depois de ATA, AHCI, NVMe e VirtIO Block.

Um probe bem-sucedido registra:

~~~text
name = "usb"
kind = BD_USB
sector_size = 512
writable = 1
flush = 0
~~~

A seleção de root continua sendo responsabilidade da lógica genérica de storage.

## Realidade dos host controllers: UHCI para storage, xHCI para HID

Há dois caminhos USB separados no ChrisOS.

### UHCI para armazenamento

`usb_msc.c` procura PCI class code:

~~~text
0x0C0300
~~~

que representa um controlador USB com interface de programação UHCI.

Esse arquivo contém o caminho de storage, control transfers, BOT, SCSI e também um pequeno caminho HID para tablet.

### xHCI para HID

`xhci.c` procura:

~~~text
0x0C0330
~~~

e implementa xHCI separado para boot keyboard e mouse.

Ele possui command ring, event ring, endpoint configuration e TRBs, mas **não** oferece Mass Storage.

Logo, no ChrisOS atual, “USB storage” significa “storage sobre UHCI”, e não “storage sobre qualquer host controller USB disponível”.

## Descoberta PCI do UHCI

O probe percorre buses 0 a 7, devices 0 a 31 e functions 0 a 7.

Para uma função UHCI, lê o BAR4 no offset `0x20`.

Esse BAR precisa ser de I/O:

~~~text
bar & 1 != 0
~~~

A base de portas é:

~~~text
bar & ~3
~~~

O PCI command register recebe `| 5`, habilitando:

- I/O space;
- bus mastering.

Portanto, o driver depende do modelo clássico de registradores por port I/O do UHCI.

## Por que o DMA precisa estar abaixo de 4 GiB

Os ponteiros de schedule e transfer descriptors do UHCI são de 32 bits.

O ChrisOS chama:

~~~text
hw_dma_alloc_low(4)
~~~

Isso reserva quatro páginas contíguas, totalizando 16 KiB, por meio do allocator DMA32.

Diferentemente de NVMe ou VirtIO Block, esse caminho não pode simplesmente escrever partes low/high de um endereço físico de 64 bits.

A limitação de largura do DMA do hardware chega diretamente à política de alocação física do kernel.

## Arena DMA compartilhada de 16 KiB

A implementação usa regiões fixas dentro das quatro páginas:

| Offset | Uso |
|---:|---|
| 0x0000 | frame list com 1024 entradas |
| 0x1000 | queue head e transfer descriptors |
| 0x2000 | SETUP packet e payload de control transfer |
| 0x3000 | buffer de payload bulk |
| ~0x3400 | buffer do pequeno caminho HID UHCI |

A frame list ocupa exatamente 4096 bytes:

~~~text
1024 × 4 bytes
~~~

Cada entrada aponta inicialmente para o queue head em `page_phys + 4096`, com o tipo QH codificado no link.

Esse layout fixo simplifica o código, mas concentra enumeração, armazenamento e HID UHCI na mesma arena e reforça a necessidade de ownership serial.

## Halt e reset do UHCI

O driver pode parar o controller limpando Run/Stop e consultando o status até o HC entrar em estado halted.

`uhci_reset` executa host-controller reset e aguarda o bit de reset desaparecer.

As esperas são finitas.

`uhci_ack` grava 1s em USBSTS para limpar bits de status e evitar manter IRQ 11 pendente.

Mesmo assim, o fluxo normal continua orientado a polling, e não a interrupções.

## Transfer descriptors UHCI

`td_write` constrói um TD com:

- link pointer;
- status/active;
- token USB;
- endereço do data buffer.

Quando há outro TD depois dele, o driver seta o bit de depth-first no link.

O source explica o motivo: sem depth-first, o controlador terminava o SETUP TD e voltava para o queue head antes de concluir o status stage do control transfer.

Essa é uma consequência direta do schedule muito pequeno e reaproveitado do ChrisOS.

## Construção do token USB

A função `token` monta:

- PID;
- device address;
- endpoint;
- data toggle;
- maximum length.

Os PIDs usados no source são:

~~~text
0x2D  SETUP
0x69  IN
0xE1  OUT
~~~

Para zero-length packet, o UHCI usa a codificação especial `0x7FF`; para os demais casos, o campo recebe `len - 1`.

## Espera por completion de TD

`td_wait` faz polling do bit Active.

Se o TD termina com bits no error mask, retorna erro. Se permanece ativo além do limite, retorna timeout.

A função conta mudanças em FRNUM e mantém também um guard counter.

Há um detalhe específico do ambiente virtualizado: leituras periódicas da porta `0x80` provocam VM exit suficiente para o timer UHCI avançar em QEMU/KVM. O comentário do source afirma que um loop apenas com `pause` podia nunca completar.

Esse workaround é útil para a validação do projeto, mas não deve ser confundido com uma primitiva USB portátil.

## Execução via queue head

`run_qh` é síncrono:

1. para o UHCI;
2. configura o queue head;
3. limpa status;
4. programa a frame-list base;
5. inicia o controller;
6. espera o primeiro TD.

Todos os transfers reutilizam a mesma região de QH/TD.

Isso facilita inspeção e debugging, mas impede concorrência real.

## Control transfers

`control` monta o fluxo padrão:

~~~text
SETUP
DATA opcional
STATUS
~~~

O setup packet fica por volta do offset 8192.

Quando existe data stage, o ChrisOS usa um único TD para os dados.

Isso cria uma limitação importante: o código não fragmenta a etapa de dados de acordo com o maximum packet size de endpoint zero. O probe também não lê inicialmente o device descriptor para obter `bMaxPacketSize0`.

Descritores de configuração podem ser requisitados com até 128 bytes, mas o caminho atual não implementa packetização completa do EP0.

O cenário QEMU testado aceita o fluxo, mas isso não prova compatibilidade ampla com hardware físico.

## Reset de porta e addressing

O probe examina duas root ports do UHCI.

Para cada porta conectada:

1. aguarda connection;
2. ativa reset;
3. remove reset e habilita a porta;
4. envia `SET_ADDRESS` quando o device ainda está no endereço 0;
5. distribui endereços sequenciais começando em 1.

Não há enumeração de hubs.

Assim, devices atrás de hub externo não pertencem ao caminho suportado atual.

## Descoberta do configuration descriptor

Depois do endereço ser atribuído, o driver pede primeiro nove bytes do configuration descriptor.

Ele lê `wTotalLength`, limita a 128 bytes e então requisita o restante dentro desse teto.

O parser percorre interface descriptors e endpoint descriptors, mantendo:

- classe da interface mais recente;
- número da interface;
- endpoint bulk IN;
- endpoint bulk OUT;
- primeiro interrupt IN endpoint.

O código é suficiente para o cenário QEMU utilizado, mas não constrói uma representação genérica de configurations, interfaces e alternate settings.

## Limitação importante no matching de Mass Storage

O caminho atual assume que um device é candidato a storage quando encontra:

~~~text
bulk IN
e
bulk OUT
e
nenhum disk USB registrado ainda
~~~

Ele **não** exige:

~~~text
bInterfaceClass    = 0x08
bInterfaceSubClass = 0x06
bInterfaceProtocol = 0x50
~~~

A classe da interface é registrada, mas não é usada para bloquear o binding de MSC.

Isso significa que uma interface USB de outra função, desde que tenha bulk IN e bulk OUT, pode receber comandos BOT/SCSI incorretamente.

O device USB Storage do QEMU corresponde às expectativas, mas o matcher atual é amplo demais para hardware genérico.

## Propriedades de endpoint ignoradas

O endpoint descriptor contém, entre outros campos, maximum packet size.

O caminho MSC não preserva nem valida esse valor.

`bulk` fixa cada operação em no máximo:

~~~text
64 bytes
~~~

Esse tamanho corresponde ao máximo de bulk em full-speed e funciona no ambiente UHCI/QEMU validado, mas não é uma implementação orientada pelas propriedades reais do endpoint.

Também não há tratamento completo de short packets baseado no actual length retornado.

## SET_CONFIGURATION

Quando os endpoints foram identificados, o driver envia:

~~~text
SET_CONFIGURATION
~~~

usando o configuration value do descriptor, com fallback para 1.

Depois, os toggles bulk IN/OUT começam em DATA0.

Não há seleção explícita de alternate interface setting.

## Engine de bulk transfers

`bulk` divide uma fase BOT em pacotes de até 64 bytes.

Para cada pacote:

1. copia dados OUT para o buffer DMA quando necessário;
2. monta um TD;
3. executa o queue head;
4. alterna o data toggle;
5. copia dados IN para o caller quando necessário.

Para um payload de 4096 bytes:

~~~text
4096 / 64 = 64 pacotes USB
~~~

além do CBW e do CSW.

É um caminho simples de analisar, porém custoso em CPU e em reprogramação do controller.

## Bulk-Only Transport

`scsi` implementa três fases:

~~~text
Command Block Wrapper
data opcional
Command Status Wrapper
~~~

O CBW tem 31 bytes e contém a assinatura `USBC`.

O tag é fixo em 1.

A direção é preenchida como IN ou OUT, LUN fica zero e o SCSI command descriptor block é copiado para o CBW.

### Lacunas na validação do BOT

O CSW possui 13 bytes, mas o código verifica apenas:

~~~text
csw[12] == 0
~~~

Não são validados:

- assinatura do CSW;
- tag correspondente ao CBW;
- data residue;
- phase errors de forma estruturada.

Também não existe BOT reset recovery nem sequência de `CLEAR_FEATURE(ENDPOINT_HALT)`.

Status diferente de zero vira erro genérico de I/O.

## Conjunto de comandos SCSI

A implementação utiliza somente alguns comandos.

### READ CAPACITY(10)

No probe:

~~~text
opcode = 0x25
~~~

Os primeiros quatro bytes da resposta são tratados como last LBA:

~~~text
sector_count = last_lba + 1
~~~

### READ(10)

Reads:

~~~text
0x28
~~~

### WRITE(10)

Writes:

~~~text
0x2A
~~~

Não há `INQUIRY`, `TEST UNIT READY`, `REQUEST SENSE`, `MODE SENSE`, `SYNCHRONIZE CACHE` ou READ CAPACITY(16).

## Suposição de block size

READ CAPACITY(10) retorna também o logical block length nos bytes 4 a 7.

O ChrisOS ignora esses bytes e registra sempre:

~~~text
sector_size = 512
~~~

Isso é uma suposição real da implementação.

Um device com block size diferente de 512 bytes seria representado incorretamente.

A própria `BlockDevice` genérica atual também exige setores de 512 bytes.

## Limite de capacidade

READ CAPACITY(10) possui last LBA de 32 bits.

A block layer do ChrisOS também utiliza LBA e sector count de 32 bits.

Quando READ CAPACITY(10) retorna `0xFFFFFFFF`, o caminho padrão seria usar READ CAPACITY(16). O ChrisOS não faz isso.

O incremento de `0xFFFFFFFF` para `sector_count` volta a zero e o device acaba rejeitado pelo tamanho mínimo.

O limite prático continua, portanto, próximo de 2 TiB para setores de 512 bytes.

## Chunking de read e write

`usb_rw` limita um READ(10) ou WRITE(10) a:

~~~text
8 setores
~~~

Logo:

~~~text
8 × 512 = 4096 bytes
~~~

Requests maiores são quebrados sequencialmente.

O transfer length do CDB é preenchido em formato big-endian de 16 bits.

## Cópias pela CPU

Esse caminho não é zero-copy.

Em OUT, cada pacote de 64 bytes é empacotado para o buffer DMA compartilhado.

Em IN, cada pacote é copiado de volta do buffer para a memória do caller.

O custo de cópia cresce linearmente com o volume transferido.

## Modelo de concorrência

O driver usa estado global:

~~~text
g_usb
g_hid
g_ready
~~~

mais uma única arena DMA.

Não existe lock de storage.

Dois requests concorrentes poderiam disputar:

- TDs;
- queue head;
- bulk buffer;
- data toggles;
- estado run/halt do controller.

O invariante prático é um único transfer sequence UHCI ativo por vez.

O pequeno caminho de tablet UHCI também compartilha os mesmos recursos.

## Timeout e recovery

Timeout de TD pode retornar `-2`, convertido em:

~~~text
BD_ETIMEOUT
~~~

Falhas BOT/SCSI restantes viram:

~~~text
BD_EIO
~~~

Durante probe malsucedido, o código possui cleanup razoável: reseta UHCI, libera a arena DMA e limpa o estado global quando nenhum device útil foi retido.

Porém o recovery após timeout em I/O normal é incompleto. Não há uma sequência total que:

- faça BOT reset;
- limpe halt de endpoints;
- ressincronize toggles;
- execute REQUEST SENSE;
- prove que o controller não continuará acessando o buffer antigo.

Assim, timeout pode deixar o estado de protocolo ambíguo.

## Lifetime de recursos no probe

Comparado a alguns outros drivers iniciais, o caminho USB faz cleanup mais consistente quando um controller candidato não produz storage/HID utilizável.

Quando `keep` é verdadeiro, a arena e o controller permanecem deliberadamente associados ao device para I/O futuro.

Não há, entretanto, teardown para hot-unplug depois do registro.

## Persistência de writes

O `BlockDevice` USB é registrado com:

~~~text
flush = 0
~~~

Não há SCSI `SYNCHRONIZE CACHE`.

Como `bd_flush` considera callback ausente como sucesso, o sistema não oferece uma persistence barrier explícita para USB storage.

Conclusão de WRITE(10) significa apenas que o comando terminou com sucesso segundo o caminho BOT/SCSI atual.

## Writable flag

O device recebe:

~~~text
writable = 1
~~~

Não existe descoberta explícita de write-protect.

Uma mídia read-only pode ser apresentada como writable até o primeiro WRITE(10) falhar.

## HID dentro de usb_msc.c

`usb_msc.c` também contém suporte pequeno a tablet USB via UHCI.

Ele identifica interface class 3 e interrupt IN endpoint, configura o device e consulta relatórios curtos.

Esse suporte serve ao cenário QEMU, mas não representa uma stack HID genérica.

Também evidencia que o nome do arquivo `usb_msc.c` não descreve toda a responsabilidade atual: ali existe parte significativa do próprio host-controller backend UHCI.

## Fronteira arquitetural do xHCI

O caminho xHCI é estruturalmente diferente.

Ele possui:

- command ring;
- event ring;
- ERST;
- DCBAA;
- rings de endpoint zero;
- rings de interrupt endpoint;
- commands para slots/address/configuration;
- transfer events.

Ele encontra PCI class `0x0C0330`.

Apesar disso, sua API pública é explicitamente HID:

~~~text
xhci_hid_probe
xhci_hid_ready
xhci_hid_poll
~~~

O driver configura boot keyboard e mouse, não bulk storage.

Logo, adicionar xHCI ao armazenamento exige primeiro separar melhor “host controller” de “USB class driver”, em vez de apenas apontar o código MSC atual para `xhci.c`.

## Segurança e trust boundaries

O UHCI recebe endereços físicos de uma arena DMA32 do kernel.

Não existe domínio IOMMU dedicado.

Proteções existentes incluem:

- arena fixa de 16 KiB;
- alocação DMA32;
- offsets de buffers predeterminados;
- waits finitos;
- checks de range da block layer;
- chunk máximo conhecido.

Faltam isolamento por IOMMU, tracking mais forte de ownership, defesa completa contra descriptors USB malformados, hot-unplug e recovery pós-timeout robusto.

## Características de desempenho

O caminho atual prioriza clareza e funcionalidade.

Seus principais custos são:

- UHCI em vez de EHCI/xHCI para storage;
- halt/restart do controller para operações pequenas;
- pacotes bulk de 64 bytes;
- polling síncrono;
- cópias repetidas pela CPU;
- um request por vez;
- limite de oito setores por SCSI command;
- sem pipeline de comandos;
- sem completion assíncrona;
- sem scatter/gather.

Portanto, é adequado como implementação educacional e backend funcional em QEMU, não como stack USB de alto desempenho.

## Evidência de validação

`scripts/qemu.mk` possui o gate `test-qemu-usb`.

Ele cria uma imagem de 32 MiB e conecta:

~~~text
-device usb-storage,bus=usb-bus.0,port=1,drive=usbdisk
~~~

Também conecta um USB tablet na porta 2.

O gate exige:

~~~text
usb msc sectors=
bdev rw ok usb
~~~

`bdev_rw_tests` verifica o último setor do device USB writable e não-root:

1. lê o setor original;
2. escreve um pattern;
3. lê novamente;
4. compara os 512 bytes;
5. restaura os dados originais.

Esse gate exercita, em QEMU:

~~~text
descoberta PCI UHCI
-> reset/address da porta
-> configuration descriptor
-> bulk endpoints
-> SET_CONFIGURATION
-> READ CAPACITY(10)
-> BOT CBW/data/CSW
-> WRITE(10)
-> READ(10)
-> verificação da block layer
~~~

O gate separado `test-qemu-xhci` valida apenas o caminho xHCI HID com keyboard/mouse. Ele não prova Mass Storage sobre xHCI.

## Limitações atuais

Na revisão documentada, USB storage possui:

- somente UHCI;
- duas root ports;
- sem hubs;
- sem EHCI storage;
- sem xHCI storage;
- sem abstração genérica de host controller;
- sem device model USB genérico;
- um storage device registrado;
- somente LUN 0;
- matching amplo por bulk IN/OUT em vez de class/subclass/protocol de MSC;
- pacotes fixos de 64 bytes sem usar endpoint MPS;
- data stage de control transfer em um único TD;
- configuration descriptor limitado a 128 bytes;
- BOT tag fixo;
- validação de CSW reduzida ao status byte;
- sem BOT reset recovery;
- sem clear-halt recovery;
- sem REQUEST SENSE;
- sem TEST UNIT READY;
- sem INQUIRY;
- sem SYNCHRONIZE CACHE;
- sem READ CAPACITY(16);
- block length de READ CAPACITY ignorado;
- suposição de blocos de 512 bytes;
- capacidade/LBA de 32 bits;
- máximo de oito setores por READ/WRITE(10);
- polling;
- sem locking;
- sem lifecycle de hotplug após registro;
- validação centrada em QEMU.

## Fronteira de roadmap

Uma arquitetura mais completa deve separar USB core/class drivers dos host controllers, exigir matching correto de MSC, usar maximum packet size real dos endpoints, packetizar control transfers corretamente, implementar BOT reset recovery, validar signature/tag/residue do CSW, adicionar sense handling, READ CAPACITY(16), validação de block size, `SYNCHRONIZE CACHE`, hotplug e storage sobre xHCI.

EHCI ou xHCI storage deveriam reutilizar a mesma camada BOT/SCSI por uma API genérica de transfer, evitando duplicação por controller.

Esses recursos permanecem futuros até existirem no source e nos testes.

## Mapa de source e revisão

`kernel/fs/usb_msc.c` reúne hoje scheduling UHCI, enumeração USB, um pequeno caminho HID, BOT, SCSI e adaptação para `BlockDevice`. `kernel/fs/usb.h` documenta explicitamente que a arquitetura ainda não é genérica e separa UHCI MSC de xHCI HID. `kernel/fs/xhci.c` implementa o caminho HID independente. `kernel/gfx/hwgate.c` fornece DMA32. `kernel/fs/block_device.h`, `kernel/fs/bdev.h` e `kernel/fs/bdev.c` definem e registram o device. `kernel/fs/storage.c` integra USB à descoberta e aos testes genéricos. `scripts/qemu.mk` contém os gates específicos.

Todas as afirmações sobre comportamento atual neste capítulo foram reconciliadas com ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
