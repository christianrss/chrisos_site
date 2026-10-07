---
id: bibliography
lang: pt-br
type: reference-chapter
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources: []
symbols: []
depends_on:
  - specifications-policy
related:
  - source-policy
  - validation-evidence
---

# Bibliografia primária e mapa de padrões

## Propósito

Este capítulo define as referências externas primárias usadas para interpretar arquitetura, interfaces, protocolos e claims de implementação do ChrisOS.

Não é uma lista genérica de leitura. O objetivo é responder a três perguntas de engenharia:

1. qual autoridade define um comportamento que o ChrisOS não controla;
2. qual documento deve ser consultado antes de alterar um contrato externamente visível;
3. como especificações externas, source do ChrisOS e evidência de validação são conciliados quando parecem divergir.

O catálogo machine-readable canônico é mantido em `data/bibliography.yml`. Este capítulo explica como esse catálogo deve ser usado e como cada família de referência se relaciona com o sistema operacional.

## Modelo de autoridade

A documentação do ChrisOS separa quatro tipos de autoridade.

| Autoridade | Papel |
|---|---|
| Source atual do ChrisOS em `main` | define o comportamento implementado pelo ChrisOS |
| Especificação interna/persistida do ChrisOS | define formatos e contratos controlados pelo projeto |
| Especificação externa primária | define standards consumidos pelo ChrisOS |
| Evidência de teste ou hardware | demonstra que um caminho implementado se comporta como alegado |

Essas autoridades respondem a perguntas diferentes.

A especificação VirtIO, por exemplo, define o device protocol. O source do ChrisOS define qual subconjunto de VirtIO está implementado. Evidência em QEMU ou hardware mostra se esse subconjunto interoperou no ambiente testado.

Nenhuma dessas camadas substitui as outras.


## Fronteira de escopo de source desta bibliografia

Este capítulo declara intencionalmente `sources: []` porque seu objeto é o catálogo de referências externas e as regras para utilizá-lo, não o estado de implementação de um subsistema do ChrisOS.

Essa fronteira tem uma consequência concreta: esta página não deve congelar afirmações dependentes de revisão como "o ChrisOS atualmente usa a feature X" ou "o driver atual suporta Y" sem também declarar e manter as dependências de source correspondentes. Estado de implementação pertence ao chapter do subsistema, à especificação, ao source map gerado ou ao registro de validação vinculado à revisão do código pertinente.

A bibliografia ainda pode explicar como um standard externo se relaciona ao ChrisOS. Essa redação deve permanecer condicional ou metodológica: pode indicar qual autoridade consultar, qual evidência um chapter de implementação precisa apresentar e como descrever compliance parcial. A presença de um standard neste catálogo nunca é evidência de que o ChrisOS implementa esse standard ou uma feature específica dele.

## Regra de fonte primária

Quando uma tecnologia externa possui especificação normativa, a bibliografia deve preferir essa especificação em vez de:

- tutorials;
- blog posts;
- forum answers;
- vendor summaries;
- explicações geradas por IA;
- textbooks secundários;
- source de outros sistemas operacionais.

Fontes secundárias podem ajudar na explicação, mas não são autoridade final para bit layouts, reserved values, state transitions, timing requirements ou regras de ABI.

## Fixação de revisão

Standards externos evoluem independentemente do histórico Git do ChrisOS.

Um registro rigoroso deve carregar, quando relevante:

    revisão do source ChrisOS
    revisão da especificação externa

A afirmação "o driver segue VirtIO" é incompleta se o comportamento do protocolo mudou entre revisões.

O catálogo usa títulos de famílias de standards que continuam evoluindo. Quando a edição específica altera comportamento, o chapter de implementação deve registrar essa edição.

## Referências de arquitetura x86

### Intel Software Developer's Manual

**Intel 64 and IA-32 Architectures Software Developer's Manual**

Organização: Intel.

Use esta família como referência primária para comportamento x86 definido pela Intel, incluindo:

- instruction semantics;
- control registers;
- segmentation;
- paging;
- exceptions e interrupts;
- APIC;
- memory ordering;
- cache-control mechanisms;
- system instructions;
- VMX quando aplicável.

Capítulos do ChrisOS sobre long mode, page tables, exceptions, interrupt control, SMP e feature detection devem separar garantias arquiteturais das decisões específicas do kernel.

### AMD64 Architecture Programmer's Manual

**AMD64 Architecture Programmer's Manual**

Organização: AMD.

É a família primária correspondente para comportamento AMD64.

É especialmente relevante para:

- long-mode architectural state;
- page translation;
- SYSCALL/SYSRET;
- model-specific registers;
- exception semantics;
- AMD-specific feature bits;
- SVM.

Quando Intel e AMD descrevem comportamento comum de x86-64 com terminologia diferente, a documentação do ChrisOS não deve assumir que detalhes de uma vendor são automaticamente detalhes da outra.

## Referências RISC-V

### RISC-V unprivileged architecture

**The RISC-V Instruction Set Manual, Volume I — Unprivileged Architecture**

Organização: RISC-V International.

Use para:

- base instruction semantics;
- integer register model;
- memory operations;
- control-flow instructions;
- ISA extensions.

### RISC-V privileged architecture

**The RISC-V Instruction Set Manual, Volume II — Privileged Architecture**

Organização: RISC-V International.

Use para:

- privilege modes;
- CSRs;
- traps;
- interrupt delegation;
- address translation;
- `satp`;
- Sv39 e regras associadas.

Quando o ChrisOS documenta bring-up RISC-V, estes manuals definem o contrato arquitetural. O chapter de implementação correspondente deve registrar a superfície de execução realmente implementada e sua evidência; uma feature definida pelo standard não comprova que o ChrisOS a implemente.

## Firmware e boot

### UEFI

**Unified Extensible Firmware Interface Specification**

Organização: UEFI Forum.

Use UEFI como referência primária para firmware services, boot services, runtime services, system tables, memory maps e executable-loading conventions definidos pela firmware interface.

UEFI não é o mesmo que o boot protocol do ChrisOS.

Firmware pode carregar um bootloader; o bootloader depois entrega controle ao ChrisOS por outro contrato.

### ACPI

**Advanced Configuration and Power Interface Specification**

Organização: UEFI Forum.

Use ACPI para estruturas e semânticas de:

- RSDP;
- RSDT/XSDT;
- MADT/APIC topology;
- FADT/FACP;
- MCFG;
- AML-described platform configuration quando implementado.

Um probe do ChrisOS que encontra uma tabela não equivale a implementar toda ACPI.

A documentação deve dizer exatamente quais tabelas e fields o kernel consome.

### Limine boot protocol

**Limine Boot Protocol**

Organização: projeto Limine.

Os chapters de boot do ChrisOS usam a especificação do Limine para separar respostas definidas pelo bootloader do tratamento controlado pelo kernel. Cabe ao chapter de implementação, e não a esta bibliografia, registrar quais requests e responses são usados em uma revisão específica do source.

Use a referência do Limine para requests/responses como:

- framebuffer;
- memory map;
- higher-half direct map;
- multiprocessor information;
- kernel command line.

O source do ChrisOS continua sendo autoridade para quais recursos são requisitados e como respostas ausentes são tratadas.

## Executáveis, ABI e debug

### ELF

**System V Application Binary Interface — Executable and Linking Format**

Use ELF para:

- ELF headers;
- program headers;
- section headers quando relevantes;
- symbol tables;
- relocations;
- estrutura de executáveis e object files.

Loaders do ChrisOS podem implementar apenas um subset.

Uma feature válida em ELF não é automaticamente suportada pelo loader do ChrisOS.

### AMD64 System V ABI

**System V Application Binary Interface — AMD64 Architecture Processor Supplement**

Use para convenções x86-64 de:

- register argument passing;
- return values;
- stack alignment;
- caller/callee-saved registers;
- data layout;
- relocation/linking conventions.

Convenções internas do kernel ChrisOS podem divergir propositalmente do ABI de user space. Essas diferenças devem ser documentadas como decisões do ChrisOS.

### DWARF

**DWARF Debugging Information Format**

Organização: DWARF Standards Committee.

Use para debug-information encodings consumidos ou emitidos por compiler/debugger tooling.

Um debugger útil pode implementar apenas subset de DWARF; o subset precisa ser declarado explicitamente.

### ISO C

**ISO/IEC 9899 — Programming Languages — C**

Organização: ISO/IEC JTC 1/SC 22/WG 14.

Use o C standard para language semantics.

Isso é especialmente importante em kernel/compiler work que toca:

- integer conversion;
- signed overflow;
- aliasing;
- volatile access;
- object lifetime;
- alignment;
- implementation-defined behavior.

Hardware manual não substitui o C abstract machine, e o C standard não define side effects de device registers. Low-level code correto precisa respeitar as duas camadas.

## PCI e device interfaces

### PCI Express

**PCI Express Base Specification**

Organização: PCI-SIG.

Use para PCIe configuration space, capability structures, BARs, bus/device/function addressing, transaction requirements e conceitos de MSI/MSI-X.

Uma implementação PCI do ChrisOS pode ser mais estreita que o modelo PCIe completo. Um helper limitado a bus 0, por exemplo, seria limitação da implementação e não propriedade de PCIe.

### VirtIO

**Virtual I/O Device (VIRTIO) Specification**

Organização: OASIS.

Use para:

- feature negotiation;
- device status;
- virtqueue layout;
- descriptors;
- avail/used rings;
- MMIO/PCI transport;
- device-specific configuration.

Para qualquer driver VirtIO do ChrisOS, o chapter de implementação deve identificar transport e feature subset negociado. A presença de VirtIO nesta bibliografia não comprova que um device path específico exista no source atual.

## Storage

### NVMe

**NVM Express Base Specification**

Organização: NVM Express.

Use para:

- controller registers;
- submission/completion queues;
- command formats;
- namespaces;
- doorbells;
- status codes;
- queue lifecycle.

Success marker em QEMU estabelece interoperabilidade com um controller virtual testado, não compatibilidade universal com NVMe físico.

### AHCI

**Serial ATA Advanced Host Controller Interface**

Organização: Intel.

Use para:

- HBA registers;
- ports;
- command lists;
- command tables;
- FIS receive areas;
- port state.

AHCI define a interface do host controller. Os ATA commands transportados por ela são regidos por command-set specifications de ATA.

### ATA/ATAPI

**ATA/ATAPI Command Set**

Organização: INCITS Technical Committee T13.

Use para semantics de commands como IDENTIFY e sector I/O.

PIO register programming e AHCI transport são operacionalmente diferentes mesmo quando transportam commands ATA relacionados.

A documentação não deve colapsar transport e command set numa camada única.

## USB

### USB specification

**Universal Serial Bus Specification**

Organização: USB Implementers Forum.

Use para conceitos como:

- descriptors;
- endpoints;
- transfer types;
- device configuration;
- enumeration behavior independente de class.

Class specifications adicionam comportamento além do USB base.

### xHCI

**eXtensible Host Controller Interface for Universal Serial Bus**

Organização: Intel.

Use para:

- capability/operational registers;
- device contexts;
- transfer rings;
- event rings;
- command rings;
- TRBs;
- doorbells.

USB device protocol e xHCI host-controller mechanics pertencem a standards diferentes.

## Protocolos de Internet

As publicações RFC presentes no catálogo são referências primárias para a network stack.

### ARP — RFC 826

Use para resolução IPv4 → link-layer address em redes Ethernet-like.

### UDP — RFC 768

Use para UDP header e core datagram semantics.

### IPv4 — RFC 791

Use como referência histórica base do IPv4.

RFCs posteriores atualizam partes do comportamento; capítulos devem identificar documentos posteriores quando a regra discutida foi alterada.

### IPv6 — RFC 8200

Use como especificação base primária do IPv6.

### TCP — RFC 9293

Use RFC 9293 como especificação consolidada moderna do TCP em vez de depender apenas do texto original da RFC 793.

### DNS — RFC 1035

Use para message formats, labels e fundamentos do protocol DNS.

### DHCP — RFC 2131

Use para state e message exchange de DHCP.

## Interpretação de RFCs

Uma RFC pode ser:

- definição original;
- update standards-track;
- clarificação;
- extensão;
- deprecation.

Portanto citar número antigo não basta quando RFCs posteriores atualizam exatamente a regra usada.

Em implementação de protocolo, devem ser verificadas relações "Updates" e "Obsoletes" antes de considerar uma RFC antiga como definição completa.

## Graphics

### OpenGL

**OpenGL Specification**

Organização: Khronos Group.

Use para conceitos que o ChrisOS modela de forma OpenGL-like.

A graphics stack do ChrisOS não é uma implementação OpenGL completa salvo se uma camada específica declarar e provar essa compatibilidade.

### GLSL

**The OpenGL Shading Language Specification**

Organização: Khronos Group.

Use GLSL como referência externa para comparar syntax/semantics com o shader frontend do ChrisOS.

Quando um shader frontend do ChrisOS aceita sintaxe GLSL-like, a especificação de shaders e o chapter de implementação vinculado à revisão devem definir o subset suportado.

Um source iniciado com `#version 330` não torna o ChrisOS conformant com GLSL 3.30.

O contract real está em `shader-spec`.

### TGSI

**TGSI — Tungsten Graphics Shader Infrastructure**

Organização: Mesa.

Use para interpretar o IR externo esperado em qualquer path Mesa/VirGL no qual uma implementação do ChrisOS gere TGSI text.

TGSI não é o mesmo representation que CSIR.

### virglrenderer

**virglrenderer protocol and command definitions**

Organização: Mesa / projeto virglrenderer.

Use source/protocol definitions do virglrenderer para interpretar o path de commands 3D virtualizados.

VirtIO-GPU transport, VirGL commands, TGSI e a API gráfica própria do ChrisOS são camadas separadas.

## Material universitário

O catálogo também mantém duas coleções do MIT OpenCourseWare.

Elas são classificadas como **university lecture notes**, não como specifications normativas.

### MIT 6.012 — Microelectronic Devices and Circuits

Use para foundations de semiconductor/transistor behavior.

É útil em chapters que ligam:

- MOS electrostatics;
- transistor switching;
- capacitance;
- delay;
- power;
- physical implementation

a digital systems.

### MIT 6.004 — Computation Structures

Use para foundations de:

- combinational logic;
- sequential logic;
- finite-state machines;
- processors;
- pipelining;
- memory hierarchy;
- computer organization.

Essas notas explicam fundamentos. Não definem x86, RISC-V ou ChrisOS.

## Taxonomia de classes

O catálogo usa classes como:

- `architecture-manual`;
- `architecture-specification`;
- `firmware-specification`;
- `boot-protocol-specification`;
- `abi-specification`;
- `debug-format-specification`;
- `language-standard`;
- `bus-specification`;
- `device-specification`;
- `storage-specification`;
- `internet-standard`;
- `graphics-api-specification`;
- `graphics-language-specification`;
- `graphics-protocol-reference`;
- `graphics-ir-reference`;
- `university-lecture-notes`.

A classe comunica que tipo de autoridade a source possui.

Lecture note não deve ser citada como hardware standard.

Vendor manual não deve ser citado como se definisse policy interna do ChrisOS.

## Mapeamento entre standard e evidência ChrisOS

Um claim de implementação útil pode ser modelado como:

[
C = (S_e,; R_e,; S_c,; T)
]

onde:

- (S_e) é a família da external specification;
- (R_e) é a external revision quando relevante;
- (S_c) é a revisão do source ChrisOS;
- (T) é validation evidence.

Exemplo:

    VirtIO specification
      + revisão do protocol
      + commit do driver ChrisOS
      + evidência QEMU/device

é uma afirmação muito mais forte que "VirtIO suportado".

## Compliance versus subset implementation

Chapters de implementação do ChrisOS podem definir deliberadamente subsets pequenos de standards externos maiores.

A documentação deve distinguir pelo menos:

1. **format recognized** — parser reconhece a estrutura;
2. **subset implemented** — algumas operações funcionam;
3. **tested interoperability** — um peer/device específico passou;
4. **standards conformance** — todos os requisitos de um profile declarado são satisfeitos.

As três primeiras não estabelecem automaticamente a quarta.

Isso é especialmente importante para ELF, ACPI, USB, VirtIO, GLSL e network protocols.

## Resolução de conflitos

Quando fontes parecem divergir, use a sequência seguinte.

### Comportamento externo

Se a pergunta é "o que PCIe/UEFI/TCP exige?", vence a external normative source.

O source ChrisOS pode então ser classificado como conformante, incompleto ou incorreto.

### Comportamento do ChrisOS

Se a pergunta é "o que esta revisão do ChrisOS realmente faz?", vence o source atual do ChrisOS.

Uma página que descreve comportamento ideal do standard mas contradiz o source precisa ser corrigida ou marcada como roadmap.

### Formatos persistidos do ChrisOS

Para formatos próprios como ChrisFS, ChrisO, CLVM e CSIR, a project specification e os readers/writers atuais precisam ser reconciliados.

Se specification e implementation divergem, isso é compatibility defect; não se deve escolher silenciosamente um deles.

## Standards pagos ou access-controlled

Algumas specifications são distribuídas com restrições de acesso/licenciamento.

O catálogo pode portanto registrar title e issuing organization sem espelhar o documento.

Não copie grandes trechos de standards proprietários para o corpus.

Em vez disso:

- cite o standard;
- explique o subset usado pelo ChrisOS;
- registre fields/behavior necessários para entender o implementation;
- aponte para material público oficial quando permitido.

## Links estáveis versus títulos

URLs mudam mais frequentemente que nomes de standards.

Por isso o catálogo trata title, organization e class como identidade estável.

URL é metadata útil quando há authoritative public landing page, mas sua ausência não reduz a autoridade da source identificada.

Broken URLs devem ser reparados sem renomear a key, salvo mudança real de identidade.

## Bibliography keys

Keys como:

    intel-sdm
    amd-apm
    virtio
    rfc-9293
    glsl

são identifiers estáveis do projeto.

Devem permanecer curtas, lowercase e semanticamente duráveis.

Uma key não deve embutir revision salvo quando duas revisions precisam coexistir.

## Adicionando referência

Nova entry deve ser criada quando ao menos um substantive chapter depender de autoridade externa ainda não catalogada.

Antes de adicionar:

1. identifique o standards body, vendor ou project original;
2. prefira normative document a explanation secundária;
3. escolha key estável;
4. registre title e organization;
5. atribua authority class;
6. acrescente official URL quando conhecida com segurança;
7. cite exact revision no implementation chapter quando necessário.

Não crie duplicates para mirrors do mesmo source.

## Removendo referência

Uma referência não deve desaparecer apenas porque o code atual deixou de usá-la.

History chapters podem ainda depender dela.

Remoção faz sentido quando:

- entry está errada;
- duplica outra key;
- source foi identificada incorretamente;
- nenhum authored/historical chapter usa a source e nenhum compatibility record depende dela.

## Validação e bibliografia

Documentation build valida syntax do catálogo e integração do site; não valida o standard externo.

Claims de hardware/protocol precisam de evidência separada.

Exemplos:

- host tests para parser;
- QEMU gates;
- physical hardware records;
- differential execution;
- packet traces;
- filesystem image checks.

A bibliografia diz contra qual contrato comparar. Os tests mostram se a implementação corresponde ao contract selecionado.

## Cobertura atual do catálogo

Nesta revisão o catálogo cobre as principais authorities necessárias ao corpus ChrisOS:

- x86 e RISC-V;
- UEFI, ACPI e Limine;
- ELF, AMD64 ABI, DWARF e C;
- PCIe e VirtIO;
- NVMe, AHCI e ATA;
- USB e xHCI;
- IPv4/IPv6, ARP, UDP, TCP, DNS e DHCP;
- OpenGL, GLSL, TGSI e VirGL;
- material universitário para device physics e computation structures.

Não é uma bibliografia exaustiva de ciência da computação.

O catálogo cresce quando source tree ou curriculum introduzem dependência concreta.

## Nota de revisão

Este capítulo foi reconciliado contra o baseline ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56` e o catálogo de bibliografia mantido no repository de documentação.

External standards continuam versionados independentemente. Chapters futuros devem fixar a edição exata quando interoperability ou binary compatibility depender dela.
