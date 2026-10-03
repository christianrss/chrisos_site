---
id: user-mode-entry
lang: pt-br
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/user_enter.c
  - kernel/metal/user_enter.h
  - kernel/metal/gdt.c
  - kernel/metal/gdt.h
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/syscall.c
  - kernel/metal/syscall.h
  - kernel/metal/idt.c
  - kernel/metal/irq.c
  - kernel/metal/irq.h
symbols:
  - enter_user
  - syscall_set_kernel_return
  - syscall_return_to_kernel
  - proc_switch
  - syscall_init
depends_on:
  - gdt-tss
  - virtual-memory
related:
  - user-copy
  - process-lifecycle
  - idt-exceptions
---

# Entrada em user mode e retorno controlado a ring 0

## Escopo

Executar aplicação em CPL 3 exige mais do que saltar para um endereço lower-half. A CPU precisa entrar com seletores de usuário, stack de usuário válida, page tables cujos mapeamentos tenham permissão User/Supervisor adequada, um caminho de interrupção/syscall para voltar ao kernel e uma continuação de ring 0 controlada pelo kernel para exit/fault.

O ChrisOS faz a queda de privilégio via `iretq` em `enter_user`. Processos e syscalls ao redor dessa função definem CR3, mapeamentos, gate `0x80` DPL 3, validação de memória e a capacidade de reescrever o frame salvo quando o usuário termina ou falha.

## CPL, seletores e permissões de página

Proteção x86-64 combina mecanismos. Os bits inferiores de CS definem Current Privilege Level. O descritor selecionado na GDT possui Descriptor Privilege Level. Page tables têm bit U/S para permitir ou proibir acesso de user mode.

Logo, contexto user exige simultaneamente:
- seletores válidos para ring 3;
- páginas marcadas como acessíveis ao usuário.

O ChrisOS define `GDT_USER_DATA = 0x18` e `GDT_USER_CODE = 0x20`. `enter_user` combina ambos com 3 para RPL 3.

Isso não muda permissões de page table. `proc_map_user` acrescenta `MM_USER` aos mapeamentos destinados ao processo.

## Contexto de address space

Cada processo possui CR3. `proc_create` chama `mm_clone_kernel_space` e cria a primeira página de stack de usuário.

`proc_switch` exige BSP; uma chamada em AP causa panic. Para PID válido, atualiza `g_current` e chama `mm_switch(cr3)`.

Portanto `enter_user` pressupõe que address space correto já foi selecionado. A função não escolhe CR3. Essa separação mantém ownership de memória em proc/mm e deixa a primitiva de transição arquitetural pequena.

## Regiões virtuais atuais

`proc.h` define bases:

| Região | Base |
|---|---:|
| VM | `0x02000000` |
| heap | `0x04000000` |
| framebuffer | `0x06000000` |
| stack | `0x07F00000` |
| library | `0x08000000` |

Esses valores formam o layout usado pela implementação atual, não um ABI genérico completo.

A região de stack pode crescer por demand commit em quatro páginas a partir de `PROC_STACK_VIRT`. O RSP passado para `enter_user` deve terminar em uma página user gravável, pois operações de stack começam imediatamente.

## Continuação do kernel

Antes de mudar CPL, `enter_user` obtém `__builtin_return_address(0)` e chama `syscall_set_kernel_return`.

Assim fica registrado um RIP de ring 0 associado ao call site. Exit e fault usam essa continuação para voltar ao kernel.

O estado é global, não um objeto por thread. Isso funciona dentro do modelo em que execução de usuário é serializada no BSP. Múltiplas tarefas user simultâneas em CPUs diferentes exigiriam estado de retorno per-task/per-CPU.

## Frame de `iretq`

A função monta:

```c
cs = GDT_USER_CODE | 3;
ss = GDT_USER_DATA | 3;
rflags = 0x202;
```

`0x202` deixa IF ativo em user mode.

A asm empilha:

```text
SS_user
RSP_user
RFLAGS
CS_user
RIP_user
iretq
```

`iretq` restaura RIP, CS e flags; como há transição de CPL 0→3, também instala RSP/SS de usuário.

O hardware valida privilégios e descritores. Não é equivalente a escrever CS diretamente nem simplesmente “rodar código em endereço baixo”.

## Validações feitas pela CPU

CS precisa apontar para descritor presente/executável compatível com CPL 3. SS precisa ser segmento de dados válido e gravável. RIP/RSP devem ser canônicos. Ao buscar a primeira instrução, page tables precisam permitir User access.

Inconsistências geram exceções como #GP ou #SS.

Mesmo depois de entrar, páginas legais mas ainda não residentes podem gerar #PF; o kernel pode materializá-las por demand paging e repetir a instrução.

## Entrada no kernel via syscall

`syscall_init` altera o gate 0x80 para DPL 3. Aplicação executa `int 0x80`, a CPU atravessa para seletor de código de ring 0 e o caminho comum produz `irq_frame`.

A infraestrutura TSS/GDT fornece stack privilegiada confiável quando há mudança de ring. Por isso user mode depende de GDT/TSS mesmo que o isolamento principal seja paging.

`irq_dispatch` reconhece 0x80 e chama `syscall_dispatch`.

## Restrição ao BSP

`syscall_dispatch` rejeita execução em CPU diferente de zero, colocando -1 em RAX e avançando RIP.

Isso acompanha a regra de `proc_switch`. O ChrisOS atual não migra contexto user para APs.

A restrição simplifica `g_current` e `g_user_kernel_rip` globais, mas limita escalabilidade.

## Contrato interno do `irq_frame`

A entrada de interrupção não entrega apenas um número de vetor. O stub comum organiza os registradores em `struct irq_frame`, definida em `irq.h`. A ordem inclui os registradores gerais, depois `vector`, `error`, `rip`, `cs` e `rflags`.

Esse layout é um ABI interno entre assembly e C. `syscall_dispatch` lê diretamente RAX como número, RDI/RSI/RDX como argumentos e altera RAX/RIP no próprio frame. `panic_user_fault` usa RIP e o código de erro; `irq_dispatch` consulta CS para distinguir origem ring 0 de ring 3.

Se a ordem de pushes no stub e a struct C divergirem, o kernel pode interpretar um registrador como outro mesmo que toda a numeração de syscalls permaneça correta. Por isso a compatibilidade do frame precisa ser tratada como parte da interface de entrada privilegiada.

## Retorno normal de syscall

A maioria das syscalls grava resultado em RAX salvo, avança RIP em 2 bytes e retorna ao stub. O stub restaura estado e executa `iretq` para ring 3.

O incremento de 2 corresponde ao tamanho de `int imm8` e ao convention adotado pelo frame do sistema. Essa convenção precisa permanecer consistente com o código user e os stubs.

Mudar para SYSCALL/SYSRET exigiria outra semântica de entry/return e registradores.

## Invariante de control flow no retorno

O retorno normal de syscall e o retorno de término compartilham o mesmo mecanismo físico de `iretq`, mas não o mesmo destino lógico. No retorno normal o frame preserva CS de usuário e avança para a próxima instrução user. No término, o kernel substitui RIP e CS para transformar o mesmo epílogo de interrupção em retorno privilegiado.

Isso reduz duplicação de assembly, mas cria um invariante: o formato do frame produzido na entrada precisa ser exatamente o formato que `syscall_return_to_kernel` espera modificar. Mudanças futuras em stubs, IST, stack frame ou mecanismo de syscall devem revalidar essa hipótese antes de reutilizar o caminho de saída.

## Exit e retorno a ring 0

Para `SYS_EXIT`, o kernel não quer executar a próxima instrução user. `syscall_return_to_kernel` altera o frame salvo:
- RIP = `g_user_kernel_rip`;
- CS = `GDT_KERNEL_CODE`;
- RFLAGS = `0x202`;
- `g_user_exited = 1`.

Quando o stub executa `iretq`, o destino é ring 0.

Alterações futuras no layout de frame ou stack precisam revalidar essa transformação; retornar entre níveis de privilégio não é apenas substituir um pointer.

## Fault de usuário

`panic_user_fault`, apesar do nome, não derruba o kernel. Registra fault do processo, destrói o PID, grava diagnóstico, coloca exit code -11 e usa o mesmo mecanismo de retorno ao kernel.

O dispatcher só escolhe esse caminho quando CS salvo indica origem user. Fault de ring 0 segue para panic global.

Assim uma falha de aplicação é contida no processo quando possível.

## Demand paging

No #PF, antes de matar o processo, `proc_fault_demand` recebe CR2. Ele reconhece VM, stack, heap e framebuffer dentro dos limites atuais.

`proc_commit` aloca frame físico, zera, mapeia com flags de user/write, registra ownership e pode flushar TLB do processo atual.

Se isso resolver a causa, `irq_dispatch` retorna sem alterar RIP. A instrução de usuário é repetida.

Logo, `enter_user` não precisa materializar antecipadamente todas as páginas de regiões lazy. Precisa apenas do conjunto inicial capaz de iniciar execução, incluindo entry e stack.

## Segurança

A fronteira resulta da composição:
- CS/SS de usuário têm RPL 3 e apontam a descritores DPL 3;
- mapeamentos user recebem `MM_USER` explicitamente;
- somente interfaces intencionais da IDT, como 0x80, têm DPL 3;
- operações privilegiadas permanecem inacessíveis ao CPL 3;
- ponteiros recebidos por syscall passam por tradução/checagem de flags, não apenas teste de canonicalidade.

Nenhuma dessas camadas sozinha é “todo o sandbox”.

## Ownership da continuação privilegiada

`g_user_kernel_rip` não pertence ao processo em uma estrutura `Proc`; ele pertence à execução user corrente do modelo global. `enter_user` o sobrescreve imediatamente antes da queda de privilégio, e tanto `SYS_EXIT` quanto fault fatal de user mode dependem desse valor.

Esse desenho funciona porque o sistema impede process switching em AP e trata a execução nativa como fluxo serializado no BSP. Se duas execuções user independentes pudessem coexistir, a segunda poderia substituir a continuação da primeira. A evolução para SMP precisa mover esse estado para uma estrutura com ownership explícito por thread/processo ou por CPU.

## Estado global

`g_user_kernel_rip`, exit flags e `g_current` são globais. A regra BSP-only torna isso coerente na revisão atual.

Para userspace SMP, esses campos precisariam migrar para estruturas por thread/processo/CPU e teardown teria que sincronizar com execução remota.

## IF e interrupções

User RFLAGS inicial é `0x202`, portanto IF=1. IRQs mascaráveis podem interromper aplicação quando controladores também permitem.

Interrupt gate limpa IF na entrada privilegiada; `iretq` restaura flags salvas no retorno. O kernel não precisa setar IF manualmente apenas para preservar o estado user.

NMI permanece independente de IF.

## Segurança da stack

Stack user não pode funcionar como stack privilegiada confiável. A transição para ring 0 utiliza estado do TSS.

Na direção oposta, `enter_user` instala deliberadamente o RSP fornecido. O caller precisa apontá-lo para região válida do processo. Hardware detecta mapeamentos/seletores ilegais, mas a semântica do layout é responsabilidade do loader/runtime.

O TSS atual tem `rsp0` fixo, não stack de kernel por user thread. Isso acompanha o modelo serial no BSP.

## Falhas possíveis

Transição pode falhar por seletor inválido, endereço não canônico, página ausente sem demand handling, página supervisor-only, stack descriptor errado ou corrupção de GDT/TSS.

Depois de entrar, privileged instruction, ponteiro ilegal ou acesso fora das regiões podem faultar. Demand fault válido é recuperado; fault user inválido encerra o processo; fault kernel paralisa o sistema.

Corrupção de `g_user_kernel_rip` faria exit voltar ao endereço privilegiado errado. Apesar de pequeno, esse estado faz parte da integridade de control flow.

## Desempenho

`iretq` + `int 0x80` priorizam clareza e integração com o dispatcher comum, mas não são a interface de syscall de menor overhead disponível em x86-64. SYSCALL/SYSRET é alternativa futura.

Demand paging reduz commitment inicial e desloca custo para first touch, introduzindo latência de page fault.

A decisão sobre otimização deve ser baseada em medição, não apenas no custo teórico da instrução.

## Evidência e limites da revisão

A revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56` preserva os mesmos arquivos de implementação de user entry, processo e syscall usados pela revisão anteriormente documentada. Os commits intermediários alteraram principalmente documentação e metadados do repositório, não o mecanismo de transição descrito aqui.

Isso permite avançar `reviewed_revision` sem inferir comportamento novo. Ainda assim, inspeção estática prova somente a estrutura do mecanismo. A correção efetiva da sequência `iretq`, da troca de stack via TSS e do retorno por frame depende de execução em ambiente compatível; portanto, boot/QEMU/hardware continuam sendo evidência necessária para a transição completa.

## Validação

Gates relevantes devem provar:
- CPL 3 depois da entrada;
- todas as syscalls suportadas;
- IRQ durante execução user;
- demand page com retry transparente;
- acesso inválido terminando somente o processo;
- exit retornando à continuação kernel correta;
- páginas supervisor-only inacessíveis;
- política BSP-only preservada.

Fonte mostra mecanismo; testes demonstram que descritores, paging e frame realmente concordam.

## Limitações atuais

Execução user é BSP-only. Return target é global. TSS usa stack ring-0 fixa. Syscall é `int 0x80`. Layout virtual e número de processos/páginas são limitados por constantes.

São limites do ChrisOS atual, não limites inerentes ao x86-64.

## Resumo dos invariantes

A transição é correta somente enquanto todos estes contratos permanecem simultaneamente verdadeiros:

- CR3 do processo correto já está ativo antes de `enter_user`;
- RIP e RSP user são canônicos e mapeados com `MM_USER`;
- seletores GDT de código/dados aceitam CPL 3;
- TSS fornece stack privilegiada válida para a entrada no kernel;
- gate 0x80 permanece DPL 3 e os demais gates não são acidentalmente expostos;
- layout assembly do frame coincide com `struct irq_frame`;
- retorno global aponta para continuação kernel válida;
- política BSP-only impede corrida sobre estado global de execução user.

A quebra de qualquer camada pode produzir #GP/#SS/#PF, corrupção de retorno ou escalonamento inseguro. Esse é o motivo para tratar user-mode entry como composição de contratos, não como uma única instrução `iretq`.

## Mapa de fonte

A transição está em `kernel/metal/user_enter.c`. GDT/TSS em `gdt.c`/`gdt.h`. CR3 e regiões user em `proc.c`/`proc.h`. Retorno e syscall 0x80 em `syscall.c`/`syscall.h`; `idt.c` expõe DPL 3. O Source Atlas publica todos integralmente na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
