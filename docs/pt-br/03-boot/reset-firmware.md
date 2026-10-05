---
id: reset-firmware
lang: pt-br
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/start.c
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/linker.ld
  - kernel/metal/gdt.c
  - kernel/metal/mm.c
  - iso_root/boot/limine/limine.conf
  - README.md
symbols:
  - kstart
  - bootinfo_init
  - bootinfo_get
  - bootinfo_mp_response
  - gdt_init
  - mm_init
  - smp_init
depends_on:
  - acpi-platform
  - x86-registers-flags
  - x86-64-memory-privilege
related:
  - uefi
  - limine
  - boot-information
  - elf-linking
  - linker-script
  - higher-half-kernel
  - power-on-kstart
  - installation-real-hardware
---

# Reset, inicialização da CPU e firmware

## Escopo

A primeira instrução executada pelo processador depois de reset não é a primeira instrução do ChrisOS.

Entre o reset elétrico e **kstart** existe uma cadeia completa de inicialização:

~~~text
energia / reset
    |
estado arquitetural de reset da CPU
    |
vetor de reset do firmware
    |
inicialização da plataforma
    |
inicialização de memória/chipset
    |
serviços UEFI e Boot Manager
    |
Limine
    |
carregamento ELF + page tables + protocolo de boot
    |
ChrisOS kstart
~~~

O ChrisOS delega deliberadamente as etapas de firmware e bootloader ao firmware da plataforma e ao Limine.

O kernel não possui stub de reset de 16 bits, não entra em protected mode por conta própria, não entra em long mode por conta própria, não inicializa DRAM a partir de um controlador frio e não implementa uma pilha de firmware UEFI.

Seu entry point linkado é a função C **kstart** em um ELF64 higher-half. Portanto uma quantidade significativa de estado já precisa existir antes da primeira instrução C do ChrisOS.

![Reset até a entrada do ChrisOS](../../assets/diagrams/reset-firmware-pt-br.svg)

## Reset é uma transição de estado arquitetural

Reset não significa simplesmente "pular para endereço zero".

Um hardware reset estabelece estado arquitetural:

- registradores de controle recebem valores de reset;
- paginação está desligada;
- o processador ainda não está no ambiente long mode usado pelo kernel;
- a execução começa no vetor de reset definido pela arquitetura;
- dispositivos e memória ainda não estão no estado de runtime pertencente ao sistema operacional.

A documentação Intel descreve CR0 como **0x60000010** após power-up reset. Protection Enable e Paging estão limpos, então a CPU inicia em real-address mode com paginação desligada.

O sistema operacional normalmente não observa diretamente esse estado porque o firmware executa primeiro.

## Vetor de reset x86

O endereço inicial é formado por um estado incomum do CS:

~~~text
seletor CS      = 0xF000
base oculta CS  = 0xFFFF0000
EIP             = 0xFFF0

endereço linear =
0xFFFF0000 + 0xFFF0
= 0xFFFFFFF0
~~~

A primeira instrução é buscada dezesseis bytes abaixo do limite de 4 GiB.

O checker do capítulo valida essa aritmética.

## Por que a base oculta do CS importa

A tradução comum do real mode é apresentada como:

~~~text
linear = segmento * 16 + offset
~~~

Se essa regra comum fosse aplicada imediatamente a CS=0xF000:

~~~text
0xF000 << 4 = 0x000F0000
0x000F0000 + 0xFFF0 = 0x000FFFF0
~~~

Esse não é o reset vector.

No hardware reset, seletor visível e base oculta de CS possuem uma relação especial. Quando o software recarrega CS por uma transferência de controle far, as regras normais do real mode voltam a se aplicar.

Esse detalhe mostra que os bits visíveis de um registrador de segmento não descrevem necessariamente todo o estado interno da CPU.

## O vetor de reset é apenas a porta de entrada

O vetor normalmente contém apenas código suficiente para redirecionar a execução para uma imagem maior de firmware.

Dezesseis bytes não são suficientes para inicializar uma plataforma moderna.

O firmware precisa construir progressivamente:

- armazenamento temporário para execução;
- estado do chipset;
- clocks e dependências de silício;
- DRAM;
- memória permanente;
- buses e protocolos;
- dispositivos necessários para boot;
- console;
- ambiente usado pelo OS loader.

O reset vector inicia o firmware, não o ChrisOS.

## Tipos de reset não são equivalentes

Power-on reset, cold reset, warm reset e eventos INIT de processador são mecanismos diferentes.

Cada um pode preservar partes diferentes do estado da plataforma.

O evento x86 INIT é especialmente relevante para startup multiprocessor, mas não equivale ao reset completo da máquina.

Por isso um sistema operacional ou emulador não deve modelar toda operação "parecida com reset" como uma repetição integral do cold boot.

## BSP e APs

Um processador lógico atua como Bootstrap Processor durante a inicialização inicial do firmware. Os demais são Application Processors.

O modelo clássico de startup x86 pode ativar APs por INIT e Startup IPIs.

O ChrisOS atual não implementa diretamente esse estágio mais baixo.

**smp_init** consome a resposta multiprocessor do Limine e escreve um **ap_entry** nas estruturas por CPU fornecidas pelo bootloader.

Logo:

~~~text
startup arquitetural INIT/SIPI
!=
startup atual do ChrisOS assistido pelo Limine
~~~

O capítulo de SMP trata a execução posterior em detalhe.

## Firmware cria a máquina que o kernel depois administra

Antes de memória permanente existir, o firmware não pode assumir DRAM normal pronta.

O firmware executa tarefas como:

- inicialização inicial de CPU/chipset;
- criação de RAM temporária;
- inicialização do controlador de memória;
- descoberta e training da DRAM;
- criação da memória permanente;
- descoberta de firmware volumes;
- inicialização dos dispositivos necessários ao boot.

Esse trabalho depende fortemente do hardware.

Quando o ChrisOS chega a **pmm_init**, a DRAM já foi inicializada e descrita ao ambiente de boot.

O PMM gerencia páginas. Ele não treina DRAM.

## BIOS e UEFI são modelos diferentes

BIOS legado historicamente expôs serviços em real mode e fluxos de boot orientados a setores.

UEFI define outra interface, incluindo:

- carregamento de executáveis;
- handles e protocols;
- Boot Services;
- Runtime Services;
- device paths;
- variables;
- configuration tables;
- Boot Manager;
- imagens PE/COFF.

O perfil de hardware real do ChrisOS é orientado a UEFI.

Compatibilidade BIOS pode existir por meio do Limine e de ambientes de teste, mas não é o centro arquitetural do roadmap físico.

## UEFI e Platform Initialization são camadas diferentes

A especificação UEFI define a interface padronizada usada por aplicações UEFI, bootloaders e sistemas operacionais.

As especificações Platform Initialization descrevem uma arquitetura comum para construir o firmware propriamente dito.

Uma implementação pode fornecer UEFI sem ser internamente idêntica a uma implementação PI de referência.

Mesmo assim, as fases PI são úteis para entender a evolução do sistema até o boot.

Na data desta revisão, o UEFI Forum lista:

- UEFI Specification 2.11;
- Platform Initialization Specification 1.10.

## Modelo comum de fases PI

Fluxo comum:

~~~text
Reset
  |
SEC
  |
PEI
  |
DXE
  |
BDS
  |
aplicação de boot UEFI
  |
ExitBootServices
  |
sistema operacional
~~~

Recovery, resume e outros caminhos podem variar.

## SEC

SEC é a fase inicial da arquitetura PI.

Ela precisa estabelecer ambiente mínimo para entrar em PEI.

Pode envolver:

- entrada pelo reset vector;
- armazenamento temporário;
- raízes iniciais de segurança/measurement;
- localização da PEI Foundation;
- handoff inicial.

Nesse ponto DRAM normal pode ainda não estar disponível.

## RAM temporária

Firmware precisa de stack e dados antes da memória permanente.

A técnica depende da plataforma e pode usar cache-as-RAM ou memória on-chip.

O ponto importante é:

~~~text
CPU pode executar
antes de
DRAM normal estar completamente inicializada
~~~

Isso ocorre muito antes de kstart.

## PEI

Pre-EFI Initialization prepara o mínimo exigido para DXE.

Uma das tarefas principais é inicializar memória permanente.

PEIMs podem configurar:

- controlador de memória;
- DRAM;
- boot mode;
- recovery;
- segurança da plataforma;
- dependências do chipset.

Depois PEI constrói Hand-Off Blocks para transferir estado ao DXE.

## HOBs

Hand-Off Blocks são registros estruturados usados para transportar estado de PEI para DXE.

Podem descrever recursos e resultados de inicialização.

Eles pertencem ao firmware.

São conceitualmente semelhantes a estruturas de boot info, mas não são o protocolo Limine e não são consumidos diretamente pelo ChrisOS.

## Memory training versus PMM

Memory training trabalha com parâmetros elétricos e temporais para tornar DRAM confiável.

O Physical Memory Manager trabalha com ownership de memória que já funciona.

As camadas são:

~~~text
firmware:
tornar DRAM utilizável

bootloader:
descrever memória utilizável

ChrisOS PMM:
alocar/liberar páginas físicas
~~~

Misturar essas responsabilidades exageraria o que o kernel realmente faz.

## DXE

Driver Execution Environment executa grande parte da inicialização da plataforma em firmware UEFI maduro.

A DXE Foundation fornece serviços e dispatcher.

DXE drivers podem inicializar:

- CPUs;
- buses;
- armazenamento;
- consoles;
- rede;
- protocolos da plataforma.

É nessa fase que o firmware constrói grande parte do ambiente usado pelo UEFI Boot Manager.

## Dispatch orientado por dependências

DXE drivers podem declarar dependências.

O dispatcher só executa um driver quando os protocols e serviços necessários já existem.

~~~text
protocol produzido
      |
driver dependente fica elegível
      |
novo protocol produzido
~~~

A ideia lembra inicialização por dependências no sistema operacional, mas continua sendo arquitetura de firmware.

## Boot Services

Antes do handoff ao sistema operacional, UEFI Boot Services oferecem recursos como:

- alocação de memória;
- descoberta de protocols;
- carregamento de imagens;
- eventos e timers;
- acesso a dispositivos;
- gerenciamento de handles.

Um bootloader pode usar esses serviços para preparar o OS.

Depois de **ExitBootServices**, eles deixam de ser válidos para uso normal.

O ChrisOS não os chama diretamente no desenho atual porque o Limine ocupa essa camada.

## Runtime Services

Alguns Runtime Services podem permanecer disponíveis depois de ExitBootServices, respeitando o contrato de mapeamento e chamada UEFI.

Exemplos incluem variables e time services.

Bootar via UEFI não significa que o kernel implementa automaticamente Runtime Services.

O ChrisOS atual ainda não possui subsistema geral para isso.

## BDS e Boot Manager

Boot Device Selection conecta a plataforma inicializada à política de boot.

O UEFI Boot Manager utiliza:

- BootOrder;
- variáveis Boot####;
- device paths;
- aplicações EFI;
- caminhos de fallback.

Ele finalmente carrega um executável EFI.

Na arquitetura atual do ChrisOS, esse executável é o Limine, não o ELF do kernel.

## Caminho de fallback removível

Em mídia removível UEFI x86-64, o caminho padronizado é:

~~~text
\EFI\BOOT\BOOTX64.EFI
~~~

O plano de instalação do ChrisOS utiliza esse caminho para o Limine.

A cadeia é:

~~~text
firmware
  -> BOOTX64.EFI
  -> Limine
  -> kernel.elf
  -> kstart
~~~

## EFI System Partition

A ESP contém artefatos que o firmware consegue ler.

O fluxo de instalação do ChrisOS grava ali o loader EFI e arquivos de boot associados.

ChrisFS é outra camada, usada como filesystem persistente do sistema operacional.

~~~text
ESP:
cadeia visível ao firmware

ChrisFS:
filesystem do ChrisOS
~~~

Ter ChrisFS funcional não remove a necessidade da ESP.

## PE/COFF versus ELF

Aplicações UEFI são normalmente imagens PE/COFF.

O kernel ChrisOS é ELF64.

O Limine cruza essa fronteira de formatos.

O firmware carrega um executável EFI; o Limine carrega o ELF do kernel segundo seu protocolo.

O firmware não trata diretamente o kernel ELF como aplicação EFI.

## Configuração atual do Limine

O repositório contém:

~~~text
/ChrisOS
    protocol: limine
    path: boot():/boot/kernel.elf
    resolution: 1920x1080x32
~~~

A resolução é uma preferência do bootloader.

O kernel consome a geometria real retornada pelo Limine e não deveria assumir que o modo pedido foi obrigatoriamente concedido por qualquer firmware.

## Requests Limine embutidos no kernel

O kernel atual solicita:

- framebuffer;
- HHDM;
- memory map;
- multiprocessor info;
- command line.

Esses requests vivem em seções especiais preservadas pelo linker script.

Eles fazem parte do contrato entre o ELF e o Limine.

## Segmento de requests

O linker preserva:

~~~text
.limine_requests_start
.limine_requests
.limine_requests_end
~~~

em um segmento carregável dedicado.

Isso é relevante para o roadmap do toolchain nativo.

Um linker que produz apenas um blob executável de texto não reproduz o contrato real do kernel.

## Entry do linker

O script atual declara:

~~~text
OUTPUT_FORMAT(elf64-x86-64)
OUTPUT_ARCH(i386:x86-64)
ENTRY(kstart)
~~~

e inicia o kernel em:

~~~text
0xffffffff80000000
~~~

A entrada do ChrisOS é uma função C 64-bit, não um stub de real mode.

## Endereço higher-half

O endereço:

~~~text
0xffffffff80000000
~~~

fica na metade canônica superior do espaço virtual x86-64 no modelo tradicional de 48 bits.

O Limine precisa estabelecer mappings coerentes com os endereços virtuais do ELF antes de transferir controle a **kstart**.

O kernel não começa em um endereço baixo e depois se reloca para o higher half.

## Classes de segmentos ELF

O linker cria classes:

~~~text
requests  gravável
text      executável
data      gravável
~~~

A BSS é NOLOAD.

O loader deve zerar memória quando o tamanho em memória de um segmento é maior que o tamanho no arquivo.

Por isso um kernel bootável não é apenas uma sequência de opcodes.

## Stack reservada do kernel

O linker reserva um MiB entre:

~~~text
__stack_bottom
__stack_top
~~~

na região BSS/data.

Mais tarde **gdt.c** usa **__stack_top** como **rsp0** do TSS.

Entretanto, não existe stub de entrada no repositório que carregue o RSP inicial com **__stack_top** antes de chamar **kstart**.

Logo, a existência desse símbolo não prova que o ChrisOS estabelece sua própria stack inicial.

A stack de entrada pertence ao contrato do bootloader; **__stack_top** é certamente usada depois para transições de privilégio.

## Entrada C implica ABI existente

Como **kstart** é C compilado, a CPU já precisa estar em estado compatível com o código 64-bit gerado.

O kernel usa ambiente freestanding x86-64 e desativa red zone.

A stack precisa ser válida antes do prólogo da função.

Uma função C não consegue "consertar" uma stack inicial inválida antes de o próprio prólogo já depender dela.

## bootinfo_init

A primeira grande transferência de ownership dentro do ChrisOS é **bootinfo_init**.

Ela exige:

- base revision Limine suportada;
- framebuffer;
- HHDM;
- memory map;
- multiprocessor response.

E registra:

- offset HHDM;
- endereço/geometria do framebuffer;
- memória utilizável;
- quantidade de entradas do memory map;
- número de CPUs;
- BSP LAPIC ID.

Isso converte estruturas do bootloader em estado resumido pertencente ao kernel.

## Contrato do framebuffer

O framebuffer chega antes de **gfx_init**.

Portanto a tela inicial não nasce de um driver ChrisOS configurando GPU desde o reset.

Firmware e bootloader já estabeleceram um modo gráfico e uma superfície linear.

O ChrisOS consome essa superfície e pode iniciar outros caminhos gráficos depois.

## Contrato HHDM

O Limine fornece o offset Higher-Half Direct Map.

**bootinfo_phys_to_virt** soma esse offset aos endereços físicos.

Código inicial de memória depende desse mapping.

Logo o ChrisOS começa dentro de um ambiente paginado já existente.

Seu MM administra e amplia esse ambiente; não cria as primeiras page tables a partir do reset.

## Handoff do memory map

A cadeia aproximada é:

~~~text
firmware inicializa DRAM
        |
UEFI conhece regiões
        |
Limine obtém/normaliza informação
        |
resposta Limine
        |
bootinfo do ChrisOS
        |
PMM
~~~

O PMM decide quais páginas o kernel pode usar depois do handoff.

## Handoff multiprocessor

O Limine fornece a resposta MP usada pelo ChrisOS.

Ela contém registros de CPUs e informações BSP/AP consumidas por **smp_init**.

Assim, o startup atual dos APs é assistido pelo bootloader.

O kernel pode assumir mais responsabilidade futuramente, mas esse não é o estado desta revisão.

## ExitBootServices

Um loader UEFI normalmente obtém o memory map atual e chama **ExitBootServices**.

A map key faz parte do contrato de sincronização.

Se alocações ocorrerem entre a obtenção do map e a chamada, o loader pode precisar obter o map novamente e repetir a operação.

O Limine encapsula essa responsabilidade para o ChrisOS.

O kernel não executa hoje o fluxo UEFI ExitBootServices diretamente.

## Ownership após ExitBootServices

Depois do fim de Boot Services, regiões de memória possuem regras diferentes.

Algumas áreas de firmware podem ser reaproveitadas; áreas de Runtime Services exigem preservação apropriada.

O ChrisOS recebe a classificação via Limine e depois constrói reservas do PMM.

Os detalhes aparecem nos capítulos de boot information e memória física.

## UEFI variables não são arquivos da ESP

Variáveis como BootOrder são objetos gerenciados pelo firmware, identificados por nome e GUID.

Elas são diferentes dos arquivos da ESP.

Ler **BOOTX64.EFI** de FAT não significa que o OS implementa acesso às variables NVRAM.

O ChrisOS não possui hoje uma camada geral de UEFI variables.

## Secure Boot

Secure Boot é uma política de confiança para autenticação de imagens EFI e cadeias relacionadas.

Não é sinônimo de UEFI.

Uma máquina UEFI pode operar com Secure Boot desligado.

O roadmap atual não afirma implementação completa de Secure Boot controlada pelo ChrisOS.

## Measured boot

Measured boot registra medições para attestation posterior, normalmente com TPM.

Verified boot e measured boot resolvem problemas diferentes.

Nenhum deles deve ser confundido com a correção básica da cadeia reset -> kernel.

## POST

POST é um termo histórico amplo.

Firmware moderno realiza inicialização distribuída por várias fases.

Para documentação técnica, SEC/PEI/DXE/BDS descrevem melhor responsabilidades do que tratar todo o pré-OS como um único bloco "POST".

## Firmware Volumes

Implementações PI normalmente armazenam módulos em Firmware Volumes.

Eles podem conter PEIMs, DXE drivers e outros componentes.

O ChrisOS não interpreta firmware volumes porque esse trabalho acontece antes do handoff.

## Mapeamento de flash

O vetor de reset fica próximo do topo do espaço físico de 32 bits.

Lógica da plataforma mapeia conteúdo de flash para que o código de reset seja visível nesse endereço.

Essa região não deve ser confundida com DRAM gravável comum.

O mapeamento pode mudar durante a inicialização do chipset.

## Microcode

Firmware frequentemente aplica atualizações de microcode antes do OS.

Sistemas operacionais maduros também podem suportá-las.

Microcode altera implementação interna preservando o contrato arquitetural.

O ChrisOS ainda não possui um subsistema de microcode de produção.

## Descoberta de features da CPU

Reset fornece estado arquitetural básico, não autorização para usar toda feature opcional sem checagem.

Firmware e OS usam mecanismos como CPUID e control registers.

O hardening para hardware real deve tornar requisitos da CPU explícitos antes de usar facilities opcionais.

## Entrada em long mode

Conceitualmente, long mode envolve uma transição coordenada com:

- estado protected mode;
- CR4.PAE;
- page tables;
- EFER.LME;
- CR0.PG;
- segmento de código 64-bit.

O ChrisOS não executa essa transição a partir de reset.

O Limine entrega a CPU no ambiente exigido pelo protocolo.

## kstart como fronteira de design

Uma entrada ELF diretamente em C expressa uma escolha:

~~~text
firmware + bootloader:
responsáveis pela transição pré-C

ChrisOS:
responsável pela inicialização do kernel após handoff
~~~

Isso reduz bootstrap assembly interno, mas torna o contrato com Limine essencial.

## Primeiras operações de kstart

A sequência fonte começa por:

1. serial;
2. identidade do build;
3. bootinfo;
4. boot flags;
5. GDT;
6. IDT/syscall/PIC/PIT/PS2;
7. PMM e MM;
8. heap/processos;
9. gráficos;
10. APIC/IOAPIC/SMP;
11. ACPI;
12. storage/filesystem/runtime.

Isso já é inicialização de sistema operacional, muito acima do reset físico.

## Diagnóstico inicial

**kstart** chama **serial_init** imediatamente.

Se a serial falhar, o código desabilita interrupções e entra em HLT infinito.

Portanto ausência de log serial não prova que firmware ou Limine falharam.

Pode significar:

~~~text
kstart nunca foi alcançado
ou
kstart foi alcançado e a serial falhou
~~~

Bring-up físico deve usar múltiplos canais de diagnóstico quando possível.

## ISO versus disco instalado

Bootar a mídia de instalação e bootar o disco instalado são gates diferentes.

O teste do disco precisa remover a mídia e provar que o firmware encontra a ESP, executa o loader instalado, encontra sua configuração e carrega o kernel esperado.

O plano de hardware real do ChrisOS trata isso separadamente.

## Boot funcionando versus self-hosting

Uma máquina pode bootar perfeitamente um kernel compilado no host.

Isso não prova que o kernel foi compilado/linkado dentro do próprio ChrisOS.

As auditorias do repositório separam esses milestones.

A proveniência do artefato precisa ser registrada independentemente do sucesso de boot.

## Pipeline real do kernel hoje

O caminho aproximado é:

~~~text
fontes do kernel
    |
GCC + NASM no host
    |
ld do host + kernel/metal/linker.ld
    |
ELF higher-half
    |
Limine
    |
ChrisOS
~~~

O toolchain nativo ainda não provou a reprodução integral desse pipeline e o reboot de um kernel produzido internamente.

## Linker script faz parte da arquitetura de boot

O linker script define:

- símbolo de entrada;
- base virtual higher-half;
- segmento de requests Limine;
- código executável;
- dados graváveis;
- BSS;
- região de stack de um MiB;
- metadados descartados.

Um linker nativo precisa reproduzir essas propriedades para ser equivalente ao kernel real.

## ChrisVM protocol v1

O ChrisVM atual ignora reset e firmware.

Protocol v1 cria diretamente:

- long mode;
- page tables;
- GDT;
- stack;
- framebuffer;
- estado de entrada ELF.

Ele não implementa:

- reset vector;
- BIOS;
- UEFI;
- Limine;
- inicialização de DRAM.

É um bootstrap direto para guests de teste.

## Protocol v1 ainda não boota o ChrisOS real

O kernel real está linkado em:

~~~text
0xffffffff80000000
~~~

Protocol v1 rejeita esse ELF higher-half.

Também não fornece estruturas equivalentes ao bootinfo Limine.

Portanto:

~~~text
ChrisCPU executa ELF
!=
ChrisVM boota ChrisOS
~~~

## Dois modelos futuros para o ChrisVM

### Direct kernel mode

Criar mappings higher-half e bootinfo explícito suficiente para o ChrisOS sem emular UEFI.

Vantagens:

- menor escopo;
- determinístico;
- caminho mais rápido até o kernel real.

### Firmware mode

Emular hardware suficiente para executar firmware UEFI e Limine.

Vantagens:

- valida a cadeia real;
- testa hardware visível ao firmware.

O escopo é muito maior.

Os dois modos podem coexistir.

## Progressão sugerida do ChrisVM

~~~text
Estágio 1
guests diretos long mode atuais

Estágio 2
ELF higher-half
bootinfo explícito
entrada no kernel real

Estágio 3
PCI/ACPI/interrupções
mais drivers nativos

Estágio 4
UEFI + Limine opcional

Estágio 5
fidelidade de reset/firmware
~~~

O emulador não precisa reproduzir cold boot completo antes de ser útil no desenvolvimento do OS.

## Matriz de responsabilidades

| Responsabilidade | CPU/Firmware | Limine | ChrisOS |
|---|---:|---:|---:|
| estado arquitetural de reset | sim | não | não |
| execução do reset vector | firmware | não | não |
| inicialização da DRAM | firmware | não | não |
| ambiente UEFI | firmware | não | não |
| política de boot EFI | firmware | não | não |
| carregar aplicação EFI Limine | firmware | não | não |
| interpretar requests Limine | não | sim | declara |
| carregar kernel ELF | não | sim | produz imagem |
| criar mappings de boot | não | sim | consome |
| handoff de framebuffer | firmware/loader | sim | consome |
| HHDM | não | sim | consome |
| memory map | derivado do firmware | sim | consome |
| handoff MP | derivado da plataforma | sim | consome |
| PMM/MM/heap | não | não | sim |
| filesystem/runtime/desktop | não | não | sim |

## Localização de falhas

Antes do primeiro log serial consistente do ChrisOS, classes possíveis incluem:

- firmware;
- política de boot;
- loader EFI ausente;
- configuração Limine;
- kernel não carregado;
- incompatibilidade ELF/protocolo;
- estado de entrada;
- serial.

Depois do log de **kstart**, a transição firmware -> bootloader -> kernel pelo menos alcançou a função C.

Isso reduz muito o espaço de diagnóstico.

## Identidade do boot

O plano de hardware real prevê saída semelhante a:

~~~text
ChrisOS <version>
Build: <id>
Compiler: <toolchain>
Kernel SHA256: <hash>
~~~

Isso evita validar acidentalmente um kernel antigo.

Um teste de boot sem proveniência do artefato pode passar testando a imagem errada.

## Checker reproduzível

O checker deste capítulo valida:

1. aritmética do reset vector;
2. diferença entre base especial de CS no reset e segmentação real-mode comum;
3. canonicidade do endereço higher-half atual;
4. número de máquina ELF x86-64;
5. **ENTRY(kstart)** no linker source;
6. base higher-half atual;
7. seções de requests Limine;
8. protocol/path atuais do Limine;
9. respostas obrigatórias consumidas por **bootinfo_init**.

Ele não emula firmware nem certifica hardware físico.

## Matriz da implementação atual

| Camada / recurso | Estado |
|---|---|
| reset-vector pertencente ao ChrisOS | não implementado por design |
| bootstrap 16-bit no kernel | não implementado por design |
| transição protected mode no kernel | não implementada por design |
| transição long mode no kernel | não implementada por design |
| firmware UEFI | dependência externa |
| Limine | bootloader externo utilizado |
| kernel ELF64 higher-half | implementado |
| segmento de requests Limine | implementado |
| framebuffer request | implementado |
| HHDM request | implementado |
| memory-map request | implementado |
| MP request | implementado |
| entry C kstart | implementado |
| Runtime Services nativo | não implementado |
| subsistema UEFI variables | não implementado |
| Secure Boot controlado pelo ChrisOS | não implementado |
| boot integral de kernel self-hosted | não provado |
| boot direto de guests pequenos no ChrisVM | implementado |
| boot do ChrisOS higher-half no ChrisVM | não implementado |
| UEFI/Limine no ChrisVM | não implementado |
| execução de reset/firmware no ChrisVM | não implementada |

## Limite de validação

Este capítulo foi conciliado com ChrisOS main **da3df29cb397932c43d32373871fb9380e688ade**.

Na data da revisão, o UEFI Forum lista UEFI Specification 2.11 e Platform Initialization Specification 1.10.

A documentação Intel define o estado de reset e o comportamento do reset vector descritos aqui.

Execute:

~~~text
python scripts/check_reset_firmware_examples.py --source .source
~~~

O script valida aritmética e contratos selecionados do source. Não é suíte de conformidade UEFI, Limine ou hardware físico.

## Gatilhos de revisão

Revisar quando:

- o bootloader mudar;
- o contrato de requests Limine mudar;
- entry ou base virtual do kernel mudar;
- surgir entry assembly pré-C;
- ownership da stack inicial mudar;
- bootinfo receber dados UEFI/ACPI/SMBIOS;
- Runtime Services aparecerem;
- Secure Boot/measured boot virar alvo suportado;
- kernel self-hosted for instalado e reiniciado com prova;
- ChrisVM bootar o kernel higher-half real;
- ChrisVM ganhar UEFI ou execução desde reset vector.

## Referências primárias

- Intel 64 and IA-32 Architectures Software Developer's Manual, Processor Management and Initialization.
- UEFI Forum, UEFI Specification 2.11.
- UEFI Forum, Platform Initialization Specification 1.10.
- Arquivos-fonte do ChrisOS listados no front matter.
