---
id: native-toolchain
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/kcc/kcc.h
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.h
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/chrisld/chrisld.h
  - compiler/chrisld/chrisld.c
  - kernel/tools/native_link.h
  - kernel/tools/native_link.c
  - kernel/tools/chrisbuild.c
  - kernel/metal/linker.ld
  - tools/kcc_main.c
  - tools/test_kcc.c
  - tools/test_native_link.c
  - tools/seed_selfhost.c
symbols:
  - kcc_compile_source
  - kcc_compile_named
  - chrisasm_assemble
  - chriso_init
  - chriso_write
  - chriso_read
  - chriso_merge_text
  - chrisld_link
  - chrisld_link_objects
  - chrisld_validate
  - native_link_write_elf
  - chrisbuild_mk_kernel
depends_on:
  - compiler-pipeline
  - native-codegen
  - x86-instruction-encoding
  - elf-linking
related:
  - kcc
  - chrisasm
  - chriso
  - chrisld
  - self-hosting-bootstrap
  - linker-script
---

# Toolchain nativa: KCC, ChrisAsm, ChrisO e ChrisLd

## Escopo

A toolchain nativa do ChrisOS implementa um caminho experimental completo de um subset de C orientado ao kernel até bytes executáveis x86-64:

    source C
      -> KCC
      -> assembly textual x86-64
      -> ChrisAsm
      -> objeto ChrisO
      -> ChrisLd
      -> executável ELF64

O projeto também possui infraestrutura dentro do kernel capaz de invocar KCC e ChrisLd sobre arquivos armazenados no ChrisFS.

Isso ainda **não prova self-hosting completo do kernel de produção**. A implementação atual demonstra mecanismos reais de compiler, assembler, object format e linker, mas o builder interno ainda é mais estreito que o host build e não reproduz integralmente o contrato do production linker script.

![Pipeline da toolchain nativa](../../assets/diagrams/native-toolchain-pt-br.svg)

## Por que a toolchain existe

O build normal do ChrisOS ainda depende de C compiler e ferramentas de assembly/link do host para gerar o kernel de produção.

A linha native-toolchain tem dois objetivos:

- tornar compilation/linking explícitos para ensino e pesquisa de systems;
- reduzir progressivamente o conjunto de ferramentas externas necessário para reconstruir ChrisOS de dentro do próprio sistema.

Esses objetivos não são equivalentes. Um compiler pode ser tecnicamente relevante muito antes de conseguir reconstruir todas translation units e boot artifacts.

## Fronteira arquitetural

Há quatro contratos principais.

| Estágio | Entrada | Saída | Implementação atual |
| --- | --- | --- | --- |
| KCC | source C orientado ao kernel | assembly e depois ChrisO | `compiler/kcc/kcc.c` |
| ChrisAsm | subset textual x86-64 | ChrisO | `compiler/chrisasm/chrisasm.c` |
| ChrisO | sections, symbols, relocations | object image serializada | `compiler/chrisld/chriso.c` |
| ChrisLd | um ou mais ChrisO | ELF64 ET_EXEC | `compiler/chrisld/chrisld.c` |

KCC reutiliza ChrisAsm em vez de manter um machine-code emitter independente para toda instruction. Assim compiler-generated assembly e assembly manual suportado passam pelo mesmo encoder.

## Front end e estado do KCC

KCC não é wrapper do GCC. Ele possui preprocessing, parsing, semantic state e code generation próprios.

O estado global de capacidade fixa inclui:

    KCC_ASM_MAX     = 256 KiB
    KCC_PP_MAX      = 256 KiB
    KCC_SYM_MAX     = 2048
    KCC_MAC_MAX     = 256
    KCC_STRUCT_MAX  = 80
    KCC_FIELD_MAX   = 32
    KCC_TYPEDEF_MAX = 64
    KCC_ENUM_MAX    = 512
    KCC_PARAM_MAX   = 16

Representações centrais incluem `Type`, `Field`, `StructDef`, `Sym`, `Macro` e `Val`.

`Val` guarda também a categoria de lvalue, permitindo distinguir locals, globals, address lvalues e valores não atribuíveis durante lowering.

O compiler usa bastante mutable process-global state. Portanto não é reentrant e não deve ser tratado como seguro para compilations independentes concorrentes sem serialização externa.

## Preprocessor

KCC possui preprocessor limitado e próprio.

Mecanismos atuais incluem:

- object-like macros;
- function-like macros com até quatro parâmetros;
- token pasting `##`;
- conditional compilation;
- `defined(...)`;
- includes quoted/system;
- line markers para diagnostics;
- subset built-in de macros inteiras e de tamanho.

Recursive macro expansion é bounded.

Em freestanding, includes são lidos do filesystem ChrisOS.

No host, são usados host file reads.

Search path conhece diretórios do projeto, inclusive `kernel/metal`, `kernel/gfx`, `kernel/fs`, `compiler/chrisld`, `compiler/chrisasm` e headers do Limine.

## Perfil de tipos e linguagem

O modelo interno representa:

- void/bool/char;
- unsigned 8/16/32/64-bit integers;
- int;
- structs;
- pointers;
- arrays;
- function pointers;
- volatile;
- float como categoria reconhecida.

Reconhecer não significa implementar completamente.

Native floating-point operations continuam fora do subset aceito. Essa é uma das razões pelas quais compilar muitos arquivos low-level do kernel é um milestone diferente de compilar todo graphics stack.

## Estratégia de native code generation

KCC gera assembly textual em buffer bounded.

Depois chama `chrisasm_assemble`.

Essa arquitetura oferece ponto de inspeção: `kcc_last_asm()` retorna assembly gerado para tests/debugging.

A host suite usa isso para verificar propriedades semânticas:

- volatile loads/stores preservados;
- dead-store reduction em non-volatile;
- struct field offsets;
- control-flow targets;
- immediates;
- `sizeof`.

## Diagnostics

`KccDiag` registra:

- source file;
- line;
- column;
- severity;
- message.

`kcc_compile_named` mantém filename no diagnóstico; `kcc_compile_source` é entry point simples usado em caminhos dentro do kernel.

Failure retorna resultado não zero e pode ser consultado por `kcc_last_error()`.

## Papel do ChrisAsm

ChrisAsm traduz linguagem assembly bounded para ChrisO.

Entende as quatro sections:

    .text
    .rodata
    .data
    .bss

BSS size é separado de file-backed bytes. `.zero`/ `.skip` em BSS aumenta section size sem emitir bytes.

Também suporta directives como:

- `.extern`;
- `.local`;
- `.global`;
- `.byte`;
- `.quad`;
- `.ascii`;
- `.asciz`;
- `.zero` / `.skip`.

Label em text vira function symbol; em sections de dados vira object symbol.

Local labels e forced-local symbols usam local binding.

## Instruction encoding

ChrisAsm contém encoder x86-64 próprio, sem chamar NASM.

O subset cobre instruction families usadas por KCC e por paths low-level selecionados.

O host KCC gate verifica bytes concretos de operações como:

- `in` / `out`;
- `hlt`;
- `cli` / `sti`;
- `pause`;
- `lgdt`;
- `iretq`;
- `lock cmpxchg`.

Symbol references não resolvidas viram relocations ChrisO, em vez de receber endereço final prematuro.

## Modelo ChrisO

ChrisO v2 é o object contract intermediário.

Quatro sections:

    TEXT
    RODATA
    DATA
    BSS

`ChrisoImage` contém section pointers/sizes, symbol table e relocation table de capacidade fixa.

Limites:

    CHRISO_SYM_MAX = 256
    CHRISO_REL_MAX = 512

Symbol contém:

- name;
- section;
- offset;
- size;
- binding;
- kind.

Bindings: local, global, undefined.

Kinds: notype, function, object.

## Relocations

ChrisO representa:

    R_X86_64_NONE
    R_X86_64_64
    R_X86_64_PC32
    R_X86_64_PLT32
    R_X86_64_32
    R_X86_64_32S

Cada relocation v2 registra:

    section
    offset
    sym_index
    addend
    type

Estrutura on-disk v2 tem 20 bytes. Reader mantém compatibilidade com layout v1.

Esse object boundary preserva unresolved references entre units até final linking.

## Symbol resolution no ChrisLd

`chrisld_link_objects` linka múltiplas ChrisO images.

Antes do layout, duplicate global definitions são rejeitadas.

Undefined reference é resolvida procurando unique global defined symbol com mesmo nome entre os objetos.

Unresolved/ambiguous symbols causam link failure.

Local defined symbols são resolvidos no próprio objeto de origem.

## Section packing

Para cada section, ChrisLd coloca contribution de cada object na combined section.

Contributions posteriores são alinhadas a 16 bytes.

Layout lógico:

    RX: .text + .rodata
    RW: .data + .bss

BSS participa do memory size, não dos bytes do arquivo.

Isso evita gerar um único blob RWX.

## Política de program headers ELF

ChrisLd emite ELF64 `ET_EXEC`, machine `EM_X86_64`.

Sem writable sections pode existir um único load segment.

Com data/BSS, gera dois PT_LOAD:

- `PF_R | PF_X` para text/rodata;
- `PF_R | PF_W` para data/BSS.

`chrisld_validate` rejeita PT_LOAD simultaneamente writable e executable.

Também verifica:

- ELF magic/class/data;
- x86-64 machine ID;
- tamanho/quantidade de program headers;
- `filesz <= memsz`;
- load segments não sobrepostos;
- entry point dentro de executable segment.

## Seleção do entry point

ChrisLd procura primeiro symbol definido:

    kstart

Se não existir, procura:

    main

Se nenhum existir, o default inicial permanece o `load_addr` informado.

Para production kernel, `kstart` é a convention relevante.

## Aplicação de relocations

Para cada relocation, linker:

1. valida `sym_index`;
2. resolve referenced symbol;
3. calcula output file offset e runtime place address;
4. calcula runtime symbol address;
5. aplica a relocation.

PC-relative displacement deve caber em signed 32 bits.

Unsupported relocation type falha o link em vez de truncar silenciosamente.

## Native user linking

`kernel/tools/native_link.c` fornece caminho interno simples para produzir ELF de uma ChrisO image.

`native_link_write_elf` aloca output buffer, chama ChrisLd em `NATIVE_USER_LOAD`, grava no ChrisFS e libera buffer.

É distinto do kernel self-build path.

## Builder de kernel dentro do sistema

`chrisbuild_mk_kernel` lê:

    SYS/BUILD.MK

para `BuildManifest`.

Manifest mantém:

- output path;
- kernel load address;
- até 48 C source paths.

Para cada C source:

1. converte host-style path para ChrisFS path;
2. lê até 64 KiB;
3. chama KCC;
4. mescla object no aggregate;
5. ao final chama ChrisLd;
6. grava ELF.

Isso é infraestrutura real de compile/link dentro do kernel.

## Limitação crítica: merge somente de text

Builder atual combina units por:

    chriso_merge_text(&merged, &unit)

e inicializa apenas um merged TEXT buffer de 64 KiB.

Isso não equivale a `chrisld_link_objects` sobre objetos originais.

Production kernel exige também:

- RODATA;
- initialized DATA;
- BSS;
- symbols por object;
- cross-unit relocations.

Os host tests provam que ChrisLd consegue linkar full objects. Mas `chrisbuild_mk_kernel` ainda colapsa units pelo caminho mais estreito.

Logo um build interno aparentemente bem-sucedido ainda não prova semantic reproduction do production kernel.

## Limitação crítica: ASM_OBJECTS não são construídos

`BuildManifest` detecta `ASM_OBJECTS=` somente para parar a coleta de C paths.

Não guarda nem monta os listed assembly objects.

Assim handwritten assembly exigido pelo full kernel não entra nesse build path.

É self-hosting gap concreto.

## Limitação crítica: semântica do production linker script

Host production linker script define higher-half base e preserva explicitamente Limine request sections:

    .limine_requests_start
    .limine_requests
    .limine_requests_end

ChrisLd não interpreta `kernel/metal/linker.ld`.

Ele possui layout fixo próprio: packed text/rodata seguido de writable data/BSS page-aligned.

KCC tests mostram que marker bytes de Limine em `bootinfo.c` podem chegar a initialized data, mas preservar section identity e KEEP ordering exatos é outro contrato.

Kernel native-built não é boot-equivalent até esse contrato ser reproduzido ou substituído por layout alternativo verificado.

## Limitação crítica: ownership de objetos

`native_image_free` libera hoje apenas TEXT de uma `ChrisoImage`.

Build loop interno também libera explicitamente apenas `unit.sec[TEXT]`.

Como objetos KCC/ChrisAsm podem conter rodata/data, lifetime management completo precisa de section-complete ownership API.

## Validação atual no host

`tools/test_native_link.c` testa cadeia básica:

    ChrisAsm -> ChrisO -> ChrisLd -> ELF

com `main` mínimo retornando 42.

Valida ELF magic e expected entry address.

`tools/test_kcc.c` é muito mais profundo.

Entre outros casos, verifica:

- fixture inicial e undefined-call relocation;
- `kernel/metal/serial.c` real;
- link de serial + klog + assembly stubs;
- BSS objects;
- volatile semantics;
- string/memory routines;
- packed/normal struct layouts;
- control flow;
- preprocessor;
- enums, nested aggregates e initialized data;
- static assertions;
- privileged instruction bytes.

O test atual contém conjunto explícito de **26 translation units reais em `kernel/metal/*.c`**, cada uma compilada com required symbol check.

Essa é evidência direta da revisão atual. A afirmação antiga de “50 de 112” não é mais usada porque não é uma medição confiável deste source revision.

## O que os gates provam

Atualmente está demonstrado que:

- KCC compila subset C não trivial orientado a kernel;
- ChrisAsm codifica instruction subset exercitado;
- ChrisO carrega code/data/BSS, symbols e relocations;
- ChrisLd resolve múltiplos objects e emite program headers ELF separados RX/RW;
- vários kernel/metal units reais passam pelo KCC no host.

Ainda não está demonstrado:

- compile de todas production translation units;
- substituição integral de handwritten assembly;
- reprodução fiel do production linker script;
- boot de kernel produzido somente pela native toolchain;
- install/reboot desse kernel;
- recursive rebuild da toolchain por ela própria.

## Capacity e complexidade

A toolchain usa intencionalmente bounded arrays e linear searches.

Exemplos:

- KCC symbol/macro/struct tables;
- ChrisO symbol/relocation tables;
- ChrisLd cross-object symbol resolution.

Com object counts pequenos, implementação fica transparente.

Para N objects com S symbols, global resolution ingênua pode se aproximar de O(N*S) por unresolved symbol; duplicate-global checks são quadráticos entre symbol sets.

É aceitável na escala experimental atual, mas merece revisão antes de programas muito maiores.

## Concorrência

KCC e ChrisAsm usam bastante global mutable state.

Não são desenhados para compilations/assemblies independentes concorrentes sem serialização.

Kernel jobs/build paths devem serializar uso até front ends migrarem para per-compilation context.

ChrisLd é mais naturalmente call-scoped, mas buffers de input/output ainda exigem ownership normal.

## Failure containment

Cada estágio falha em problemas estruturais relevantes:

- KCC emite diagnostic;
- ChrisAsm rejeita syntax/opcode/capacity inválidos;
- ChrisO reader rejeita framing inválido;
- ChrisLd rejeita duplicate globals, unresolved references, relocation indices/types inválidos e output overflow;
- ELF validator rejeita layouts malformed ou W+X.

Caller continua responsável por reporting e liberação de temporary section buffers.

## Fronteira de self-hosting

Uma hierarquia útil:

    ferramenta existe
      < compila fixtures
      < compila kernel units reais
      < gera todos kernel objects
      < linka com layout boot-equivalent
      < kernel gerado boota
      < kernel gerado é instalado/rebootado
      < sistema gerado se reconstrói

ChrisOS está atualmente no meio dessa hierarquia.

Há compile/link infrastructure genuína dentro do sistema, mas full production-kernel bootstrap permanece não provado.

## Próximos passos necessários

Para o caminho nativo virar complete kernel builder confiável:

1. substituir text-only merge por full multi-object linking;
2. ingerir/montar `ASM_OBJECTS`;
3. preservar ownership de todas ChrisO sections;
4. modelar Limine/linker-script section contract;
5. compilar todas required production translation units;
6. linkar sem unresolved symbols;
7. validar ELF contra production contract;
8. bootar sob QEMU;
9. instalar no target boot medium;
10. rebootar na image gerada;
11. somente então elevar self-host evidence level correspondente.

## Mapa de source e revisão

`compiler/kcc/kcc.c` implementa C-subset compiler e assembly generation.

`compiler/chrisasm/chrisasm.c` codifica assembly em ChrisO sections/symbols/relocations.

`compiler/chrisld/chriso.c` serializa/deserializa object format.

`compiler/chrisld/chrisld.c` implementa section layout, symbol resolution, relocation e ELF64 generation.

`kernel/tools/native_link.c` implementa ELF writer interno simples.

`kernel/tools/chrisbuild.c` é o atual in-kernel kernel-build orchestrator.

`tools/test_kcc.c` e `tools/test_native_link.c` fornecem a principal validation evidence.

Todas as afirmações de comportamento atual foram reconciliadas com ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
