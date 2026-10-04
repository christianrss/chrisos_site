---
id: vmx
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
  - svm
  - ept-npt
  - chrisvm-machine
  - determinism-replay
---

# Intel VMX e o futuro backend ChrisHV

## Escopo

Intel Virtual Machine Extensions, normalmente chamado VMX ou Intel VT-x, fornece suporte arquitetural para executar um contexto guest diretamente em um processador Intel físico mantendo transferência controlada de execução para um virtual-machine monitor.

VMX **não** elimina a necessidade de uma máquina virtual.

Ele acelera a parte de execução da CPU.

Um VMM completo ainda precisa de:

- ownership de estado guest/host;
- virtualização de memória;
- interrupt routing;
- I/O;
- device models;
- política de tempo;
- dispatch de exits;
- recovery;
- teardown;
- segurança;
- validação.

Este capítulo separa a arquitetura Intel VMX do estado atual do ChrisOS.

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, VMX não está implementado.

O código declara isso diretamente em:

    chrisvm/cpu/hv/vmx/vmx.h

e a inicialização do ChrisHV falha deliberadamente.

Portanto, estruturas, instruções e sequências VMX descritas abaixo são teoria arquitetural ou plano de implementação, salvo quando identificadas explicitamente como comportamento atual do ChrisOS.

## Referência arquitetural primária

A fonte normativa para VMX é o Intel 64 and IA-32 Software Developer's Manual, especialmente os volumes de system programming que documentam VMX operation, VMCS, VM entry, VM exit, EPT, VPID e as instruções VMX.

A documentação revisada para este capítulo é a versão 093 do Intel SDM publicada pela Intel em 2026.

O manual da Intel, e não este capítulo, é autoritativo para requisitos específicos de processador e capability bits.

Software VMX deve derivar controles suportados dos MSRs de capability do processador em vez de assumir que todos os Intel implementam o mesmo conjunto.

## Estado atual do ChrisOS

O source atual do ChrisHV diz explicitamente:

    There is no VMX, no SVM, and no KVM.

O header VMX diz:

    Not started.

Selecionar:

    --backend=chrishv

chega a chrishv_backend.

Seu callback init imprime a mensagem de não implementação e retorna falha.

A criação da machine é então rejeitada.

A suíte de testes do ChrisVM espera exatamente essa falha.

Logo, o ChrisOS hoje possui a abstração de backend para virtualização futura, não uma implementação VMX parcial.

## O modelo de execução do host importa

O Makefile atual do ChrisVM compila a frontend com GCC comum do host:

    gcc ... -o ../build/chrisvm/chrisvm

O resultado é um executável host normal.

VMX direto é funcionalidade privilegiada da CPU.

Um processo comum em user space não pode simplesmente executar VMXON e assumir ownership de VMCS, interrupts e memória em um sistema operacional host convencional.

Portanto, ChrisHV real precisa escolher uma arquitetura de execução.

Opções plausíveis incluem:

1. um ambiente privilegiado ChrisOS/nativo que possua a máquina diretamente;
2. kernel module/driver do host executando operações VMX para a frontend;
3. API de virtualização existente, como Linux KVM;
4. hypervisor bare-metal separado.

O código atual diz explicitamente que não usa /dev/kvm.

Isso descreve o estado presente, não uma proibição arquitetural permanente.

## VMX root e non-root

VMX introduz dois modos ortogonais aos rings normais do x86:

    VMX root operation
    VMX non-root operation

O VMM normalmente roda em VMX root.

O guest normalmente roda em VMX non-root.

Isso não significa:

    root = ring 0
    non-root = ring 3

Um kernel guest pode executar em CPL 0 dentro de VMX non-root.

O VMM host pode executar em CPL 0 dentro de VMX root.

VMX adiciona, portanto, uma segunda dimensão de controle acima do modelo de rings do guest.

## Por que VMX existe

Sem assistência de hardware, determinadas operações privilegiadas do guest não podem simplesmente executar livremente sem comprometer controle do host.

VMX permite executar instruções guest diretamente até que um evento configurado provoque retorno ao monitor.

O loop central torna-se:

    configurar VMCS
        ↓
    VM entry
        ↓
    guest executa em non-root
        ↓
    evento configurado
        ↓
    VM exit
        ↓
    VMM examina exit reason
        ↓
    emula / atualiza estado / injeta evento
        ↓
    VMRESUME

Isso é fundamentalmente diferente do ChrisCPU, que decodifica e implementa cada instrução guest em software.

## Detecção de capability

Um VMM não deve tentar inicializar VMX apenas por estar em CPU Intel.

No mínimo é necessário verificar suporte VMX via CPUID.

Depois, os capability MSRs relevantes precisam ser lidos.

Classes importantes incluem:

- IA32_VMX_BASIC;
- VMX control capability MSRs;
- fixed bits de CR0;
- fixed bits de CR4;
- capabilities EPT/VPID;
- capabilities miscellaneous de VMX.

A legalidade de controles varia entre processadores.

Um futuro ChrisHV deve centralizar capability discovery em estruturas de dados, não espalhar assumptions por setup code.

## IA32_FEATURE_CONTROL

A habilitação de VMX também depende de IA32_FEATURE_CONTROL.

Firmware normalmente configura e bloqueia esse MSR.

Uma plataforma pode possuir VMX no silício e mesmo assim não permitir o uso pretendido.

A implementação precisa distinguir:

- VMX ausente;
- VMX presente, mas desabilitado por firmware;
- VMX disponível;
- VMX indisponível porque o host já possui/controla a virtualização.

Uma mensagem genérica "VMX failed" seria insuficiente para bring-up.

## CR4.VMXE

Antes de VMXON, software precisa habilitar VMX por CR4.VMXE e satisfazer requisitos arquiteturais.

CR0 e CR4 também precisam obedecer aos fixed-bit constraints informados pelo processador.

O padrão conceitual é:

    cr0 = (cr0 | fixed0_cr0) & fixed1_cr0
    cr4 = (cr4 | fixed0_cr4) & fixed1_cr4
    cr4 |= VMXE

A ordem e regras exatas devem seguir a arquitetura Intel.

A regra de projeto é simples: os MSRs de fixed bits são autoritativos.

Máscaras hard-coded não são seguras entre gerações.

## Região VMXON

Entrar em VMX operation exige uma região VMXON em memória física.

A região precisa satisfazer alinhamento e memory type definidos pelo processador.

A Intel documenta o modelo com alinhamento de 4 KiB.

O VMM lê o VMCS revision identifier de IA32_VMX_BASIC e grava o revision value necessário na região VMXON antes de executar VMXON.

Conceitualmente:

    alocar VMXON region
    preparar/zerar
    gravar revision identifier
    obter physical address
    VMXON [physical-address operand]

VMXON bem-sucedido coloca o logical processor em VMX operation.

Isso ainda não lança guest algum.

## Ownership por CPU física

VMX operation é associado ao logical processor.

Em host SMP, cada logical processor usado pelo hypervisor precisa de lifecycle VMX correto.

Isso implica futuro estado per-CPU, por exemplo:

    ChrisHvCpu
        host cpu id
        VMXON region
        ownership de VMCS
        capability cache
        host stack
        exit context

ChrisMachine hoje possui apenas um ChrisCpu e não resolve esse problema host-side.

Mesmo um guest single-vCPU pode migrar entre host CPUs se a implementação não fixar affinity ou realizar transições corretas.

## VMCS

Virtual-Machine Control Structure, VMCS, define o contrato de execução de um guest VMX.

VMCS não é uma struct C cujo layout pode ser dereferenced diretamente pelo software.

Intel define VMREAD e VMWRITE como interface arquitetural para os fields.

O VMCS contém classes de estado como:

- guest state;
- host state;
- VM-execution controls;
- VM-entry controls;
- VM-exit controls;
- VM-exit information;
- event-injection fields;
- endereços de estruturas opcionais.

ChrisHV deve tratar field encodings do VMCS como ABI arquitetural, não sobrepor uma struct inventada sobre a região.

## Lifecycle do VMCS

Um lifecycle típico é:

    alocar VMCS region
    gravar revision identifier
    VMCLEAR
    VMPTRLD
    VMWRITE de controls/state
    VMLAUNCH
    ...
    VMRESUME
    ...
    VMCLEAR antes de liberar ownership

O VMM também precisa respeitar as noções de VMCS active/current.

Estado do VMCS pode permanecer cacheado internamente pelo processador.

Teardown correto é requisito arquitetural, não simples free de memória.

## VMLAUNCH e VMRESUME

A primeira entrada de um VMCS usa VMLAUNCH.

Entradas posteriores usam VMRESUME depois de launch bem-sucedido.

Software precisa rastrear launch state.

Usar a instrução errada é condição de VM-entry failure.

Uma futura estrutura de vCPU deveria tornar isso explícito:

    enum {
        VMCS_CLEAR,
        VMCS_LOADED,
        VMCS_LAUNCHED
    }

em vez de inferir por campos indiretos.

## Guest state

Guest-state fields representam estado carregado na VM entry e atualizado durante VM exit.

Categorias relevantes incluem:

- estado geral da CPU;
- control registers;
- segments;
- descriptor tables;
- RIP;
- RSP;
- RFLAGS;
- MSRs selecionados;
- interruptibility/activity;
- paging e long mode.

O ChrisOS já possui:

    ChrisArchitectureState

como contrato backend-neutral.

Essa estrutura é o candidato natural para tradução de/para VMCS.

Mas ela não deve ser presumida completa.

A implementação precisa realizar gap analysis field-by-field contra os requisitos de VMX.

## Host state

VM exit transfere controle para um host context descrito pelos host-state fields do VMCS.

Esses fields incluem estado necessário para continuar com segurança no VMM.

Uma implementação bare-metal precisa construir explicitamente:

- CR3;
- host stack;
- host RIP;
- segment selectors;
- descriptor tables;
- MSRs necessários.

Esse é um dos motivos pelos quais VMX não é apenas "executar VMLAUNCH".

A saída forma um ABI de context transfer de baixo nível.

## VM-execution controls

Execution controls definem quais eventos do guest executam diretamente e quais causam VM exit.

Exemplos incluem:

- I/O;
- MSR;
- HLT;
- acesso a control registers;
- exceptions;
- external interrupts;
- secondary processor controls;
- EPT;
- VPID.

O conjunto exato depende do processador.

ChrisHV deve construir controles através de capability MSRs e verificar se features requeridas permaneceram habilitadas.

## Construção segura de controls

Um padrão perigoso seria:

    vmwrite(PIN_BASED_CONTROLS, CONSTANT)

porque alguns bits podem ser obrigatórios ou proibidos dependendo da CPU.

Uma abstração mais segura seria:

    vmx_adjust_controls(msr, desired, required)

que:

1. lê capabilities;
2. força bits obrigatórios;
3. limpa bits não suportados;
4. falha quando feature requerida não pode ser habilitada;
5. registra o effective value.

Esse valor final deve aparecer em diagnostics.

## Interceptação de I/O

VMX pode fazer operações IN/OUT do guest saírem para o monitor.

I/O bitmaps permitem controle fino.

Isso encaixa diretamente no device model atual do ChrisVM.

Um fluxo futuro:

    guest IN/OUT
        ↓
    VM exit
        ↓
    interpretar exit qualification
        ↓
    chris_io_in / chris_io_out
        ↓
    escrever resultado/estado
        ↓
    avançar guest RIP
        ↓
    VMRESUME

Esse reuso é uma das razões para ChrisHV permanecer abaixo de ChrisMachine.

## Interceptação de MSR

VMX permite interceptar RDMSR e WRMSR seletivamente.

MSR bitmaps podem evitar exits para MSRs seguros e interceptar os demais.

ChrisCPU hoje implementa somente um conjunto limitado de MSRs.

ChrisHV não deve expor MSRs do host físico apenas porque hardware execution facilita isso.

O guest-visible MSR contract deve continuar sendo o contrato da CPU virtual.

## CPUID

CPUID exige cuidado especial.

ChrisCPU retorna identidade virtual determinística e não o CPUID físico do host.

Se ChrisHV deixar o guest executar CPUID nativamente, o guest passará a observar a CPU real.

Isso quebra equivalência entre backends e determinismo.

Portanto, ChrisHV deve interceptar CPUID e preservar a política de virtual CPUID do ChrisCPU, salvo mudança arquitetural deliberada.

## HLT

HLT é um excelente primeiro exit para bring-up.

ChrisCPU converte HLT em stop reason da VM.

ChrisHV precisa definir comportamento equivalente.

Em hypervisor completo, HLT pode significar vCPU aguardando interrupt, não necessariamente shutdown.

Para os guests pequenos atuais, preservar semântica observável do ChrisCPU provavelmente é mais valioso no início.

## Exceptions

VMX pode deixar algumas exceptions serem entregues diretamente ao guest ou interceptá-las.

A escolha afeta equivalência de backend.

ChrisCPU possui modelo explícito de software exception delivery.

ChrisHV precisará de uma matriz definindo:

- exceptions tratadas integralmente pelo hardware no guest;
- exceptions interceptadas;
- exceptions reinjetadas;
- failures terminais do monitor.

O objetivo não é maximizar VM exits, mas preservar a arquitetura virtual declarada.

## VM exit

Quando um evento configurado ocorre, o processador executa VM exit.

VMCS fornece informação como:

- exit reason;
- exit qualification;
- guest linear/physical information em certos exits;
- interruption information;
- instruction length quando definido.

O dispatcher conceitual:

    reason = vmread(EXIT_REASON)

    switch reason:
        CPUID
        I/O
        MSR
        HLT
        exception
        EPT violation
        external interrupt
        ...

Cada handler precisa indicar se:

- modifica guest state;
- avança RIP;
- injeta evento;
- resume;
- encerra a VM.

## Avanço de RIP

Um bug clássico de hypervisor é avançar RIP incorretamente.

Para instrução interceptada e emulada pelo monitor, normalmente o guest deve continuar após ela.

Para um fault que será entregue ao guest, RIP pode precisar permanecer na instrução causadora.

VMX fornece instruction-length information em exits relevantes.

ChrisHV deve centralizar essa política.

Um contrato possível:

    VMX_ACTION_RESUME_SAME_RIP
    VMX_ACTION_RESUME_NEXT_RIP
    VMX_ACTION_INJECT
    VMX_ACTION_STOP

## VM-entry failure

VMLAUNCH/VMRESUME pode falhar antes de o guest executar.

Isso é diferente de um VM exit normal.

Falhas podem ocorrer por controls inválidos ou estado guest/host inválido.

Bring-up precisa registrar:

- VM-instruction error;
- controls;
- guest fields relevantes;
- host fields relevantes;
- capability MSRs;
- VMCS lifecycle state.

"VMLAUNCH failed" não é diagnóstico suficiente.

## Interrupt injection

VMCS possui mecanismos de event injection na VM entry.

ChrisHV pode usá-los para entregar interrupts e exceptions virtuais.

A interface de backend já contém:

    inject_irq(cpu, vector)

Portanto, a seam de software existe.

A implementação real precisa definir:

- quando interrupt torna-se pending;
- se guest está interruptible;
- respeito a IF e interruptibility state;
- persistência de evento por exits;
- uso de interrupt-window exiting.

Isso precisa acompanhar o modelo de interrupt controller da machine.

## Interrupts externos

Um interrupt físico do host durante execução do guest não é automaticamente um interrupt guest.

É necessário distinguir:

    host interrupt
    guest virtual interrupt

Hardware físico pertencente ao host pode interromper o VMM.

Um virtual device pode requerer posterior injection no guest.

Misturar essas categorias quebra isolamento.

## EPT

Extended Page Tables implementam second-level translation da Intel.

Com EPT:

    guest virtual
        ↓ guest page tables
    guest physical
        ↓ EPT
    host physical

EPT possui complexidade suficiente para capítulo próprio.

Para VMX, o ponto essencial é que execução hardware-assisted não remove o physical machine model do ChrisVM.

EPT define qual memória host implementa cada guest-physical address.

MMIO continua precisando de trapping ou mapping deliberado.

## EPT violation

EPT violation não é igual a guest #PF.

Guest page fault pertence ao primeiro nível de tradução.

EPT violation pertence à tradução controlada pelo hypervisor.

Pode ser usado para:

- demand mapping;
- MMIO;
- dirty/access tracking;
- copy-on-write;
- proteção;
- diagnostics.

ChrisHV não deve injetar #PF apenas porque ocorreu EPT violation, salvo quando a arquitetura virtual exigir efeito equivalente.

## VPID

Virtual Processor Identifiers reduzem custo de invalidation entre transições de VM.

Sem VPID, invalidation conservadora do TLB pode ser cara.

Com VPID, translations podem ser associadas a identidades virtuais seguindo regras arquiteturais.

Primeiro bring-up pode priorizar correctness sem VPID.

Mas APIs de alto nível não devem assumir que "flush tudo sempre" será política definitiva.

O método existente:

    invalidate_tlb

é uma seam útil para mapear futuramente INVVPID/INVEPT.

## INVEPT e INVVPID

Alterações em EPT ou VPID podem deixar stale translations.

Intel fornece INVEPT e INVVPID com scopes definidos.

O memory subsystem futuro precisa de uma regra clara:

    atualizar translation structure
        ↓
    publicar ordering requerido
        ↓
    executar invalidation
        ↓
    retomar guest

Omitir invalidation produz bugs dependentes de histórico que parecem não determinísticos.

## Unrestricted guest

Implementações modernas de VMX podem fornecer unrestricted guest.

A feature facilita virtualização de estados antigos de startup.

O boot protocol v1 do ChrisVM começa diretamente em long mode sintético.

Portanto, unrestricted guest não é necessário apenas para reproduzir o boot guest atual.

Torna-se importante caso ChrisHV futuramente execute firmware, real mode ou bootloader completo.

## VMX preemption timer

Algumas CPUs oferecem VMX preemption timer.

Ele limita execução do guest até um VM exit forçado.

ChrisCPU hoje usa max_steps lógico.

Esses mecanismos não são equivalentes.

Timer VMX não mede interpreter instructions.

Se equivalência ou replay precisar de orçamento lógico, ChrisHV terá que definir outra estratégia.

## Determinismo

Virtualização por hardware adiciona fontes de não determinismo que o interpretador atual evita:

- host scheduling;
- physical interrupt timing;
- variável de VM exits;
- host TSC;
- diferenças de performance.

ChrisHV não pode declarar equivalência determinística simplesmente por executar o mesmo instruction stream.

Record/replay precisa controlar ou registrar eventos externos e fontes de tempo.

## Virtualização de TSC

VMX oferece mecanismos para virtualizar TSC guest.

O design precisa escolher se o guest vê:

- host TSC;
- host TSC com offset;
- TSC escalado onde suportado;
- tempo lógico sintético.

Encaminhar host TSC conflitaria com as metas de reprodução do ChrisCPU.

O virtual CPU contract deve definir uma semântica e aproximar os backends dela.

## FPU/SSE/XSAVE

ChrisArchitectureState reserva armazenamento XMM, mas ChrisCPU ainda não implementa toda a arquitetura de extended state moderna.

Em hardware, o guest pode executar muitas instruções diretamente se elas não forem bloqueadas por CPUID/controls.

Isso cria uma regra crítica:

    ChrisHV não pode anunciar ou permitir estado arquitetural
    que não consegue salvar, restaurar ou expor deliberadamente.

Antes de liberar features mais amplas, precisa existir política para FPU/SSE/AVX/XSAVE ou um conjunto de features restrito.

## Segurança

VMX forma um boundary de privilégio.

Bugs em VM-exit handling podem vazar estado host ou corromper memória.

Áreas críticas incluem:

- guest-controlled physical addresses;
- EPT;
- VMCS addresses;
- MSR load/store lists;
- I/O bitmaps;
- exit qualifications;
- guest lengths;
- host stack;
- vazamento de estado entre vCPUs.

Valores provenientes do guest devem ser tratados como input não confiável.

## Validação de endereços físicos

Estruturas VMX carregam physical addresses reais do host.

A implementação precisa distinguir:

- guest physical;
- host virtual;
- host physical.

Esses conceitos não são intercambiáveis.

O emulador atual pode usar host pointers diretamente porque software faz a tradução.

VMX exige ownership físico rigoroso.

Um backend direto não pode fornecer arbitrariamente um malloc pointer como endereço físico de VMCS/EPT sem mecanismo que resolva/pinne as páginas reais.

## DMA

EPT virtualiza tradução de memória da CPU.

Ele não resolve automaticamente DMA isolation.

Se ChrisHV futuramente fizer device passthrough, IOMMU torna-se parte da segurança.

O ChrisVM atual usa device models em software; passthrough está fora do escopo atual.

## Bring-up em estágios

Implementação VMX deve ser incremental.

Uma sequência segura é:

1. detectar support;
2. validar firmware policy;
3. entrar/sair de VMX sem guest;
4. criar/clear/load VMCS;
5. validar host exit path;
6. lançar guest mínimo com exit imediato;
7. tratar HLT;
8. tratar CPUID;
9. tratar port I/O;
10. adicionar RAM via EPT;
11. adicionar MMIO;
12. adicionar interrupt injection;
13. validar teardown/recovery.

Tentar bootar o ChrisOS completo primeiro tornaria qualquer falha difícil de localizar.

## Primeiro guest mínimo

Um primeiro guest útil pode ser:

    CPUID
    OUT test-port
    HLT

Isso verifica:

- VM entry;
- CPUID interception;
- I/O exit;
- atualização de guest state;
- RIP advancement;
- HLT exit;
- VMRESUME;
- teardown.

Só depois disso devem entrar paging complexo e devices adicionais.

## Ponte ChrisArchitectureState

O objetivo arquitetural do backend existente é:

    ChrisArchitectureState
        ↕
    ChrisCPU software state
        ou
    VMCS guest state

Funções futuras poderiam ter contratos como:

    vmx_import_arch_state(vcpu, state)
    vmx_export_arch_state(vcpu, state)

Elas deveriam ser testáveis independentemente de VMLAUNCH.

Precisam de regras precisas para segment attributes, controls, MSRs, activity state e campos ainda ausentes.

## Comportamento backend-neutral

ChrisMachine deve continuar responsável por:

- virtual RAM policy;
- serial state;
- framebuffer;
- I/O routing;
- MMIO routing;
- boot/image policy.

ChrisHV deve possuir:

- host virtualization capability;
- per-CPU VMX state;
- VMCS;
- hardware guest execution;
- exit decoding;
- integração da second-level translation.

Essa divisão evita dois virtual platforms incompatíveis.

## KVM como alternativa

Como ChrisVM atual é executável user-space, Linux KVM é uma opção arquitetural prática.

KVM já possui VMX/SVM privilegiado no kernel host.

Um ChrisHV baseado em KVM manteria machine/frontend em user space e utilizaria ioctls para executar vCPU.

Trade-offs:

- menos contato direto com raw VMX;
- dependência de Linux/KVM;
- acesso seguro mais rápido à virtualização;
- implementação funcional mais curta.

VMX direto é mais educacional e fornece controle mais profundo, mas exige ambiente privilegiado.

O projeto precisa decidir conscientemente essa fronteira.

## VMX direto como objetivo de pesquisa

Caso o objetivo seja aprender e implementar VMX diretamente, ele continua válido.

Nesse caso, deve ser tratado como outra arquitetura host, não apenas uma extensão do executável atual.

Possibilidades:

- monitor dentro do ChrisOS ring 0;
- driver Linux privilegiado;
- monitor bare-metal.

O Makefile atual sozinho não fornece privilégio necessário para VMXON.

## Validação diferencial com ChrisCPU

Quando VMX executar guests, testes diferenciais serão extremamente valiosos.

Para guest suportado por ambos:

    executar no ChrisCPU
    capturar resultado

    executar no ChrisHV
    capturar resultado

comparar:

- RIP/RSP;
- GPRs;
- RFLAGS;
- control registers;
- virtual CPUID;
- serial output;
- memory digest;
- exit reason;
- exception behavior.

Isso não prova correção completa, mas forma um oracle específico do projeto.

## Negative tests

VMX também exige testes de falha.

Exemplos:

- VMX ausente;
- VMX bloqueado por firmware;
- revision inválida;
- control requerido não suportado;
- guest state inválido;
- host state inválido;
- VM-entry failure;
- EPT misconfiguration;
- init/shutdown repetido;
- cleanup após falha parcial;
- execução no host CPU errado.

Muitos bugs VMX aparecem antes da primeira instrução guest.

## Diagnostics

Diagnostics úteis devem mostrar:

- CPUID VMX;
- IA32_FEATURE_CONTROL;
- IA32_VMX_BASIC revision/size;
- pin/primary/secondary controls ajustados;
- EPT/VPID capability;
- VMCS lifecycle;
- VM-instruction error;
- exit reason/qualification;
- guest RIP;
- guest linear/physical address quando aplicável;
- host CPU id.

Esses dados devem existir sem necessidade de inserir printf ad-hoc a cada falha.

## Performance

VMX não torna toda operação do guest gratuita.

Performance depende muito da frequência de VM exits.

Exits frequentes para:

- I/O;
- CPUID;
- MSRs;
- faults;
- timers;
- interrupts;

podem dominar custo.

A meta é deixar executar diretamente o que for seguro e interceptar o que o virtual machine contract exige.

Antes de correctness, tentar minimizar exits só dificulta debugging.

## Limitações atuais do source

Na revisão analisada, o ChrisOS não contém:

- VMX capability probe para ChrisHV;
- FEATURE_CONTROL validation;
- CR4.VMXE setup;
- VMXON;
- VMCS allocation;
- VMCLEAR/VMPTRLD;
- VMREAD/VMWRITE wrappers;
- control adjustment;
- host-state setup;
- guest-state translation;
- VMLAUNCH/VMRESUME;
- VM-exit assembly stub;
- exit dispatcher;
- EPT;
- VPID;
- INVEPT/INVVPID;
- interrupt-window handling;
- teardown VMX.

A ausência é intencional e declarada.

## Prioridades para implementar VMX

Uma ordem razoável é:

1. decidir arquitetura privilegiada: VMX direto versus API como KVM;
2. capability discovery e diagnostics;
3. per-host-CPU VMXON ownership;
4. VMCS management;
5. adjustment de controls;
6. host-state/exit trampoline mínimo;
7. importar/exportar subset mínimo de ChrisArchitectureState;
8. lançar guest mínimo;
9. implementar CPUID, HLT e port-I/O exits;
10. conectar serial/shutdown do ChrisVM;
11. adicionar EPT para RAM;
12. MMIO trapping;
13. interrupt injection;
14. cleanup completo;
15. differential tests ChrisCPU/ChrisHV;
16. só então ampliar features e otimizações.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, Intel VMX é alvo arquitetural do ChrisHV, não backend implementado. O ChrisVM já possui seams úteis — ChrisCpuBackend, ChrisArchitectureState e ownership de I/O/MMIO na machine — mas toda camada privilegiada VMX está ausente. Como o binário atual é um executável host comum, o projeto precisa primeiro decidir como obter ownership privilegiado de VMX antes que VMXON, VMCS, VM entry/exit, EPT ou guest execution em hardware possam existir.
