---
id: uefi
lang: pt-br
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/start.c
  - kernel/metal/linker.ld
  - kernel/fs/install.c
  - iso_root/boot/limine/limine.conf
  - scripts/qemu.mk
  - makefile
symbols:
  - bootinfo_init
  - bootinfo_get
  - bootinfo_phys_to_virt
  - install_disk
  - install_auto
depends_on:
  - reset-firmware
related:
  - limine
  - boot-information
  - acpi-platform
  - partitions-gpt
  - elf-linking
  - installation-real-hardware
---

# UEFI

## Escopo

UEFI define a interface padronizada entre o firmware da plataforma e o software executado antes do sistema operacional.

É o ambiente no qual o bootloader do ChrisOS executa no perfil de hardware físico planejado.

O ChrisOS não chama atualmente Boot Services ou Runtime Services do UEFI diretamente. O Limine ocupa essa fronteira:

~~~text
firmware da plataforma
      |
interfaces UEFI
      |
imagem EFI do Limine
      |
protocolo de boot Limine
      |
kernel ELF64 do ChrisOS
~~~

Essa distinção é fundamental.

O kernel consome framebuffer, memory map, HHDM e informações multiprocessor por estruturas do Limine. Ele não recebe hoje um ponteiro para EFI System Table em bootinfo e não chama GetMemoryMap, ExitBootServices, GetVariable ou SetVariable.

![Handoff UEFI até ChrisOS](../../assets/diagrams/uefi-pt-br.svg)

Na data desta revisão, o UEFI Forum lista UEFI Specification 2.11 como a especificação UEFI corrente.

## O que UEFI padroniza

UEFI define um ambiente de execução e serviços para aplicações de firmware, OS loaders e drivers.

Conceitos principais incluem:

- imagens EFI;
- image handles;
- EFI System Table;
- Boot Services;
- Runtime Services;
- banco de handles/protocols;
- device paths;
- configuration tables;
- memory map;
- eventos e timers;
- protocolos de console;
- Graphics Output Protocol;
- block I/O;
- filesystem protocols;
- firmware variables;
- política de boot;
- mecanismos de autenticação e segurança de imagens.

UEFI é muito mais amplo que apenas "firmware consegue ler FAT".

## UEFI não é o sistema operacional

UEFI fornece serviços antes do OS assumir a máquina.

Um loader pode usar esses serviços e depois transferir o ownership ao kernel.

Após ExitBootServices, a maior parte dos Boot Services deixa de fazer parte do contrato.

O sistema operacional passa a controlar:

- alocação de memória;
- drivers;
- scheduling;
- interrupções;
- filesystems;
- processos;
- política de hardware.

No ChrisOS, essa transição é mediada pelo Limine.

## Entrada de uma imagem EFI

Uma aplicação UEFI é carregada como EFI image.

Sua entrada recebe conceitualmente:

~~~text
ImageHandle
SystemTable
~~~

ImageHandle identifica a imagem carregada no banco de handles do firmware.

SystemTable fornece acesso ao ambiente UEFI principal.

No boot atual, o Limine é essa aplicação EFI.

O kernel ChrisOS não usa a assinatura de entrada de uma aplicação EFI.

## EFI System Table

EFI System Table é uma das raízes centrais da interface UEFI.

Campos importantes incluem:

- table header;
- string do fornecedor do firmware;
- revisão;
- console input handle/protocol;
- console output handle/protocol;
- standard error;
- ponteiro Runtime Services;
- ponteiro Boot Services;
- quantidade de configuration tables;
- array ConfigurationTable.

Conceitualmente:

~~~text
EFI_SYSTEM_TABLE
  |
  +-- ConIn
  +-- ConOut
  +-- StdErr
  +-- BootServices
  +-- RuntimeServices
  +-- ConfigurationTable[]
~~~

Um loader deve respeitar o lifetime desses ponteiros.

## Cabeçalhos de tabelas

Tabelas de serviços UEFI utilizam EFI_TABLE_HEADER.

O cabeçalho contém campos como:

- signature;
- revision;
- header size;
- CRC32;
- reserved.

O CRC protege contra corrupção acidental.

Assim como checksums ACPI, isso não autentica criptograficamente o firmware.

O ChrisOS atual não interpreta essas tabelas diretamente.

## Handles

Um handle UEFI é um identificador opaco associado a um ou mais protocols.

O handle sozinho não define "tipo de dispositivo".

O significado surge dos protocols instalados nele.

Um mesmo handle pode, por exemplo, representar um dispositivo de bloco com Block I/O e também carregar um Device Path.

Outro handle pode representar uma imagem carregada.

Esse modelo evita uma hierarquia global fixa de structs de dispositivos.

## Protocols

Protocol é uma interface identificada por GUID.

Pode expor:

- dados;
- function pointers;
- capabilities;
- relações de driver.

Exemplos importantes:

- Loaded Image Protocol;
- Device Path Protocol;
- Graphics Output Protocol;
- Block I/O Protocol;
- Disk I/O Protocol;
- Simple File System Protocol;
- File Protocol;
- Simple Text Input/Output;
- RNG Protocol;
- TCG2 Protocol.

Boot Services fornecem mecanismos para localizar e abrir esses protocols.

## Banco de protocols

O firmware mantém um banco associando GUIDs de protocols a handles.

Clientes descobrem capabilities consultando esse banco.

Um loader maduro não deveria depender de "disco zero" ou "GPU zero" por endereço fixo.

Ele localiza handles que oferecem as interfaces necessárias.

## OpenProtocol

OpenProtocol é mais que uma simples busca de ponteiro.

A chamada também participa do modelo de relacionamento entre agentes, drivers e controllers.

Existem atributos para relações como:

- acesso por handle;
- acesso por driver;
- child controller;
- exclusividade.

Loaders simples usam apenas parte desse mecanismo, mas o modelo completo suporta o ambiente dinâmico de drivers do firmware.

## LocateProtocol e LocateHandleBuffer

Boot Services fornecem helpers de descoberta.

LocateProtocol retorna uma interface compatível quando uma única instância basta.

LocateHandleBuffer pode retornar conjuntos de handles segundo critérios.

Essas chamadas são úteis para localizar GOP, filesystem ou outros serviços sem hardcode.

O kernel ChrisOS não as chama; essa camada pertence ao Limine.

## Device paths

Device paths UEFI descrevem localização como sequência de nós tipados.

Podem representar:

- hardware;
- ACPI;
- messaging/bus;
- mídia;
- file path;
- nó final.

Device path não é um caminho POSIX.

Um file-path node pode ser apenas parte de uma descrição maior que identifica disco, partição e arquivo.

## Por que device paths importam

Variáveis de boot não guardam apenas uma string como C:\bootloader.

Uma load option UEFI pode conter um device path binário que descreve:

~~~text
controlador PCI
 -> storage
 -> partição
 -> filesystem
 -> arquivo EFI
~~~

Isso torna a política de boot independente de convenções de drive letters do sistema operacional.

## Loaded Image Protocol

Uma imagem EFI pode consultar o Loaded Image Protocol associado ao próprio ImageHandle.

Ele contém informações como:

- ParentHandle;
- SystemTable;
- DeviceHandle de origem;
- FilePath;
- ImageBase;
- ImageSize;
- memory type de código;
- memory type de dados;
- callback de unload.

Um bootloader pode assim descobrir sua própria origem.

O kernel ChrisOS não usa essa interface diretamente.

## Lifetime dos Boot Services

Boot Services existem até ExitBootServices ter sucesso.

Categorias incluem:

- eventos e task priority;
- memória;
- protocol handling;
- image services;
- serviços diversos de boot.

Após o handoff, o sistema operacional não deve continuar chamando os Boot Services normais.

Essa é uma das fronteiras de lifetime mais importantes do UEFI.

## AllocatePages

AllocatePages reserva páginas físicas a partir do memory map UEFI.

Pode solicitar:

- quaisquer páginas adequadas;
- páginas abaixo de um endereço máximo;
- um endereço específico.

Cada alocação pode alterar o memory map.

Isso importa imediatamente antes de ExitBootServices porque uma mudança pode invalidar o MapKey.

## AllocatePool

AllocatePool fornece buffers menores gerenciados pelo firmware.

É conveniente para estruturas temporárias do loader.

Assim como AllocatePages, pode modificar o estado do memory map.

Por isso o loader deve evitar alocações desnecessárias entre o último GetMemoryMap e ExitBootServices.

## Memory map UEFI

GetMemoryMap retorna um array de EFI memory descriptors.

Cada descriptor contém campos como:

- Type;
- PhysicalStart;
- VirtualStart;
- NumberOfPages;
- Attribute.

A chamada também devolve:

- tamanho total do buffer;
- MapKey;
- tamanho de cada descriptor;
- versão do descriptor.

O stride retornado precisa ser respeitado.

## DescriptorSize

O loop correto é conceitualmente:

~~~text
cursor = map_buffer

while cursor < map_buffer + map_size:
    descriptor = cursor
    processar descriptor
    cursor += descriptor_size
~~~

Usar sizeof(EFI_MEMORY_DESCRIPTOR) como stride fixo em vez de DescriptorSize retornado é um bug clássico de bootloader.

O checker deste capítulo valida essa aritmética.

## Tipos de memória UEFI

O memory map diferencia classes como:

- Reserved;
- Loader Code;
- Loader Data;
- Boot Services Code;
- Boot Services Data;
- Runtime Services Code;
- Runtime Services Data;
- Conventional Memory;
- Unusable Memory;
- ACPI Reclaim;
- ACPI NVS;
- MMIO;
- MMIO Port Space;
- categorias adicionais de memória persistente/unaccepted em revisões modernas.

As regras de ownership variam.

O kernel não pode marcar todas as regiões como livres após o handoff.

## Conventional Memory

EfiConventionalMemory representa memória de uso geral no ambiente UEFI.

Após o handoff, essas páginas normalmente podem entrar no allocator do OS, descontadas as reservas do loader/kernel.

O ChrisOS não recebe os descriptors EFI crus hoje.

Ele recebe o memory map já abstraído pelo Limine.

## Boot Services memory

Boot Services Code e Data pertencem ao firmware durante o boot.

Depois de ExitBootServices, essas regiões deixam de ser necessárias para os Boot Services e podem se tornar reutilizáveis conforme o contrato UEFI.

A decisão deve vir do tipo do descriptor, não de faixas de endereço presumidas.

## Runtime memory

Runtime Services Code/Data precisam ser preservados caso o OS queira continuar chamando Runtime Services.

Esses descriptors possuem semântica específica de runtime.

Mesmo um kernel que não use Runtime Services não deveria sobrescrever arbitrariamente essas regiões.

## Memória ACPI

UEFI possui tipos distintos para ACPI Reclaim e ACPI NVS.

ACPI Reclaim pode ser reaproveitada quando as tabelas necessárias forem consumidas e o OS souber que o armazenamento não é mais necessário.

ACPI NVS deve ser preservada segundo as semânticas de energia/resume aplicáveis.

Isso conecta o UEFI ao capítulo de ACPI.

## Padrão de duas chamadas de GetMemoryMap

É comum começar com uma chamada para descobrir o tamanho necessário.

Depois se aloca um buffer com margem e se chama novamente.

~~~text
GetMemoryMap(NULL)
 -> BUFFER_TOO_SMALL + required_size

alocar buffer com margem

GetMemoryMap(buffer)
 -> descriptors + MapKey
~~~

A margem é importante porque a própria alocação pode aumentar o map.

## MapKey

GetMemoryMap devolve um MapKey representando a geração atual do memory map.

ExitBootServices exige a key corrente.

Se o map mudar depois da chamada que produziu a key, ela fica obsoleta.

ExitBootServices pode então retornar EFI_INVALID_PARAMETER.

Isso é sincronização prevista pela especificação.

## Loop correto de ExitBootServices

O loader deve fazer algo conceitualmente equivalente a:

~~~text
repetir:
    obter memory map fresco
    guardar map_key

    evitar operações que alterem o map

    status = ExitBootServices(image_handle, map_key)

até sucesso
ou erro não recuperável
~~~

Se a key ficar inválida, deve-se obter o map novamente e repetir.

## Fronteira de transição

Antes de ExitBootServices:

~~~text
firmware Boot Services ainda controlam parte da máquina
~~~

Depois:

~~~text
OS / ambiente do loader controla o runtime normal
~~~

Runtime Services são a exceção explicitamente definida.

## ChrisOS e ExitBootServices

Nenhum caminho atual do ChrisOS chama GetMemoryMap ou ExitBootServices.

Isso é esperado.

O Limine é o bootloader UEFI e executa essa transição antes de entrar no kernel.

O ChrisOS já começa depois da fase de Boot Services.

## O que bootinfo não preserva

Depois que o Limine converte dados de firmware para seu protocolo, o ChrisOS não mantém automaticamente:

- EFI System Table;
- descriptors originais EFI;
- MapKey;
- handles;
- function pointers dos Boot Services;
- ImageHandle do Limine.

Esses detalhes pertencem à camada do loader, salvo se forem encaminhados explicitamente.

O bootinfo atual não os mantém.

## Configuration Tables

EFI System Table possui o array ConfigurationTable.

Cada entrada associa:

~~~text
VendorGuid
VendorTable pointer
~~~

Tabelas conhecidas podem apontar para:

- ACPI RSDP;
- SMBIOS;
- outras estruturas de firmware/plataforma.

Esse é o caminho UEFI nativo para descobrir metadados importantes sem varreduras legadas de memória.

## Relação UEFI e ACPI no ChrisOS

O capítulo anterior mostrou que o ChrisOS ainda procura RSDP na região BIOS legada.

O caminho UEFI correto é:

~~~text
EFI System Table
 -> GUID ACPI
 -> RSDP
 -> resposta do bootloader
 -> bootinfo ChrisOS
~~~

Como o kernel não recebe SystemTable diretamente, o Limine deveria encaminhar RSDP por seu protocolo.

O bootinfo atual ainda não solicita/armazena essa informação.

## SMBIOS

SMBIOS também costuma ser descoberto por configuration tables UEFI.

Pode descrever:

- fabricante;
- produto;
- placa;
- firmware;
- módulos de memória;
- identificação do sistema.

O plano de hardware real menciona SMBIOS como informação opcional.

Ainda não há parser geral de SMBIOS no kernel.

## Graphics Output Protocol

Graphics Output Protocol fornece interface gráfica do firmware.

Ele expõe:

- modos suportados;
- modo atual;
- framebuffer base;
- framebuffer size;
- pixel format;
- bit masks;
- resolução;
- PixelsPerScanLine.

Uma aplicação UEFI pode consultar e selecionar modo antes do handoff.

## PixelsPerScanLine

PixelsPerScanLine é especialmente importante.

O stride pode ser maior que a largura visível.

~~~text
pitch_bytes
pode ser maior que
width * bytes_per_pixel
~~~

O ChrisOS consome o pitch real fornecido pelo Limine.

O plano de hardware exige testar resoluções e pitches diferentes.

## Pixel format

GOP pode usar formatos predefinidos ou máscaras explícitas.

Assumir um único ARGB/XRGB universal pode produzir cores incorretas.

Limine abstrai os metadados do framebuffer, mas o kernel ainda deve respeitar o formato entregue.

O caminho gráfico atual depende fortemente de framebuffer 32-bpp.

## GOP não é aceleração de GPU

GOP fornece framebuffer pré-OS.

Não é um driver completo da GPU.

Ele não oferece necessariamente:

- command submission;
- VRAM manager;
- shaders;
- aceleração 3D;
- display-engine power management.

Isso explica por que GOP é adequado como display do perfil de hardware 1 do ChrisOS.

## Block I/O Protocol

EFI_BLOCK_IO_PROTOCOL oferece acesso em blocos.

A estrutura de mídia informa propriedades como:

- media present;
- removable;
- media ID;
- block size;
- last block;
- alinhamento.

O protocol fornece leitura, escrita e flush de blocos.

Depois do boot, o ChrisOS usa seus próprios drivers de armazenamento.

## Disk I/O Protocol

Disk I/O fornece acesso orientado a bytes sobre dispositivos de disco.

Pode facilitar operações não alinhadas a bloco.

Loaders podem utilizar filesystem protocol, Block I/O ou Disk I/O conforme sua arquitetura.

O kernel ChrisOS não depende desses protocols após o handoff.

## Descoberta de partições

UEFI entende esquemas como GPT.

A EFI System Partition utiliza o GUID:

~~~text
C12A7328-F81F-11D2-BA4B-00A0C93EC93B
~~~

install.c atual grava esse GUID na primeira entrada GPT.

O checker reconstrói o GUID a partir dos bytes presentes no source.

## Simple File System Protocol

EFI_SIMPLE_FILE_SYSTEM_PROTOCOL representa um volume de filesystem acessível pelo firmware.

OpenVolume retorna o EFI_FILE_PROTOCOL da raiz.

O loader pode navegar arquivos e diretórios.

Essa é a abstração UEFI para ler arquivos do volume FAT.

O ChrisOS não chama essa interface diretamente.

## EFI File Protocol

EFI_FILE_PROTOCOL oferece operações como:

- Open;
- Close;
- Read;
- Write;
- GetPosition;
- SetPosition;
- GetInfo;
- SetInfo;
- Flush.

Paths UEFI usam convenções do firmware e strings Unicode.

Isso não é a API ChrisFS.

## Formato de filesystem EFI

UEFI define um perfil específico de FAT.

A especificação UEFI 2.11 descreve FAT32 para uma system partition e FAT12/FAT16 para mídia removível, com suporte do firmware às variantes segundo as regras do EFI filesystem.

Para uma ESP de disco rígido, o alvo do projeto deve ser uma system partition FAT32 válida.

## Divergência importante no instalador atual

O plano de hardware real declara:

~~~text
GPT + FAT32 ESP + ChrisFS
~~~

porém install.c atual escreve um filesystem no estilo FAT16:

- BPB contém a string FAT16;
- entries da FAT são uint16_t;
- root directory é uma área fixa;
- cluster chains usam valores FAT16.

Ao mesmo tempo, a partição GPT recebe o GUID de EFI System Partition.

Portanto o ESP atual do disco instalado **ainda não corresponde ao alvo FAT32 declarado pelo projeto**.

Ele pode funcionar em firmware/emulador permissivo, mas não deve ser descrito como ESP hard-disk UEFI plenamente conforme até que o writer seja corrigido e testado.

## Por que isso importa no hardware físico

Firmware varia em tolerância.

OVMF aceitar um layout não prova que firmwares físicos diferentes aceitarão o mesmo disco.

O gate físico deve exigir:

- ESP FAT32;
- BPB/FSInfo/FAT32 corretos;
- GPT ESP type GUID;
- fallback path;
- segundo boot sem mídia de instalação.

Essa é uma lacuna concreta encontrada durante a reconciliação deste capítulo.

## Nuance de FAT em mídia removível

UEFI permite FAT12, FAT16 ou FAT32 em mídia removível segundo as regras do EFI filesystem.

Isso não transforma automaticamente uma ESP FAT16 em disco rígido no alvo FAT32 do projeto.

É necessário distinguir classe da mídia e system partition.

## Layout de diretórios ESP

Para fallback x86-64:

~~~text
\EFI\BOOT\BOOTX64.EFI
~~~

é o executável EFI padrão.

O instalador atual cria:

~~~text
EFI/
  BOOT/
    BOOTX64.EFI
~~~

e também grava kernel/configuração em seu layout de ESP.

## Writer ESP atual

install.c escreve diretamente as estruturas do filesystem.

Isso é esperado: a instalação ocorre depois que o ChrisOS já está rodando e controlando seus block devices.

O instalador constrói:

- GPT;
- ESP;
- diretórios;
- BOOTX64.EFI;
- kernel ELF;
- configuração Limine;
- partição ChrisFS.

É um formatter do sistema operacional, não uma chamada a Boot Services.

## Firmware variables

UEFI Runtime Services fornecem armazenamento persistente de variables.

Uma variável é identificada por:

~~~text
nome Unicode
+
Vendor GUID
~~~

Attributes podem marcar:

- nonvolatile;
- acesso durante Boot Services;
- acesso durante Runtime Services;
- requisitos de escrita autenticada.

## Variáveis padrão de boot

UEFI Boot Manager utiliza variables como:

- BootOrder;
- BootNext;
- BootCurrent;
- Timeout;
- Boot####.

Uma Boot#### contém EFI_LOAD_OPTION com:

- attributes;
- description;
- device path;
- optional data.

BootOrder guarda uma sequência de identificadores ####.

## ChrisOS não cria Boot#### hoje

O instalador atual usa deliberadamente o fallback path.

A documentação do repositório registra que não cria uma entrada NVRAM Boot####.

O estado correto é:

~~~text
fallback EFI loader instalado: implementado
registro NVRAM de boot: não implementado
~~~

## Benefício do fallback

Fallback reduz complexidade do instalador e evita dependência de escrita NVRAM.

Também evita inicialmente:

- falha de SetVariable;
- comportamento específico do Boot Manager;
- entradas Boot#### obsoletas;
- limites de NVRAM.

No futuro, Boot#### pode melhorar a integração mantendo fallback como recuperação.

## BootNext

BootNext seleciona uma opção de boot uma única vez.

É útil em instaladores e atualização de firmware.

O ChrisOS não manipula BootNext atualmente.

## Runtime variable services

GetVariable, SetVariable, GetNextVariableName e QueryVariableInfo são Runtime Services.

Para gerenciar BootOrder após o boot, o kernel teria de preservar e chamar o ambiente runtime do firmware corretamente.

Isso não é equivalente a gravar um arquivo na ESP.

## ABI UEFI em x86-64

UEFI define um calling convention x64 representado em C por EFIAPI.

Esse ABI não é o mesmo ABI System V AMD64 usado pelo build normal do kernel ChrisOS.

Chamar ponteiros UEFI diretamente a partir de C SysV exigiria wrappers ou atributos de compilador apropriados.

Runtime Services são portanto um subsistema real, não apenas "guardar um ponteiro".

## System V versus ABI UEFI

O kernel ChrisOS atual segue System V AMD64.

Os primeiros argumentos inteiros em SysV são conceitualmente:

~~~text
RDI RSI RDX RCX R8 R9
~~~

O ABI x64 do UEFI possui regras diferentes para registradores e stack.

Ambos executam x86-64, mas isso não torna os function calls binariamente compatíveis.

## SetVirtualAddressMap

Runtime Services podem continuar após o kernel instalar seu próprio espaço virtual.

UEFI define SetVirtualAddressMap para comunicar os virtual addresses das regiões runtime.

É uma transição delicada de lifetime.

O ChrisOS atual evita essa complexidade porque não usa Runtime Services.

## ConvertPointer

ConvertPointer auxilia na conversão de ponteiros internos após a mudança para endereçamento virtual de runtime.

Ele pertence a essa mesma transição.

Uma implementação parcial sem modelo de runtime completo seria inadequada.

## Protocolos de console

SystemTable expõe console input/output.

Simple Text Output permite imprimir texto antes do console nativo do OS.

Simple Text Input fornece entrada básica via firmware.

Bootloaders usam essas interfaces.

O ChrisOS, após entry, utiliza sua própria serial, framebuffer e input stack.

## Eventos UEFI

Boot Services oferecem eventos, callbacks e timers.

Drivers e aplicações EFI podem coordenar ações assíncronas.

Esses eventos não são primitives permanentes do kernel depois de ExitBootServices.

ChrisOS possui seus próprios timers, interrupções e jobs.

## LoadImage

LoadImage pede ao firmware que carregue uma imagem UEFI.

A origem pode vir de device path ou buffer.

O firmware valida o formato de executável esperado.

É assim que Boot Manager ou outra aplicação EFI pode carregar uma nova aplicação EFI.

O kernel ELF do ChrisOS não é uma aplicação UEFI PE/COFF comum.

## StartImage

StartImage transfere controle para a imagem EFI carregada.

A imagem filha recebe seu ImageHandle e SystemTable.

O Limine, carregado como aplicação EFI, participa desse modelo.

kstart não participa diretamente.

## PE32+ em x86-64

Aplicações UEFI x86-64 utilizam PE32+ para a arquitetura x64.

O nome de fallback reflete a arquitetura:

~~~text
BOOTX64.EFI
~~~

Outras arquiteturas usam outros nomes padronizados.

## Autenticação de imagens

Quando Secure Boot está ativo, firmware pode autenticar imagens antes da execução.

A política pode envolver:

- Platform Key;
- Key Exchange Keys;
- banco de assinaturas permitidas;
- banco de revogação;
- updates autenticados de variables.

A presença de BOOTX64.EFI por si só não indica Secure Boot.

## Variables de Secure Boot

Variables comuns incluem:

- PK;
- KEK;
- db;
- dbx;
- SecureBoot;
- SetupMode.

Uma integração completa exigiria assinatura e políticas de enrollment.

O ChrisOS atualmente mantém implementação custom de Secure Boot fora do escopo.

## Limine e Secure Boot

Usar Limine não significa automaticamente que Secure Boot está configurado.

A aceitação da imagem depende de assinatura, chaves e política do firmware.

A documentação não deve marcar Secure Boot como implementado apenas por utilizar UEFI.

## TCG2 e measured boot

UEFI possui interfaces como TCG2 para ambientes com TPM e measured boot.

Measured boot registra eventos/measurements para attestation.

O ChrisOS ainda não integra TCG2.

É uma área futura de pesquisa em segurança.

## Watchdog UEFI

Boot Services incluem watchdog.

Firmware pode resetar uma aplicação de boot que fique travada.

O loader controla isso durante a fase de boot.

Depois do handoff, o OS precisa usar seus próprios mecanismos.

O ChrisOS não controla o watchdog UEFI diretamente.

## Serviços de tempo

Runtime Services incluem operações de relógio.

Isso é distinto do timer monotônico usado pelo scheduler/kernel.

Um OS pode usar RTC ou outros timers nativos.

O ChrisOS não utiliza Runtime Services para timekeeping atualmente.

## ResetSystem

Runtime Services inclui ResetSystem.

Ele pode solicitar reset ou shutdown.

O ChrisOS atual não roteia reboot por uma camada genérica de UEFI Runtime Services.

O capítulo de ACPI também mostrou que reset ACPI é outra possibilidade.

## Capsule update

UEFI Runtime Services podem suportar capsule updates para firmware.

Isso está muito além do escopo atual do boot ChrisOS.

Ter UEFI não obriga o kernel a implementar atualização de firmware.

## Fronteira de segurança de firmware runtime

Chamar código de firmware após o OS assumir a máquina é uma fronteira de confiança profunda.

Runtime firmware pode depender de:

- regiões de memória preservadas;
- mappings específicos;
- calling convention;
- sincronização;
- detalhes da plataforma.

Manter a integração pequena e isolada é desejável.

A ausência atual de Runtime Services simplifica o ChrisOS.

## Fronteira de confiança do bootloader

Limine também executa com grande autoridade.

Ele determina:

- carregamento do kernel;
- mappings no entry;
- boot information;
- framebuffer;
- handoff de CPUs.

O ChrisOS valida partes das respostas, mas confia no loader para construir um ambiente coerente.

Isso é normal em protocolos de boot.

## Fronteira atual no código-fonte

Buscas no source revisado não encontram implementação nativa de:

- EFI_SYSTEM_TABLE;
- GetMemoryMap;
- ExitBootServices;
- manipulação de BootOrder.

Isso é coerente com:

~~~text
detalhes UEFI
    pertencem ao Limine

ChrisOS
    consome o protocolo Limine
~~~

## Installer versus bootloader

O instalador executa depois que o ChrisOS já bootou.

Ele escreve artefatos que o firmware encontrará no próximo boot.

Precisa conhecer:

- GPT;
- GUID da ESP;
- filesystem EFI;
- fallback filename;
- localização da configuração Limine.

Não precisa chamar Boot Services durante a formatação do disco.

## Estado atual do boot instalado

A documentação do repositório separa:

- criação da imagem de instalação: testada;
- boot do disco instalado sob OVMF sem ISO: ainda não provado em gate dedicado;
- boot em máquina UEFI física: não provado.

Um self-test de bytes da ESP não substitui o firmware realmente bootando o disco.

## OVMF

OVMF é uma implementação UEFI utilizada com QEMU.

O gate de disco instalado deve iniciar QEMU/OVMF somente com o disco gerado, removendo a mídia de instalação.

Esse teste valida muito mais da cadeia real.

O plano já prevê esse gate, mas ele ainda não é resultado medido.

## Aceitação no QEMU não garante hardware físico

Firmwares diferem em rigor.

Algo aceito em OVMF pode falhar em firmware físico.

O instalador precisa mirar a especificação, não apenas o comportamento mais permissivo observado.

Isso é particularmente importante para o atual mismatch FAT16/FAT32.

## Conversão necessária para FAT32

Antes de declarar ESP hard-disk alinhada ao perfil 1, install.c deve evoluir para FAT32 correto.

Isso envolve:

- BPB FAT32;
- entries FAT de 32 bits;
- root directory em cluster chain;
- FSInfo quando aplicável;
- backup boot sector;
- regras de cluster count;
- identificação FAT32;
- long filenames robustos;
- cálculo de capacidade.

Os detalhes de implementação pertencem ao capítulo de partições/instalação; o requisito UEFI é registrado aqui.

## Device path para Boot#### futuro

Se o ChrisOS criar Boot#### no futuro, precisará montar um EFI device path correto para o loader instalado.

Não basta salvar uma string de caminho.

A load option precisa codificar partição/dispositivo e o file path segundo as estruturas UEFI.

Esse é um passo considerável além do fallback atual.

## GUID da ESP

O instalador já usa os bytes correspondentes ao GUID:

~~~text
C12A7328-F81F-11D2-BA4B-00A0C93EC93B
~~~

O checker verifica essa reconstrução.

Isso mostra que a camada GPT já segue uma parte importante do modelo UEFI, mesmo que o filesystem ainda precise ser corrigido.

## Proveniência do boot

UEFI pode encontrar múltiplos loaders e dispositivos.

O kernel precisa imprimir identidade própria para provar qual artefato executou.

O plano de hardware prevê:

~~~text
ChrisOS <version>
Build: <id>
Compiler: <toolchain>
Kernel SHA256: <hash>
~~~

Isso é essencial para validar fallback, Boot#### e self-hosting.

## Handoff futuro de dados UEFI

Mantendo Limine, ainda é possível encaminhar mais informações do firmware.

Candidatos úteis:

- ACPI RSDP;
- SMBIOS;
- EFI System Table apenas se Runtime Services forem intencionalmente suportados;
- metadados adicionais que não sejam já cobertos pela abstração Limine.

O kernel não deveria conservar ponteiros de firmware apenas porque existem.

Cada interface aumenta o ABI e a superfície de confiança.

## Por que manter Limine é útil

Limine evita que o ChrisOS precise implementar imediatamente:

- loader ELF UEFI;
- higher-half boot mapping;
- framebuffer discovery;
- HHDM;
- memory map handoff;
- multiprocessor handoff.

Isso mantém o kernel concentrado em arquitetura de sistema operacional.

O plano atual do projeto é manter Limine.

## Se o ChrisOS criar seu próprio loader

Substituir Limine exigiria uma aplicação EFI separada.

Ela precisaria ao menos de:

- entry EFI e ABI;
- SystemTable;
- filesystem/device discovery;
- parser ELF;
- alocação de memória;
- page tables;
- seleção de framebuffer;
- captura do memory map;
- retry de ExitBootServices;
- bootinfo próprio;
- salto ao kernel higher-half.

É um projeto independente de porte significativo.

## Relação com ChrisVM

ChrisVM atualmente pula UEFI completamente.

Um modo de fidelidade de firmware exigiria hardware virtual suficiente para executar firmware UEFI:

- CPU desde reset;
- chipset;
- flash;
- PCI;
- timers;
- storage;
- display;
- ACPI;
- mídia bootável.

Isso é muito maior que o caminho de direct kernel boot.

## Direct kernel mode continua útil

Para desenvolvimento do kernel, ChrisVM pode primeiro reproduzir um handoff equivalente ao Limine:

- ELF higher-half;
- mappings;
- bootinfo;
- framebuffer;
- memory map;
- topologia de CPUs.

UEFI real pode ser um nível posterior de fidelidade.

## Checker reproduzível

scripts/check_uefi_examples.py valida:

1. reconstrução do GUID da ESP;
2. fallback filename x86-64;
3. aritmética de page counts;
4. iteração por descriptor stride;
5. modelo de freshness do MapKey;
6. GUID ESP usado pelo instalador;
7. marcador FAT16 e estado FAT de 16 bits do writer atual;
8. caminho EFI/BOOT/BOOTX64.EFI;
9. protocol/path do Limine;
10. ausência de API UEFI nativa no kernel atual.

Os testes não executam firmware.

## Matriz da implementação atual

| Capability | Estado |
|---|---|
| boot via imagem EFI do Limine | arquitetura atual / caminho QEMU |
| EFI System Table consumida pelo kernel | não implementado |
| Boot Services chamados pelo kernel | não implementado |
| Runtime Services chamados pelo kernel | não implementado |
| GetMemoryMap no kernel | não implementado |
| ExitBootServices no kernel | não implementado; responsabilidade do loader |
| GOP consumido via framebuffer Limine | implementado |
| GOP protocol nativo no kernel | não implementado |
| memory map EFI cru | não implementado |
| memory map Limine | implementado |
| GUID GPT de ESP | implementado |
| fallback EFI/BOOT/BOOTX64.EFI | implementado |
| ESP hard-disk FAT32 | não implementado; writer atual é FAT16-style |
| registro NVRAM Boot#### | não implementado |
| BootOrder | não implementado |
| UEFI variables | não implementado |
| Secure Boot controlado pelo ChrisOS | não implementado |
| TCG2/measured boot | não implementado |
| gate OVMF de segundo boot apenas pelo disco | ainda não provado |
| boot em máquina UEFI física | não provado |
| firmware UEFI executado pelo ChrisVM | não implementado |

## Limite de validação

Este capítulo foi conciliado com ChrisOS main **da3df29cb397932c43d32373871fb9380e688ade**.

O UEFI Forum lista UEFI Specification 2.11, publicada em dezembro de 2024, como versão UEFI mais recente.

O projeto usa Limine como bootloader externo. Este capítulo não tenta documentar internals do Limine; o próximo capítulo trata o protocolo de boot a partir do ponto de vista do ChrisOS.

Execute:

~~~text
python scripts/check_uefi_examples.py --source .source
~~~

O checker valida cálculos selecionados e fatos do repositório.

## Gatilhos de revisão

Revisar quando:

- o installer migrar de FAT16-style para FAT32;
- o gate OVMF do disco instalado existir ou passar;
- surgir suporte Boot####/BootOrder;
- Runtime Services forem integrados;
- EFI System Table for preservada em bootinfo;
- RSDP/SMBIOS forem encaminhados pelo Limine;
- Secure Boot se tornar alvo suportado;
- Limine for substituído ou complementado por loader EFI próprio;
- ChrisVM ganhar execução de firmware UEFI.

## Referências primárias

- UEFI Forum, UEFI Specification 2.11.
- UEFI Forum, Platform Initialization Specification 1.10.
- Arquivos-fonte do ChrisOS listados no front matter.
