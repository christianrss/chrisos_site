---
id: svm
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/Makefile
  - chrisvm/chris_arch.h
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/machine.h
  - chrisvm/cpu/hv/chrishv.c
  - chrisvm/cpu/hv/vmx/vmx.h
  - chrisvm/cpu/hv/svm/svm.h
  - chrisvm/tests/test_chrisvm.c
symbols:
  - ChrisCpuBackend
  - ChrisArchitectureState
  - chrishv_backend
  - chris_backend_by_name
depends_on:
  - virtualization-chrishv
  - chris-architecture-state
  - x86-64-memory-privilege
related:
  - vmx
  - ept-npt
  - chrisvm-machine
  - determinism-replay
---

# AMD SVM e o futuro backend ChrisHV

## Escopo

AMD Secure Virtual Machine, normalmente chamado SVM ou AMD-V, fornece assistência de hardware para executar software guest diretamente em um processador AMD64 enquanto o virtual-machine monitor intercepta operações selecionadas e preserva isolamento.

SVM resolve o mesmo problema geral do Intel VMX, mas utiliza instruções, estruturas de controle e lifecycle diferentes.

Para o ChrisHV, SVM deve ser um backend irmão de VMX sob os mesmos contratos de machine e architectural state, não um conjunto de wrappers VMX renomeados para AMD.

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, SVM não está implementado.

O source declara:

    AMD SVM backend for ChrisHV.
    Not started. VMX comes first, on the ISA of the development machine.

Este capítulo documenta a arquitetura AMD relevante para um futuro ChrisHV mantendo explícita a fronteira entre teoria e implementação atual.

## Referência arquitetural primária

A fonte normativa é AMD64 Architecture Programmer's Manual, Volume 2: System Programming, capítulo 15, Secure Virtual Machine.

A revisão considerada é a publicação AMD 24593, revisão 3.44, de março de 2026.

Esse manual é autoritativo para:

- feature discovery de SVM;
- layout do VMCB;
- intercept semantics;
- VMRUN;
- VMLOAD/VMSAVE;
- nested paging;
- ASID/TLB;
- interrupt virtualization;
- extensões SVM mais recentes.

ChrisHV deve consultar capabilities informadas pela CPU em vez de presumir que todos os AMD64 suportam o mesmo conjunto de recursos.

## Estado atual do ChrisOS

A inicialização do ChrisHV atual falha antes de qualquer caminho vendor-specific.

O header SVM não contém structs ou código executável.

Não existe atualmente:

- SVM CPUID probe;
- EFER.SVME setup;
- ownership de VM_HSAVE_PA;
- definição de VMCB;
- wrapper VMRUN;
- dispatcher #VMEXIT;
- nested paging;
- ASID allocator;
- TLB control;
- event injection;
- AVIC;
- SEV.

Portanto, SVM é somente alvo arquitetural.

## SVM versus VMX

VMX e SVM não devem ser tratados como equivalentes instrução por instrução.

Ambos fornecem conceitualmente:

    guest state
    execution controls
    entrada no guest
    saída ao monitor
    second-level translation
    event injection
    suporte de TLB

Mas os mecanismos concretos diferem.

Intel centraliza VMXON e VMCS acessado por VMREAD/VMWRITE.

AMD centraliza SVM no Virtual Machine Control Block, VMCB, residente em memória e consumido por VMRUN.

ChrisHV deve normalizar comportamento na fronteira da machine, não esconder à força todas as diferenças internas.

## Feature discovery

AMD expõe SVM por extended CPUID leaves.

O backend futuro deve identificar ao menos:

- presença de SVM;
- feature set disponível;
- capacidade de ASIDs;
- suporte a nested paging;
- recursos opcionais de interrupt virtualization;
- clean bits e decode assists quando presentes;
- qualquer feature necessária pelo modo ChrisHV selecionado.

Capability discovery deve produzir uma estrutura estável, por exemplo:

    ChrisSvmCaps

em vez de CPUID tests espalhados pelo runtime.

## EFER.SVME

SVM requer habilitação do bit Secure Virtual Machine Enable em EFER.

Conceitualmente:

    ler EFER
    habilitar SVME
    gravar EFER

Esse estado é privilegiado.

Assim como VMX direto, um processo ChrisVM comum em user space sob um host convencional não pode simplesmente assumir ownership de SVM.

O projeto precisa escolher uma arquitetura privilegiada:

- execução direta em ambiente ChrisOS/bare-metal;
- componente de kernel host;
- ou API de virtualização como KVM.

## VM_HSAVE_PA

Antes das transições guest, SVM usa VM_HSAVE_PA para indicar uma host-save area em memória física.

O monitor aloca uma página física apropriada e grava seu endereço no MSR correspondente.

O processador utiliza essa área no world switch.

Isso é estado host/global por logical processor, não guest RAM.

Um ChrisHV futuro deve possuir claramente esse recurso e liberar corretamente no teardown.

## VMCB

Virtual Machine Control Block é a estrutura central de SVM.

Diferente do VMCS, o VMCB possui layout de memória arquiteturalmente definido e pode ser manipulado diretamente pelo software.

Ele possui duas áreas conceituais principais:

- control area;
- state-save area.

A control area define política de virtualização.

A state-save area representa estado arquitetural do guest.

Um futuro ChrisSvmVcpu pode possuir um VMCB e metadata host associada.

## Alinhamento e endereço físico

VMRUN identifica o VMCB por physical address.

Isso exige distinguir:

- host virtual pointer usado pelo C;
- host physical address consumido pela CPU;
- guest physical addresses dentro do estado guest.

Um pointer retornado por malloc não é automaticamente um physical address válido para VMCB.

SVM direto exige memória pinned/owned fisicamente endereçável e uma tradução explícita host virtual → host physical.

## Control area

A control area do VMCB contém política como:

- instruction intercepts;
- exception intercepts;
- base do I/O permission map;
- base do MSR permission map;
- ASID;
- TLB-control request;
- virtual interrupt controls;
- nested paging controls;
- event injection;
- exit information;
- clean bits;
- campos opcionais de features.

O ideal é encapsular offsets e encoding em um módulo SVM específico.

Código genérico ChrisHV não deve manipular offsets VMCB diretamente.

## State-save area

A state-save area contém estado guest para world switch.

Categorias importantes:

- segment registers e attributes;
- descriptor tables;
- control registers;
- EFER;
- RIP;
- RSP;
- RFLAGS;
- RAX;
- MSRs e system state selecionados.

ChrisArchitectureState é a ponte backend-neutral natural.

Entretanto, o mapping não precisa ser 1:1.

A implementação deve definir regras explícitas de import/export e documentar qualquer estado requerido por SVM que a struct ainda não represente.

## VMRUN

VMRUN realiza a transição principal host → guest.

O monitor fornece o physical address do VMCB conforme a convenção AMD e executa VMRUN.

O processador:

- salva o host state necessário;
- carrega guest state e controls do VMCB;
- executa o guest;
- retorna ao monitor quando ocorre evento interceptado ou condição de exit;
- atualiza informações de saída/estado no VMCB.

O contrato exato de world switch precisa ser implementado em low-level code privilegiado.

## Wrapper de world switch

Um backend robusto não deve espalhar inline assembly de VMRUN por arquivos C.

Um wrapper arquitetural estreito deve controlar:

- host callee-saved state;
- invocação VMRUN;
- return path;
- host stack assumptions;
- clobbers;
- captura de exit/error state.

Esse wrapper se torna uma ABI entre ChrisHV genérico e a implementação AMD64.

## VMLOAD e VMSAVE

SVM fornece VMLOAD e VMSAVE para categorias selecionadas de estado associadas ao VMCB.

O papel dessas instruções é diferente de copiar memória do VMCB manualmente.

O backend precisa saber precisamente quais fields:

- VMRUN carrega;
- VMLOAD/VMSAVE gerenciam;
- software gerencia;
- ChrisArchitectureState representa.

Errar essa fronteira pode causar state leakage ou resume incorreto.

## Intercepts

SVM permite configurar interceptação de instruções, exceptions e eventos.

Exemplos relevantes:

- CPUID;
- HLT;
- I/O;
- MSR;
- control-register accesses;
- selected exceptions;
- external-interrupt handling.

Durante bring-up inicial é melhor interceptar mais e reduzir depois.

Depois de provar semântica, intercepts desnecessários podem ser removidos para performance.

## CPUID interception

ChrisCPU fornece CPUID virtual fixo.

Se SVM executar CPUID nativo sem interception, o guest observará a CPU AMD física.

Isso quebra equivalência de backend e determinismo.

ChrisHV deve interceptar CPUID e utilizar a mesma política virtual versionada do ChrisCPU, ou definir explicitamente um novo modelo compartilhado.

## I/O interception

SVM suporta interceptação de I/O por meio de I/O permission map.

Isso encaixa diretamente no I/O bus atual.

Fluxo futuro:

    guest IN/OUT
        ↓
    #VMEXIT
        ↓
    examinar exit information
        ↓
    chris_io_in / chris_io_out
        ↓
    atualizar resultado guest
        ↓
    avançar RIP corretamente
        ↓
    VMRUN

Serial e shutdown devices não devem ser reimplementados dentro do backend SVM.

## MSR interception

SVM suporta MSR Permission Map.

ChrisHV deve utilizá-lo para manter o guest-visible MSR contract.

Liberar MSRs físicos arbitrários expõe host state e pode comprometer isolamento.

O desenho deve classificar MSRs em:

- emulados/interceptados;
- virtualizados por suporte de hardware;
- não suportados;
- passthrough somente quando fizer parte explícita do virtual CPU model.

## #VMEXIT

SVM retorna ao VMM por semântica #VMEXIT e grava exit information no VMCB.

A control area possui fields como:

    exit_code
    exit_info1
    exit_info2
    exit_int_info

além de decode assists onde suportados.

Handlers precisam decidir se irão:

- emular;
- injetar evento;
- alterar mappings;
- retomar;
- parar a VM.

## Decode assist

Alguns processadores AMD oferecem decode assists para reduzir trabalho de decoding em certos exits.

O backend deve consultar capability antes de depender desses dados.

A implementação precisa permanecer correta quando o assist opcional não existe.

O decoder x86 do ChrisCPU pode servir de fallback em alguns casos, mas é necessário reconciliar cuidadosamente metadata de hardware e decoder de software.

## Avanço de RIP

Assim como em VMX, RIP advancement incorreto é uma fonte clássica de bugs.

Alguns exits representam uma instrução emulada que deve ser pulada.

Outros representam faults/eventos reinjetados sem avanço.

O backend deve usar ações explícitas de resume em vez de modificar RIP de forma dispersa.

## Nested paging

Nested paging implementa second-level translation em AMD.

Fluxo:

    guest virtual
        ↓ guest page tables
    guest physical
        ↓ nested page tables
    system physical

É o equivalente funcional de EPT da Intel.

O guest mantém seu próprio CR3 e paging, enquanto ChrisHV controla guest physical → system physical.

## Nested page faults

Nested-page fault não é igual a guest #PF.

Guest #PF pertence ao primeiro nível.

Nested page fault pertence ao nível controlado pelo hypervisor.

Pode ser usado para:

- MMIO trapping;
- lazy mapping;
- access control;
- dirty tracking;
- copy-on-write;
- diagnostics.

ChrisHV precisa distinguir as duas classes e não injetar #PF apenas porque NPT falhou.

## nCR3

Nested paging usa um root próprio.

O VMCB contém o estado necessário, incluindo nested CR3/root.

Esse root pertence ao hypervisor.

Não deve ser confundido com o guest CR3 exposto em ChrisArchitectureState.

## ASIDs

SVM usa Address Space Identifiers para taguear translations.

ASIDs diminuem a necessidade de flush completo em cada world switch.

Um futuro allocator precisa lidar com:

- valor inválido/reservado;
- rollover;
- generation tracking;
- flush policy;
- ownership per-host-CPU quando aplicável.

## TLB control

AMD define TLB-control no VMCB.

Alterar paging guest ou nested paging não significa que stale translations serão removidas automaticamente.

O VMM precisa solicitar invalidation apropriada.

O método genérico:

    invalidate_tlb

já oferece uma seam, mas a implementação AMD deve considerar ASIDs e nested paging.

## INVLPGA

AMD fornece INVLPGA para invalidar translations associadas a address/ASID.

Um backend maduro pode usar invalidation direcionada.

Primeiro bring-up pode usar política conservadora onde permitido, priorizando correctness.

## Clean bits

VMCB clean bits permitem indicar quais grupos de estado não mudaram desde a execução anterior.

Isso pode reduzir overhead.

Mas é um contrato de correctness.

Se software modificar um field e deixar o grupo marcado como clean, a CPU pode reutilizar estado interno antigo.

Bring-up inicial deve ser conservador e marcar grupos como dirty até ownership estar comprovado.

## Campos fora dos clean bits

AMD documenta campos que não participam do clean-bit mechanism, especialmente estado runtime/exit-sensitive.

Isso significa que não existe um único global "VMCB unchanged".

ChrisHV deve esconder clean-bit bookkeeping por setters ou state-group tracking.

## Virtual interrupts

SVM fornece mecanismos para virtual interrupt handling.

Suporte básico deve manter:

- pending interrupt state;
- guest IF;
- interrupt shadow/state;
- priority quando modelada;
- timing correto de injection.

O método genérico inject_irq pode ser a entrada.

O backend converte a solicitação para os fields/event injection do VMCB.

## AVIC

Processadores AMD modernos podem oferecer Advanced Virtual Interrupt Controller.

AVIC reduz exits de interrupt virtualization.

Não é necessário para o primeiro bring-up.

Deve ser feature opcional adicionada depois que injection e virtual APIC básicos estiverem corretos.

## PAUSE filtering

SVM também possui mecanismos como PAUSE filtering em processadores compatíveis.

Eles podem reduzir overhead de guests em spin loops.

Isso é otimização, não pré-requisito de backend funcional.

## Determinismo

SVM introduz as mesmas fontes de variação que VMX:

- host scheduling;
- physical interrupt timing;
- hardware TSC;
- variable exit timing;
- performance específica do host.

ChrisHV não deve herdar host time ou host CPUID silenciosamente se o virtual machine contract promete estabilidade.

Record/replay precisa controlar ou registrar eventos externos.

## Virtualização de TSC

SVM oferece suporte relacionado a virtualização de TSC guest.

ChrisHV precisa definir uma semântica única.

Possibilidades:

- host TSC;
- host TSC com offset/escala quando disponível;
- synthetic logical time.

Para equivalência com ChrisCPU, passthrough direto do TSC físico é inadequado salvo mudança deliberada do contrato.

## Isolamento de host state

Guest não pode herdar estado host indevido.

Categorias críticas:

- MSRs;
- debug registers;
- segments;
- extended processor state;
- performance state;
- tempo/TSC;
- security-sensitive controls.

O world-switch layer precisa documentar o que hardware salva/restaura e o que software deve gerenciar.

## FPU e extended state

Execução em hardware pode liberar instruções não implementadas no ChrisCPU.

Se CPUID anunciar SSE/AVX/XSAVE, ChrisHV precisa preservar esse estado corretamente.

Um primeiro backend deveria expor intencionalmente apenas features que consegue salvar, restaurar e validar.

## Segurança

SVM executa guest não confiável diretamente na CPU host.

O VMM deve proteger:

- host memory;
- VMCB;
- host-save area;
- nested page tables;
- IOPM/MSRPM;
- host stacks;
- device-model memory;
- vCPU metadata.

Qualquer endereço/exit data controlado pelo guest deve ser validado antes de indexar memória host.

## IOPM e MSRPM

I/O Permission Map e MSR Permission Map são estruturas host-owned referenciadas por physical address.

Devem permanecer pinned e válidas enquanto o VMCB as referenciar.

Guest não pode ter capacidade de remapear ou sobrescrever essas regiões.

## SEV não é SVM básico

Secure Encrypted Virtualization, incluindo SEV-ES e SEV-SNP, pertence ao ecossistema AMD virtualization, mas altera profundamente o trust model.

Implementar SVM não significa implementar SEV.

SEV adiciona firmware protocols, encrypted guest state e propriedades de memory encryption/integrity.

Essas features devem ser tratadas separadamente.

## Arquitetura privilegiada do host

O mesmo problema prático de VMX ocorre aqui.

ChrisVM atual é um executável host comum.

VMRUN direto requer privilégio.

O projeto deve escolher entre:

- SVM dentro de ambiente ChrisOS privilegiado;
- host kernel driver;
- KVM;
- monitor bare-metal.

Hoje nenhuma dessas camadas existe no repo ChrisVM.

## Caminho KVM em host AMD

Linux KVM já gerencia SVM no kernel.

Um ChrisHV baseado em KVM poderia manter ChrisMachine em user space e delegar world switch privilegiado.

Trade-offs:

- menos controle de raw SVM;
- implementação funcional mais rápida;
- dependência do Linux/KVM;
- privilege e physical-memory management simplificados.

SVM direto pode continuar como objetivo educacional/research.

## Sequência de bring-up

Uma ordem segura:

1. detectar SVM;
2. verificar policy do host;
3. alocar host-save area;
4. habilitar EFER.SVME;
5. inicializar VMCB;
6. configurar intercepts mínimos;
7. montar guest long-mode state válido;
8. executar VMRUN;
9. tratar HLT;
10. interceptar CPUID;
11. interceptar I/O;
12. adicionar nested paging;
13. adicionar interrupt injection;
14. validar teardown e repetição.

Essa progressão reduz variáveis a cada milestone.

## Guest mínimo

O primeiro guest pode conter:

    CPUID
    OUT test-port
    HLT

Isso valida:

- world switch;
- intercept configuration;
- exit decode;
- virtual CPUID;
- I/O bus;
- RIP progression;
- HLT;
- VMRUN repetido.

O kernel ChrisOS completo não deve ser o primeiro teste.

## Ponte ChrisArchitectureState

O objetivo permanece:

    ChrisArchitectureState
        ↕
    ChrisCPU state
        ou
    SVM VMCB state

Funções futuras poderiam ser:

    svm_import_arch_state(vcpu, state)
    svm_export_arch_state(vcpu, state)

Essas funções devem ser testáveis com VMCBs sintéticos antes de hardware execution.

## Machine model backend-neutral

ChrisMachine deve continuar dono de:

- RAM policy;
- serial;
- framebuffer;
- I/O;
- MMIO;
- boot/image behavior.

SVM deve possuir:

- host SVM capability;
- host-save area;
- per-vCPU VMCB;
- VMRUN;
- exit decoding;
- NPT integration;
- hardware event injection.

Essa é a mesma fronteira planejada para VMX.

## Validação diferencial

Quando SVM estiver funcional, o mesmo guest deve poder rodar em ChrisCPU e ChrisHV.

Comparações úteis:

- GPRs;
- RIP/RSP;
- RFLAGS;
- CRs;
- virtual CPUID;
- serial output;
- RAM digest;
- exit reason;
- exceptions;
- framebuffer quando relevante.

Isso ajuda a localizar divergências entre CPU backend e generic machine model.

## Testes negativos

É necessário testar:

- SVM ausente;
- SVM bloqueado;
- VMCB address inválido;
- malformed control state;
- invalid guest state;
- NPT root inválido;
- ASID rollover;
- stale TLB;
- init/shutdown repetido;
- cleanup após falha parcial;
- migração para host CPU sem setup correspondente.

## Diagnostics

Bring-up deve expor:

- SVM CPUID;
- feature bits;
- ASID capacity;
- EFER.SVME;
- host-save physical address;
- VMCB physical address;
- intercept configuration;
- NPT enable/root;
- current ASID;
- TLB-control;
- exit code;
- exit info;
- guest RIP;
- guest physical/linear address relevante.

Sem isso, debugging vira tentativa e erro.

## Performance

Performance depende muito de world switches e exits.

Exits frequentes de:

- CPUID;
- I/O;
- MSR;
- interrupts;
- memory faults;

podem dominar custo.

Depois de correctness, otimizações incluem:

- reduzir intercepts;
- usar NPT;
- usar ASIDs;
- clean bits corretos;
- decode assists;
- virtual interrupt acceleration.

## Limitações atuais

Na revisão analisada não existem:

- SVM capability structure;
- EFER.SVME management;
- VM_HSAVE_PA;
- VMCB wrapper;
- intercept setup;
- IOPM/MSRPM allocation;
- VMRUN wrapper;
- VMLOAD/VMSAVE integration;
- #VMEXIT dispatcher;
- NPT;
- ASID allocator;
- TLB-control logic;
- INVLPGA policy;
- interrupt injection;
- AVIC;
- SEV.

Isso corresponde ao header que declara SVM ainda não iniciado.

## Prioridades de implementação

Uma ordem razoável é:

1. decidir a arquitetura privilegiada do host;
2. capability discovery e diagnostics;
3. per-host-CPU SVM state;
4. host-save e EFER.SVME lifecycle;
5. VMCB abstraction;
6. assembly world-switch wrapper;
7. import/export do subset mínimo de ChrisArchitectureState;
8. lançar guest mínimo;
9. tratar HLT, CPUID e port I/O;
10. conectar devices atuais;
11. NPT para RAM;
12. MMIO trapping;
13. ASID/TLB policy;
14. interrupt injection;
15. teardown robusto;
16. differential tests com ChrisCPU;
17. somente depois adicionar extensões opcionais de performance/segurança.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, AMD SVM não está implementado no ChrisHV. O projeto contém apenas o placeholder vendor-specific e a seam genérica do hardware backend. Um backend real exigirá ownership privilegiado de SVM, host-save state, VMCB, VMRUN/#VMEXIT, nested paging, ASIDs e interrupt virtualization, preservando os mesmos contratos ChrisMachine e ChrisArchitectureState usados pelo ChrisCPU e pelo VMX planejado.
