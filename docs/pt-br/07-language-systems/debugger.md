---
id: debugger
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/debug/cdbg.h
  - compiler/debug/cdbg.c
  - compiler/debug/dbg_session.h
  - compiler/debug/dbg_session.c
  - compiler/chrisc/chrisc.h
  - compiler/lang_pipeline.c
  - compiler/lang_pipeline.h
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
  - kernel/lang/clvm_sys.c
  - APPS/EDITOR/EDITOR.CC
  - tools/test_cdbg.c
  - tools/test_dbg_step.c
  - tools/test_editor_vi.c
symbols:
  - CdbgImage
  - cdbg_encode
  - cdbg_decode
  - cdbg_from_result
  - cdbg_line_at
  - cdbg_func_at
  - cdbg_parse_map_line
  - DbgSession
  - dbg_session_create
  - dbg_session_add_break
  - dbg_session_resolve
  - dbg_session_add_watch
  - dbg_step_should_pause
  - lang_write_map
  - lang_load_map
  - lang_begin_step
  - lang_debug_step
  - lang_debug_step_over
  - lang_debug_step_out
  - lang_debug_continue
  - lang_bp_toggle_line
  - lang_debug_ctl
  - lang_debug_text
depends_on:
  - clvm-interpreter
  - jit
  - chrisc-clvm
related:
  - clvm-syscalls
  - calling-conventions
  - process-lifecycle
  - native-toolchain
---

# Debugger, source maps e controle de execução

## Escopo

ChrisOS possui um source-level debugger para aplicações ChrisC/CLVM, integrado ao Editor e ao language runtime.

Não é um hardware debugger convencional. Ele não programa x86 debug registers, não injeta INT3 em native code e não usa ptrace. Seu target principal é uma instância de ClvmVm.

O caminho atualmente usado é:

    ChrisC compiler
        -> source/PC map
        -> sidecar .MAP
        -> estado de debug do LangSlot
        -> interpreter single-step
        -> UI do Editor via dbg_ctl / dbg_text

Existe também uma segunda arquitetura, mais estruturada:

    ChrisResult
        -> metadata binária .CDBG
        -> CdbgImage
        -> DbgSession

Na revisão documentada, essa segunda camada está implementada e possui unit tests, mas ainda não é o mecanismo de metadata/session utilizado pelo debugger ao vivo de lang_pipeline.

![Arquitetura do debugger do ChrisOS](../../assets/diagrams/debugger-pt-br.svg)

Essa divisão é o principal ponto para compreender o estado atual: o repository já contém uma base de debugger orientado a sessões, enquanto o fluxo de produção do Editor ainda opera sobre estruturas globais/per-slot anteriores.

## Por que debug força o interpreter

Aplicações CLVM normalmente preferem JIT quando disponível.

No debug launch, Editor habilita g_want_debug por dbg_ctl e depois chama compilation e sys_run.

lang_run_internal observa g_want_debug e não seleciona JIT.

O slot criado recebe:

    debug_on = g_want_debug
    paused   = g_want_debug

Depois o Editor limpa o global launch flag.

Logo g_want_debug é policy de launch; LangSlot.debug_on é estado persistente do target criado.

O target permanece executando pelo interpreter enquanto está em debug.

Isso é necessário porque breakpoints e line stepping usam clvm_step com budget de uma instruction.

## Sequência de debug launch

do_debug no Editor executa aproximadamente:

1. salva source dirty;
2. ativa debugger launch mode com dbg_ctl(1, 1);
3. compila o arquivo;
4. deriva output .CLV;
5. chama sys_run;
6. limpa global debugger-launch flag;
7. marca UI como debugging;
8. consulta source line atual e segue até ela.

Target application inicia pausada.

Editor é outra CLVM application e controla o target via debug syscalls, sem acesso direto à estrutura ClvmVm do alvo.

## ABI do debugger para guest

Builtin table do ChrisC expõe:

    dbg_ctl(op, arg)  -> syscall 250
    dbg_text(kind, dst) -> syscall 251

Ambos retornam integer.

dbg_ctl é multiplexed numeric control API.

Operações:

| op | Operação |
|---:|---|
| 0 | consulta se algum slot está pausado |
| 1 | configura debugger launch mode |
| 2 | step into |
| 3 | step over |
| 4 | step out |
| 5 | continue |
| 6 | detach |
| 7 | toggle source-line breakpoint |
| 8 | define memory-watch base address |
| 9 | PC atual |
| 10 | source line atual |
| 11 | operand-stack depth |
| 12 | stack value por depth |
| 13 | return PC por call depth |
| 14 | lê 32-bit guest memory |
| 15 | lê um guest byte |
| 16 | recent syscall ID |
| 17 | indica process fault registrado |
| 18 | RIP/PC do fault registrado |
| 19 | guest-memory size |
| 20 | watch address atual |

Não há typed enum compartilhado com guest ChrisC nem debugger ABI version negotiation.

O significado desses códigos é portanto definido diretamente pela implementação.

## ABI textual

dbg_text pede um pequeno registro textual formatado.

Kinds atuais:

| kind | Texto |
|---:|---|
| 0 | line, PC, function, stack depth, breakpoint count e state |
| 1 | valores do topo da stack |
| 2 | primeira watched-memory hex row |
| 3 | segunda watched-memory hex row |
| 4 | pending breakpoint line numbers |
| 5 | recent syscall IDs |
| 6 | summary do último process fault |

Kernel usa temporary buffer de 96 bytes.

ABI recebe apenas kind e destination address; não recebe destination capacity.

vm_copy_out garante que range final está dentro da guest memory, mas não sabe o tamanho do objeto guest indicado pelo caller.

ABI futura deve incluir capacity explícita.

## Geração de source maps

ChrisC grava source mapping em ChrisResult.

Limites:

    CHRIS_MAP_MAX  = 8192
    CHRIS_FILE_MAX = 32

Cada ChrisMapEnt contém:

    pc
    line
    file_id

ChrisResult também carrega até 64 exported function names, entry PCs e argument counts.

lang_write_map emite arquivo textual .MAP ao lado da CLV.

Line records:

    0x<pc> <line> <file_id>

Function records:

    F <name> <pc>

Assim file ID existe no metadata gerado.

## Ingestão de .MAP no runtime

lang_load_map lê sidecar textual em:

    char buf[8192]

e chama fs_read com no máximo sizeof(buf) - 1 bytes.

O live debugger consegue portanto ingerir no máximo 8191 bytes de map text por programa.

Isso fica muito abaixo da capacidade teórica CHRIS_MAP_MAX para programas maiores.

Map grande passa a ser representado somente pelo prefix que cabe no buffer.

Slot então armazena entries em:

    map_pc[CHRIS_MAP_MAX]
    map_line[CHRIS_MAP_MAX]
    map_file[CHRIS_MAP_MAX]

mas o input buffer é o limitante real anterior.

Source lines posteriores podem ficar indisponíveis para breakpoint/stepping mesmo tendo sido geradas pelo compiler.

## Limites de function names

Live LangSlot mantém:

    fn_name[16][24]
    fn_pc[16]

Apenas 16 function records são carregados do .MAP.

Names são truncados para 23 chars mais NUL.

ChrisResult, porém, suporta 64 functions com names de até 31 chars, e CDBG_FUNCS é 64.

O live debugger tem portanto visão de symbols menor que compiler output e structured CDBG design.

## Lookup de PC para line

lang_line_at percorre source-map entries em ordem de PC e mantém a entry mais recente com:

    map_pc[i] <= pc

Interrompe ao primeiro PC posterior.

Complexity O(n) por lookup em relação às loaded map entries.

Line stepping chama isso repetidamente após individual VM instructions.

Em maps maiores, o custo pode ser relevante.

Binary search reduziria para O(log n); cache/index poderia tornar sequential stepping próximo de O(1).

## File IDs são carregados mas ignorados

map_file é preenchido por lang_load_map.

Entretanto line lookup, stepping e breakpoints principais tomam decisões apenas pelo número de line.

lang_line_at retorna somente uint16_t line.

lang_begin_step guarda apenas last_line.

lang_arm_line procura:

    map_line[i] == requested_line

e usa o primeiro match.

file_id é ignorado.

Programas multi-file podem portanto ter source locations ambíguas.

Line 20 em SRC/MAIN.CC e line 20 em LIB/UTIL.CC são locations distintas, mas pending breakpoint 20 não representa essa diferença.

É exatamente um problema que o tipo estruturado DbgBreak já evita ao possuir file_id + line.

## Representação de breakpoints no debugger ao vivo

Cada LangSlot contém:

    uint32_t breakpoints[32]
    int nbreak

São bytecode PCs resolvidos.

Pending global set contém:

    int g_pend_line[32]
    int g_pend_n

Pending breakpoints guardam somente source line.

Quando target de debug inicia, cada line pendente é resolvida por lang_arm_line.

lang_arm_line escolhe o primeiro source-map PC da line e insere no breakpoint array.

Se uma source line corresponde a múltiplos bytecode ranges, somente o primeiro PC é armado.

## Verificação de breakpoint

Antes de executar o target em lang_tick, debugger percorre linearmente os breakpoint PCs ativos.

Quando algum é igual a vm.pc:

    paused = 1
    step_one = 0
    step_line = 0
    step_mode = NONE

e ordinary execution é pulada.

Custo O(B), B <= 32.

Com limite pequeno, é adequado.

Nenhum bytecode patch é necessário; target code permanece immutable.

## Re-hit ao usar continue

Persistent breakpoint possui uma limitação concreta.

Suponha target parado em:

    vm.pc == breakpoint_pc

lang_debug_continue limpa paused, mas não move pc, não desabilita temporariamente o breakpoint e não grava ignore-once token.

No próximo lang_tick, pre-execution breakpoint scan encontra o mesmo pc e pausa novamente antes de executar a instruction.

Assim plain continue pode imediatamente re-hit o breakpoint atual.

Step consegue escapar porque step_line permanece setado e permite entrada no stepping path mesmo após breakpoint scan marcar paused.

Debugger completo precisa de um mecanismo padrão:

- suprimir breakpoint atual por uma instruction;
- executar uma instruction e rearmar;
- ou representar ignore-once PC.

## Step modes

dbg_step_should_pause define três policies.

Step in:

    pause quando line != start_line

Step over:

    pause quando depth <= start_depth
    e line != start_line

Step out:

    pause quando depth < start_depth

Depth é ClvmVm.csp, stack de return PCs da CLVM.

Isso mantém implementação compacta e relaciona over/out às source function calls implementadas pela VM call stack.

## Loop de stepping

lang_begin_step captura:

    last_line
    step_mode
    step_depth

e despausa todos os slots debug_on.

lang_tick então chama interpreter com budget 1 repetidamente.

Limites:

    step in:   512 instructions
    over/out: 8192 instructions

Após o loop, slot é pausado incondicionalmente.

Um step pode portanto parar porque:

- source/depth condition foi satisfeita;
- VM halted;
- VM faulted;
- ou instruction limit foi esgotado.

UI não informa hoje qual razão causou a pausa.

## WAIT durante stepping

Stepping loop interrompe explicitamente apenas em HALT ou FAULT antes de testar source/depth.

CLVM_STEP_YIELD não encerra imediatamente o loop.

Se uma stepped instruction deixa VM em WAITING, chamadas posteriores de clvm_step retornam YIELD sem source progress.

Loop pode consumir 512/8192 iterações restantes e só então pausar target.

É bounded, mas não é scheduler-aware asynchronous stepping.

Implementação futura deve manter step request pendente e retomá-lo quando target acordar.

## Controle global versus per-target

Algumas operações percorrem todos os debug_on slots:

- step;
- step over;
- step out;
- continue;
- detach.

Inspection APIs como lang_debug_pc, lang_debug_stack, lang_debug_mem e lang_debug_fn normalmente escolhem o primeiro debug_on slot.

O live debugger funciona portanto como um global debugging context, apesar de múltiplos LangSlot poderem tecnicamente ter debug_on.

dbg_ctl não expõe stable target/session ID.

Aqui DbgSession está arquiteturalmente à frente do fluxo ligado ao Editor.

## Subsistema DbgSession

compiler/debug/dbg_session.c implementa abstraction separada de session.

Limites:

    DBG_SESSION_MAX = 8
    DBG_BREAK_MAX   = 32
    DBG_WATCH_MAX   = 8

Cada DbgSession registra:

- owner;
- target slot;
- debugger state;
- step state;
- breakpoints;
- watch records;
- fault type/fault PC.

Access control:

    caller < 0 -> kernel
    caller >= 0 -> caller deve ser session owner

É uma base adequada para future multi-client debugger.

## Structured breakpoints

DbgBreak contém:

    file_id
    line
    pc
    used
    enabled
    temporary
    resolved

dbg_session_resolve compara file_id e line com DbgMapRef array.

Isso resolve a ambiguidade de arquivos do live g_pend_line.

Temporary breakpoint é removido automaticamente ao hit em dbg_session_on_pc.

Persistent breakpoint continua ativo.

O live lang_pipeline debugger ainda não chama essas DbgSession functions.

Na revisão atual são um subsystem testado aguardando integração, não session manager efetivamente usado pelo Editor.

## Watch records versus live watch

DbgSession suporta oito watches tipados:

    DBG_WATCH_MEM
    DBG_WATCH_INT
    DBG_WATCH_FLOAT
    DBG_WATCH_PTR

Live debugger não utiliza essa watch table.

LangSlot possui apenas:

    uint32_t watch

e dbg_ctl op 8 grava address.

dbg_text kinds 2/3 mostram duas rows de oito bytes a partir desse base address.

Não há memory-write interception.

O "watch" atual do Editor é memory viewer base address, não watchpoint capaz de pausar em change/write.

## Leitura de guest memory

lang_debug_bytes/lang_debug_mem mudam para target process address space quando user_ram está ativo.

Depois leem vm.memory.

lang_debug_bytes:

- rejeita target/destination inexistente ou length <= 0;
- rejeita start address fora da memory;
- limita read que cruza end;
- restaura process context anterior.

lang_debug_mem lê quatro bytes, mas retorna zero tanto para invalid access quanto para legitimate zero value.

dbg_ctl op 15 é menos ambíguo para um byte porque retorna -1 quando não pode ler.

Typed debugger API deveria separar status e value.

## Inspeção de operand/call stack

lang_debug_stack indexa a partir do topo:

    index 0 -> top of stack

Out-of-range retorna zero.

lang_debug_call faz equivalente sobre most recent return PC em vm.calls.

Novamente zero pode ser dado válido/sentinel e invalid-access return.

API prioriza compactness sobre explicit result/status pair.

## Function lookup

lang_debug_fn percorre function-start table e escolhe greatest start <= pc.

Não possui/testa function end.

PC após uma função e antes do próximo known start ainda recebe o nome anterior.

Como existem somente 16 live function records, functions posteriores podem estar totalmente ausentes.

CdbgFunc estruturado já possui start/end e é mais adequado para lookup preciso.

## Formato binário CDBG

Structured CDBG sidecar começa com header de 28 bytes contendo:

    magic "CDBG"
    version
    ABI major/minor
    flags/reserved
    executable hash
    source hash
    file count
    line count
    function count
    reserved

Depois serializa file records, line intervals e function records.

Limites em cdbg.h:

    CDBG_FILES = 32
    CDBG_LINES = 256
    CDBG_FUNCS = 64
    CDBG_PATH  = 96
    CDBG_NAME  = 32

Representação é little-endian por helpers put_u16/put_u32 explícitos.

## CDBG line records

Cada CdbgLine:

    pc_start
    pc_end
    file_id
    line
    column

cdbg_from_result constrói pc_end pelo próximo source-map entry ou code_end no último.

É representação mais rica, capaz de expressar source intervals.

Porém cdbg_line_at escolhe a última entry com:

    pc_start <= pc

e não verifica pc < pc_end.

Para generated contiguous intervals normalmente funciona.

Em CDBG com gaps, PC no gap pode ser atribuído à line anterior.

## Mismatch de count entre generator e decoder

Existe incompatibilidade concreta.

cdbg_decode rejeita:

    nlines > CDBG_LINES

com CDBG_LINES = 256.

Mas cdbg_from_result define:

    lines = result->map_n

e limita somente a 65535, não CDBG_LINES.

Depois serializa todas essas records.

Assim cdbg_from_result pode produzir sidecar CDBG com mais de 256 lines que cdbg_decode se recusa a carregar.

Programas reais com mais de 256 source-map entries podem produzir structured debug metadata internamente incompatível.

Generator e decoder precisam compartilhar uma capacity rule adequada a maps reais.

## Hashes CDBG são zero no publication path atual

CdbgImage possui exec_hash/source_hash para ligar metadata a executable/source version.

cdbg_from_result calcula FNV hash se code bytes forem fornecidos.

Porém lang_write_map chama:

    cdbg_from_result(blob, cap, result, 0, 0, 0)

Consequentemente:

    exec_hash   = 0
    source_hash = 0

nos CDBG escritos por esse path.

Campos existem no formato, mas ainda não protegem contra stale metadata/executable mismatch.

## CDBG não é carregado por lang_pipeline

Na revisão documentada, cdbg_decode/cdbg_line_at/cdbg_func_at aparecem na implementação e nos testes, não no live lang_pipeline loader.

lang_load_map lê .MAP.

Editor debugger usa LangSlot map arrays.

CDBG deve ser descrito como implemented metadata format e future integration path, não como runtime source-mapping backend atual.

## Fault reporting

Em CLVM execution fault, lang_tick chama proc_record_fault com target process ID/current VM PC, imprime VM state detalhado em serial e desmonta o slot.

Serial inclui:

- pc;
- source line;
- sp;
- vm.fault;
- vm.fault_pc;
- csp;
- return addresses;
- top of stack.

UI-facing lang_debug_fault, porém, lê proc_last_fault.

Esse process-level record fornece cr2, pid e rip-like PC.

Não expõe full ClvmFault enum/fault_pc pelo dbg_ctl.

Como lang_tick mata target após HALT/FAULT, live LangSlot VM state também é perdido para postmortem interativo.

Debugger mais rico deve snapshotar target state antes do teardown.

## Syscall trace

clvm_sys_dispatch mantém ring pequeno de recent syscall IDs/slot IDs.

lang_debug_sys o expõe ao debugger.

dbg_text kind 5 mostra até seis IDs recentes.

É útil porque muitas operations de source-level ChrisC terminam em host-service calls.

Trace é observacional: não inclui arguments nem return values.

## Integração com Editor

Editor expõe comandos/shortcuts para:

- debug launch;
- step in;
- step over;
- step out;
- continue;
- stop/detach;
- toggle breakpoint;
- inspecionar memory address.

Gutter mostra breakpoint/source position.

Debug panel pede status, stack e memory rows por dbg_text.

Isso mantém debugger self-hosted no ambiente ChrisOS: um ChrisC program controla outro ChrisC/CLVM target via CLVM service ABI.

## Segurança e ownership

Live dbg_ctl/dbg_text chama global lang_debug_* functions.

Não aplica DbgSession owner checks.

Qualquer CLVM program capaz de chamar esses builtins pode alcançar global debugger control surface.

DbgSession possui explicit owner model, mas esse modelo ainda não está conectado ao syscall path.

Em ambiente multi-application hardened, debugger access deveria exigir:

- target ID específico;
- session ownership;
- attach authorization/capability;
- validated memory-inspection ranges;
- teardown ao sair owner/target.

Debugging é intrinsecamente privilegiado por expor memory e controlar execução de outro programa.

## Complexidade

Live algorithms possuem small fixed limits, mas são majoritariamente lineares.

| Operação | Complexidade |
|---|---|
| breakpoint hit check | O(B), B <= 32 |
| source line lookup | O(M), M = loaded map entries |
| source-line breakpoint resolution | O(M) |
| function lookup | O(F), F <= 16 live |
| pending-breakpoint membership | O(P), P <= 32 |
| stack/call lookup | O(1) |
| watched-memory read | O(n) bytes |
| DbgSession lookup | O(1) por session ID |
| DbgSession breakpoint resolve | O(B * M) |

Maior custo evitável é repeated linear source-map lookup durante instruction-by-instruction stepping.

## Concurrency

Debug state é em grande parte global ou dentro de LangSlot.

g_want_debug, g_pend_line, g_pend_watch e DbgSession table são process-global kernel data.

Não há lock em torno de DbgSession table nem dos live breakpoint globals nesses modules.

Usage model atual assume controle serialized/cooperative pelo desktop/language scheduler.

Essa assumption deve ser revista se vários CPUs/debugger clients puderem alterar state simultaneamente.

## Evidência de validação

tools/test_cdbg.c valida:

- CDBG encode/decode round trip;
- file/line/function lookup;
- parser de .MAP antigo e file-aware;
- multi-file ChrisC source mapping;
- diagnostic records.

tools/test_dbg_step.c valida:

- step-in/over/out rules;
- DbgSession ownership;
- file-aware breakpoint resolution;
- temporary/persistent breakpoint behavior;
- typed watch records;
- fault isolation entre sessions.

tools/test_editor_vi.c valida interpreter call-stack overflow e Editor-related generated control flow.

Testes gerais de CLVM/JIT dão as execution semantics necessárias ao debugger.

Gap principal é integração: richer DbgSession/CDBG tests não provam que live Editor debugger usa essas abstrações, porque ainda não usa.

## Limitações atuais

Na revisão documentada:

- runtime ao vivo usa text .MAP em vez de CDBG;
- .MAP reader é limitado a 8191 bytes;
- live source lookup ignora file_id;
- breakpoints pendentes são apenas números de line;
- source breakpoint arma somente primeiro matching map PC;
- continue em persistent breakpoint pode re-hit imediatamente o mesmo PC;
- step operations possuem ceilings de 512/8192 instructions;
- stepping de WAITING VM pode gastar o restante do loop repetindo YIELD;
- live control é global, não target/session-addressed;
- inspection APIs escolhem primeiro debug_on slot;
- live function metadata limita-se a 16 names de 23 chars;
- CDBG generator pode produzir >256 lines, enquanto decoder rejeita >256;
- live CDBG sidecars são escritos com executable/source hashes zero;
- CdbgLine.pc_end não é aplicado por cdbg_line_at;
- DbgSession ownership, typed watches e temporary breakpoints não estão ligados a lang_pipeline;
- live "watch" é memory-view address, não watchpoint;
- process fault UI não preserva full ClvmFault após slot teardown;
- dbg_text não recebe destination capacity;
- debugger syscalls não possuem privilege/capability check nem session owner.

## Fronteira de roadmap

O caminho natural de consolidação é tornar CDBG + DbgSession o único runtime debugger model.

Isso permitiria:

- runtime loading e hash validation de CDBG;
- file-aware source breakpoints;
- target-addressed sessions;
- temporary breakpoint para continue/step-over;
- structured pause reasons;
- asynchronous stepping através de WAITING;
- postmortem VM snapshots;
- typed memory inspection com explicit status;
- true watchpoints por write instrumentation;
- binary-search source lookup;
- metadata completo para 64 functions;
- owner/capability checks no attach;
- versioned debugger protocol em vez de numeric controls mágicos.

São mudanças futuras até integração no source.

## Mapa de source e revisão

compiler/debug/cdbg.h/cdbg.c definem structured debug metadata e lookup functions.

compiler/debug/dbg_session.h/dbg_session.c definem session ownership, structured breakpoints, typed watches e step-policy helpers.

compiler/chrisc/chrisc.h define compiler-side source map, diagnostics e exported-function metadata.

compiler/lang_pipeline.c implementa live debugger state, .MAP generation/loading, breakpoint handling, stepping, memory inspection e Editor-facing controls.

kernel/lang/clvm_sys.c expõe dbg_ctl/dbg_text como syscalls CLVM 250/251.

APPS/EDITOR/EDITOR.CC implementa o visible debugger workflow.

Todas as afirmações de comportamento atual deste capítulo foram reconciliadas com ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
