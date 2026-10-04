---
id: chrisvm-machine
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/config.c
  - chrisvm/machine/boot.c
  - chrisvm/buses/io.c
  - chrisvm/buses/mmio.c
  - chrisvm/devices/serial/serial.c
  - chrisvm/devices/fb/fb.c
symbols:
  - ChrisMachine
  - ChrisConfig
  - ChrisCpu
  - chris_machine_create
  - chris_machine_destroy
  - chris_run
  - chris_backend_by_name
  - chris_phys_read
  - chris_phys_write
depends_on:
  - chris-architecture-state
  - chrisvm-chriscpu
related:
  - chrisvm-memory-map
  - chrisvm-io-bus
  - chrisvm-mmio-bus
  - chrisvm-devices
  - chrisvm-boot
---

# ChrisMachine: ownership, ciclo de vida e fronteiras da plataforma

## Escopo

ChrisMachine é o container runtime de mais alto nível da plataforma ChrisVM atual. Ele possui os objetos que transformam um fluxo de instruções em uma máquina executável: RAM, seleção do backend de CPU, uma instância de CPU, registros de I/O e MMIO, estado serial, framebuffer, estado de boot/shutdown, configuração e callbacks de log.

A estrutura é deliberadamente pequena. Ela não representa ainda um chipset de PC completo e não contém uma implementação madura de PCI, APIC/IOAPIC, timers, storage, network ou SMP.

O princípio de ownership é:

    ChrisMachine
      possui memória e dispositivos da plataforma
      seleciona um ChrisCpuBackend
      possui uma CPU do backend
      expõe ciclo de vida e APIs para o host

Este capítulo documenta a revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Configuração pública

ChrisConfig contém:

- ram_size;
- backend;
- trace;
- trace_memory;
- trace_io;
- trace_mmio;
- deterministic;
- max_steps;
- break_rip;
- has_break;
- debug;
- headless;
- fb_dump.

chris_config_init zera a estrutura e define:

    RAM           = 16 MiB
    backend       = "chriscpu"
    deterministic = 1
    max_steps     = 1.000.000

Os demais campos começam em zero ou null.

Se chris_machine_create recebe configuração nula, cria internamente uma configuração padrão.

## Parsing de argumentos

chris_config_from_args reconhece:

- --trace;
- --trace-memory;
- --trace-io;
- --trace-mmio;
- --deterministic;
- --debug;
- --headless;
- --backend;
- --break;
- --fb-dump;
- --max-steps.

Opções desconhecidas e argumentos posicionais extras são rejeitados.

O parser exige um ELF de guest.

Uma limitação atual é que deterministic já começa em um e a CLI oferece apenas uma opção que o define novamente como um. Além disso, o runtime inspecionado não possui branch que mude a execução com base em cfg.deterministic.

Portanto, o campo expressa intenção de projeto, mas ainda não é um seletor funcional de modo determinístico.

## Campos centrais de ChrisMachine

ChrisMachine contém:

| Campo | Função |
|---|---|
| cfg | cópia da configuração |
| ram | allocation host que representa RAM guest |
| ram_size | tamanho da RAM |
| io[8] | tabela de port I/O |
| mmio[8] | tabela MMIO |
| serial | estado serial integrado |
| fb | estado de framebuffer |
| cpu | objeto único de CPU |
| backend | ChrisCpuBackend selecionado |
| entry | entry point carregado |
| booted | estado de boot |
| shutdown | pedido de shutdown |
| log/log_ctx | callback opcional de log |

A máquina possui exatamente um ChrisCpu. create_cpu é chamado com CPU ID zero.

Isso constitui uma plataforma uniprocessador. O parâmetro cpu_id existe como seam, mas não representa suporte SMP.

## Registros com capacidade fixa

O header interno define:

    CHRIS_IO_MAX   = 8
    CHRIS_MMIO_MAX = 8

As duas tabelas são arrays fixos embutidos em ChrisMachine.

Cada novo mapping consome o primeiro slot livre. Não há crescimento dinâmico nem unregister.

Para uma máquina de bring-up isso é suficiente, mas torna-se um limite quando forem adicionados interrupt controllers, timers, PCI functions e vários virtio devices.

## Validação inicial de RAM

chris_machine_create exige que ram_size seja:

- no mínimo 2 MiB;
- alinhado a 2 MiB.

Esse requisito acompanha o boot protocol atual, que cria mappings iniciais com páginas de 2 MiB.

Porém, essa não é a restrição final efetiva.

## Teto efetivo de 32 MiB

O framebuffer é fixado em:

    CHRIS_FB_PHYS = 0x02000000

ou 32 MiB.

chris_fb_attach rejeita a criação quando:

    ram_size > CHRIS_FB_PHYS

Assim, apesar de chris_machine_create inicialmente aceitar tamanhos alinhados maiores, a máquina atual só pode ser criada com até 32 MiB de RAM.

Isso é uma restrição concreta da plataforma.

O código de boot/paging consegue conceitualmente construir mappings maiores, mas a criação da máquina é interrompida antes pela posição fixa do framebuffer.

Uma futura memory map deve separar endereço de device e tamanho de RAM de forma explícita.

## Seleção de backend

chris_backend_by_name reconhece:

- null ou "chriscpu";
- "chrishv".

Outros nomes retornam null.

ChrisCPU é o padrão.

ChrisHV está registrado, mas hv_init falha nesta revisão. Selecioná-lo faz chris_machine_create retornar falha.

A arquitetura de seleção de backend já existe, mas somente o interpretador é operacional.

## Ciclo de criação

Uma criação bem-sucedida segue:

1. alocar ChrisMachine zerada;
2. copiar configuração;
3. selecionar backend;
4. executar backend->init;
5. alocar RAM zerada;
6. anexar serial e shutdown port;
7. anexar framebuffer;
8. executar backend->create_cpu(machine, 0);
9. retornar a máquina.

A ordem é relevante porque cada fase depende dos recursos anteriores.

A allocation zerada também faz todos os slots I/O/MMIO começarem livres.

## Cleanup em falhas

Existem caminhos de cleanup para falha de RAM, framebuffer e CPU.

Isso é suficiente para ChrisCPU, cujo init não cria recursos persistentes de virtualização.

Para um backend futuro, porém, o contrato é incompleto: se backend->init alocar recursos e uma etapa posterior falhar, não existe callback específico para destruir estado do backend em uma máquina parcialmente construída.

Um desenho mais robusto deve centralizar cleanup ou adicionar uma etapa de teardown do backend.

## Ownership da RAM

A RAM do guest é um único:

    calloc(1, ram_size)

Logo, inicia zerada.

ChrisMachine possui e libera essa allocation.

chris_write_ram e chris_read_ram chamam chris_phys_write/chris_phys_read, e não memcpy diretamente.

Assim, apesar do nome, essas APIs passam pela camada completa de endereçamento físico e podem acessar regiões que não sejam RAM quando o endereço informado estiver fora dela.

## Ownership do framebuffer

chris_fb_attach cria framebuffer com:

    base   = 0x02000000
    width  = 640
    height = 480
    pitch  = width * 4
    size   = pitch * height

Os pixels ficam em allocation separada da RAM.

chris_phys_read/chris_phys_write roteiam a região correspondente para essa allocation.

Writes definem fb.dirty.

APIs host conseguem ler pixel, consultar dirty e exportar PNG/PPM.

O endereço fixo do framebuffer é justamente o que impõe o teto de 32 MiB.

## Ownership do serial

ChrisMachine embute ChrisSerial diretamente.

chris_serial_attach zera o estado e registra:

    0x3f8..0x3ff  serial
    0x501         shutdown port

O serial mantém registradores UART-like, loopback, buffer TX e callback opcional do host.

O buffer TX é limitado por:

    CHRIS_TX_MAX = 8192

O modelo não reproduz timing completo, FIFOs e IRQs reais de UART.

## Shutdown port

Um write cujo byte baixo seja 0x01 em 0x501 define:

    machine->shutdown = 1

e, se existe CPU:

    exit_reason = CHRIS_EXIT_SHUTDOWN
    halted = 1

É uma convenção própria da plataforma virtual ChrisVM para shutdown determinístico, não uma interface ACPI padrão.

## Registro de port I/O

ChrisIoSlot armazena:

- used;
- range start/end;
- input callback;
- output callback;
- contexto opaco.

chris_io_map verifica apenas a existência da máquina e start <= end.

Não há check de overlap.

find_io percorre os slots em ordem e retorna o primeiro range correspondente.

Logo, dois ranges sobrepostos são permitidos e a ordem de registro determina qual device recebe o acesso.

Esse comportamento deve ser tratado como gap de plataforma.

## Portas sem device

IN em porta não mapeada retorna:

- 0xff para 8 bits;
- 0xffff para 16 bits;
- 0xffffffff para 32 bits.

OUT sem mapping é ignorado.

É uma política tolerante útil para probes legacy, mas é comportamento observável do virtual hardware.

## Registro MMIO

ChrisMmioSlot contém:

- used;
- base;
- size;
- read callback;
- write callback;
- contexto.

Assim como I/O, o primeiro slot livre é utilizado e overlaps não são rejeitados.

chris_mmio_find retorna a primeira região que contém o endereço.

Não existe estrutura dinâmica de intervals nem remoção de mapping.

## Roteamento de endereço físico

chris_phys_read e chris_phys_write usam esta prioridade:

1. RAM;
2. framebuffer;
3. MMIO genérico.

Se o range inteiro cabe em RAM, usa memcpy.

Se cabe inteiro no framebuffer, usa a allocation de pixels.

Caso contrário, tenta MMIO genérico byte a byte.

A ordem define precedência. Um mapping MMIO sobreposto à RAM não recebe o acesso se o request inteiro couber em RAM.

## Gap em acessos que cruzam regiões

Os fast paths exigem que o range completo esteja dentro de uma única região.

Considere um acesso que começa nos últimos bytes de RAM e termina numa região MMIO imediatamente após ela.

O fast path de RAM falha porque o range inteiro não cabe.

O código cai no caminho MMIO para todos os bytes, inclusive aqueles que ainda pertencem à RAM.

Sem um mapping MMIO cobrindo esses primeiros bytes, a operação falha.

Portanto, a camada física atual não divide um request entre regiões heterogêneas adjacentes.

Uma memory map geral deve separar o acesso em chunks por fronteira de região, preservando ao mesmo tempo as regras de fault/atomicidade do guest.

## MMIO genérico é serializado em bytes

No caminho MMIO genérico, o acesso é iterado byte a byte.

O callback recebe sempre:

    size = 1

mesmo quando o guest originou um acesso de 32 ou 64 bits.

Para devices simples isso funciona.

Para hardware realista, largura de acesso pode ser parte da semântica: alguns registradores só aceitam dword, geram side effect uma vez por transaction ou têm latch específico.

Esse comportamento é uma limitação da plataforma.

## Validação de callbacks

chris_mmio_map e chris_io_map aceitam pointers de callback sem exigir que sejam não nulos.

Os devices internos fornecem handlers válidos, mas a API genérica pode registrar uma direção de acesso que depois resulte em dereference inválido.

Um contrato endurecido deve permitir ausência explicitamente e tratá-la com segurança, ou rejeitar o mapping na criação.

## Fronteira de boot

Criar a máquina não faz boot.

chris_load_elf carrega segmentos válidos e registra entry point.

chris_boot separadamente:

- constrói page tables;
- cria GDT inicial;
- monta ChrisArchitectureState;
- define RIP/RSP;
- envia estado para o backend;
- marca booted.

Separar construção, image loading e boot state é uma decisão correta de arquitetura.

## Contrato de run

chris_run rejeita execução se:

- machine é null;
- não existe CPU;
- booted ainda é falso.

Se shutdown já estiver marcado, retorna CHRIS_EXIT_SHUTDOWN sem chamar o backend.

Caso contrário:

    backend->run(cpu, max_steps)

O argumento max_steps é o budget imediato.

ChrisConfig também possui max_steps, mas chris_run não substitui automaticamente o argumento pelo valor da configuração. A frontend escolhe qual budget passar.

## Ownership de uma única CPU

ChrisMachine guarda:

    ChrisCpu *cpu

e não uma coleção.

O backend recebe ID zero em create_cpu.

Adicionar SMP exige mudanças em ownership, scheduler, interrupt routing, APIC, memória compartilhada, debugger e device targeting.

A existência de cpu_id no callback é apenas uma fronteira preparada para evolução.

## Destruição

chris_machine_destroy executa:

1. backend->shutdown(cpu);
2. free(cpu);
3. free(fb.pix);
4. free(ram);
5. free(machine).

No ChrisCPU, o objeto CPU foi criado com calloc e isso é correto.

Para futuros backends, o contrato implica que o objeto externo de CPU continue compatível com free, ou que shutdown libere apenas recursos internos.

Um callback destroy_cpu deixaria esse ownership mais explícito.

## Logging

ChrisMachine armazena callback opcional de log e contexto.

O trace do interpretador usa essa camada.

Esses pointers pertencem ao processo host, não ao estado arquitetural do guest.

Não devem fazer parte de snapshot/migration serializável.

## Breakpoint e trace

Configurações de trace e breakpoint saem de ChrisConfig e são copiadas para ChrisCpu no create_cpu.

Assim, parte do debug nasce na máquina e depois vira runtime state do backend.

Uma interface futura mais geral deve deixar clara essa divisão, especialmente com múltiplas CPUs.

## deterministic ainda não seleciona comportamento

cfg.deterministic começa em um e pode ser definido pela CLI.

Não existe, no código inspecionado, uma condição que mude execução em função desse campo.

Alguns componentes são determinísticos por construção, como CPUID virtual e TSC baseado em retirement, mas isso independe da flag.

O futuro determinism/replay deve tornar o campo operacional ou remover a impressão de modo selecionável.

## Evidência atual de testes

test_chrisvm.c cobre:

- criação padrão;
- load de RAM;
- boot e run;
- serial e loopback;
- shutdown port;
- I/O sem mapping;
- MMIO;
- framebuffer;
- rejeição de ELF;
- exception exits;
- rejeição do backend ChrisHV.

Os testes mostram que a máquina compacta serve aos guests atuais de smoke e aos testes de framebuffer/serial.

Eles não comprovam compatibilidade com uma plataforma PC completa.

## Fronteiras atuais

ChrisMachine ainda não implementa de forma madura:

- SMP;
- local APIC/IOAPIC;
- PIT/HPET;
- PCI/PCIe;
- virtio amplo;
- storage controller;
- network platform;
- ACPI;
- firmware execution;
- hotplug;
- mapa dinâmico de memória;
- chipset genérico.

Cada item exige contrato explícito de hardware virtual, e não apenas novos campos na struct.

## Prioridades de hardening

Os trabalhos de maior valor são:

1. remover o teto implícito de 32 MiB por meio de uma memory map real;
2. substituir ou justificar os arrays fixos de oito slots;
3. rejeitar overlaps acidentais de I/O/MMIO;
4. dividir accesses físicos em fronteiras de região;
5. preservar a largura original em callbacks MMIO;
6. validar handlers ausentes com segurança;
7. adicionar cleanup de backend em falhas parciais;
8. substituir free(cpu) por contrato destroy_cpu;
9. tornar deterministic semanticamente ativo;
10. definir ownership multi-CPU antes de APIC/SMP;
11. separar callbacks host de estado serializável;
12. gerar uma descrição explícita do mapa da máquina para detectar colisões entre RAM e devices.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisMachine é um container coerente e compacto para a plataforma atual baseada em ChrisCPU. Ele integra RAM, uma CPU, serial, shutdown I/O, framebuffer e MMIO de teste. As principais restrições estruturais são o teto de 32 MiB imposto pelo framebuffer, registries fixos, prioridade oculta por primeiro overlap, MMIO genérico byte a byte e ausência de split para acessos físicos que cruzam regiões. Essas fronteiras definem o próximo trabalho necessário para transformar ChrisVM de harness especializado em uma plataforma virtual mais ampla.
