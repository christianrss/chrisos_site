---
id: kcc
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
  - kernel/metal/kcc_job.c
  - kernel/tools/chrisbuild.c
  - kernel/tools/native_link.c
  - kernel/tools/shell.c
  - tools/kcc_main.c
  - tools/test_kcc.c
symbols:
  - kcc_compile_named
  - kcc_compile_source
  - kcc_last_error
  - kcc_last_asm
  - preprocess
  - parse_base
  - parse_struct_body
  - parse_expr
  - parse_binary
  - parse_stmt
  - parse_args
  - parse_initializer
  - parse_asm_stmt
  - emit_sync_cas
  - emit_sync_add
  - emit_sync_release
depends_on:
  - native-toolchain
  - semantic-analysis
  - native-codegen
  - calling-conventions
  - x86-instruction-encoding
related:
  - chrisasm
  - chriso
  - chrisld
  - self-hosting-bootstrap
---

# Arquitetura do KCC e perfil de C

## Escopo

KCC é o compiler de subset C nativo usado pela toolchain experimental do ChrisOS.

O caminho atual de compilação é:

    source C-like
        -> preprocessor KCC
        -> recursive-descent parse + semantic/code-generation state
        -> assembly textual x86-64
        -> ChrisAsm
        -> objeto ChrisO

KCC não é wrapper de GCC e não usa LLVM como lowering. Preprocessing, parsing, modelo de tipos, symbol handling, constant evaluation, stack-frame assignment e lowering orientado a x86-64 estão implementados em `compiler/kcc/kcc.c`.

O compiler é deliberadamente mais estreito que ISO C. O contrato correto não é simplesmente “suporta C”. KCC implementa um perfil concreto cuja sintaxe aceita e semântica de máquina são definidas pelo source e testes atuais.

![Pipeline de compilação do KCC](../../assets/diagrams/kcc-pt-br.svg)

## Interface pública

`compiler/kcc/kcc.h` expõe quatro funções:

- `kcc_compile_named(file, src, out)`;
- `kcc_compile_source(src, out)`;
- `kcc_last_error()`;
- `kcc_last_asm()`.

`kcc_compile_named` preserva filename para diagnostics. `kcc_compile_source` é o entry point sem filename usado por vários caminhos dentro do kernel.

Compilação bem-sucedida produz `ChrisoImage`.

Assembly textual não é o artifact público principal, mas `kcc_last_asm` expõe o último assembly gerado para tests/debugging.

O driver host em `tools/kcc_main.c` lê source, chama `kcc_compile_named`, serializa ChrisO e grava o object file.

## Estado global do compiler

Grande parte do state é global no arquivo.

Limites principais:

| Recurso | Limite atual |
| --- | ---: |
| assembly gerado | 256 KiB |
| source preprocessado | 256 KiB |
| symbols | 2048 |
| macros | 256 |
| parâmetros de macro | 4 |
| corpo de macro | 768 bytes |
| structs | 80 |
| fields por struct | 32 |
| typedefs | 64 |
| enum constants | 512 |
| parâmetros/argumentos | 16 |
| buffer de static initializer | 4096 bytes |

State central inclui `g_p`, `g_file`, `g_line`, tabelas de symbols/types, tabelas do preprocessor, frame allocator, temporary spill state e assembly buffer.

`kcc_compile_named` reseta esses dados antes de cada compilation.

A implementação é simples e reduz allocations, mas significa que KCC **não é reentrant**.

Compilações concorrentes podem corromper parser, preprocessor, symbols e output umas das outras.

## Hazard de concorrência no kernel job

Essa limitação já encontra um caller concorrente potencial.

`kernel/metal/kcc_job.c` envia `kcc_worker` ao job system, e APs executam `job_worker_forever`.

O worker chama `kcc_compile_source` sem lock específico do KCC.

Além disso, `kcc_job_submit_path` grava o path em um único buffer:

    static char g_kcc_path[512];

e passa esse shared buffer ao job.

Overlapping submissions têm dois race surfaces:

1. path pode ser sobrescrito antes de o worker consumi-lo;
2. dois workers podem entrar simultaneamente no global compiler state.

Até existir serialização ou per-compilation context, esse path deve ser tratado como single-flight.

## Modelo de preprocessing

KCC possui preprocessor próprio.

Implementa os mecanismos exigidos pelo subset atual:

- object-like macros;
- function-like macros;
- até quatro macro parameters;
- nested macro expansion;
- token pasting `##`;
- `#if`;
- `#ifdef` / `#ifndef`;
- `#elif` / `#else` / `#endif`;
- `defined(...)`;
- quoted e angle-bracket includes;
- `#error`;
- `#pragma` e `#warning` aceitos/ignorados;
- markers `#line` para diagnostics.

Macro recursion é bounded. `pp_expand_into` interrompe recursive expansion acima de depth 8 e copia o restante.

Include preprocessing rejeita depth > 16.

Conditional nesting usa stack fixa de 32 entries.

## Ambiente built-in do preprocessor

Cada compilation inicia com macros como:

    __x86_64__ = 1
    __freestanding__ = 1
    __VERSION__ = "KCC"
    LIMINE_API_REVISION = 3

Para alguns standard headers, como `stdint.h` e `stddef.h`, KCC consegue sintetizar macros de integer limits porque primitive types correspondentes são internos ao compiler.

Quoted include tenta primeiro path relativo ao arquivo atual.

Depois são consultados diretórios do projeto, incluindo:

- `third_party/limine`;
- `kernel/metal`;
- `kernel/gfx`;
- `kernel/wm`;
- `kernel/tools`;
- `kernel/fs`;
- `kernel/lang`;
- `kernel/net`;
- `compiler`;
- `compiler/chrisld`;
- `compiler/chrisasm`;
- `compiler/kcc`.

No build freestanding, files são lidos pelo filesystem do ChrisOS.

No host, usam file I/O normal.

## Limitações do preprocessor

KCC não é cpp completo.

Entre os limites atuais:

- não há `#undef` no directive dispatcher;
- function-like macro suporta até quatro params;
- logical lines são bounded;
- macro body/expansion são bounded;
- include depth é bounded;
- não existe generic hosted include environment;
- pragmas são ignorados.

Esses pontos são boundaries da implementação atual, não características de C padrão.

## Arquitetura do parser

KCC usa recursive descent direto e gera assembly durante parsing.

Não há AST independente nem general-purpose IR nesse path.

Expressions usam precedence parser.

`parse_binary` reconhece 18 operators binários e recursa RHS em precedence maior.

No nível zero também trata:

- `?:`;
- simple assignment;
- `+=`;
- `-=`;
- `|=`;
- `&=`;
- `^=`;
- `/=`.

Postfix parsing trata:

- calls;
- indexing;
- postfix increment/decrement;
- `.` e `->`.

Unary path cobre unary operators suportados, address/deref, prefix increment/decrement, casts e `sizeof`.

## Categorias de valor

`Val` carrega semantic state transitório da expression.

Campos relevantes:

- `Type type`;
- flag de lvalue;
- flag de function;
- lvalue class;
- frame offset;
- optional immediate;
- global symbol name.

Lvalues:

    LV_NONE
    LV_LOCAL
    LV_GLOBAL
    LV_ADDR

A classe controla address generation e store behavior.

`LV_ADDR` aparece após pointer dereference, indexing ou member selection quando endereço foi calculado e salvo em temporary stack slot.

## Representação de tipos

`Type` contém:

- kind;
- pointer flag;
- pointee size;
- array length;
- second-dimension length;
- struct ID;
- byte size;
- alignment;
- volatile qualifiers;
- function-pointer flag.

Categorias reconhecidas:

    void
    bool
    char
    int
    uint8_t
    uint16_t
    uint32_t
    uint64_t
    struct
    float

Pointers têm oito bytes.

Arrays carregam size/stride metadata no `Type`.

Function pointer declarators são reconhecidos, mas full function signature não é preservada.

## Desvio importante do data model de C

O data model atual não é LP64 C.

KCC mapeia:

    int -> 8 bytes

enquanto:

    unsigned -> 4 bytes

e `uint32_t` / `int32_t` compartilham a mesma categoria interna de quatro bytes.

`int64_t` e `uint64_t` também compartilham categoria de oito bytes.

Signedness de source não é representado com fidelidade equivalente à de compiler C conformante.

Esse fato precisa ser considerado ao classificar translation units como KCC-safe.

## Signedness incompleto

A perda de signedness aparece no codegen.

Divisão/modulo usa:

    xor rdx, rdx
    div rcx

ou seja, unsigned x86-64 division.

Comparisons relacionais, porém, usam jumps signed como `jl`, `jg`, `jle` e `jge`.

Uma mesma categoria interna pode portanto receber mistura de signed/unsigned machine semantics.

KCC ainda não implementa integralmente integer conversions/signedness rules de ISO C.

Future type system precisa carregar signedness e usual arithmetic conversions explicitamente.

## Integer literals

`take_number` aceita decimal e hexadecimal.

Há overflow check contra 64-bit unsigned range.

Suffix chars `u/U/l/L` são consumidos, mas não alimentam complete C integer-rank model.

Numeric primary expressions são emitidas como 64-bit immediates.

Isso é útil para addresses, masks e flags de kernel, sem pretender reproduzir toda literal typing de C.

## Layout de structs

`parse_struct_body` calcula fields sequencialmente.

Em ordinary struct:

    field_offset = align_up(current_offset, field_alignment)

Tamanho final é arredondado ao maior field alignment.

Com `__attribute__((packed))`, field alignment vira 1.

Cada field guarda concrete type + byte offset.

Há suporte a pointers, nested structs, function-pointer fields e arrays.

Arrays em fields suportam até duas dimensions no parser atual.

Não existe parser de `union` no KCC atual.

## Structs incompletas

Tagged struct pode ser introduzida antes do body.

Placeholder começa sem fields e size zero.

Pointer pode referenciar tipo incompleto.

Direct non-pointer field de incomplete struct é rejeitado.

Isso atende forward declarations comuns em kernel data structures.

## Initializers

Global initializer lowering usa staging buffer de 4096 bytes.

Formas suportadas incluem:

- scalar constant expressions;
- string arrays;
- array initializer lists;
- nested struct initializers;
- designated fields, como `.field = value`.

Depois KCC emite bytes inicializados em `.data`.

Globals sem initializer vão para `.bss` usando `.zero`.

O initializer path é estático: constant expressions são avaliadas antes de ChrisAsm construir as sections ChrisO.

## Constant expressions

KCC possui evaluator separado, `ce_expr`.

Ele cobre broad integer operators usados por:

- enum values;
- array bounds;
- initializers;
- static assertions.

`_Static_assert` falha compilation quando constant expression vale zero.

Esse evaluator é integer-oriented, não um avaliador geral de qualquer C expression.

## `sizeof` e unevaluated expressions

`sizeof` aceita type ou expression.

Para `sizeof(expr)`, KCC parseia expression para descobrir type, mas salva/restaura:

- assembly length;
- overflow state;
- dead-store state;
- temporary count;
- frame allocation state.

Side effects gerados pelo parse são descartados.

Logo `sizeof(expr)` usa semantic/type path sem manter normal runtime lowering.

## Fronteira de float

`float` é recognized type para declarations/type parsing.

Native float execution não está implementado.

`reject_float` produz:

    float is outside this subset

quando float não-pointer entra no ordinary lowering.

Isso evita emitir integer code silenciosamente incorreto, mas deixa math/graphics source com native FP fora do perfil KCC.

## Local storage e stack frame

Toda função normal emitida começa com:

    push rbp
    mov rbp, rsp
    sub rsp, 2048

São reservados dois KiB independentemente da quantidade real de locals.

`alloc_slot` aloca locals.

Cada objeto usa no mínimo oito bytes e arredondamento de oito bytes.

Normal-local allocator rejeita quando `g_frame + size > 1536`, reservando a região inferior do frame para compiler temporaries.

## Temporary spills

Temporaries usam:

    -1600 - g_ntemp * 8

e `g_ntemp` volta a zero no início de cada statement.

Diferentemente de `alloc_slot`, `temp_slot` não possui lower-bound check.

Como frame termina em `rbp - 2048`, statement suficientemente complexo pode criar temporary offsets abaixo da área reservada.

Há, portanto, stack-frame capacity gap concreto.

Compiler deve limitar temporaries ou dimensionar frame dinamicamente.

## Calling convention

KCC usa subset prático do x86-64 System V integer ABI.

Primeiros seis args:

    rdi, rsi, rdx, rcx, r8, r9

Na entrada, esses values são copiados para frame slots.

Args além do sexto são lidos do callee a partir de:

    [rbp + 16]

Caller reserva stack space para extra args e arredonda para número par de 8-byte slots, preservando alignment compatível com call/prologue.

Return values usam `rax`.

Não há full ABI classification para float, vectors, large aggregates ou mixed-class arguments.

## Function signatures são superficiais

KCC registra function symbol e seu return-like `Type`, mas não guarda parameter signature completa.

Function pointer declarators também marcam `is_func_ptr` enquanto grande parte da parameter declarator list é apenas consumida.

Call lowering aceita até 16 args sem comparar types/count contra stored prototype.

Unknown identifier seguido de `(` também pode virar function target com TY_INT-like return.

Isso ajuda external calls a chegarem ao ChrisO como unresolved references.

Ao mesmo tempo significa que KCC ainda não oferece standard prototype checking e pode aceitar calls ABI-incompatíveis.

## Inline functions

Quando definition está marcada `inline`, KCC atual pula o braced body.

Não executa inlining nem necessariamente materializa função normal.

É mecanismo de source compatibility, não optimization pass.

Source não deve depender daquela inline definition como única implementação resolvível.

## Control flow

`parse_stmt` emite labels/branches diretamente para:

- blocks;
- `if` / `else`;
- `switch` / `case` / `default`;
- `while`;
- `for`;
- `break`;
- `continue`;
- `return`;
- `goto`;
- labels.

`switch` aceita até 64 cases e gera sequência linear compare/branch.

Dispatch é O(C) para C cases.

Não há jump-table selection nem CFG optimization.

## Lowering de loops

`while` usa head/end labels.

`for` captura initializer, condition e step em bounded text buffers, reparsa com `parse_from` e aponta `continue` para step label.

Esse detalhe é testado porque `continue` em `for` precisa executar step antes de voltar à condition.

## Labels e goto

Label vira assembly label direto.

`goto name;` vira direct jump.

Não existe high-level CFG validation.

Unknown labels são delegados ao assembler/linking boundary.

## Loads e stores

Valores escalares avaliados ficam em `rax`.

Address calculations também passam por `rax` e temporaries são spilled no frame.

Objects de um byte usam byte access.

Volatile objects de quatro bytes recebem dword access.

Os demais acessos escalares normalmente usam 8-byte `mov`.

Isso cria limitação relevante de width.

## Gap de acesso ordinary 16/32-bit

Para non-volatile global ou address lvalue:

- size 1 usa byte access;
- volatile size 4 usa dword access;
- demais casos usam acesso de oito bytes.

Logo ordinary `uint16_t`, `int16_t`, `uint32_t` e `int32_t` podem ser carregados/gravados como oito bytes apesar do declared size.

Em globals ou aggregate fields adjacentes isso pode ler ou sobrescrever storage vizinho.

A suite testa field offsets e volatile 32-bit accesses, mas essa regra do source continua sendo correctness limitation concreta.

É necessário width-specific lowering para 8/16/32/64 bits.

## Volatile

KCC preserva volatile flag em type e pointee.

Volatile access limpa dead-store optimization state e força o memory access implementado.

Host suite verifica source MMIO-style contando loads/stores gerados.

É evidência útil para os casos suportados, não prova toda C volatile semantics enquanto width lowering permanece incompleto.

## Dead-store reduction

Existe peephole muito pequeno para non-volatile globals.

Após store, compiler guarda symbol + assembly position.

Se novo eligible store ao mesmo symbol ocorrer antes de operação que invalide state, `dead_store_drop` remove o store anterior do assembly buffer.

Não é SSA, data-flow nem alias analysis.

Calls, loads e volatile activity limpam esse state.

## Pointer operations

Pointers têm oito bytes.

`pointee_size` define scaling de indexing e pointer ++/--.

Indexing calcula:

    address = base + index * element_size

e produz `LV_ADDR`.

`.` usa address do struct lvalue.

`->` carrega pointer e soma field offset.

Array lvalue decays para pointer quando consumido como value em `load_val`.

## Function pointers

KCC reconhece declarations e indirect calls.

Target é avaliado e spilled, args são preparados, depois target é restaurado e executado com:

    call rax

Como full signature não é preservada, type checking do indirect call fica essencialmente restrito ao marker de function pointer.

## Perfil de inline assembly

KCC aceita `asm` / `__asm__`, mas não implementa GNU inline assembly geral.

Parser reconhece allowlist de templates exatos usados pelo ChrisOS:

- `cli` / `sti` / `hlt` / `pause`;
- port `in` / `out`;
- CR2/CR3;
- stack-pointer read;
- `invlpg`;
- `lidt`;
- `str`;
- GDT reload sequence;
- AP stack switch;
- kernel-thread stack switch;
- user-mode `iretq`.

Constraints são interpretados apenas no nível necessário a esses templates.

Unknown template é rejeitado salvo quando corresponde a uma das sequências explicitamente suportadas.

Esse desenho mantém low-level compatibility surface como allowlist.

## Atomic builtins

KCC special-case:

- `__sync_bool_compare_and_swap`;
- `__sync_fetch_and_add`;
- `__sync_lock_release`;
- `__builtin_return_address(0)`.

CAS emite `lock cmpxchg` para pointee de 32/64 bits.

Fetch-and-add usa `lock xadd`.

Lock release grava zero.

Outros nomes iniciados por `__sync`, `__atomic` ou `__builtin` são rejeitados como outside subset.

Assim unsupported intrinsic não degrada silenciosamente para external call.

## Assembly como boundary intermediário

KCC não gera machine bytes diretamente.

Depois de parsing:

1. `g_asm` recebe terminator;
2. `chrisasm_assemble(g_asm, out)` é chamado;
3. ChrisAsm constrói `ChrisoImage`.

Assembly-buffer overflow é falha antes de assembler.

Se ChrisAsm rejeitar output, KCC produz:

    assembler rejected the translation

O boundary textual é útil: host tests inspecionam `kcc_last_asm` e também machine bytes nas ChrisO sections.

## Diagnostics

`KccDiag` contém:

- file;
- line;
- column;
- severity;
- message.

Preprocessing injeta `#line` para que diagnostics de includes atualizem file/line durante parse.

Muitos parser failures usam column 1 em vez da coluna precisa do token.

Modelo é single-error: `fail` seta `g_stuck` e interrompe compilation, em vez de fazer recovery para múltiplos diagnostics.

## Ownership de memória

Front end usa principalmente fixed global arrays.

Include content é temporary heap allocation e é liberado após recursive preprocessing.

Output `ChrisoImage` contém section allocations produzidas por ChrisAsm.

Caller é responsável pelo lifetime do object conforme regras ChrisO/native-toolchain.

Isso é relevante porque alguns in-kernel callers ainda não fazem section-complete cleanup de todos os paths.

## Integração no sistema

KCC é usado por:

- shell native compilation;
- `kcc_job_submit_path`;
- `chrisbuild_mk_kernel`;
- host tool.

Shell command `kcc` compila source para ChrisO e depois usa `native_link_write_elf` para gerar ELF nativo.

`chrisbuild_mk_kernel` compila múltiplos C files, mas builder atual ainda agrega somente TEXT em vez de preservar full multi-object semantics descrita no capítulo native-toolchain.

KCC já produz objetos mais ricos do que o kernel-builder interno consome.

## Evidência de validação

`tools/test_kcc.c` cobre muito mais que toy expressions.

A revisão atual testa:

- level-0 fixture;
- undefined external call relocation;
- `kernel/metal/serial.c` real;
- `kernel/metal/string.c` real;
- `meminfo.c` e `pit.c`;
- normal/packed struct offsets;
- volatile MMIO;
- BSS e initialized DATA;
- designated aggregate initialization;
- enums;
- nested aggregates;
- arrays;
- function-pointer forms;
- `switch` e `goto`;
- `for` continue semantics;
- `sizeof`;
- `_Static_assert`;
- token pasting e conditional preprocessing;
- CR2/CR3;
- `invlpg`;
- `lidt`;
- atomics;
- `iretq`;
- port I/O;
- interrupt enable/disable;
- `hlt` e `pause`.

O teste contém ainda tabela explícita de **26 translation units reais em `kernel/metal/*.c`**, exigindo um symbol selecionado de cada compilation.

Isso prova cobertura low-level não trivial no source revision atual.

Não prova que todo ChrisOS compila no KCC.

## O que os tests não provam

A suite não estabelece:

- ISO C conformance;
- signed/unsigned conversion correto;
- ordinary 2/4-byte access correto em todos objects;
- arbitrary inline asm;
- native floating point;
- unions;
- complete variadic ABI;
- prototype/argument checking completo;
- thread-safe parallel compilation;
- full production-kernel rebuild;
- todos extreme-capacity boundaries.

Esses itens exigem implementation + tests específicos.

## Performance

KCC privilegia fixed arrays e linear searches.

`sym_find` procura symbols de trás para frente.

Typedef, enum e struct lookup também são lineares.

Na escala atual isso mantém implementation transparente.

Em unidades grandes, lookup pode custar O(N) por identifier e parsing pode se aproximar de comportamento quadrático em symbol-heavy input.

Assembly também é construído em único bounded text buffer.

O projeto prioriza observability sobre optimizer-scale throughput.

## Segurança e robustez

Source pode vir do ChrisOS filesystem, então falhas precisam ser contidas.

Pontos positivos:

- bounded tables;
- bounded source/assembly/preprocessor buffers;
- include-depth limit;
- conditional-depth limit;
- integer literal overflow checks;
- array-size checks;
- unsupported builtins rejeitados explicitamente;
- ChrisAsm rejection propagada como compile failure.

Gaps importantes:

- global state exposto a concurrent jobs;
- shared `g_kcc_path`;
- temporary spill count sem bound do fixed frame;
- width mis-lowering de ordinary 16/32-bit objects;
- shallow function-signature checks;
- signedness semantics inconsistentes.

## Limitações atuais

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56:

- KCC é kernel-oriented C subset, não ISO C;
- plain `int` tem oito bytes e plain `unsigned` quatro;
- fixed-width signed types não preservam signedness completa;
- comparison/division não formam coherent C signedness model;
- float nativo é rejeitado;
- union não existe;
- inline bodies são pulados, não realmente inlined;
- prototypes/signatures não são totalmente preservados;
- unknown call name pode virar unresolved function call;
- ordinary non-volatile 16/32-bit memory access pode virar oito bytes;
- toda normal function reserva 2048 bytes;
- temporary spills não têm explicit frame-bound check;
- compiler é global/non-reentrant;
- async kernel job adiciona shared-state races;
- preprocessor e inline asm são bounded subsets;
- production self-hosting continua incompleto.

## Fronteira de roadmap

Evoluções prioritárias:

1. per-compilation context em vez de mutable globals;
2. lock/single-flight até esse refactor;
3. storage independente por queued job path;
4. signedness e integer ranks explícitos;
5. usual arithmetic conversions;
6. width-correct loads/stores 8/16/32/64;
7. full function signatures e call checking;
8. variadic ABI explícito quando necessário;
9. real inline semantics ou emissão normal das bodies;
10. bounded/dynamic temporary stack allocation;
11. maior correção do constant evaluator;
12. structured IR se optimization demand superar direct assembly lowering;
13. ampliar asm allowlist somente com source/test evidence;
14. cobrir todas production translation units;
15. demonstrar boot end-to-end pela native toolchain.

São roadmap items até aparecerem no source e na validation evidence.

## Mapa de source e revisão

`compiler/kcc/kcc.c` implementa preprocessor, parser, semantic state, constant evaluator, direct assembly lowering e handoff para ChrisAsm.

`compiler/kcc/kcc.h` define compile/diagnostic API.

`compiler/chrisasm/chrisasm.c` é o machine-code/object backend chamado pelo KCC.

`compiler/chrisld/chriso.h` define object image devolvida.

`tools/kcc_main.c` é CLI host.

`tools/test_kcc.c` é a principal evidence executável do perfil C e dos low-level instruction paths.

`kernel/metal/kcc_job.c` expõe async compilation e mostra o atual concurrency hazard.

`kernel/tools/chrisbuild.c` consome KCC no experimental kernel rebuild.

`kernel/tools/shell.c` oferece interactive native compilation.

Todas as afirmações de comportamento atual foram reconciliadas contra ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
