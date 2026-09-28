---
id: resource-lifetime
lang: pt-br
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/proc.c
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/heap.c
  - kernel/metal/kthread.c
  - kernel/metal/syscall.c
  - kernel/net/sock.c
  - kernel/lang/clvm_sys.c
  - compiler/lang_pipeline.c
  - compiler/jit/jit.c
  - kernel/gfx/gfx_slot.c
  - kernel/gfx/gfx3d.c
  - kernel/gfx/shader/sh_api.c
  - kernel/metal/job.c
symbols:
  - proc_destroy
  - proc_release_user
  - mm_free_user_space
  - mm_tlb_shootdown_range
  - mm_tlb_quarantine
  - kthread_join
  - lang_kill
  - lang_slot_release_gfx
  - clvm_sys_close_slot
  - syscall_close_owner
  - sock_close_slot
  - sock_close_proc
  - gfx_slot_free
  - gfx3d_context_destroy
  - sh_guest_drop_owner
depends_on:
  - heap-ownership
  - spinlocks
  - tlb-shootdown
related:
  - process-lifecycle
  - kernel-jobs-kthreads
  - jit-memory
  - address-spaces
---

# Lifetime de recursos, teardown e reclamation segura

## Escopo

Alocar é apenas metade do gerenciamento de recursos.

Um objeto do kernel só pode ser reclamado quando todo ator que ainda possa alcançá-lo, executá-lo, fazer DMA sobre ele, possuir tradução para ele ou usá-lo de outra forma já tiver parado.

O ChrisOS não possui atualmente um object manager universal nem garbage collector de recursos do kernel. Lifetime é representado por regras de ownership específicas de cada subsistema e por destroy paths explícitos.

Exemplos:

- páginas físicas e page tables pertencentes a processos;
- buffers do heap;
- stacks de kthreads;
- frames físicos e mappings executáveis do JIT;
- buffers de slots gráficos;
- objetos de shader/program;
- file descriptors do CLVM;
- slots TCP;
- input capture;
- handles de syscall vinculados ao processo.

O problema de engenharia é comum:

~~~text
criação -> publicação -> uso ativo -> detach -> quiescência -> reclamation
~~~

Free antes de detach ou quiescência cria use-after-free. Recurso desacoplado que nunca é reclamado vira leak.

![Ordem genérica de teardown de recursos](../../assets/diagrams/resource-lifetime-pt-br.svg)

## Ownership versus reachability

Ownership responde qual subsistema é responsável por destruir o recurso.

Reachability responde quem ainda consegue acessá-lo agora.

São perguntas diferentes.

Um processo pode ser o owner de uma página enquanto:

- sua page table ainda mapeia essa página;
- uma CPU ainda possui a tradução no TLB;
- alguma estrutura ainda guarda o endereço físico.

O owner é conhecido, mas a página ainda não está necessariamente pronta para reutilização.

Da mesma forma, um slot de runtime pode ser owner de uma superfície gráfica enquanto task/window state ainda referencia esse slot.

## Máquina de estados de teardown

Um modelo útil é:

1. **Impedir criação de novas referências.**
2. **Marcar o objeto como closing/dying quando necessário.**
3. **Remover handles e referências públicas.**
4. **Aguardar usuários em voo.**
5. **Parar produtores assíncronos, como CPUs, devices ou callbacks.**
6. **Desmapear ou invalidar addressability.**
7. **Destruir recursos filhos.**
8. **Liberar backing storage.**
9. **Limpar metadata de ownership antes de reutilizar o slot.**

Nem todo recurso do ChrisOS possui todos esses estados explícitos.

A ordem continua sendo o princípio central.

## Por que lock não resolve lifetime

Spinlock impede mutação simultânea do estado protegido.

Ele não garante que o objeto continua vivo depois do unlock.

Exemplo:

~~~text
CPU A adquire lock
CPU A remove ponteiro da tabela
CPU A libera lock
CPU A libera objeto

CPU B já tinha copiado o ponteiro antes da remoção
CPU B usa memória já liberada
~~~

O lock pode estar correto e o lifetime ainda estar errado.

As soluções dependem do recurso:

- reference counting;
- generation handles;
- join/wait;
- owner sweep;
- quiescência de hardware;
- TLB shootdown;
- quarantine;
- lifetime até reboot.

O ChrisOS usa diferentes mecanismos em subsistemas diferentes.

## Relação pai-filho

Muitos objetos formam árvores de ownership.

Um processo possui:

- user leaf frames;
- page tables do lower half;
- PML4;
- handles de syscall;
- sockets vinculados ao PID.

Um slot de runtime pode possuir:

- frames do JIT;
- RAM do VM;
- superfícies gráficas;
- shaders/programs;
- sockets;
- CLVM file handles;
- processo associado.

O destroy do pai precisa:

- destruir filhos;
- transferir ownership;
- ou comprovar que o filho possui lifecycle independente.

Apenas limpar o slot do pai não basta.

## Destruição de processo

proc_destroy é um teardown multi-camada.

A sequência atual é aproximadamente:

~~~text
se o processo é o atual:
    muda para o processo kernel

libera user leaf pages
libera page tables lower-half e PML4
fecha recursos de syscall pertencentes ao PID
fecha sockets do processo
marca o slot como livre
~~~

O primeiro passo é essencial.

Um processo não pode destruir o PML4 que ainda está carregado em CR3 no BSP.

Se o alvo é o processo corrente, proc_destroy primeiro executa proc_switch(PROC_KERNEL).

## Ownership dos user leaf frames

proc_release_user percorre o ledger de páginas do processo.

Para cada entrada:

1. remove o mapping com mm_unmap_cr3;
2. devolve o frame com pmm_free;
3. limpa a entrada.

Depois zera:

- npages;
- vm_bytes;
- fb_pages;
- heap_brk.

Existe uma separação clara:

~~~text
Proc.pages[] possui os frames de dados do processo
MM possui os frames das page tables intermediárias
~~~

Cada classe é destruída por função diferente.

## Destruição da hierarquia de page tables

mm_free_user_space percorre somente PML4[0..255].

Esses são os entries do user half.

A metade superior é compartilhada com o espaço do kernel e não deve ser liberada durante teardown de um processo.

A função recursivamente libera page-table frames, depois o PML4 root.

Ela não libera os user leaf frames.

Isso evita double-free, pois os leaf frames já pertencem ao ledger do processo.

## Hipótese atual sobre TLB de usuário

Existe uma dependência arquitetural importante.

proc_release_user remove mapping e imediatamente executa pmm_free no frame.

mm_unmap_cr3 faz invalidation local somente quando o CR3 alvo é o CR3 corrente.

O scheduler nativo de processos continua BSP-only.

O desenho atual depende, portanto, do fato de address spaces de usuário não executarem em APs arbitrários.

Se no futuro processos migrarem ou rodarem simultaneamente em vários CPUs, o teardown precisará de shootdown/quiescência por address space antes de reutilizar os leaf frames.

O protocolo atual de TLB para mappings compartilhados mostra a classe de solução necessária, mas proc_destroy ainda não é um algoritmo geral de reclamation SMP de address spaces.

## Fechamento de recursos do processo

Depois do teardown de memória, proc_destroy chama:

- syscall_close_owner(pid);
- sock_close_proc(pid).

Essas funções procuram recursos pelo owner e os fecham.

É um padrão de owner sweep.

O Proc não precisa armazenar todos os sockets individualmente quando o subsystem de sockets consegue enumerar sua tabela por owner.

O custo é que toda nova classe de recurso precisa participar explicitamente do destroy path.

## Cleanup indexado por owner

Vários subsistemas usam owner IDs:

- sockets;
- shader guest objects;
- graphics 3D handles;
- syscall file entries;
- CLVM file entries.

Isso permite:

~~~text
para cada recurso:
    se resource.owner == owner_em_teardown:
        destroy(resource)
~~~

É simples e adequado a tabelas pequenas e limitadas.

Também impõe O(N) por sweep e exige disciplina para que novos tipos de recurso não sejam esquecidos.

## Teardown de runtime slot

lang_kill é o caminho principal de teardown de um slot de VM.

A sequência revisada inclui:

1. liberar JIT;
2. liberar RAM do slot;
3. liberar graphics state;
4. fechar recursos CLVM/system;
5. liberar loaded-file buffer;
6. destruir processo associado;
7. marcar slot unused;
8. limpar dying/task/name/JIT state.

Esse é um destructor que cruza vários subsistemas.

A ordem importa porque recursos filhos ainda usam a identidade do slot durante o cleanup.

## Por que o JIT é liberado cedo

lang_kill chama jit_free antes de limpar estado principal do slot.

Memória JIT pode estar executável e possui requisitos de reclamation mais fortes que um buffer comum do heap.

jit_free:

1. remove os mappings de execução;
2. executa TLB shootdown;
3. devolve os frames ao PMM somente se reuse for seguro;
4. caso contrário, coloca os frames em quarantine.

O slot é owner do JIT, mas ownership não comprova ausência de stale translation.

## RAM do slot

O runtime mantém memória do VM separada dos frames executáveis do JIT.

Durante teardown essa RAM é liberada ou desacoplada antes de o slot se tornar reutilizável.

A invariante é:

~~~text
slot reutilizável -> nenhuma referência de memória do runtime anterior
~~~

Reutilizar o slot antes de destruir filhos faria owner-based cleanup apontar para a entidade errada.

## Teardown gráfico

lang_slot_release_gfx chama gfx_slot_free para o graphics slot.

gfx_slot_free libera:

- pixel buffer;
- z-buffer opcional.

Depois zera pointers, used flag e restaura defaults do z-buffer global.

O slot gráfico não é simplesmente marcado livre deixando backing memory alocada.

## Resize como transação de replacement

gfx_slot_resize e gfx_slot_resize2d seguem um padrão importante.

Primeiro alocam o novo buffer.

Somente após sucesso liberam o buffer antigo e publicam os novos pointers.

~~~text
aloca replacement
se falhar:
    mantém objeto antigo válido
senão:
    libera antigo
    publica novo
~~~

Liberar primeiro e alocar depois transformaria falha de memória em perda de estado válido.

## Handles com geração

O subsystem 3D usa handles com componente de geração.

Quando um slot é reutilizado, a geração muda.

Isso reduz o risco de um stale handle antigo se tornar válido automaticamente para outro objeto que ocupou o mesmo índice.

Generation handles são defesa de lifetime.

Não substituem teardown real, mas ajudam a detectar referências que sobreviveram ao objeto.

## CPU backing e device backing

Recursos gráficos podem existir em duas camadas.

Um mesh pode possuir:

- buffers no heap;
- buffers no device/VirGL.

release_mesh_dev destrói objetos do device.

mesh_free_buf libera memória CPU.

Uma ordem segura é conceitualmente:

~~~text
parar/destruir objeto visível ao device
liberar backing CPU
marcar slot morto
~~~

Recursos de hardware podem exigir quiescência mais forte que objetos comuns do heap.

## Cleanup de shaders por owner

clvm_sys_close_slot chama sh_guest_drop_owner(slot_id).

A função percorre tabelas de guest shaders e programs e destrói todos os objetos do owner.

Isso impede que um VM slot morto deixe recursos persistentes nas tabelas globais.

O teste de shader também verifica comportamento de owner cleanup.

## File descriptors do CLVM

Entries de arquivo podem manter:

- buffer no heap;
- dirty state;
- path;
- posição;
- capacidade.

fd_free:

1. escreve dirty buffer quando necessário;
2. libera o buffer;
3. zera pointer;
4. zera used/dirty/streaming state.

clvm_sys_close_slot percorre todos os file entries e fecha os do slot.

Assim um VM que termina anormalmente não depende de ter chamado fclose cooperativamente.

Essa é uma regra importante:

> exit do processo/runtime deve limpar recursos mesmo quando o guest não cooperou.

## Sockets

clvm_sys_close_slot chama sock_close_slot.

proc_destroy também chama sock_close_proc.

sock_close_matching percorre a socket table.

Se a conexão está established, tenta enviar close antes de marcar:

~~~text
state = SK_FREE
slot = -1
~~~

O teardown TCP é simplificado, mas ownership da tabela é removido explicitamente.

## Recursos lógicos

O close do slot também libera:

- input capture;
- voxel ownership;
- shader owner state;
- sockets;
- files.

Nem todos são allocations de bytes.

Lifetime também se aplica a capabilities e tokens lógicos.

Um slot morto não pode continuar sendo reconhecido como dono do input capture.

## Lifetime de kthread

kthread_create aloca stack privada de 32 KiB no heap.

O callback roda e depois marca done.

kthread_join espera done.

Somente então:

1. adquire g_slot_lock;
2. retira o pointer da stack;
3. limpa metadata do slot;
4. libera o lock;
5. chama kfree.

O wait é a etapa de quiescência.

Liberar a stack enquanto kt_run ainda executa sobre ela destruiria o contexto da própria CPU.

## Detach antes de free

kthread_join mostra um padrão útil.

A referência pública é removida sob lock.

O free ocorre depois do unlock.

~~~text
lock da tabela
remove referência pública
unlock
free do objeto desacoplado
~~~

Isso evita que outro código encontre o pointer pelo slot e também reduz nesting de locks com o heap.

## Lifetime de argumentos de jobs

job_submit armazena:

- function pointer;
- void *arg.

A fila não copia o objeto apontado.

O submitter precisa garantir que arg continue vivo até o worker executar o callback.

É um borrowed-reference contract implícito.

Passar pointer para variável local que saiu de escopo, ou liberar o heap object logo após submit, seria incorreto.

O inflight counter mede jobs, não reference counts de argumentos.

## Estado dying

Quando teardown é multi-etapas, um estado dying ajuda a impedir operações normais sobre um objeto parcialmente destruído.

lang_kill aceita slots used ou dying e só limpa dying no final.

Um modelo mais formal seria:

~~~text
FREE -> INITIALIZING -> LIVE -> DYING -> FREE
~~~

Nem todo subsystem implementa esses estados explicitamente, mas o modelo ajuda a evitar double teardown e early reuse.

## Idempotência

Destroy APIs têm contratos diferentes.

Exemplos:

- kfree detecta double-free e entra em panic;
- vários slot destroy retornam silenciosamente para ID inválido;
- jit_free retorna se buf é null ou phys é zero;
- proc_destroy retorna para PID inválido ou unused.

Destroy idempotente facilita rollback.

Destroy não-idempotente pode detectar bugs com mais agressividade.

O contrato precisa ser conhecido por recurso.

## Partial construction e rollback

Criação pode falhar depois de adquirir recursos.

O caminho correto libera apenas o que já foi adquirido.

Exemplos atuais:

- graphics allocation libera primeiro buffer se o segundo falha;
- JIT devolve frames físicos se a alocação de virtual range falha;
- proc_create chama proc_destroy quando stack inicial não consegue ser committed.

Padrão:

~~~text
adquire A
adquire B
adquire C

se C falha:
    libera B
    libera A
~~~

Rollback normalmente segue a ordem inversa de dependência.

## Reclamation de memória executável

JIT é o caso mais forte de reclamation atrasada.

Depois de unmap, outra CPU ainda pode possuir a tradução no TLB.

Se os frames forem devolvidos imediatamente ao PMM, eles podem ser reutilizados para dados enquanto uma CPU stale ainda consegue executar aquele endereço.

A relação segura é:

~~~text
unmap
  ->
invalidation nos CPUs relevantes
  ->
provar reuse seguro
  ->
liberar frame
~~~

Se a prova falha, o ChrisOS usa quarantine.

Leak é preferível a execução stale.

## TLB quarantine

MM mantém uma quarantine limitada de extents físicos.

mm_tlb_quarantine libera imediatamente quando reuse já é seguro.

Caso contrário armazena o extent.

mm_tlb_reap libera posteriormente quando o protocolo TLB sinaliza segurança.

Se a quarantine está cheia, o novo extent não é liberado.

Isso pode causar leak, mas preserva a invariante:

~~~text
resource exhaustion > unsafe physical reuse
~~~

## Destruição lógica versus física

Um recurso pode estar logicamente morto antes de sua memória física ficar disponível.

No caso de JIT quarantined:

- o runtime não expõe mais o JIT;
- o virtual mapping foi removido;
- os frames podem continuar reservados.

Assim “destroyed” na API não significa necessariamente “páginas já retornaram ao allocator”.

## Lifetime e segurança

Use-after-free é problema de segurança porque uma referência stale pode acabar acessando memória pertencente a um novo owner.

Defesas atuais incluem:

- limpar owner state antes de slot reuse;
- generation handles em parte do graphics stack;
- owner validation;
- unmap antes de physical reuse;
- cleanup independente de cooperação do guest;
- zerar pointers depois de free.

Ainda não há infraestrutura kernel-wide para:

- generic reference counting;
- RCU/epoch reclamation;
- lockdep de lifetime;
- heap poisoning;
- geração universal de objetos.

O modelo é explícito e específico por subsystem.

## Estratégia de validação

Lifetime precisa de testes de destruição, não só de criação.

Evidências úteis:

- ciclos repetidos create/destroy;
- rollback sob allocation failure;
- owner cleanup depois de morte anormal;
- contadores gráficos voltando ao baseline;
- teardown TLB cross-CPU;
- stale handles rejeitados depois de slot reuse;
- kthread join antes do free da stack;
- file buffers liberados no close;
- sockets removidos depois do owner morrer.

O demo VirGL contém verificação de resource leak em destroy.

Os testes do protocolo TLB comprovam que reuse permanece bloqueado até acknowledgement ou condições de fenced/flush/halt.

## Limitações arquiteturais atuais

Na revisão analisada:

- não existe ownership registry global;
- destroy order é codificada manualmente por subsystem;
- owner sweep usa tabelas limitadas e scanning;
- address-space reclamation depende de user execution BSP-only;
- alguns recursos possuem lifetime até reboot;
- job arguments são raw borrowed pointers;
- quarantine TLB é limitada e pode vazar memória intencionalmente;
- APIs têm contratos diferentes de idempotência e stale-handle defense.

Por isso a documentação de teardown é parte essencial da arquitetura.

## Checklist para novos recursos

Ao adicionar novo tipo de recurso:

1. Quem aloca?
2. Quem se torna owner?
3. Ownership pode ser transferido?
4. Quais tabelas/handles ainda podem alcançá-lo?
5. IRQ, AP, job ou device pode acessá-lo assincronamente?
6. Qual estado inicia teardown?
7. Como novas referências são bloqueadas?
8. Como usuários em voo chegam à quiescência?
9. Mapping/device binding é removido antes do backing?
10. O que ocorre se teardown falhar parcialmente?
11. Destroy repetido é válido?
12. Qual teste comprova retorno ao baseline?

Recurso sem essas respostas não possui lifecycle completo.

## Fronteira de revisão

Este capítulo foi reconciliado com ChrisOS main na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

O modelo atual não é apenas “chamar free”:

~~~text
identificar owner
  -> remover referências
  -> parar/aguardar usuários
  -> fechar ou desmapear filhos
  -> satisfazer quiescência de hardware/TLB
  -> liberar backing storage
  -> limpar owner metadata
  -> permitir reuse do slot
~~~

Processos, kthreads, runtime slots, graphics, files, sockets e JIT implementam partes diferentes dessa mesma invariante de lifetime.
