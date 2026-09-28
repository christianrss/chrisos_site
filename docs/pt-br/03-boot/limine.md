---
id: limine
lang: pt-br
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/linker.ld
  - kernel/metal/start.c
  - kernel/metal/smp.c
  - kernel/metal/pmm.c
  - kernel/metal/mm.c
  - iso_root/boot/limine/limine.conf
  - makefile
  - .cursor/install.sh
symbols:
  - kstart
  - bootinfo_init
  - bootinfo_get
  - bootinfo_phys_to_virt
  - bootinfo_memmap_count
  - bootinfo_memmap_entry
  - bootinfo_mp_response
  - smp_init
  - pmm_init
  - mm_init
depends_on:
  - uefi
  - reset-firmware
related:
  - boot-information
  - acpi-platform
  - elf-linking
  - linker-script
  - higher-half-kernel
  - interrupts-smp
  - physical-memory
  - hhdm
  - installation-real-hardware
---

# Protocolo de boot Limine

## Escopo

Limine é atualmente a fronteira entre o firmware de boot da plataforma e o kernel ChrisOS.

No caminho planejado para hardware físico, UEFI carrega a imagem EFI do Limine. O Limine carrega o executável ELF64 do ChrisOS, constrói o ambiente de memória virtual da entrada, resolve requests do protocolo embutidos no kernel, publica as estruturas de resposta, encerra os UEFI Boot Services e transfere controle para o entry point do kernel.

O ChrisOS não recebe o estado de boot por uma convenção privada passada em registradores.

Ele declara estruturas de dados dentro do próprio executável:

~~~text
ELF do ChrisOS
  |
  +-- request start marker
  +-- base revision tag
  +-- framebuffer request
  +-- HHDM request
  +-- memory-map request
  +-- MP request
  +-- executable command-line request
  +-- request end marker
~~~

O Limine encontra essas estruturas, escreve os ponteiros de resposta, prepara o ambiente x86-64 e salta para o entry point ELF.

![Requests, responses e handoff do Limine](../../assets/diagrams/limine-pt-br.svg)

A revisão atual do ChrisOS fixa o Limine no commit:

~~~text
ee5d29cd0a8034612dcd1df3f00052480db785c5
~~~

da branch v9.x-binary. O header fixado suporta LIMINE_API_REVISION até 3 e o ChrisOS seleciona API revision 3.

Separadamente, o kernel solicita Limine base revision 3.

Esses dois números representam contratos diferentes.

## Bootloader Limine versus protocolo Limine

O projeto Limine fornece um bootloader e também é a implementação de referência do protocolo Limine.

O protocolo é uma especificação independente que pode, em princípio, ser implementada por outros bootloaders.

É necessário separar:

~~~text
implementação do bootloader Limine
de
ABI do Limine Boot Protocol
~~~

O código do kernel depende principalmente das estruturas do protocolo.

O build de ISO/disco também depende dos binários e ferramentas host do Limine.

## Por que existe um protocolo de boot

Um kernel 64-bit precisa receber muito mais que um instruction pointer.

Informações úteis incluem:

- topologia de memória;
- mappings virtuais;
- framebuffer;
- topologia de CPUs;
- tabelas derivadas do firmware;
- módulos;
- metadados do executável;
- argumentos de boot.

Sem protocolo, cada combinação de bootloader e kernel precisaria de ABI privado.

Limine padroniza isso por requests e responses descobertos na imagem carregada.

## Três domínios diferentes de versão

O código relacionado ao Limine possui vários conceitos independentes de revisão.

Eles não devem ser confundidos.

### Header API revision

O limine.h fixado pelo projeto possui:

~~~text
LIMINE_API_REVISION
~~~

O ChrisOS define:

~~~text
#define LIMINE_API_REVISION 3
~~~

e o build também passa:

~~~text
-DLIMINE_API_REVISION=3
~~~

Isso seleciona compatibilidade de nomes e estruturas dentro do header C fixado.

Revisões antigas do header usavam nomes como SMP ou kernel-file; modos mais novos usam MP ou executable-file.

### Protocol base revision

O ChrisOS embute:

~~~text
LIMINE_BASE_REVISION(3)
~~~

A base revision altera semânticas globais do protocolo, incluindo:

- comportamento dos delimitadores;
- existência de identity map;
- cobertura do HHDM;
- semântica de ponteiros de tabelas de firmware;
- partes do estado da CPU na entrada.

Ela não é a mesma coisa que a API revision do header.

### Revision de cada request

Cada request possui seu próprio campo:

~~~text
revision
~~~

Os cinco requests atuais usam:

~~~text
.revision = 0
~~~

A feature revision evolui uma funcionalidade individual sem ser igual à base revision global.

O modelo completo é:

~~~text
API revision do header C
        |
base revision do protocolo
        |
revision da feature/request
~~~

Os três valores podem ser diferentes.

## Header fixado pelo projeto

.cursor/install.sh documenta a dependência exata:

~~~text
LIMINE_SHA =
ee5d29cd0a8034612dcd1df3f00052480db785c5

branch:
v9.x-binary

comment:
API revision 3
~~~

O script busca essa revisão quando third_party/limine/limine.h não existe.

Isso é importante para reprodutibilidade.

Compilar com um limine.h arbitrariamente mais novo não equivale ao source revisado do ChrisOS.

## Estado atual do protocolo upstream

A especificação Limine atual define base revisions 0 a 6 e marca 0 a 5 como deprecated.

O ChrisOS ainda solicita base revision 3 porque esse é o contrato associado à dependência fixada e à implementação corrente.

Isso não torna os boots atuais inválidos.

Significa, porém, que modernizar o protocolo tornou-se dívida técnica explícita.

Uma migração futura deve atualizar:

- commit fixado do Limine;
- limine.h;
- compatibilidade de API;
- base revision;
- suposições de memory map;
- caminho ACPI/RSDP;
- documentação do estado da CPU;
- expectativas do KCC;
- checks de CI.

## Descoberta dos requests

Os requests são objetos estáticos embutidos na imagem carregada.

O ChrisOS abre a região com:

~~~text
LIMINE_REQUESTS_START_MARKER
~~~

e fecha com:

~~~text
LIMINE_REQUESTS_END_MARKER
~~~

Na base revision 3, delimitadores presentes devem ser respeitados.

Os requests válidos estão na região delimitada da imagem carregada.

## Alinhamento

O protocolo especifica markers e base-revision tag em fronteiras de 8 bytes.

As estruturas são naturalmente compostas de palavras de 64 bits.

O linker posiciona a seção como um todo em fronteira de 4 KiB, mais forte que o mínimo exigido para o início da seção.

Os objetos internos ainda precisam manter alinhamento compatível.

## Placement no source

bootinfo.c utiliza atributos como:

~~~text
__attribute__((used, section(".limine_requests")))
~~~

used impede o compilador de remover um objeto que parece não ser referenciado.

section coloca os objetos no local que o linker trata como metadata de boot.

Esses atributos fazem parte do ABI do boot.

## Preservação pelo linker

kernel/metal/linker.ld contém:

~~~text
.limine_requests : ALIGN(4K) {
    KEEP(*(.limine_requests_start))
    KEEP(*(.limine_requests))
    KEEP(*(.limine_requests_end))
} :requests
~~~

KEEP impede garbage collection dos requests.

A seção pertence ao PT_LOAD requests.

Um linker self-hosted que não reproduza isso pode gerar ELF válido estruturalmente, mas não bootável pelo Limine.

## Permissões do segmento de requests

O linker define:

~~~text
requests PT_LOAD FLAGS(6)
~~~

FLAGS 6 significa:

~~~text
PF_R | PF_W
~~~

sem execução.

Isso é coerente porque o Limine precisa escrever ponteiros de resposta nos objetos.

Metadata de protocolo é dado, não código executável.

## Handshake da base revision

O base revision tag possui três valores de 64 bits.

Conceitualmente:

~~~text
magic_0
magic_1
requested_revision
~~~

Quando a revisão é suportada, o bootloader sinaliza isso alterando o último valor para zero.

O ChrisOS verifica:

~~~text
LIMINE_BASE_REVISION_SUPPORTED
~~~

e entra em panic se base revision 3 não tiver sido aceita.

O header fixado também permite consultar a revisão realmente carregada, mas o ChrisOS ainda não a registra.

## Por que validar base revision primeiro

Se o bootloader não honra a base revision solicitada, semânticas de ponteiros e mappings podem divergir do que o kernel espera.

Portanto essa validação precisa ocorrer antes de consumir responses.

bootinfo_init faz exatamente isso.

## Os cinco requests atuais

O ChrisOS possui:

| Request | Obrigatório? | Consumidor principal |
|---|---:|---|
| framebuffer | sim | gráficos / bootinfo |
| HHDM | sim | acesso à memória física |
| memory map | sim | PMM / diagnóstico |
| MP | sim | SMP |
| executable command line | não | boot flags |

Os quatro primeiros são dependências duras.

A command line é opcional.

## Requests ausentes também importam

O kernel atual não solicita:

- bootloader information;
- firmware type;
- stack size;
- paging mode;
- executable file;
- módulos;
- RSDP;
- SMBIOS;
- EFI System Table;
- EFI memory map;
- executable address;
- TSC frequency;
- entropy.

Nenhum subsistema deve presumir que esses responses já existem.

## ABI de entrada

O protocolo define ABI por arquitetura.

Para x86-64:

~~~text
System V ABI
sem FP/SIMD na interação com o protocolo
~~~

Isso corresponde à família de ABI utilizada pelo kernel.

O build host ainda desativa MMX/SSE/SSE2 no perfil inicial e o kernel inicializa SIMD posteriormente.

## Entry point ELF

O ChrisOS não usa Entry Point request.

Portanto Limine entra pelo entry point do formato executável.

O linker declara:

~~~text
ENTRY(kstart)
~~~

Logo e_entry resolve para kstart.

kstart(void) não recebe ponteiro de boot em parâmetro.

O estado é acessado pelos objetos estáticos que o Limine modificou antes da entrada.

## Placement higher-half

O protocolo Limine carrega executáveis no higher half a partir de:

~~~text
0xffffffff80000000
~~~

Executáveis não relocáveis devem ser linkados para endereços virtuais compatíveis.

O ChrisOS inicia exatamente em:

~~~text
0xffffffff80000000
~~~

no linker script.

Isso corresponde diretamente ao modelo do protocolo.

## Permissões PT_LOAD

Limine traduz permissões dos segmentos ELF para os mappings iniciais.

No ChrisOS:

~~~text
requests -> RW
text/rodata -> RX
data/bss -> RW
~~~

Em x86-64, execução protegida depende de NX quando disponível.

Isso já cria separação útil antes de o MM do kernel assumir controle completo.

## Endereço físico não é endereço virtual

O kernel é linkado virtualmente no higher half.

O bootloader escolhe onde colocar os bytes fisicamente.

Não existe garantia:

~~~text
physical == virtual
~~~

Caso o kernel precise conhecer a base física, deve solicitar executable-address em vez de inferir por page tables internas do bootloader.

## Paging mode padrão

O ChrisOS não solicita paging-mode.

Em x86-64, o default Limine é paging de quatro níveis.

Isso coincide com o MM atual:

~~~text
PML4
 -> PDPT
 -> PD
 -> PT
~~~

A dependência ainda é implícita.

Um caminho mais forte seria solicitar explicitamente 4-level ou implementar LA57.

## Suposição atual do MM

mm_translate e os walkers atuais partem de PML4 e possuem quatro níveis.

Eles não entendem LA57.

Se um dia o boot request ativar cinco níveis, o MM precisará evoluir ao mesmo tempo.

## Estado x86-64 na entrada

No handoff, rip aponta para o entry e o bootloader já estabeleceu execução 64-bit paginada.

O protocolo garante, entre outras coisas:

- segmento de código 64-bit;
- seletores de dados;
- bases FS/GS em zero;
- IF limpo;
- VM limpo;
- DF limpo;
- CR0.PE;
- CR0.WP;
- CR0.PG;
- CR4.PAE;
- EFER.LME/LMA;
- NX quando disponível;
- A20 aberto;
- IRQs do PIC mascaradas;
- Boot Services encerrados quando o boot foi EFI.

Isso permite entrar diretamente em C freestanding x86-64.

## O que base revision 3 não garante

Revisões posteriores tornaram o estado x86 mais estrito.

Base revision 5, por exemplo, define com mais precisão control registers, RFLAGS, descriptor tables, APIC e IOMMU.

O ChrisOS solicita base revision 3.

Logo a documentação não deve atribuir ao handoff atual garantias que só surgiram depois.

O kernel inicializa GDT e IDT próprios rapidamente.

## Stack inicial

Limine fornece stack em memória bootloader-reclaimable.

O protocolo atual garante no mínimo 64 KiB, salvo Stack Size request maior.

O ChrisOS não faz esse request.

Portanto a stack garantida na entrada é a default do protocolo, e não a área de 1 MiB reservada pelo linker.

__stack_top é usada posteriormente em TSS rsp0 e pertence a outro estágio.

## Return address inválido

O protocolo coloca zero como return address inválido antes do salto ao executável.

Um entry de kernel não deve retornar.

kstart prossegue para o runtime do sistema.

## General-purpose registers

O estado inicial dos GPRs segue o contrato do protocolo e não é usado como canal privado de bootinfo.

Como kstart não recebe argumentos, toda informação vem dos requests/responses.

## Ownership de descriptor tables

Limine fornece descriptor state suficiente para a entrada.

O ChrisOS chama gdt_init e idt_init e passa a controlar GDT, TSS e IDT próprios.

As tabelas do bootloader são apenas parte da transição.

## HHDM

Higher Half Direct Map request devolve um offset.

Para um endereço físico que realmente esteja coberto pelo HHDM:

~~~text
virtual = physical + offset
~~~

bootinfo_phys_to_virt faz exatamente isso.

O offset é escolhido pelo bootloader e nunca pode ser hardcoded.

## HHDM não é cast universal de endereço físico

A base revision define quais classes são mapeadas.

Na base revision 3, as classes relevantes são:

- usable;
- bootloader reclaimable;
- executable and modules;
- framebuffer.

Os primeiros 4 GiB não são mapeados incondicionalmente.

Portanto:

~~~text
phys + hhdm_offset
~~~

só é válido se o range físico pertencer ao HHDM.

Não substitui ioremap.

## Exceção MMIO já reconhecida no ChrisOS

dump_lapic_not_ram registra explicitamente que:

~~~text
HHDM + LAPIC
não é mapping MMIO válido
~~~

O LAPIC depois é mapeado por caminho MMIO dedicado.

A distinção correta é:

~~~text
direct map de RAM
!=
MMIO de dispositivo
~~~

## Base revision 3 e a lacuna ACPI

O probe ACPI atual usa bootinfo_phys_to_virt para examinar endereços físicos do firmware legado.

Porém base revision 3 não mapeia genericamente Reserved, ACPI Reclaimable e ACPI NVS pelo HHDM.

Pode ocorrer:

~~~text
RSDP físico existe
mas
physical + HHDM não está mapeado
~~~

em hardware real.

Isso é uma lacuna de portabilidade.

A correção preferida é adicionar o RSDP request do Limine.

## Mudanças da base revision 4

A especificação atual amplia o HHDM na base revision 4 para incluir:

- reserved-mapped;
- ACPI reclaimable;
- ACPI NVS.

Também introduz LIMINE_MEMMAP_RESERVED_MAPPED.

Esse é um benefício concreto de migrar além da base revision 3.

Ainda assim, toda suposição de memory type precisa ser auditada.

## Framebuffer response

O response pode informar:

- address;
- width;
- height;
- pitch;
- bpp;
- memory model;
- channel masks;
- EDID;
- modes em revisões compatíveis.

O ChrisOS escolhe o primeiro framebuffer e exige 32 bpp.

## Simplificação atual do framebuffer

bootinfo_init copia:

- address;
- width;
- height;
- pitch;
- bpp.

Não retém:

- memory model;
- masks RGB;
- shifts;
- EDID;
- lista de modes.

O modelo interno é mais estreito que o protocolo.

No hardware físico, 32 bpp não deve ser tratado como prova automática de layout de cores compatível.

## Endereço do framebuffer

O address do framebuffer já é um endereço virtual mapeado segundo o protocolo.

O ChrisOS o armazena diretamente.

mm_init depois usa mm_virt_to_phys para descobrir o backing físico.

Isso depende de manter os mappings herdados ativos.

## Pitch

O kernel preserva o pitch retornado.

Ele não presume:

~~~text
pitch == width * 4
~~~

Essa é uma propriedade importante para framebuffers de firmware.

## Memory map

A resposta contém:

~~~text
entry_count
entries[]
~~~

Cada entry possui:

~~~text
base
length
type
~~~

base é endereço físico.

O ponteiro para a estrutura entry é ponteiro do protocolo.

Esses domínios de endereço não podem ser confundidos.

## Tipos atuais de memória

O header fixado define:

| Tipo | Significado |
|---:|---|
| 0 | USABLE |
| 1 | RESERVED |
| 2 | ACPI_RECLAIMABLE |
| 3 | ACPI_NVS |
| 4 | BAD_MEMORY |
| 5 | BOOTLOADER_RECLAIMABLE |
| 6 | EXECUTABLE_AND_MODULES |
| 7 | FRAMEBUFFER |

memmap_type_name entende essas classes.

## bootinfo retém o response original

bootinfo_init mantém:

~~~text
static struct limine_memmap_response *memmap_response;
~~~

As funções posteriores continuam lendo o response original.

O memory map não é copiado integralmente para memória pertencente ao kernel.

Isso determina o lifetime da memória do bootloader.

## Lifetime dos responses

O protocolo coloca responses e estruturas relacionadas em bootloader-reclaimable memory.

Reclaimable não significa liberável imediatamente em kstart.

O kernel precisa primeiro remover todas as dependências.

O ChrisOS mantém ponteiros vivos após bootinfo_init.

## PMM atual

pmm_init mantém LIMINE_MEMMAP_BOOTLOADER_RECLAIMABLE como reservado.

Não existe etapa posterior que libere essa classe.

É conservador e seguro.

A consequência é memória permanentemente indisponível ao allocator.

## Page tables do Limine também são reclaimable

A especificação coloca page tables do bootloader em bootloader-reclaimable memory.

mm_init lê o CR3 herdado:

~~~text
mm_cr3_phys = current CR3
~~~

e adota essas mesmas tabelas como raiz do kernel.

Depois o ChrisOS modifica e amplia essas tabelas.

Logo copiar bootinfo não é suficiente para liberar a memória do bootloader.

## Sequência segura para reclamation

Um caminho futuro precisa:

1. copiar dados duráveis dos responses;
2. concluir o handoff dos APs;
3. remover dependência dos MP structures;
4. criar page tables próprias;
5. trocar CR3;
6. abandonar stacks do bootloader;
7. provar ausência de ponteiros restantes;
8. liberar páginas elegíveis.

O ChrisOS ainda não concluiu isso.

## Contagem USABLE

bootinfo_init soma lengths de entries USABLE em usable_bytes.

pmm_init libera apenas páginas completas desses ranges.

Essa separação entre parsing e geometria do allocator é adequada.

## Alinhamento no PMM

Ranges usáveis são alinhados para dentro.

Ranges reservados são alinhados para fora.

Isso impede alocar página parcialmente ocupada por uma região reservada.

## ACPI reclaimable

ACPI_RECLAIMABLE permanece reservada porque o bitmap começa totalmente ocupado e somente USABLE é liberado.

Uma futura camada ACPI pode liberar essas páginas quando o lifetime das tabelas permitir.

## Self-test HHDM

O self-test do PMM chama bootinfo_phys_to_virt apenas para páginas obtidas de USABLE.

Isso é compatível com base revision 3.

O teste não demonstra que todo endereço físico possui alias HHDM.

## MP request

MP não é apenas uma lista de CPUs.

A presença desse request instrui o bootloader a bootstrapar processadores secundários.

No x86, o response traz:

- flags;
- BSP LAPIC ID;
- CPU count;
- CPU descriptors.

Cada descriptor inclui:

- processor ID;
- LAPIC ID;
- goto_address;
- extra_argument.

## Política x2APIC

O ChrisOS usa:

~~~text
.flags = 0
~~~

e não solicita x2APIC.

Isso combina com estruturas atuais que indexam LAPIC IDs em arrays pequenos e mantêm várias suposições xAPIC.

Migrar para x2APIC exige alterar request e implementação SMP/APIC em conjunto.

## Handoff dos APs

smp_init:

1. identifica BSP e APs;
2. aloca stacks pertencentes ao kernel;
3. associa índice lógico de CPU;
4. grava extra_argument;
5. grava ap_entry em goto_address;
6. espera os APs entrarem online.

O startup arquitetural de baixo nível é executado pelo bootloader.

O ChrisOS assume o AP quando ele entra em ap_entry.

## Semântica de ponteiros MP

Os ponteiros de response já seguem as regras do protocolo.

ap_info_virt possui lógica defensiva que adiciona HHDM quando o ponteiro não parece higher-half.

Esse comportamento representa compatibilidade histórica/ambiguidade.

Com um contrato fixado e validado, a interpretação deveria se tornar única em vez de heurística.

## Troca de stack dos APs

Os APs migram para stacks alocadas pelo kernel antes da execução normal de workers.

Isso reduz dependência de stacks fornecidas pelo Limine.

É uma transição importante de ownership.

## Executable command line

O response de command line é opcional.

Quando existe, o ChrisOS reconhece tokens como:

- safe;
- nosmp;
- noapic;
- noac97;
- nonet;
- nojit;
- gfx.stress;
- gfx.virgl.debug;
- gfx.backend=framebuffer ou virtio;
- gfx.3d=auto, software ou virgl.

É o canal mais precoce para alterar política de boot.

## Safe mode

safe habilita:

~~~text
nosmp
noapic
noac97
nonet
nojit
~~~

Isso é útil no bring-up físico porque permite desligar subsistemas experimentais sem recompilar.

## Configuração atual do Limine

O arquivo atual contém:

~~~text
/ChrisOS
    protocol: limine
    path: boot():/boot/kernel.elf
    resolution: 1920x1080x32
~~~

Não existe command line explícita nesse arquivo atualmente.

O parser do kernel está pronto para consumir uma quando configurada.

## Revision zero nos requests

Todos os requests atuais usam revision zero.

É um baseline conservador.

O kernel não deveria acessar campos cuja semântica dependa de revisões maiores sem negociar isso.

## Validações existentes

bootinfo_init valida:

- base revision suportada;
- framebuffer response;
- framebuffer_count;
- array de framebuffers;
- HHDM response;
- memmap response;
- array de entries;
- MP response;
- CPU count;
- array de CPUs;
- entries de memmap não nulas;
- primeiro framebuffer em 32 bpp.

É uma boa fronteira de validação inicial.

## Hardening adicional

Pode evoluir com:

- limite máximo de entries;
- base + length com overflow check;
- detecção de ranges sobrepostos;
- validação de pitch/tamanho de framebuffer;
- validação de formato de pixel;
- limite de CPU count;
- política para LAPIC IDs;
- limite de command line;
- validação de response revision.

Confiar no bootloader não elimina o valor de parser defensivo.

## Aritmética de ranges

Qualquer:

~~~text
base + length
~~~

pode fazer wrap de 64 bits.

Um helper seguro verifica:

~~~text
length <= UINT64_MAX - base
~~~

antes de formar end.

O checker do capítulo testa essa invariável.

## Contrato fixado versus upstream atual

Existem duas linhas de tempo:

~~~text
ChrisOS fixado
  Limine v9.x
  API revision 3
  base revision 3

upstream atual
  header novo
  base revision 6 corrente
  base revisions 0..5 deprecated
~~~

A documentação precisa representar o source real e não fingir migração já concluída.

## Migração controlada

A evolução deve:

1. atualizar o Limine fixado;
2. atualizar o protocol header;
3. adaptar compatibilidade de API;
4. solicitar base revision corrente;
5. tratar novos memory types;
6. adicionar RSDP request;
7. auditar HHDM;
8. auditar entry state;
9. rodar gates QEMU BIOS/UEFI;
10. rodar boot do disco instalado somente via OVMF;
11. atualizar o baseline de hardware físico.

## RSDP é o request ausente mais urgente

O capítulo ACPI mostrou dependência de scan legado.

Limine já possui RSDP feature.

O caminho desejado é:

~~~text
firmware
 -> Limine
 -> RSDP response
 -> parser ACPI ChrisOS
~~~

Isso remove a dependência de ranges físicos legados estarem no HHDM.

## Bootloader info

Bootloader-info permitiria registrar nome e versão.

Um log futuro poderia mostrar:

~~~text
Bootloader: Limine <version>
Loaded base revision: <n>
~~~

Isso melhora reprodutibilidade e diagnóstico.

## Firmware type

Firmware-type permitiria confirmar explicitamente EFI64 ou outro ambiente.

É mais robusto que inferir o firmware pelo meio de boot.

## Executable address

A feature de executable-address fornece base física e virtual.

É útil para:

- accounting de memória;
- validação do linker;
- proveniência;
- diagnóstico de relocação.

O ChrisOS ainda não solicita.

## Stack size

Sem request de stack size, a entrada usa o mínimo default do protocolo.

Se o early boot crescer, o kernel pode solicitar uma stack maior ou trocar mais cedo para stack BSP própria.

A segunda opção melhora ownership.

## Paging mode

Hoje o kernel depende do default 4-level.

Um request explícito tornaria essa suposição formal.

Ou o MM precisa ser ampliado para LA57.

## EFI System Table

Limine pode fornecer EFI System Table.

O ChrisOS só deveria preservá-la se existir um projeto concreto de Runtime Services.

Guardar ponteiro de firmware sem consumidor aumenta a superfície de lifetime e segurança.

## EFI memory map

O memory map normalizado pelo Limine já atende o PMM atual.

Descriptors EFI crus são necessários principalmente para Runtime Services ou atributos de firmware mais específicos.

Devem ser adicionados quando houver consumidor real.

## Implicações para self-hosting

O toolchain nativo precisa reproduzir o ABI de boot.

KCC deve compilar:

- limine.h;
- initializers dos requests;
- constantes grandes de 64 bits;
- section attributes;
- globals volatile.

ChrisLd precisa preservar:

- markers;
- base revision;
- requests;
- permissões PT_LOAD;
- higher-half layout;
- ELF entry.

Boot equivalence depende tanto de metadata/link quanto de machine code.

## Dependência Limine dentro do KCC

KCC atualmente predefine:

~~~text
LIMINE_API_REVISION = 3
~~~

durante preprocessing.

Migrar a API do Limine afeta também o bootstrap do compilador.

Não é alteração restrita ao bootinfo.

## Por que os requests são volatile

O source inicializa response com zero.

O bootloader externo altera o objeto antes da execução do kernel.

volatile impede otimizações que tratem aquele estado como imutável.

used resolve outro problema: retenção do objeto.

São atributos com finalidades diferentes.

## Referências externas e garbage collection

O grafo normal de símbolos não sabe que Limine varre bytes da imagem atrás dos magics.

Sem KEEP, o linker pode remover metadata aparentemente inalcançável.

É um exemplo clássico de dado observado por um interpretador externo.

## BootSnapshot durável

Uma fronteira interna melhor seria copiar o necessário para uma estrutura pertencente ao kernel:

~~~text
BootSnapshot
  protocol revision
  bootloader identity
  firmware type
  framebuffer
  HHDM
  memory ranges[]
  CPUs[]
  RSDP
  SMBIOS
  executable identity
  command line
~~~

Depois de trocar page tables e concluir APs, os ponteiros Limine poderiam ser descartados.

## Diferença para ChrisVM

ChrisVM protocol v1 não implementa Limine.

Ele configura diretamente:

- long mode;
- page tables;
- GDT;
- stack;
- framebuffer;
- entry ELF.

Não existe scan de requests nem responses Limine.

Por isso o kernel real do ChrisOS ainda não pode ser bootado por esse protocolo.

## Alternativas para ChrisVM v2

### ABI compatível com Limine

ChrisVM poderia localizar requests e preencher responses Limine.

Isso maximiza compatibilidade binária.

Também acopla ChrisVM às versões do protocolo externo.

### ABI interno normalizado

O ChrisOS pode concluir um adaptador de boot:

~~~text
adaptador Limine ----\
                      -> BootSnapshot -> kernel
adaptador ChrisVM ---/
~~~

Isso mantém um contrato interno único e permite mais de um ambiente externo.

## Fronteira preferida

A arquitetura mais limpa é:

~~~text
ambiente externo de boot
      |
adaptador pequeno
      |
snapshot imutável do kernel
      |
PMM / MM / SMP / gráficos / ACPI
~~~

bootinfo.c já inicia essa direção, mas ainda retém ponteiros externos de memmap e MP.

## Testes determinísticos

Após separar parsing dos globals reais, testes host podem injetar:

- base revision não suportada;
- response obrigatório ausente;
- entry nula;
- ranges sobrepostos;
- overflow;
- CPU count absurdo;
- framebuffer inválido;
- command lines diversas.

A fronteira de boot então se torna fuzzável.

## Localização de falhas

Os panic paths atuais distinguem:

~~~text
base revision não suportada
framebuffer ausente
HHDM ausente
memmap ausente
MP ausente
framebuffer não 32 bpp
MP sem CPUs
entry de memmap nula
~~~

Quando uma dessas mensagens aparece, o processador já chegou a kstart.

Falhas anteriores pertencem a firmware, loader ou carregamento da imagem.

## Matriz da implementação atual

| Capability | Estado |
|---|---|
| dependência Limine fixada | implementada |
| v9.x API revision 3 | implementada |
| Limine base revision 3 | implementada |
| migração para base revision 6 | não implementada |
| markers start/end | implementados |
| PT_LOAD dedicado para requests | implementado |
| framebuffer request | implementado |
| HHDM request | implementado |
| memory-map request | implementado |
| MP request | implementado |
| command-line request | implementado |
| bootloader-info request | não implementado |
| firmware-type request | não implementado |
| stack-size request | não implementado |
| paging-mode request | não implementado |
| RSDP request | não implementado |
| SMBIOS request | não implementado |
| EFI System Table request | não implementado |
| EFI memory-map request | não implementado |
| executable-address request | não implementado |
| TSC frequency request | não implementado |
| entropy request | não implementado |
| deep copy de todos os responses | não implementada |
| reclaim de bootloader-reclaimable | não implementado |
| page-table root próprio | não implementado |
| MP request com x2APIC | não implementado |
| boot ChrisVM compatível com Limine | não implementado |

## Checker reproduzível

scripts/check_limine_examples.py valida:

1. start/end markers;
2. base revision 3;
3. API revision 3 no source/build;
4. exatamente os cinco requests atuais;
5. revision zero nos requests;
6. KEEP e PT_LOAD de requests;
7. base higher-half;
8. dependência de paging de quatro níveis;
9. modelo HHDM da base revision 3;
10. ausência de RSDP, paging-mode e stack-size requests;
11. reserva de bootloader-reclaimable no PMM;
12. retenção dos ponteiros Limine de memmap/MP;
13. SHA fixado do Limine;
14. range arithmetic segura.

Não é uma suíte de conformidade Limine.

## Limite de validação

Este capítulo foi conciliado com ChrisOS main:

~~~text
da3df29cb397932c43d32373871fb9380e688ade
~~~

e com a dependência Limine fixada:

~~~text
ee5d29cd0a8034612dcd1df3f00052480db785c5
~~~

A especificação upstream atual também foi revisada. Ela considera base revision 6 como corrente não deprecated e revisions 0 a 5 deprecated.

O capítulo descreve primeiro o contrato realmente usado pelo ChrisOS e depois a evolução upstream.

Execute:

~~~text
python scripts/check_limine_examples.py --source .source
~~~

## Gatilhos de revisão

Revisar quando:

- o commit Limine fixado mudar;
- LIMINE_API_REVISION mudar;
- base revision mudar;
- qualquer request revision mudar;
- RSDP/SMBIOS/firmware-type forem adicionados;
- paging mode se tornar explícito;
- x2APIC for solicitado;
- bootinfo copiar memmap/MP;
- page tables próprias substituírem CR3 herdado;
- bootloader-reclaimable começar a ser liberado;
- layout de requests do linker mudar;
- ChrisLd bootar kernel real;
- ChrisVM ganhar handoff compatível com Limine ou normalizado.

## Referências primárias

- Limine Boot Protocol, especificação oficial limine-protocol.
- Header oficial do protocolo Limine.
- limine.h v9.x fixado em ee5d29cd0a8034612dcd1df3f00052480db785c5.
- Arquivos-fonte do ChrisOS listados no front matter.
