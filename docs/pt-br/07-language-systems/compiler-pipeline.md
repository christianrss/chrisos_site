---
id: compiler-pipeline
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/lang_pipeline.h
  - compiler/lang_pipeline.c
  - compiler/chrisc/chrisc.h
  - compiler/chrisc/chrisc.c
  - compiler/clvm/clasm.h
  - compiler/clvm/clasm.c
  - compiler/clvm/clvm.h
  - compiler/clvm/clvm_format.c
  - compiler/kcc/kcc.h
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.h
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/chrisld/chrisld.h
  - compiler/chrisld/chrisld.c
  - kernel/metal/kcc_job.c
  - tools/kcc_main.c
  - tools/test_chrisc_lang.c
  - tools/test_fuzz_chrisc.c
  - tools/test_kcc.c
  - tools/test_chrisasm.c
  - tools/test_chriso.c
  - tools/test_chrisld.c
symbols:
  - chrisc_compile
  - chrisc_compile_ex
  - chrisc_compile_files_ex
  - ChrisResult
  - clasm_compile
  - clvm_write_image
  - clvm_write_image_v2
  - clvm_parse
  - lang_compile_file
  - lang_compile_many
  - lang_compile_list
  - lang_compile_path
  - lang_disk_cc
  - lang_make_cc
  - kcc_compile_named
  - kcc_compile_source
  - kcc_last_asm
  - chrisasm_assemble
  - ChrisoImage
  - chriso_write
  - chriso_read
  - chrisld_link
  - chrisld_link_objects
  - chrisld_validate
depends_on:
  - cpu-datapath-isa
  - machine-code
  - x86-instruction-encoding
  - elf-linking
related:
  - lexical-analysis
  - parsing
  - semantic-analysis
  - intermediate-representation
  - native-codegen
  - calling-conventions
  - chrisc-clvm
  - clvm-bytecode
  - native-toolchain
  - kcc
  - chrisasm
  - chriso
  - chrisld
---

# Pipeline de compilação no ChrisOS

## Escopo

ChrisOS não possui um único pipeline monolítico de compilação.

Hoje existem duas famílias de tradução distintas:

1. **ChrisC / CLVM**, usada para aplicações, drivers e outros programas executados pelo runtime CLVM.
2. **KCC / ChrisAsm / ChrisO / ChrisLd**, usada para traduzir um perfil próprio de C para código nativo x86-64 e, ao final, ELF64.

Os dois caminhos compartilham conceitos clássicos de compiladores, mas não compartilham frontend, IR ou object format.

O primeiro é fundamentalmente um **pipeline de máquina virtual**:

~~~text
fonte .CC
   -> preprocessing ChrisC
   -> tokens
   -> estruturas internas de sintaxe/semântica
   -> bytecode CLVM
   -> imagem .CLV
   -> interpreter ou JIT CLVM
~~~

O segundo é um **pipeline de separate compilation**:

~~~text
fonte C
   -> preprocessing/parsing KCC
   -> assembly textual x86-64
   -> ChrisAsm
   -> objeto relocável ChrisO
   -> ChrisLd
   -> ELF64 ET_EXEC
   -> execução nativa x86-64
~~~

Existe ainda o formato-fonte `.CVA`, assembly CLVM, que passa diretamente por `clasm_compile`.

Este capítulo mapeia os estágios conceituais de compiladores para essas implementações concretas e separa comportamento atual de roadmap.

![Famílias de pipelines de compilação do ChrisOS](../../assets/diagrams/compiler-pipeline-pt-br.svg)

## Por que os estágios ainda importam

A decomposição clássica continua útil:

~~~text
texto fonte
 -> preprocessing
 -> lexical analysis
 -> parsing
 -> semantic checks
 -> intermediate representation
 -> code generation
 -> object/image generation
 -> linking/loading
 -> execução
~~~

Porém compiladores reais podem fundir etapas.

ChrisC possui tokens e nodes explícitos, mas emite bytecode CLVM sem um IR SSA reutilizável separado.

KCC possui preprocessing, tipos, símbolos e parser/codegen, mas emite assembly textual diretamente em vez de produzir primeiro um IR genérico de otimização.

Portanto a implementação não deve ser descrita como se fosse um pipeline estilo LLVM apenas porque o modelo conceitual inclui uma etapa de IR.

## Pipeline A: ChrisC para CLVM

### Entradas públicas

A API principal está em:

~~~text
compiler/chrisc/chrisc.h
~~~

Entradas relevantes:

~~~text
chrisc_compile
chrisc_compile_ex
chrisc_compile_files
chrisc_compile_files_ex
~~~

`chrisc_compile` é a interface simples em memória.

`chrisc_compile_ex` adiciona source path e callbacks de leitura para includes/arquivos.

`chrisc_compile_files_ex` compila vários source paths no mesmo contexto e pode reportar progresso.

A integração com editor, filesystem, runtime e debugger está principalmente em:

~~~text
compiler/lang_pipeline.c
~~~

## Modelo de recursos do ChrisC

ChrisC usa um grande contexto estático, e não uma coleção de objetos de compilação dinamicamente dimensionados.

Alguns limites atuais:

~~~text
source buffer          4 MiB
tokens                 262.144
nodes                  131.072
symbols                16.384
functions              4.096
struct definitions     1.024
include depth          16
source map entries     8.192
diagnostics estruturados 8
~~~

Esses números são ceilings de implementação, não garantias do padrão C.

O compilador também mantém buffers estáticos grandes para translation unit, cache de includes, token stream, nodes e tabelas de lookup.

## Preprocessing no ChrisC

`chrisc_compile_ex` começa resetando todo o estado do compilador e constrói uma translation unit expandida.

A implementação atual contém mecanismos para:

- includes carregados por callback;
- cache de include;
- macros;
- estado de conditional preprocessing;
- `pragma once`;
- mapeamento de arquivo/linha;
- definições built-in.

O texto expandido fica em buffers internos do compilador.

O mapeamento de linhas é preservado para que diagnostics e debug maps apontem de volta aos arquivos originais.

## Lexical analysis

Depois do preprocessing, ChrisC chama seu lexer.

O modelo de token cobre:

- identifiers;
- integer/float literals;
- strings;
- keywords;
- operadores;
- pontuação.

O enum atual inclui construções como:

- aritmética e comparação;
- pointers;
- structs/unions;
- enums/typedefs;
- loops e switch;
- goto/labels;
- casts e sizeof;
- static assertions;
- alignment;
- qualifiers como const, volatile e restrict;
- formas adicionais usadas pelo projeto.

Ter um token no source não significa conformidade completa com ISO C.

ChrisC continua sendo um compilador de perfil próprio.

## Parsing e representação interna

ChrisC armazena a estrutura parseada em um array fixo de nodes.

Existem nodes para:

- blocos e declarações;
- assignments;
- control flow;
- integer/float/string expressions;
- calls;
- unary/binary operations;
- indexing;
- fields;
- pointers;
- switch/case;
- labels/goto;
- casts;
- function pointers;
- inline assembly.

É correto chamá-la de AST-like representation ou árvore interna de sintaxe.

Ela não é um IR geral independente da linguagem.

Sua forma é orientada ao source e fortemente ligada ao code generator CLVM.

## Estado semântico do ChrisC

O compilador mantém tabelas explícitas para:

- símbolos;
- funções;
- structs;
- typedefs;
- enums/constants;
- scopes;
- function pointers;
- global initializers;
- labels/gotos;
- arquivos;
- source maps.

O type state inclui width, pointer state, signedness, float state, struct IDs e arrays.

Semantic analysis e decisões de codegen são, portanto, interligadas nessa representação específica em vez de passar por uma interface formal de typed IR.

## Code generation do ChrisC

Após preprocessing, lexing e parsing, `chrisc_compile_ex` chama o emitter.

A saída é bytecode CLVM escrito diretamente em buffer fornecido pelo caller.

`ChrisResult` devolve:

- code size;
- entry PC;
- quantidade de variables;
- primary diagnostic;
- até oito diagnostics estruturados;
- lista de arquivos;
- mapeamento PC → source;
- ABI major/minor;
- funções exportadas, PCs e argc.

Esse resultado conecta compilação, debugger e criação da imagem executável.

## Sem relocatable objects no ChrisC

ChrisC não gera um objeto relocável por translation unit para depois executar um linker CLVM.

Multi-file compilation ocorre dentro de uma única chamada:

~~~text
chrisc_compile_files_ex(...)
~~~

A saída é um único programa de bytecode.

Isso é diferente do caminho nativo de ChrisO.

A diferença impacta:

- incremental builds;
- symbol visibility;
- separate compilation;
- binary interfaces;
- linker diagnostics.

## Assembly CLVM

Arquivos `.CVA` usam:

~~~text
clasm_compile
~~~

em vez de ChrisC.

O assembler CLVM é two-pass.

Pass 1 calcula labels e byte offsets.

Pass 2 emite opcodes e resolve branches relativos.

O entry padrão é o endereço de:

~~~text
main
~~~

quando esse label existe; caso contrário, zero.

Portanto o mesmo pipeline de VM aceita ChrisC de alto nível e assembly CLVM de baixo nível.

## Criação da imagem CLVM

O bytecode é encapsulado em `.CLV`.

Há dois layouts.

### Versão 1

Header de 16 bytes com entry de 16 bits.

É usado pela integração quando code size e entry cabem no formato legado.

### Versão 2

Header de 24 bytes contendo:

- code size de 32 bits;
- checksum de 32 bits;
- entry de 32 bits;
- memory hint.

Magic:

~~~text
CLVM
~~~

O checksum é FNV-1a sobre o bytecode.

O loader rejeita:

- magic inválido;
- version não suportada;
- flags desconhecidas;
- code size inválido;
- entry fora do bytecode;
- checksum incorreto.

## Limite do formato versus limite da integração

O formato CLVM define:

~~~text
CLVM_MAX_CODE = 16 MiB
~~~

mas `lang_pipeline.c` usa:

~~~text
LANG_CODE_MAX = 4 MiB
~~~

para o buffer integrado de compilação.

Logo, o caminho usado dentro do OS tem ceiling prático menor que o formato CLVM em si.

## Política de imagem no runtime

`emit_game_clv` marca as imagens produzidas com:

~~~text
CLVM_FLAG_GAME
~~~

Quando o código excede 200.000 bytes, a integração define:

~~~text
mem_hint = 32 MiB
~~~

para acomodar workloads maiores, incluindo o caminho de Doom.

Em imagens menores o hint pode permanecer zero.

## Debug maps

ChrisC produz mapeamento PC → source.

`lang_pipeline` grava e depois carrega esses dados para recursos do debugger como:

- source line lookup;
- breakpoints;
- stepping;
- nomes em call stack;
- watches.

O source map faz parte do contrato prático da ferramenta.

## Execução após compilação

Uma imagem `.CLV` passa por `clvm_parse` antes de rodar.

O runtime pode usar:

- interpreter;
- JIT.

O artifact continua sendo bytecode CLVM em ambos os casos.

O JIT é backend de runtime, não um segundo frontend ChrisC:

~~~text
ChrisC -> CLVM bytecode
               |
               +-> interpreter
               |
               +-> JIT
~~~

## Guest compiler e bootstrap

Para arquivos `.CC`, `lang_compile_file` tenta primeiro:

~~~text
lang_disk_cc(...)
~~~

Esse caminho carrega:

~~~text
APPS/CC/CC.CLV
~~~

e executa esse compilador guest dentro de um processo CLVM.

Source e destination path são passados como argumento.

Depois, o output é relido e validado com:

~~~text
clvm_parse
~~~

Se esse caminho não funcionar, `lang_compile_file` ainda pode cair no ChrisC integrado ao kernel.

## O que `lang_make_cc` demonstra

`lang_make_cc` usa o guest compiler para compilar fontes selecionadas, inclusive uma fonte de compilador que produz:

~~~text
CC2.CLV
~~~

Isso é infraestrutura real de bootstrap/self-hosting.

Mostra que um compiler artifact rodando em CLVM consegue produzir outro artifact CLVM.

Não prova automaticamente:

- fixed-point bit a bit;
- reproducible builds;
- resistência a trusting-trust;
- equivalência total entre estágios.

Isso exigiria comparação formal entre stages.

## Pipeline B: KCC para ELF64 nativo

O pipeline nativo começa em:

~~~text
kcc_compile_named
~~~

ou:

~~~text
kcc_compile_source
~~~

em:

~~~text
compiler/kcc/kcc.c
~~~

A saída ainda não é ELF final.

A saída é um:

~~~text
ChrisoImage
~~~

depois do estágio de assembly.

## Preprocessor do KCC

KCC possui preprocessor próprio.

Seu estado inclui tabelas fixas para:

- macros object-like/function-like;
- parâmetros de macro;
- typedefs;
- enums;
- structs;
- symbols.

Predefined macros atuais incluem:

~~~text
__x86_64__ = 1
__freestanding__ = 1
__VERSION__ = "KCC"
LIMINE_API_REVISION = 3
~~~

KCC também trata alguns built-in headers e includes do projeto.

Ele deve ser entendido como compiler freestanding de perfil próprio, não como wrapper de GCC/Clang.

## Parsing e semântica no KCC

KCC possui estruturas explícitas:

~~~text
Type
StructDef
Sym
Val
~~~

Elas carregam estado como:

- scalar kind;
- pointer;
- size/alignment;
- struct identity;
- arrays;
- volatile;
- function pointer;
- lvalue location;
- frame offset;
- global symbol.

Parser e codegen são fortemente acoplados.

Não existe um IR geral persistente entre parsing e assembly.

## Backend do KCC

KCC escreve assembly x86-64 textual em:

~~~text
g_asm
~~~

O buffer de assembly é:

~~~text
256 KiB
~~~

e o buffer de source preprocessado também é:

~~~text
256 KiB
~~~

Após compilar a unidade, KCC chama:

~~~text
chrisasm_assemble(g_asm, out)
~~~

Portanto `kcc_compile_named` já inclui o assembler internamente.

`kcc_last_asm()` permite inspecionar assembly produzido.

## ChrisAsm

ChrisAsm implementa o subset x86-64 necessário à toolchain.

Ele produz dentro de `ChrisoImage`:

- section bytes;
- symbols;
- relocations;
- BSS size.

Sections:

~~~text
.text
.rodata
.data
.bss
~~~

As três primeiras possuem buffers de bytes.

BSS armazena size sem payload no object file.

## Fixups locais e externos

Labels locais da mesma section são resolvidos no assembler.

Referências externas ou de nível de objeto tornam-se symbols/relocations ChrisO.

Por exemplo, call para símbolo não definido pode gerar:

~~~text
R_X86_64_PLT32
~~~

em vez de endereço falso.

Isso permite separate compilation.

## Formato ChrisO

ChrisO é o object format relocável próprio do projeto.

A versão 2 contém:

- section sizes;
- symbol table;
- relocation table;
- BSS size.

Cada symbol ocupa 80 bytes.

Cada relocation v2 ocupa 20 bytes.

Limites atuais:

~~~text
symbols      256
relocations  512
~~~

Bindings:

~~~text
LOCAL
GLOBAL
UNDEF
~~~

e kinds incluem function/object/notype.

## Serialização ChrisO

`chriso_write` serializa `ChrisoImage`.

`chriso_read` aceita v2 e legado v1.

O driver host:

~~~text
tools/kcc_main.c
~~~

faz:

~~~text
C source
 -> kcc_compile_named
 -> ChrisoImage
 -> chriso_write
 -> output.chriso
~~~

Esse driver não executa ChrisLd.

Link é estágio separado.

## KCC rodando no ChrisOS

O kernel inclui:

~~~text
kernel/metal/kcc_job.c
~~~

que permite submeter compilação KCC por path.

O worker:

1. lê o source;
2. compila para `ChrisoImage`;
3. serializa ChrisO;
4. grava `.CHRISO`.

Esse path usa work buffers de 64 KiB para source/output.

É um limite adicional da orquestração.

## ChrisLd

ChrisLd recebe um ou mais `ChrisoImage`.

`chrisld_link_objects` aceita até:

~~~text
32 objects
~~~

por link.

Ele:

1. empacota sections;
2. detecta globals duplicados;
3. resolve symbols;
4. calcula endereços;
5. aplica relocations;
6. gera ELF/program headers;
7. escolhe entry;
8. entrega bytes ELF finais.

## Escolha do entry point

ChrisLd procura primeiro:

~~~text
kstart
~~~

Se não achar, procura:

~~~text
main
~~~

Se nenhum for encontrado, o valor inicial de entry permanece o load address fornecido.

Esse comportamento deve ser conhecido por quem chama o linker.

## Relocations suportadas

O linker atual trata:

~~~text
R_X86_64_64
R_X86_64_PC32
R_X86_64_PLT32
R_X86_64_32
R_X86_64_32S
R_X86_64_NONE
~~~

Ele rejeita tipos desconhecidos, sites inválidos, unresolved symbols e overflow de displacement/value.

## ELF final

ChrisLd gera:

~~~text
ELF64
little-endian
ET_EXEC
EM_X86_64
System V ABI
~~~

Imagem somente com código pode ter um único segment R-X.

Com data/BSS, o linker cria segment R-W separado.

`chrisld_validate` também rejeita PT_LOAD simultaneamente writable e executable.

## Por que existe ChrisO

ChrisO funciona como object ABI pequeno, controlado pelo projeto.

Assim ChrisAsm e KCC implementam:

- sections;
- symbols;
- unresolved references;
- relocations;

sem precisar implementar todo o formato ELF relocatable.

ChrisLd é a fronteira em que os objects próprios se transformam em ELF executável padrão.

## Dois significados diferentes de “link”

### ChrisC / CLVM

Vários sources podem ser compilados dentro de um único contexto.

Não há object file CLVM por source seguido de linker.

### KCC / native

Cada compilation pode produzir ChrisO.

ChrisLd resolve objects e relocations.

Somente o segundo caminho implementa separate compilation clássica.

## Diagnostics

### ChrisC

`ChrisResult` contém:

- primary diagnostic;
- até oito structured diagnostics;
- file;
- line/column;
- ranges;
- severity;
- message.

A integração do OS converte isso em status do editor e serial output.

### KCC

KCC expõe um:

~~~text
KccDiag
~~~

com:

- file;
- line;
- column;
- severity;
- message.

### ChrisAsm e ChrisLd

Esses estágios posteriores normalmente devolvem status coarse de sucesso/falha.

A riqueza diagnóstica cai após o KCC.

Uma toolchain mais madura deve preservar contexto até assembler/linker.

## Propagação de falhas

O pipeline só é confiável se falhas interromperem o build.

No estado atual:

- ChrisC falha em erros de preprocess/lex/parse/emission;
- image writers CLVM rejeitam size/entry inválidos;
- `clvm_parse` rejeita image malformada;
- KCC retorna diagnostic em falhas do frontend/codegen;
- rejeição do ChrisAsm vira erro do KCC;
- ChrisAsm rejeita mnemonic/forma unsupported;
- ChrisO read/write rejeita formato/buffer inválido;
- ChrisLd rejeita unresolved, duplicate globals e relocation overflow;
- `chrisld_validate` rejeita certas condições inseguras/malformadas de ELF.

Continuar silenciosamente não é o contrato pretendido.

## Modelo de otimização

Nenhum dos pipelines possui hoje framework SSA reutilizável.

ChrisC emite CLVM a partir de sua representação orientada a source.

KCC emite assembly textual a partir de parser/type/symbol state.

Podem existir otimizações locais, mas são acopladas ao backend.

Os testes nativos, por exemplo, inspecionam diferenças de assembly entre accesses volatile e não-volatile.

Isso não equivale a um pipeline formal com passes como:

~~~text
mem2reg
GVN
LICM
vectorization
~~~

Esses estágios não existem na arquitetura atual.

## Fronteiras de ABI

### ABI ChrisC / CLVM

O output deve respeitar:

- opcode encoding CLVM;
- regras de call/stack;
- memory model CLVM;
- SYS/builtin ABI;
- entry/flags da image.

### ABI nativa

KCC/ChrisAsm/ChrisLd precisam respeitar:

- encoding x86-64;
- calling conventions do projeto;
- stack frames;
- sections/symbols;
- relocations;
- layout ELF final.

Parser correto não basta se ABI/codegen estiver errado.

## Reentrância e concorrência

Os compiladores usam bastante estado global mutável.

ChrisC possui compiler object e buffers globais.

KCC mantém globals para preprocessing, symbols, parser e assembly.

ChrisAsm também usa buffers e fixup tables file-static.

Essas APIs não devem ser consideradas naturalmente reentrantes ou seguras para compilações independentes concorrentes sem serialização externa.

Isso é especialmente relevante porque o kernel expõe KCC por um job system.

Job assíncrono não torna automaticamente o compilador parallel-safe.

## Ownership de memória

ChrisC escreve bytecode em buffer do caller.

KCC chama ChrisAsm, que aloca payloads de sections no `ChrisoImage`.

ChrisO serialization copia esses dados para buffer do caller.

ChrisLd também escreve ELF em buffer fornecido pelo caller.

O pipeline mistura:

- compiler state estático;
- sections alocadas;
- artifact buffers do caller.

Ownership precisa ser tratado explicitamente pela orquestração.

## Evidência de validação: ChrisC

A árvore de testes cobre vários aspectos:

- arrays;
- functions;
- pointers;
- structs;
- strings;
- floats;
- includes;
- language semantics;
- Doom-related compile paths;
- applications/games.

`test_chrisc_lang.c` compila snippets e executa o bytecode no CLVM para verificar a semântica observável.

Isso é mais forte que apenas verificar se algum bytecode foi emitido.

## Fuzz smoke do ChrisC

`test_fuzz_chrisc.c` envia texto pseudo-random determinístico ao compilador.

Ele exige somente returns documentados de sucesso/falha e depois confirma que um programa válido ainda compila.

É smoke de robustez.

Não é prova formal nem fuzzing coverage-guided de segurança.

## Evidência da toolchain nativa

`test_kcc.c` compila inclusive arquivos reais de:

~~~text
kernel/metal/
~~~

e verifica:

- symbols esperados;
- BSS/rodata;
- relocations;
- struct layout;
- comportamento de volatile;
- multi-object linking com stubs.

`test_chrisasm.c` verifica encoding e relocations.

`test_chriso.c` verifica serialização básica.

`test_chrisld.c` verifica:

- ELF de um object;
- symbol resolution multi-object;
- rejeição de undefined;
- rejeição de duplicate global;
- layout R-X/R-W;
- endereçamento de BSS.

## O que os testes não demonstram ainda

Não há prova atual de:

- full ISO C compliance;
- equivalência ChrisC/KCC em source comum;
- output determinístico em todas as plataformas host;
- bootstrap fixed-point;
- concurrent compilation thread-safe;
- cobertura completa ELF/relocation;
- correctness de optimizations sobre IR formal;
- hardening contra input hostil em todos os parsers/readers.

São problemas separados.

## Limitações atuais

Na revisão documentada:

- dois compiler stacks quase independentes;
- sem frontend compartilhado;
- sem type system compartilhado;
- sem IR target-independent compartilhado;
- sem pipeline SSA;
- multi-file ChrisC monolítico, sem object/link stage;
- buffer integrado CLVM de 4 MiB apesar do formato permitir 16 MiB;
- ChrisC/KCC dependem de grandes tabelas fixas;
- ChrisC limita structured diagnostics a 8;
- KCC expõe um diagnostic corrente;
- ChrisAsm/ChrisLd têm errors majoritariamente coarse;
- buffers KCC de preprocessing/assembly são 256 KiB;
- sections do ChrisAsm são limitadas a 64 KiB cada;
- ChrisO tem limites fixos de symbols/relocations;
- ChrisLd aceita no máximo 32 objects;
- compiler internals são globais e não reentrantes;
- sem build graph incremental unificado;
- sem frontend de ELF relocatable na toolchain nativa;
- bootstrap existe, mas fixed-point/reproducibility ainda não fazem parte do validation contract.

## Fronteira de roadmap

Uma arquitetura futura pode adicionar:

- typed IR explícito onde trouxer benefício;
- interfaces separadas de frontend/semantic/backend;
- reusable optimization passes;
- separate compilation para CLVM, se necessário;
- diagnostics ricos no assembler/linker;
- compiler contexts reentrantes;
- recursos dinâmicos em vez de ceilings fixos;
- dependency-aware incremental builds;
- deterministic-build tests;
- comparação entre bootstrap stages;
- differential testing interpreter/JIT/native onde houver semântica comum;
- fuzzing por corpus e coverage;
- especificações formais do language profile de ChrisC e KCC.

Tudo isso continua roadmap até existir em source e testes reproduzíveis.

## Mapa de source e revisão

O frontend/backend ChrisC está principalmente em `compiler/chrisc/chrisc.c`, com contratos em `chrisc.h`. `compiler/lang_pipeline.c` integra compilation, filesystem, geração CLVM, guest compiler, debug maps e runtime. CLVM assembly/image está em `compiler/clvm`.

O caminho nativo está em `compiler/kcc`, `compiler/chrisasm` e `compiler/chrisld`. `ChrisoImage` é a fronteira de relocatable object. `tools/kcc_main.c` fornece o driver host e `kernel/metal/kcc_job.c` expõe compilação dentro do sistema.

Todas as afirmações sobre comportamento atual foram reconciliadas com ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
