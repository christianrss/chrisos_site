---
id: toolchain-history
lang: pt-br
type: technical-chapter
volume: 16-history
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisc/chrisc.c
  - compiler/clvm/clvm_format.c
  - compiler/clvm/clvm_vm.c
  - compiler/jit/jit.c
  - compiler/jit/jit_compile.c
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chriso.c
  - compiler/lang_pipeline.c
  - kernel/tools/native_link.c
  - kernel/tools/chrismake.c
  - kernel/tools/chrisbuild.c
  - kernel/tools/editor_window.c
symbols:
  - chrisc_compile
  - clvm_parse
  - clvm_step
  - jit_compile
  - kcc_compile
  - chrisasm_assemble
  - chrisld_link_objects
depends_on:
  - architecture-history
related:
  - compiler-pipeline
  - chrisc-clvm
  - clvm-spec
  - jit
  - native-toolchain
  - kcc
  - chrisasm
  - chrisld
  - self-hosting-bootstrap
  - stage-compilers
---

# História do toolchain nativo

## Escopo

O ChrisOS não recebeu um único toolchain monolítico de uma vez.

A stack atual resulta de várias linhas de desenvolvimento que começaram resolvendo problemas diferentes:

- compilação de ChrisC para applications;
- execução de bytecode CLVM;
- JIT de workloads CLVM;
- ChrisAsm e ChrisLd para objetos nativos e ELF;
- KCC para um path restrito C -> native;
- build/edit/run dentro do próprio sistema;
- gates progressivamente mais fortes para claims de self-hosting.

Este capítulo reconstrói essas linhas a partir do Git e as reconcilia com a revisão atual `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

## "Self-hosted" precisa de definição histórica

A expressão "self-hosted" pode descrever níveis diferentes.

Para o ChrisOS é preciso distinguir pelo menos:

1. **editor-integrated compilation** — source compila dentro do ambiente do OS;
2. **native tool availability** — assembler/linker/compiler próprios existem no codebase;
3. **host-tested compiler subset** — o compiler do projeto compila translation units selecionadas do próprio ChrisOS;
4. **bootstrap stage** — tools do projeto geram binaries nativos úteis a partir dos próprios formats;
5. **full self-hosted kernel build** — o kernel de produção completo é reconstruído e bootado usando apenas o toolchain próprio.

O Git mostra progresso incremental pelos quatro primeiros níveis.

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, o quinto ainda não deve ser reivindicado.

## 18 de setembro de 2026 — ChrisC e CLVM formam pipeline de application

O primeiro marco forte é:

    3042fcf2951b6681e8d58f662ac667f460229293

Mensagem:

    feat: PASSO 05 — Editor: Save, Compile e Run

O commit adicionou:

- `compiler/chrisc/chrisc.c`;
- assembler/format da CLVM;
- interpreter CLVM;
- central language pipeline;
- integração com o editor.

O significado vai além de adicionar parser.

Passou a existir um loop end-to-end:

    editar ChrisC
        |
        v
      compilar
        |
        v
      image CLVM
        |
        v
     interpreter
        |
        v
    application window

Essa foi uma forma inicial forte de "desenvolvimento dentro do ChrisOS".

## ChrisC começou como path orientado a VM

O ChrisC inicial não tentava produzir o kernel de produção.

Seu target era CLVM.

Isso reduziu complexidade inicial:

- bytecode controlado;
- VM state explícito;
- syscalls gerenciadas;
- memory guest bounded;
- faults definidos;
- scheduling/yield controlável.

Assim applications puderam compilar e rodar antes de o projeto resolver completamente ABI nativo, relocations e final linking.

## CLVM tornou o editor loop prático

CLVM forneceu um target estável para o compiler.

Em vez de gerar native code imediatamente, ChrisC podia emitir bytecode próprio.

Isso trouxe:

- validação simples de instructions;
- faults explícitos;
- host testing;
- linear memory;
- scheduler boundary;
- syscall interface consistente.

O atual `clvm-spec` formaliza o contrato que começou como execution target prático.

## 19 de setembro — JIT vira segundo backend CLVM

Commit:

    431dfce847e414c2b0696c785e5a16db616839ccc

introduziu:

- `jit.c`;
- `jit_compile.c`;
- `jit_emit.c`;
- headers e integração.

O architecture model passou a ser:

    CLVM bytecode
       /      \
      v        v
 interpreter   JIT
               |
               v
            x86-64

Historicamente, JIT não substituiu CLVM.

CLVM continuou sendo semantic contract; JIT virou acceleration backend.

## Interpreter-first semantics

Essa ordem moldou o sistema atual.

O interpreter continua sendo referência clara para:

- stack effects;
- memory semantics;
- fault behavior;
- syscalls;
- control flow.

O JIT precisa preservar essas semantics ao traduzir para executable x86-64.

Isso é mais seguro que permitir que JIT vire uma runtime independente.

## 19 de setembro — aparece o bootstrap toolchain nativo

Outra linha surge em:

    7bfd60fbeb32e7ccac843c7f640012641c4754fc

Mensagem:

    feat: fase16/23, build layout, and repo hygiene

O commit introduziu:

- KCC;
- ChrisAsm;
- ChrisLd;
- ChrisO;
- test drivers;
- ChrisBuild;
- integração com shell.

Nesse ponto ChrisOS deixa de depender apenas de ChrisC -> CLVM e passa a ter uma lineage distinta de native toolchain.

Pipeline conceitual:

    restricted C
       |
       v
      KCC
       |
       v
   ChrisAsm
       |
       v
    ChrisO
       |
       v
    ChrisLd
       |
       v
     ELF64

## ChrisO altera a arquitetura

ChrisO separou assembler e linker por meio de um object format próprio.

Isso desacoplou:

- source-language concerns;
- instruction encoding;
- symbol/relocation representation;
- final ELF layout.

Sem object boundary, todos esses papéis tenderiam a ficar misturados.

ChrisO tornou possível a evolução posterior para multi-object linking.

## KCC inicial era propositalmente pequeno

O primeiro KCC não deve ser lido com as capabilities atuais.

Ele começou como compiler restrito.

Isso era intencional: seria melhor crescer um subset verificável contra real kernel source do que fingir suporte amplo a C.

Essa filosofia aparece claramente depois, quando o compiler passa a falhar de forma fechada em source não suportado.

## 20 de setembro — ChrisC, CLVM e JIT expandem fortemente

Commit:

    16ac03ecb3ae5625d0729ce78e88795f2208af33

foi uma grande expansão de language/toolchain.

ChrisC cresceu milhares de linhas, CLVM ficou mais rica, JIT foi ampliado, IL e GC apareceram e `kernel/tools/native_link.c` foi adicionado.

Nesse ponto as duas linhas começaram a se aproximar:

- VM execution;
- JIT;
- native linking;
- richer compiler semantics;
- linking dentro do OS.

## Native linking dentro do sistema

`native_link.c` é historicamente relevante porque linking final deixa de ser apenas operação host-side.

ChrisOS passa a possuir lógica para consumir objects próprios e produzir ELF executável dentro do sistema.

Isso é mais forte que simplesmente armazenar source de compiler no repository.

## ChrisMake adiciona orchestration

Mais tarde no mesmo dia:

    dea12e87f0392e7d3402d0aa3213ea51de29b334

introduziu ChrisMake.

O sistema passou de compile/run isolado para build orchestration.

Ambiente self-hosted precisa de mais que compiler stages:

- build order;
- recipes;
- file naming;
- repeated build;
- diagnostics.

ChrisMake foi uma primeira camada para isso.

## Applications pressionam o compiler

Entre 20 e 24 de setembro, ChrisC e `lang_pipeline` mudaram repetidamente enquanto Doom, ChrisEditor, games e apps maiores eram integrados.

Isso mostra de onde vieram muitas features.

Elas não surgiram apenas para passar unit tests artificiais.

Vieram de source real.

Por outro lado, application-driven compiler growth também pode acumular fixes específicos.

Por isso os gates e rejection semantics posteriores foram importantes.

## 24 de setembro — relocations ficam mais maduras

Commit:

    aa5186ac5281bebb15e26fb53a3757507b7276b7

corrigiu call relocations entre objects.

O commit registra que ChrisAsm representava call como:

    undefined symbol + R_X86_64_PLT32

e ChrisLd ganhou:

- aplicação de relocations;
- missing-global rejection;
- duplicate-global rejection;
- ELF validation;
- rejection de unknown mnemonics.

Isso foi uma evolução importante.

O linker começou a atuar como verdadeiro symbol-resolution component.

## Por que call relocations importam

Single-file compiler pode esconder muitos problemas.

Calls cross-object obrigam o toolchain a definir:

- binding;
- undefined reference;
- relocation type;
- addend;
- place address;
- duplicate symbol policy.

Para PC-relative relocation:

[
value = S + A - P
]

onde:

- (S) é symbol address;
- (A) é addend;
- (P) é patch place.

Isso é pré-requisito para escalar compilação nativa real.

## 24 de setembro — KCC passa a fail closed

Um dos marcos de qualidade mais importantes foi:

    89812c7888667dedb22081099dae2a22fac7c5b7

Mensagem:

    kcc: reject source outside the level-0 subset

Antes, source pulado/unsupported podia parecer compile success.

Depois, KCC passou a:

- reportar file/line/column;
- definir level-0 subset explícito;
- rejeitar constructs não suportados;
- falhar o kernel gate diante de source real não compilável.

Isso mudou o significado de "KCC passou".

## Fail-closed é correctness

Em self-hosting, rejection costuma ser melhor que miscompilation.

Um compiler que diz:

    unsupported

é limitado.

Um compiler que gera machine code errado silenciosamente pode corromper o kernel.

A evolução do KCC para fail-closed foi, portanto, marco de confiabilidade.

## 25 de setembro — grande expansão self-hosted

Commit:

    6087c38ce115ccd25b32f94a5488f7a9ac230902

expandiu fortemente KCC e ChrisAsm.

KCC cresceu milhares de linhas.

ChrisAsm ganhou encoding muito mais amplo.

ChrisLd e tests também avançaram.

É a transição de demo compiler para ferramenta que pode ser avaliada contra translation units reais do kernel.

## Kernel source vira benchmark

Depois desse ponto, progresso do KCC é melhor medido por quais files reais de `kernel/metal` compilam.

Isso é melhor que contar syntax features.

Uma capability importa quando leva uma production translation unit ao fim corretamente.

Os commits seguintes medem progresso dessa forma.

## KCC compila kernel log ring

Commit:

    a3a3340f5b4dfb1e1f899d40ffc930ee57838abd

adicionou suporte necessário a uninitialized BSS arrays e compilou `klog.c`.

O host gate linked serial e klog com stubs.

Historicamente, isso significa que KCC passou a compilar infraestrutura stateful real do kernel, não apenas expressões isoladas.

## Volatile MMIO é preservado

Commit:

    f0e59c3e0421583b653cbfa676a20e4b1de8fdef

adicionou uma propriedade essencial de systems programming:

- ordinary repeated stores podem ser folded;
- `volatile uint32_t` loads/stores precisam permanecer;
- ChrisAsm passa a aceitar os dword forms produzidos.

Em kernel code, `volatile` pode representar device access externamente observável.

Remover essas operações seria bug de hardware semantics.

Foi passo real de "C-like" para "systems C subset".

## Mais C para kernel

Commit:

    2611508a614b0507632ba776b9a017008b33b46b

adicionou suporte a:

- void pointers;
- `size_t`;
- named/packed structs;
- function pointers;
- seventh stack argument;
- unary minus;
- conditional operator.

Com isso, `string.c`, `pit.c`, `meminfo.c` e outros files entraram no gate.

O commit registra seis metal translation units compilando.

## Quatorze metal files compilam

Commit:

    30b24058dc800dbeb234f96e3e0a1661377104da

expandiu ChrisAsm e KCC.

KCC passou a aceitar:

- `break`;
- `continue`;
- unary not;
- `sizeof`;
- `_Static_assert`;
- subset fechado de inline asm.

ChrisAsm ganhou instructions e patch de same-section `.L` labels.

O gate passou a cobrir quatorze metal files.

## Inline asm como subset fechado

KCC não tentou aceitar GCC inline asm arbitrário.

O subset suportado foi fechado em torno de operações como:

- `cli`;
- `sti`;
- `hlt`;
- `pause`;
- compiler barrier;
- port I/O.

Privileged asm não reconhecido e `__sync` eram rejeitados.

Essa escolha privilegia auditability em vez de generalidade.

## Local labels deixam de pressionar ChrisO

ChrisAsm passou a patchar branches `.L` dentro da mesma section.

Assim compiler-generated local labels não precisavam consumir entries na ChrisO symbol table.

Isso mostra amadurecimento da fronteira assembler/object format.

Nem todo label interno precisa ser link-visible symbol.

## 25 de setembro — KCC compila todo kernel/metal C

O maior milestone atual é:

    aa591ccd3b414c2b0696c785e5a16db616839ccc

Mensagem:

    feat: compile the metal kernel with KCC (#14)

A mudança adicionou preprocessing e low-level support suficiente para host-compile todos os C files de `kernel/metal`.

O commit registra suporte a:

- `#if`, `#elif`, `defined`;
- function-like macros;
- token paste;
- line continuation;
- Limine includes;
- CR2/CR3;
- `invlpg`;
- `lidt`, `lgdt`;
- `lretq`, `iretq`;
- `str`;
- lock `cmpxchg`/`xadd`;
- fixed low-level context-switch sequences.

É um marco substancial.

## O que esse milestone não prova

O mesmo commit registra limites explícitos:

- dezenas de translation units fora de `kernel/metal` ainda falhavam;
- IDT stubs continuavam em NASM;
- ChrisLd ainda não produzia a Limine image completa;
- float loads/stores não estavam completos no KCC;
- constructs fora do closed subset permaneciam não suportados.

A frase correta é:

> KCC host-compila todo o C de `kernel/metal` daquela revisão.

Não:

> ChrisOS reconstrói seu kernel completo usando KCC.

## Duas famílias de compiler coexistem

Nesse estágio o ChrisOS possui dois source-language paths principais.

### ChrisC

    ChrisC
      |
      v
    CLVM
      |
      +--> interpreter
      |
      +--> JIT

Esse path é application-oriented e ligado ao runtime/syscall model.

### KCC

    restricted C
       |
       v
      KCC
       |
       v
   ChrisAsm
       |
       v
    ChrisO
       |
       v
    ChrisLd
       |
       v
     ELF64

Esse path mira native execution e bootstrap.

São problemas relacionados, mas diferentes.

## ChrisC não é "KCC antigo"

ChrisC não é simplesmente o nome anterior do KCC.

Seus contracts diferem.

ChrisC está ligado a:

- CLVM;
- runtime syscalls;
- guest memory;
- JIT;
- application lifecycle.

KCC está ligado a:

- native x86-64;
- ChrisAsm encoding;
- ChrisO relocations;
- ChrisLd ELF;
- systems C para kernel.

A história precisa preservar essa distinção.

## lang_pipeline vira orchestration layer

`compiler/lang_pipeline.c` mudou em muitos commits.

Seu papel cresceu para integrar:

- compile;
- packaging;
- VM creation;
- JIT selection;
- lifecycle;
- debugger;
- close/restart;
- runtime state.

Assim o toolchain deixou de ser apenas coleção de host utilities e virou subsystem do OS.

## ChrisEditor fecha outro loop

Em 25 de setembro, commits passaram a adicionar debugging de self-hosted programs no ChrisEditor.

O loop se torna:

    edit
      -> compile
      -> run
      -> debug
      -> edit

Isso não equivale a full compiler bootstrap, mas aumenta a autonomia do ambiente de desenvolvimento.

## Testes evoluíram junto

Os gates passaram de "gera output" para checks específicos:

- instruction encoding;
- relocations;
- KCC subset;
- real kernel translation units;
- negative tests;
- native linking;
- CLVM fuzzing;
- JIT differential execution;
- JIT performance gate.

A definição de "supported" se tornou progressivamente mais forte.

## Arquitetura atual

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, o toolchain possui camadas conectadas.

### Application language path

    ChrisC source
        |
        v
      compiler
        |
        v
       CLVM
       /  \
      v    v
 interpreter JIT
      |      |
      +-- runtime/syscalls --+

### Native bootstrap path

    restricted C
        |
        v
       KCC
        |
        v
     ChrisAsm
        |
        v
      ChrisO
        |
        v
      ChrisLd
        |
        v
       ELF64

### In-system orchestration

    editor / shell / ChrisMake / ChrisBuild
              |
              v
      compile-link-run workflows

A história é a conexão gradual dessas layers.

## Milestones históricos

| Data | Commit | Significado |
|---|---|---|
| 2026-09-18 | `3042fcf` | ChrisC + CLVM + editor compile/run |
| 2026-09-19 | `431dfce` | JIT vira segundo backend CLVM |
| 2026-09-19 | `7bfd60f` | KCC, ChrisAsm, ChrisLd e ChrisO |
| 2026-09-20 | `16ac03e` | expansão language/JIT e native linking |
| 2026-09-20 | `dea12e8` | ChrisMake adiciona orchestration |
| 2026-09-24 | `89812c7` | KCC rejeita source fora do level-0 |
| 2026-09-24 | `aa5186a` | cross-object call relocations |
| 2026-09-25 | `6087c38` | grande expansão self-hosted |
| 2026-09-25 | `a3a3340` | kernel log infrastructure compila |
| 2026-09-25 | `f0e59c3` | volatile MMIO preservado |
| 2026-09-25 | `2611508` | seis metal units compilam |
| 2026-09-25 | `30b2405` | quatorze metal files e closed asm subset |
| 2026-09-25 | `aa591cc` | todo `kernel/metal` C host-compila com KCC |

## Lições arquiteturais

### VM target acelera language development

CLVM tornou ChrisC útil antes de ABI/linking nativo estar maduro.

### Bootstrap nativo precisa de object boundary

ChrisO separou assembler output de final linking.

### Real source é benchmark melhor que lista de features

Compilar real kernel translation units fornece evidência mais forte que dizer quantas constructs o compiler aceita.

### Fail closed

A policy level-0 do KCC melhorou a confiabilidade de todos os claims posteriores.

### Self-hosting é staged

Editor/compiler interno, native linker, kernel-subset compiler e complete bootstrapped kernel são milestones distintos.

## Claims históricos superados

Snapshots antigos podem afirmar ou sugerir:

- ChrisC é o único language path;
- CLVM é interpreter-only;
- KCC pula source unsupported;
- ChrisAsm não suporta cross-object calls;
- ChrisLd só lida com objetos triviais;
- KCC só compila fixtures;
- kernel completo já é self-hosted.

As seis primeiras afirmações foram superadas.

A última continua sendo overclaim na revisão atual.

## Limite atual

O gate KCC mais forte diz que todo `kernel/metal` C é host-compiled.

Ao mesmo tempo, full kernel build continua incompleto.

O milestone final exigiria evidência para:

    project compiler
      -> todos kernel objects
      -> assembly/stubs
      -> final boot image
      -> successful boot
      -> validation gates

Qualquer coisa abaixo disso é partial self-hosting.

## Nota de revisão

Este capítulo foi reconciliado contra a revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56` e os milestones Git listados.

Entradas futuras devem ser adicionadas quando o toolchain cruzar uma boundary real: compiler semantics mais amplas, novo ABI/object compatibility, bootstrap-stage completion, full kernel link ou verified self-hosted boot.
