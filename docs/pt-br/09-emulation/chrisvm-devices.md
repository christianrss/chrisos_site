---
id: chrisvm-devices
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.h
  - chrisvm/devices/serial/serial.c
  - chrisvm/devices/fb/fb.c
  - chrisvm/frontend/view.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - ChrisSerial
  - ChrisFb
  - chris_serial_attach
  - chris_fb_attach
  - chris_fb_get
  - chris_fb_write_image
  - chris_view_show
depends_on:
  - chrisvm-io-bus
  - chrisvm-mmio-bus
related:
  - chrisvm-machine
  - chrisvm-memory-map
  - chrisvm-boot
---

# Devices integrados do ChrisVM

## Escopo

A máquina ChrisVM atual possui um conjunto intencionalmente pequeno de devices integrados:

- serial UART-like no range tradicional de COM1;
- shutdown port próprio do projeto;
- framebuffer linear fixo;
- viewer SDL opcional no host.

O cell MMIO usado nos testes é apenas uma fixture e não um device permanente da plataforma.

Não existe ainda no ChrisVM inspecionado uma implementação madura de PCI, block device, network device, APIC/IOAPIC, teclado, timer complexo ou ACPI.

Este capítulo documenta o comportamento integrado na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Ownership

ChrisMachine embute:

    ChrisSerial serial
    ChrisFb fb

O serial registra ranges no port-I/O bus.

O framebuffer possui caminho físico dedicado e não usa o registry MMIO genérico.

Os devices, portanto, usam mecanismos diferentes de attach dentro da mesma máquina.

## Range do serial

chris_serial_attach registra:

    0x3f8 .. 0x3ff

correspondente ao COM1 tradicional.

Os três bits baixos da porta selecionam o register.

O modelo implementa comportamento suficiente para diagnóstico, captura de output e loopback.

Não é uma implementação completa e timing-accurate de 16550A.

## Estado de ChrisSerial

ChrisSerial armazena:

- ier;
- lcr;
- mcr;
- scr;
- dll;
- dlm;
- loop_data;
- loop_dr;
- buffer TX;
- tamanho TX;
- callback host opcional e contexto.

Não há FIFOs completos de RX/TX, fila de interrupts ou engine de timing.

O modelo é síncrono e orientado a registradores.

## DLAB

DLAB é o bit 7 de LCR.

Com DLAB ativo:

- offset 0 acessa DLL;
- offset 1 acessa DLM.

Com DLAB limpo:

- offset 0 é data register;
- offset 1 é IER.

Os bytes do divisor são armazenados, mas não controlam timing real de baud rate.

## Data register

Em write comum para offset zero com DLAB limpo:

- se loopback está ativo, o byte vai para loop_data;
- caso contrário, entra no buffer TX quando há capacidade;
- o host hook opcional é chamado.

Somente o low byte é usado.

Output serial torna-se observável imediatamente, sem atraso de transmissão simulado.

## Buffer TX

O buffer possui:

    CHRIS_TX_MAX = 8192

bytes.

A implementação adiciona bytes enquanto:

    tx_len + 1 < CHRIS_TX_MAX

reservando um byte para terminador null.

Quando o buffer enche, novos bytes deixam de ser adicionados ao texto armazenado.

O host hook continua sendo chamado no caminho normal, mesmo quando o buffer fixo não cresce mais.

Logo, hook e chris_serial_text podem divergir em streams muito longos.

## Host hook

chris_serial_set_hook instala callback e contexto.

Cada byte transmitido normalmente chama esse callback.

Isso permite stream de serial sem polling do buffer fixo.

O pointer pertence ao processo host e não deve ser serializado como estado da VM.

## Loopback

Bit 4 de MCR ativa o loopback simplificado.

Write no data register grava em loop_data e define loop_dr.

Read posterior retorna o byte e limpa loop_dr.

LSR bit 0 reflete a presença desse dado.

A suíte de integração verifica o round-trip guest OUT/IN.

## IER

IER é armazenado quando DLAB está limpo.

Porém, o modelo atual não usa IER para gerar IRQ.

O guest consegue ler/escrever o valor sem ganhar uma fonte real de interrupt UART.

## IIR/FCR

Offset dois em read retorna:

    0x01

indicando nenhum interrupt pending no modelo simplificado.

Writes são aceitos como FCR, mas ignorados.

Não há configuração real de FIFO.

## LCR

LCR é armazenado integralmente.

O bit DLAB altera multiplexação.

Demais bits de formato não afetam wire model porque largura de character, parity, stop bits e baud timing não são simulados.

## MCR

MCR é armazenado.

Bit 4 controla o loopback do projeto.

Outros sinais de modem não controlam hardware externo modelado.

## LSR

LSR retorna:

    0x60

como estado básico de transmitter ready.

Quando loop_data está disponível, bit 0 também é definido.

Não há modelagem detalhada de overrun, parity, framing, break ou FIFO status.

## MSR e SCR

MSR retorna zero.

SCR pode ser gravado e lido.

SCR é útil para probes de UART que verificam se o scratch register funciona.

## Simplificação de largura

O port bus preserva size, mas os callbacks serial ignoram o argumento.

serial_out reduz value para uint8_t.

Assim, operações word/dword não modelam acesso multi-register; somente o low byte importa.

Os guests atuais usam byte I/O.

## Sem timing UART

Não há modelo de:

- baud;
- atraso do shift register;
- chegada RX;
- FIFO thresholds;
- IRQ timing;
- DMA;
- scheduling de input do host.

A simplicidade favorece determinismo, não fidelidade temporal.

## Shutdown port

chris_serial_attach também registra:

    0x501

como CHRIS_SHUTDOWN_PORT.

Apesar de estar em serial.c, é conceitualmente um device de controle da máquina.

Write com low byte 0x01:

- define shutdown;
- halted na CPU;
- define CHRIS_EXIT_SHUTDOWN.

Reads retornam zero.

É um mecanismo paravirtual próprio, não ACPI.

## Framebuffer

O framebuffer fixo é:

    base física = 0x02000000
    width       = 640
    height      = 480
    bytes/pixel = 4
    pitch       = 2560
    size        = 1.228.800 bytes

chris_fb_attach cria allocation host zerada.

Não existem registers de controle guest-visible.

O guest escreve diretamente na memória de pixels.

## Pixel format

Viewer e image export interpretam o pixel de 32 bits com:

    red   = bits 23..16
    green = bits 15..8
    blue  = bits 7..0

O viewer SDL usa SDL_PIXELFORMAT_ARGB8888.

O byte alto funciona como alpha/reserved no caminho visual, enquanto PNG/PPM usa explicitamente RGB.

Os splash tests escrevem valores compatíveis com esse layout.

## Dirty tracking

Write físico totalmente dentro do framebuffer define:

    fb.dirty = 1

chris_fb_dirty expõe o estado.

Não existe dirty rectangle nem tracking por página.

Depois de definido, o flag não é limpo pelo caminho comum de write.

A frontend usa dirty para decidir se deve mostrar o framebuffer após execução.

## Leitura host de pixels

chris_fb_get valida machine, output, backing e coordenadas.

O offset é:

    y * pitch + x * 4

e um pixel de 32 bits é copiado.

É uma API de inspeção host, não um register do guest.

## Export de imagem

chris_fb_write_image escolhe formato pela extensão.

Arquivos com extensão .png usam o writer PNG próprio do projeto.

Outras extensões geram PPM binário.

O PNG monta signature, IHDR, IDAT com stored deflate blocks e IEND.

Assim, dumps não dependem de uma biblioteca PNG externa.

Esse export não altera estado do guest.

## Viewer SDL

chris_view_show funciona quando CHRIS_HAVE_SDL está disponível.

Ele:

1. copia os pixels via chris_fb_get;
2. cria janela 640x480;
3. cria software renderer;
4. cria texture ARGB8888;
5. envia pixels;
6. apresenta;
7. processa close events durante o tempo pedido.

É uma visualização de snapshot, não uma tela continuamente sincronizada com a CPU durante a mesma função.

Sem SDL, retorna falha.

## Headless

A frontend não abre o viewer quando cfg.headless está ativo.

O framebuffer continua existindo e mantém exatamente o mesmo physical layout.

Headless afeta apresentação no host, não virtual hardware.

## Consequência da base fixa

Como o framebuffer começa em 32 MiB, RAM acima disso colide.

chris_fb_attach rejeita essa máquina.

Logo, um device define atualmente o teto efetivo de RAM.

Mover placement para um machine map autoritativo é prioridade.

## Sem mode setting

O guest não programa:

- resolução;
- pitch;
- pixel format;
- base;
- refresh rate.

Não há VBE/GOP register interface nem PCI display device.

O framebuffer é um contrato preconfigurado do boot.

## Sem scanout timing

Não há:

- vblank;
- horizontal timing;
- refresh;
- display IRQ;
- tearing model;
- scanout DMA.

Writes alteram o backing imediatamente.

O viewer mostra uma cópia posterior.

## Evidência de framebuffer

test_chrisvm.c possui um teste baseado em REP STOSD.

O guest:

- aponta RDI para framebuffer;
- configura RCX;
- carrega pixel;
- executa STOS;
- halt.

O host verifica pixels e dirty flag.

Outro splash guest verifica coordenadas específicas e serial output.

Isso valida o caminho real:

    instrução
    -> paging
    -> framebuffer físico
    -> host inspection

## Device inventory versus fixture

O MMIO cell em 0x06000000 é criado dentro do teste.

chris_machine_create não o registra.

Logo, não pertence ao standard device inventory.

A lista padrão deve vir de built-in attach calls e machine construction, não de mappings experimentais usados em testes.

## Devices ausentes

A plataforma ChrisVM inspecionada ainda não oferece implementations maduras integradas de:

- local APIC;
- IOAPIC;
- PIC/PIT;
- HPET;
- PCI/PCIe root;
- storage;
- NVMe;
- virtio block;
- virtio net;
- USB;
- keyboard/mouse;
- RTC;
- ACPI power hardware.

O kernel ChrisOS pode conter drivers para várias dessas classes, mas isso não significa que ChrisVM emule o hardware correspondente.

Kernel driver inventory e virtual platform inventory são coisas diferentes.

## Gap de interrupts

Nem serial nem framebuffer geram hardware IRQ.

IER é apenas storage.

Framebuffer não possui fonte de interrupt.

Isso simplifica a máquina, mas impede driver behavior interrupt-driven realista.

Antes de devices complexos, ChrisVM precisa de uma topologia de interrupt controller.

## Reset de devices

A criação da máquina zera serial e framebuffer.

Não existe API separada de runtime reset por device.

Um futuro machine reset precisa definir quais registradores voltam ao power-on state e quais recursos host persistem.

## Snapshot

Device state não está dentro de ChrisArchitectureState.

Um snapshot completo precisa incluir ao menos:

- registradores e loopback/TX do serial;
- pixels e dirty do framebuffer;
- shutdown state;
- filas/timers de devices futuros.

Callbacks host nunca devem ser serializados diretamente.

## Prioridades de hardening

Os próximos trabalhos de maior valor são:

1. mover placement para mapa físico autoritativo;
2. implementar UART IRQ se drivers precisarem;
3. definir RX host e scheduling determinístico;
4. respeitar width/timing no UART;
5. remover teto de RAM imposto pelo framebuffer;
6. criar contrato guest-discoverable para framebuffer;
7. definir reset e snapshot de devices;
8. construir interrupt-controller layer antes de devices interrupt-driven;
9. manter fixtures de teste fora do inventory padrão;
10. adicionar device identity a traces e map;
11. só adicionar storage/network com contratos explícitos de bus, DMA e IRQ;
12. manter SDL e apresentação host fora do estado arquitetural do guest.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, a plataforma padrão do ChrisVM consiste em serial simplificado compatível com o range COM1, shutdown port próprio e framebuffer linear fixo 640x480 com dump/view host. Isso basta para diagnóstico determinístico e graphics smoke tests, mas deliberadamente não modela timing, interrupts de device, enumeration ou uma plataforma PC geral.
