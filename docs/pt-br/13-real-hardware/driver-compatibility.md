---
id: driver-compatibility
lang: pt-br
type: technical-chapter
volume: 13-real-hardware
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/pci.c
  - kernel/metal/ps2.c
  - kernel/fs/storage.c
  - kernel/fs/bdev.c
  - kernel/fs/ata_pio.c
  - kernel/fs/ahci.c
  - kernel/fs/nvme.c
  - kernel/fs/virtio_blk.c
  - kernel/fs/usb_msc.c
  - kernel/fs/xhci.c
  - kernel/gfx/graphics.c
  - kernel/gfx/vgpu.c
  - kernel/gfx/ac97.c
  - kernel/net/virtio_net.c
  - scripts/qemu.mk
  - tools/qemu_gate.py
symbols:
  - pci_read
  - storage_init
  - ata_pio_identify
  - ahci_probe
  - nvme_probe
  - virtio_blk_probe
  - usb_msc_probe
  - xhci_hid_probe
  - ps2_init
  - vgpu_boot
  - ac97_init
  - virtio_net_init
depends_on:
  - hardware-profile
  - bringup-diagnostics
  - validation-evidence
related:
  - installation-real-hardware
  - qemu-gates
  - hardware-gates
  - fault-injection
---

# Compatibilidade de drivers: implementação, descoberta e evidência

## Escopo

Compatibilidade de driver no ChrisOS não é uma propriedade binária.

Uma família de controladores pode estar representada no source enquanto um dispositivo físico específico continua inutilizável porque discovery, premissas de firmware, endereçamento DMA, roteamento de interrupts, geometria de setores, layout de filas ou comportamento específico do dispositivo ficam fora do envelope implementado.

Este capítulo define o contrato de compatibilidade usado pela documentação. Ele separa quatro perguntas:

1. existe um caminho de software implementado;
2. o kernel consegue descobrir o dispositivo;
3. o caminho implementado passa em um gate determinístico de máquina virtual;
4. a mesma classe foi reproduzida em hardware físico identificado.

Somente a quarta pergunta estabelece compatibilidade física para um perfil registrado de máquina/controlador.

## Modelo de estado de compatibilidade

Para fins de documentação, cada caminho de device é descrito pela tupla de evidência:

[
C = (I, D, Q, P)
]

onde:

- (I) — a implementação existe na revisão atual;
- (D) — o caminho de discovery cobre a topologia testada;
- (Q) — um gate QEMU prova o caminho por markers positivos explícitos;
- (P) — um registro de hardware físico preso à revisão prova o caminho em uma máquina nomeada.

Os estados não são condensados propositalmente em uma única palavra como "suportado".

Por exemplo:

[
(1,1,1,0)
]

significa que o driver existe, a topologia testada é descobrível e há evidência QEMU, mas compatibilidade física ainda não foi estabelecida.

## Por que implementação é mais fraca que compatibilidade

Um driver pode conter lógica correta de protocolo e ainda falhar em uma máquina real porque o dispositivo nunca é descoberto.

Da mesma forma, um controlador descoberto ainda pode falhar porque:

- o layout dos BARs difere;
- a memória DMA não é endereçável pelo device;
- um interrupt não é roteado como esperado;
- uma fila é menor que a implementação pressupõe;
- o firmware deixa o controlador em estado inesperado;
- um disco usa tamanho lógico de setor não suportado;
- o device está atrás de uma bridge PCIe não percorrida;
- o device expõe revisão ou combinação de features não exercitada no QEMU.

Portanto, presença no source é evidência de implementação, não prova de interoperabilidade com hardware.

## Limite de discovery PCI

O ChrisOS usa o mecanismo legado de configuração PCI #1 pelos ports padrão de configuração.

Os helpers genéricos de `kernel/metal/pci.c` operam sobre coordenadas de bus, slot e function e algumas buscas auxiliares percorrem:

    bus 0
    slots 0..31
    functions 0..7

Vários drivers de subsistemas fazem sua própria varredura mais ampla.

AHCI, NVMe e VirtIO block percorrem atualmente:

    buses 0..7
    devices 0..31
    functions 0..7

O caminho VirtIO-GPU percorre buses 0..7 e devices 0..31, mas testa function 0 nessa busca.

Isso não é um enumerador genérico de fabric PCIe.

Não há bridge traversal recursivo que descubra todos os secondary/subordinate buses nem uma camada geral ECAM/MCFG que torne topologias PCIe arbitrárias visíveis.

A invariável prática é:

    protocolo do device pode estar implementado
    E
    device ainda pode estar invisível

quando está fora da topologia varrida.

## Complexidade da descoberta

Uma varredura plana sobre (B) buses, (D) devices e (F) functions tem complexidade de pior caso em leituras de configuração:

[
O(BDF)
]

Para o envelope de AHCI/NVMe/VirtIO block:

[
8 	imes 32 	imes 8 = 2048
]

coordenadas de functions são candidatas antes do filtro por class/vendor.

A abordagem atual é simples e determinística para QEMU e layouts pequenos de PC. Ela não escala como estratégia geral de PCIe porque ignora a estrutura em grafo representada pelas bridges.

Um enumerador consciente de bridges deve percorrer as arestas descobertas e validar os intervalos secondary/subordinate.

## Abstração de block devices

Drivers de storage registram devices por uma camada comum de block device.

A abstração carrega:

- tamanho do setor;
- quantidade de setores;
- função de leitura;
- função de escrita;
- operação opcional de flush;
- writability;
- tipo e flags do device.

Isso permite que filesystem, parser de partições e installer operem sem embutir lógica específica de cada controlador.

A consequência para compatibilidade é importante: um driver só se torna um dispositivo de storage viável para o ChrisOS depois que initialization do protocolo e registro do block device têm sucesso.

## Premissas globais de geometria de storage

A stack atual de storage é fortemente centrada em setores de 512 bytes.

O caminho comum de instalação e filesystem espera:

    sector_size = 512

NVMe rejeita explicitamente namespaces cujo active LBA data size não seja (2^9) bytes.

USB mass storage e VirtIO block registram setores de 512 bytes nos caminhos atuais.

A contagem comum de setores é 32-bit. Vários drivers rejeitam representações de capacidade que exigem words altas de 32 bits.

Com 512 bytes por setor, o envelope endereçável é aproximadamente:

[
2^{32} 	imes 512 = 2 	ext{TiB}
]

antes de considerar restrições do filesystem/layout.

Consequentemente, "driver NVMe implementado" não implica compatibilidade com namespaces 4 KiB-native ou devices arbitrariamente grandes.

## ATA PIO

O caminho ATA implementa acesso legado por programmed I/O e a interface clássica de registradores ATA.

Características de compatibilidade incluem:

- modelo legado de I/O ports ATA;
- command completion orientado a polling;
- setores lógicos de 512 bytes no contrato atual de storage;
- nenhuma afirmação de ampla compatibilidade com controladores SATA modernos por esse caminho.

ATA continua útil como baseline simples e gate QEMU porque sua superfície de controle é pequena e falhas são relativamente fáceis de localizar.

Ele não deve ser usado como evidência de que controladores modernos arbitrários são suportados.

## AHCI

O caminho AHCI descobre controladores PCI mass-storage que correspondem ao contrato de class/subclass/prog-if de AHCI, mapeia MMIO do controlador pela camada de hardware gate, examina ports implementados e tenta iniciar um device SATA conectado.

O probe percorre buses 0..7, devices 0..31 e functions 0..7.

A compatibilidade atual é limitada por:

- envelope finito de varredura PCI;
- modelo de registradores do controlador exercitado no QEMU;
- buffers DMA disponíveis;
- comportamento implementado de command list/FIS;
- envelope comum de sector count de 32 bits;
- devices SATA que apresentem o comportamento ATA identify esperado.

O gate QEMU de AHCI exige evidência serial explícita incluindo:

    ahci disk sectors=
    bdev rw ok ahci

Isso prova o caminho atual contra a configuração ICH9 AHCI emulada pelo gate.

Não estabelece compatibilidade com um controlador AHCI físico.

## NVMe

O caminho NVMe inicializa um controlador PCI NVMe, admin queues e uma I/O queue, identifica um namespace e o expõe como block device.

Um namespace é rejeitado quando o active LBA data size não é 512 bytes.

O caminho também rejeita capacidades fora do envelope atual de representação.

Os limites importantes incluem:

- visibilidade PCI;
- premissas sobre registers/doorbells;
- queue allocation e endereçamento DMA;
- comportamento do namespace 1 usado pela implementação;
- formato LBA de 512 bytes;
- sector count limitado.

Uma afirmação física de NVMe exige registrar PCI vendor/device ID, modelo do controlador, geometria do namespace, versão de firmware quando disponível e revisão exata do ChrisOS.

## VirtIO block

VirtIO block é um caminho de compatibilidade para device virtual, não substituto de driver de storage físico.

A implementação negocia a interface VirtIO PCI, valida capacidade da queue, aloca estado e expõe o disco virtual pela mesma camada de block device.

Ela rejeita devices quando a capacidade exige high bits não suportados e registra atualmente geometria de 512 bytes por setor.

A evidência mais forte atual para esse caminho é evidência de virtualização.

Sua presença é valiosa porque exercita a camada genérica de storage sem prender a validação a ATA/AHCI/NVMe.

## USB mass storage

A implementação atual de USB mass storage é explicitamente estreita.

O próprio source a identifica como:

    UHCI host + BOT mass storage

e declara que não é uma stack USB genérica.

O caminho usa Bulk-Only Transport e comandos no estilo SCSI para determinar capacidade e executar block I/O.

Compatibilidade, portanto, não pode ser generalizada para:

- mass storage via xHCI;
- host controllers USB arbitrários;
- UAS;
- layouts arbitrários de dispositivos USB compostos.

O driver registra blocos de 512 bytes e usa a mesma geometria limitada da stack atual.

## xHCI HID

A implementação xHCI também é propositalmente limitada.

O source descreve um caminho poll-only para:

- um teclado QEMU xHCI;
- um boot mouse.

A implementação é evidência significativa de que o ChrisOS consegue construir rings xHCI, resetar ports, configurar endpoints e traduzir reports de HID boot protocol para o input subsystem.

Ela não é uma afirmação geral de compatibilidade USB HID entre controladores xHCI e topologias físicas.

Um registro de hardware precisa identificar:

- PCI ID do xHCI;
- root port;
- velocidade negociada;
- teclado/mouse;
- markers de ready observados;
- comportamento sustentado de input após o desktop iniciar.

## Input PS/2

A inicialização PS/2 contém esperas limitadas para prontidão de input/output do controller e trata input como caminho opcional da plataforma.

Um sistema sem PS/2 utilizável ainda pode ser viável se outro caminho de input funcionar.

Falha de PS/2 deve, portanto, ser registrada como resultado de uma classe de device, não automaticamente como falha de boot da máquina inteira.

Para bring-up físico inicial, PS/2 continua atraente porque evita a complexidade de controladores USB.

## Gráficos por framebuffer

O limite fundamental de compatibilidade gráfica é o framebuffer de boot.

O ChrisOS exige um framebuffer fornecido pelo Limine e atualmente exige 32 bits por pixel.

Esse caminho depende mais do handoff firmware/bootloader do que de um driver nativo de GPU.

Assim, uma máquina pode exibir o desktop do ChrisOS sem que o ChrisOS contenha driver nativo para sua GPU moderna, desde que firmware e Limine exponham framebuffer compatível.

A distinção deve permanecer explícita:

    framebuffer funciona

não equivale a:

    GPU nativa suportada.

## VirtIO GPU e VirGL

VirtIO GPU é um caminho gráfico orientado a virtualização.

A implementação negocia features VirtIO e pode solicitar a feature VirGL.

VirGL só é usado quando a feature é negociada e capsets válidos estão disponíveis; caso contrário, a stack pode retornar ao rendering em software.

O source emite evidências como:

    VIRGL feature: yes/no
    3D backend -> virgl
    3D backend -> software
    VirGL failure

Compatibilidade deve ser reportada no backend realmente selecionado, não inferida apenas pela presença do device.

## Áudio

O caminho nativo de áudio atual mira AC97.

AC97 é útil para QEMU e experimentos com hardware legado, mas não representa os controladores High Definition Audio presentes na maioria dos sistemas modernos.

Nenhuma documentação deve converter a existência de `ac97_init` em afirmação de suporte geral a áudio de PC.

Uma máquina pode ser classificada como compatível para boot mesmo quando áudio permanece indisponível.

## Rede

O caminho de NIC implementado é VirtIO network.

Isso estabelece target útil para rede em máquina virtual, mas não fornece ampla cobertura de NICs bare metal.

Controladores Ethernet físicos de Intel, Realtek, Broadcom e outros exigem drivers próprios antes que compatibilidade física de rede possa ser afirmada.

Rede é, portanto, capacidade opcional no perfil atual de hardware físico.

## Evidência fornecida pelos gates QEMU

`scripts/qemu.mk` contém gates dedicados para caminhos como:

- ATA;
- AHCI;
- NVMe;
- VirtIO block;
- USB;
- VirtIO GPU;
- xHCI;
- instalação;
- variantes safe/SMP;
- cobertura condicional de VirGL.

O gate runner exige markers seriais positivos e rejeita markers fatais.

Isso é mais forte do que apenas observar que o QEMU permaneceu executando até um timeout.

Um gate estabelece:

    implementação + topologia virtual testada + comportamento observável esperado

para a revisão testada.

Ele não estabelece compatibilidade com hardware físico.

## Registro de compatibilidade física

Um resultado físico deve capturar no mínimo:

| Campo | Evidência requerida |
|---|---|
| Revisão ChrisOS | commit Git e identidade do kernel |
| Máquina | fabricante e modelo |
| Firmware | fabricante, versão, modo UEFI/legacy |
| Secure Boot | estado enabled/disabled |
| CPU | modelo e número de CPUs lógicas |
| Device PCI | bus/device/function, vendor/device IDs |
| Controlador | modelo/classe sob teste |
| Mídia | modelo, capacidade, logical sector size |
| Boot flags | command line exata |
| Discovery | markers seriais provando visibilidade |
| Operação | evidência específica de read/write/input/render/network |
| Falha | último marker de sucesso e contexto fatal |
| Repetição | número de repetições cold/warm bem-sucedidas |

Uma afirmação sem provenance de revisão é anedota temporária, não evidência sustentável.

## Classes de compatibilidade

A documentação usa as seguintes classes:

| Classe | Significado |
|---|---|
| Implementado | caminho existe no source e é alcançável |
| Validado no QEMU | gate virtual determinístico passa |
| Observado fisicamente | ao menos uma máquina identificada passou procedimento registrado |
| Hardware-gated | automação física repetível existe |
| Não suportado | não há implementação atual ou existe incompatibilidade explícita |

"Observado fisicamente" é propositalmente mais fraco que "hardware-gated".

O segundo exige repetibilidade e artifacts retidos.

## Classificação de falhas

Um teste de driver deve registrar a primeira camada que falhou:

1. device invisível para discovery PCI/firmware;
2. controlador visível, mas class/vendor rejeitado;
3. setup de BAR/MMIO falhou;
4. alocação DMA/queue falhou;
5. reset/init do controlador expirou;
6. device/namespace/port não apareceu;
7. geometria ou feature set rejeitada;
8. operação block/input/network falhou;
9. subsistema superior falhou depois do driver ficar ready.

Essa ordem impede que sintomas posteriores sejam confundidos com falhas de discovery.

## Limite de segurança em compatibilidade de storage

Testes de storage podem ser destrutivos.

A inicialização atual pode executar testes write/read/restore em discos graváveis não-root, e discovery de device em branco pode formatar um device suficientemente vazio.

Por isso, testes físicos de storage devem usar mídia descartável ou target dedicado até que a política de probing se torne read-only por padrão.

Uma matriz de compatibilidade nunca deve recomendar teste contra disco com dados valiosos.

## Drift por revisão

Compatibilidade é presa à revisão.

Mudanças em qualquer item abaixo podem invalidar resultados anteriores:

- enumeração PCI;
- tratamento de bootloader/BootInfo;
- alocação de memória física;
- tradução DMA;
- setup de interrupts/APIC;
- layout de queues;
- geometria de filesystem;
- timeouts;
- configuração da máquina QEMU.

A revisão registrada neste capítulo faz parte do contrato técnico, não é decoração de metadados.

## Matriz atual na revisão analisada

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, a fronteira de evidência é:

| Caminho | Implementado | Evidência QEMU | Evidência física no repositório |
|---|---:|---:|---:|
| ATA PIO | sim | sim | não estabelecida |
| AHCI | sim | sim | não estabelecida |
| NVMe | sim | sim | não estabelecida |
| VirtIO block | sim | sim | device virtual |
| UHCI + USB BOT mass storage | sim | sim | não estabelecida |
| teclado/mouse PS/2 | sim | parcial/integração | não estabelecida |
| xHCI boot HID | sim | sim | não estabelecida |
| framebuffer Limine | sim | sim | não estabelecida como matriz |
| VirtIO GPU | sim | sim | device virtual |
| VirGL | sim | condicional | device virtual |
| AC97 | sim | caminho de integração | não estabelecida |
| VirtIO network | sim | caminho de integração | device virtual |
| GPU moderna nativa | não | não | não |
| HDA | não | não | não |
| famílias gerais de NIC física | não | não | não |

A tabela descreve evidência presente no repositório inspecionado. Ela não é promessa de que todo device de uma classe implementada funcione.

## Trabalho de maior valor

As próximas melhorias são estruturais, não simples adição de nomes de drivers:

1. bridge traversal PCI recursivo;
2. enumeração ACPI MCFG/ECAM;
3. export estável de identidade PCI no boot log;
4. modo read-only de hardware discovery;
5. modelo/serial/capacidade em storage;
6. registros físicos de AHCI e NVMe;
7. registros físicos de xHCI;
8. hardware-gate automatizado com serial capture e power/reset;
9. HDA somente depois de estabilizar evidência de boot/storage/input;
10. drivers de NIC física somente acompanhados de gates repetíveis.

## Nota de revisão

Este capítulo foi reconciliado contra a revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56` do ChrisOS.

O source atual contém cobertura substancial de drivers e gates QEMU explícitos, mas o repositório ainda não contém matriz geral de compatibilidade com hardware físico. Afirmações de compatibilidade devem permanecer limitadas aos caminhos implementados, limites de discovery e classe exata de evidência disponível para cada device.
