---
id: clvm-syscalls
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisc/chrisc.c
  - compiler/clvm/clvm.h
  - compiler/clvm/clvm_vm.c
  - compiler/clvm/clvm_vm.h
  - compiler/jit/jit_runtime.c
  - compiler/lang_pipeline.c
  - compiler/lang_pipeline.h
  - kernel/lang/clvm_sys.c
  - kernel/lang/clvm_sys.h
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/net/sock.c
  - kernel/gfx/shader/sh_pub.c
symbols:
  - builtins
  - builtin
  - clvm_sys_dispatch
  - clvm_sys_close_slot
  - vm_bytes
  - vm_cstr
  - vm_copy_in
  - vm_copy_out
  - guest_read
  - guest_write
  - sys_fopen
  - sys_fclose
  - sys_fread
  - sys_fwrite
  - fd_owned
  - drv_cap
  - vm_sync_slot
  - clvm_threads_tick
  - jit_rt_sys
depends_on:
  - clvm-bytecode
  - clvm-memory
related:
  - clvm-interpreter
  - calling-conventions
  - processes-syscalls
  - network-stack
  - shaders-csir
  - gc-libraries
---

# Syscalls do CLVM e ABI de serviços do host

## Escopo

O bytecode CLVM é intencionalmente pequeno. A maioria dos serviços de sistema operacional e aplicação não existe como opcode específico da VM. ChrisC reduz essas chamadas à instrução genérica `SYS` e passa um numeric service ID.

A fronteira conecta quatro camadas:

    builtin no source ChrisC
        -> numeric Builtin ID
        -> CL_OP_SYS
        -> clvm_sys_dispatch
        -> subsistema ChrisOS

Este capítulo documenta essa fronteira como ABI, e não apenas como catálogo de funções convenientes.

As propriedades críticas são:

- como argumentos e retornos usam operand stack;
- como guest pointers são validados antes de acesso do kernel;
- quais resources pertencem a cada slot;
- quais serviços podem bloquear;
- como capabilities protegem hardware privilegiado;
- quais falhas viram retorno para o guest e quais viram VM fault;
- quais partes da surface atual possuem inconsistências internas.

![Fluxo de syscall do CLVM](../../assets/diagrams/clvm-syscalls-pt-br.svg)

## A instrução `SYS`

`CL_OP_SYS` possui opcode `0x20`.

Não tem immediate operand.

O syscall number fica na própria VM operand stack.

Em chamada normal de builtin ChrisC, codegen avalia argumentos na ordem do source, empilha o builtin numeric ID e emite `SYS`.

Para:

    service(a, b, c)

a stack imediatamente antes de `SYS` é:

    ... | a | b | c | service_id

Core interpreter retira primeiro service_id.

clvm_sys_dispatch então remove argumentos em ordem inversa:

    c, b, a

Por isso casos do dispatcher aparecem frequentemente como:

    pop(c)
    pop(b)
    pop(a)

embora a ordem source-level seja a, b, c.

Serviço com retorno empilha o resultado na mesma operand stack.

Serviço declarado void não deveria deixar resultado.

## Return code do dispatcher versus retorno do guest

Existem dois canais de retorno diferentes.

O return value C de clvm_sys_dispatch é control status interno.

- `0` significa que o dispatcher completou a operação SYS do ponto de vista do VM engine.
- valor diferente de zero significa que o VM engine trata a chamada como rejeitada.

No interpreter:

    if sys(...) != 0
        -> CLVM_FAULT_BAD_SYS

Isso é separado do resultado visível ao programa ChrisC.

Muitas falhas operacionais normais fazem:

    push(-1)
    return 0

VM continua executando e programa recebe -1.

Já:

    return -1

sem traduzir a condição para guest result faz a própria instrução `SYS` faultar.

Essa distinção pertence ao ABI.

## Equivalência com JIT

JIT usa jit_rt_sys para handling genérico de SYS.

jit_rt_sys remove syscall ID e chama o mesmo vm->sys callback para serviços comuns.

ID 1, primitive pixel, possui fast path especializado no JIT runtime.

Nos demais casos, dispatcher continua sendo autoridade semântica.

Mudanças em argument order, result shape, ownership ou blocking precisam permanecer compatíveis tanto com switch interpreter quanto com native generated execution.

## Precondition do dispatcher: graphics context

clvm_sys_dispatch começa exigindo:

    vm != NULL
    ctx != NULL
    ctx->pixels != NULL

Se qualquer condição falha, retorna -1 antes de examinar service ID.

Logo a syscall surface atual não é uma generic headless kernel-service interface.

Mesmo serviços logicamente não gráficos—files, sockets, crypto, malloc, threads e hardware I/O—passam por dispatcher que exige ClvmGfxCtx válido com pixels.

O normal desktop CLVM path satisfaz isso.

Uma futura execução command-line/headless precisará de minimal context, refactoring do dispatcher ou service layer separada.

## Registry do compiler

ChrisC descreve serviços com:

    struct Builtin {
        name
        id
        argc
        returns
        ret_float
    }

A builtin table é ABI de linguagem em compile time.

`builtin(name)` percorre a tabela do começo ao fim e devolve o primeiro nome correspondente.

Na revisão documentada existem:

- 173 Builtin entries;
- 173 numeric dispatcher cases correspondentes;
- 172 nomes únicos.

A diferença vem de um nome duplicado descrito adiante.

## Surface de serviços por subsistema

A tabela agrupa o registry implementado. Ela mapeia a surface atual, sem afirmar maturidade idêntica entre todos os serviços.

| IDs | Subsistema | Builtins ChrisC |
|---|---|---|
| 1-6 | desenho 2D | pixel, rect, line, sprite, tilemap, clear |
| 10-13 | input/tempo/áudio básico | key, ticks, wait, tone |
| 20-23 | primitives 3D | tri, mesh, transform, meshf |
| 30-41 | math/view/voxel | fps, sin, cos, cam, light, tex, voxel, voxel_get, world, viewport, screen_w, screen_h |
| 50-59, 61, 64-65 | files, allocation, nonlocal control, CLA | fopen, fclose, fread, fwrite, fsize, fexists, malloc, free, setjmp, longjmp, realloc, cla_load, fseek |
| 62-63 | threads | thrd_create, thrd_join |
| 70-73 | GC/framebuffer/palette | gc_alloc, gc_collect, fb_blit, setpal |
| 80-91 | mouse/events/surfaces | mouse_x, mouse_y, mouse_btn, ev_key, ev_text, fillrgb, text, glyph, surf_place, surf_move, surf_raise, surf_close |
| 92-112 | filesystem/apps/system | readdir, mkdir, unlink, rename, app_spawn, app_kill, app_count, app_info, sys_cc, sys_run, sys_make, disp_w, disp_h, sys_err, app_spawn_arg, app_arg, lib_load, lib_reload, isdir, kb_layout, kb_get |
| 113-126 | window state/telemetry/text | surf_resize, surf_minimize, surf_maximize, surf_restore, métricas de heap/PMM/frame/CFS/apps, app_raise, textruns |
| 127-134 | synchronization/TLS/state | mtx_lock, mtx_unlock, cnd_wait, cnd_signal, tls_get, tls_set, app_state, app_reload |
| 140-146 | sockets/DNS | sock_listen, sock_accept, sock_connect, sock_send, sock_recv, sock_close, dns_lookup |
| 150-153 | RNG/crypto | rng_u32, sha256, aes_encrypt, x25519 |
| 160 | PCM audio | pcm_write |
| 170-175 | low-level driver I/O | drv_outw, drv_inw, drv_outb, drv_inb, drv_irq, drv_pci |
| 180 | process heap | sbrk |
| 190-198 | scene/physics/animation | scene_add, scene_draw, phys_add, phys_step, anim_key, anim_apply, phys_x, phys_y, tex_ofs |
| 210-233 | PCI/MMIO/DMA/disk/GPU | pci_write, bar_map, mmio_r32/w32/r8/w8/r16/w16, dma_alloc/lo/hi/w32/r32, disk services, gpu_arm, gpu_ready |
| 240-243 | relative mouse | mouse_dx, mouse_dy, mouse_cap, mouse_rel |
| 250-251 | debugger | dbg_ctl, dbg_text |
| 260-274 | shader/program API | shader_make/ok/log/drop, prog_make/attach/link/ok/log/drop/uniloc/setf/samp, shader_vert, shader_frag |

Os grandes gaps numéricos são consequência do crescimento por subsistemas; syscall IDs não precisam ser contíguos.

## Argumentos float

A maioria dos builtin arguments usa integer stack values.

Floats são representados pelo bit pattern de 32 bits dentro de VM stack slot.

O helper pop_f retira integer VM value, reinterpreta os low 32 bits como IEEE-754 float e devolve native float.

ChrisC marca builtins com ret_float quando codegen precisa de float result semantics.

Service ID continua integer.

## Guest pointers são offsets

Ordinary CLVM memory pointers são guest offsets em:

    vm->memory[0 .. vm->mem_size)

Não são arbitrary kernel C pointers.

Uma syscall que recebe address precisa validar antes de dereference.

Dispatcher tem vários helpers.

### vm_bytes

vm_bytes valida address e positive length e só devolve pointer para guest RAM depois de provar:

    address < mem_size
    length <= mem_size - address

A forma por subtração evita wraparound em address + length.

### vm_cstr

vm_cstr copia byte a byte para bounded kernel buffer.

Só retorna success ao encontrar NUL antes tanto da kernel capacity quanto do guest-memory boundary.

É usado para paths, shader sources/names e outros text inputs.

### vm_copy_in e vm_copy_out

vm_copy_in copia validated guest range para kernel-owned memory.

vm_copy_out copia kernel bytes para validated guest range.

Esses helpers são preferíveis a manter guest pointer direto enquanto se chama subsistema com lifetime/blocking diferente.

### guest_read e guest_write

Crypto, audio e algumas famílias mais recentes usam helpers com uint64_t offset guest_read/guest_write.

Eles aplicam a mesma exigência de complete range.

## Exceções de pointer domain

Nem todo serviço pointer-like usa ordinary guest-offset domain.

O ABI atual possui pelo menos três pointer domains.

### malloc

malloc retorna offset de clvm_guest_malloc.

É diretamente utilizável por ordinary CLVM LOAD/STORE.

### gc_alloc

gc_alloc chama o kernel/compiler GC allocator e empilha native pointer convertido para int64_t.

Não é ordinary vm->memory offset.

CLVM LOAD/STORE comum não deve ser assumido capaz de dereference desse valor.

### sbrk

sbrk chama proc_sbrk e devolve process virtual address na process heap region iniciada em PROC_HEAP_VIRT.

Esse address também é distinto do ordinary CLVM guest offset model.

A coexistência de guest offsets, managed native pointers e process virtual addresses é complexidade atual do ABI.

Um ABI futuro mais forte deveria taggear/unificar essas representações em vez de depender de o caller saber quais operações aceitam cada address class.

## Modelo de file descriptors

CLVM implementa slot-owned file table em clvm_sys.c.

Limites importantes:

    CLVM_FD_MAX = 32
    CLVM_FD_PER_SLOT = 8
    CLVM_FD_CAP = 65536
    CLVM_FD_MAX_BYTES = 16 MiB

Descriptors 0-2 ficam reservados por convenção; fopen procura a partir do 3.

fd_owned verifica que descriptor pertence ao application/graphics slot atual.

Isso impede que um slot CLVM comum feche/leia buffered file descriptor de outro slot.

Writes para stdout/stderr são exceção: fwrite em fd 1/2 copia guest bytes validados em chunks e envia para serial.

## Policy de fopen

sys_fopen:

1. copia path da guest memory;
2. remove leading "./";
3. rejeita path components `..` por path_ok;
4. impõe limite de descriptors por slot;
5. verifica permissões CFS read/write quando CFS está disponível;
6. exige que target já exista e seja file.

O fopen atual não cria arquivo inexistente.

Small files são buffered em kernel memory.

Arquivos maiores que CLVM_FD_CAP usam streaming reads.

Streaming descriptors rejeitam buffered fwrite path.

## Ownership de buffered writes

Buffered writes alteram o ClvmFile em memória e marcam dirty.

fd_free grava dirty buffer de volta no filesystem antes de liberar.

clvm_sys_close_slot percorre global descriptors e fecha os pertencentes ao slot.

Logo slot teardown faz parte da durability de buffered CLVM writes.

Um abnormal path que ignorasse clvm_sys_close_slot poderia perder buffered writes.

## Cleanup de resources por slot

clvm_sys_close_slot executa vários cleanups:

- shader/program objects do slot;
- voxel ownership;
- input capture;
- todos os sockets do slot;
- todos os CLVM file descriptors do slot.

É uma lifecycle boundary útil.

Porém a função não percorre a global CLVM child-thread table.

Isso importa porque child VMs são allocations separadas e compartilham parent code/memory.

Se slot é destruído com child CLVM threads ativas, essas entries não são visivelmente recuperadas por clvm_sys_close_slot na revisão atual.

lang_kill também libera slot RAM e posteriormente o backing file do CLV.

Uma child sobrevivente pode portanto reter references a backing cujo owner já foi desmontado.

É lifecycle gap atual que deve ser corrigido com cancel/join cleanup explícito por slot.

## Modelo de thread services

Runtime suporta:

    CLVM_TH_MAX = 32
    CLVM_TH_PER = 8

thrd_create aloca novo ClvmVm, copia code, memory, mem_size, sys callback, context e process identity do parent, configura child PC na função solicitada e coloca thread argument na child operand stack.

Parent e child compartilham guest RAM, mas possuem VM operand/call stacks independentes.

O capítulo de memória documenta o bug separado em que child não herda/compartilha heap_off do allocator.

thrd_join usa parent join_wait e pode colocar parent em CLVM_WAITING até child finalizar.

## Synchronization objects

mtx_lock/mtx_unlock e cnd_wait/cnd_signal usam addresses dentro da shared guest RAM como localização dos synchronization objects.

Mutex word guarda small owner identity.

Runtime também guarda blocked child-thread metadata em g_th.

O design é leve, porém acopla synchronization correctness ao shared guest-memory model.

Guest deve usar storage locations válidas e seguir o lock protocol esperado.

## Serviços bloqueantes

Vários serviços podem colocar VM em CLVM_WAITING:

- wait;
- thrd_join;
- sock_recv quando não há dados;
- drv_irq;
- mutex/condition paths.

wait é timer-oriented.

Configura wake_tick e devolve YIELD até clvm_vm_wake observar o tempo solicitado.

Os demais blocking handlers tentam convenção diferente: reempilham original arguments e syscall ID antes de retornar com state WAITING.

## Inconsistência atual do retry protocol

Interpreter consome SYS opcode e avança vm->pc antes de chamar dispatcher.

Quando dispatcher define CLVM_WAITING, clvm_step devolve CLVM_STEP_YIELD.

Ao acordar, clvm_vm_wake muda state para READY.

No interpreter inspecionado não há rewind de vm->pc para SYS.

Handlers bloqueantes de sock_recv, thrd_join, drv_irq e synchronization reempilham arguments mais syscall ID, aparentemente preparando retry, mas o próximo interpreter step continua na bytecode instruction seguinte ao SYS.

O generic syscall helper do JIT também chama dispatcher sem estabelecer visible retry-PC protocol.

Assim o source atual mostra continuation/retry contract incompleto para esses restacked blocking syscalls.

Isso deve ser tratado como source-level correctness issue e receber regression tests e design explícito, por exemplo:

- rebobinar PC até SYS;
- manter pending syscall record fora da operand stack;
- ou fazer scheduler reexecutar pending syscall antes de normal bytecode execution.

Até isso ser definido, blocking semantics além do timer wait não devem ser descritos como completamente estabilizados.

## Ownership de sockets

Socket operations usam vm_sync_slot para associar atividade ao application slot.

sock_listen_for, sock_accept_for, sock_connect_for, sock_send_for, sock_recv_for e sock_close_for recebem owner.

clvm_sys_close_slot chama sock_close_slot, encerrando sockets do slot no teardown.

sock_send/sock_recv usam kernel temporary buffer de 200 bytes por dispatcher call.

Lengths acima de 200 são limitados.

Guest source/destination ranges são validados antes da copy.

Recv com retorno zero é interpretado como condição para block/retry, e não imediatamente como ordinary zero result.

Isso depende do retry protocol ainda incompleto descrito acima.

## DNS

dns_lookup copia bounded guest C string para local buffer de 64 bytes e chama sock_dns.

Numeric IP result é empilhado como integer.

Dispatcher descarta o rc separado da chamada e devolve IP result, usando zero como failure-like value.

## Serviços criptográficos

A surface atual contém:

- rng_u32;
- sha256;
- aes_encrypt;
- x25519.

Essas calls não passam guest pointers diretamente às crypto implementations.

Copiam fixed/bounded input para local kernel arrays, executam primitive e copiam resultado de volta para validated guest memory.

sha256 aceita no máximo 256 bytes por chamada.

AES usa path de key/input/output de 16 bytes.

x25519 copia scalar/point de 32 bytes e grava resultado de 32 bytes.

Esse copy-in/copy-out design oferece protection boundary mais clara do que operar diretamente em unchecked guest ranges.

## Graphics e surface ownership

Muitos syscall IDs iniciais desenham diretamente no pixel buffer do ClvmGfxCtx atual.

sprite e tilemap validam guest-memory source extents antes de renderizar.

Viewport changes podem resize/allocate graphics slots.

Surface/window operations conectam CLVM application ao desktop task/window model.

Dispatcher carrega Gfx3DCtx do slot na entrada e usa cleanup attribute para salvar ao retornar.

Isso evita implicit global 3D state de outro slot.

## Ownership de shader objects

Shader/program syscalls usam fd_slot(user) como owner key.

Shader subsystem recebe owner para compile, status, logs, deletion, program creation/linking e uniform/sampler operations.

clvm_sys_close_slot chama sh_guest_drop_owner(slot_id), fornecendo bulk cleanup explícito.

Shader source é copiado da guest memory para bounded kernel allocation antes de compilation.

Shader/program logs retornam por vm_copy_out.

## Administração de apps e filesystem

IDs 92-112 expõem directory operations, application launch/kill/query, build/run helpers, library loading e keyboard configuration.

readdir copia path para kernel memory, enumera por index e depois copia selected name para guest destination.

mkdir, unlink e rename rejeitam traversal por path_ok.

app_spawn executa outro CLVM path.

app_kill opera pelo task/slot model, e não por arbitrary process memory.

sys_cc/sys_make podem disparar compilation/build workflows dentro do ambiente; são high-level OS services, não narrow POSIX syscalls tradicionais.

## Hardware capabilities

Low-level hardware operations são capability-gated.

Bits:

    CAP_PCI        = 1
    CAP_PORT_IO    = 2
    CAP_MMIO       = 4
    CAP_DMA        = 8
    CAP_IRQ        = 16
    CAP_DISK_ADMIN = 32

CAP_DRIVER é union dos seis.

Exemplos:

- pci_write exige CAP_PCI;
- bar_map exige CAP_MMIO;
- dma_alloc exige CAP_DMA;
- disk installation/metadata administration usa CAP_DISK_ADMIN;
- muitas raw MMIO, port, IRQ e disk operations exigem CAP_DRIVER.

Isso é substancialmente mais seguro que expor hardware primitives a qualquer CLVM app.

## Policy de capability grant

Launch policy atual atribui:

    CAP_DRIVER

quando path_is_driver(name) reconhece path contendo padrão SYS/DRV.

Outros ordinary CLVM programs recebem zero capabilities.

É pathname-based trust policy.

Não há nessa decisão cryptographic code identity, signature verification, manifest-declared permission prompt ou capability grant derivado de CFS ACL.

Segurança depende portanto de quem pode criar/modificar executable content sob driver path reconhecido e da filesystem policy desse local.

Design hardened deveria ligar privilege a authenticated metadata explícito, não apenas path convention.

## Handles de hardware services

MMIO/DMA services normalmente evitam entregar raw physical addresses diretamente ao guest.

bar_map devolve managed window/handle.

mmio calls seguintes usam window ID + offset.

DMA allocation igualmente devolve ID e oferece dma_lo, dma_hi, dma_w32 e dma_r32.

A indirection dá ao kernel ponto para validar ownership e bounds.

A policy detalhada do hwgate pertence a outro capítulo, mas syscall boundary deve checar capability antes de entrar.

## Inconsistência no nome disk_sectors

Compiler builtin registry contém duas entries com mesmo source-level name:

    {"disk_sectors", 223, 0, 1, 0}
    {"disk_sectors", 233, 1, 1, 0}

Ambos numeric IDs têm dispatcher cases.

Porém builtin(name) faz forward linear scan e devolve primeiro name correspondente.

Assim lookup normal de `disk_sectors` em ChrisC resolve para ID 223 com zero arguments.

A posterior one-argument ID 233 não é alcançável pelo mesmo builtin name no lookup comum.

É ABI registry defect.

As duas operações precisam de nomes distintos ou uma deve substituir explicitamente a outra.

## Mismatch de stack contract em fclose

Compiler table declara:

    {"fclose", 51, 1, 0, 0}

returns = 0, então ChrisC codegen trata fclose como void builtin.

Dispatcher case ID 51, porém, faz:

    push(sys_fclose(...))

e retorna success.

Isso deixa operand-stack value extra para chamada que compiler diz não produzir expression value.

É mismatch direto entre compiler/runtime ABI.

Correção deve escolher um contract:

- fclose retorna status e returns passa a 1;
- ou permanece void e dispatcher para de empilhar result.

Regression test deve verificar stack depth após chamadas repetidas de fclose.

## Padrões de erro

Dispatcher usa diferentes guest-visible conventions:

| Padrão | Significado típico |
|---|---|
| -1 | invalid resource, operation failure ou permission/capability failure |
| 0 | false/not found/no result, ou success em algumas operações |
| positive integer | handle, count, success flag, size ou ID |
| service-specific | IP, pointer-like value, timestamp, metric |

Não é uniform errno ABI.

Alguns serviços usam -1 para falha; outros zero.

Void services podem não expor guest result.

A source-level builtin signature faz parte da interpretação.

## VM-fault boundary

Falhas estruturais de ABI podem faultar VM.

Exemplos:

- syscall ID ausente da stack;
- handler argument underflow;
- invalid ID no default;
- helper/dispatcher retornar -1 em vez de guest error.

Nesses casos VM registra CLVM_FAULT_BAD_SYS para a SYS operation.

Já operational failures esperadas normalmente são codificadas como -1/0 empilhados e mantêm VM runnable.

Debugger deve mostrar tanto VM fault quanto recent syscall trace.

## Syscall trace

Dispatcher mantém ring de recent service IDs e slot IDs.

SYS_TRACE = 32.

Cada invocation registra:

    id
    slot

antes do switch.

clvm_sys_trace recupera entries recentes.

Debugger expõe syscall trace text pela debugging API.

É útil para diagnosticar incorrect IDs, blocked operations, capability failures e stack-contract mismatches sem tracing completo do interpreter.

## Performance

Uma syscall custa no mínimo:

1. pop de service ID;
2. C callback dispatch;
3. switch branch;
4. argument pops;
5. trabalho do subsistema;
6. optional result push.

Para drawing primitives, overhead importa quando chamada por pixel/tiny primitive.

JIT tem special case para pixel ID 1, mas maioria cruza generic callback.

Buffer-oriented services reduzem crossings aceitando guest ranges, por exemplo sprite, tilemap, file I/O, PCM e crypto.

Copy-in/copy-out adiciona O(n), mas forma protection boundary mais clara.

File buffering troca memória por menos filesystem operations.

## Concurrency

Global syscall state inclui:

- g_fds;
- g_th;
- palette storage;
- syscall trace ring;
- subsystem-global resources alcançados pelo dispatcher.

Ownership costuma ser expresso por slot IDs, mas dispatcher não é pure reentrant stateless function.

CLVM scheduling é cooperative/sliced no nível VM, enquanto ChrisOS pode executar em SMP.

Subsystem locking é portanto necessário onde services atingem shared kernel state.

Syscall ABI não deve sugerir thread safety maior que a do subsistema chamado.

## Evidência de validação

Repository contém testes amplos para ChrisC codegen, CLVM interpreter, JIT equivalence, filesystems, graphics, crypto e lower-level subsystems.

Builtin table e dispatcher podem ser cross-checked mecanicamente: nesta revisão todos os 173 builtin numeric IDs têm dispatcher cases correspondentes.

Documentation build também valida source-symbol references e corpus técnico.

Porém o inspected test set não mostra dedicated host-side regression suite que exercite clvm_sys_dispatch diretamente sobre todos os 173 service IDs.

Devem ser adicionados testes específicos para:

- stack balance de fclose entre compiler/runtime;
- duplicate builtin-name detection;
- blocked syscall resume/retry semantics;
- teardown com live child CLVM threads;
- capability grant/rejection paths;
- invalid guest ranges em cada família de buffer-bearing syscalls.

## Limitações atuais

Na revisão documentada:

- syscall dispatcher exige graphics context mesmo para serviços não gráficos;
- ABI tem 173 entries mas 172 nomes únicos por duplicação de disk_sectors;
- forma one-argument do ID 233 fica shadowed pelo nome anterior;
- fclose é void no compiler, mas empilha result no dispatcher;
- retry semantics de blocking syscalls estão incompletas no contract interpreter/JIT inspecionado;
- slot teardown não recupera visivelmente live child CLVM thread entries;
- guest-offset pointers coexistem com native GC pointers e process-virtual sbrk pointers;
- grant do conjunto CAP_DRIVER depende de convenção de path SYS/DRV;
- error returns são service-specific, não uniform errno;
- syscall IDs são hard-coded em compiler e dispatcher em vez de gerados por single schema;
- não existe version-negotiated syscall capability table no CLV image;
- não há dedicated exhaustive dispatcher conformance test evidente.

## Fronteira de roadmap

Syscall architecture mais forte pode introduzir um machine-readable service schema único gerando:

- ChrisC builtin declarations;
- numeric ID constants;
- dispatcher prototypes;
- argument/return metadata;
- documentation tables;
- conformance tests.

Também pode adicionar:

- explicit syscall ABI versioning;
- typed pointer-domain descriptors;
- uniform error/errno convention;
- headless service contexts;
- scheduler-owned pending-syscall records;
- cleanup automático de threads/handles por slot;
- capability manifests autenticados independentemente do pathname;
- build failures para duplicate names/IDs;
- generated stack-effect verification.

São future directions até existirem no source.

## Mapa de source e revisão

compiler/chrisc/chrisc.c define Builtin registry, builtin lookup e SYS code generation.

compiler/clvm/clvm_vm.c define core SYS execution e CLVM_FAULT_BAD_SYS.

compiler/jit/jit_runtime.c fornece bridge genérico de SYS no JIT.

kernel/lang/clvm_sys.c implementa service dispatcher, guest-memory marshalling, file/thread/socket state, capability checks e lógica service-specific.

compiler/lang_pipeline.c e compiler/lang_pipeline.h definem slot ownership, capability assignment e integração com teardown.

Todas as afirmações de comportamento atual deste capítulo foram reconciliadas com ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
