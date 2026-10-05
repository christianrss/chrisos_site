---
id: validation-evidence
lang: pt-br
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - makefile
  - scripts/qemu.mk
  - tools/qemu_gate.py
  - tools/check_test_gates.py
  - chrisvm/tests/test_chrisvm.c
  - tools/test_elf_malformed.c
  - tools/test_fuzz_elf.c
symbols: []
depends_on:
  - kernel-model
related:
  - host-tests
  - qemu-gates
  - hardware-gates
  - fault-injection
  - fuzzing
  - performance-measurement
  - self-hosting-bootstrap
  - installation-real-hardware
---

# Validação, classes de evidência e confiabilidade

## Propósito

ChrisOS trata validação como um conjunto de classes de evidência, não como um único rótulo booleano chamado "working".

Source code prova que uma implementação existe. Build bem-sucedido prova que um path selecionado compilou e linkou. Host test prova comportamento em um processo host. QEMU gate prova integração guest sob virtual machine configuration declarada. ChrisVM tests provam comportamento no emulator controlado pelo próprio projeto. Hardware físico prova apenas o profile físico identificado.

Essas afirmações não são equivalentes.

O objetivo é impedir que claims de implementação fiquem mais fortes que a evidência que realmente os produziu.

## Registro de evidência

Um resultado útil precisa de seis elementos:

| Elemento | Significado |
|---|---|
| Revisão | commit exato do ChrisOS |
| Comando | gate, test ou build executado |
| Ambiente | host, machine e device configuration |
| Oracle | regra exata de pass/fail |
| Artifact | log, markers, image, counter ou state comparison |
| Limitações | condições e propriedades não estabelecidas |

"Passou na minha máquina" omite quase todo esse conjunto.

Um claim reproduzível permite reconstruir workload e regra de decisão.

## Identidade da revisão

Gate result pertence à source revision que executou.

Se R1 passa e o repository move para R2, o resultado antigo vira historical evidence. Não prova automaticamente R2.

Por isso authored documentation registra `reviewed_revision` e serious test reports devem identificar commit.

Isso impede um label como "QEMU-tested" de sobreviver indefinidamente após mudanças relevantes de source.

## Evidência é específica à propriedade

Um comando pode estabelecer várias propriedades, mas não estabelece todas as propriedades do subsystem.

Por exemplo, markers:

    root ata
    cfs mounted

mostram que o boot testado escolheu ATA como root e montou ChrisFS.

Não provam todo ATA command, todo filesystem path, todo interleaving de concorrência ou todo physical controller.

Evidência deve ser interpretada na mesma granularidade do oracle.

## Camada 0: build

A primeira camada executável é compilation/linking.

Build evidence detecta:

- declarations ausentes;
- type errors;
- undefined symbols;
- warnings promovidos a errors;
- object-format incompatibility;
- linker-script failures;
- image-construction failures.

Build bem-sucedido não prova boot nem runtime behavior.

Prova apenas que o artifact graph selecionado pôde ser construído com aquele toolchain.

## Camada 1: host tests

Host tests executam lógica ChrisOS como programas host normais.

São valiosos porque costumam ser:

- rápidos;
- determinísticos;
- isoláveis;
- repetíveis;
- fáceis de inspecionar;
- compatíveis com sanitizers.

O root `host-gates` agrega tests de filesystem, JIT, native toolchain, graphics, queues, memory-management protocols, synchronization, ELF, sockets, fuzzers e editor/debugger.

Isso fornece ampla cobertura algorítmica sem bootar o kernel para cada assertion.

## Limite de fidelidade host

Host test usa ABI, virtual memory e scheduler do host.

Não reproduz automaticamente:

- guest page tables;
- real kernel privilege transitions;
- interrupt entry;
- DMA;
- firmware;
- PCI enumeration;
- QEMU device behavior;
- physical timing.

Parser ou allocator pode ser muito bem testado em host e ainda precisar de guest integration.

O claim correto é "host-tested", não "hardware-tested".

## Auditoria de reachability

ChrisOS possui `tools/check_test_gates.py`.

O script analisa dependency graph do makefile a partir de `host-gates` e reporta targets com aparência de test que não são reachable pelo aggregate.

Isso protege contra uma falsa sensação de cobertura:

> um test pode existir no source e nunca executar quando o aggregate oficial é chamado.

A auditoria prova reachability, não a qualidade do test.

## Host gates agregados

A dependency list atual de `host-gates` cobre famílias como:

- ChrisFS e fsck;
- indirect/journal/chmod/max-write;
- JIT encoding, VM, native e benchmark;
- ChrisO, ChrisAsm, ChrisLd e KCC;
- graphics e shaders;
- VirtIO queues/resources;
- PMM/heap SMP;
- kthread/job saturation;
- TLB protocol;
- build metadata;
- CLVM synchronization;
- malformed ELF;
- ownership/write paths;
- deterministic fuzzers;
- editor/debugger model.

A lista exata é revision-bound.

A propriedade importante é o aggregate explícito e auditável.

## Camada 2: sanitizers

`host-sanitize` compila targets selecionados com AddressSanitizer e UndefinedBehaviorSanitizer.

A cobertura atual inclui paths selecionados de PMM/heap SMP, kthread, job saturation e key state.

Sanitizers melhoram a detecção de classes como:

- invalid host memory access;
- alguns lifetime errors;
- buffer misuse;
- undefined C behavior detectável.

Não provam ausência de todos os memory bugs.

Também não instrumentam todos os host gates.

O resultado deve permanecer restrito aos targets instrumentados.

## Aggregate stability

O target `stability` depende de:

    host-gates
    host-sanitize

Quando `qemu-system-x86_64` existe, também executa:

    qemu-stress

Se QEMU está ausente, o makefile informa que apenas host gates foram executados.

Logo "stability passed" é incompleto sem dizer se a parte QEMU ocorreu.

## Stress evidence

Stress repete state transitions e pressiona resources.

A família host-stress inclui exemplos ligados a:

- PMM/heap SMP;
- kthreads;
- job saturation;
- TLB protocol;
- logging;
- PMM cycles;
- filesystem locking;
- fuzz workloads;
- task/window behavior.

Passar muitas iterations aumenta confiança nas transitions exercitadas.

Não é prova matemática de race freedom em todo scheduling possível.

## Camada 3: QEMU integration

O base x86 dos gates usa configuração declarada com:

    pc machine
    2048 MiB RAM
    SMP configurável
    qemu64 CPU
    TCG
    display headless
    serial log

TCG é usado no path headless portável.

KVM não é requisito para a principal suite QEMU.

Isso torna o ambiente mais reproduzível em hosts que não expõem hardware virtualization.

## Oracle do QEMU

`tools/qemu_gate.py` define o oracle por serial markers.

QEMU pode terminar normalmente ou ficar ativo até timeout.

Código 124 é aceito apenas se:

- todos expected markers existem;
- nenhum fatal marker existe;
- QEMU não encerrou com outro error code.

Fatal markers atuais incluem categorias como:

- kernel panic;
- explicit exception vector;
- double fault;
- general protection;
- heap corruption;
- PMM corruption.

Assim "QEMU continuou aberto" não vira pass por acidente.

## Expected markers

Marker deve corresponder ao invariant ou milestone testado.

ATA gate, por exemplo, exige:

- CPU-online count configurado;
- ATA como root;
- ChrisFS mounted.

NVMe gate exige discovery de NVMe e read/write marker.

Marker emitido cedo demais produz oracle fraco.

O gate deve emitir sucesso depois da operação que pretende provar.

## Matriz de QEMU

O aggregate `qemu-gates` atual inclui paths para:

- ATA;
- AHCI;
- NVMe;
- VirtIO block;
- USB mass storage;
- VirtIO GPU;
- RISC-V;
- no-ATA fallback;
- installer;
- safe mode;
- xHCI HID.

A variante de uma CPU entra em `full-gates`, não em base `qemu-gates`.

VirGL é separado e condicional porque depende de graphics capability do host.

Reports devem preservar essas diferenças.

## Topologia negativa

No-ATA gate é exemplo de topology testing negativa.

Espera ATA ausente, AHCI selecionado como root, ChrisFS montado e boot continuando.

Isso estabelece fallback quando uma device class não existe.

Não é equivalente a provocar I/O failure depois de device initialization.

Topology variation e mid-flight fault injection provam propriedades diferentes.

## Installer gate

Installer gate cruza várias layers:

1. prepara source/target images;
2. boota automatic installer;
3. exige progress markers;
4. valida estruturalmente o disk image produzido;
5. boota a instalação sob OVMF/UEFI;
6. exige filesystem e desktop milestones.

Isso é mais forte que provar existência de installer code.

Ainda não prova instalação em firmware/controller físico arbitrário.

## VirGL e skip

VirGL gate primeiro verifica host capability.

Se QEMU/display stack não consegue fornecer VirtIO GPU com GL, o test informa skip.

Skip é:

- não pass;
- não guest failure.

Significa que o environment não conseguiu criar o test.

Esse terceiro estado deve permanecer explícito para evitar feature claim falso.

## Camada 4: ChrisVM

`make chrisvm-test` executa a suite do emulator do próprio projeto.

A suite atual possui tests para:

- arithmetic flags;
- ADD interpretado;
- memory e CALL/RET;
- serial/port I/O;
- faults;
- CPUID/MSR;
- multiply/divide;
- ELF acceptance/rejection;
- decoder fuzz;
- MMIO callbacks;
- STOS/framebuffer splash.

Isso é evidência sobre ChrisCPU/ChrisVM semantics.

Não prova equivalência com x86 físico.

## Evidência diferencial

Para emulator, uma técnica futura forte é differential execution.

Partindo de state equivalente, execute workload bounded em ChrisCPU e reference environment, depois compare:

- registers;
- flags;
- memory;
- exception vector;
- exit reason;
- device-visible effects.

Agreement com reference independente é mais forte que tests baseados apenas nas próprias expectations do projeto.

Timing pode precisar de normalization.

## Camada 5: hardware físico

Physical hardware introduz variabilidade que QEMU regulariza:

- firmware;
- chipset;
- storage revisions;
- DMA;
- interrupt routing;
- device timing;
- boot media;
- GPU/display.

Hardware result deve identificar profile.

No mínimo: machine, CPU, firmware, devices relevantes, boot medium e revision.

O repository não possui generic automated physical-hardware gate equivalente a `qemu-gates`.

Manual hardware evidence não deve ser descrita como CI reproduzível continuamente.

## Fault injection

Fault injection perturba um path válido.

Exemplos atuais incluem:

- ChrisFS block I/O failure;
- malformed executable data;
- allocation budget failure;
- deliberate process fault;
- missing-device topology.

A pergunta muda de:

> o path normal funciona?

para:

> quando dependency falha, ownership e consistency invariants sobrevivem?

Essa diferença é central em reliability work.

## Fuzzing

Os fuzzers atuais são deterministic pseudo-random ou structured adversarial tests, não continuous coverage-guided infrastructure.

Existem workloads para:

- ChrisFS operation sequences;
- ELF loading;
- ChrisC source;
- CLVM images;
- ChrisVM decoder.

Fixed seeds tornam failures reproduzíveis.

A limitação é exploração restrita sem ampliar corpus ou seeds.

Fuzzer fica muito mais forte quando possui semantic oracle, como no-leak, successful fsck ou bounded decoder result.

## Negative tests

Reliable suite inclui inputs cuja resposta correta é rejeição.

Exemplos:

- malformed ELF;
- invalid relocation;
- unsupported compiler source;
- corrupt metadata;
- invalid owner/handle;
- missing device;
- allocator exhaustion.

Expected rejection é pass.

A propriedade é rejeitar na boundary correta sem corromper state não relacionado.

## Testes orientados a invariants

Invariant deve permanecer verdadeiro em transitions permitidas.

Exemplos:

- allocators independentes não possuem a mesma physical frame;
- filesystem allocation state permanece consistente após error;
- failed ELF load não vaza pages;
- resource handle não cruza owner boundary;
- page fault retém faulting address em CR2;
- backend fallback preserva resource identity pública.

Testes de invariants fornecem evidência mais forte que apenas procurar success string final.

## Qualidade do oracle

Validation result é tão forte quanto seu oracle.

Oracle fraco:

    process exited 0

Oracles mais fortes incluem:

- exact state comparison;
- structural image validation;
- expected markers presentes;
- forbidden markers ausentes;
- ownership counters de volta ao baseline;
- round-trip encode/decode;
- filesystem consistency check.

O oracle deve ficar perto da propriedade declarada.

## False positives

False positive ocorre quando gate passa com propriedade quebrada.

Causas comuns:

- marker emitido antes de completar operação;
- test target existe mas não está no aggregate;
- timeout aceito sem progress markers;
- unsupported feature faz silent fallback;
- apenas um field de state é comparado;
- stale artifact satisfaz oracle.

Gate design deve defender explicitamente esses casos.

## False negatives

False negative ocorre quando target behavior está correto, mas test environment falha por motivo diferente.

Exemplos:

- QEMU host sem VirGL;
- QEMU ausente;
- KVM indisponível em interactive path;
- tool version altera diagnostics;
- graphics display stack ausente.

Environment, guest e infrastructure failures devem ser separados.

## Performance evidence

Benchmark não é correctness gate.

Precisa registrar:

- workload;
- build config;
- host;
- timing source;
- warmup;
- repetitions;
- statistic;
- revision.

Resultado mais rápido não compensa invariant quebrado.

Regression threshold só deve virar gate depois que measurement noise é conhecido.

## Matriz de evidência

| Classe | Estabelece | Não estabelece |
|---|---|---|
| build | source selecionado compila/linka | runtime correctness |
| host unit | lógica executada no host | guest/physical integration |
| sanitizer | paths instrumentados selecionados | ausência de todo memory bug |
| stress | transitions repetidas | todo interleaving possível |
| QEMU gate | guest path em virtual hardware declarado | hardware físico arbitrário |
| ChrisVM | emulator behavior | equivalência com physical x86 |
| fault injection | selected failure behavior | toda failure class |
| fuzzing | corpus adversarial/gerado | input space exaustivo |
| hardware | um physical profile | universal compatibility |
| benchmark | workload performance | correctness/portability |

## Promoção de claim

Capability claim deve ampliar somente quando evidence cruza a boundary necessária.

Progressão comum:

    source exists
      -> narrow host test
      -> aggregate host gate
      -> guest integration
      -> topology variants
      -> identified hardware
      -> broader compatibility matrix

Nem toda feature exige todos os estágios.

Depende do claim exato.

## Registro de failures

Failed run é evidência útil quando localizado.

Registre:

- source revision;
- command;
- environment;
- first meaningful error;
- last successful marker;
- log/artifact;
- clean-build reproducibility;
- classificação host/guest/infrastructure.

Descartar run vermelho perde informação diagnóstica.

## Reproducibility

Gate reproduzível minimiza hidden state.

Boas práticas:

- deterministic disk images;
- fixed fuzz seeds;
- explicit QEMU configuration;
- clean artifact boundaries;
- versioned source;
- machine-readable markers;
- bounded timeouts.

Não exige wall-clock igual em todo host.

Exige que o semantic pass/fail possa ser reconstruído.

## Reliability é cumulativa

Nenhum gate isolado prova que um OS é confiável.

Confiança aumenta quando classes independentes exercitam invariants sobrepostos:

    host tests
      + sanitizers
      + guest integration
      + fault injection
      + fuzzing
      + identified hardware

As classes são complementares porque seus blind spots são diferentes.

## Boundary atual

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, ChrisOS possui host gates amplos, sanitizer paths selecionados, QEMU gates estruturados, ChrisVM tests, fault injection e deterministic fuzzing.

Physical hardware validation continua menos automatizada e profile-specific.

Use frases precisas:

- host-tested;
- QEMU-gated;
- ChrisVM-tested;
- tested on identified hardware;
- unverified on physical hardware.

Evite "fully tested" sem qualification.

## Nota de revisão

Este capítulo foi reconciliado contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

Regra central: **todo validation claim deve nomear execution class, revision e oracle, e nunca pode afirmar mais que o ambiente realmente demonstrou.**
