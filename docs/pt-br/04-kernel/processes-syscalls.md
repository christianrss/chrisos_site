---
id: processes-syscalls
lang: pt-br
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/syscall.c
  - kernel/metal/syscall.h
  - kernel/metal/elf.c
  - kernel/metal/user_enter.c
  - kernel/metal/idt.c
  - kernel/metal/irq.c
  - kernel/metal/irq.h
  - kernel/fs/fs.c
  - kernel/gfx/input.c
  - tools/test_sys_write.c
symbols:
  - proc_create
  - proc_destroy
  - proc_switch
  - syscall_init
  - syscall_dispatch
  - syscall_write_term
  - user_span_ok
  - user_copy
  - enter_user
  - panic_user_fault
  - proc_commit
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

## Estado concreto de processos e syscalls

A implementação usa tabelas de tamanho fixo residentes no kernel, em vez de objetos de controle de processo e descritores alocados dinamicamente.

A tabela de processos possui `PROC_MAX = 32` entradas. Cada registro privado `Proc` contém `used`, `alive`, estado do scheduler, `cr3`, contabilidade de memória virtual, `heap_brk`, quantidade de páginas de framebuffer, nome com 24 bytes e um vetor de `PROC_PAGES = 288` registros de páginas pertencentes ao processo. Cada `ProcPage` registra um endereço virtual e um endereço físico. Essa representação torna o teardown determinístico: o kernel percorre as páginas registradas e libera os frames sem precisar reconstruir ownership a partir das page tables.

A camada de syscalls mantém separadamente `UFile g_ufile[8]`. Cada entrada contém somente `used`, PID proprietário e um path de 128 bytes. Não existe nessa estrutura offset corrente, flags de abertura, reference count ou objeto de arquivo do filesystem. Portanto, o descritor nativo é atualmente um pequeno handle de path escopado por PID, não um open-file description no sentido POSIX.

Também são globais `g_user_exited`, `g_user_exit_code`, `g_user_kernel_rip` e a janela aceita para cópia de memória de usuário. Essa natureza global é uma das razões para a execução nativa em user mode permanecer restrita ao BSP.

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

## Máquina de estados do dispatch

O caminho completo de uma syscall nativa normal é:

1. código em ring 3 executa `int 0x80`;
2. o gate DPL3 da IDT transfere controle para o stub ISR comum;
3. o stub materializa os registradores em `struct irq_frame`;
4. `irq_dispatch` reconhece o vetor `0x80` antes do tratamento genérico de exceções e IRQs;
5. `syscall_dispatch` lê o número salvo em RAX e os registradores de argumentos;
6. a operação valida limites escalares, ownership de descritor e/ou memória user;
7. o resultado é escrito no RAX salvo;
8. caminhos que não são `EXIT` avançam o RIP salvo em dois bytes;
9. o retorno comum de interrupção restaura a execução.

O layout de `irq_frame` faz parte do contrato interno entre o código assembly de entrada e o dispatcher C. O dispatcher depende especificamente dos campos salvos de `rax`, `rdi`, `rsi`, `rdx`, `rip`, `cs` e `rflags`. Alterar a ordem de salvamento no assembly sem atualizar a struct corromperia a interpretação da syscall mesmo que a numeração pública continuasse igual.

`SYS_EXIT` é a exceção deliberada ao avanço normal de RIP: ele reescreve o estado salvo para que o `iretq` comum retorne a uma continuação no kernel.

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

## Algoritmo de user-copy e janela válida

A janela padrão aceita para cópia é `[0x400000, 0x500000)`; ela pode ser substituída por `syscall_set_user_map`. `user_span_ok` trata primeiro comprimento zero e depois rejeita endereço no upper half, overflow que atravessaria o limite canônico inferior, início fora da janela configurada ou comprimento que ultrapasse o limite superior.

Para um span não vazio, `user_copy` obtém o CR3 do PID atual e itera até transferir todos os bytes. Em cada trecho ele traduz o endereço virtual com `mm_translate`, exige `MM_PRESENT | MM_USER`, exige adicionalmente `MM_WRITE` quando a direção é kernel→user, limita o chunk ao restante da página de 4 KiB, converte o endereço físico pela HHDM e então copia os bytes.

O kernel, portanto, não desreferencia diretamente o ponteiro virtual fornecido por user space. Uma página ausente, sem USER ou sem WRITE quando necessário vira erro da syscall, em vez de um page fault de ring 0 provocado por acesso C direto.

O algoritmo é page-aware, mas o loop final de transferência é byte a byte. Para `n` bytes distribuídos em `p` páginas, o custo é proporcional a `O(p * T_translate + n)`. Com os limites atuais de payload, a implementação privilegia simplicidade e verificabilidade em vez de throughput.

## User-copy

Acesso de buffer verifica canonicalidade/janela, CR3 current, tradução por página, Present/User e Write quando destino é user.

Página ausente em copy retorna erro.

O capítulo user-copy detalha o algoritmo.

## Tabela de arquivos

`UFILE_MAX = 8`. FOPEN aloca 2–7.

Cada slot possui used, owner PID e path até 128 bytes.

Não há offset de arquivo dentro dessa estrutura.

`ufile_owned` garante owner=current.

## Algoritmo de alocação de descritores

A alocação percorre linearmente os slots de fd 2 até 7. Existem apenas seis posições alocáveis; por isso o pior caso concreto examina seis entradas, embora formalmente seja `O(UFILE_MAX)`. A verificação de ownership usa acesso indexado seguido da comparação do PID.

Durante teardown, `syscall_close_owner(pid)` também percorre fd 2–7 e invalida todas as entradas daquele processo. Isso evita que um slot de arquivo sobreviva à destruição e seja acidentalmente herdado quando o mesmo número de PID for reutilizado.

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

## Comportamentos de borda das syscalls de arquivo

Há detalhes observáveis que precisam ser preservados por compatibilidade ou alterados de forma explicitamente versionada:

- `FOPEN` solicita a `copy_from_user` exatamente 127 bytes antes de procurar o NUL. Assim, todo esse span precisa ser válido dentro da janela user mesmo quando o pathname lógico termina antes.
- `FREAD` rejeita mais de 512 bytes, lê primeiro para um buffer kernel de 512 bytes e copia para user somente a quantidade realmente retornada pelo filesystem.
- `FWRITE` copia o payload completo antes de validar ownership do fd. Para fd 1 usa `serial_puts`; quando `n == 512`, o byte 511 é substituído por NUL e a função ainda reporta 512. Isso é um comportamento concreto da implementação atual, não uma garantia de write binário.
- para descritores normais, o retorno de `fs_write` é convertido para RAX; nem todo valor negativo produzido pelo filesystem é normalizado previamente pelo dispatcher.
- `FCLOSE` retorna zero mesmo quando o descritor fornecido não pertence ao processo e nada é fechado.

Esses pontos impedem que a documentação trate nomes familiares como equivalentes automáticos às semânticas de Linux/POSIX.

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

## Recuperação de fault versus falha de cópia em syscall

Existem dois caminhos distintos para memória inválida. A cópia de syscall não tenta materializar páginas por fault: falha de tradução ou de permissão retorna -1 ao dispatcher. Já um page fault de CPU no vetor 14 chama primeiro `proc_fault_demand`, que pode comitar uma página nas regiões configuradas de VM, stack, heap ou framebuffer.

Somente quando o demand paging falha e o CS salvo indica origem em user mode é que `panic_user_fault` registra o fault, destrói o processo, define código de saída -11 e redireciona o retorno para a continuação do kernel.

Portanto, “ponteiro inválido passado a uma syscall” e “instrução de usuário gerou page fault” não são necessariamente o mesmo caminho de recuperação, mesmo quando ambos representam acesso inválido de user space.

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

## Invariantes de lifecycle e ownership

`proc_create` procura um slot livre de PID entre 1 e 31, clona o espaço de kernel com `mm_clone_kernel_space`, inicializa o estado e comita a primeira página da stack. Se esse commit falha, `proc_destroy` desfaz o processo parcial.

`proc_destroy` troca primeiro para o processo kernel quando o PID destruído é o corrente. Em seguida libera os frames registrados, libera a estrutura de address space quando aplicável, remove descritores por PID, fecha sockets associados e finalmente marca o slot como livre. A ordem evita permanecer executando com CR3 pertencente ao processo que está sendo destruído e evita que recursos indexados por PID sobrevivam à reutilização do slot.

`proc_commit` alinha o endereço virtual à página, pesquisa linearmente se a página já pertence ao processo, aloca um frame, zera os 4096 bytes, cria o mapping com `MM_USER`, registra `virt/phys` e, se o processo for o corrente, invalida o TLB. O vetor fixo de 288 páginas funciona simultaneamente como registro de ownership e limite de páginas explicitamente rastreadas por esse mecanismo.

## Segurança

Gate DPL3 é intencionalmente limitado. Ponteiros são traduzidos. fd tem owner. Seletores e PTEs separam user/kernel.

API não é POSIX e não deve herdar por documentação semânticas de Linux.

## Concorrência e estado global

O modelo atual não é reentrante entre CPUs. `g_current` é global, assim como a continuação de retorno de user mode e o status de saída; a tabela de arquivos também usa ownership por PID sem lock nessa camada. `proc_switch` gera panic se chamado fora do BSP, enquanto `syscall_dispatch` rejeita uma syscall observada em CPU diferente de zero.

Essa restrição é um invariante arquitetural atual, não apenas uma limitação de performance. Para processos nativos SMP seriam necessários, no mínimo, current-process por CPU, ownership definido para continuações de retorno, sincronização das tabelas compartilhadas, regras para residência de CR3 e coordenação entre destruição de processo e syscalls em andamento.

## Resumo de custo algorítmico

| Operação | Representação atual | Característica de custo |
|---|---|---|
| alocar PID | scan dos slots 1–31 | `O(PROC_MAX)`, limitado a 31 candidatos |
| alocar fd | scan de 2–7 | `O(UFILE_MAX)`, limitado a 6 candidatos |
| validar ownership de fd | índice + comparação de PID | `O(1)` |
| limpar fds de um owner | scan 2–7 | `O(UFILE_MAX)` |
| copiar memória user | tradução por página + cópia por byte | `O(p * T_translate + n)` |
| procurar página em `proc_commit` | scan linear de `ProcPage[]` | `O(npages)` |
| destruir processo | liberar páginas + address space + recursos | pelo menos `O(npages + UFILE_MAX)`, além dos custos inferiores |

Os limites fixos tornam esses algoritmos adequados ao sistema experimental atual, mas as mesmas estruturas se tornariam gargalos antes de atingir quantidade de processos típica de um sistema desktop geral.

## Desempenho

`int 0x80` e cópia byte a byte privilegiam clareza. Buffers são pequenos.

Fast path futuro pode usar SYSCALL/SYSRET e I/O maior, mantendo validação/ownership.

## Evidência executável existente

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, `tools/test_sys_write.c` fornece uma evidência host focada em apenas uma fronteira do ABI. O teste verifica que payload de 80 bytes é aceito quando há capacidade 81 para o NUL, que capacidade 80 é rejeitada para payload 80 e que comprimento 81 é rejeitado.

Essa evidência valida especificamente `syscall_write_term`. Ela não demonstra funcionamento de ownership de fd, tradução de user-copy, saída de processo, contenção de faults nem do caminho completo `int 0x80` em um kernel inicializado. Esses contratos exigem evidência host adicional e, para o fluxo real de entrada/retorno, gates em QEMU ou hardware.

## Validação

Testar todas syscalls, número inválido, limites 80/512, pointers inválidos/cross-page, exaustão/ownership de fd, close/destroy, exit, fault containment, AP rejection e bordas de graphics/input.

## Matriz prática de erro

A superfície de erro também é parte do ABI atual:

| Caso | Resultado observado na camada |
|---|---|
| syscall em AP | RAX = -1, RIP avança 2 |
| número desconhecido | RAX = -1, RIP avança 2 |
| `WRITE` com fd != 1 ou n > 80 | -1 |
| user-copy inválida | -1 |
| `FOPEN` sem slot | -1 |
| `FREAD` sem ownership ou n > 512 | -1 |
| `FWRITE` n > 512 | -1 |
| `FCLOSE` inválido/não owned | 0 |
| user fault fatal não resolvido | processo destruído, código -11, retorno ao kernel |

A tabela descreve a implementação atual; não é uma promessa de que todos esses códigos permanecerão imutáveis em uma ABI futura.

## Limitações atuais

31 processos user, seis fds dinâmicos nesse layer, userspace BSP-only, fd por path, sem fork/exec/wait POSIX, sem signals e sem SYSCALL/SYSRET.

São limites explícitos.

## Reconciliação de revisão

Esta página foi reconciliada da revisão `da3df29cb397932c43d32373871fb9380e688ade` para `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Os commits intermediários alteraram documentação do repositório, arquivos de contribuição e metadados relacionados, mas não modificaram os arquivos de implementação que definem o contrato de processos e syscalls listado no frontmatter. Assim, a revisão inspecionada pode avançar sem atribuir comportamento novo ao runtime.

## Mapa de fonte

`proc.c`/`proc.h`: processo. `user_enter.c`: entry. `idt.c`/`irq.c`/`syscall.c`: ABI. `elf.c`: executable loading. FS/input/graphics: serviços concretos. Source Atlas publica tudo integralmente.
