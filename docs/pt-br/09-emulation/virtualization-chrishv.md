---
id: virtualization-chrishv
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.c
  - chrisvm/cpu/hv/chrishv.c
  - chrisvm/cpu/hv/vmx/vmx.h
  - chrisvm/cpu/hv/svm/svm.h
symbols:
  - chris_backend_by_name
  - chrishv_backend
depends_on:
  - chrisvm-chriscpu
related:
  - chrisvm-machine
  - chrisvm-spec
  - vmx
  - svm
  - ept-npt
  - x86-64-memory-privilege
---

# Virtualização assistida por hardware e a fronteira ChrisHV

## Escopo

ChrisHV é o backend de CPU reservado para hardware-assisted execution no ChrisVM.

Na revisão analisada ele **não** executa Intel VMX, AMD SVM nem Linux KVM. O implementation atual é propositalmente um backend recusado que preserva o seam futuro sem fingir capability inexistente.

A distinção básica é:

~~~text
implementado hoje
    |
    +-- ChrisVM machine model
    +-- ChrisArchitectureState
    +-- ChrisCpuBackend
    +-- ChrisCPU interpreter
    +-- nome/vtable ChrisHV
    +-- initialization failure explícita

não implementado hoje
    |
    +-- VMXON / VMCS
    +-- VMRUN / VMCB
    +-- EPT / NPT
    +-- hardware vCPU execution
    +-- VM-exit dispatch
    +-- hardware interrupt injection
~~~

Os chapters VMX, SVM e EPT/NPT documentam arquitetura externa necessária no futuro. Este capítulo define como ela deve se encaixar no ChrisOS.

## Estado atual do source

`chrishv.c` é pequeno de forma intencional.

O próprio comentário declara:

- sem VMX;
- sem SVM;
- sem KVM.

`hv_init()` imprime:

    chrishv: not implemented (no VMX/SVM in this round)

e retorna failure.

As demais operações são inert ou retornam erro.

Os headers VMX/SVM também afirmam que implementations ainda não começaram.

Isso é non-capability explícita, não feature escondida.

## Backend selection

`chris_backend_by_name()` reconhece:

    chriscpu
    chrishv

Ter dois names significa que machine layer conhece duas identidades.

Não significa que ambas conseguem criar CPU.

Durante `chris_machine_create()`, backend initialization ocorre antes da machine completar a criação. Como ChrisHV falha, machine creation falha em vez de fazer fallback silencioso.

## Por que fallback silencioso seria incorreto

Se:

    --backend chrishv

executasse ChrisCPU sem avisar, guest poderia terminar com sucesso, mas a evidência provaria apenas interpreter behavior.

Seria possível reportar incorretamente que VMX/SVM funcionam.

Fail-closed evita esse erro de evidence class.

Para validation de backend, "indisponível" é melhor que "passou usando outro engine".

## Interpretação versus hardware virtualization

ChrisCPU executa cada guest instruction em software.

O caminho faz:

1. translate RIP;
2. fetch;
3. decode;
4. execute em C;
5. update de `ChrisArchitectureState`;
6. model de faults/I/O/control flow.

Hardware virtualization muda quem executa ordinary instructions.

A CPU física executa guest diretamente em modo virtualizado até evento configurado devolver controle ao monitor.

Machine model continua existindo.

## Modelo Intel VMX

Intel VMX distingue VMX root e VMX non-root.

Hypervisor opera em root; guest normalmente em non-root.

VM entry entra no guest.

Eventos interceptados produzem VM exit.

VMCS contém guest state, host state, execution controls e exit information.

Um futuro backend ChrisHV/VMX precisaria mapear:

    ChrisArchitectureState
        |
        v
    VMCS guest state

e também transformar policy do ChrisVM nos controles VMX apropriados.

Nada disso está implementado hoje.

## Modelo AMD SVM

AMD SVM usa VMCB.

`VMRUN` inicia guest a partir do control block.

VMCB carrega guest state e controls/intercepts.

Conceitualmente:

    ChrisArchitectureState
        |
        v
       VMCB

mas VMCS e VMCB são formatos vendor-specific.

Dual-vendor support exige implementação diferente sob um common backend contract.

## Shared state como portability boundary

`chris_arch.h` já contém a decisão importante: backends não devem criar modelos arquiteturais separados.

`ChrisArchitectureState` contém:

- GPRs;
- RIP/RFLAGS;
- control registers;
- segments;
- descriptor tables;
- EFER/MSRs selecionados;
- TSC;
- XMM storage;
- CPL.

Em hardware execution parte desse state pode permanecer no VMCS/VMCB enquanto guest roda.

Backend precisa definir import/export coerente em exit, reset, debug e shutdown.

## Problema de state synchronization

No ChrisCPU, o state em memória é authoritative.

Com VMX/SVM, state pode temporariamente estar nos control structures da CPU.

É preciso definir:

- fields carregados antes de entry;
- fields lidos depois de exit;
- fields cached;
- quando machine code externo pode mudar state;
- como TLB invalidation chega ao hardware;
- como debugger obtém snapshot consistente.

Sem regras explícitas, machine e backend podem discordar sobre guest state.

## VM exits

VM exit não significa necessariamente erro.

É transferência controlada do guest para monitor.

Classes possíveis incluem:

- I/O interceptado;
- control-register access;
- CPUID conforme controls;
- exceptions/interrupts conforme configuration;
- second-level translation violation;
- HLT;
- privileged virtualization-sensitive operations.

Dispatcher futuro precisa decidir:

1. emulate e resume;
2. reflect/inject event;
3. terminate/report machine exit.

Policy pertence ao backend ChrisHV.

## Evitando exits desnecessários

Hardware virtualization é útil porque ordinary guest instructions podem executar sem interpreter dispatch.

Se tudo causar exit, semantics podem estar corretas, mas grande parte do ganho de performance desaparece.

Design precisa equilibrar:

- observability;
- device emulation;
- correctness;
- isolation;
- exit frequency.

Performance deve medir exits reais, não presumir que hardware virtualization é automaticamente rápida.

## Device model continua necessário

Hardware CPU execution não elimina virtual machine.

Guest port I/O pode gerar VM exit.

ChrisHV então precisa encaminhar operação ao mesmo ChrisVM I/O model usado pelo interpreter.

MMIO também exige ownership e dispatch.

~~~text
guest instruction em hardware
        |
        v
      VM exit
        |
        v
     ChrisHV
        |
        v
ChrisVM I/O ou MMIO bus
        |
        v
 virtual device
~~~

Por isso ChrisHV fica abaixo do ChrisVM.

## Interrupt injection

A vtable comum já define IRQ injection.

ChrisCPU mantém pending vector em software.

Backend hardware precisará transformar o mesmo pedido em event injection vendor-specific e respeitar interruptibility do guest.

Não basta escrever vector e executar guest em qualquer estado.

## Second-level translation

Guest paging normal faz:

[
GVA ightarrow GPA
]

Hypervisor também precisa:

[
GPA ightarrow HPA
]

Intel EPT e AMD NPT realizam essa segunda translation em hardware.

Combinação:

[
GVA ightarrow GPA ightarrow HPA
]

ChrisCPU faz guest translation em software e depois acessa machine memory backing.

ChrisHV precisará de backing strategy e second-level page tables ou interface host equivalente.

## Memory ownership

Hoje guest RAM é host allocation.

Backend hardware precisará manter backing pages válidas enquanto EPT/NPT as referencia.

Novos invariants incluem:

- backing não pode ser freed durante execução;
- unmap precisa invalidar stale translation;
- teardown precisa parar hardware antes de liberar pages;
- shared/device memory requer permissions explícitas;
- MMIO/framebuffer podem exigir mappings distintos.

Essas rules ainda não existem no stub atual.

## Capability detection

Backend real deve falhar antes de ativar virtualization quando CPU/platform não suporta o mechanism.

No Intel, VMX capability e permission state precisam ser verificados.

No AMD, SVM capability e firmware-disable state precisam ser avaliados antes de `VMRUN`.

Current source não executa esses checks porque falha ainda antes.

Diagnostics futuros devem distinguir:

- CPU feature absent;
- firmware disabled;
- locked/unavailable;
- initialization failure;
- VM-entry failure.

## Privilege e ambiente host

VMX/SVM setup é privileged.

Processo userspace comum não executa arbitrariamente VMXON/VMRUN sem interface do OS ou contexto privilegiado.

Isso é importante porque ChrisVM hoje é host program.

Uma implementação futura precisa escolher explicitamente:

- direct privileged execution em ambiente adequado;
- interface do sistema operacional como KVM;
- outra execution layer controlada.

Comentários atuais declaram que KVM não é usado.

## Direct VMX/SVM versus KVM

São caminhos diferentes.

### Direct VMX/SVM

ChrisHV possuiria:

- capability setup;
- virtualization enable;
- control structures;
- guest entry;
- exit decoding;
- second-level tables;
- interrupt injection.

### KVM-backed

Host kernel possuiria parte importante do hardware virtualization, enquanto ChrisVM usaria API KVM.

Nenhum dos dois caminhos existe atualmente.

A escolha futura altera portability, tests e host boundary.

## Error cleanup

Virtualization setup adquire estado que precisa ser desfeito em ordem reversa.

Conceitualmente:

~~~text
detect capability
  -> enable virtualization
  -> allocate control structure
  -> configure memory
  -> load guest state
  -> enter guest
~~~

Failure não pode deixar control structures, pinned pages ou virtualization state vazando após destroy.

Repeated create/destroy tests tornam isso especialmente importante.

## Multi-vCPU

ChrisVM atual cria uma CPU.

Hardware virtualization pode incentivar parallel vCPUs, mas isso muda o machine contract.

Surgem:

- concurrent RAM access;
- interrupt routing;
- guest atomic operations;
- AP startup;
- device synchronization;
- inter-vCPU invalidation;
- deterministic scheduling.

ChrisHV não deve adicionar SMP acidentalmente.

Single-vCPU equivalence é milestone inicial mais seguro.

## Equivalência com ChrisCPU

Validation inicial forte é differential execution.

Para guest suportado nos dois backends:

1. criar machine state igual;
2. executar workload bounded em ChrisCPU;
3. executar o mesmo em ChrisHV;
4. comparar architectural state;
5. comparar memory;
6. comparar I/O/device state;
7. comparar exit classification.

Timing/TSC pode precisar de normalization.

ChrisCPU então permanece semantic reference após chegada de acceleration.

## Milestone mínimo VMX

Primeiro milestone Intel honesto poderia ser:

- capability detected;
- VMX activation;
- um VMCS;
- minimal 64-bit guest entry;
- bounded register-only workload;
- controlled HLT/exit;
- state recovered;
- clean teardown.

Só depois de gate reproduzível deveria haver claim de executable VMX support.

## Milestone mínimo SVM

No AMD:

- SVM capability;
- VMCB configurado;
- guest state mínimo;
- `VMRUN`;
- controlled intercept;
- state recovery;
- clean teardown.

Header vazio não é implementation evidence.

## Security boundary

Hardware virtualization fornece primitives fortes de CPU isolation, mas não torna VM segura automaticamente.

Security depende também de:

- EPT/NPT permissions;
- exit handlers;
- device emulation;
- host mappings;
- DMA policy;
- interrupts;
- guest-state validation.

Bug em virtual device ou memory mapping ainda pode quebrar boundary.

Nenhum security claim desse tipo é válido para o stub atual.

## Performance model

O custo deixa de ser interpretação de cada ordinary instruction.

Custos importantes passam a incluir:

- VM entry/exit;
- second-level translation/TLB;
- intercepted I/O;
- event injection;
- device emulation;
- synchronization;
- host scheduler.

Workload com poucos exits pode se beneficiar muito.

Workload que causa exits constantes pode perder parte do ganho.

Performance precisa ser medida.

## Evidência atual

A evidência mais forte do ChrisHV atual é negativa e intencional:

- backend name resolve;
- initialization falha;
- source declara ausência de VMX/SVM/KVM;
- VMX header diz not started;
- SVM header diz not started.

Isso prova que ChrisHV não se apresenta falsamente como acceleration funcional.

## VM entry e exit como transação

Uma execução hardware-backed de vCPU deve ser tratada como transação de estado.

Antes da entry, ChrisHV precisa estabelecer guest state e execution controls consumidos pelo processador. Após exit, precisa recuperar os fields necessários pelo ChrisVM antes de qualquer machine-level observer assumir que `ChrisArchitectureState` está atualizado.

Conceitualmente:

~~~text
machine state
    -> backend import
    -> hardware control state
    -> VM entry
    -> guest execution
    -> VM exit
    -> backend export
    -> coherent machine state
~~~

A transação também precisa definir entry failure. Nesse caso não houve guest execution válida, mas resources parcialmente preparados ainda podem exigir cleanup.

Esse modelo evita estado intermediário ambíguo em que alguns registers estão em `ChrisArchitectureState` e outros já mudaram dentro de VMCS/VMCB.

## Observabilidade do backend

Hardware acceleration não deve tornar failures menos diagnosticáveis que o interpreter.

ChrisHV futuro deve fornecer diagnostics estruturados para:

- capability detection;
- virtualization-enable failure;
- control-structure validation;
- VM-entry failure;
- VM-exit reason;
- second-level translation violation;
- event-injection failure;
- teardown failure.

O diagnostic deve identificar backend e stage sem expor host-privileged state desnecessariamente.

Para equivalence testing, também é útil preservar trace bounded ao redor da última entry/exit quando possível. O objetivo não é registrar toda native guest instruction, mas tornar cada backend transition atribuível a machine state e exit reason específicos.

## Limitações atuais

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, faltam:

- VMX initialization;
- SVM initialization;
- KVM integration;
- VMCS/VMCB allocation;
- VM entry;
- VM-exit handling;
- EPT/NPT;
- hardware event injection;
- hardware vCPU lifecycle;
- state synchronization;
- hardware-backend tests;
- SMP hardware execution.

Tudo acima é future work.

## Sequência de roadmap

Uma ordem defensável:

1. capability detection;
2. uma vendor, uma CPU;
3. control-structure lifetime;
4. minimal entry/exit;
5. state import/export;
6. second-level memory;
7. port-I/O/MMIO exits;
8. event injection;
9. differential tests com ChrisCPU;
10. broader devices;
11. SMP somente após single-vCPU stable;
12. segunda vendor.

Isso minimiza unknowns simultâneos.

## Invariante arquitetural

ChrisHV deve preservar:

> O CPU execution backend pode mudar, mas o machine contract guest-visible do ChrisVM não deve mudar apenas porque execution passou de interpreter para hardware virtualization.

Backend choice não deve alterar silenciosamente:

- RAM layout;
- boot protocol;
- device addresses;
- serial;
- framebuffer;
- machine exit semantics.

Detalhes vendor-specific ficam abaixo da interface.

## Nota de revisão

Este capítulo foi reconciliado contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56` e documentação arquitetural atual de Intel VMX e AMD SVM.

O claim implementado é estreito: **ChrisHV é um backend seam reservado e fail-closed. Hardware-assisted execution não está implementada.**
