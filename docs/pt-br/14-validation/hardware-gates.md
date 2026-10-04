---
id: hardware-gates
lang: pt-br
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/start.c
  - kernel/metal/serial.c
  - kernel/metal/buildid.c
  - kernel/metal/klog.c
  - kernel/metal/panic.c
  - kernel/metal/bootinfo.c
  - kernel/metal/pci.c
  - kernel/metal/acpi.c
  - kernel/fs/storage.c
  - scripts/qemu.mk
symbols:
  - kstart
  - serial_init
  - build_info_log
  - klog_copy
  - panic
  - panic_exception
  - bootinfo_init
  - pci_read
  - acpi_probe
  - storage_init
depends_on:
  - qemu-gates
  - driver-compatibility
  - bringup-diagnostics
related:
  - installation-real-hardware
  - hardware-profile
  - fault-injection
  - performance-measurement
---

# Validação em hardware físico e hardware gates

## Escopo

Validação em hardware físico é a camada de evidência mais alta atualmente definida para compatibilidade de devices e plataforma no ChrisOS.

Na revisão analisada, o ChrisOS contém logging, identidade de build, markers de boot e drivers suficientes para realizar testes físicos disciplinados.

Ele **ainda não contém** um harness automatizado de hardware físico integrado ao repositório equivalente a `tools/qemu_gate.py`.

A distinção é fundamental:

    testável em hardware != hardware-gated

Um boot observado manualmente pode estabelecer evidência para uma máquina e revisão específicas.

Hardware gate exige um controlador repetível ao redor da máquina: power/reset, deployment da image, captura serial, identidade da máquina, avaliação de markers e artifacts preservados.

## Hierarquia de evidência

A camada física deve ser interpretada depois das camadas inferiores:

    source presente
        -> host tested
        -> QEMU tested
        -> observado fisicamente
        -> hardware gated

Cada promoção acrescenta realismo ambiental.

Ela não elimina os testes inferiores.

Um AHCI físico que passa deve continuar apoiado pelos host tests de filesystem e pelo gate AHCI do QEMU, pois essas camadas localizam falhas com custo menor.

## Tupla mínima de evidência

Um resultado físico deve ser representado por:

[
H = (R, M, F, D, C, O)
]

onde:

- (R) — revisão Git e hash do kernel;
- (M) — identidade da máquina;
- (F) — identidade e modo do firmware;
- (D) — identidade do device testado;
- (C) — condições exatas de boot/configuração;
- (O) — observações ordenadas e resultado.

Sem (R), o resultado não é reproduzível depois que o código muda.

Sem (D), o resultado não estabelece compatibilidade do device.

## Provenance da build

O ChrisOS emite identidade da build no início do boot.

O registro atual inclui:

- Build ID;
- revisão Git;
- data;
- versão do compiler;
- SHA-256 embutido na image linkada do kernel.

O log já fornece uma chave forte para ligar resultado físico ao source.

Um registro deve copiar o bloco completo em vez de depender de uma versão escrita manualmente.

## Dependência serial precoce

O canal mais precoce atual é COM1 legado em:

    0x3f8

`serial_init` configura UART e executa loopback.

Se o loopback falha, `kstart` desabilita interrupts e entra em halt.

Há duas consequências:

1. uma máquina com serial compatível oferece excelente observabilidade precoce;
2. uma máquina sem COM1 compatível pode parar antes dos diagnósticos posteriores, mesmo que outras partes da plataforma fossem utilizáveis.

Os primeiros hardware gates devem preferencialmente usar máquina com COM1 real ou bridge confiável.

Um fallback futuro por framebuffer/debug port ampliaria o conjunto de máquinas testáveis.

## Contrato de captura serial

Um hardware gate real precisa de captura serial externa.

O sistema de captura deve:

- abrir serial antes de reset/power-on;
- registrar bytes crus com timestamps;
- evitar transformações do terminal;
- preservar log completo;
- associar o log a um run ID;
- distinguir perda/desconexão de guest failure.

A sessão deve iniciar antes do handoff do firmware, pois ausência do primeiro marker do ChrisOS também é evidência.

## Markers e estágios de boot

O gate físico deve avaliar milestones ordenados.

Estágios úteis já emitidos incluem:

1. build identity;
2. BootInfo/HHDM/framebuffer/memory map;
3. CPU topology;
4. SMP online ou safe mode;
5. ACPI observations;
6. discovery de storage;
7. root selecionado;
8. ChrisFS mounted;
9. desktop ready;
10. markers opcionais de device.

O critério de pass precisa ser específico à capacidade.

Gate de storage deve exigir discovery do controller e operação bem-sucedida, não apenas desktop.

## Evidência fatal

Hardware gates devem rejeitar as mesmas classes fatais do QEMU e preservar contexto arquitetural.

O kernel atual emite:

    PANIC:
    EXCEPTION vector=

e pode incluir:

- vector;
- error code;
- RIP;
- CR2;
- CPU;
- CR3;
- RSP;
- Build ID;
- Git;
- SHA-256 do kernel.

Isso já transforma muitas falhas físicas em artifacts presos à revisão.

Depois de marker fatal, o run não pode continuar classificado como saudável, mesmo se marker de sucesso apareceu antes.

## Log em memória

Serial é espelhado para ring de kernel de 8192 bytes.

Depois que ChrisFS está disponível, o boot tenta persistir parte do log em:

    SYS/BOOT.LOG

Isso é artifact secundário útil.

Não substitui captura serial externa porque:

- ring pode sobrescrever início;
- boot pode falhar antes do mount;
- falha de filesystem pode impedir persistência;
- crash pode ocorrer antes da escrita.

Serial externa continua canal principal.

## Identidade da máquina

Um registro físico deve identificar ao menos:

| Campo | Categoria |
|---|---|
| Fabricante/modelo | motherboard ou sistema completo |
| CPU | modelo exato |
| RAM | capacidade/topologia relevante |
| Firmware | fabricante/versão |
| Boot mode | UEFI/legacy |
| Secure Boot | enabled/disabled |
| GPU/framebuffer | caminho visível ao firmware |
| Storage controller | PCI ID/modelo |
| Storage device | modelo/serial/geometria |
| USB controller | PCI ID/modelo quando testado |
| Network/audio | identidade do device quando testado |

"Testado em um PC" não é evidência suficiente.

## Identidade PCI

Compatibilidade física deve ser ligada a PCI identities concretas quando aplicável.

A descoberta PCI atual é incompleta:

- alguns helpers genéricos percorrem somente bus 0;
- alguns drivers executam varreduras planas mais amplas;
- não há bridge traversal recursivo geral;
- não há enumerador geral ECAM/MCFG.

Assim, protocolo pode estar implementado e o device continuar invisível em uma topologia específica.

O registro deve incluir bus/device/function e vendor/device IDs quando possível.

## Evidência de firmware

Firmware é fonte importante de divergência em relação ao QEMU.

O boot depende de Limine e espera:

- framebuffer response;
- HHDM;
- memory map;
- multiprocessor information.

Um registro físico deve preservar:

- firmware version;
- UEFI/legacy;
- Secure Boot;
- geometria do framebuffer;
- resumo do memory map;
- CPU count.

Falha antes da initialization dos devices pode então ser classificada como falha de platform/boot contract, não driver.

## Evidência ACPI

O código ACPI atual é diagnóstico e limitado.

Ele procura RSDP no range físico legado e reporta algumas tabelas XSDT:

    APIC
    MCFG
    FACP

O log físico deve guardar esses markers.

A presença ajuda no diagnóstico da plataforma, mas o ChrisOS ainda não consome descrição completa de ACPI/PCIe.

Ausência ou discovery parcial deve ser registrada como limitação, não ignorada.

## Segurança em storage

Testar storage físico é perigoso na revisão atual.

A initialization pode executar write/read/restore em devices graváveis não-root.

Discovery de device vazio também pode formatar um device suficientemente zerado ao procurar root.

Hardware gate deve usar:

- mídia descartável;
- disco dedicado;
- ou clone isolado.

Nunca deve apontar para disco contendo dados valiosos.

Modo read-only futuro é pré-requisito para ampliar testes físicos com segurança.

## Procedimento para storage

Um gate físico mínimo de AHCI ou NVMe deve:

1. identificar controller e disk;
2. registrar logical sector size/capacity;
3. bootar image ChrisOS presa à revisão;
4. capturar serial desde power-on;
5. exigir discovery do controller;
6. exigir registro do block device;
7. exigir marker conhecido de read/write em mídia dedicada;
8. exigir mount quando testando root;
9. rebootar;
10. verificar persistência ou discovery saudável repetido;
11. preservar log e machine record.

Um único marker de detecção não é suficiente.

## Procedimento para input

Para PS/2 ou xHCI HID, "ready" sozinho não basta.

O gate deve verificar:

- discovery do controller;
- entrega de keyboard events;
- press/release;
- mouse motion/buttons quando aplicável;
- input sustentado após desktop;
- ausência de fatal markers durante interação.

Testes de input exigem estímulos reproduzíveis.

Harness maduro pode usar emulador/relay USB programável em vez de interação humana.

## Procedimento gráfico

O caminho físico gráfico base é framebuffer fornecido pelo Limine.

Um gate deve registrar:

- address;
- width;
- height;
- pitch;
- bpp;
- marker de desktop;
- presentation repetida sem corrupção.

Isso **não** prova native GPU driver.

Compatibilidade com GPU moderna nativa permanece fora da implementação atual.

## Rede e áudio

Rede atual é orientada a VirtIO e o target de áudio nativo é AC97.

Não representam famílias amplas de hardware moderno.

Uma máquina pode passar core boot/storage/input enquanto network ou audio permanece indisponível.

A matriz deve classificar capacidades separadamente em vez de reduzir a máquina a um único bit.

## Observação manual versus hardware gate

As classes devem permanecer distintas.

### Observado fisicamente

Pessoa executa procedimento, captura logs e registra identidade da máquina.

É evidência válida quando provenance é completa.

### Hardware-gated

Controlador automatizado repete o experimento sem interpretação manual.

Deve controlar ou observar:

- seleção/deployment da image;
- power cycle/reset;
- boot target;
- serial capture;
- timeout;
- positive markers;
- fatal markers;
- artifact upload;
- machine identity;
- status final.

O ChrisOS atual oferece metodologia para a primeira classe, não automação de repositório para a segunda.

## Contrato proposto para runner

Um runner futuro deve aceitar conceitualmente:

    --machine <profile>
    --image <artifact>
    --serial <device>
    --timeout <seconds>
    --expect <marker>...
    --fatal <marker>...
    --power-cycle <backend>

e gerar resultado estruturado:

    run_id
    machine_id
    firmware
    git_revision
    kernel_sha256
    image_sha256
    timestamps
    markers observados em ordem
    fatal marker
    serial artifact
    pass/fail/infra-error

Falha de infraestrutura precisa ser distinta de guest failure.

Cabo serial desconectado não é regressão do ChrisOS.

## Controle de power/reset

Hardware gate repetível precisa de reset determinístico.

Mecanismos possíveis:

- PDU gerenciável;
- relay no header de power/reset;
- BMC/IPMI/Redfish;
- USB relay em rede;
- reset line de placa de desenvolvimento.

O requisito não é a marca.

É conseguir estabelecer estado conhecido e repetir o mesmo experimento.

## Gestão da mídia de boot

O runner precisa saber exatamente qual image bootou.

Um caminho robusto:

1. grava image em mídia dedicada;
2. calcula hash do artifact;
3. seleciona boot device;
4. registra image hash;
5. impede reutilização silenciosa de mídia antiga.

Sem identidade da image, a build identity do serial pode revelar mismatch, mas o gate deve detectá-lo automaticamente.

## Repetição

Hardware pode falhar intermitentemente.

Um único boot prova possibilidade, não confiabilidade.

Para hardware gate, use várias tentativas:

[
p_{obs} = rac{	ext{tentativas bem-sucedidas}}{	ext{tentativas totais}}
]

Isso não é estimativa estatística completa de reliability, mas torna flakiness visível.

Cold boots, warm resets e operações de devices devem ser contados separadamente.

## Localização de falhas

Quando gate físico falhar:

1. preservar primeiro failing log;
2. identificar último marker confirmado;
3. comparar com gate QEMU equivalente;
4. repetir safe mode quando aplicável;
5. mudar uma dimensão por vez;
6. repetir na mesma revisão;
7. classificar a fronteira antes de alterar código.

Quando host/QEMU passam e hardware físico falha de forma consistente, a investigação se desloca para firmware, topologia, timing e premissas específicas do device.

## Regra para compatibility matrix

Entrada de matrix nunca deve ser inferida pelo nome do driver.

Precisa de evidence record concreto.

Estados recomendados:

    implemented
    qemu-validated
    physically observed
    hardware-gated
    known incompatible
    not tested

Isso preserva incerteza em vez de converter ausência de evidência em suporte.

## Estado atual

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`:

- build identity presa à revisão existe;
- logging COM1 precoce existe;
- contexto de fatal exception existe;
- markers de boot existem;
- avaliação por markers no QEMU existe;
- documentação de hardware profile existe;
- evidência física manual pode ser registrada de forma rigorosa;
- nenhum runner geral automatizado de hardware físico foi encontrado no repositório inspecionado;
- nenhuma broad physical compatibility matrix mantida foi estabelecida.

## Próximos passos de maior valor

A sequência mais útil é:

1. escolher uma máquina de desenvolvimento com COM1 acessível;
2. adicionar hardware discovery não destrutivo;
3. registrar identidade PCI/device completa;
4. validar framebuffer + safe mode;
5. estabelecer primeiro resultado físico AHCI ou NVMe com mídia descartável;
6. automatizar serial capture;
7. automatizar reset/power cycle;
8. armazenar machine profile/artifacts;
9. promover procedimento a hardware gate repetível;
10. expandir uma classe de device por vez.

## Nota de revisão

Este capítulo foi reconciliado contra a revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56` do ChrisOS.

O ChrisOS já fornece provenance e diagnóstico serial suficientes para validação bare metal disciplinada, mas compatibilidade física ainda é tarefa de coleta de evidência, não um gate automatizado no repositório atual. Afirmações devem distinguir observação manual de hardware gating repetível.
