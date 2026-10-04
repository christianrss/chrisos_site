---
id: chrisvm-io-bus
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.h
  - chrisvm/buses/io.c
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/devices/serial/serial.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - ChrisIoSlot
  - chris_io_map
  - chris_io_in
  - chris_io_out
  - do_io
depends_on:
  - chrisvm-memory-map
  - x86-decoding
related:
  - chrisvm-mmio-bus
  - chrisvm-devices
  - chrisvm-machine
---

# Barramento de port I/O do ChrisVM

## Escopo

O ChrisVM modela o address space de port I/O x86 separadamente da memória física. O barramento conecta instruções IN/OUT decodificadas a callbacks de devices registrados usando port numbers de 16 bits.

A implementação atual é compacta:

- oito slots;
- ranges inclusivos;
- acessos de byte, word e dword;
- dispatch pelo primeiro match;
- comportamento tolerante para portas sem device.

Isso é suficiente para serial e shutdown usados pelos guests atuais, mas ainda não modela checks de privilégio, TSS I/O bitmap, string I/O, PCI configuration complexa ou registry escalável.

Este capítulo documenta a revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Address space separado

Port I/O não passa por chris_phys_read/chris_phys_write.

O caminho é:

    instrução IN/OUT do guest
      -> decode.c
      -> do_io()
      -> chris_io_in/chris_io_out
      -> callback do ChrisIoSlot correspondente

O endereço é uma porta de 16 bits independente de virtual-memory translation e de RAM/MMIO.

O mesmo número pode existir simultaneamente como physical memory address e I/O port sem conflito porque são espaços arquiteturais diferentes.

## Estrutura de registro

Cada ChrisIoSlot guarda:

- used;
- start;
- end;
- callback de input;
- callback de output;
- contexto opaco.

O range é inclusivo:

    start <= port <= end

A máquina possui:

    ChrisIoSlot io[CHRIS_IO_MAX]

com:

    CHRIS_IO_MAX = 8

Não há allocation dinâmica no lookup.

## Registro

chris_io_map valida apenas:

- machine não nula;
- start <= end.

Depois seleciona o primeiro slot livre.

Falha quando os oito slots estão ocupados.

Não verifica:

- overlap com ranges existentes;
- callback input nulo;
- callback output nulo;
- requisitos de largura específicos do device.

Esses pontos são fronteiras atuais do contrato.

## Dispatch por primeiro match

find_io percorre os slots do zero para cima.

O primeiro range usado que contém a porta vence.

Assim, overlap não é ambíguo para o código, mas é resolvido por ordem de registro.

Isso cria prioridade implícita. Uma plataforma mais madura deve rejeitar overlap acidental ou definir prioridade explicitamente.

## Larguras aceitas

chris_io_in e chris_io_out aceitam:

    1 byte
    2 bytes
    4 bytes

Qualquer outro tamanho é rejeitado.

Isso corresponde às formas escalares implementadas de:

- IN AL;
- IN AX;
- IN EAX;
- OUT AL;
- OUT AX;
- OUT EAX.

Não há port I/O de 64 bits.

## IN/OUT com porta imediata

O decoder reconhece:

    E4 E5 E6 E7

Essas formas carregam uma porta imediata de 8 bits.

O decoder marca:

    imm_src = 1
    imm_bytes = 1

do_io usa:

    imm & 0xff

Portanto, a forma imediata alcança diretamente portas 0x00..0xff.

## IN/OUT com DX

Também são reconhecidos:

    EC ED EE EF

Nessas formas, do_io usa:

    RDX & 0xffff

como port number.

Assim, todo o address space de 16 bits é alcançável por DX.

Somente os dezesseis bits inferiores importam.

## Seleção de largura do operando

As formas byte E4/E6/EC/EE forçam os igual a um.

As formas não-byte usam o operand-size state:

- 32 bits por padrão;
- prefixo 0x66 seleciona 16 bits quando aplicável.

do_io converte:

    os 1 -> size 1
    os 2 -> size 2
    demais -> size 4

REX.W não produz semântica de IN/OUT de 64 bits.

## Semântica do acumulador

IN grava o valor retornado na família do accumulator por chris_write_gpr.

Conforme a largura, o destino é efetivamente:

- AL;
- AX;
- EAX.

OUT lê a largura correspondente por chris_read_gpr.

O bus recebe somente os bits baixos arquiteturalmente selecionados.

## Leitura de porta não mapeada

Quando nenhum slot corresponde ao IN, chris_io_in retorna sucesso com all-ones:

    1 byte -> 0xff
    2 bytes -> 0xffff
    4 bytes -> 0xffffffff

Isso permite probing de hardware legado sem exception ou exit do emulador.

O valor é comportamento observável da plataforma.

## Escrita em porta não mapeada

OUT em porta sem mapping retorna sucesso e descarta o valor.

A política é permissiva para não encerrar guests por writes legacy desconhecidos.

Qualquer mudança futura é guest-visible.

## Largura é preservada nos callbacks

Diferentemente do generic MMIO atual, port I/O entrega a largura original ao callback.

Um OUT de 2 bytes gera uma única chamada contendo:

    port
    size = 2
    value

O bus, portanto, preserva melhor a transaction width.

O device pode ignorá-la, como ocorre em partes do serial atual.

## Range serial integrado

chris_serial_attach registra:

    0x3f8 .. 0x3ff

para o UART-like serial.

É o range tradicional de COM1.

O modelo inclui partes de:

- divisor latch;
- interrupt-enable storage;
- line control;
- modem control;
- scratch;
- status;
- loopback;
- captura TX pelo host.

Não é uma implementação timing-accurate de 16550.

## Loopback serial

Quando o bit de loopback no modem control está ativo, writes no data register vão para loop_data em vez do buffer host.

Uma leitura seguinte recupera o byte e limpa o marcador de data ready.

test_chrisvm.c exercita o caminho completo:

    decoder
    -> do_io
    -> bus
    -> serial callback
    -> accumulator

É evidência end-to-end real do port bus.

## Simplificação de largura no serial

serial_in e serial_out recebem size, mas ignoram o argumento.

serial_out reduz value para uint8_t.

Logo, um OUT word ou dword ao serial usa somente o low byte no modelo atual.

Isso serve aos guests existentes, mas não deve ser descrito como comportamento completo de UART.

## Shutdown port

A máquina registra:

    CHRIS_SHUTDOWN_PORT = 0x501

O callback verifica o low byte do valor.

Quando é 0x01:

- machine->shutdown vira 1;
- exit_reason vira CHRIS_EXIT_SHUTDOWN;
- a CPU é halted.

É uma convenção paravirtual própria do ChrisVM, independente de ACPI.

## Capacidade fixa

Serial e shutdown já consomem dois dos oito slots.

Restam seis para outros devices.

Sem crescimento dinâmico, uma plataforma com timers, PIC compatibility, PCI config e dispositivos adicionais pode atingir o limite rapidamente.

CHRIS_IO_MAX deve ser visto como constante de bring-up.

## Overlap

Se um novo device registrar:

    0x3f8 .. 0x3f8

depois do serial, ambos os slots existem.

Como find_io encontra o serial primeiro, o novo mapping fica inacessível naquela porta.

Mudar a ordem muda o owner.

Esse tipo de prioridade escondida pode mascarar erros de configuração.

## Callbacks nulos

chris_io_map não exige callbacks não nulos.

Se uma porta casar com um slot e o callback da direção usada for null, o dispatch tenta chamá-lo.

Os devices internos fornecem handlers válidos, mas a API genérica não garante essa invariável.

O desenho deve rejeitar handlers ausentes ou definir comportamento seguro para ranges read-only/write-only.

## Sem unregister

Não há API para remover mapping de I/O.

Também não existe replacement ou hook de lifecycle do slot.

Isso é suficiente para topologia estática, mas limita hotplug e testes com reconfiguração.

## Ausência de privilege enforcement

O caminho IN/OUT não verifica:

- CPL;
- IOPL em RFLAGS;
- TSS I/O-permission bitmap.

Se a instrução decodifica, do_io acessa o barramento independentemente do privilege level.

Em x86 real, acesso não autorizado pode gerar #GP.

Essa é uma das principais lacunas arquiteturais do port-I/O atual.

## Sem string I/O

A revisão inspecionada implementa opcodes escalares E4-E7 e EC-EF.

Não existe caminho ChrisVM para INS/OUTS.

Consequentemente, REP string I/O, DF e repeated I/O interruptível não são implementados.

Suporte a STOS em outra parte do executor não implica suporte genérico a string I/O.

## Sem TSS I/O bitmap

ChrisArchitectureState reserva TR, mas não existe TSS completo em funcionamento.

Logo, o bus não consegue consultar guest TSS I/O bitmap.

Implementar ring-3 I/O correto exige tanto privilege logic quanto task-state funcional.

## Trace assimétrico

do_io possui log para output quando trace_io está ativo.

O caminho observado registra uma linha genérica "io out".

IN não tem logging equivalente no mesmo helper.

Portanto, trace_io ainda não é um trace simétrico de transactions.

Um trace de device útil deveria incluir:

- direção;
- porta;
- largura;
- valor;
- owner do device.

## Propagação de falhas

Um callback mapeado pode retornar falha.

chris_io_in/out propaga esse status para do_io, e do_io para o executor.

Se não houver outro fault/exit explícito, o loop pode converter o problema em CHRIS_EXIT_EXCEPTION.

Não existe exception x86 dedicada para "callback de device virtual falhou".

Cada device precisa distinguir falha guest-visible de erro interno do emulador.

## Bus versus device

O barramento deve ser entendido como transporte e roteamento.

Ele define:

- owner do range;
- largura válida;
- callback chamado;
- fallback para portas ausentes.

A semântica dos registradores pertence ao device.

Essa separação precisa permanecer clara conforme novos devices forem adicionados.

## Testes atuais

A suíte executa guest code que:

- configura serial loopback;
- escreve byte;
- lê de volta com IN;
- verifica accumulator;
- lê porta não mapeada e espera 0xff;
- escreve 0x01 no shutdown port e espera CHRIS_EXIT_SHUTDOWN.

Faltam testes amplos para:

- forms de 16/32 bits;
- overlap;
- slot exhaustion;
- handlers nulos;
- privilege checks;
- string I/O;
- callback failure.

## Fronteira com ChrisHV

Um futuro ChrisHV precisará provavelmente receber VM exits de port I/O e encaminhá-los ao mesmo bus.

O contrato lógico deve ser backend-independent.

VMX/SVM deverá produzir a mesma descrição de transaction:

    port
    direction
    width
    value

em vez de criar uma segunda implementação de devices.

## Prioridades de hardening

Os próximos passos de maior valor são:

1. implementar CPL/IOPL/TSS I/O-bitmap;
2. rejeitar overlaps acidentais;
3. definir read-only/write-only com segurança;
4. remover ou tornar deliberado o limite de oito slots;
5. adicionar unregister/reset se devices dinâmicos forem necessários;
6. implementar INS/OUTS e REP;
7. tornar trace_io simétrico e detalhado;
8. testar byte/word/dword para immediate e DX;
9. testar exhaustion e overlap;
10. classificar callback failure explicitamente;
11. reutilizar o mesmo transaction interface em VMX/SVM;
12. centralizar e versionar as portas internas da plataforma.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, o port-I/O bus do ChrisVM fornece um caminho funcional de IN/OUT escalar, preserva largura de acesso, usa first-match determinístico e possui comportamento permissivo para portas ausentes. Serial e shutdown funcionam end-to-end. As principais lacunas são ausência de privilege checks x86, capacidade fixa, overlap implícito, falta de string I/O e trace incompleto.
