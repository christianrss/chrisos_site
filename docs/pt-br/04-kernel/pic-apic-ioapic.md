---
id: pic-apic-ioapic
lang: pt-br
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/irq.c
  - kernel/metal/irq.h
  - kernel/metal/apic.c
  - kernel/metal/apic.h
  - kernel/metal/ioapic.c
  - kernel/metal/ioapic.h
  - kernel/metal/mm.h
  - kernel/metal/smp.c
  - kernel/metal/bootinfo.c
symbols:
  - pic_init
  - pic_set_mask
  - irq_set_handler
  - irq_eoi
  - irq_dispatch
  - apic_init
  - apic_enable_local
  - apic_ipi
  - apic_ipi_nmi
  - ioapic_init
depends_on:
  - idt-exceptions
  - buses-mmio-dma
related:
  - interrupts-smp
  - timers
  - tlb-shootdown
---

# PIC, Local APIC e roteamento IOAPIC

## Escopo

Entrega de interrupções em um x86 multiprocessado não é responsabilidade de um único componente. Um dispositivo afirma uma fonte, um controlador associa essa fonte a vetor e destino, a CPU alvo aceita o vetor, a IDT seleciona o entry point, o kernel despacha o evento e o controlador é finalmente reconhecido com EOI. O ChrisOS usa hoje um arranjo híbrido deliberado: o PIC legado ainda roteia IRQs comuns, o Local APIC fornece controle local e IPIs, e o módulo IOAPIC ainda é um stub diagnóstico.

A existência de código LAPIC, portanto, não significa que todos os dispositivos já foram migrados para IOAPIC.

## Modelo 8259 PIC

A arquitetura PC tradicional possui dois controladores 8259 compatíveis em cascata. O master atende IRQ0–7. O slave atende IRQ8–15 e chega ao master pela IRQ2.

| Controlador | Command | Data |
|---|---:|---:|
| PIC1 / master | `0x20` | `0x21` |
| PIC2 / slave | `0xA0` | `0xA1` |

O mapeamento histórico do PIC colide com vetores reservados de exceção da CPU. `pic_init` remapeia o master para `0x20` e o slave para `0x28`. Assim IRQ0 vira vetor 32 e IRQ15 vira vetor 47.

## Sequência de inicialização

`pic_init` começa com `cli`, envia ICW1 `0x11` para os dois controladores, programa os offsets, informa ao master que há slave na IRQ2, informa ao slave sua identidade em cascata, seleciona modo 8086 e termina mascarando todas as linhas.

`io_wait` separa writes que historicamente precisam de tempo de I/O.

O estado resultante é “controlador configurado, porém linhas desabilitadas”. Cada driver libera sua IRQ somente depois de preparar handler e hardware. `pit_init`, por exemplo, registra o handler de IRQ0 e só então desmascara a linha.

Essa ordem evita que um dispositivo interrompa o kernel antes de existir caminho válido para atendê-lo.

## Máscaras e cascata

`pic_set_mask` escolhe o data port, lê a máscara corrente, altera um bit e grava novamente. IRQs 0–7 usam master; 8–15 usam slave.

Ao liberar uma IRQ do slave, a função também libera a IRQ2 do master. Caso contrário, o slave poderia sinalizar sua saída e mesmo assim o master bloquearia toda a cascata.

Valores fora de 0–15 são ignorados porque essa API representa especificamente IRQs do PIC, não vetores LAPIC ou outros mecanismos modernos.

## Tabela de handlers

Há um array estático com 16 function pointers. `irq_set_handler` registra callback; `irq_get_handler` consulta. A IDT não aponta diretamente a esses callbacks. Vetores 32–47 entram no stub assembly comum e em `irq_dispatch`; somente depois são transformados em `irq = vector - 32`.

Essa camada comum concentra normalização de frame, separação entre exception/IRQ, contenção de storm e política de EOI.

## End of interrupt

Após atender uma interrupção, o controlador precisa ser informado de que a entrada em serviço terminou. Para IRQ8–15, `irq_eoi` envia `PIC_EOI` primeiro ao slave e depois ao master. Para IRQ0–7, somente ao master.

Quando o LAPIC está ativo, `irq_eoi` também chama `apic_eoi`. Isso reflete o estado híbrido atual: estado LAPIC pode estar habilitado enquanto o PIC segue participando da entrega. O código não pressupõe uma topologia IOAPIC-only que ainda não existe.

## Contenção de interrupt storm

`irq_dispatch` possui contador por IRQ. Para IRQ1–15, ao atingir 10.000 entregas, a linha é mascarada e o kernel registra “irq storm”.

IRQ0 é explicitamente excluída: é o timer periódico de 60 Hz. Se fosse tratada pelo mesmo contador cumulativo, uma operação normal acabaria desabilitando o relógio do sistema.

Não se trata de rate limiting sofisticado. Não há janela temporal nem reativação automática. É uma barreira simples contra uma linha que não deixa de interromper e pode impedir boot/desktop de avançarem.

## Local APIC

Cada processador em um sistema APIC-capable possui Local APIC. Ele participa de priorização local, timer local, EOI e transmissão/recepção de IPI. O ChrisOS usa nesta revisão principalmente enable local, EOI e IPIs.

`apic.c` guarda ponteiro para a página mapeada e `g_apic_on`. A janela física típica `0xFEE00000` é MMIO, não RAM comum. `bootinfo.c` registra explicitamente que “HHDM + LAPIC” não deve ser desreferenciado como se fosse memória normal e verifica que essa faixa não foi marcada como USABLE. O mapeamento válido é obtido por `mm_lapic_virt()`.

Essa distinção evita um erro comum: um direct map de RAM não torna automaticamente qualquer endereço físico de dispositivo acessível com atributos adequados.

## Habilitação do LAPIC

`apic_enable_local` acessa o Spurious Interrupt Vector Register no offset `0xF0` e grava `0x100 | 0xFF`. O bit `0x100` habilita por software o LAPIC; `0xFF` seleciona o vetor de spurious interrupt.

A função não mexe em IMCR e não desliga o caminho 8259. O comentário é explícito: timer e ATA ainda dependem do PIC.

`apic_init` é ainda mais conservador: apenas obtém o ponteiro e mantém `g_apic_on = 0`. `smp_init` chama `apic_enable_local` depois, salvo quando o boot flag `noapic` está ativo.

## IPIs fixos

`apic_ipi(dest_lapic, vector)` grava o destino no ICR high (`0x310`) e o comando no ICR low (`0x300`). Em seguida verifica delivery-status bit 12 por no máximo 100.000 iterações, executando `pause`.

Retorno zero significa que o envio no ICR terminou. Isso não prova que o CPU destino executou o handler. Protocolos de sincronização precisam de ack próprio. O TLB shootdown é um exemplo: ele mantém geração e estado por CPU em vez de interpretar “ICR entregue” como “TLB já invalidada”.

## IPI NMI

`apic_ipi_nmi` escolhe delivery mode NMI (100b) e level assert. O campo vector é ignorado nesse modo. A função também possui polling com limite.

No ChrisOS, NMI serve como mecanismo mais forte de fencing durante TLB shootdown. IF pode bloquear interrupções mascaráveis, mas não NMI. Se um AP deixar de participar do protocolo normal de invalidação, a camada de memória pode cercá-lo e enviar NMI para fazê-lo invalidar/parar.

A segurança aqui depende de um invariante de memória: frames físicos não podem ser reutilizados enquanto uma CPU ainda puder executar com traduções antigas. Logo, identificar e interromper corretamente o AP é parte de correctness, não apenas de disponibilidade.

## Identidade de CPU e APIC ID

`smp.c` armazena LAPIC IDs fornecidos pela resposta MP do Limine. O código evita usar exclusivamente uma leitura de MMIO compartilhada para descobrir “quem sou eu”. Um comentário registra uma falha anterior em que a leitura podia reproduzir o ID do BSP e fazer uma NMI posterior atingir a CPU do desktop.

A identidade lógica atual do AP é derivada principalmente da faixa virtual de sua stack dedicada. `smp_current_cpu` calcula o índice a partir de RSP. O mapa CPU-index → LAPIC-ID gravado no boot é então usado quando um IPI precisa de um destino físico.

É importante não confundir “índice lógico do ChrisOS” e “LAPIC ID”.

## Estado do IOAPIC

IOAPIC é o componente que normalmente substitui o 8259 como roteador de interrupções externas em sistemas APIC. Sua redirection table define vetor, delivery mode, polaridade, trigger mode, máscara e destino para cada entrada.

Na revisão analisada, `ioapic_init` não enumera IOAPIC, não mapeia registradores e não programa redirection entries. A função somente escreve:

```text
ioapic: PIC still routes IRQ (full IOAPIC in fase7 PASSO 01)
```

Portanto, afirmar “ChrisOS usa IOAPIC para IRQs” seria incorreto. O estado factual é: LAPIC/IPI existem; IRQs externas comuns continuam roteadas pelo PIC; IOAPIC está pendente.

## Ordem no boot

`kstart` estabelece a infraestrutura em sequência:

```text
GDT
IDT
gate de syscall
remap/mask do PIC
PIT + handler IRQ0
...
memória / heap
gráficos
...
apic_init
ioapic_init
job_init
smp_init
...
sti perto do início do desktop
```

APs entram no worker com IF inicialmente zero. Somente depois `smp_release_ap_irqs` permite que cada worker habilite seu LAPIC e execute `sti`. O comentário em `smp.c` documenta a motivação empírica: habilitar interrupções de AP durante uma cópia ATA impedia a operação de terminar.

Assim a ordem é parte do contrato de sincronização do boot.

## Concorrência e ownership

Programação do PIC é estado global. `pic_set_mask` faz read-modify-write sem lock dedicado; o modelo atual pressupõe chamadas em contextos controlados de inicialização/IRQ. Se vários CPUs passassem a manipular máscaras em paralelo, seria necessário serializar para evitar lost updates.

O ICR do LAPIC também é um recurso de hardware que envolve writes coordenados. `apic_ipi` envia um comando e espera seu delivery status antes de retornar. Um futuro cenário com múltiplos emissores concorrentes na mesma CPU exigiria política explícita de serialização.

A tabela de handlers também é simples e estática; registro é pensado para fase de inicialização, não como estrutura dinâmica lock-free alterada sob tráfego.

## Modos de falha

Base de vetor errada pode transformar IRQ em aparente exceção. IRQ2 mascarada pode eliminar todo o slave. EOI ausente pode bloquear interrupções futuras. EOI no momento errado pode quebrar o protocolo de um driver. Mapeamento LAPIC incorreto pode gerar page fault ou comportamento de MMIO inválido. IPI para APIC ID incorreto pode travar uma barreira ou, em NMI, parar a CPU errada.

Diagnóstico precisa separar as etapas: o dispositivo afirmou a linha? o controlador roteou? a CPU recebeu? a IDT entrou? o handler limpou a condição do dispositivo? o EOI ocorreu?

## Limite arquitetural atual

Na revisão `da3df29cb397932c43d32373871fb9380e688ade`, a descrição correta é “IRQ externa roteada por PIC, com Local APIC disponível para enable/EOI/IPI”. Ainda não é uma arquitetura de IRQ externa dirigida por IOAPIC. Afinidade de IRQ externa, política completa de redirection table e retirada sistemática do 8259 permanecem implementação futura.

## Mapa de fonte

PIC e dispatch ficam em `kernel/metal/irq.c`/`irq.h`. EOI e IPIs LAPIC ficam em `kernel/metal/apic.c`/`apic.h`. O stub IOAPIC está em `kernel/metal/ioapic.c`. Identidade LAPIC, boot dos APs e enable tardio de IRQ estão em `kernel/metal/smp.c`. As restrições de MMIO aparecem também em `kernel/metal/bootinfo.c` e na interface de memória. O Source Atlas publica a íntegra desses arquivos.
