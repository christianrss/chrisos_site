---
id: kernel-model
lang: pt-br
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/start.c
  - kernel/metal/proc.c
  - kernel/metal/syscall.c
  - kernel/metal/mm.c
  - kernel/metal/pmm.c
  - kernel/metal/irq.c
  - kernel/metal/smp.c
  - kernel/metal/job.c
  - kernel/gfx/graphics.c
  - kernel/fs/fs.c
  - kernel/net/net.c
  - kernel/wm/main.c
  - docs/LOCKING.md
  - docs/RESOURCE_OWNERSHIP.md
symbols:
  - kstart
  - proc_switch
  - syscall_dispatch
  - irq_dispatch
depends_on:
  - power-on-kstart
  - x86-64-memory-privilege
related:
  - interrupts-smp
  - processes-syscalls
  - resource-lifetime
---

# Modelo de kernel e fronteiras de confiança

## Escopo

“Kernel” identifica software privilegiado, mas não determina uma única arquitetura interna. Monolítico, microkernel e híbrido podem oferecer processos, memória virtual, arquivos e drivers com fronteiras de proteção diferentes. Para entender o ChrisOS é necessário perguntar onde cada componente executa, qual memória pode alcançar, quais transições são impostas por hardware, quem possui estado compartilhado e quais falhas podem ser contidas.

Na revisão `da3df29cb397932c43d32373871fb9380e688ade`, o ChrisOS é um kernel x86-64 monolítico modular. Memória, PMM, processos, interrupções, storage, filesystem, rede, gráficos, window manager, runtime de linguagem e a maioria dos drivers executam em caminhos privilegiados do kernel. Diretórios e APIs separam responsabilidades, mas não criam processos isolados entre esses módulos.

## Monolítico não significa sem estrutura

Monolítico descreve colocação no domínio privilegiado, não qualidade de organização.

O ChrisOS separa:
- `kernel/metal`: CPU, memória, IRQ, processo e mecanismos fundamentais;
- `kernel/fs`: block devices, partições, filesystems;
- `kernel/gfx`: framebuffer, software raster, VirtIO-GPU/VirGL e recursos;
- `kernel/net`: networking;
- `kernel/wm`: window/desktop policy;
- toolchain/runtime: ChrisC, CLVM e caminhos nativos.

Uma chamada C entre dois módulos continua em ring 0. Interfaces ajudam coesão e manutenção, mas um pointer incorreto em driver pode atingir memória global privilegiada.

## Comparação com microkernel

Microkernel normalmente mantém conjunto menor de mecanismos em privilégio e executa drivers/filesystems como servidores isolados com IPC. Um crash de driver pode, dependendo do desenho, ser limitado e reiniciado.

ChrisOS não possui hoje essa separação para seus serviços principais. Driver e filesystem compartilham address space privilegiado com MM e scheduler.

Logo, “modular” não deve ser convertido em “microkernel”. O projeto pode adotar ideias de interfaces estreitas e ownership sem afirmar uma proteção que o hardware/process model ainda não fornece.

## Ring 0 e ring 3

A fronteira nativa mais forte é CPL 3 ↔ CPL 0.

Código ring 3:
- usa CS/SS de usuário;
- roda em CR3 de processo;
- acessa apenas mappings permitidos pelo bit USER;
- entra em serviço por gate DPL 3 `int 0x80`;
- não executa operações privilegiadas como alterar CR3 ou GDTR.

Ring 0 controla page tables, devices e estado global.

A proteção depende de configuração correta. Se kernel mapear página privilegiada com USER ou aceitar user pointer sem validação, a existência de rings não corrige o erro.

## CLVM é outra fronteira

Aplicações ChrisC via CLVM operam por outro contrato. Offset da memória da VM não é virtual address de processo ring 3, e CLVM syscall não é ABI `int 0x80`.

Sandbox CLVM é construído em software; isolamento nativo combina hardware rings e paging.

Os dois modelos devem ter documentação e testes separados.

## Trusted Computing Base

A TCB é ampla porque muitos serviços são ring 0.

Componentes críticos incluem:
- PMM/page tables;
- GDT/TSS/entry de interrupt;
- process switch;
- user-copy/syscall;
- storage/filesystem metadata;
- drivers MMIO/DMA;
- graphics privileged resources;
- parsers de rede;
- locks e TLB reclamation.

Criticidade não é medida por linhas de código. Um pequeno helper que altera PTE pode ter maior consequência que um grande app.

## DMA amplia o domínio de confiança

Page protection da CPU não impede automaticamente um device bus-master de escrever por DMA. Driver que programa endereço físico incorreto pode corromper kernel sem uma CPU store.

Ownership precisa incluir lifetime de frame, endereço device-visible, lifetime do descriptor, completion e proibição de reuse enquanto hardware ainda puder acessar.

IOMMU seria outra fronteira, mas não pode ser presumida sem implementação.

## Boot order como arquitetura

`kstart` funciona como grafo executável de dependências.

Serial/build identity vêm primeiro; depois bootinfo, GDT/IDT/syscall/PIC/PIT/PS2, PMM/MM/heap/process, graphics, APIC/jobs/SMP, ACPI/storage/fs/install, runtime/audio, compiler self-host stage, `sti`, release de IRQ em AP, desktop/apps, rede e loop principal.

As dependências são reais:
- PMM antecede crescimento de mappings;
- IDT antecede IRQ segura;
- handler antecede unmask;
- heap antecede consumidores;
- storage antecede fs em disco;
- queue antecede AP worker;
- operações sensíveis de install precedem IRQs de AP.

Mudar ordem pode mudar correctness.

## Estado global

Há estado global em current process, process table, jobs, devices, graphics e filesystem.

Para cada objeto global é necessário saber:
- CPU inicializadora;
- CPUs autorizadas a mutar;
- lock;
- uso em IRQ;
- teardown;
- lifetime relativa a processos/devices.

`docs/LOCKING.md` e `docs/RESOURCE_OWNERSHIP.md` registram vários contratos.

## Userspace BSP-only

Kernel jobs rodam em múltiplas CPUs, mas user process switch permanece BSP-only. `proc_switch` causa panic em AP e syscall off-BSP é rejeitada.

Portanto o SMP atual inclui AP workers, TLB coherence e IPIs, mas mantém scheduler user global sob uma CPU.

Isso reduz races em `g_current`, CR3 user e return state enquanto o sistema evolui.

## Mecanismo e política

`mm_map_cr3` é mecanismo; decidir quais páginas são USER é política.
`apic_ipi` envia; protocolo TLB decide quem precisa ack.
`proc_block` muda estado; socket/join/IRQ determinam o motivo.
Block-device API movimenta setores; filesystem decide layout e root.

Separar conceitos ajuda mesmo quando código experimental mantém decisões próximas.

## Ownership

Todo recurso precisa de owner e release condition.

Processo guarda frames owned; file descriptors guardam owner PID; kthread possui stack; dispositivo possui resources/queues.

Mapping não equivale a ownership. Um frame pode estar mapeado em vários lugares e ter um único responsável por devolver a PMM.

Da mesma forma, buffer DMA não pode ser liberado até completion provar que hardware terminou.

## Domínios de falha

User page fault pode ser demand-resolved ou matar um processo.

Exception ring 0 vira panic fatal.

IRQ storm pode ser contida mascarando a linha.

AP silencioso em TLB protocol pode ser fenced/NMI para manter reuse de frames seguro.

Filesystem/storage possui outras fronteiras.

Arquitetura é também a definição de até onde cada classe de falha pode se propagar.

## Assincronia

Estado muda por chamadas, IRQ, múltiplas CPUs e devices DMA.

Uma única CPU pode deadlockar se IRQ tenta lock já mantido pelo código interrompido. Vários CPUs adicionam paralelismo real. DMA adiciona agente fora do fluxo da CPU.

Correctness depende de lock order, interrupt state, atomics, barriers, ownership handoff, completion e TLB invalidation.

“Thread-safe” genérico não substitui esses contratos.

## Interfaces produzidas

ABI nativa oferece hoje números para exit, write, putpixel, fopen, fread, fwrite, fclose e key.

CLVM tem interface própria.

Internamente existem contratos de fs, graphics, block device, sockets, processos e drivers.

Uma interface estável precisa definir validade de argumentos, ownership, contexto concorrente, erro e lifetime.

## Security boundary versus API boundary

Chamada C entre módulos ring 0 é API boundary, não hardware isolation.

Ring 3 → ring 0 é privilege boundary.
Offset CLVM → host pointer é sandbox boundary.
Driver API → MMIO é abstraction/hardware side-effect boundary.
FS API → metadata em disco é consistency boundary.

Nomear corretamente evita diagramas que prometem isolamento inexistente.

## Evidência

Código existente não prova sozinho maturidade.

Evidência deve combinar inspeção, host tests, gates QEMU, stress SMP/device e hardware real quando suportado.

O corpus separa implementation, validation e roadmap justamente para não transformar stub IOAPIC ou feature planejada em capability.

## Limitações atuais

Não há fault isolation de drivers/servers como em microkernel. User scheduling é BSP-only. Estruturas globais ainda são simples. Exception privilegiada fatal para o sistema. Suporte de hardware varia por subsistema.

Esses limites fazem parte do modelo de confiança atual.

## Mapa de fonte

`kernel/metal/start.c` mostra dependências. `proc.c`/`syscall.c` mostram boundary nativa. `mm.c`/`pmm.c` controlam memória. `irq.c`/`smp.c`/`job.c` mostram concorrência. Graphics/fs/net/wm demonstram a extensão do monolito. `LOCKING.md` e `RESOURCE_OWNERSHIP.md` registram contratos transversais. O Source Atlas preserva os arquivos integralmente.
