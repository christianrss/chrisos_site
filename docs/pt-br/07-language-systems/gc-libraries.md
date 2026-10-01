---
id: gc-libraries
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/gc/gc.h
  - compiler/gc/gc.c
  - compiler/cls/cls.h
  - compiler/cls/cls.c
  - compiler/cla/cla.h
  - compiler/cla/cla.c
  - compiler/il/il.h
  - compiler/il/il.c
  - compiler/chrisc/chrisc.c
  - compiler/chrisc/chrisc.h
  - compiler/lang_pipeline.c
  - kernel/lang/clvm_sys.c
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - tools/mk_clv.c
  - tools/test_cls.c
  - tools/test_cla_gc.c
symbols:
  - gc_init
  - gc_alloc
  - gc_root_reg
  - gc_request
  - gc_poll
  - gc_collect
  - gc_type_register
  - gc_type_lookup
  - cls_parse
  - cls_write
  - cls_runtime_init
  - cls_runtime_load
  - cls_runtime_reload
  - cls_runtime_resolve
  - cls_map_proc
  - cla_parse
  - cla_load_bytes
  - cla_resolve
depends_on:
  - clvm-memory
  - clvm-syscalls
  - clvm-interpreter
  - debugger
related:
  - chrisc-clvm
  - jit
  - native-toolchain
  - resource-lifetime
  - process-lifecycle
---

# Bibliotecas, módulos e garbage collection

## Escopo

ChrisOS possui hoje vários mecanismos que podem parecer “bibliotecas” no source level, mas têm semânticas de runtime diferentes:

1. **composição de source ChrisC** por `#include` e compilação multi-file via `.LST`;
2. **runtime libraries CLS**, que empacotam CLVM code, ABI metadata, exports, imports, type descriptions e optional data;
3. **assemblies CLA**, que empacotam métodos IL verificados, referências e managed-type metadata;
4. um pequeno **garbage collector**, compartilhado pelos experimentos de runtime gerenciado e exposto ao CLVM por syscalls.

Esses mecanismos se relacionam, mas ainda não formam um único dynamic-linking system.

A composição de source é o caminho mais completo usado pelas aplicações ChrisC comuns. CLS fornece loading, ABI checks, hot-reload state e process-mapping infrastructure, porém o source atual ainda não conecta normal ChrisC calls a `cls_runtime_resolve`. CLA fornece container de IL e verifier, mas também é camada experimental de managed runtime, não o formato normal de execução das aplicações.

O garbage collector funciona para host roots explicitamente registrados e grafos simples, mas a integração CLVM atual ainda não fornece um managed root set completo.

![Camadas de libraries e GC](../../assets/diagrams/gc-libraries-pt-br.svg)

## Bibliotecas de source em compile time

O modelo comum de bibliotecas ChrisC começa antes do runtime.

Aplicações podem incluir source/header files:

    #include "LIB/STDIO.H"
    #include "LIB/STR.CC"

O preprocessing/expansion path do compiler lê includes usando o `ChriscReadFn` configurado.

No ChrisOS, `lang_pipeline.c` fornece `chrisc_fs_read`, então includes são resolvidos pelo filesystem do sistema.

O compiler acompanha source files incluídos para diagnostics/source maps e limita nesting com:

    INCLUDE_DEPTH = 16

Também existem include cache e tracking de `#pragma once`.

Esse caminho é source composition. Não cria runtime library handle.

## Compilação multi-file

Arquivo `.LST` contém uma lista de translation-unit paths.

`lang_compile_list` lê os paths e chama `chrisc_compile_files_ex`.

A ferramenta host `mk_clv` usa o mesmo modelo geral.

Com múltiplos inputs ChrisC, o compiler analisa declarations dos units listados e emite uma única CLVM image.

Na prática:

    vários .CC/.H
        -> um compiler state
        -> uma CLVM code image

Não há runtime relocation desses source files depois que o CLV é construído.

## Metadata de ABI do ChrisC

ChrisC carrega uma versão simples de library ABI:

    abi_major
    abi_minor

O default é:

    1.0

e source pode configurar ABI por pragma suportado, como em `LIB/WIN.CC`:

    #pragma abi(1, 0)

O `ChrisResult` emitido também contém export metadata.

Na revisão atual, cada função definida com body e entry PC pode virar export record, até 64 entries.

Para cada exported function o compiler registra:

- name;
- bytecode PC;
- argument count.

Ainda não existe source-level visibility system em que apenas funções explicitamente marcadas sejam exports CLS.

## CLS: runtime library image

CLS é o container atual de runtime libraries.

Magic:

    "CLS\0"

Um `ClsImage` contém:

- library name;
- ABI major/minor;
- exports;
- imports;
- managed-type metadata;
- code section;
- data section.

Limites fixos:

    CLS_MAX_EXPORTS = 64
    CLS_MAX_IMPORTS = 32
    CLS_MAX_TYPES   = 32
    CLS_MAX_LIBS    = 16
    CLS_MAX_CODE    = 512 KiB

Parser on-disk valida table counts e garante que code+data caibam no arquivo fornecido.

## Exports CLS

Cada `ClsExport` armazena:

    name
    sym_ver
    argc
    pc
    flags

`cls_find_export` procura name exato.

Requested symbol version zero funciona como wildcard; nos demais casos `sym_ver` precisa coincidir.

Runtime mantém `tramp[]` por loaded library.

Em load/reload copia cada export PC para esse array.

Apesar do nome, atualmente são integer PC entries, não executable trampoline stubs gerados.

## Imports CLS

Cada import descreve:

    library name
    symbol name
    required ABI major
    required ABI minor
    symbol version

Antes de aceitar nova CLS image, `check_imports` exige que cada referenced library já esteja carregada.

Regra de compatibility:

    have_major == need_major
    have_minor >= need_minor

Depois o export e symbol version solicitados precisam existir.

É uma validação útil em load time.

Mas validação não significa linking.

O loader atual não patcha CLVM call sites a partir da import table, e a busca no repository mostra `cls_runtime_resolve` sem call site fora da própria definição/declaration.

Assim imports são hoje validated metadata, não dynamic-link executable path completo para normal ChrisC calls.

## Criação de CLS

`tools/mk_clv.c` consegue compilar `.LST` como CLS:

    mk_clv LIB/WIN.LST --cls LIB/WIN

Primeiro compila ChrisC e depois transfere exports do `ChrisResult` para `ClsImage`.

O writer atual define:

- library ABI a partir de ChrisResult;
- compiled CLVM bytes como code;
- symbol version 1 para cada export;
- argument count vindo do compiler;
- export PC do bytecode gerado.

O `write_cls` atual não preenche imports, managed types nem data a partir de source metadata ChrisC.

Os campos existem no formato/runtime, mas ainda não são gerados pelo build path comum.

## Loading de CLS libraries

`cls_runtime_load` lê o arquivo inteiro e passa para internal load path.

Novo load:

1. parseia CLS image;
2. rejeita code > CLS_MAX_CODE;
3. valida imports contra libraries já carregadas;
4. rejeita duplicate library name;
5. aloca/copia code buffer;
6. aloca/copia data;
7. instala metadata da image;
8. popula export PC entries;
9. atribui/registra managed-type IDs;
10. incrementa loaded-library count.

Runtime table é global.

Library IDs são slots da tabela fixa de 16 entries.

## Hot reload

`cls_runtime_reload` parseia a image nova primeiro e procura library existente pelo embedded library name.

Se não existir, reload funciona como new load.

Para library existente, ABI major deve permanecer igual.

Code storage é reutilizado quando a allocation antiga tem capacidade suficiente; caso contrário é alocado fresh code storage.

Se code allocation mudar em freestanding build, runtime tenta remapear CLS libraries em cada live process antes de liberar old code buffer.

## Preservação de data em reload

CLS reload possui regra intencional de state preservation.

Data storage antigo é preservado quando:

- data size não muda;
- ABI major não muda;
- novo ABI minor não retrocede.

Se size mudar ou novo minor for menor que old minor, old data buffer é descartado e fresh buffer é inicializado pela image.

É política simples de hot-reload state.

Não há schema migration.

Estrutura de mesmo tamanho pode ser semanticamente incompatível mesmo com ABI metadata permitindo preservação.

## Type metadata e gap no reload

Nova library recebe faixa contígua de type IDs iniciada em `g_next_type_base`.

Cada CLS type possui:

    name
    size
    gc_bits

Descriptors são registrados no GC.

Porém `install_types` só é chamado em new load.

No reload, loader atual atualiza `L->img`, mas não registra novamente os type descriptions.

Alterar type size, `gc_bits`, count ou order durante reload pode portanto deixar GC registry descrevendo a image anterior.

Major-version check sozinho não impede isso.

Hot reload deveria congelar type layout durante a vida do library ID ou reconciliar atomicamente a GC type table.

## Process mapping

`cls_map_proc` mapeia loaded library code em cada process começando em:

    PROC_LIB_VIRT = 0x08000000

Cada library recebe virtual window de um MiB baseado no slot.

Data é copiada para segunda região oito MiB acima de PROC_LIB_VIRT.

Code mapping usa `proc_map_user(..., MM_PRESENT)`.

`proc_map_user` adiciona MM_USER automaticamente.

MM_WRITE não é solicitado para code pages e MM_NX também não, então a intenção do page-table policy é user-readable/executable e não writable.

Data page é criada pelo normal process commit path e é writable.

## Ceiling de 32 KiB no process mapping

Existe mismatch entre CLS image limits e process mapping.

CLS aceita:

    CLS_MAX_CODE = 512 KiB

mas `cls_map_proc` calcula pages e depois aplica:

    if (pages > 8)
        pages = 8

Oito páginas de 4 KiB mapeiam apenas 32 KiB.

Logo CLS válida maior que aproximadamente 32 KiB pode ser aceita e armazenada pelo runtime, mas somente a primeira parte fica mapped em process por esse path.

É integration limit concreto.

Mapping deveria cobrir toda code section validada ou CLS_MAX_CODE deveria refletir o executable mapping limit real.

## Gap de validação do export PC

`cls_parse` valida framing das tabelas, mas não verifica se cada export PC é menor que `code_size`.

`cls_runtime_resolve` pode portanto devolver export PC fora da loaded code section se arquivo malformado porém estruturalmente válido fornecer esse valor.

Como ordinary call binding ainda não usa esse resolver, não é atualmente primary execution path, mas deve ser validado no load.

Future linker/call bridge não pode confiar em export PC apenas porque CLS parseou corretamente.

## Fronteira atual de dynamic calls

Runtime expõe:

    cls_runtime_resolve(lib, name, sym_ver, &pc, &lib_id)

mas o source atual não possui consumer desse resolver.

CLVM syscall surface expõe `lib_load` e `lib_reload`, devolvendo library ID, porém não existe general `lib_resolve` ou `lib_call` builtin correspondente.

Portanto CLS atualmente fornece:

- loading;
- ABI/dependency validation;
- metadata;
- process mapping;
- reload bookkeeping;

mas não source-to-runtime dynamic function call ABI completo.

Essa distinção é essencial ao descrever o estado atual.

## Managed assemblies CLA

CLA é formato separado de assembly para IL-oriented runtime experiments.

Um `ClaImage` pode conter:

- até 64 methods;
- até 32 types;
- até 8 assembly references;
- IL byte stream;
- assembly name/version metadata.

Até oito CLA images podem ser carregadas globalmente:

    CLA_MAX_ASM = 8

Cada loaded assembly recebe private 64-KiB IL storage buffer.

## Verificação CLA

`cla_load_bytes` parseia image e verifica cada method antes de aceitar.

Para cada method:

    rva + size <= il_size

precisa valer.

Depois `il_verify` verifica IL conforme signature do method.

Assembly references precisam resolver em assemblies já loaded.

Isso se aproxima mais de managed module loader porque verifica per-method IL structure antes de instalação.

Builtin CLVM `cla_load` lê arquivo para bounded temporary buffer e chama `cla_load_bytes`.

## Ordem de dependencies em CLA

CLA reference resolution depende da load order.

Ao carregar image com refs, `cla_resolve` procura apenas assemblies já presentes na global table.

Não há recursive dependency loader.

Caller deve carregar dependencies antes dos dependents.

A mesma policy geral aparece hoje em CLS imports.

## Arquitetura do garbage collector

GC é um stop-the-world mark/sweep compacto com pequena nursery optimization.

Limites globais:

    GC_MAX     = 4096 objects
    GC_NURSERY = 65536 bytes
    roots      = 256 slots
    types      = 256 descriptors

Cada object record guarda:

    type_id
    size
    marked
    nurs
    payload

Object metadata fica em fixed global table.

Payload usa:

- static nursery para small allocations;
- ou heap allocation via malloc/kmalloc.

## Allocation

`gc_alloc(type_id, size)` transforma request zero em oito bytes.

Se registered type metadata declarar size maior, type size prevalece.

Small objects de até 256 bytes usam nursery enquanto houver espaço.

Demais objects usam backing allocator.

Novo payload é zerado.

Quando object table atinge GC_MAX, allocation executa collection e tenta liberar table capacity.

Nursery exhaustion isolada não dispara collection.

Quando os 64 KiB se esgotam, novos small objects passam para normal heap enquanto ainda houver object-table capacity.

## Roots

Roots são host slots explícitos.

`gc_root_reg(void **slot)` registra o endereço de uma pointer variable.

Durante collection, collector lê current pointer de cada slot e marca se ele for exatamente igual ao payload address de managed object.

Root portanto não é apenas object pointer; é endereço de variável que pode ser atualizada quando object muda.

Root table suporta 256 entries.

Não existe root-unregister API.

## Integração atual de roots é incompleta

Na revisão documentada, repository search encontra implementação/declaration de `gc_root_reg`, mas o uso efetivo aparece apenas em `tools/test_cla_gc.c`.

CLVM operand stack, CLVM guest memory, ChrisC globals, process stacks e TLS não são registrados/varridos como GC roots por `gc_collect`.

Isso afeta diretamente builtin CLVM `gc_alloc`.

Syscall ID 70 aloca pelo GC e devolve o **native pointer value** como integer ao guest.

Se guest guardar esse valor em CLVM memory ou mantê-lo na operand stack, collector não reconhece esses locais como roots.

Um `gc_collect` explícito pode portanto reclaim object mesmo com guest code ainda guardando pointer-like value.

A integração atual não deve ser descrita como managed-memory system completo para programas CLVM.

## Mismatch de pointer domains

GC devolve native host/kernel addresses.

Ordinary CLVM LOAD/STORE espera guest offsets dentro de `vm->memory`.

Resultado de `gc_alloc` não é intercambiável com CLVM `malloc`.

Esse mismatch também aparece nos capítulos memory/syscalls e é especialmente importante aqui: antes mesmo de resolver root tracking, managed references precisam de address representation definido que CLVM consiga consumir com segurança.

## Type-guided marking

GC type metadata possui mask de 32 bits `gc_bits`.

Bit N indica que pointer-sized field N deve ser tratado como managed reference.

Quando metadata existe e `gc_bits != 0`, marker inspeciona apenas esses slots.

Caso contrário, collector faz conservative scan de cada pointer-sized position do payload.

Candidate conta como reference apenas se for exatamente igual ao payload start de object atual no object table.

Interior pointers não são reconhecidos.

## Complexidade do marking

`is_ptr` faz linear scan de todos live objects.

Cada candidate field pode portanto custar O(N).

Com F candidate pointer fields, traversal pode chegar próximo de:

    O(F * N)

com N <= 4096.

Para experimental heap pequeno o algoritmo é simples, mas não escala como hash table, address-ordered tree ou page metadata lookup.

## Nursery promotion

Durante collection, marked nursery object é copiado para fresh normal heap allocation.

Registered root slots apontando diretamente para old nursery address são atualizados.

Object record é mantido com:

    nurs = 0

Depois do sweep, nursery allocation cursor volta a zero.

É copying promotion combinado com mark/sweep para non-nursery objects.

## Falta de reference rewriting na promotion

Promotion atual atualiza apenas explicit root slots.

Não reescreve managed references guardadas dentro de outros marked objects.

Considere:

    root -> object A -> nursery object B

Marker encontra B por meio de A.

No sweep B é promovido para nova allocation.

Root não aponta diretamente para B, então não é atualizado.

Field de A continua com old nursery address de B.

Depois:

    g_nused = 0

permite reutilizar nursery.

O graph fica com stale reference.

É correctness gap importante no moving-nursery design.

Promotion precisa de forwarding map + pointer-rewrite pass sobre roots e live objects, ou nursery objects precisam permanecer non-moving até existir relocation algorithm completo.

## OOM durante promotion

Se allocation do promoted storage falhar, collection atual executa `continue` para aquele marked nursery object.

Object não é preservado no compacted live prefix e root ainda pode apontar para nursery.

Mesmo assim nursery cursor é resetado.

Logo OOM na promotion pode invalidar live object silenciosamente em vez de produzir controlled collection failure.

Collector usado como safety boundary precisa de failure policy explícita.

## Triggers de collection

Há três conceitos:

1. `gc_collect()` direto;
2. deferred request por `gc_request()` + `gc_poll()`;
3. automatic collection ao atingir GC_MAX.

ChrisOS instala `lang_safepoint` como VM safepoint callback; ela chama `gc_poll`.

JIT preserva safepoint callback path.

Porém repository search não encontra current caller de `gc_request()` fora do próprio GC.

Assim normal safepoints consultam flag que não é normalmente setado.

Eles não criam periodic collection por si só.

Active automatic pressure trigger é object-table exhaustion, além de calls explícitas a `gc_collect`.

## Safepoints e stop-the-world

Global GC tables não possuem internal locking.

Collection modifica:

- object records;
- root pointers;
- nursery state;
- type metadata indiretamente via library lifecycle.

Design assume coordinated execution, não concurrent marking com mutators.

Safepoints oferecem lugar natural para future stop-the-world coordination, mas `gc_poll` atual é apenas request check.

Não existe multi-thread handshake provando que todas CLVM threads/kernel mutators pararam antes da collection.

## Lifetime da root table

Como roots não podem ser unregister, registro é efetivamente permanente até `gc_init`.

Registrar endereço de short-lived stack variable seria inseguro depois de o stack frame desaparecer.

O teste existente mantém root variable viva durante collection.

Production API precisa de:

- scoped root registration/unregistration;
- handles;
- shadow stacks;
- compiler-generated stack maps;
- ou conservative scan de stable root region.

## Inicialização global

`gc_init` reseta objects, roots, nursery usage, requests e type metadata.

`cls_runtime_init` libera CLS code/data buffers, reseta library table, type-base allocation e chama `gc_type_clear`.

Não chama `gc_init`.

No startup normal, zero-initialized GC globals deixam estado inicial utilizável, mas as duas reset APIs possuem semânticas diferentes.

Chamar `cls_runtime_init` com managed objects vivos apagaria type metadata sem limpar objects/root registrations.

Essa lifecycle dependency precisa ficar explícita caso runtime reinitialization vire operação suportada.

## CLS e GC type IDs

Cada nova CLS library recebe:

    type_base = g_next_type_base

Types recebem IDs consecutivos:

    type_base + 0
    type_base + 1
    ...

Global base avança pelo número de types, ou pelo menos um quando library não declara types.

Isso evita colisão normal de type IDs entre new libraries durante runtime session.

Não há reclamation/reuse dos ranges porque libraries não são unloaded individualmente.

## Ausência de library unload

Public runtime oferece load, reload, find, get, resolve, map e count.

Não existe `cls_runtime_unload`.

Libraries vivem até `cls_runtime_init`.

Isso simplifica pointer/ID stability, mas significa:

- slots não podem ser recuperados individualmente;
- code/data lifetime é runtime-wide;
- type-ID ranges não retornam;
- dependency lifetime não pode ser expresso.

Com apenas 16 slots, workflows de dynamic loading prolongados podem esgotar a table.

## Security e trust boundary

CLS/CLA podem vir do filesystem e exigem defensive parsing.

Pontos positivos atuais:

- fixed table-count limits;
- complete file-length checks para framing;
- code-size limit;
- ABI/dependency checks;
- IL verification para CLA methods;
- bounded syscall path copies.

Gaps relevantes:

- CLS export PCs não validados contra code_size;
- ausência de cryptographic authenticity/signature model;
- ausência de complete import relocation/call verifier;
- somente primeiras oito code pages mapped por process;
- runtime structures globais sem forte isolation por application;
- GC native pointers não formam safe CLVM reference model;
- moving nursery não reescreve object-to-object references.

## Evidência de validação

`tools/test_cls.c` verifica:

- round trip de CLS write/parse;
- comportamento de ABI-major compatibility;
- runtime load/reload quando temp path existe;
- integração com GC type registration.

`tools/test_cla_gc.c` verifica:

- IL verification de método pequeno;
- GC allocation;
- root registration;
- sobrevivência de rooted object em collection;
- reclamation depois de limpar root;
- CLA write/load;
- basic assembly reference resolution.

ChrisC include e multi-file behavior também são cobertos por testes dedicados de include/apps/compiler.

Os testes estabelecem comportamento útil de componentes, mas não cobrem todos integration gaps identificados.

## Focused tests ausentes

Adições de alto valor:

- graph root -> A -> nursery B sobrevivendo promotion com field de A reescrito;
- promotion allocation failure;
- CLVM-held GC reference atravessando explicit collection;
- root registration lifetime/unregistration;
- GC com 256 roots e 4096 objects;
- rejection de CLS export PC >= code_size;
- CLS mapping com code > 32 KiB;
- hot reload alterando type size/gc_bits;
- hot reload preservando data com increasing ABI minor;
- import resolution seguido por executable cross-library call real;
- exhaustion/recovery dos 16 library slots;
- concurrent/multi-thread safepoint collection.

## Limitações atuais

Na revisão documentada:

- compile-time includes/`.LST` estão mais completos que runtime linking;
- toda defined ChrisC function pode virar CLS export;
- ordinary `mk_clv --cls` não preenche imports, types nem data;
- CLS valida imports mas não patcha normal ChrisC call sites;
- `cls_runtime_resolve` não possui consumer atual;
- CLS não tem unload individual;
- CLS aceita até 512 KiB de code, mas process mapping limita a oito pages/32 KiB;
- export PCs não são validados contra code section;
- reload não atualiza GC type metadata registrado;
- GC roots são explicit host pointer slots e production CLVM roots não estão integrados;
- GC references usam native pointers, não CLVM guest offsets;
- nursery promotion atualiza roots, mas não references em live objects;
- promotion OOM não possui safe recovery;
- `gc_request` não tem caller ativo, então safepoint polling não agenda normal collections;
- root registrations não podem ser removidos;
- GC metadata/runtime tables são globais e sem collector-level locks;
- CLA dependency resolution é ordered e non-recursive.

## Fronteira de roadmap

Runtime futuro coerente pode unificar esses componentes em um module contract:

    source/interface metadata
        -> versioned module image
        -> verified imports/exports/types
        -> stable call indirection
        -> process mapping
        -> managed root metadata
        -> hot reload / unload

Passos úteis:

- gerar explicit export/import/type metadata a partir de ChrisC;
- adicionar verified cross-library call stubs ou resolver opcode;
- validar todos CLS export PCs/call targets;
- mapear toda accepted code section com explicit RX permissions;
- adicionar unload com dependency/type-lifetime rules;
- preservar/reconciliar GC type metadata no reload;
- introduzir managed-reference representation real para CLVM;
- usar compiler stack maps ou VM stack scanning para roots;
- adicionar scoped root handles;
- implementar forwarding e object-field rewriting na nursery promotion;
- definir collection failure behavior;
- adicionar stop-the-world coordination para CLVM threads;
- conectar allocation pressure a `gc_request`/safepoints.

São future directions até existirem no source e testes.

## Mapa de source e revisão

`compiler/gc/gc.c` e `gc.h` implementam object table, nursery, root table, type registry e collection algorithm.

`compiler/cls/cls.c` e `cls.h` implementam CLS image versionada, dependency checks, load/reload runtime, process mapping e GC type registration.

`compiler/cla/cla.c` e `cla.h` implementam IL assembly image e load-time method/reference validation.

`compiler/il/il.c` e `il.h` fornecem CLA method verification.

`compiler/chrisc/chrisc.c` e `chrisc.h` implementam include expansion, multi-file compilation, ABI metadata e export collection.

`compiler/lang_pipeline.c` conecta source compilation, CLS initialization, process mapping e GC safepoint polling.

`kernel/lang/clvm_sys.c` expõe `gc_alloc`, `gc_collect`, `cla_load`, `lib_load` e `lib_reload` a programas CLVM.

`tools/mk_clv.c`, `tools/test_cls.c` e `tools/test_cla_gc.c` fornecem as principais evidências de build/test desses runtime layers.

Todas as afirmações de comportamento atual deste capítulo foram reconciliadas com ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
