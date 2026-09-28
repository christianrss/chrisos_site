---
id: pci-pcie
lang: pt-br
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/pci.c
  - kernel/metal/pci.h
  - kernel/metal/acpi.c
  - kernel/gfx/hwgate.c
  - kernel/gfx/vgpu.c
  - kernel/fs/virtio_blk.c
  - kernel/fs/ahci.c
  - kernel/fs/nvme.c
  - kernel/fs/xhci.c
  - kernel/fs/usb_msc.c
  - kernel/gfx/ac97.c
  - kernel/net/virtio_net.c
  - SYS/DRV/VIRTIOGPU.CC
  - compiler/lang_pipeline.h
  - kernel/lang/clvm_sys.c
  - chrisvm/machine/machine.h
symbols:
  - pci_read
  - pci_write
  - pci_find_virtio_net
  - pci_find_ide
  - pci_find_ac97
  - hw_pci_write
  - hw_bar_map
  - ahci_probe
  - nvme_probe
  - virtio_blk_probe
  - vgpu_boot
  - acpi_probe
depends_on:
  - buses-mmio-dma
  - x86-64-memory-privilege
related:
  - acpi-platform
  - interrupts-smp
  - pic-apic-ioapic
  - virtio-block
  - virtio-gpu-transport
  - installation-real-hardware
---

# PCI e PCI Express

## Escopo

PCI define um modelo de hardware descobrível, não apenas um conector para placas. Uma função PCI possui espaço de configuração, identificadores, classe, registradores de comando/estado, recursos de endereço, capabilities e mecanismos de interrupção. PCI Express preserva esse modelo de software enquanto substitui o antigo barramento paralelo compartilhado por uma interconexão serial comutada e orientada a pacotes.

O ChrisOS já depende de PCI para armazenamento, rede, USB, áudio e gráficos. O kernel atual consegue acessar configuração PCI legada, identificar funções por vendor/device ou classe, habilitar decode e bus mastering, mapear BARs e percorrer listas de capabilities usadas pelo transporte PCI moderno do VirtIO.

A implementação ainda é deliberadamente incompleta. A tabela ACPI MCFG é detectada, porém não interpretada para criar acesso ECAM; offsets de configuração possuem somente oito bits; não há enumerador central ciente de topologia, travessia recursiva de bridges, núcleo MSI/MSI-X, alocador genérico de recursos ou root complex PCI no ChrisVM.

![Caminho de descoberta PCI e PCIe](../../assets/diagrams/pci-pcie-pt-br.svg)

## PCI versus PCI Express

PCI convencional utilizava barramento paralelo compartilhado. Dispositivos dividiam linhas elétricas de endereço, dados e controle, com arbitragem para selecionar o mestre atual.

PCI Express utiliza links seriais ponto a ponto. Switches encaminham pacotes entre portas, root complexes e endpoints.

As camadas inferiores mudaram radicalmente, mas o modelo de programação manteve:

- endereçamento bus/device/function;
- Vendor ID e Device ID;
- class/subclass/programming interface;
- espaço de configuração;
- BARs;
- registradores Command/Status;
- capabilities;
- configuração de interrupções.

É por isso que um controlador NVMe PCIe continua sendo descoberto como uma função PCI.

## Camadas de protocolo do PCIe

PCIe pode ser compreendido por três camadas principais.

| Camada | Responsabilidade |
|---|---|
| Transaction | requests/completions de memória, configuração, I/O e mensagens |
| Data Link | confiabilidade local do link, sequência, CRC e replay |
| Physical | lanes, sinalização, encoding e treinamento do link |

Quando o ChrisOS acessa um BAR, ele não constrói diretamente um pacote PCIe. O root complex converte a transação da CPU em um Transaction Layer Packet.

## Root complex, switches, bridges e endpoints

O root complex conecta CPU/memória ao domínio PCIe. Root ports iniciam links. Switches distribuem tráfego para portas downstream. Endpoints implementam dispositivos. Bridges fornecem a estrutura de roteamento visível pelo software entre domínios de bus number.

~~~text
CPU / memória
     |
Root Complex
     |
Root Port
     |
   Switch
   /   \
Porta  Porta
 |       |
NVMe    GPU
~~~

Um sistema operacional correto descobre uma topologia, não apenas uma lista plana.

## Endereçamento BDF

Uma função PCI convencional é selecionada por:

~~~text
Bus      8 bits  0..255
Device   5 bits  0..31
Function 3 bits  0..7
~~~

A tupla é normalmente chamada BDF.

~~~text
02:05.3
~~~

significa bus 2, device 5, function 3.

Um mesmo encapsulamento físico pode expor várias funções. Drivers vinculam-se a funções.

## Espaço de configuração

Cada função fornece registradores de configuração.

Campos importantes de um header compatível tipo 0 incluem:

| Offset | Significado |
|---:|---|
| 0x00 | Vendor ID e Device ID |
| 0x04 | Command e Status |
| 0x08 | Revision, Programming Interface, Subclass, Base Class |
| 0x0C | Header Type entre outros campos legados |
| 0x10..0x24 | BAR0..BAR5 |
| 0x2C | Subsystem Vendor/Subsystem ID |
| 0x34 | ponteiro da lista de capabilities |
| 0x3C | Interrupt Line e Interrupt Pin |

PCI convencional expõe 256 bytes por função. PCIe amplia para 4096 bytes mantendo os primeiros 256 bytes compatíveis.

Isso já revela um limite atual do ChrisOS: pci_read e pci_write recebem offset uint8_t e, portanto, não alcançam 0x100..0xFFF.

## Vendor ID e Device ID

No offset 0x00:

~~~text
bits 15:0   Vendor ID
bits 31:16  Device ID
~~~

Vendor ID 0xFFFF normalmente indica que nenhuma função respondeu.

O ChrisOS utiliza essa regra nos probes.

Dispositivos VirtIO modernos usam vendor 0x1AF4 com Device IDs específicos. Vendor/device identifica uma família concreta; class matching expressa um modelo de programação independente do fabricante.

## Class, Subclass e Programming Interface

O offset 0x08 contém:

~~~text
bits  7:0   Revision ID
bits 15:8   Programming Interface
bits 23:16  Subclass
bits 31:24  Base Class
~~~

Exemplos usados no ChrisOS:

| Tupla | Uso |
|---|---|
| 01:06 | caminho SATA/AHCI |
| 01:08 | memória não volátil/NVMe |
| 04:01 | áudio/AC97 |
| 0C:03:00 | USB UHCI |
| 0C:03:30 | USB xHCI |

Programming Interface importa quando uma subclass possui mais de um modelo de registradores.

Os probes atuais de AHCI e NVMe comparam principalmente class/subclass; o xHCI inclui Programming Interface.

## Header Type

O byte em 0x0E define o layout do header.

Os sete bits inferiores identificam:

- tipo 0: endpoint comum;
- tipo 1: bridge PCI-to-PCI;
- tipo 2: bridge CardBus.

O bit 7 na função 0 indica capacidade multifuncional.

Um enumerador genérico deveria sondar a função 0, ler Header Type e sondar funções 1..7 quando apropriado. Bridges tipo 1 devem levar a enumeração ao secondary bus.

O ChrisOS ainda não implementa esse algoritmo central.

## Configuration Mechanism #1 legado

pci_read e pci_write formam:

~~~text
0x80000000
| (bus << 16)
| (device << 11)
| (function << 8)
| (offset & 0xFC)
~~~

O endereço é escrito na porta 0xCF8. O dword é transferido pela 0xCFC.

Layout:

| Bits | Significado |
|---|---|
| 31 | enable |
| 23:16 | bus |
| 15:11 | device |
| 10:8 | function |
| 7:2 | registrador dword |
| 1:0 | zero |

Para BDF 02:05.3 e offset 0x14:

~~~text
0x80000000
| (2 << 16)
| (5 << 11)
| (3 << 8)
| 0x14
= 0x80022B14
~~~

O checker do capítulo reproduz esse valor.

## Corrida SMP em CF8/CFC

CF8/CFC é um mecanismo compartilhado de endereço + dados.

~~~text
CPU0: seleciona função A em CF8
CPU1: seleciona função B em CF8
CPU0: lê CFC
~~~

CPU0 pode receber o registrador selecionado por CPU1.

A operação completa de seleção e acesso precisa ser serializada quando múltiplos contextos podem acessar configuração PCI.

pci_read/pci_write atuais não possuem um lock global de configuração PCI. Isso se torna um limite real conforme PCI deixa de existir somente no boot sequencial.

## Por que 256 bytes não bastam para PCIe

Mechanism #1 alcança apenas os 256 bytes convencionais.

PCIe fornece 4 KiB por função. Extended capabilities ocupam 0x100..0xFFF.

Um kernel limitado a offsets de oito bits não consegue implementar genericamente recursos estendidos como Advanced Error Reporting e outras capabilities PCIe.

Em sistemas ACPI, o caminho moderno comum é ECAM descrito por MCFG.

## Geometria ECAM

Enhanced Configuration Access Mechanism mapeia configuração PCIe em memória.

Para uma alocação MCFG:

~~~text
endereço =
    ecam_base
  + ((bus - start_bus) << 20)
  + (device << 15)
  + (function << 12)
  + register
~~~

Os strides derivam do formato:

~~~text
uma function = 0x1000 bytes
8 functions  = 0x8000 bytes por device
32 devices   = 0x100000 bytes por bus
~~~

O registrador ocupa 12 bits e cada função recebe 4 KiB.

## ACPI MCFG no ChrisOS atual

acpi_probe percorre entradas da XSDT e reconhece assinaturas como APIC, MCFG e FACP.

Para MCFG, hoje apenas informa a presença da tabela.

Não interpreta registros de alocação, não mapeia janelas ECAM e não fornece backend ECAM a pci.c.

Portanto o estado correto é:

~~~text
detecção da assinatura MCFG: implementada
parsing das alocações MCFG: não implementado
acesso ECAM: não implementado
~~~

O capítulo acpi-platform aprofunda validação das tabelas e alocações.

## Segment groups

Um sistema pode possuir mais de um grupo de segmento PCI.

BDF isolado não é identidade global suficiente.

Uma representação escalável é:

~~~text
segment:bus:device.function
~~~

Um futuro PciAddress do ChrisOS deve carregar segment explicitamente, mesmo que a primeira versão aceite apenas segmento zero.

## Enumeração como travessia de topologia

Bridges PCI possuem campos Primary, Secondary e Subordinate Bus Number.

Algoritmo conceitual:

~~~text
enumerate_bus(bus):
    para device 0..31:
        sondar function 0
        se ausente:
            continuar

        visitar function 0

        se multifunction:
            sondar functions 1..7

visit function:
    registrar identidade
    interpretar header
    interpretar BARs
    interpretar capabilities

    se bridge tipo 1:
        enumerar secondary bus
~~~

Isso representa a topologia real em vez de um prefixo arbitrário de números de bus.

## Enumeração atual do ChrisOS

Hoje os drivers fazem buscas independentes.

Exemplos:

- pci_find_virtio_net, pci_find_ide e pci_find_ac97 pesquisam bus 0;
- AHCI, NVMe, virtio-blk e alguns caminhos USB pesquisam buses 0..7;
- VirtIO GPU possui outra busca;
- capabilities são interpretadas localmente pelos drivers.

Isso é adequado para bring-up, mas não para cobertura ampla de hardware real.

Aumentar o limite de 8 para 256 não resolveria segmentos, bridges, recursos, binding ou hot-plug.

## Registrador Command

Bits importantes:

| Bit | Significado |
|---:|---|
| 0 | I/O Space Enable |
| 1 | Memory Space Enable |
| 2 | Bus Master Enable |

O ChrisOS usa combinações como:

~~~text
0x0005 = I/O Space + Bus Master
0x0006 = Memory Space + Bus Master
~~~

AHCI, NVMe e VirtIO moderno precisam de MMIO e DMA, então habilitam memória e bus mastering.

Bus Master Enable é também uma fronteira de segurança, pois autoriza tráfego de memória iniciado pelo dispositivo.

## Lista padrão de capabilities

Em headers compatíveis, offset 0x34 aponta para uma lista encadeada.

Cada entrada começa com:

~~~text
byte 0 = Capability ID
byte 1 = ponteiro para próxima
~~~

Capabilities comuns incluem:

- Power Management;
- MSI;
- PCI Express;
- MSI-X;
- vendor-specific.

A lista termina quando next é zero.

Um parser genérico deve validar presença no Status, range, alinhamento e ciclos.

## Segurança do parser

Estruturas de configuração precisam ser tratadas como entrada limitada.

Uma lista malformada pode:

- apontar fora da região válida;
- formar ciclo;
- apontar indefinidamente para trás;
- violar alinhamento;
- anunciar estrutura curta demais.

Um walker seguro mantém conjunto de offsets visitados e limite máximo de passos.

O checker executável deste capítulo demonstra essas invariantes.

## Capabilities PCI do VirtIO

VirtIO 1.3 utiliza Capability ID vendor-specific 0x09.

cfg_type relevantes:

| cfg_type | Estrutura |
|---:|---|
| 1 | common configuration |
| 2 | notification configuration |
| 3 | ISR status |
| 4 | device-specific configuration |
| 5 | PCI configuration access |
| 8 | shared-memory region |

Cada estrutura aponta para BAR, offset e comprimento.

Assim, o layout moderno do dispositivo é descoberto em vez de codificado em offsets fixos.

## Walker atual do VirtIO

virtio-blk moderno, VirtIO GPU e o driver ChrisC de VirtIO GPU começam em 0x34 e extraem:

- Capability ID;
- next pointer;
- cfg_type;
- BAR;
- offset dentro do BAR;
- notification multiplier quando aplicável.

O BAR é mapeado por hw_bar_map.

Isso já constitui transporte real orientado por capabilities PCI.

## Notification multiplier

O endereço de notificação VirtIO é:

~~~text
notify_address =
notify_capability_base
+ queue_notify_off * notify_off_multiplier
~~~

O ChrisOS lê os dois fatores.

Multiplier incorreto pode notificar a fila errada mesmo com descritores corretos.

O checker valida essa aritmética.

## BARs

Base Address Registers descrevem recursos.

Um BAR pode representar:

- espaço de portas I/O;
- memória 32-bit;
- memória 64-bit.

Em BARs de memória, bits baixos codificam atributos.

~~~text
bit 0      = 0 para memória
bits 2:1   = tipo
bit 3      = prefetchable
bits 31:4  = endereço
~~~

Um BAR 64-bit usa o próximo dword para bits 63:32 e consome dois slots.

## Cálculo de tamanho de BAR

Uma máscara de BAR 32-bit convencional pode ser convertida por:

~~~text
mask = readback & 0xFFFFFFF0
size = (~mask + 1) & 0xFFFFFFFF
~~~

Exemplo:

~~~text
mask = 0xFFFFF000
size = 0x1000
~~~

A operação deve preservar a atribuição original.

Recursos 64-bit exigem tratar os dois dwords como uma unidade.

## hw_bar_map atual

hw_bar_map já:

- rejeita I/O BAR quando precisa de MMIO;
- combina base de BAR 64-bit;
- executa sondagem simplificada de tamanho;
- restaura o BAR;
- mapeia páginas pelo caminho MMIO dedicado;
- acompanha janelas limitadas.

Limites atuais:

- sizing 64-bit simplificado;
- número e tamanho finitos de janelas;
- sem unmap/reuso;
- sem alocação global/rebalance;
- dependência de recursos já atribuídos por firmware/emulador.

## Prefetchable não significa RAM comum

O atributo PCI prefetchable descreve semântica do recurso para o fabric/gerenciador.

Não significa que registradores arbitrários devam ser mapeados como write-back da CPU.

Framebuffers e registradores de controle possuem requisitos diferentes. A política de cache continua pertencendo a MMU/PAT/MTRR.

## Janelas de bridge

Um endpoint atrás de uma bridge só é alcançável se o recurso couber nas janelas encaminhadas pela bridge.

~~~text
BAR do endpoint
  dentro da janela da bridge filha
    dentro da bridge pai
      dentro do aperture do root complex
~~~

Isso forma uma hierarquia de recursos.

Um núcleo PCI futuro deve representar essa árvore.

## Atribuição de recursos

Firmware pode programar BARs antes da entrada do kernel.

Um sistema pequeno pode consumir essas atribuições.

Um alocador completo pode precisar:

- descobrir apertures do host bridge;
- calcular todos os tamanhos;
- alocar ranges sem sobreposição;
- configurar bridge windows;
- respeitar restrições 32-bit;
- separar prefetchable/non-prefetchable;
- preservar regiões reservadas.

O ChrisOS atual consome as atribuições existentes.

## PCI Express Capability

A capability PCI Express padrão expõe:

- tipo de device/port;
- Device Capabilities/Control/Status;
- Link Capabilities/Control/Status;
- informações de slot;
- dados específicos de root port.

O ChrisOS ainda não possui parser genérico dessa capability.

Para hardware real, relatar velocidade e largura negociadas seria útil antes de diagnosticar drivers de alto nível.

## Lanes e largura negociada

Uma lane PCIe é full-duplex.

Larguras comuns:

~~~text
x1 x2 x4 x8 x16
~~~

O tráfego é distribuído pelas lanes ativas.

A largura física do conector não garante a largura negociada. O software deve consultar Link Status.

## Gerações PCIe

Revisões posteriores aumentam transfer rate e alteram detalhes físicos.

Para software de sistemas:

- velocidade negociada pode ser inferior à máxima;
- largura multiplica capacidade;
- GT/s não é igual a bytes/s de aplicação;
- encoding e overhead importam.

PCIe 6.x introduziu operação PAM4/FLIT a 64 GT/s. PCIe 7.x dobra a taxa nominal para 128 GT/s preservando o modelo geral de configuração.

Na data desta revisão, a PCI-SIG lista PCI Express Base Specification Revision 7.1 como aprovada em 17/09/2026.

## TLPs

Transaction Layer Packets transportam:

- Memory Read;
- Memory Write;
- Configuration Read/Write;
- Completion;
- Messages.

Uma store MMIO da CPU vira transação em direção ao endpoint.

Uma leitura DMA iniciada pelo dispositivo vira Memory Read Request rumo à memória do sistema e recebe completion data.

Uma escrita DMA normalmente é Memory Write posted.

## Escritas posted

Uma escrita posted não exige Completion para a própria escrita.

Portanto:

~~~text
CPU aposentou store MMIO
não implica
endpoint já consumiu o comando
~~~

Readback/flush definido pelo dispositivo pode ser necessário quando o software precisa de garantia mais forte.

## Data Link e Physical Layer

Data Link fornece confiabilidade local do link por sequência, CRC e replay.

Physical Layer implementa sinalização, lanes e link training.

Essas camadas podem entregar a transação perfeitamente e ainda assim o comando do dispositivo falhar. O driver continua precisando verificar status.

O ChrisOS não possui hoje diagnóstico genérico de link training ou erros de link.

## Extended capabilities

Extended capabilities PCIe ocupam 0x100..0xFFF e utilizam formato de encadeamento diferente da lista convencional.

Um futuro core precisa distinguir:

~~~text
capabilities padrão:
região dos primeiros 256 bytes

extended capabilities:
região estendida PCIe
~~~

O backend atual com offset uint8_t não alcança a segunda.

## AER

Advanced Error Reporting é uma extended capability que reporta erros correctable, non-fatal e fatal com maior detalhamento.

AER é um exemplo concreto de por que ECAM importa para diagnóstico de hardware real.

O ChrisOS ainda não implementa AER.

## INTx

Interrupções tradicionais PCI utilizam semântica baseada em pinos INTx.

INTx é level-triggered e pode ser compartilhado.

O campo Interrupt Line em 0x3C não constitui sozinho uma solução moderna de roteamento; firmware e IOAPIC também participam.

O ChrisOS ainda usa informação de IRQ legada em caminhos como AC97 e VirtIO GPU.

## MSI

Message Signaled Interrupts codificam interrupção como uma escrita de memória gerada pelo dispositivo.

Vantagens incluem ausência de linha INTx compartilhada e melhor alocação de vetores.

MSI é configurado por capability PCI padrão.

O ChrisOS não possui subsistema MSI genérico.

## MSI-X

MSI-X usa tabela e Pending Bit Array localizados por recursos BAR.

Implementação correta exige:

- localizar capability;
- identificar BAR/offset da tabela e PBA;
- alocar vetores;
- programar endereço/dados;
- mascarar/desmascarar com ordem correta.

O ChrisOS ainda não implementa MSI-X.

O plano de hardware real coloca MSI/MSI-X depois do bring-up inicial baseado em polling.

## Qualidade de binding de drivers

ahci_probe atual identifica class/subclass 01:06 e assume o modelo AHCI em BAR5. Um matcher de produção deveria validar também Programming Interface.

nvme_probe identifica 01:08 e mapeia BAR0. Uma versão madura deve validar Programming Interface e requisitos do controlador.

O xHCI compara também o Programming Interface 0x30, aproximando-se do estilo que deveria ser padronizado por um registry central.

## VirtIO legado e moderno

O repositório contém:

- virtio-net legado usando I/O BAR;
- virtio-blk e virtio-gpu modernos usando capabilities vendor-specific e MMIO.

Isso demonstra:

~~~text
identidade vendor/device
não define sozinha o transporte
~~~

Capabilities e layout de recursos também fazem parte do binding.

## Teardown e lifetime

Uma função PCI pode continuar fazendo DMA ou gerando interrupções após o driver deixar a rotina local.

Teardown seguro pode exigir:

- parar filas;
- mascarar interrupções;
- esperar DMA quiescer;
- desabilitar bus mastering quando necessário;
- resetar;
- liberar vetores;
- liberar mappings DMA;
- desmontar BARs.

O ChrisOS atual trata a maior parte dos dispositivos como recursos de lifetime do boot.

## Hot-plug, SR-IOV e ACS

PCIe pode oferecer hot-plug, SR-IOV e Access Control Services.

Esses recursos introduzem topologia dinâmica, ownership por função e requisitos mais fortes de isolamento IOMMU/topologia.

O ChrisOS não os implementa atualmente.

Eles são relevantes para a arquitetura futura de ChrisHV e isolamento de hardware.

## Ownership ACPI _OSC

Em ACPI, _OSC pode negociar controle de serviços PCIe nativos entre firmware e sistema operacional.

A capacidade de ler configuração PCI não significa automaticamente que o OS possui controle de todos os serviços PCIe.

Uma futura integração ACPI/PCI deve associar _OSC a recursos como hot-plug nativo e tratamento avançado de erros.

## PCI como fronteira de segurança

Configuração PCI pode habilitar DMA, redirecionar decode de BAR e reprogramar interrupções.

Portanto, autoridade sobre PCI equivale a autoridade profunda sobre o sistema.

O ChrisOS já define CAP_PCI e CAP_DRIVER.

Um modelo robusto deve evoluir para permissões associadas a objetos:

~~~text
esta função PCI
estes BARs
este domínio/mask DMA
estes vetores
estes campos de configuração graváveis
~~~

Um booleano global de permissão PCI é amplo demais para isolamento forte.

## Driver VirtIO GPU em ChrisC

SYS/DRV/VIRTIOGPU.CC já exercita a fronteira de driver:

1. encontra o VirtIO GPU;
2. altera Command;
3. percorre capabilities;
4. mapeia BARs;
5. localiza common/notify;
6. aloca DMA;
7. programa virtqueue;
8. notifica o dispositivo.

Mover o driver para ChrisC não o isola automaticamente. O isolamento depende de limitar os recursos manipulados pelas syscalls.

## Estado atual do ChrisVM

ChrisVM possui buses genéricos de I/O e MMIO, RAM, framebuffer e poucos dispositivos.

Ainda não implementa:

- espaço de configuração PCI;
- portas root CF8/CFC;
- ECAM;
- bridges;
- alocação de BAR;
- MSI/MSI-X;
- capabilities PCI.

Por isso a descoberta PCI nativa do ChrisOS ainda não pode rodar integralmente no ChrisVM.

## Marco mínimo de PCI no ChrisVM

Uma primeira implementação útil precisa de:

1. root bus;
2. objetos de função;
3. 256 bytes de configuração por função;
4. campos de identidade/classe/header;
5. BARs declarados;
6. Command;
7. portas CF8/CFC;
8. roteamento BAR para buses I/O/MMIO existentes;
9. reset determinístico.

Isso já permitiria exercitar o backend PCI legado atual.

## Marco moderno de PCIe no ChrisVM

Depois:

1. configuração de 4 KiB;
2. ECAM;
3. exposição ACPI MCFG;
4. PCI Express Capability;
5. capabilities VirtIO;
6. MSI/MSI-X;
7. bridges/root ports;
8. extended capabilities;
9. integração IOMMU/DMA.

O emulador não precisa simular SerDes físico para implementar corretamente a interface visível ao software.

## Substituição progressiva do QEMU

Sequência prática:

~~~text
Fase 1
CF8/CFC
um root bus
BARs de endpoints
polling ou IRQ legado

Fase 2
VirtIO moderno
DMA
MSI/MSI-X
multifunction

Fase 3
ECAM + MCFG
bridges/root ports
extended capabilities

Fase 4
IOMMU
injeção de erros
hot-plug
serviços PCIe avançados
~~~

Cada fase aumenta a parcela do ChrisOS executável sem QEMU.

## Estrutura futura do core PCI

Um objeto central pode separar endereço, identidade, recursos e ownership:

~~~text
PciFunction
  address:
    segment, bus, device, function

  identity:
    vendor, device
    class, subclass, prog_if
    subsystem, revision

  header:
    type, multifunction

  resources:
    BAR[6], ROM

  capabilities:
    standard, extended

  interrupt:
    INTx, MSI, MSI-X

  topology:
    parent bridge, child bus

  owner:
    driver
~~~

Drivers deveriam receber esses objetos em vez de repetir aritmética BDF.

## Abstração do backend de configuração

Uma API futura:

~~~text
pci_cfg_read(address, offset, width)
pci_cfg_write(address, offset, width, value)
~~~

pode selecionar internamente:

~~~text
CF8/CFC legado
ou
ECAM
~~~

A mesma camada superior poderia ser testada com backend virtual do ChrisVM.

## Larguras de acesso

pci_read/pci_write atuais operam em dwords.

Uma API completa precisa de 8, 16 e 32 bits.

Muitos campos são sub-dword, e read-modify-write não é sempre equivalente a acesso estreito quando existem bits write-one-to-clear ou outros efeitos.

A largura deve fazer parte do contrato.

## Discovery, binding e initialization

Projeto maduro separa:

~~~text
PCI core:
descobrir topologia e recursos

driver registry:
selecionar driver

driver:
inicializar função atribuída
~~~

Hoje essas etapas estão misturadas nos probes.

Separá-las melhora diagnóstico, permissões, hot-plug e testes determinísticos.

## Checker reproduzível

scripts/check_pci_examples.py valida:

1. encoding e decoding CF8;
2. extração class/subclass/prog-if;
3. Header Type/multifunction;
4. strides ECAM;
5. cálculo de endereço ECAM;
6. extração de base BAR 32/64-bit;
7. sizing canônico de BAR;
8. walker de capabilities com range e detecção de ciclos;
9. multiplicação do offset de notificação VirtIO.

São verificações mecânicas/documentais, não uma suíte de conformidade PCIe.

## Matriz de implementação atual

| Recurso | Estado |
|---|---|
| configuração dword CF8/CFC | implementada |
| primeiros 256 bytes | implementados |
| serialização SMP de CF8/CFC | não implementada |
| configuração PCIe 4 KiB | não implementada |
| detecção da assinatura MCFG | implementada |
| parsing de alocações MCFG | não implementado |
| backend ECAM | não implementado |
| match vendor/device | implementado nos drivers |
| class matching | implementado nos drivers |
| grafo central de dispositivos | não implementado |
| recursão de bridges | não implementada |
| BAR mapping | parcial |
| capability walk padrão | implementado em VirtIO moderno |
| framework genérico de capabilities | não implementado |
| extended capabilities | não implementadas |
| INTx/IRQ legado | parcial |
| MSI | não implementado |
| MSI-X | não implementado |
| AER | não implementado |
| hot-plug | não implementado |
| SR-IOV | não implementado |
| integração IOMMU | não implementada |
| PCI root complex no ChrisVM | não implementado |

## Limite de validação

Este capítulo foi conciliado com ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

Na data da revisão, a PCI-SIG lista PCI Express Base Specification Revision 7.1 como aprovada em 17/09/2026. Os conceitos estáveis tratados aqui não dependem da geração física mais nova.

Execute:

~~~text
python scripts/check_pci_examples.py
~~~

O checker valida somente a aritmética e invariantes do capítulo.

## Gatilhos de revisão

Revisar quando:

- configuração ganhar locking ou suporte a larguras;
- MCFG/ECAM for implementado;
- surgir grafo central de funções PCI;
- bridges/resource allocation forem implementados;
- MSI/MSI-X surgir;
- política _OSC for implementada;
- integração IOMMU começar;
- ChrisVM ganhar root complex PCI.

## Referências primárias

- PCI-SIG, PCI Express Base Specification e índice de especificações.
- PCI-SIG, PCI Code and ID Assignment Specification.
- ACPI Specification, MCFG e interfaces de controle de host bridge PCI.
- Virtual I/O Device (VIRTIO) Version 1.3, PCI Transport.
- Documentação Intel 64/IA-32 para instruções x86 de I/O usadas no backend legado.
