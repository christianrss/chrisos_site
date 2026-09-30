---
id: native-codegen
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/kcc/kcc.c
  - compiler/kcc/kcc.h
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisasm/chrisasm.h
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chrisld.h
  - kernel/tools/native_link.c
  - tools/test_kcc.c
  - tools/test_chrisasm.c
  - tools/test_chriso.c
  - tools/test_chrisld.c
  - tools/test_native_link.c
symbols:
  - kcc_compile_named
  - asm_line
  - asm_cat
  - asm_mov_imm
  - alloc_slot
  - temp_slot
  - load_val
  - store_val
  - gen_addr
  - parse_args
  - apply_bin
  - epilogue
  - chrisasm_assemble
  - add_sym
  - add_reloc
  - ChrisoImage
  - ChrisoSym
  - ChrisoRel
  - chriso_write
  - chriso_read
  - chrisld_link_objects
  - resolve_sym
  - apply_one
depends_on:
  - intermediate-representation
  - semantic-analysis
  - x86-instruction-encoding
  - elf-linking
related:
  - calling-conventions
  - native-toolchain
  - kcc
  - chrisasm
  - chriso
  - chrisld
---

# Geração de código nativo

## Escopo

Geração de código nativo converte a semântica da linguagem em instructions e data structures executadas diretamente pelo processador-alvo, sem passar pelo interpreter CLVM.

No ChrisOS atual, o caminho C-like nativo é:

    source C-like
        ->
    preprocessing + parsing + semantic actions do KCC
        ->
    assembly x86-64 textual
        ->
    ChrisAsm
        ->
    object image ChrisO
        ->
    ChrisLd
        ->
    ELF64 executable image

KCC não faz lowering através de uma machine IR target-independent persistente. Parsing e native emission são acoplados. ChrisAsm realiza o encoding real das instructions x86-64, e ChrisLd faz section placement, symbol resolution e relocation.

Este capítulo documenta esse caminho nativo. Lowering para CLVM bytecode pertence aos capítulos de ChrisC/CLVM, enquanto runtime JIT translation é outro mecanismo.

![Geração de código nativo no ChrisOS](../../assets/diagrams/native-codegen-pt-br.svg)

## Fronteira de code generation

Existem duas fronteiras distintas de geração.

KCC traduz operações de source para textual assembly.

ChrisAsm traduz essas textual instructions para bytes x86-64 exatos e relocation records.

Essa divisão é importante.

KCC precisa saber que registers e instruction families expressam uma operação, mas não codifica diretamente REX prefixes, ModRM bytes, SIB bytes ou immediate fields.

ChrisAsm é responsável por esses detalhes.

O backend pipeline prático é:

    semantic value
        ->
    assembly spelling
        ->
    machine encoding
        ->
    relocatable object state
        ->
    linked executable

## Modelo de emissão do KCC

KCC emite para um assembly text buffer global.

Helpers como:

    asm_line(...)
    asm_cat(...)
    asm_mov_imm(...)

anexam instruction text.

asm_mov_imm, por exemplo, converte um immediate para decimal e produz a forma textual:

    mov register, immediate

No final de kcc_compile_named, KCC termina o buffer e chama:

    chrisasm_assemble(g_asm, out)

onde out é um ChrisoImage.

Se ChrisAsm rejeita a translation, KCC reporta compile error.

Portanto, parse bem-sucedido do KCC não é suficiente: o assembly gerado também precisa ser aceito pelo project assembler.

## RAX como expression register principal

O generator atual usa RAX como primary value register para a maior parte da avaliação de expressions.

Literal values são materializados em RAX.

Loads colocam values em RAX.

Arithmetic normalmente deixa result em RAX.

Function results são esperados em RAX no call path gerado.

Quando dois values precisam coexistir, KCC geralmente salva um deles num temporary frame slot, avalia o outro, move esse resultado para RCX ou outro helper register e recarrega o primeiro em RAX.

É uma estratégia simples orientada a accumulator, não um register-allocation algorithm.

## Temporary values e frame spills

save_rax aloca temporary slot e armazena RAX.

Temporary slots começam em uma região separada de offsets negativos abaixo de RBP.

Ordinary local storage é alocado por alloc_slot.

alloc_slot arredonda cada slot para pelo menos oito bytes e alignment de oito bytes. Ele rejeita crescimento do frame local comum além do budget configurado de 1536 bytes.

Function entry atualmente reserva:

    sub rsp, 2048

depois de estabelecer RBP.

Assim, o compilador mantém uma frame area fixa suficientemente ampla para locals e para a região de temporary spills usada pelo generator.

O design é simples e determinístico, mas produz mais memory traffic que um backend com liveness analysis e register allocation.

## Modelo de endereçamento local

frame_txt constrói endereços relativos a RBP.

Um local pode aparecer como:

    [rbp-N]

Parameters além do subset recebido em registers são acessados por offsets positivos:

    [rbp+16]
    [rbp+24]
    ...

gen_addr usa LEA para endereços locais.

Manter frame pointer estável simplifica local-variable addressing, temporary spills e debugging.

O custo é dedicar RBP permanentemente à função de frame pointer nos functions gerados.

## Function prologue e epilogue

Uma function normal gerada pelo KCC começa com:

    push rbp
    mov rbp, rsp
    sub rsp, 2048

O helper epilogue emite:

    mov rsp, rbp
    pop rbp
    ret

Isso dá a todos os functions gerados uma stack-frame shape ampla e constante independentemente da quantidade real de local storage.

O compilador evita, assim, uma passagem posterior para finalizar frame size.

Um backend mais avançado poderia calcular tamanho exato após analysis, mas KCC atual prioriza direct single-pass emission.

## Loading de values

load_val conecta semantic Val state a machine instructions.

Um value pode ser:

- immediate;
- local frame lvalue;
- global lvalue;
- indirect address lvalue;
- array que precisa decay para pointer;
- function-like value.

Immediate values são rematerializados em RAX.

Local scalar values são carregados de memória relativa a RBP.

Globals usam syntax RIP-relative:

    [rel symbol]

Indirect lvalues carregam através de address.

Objetos pequenos podem usar byte ou 32-bit loads, enquanto pointer e formas maiores usam 64-bit operations conforme Type metadata.

Assim, semantic size influencia diretamente o width da machine instruction selecionada.

## Stores de values

store_val realiza a tradução inversa.

Para local destination, RAX é escrito no frame slot.

Para globals, KCC emite symbol-relative stores.

Para indirect destinations, o address é materializado e o result é armazenado por esse pointer.

Widths novamente dependem de Type.

O generator distingue byte-sized values de values maiores e pointers.

Volatile global stores também interagem com local dead-store optimization state: volatile accesses limpam ou ignoram esse estado para preservar accesses observáveis.

## Address generation

gen_addr suporta as location classes representadas por Val.

Para local:

    lea rax, [rbp-offset]

Para global:

    lea rax, [rel symbol]

Para address lvalue já calculado, KCC recarrega o temporary que guarda o endereço.

Array indexing e structure field access formam addresses somando scaled offsets a uma base.

Pointer increment/decrement usa pointee_size como step.

O backend depende, portanto, da semantic analysis ter produzido sizes e offsets corretos.

## Binary arithmetic

apply_bin faz lowering direto de várias binary operations.

O pattern geral é:

1. avaliar o left side;
2. salvar RAX em temporary slot;
3. avaliar o right side;
4. mover o right result para RCX;
5. recarregar o left em RAX;
6. emitir target instruction.

Exemplos:

    add rax, rcx
    sub rax, rcx
    and rax, rcx
    or rax, rcx
    xor rax, rcx
    imul rax, rcx

Division usa explicitamente conventions de RDX:RAX.

Nos paths suportados, o generator limpa RDX e usa div conforme o current arithmetic profile.

É direct instruction selection, sem target-selection DAG intermediário.

## Comparisons

Comparison operators emitem:

    cmp rax, rcx

e depois um helper converte a condition selecionada em boolean value canônico.

set_flag cria local labels e branches que produzem zero ou um em RAX.

O result Type se torna boolean.

É uma branch-based materialization strategy em vez de usar SETcc universalmente.

ChrisAsm suporta as instruction forms selecionadas pelo assembly gerado, mas a sequência é escolhida pelo high-level KCC path.

## Short-circuit control flow

Logical AND e OR não podem ser tratados como arithmetic comum, porque a right expression pode não executar.

KCC cria labels durante parsing.

Para &&, left igual a zero desvia da avaliação do right side.

Para ||, left diferente de zero pula a avaliação do right.

O result final é normalizado para boolean.

Ternary expressions usam estratégia semelhante com labels para false branch e join point.

É direct control-flow code generation; não existe CFG lowering posterior.

## Statements e labels

new_lab gera names como:

    .L0
    .L1

Structured statements emitem branches contra esses labels.

if, loops, break, continue e ternary expressions tornam-se local assembly labels e conditional/unconditional jumps durante parsing.

ChrisAsm trata labels .L como assembler-local. Same-section local branches são corrigidos internamente e não consomem ordinary ChrisO symbol entries.

Isso é importante porque kernel files podem conter mais local labels que a finite symbol table deve representar.

## Function calls

O call generator atual avalia arguments antes da chamada.

As seis primeiras integer/pointer argument positions são movidas para:

    rdi
    rsi
    rdx
    rcx
    r8
    r9

Arguments adicionais são gravados em stack space preparado pelo caller.

Direct calls emitem:

    call symbol

Function-pointer calls carregam target e emitem:

    call rax

Depois da chamada, o result permanece em RAX.

O calling-convention contract completo e o stack layout ficam no próximo capítulo; aqui o ponto de codegen é que call lowering ocorre imediatamente a partir da parsed argument list.

## Function parameters

Na function entry, KCC copia os seis primeiros incoming register parameters para local frame slots.

Referências posteriores a esses parameters então usam o mesmo local-load machinery de ordinary locals.

Parameters depois dos seis primeiros são representados por offsets positivos de RBP iniciando em 16 bytes.

Isso simplifica expression code generation porque a maior parte dos parameter reads é normalizada para memory locations.

O trade-off é additional memory traffic.

## Global objects

KCC também emite data declarations, não apenas instructions.

Global initialization é transformada em byte buffers conforme Type size e aggregate layout.

O assembly gerado escolhe sections e emite object bytes ou zero-initialized storage segundo a syntax suportada pelo assembler atual.

External declarations tornam-se undefined symbols em vez de storage alocado.

Identidade static/global é carregada até assembly names e depois para ChrisO symbol bindings.

Native code generation inclui, portanto, executable text e object data layout.

## Inline assembly

O subset C suportado inclui forms selecionadas de inline assembly.

KCC interpreta formas com constraints limitadas e consegue emitir instructions necessárias ao low-level kernel code, inclusive port I/O e operações de sistema/controle.

Não é implementação geral compatível com GCC inline assembly.

O parser reconhece um subset do projeto.

Inline assembly atravessa a normal semantic-to-instruction selection boundary: source pode solicitar comportamento target-specific diretamente.

## Atomic builtins

KCC possui lowering especializado para alguns synchronization builtins.

Compare-and-swap, por exemplo, emite lock-prefixed cmpxchg com width selecionado a partir do pointer type.

Fetch/add usa lock xadd.

Essas operations mostram por que native codegen precisa preservar memory-width semantics com precisão.

Também mostram que high-level builtin names podem reduzir para instruction sequences que não são expressas como ordinary arithmetic source operators.

## Responsabilidade do ChrisAsm

ChrisAsm recebe textual assembly e produz machine bytes.

Ele controla:

- register encoding;
- REX prefix emission;
- opcode bytes;
- ModRM/SIB construction;
- displacement encoding;
- immediate encoding;
- local-label fixups;
- symbol creation;
- relocation creation;
- section buffers.

Essa fronteira é clara: KCC seleciona assembly semantics, enquanto ChrisAsm realiza binary encoding.

## Instruction encoding

ChrisAsm implementa helpers para instruction families sem delegar a external assembler.

A emissão de register-immediate MOV, por exemplo, escreve REX prefix, opcode e immediate de 64 bits.

Memory operands constroem ModRM e, quando necessário, SIB e displacement.

RIP-relative symbolic memory references produzem placeholder de displacement e relocation ChrisO.

O assembler implementa, portanto, o subset de encoding x86-64 exigido pela native toolchain do ChrisOS.

Não é substituto completo de NASM/GAS.

## Local fixups versus object relocations

Existem dois mecanismos diferentes para names ainda não resolvidos.

Assembler-local .L labels são mantidos em internal local-label/fixup tables e corrigidos quando a assembly unit termina.

Symbols externos ou object-visible tornam-se ChrisoSym.

References que não podem ser finalizadas dentro da mesma unit tornam-se ChrisoRel.

Essa separação impede temporary branch labels de poluir a object symbol table.

## Object representation ChrisO

ChrisoImage contém quatro logical sections:

    .text
    .rodata
    .data
    .bss

e arrays de capacidade fixa para symbols e relocations.

ChrisoSym registra:

- name;
- section;
- offset;
- size;
- binding;
- kind.

ChrisoRel registra:

- section;
- offset;
- symbol index;
- addend;
- relocation type.

O relocation vocabulary atual inclui formas x86-64 conhecidas como:

    R_X86_64_64
    R_X86_64_PC32
    R_X86_64_PLT32
    R_X86_64_32
    R_X86_64_32S

ChrisO é, portanto, um compact project object format suficiente para o native linker.

## Referências RIP-relative

Quando ChrisAsm codifica symbolic RIP-relative memory operand, ele escreve displacement zero e adiciona relocation R_X86_64_PC32 com addend -4.

O linker calcula depois o final displacement.

Conceitualmente:

    disp32 = S + A - P

onde:

- S é o resolved symbol address;
- A é relocation addend;
- P é relocation place.

O linker verifica que o result cabe no signed range exigido antes de gravá-lo.

## Symbol resolution

ChrisLd resolve symbols entre múltiplos ChrisoImage objects.

Defined non-global symbol resolve dentro do próprio object.

Global symbols são procurados no object set.

Duplicate global definitions são rejeitadas.

Undefined reference precisa encontrar global definition compatível ou linking falha.

É static-linker behavior convencional implementado num linker pequeno e específico do projeto.

## Section packing

ChrisLd calcula offsets de cada object dentro de cada logical section.

Contribuições de objects dentro de uma section são alinhadas a 16 bytes depois da primeira contribuição não vazia.

Read-only data segue text na executable/read-only region.

Data e BSS provocam criação de writable region.

BSS contribui para memory size, não para file bytes.

O output final é ELF64 com um ou dois loadable segments dependendo da presença de writable state.

## Seleção de entry

Durante linking, ChrisLd procura primeiro defined symbol:

    kstart

Se não existir kstart, procura:

    main

O address selecionado torna-se ELF entry point.

Se nenhum dos dois for encontrado, o initial load address permanece como default entry no implementation atual.

Kernel builds obtêm preferência por kstart, enquanto programas nativos mais simples podem entrar por main.

## Aplicação de relocations

Para cada ChrisoRel, o linker determina:

- file offset do relocation site;
- runtime address desse place;
- referenced symbol definition;
- final symbol virtual address.

apply_one grava então o relocated value apropriado.

64-bit absolute relocation grava oito bytes.

PC32/PLT32 calcula signed relative displacement.

32/32S grava checked 32-bit value segundo as constraints atuais.

Unsupported relocation kinds fazem linking falhar em vez de produzir image silenciosamente incorreta.

## Failure containment

Native code generation é fail-fast entre stages.

KCC pode rejeitar source não suportado ou overflow de buffers.

ChrisAsm rejeita malformed/unsupported assembly, section overflow, duplicate definitions e fixup failures.

ChrisO readers validam magic, version, counts e total serialized size.

ChrisLd rejeita duplicate globals, unresolved symbols, bad relocation indexes, invalid relocation sites e out-of-range relocation values.

Source parse bem-sucedido não implica executable image bem-sucedida; cada boundary posterior valida sua própria representation.

## Performance characteristics

KCC evita optimizer grande e intermediate machine graph, então compile-time overhead é pequeno e suas data structures são simples.

Por outro lado, generated code frequentemente faz spill de expression values para frame slots e os recarrega.

Cada function reserva fixed 2048-byte stack frame.

O backend não possui graph-coloring ou linear-scan register allocation, global liveness analysis, instruction scheduling ou peephole optimizer como separate pass framework.

ChrisAsm executa direct encoding em tempo essencialmente linear sobre assembly lines, com bounded local symbol/fixup tables.

ChrisLd faz object packing mais symbol e relocation scans; seu global-symbol search simples pode ser quadrático no pior caso em object/symbol counts, embora fixed limits mantenham o implementation bounded.

## Evidência de validação

tools/test_kcc.c compila snippets focados e source real do kernel. Ele verifica propriedades do generated assembly, volatile behavior, structures, pointer operations, functions e linked object behavior.

tools/test_chrisasm.c exercita native assembly encoding e object creation.

tools/test_chriso.c valida object serialization e parsing.

tools/test_chrisld.c valida linking, symbols e relocations.

tools/test_native_link.c exercita o high-level native link path.

O CI da documentação também verifica instruction e register contracts contra o source atual.

Esses testes demonstram o active path de KCC até ChrisO e ELF, mas não provam que KCC seja um complete optimizing C compiler.

## Limitações atuais

Na revisão documentada:

- native code generation tem target x86-64 apenas;
- KCC emite assembly durante parsing em vez de partir de target-independent IR;
- RAX funciona como primary accumulator e muitos intermediate values fazem spill para memory;
- não existe general register allocator;
- cada generated function reserva fixed 2048-byte frame;
- ordinary local allocation é limitada;
- floating-point native value operations permanecem fora do KCC subset suportado;
- assembler cobre o x86-64 subset exigido pelo projeto, não a ISA completa;
- ChrisO symbol e relocation tables possuem capacidades fixas;
- optimization é majoritariamente local e syntax-directed;
- inline assembly suporta somente forms selecionadas;
- linker implementa focused static-link model, não feature set completo de ELF linker.

## Fronteira de roadmap

Um native backend mais avançado poderia introduzir:

- typed machine-independent IR;
- basic blocks e liveness explícitos;
- instruction selection a partir de IR patterns;
- virtual registers;
- linear-scan ou graph-coloring register allocation;
- exact frame-size computation;
- ABI-aware tail calls;
- peephole e machine optimization passes;
- floating/SIMD lowering mais amplo;
- unwind metadata;
- debug information;
- additional target architectures;
- suporte mais amplo de relocations e ELF.

Esses itens continuam roadmap até existir implementation e validation correspondentes.

## Mapa de source e revisão

A emissão do KCC está concentrada em compiler/kcc/kcc.c em torno de asm_line, asm_cat, asm_mov_imm, load_val, store_val, gen_addr, parse_args, apply_bin, statement lowering, alloc_slot, temp_slot e epilogue.

Binary instruction encoding, local-label fixups, symbols e relocations ficam em compiler/chrisasm/chrisasm.c.

O native object format é definido por compiler/chrisld/chriso.h e serializado por chriso.c.

Final section layout, symbol resolution, relocation application e ELF construction são implementados em compiler/chrisld/chrisld.c.

Todas as afirmações sobre comportamento atual deste capítulo foram reconciliadas com a revisão ChrisOS e05a17fd76333114a3fb5c2452f38ca747d4ac56.
