---
id: chrisvm-memory-map
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/boot.c
  - chrisvm/buses/mmio.c
  - chrisvm/devices/fb/fb.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - CHRIS_STACK_RSP
  - CHRIS_GDT_PHYS
  - CHRIS_PT_RESERVE
  - CHRIS_FB_PHYS
  - chris_phys_read
  - chris_phys_write
  - install_tables
  - chris_load_elf
depends_on:
  - chrisvm-machine
  - emulator-paging
related:
  - chrisvm-mmio-bus
  - chrisvm-boot
  - physical-memory
  - virtual-memory
---

# Mapa de memória física do ChrisVM

## Escopo

O mapa físico do ChrisVM é definido atualmente por algumas constantes fixas, pelo tamanho de RAM e pelos registros MMIO criados em runtime. Não existe uma tabela central descrevendo todas as regiões físicas. Ownership fica distribuído entre boot constants, allocation de RAM, framebuffer e registry MMIO.

Esse desenho é simples de inspecionar, mas cria acoplamento implícito: loader, page-table builder, framebuffer e dispatcher físico precisam concordar sobre os endereços sem uma estrutura única validando o layout completo.

Este capítulo documenta o contrato de endereço físico na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Layout padrão

Com a configuração padrão de 16 MiB de RAM, as regiões principais são:

| Range / endereço | Função |
|---|---|
| 0x00000000 .. fim da RAM | RAM do guest |
| 0x00070000 .. 0x00070fff | página reservada para GDT |
| 0x0007f000 .. 0x0007ffff | página inicial de stack reservada pelo loader |
| 0x00080000 | RSP inicial, stack cresce para baixo |
| RAM_size - 0x4000 | página PML4 |
| RAM_size - 0x3000 | página PDPT |
| RAM_size - 0x2000 | página PD |
| RAM_size - 0x1000 .. RAM_size | reservado pelo loader e não usado por install_tables |
| 0x02000000 .. 0x0212bfff | bytes de framebuffer |
| ranges registrados em runtime | MMIO genérico |

Port I/O, como serial 0x3f8..0x3ff e shutdown port 0x501, pertence a outro address space e não faz parte do mapa físico de memória.

## Região de RAM

ChrisMachine aloca um buffer host contíguo e zerado para a RAM guest.

O tamanho precisa ser:

- no mínimo 2 MiB;
- alinhado a 2 MiB.

O padrão é 16 MiB.

O framebuffer impõe um teto efetivo adicional de 32 MiB porque chris_fb_attach rejeita ram_size acima de CHRIS_FB_PHYS.

Assim, na máquina atual:

    2 MiB <= RAM <= 32 MiB
    tamanho múltiplo de 2 MiB

O primeiro byte físico depois da RAM não é automaticamente guard ou reservado. Ele pode pertencer ao framebuffer ou a MMIO conforme o endereço.

## ELF orientado a identidade

chris_load_elf aceita ELF x86-64 little-endian de 64 bits.

Para cada PT_LOAD, usa p_vaddr como offset de destino dentro da RAM. p_paddr não funciona como endereço físico independente.

O segmento inteiro precisa caber na RAM.

O loader também rejeita virtual addresses em ou acima de:

    0xffff800000000000

no boot protocol v1.

Na prática, o modelo inicial é orientado a identidade: o virtual load address do ELF é copiado no physical offset de mesmo número e depois identity-mapped pelas page tables iniciais.

Ainda não é um loader geral para placement físico e virtual independentes.

## Regiões reservadas dentro da RAM

O loader impede PT_LOAD sobre três classes de memória controladas pelo boot.

### Página da GDT

A GDT fica em:

    CHRIS_GDT_PHYS = 0x70000

Uma página de 4 KiB completa é reservada.

install_tables escreve atualmente três descriptors de oito bytes:

- null;
- code long mode;
- data.

A maior parte da página permanece livre, mas protegida contra ELF loading.

### Página inicial de stack

O RSP inicial é:

    CHRIS_STACK_RSP = 0x80000

O loader rejeita overlap com a página imediatamente abaixo:

    0x7f000 .. 0x7ffff

A stack começa em 0x80000 e cresce para baixo.

Não existe um objeto dinâmico de stack no boot atual; a convenção usa RAM já zerada.

### Reserva de page tables

O loader reserva os últimos:

    CHRIS_PT_RESERVE = 0x4000

bytes da RAM, isto é, quatro páginas de 4 KiB.

install_tables usa:

    PML4 = RAM_size - 0x4000
    PDPT = RAM_size - 0x3000
    PD   = RAM_size - 0x2000

A página final:

    RAM_size - 0x1000 .. RAM_size

continua bloqueada para o ELF, mas não é usada por install_tables nesta revisão.

A quarta página oferece espaço potencial de expansão, mas ainda não tem papel próprio codificado.

## Topologia inicial de paginação

O boot constrói:

    PML4[0] -> PDPT
    PDPT[0] -> PD

O PD contém mappings de identidade em páginas de 2 MiB.

Para cada chunk de RAM:

    PDE[i] = physical_base | 0x83

onde 0x83 corresponde a Present, Writable e Page Size.

Um único PD permite teoricamente até 1 GiB nesse layout.

O limite real da máquina chega antes, em 32 MiB, por causa do framebuffer.

## Região física do framebuffer

O framebuffer inicia em:

    CHRIS_FB_PHYS = 0x02000000

ou 32 MiB.

Dimensões:

    width  = 640
    height = 480
    pitch  = 640 * 4

Tamanho:

    640 * 480 * 4 = 1.228.800 bytes = 0x12c000

Portanto o backing real ocupa:

    0x02000000 .. 0x0212bfff

e o primeiro byte depois dele é:

    0x0212c000

Os pixels ficam em allocation host separada da RAM.

## Mapping virtual do framebuffer

install_tables identity-maps o framebuffer.

O início é alinhado para baixo em 2 MiB e são instalados PDEs de 2 MiB até cobrir todo o tamanho.

Como 0x02000000 já é alinhado e o framebuffer ocupa menos de 2 MiB, uma large page cobre:

    0x02000000 .. 0x021fffff

Mas apenas os primeiros 0x12c000 bytes possuem backing de framebuffer.

Os endereços restantes dessa large page não pertencem automaticamente ao framebuffer. Sem MMIO adicional, chris_phys_read/write falha nesses physical addresses.

É importante distinguir cobertura de page table de backing físico de device.

## Motivo do teto de 32 MiB

Com exatamente 32 MiB de RAM:

    RAM = 0x00000000 .. 0x01ffffff

e framebuffer começa em:

    0x02000000

Logo, não há overlap.

Se a RAM for maior, invade a base fixa do framebuffer.

Em vez de mover o device, chris_fb_attach falha.

O teto é, portanto, uma política de collision handling codificada indiretamente no device.

Uma futura memory map deve detectar e resolver regiões centralmente.

## MMIO genérico

chris_mmio_map permite registrar regiões em runtime.

Cada região define:

- base;
- size;
- read callback;
- write callback;
- context.

Há até oito slots.

A função não verifica overlap com:

- RAM;
- framebuffer;
- outro MMIO.

Logo, um slot pode existir na tabela e nunca receber acessos por estar encoberto por uma região de maior prioridade.

## Prioridade do dispatcher físico

chris_phys_read e chris_phys_write aplicam:

    1. RAM
    2. framebuffer
    3. MMIO genérico

RAM e framebuffer exigem que o request inteiro caiba dentro da região.

MMIO só é usado depois das duas tentativas.

Portanto, o mapa efetivo é também definido por essa prioridade.

### RAM encobre MMIO

MMIO sobreposto à RAM não recebe requests totalmente contidos em RAM.

### Framebuffer encobre MMIO

MMIO sobreposto ao backing do framebuffer perde para o framebuffer.

### MMIO é fallback

O generic MMIO ocupa efetivamente os endereços restantes alcançáveis.

Até haver rejeição de overlap, essa prioridade faz parte do contrato da plataforma.

## Requests que cruzam regiões não são divididos

Um request físico pode falhar mesmo se todos os seus bytes individualmente possuem backing.

Exemplo:

    [2 últimos bytes da RAM][2 primeiros bytes de MMIO]

em um único acesso de 4 bytes.

O fast path de RAM rejeita porque o range completo não cabe.

Então o código entra no caminho MMIO para todos os bytes, inclusive os dois primeiros ainda pertencentes à RAM.

Sem MMIO nesses endereços, falha.

Não existe splitter por fronteira de região.

Uma memory map madura deve dividir o request ou rejeitar explicitamente crossings não suportados com semântica arquitetural definida.

## Largura de transação MMIO é perdida

O generic MMIO é processado byte a byte.

Um acesso guest de 4 bytes gera quatro callbacks com:

    size = 1

e não um callback de size 4.

Isso preserva bytes para devices triviais, mas perde semântica de transaction width.

Hardware realista pode depender de word/dword access, latches ou side effects por transação.

O dispatcher futuro deve identificar a região primeiro e preservar a largura quando o device suportar.

## Memória física sem backing

Se um physical address está fora de RAM, framebuffer e MMIO, chris_phys_read/write retorna falha.

Quando a MMU já produziu uma tradução válida e o wrapper encontra esse problema, ChrisCPU classifica como:

    CHRIS_EXIT_UNMAPPED

e não como #PF normal do guest.

Essa separação é correta: as page tables podem estar válidas, mas o emulador não implementa nenhum recurso físico naquele endereço.

## MMIO de teste em 96 MiB

test_chrisvm.c registra um device MMIO em:

    0x06000000

ou 96 MiB.

O teste instala manualmente um PDE de 2 MiB apontando para a região e executa guest code que escreve e lê o cell.

Isso comprova que generic MMIO pode existir bem acima de RAM e framebuffer.

Virtual mapping e physical backing são duas etapas separadas.

## Collision checks do loader

chris_load_elf rejeita overlap com:

- últimos 16 KiB reservados;
- página da GDT;
- página inicial de stack.

Ele não consulta os slots MMIO de runtime.

Também não precisa verificar framebuffer diretamente porque PT_LOAD precisa caber dentro da RAM, e o framebuffer começa no limite ou depois da RAM permitida.

Um mapa configurável exigirá uma API genérica de collision detection.

## Endereço físico versus virtual

O boot protocol identity-maps RAM e framebuffer, mas o modelo continua em duas fases:

    virtual guest -> physical guest

pela MMU, seguido por:

    physical guest -> RAM / FB / MMIO / unmapped

pelo dispatcher da máquina.

Os números iguais são uma propriedade do boot v1, não uma razão para fundir os dois conceitos.

A separação é necessária para higher-half, userspace, shared mappings e remapeamento de devices.

## GDT e identidade

A GDT fica fisicamente em 0x70000.

Como a RAM inicial é identity-mapped, GDTR.base também recebe 0x70000 e o acesso virtual ao descriptor alcança os mesmos bytes.

Isso depende do mapa inicial de identidade.

Um boot futuro pode manter GDT em outro physical backing desde que o linear address em GDTR esteja mapeado corretamente.

## Stack e crescimento

RSP começa em 0x80000.

Somente uma página abaixo é reservada contra ELF loading.

O emulador não impõe um limite próprio para stack. Se o guest continuar fazendo pushes para páginas inferiores mapeadas, a MMU pode permitir.

Portanto, "stack page" é uma reserva de ownership do loader, não um guard page arquitetural.

Um guard real exige mapping not-present/protected.

## Page tables continuam acessíveis ao guest

Os últimos 16 KiB são excluídos de segmentos ELF, mas continuam RAM física normal depois do boot.

As identity mappings cobrem essas páginas.

Logo, código privilegiado guest pode ler ou sobrescrever suas próprias page tables.

Isso é normal em kernels, mas mostra que "reservado pelo loader" não significa "protegido em runtime".

## Ausência de region descriptor central

ChrisMachine não possui hoje uma estrutura única como:

    region {
        base
        size
        type
        owner
        permissions
        widths
        priority
    }

O mapa é inferido a partir de ram_size, constantes do framebuffer, slots MMIO, constantes de boot e ordem do dispatcher.

Isso simplifica o bring-up, mas prejudica validação, visualização, snapshot e hotplug.

Um modelo central permitiria gerar um mapa autoritativo e detectar colisões antes da execução.

## Relação com boot protocol v1

O boot v1 assume:

- ELF em low RAM;
- RAM identity-mapped;
- GDT fixa em low memory;
- stack fixa em low memory;
- page tables no topo da RAM;
- framebuffer fixo em 32 MiB;
- ausência de firmware memory map;
- ausência de ACPI/e820 discovery.

O guest recebe uma máquina por convenção, não por enumeração de firmware.

Isso basta para os guests próprios atuais, mas não para operating systems arbitrários.

## Evidência de validação

Os testes verificam:

- rejeição de ELF em regiões reservadas;
- construção funcional de page tables;
- MMIO em 96 MiB;
- framebuffer físico fixo;
- CHRIS_EXIT_UNMAPPED para backing ausente;
- permissões de paging pelo probe independente da MMU.

Ainda faltam testes sistemáticos de overlap e crossings em todas as fronteiras.

## Prioridades de hardening

Os próximos passos de maior valor são:

1. criar registry físico autoritativo único;
2. detectar overlap na criação/registro;
3. remover teto de RAM movendo devices de forma configurável;
4. dividir physical accesses por fronteiras de região;
5. preservar largura de transaction em MMIO;
6. expressar regiões reservadas pelo mesmo mapa em vez de checks hard-coded;
7. criar memory-map handoff real para o guest;
8. adicionar guard semantics à stack se desejado;
9. dar função explícita à quarta página reservada no topo da RAM ou liberá-la;
10. testar limites exatos de RAM, framebuffer e MMIO adjacente;
11. separar permissões de region das permissões de page table;
12. expor o mapa físico gerado para debugger e documentação.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, o mapa físico do ChrisVM é simples por design: RAM contígua em low memory, estruturas de boot dentro dela, framebuffer fixo em 32 MiB e pequeno registry MMIO como fallback. Isso é suficiente para os smoke guests atuais, mas falta um modelo central autoritativo de regiões. As principais consequências são o teto de 32 MiB, prioridade implícita de dispatch, overlaps não validados e ausência de split de um request físico entre regiões.
