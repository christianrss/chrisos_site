---
id: chris-architecture-state
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/boot.c
  - chrisvm/cpu/common/state.c
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/hv/chrishv.c
symbols:
  - ChrisArchitectureState
  - ChrisSeg
  - ChrisDtr
  - ChrisCpuBackend
  - chris_arch_reset
  - cpu_get
  - cpu_set
  - chris_boot
depends_on:
  - chrisvm-chriscpu
  - emulator-paging
  - x86-registers-flags
related:
  - chrisvm-machine
  - determinism-replay
  - virtualization-chrishv
---

# ChrisArchitectureState: o contrato compartilhado de estado da CPU

## Propósito

ChrisArchitectureState é o registro central de estado arquitetural usado pelo ChrisVM. Ele forma a fronteira entre o estado x86-64 visível ao guest e o backend de CPU que executa esse estado.

A própria fonte explicita a intenção: o ChrisCPU executa essa estrutura hoje, enquanto um futuro backend ChrisHV deverá importar e exportar o mesmo estado lógico para estruturas de virtualização por hardware como VMCS ou VMCB. O objetivo é evitar dois modelos arquiteturais paralelos e potencialmente divergentes, um para o interpretador e outro para execução assistida por hardware.

A separação correta é:

- ChrisArchitectureState descreve estado arquitetural do guest;
- ChrisCpu contém estado de controle/runtime do backend;
- ChrisMachine possui RAM, dispositivos, configuração e o backend selecionado.

As três camadas interagem durante a execução, mas não são equivalentes.

Este capítulo documenta o contrato na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56 do ChrisOS.

## Visão geral da estrutura

O estado atual agrupa:

| Categoria | Campos |
|---|---|
| registradores de propósito geral | gpr[16], com aliases nomeados rax até r15 |
| fluxo de controle | rip, rflags |
| registradores de controle | cr0, cr2, cr3, cr4, cr8 |
| estado de segmentos | cs, ds, es, fs, gs, ss |
| segmentos de sistema | tr, ldtr |
| descriptor tables | gdtr, idtr |
| estado estendido/MSRs | efer, star, lstar, cstar, fmask |
| base MSRs | fs_base, gs_base, kernel_gs_base |
| estado relacionado ao interrupt controller | apic_base |
| estado temporal | tsc |
| armazenamento SIMD | xmm[16][16] |
| privilégio | cpl |

A estrutura contém intencionalmente mais estado que o interpretador atual consome de fato. Isso a torna um contrato voltado ao crescimento futuro, mas presença de campo não significa suporte completo à semântica correspondente.

## Registradores de propósito geral

O primeiro campo é uma union que expõe os dezesseis GPRs de 64 bits de duas formas.

Forma indexada:

    gpr[0] ... gpr[15]

Forma nomeada:

    rax rcx rdx rbx rsp rbp rsi rdi
    r8  r9  r10 r11 r12 r13 r14 r15

O projeto define constantes para os primeiros índices, começando por CHRIS_GPR_RAX igual a zero e CHRIS_GPR_RSP igual a quatro. Decoder e operand helpers usam índices numéricos; APIs como chris_get_gpr e chris_set_gpr também expõem acesso indexado.

Como array e membros nomeados ocupam o mesmo storage da union, alterar uma visão altera a outra. Isso elimina a necessidade de sincronizar duas cópias dos GPRs.

A ordem dos registradores faz parte do contrato lógico. Um backend futuro deve preservar esse mapeamento mesmo se armazenar o estado em formato completamente diferente.

## RIP e RFLAGS

rip é o instruction pointer atual do guest.

No loop do interpretador, o instruction fetch inicia em arch.rip. A maioria das instruções não altera RIP diretamente; depois da execução, o loop adiciona o comprimento decodificado salvo se rip_dirty tiver sido marcado por alguma transferência de controle.

JMP, CALL, Jcc, INT, IRETQ e HLT podem manipular RIP por caminhos específicos.

rflags guarda a palavra de flags modelada.

O reset estabelece a invariável:

    RFLAGS = 2

preservando o bit arquiteturalmente fixo 1.

Helpers aritméticos atualizam apenas status flags selecionadas; outros caminhos manipulam IF, DF, TF, RF e VM quando implementados.

RFLAGS, portanto, participa simultaneamente de ALU, branch conditions, interrupções, string operations e exception delivery.

## Estado de reset

chris_arch_reset executa duas operações:

1. zera toda a ChrisArchitectureState;
2. define:
   - RFLAGS como 2;
   - CR0 como PE | NE.

Esse é um reset mínimo do projeto, não uma reprodução completa do reset arquitetural x86.

Ele não coloca a CPU no real reset vector, não modela startup em real mode de 16 bits e não inicializa estado de firmware.

O boot protocol v1 do ChrisVM constrói um estado sintético de long mode sobre esse registro inicial.

## Construção do estado no boot

chris_boot cria uma ChrisArchitectureState local e chama chris_arch_reset.

install_tables adiciona o estado de long mode exigido pelo protocolo:

- CR0 recebe PE, NE, WP e PG;
- CR3 aponta para a PML4 gerada;
- CR4 recebe PAE;
- EFER recebe LME e LMA;
- GDTR aponta para a GDT;
- CS recebe o code segment de long mode;
- SS, DS e ES recebem o data descriptor;
- RFLAGS é definido como 2;
- CPL é definido como zero.

Depois, chris_boot define:

- RIP no entry point;
- RSP no endereço escolhido para a stack.

O estado completo é então enviado por:

    backend->set_state(cpu, &st)

Esse é um dos usos mais importantes da abstração de backend. O boot não precisa saber se o backend armazena o estado em uma struct C, em VMCS/VMCB ou em outra representação.

## Import/export no ChrisCPU

O ChrisCPU implementa transferência de estado da forma mais simples possível.

cpu_get:

    *out = cpu->arch

cpu_set:

    cpu->arch = *in

A estrutura inteira é copiada por valor.

Isso oferece semântica direta field-for-field para o interpretador atual. Ao mesmo tempo, não há validação, normalização ou side effects durante importação.

cpu_set não:

- valida combinações CR0/CR4;
- valida RIP canônico;
- verifica descriptors;
- recalcula CPL a partir de CS;
- invalida translation state;
- normaliza reserved bits de RFLAGS;
- reconcilia estado duplicado de segmentos/bases.

Para o boot controlado atual isso é suficiente, mas é uma fronteira importante para migration, snapshots e debugger state injection.

## A interface de backend

ChrisCpuBackend define a fronteira de execução:

- init;
- create_cpu;
- reset;
- run;
- inject_irq;
- get_state;
- set_state;
- invalidate_tlb;
- shutdown.

get_state e set_state são a ponte arquitetural. Eles deveriam manter o restante do ChrisVM independente da forma como cada backend armazena CPU state.

O ChrisCPU guarda ChrisArchitectureState diretamente dentro de ChrisCpu. Um ChrisHV real provavelmente terá de traduzir parte desse estado para estruturas de virtualização do processador e manter eventualmente shadow state no host.

O contrato lógico deve permanecer estável mesmo quando a representação física mudar.

## ChrisHV é apenas uma fronteira reservada hoje

O chrishv.c atual declara explicitamente que virtualização assistida por hardware ainda não está implementada.

hv_init falha. Como consequência, chris_machine_create rejeita o backend chrishv antes de criar uma CPU utilizável.

Os demais callbacks do ChrisHV permanecem stubs, inclusive hv_get e hv_set.

Assim, ChrisArchitectureState já funciona como contrato arquitetural compartilhado de projeto, mas somente ChrisCPU implementa import/export funcional.

Não é correto descrever sincronização com VMCS/VMCB como funcional nesta revisão.

## Registradores de controle

O estado armazena CR0, CR2, CR3, CR4 e CR8.

### CR0

O interpretador usa atualmente bits como:

- PE;
- NE;
- WP;
- PG.

WP e PG influenciam diretamente a MMU.

### CR2

CR2 recebe o endereço virtual de page faults modelados e alguns diagnósticos de physical backing ausente.

### CR3

CR3 identifica a raiz PML4 usada pelo page walker de quatro níveis.

A MMU mascara os doze bits inferiores e não implementa PCID.

### CR4

O boot inicial estabelece PAE. Outros recursos modernos de CR4 não são amplamente modelados.

### CR8

CR8 existe no estado, no caminho MOV-CR e na API pública.

A implementação inspecionada ainda não conecta CR8 a um local APIC com task-priority modelado. O campo representa storage arquitetural antes da implementação completa da semântica correspondente.

## Estado de segmentos

ChrisSeg contém:

- selector;
- base;
- limit;
- attributes.

ChrisArchitectureState armazena os segmentos comuns:

- CS;
- DS;
- ES;
- FS;
- GS;
- SS;

e registros de sistema com formato semelhante:

- TR;
- LDTR.

A estrutura representa tanto o selector visível quanto cache derivado de descriptor. Isso é útil porque registradores de segmento reais possuem estado oculto além do selector.

Entretanto, a implementação atual não fornece semântica completa de segment loading e privilégio para todos os campos.

CS possui um helper específico usado por exception delivery. DS/ES/FS/GS/SS, TR e LDTR ainda não possuem mecanismos equivalentes e completos de transição arquitetural.

Presença desses campos não equivale a compatibilidade integral de segmentação.

## GDTR e IDTR

ChrisDtr contém:

- base;
- limit.

gdtr e idtr usam essa representação.

O executor implementa um subconjunto de SGDT, SIDT, LGDT e LIDT. Exception delivery usa IDTR e carregamento de CS consulta GDTR.

Os descriptors em si continuam na memória do guest; a estrutura não mantém um cache completo de GDT/IDT.

## EFER

O estado inclui EFER e constantes para:

- SCE;
- LME;
- LMA;
- NXE.

O protocolo de boot define LME e LMA.

A MMU usa NXE para decidir se o bit NX nas page tables impede instruction fetch.

SCE existe como bit de estado, mas o decoder/executor inspecionado ainda não implementa um caminho SYSCALL/SYSRET.

É um exemplo direto da diferença entre armazenamento de estado e suporte de instrução.

## STAR, LSTAR, CSTAR e FMASK

O estado mantém os MSRs de syscall:

- STAR;
- LSTAR;
- CSTAR;
- FMASK.

RDMSR e WRMSR conseguem acessar esses slots modelados.

Sem SYSCALL/SYSRET funcional, esses MSRs operam principalmente como storage arquitetural, não como configuração ativa de control flow.

Uma implementação futura deve consumi-los por esse mesmo contrato compartilhado.

## FS_BASE, GS_BASE e KERNEL_GS_BASE

Existem slots explícitos para:

- fs_base;
- gs_base;
- kernel_gs_base.

RDMSR/WRMSR acessam esses campos.

Ao mesmo tempo, ChrisSeg fs e gs também possuem campos base.

A representação permite hoje situações como:

    fs.base != fs_base

cpu_set não reconcilia automaticamente esses valores.

Além disso, o decoder atual descarta a identidade de segment overrides e o executor ainda não oferece endereçamento geral FS/GS-relative.

Portanto, a inconsistência não afeta ainda um conjunto amplo de guests, mas precisa ser resolvida antes de uma implementação completa de FS/GS e SWAPGS-like semantics.

## APIC base

apic_base representa storage do IA32_APIC_BASE.

RDMSR/WRMSR acessam o campo.

A plataforma ChrisVM atual ainda não possui APIC/IOAPIC/SMP maduro ligado a esse estado. Assim como CR8, é armazenamento arquitetural antecipando uma camada ainda incompleta da plataforma.

## TSC

tsc pertence a ChrisArchitectureState e, portanto, é tratado como estado arquitetural do guest.

O loop do ChrisCPU executa:

    cpu->arch.tsc++

uma vez por instrução interpretada.

Isso gera comportamento determinístico em função de retirement no interpretador, mas não representa ciclos reais, wall-clock time ou frequência física do TSC.

O decoder x86 atual também não implementa uma instrução guest RDTSC.

Logo, o campo avança internamente mesmo sem uma forma geral de guest code consultá-lo por RDTSC.

Para determinism/replay, essa distinção é essencial: o TSC atual é próximo de um contador lógico de instruções, não um simulador temporal.

## Armazenamento XMM

A estrutura reserva:

    xmm[16][16]

ou seja, dezesseis slots de 128 bits correspondentes estruturalmente a XMM0-XMM15.

O decoder/executor do ChrisCPU não implementa cobertura ampla SSE/AVX nesta revisão, e não existe caminho de execução ChrisVM consumindo esse storage.

A presença dos campos não é evidência de SIMD emulado.

Quando SIMD for implementado, o projeto também precisará decidir onde ficam MXCSR e eventual estado YMM/ZMM.

## CPL

A estrutura armazena cpl como um inteiro separado.

A MMU classifica user mode com:

    cpl == 3

O boot inicializa cpl em zero.

Isso simplifica a implementação, mas permite divergência em relação ao privilégio indicado por CS, pois nenhuma invariável força atualmente:

    cpl == (cs.sel & 3)

chris_seg_load_cs atualiza CS e não atualiza cpl no código inspecionado.

Essa é uma fronteira concreta de consistência. Transições futuras de privilégio precisam definir se CPL é estado derivado, estado autoritativo ou uma redundância validada.

Manter ambos mutáveis e sem reconciliação pode fazer a MMU enxergar um privilégio diferente daquele representado por CS.

## Estado arquitetural versus estado runtime

Nem todo estado relacionado à CPU pertence à ChrisArchitectureState.

ChrisCpu armazena separadamente:

- steps;
- halted;
- exit_reason;
- exception diagnostics;
- delivering;
- IRQ pendente e vetor;
- sti_delay;
- rip_dirty;
- tlb_gen;
- configuração de trace;
- breakpoint state;
- trace ring.

Esses campos afetam execução, mas não são todos registradores visíveis ao guest.

A separação é conceitualmente correta. Porém, ela implica que copiar apenas ChrisArchitectureState não produz um snapshot suficiente para continuação bit-exact do emulador.

Restaurar registradores sem restaurar pending IRQ, STI delay ou determinadas condições do monitor pode mudar a execução seguinte.

Essa questão liga diretamente o estado arquitetural ao futuro capítulo de determinism/replay.

## Estado da máquina é outra camada

ChrisMachine possui estado da plataforma fora da CPU:

- RAM;
- registros de I/O;
- registros MMIO;
- serial;
- framebuffer;
- backend;
- entry point;
- boot/shutdown state;
- configuração.

Um snapshot completo de VM precisa combinar:

    estado arquitetural da CPU
    + estado runtime do backend
    + dispositivos/máquina
    + memória

ChrisArchitectureState cobre deliberadamente apenas a primeira categoria.

## Vazamento de abstração na API pública

Apesar de ChrisCpuBackend definir get_state e set_state, vários helpers públicos de machine.c acessam diretamente a estrutura do interpretador.

Exemplos:

- chris_set_gpr;
- chris_get_gpr;
- chris_get_rip;
- chris_get_rflags;
- chris_get_cr;
- chris_set_cr.

Eles leem ou escrevem:

    m->cpu->arch

em vez de usar backend->get_state/backend->set_state.

Isso funciona porque ChrisCPU mantém o estado autoritativo exatamente nesse local.

Não funcionaria automaticamente com um ChrisHV cujo estado autoritativo estivesse em VMCS/VMCB ou outra representação.

Essa é uma lacuna real de layering.

Uma API realmente backend-neutral deve passar leituras/escritas pelo contrato de backend ou definir uma regra explícita garantindo que cpu->arch seja sempre um shadow autoritativo sincronizado.

## Mutação direta não gera side effects arquiteturais

Os setters públicos também alteram campos sem executar side effects relacionados.

Por exemplo, chris_set_cr pode mudar CR3 diretamente.

Ele não:

- invalida uma futura TLB;
- valida combinações de control registers;
- força flush de translation state;
- verifica implicações de canonicalidade;
- sincroniza campos dependentes no backend.

Como a MMU atual não possui TLB, mudar CR3 torna-se visível imediatamente.

Essa segurança é acidental e desapareceria quando uma TLB real for adicionada.

A API deveria diferenciar:

- restore cru de snapshot;
- write arquitetural executado por instrução;
- mutação forçada por debugger.

Essas operações não necessariamente possuem os mesmos side effects.

## A struct C não é um ABI de serialização

ChrisArchitectureState é uma struct C contendo union, nested structs, arrays e um campo int.

Seus campos lógicos formam um contrato arquitetural, mas o layout bruto em memória não deve ser tratado automaticamente como formato permanente de arquivo ou rede.

Problemas possíveis:

- padding do compilador;
- alinhamento;
- ABI diferente;
- endianness;
- inserção futura de campos;
- largura assumida para int;
- evolução de versão.

Um snapshot ou formato de migration estável deve serializar campos nomeados explicitamente e incluir versão/schema.

Gravar sizeof(ChrisArchitectureState) bytes diretamente criaria dependência com um ABI e uma revisão específicos.

## Importação de estado exige regras de normalização

Um set_state robusto futuro precisa definir comportamento para estado inconsistente ou arquiteturalmente inválido.

Exemplos:

- bit 1 de RFLAGS limpo;
- RIP não canônico;
- CR0.PG ativo sem pré-requisitos;
- EFER.LMA incompatível com control state;
- CPL divergente de CS;
- selector incompatível com atributos cacheados do segmento;
- FS/GS base divergente dos MSRs correspondentes;
- CR3 contendo PCID não suportado;
- XMM sem MXCSR associado.

cpu_set atual não verifica nenhum desses casos.

Ele deve ser entendido como primitive de transferência crua, não como fronteira de validação arquitetural.

## Evidência de testes

A suíte ChrisVM atual exercita diversos campos indiretamente:

- GPRs depois da execução;
- RFLAGS depois de operações ALU;
- CR2 após page fault;
- CR/MSR;
- progressão de RIP;
- inicialização pelo boot;
- permissões de paginação;
- exception state;
- incremento interno de TSC.

Os testes também confirmam que selecionar chrishv é rejeitado atualmente.

Entretanto, não existe no conjunto inspecionado um teste dedicado de round-trip que:

1. preencha todos os campos de ChrisArchitectureState;
2. execute backend set_state;
3. execute backend get_state;
4. compare todos os campos lógicos.

Esse teste deve existir antes de ChrisHV começar a traduzir estado real de VMCS/VMCB.

## Prioridades de hardening

Os próximos trabalhos de maior valor são:

1. criar teste completo backend-neutral de round-trip para todos os campos;
2. fazer getters/setters públicos passarem por get_state/set_state ou definir shadow state autoritativo;
3. separar restore cru de register writes arquiteturais;
4. definir regras de normalização e validação de estado importado;
5. tornar explícita a consistência entre CPL e CS;
6. definir relação canônica entre cache FS/GS e MSRs FS_BASE/GS_BASE;
7. versionar formato de serialização em vez de gravar a struct bruta;
8. separar TSC lógico determinístico de futura virtualização temporal/hardware;
9. adicionar MXCSR e estado vetorial mais amplo apenas quando houver execução correspondente;
10. definir quais campos runtime precisam acompanhar snapshots/migration;
11. fazer mudanças futuras em CR0/CR3/CR4 dispararem invalidação apropriada;
12. compartilhar as mesmas fixtures de estado entre ChrisCPU e futuro ChrisHV.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisArchitectureState é um modelo lógico coerente de registradores compartilhado e o ChrisCPU implementa import/export por cópia integral da estrutura. O desenho fornece uma boa fronteira para backends, porém APIs ao redor ainda assumem diretamente o layout cpu->arch do interpretador. ChrisHV continua stub, importação não é validada, CPL pode divergir de CS e a estrutura ainda não deve ser usada como ABI permanente de serialização. Essas fronteiras precisam ser resolvidas antes que virtualização por hardware, migration ou snapshot/replay dependam do contrato.
