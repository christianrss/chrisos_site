---
id: boot-information
lang: pt-br
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/pmm.c
  - kernel/metal/mm.c
  - kernel/metal/smp.c
  - kernel/metal/acpi.c
  - kernel/metal/start.c
symbols:
  - bootinfo_init
  - bootinfo_get
  - bootinfo_memmap_count
  - bootinfo_memmap_entry
  - bootinfo_mp_response
  - bootinfo_phys_to_virt
  - pmm_init
  - mm_init
  - smp_init
depends_on:
  - limine
related:
  - physical-memory
  - hhdm
  - interrupts-smp
  - acpi-platform
  - higher-half-kernel
  - resource-lifetime
  - chrisvm
---

# Informações de boot, normalização e ownership

## Escopo

Informação de boot não é apenas um conjunto de valores entregue ao kernel.

É um problema de lifetime e ownership.

Na entrada do kernel, o ChrisOS recebe dados criados por um ambiente externo. Hoje esse ambiente é o Limine. No futuro também pode ser o ChrisVM ou outro adaptador de boot.

Para cada informação, o kernel precisa responder:

1. qual fato está sendo comunicado;
2. onde os bytes originais vivem;
3. por quanto tempo esses bytes continuam válidos;
4. se o kernel já copiou o fato para memória que controla.

Essas respostas determinam quando uma região pode ser liberada com segurança.

O código atual do ChrisOS normaliza apenas parte do estado Limine.

Alguns scalars são copiados para struct bootinfo, mas memory map e multiprocessor response continuam acessados por ponteiros pertencentes ao Limine.

Essa distinção é o centro deste capítulo.

![Transição de ownership das informações de boot](../../assets/diagrams/boot-information-pt-br.svg)

## Dados externos versus estado do kernel

Na entrada:

~~~text
Limine = produtor
ChrisOS = consumidor
~~~

Arquitetura desejada:

~~~text
protocolo externo
      |
responses crus
      |
validação
      |
normalização
      |
snapshot pertencente ao kernel
      |
PMM / MM / SMP / gráficos / ACPI
~~~

A implementação atual para no meio:

~~~text
responses Limine
      |
      +-- copia scalars para struct bootinfo
      |
      +-- mantém memmap_response
      |
      +-- mantém mp_request.response
~~~

Logo objetos do protocolo ainda fazem parte do estado vivo do kernel.

## O que significa normalizar

Normalizar converte dados específicos do bootloader em dados definidos pelo ChrisOS.

Não é apenas trocar nomes.

É desacoplamento arquitetural.

Em vez de PMM depender de:

~~~text
struct limine_memmap_entry
~~~

o kernel pode definir:

~~~text
struct boot_mem_range {
    uint64_t base;
    uint64_t length;
    enum boot_mem_type type;
};
~~~

Assim, Limine passa a ser um adaptador e deixa de ser o modelo de dados de todo o kernel.

O mesmo princípio vale para CPUs, framebuffer, firmware roots e command line.

## Vocabulário de ownership

Este capítulo utiliza quatro classes.

### Borrowed

O kernel pode ler, mas o armazenamento pertence ao bootloader.

Exemplo atual:

~~~text
memmap_response
~~~

### Copied

O kernel duplicou campos necessários para memória própria.

Exemplos:

~~~text
info.hhdm_offset
info.fb_width
info.cpu_count
~~~

### Adopted

O kernel começa a usar diretamente um objeto criado pelo bootloader como objeto de runtime.

O maior exemplo é a hierarquia de page tables ativa em CR3.

O MM não apenas lê: ele a modifica e amplia.

### Reclaimable

A memória pode voltar ao allocator somente quando nenhum objeto borrowed ou adopted depender dela.

Isso exige prova de lifetime.

O tipo de memory map sozinho não basta.

## struct bootinfo atual

O header define:

~~~text
struct bootinfo {
    hhdm_offset
    fb_addr
    fb_width
    fb_height
    fb_pitch
    fb_bpp
    usable_bytes
    memmap_entries
    cpu_count
    bsp_lapic_id
}
~~~

Esses campos são scalars copiados de responses Limine.

Depois da cópia, cada scalar individual não depende mais do response original.

Mas outras APIs continuam expondo diretamente os objetos externos.

## Resumo escalar versus snapshot completo

A struct atual é melhor descrita como resumo escalar.

Ela não contém:

- ranges de memória copiados;
- descritores de CPUs copiados;
- identidade do bootloader;
- tipo de firmware;
- RSDP;
- SMBIOS;
- masks/formato do framebuffer;
- cópia da command line;
- base física do kernel;
- base virtual do executável;
- metadata de revisão do protocolo;
- paging mode;
- proveniência completa.

Nem todos esses campos precisam existir obrigatoriamente.

O ponto é que ainda não existe um único objeto interno contendo todos os fatos que o kernel deseja preservar.

## Por que reter ponteiros importa

Se bootinfo_init copiasse todos os ranges do memory map para memória própria, o response original poderia ser abandonado.

Hoje bootinfo_memmap_entry faz:

~~~text
entry = memmap_response->entries[index]
~~~

em toda consulta.

Portanto PMM continua dependendo da árvore de objetos Limine.

SMP chama:

~~~text
bootinfo_mp_response()
~~~

que devolve diretamente o response Limine.

Dois subsistemas fundamentais ainda dependem do bootloader.

## Grafo de ownership atual

A dependência é aproximadamente:

~~~text
BOOTLOADER_RECLAIMABLE
  |
  +-- memory-map response
  |      |
  |      +-- array de pointers
  |      +-- entries
  |             |
  |             +--> PMM
  |
  +-- MP response
  |      |
  |      +-- array de CPUs
  |      +-- limine_mp_info
  |             |
  |             +--> SMP
  |
  +-- page tables iniciais
  |      |
  |      +--> CR3 ativo
  |      +--> MM modifica
  |
  +-- stacks iniciais BSP/AP
~~~

Por isso não é seguro simplesmente liberar BOOTLOADER_RECLAIMABLE.

## Categorias de lifetime

Uma arquitetura robusta deve classificar cada informação.

### Entry-only

Necessária apenas durante a transição inicial.

Exemplos:

- metadata transitória do loader;
- markers do protocolo;
- handles temporários.

### Early-boot

Necessária até o kernel assumir ownership.

Exemplos:

- CPU descriptors crus até SMP copiar topologia;
- memory map cru até normalização;
- page tables do loader até substituição.

### Persistent

Mantida pelo kernel durante todo o runtime.

Exemplos:

- topologia física normalizada;
- geometria do framebuffer;
- firmware roots;
- proveniência de boot.

### Conditionally reclaimable

Necessária até um subsistema concluir consumo.

Exemplos:

- ACPI reclaimable;
- responses Limine depois da cópia.

## Ordem atual de inicialização

kstart chama bootinfo_init muito cedo.

Depois, conceitualmente:

~~~text
bootinfo_init
   |
GDT / IDT / interrupts
   |
PMM
   |
MM
   |
heap
   |
graphics
   |
APIC / SMP
   |
ACPI
   |
storage / filesystem / desktop
~~~

Se dados do bootloader forem liberados cedo, todos os consumidores precisam:

- ter executado antes; ou
- consumir uma cópia própria.

BootSnapshot resolve a segunda opção.

## Objetivo de BootSnapshot

A estrutura interna desejada pode ser pensada como:

~~~text
BootSnapshot
{
    protocol;
    firmware;
    kernel_image;
    hhdm;
    framebuffer;
    memory_ranges[];
    cpus[];
    firmware_roots;
    command_line;
    provenance;
}
~~~

Não precisa ser literalmente uma struct gigante.

É uma fronteira de ownership.

A propriedade fundamental é:

~~~text
após finalizar o snapshot,
subsistemas não precisam de objetos crus do bootloader
~~~

## Imutabilidade

A maior parte das informações de boot é imutável.

A API interna pode ser:

~~~text
const struct boot_snapshot *boot_snapshot_get(void)
~~~

Depois de finalizado:

- memory topology não deve mudar casualmente;
- CPU topology de entrada é histórica;
- command line permanece fixa;
- firmware roots são fatos do boot.

Hotplug futuro pertence a outra estrutura de runtime.

## Memory ranges normalizados

Um range interno pode ser:

~~~text
struct boot_mem_range {
    uint64_t base;
    uint64_t length;
    uint32_t type;
    uint32_t flags;
};
~~~

O type deve ser enum do ChrisOS, não constante Limine.

Exemplo:

~~~text
BOOT_MEM_USABLE
BOOT_MEM_RESERVED
BOOT_MEM_ACPI_RECLAIM
BOOT_MEM_ACPI_NVS
BOOT_MEM_BAD
BOOT_MEM_BOOTLOADER
BOOT_MEM_KERNEL
BOOT_MEM_FRAMEBUFFER
BOOT_MEM_MMIO
BOOT_MEM_UNKNOWN
~~~

Assim, evoluir Limine não obriga PMM a conhecer seu ABI.

## Preservar metadata original

Normalizar não significa perder informação.

Se uma nova revisão Limine introduzir outro type, o adaptador pode preservar:

- categoria normalizada;
- valor raw;
- flags de interpretação parcial.

Nunca mapear unknown automaticamente para usable.

Unknown deve ser tratado como reserved.

## Invariantes do memory map

Antes de aceitar um range:

- base precisa caber em uint64;
- length precisa ser válido;
- base + length não pode wrap;
- política de alinhamento deve ser explícita;
- type desconhecido deve falhar fechado;
- quantidade de ranges deve respeitar limite.

Memory map é input externo privilegiado.

Precisa de parser defensivo.

## Ordenação

O snapshot pode ordenar ranges por base.

Vantagens:

- overlap detection;
- logs determinísticos;
- coalescing;
- testes reproduzíveis.

Não presumir que o bootloader já ordenou a lista salvo garantia explícita.

## Detecção de overlap

Depois de ordenar:

~~~text
prev_end <= current_base
~~~

é uma invariável simples.

Se houver overlap, políticas possíveis:

- panic;
- prioridade explícita;
- split em ranges canônicos.

Durante hardening, falhar fechado é mais seguro.

Resolver silenciosamente pode transformar firmware reservado em RAM utilizável.

## Coalescing

Ranges adjacentes com mesmo tipo podem ser unidos:

~~~text
A.end == B.base
A.type == B.type
~~~

Isso reduz a quantidade de entradas.

Entretanto preservar os ranges raw pode ser útil para debug.

Coalescing deve ocorrer após validação.

## Snapshot não deve aplicar política de páginas

Idealmente o snapshot conserva ranges exatos em bytes.

O PMM transforma isso em páginas completas.

São responsabilidades diferentes:

~~~text
BootSnapshot:
o que o loader informou

PMM:
quais páginas inteiras podem ser alocadas
~~~

Misturar as duas perde fidelidade.

## Transformação do PMM

O PMM atual usa alinhamento assimétrico correto:

~~~text
usable:
start para cima
end para baixo

reserved:
start para baixo
end para cima
~~~

Somente páginas completamente usáveis ficam livres.

Essa regra deve continuar na fronteira PMM.

## Capacidade do memory map

No early boot não há heap confiável.

Opções:

- array estático com máximo explícito;
- arena de boot em BSS;
- sizing em duas passagens;
- allocator inicial dedicado.

Array estático é o caminho mais simples primeiro.

## Exemplo de capacidade

Algo como:

~~~text
#define BOOT_MAX_MEM_RANGES 256
~~~

pode ser um ponto de partida.

Se o raw map exceder a capacidade, o kernel deve falhar claramente.

Nunca truncar.

Um map truncado pode omitir regiões reservadas.

## Normalização da topologia de CPU

O MP response também deve ser copiado.

Exemplo:

~~~text
struct boot_cpu {
    uint32_t processor_id;
    uint32_t apic_id;
    uint32_t logical_index;
    uint32_t flags;
};
~~~

Depois SMP não precisa mais de struct limine_mp_info para consultar topologia.

## Identidade do BSP

O snapshot deve armazenar explicitamente:

~~~text
bsp_index
bsp_apic_id
cpu_count
cpus[]
~~~

Não obrigar consumidores a descobrir BSP repetidamente.

Isso também centraliza detecção de IDs duplicados.

## Limite de CPU count

Hoje bootinfo valida apenas que cpu_count não é zero.

O adaptador futuro deve reconciliar o valor externo com:

- SMP_CPU_CAP;
- SMP_MAX_APS;
- tamanhos de arrays internos.

A validação precisa acontecer antes de índices serem usados.

## IDs duplicados

Topologia malformada pode repetir:

- processor ID;
- LAPIC ID.

Isso deve ser detectado.

APIC ID duplicado pode quebrar:

- IPI;
- TLB shootdown;
- accounting;
- CPU retirement.

Não é apenas metadata estética.

## Preparação para x2APIC

O snapshot deve manter APIC IDs completos.

Não incorporar truncamento de 8 bits no ABI interno.

Restrições de xAPIC pertencem ao subsistema APIC atual.

## Handoff SMP e lifetime

Há uma sutileza.

limine_mp_info não é somente informação estática.

goto_address e extra_argument são canais ativos usados para iniciar APs.

Logo o raw MP response só pode ser abandonado **depois** do handoff.

Sequência:

~~~text
copiar topologia
   |
alocar estado/stacks
   |
escrever goto_address
   |
esperar APs
   |
confirmar stacks próprias
   |
descartar objetos Limine MP
~~~

Isso difere do memory map, que pode ser deep-copied imediatamente.

## Framebuffer normalizado

A descrição interna deveria conter:

~~~text
address
physical_address
width
height
pitch
bpp
memory_model
red_mask_size
red_mask_shift
green_mask_size
green_mask_shift
blue_mask_size
blue_mask_shift
~~~

O graphics backend decide depois se suporta o formato.

## Endereço virtual versus físico do framebuffer

Limine fornece endereço virtual já mapeado.

Para substituir as page tables, o kernel também precisa conhecer o backing físico.

Portanto deve capturar:

~~~text
fb_virtual
fb_physical
~~~

antes de abandonar os mappings herdados.

Depois poderá recriar o mapping em CR3 próprio.

## Tamanho do framebuffer

Não calcular espaço apenas por:

~~~text
width * height * bytes_per_pixel
~~~

porque pitch pode ser maior que row width.

A região acessada é baseada em:

~~~text
pitch * height
~~~

com overflow check.

## Validação de pixel format

32 bpp não garante um único layout.

O snapshot deve copiar masks e shifts.

O backend pode classificar:

~~~text
XRGB8888
XBGR8888
custom masks
unsupported
~~~

Hoje bootinfo só exige bpp == 32.

## HHDM normalizado

O offset é copiado hoje, mas a validade dos ranges não é representada.

Uma API futura pode oferecer:

~~~text
boot_hhdm_contains(phys, size)
boot_phys_to_hhdm(phys, size)
~~~

em vez de permitir qualquer soma.

Isso incorpora a política derivada do memory map.

## Conversão segura physical -> virtual

Hoje:

~~~text
bootinfo_phys_to_virt(phys)
~~~

apenas soma o offset.

Uma versão hardened deve rejeitar ranges que não estejam garantidamente direct-mapped.

MMIO continua usando map_mmio_page ou mecanismo equivalente.

## Command line

O parser atual já aplica um bom padrão.

Ele lê a string externa uma vez e converte para flags internas.

Depois nenhum subsistema precisa reconsultar o Limine para essas opções.

Esse padrão deveria ser replicado em memory map e CPU topology.

## Limite da command line

Hoje o parser percorre até NUL sem máximo explícito.

Uma fronteira defensiva deve definir:

~~~text
BOOT_CMDLINE_MAX
~~~

e copiar para buffer próprio.

Sempre terminar com NUL.

## Flags desconhecidas

Flags desconhecidas são ignoradas.

Isso favorece forward compatibility.

Um modo diagnóstico poderia registrar tokens desconhecidos para detectar typos.

## Firmware roots

BootSnapshot é o lugar certo para transportar roots como:

- RSDP;
- SMBIOS;
- EFI System Table, apenas se Runtime Services forem desejados;
- DTB em outras arquiteturas.

Os subsistemas não devem depender diretamente de types Limine.

## Ownership do RSDP

Guardar endereço RSDP não equivale a copiar tabelas ACPI.

ACPI ainda precisa:

1. validar RSDP;
2. localizar XSDT/RSDT;
3. validar SDTs;
4. determinar lifetime das tabelas;
5. só então permitir reclaim de ACPI memory.

Boot normalization e ACPI parsing são estágios distintos.

## SMBIOS

O snapshot pode carregar os entry points.

O parser SMBIOS decide depois o que manter.

Boot layer deve transportar roots, não interpretar todo firmware.

## Identidade do bootloader

Informações persistentes úteis:

~~~text
boot_protocol
bootloader_name
bootloader_version
protocol_base_revision
firmware_type
~~~

Logs poderiam mostrar:

~~~text
Boot protocol: Limine
Bootloader: Limine 9.x
Base revision: 3
Firmware: UEFI64
~~~

Isso ajuda muito em bug reports.

## Identidade do kernel

Também é útil manter:

- kernel physical base;
- kernel virtual base;
- size;
- build ID;
- SHA256/provenance.

O projeto já utiliza identidade de build.

BootSnapshot pode conectar proveniência do bootloader e da imagem.

## Fronteira de segurança

Boot info é input privilegiado.

Se bootloader for comprometido, kernel não consegue se proteger completamente de page tables ou memory maps maliciosos.

Mesmo assim, validação detecta:

- bugs de firmware;
- bugs do bootloader;
- corrupção;
- revisão incompatível;
- bugs do emulador;
- erros de adaptadores futuros.

Trust não elimina validação.

## O problema das page tables herdadas

Mesmo copiando metadata, o kernel ainda depende das page tables do Limine.

mm_init lê CR3 e guarda:

~~~text
mm_cr3_phys
~~~

Depois map_4k e outros métodos modificam a mesma hierarquia.

Isso é adoção, não cópia.

## Por que substituir as page tables

Uma raiz própria oferece:

- lifetime claro;
- permissões conhecidas;
- HHDM controlado;
- eliminação de mappings escondidos;
- reclaim seguro;
- maior paridade com ChrisVM;
- layout reproduzível.

A troca só pode ocorrer quando já for possível alocar page tables próprias.

## Plano de transição

Sequência possível:

~~~text
1. copiar memory map
2. inicializar PMM
3. alocar PML4 novo
4. mapear kernel ELF
5. mapear stack
6. construir HHDM
7. mapear framebuffer
8. mapear MMIO necessário
9. trocar CR3
10. verificar traduções
11. aposentar page tables do loader
~~~

Código em execução deve permanecer mapeado durante toda a transição.

## Página do RIP e stack

Antes de escrever CR3, o novo espaço precisa conter:

- página atual de RIP;
- stack atual;
- globals;
- código de MM;
- GDT/IDT e outros objetos se interrupções estiverem habilitadas.

Trocar page table é transição executável, não simples substituição de pointer.

## TLB

Escrever CR3 altera o contexto de tradução e invalida TLB conforme regras x86.

Fazer essa transição antes de SMP ativo simplifica coordenação.

Esse é um motivo para estabelecer a ownership barrier cedo.

## Stack BSP

A stack de entrada BSP pertence ao bootloader.

O kernel reserva __stack_top e usa depois em TSS rsp0, mas não troca imediatamente RSP para essa área.

Antes de reclaim de loader memory, o BSP deve estar explicitamente em stack própria.

## Stacks dos APs

APs já fazem melhor essa transição.

smp_init aloca stacks via PMM e ap_entry troca RSP antes do worker normal.

O BSP deveria seguir o mesmo princípio.

## Barrier de reclaim

BOOTLOADER_RECLAIMABLE só pode ser liberado quando:

~~~text
memory map copiado
CPU topology copiada
handoff dos APs concluído
BSP em stack própria
APs em stacks próprias
page tables próprias ativas
nenhum response pointer restante
nenhum dado do loader restante em uso
~~~

É uma barreira formal de lifetime.

## API de release

Em vez de PMM reinterpretar memória silenciosamente, usar operação explícita:

~~~text
boot_release_bootloader_memory()
~~~

Ela deve validar os pré-requisitos.

Depois converte ranges elegíveis em páginas livres do PMM.

## Barrier separada para ACPI

ACPI_RECLAIMABLE tem outro lifetime.

Só pode ser liberada quando ACPI confirmar que não precisa mais dos bytes originais.

Logo o kernel pode ter várias fases:

~~~text
release bootloader memory
release ACPI reclaimable
release init-only sections
...
~~~

## Máquina de estados de boot

Uma representação útil:

~~~text
BOOT_RAW
  |
BOOT_VALIDATED
  |
BOOT_SNAPSHOT_READY
  |
BOOT_PMM_READY
  |
BOOT_KERNEL_PAGING
  |
BOOT_SMP_HANDOFF_DONE
  |
BOOT_BOOTLOADER_RELEASED
  |
BOOT_RUNTIME
~~~

APIs podem exigir fase mínima.

Isso detecta uso de pointer externo depois do reclaim.

## bootinfo_ready atual

Hoje existe apenas:

~~~text
bootinfo_ready
~~~

Ele diferencia:

~~~text
não inicializado
inicializado
~~~

Não representa as várias transições de ownership.

## Acoplamento atual do bootinfo.c

O mesmo arquivo contém:

- declarations Limine;
- validation;
- command-line parser;
- API pública do boot.

Uma organização futura pode ser:

~~~text
boot/limine.c
    adapter do protocolo

boot/snapshot.c
    normalização e ownership

boot/config.c
    políticas da command line
~~~

Subsistemas consomem apenas tipos do ChrisOS.

## Leakage no header

bootinfo.h forward-declara:

~~~text
struct limine_mp_response;
~~~

e expõe:

~~~text
struct limine_mp_response *bootinfo_mp_response(void);
~~~

Isso é vazamento direto do protocolo externo na API interna.

Uma topologia normalizada elimina esse type do header.

## API pública desejada

Exemplo:

~~~text
const struct boot_snapshot *boot_snapshot_get(void);

uint64_t boot_memory_count(void);
int boot_memory_range(index, struct boot_mem_range *);

uint32_t boot_cpu_count(void);
int boot_cpu(index, struct boot_cpu *);

const struct boot_framebuffer *boot_framebuffer(void);
const struct boot_firmware_roots *boot_firmware(void);
~~~

Nenhum type Limine precisa aparecer.

## Integração com ChrisVM

ChrisVM v1 não possui boot info.

O milestone do protocolo v2 exige:

- ELF higher-half;
- boot info explícito;
- mesmo estado arquitetural;
- kernel independente de ChrisCPU/ChrisHV.

BootSnapshot é o alvo natural.

## Modelo de adaptadores

~~~text
adaptador Limine
  framebuffer
  memory map
  MP
  RSDP
       |
       v
    BootSnapshot
       ^
       |
adaptador ChrisVM
  RAM ranges
  framebuffer virtual
  vCPU topology
  ACPI sintético
~~~

Abaixo disso o kernel não precisa saber a origem.

## Por que não criar structs paralelas do ChrisVM

Se cada subsistema souber diferenciar:

~~~text
if Limine
else if ChrisVM
~~~

o acoplamento cresce em toda a árvore.

Normalizar uma vez na fronteira é melhor.

## Independência de backend

A documentação do ChrisVM já determina que o guest não deveria diferenciar ChrisCPU de ChrisHV.

O mesmo princípio se estende ao boot:

~~~text
o kernel não deveria se importar
se os fatos vieram de Limine ou ChrisVM
~~~

Somente o adaptador conhece a origem.

## Dump determinístico

BootSnapshot pode gerar um dump canônico:

~~~text
protocol=limine
firmware=uefi64
hhdm=...
mem[0]=...
cpu[0]=...
fb=...
rsdp=...
~~~

Isso facilita comparação entre:

- QEMU;
- ChrisVM;
- hardware físico.

## Hash do snapshot

Um hash diagnóstico do estado normalizado pode ajudar a detectar diferenças inesperadas.

Exemplo:

~~~text
BootSnapshot SHA256: ...
~~~

Não é autenticação.

É identidade de configuração de boot.

## Reprodutibilidade

Hardware físico pode mudar endereços entre boots.

Reprodutibilidade aqui significa:

- parser determinístico;
- ordering determinístico;
- normalização estável;
- nenhum uso de memória não inicializada.

O mesmo input cru deve produzir o mesmo snapshot.

## Testes host

Funções de normalização podem ser testadas fora do QEMU:

~~~text
normalize_memory_map()
normalize_cpu_topology()
normalize_framebuffer()
parse_boot_config()
~~~

Isso reduz custo de teste.

## Fuzzing

Memory map é ótimo alvo de fuzzing.

Casos:

- zero length;
- overflow;
- endereços máximos;
- overlap;
- ranges duplicados;
- types desconhecidos;
- input fora de ordem;
- milhares de entries.

Resultado deve ser:

- snapshot válido; ou
- rejeição explícita.

Nunca corrupção silenciosa.

## Diagnóstico antes de panic

Quando possível, logar:

~~~text
boot: invalid mem range index=17
base=...
length=...
type=...
reason=overflow
~~~

Em hardware real, reproduzir o firmware pode ser difícil.

Logs detalhados reduzem tempo de diagnóstico.

## Unknown memory = reserved

Regra crítica:

~~~text
memory type desconhecido
    ->
reserved
~~~

Nunca assumir usable.

Isso garante forward compatibility segura.

## Snapshot versioning

Se BootSnapshot algum dia virar formato binário serializado, pode ter:

~~~text
version
size
flags
~~~

Enquanto for apenas estrutura interna C, versionamento explícito pode ser desnecessário.

Evitar complexidade sem consumidor real.

## Armazenamento estático inicial

Um primeiro passo simples:

~~~text
static struct boot_snapshot snapshot;
static struct boot_mem_range ranges[BOOT_MAX_MEM_RANGES];
static struct boot_cpu cpus[BOOT_MAX_CPUS];
static char cmdline[BOOT_CMDLINE_MAX];
~~~

Mesmo após heap estar disponível, esses buffers podem continuar estáticos.

Ownership correto é mais importante que economizar alguns KiB.

## Overflow de capacidade

Se:

~~~text
raw_count > BOOT_MAX_MEM_RANGES
~~~

o kernel deve falhar claramente.

Nunca truncar.

Truncar memory map pode esconder memória reservada.

## Totais de memória

Após normalização, é possível derivar:

- usable bytes;
- reserved bytes;
- bootloader bytes;
- framebuffer bytes;
- ACPI bytes.

Toda soma precisa de overflow checking.

usable_bytes atual pode ser derivado do snapshot.

## Uma única fonte da verdade

Hoje existem:

~~~text
usable_bytes
memmap_entries
memmap_response
~~~

Se no futuro alguma versão normalizada divergir do raw map, isso pode gerar inconsistência.

O snapshot deve ser a única fonte.

Summaries são derivados.

## CPU count também deve ter fonte única

Hoje cpu_count é copiado, mas SMP também consulta o MP response.

Depois da normalização deve existir uma única topologia interna.

## BootConfig

Flags atuais podem ser agrupadas:

~~~text
struct boot_config {
    safe;
    nosmp;
    noapic;
    noac97;
    nonet;
    nojit;
    gfx_backend;
    gfx_3d;
    gfx_stress;
    gfx_debug;
};
~~~

Isso é mais coerente que vários globals independentes.

## Defaults explícitos

Configuração precisa declarar defaults.

Exemplo:

~~~text
safe = false
gfx backend = virtio preferred
gfx 3D = auto
~~~

Não depender implicitamente de BSS zero quando zero não comunica intenção.

## Reconciliação: dados copiados hoje

| Fato | Copiado para scalar do ChrisOS? |
|---|---:|
| HHDM offset | sim |
| framebuffer address | sim |
| framebuffer width | sim |
| framebuffer height | sim |
| framebuffer pitch | sim |
| framebuffer bpp | sim |
| total usable bytes | sim |
| memmap count | sim |
| CPU count | sim |
| BSP LAPIC ID | sim |
| cada memory range | não |
| cada CPU descriptor | não |
| command-line bytes | não |
| RSDP | não solicitado |
| SMBIOS | não solicitado |
| firmware type | não solicitado |
| bootloader identity | não solicitado |

Essa tabela representa a fronteira atual.

## Dados borrowed hoje

Continuam externos:

~~~text
memmap_response
mp_request.response
mp_request.response->cpus[]
limine_mp_info
~~~

Esses deveriam ser removidos das APIs gerais primeiro.

## Dados adopted hoje

O kernel adota:

~~~text
CR3 e page tables herdadas
~~~

e as modifica.

Essa é dependência ainda mais forte que pointer borrowed.

## Padrão já normalizado corretamente

Boot flags são o melhor exemplo atual.

A string é lida uma vez.

O estado persistente vira configuração própria do kernel.

O mesmo padrão deve ser usado para memory map e CPU topology.

## Sequência recomendada de implementação

### Estágio 1: tipos ChrisOS

Criar:

~~~text
boot_mem_range
boot_cpu
boot_framebuffer
boot_config
boot_firmware_roots
boot_snapshot
~~~

sem mudar comportamento.

### Estágio 2: deep-copy do memory map

Construir array normalizado em bootinfo_init.

Migrar PMM.

Remover dependência de memmap_response.

### Estágio 3: copiar CPU topology

Copiar processor/APIC IDs.

Manter raw MP apenas dentro do bootstrap SMP.

Depois do handoff, descartá-lo.

### Estágio 4: firmware roots

Adicionar RSDP request primeiro.

Depois SMBIOS e firmware type.

### Estágio 5: framebuffer completo

Copiar masks e memory model.

### Estágio 6: page tables próprias

Construir novo CR3.

Capturar framebuffer físico antes.

### Estágio 7: BSP stack

Mover BSP para stack pertencente ao kernel.

### Estágio 8: reclaim Limine

Verificar invariantes e liberar BOOTLOADER_RECLAIMABLE.

### Estágio 9: adaptador ChrisVM

ChrisVM protocol v2 produz o mesmo snapshot.

## Reclaim não é o objetivo principal

A prioridade não deve ser apenas recuperar alguns MiB.

O maior ganho é:

- independência de protocolo;
- ownership explícito;
- testabilidade;
- HHDM mais seguro;
- debug reprodutível;
- integração ChrisVM.

Reclaim vem como consequência.

## Checker reproduzível

scripts/check_boot_information_examples.py valida:

1. campos atuais de struct bootinfo;
2. memmap_response ainda retido;
3. exposição pública de limine_mp_response;
4. CR3 herdado adotado pelo MM;
5. BOOTLOADER_RECLAIMABLE reservado;
6. command line transformada em flags;
7. ChrisVM v1 sem boot info;
8. range arithmetic segura;
9. sorting/overlap de ranges sintéticos;
10. page-alignment do PMM;
11. cálculo de framebuffer via pitch;
12. modelo sintético de BootSnapshot.

O modelo é ilustrativo.

Ainda não é a implementação real.

## Limite de validação

Este capítulo descreve o código atual e a arquitetura proposta.

Não afirma que BootSnapshot já existe.

O source continua possuindo:

~~~text
struct bootinfo
memmap_response
bootinfo_mp_response()
CR3 herdado
~~~

BootSnapshot é a próxima fronteira arquitetural documentada.

Revisão reconciliada:

~~~text
ChrisOS main
da3df29cb397932c43d32373871fb9380e688ade
~~~

Execute:

~~~text
python scripts/check_boot_information_examples.py --source .source
~~~

## Gatilhos de revisão

Revisar quando:

- struct bootinfo mudar;
- memory map for deep-copied;
- types Limine desaparecerem de bootinfo.h;
- CPU topology for normalizada;
- RSDP/SMBIOS forem adicionados;
- metadata completa do framebuffer for copiada;
- command line mudar;
- BSP trocar de stack;
- page tables próprias substituírem CR3;
- BOOTLOADER_RECLAIMABLE for liberado;
- ACPI reclaimable começar a ser liberado;
- ChrisVM protocol v2 publicar boot information para o kernel real.

## Referências primárias

- Limine boot protocol e limine.h fixado pelo ChrisOS.
- bootinfo, PMM, MM e SMP do ChrisOS listados no front matter.
- ChrisVM boot protocol v1.
