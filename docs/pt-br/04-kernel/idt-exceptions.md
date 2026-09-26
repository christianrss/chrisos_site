---
id: idt-exceptions
lang: pt-br
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/idt.c
  - kernel/metal/idt.h
  - kernel/metal/idt_stubs.asm
  - kernel/metal/irq.c
  - kernel/metal/irq.h
  - kernel/metal/panic.c
  - kernel/metal/syscall.c
symbols:
  - idt_init
  - idt_load
  - idt_set_user_gate
  - irq_dispatch
  - panic_exception
  - panic_user_fault
depends_on:
  - gdt-tss
  - x86-64-memory-privilege
related:
  - interrupts-smp
  - page-faults
  - processes-syscalls
---

# IDT, entrada de exceções e frames de interrupção

## Escopo

A Interrupt Descriptor Table é a estrutura x86-64 que associa cada vetor de interrupção aos metadados de entrada privilegiada. Ela atende exceções do processador, IRQs de hardware, interrupções geradas por software e vetores de IPI. Uma IDT correta, porém, é apenas a primeira etapa: stubs em assembly precisam normalizar o frame produzido pelo hardware, preservar registradores, respeitar alinhamento de stack da ABI, preservar estado SIMD/FPU, chamar C através de uma representação estável e restaurar o contexto interrompido antes de `iretq`.

O ChrisOS implementa explicitamente essas etapas. Este capítulo descreve o formato exato das gates, a política de inicialização das 256 entradas, o frame construído por `idt_stubs.asm`, o tratamento em `irq_dispatch`, a semântica especial do page fault, o gate de syscall `0x80` e a entrada NMI usada para contenção durante TLB shootdown.

## Espaço de vetores

A arquitetura x86 define 256 vetores. Os vetores 0–31 são reservados para exceções e interrupções arquiteturais como divide error, invalid opcode, general protection, page fault e NMI. Controladores de interrupção entregam IRQs em vetores configuráveis acima dessa faixa. Software também pode executar `int n` quando as regras de privilégio do descritor permitem.

No long mode, uma entrada da IDT ocupa 16 bytes. O ChrisOS a representa com `struct idt_gate` packed:

| Campo | Função |
|---|---|
| `offset_low` | bits 0–15 do endereço do handler |
| `selector` | seletor do segmento de código de destino |
| `ist` | índice opcional da IST no TSS |
| `attributes` | tipo, DPL e bit Present |
| `offset_middle` | bits 16–31 do handler |
| `offset_high` | bits 32–63 |
| `reserved` | deve permanecer zero |

`idt_init` contém assert estático de 16 bytes. Cada gate usa `GDT_KERNEL_CODE` e, nesta revisão, IST 0.

## Atributos das gates

O atributo padrão é `0x8e`: interrupt gate de 64 bits, Present, DPL 0. Isso impede que código em ring 3 invoque arbitrariamente vetores privilegiados com `int` apenas porque existem na tabela.

`idt_set_user_gate` usa `0xee`. A diferença relevante é DPL 3. `syscall_init` aplica esse atributo ao vetor `0x80`, tornando a interrupção de software explicitamente acessível ao usuário enquanto o destino permanece código de ring 0.

Essa diferença faz parte da superfície de segurança. Tornar todos os gates DPL 3 permitiria entrada voluntária de user mode em handlers que não foram construídos como interfaces de syscall.

## Construção das 256 entradas

`idt_init` percorre os 256 vetores e aponta inicialmente cada um para a entrada correspondente em `isr_stub_table`. Em seguida, o vetor 2 é substituído por `nmi_entry`. `lidt` recebe um operando packed contendo `sizeof(idt)-1` e o endereço linear da tabela estática.

A política é:

```text
para vector = 0..255:
    IDT[vector] -> isr_stub_table[vector], interrupt gate, DPL0
IDT[2] -> nmi_entry
lidt IDTR
```

Posteriormente, `syscall_init` muda somente os atributos do vetor 0x80; seu stub continua vindo da tabela comum.

## Exceções com e sem error code

Nem toda exceção produz o mesmo frame de hardware. Algumas fazem a CPU empilhar um error code; outras não. Um dispatcher comum em C é muito menos sujeito a erros se a parte superior do frame tiver layout uniforme.

`idt_stubs.asm` usa macros NASM para gerar 256 labels. Para os vetores 8, 10, 11, 12, 13, 14, 17, 21, 29 e 30, nos quais o hardware já fornece error code, o stub empilha somente o número do vetor. Nos demais, empilha primeiro um zero sintético e então o vetor.

Todos convergem em `isr_common`. Assim `frame->vector` e `frame->error` têm offsets constantes.

## Preservação de registradores e `irq_frame`

`isr_common` executa `cld`. Código C em geral assume operações de string na direção normal; herdar DF=1 do contexto interrompido quebraria essa suposição.

O stub empilha registradores gerais. `struct irq_frame` em `irq.h` reproduz exatamente a ordem:

```text
r15 r14 r13 r12 r11 r10 r9 r8
rbp rdi rsi rdx rcx rbx rax
vector error rip cs rflags
```

O assembly registra que vector fica a +120, error a +128 e RIP a +136 a partir do frame. O dispatcher pode ler e alterar o contexto salvo através dessa estrutura.

Quando há mudança de privilégio, a CPU também empilha estado adicional, como RSP e SS anteriores. A estrutura C expõe a parte comum utilizada pelo kernel; código não deve inferir que todas as origens têm palavras adicionais idênticas além do contrato declarado.

## Estado SIMD/FPU

Preservar apenas registradores inteiros seria insuficiente quando o código interrompido ou o próprio kernel utiliza estado x87/SSE. O ChrisOS reserva 528 bytes, calcula endereço alinhado a 16 bytes e executa `fxsave` antes de chamar `irq_dispatch`. Depois do retorno, `fxrstor` restaura o estado.

O endereço alinhado da área FXSAVE é mantido em armazenamento temporário associado à stack. RSP também é alinhado antes do `call` para que o compilador C receba as garantias da ABI.

Essa etapa diferencia um stub apenas demonstrativo de um caminho de interrupção que procura preservar corretamente o estado arquitetural usado pelo restante do sistema.

## Retorno

Ao voltar de `irq_dispatch`, o assembly restaura estado estendido, volta RSP ao frame de registradores, desempilha os GPRs na ordem inversa, remove os slots normalizados de vector/error e executa `iretq`.

Como C recebe um ponteiro para o frame, o handler pode modificá-lo intencionalmente. O ChrisOS usa isso quando um processo de usuário sai ou sofre fault: o caminho de syscall/fault pode substituir RIP, CS e RFLAGS de modo que o retorno vá para um endereço do kernel em vez de reentrar no contexto morto.

## Política de dispatch de exceções

`irq_dispatch` trata primeiro vetores especiais:

1. `0x80` vai para `syscall_dispatch`;
2. vetor 14 lê CR2 e chama `proc_fault_demand`;
3. se o page fault não for resolvido por demanda e CS indicar origem de usuário, `panic_user_fault` contém o erro no processo;
4. qualquer vetor restante abaixo de 32 chama `panic_exception`.

A ordem é essencial. Demand paging deve tentar materializar uma página válida antes de classificar o acesso como falha fatal. Um fault em user mode deve ser separado de um fault do kernel para impedir que um processo inválido derrube obrigatoriamente o sistema inteiro.

## Page fault

No vetor 14, CR2 contém o endereço linear que causou a falha. O dispatcher o lê diretamente. `proc_fault_demand` reconhece as regiões VM, stack, heap e framebuffer gerenciadas pelo processo e pode alocar/mapear a página ausente.

Quando isso funciona, o handler retorna sem alterar RIP. `iretq` reexecuta a instrução interrompida e agora a tradução está presente.

Se não houver demanda válida, os dois bits inferiores de CS distinguem origem user. `panic_user_fault` registra metadados, destrói o processo, escreve RIP, CR2, error code, CPU e identidade do build, define código de saída -11 e reescreve o frame para retorno controlado ao kernel.

Se a origem foi ring 0, `panic_exception` registra vetor, error, RIP e CR2, acrescenta identidade do kernel e entra em halt permanente.

## NMI

O vetor 2 não segue o caminho dos 256 stubs comuns. `nmi_entry` salva um conjunto menor de registradores, alinha RSP e chama `mm_tlb_nmi_stop`. O comentário do código explica por que a NMI usa a stack interrompida: `smp_current_cpu` depende da identidade da stack do AP.

O retorno da função decide se a CPU retorna ou fica parada. Um AP cercado pelo mecanismo de TLB pode executar `cli`/`hlt` indefinidamente. O BSP precisa retornar; uma versão anterior que o parava congelava o desktop. Logo, esta NMI é uma peça específica da contenção SMP/memória, não um framework genérico de NMI.

NMI também é útil aqui porque IF não bloqueia sua entrega, oferecendo um caminho de stop mais forte quando um AP não atende um IPI comum.

## IRQs e vetores altos

Depois das exceções, `0xF0` é reconhecido como IPI de TLB shootdown. O handler chama o polling do protocolo e envia EOI ao LAPIC.

Vetores a partir de 48, se não forem especiais, retornam antes do cálculo de IRQ legado. A faixa 32–47 corresponde aos IRQs 0–15 porque `pic_init` remapeia PIC1 para `0x20` e PIC2 para `0x28`.

## Stack, nesting e reentrância

A entrada usa a stack privilegiada ativa, salvo quando uma transição de privilégio ou IST muda a stack. Como todas as gates comuns usam `ist=0`, exceções ocorridas dentro do kernel permanecem na stack corrente. A NMI também é explicitamente mantida na stack interrompida.

Interrupções aninhadas, NMIs e faults consomem profundidade adicional. A stack de kernel criada pelo linker possui 1 MiB, mas tamanho não resolve recuperação quando a própria stack está corrompida. Para isso seria necessário configurar IST independente para exceções selecionadas.

Handlers chamam subsistemas com suas próprias regras de locking. Código executado em contexto de interrupção não pode adquirir locks em ordem que gere deadlock com código interrompido que já os possua. Essas regras pertencem aos capítulos dos subsistemas específicos.

## Propriedades de segurança

A IDT é memória estática controlada pelo kernel e `lidt` é privilegiado. DPL da gate regula invocação por software; não impede exceções reais de hardware. O ChrisOS expõe DPL 3 deliberadamente apenas no vetor 0x80.

Os stubs preservam registradores inteiros e FXSAVE para que a execução C não destrua silenciosamente o contexto interrompido. Page faults de usuário são isolados por processo quando possível. Isso reduz ambiguidades na fronteira de privilégio, mas não elimina a obrigação de validar qualquer dado não confiável lido por handlers.

## Falhas possíveis

Classes críticas de erro incluem endereço de gate incorreto, seletor de código inválido, atributos errados, divergência entre layout assembly e `irq_frame`, desalinhamento de stack antes do C, erro na normalização dos hardware error codes e corrupção do estado estendido.

Uma falha no próprio caminho de exceção pode provocar nova exceção durante a entrega da primeira. Isso pode escalar para double fault e, sem descritores/stacks válidos, resetar a máquina. Por isso layout e ordem de push/pop são invariantes arquiteturais.

## Validação

A evidência estática inclui assert de gate com 16 bytes, geração das 256 entradas, lista explícita das exceções com error code, correspondência com `irq_frame`, par FXSAVE/FXRSTOR e gate de syscall isolado em DPL 3.

Validação dinâmica deve induzir faults controlados, verificar retry após demand paging, contenção de faults user, preservação de registradores sob interrupções, atividade simultânea de timer/dispositivos e comportamento dos IPIs/NMI de TLB em SMP. O Source Atlas torna a íntegra dos stubs e do dispatcher auditável na mesma revisão.

## Limitações atuais

Nenhuma gate usa IST. Exceções de kernel são fatais. A NMI é especializada para TLB fencing. A interface de syscall usa `int 0x80`, não SYSCALL/SYSRET. São propriedades do ChrisOS revisado, não requisitos gerais do x86-64.

## Mapa de fonte

IDT fica em `kernel/metal/idt.c` e `idt.h`. Entrada/retorno assembly estão em `kernel/metal/idt_stubs.asm`. O dispatcher e contrato do frame são `kernel/metal/irq.c`/`irq.h`. Panic de exceção de kernel está em `kernel/metal/panic.c`; contenção de fault de usuário e gate 0x80 envolvem `kernel/metal/syscall.c`. O Source Atlas contém a íntegra na revisão `da3df29cb397932c43d32373871fb9380e688ade`.
