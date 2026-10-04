---
id: qemu-gates
lang: pt-br
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - makefile
  - scripts/qemu.mk
  - tools/qemu_gate.py
  - tools/check_install_img.py
  - kernel/metal/start.c
  - kernel/fs/storage.c
  - kernel/fs/xhci.c
  - kernel/gfx/vgpu.c
symbols: []
depends_on:
  - host-tests
  - validation-evidence
related:
  - hardware-gates
  - driver-compatibility
  - bringup-diagnostics
  - installation-real-hardware
  - performance-measurement
---

# Arquitetura dos gates QEMU

## Escopo

O ChrisOS usa QEMU como principal camada de validação integrada entre testes algorítmicos executados no host e evidência em hardware físico.

O target agregado canônico é:

    make qemu-gates

Um gate QEMU boota a image real do ChrisOS com topologia explícita de hardware virtual, captura o log serial do guest e julga a execução por markers observáveis.

A regra central é:

    tempo decorrido não é sucesso

Um guest pode permanecer vivo enquanto a initialization falhou silenciosamente. Por outro lado, um kernel projetado para continuar executando indefinidamente não deve falhar apenas porque o runner encerrou o QEMU ao atingir o timeout.

O gate avalia, portanto, o estado registrado no log serial.

## Runner comum

O runner é:

    tools/qemu_gate.py

Cada execução fornece:

- timeout;
- caminho do serial log;
- zero ou mais markers obrigatórios;
- comando QEMU completo após `--`.

O runner inicia QEMU com `subprocess.run`.

Se QEMU ultrapassa o timeout, o runner usa o exit code sintético 124.

Um resultado é aceitável quando o code é:

    0
    ou
    124

desde que todos os markers esperados existam e nenhum marker fatal apareça.

Qualquer outro exit status do QEMU falha o gate.

O timeout é tratado como terminação controlada de um sistema operacional de longa duração, não como sucesso por si só.

## Semântica dos markers positivos

Cada gate declara strings que precisam aparecer no serial log.

Exemplos:

    cpu_online_count=4
    root ata
    cfs mounted
    ahci disk sectors=
    bdev rw ok ahci
    xhci hid ready
    virtio-gpu ready
    ChrisOS: desktop 60Hz

O marker deve provar a propriedade sob teste.

Um gate de AHCI não passa apenas porque o desktop iniciou; ele exige discovery AHCI e evidência de read/write do block device.

Um gate de instalação exige markers do installer e um segundo boot a partir do disco produzido.

## Markers fatais

O runner rejeita logs contendo os padrões fatais atuais:

    PANIC:
    EXCEPTION vector=
    double fault
    general protection
    heap corruption
    PMM corruption

A detecção fatal é independente da lista de markers positivos.

Assim, um log que atinge um marker esperado e depois entra em panic continua sendo falha.

Isso impede que corrupção tardia seja escondida por sucesso inicial.

## Modelo de evidência

Um gate QEMU estabelece a tupla:

[
Q = (R, M, D, O)
]

onde:

- (R) é a revisão exata do ChrisOS;
- (M) é a configuração de máquina/devices QEMU;
- (D) é o estado das images/discos;
- (O) é o conjunto de markers observáveis exigidos.

Alterar qualquer elemento muda o experimento.

Dizer apenas "AHCI passa no QEMU" é incompleto sem recuperar topologia e revisão testadas.

## Configuração comum x86-64

A maioria dos gates x86-64 usa:

    -M pc
    -m 2048
    -smp $(QEMU_SMP)
    -display none
    -serial file:build/qemu-test.txt
    -no-reboot
    -cpu qemu64
    -accel tcg

O default é:

    QEMU_SMP ?= 4

Portanto, o gate ATA comum também valida que quatro CPUs lógicas alcançam o marker esperado.

TCG é deliberadamente portátil e mais determinístico que exigir KVM do host.

Isso melhora portabilidade de CI, mas reduz fidelidade de timing físico.

## Gate ATA

`test-qemu-ata` é o gate integrado básico de boot x86-64.

Ele exige:

    cpu_online_count=$(QEMU_SMP)
    root ata
    cfs mounted

O disco root é conectado por IDE do QEMU.

O gate atravessa em conjunto:

- boot da image;
- handoff do Limine;
- bring-up de CPUs;
- discovery do root ATA;
- mount do ChrisFS.

Como vários subsistemas são atravessados, uma falha deve ser localizada pelo log ordenado e não atribuída automaticamente ao ATA.

## Gate AHCI

`test-qemu-ahci` cria image secundária de 32 MiB e a conecta por:

    ich9-ahci

Markers obrigatórios:

    ahci disk sectors=
    bdev rw ok ahci

O root permanece no disco normal de boot. O disco AHCI extra é, portanto, device secundário sob teste.

Essa separação permite testar o controller depois que o sistema já tem root funcional.

O marker de read/write prova mais que simples discovery PCI.

## Gate NVMe

`test-qemu-nvme` cria image de 32 MiB e conecta:

    -device nvme,serial=chris,drive=nvmedisk

Markers:

    nvme disk sectors=
    bdev rw ok nvme

O gate valida initialization do controller, discovery do namespace e I/O do block device contra o modelo NVMe do QEMU.

Não prova compatibilidade com NVMe físico arbitrário nem namespaces 4 KiB-native.

## Gate VirtIO block

`test-qemu-vblk` usa:

    virtio-blk-pci

e exige:

    virtio-blk sectors=
    bdev rw ok virtio-blk

Esse caminho exercita a camada genérica de block device com modelo baseado em queue diferente de ATA/AHCI/NVMe.

Falha comum a vários gates de storage tende a apontar para camada acima do controller específico.

## Gate USB mass storage

`test-qemu-usb` cria image de 32 MiB e a conecta por USB mass storage do QEMU.

Também conecta um USB tablet.

Markers:

    usb msc sectors=
    bdev rw ok usb

O timeout é 50 segundos, ligeiramente maior que os gates comuns de storage.

A evidência vale para o caminho USB emulado atual e não pode ser generalizada para storage xHCI arbitrário ou UAS.

## Gate VirtIO-GPU

`test-qemu-gpu` conecta:

    virtio-gpu-pci

e exige:

    virtio-gpu ready

Esse é um gate de bring-up do transporte/device.

Ele não exige a sequência mais profunda de shaders/rendering do VirGL.

Essa separação permite CI comum sem exigir ambiente OpenGL/VirGL no host.

## Gate VirGL

`test-qemu-virgl` é condicional.

Antes do boot, verifica se o QEMU do host expõe GPU VirtIO com GL e se existe display backend utilizável.

Backends possíveis incluem:

    egl-headless
    gtk,gl=on

Sem suporte necessário, o target reporta:

    SKIP: host QEMU lacks VirGL support

e termina separadamente de um pass comum.

Quando executável, exige markers para:

- negociação da feature VirGL;
- clear;
- triangle;
- cube;
- depth;
- textured cube;
- GLSL compilation;
- varying;
- lighting;
- shader switch;
- lit mesh;
- final present;
- `3D backend -> virgl`.

É um dos testes de integração gráfica mais profundos do repositório.

Porém não integra `qemu-gates`, porque CI comum não pode pressupor GL no host.

## Gate RISC-V

`test-qemu-riscv` boota:

    qemu-system-riscv64 -M virt

com VirtIO block e VirtIO GPU.

Markers incluem:

    riscv kernel
    sv39 on
    clvm halt
    virtio-blk
    virtio-gpu detected

Isso fornece diversificação arquitetural.

Não implica equivalência de features entre os kernels x86-64 e RISC-V; prova somente o caminho de bring-up representado pelos markers.

## Gate sem ATA

`test-qemu-noata` é teste de topologia negativa.

Ele remove o caminho comum de root ATA e exige:

    ata missing
    root ahci
    cfs mounted
    install selftest ok
    desktop 60Hz

Isso prova que AHCI pode assumir root em vez de apenas coexistir como device secundário.

Também prova que o sistema não depende de ATA bem-sucedido para alcançar o desktop.

Testar remoção de topologia é mais forte que apenas adicionar devices.

## Gate de instalação

`test-qemu-install` é um teste em múltiplos estágios.

### Estágio 1: instalação

O target:

1. clona uma image ChrisFS preparada;
2. insere kernel atual, BOOTX64.EFI e configuração Limine;
3. adiciona arquivos de controle de instalação automática;
4. cria target AHCI vazio de 560 MiB;
5. boota ChrisOS;
6. exige markers do installer.

Markers esperados:

    install auto
    install tree copied
    install gpt+esp+cfs disk=ahci

### Estágio 2: inspeção estrutural

Depois do primeiro boot, o host executa:

    tools/check_install_img.py

O checker valida GPT primário/backup, localização ChrisFS e entradas esperadas no ESP.

Esse parser independente evita validar um bug do installer apenas com código guest que compartilha as mesmas premissas.

### Estágio 3: boot UEFI somente pelo disco

O disco produzido é bootado novamente usando OVMF por pflash.

O segundo gate exige:

    cfs mounted
    desktop 60Hz

Assim, o disco não é apenas estruturalmente plausível: ele boota no caminho UEFI testado.

O timeout é 300 segundos por ser um experimento substancialmente mais pesado.

## Variação SMP

`test-qemu-smp1` reutiliza o gate ATA com:

    QEMU_SMP=1

O gate normal usa quatro vCPUs.

Testar ambos é útil porque alguns erros só aparecem nas transições SMP, enquanto outros ficam escondidos quando várias CPUs são esperadas.

O gate de uma CPU não faz parte de `qemu-gates`; ele é adicionado por:

    full-gates

## Gate safe mode

O build cria ISO temporária com:

    safe

na command line do Limine.

`test-qemu-safe` exige:

    safe mode
    smp off
    desktop 60Hz

Safe mode desabilita ou reduz vários caminhos opcionais.

O gate garante que a configuração de fallback continua bootável enquanto o sistema normal evolui.

É especialmente útil quando uma regressão envolve SMP, APIC, áudio, rede ou JIT.

## Gate xHCI HID

`test-qemu-xhci` conecta:

    qemu-xhci
    usb-kbd
    usb-mouse

e exige:

    xhci hid ready

O driver atual é estreito; portanto a evidência deve ser interpretada como prova do caminho HID QEMU implementado, não como afirmação geral de compatibilidade USB.

## Target agregado

A lista atual de `qemu-gates` é:

    test-qemu-ata
    test-qemu-ahci
    test-qemu-nvme
    test-qemu-vblk
    test-qemu-usb
    test-qemu-gpu
    test-qemu-riscv
    test-qemu-noata
    test-qemu-install
    test-qemu-safe
    test-qemu-xhci

Ausentes propositalmente:

    test-qemu-virgl
    test-qemu-smp1

VirGL depende do ambiente.

A variante de uma CPU entra separadamente em `full-gates`.

## Hierarquia full-gates

A composição atual é:

    host-gates
        evidência algorítmica/userspace

    qemu-gates
        evidência integrada de hardware virtual

    test-qemu-smp1
        variação uniprocessador

e:

    full-gates: host-gates qemu-gates test-qemu-smp1

A hierarquia fornece caminho natural de localização.

Se host test falha, integração QEMU não deve ser confiada.

Se host passa e QEMU falha, investigue fronteiras privilegiadas/integradas.

Se QEMU passa e hardware físico falha, investigue firmware, topologia, device-specific behavior e timing.

## Serial log como artifact

O serial log é o principal artifact dos gates.

Vantagens:

- independe de display gráfico;
- sobrevive a falha de UI;
- preserva markers de initialization em ordem;
- contém identidade da build e registros fatais;
- é simples de inspecionar em CI.

Logs de gates que falham devem ser preservados.

Uma pipeline futura pode guardar também eventos JSON, disk images, screenshots e versão do QEMU.

## Ordem e causalidade

O runner atual verifica presença, não ordem de markers.

Assim:

    A aparece
    B aparece

é equivalente a:

    B aparece
    A aparece

se ambos existirem.

Para muitos gates isso é suficiente porque markers são específicos e o boot flow torna inversão improvável.

Um runner futuro mais forte deve modelar boot como state machine ordenada e permitir exigir sequência.

Isso evita que fragments repetidos ou antigos satisfaçam um experimento incorretamente.

## Freshness do log

A maioria dos targets remove explicitamente o log antes do boot:

    rm -f build/qemu-test.txt

Isso é essencial porque a avaliação por presença pressupõe que o arquivo pertence à execução atual.

Gate futuro que append em log existente cria risco de false positive por marker antigo.

## Projeto dos timeouts

Timeouts são definidos por experimento.

Exemplos:

- storage/GPU comuns: cerca de 40 s;
- USB: 50 s;
- safe/no-ATA/xHCI: 90 s;
- VirGL: 180 s;
- installer: 300 s.

Timeout é orçamento de liveness.

Aumentá-lo reduz falsos failures em CI lento, mas valores excessivos escondem hangs e aumentam feedback time.

O valor adequado fica confortavelmente acima do runtime saudável e ainda limita deadlocks.

## Limites da evidência QEMU

Gates QEMU não reproduzem:

- firmware arbitrário;
- topologia PCIe física;
- erratas específicas de controller;
- interações reais de DMA/IOMMU;
- interrupt routing físico;
- cache/power loss de storage;
- comportamento térmico/timing do device;
- todos os efeitos de ordenação microarquitetural.

TCG também altera timing substancialmente.

Por isso, sucesso QEMU é forte evidência de integração de software, mas permanece abaixo de evidência física.

## Melhorias prioritárias

Próximas melhorias de maior valor:

1. registrar versão QEMU por artifact;
2. preservar command line completa e hashes de images;
3. exigir ordem de markers onde causalidade importa;
4. emitir eventos JSON estruturados além de serial text;
5. guardar failed logs automaticamente em CI;
6. distinguir skip explícito de pass/failure no relatório agregado;
7. adicionar mais gates de topologia negativa;
8. adicionar loops controlados de reset/reboot;
9. comparar markers entre execuções repetidas;
10. conectar cada hardware gate físico a baseline QEMU equivalente quando possível.

## Nota de revisão

Este capítulo foi reconciliado contra a revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56` do ChrisOS.

Nesta revisão, a validação QEMU é uma camada integrada substancial, com markers positivos por device, rejeição de fatal markers, variação de topologia, teste de instalação/OVMF em múltiplos estágios e separação explícita entre gates comuns e cobertura VirGL dependente do ambiente. Sucesso no QEMU deve continuar classificado como evidência de hardware virtual, não compatibilidade física.
