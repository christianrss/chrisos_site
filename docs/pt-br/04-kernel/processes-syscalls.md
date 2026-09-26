---
id: processes-syscalls
lang: pt-br
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/syscall.c
  - kernel/metal/syscall.h
  - kernel/metal/elf.c
  - kernel/metal/user_enter.c
  - kernel/metal/idt.c
  - kernel/metal/irq.c
  - kernel/fs/fs.c
  - kernel/input/input.c
symbols:
  - proc_create
  - proc_destroy
  - proc_switch
  - syscall_init
  - syscall_dispatch
  - enter_user
depends_on:
  - virtual-memory
  - kernel-model
  - user-mode-entry
related:
  - elf-linking
  - user-copy
  - process-lifecycle
---

# Processos nativos e system calls

## Escopo

Um processo nativo combina address space protegido, recursos associados e execução controlada em ring 3. O ABI atual usa `int 0x80` e um pequeno conjunto de registradores. Ele é separado do modelo CLVM.

Este capítulo define o contrato real: PID/CR3, gate de entrada, números, argumentos, user-copy, ownership de descritores, exit/fault return, restrição de CPU e limites.

## Processo nativo versus aplicação CLVM

Processo nativo executa machine code sob page tables e CPL. Fault é observado por CS/RIP/CR2 e páginas são controladas por Proc.

ChrisC via CLVM utiliza guest memory e outro dispatcher.

“Aplicação” não identifica um único ABI no ChrisOS.

## PID e recursos

`PROC_MAX = 32`. PID0 é kernel; 1–31 são user.

`proc_current` é global e `proc_switch` somente BSP.

Um processo possui CR3, regiões, frames owned, descriptors/sockets por PID e metadados alive/state/name.

## Criação do address space

`proc_create` chama `mm_clone_kernel_space` e comita primeira página de stack.

Loader ELF adiciona segmentos e entry point; criação de Proc não depende de um formato executável específico além dos callers.

## Switch

Antes de user entry, `proc_switch` seleciona CR3.

AP é rejeitado porque current state é global.

TLB/coerência de CR3 pertencem à MM.

## Entry

`enter_user` monta frame `iretq` com CS/SS/RSP/RFLAGS/RIP de user.

Seletores têm RPL3 e páginas precisam USER bit.

IF inicial fica ativo.

Antes do switch a função grava kernel return RIP.

## Gate de syscall

`syscall_init` chama `idt_set_user_gate(0x80)`. DPL3 permite `int 0x80`.

Stub salva `irq_frame` e `irq_dispatch` roteia 0x80 para `syscall_dispatch`.

## ABI de registradores

Número vem de RAX salvo.

| Nº | Nome | Argumentos principais |
|---:|---|---|
| 1 | `SYS_EXIT` | RDI = código |
| 2 | `SYS_WRITE` | RDI fd, RSI buffer, RDX bytes |
| 3 | `SYS_PUTPIXEL` | RDI x, RSI y, RDX color |
| 4 | `SYS_FOPEN` | RDI path user |
| 5 | `SYS_FREAD` | RDI fd, RSI dst, RDX bytes |
| 6 | `SYS_FWRITE` | RDI fd, RSI src, RDX bytes |
| 7 | `SYS_FCLOSE` | RDI fd |
| 8 | `SYS_KEY` | RDI key |

Resultado vai para RAX. Erro normalmente é -1 convertido para uint64.

## BSP-only

`syscall_dispatch` rejeita CPU diferente de 0, grava -1 e avança RIP.

Isso impõe o mesmo modelo de CPU de `proc_switch`.

## Avanço de RIP

A maioria dos casos faz `frame->rip += 2`, seguindo a convenção atual da instrução `int imm8`/frame.

Migrar para SYSCALL/SYSRET exige reespecificar return semantics, não copiar esse incremento.

## EXIT

Armazena código e chama retorno controlado.

`syscall_return_to_kernel` substitui RIP por continuação kernel, CS por kernel code, RFLAGS e marca exited.

O `iretq` comum volta a ring 0.

Não é modelo POSIX de zombie/wait.

## WRITE

Só fd1 e no máximo 80 bytes.

Copia user→kernel para array 81 bytes, insere NUL seguro e escreve serial.

O byte 81 evita overflow em payload de exatamente 80.

## User-copy

Acesso de buffer verifica canonicalidade/janela, CR3 current, tradução por página, Present/User e Write quando destino é user.

Página ausente em copy retorna erro.

O capítulo user-copy detalha o algoritmo.

## Tabela de arquivos

`UFILE_MAX = 8`. FOPEN aloca 2–7.

Cada slot possui used, owner PID e path até 128 bytes.

Não há offset de arquivo dentro dessa estrutura.

`ufile_owned` garante owner=current.

## FOPEN

Copia até 127 bytes de path, força NUL, procura slot livre e grava owner/path.

Não cria objeto de open-file com offset; o slot é referência de path para operações posteriores.

Sem slot retorna -1.

## FREAD

Exige owner e máximo 512 bytes.

`fs_read` escreve em kernel buffer; depois bytes lidos são copiados a user.

Erro de FS ou copy retorna -1.

## FWRITE

Máximo 512; copia primeiro user→kernel.

fd1 vai ao serial; outros exigem owner e chamam `fs_write`.

FS nunca recebe pointer user bruto.

## FCLOSE

Se owner confere, limpa slot. Retorna zero no código atual mesmo quando não há slot owned correspondente.

Esse comportamento concreto deve ser testado se ABI precisar estabilidade.

## PUTPIXEL

Passa x/y/color a `gfx_put_pixel`.

Não há user pointer; bounds dependem do graphics subsystem.

## KEY

Consulta `input_key_down` e retorna 0/1.

É polling, não event queue user.

## Número desconhecido

Retorna -1 e avança RIP. Não envia signal nem encerra processo.

## Cleanup

`syscall_close_owner` limpa fds 2–7 de um PID.

`proc_destroy` chama essa função. Sockets possuem cleanup separado.

## Fault de usuário

#PF tenta demand paging. Se falha e origem é user, `panic_user_fault` registra, destrói PID, loga, define -11 e redireciona ao kernel.

Kernel continua vivo.

## Estados de processo

READY e block reasons para socket/join/IRQ existem.

Isso não implica scheduler POSIX. Timer apenas marca slice due.

## Ownership do ABI

Buffer user continua user-owned; syscall copia quando necessário.
fd pertence ao PID até close/destroy.
frames pertencem ao processo e são liberados no destroy.
return state pertence à execução user atual do BSP.
filesystem recebe kernel memory.

Ownership define segurança de error paths.

## Segurança

Gate DPL3 é intencionalmente limitado. Ponteiros são traduzidos. fd tem owner. Seletores e PTEs separam user/kernel.

API não é POSIX e não deve herdar por documentação semânticas de Linux.

## Desempenho

`int 0x80` e cópia byte a byte privilegiam clareza. Buffers são pequenos.

Fast path futuro pode usar SYSCALL/SYSRET e I/O maior, mantendo validação/ownership.

## Validação

Testar todas syscalls, número inválido, limites 80/512, pointers inválidos/cross-page, exaustão/ownership de fd, close/destroy, exit, fault containment, AP rejection e bordas de graphics/input.

## Limitações atuais

31 processos user, seis fds dinâmicos nesse layer, userspace BSP-only, fd por path, sem fork/exec/wait POSIX, sem signals e sem SYSCALL/SYSRET.

São limites explícitos.

## Mapa de fonte

`proc.c`/`proc.h`: processo. `user_enter.c`: entry. `idt.c`/`irq.c`/`syscall.c`: ABI. `elf.c`: executable loading. FS/input/graphics: serviços concretos. Source Atlas publica tudo integralmente.
