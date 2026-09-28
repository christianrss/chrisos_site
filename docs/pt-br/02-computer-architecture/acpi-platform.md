---
id: acpi-platform
lang: pt-br
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/acpi.c
  - kernel/metal/acpi.h
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/mm.c
  - kernel/metal/apic.c
  - kernel/metal/ioapic.c
  - kernel/metal/smp.c
  - kernel/metal/pci.c
  - kernel/metal/start.c
symbols:
  - acpi_probe
  - bootinfo_phys_to_virt
  - bootinfo_memmap_entry
  - bootinfo_mp_response
  - mm_lapic_virt
  - apic_init
  - apic_enable_local
  - ioapic_init
  - smp_init
depends_on:
  - pci-pcie
  - x86-64-memory-privilege
related:
  - reset-firmware
  - uefi
  - limine
  - boot-information
  - pic-apic-ioapic
  - interrupts-smp
  - timers
  - installation-real-hardware
---

# ACPI e descrição da plataforma

## Escopo

ACPI é o contrato por meio do qual o firmware descreve topologia de hardware, configuração, interfaces de gerenciamento de energia, roteamento de interrupções, relações entre processadores e outros detalhes específicos da máquina ao sistema operacional.

ACPI não é apenas uma interface para desligar a máquina e não é uma convenção de chamadas BIOS.

ACPI moderno combina:

- tabelas estáticas de descrição do sistema;
- namespace hierárquico;
- métodos e objetos em bytecode AML;
- registradores de hardware fixos e genéricos;
- negociação de capabilities com o sistema operacional;
- semântica de eventos, wake e gerenciamento de energia.

O UEFI Forum define ACPI como interface para configuração e gerenciamento de energia dirigidos pelo sistema operacional, OSPM. ACPI 6.6 é a revisão corrente da especificação na data desta revisão.

O ChrisOS implementa hoje apenas um probe pequeno. Ele localiza uma assinatura semelhante a RSDP na janela BIOS legada, segue XSDT quando Revision é pelo menos 2 e imprime assinaturas selecionadas de tabelas filhas. Ele ainda não valida checksums ACPI nem transforma MADT, MCFG ou FADT em estado de plataforma utilizado pelo kernel.

![Grafo de descoberta ACPI e descrição da plataforma](../../assets/diagrams/acpi-platform-pt-br.svg)

A distinção entre detectar uma tabela e implementar o recurso descrito por ela é central neste capítulo.

## ACPI como interface de descrição da plataforma

O kernel não deveria conter constantes específicas para cada placa-mãe.

O firmware pode descrever:

- controladores de interrupção;
- processadores e identidades APIC;
- roteamento global de interrupções;
- janelas PCIe ECAM;
- registradores fixos de gerenciamento de energia;
- localização de DSDT e SSDTs;
- dispositivos presentes no namespace ACPI;
- recursos exigidos pelos dispositivos;
- relações de wake e térmicas;
- métodos de controle específicos da plataforma.

ACPI transfere parte do conhecimento da plataforma do código-fonte do kernel para dados e descrição executável fornecidos pelo firmware.

## Tabelas estáticas e AML

É necessário separar duas grandes categorias.

Tabelas de dados estáticas incluem MADT, MCFG, SRAT, SLIT, HPET e muitas outras. Elas contêm estruturas binárias.

Definition Blocks como DSDT e SSDT contêm AML, ACPI Machine Language. AML cria e estende o namespace e pode conter métodos executáveis.

Um sistema operacional completo precisa, portanto, de:

~~~text
parser de tabelas ACPI
+
interpretador AML e namespace
~~~

É possível implementar ACPI de forma incremental, começando pelas tabelas estáticas antes de completar o runtime AML.

## Grafo de descoberta

Um grafo típico de ACPI é:

~~~text
RSDP
 |
 +--> XSDT ou RSDT
        |
        +--> FADT/FACP
        |      |
        |      +--> DSDT
        |      +--> FACS
        |
        +--> MADT
        +--> MCFG
        +--> HPET
        +--> SRAT
        +--> SLIT
        +--> SSDT
        +--> outras tabelas
~~~

A tabela raiz é um diretório de endereços físicos de outras tabelas, e não uma descrição completa da máquina.

## Root System Description Pointer

RSDP é a primeira estrutura ACPI que o OSPM precisa obter.

A assinatura possui oito bytes:

~~~text
RSD PTR<espaço>
~~~

O espaço final faz parte da assinatura.

Os primeiros 20 bytes são compatíveis com ACPI 1.0. Revision 2 ou superior adiciona campos como Length, XsdtAddress e Extended Checksum.

Assinatura correta sozinha não prova validade.

## Checksums do RSDP

Os primeiros 20 bytes precisam somar zero módulo 256.

Para Revision 2 ou superior, todo o objeto de Length bytes também precisa somar zero.

~~~text
sum(bytes[0:20]) & 0xFF == 0

se revision >= 2:
    sum(bytes[0:length]) & 0xFF == 0
~~~

O acpi_probe atual verifica a assinatura, mas não valida nenhum desses checksums.

O checker deste capítulo constrói RSDPs sintéticos válidos e corrompidos para manter essas regras executáveis.

## Busca legada de RSDP em IA-PC

Na descoberta IA-PC legada, ACPI define locais como:

1. primeiro 1 KiB da Extended BIOS Data Area;
2. região BIOS ROM entre 0xE0000 e 0xFFFFF.

Candidatos são procurados em fronteiras de 16 bytes e precisam passar assinatura e checksum.

O ChrisOS atual varre 0xE0000..0xFFFFF.

Ele não busca o primeiro KiB da EBDA.

Por isso acpi_probe deve ser tratado como probe de bring-up, não como descoberta IA-PC completa.

## RSDP em sistemas UEFI

O alvo de hardware real do ChrisOS é UEFI.

Em sistemas UEFI, a especificação ACPI determina que o loader obtenha o ponteiro RSDP a partir da EFI System Table Configuration Table e o entregue ao OSPM durante o handoff.

UEFI define GUIDs para ACPI 1.0 e para ACPI 2.0 ou posterior, com preferência pela entrada mais nova.

A arquitetura robusta é:

~~~text
firmware UEFI
    |
EFI System Table
    |
GUID ACPI na Configuration Table
    |
ponteiro RSDP
    |
handoff do bootloader
    |
bootinfo do ChrisOS
~~~

A varredura da memória BIOS deve ser fallback, não o caminho principal em UEFI.

## Handoff atual do Limine

bootinfo.c solicita atualmente:

- framebuffer;
- HHDM;
- memory map;
- informação multiprocessor;
- command line.

O código-fonte não preserva um ponteiro RSDP.

Por isso acpi_probe redescobre ACPI por varredura legada.

Um contrato futuro de boot deve carregar o RSDP fornecido por firmware/bootloader diretamente.

## Mecânica da varredura atual

acpi_probe percorre entradas do memory map do Limine e examina candidatos físicos na região BIOS.

Cada candidato é convertido por bootinfo_phys_to_virt, então o probe depende do HHDM.

O código confere se os bytes candidatos pertencem a uma entrada do memory map antes de ler a assinatura.

Isso é uma disciplina útil, mas insuficiente porque:

- pertencer ao memory map não prova identidade ACPI;
- checksum não é validado;
- Length do RSDP não é validado;
- o objeto completo pode ultrapassar os bytes checados;
- ponteiros filhos são confiados após validação mínima.

## Revisões do RSDP

Revision 0 fornece RSDT.

Revision 2 ou superior também fornece XSDT.

O acpi_probe atual só continua quando:

~~~text
revision >= 2
~~~

e então segue XsdtAddress.

Não existe fallback por RSDT.

Portanto a travessia de root ACPI 1.0 não está implementada.

## RSDT e XSDT

RSDT contém ponteiros físicos de 32 bits.

XSDT contém ponteiros físicos de 64 bits.

Ambas usam o cabeçalho comum System Description Table.

Em x86-64, XSDT costuma ser preferível porque endereços de tabelas não ficam limitados a 32 bits.

Ainda assim, um parser robusto pode manter suporte a RSDT por compatibilidade.

## Cabeçalho System Description Table

A maioria das tabelas ACPI começa com um cabeçalho de 36 bytes contendo:

- Signature;
- Length;
- Revision;
- Checksum;
- OEM ID;
- OEM Table ID;
- OEM Revision;
- Creator ID;
- Creator Revision.

Length inclui o próprio cabeçalho.

Toda a tabela de Length bytes precisa somar zero módulo 256.

Um validador genérico deve implementar essa regra uma vez e ser reutilizado por todas as SDTs.

## Travessia XSDT atual

acpi_probe valida a assinatura XSDT, lê Length e percorre ponteiros de 64 bits iniciando no byte 36.

Existe ainda o limite local:

~~~text
entry_offset < 512
~~~

Esse limite evita laço sem fim, mas não é uma regra semântica do ACPI.

Hoje não são validados:

- checksum da XSDT;
- Length >= 36;
- divisibilidade do payload por oito;
- range físico completo;
- checksums das tabelas filhas.

## Cálculo de quantidade de entradas

Para uma tabela válida:

~~~text
payload = Length - 36
~~~

RSDT exige:

~~~text
payload % 4 == 0
count = payload / 4
~~~

XSDT exige:

~~~text
payload % 8 == 0
count = payload / 8
~~~

O checker valida essas invariantes.

## Registry de tabelas ACPI

Um core ACPI sustentável deve descobrir as tabelas uma vez e registrá-las.

Exemplo:

~~~text
AcpiTable
  signature
  physical_address
  virtual_address
  length
  revision
  checksum_valid
~~~

Consumidores poderiam consultar:

~~~text
acpi_find(APIC, index)
acpi_find(MCFG, index)
acpi_find(FACP, index)
acpi_find(SSDT, index)
~~~

SSDTs podem existir em múltiplas instâncias, portanto assinatura não deve ser assumida como única.

## MADT

MADT possui assinatura APIC.

Ela descreve topologia de processadores e controladores de interrupção.

A parte fixa inclui Local Interrupt Controller Address e Flags. Depois há uma sequência de entradas variáveis.

Em x86, podem aparecer estruturas para:

- Processor Local APIC;
- I/O APIC;
- Interrupt Source Override;
- NMI source;
- Local APIC NMI;
- Local APIC Address Override;
- Processor Local x2APIC;
- Local x2APIC NMI.

O parser precisa avançar pelo Length de cada subestrutura.

## Walker seguro de MADT

Cada entrada variável começa por:

~~~text
Type   1 byte
Length 1 byte
~~~

Walker seguro exige:

~~~text
Length >= 2
current + Length <= table_end
~~~

e avança exatamente Length bytes.

Length zero ou um deve ser rejeitado para evitar loop ou sobreposição.

O checker inclui entradas MADT válidas e malformadas.

## Endereço físico do LAPIC

A parte fixa da MADT informa o endereço físico do controlador local.

Pode existir também Local APIC Address Override com endereço de 64 bits substituto.

Um kernel robusto deriva o endereço da MADT.

O mm.c atual define:

~~~text
LAPIC_PHYS = 0xFEE00000
~~~

e mm_selftest mapeia essa constante.

Isso funciona no perfil atual do QEMU, mas não é descoberta orientada por MADT.

## Fonte atual da topologia de CPUs

smp_init utiliza a resposta multiprocessor do Limine.

Dela obtém:

- quantidade de CPUs;
- BSP LAPIC ID;
- LAPIC IDs dos APs;
- estruturas de startup fornecidas pelo bootloader.

Essa é a informação efetivamente usada para iniciar APs.

acpi_probe apenas imprime APIC quando encontra a assinatura MADT.

Portanto MADT não é hoje a fonte de topologia SMP.

Uma arquitetura futura pode manter Limine para iniciar CPUs, mas usar MADT como descrição autoritativa e cruzar ambas as visões.

## I/O APIC

MADT pode descrever um ou mais I/O APICs.

Cada descrição inclui endereço físico e Global System Interrupt base.

Interrupt Source Override mapeia fontes ISA legadas para GSIs e informa polaridade/trigger.

ioapic_init atual não interpreta nem programa esses dados. Ele apenas informa que o PIC ainda roteia IRQs.

A existência de ioapic.c não deve ser confundida com implementação completa de IOAPIC/ACPI.

## Global System Interrupts

ACPI representa entradas de interrupção por Global System Interrupt numbers.

IRQ legado e GSI não são necessariamente iguais, porque Interrupt Source Overrides podem remapear.

Isso importa para:

- PIT;
- teclado;
- ATA;
- ACPI SCI;
- PCI INTx.

Assumir IRQ == GSI pode funcionar em emulador simples e falhar no hardware real.

## Modelo futuro da MADT

Uma representação útil seria:

~~~text
AcpiCpu
  uid
  apic_id
  enabled
  online_capable

AcpiIoApic
  id
  physical_address
  gsi_base

AcpiIso
  source_irq
  gsi
  polarity
  trigger
~~~

SMP, IOAPIC e roteamento devem consumir estruturas validadas, não bytes crus de firmware.

## MCFG

MCFG descreve regiões PCIe ECAM.

Cada alocação identifica:

- base ECAM;
- segment group;
- start bus;
- end bus.

O capítulo PCI derivou:

~~~text
ecam =
base
+ ((bus - start_bus) << 20)
+ (device << 15)
+ (function << 12)
+ register
~~~

acpi_probe atualmente detecta MCFG pela assinatura, mas não interpreta alocações.

Por isso pci.c continua usando CF8/CFC.

## Tamanho de um range MCFG

Cada bus PCI ocupa 1 MiB do espaço ECAM.

Para range inclusivo válido:

~~~text
bytes =
(end_bus - start_bus + 1)
* 0x100000
~~~

end_bus menor que start_bus é malformação.

O checker valida essa aritmética.

## FADT / FACP

Fixed ACPI Description Table usa assinatura FACP.

FADT conecta as tabelas estáticas ao modelo de hardware fixo e ao namespace AML.

Campos importantes incluem:

- FIRMWARE_CTRL e X_FIRMWARE_CTRL;
- DSDT e X_DSDT;
- SCI_INT;
- blocos PM1;
- PM timer;
- reset register/value;
- boot architecture flags;
- hardware-reduced ACPI;
- flags de capabilities da plataforma.

acpi_probe atual reconhece apenas a assinatura FACP.

Nenhum desses campos é interpretado.

## DSDT

Differentiated System Description Table contém AML.

FADT aponta para DSDT usando DSDT ou X_DSDT.

Carregar a DSDT constrói a base do namespace ACPI.

Depois do cabeçalho de 36 bytes, DSDT não é uma estrutura C fixa; seu payload é bytecode AML.

O ChrisOS ainda não possui loader DSDT nem interpretador AML.

## SSDT

Secondary System Description Tables também contêm Definition Blocks AML.

Múltiplas SSDTs podem estender o namespace.

Elas devem manter a ordem apresentada pela tabela raiz.

Isso é mais um motivo para o futuro registry permitir assinaturas repetidas com ordem estável.

## ASL e AML

Firmware normalmente é escrito em ACPI Source Language, ASL.

Um compilador produz AML.

~~~text
ASL -> compilador -> AML
                      |
                      v
                    OSPM
~~~

O kernel interpreta AML; ele não executa texto ASL.

## Namespace ACPI

Depois de carregar DSDT/SSDT, ACPI expõe namespace hierárquico.

Ele pode conter:

- Device;
- Method;
- inteiros;
- strings e buffers;
- Packages;
- Fields;
- Operation Regions;
- mutexes e events;
- objetos térmicos e de energia.

Paths podem parecer:

~~~text
\_SB.PCI0
\_SB.PCI0.XHC
\_PR.CPU0
~~~

Os nomes exatos são dados do firmware, não constantes universais.

## Requisitos de um interpretador AML

Runtime AML genérico exige:

- decoding de opcodes;
- construção de namespace;
- resolução de nomes e escopos;
- modelo de objetos;
- inteiros/buffers/packages;
- argumentos e locals;
- controle de fluxo;
- conversões;
- Operation Regions;
- Fields;
- sincronização;
- resource templates;
- limites de execução e erros.

Procurar algumas strings no DSDT não substitui um interpretador.

## Identificação e recursos de dispositivos

Objetos ACPI comuns incluem:

- _HID: hardware ID;
- _CID: compatible ID;
- _UID: unique ID;
- _STA: status;
- _CRS: recursos atuais;
- _PRS: recursos possíveis;
- _SRS: programação de recursos.

Esses mecanismos são importantes para dispositivos que não se autoenumeram por PCI ou outro bus.

O ChrisOS não avalia esses objetos atualmente.

## Roteamento PCI com _PRT

_PRT descreve roteamento de interrupções PCI no namespace ACPI.

Ele mapeia relações device/pin para recursos de interrupção e pode envolver PCI link devices.

Uma implementação completa de INTx em hardware ACPI pode exigir avaliação AML além dos campos de configuração PCI.

Existe, portanto, dependência direta entre ACPI e PCI.

## _PIC

_PIC informa ao firmware qual modelo de interrupção o OSPM selecionou.

Métodos AML podem variar o roteamento dependendo de PIC legado ou APIC.

O ChrisOS atualmente não avalia _PIC.

O caminho atual ainda mantém roteamento pelo PIC, com LAPIC parcial e IOAPIC não implementado.

## _OSC

_OSC permite ao OSPM comunicar capabilities e negociar controle com firmware.

No PCIe isso é importante para ownership de serviços nativos, incluindo partes de hot-plug e tratamento de erros.

Sem runtime AML, o ChrisOS não executa _OSC em host bridges PCI.

Acesso ECAM sozinho não prova ownership de todos os serviços PCIe.

## SCI

System Control Interrupt é a interrupção central de eventos ACPI no modelo tradicional.

FADT fornece SCI_INT.

SCI transporta eventos fixos e General Purpose Events.

O ChrisOS ainda não possui handler ACPI SCI.

## General Purpose Events

GPEs representam eventos de firmware/plataforma como wake, temperatura ou notificações de dispositivos.

Suporte correto exige:

- descobrir registradores GPE;
- gerenciar status e enable;
- integrar SCI;
- despachar métodos AML;
- limpar/mascarar corretamente.

Erros podem gerar storm de interrupções.

Não existe subsistema GPE no ChrisOS atual.

## Hardware fixo e Generic Address Structure

Plataformas ACPI tradicionais expõem PM1, PM timer e GPE.

Descrições modernas usam Generic Address Structure e podem ser hardware-reduced.

GAS descreve um registrador com:

- address-space ID;
- bit width;
- bit offset;
- access size;
- endereço de 64 bits.

Uma camada ACPI genérica deveria converter GAS em acessos I/O/MMIO seguros e com largura exata.

O ChrisOS não possui abstração GAS.

## Reset ACPI

FADT pode fornecer RESET_REG e RESET_VALUE.

Quando suportados, definem mecanismo de reset descrito pelo firmware.

acpi_probe atual não interpreta nem utiliza esses campos.

Um reboot futuro deveria preferir um caminho ACPI validado antes de fallbacks específicos da máquina.

## Sleep e soft-off

ACPI define semântica de estados de energia incluindo working, sleep, hibernation e soft-off.

Nem toda plataforma implementa todos os estados.

Transições exigem coordenação de dispositivos, fontes de wake e métodos de firmware.

O ChrisOS ainda não implementa suspend/resume ACPI genérico.

## Por que buscar _S5 em bytes não basta

Alguns kernels simples procuram o texto _S5 no DSDT e inferem valores de desligamento.

DSDT é bytecode AML, não arquivo de configuração textual.

A mesma sequência pode aparecer em contexto que o hack não compreende.

Shutdown correto deve utilizar namespace/semântica AML e registradores descritos pela FADT.

Esse tipo de busca não deve ser a arquitetura de longo prazo do ChrisOS.

## FACS

FADT pode apontar para Firmware ACPI Control Structure.

FACS contém campos de coordenação entre firmware e OS, incluindo elementos históricos ligados a wake e ACPI Global Lock.

FACS não usa o cabeçalho/checksum comum de uma SDT.

Logo, um validador genérico deve saber que nem toda estrutura ACPI é SDT comum.

O ChrisOS não utiliza FACS atualmente.

## Hardware-reduced ACPI

Algumas plataformas não implementam os blocos fixos ACPI tradicionais.

Flags na FADT indicam hardware-reduced ACPI.

O software precisa consultar essas flags antes de presumir portas PM1/GPE clássicas.

Isso mostra por que endereços fixos de power management não são arquitetura portátil.

## SRAT e SLIT

SRAT descreve afinidade de proximidade para CPUs, memória e outros iniciadores.

SLIT descreve distâncias relativas de localidade.

Essas tabelas alimentam políticas NUMA.

O ChrisOS ainda não possui alocação ou scheduling NUMA-aware, então elas são trabalho futuro de plataforma.

## HPET e timers

Uma tabela ACPI HPET pode descrever High Precision Event Timer.

O subsistema de timers futuro deveria obter HPET pelo registry ACPI, não repetir busca em firmware.

Os timers atuais do ChrisOS não são selecionados por descoberta ACPI HPET.

## Thermal e energia de processadores

O namespace ACPI pode descrever thermal zones, relações de resfriamento, estados de energia de dispositivos, idle/performance de processadores e mecanismos modernos como CPPC.

Tudo isso exige AML e política no OS.

É muito além do acpi_probe atual.

## Fronteira de confiança do firmware

Tabelas ACPI e AML são entrada controlada por firmware executada/consumida em modo kernel.

Uma implementação robusta precisa defender contra:

- lengths inválidos;
- overflow de endereços físicos;
- checksums corrompidos;
- registros variáveis malformados;
- referências cíclicas;
- execução AML excessiva;
- Operation Regions inválidas;
- firmware OEM quebrado;
- firmware virtual hostil.

Hardening do parser é parte da segurança do kernel.

## Segurança de ponteiros físicos

Tabelas ACPI contêm endereços físicos.

Antes de validar checksum da tabela inteira, o kernel precisa provar que o range declarado é seguro para leitura.

Sequência recomendada:

~~~text
mapear/ler cabeçalho mínimo
validar tamanho mínimo
validar overflow e limites máximos
mapear/ler range declarado
validar checksum
só então interpretar campos
~~~

Checksum não torna dereference inseguro em seguro.

## Checksum não é autenticação

Checksum detecta corrupção e estrutura malformada.

Não autentica firmware.

Firmware malicioso pode produzir tabelas hostis com checksums perfeitos.

Secure Boot, measured boot e confiança de plataforma são camadas distintas.

## Ordem de boot atual do ChrisOS

start.c inicializa APIC, IOAPIC e SMP antes de chamar acpi_probe.

Depois, desabilita interrupções e executa descoberta ACPI.

Assim, ACPI atualmente não fornece a topologia usada pelos subsistemas inicializados antes.

Num design de hardware real orientado por ACPI, descoberta e validação das tabelas estáticas devem ocorrer antes de consumidores de MADT, MCFG e FADT.

## Caminho LAPIC atual

A sequência atual é aproximadamente:

~~~text
mm_selftest:
    mapear 0xFEE00000 hardcoded

apic_init:
    obter ponteiro LAPIC mapeado

smp_init:
    obter CPUs pelo Limine MP

mais tarde:
    acpi_probe imprime assinatura APIC
~~~

É código funcional de bring-up, não arquitetura final de dependências.

## Caminho IOAPIC atual

ioapic_init apenas informa que o PIC ainda roteia IRQs.

Nenhum registro I/O APIC da MADT ou Interrupt Source Override é usado.

Portanto IOAPIC/ACPI deve permanecer classificado como não implementado ou experimental nesta revisão.

## Estágios recomendados de implementação

### Estágio 1: root confiável e integridade

- carregar RSDP no bootinfo;
- validar checksum de 20 bytes e extended checksum;
- suportar RSDT e XSDT;
- validar headers/checksums de SDTs;
- construir registry de tabelas.

### Estágio 2: tabelas estáticas

- MADT;
- MCFG;
- campos fixos da FADT;
- HPET quando necessário;
- SRAT/SLIT quando existirem consumidores.

### Estágio 3: consumidores de interrupção e PCI

- LAPIC/IOAPIC derivados de MADT;
- Interrupt Source Overrides;
- ECAM derivado de MCFG;
- SCI/reset derivados de FADT.

### Estágio 4: núcleo AML

- carregar DSDT/SSDT;
- decoding AML;
- namespace;
- modelo de objetos;
- resource templates.

### Estágio 5: métodos de plataforma

- _PIC;
- _PRT;
- _OSC;
- _STA/_CRS;
- métodos de energia e eventos.

### Estágio 6: modelo completo de eventos/energia

- SCI;
- GPE;
- shutdown/reset;
- suspend/resume;
- thermal;
- gerenciamento de energia de processadores.

Essa sequência cria valor para hardware real antes de terminar AML.

## Estruturas sugeridas

~~~text
AcpiContext
  rsdp
  root
  tables[]
  madt
  mcfg
  fadt
  namespace
  aml_runtime

AcpiTable
  signature
  physical_address
  length
  revision

AcpiMadt
  lapic_phys
  cpus[]
  ioapics[]
  overrides[]

AcpiMcfg
  segments[]
~~~

Consumidores devem receber modelos validados, não ponteiros crus de firmware.

## Packed structs não substituem validação

Estruturas C packed ajudam a nomear campos.

Elas não eliminam:

- checagem de Length antes de acessar campo;
- campos opcionais dependentes da revisão;
- validação de range e overflow;
- checksum;
- cuidado com alinhamento e endian.

Parser baseado em leitura de bytes pode ser mais seguro para tabelas truncadas.

## Algoritmo reutilizável de checksum

A aritmética é simples:

~~~text
sum = 0
para cada byte:
    sum = (sum + byte) & 0xFF

válido quando sum == 0
~~~

O problema difícil é provar antes que o range pode ser lido com segurança.

## ACPI determinístico no ChrisVM

O ChrisVM precisará de descrição de plataforma para substituir progressivamente o QEMU nos caminhos nativos do ChrisOS.

Um conjunto mínimo pode gerar:

~~~text
RSDP
XSDT
MADT
MCFG
FADT
DSDT
~~~

Cada tabela pode usar endereços determinísticos e checksums reproduzíveis.

Assim o ChrisOS testa seu próprio parser sem depender do layout das tabelas do OVMF/QEMU.

## MADT gerada pelo ChrisVM

No ChrisVM multiprocessor, a configuração da máquina deve definir:

- CPUs virtuais e APIC IDs;
- endereço LAPIC;
- I/O APIC;
- source overrides opcionais.

O mesmo modelo deve gerar hardware virtual e registros MADT.

Isso evita divergência entre o que o hardware faz e o que o firmware declara.

## MCFG gerada pelo ChrisVM

Quando PCIe/ECAM virtual existir, um único objeto deve definir:

~~~text
segmento PCI
range de buses
base ECAM
~~~

O ChrisVM pode rotear a região MMIO e serializar os mesmos valores na MCFG.

O guest passa a usar o mesmo caminho de descoberta previsto para UEFI físico.

## ChrisVM como laboratório AML

Uma DSDT mínima pode inicialmente expor apenas os objetos exigidos pelos testes.

Com o crescimento do runtime AML, firmware determinístico pode adicionar:

- scopes aninhados;
- Packages;
- Operation Regions;
- _STA;
- _CRS;
- _PRT;
- _PIC;
- _OSC.

Isso fornece regressões controladas para o interpretador AML.

## Testes de firmware malformado

ChrisVM ou testes host devem futuramente injetar:

- checksum RSDP inválido;
- extended checksum inválido;
- XSDT truncada;
- child table com checksum inválido;
- MADT com entry Length zero;
- MCFG com bus range invertido;
- resource templates malformados;
- falhas AML limitadas.

O resultado esperado é erro controlado de parser, nunca corrupção de memória do kernel.

## Checker reproduzível

scripts/check_acpi_examples.py valida a mecânica deste capítulo:

1. checksum dos 20 bytes do RSDP;
2. extended checksum de RSDP Revision 2;
3. checksum genérico de SDT;
4. aritmética de quantidade de entradas RSDT/XSDT;
5. travessia de entries MADT;
6. rejeição de MADT com comprimento malformado;
7. tamanho de range MCFG;
8. cálculo ECAM;
9. reparo de checksum em tabelas sintéticas.

Ele não é interpretador AML nem suíte de conformidade de firmware ACPI.

## Matriz da implementação atual

| Capability | Estado atual |
|---|---|
| scan 0xE0000..0xFFFFF por assinatura RSDP | implementado |
| scan do primeiro 1 KiB da EBDA | não implementado |
| handoff RSDP por UEFI/bootloader | não implementado em bootinfo |
| validação da assinatura RSDP | implementada |
| checksum RSDP 20 bytes | não implementado |
| extended checksum do RSDP | não implementado |
| travessia RSDT | não implementada |
| travessia XSDT | parcial |
| checksum genérico de SDT | não implementado |
| registry ACPI | não implementado |
| detecção da assinatura MADT | implementada |
| parsing MADT | não implementado |
| LAPIC address derivado de MADT | não implementado |
| I/O APIC derivado de MADT | não implementado |
| Interrupt Source Overrides | não implementados |
| detecção MCFG | implementada |
| parsing MCFG / ECAM | não implementado |
| detecção FADT/FACP | implementada |
| parsing FADT | não implementado |
| carregamento DSDT/SSDT | não implementado |
| interpretador AML | não implementado |
| namespace ACPI | não implementado |
| _PIC / _PRT / _OSC | não implementados |
| SCI/GPE | não implementado |
| reset/power-off ACPI genérico | não implementado |
| suspend/resume | não implementado |
| geração ACPI no ChrisVM | não implementada |

## Limite de validação

Este capítulo foi conciliado com ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

O UEFI Forum lista ACPI Specification Version 6.6, publicada em maio de 2025, como versão mais recente na data desta revisão.

Execute:

~~~text
python scripts/check_acpi_examples.py
~~~

O script valida apenas exemplos mecânicos e invariantes do parser descritos no capítulo.

## Gatilhos de revisão

Revisar quando:

- bootinfo começar a transportar RSDP;
- checksums ACPI forem implementados;
- RSDT for suportada;
- surgir registry de tabelas;
- MADT começar a dirigir LAPIC/IOAPIC/SMP;
- MCFG começar a fornecer ECAM;
- FADT for interpretada;
- DSDT/SSDT forem carregadas;
- AML/namespace começar a existir;
- SCI/GPE ou gerenciamento de energia for implementado;
- ChrisVM começar a gerar tabelas ACPI.

## Referências primárias

- UEFI Forum, Advanced Configuration and Power Interface Specification 6.6.
- UEFI Forum, UEFI Specification 2.11, EFI System Table e Configuration Table.
- Interfaces de firmware PCI/PCIe relacionadas a _PRT e _OSC.
- Arquivos-fonte do ChrisOS listados no front matter deste capítulo.
