---
id: ept-npt
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/machine.h
  - chrisvm/buses/mmio.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/hv/chrishv.c
  - chrisvm/cpu/hv/vmx/vmx.h
  - chrisvm/cpu/hv/svm/svm.h
symbols:
  - ChrisArchitectureState
  - chris_translate
  - chris_phys_read
  - chris_phys_write
  - chrishv_backend
depends_on:
  - vmx
  - svm
  - emulator-paging
  - chrisvm-memory-map
related:
  - chrisvm-mmio-bus
  - chrisvm-machine
  - determinism-replay
---

# EPT e NPT: tradução de segundo nível para o ChrisHV

## Escopo

Virtualização assistida por hardware cria um segundo problema de tradução de endereços que o interpretador ChrisCPU atual não precisa representar por page tables de hardware.

O guest normalmente traduz:

    guest virtual address
        ↓ guest page tables
    guest physical address

Um VMM hardware-assisted ainda precisa converter esse guest physical address para memória pertencente ao host:

    guest physical address
        ↓ EPT ou NPT
    host/system physical address

Intel chama esse mecanismo de Extended Page Tables, EPT.

AMD chama o mecanismo análogo de nested paging, normalmente abreviado NPT.

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisHV não implementa EPT nem NPT.

O caminho ChrisCPU atual realiza guest paging em software e depois encaminha o physical address resultante para ChrisMachine.

Este capítulo documenta o papel arquitetural de EPT/NPT, sua relação com o memory model já existente no ChrisVM e os requisitos para adicioná-los sem confundir guest faults com hypervisor faults.

## Caminho atual do ChrisCPU

ChrisCPU avalia guest paging explicitamente em:

    chris_translate

A função parte de:

    cpu->arch.cr3

e percorre as page tables x86-64 do guest.

Ela verifica:

- canonical addressing;
- Present;
- Writable;
- User;
- NX quando EFER.NXE está habilitado;
- large pages;
- Accessed;
- Dirty.

A saída é um guest physical address.

Depois, ChrisCPU chama:

    chris_phys_read
    chris_phys_write

para rotear esse endereço em RAM, framebuffer ou generic MMIO.

Portanto o ChrisVM atual já possui conceitualmente dois estágios:

    guest VA
        ↓ software guest walk
    ChrisVM guest PA
        ↓ software machine dispatcher
    host allocation/device callback

O segundo estágio existe em conceito, mas não como second-level paging em hardware.

## O que muda com ChrisHV

Com hardware-assisted execution, a CPU física executa o first-stage page walk do guest.

Se o guest puder usar seu próprio CR3 e controles de paging, o VMM precisa limitar o que os guest physical results podem alcançar.

EPT/NPT fornece essa restrição.

O caminho de hardware torna-se:

    guest instruction
        ↓
    guest linear address
        ↓ guest page-table walk pela CPU
    guest physical address
        ↓ EPT/NPT walk pela CPU
    host/system physical address

Isso permite execução direta mantendo isolamento da memória host.

## Por que GPA direto seria inseguro

Software guest controla suas próprias page tables.

Sem second-level translation, um guest bugado ou malicioso poderia tentar mapear physical addresses pertencentes a:

- host kernel;
- hypervisor;
- outra VM;
- device MMIO;
- VMX/SVM control structures;
- host stacks;
- page tables do VMM.

EPT/NPT transforma guest physical address em namespace intermediário, não raw host physical address.

Essa é a base do isolamento.

## Três address spaces

ChrisHV precisa manter três conceitos separados:

    GVA = guest virtual address
    GPA = guest physical address
    HPA/SPA = host/system physical address

O mesmo valor numérico pode aparecer em mais de um namespace e representar objetos diferentes.

Um bug comum de hypervisor é passar um namespace para uma API que espera outro.

Mesmo wrappers simples ajudam:

    typedef uint64_t GuestVirtualAddress;
    typedef uint64_t GuestPhysicalAddress;
    typedef uint64_t HostPhysicalAddress;

## Relação com a RAM do ChrisMachine

ChrisMachine hoje possui guest RAM como um host allocation:

    m->ram

Para ChrisCPU, o pointer basta porque software copia bytes diretamente.

Para EPT/NPT, a CPU precisa de host physical backing.

O hardware backend futuro precisa de uma camada capaz de:

- alocar/pinnar host pages;
- conhecer physical addresses;
- mapear guest physical pages para host pages;
- manter lifetime durante execução;
- desmontar mappings com segurança.

Um pointer user-space comum não é por si só um destino EPT/NPT.

## Visão geral de EPT

Intel EPT fornece um segundo hardware page-table walk.

O root é selecionado por um EPT pointer, EPTP, configurado no VMX.

A hierarquia lembra paging x86-64 estruturalmente, mas usa entry semantics próprias de EPT.

Uma tradução EPT controla se um guest physical access pode:

- ler;
- escrever;
- executar.

A leaf identifica o host physical backing e atributos necessários.

## Permissões EPT

EPT permissions são independentes das permissões das guest page tables.

Um acesso só passa quando ambos os níveis permitem.

Conceitualmente:

    guest permission
    AND
    EPT permission

Uma guest page pode ser Writable no guest e read-only no EPT.

Isso é útil para:

- copy-on-write;
- dirty tracking;
- watchpoints;
- proteção de metadata;
- MMIO trapping.

Second-level permission não pode conceder um acesso negado pelo guest paging.

## EPT execute

EPT possui execute permission separada de read/write.

Isso permite ao hypervisor impor policy de execução independente do NX do guest.

ChrisHV não deve usar EPT execute como substituto de guest NX semantics.

Guest #PF por NX pertence ao first-stage paging.

EPT execute restrictions pertencem à policy do hypervisor.

## Large pages em EPT

EPT pode mapear large pages quando suportado e alinhado.

Isso reduz profundidade de tradução e pressão de TLB.

Pode melhorar performance para grandes regiões contíguas de guest RAM.

Por outro lado reduz granularidade de proteção.

Dirty tracking, MMIO holes, copy-on-write ou proteção por página podem exigir split de mappings grandes.

Bring-up inicial deve priorizar correctness.

## EPT violation

Quando second-level translation não permite um acesso de forma que gere EPT violation, VMX retorna ao VMM.

O exit contém detalhes sobre a tentativa.

EPT violation é evento do hypervisor.

Não é automaticamente guest page fault.

O guest pode ter uma first-stage translation perfeitamente válida para um GPA que ChrisHV decidiu não mapear.

## EPT misconfiguration

Intel diferencia EPT misconfiguration de EPT violation.

Misconfiguration significa que a própria estrutura EPT contém combinação inválida ou reserved-state problem.

Isso indica bug/corrupção do VMM.

Não deve ser transformado em #PF guest.

Diagnostics devem mostrar GPA, EPTP e, quando possível, a cadeia de entries relevante.

## MMIO trapping com EPT

EPT pode ajudar a rotear MMIO.

Um desenho simples:

- mapear RAM em EPT;
- deixar GPAs de MMIO sem mapping ou sem permission;
- receber EPT violation;
- classificar GPA pelo physical map do ChrisMachine;
- chamar device model;
- emular acesso;
- retomar guest.

Isso estende os devices atuais para hardware execution.

Mas memory-instruction emulation exige conhecer:

- width;
- read/write;
- efeitos em registers;
- instruction length;
- atomicity/locking;
- partial-access behavior.

O MMIO genérico atual perde transaction width, portanto ChrisHV não deve copiar essa limitação sem necessidade.

## MMIO diretamente mapeado

Nem todo MMIO precisa ser trapped.

Hypervisor pode mapear diretamente regions seguros/passthrough.

Isso muda completamente o security model.

Os devices atuais do ChrisVM são software models.

O primeiro ChrisHV deveria preferir trapping em vez de passar hardware físico.

## Accessed/Dirty em EPT

Em CPUs compatíveis, EPT pode manter accessed/dirty state.

Esses bits ajudam em:

- migration;
- snapshots;
- dirty-page tracking;
- pesquisas de memória.

Capability detection é necessária antes de depender deles.

Primeiro backend pode operar sem advanced dirty tracking desde que use um modo EPT válido no host.

## INVEPT

Alterar EPT não garante que caches internos esqueçam imediatamente translations antigas.

Intel fornece INVEPT.

A sequência conceitual segura:

    modificar EPT
        ↓
    publicar ordering
        ↓
    INVEPT adequado
        ↓
    retomar guest

Pular invalidation pode manter permission ou backing antigos.

## Ownership de EPTP

Cada EPT context possui root/configuração em EPTP.

ChrisHV deve tratar EPTP como estado por VM/address-space, não constante global.

Cenários futuros podem precisar de múltiplos contexts:

- snapshots;
- copy-on-write;
- instrumentation views;
- research de nested virtualization.

Primeiro backend pode ter um EPT root por VM.

## Visão geral de NPT

AMD nested paging resolve o mesmo problema de second-stage translation.

O VMCB habilita nested paging e define um nested-page-table root, normalmente nCR3.

O processador executa:

    guest linear
        ↓ guest paging
    guest physical
        ↓ nested paging
    system physical

O guest mantém seu own CR3.

O VMM possui a nested hierarchy.

## Entry model do NPT

AMD NPT usa paging structures relacionadas à tradução AMD64.

Permissions e page sizes seguem a arquitetura AMD.

ChrisHV não deve tentar usar um binary table format único para EPT e NPT apenas porque ambos usam árvores multi-level.

A camada genérica deve abstrair intenção:

    map GPA range
    unmap GPA range
    set permission
    invalidate context

e cada backend codifica as entries corretas.

## Nested page fault

Quando nested translation falha, SVM gera nested-page-fault exit.

Isso não é guest #PF.

Backend precisa classificar corretamente:

    guest first-stage fault
    versus
    nested second-stage fault

Guest #PF normalmente permanece comportamento arquitetural guest.

Nested fault é evento do VMM.

## NPT e ASIDs

AMD ASIDs tagueiam translations e reduzem flushes.

Nested-paging state participa dessas regras.

Alterar nCR3 ou mappings exige invalidation correto.

Reutilizar ASID sem geração/flush pode expor stale translations de outro contexto.

ASID allocation e NPT mapping formam um mesmo subsistema.

## TLB invalidation em AMD

AMD oferece VMCB TLB control e operações como INVLPGA.

O backend deve manter a invariável:

    nenhum guest retoma com stale translation
    incompatível com a policy atual

Primeiro backend pode usar flush conservador.

Depois mede e otimiza.

## Abstração EPT/NPT

A camada genérica ChrisHV deve representar semântica, não entry format vendor-specific.

Uma API conceitual:

    slat_create(vm)
    slat_destroy(vm)

    slat_map(gpa, hpa, size, permissions)
    slat_unmap(gpa, size)
    slat_protect(gpa, size, permissions)

    slat_flush(context)

onde SLAT significa second-level address translation.

Implementações:

    vmx_ept_*
    svm_npt_*

Assim há uma única policy de memória com encodings separados.

## Region model

Second-level mappings devem derivar de um physical-region description autoritativo de ChrisMachine.

Hoje a policy é implícita:

1. RAM;
2. framebuffer;
3. generic MMIO.

Hardware backend precisa de um mapa mais rico contendo:

- GPA inicial;
- size;
- region type;
- RAM backing;
- permissions;
- trap/direct-map policy;
- device identity;
- dirty/snapshot policy.

Sem mapa único, software dispatcher e EPT/NPT podem divergir.

## Mapping de RAM

Guest RAM é o primeiro mapping mais simples.

Uma implementação mínima pode:

- alocar RAM fixa;
- pin backing pages;
- mapear GPA 0..ram_size;
- permitir R/W/X conforme o modelo inicial;
- não mapear o restante do GPA space.

Isso já impede guest de alcançar host physical memory arbitrária.

## Framebuffer

O framebuffer atual é allocation separado em GPA:

    0x02000000

ChrisHV pode:

1. mapear backing diretamente;
2. trapear acessos e usar device path.

Direct mapping é rápido e combina com framebuffer linear.

Mas dirty tracking muda.

No ChrisCPU:

    guest write
        ↓
    chris_phys_write
        ↓
    fb.dirty = 1

Com EPT/NPT direto:

    guest write
        ↓
    hardware grava direto no backing

Nenhuma função C roda.

Então fb.dirty não muda automaticamente.

## Dirty tracking do framebuffer

Possíveis soluções:

- write-protect inicial e trap no primeiro write;
- usar hardware dirty bits;
- marcar dirty conservadoramente após execution;
- redesenhar presentation state com page dirty tracking.

A escolha deve ser explícita para manter equivalência de comportamento.

## RAM e instrumentation

O mesmo vale para qualquer instrumentation presente em chris_phys_write.

Direct mapping desvia do software dispatcher.

Recursos como:

- write trace;
- watchpoints;
- dirty tracking;
- snapshot copy-on-write;
- access statistics;

precisam usar hardware permissions, A/D bits, exits ou instrumentation separada.

## Guest #PF versus second-level fault

A regra semântica mais importante é:

    first-stage fault pertence ao guest
    second-stage fault pertence ao hypervisor

Exemplo 1:

guest acessa VA sem mapping.

O próprio guest page walk falha.

Guest recebe #PF.

Exemplo 2:

guest page walk produz GPA 0x40000000, mas ChrisHV não possui mapping.

Isso gera EPT violation/NPT fault.

O VMM decide o significado desse GPA.

Não se transforma automaticamente no mesmo #PF.

## CR2

Guest #PF atualiza guest CR2.

Second-level fault não deve sobrescrever guest CR2 apenas porque envolveu um address.

ChrisHV deve alterar architectural guest state somente quando a virtual architecture exigir.

## Segurança

Second-level tables são o principal memory-isolation boundary.

ChrisHV deve garantir:

- guest RAM mapeia somente pages da própria VM;
- hypervisor pages nunca são mapeadas;
- VMCS/VMCB/EPT/NPT pages ficam inacessíveis;
- host stack/code continuam protegidos;
- device memory não vaza;
- stale mappings são invalidados antes de page reuse.

Use-after-free em SLAT pode virar disclosure/corruption entre guest e host.

## Lifecycle de mapping

Lifecycle robusto:

    alocar host page
        ↓
    atribuir à VM
        ↓
    criar SLAT mapping
        ↓
    executar guest
        ↓
    remover mapping
        ↓
    invalidar translations
        ↓
    garantir segurança de ownership
        ↓
    reutilizar/liberar page

Reusar antes da invalidation é inseguro.

## Concorrência

ChrisVM atual é single-vCPU.

SMP futuro cria concorrência sobre SLAT.

Mapping updates precisarão sincronizar:

- page-table allocation;
- entry updates;
- TLB shootdown/invalidation;
- vCPU run state;
- page ownership;
- teardown.

Locking precisa ser pensado antes do SMP.

## Huge pages e fragmentação

Large pages reduzem tradução, mas exigem backing contíguo/alinhado.

Features dinâmicas podem exigir split:

- MMIO holes;
- snapshots;
- copy-on-write;
- page protection;
- dirty logging.

Allocator não deve depender de huge pages para correctness.

Elas são otimização.

## Memory types

Second-level mappings carregam ou interagem com cacheability/memory type.

RAM, framebuffer e device MMIO não podem ser tratados da mesma forma.

Memory type incorreto pode causar:

- performance severamente ruim;
- ordering inesperado;
- comportamento incorreto de device.

Backend precisa de policy explícita region-type → hardware memory type.

## Determinismo e replay

Second-level translation influencia replay porque mapping faults e dirty state podem virar eventos observáveis do monitor.

Replay deve registrar ou reconstruir deterministicamente:

- versão do memory map;
- GPA ownership;
- protection changes;
- snapshot/COW transitions;
- external DMA/device updates.

Para mapping fixo, a tradução de RAM deve ser determinística.

## Snapshots

EPT/NPT pode sustentar snapshots eficientes.

Um desenho futuro:

1. tornar RAM read-only;
2. primeiro write gera second-level fault;
3. copiar original ou criar private page;
4. remapear writable;
5. invalidar;
6. retomar.

Isso implementa copy-on-write.

Só deve ser adicionado depois da semântica básica estar estável.

## Watchpoints

Second-level protection também pode implementar host watchpoints.

Uma page pode ser read-only para capturar writes.

A granularidade é por página.

Após violation, debugger pode examinar GPA/RIP e decidir se continua, emula ou para.

Isso amplia o debugger sem alterar guest DR0-DR7.

## Nested virtualization

Se o guest tentar rodar seu próprio hypervisor, EPT/NPT se tornam mais complexos.

Nested virtualization está fora do escopo atual.

Primeiro ChrisHV deve esconder virtualization features do guest CPUID ou rejeitá-las de forma consistente.

## Host APIs como KVM

Se ChrisHV usar KVM, kernel host gerencia EPT/NPT reais.

ChrisVM ainda precisa definir GPA map e memory slots.

Portanto a distinção GVA/GPA/HPA continua válida mesmo sem raw SLAT code no repo.

## Estratégia de validação

Uma progressão útil:

1. mapear uma RAM page;
2. provar que GPA não mapeado não alcança host;
3. testar read-only second-level;
4. testar execute protection quando disponível;
5. gerar/classificar EPT/NPT fault;
6. alterar mapping e validar invalidation;
7. mapear host pages não contíguas em GPA contíguo;
8. testar MMIO hole;
9. testar framebuffer policy;
10. teardown e page reuse;
11. comparar RAM com ChrisCPU.

## Teste diferencial

Um guest determinístico pode:

    escrever vários VAs
    ler de volta
    tocar boundary de large page
    tocar boundary framebuffer/MMIO
    HLT

Rodar em ChrisCPU e ChrisHV e comparar:

- RAM digest;
- registers;
- framebuffer;
- exit reason;
- guest exception state.

Isso testa integração first-stage + second-stage.

## Limitações atuais

Na revisão analisada não existem:

- EPTP;
- EPT entry definitions;
- INVEPT wrapper;
- EPT violation handler;
- NPT enablement;
- nCR3 ownership;
- nested-page-fault handler;
- ASID allocator para ChrisHV;
- SLAT mapping API;
- pinned host-physical RAM provider;
- hardware dirty tracking;
- cross-backend region descriptor.

O software physical dispatcher do ChrisCPU continua sendo o único backend de memória implementado.

## Prioridades de implementação

Uma ordem razoável:

1. tipos/ownership explícitos para GVA/GPA/HPA;
2. physical-region map autoritativo;
3. host-page allocation/pinning;
4. generic SLAT API;
5. EPT mínimo para RAM;
6. NPT mínimo para RAM;
7. fault classification e diagnostics;
8. invalidation;
9. MMIO trapping;
10. framebuffer dirty policy;
11. permission/watchpoint support;
12. dirty/access tracking;
13. large-page optimization;
14. snapshots/COW;
15. synchronization/shootdown quando SMP chegar.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, o ChrisVM já separa conceitualmente guest virtual translation de machine physical routing, mas ambos são implementados em software pelo ChrisCPU/ChrisMachine. ChrisHV ainda não possui EPT ou NPT. Hardware-assisted execution exigirá uma camada real de second-level translation que mapeie GPA para host/system physical pages pertencentes à VM, preserve MMIO/device semantics, diferencie guest page faults de hypervisor mapping faults e implemente invalidation, isolamento e dirty-state corretamente.
