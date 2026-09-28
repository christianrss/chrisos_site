---
id: arrays-lists-stacks-queues
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
  - kernel/metal/job.h
  - kernel/metal/job.c
  - kernel/gfx/input.c
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_parse.c
symbols:
  - ClvmVm
  - clvm_vm_push64
  - clvm_vm_pop64
  - job_init
  - job_submit
  - job_worker_once
  - queue_push
  - input_next_event
  - Ast
  - ShComp
  - sh_parse
depends_on:
  - data-structures
  - recursion-recurrences-amortization
related:
  - bitmaps-rings-free-lists
  - systems-algorithms
  - chrisc-clvm
  - shader-frontend
---

# Arrays, estruturas ligadas, stacks e queues

<div class="abstract">
Arrays, estruturas ligadas, stacks e queues são blocos lineares fundamentais sob schedulers, interpretadores, parsers, device rings e sistemas de eventos. Suas operações assintóticas são simples, mas correção em sistemas depende da representação concreta: armazenamento contíguo ou indireto, capacidade fixa ou dinâmica, validade de índices e pointers, ownership, localidade de cache, comportamento de overflow/underflow, sincronização e memory ordering. Este capítulo desenvolve esses contratos e os reconcilia com o source atual do ChrisOS. CLVM usa operand e call stacks limitadas sobre arrays; o subsistema de jobs do kernel usa queue circular de 1024 entradas protegida por spinlock; o input subsystem usa ring de 64 slots que reserva uma posição para distinguir cheio de vazio e contabiliza eventos descartados; e o parser de shaders armazena nodes da AST em array fixo enquanto encadeia sequências de statements e argumentos por índices inteiros next.
</div>

## Pré-requisitos e escopo

O capítulo geral de estruturas de dados define representação, invariantes e modelos de custo. O capítulo anterior de amortização explica crescimento geométrico e custo de sequências.

Aqui o foco é reduzido a quatro famílias lineares:

- arrays;
- estruturas ligadas;
- stacks;
- queues/rings.

Elas podem representar a mesma sequência lógica otimizando operações diferentes.

Uma descrição de sistemas precisa separar:

~~~text
semântica abstrata da sequência
        ↓
representação concreta
        ↓
capacidade e ownership
        ↓
sincronização
        ↓
comportamento de falha
~~~

Chamar uma estrutura de queue não informa se ela aloca, bloqueia, descarta dados, sobrescreve entradas antigas ou rejeita inserção.

## Arrays

Um array armazena elementos de mesmo tamanho de forma contígua.

Para endereço base B, tamanho de elemento s e índice zero-based i:

~~~text
address(A[i]) = B + i·s
~~~

Isso permite cálculo O(1) do endereço.

A fórmula só é válida quando:

~~~text
0 <= i < length
~~~

e multiplicação/soma permanecem dentro do contrato de aritmética de endereços.

## Layout e localidade de arrays

Armazenamento contíguo oferece forte spatial locality.

Traversal sequencial:

~~~text
A[0], A[1], A[2], ...
~~~

tende a acessar cache lines próximas e favorece hardware prefetch.

Isso frequentemente torna arrays mais rápidos que estruturas pointer-linked mesmo quando ambos realizam O(n) de trabalho lógico.

O modelo de custo deve considerar:

- tamanho de elemento;
- alignment e padding;
- ocupação de cache lines;
- ordem de acesso;
- write sharing entre CPUs.

Big-O isoladamente não captura localidade.

## Arrays de capacidade fixa

Um array fixo reserva armazenamento para uma quantidade máxima de elementos.

Vantagens:

- nenhuma dependência de allocator após inicialização;
- endereços estáveis dos elementos;
- footprint previsível;
- bounds checks diretos;
- saturação determinística quando especificada.

Desvantagens:

- espaço reservado e eventualmente ocioso;
- limite máximo rígido;
- possível necessidade de scans lineares para achar slots livres.

ChrisOS usa arrays fixos em vários caminhos de baixo nível nos quais memória limitada é preferível a crescimento dinâmico.

## Arrays dinâmicos

Um dynamic array normalmente mantém:

~~~text
pointer
length
capacity
~~~

Quando length atinge capacity, uma região maior é alocada e os elementos são copiados ou movidos.

Crescimento geométrico fornece append O(1) amortizado, mas um grow individual continua O(n).

Resize também pode:

- falhar por allocation;
- invalidar pointers para elementos;
- mudar localidade virtual/física;
- exigir sincronização durante substituição do pointer;
- gerar latency spike.

Esses efeitos importam mais em kernel e interrupt paths que o bound amortizado isolado.

## Inserção e remoção em arrays

Append em slot final livre conhecido é O(1).

Inserir no meio exige mover um sufixo:

~~~text
[a b c d]
inserir x em 1
[a x b c d]
~~~

A quantidade movida é proporcional ao tamanho do sufixo.

Delete que preserva ordem também move elementos posteriores para a esquerda.

Quando ordem não importa, delete pode às vezes ser O(1) movendo o último elemento para o slot removido. Isso altera a ordem da sequência e exige contrato semântico diferente.

## Espaços de índices densos e esparsos

Array é adequado quando identificadores válidos formam intervalo denso e limitado.

Se IDs são esparsos, direct array pode desperdiçar memória.

Software de sistemas frequentemente mapeia:

- CPU IDs;
- descriptors;
- object handles;
- índices de AST;
- valores de opcode;

para arrays quando o domínio é suficientemente denso.

Validade do índice é diferente de o slot conter atualmente um objeto vivo.

## Estruturas ligadas

Uma estrutura ligada armazena relações entre elementos em vez de depender apenas de posição contígua.

Um node singly linked costuma conter:

~~~text
payload
next
~~~

Uma doubly linked list acrescenta:

~~~text
prev
~~~

Inserção após node conhecido pode custar O(1), mas localizar esse node pode já ter exigido O(n).

Afirmações de complexidade precisam dizer qual referência já é fornecida à operação.

## Listas ligadas por pointers

Em uma pointer-linked list, next e prev são endereços de memória.

Vantagens:

- endereços estáveis quando nodes são alocados individualmente ou embutidos;
- splice O(1) quando os pointers relevantes já são conhecidos;
- suporte natural a intrusive linkage.

Custos:

- armazenamento de pointers;
- gerenciamento por allocator ou pool;
- localidade ruim quando nodes ficam espalhados;
- mais misses de cache/TLB;
- lifetime rules mais complexas.

Pointer obsoleto pode transformar erro lógico de lista em corrupção de memória.

## Listas ligadas por índices

Uma lista também pode usar índices de array em vez de pointers.

Por exemplo:

~~~text
nodes[i].next = j
~~~

com -1 representando ausência de sucessor.

Essa representação combina:

- armazenamento contíguo dos nodes;
- referências inteiras estáveis enquanto o array não é compactado;
- bounds checking explícito;
- serialização mais simples que host pointers.

O custo é um node pool fixo ou gerenciado separadamente e um acesso indexado extra a cada passo.

## Cadeias da AST de shaders no ChrisOS

O parser atual contém:

~~~text
Ast ast[SH_AST_MAX]
~~~

e cada Ast contém:

~~~text
int16_t next
~~~

Rotinas como parse_args, parse_block, parse_global_or_func e sh_parse constroem sequências armazenando o índice do próximo node em ast[tail].next.

Isso é uma sequência index-linked dentro de array fixo.

Não é uma biblioteca genérica heap-allocated de linked lists.

A distinção afeta:

- ownership;
- serialização;
- localidade;
- capacidade;
- comportamento diante de índice inválido.

node_new impõe o limite da AST antes de criar outro node.

## Invariantes de listas

Para sequência singly linked representada por índices, invariantes úteis incluem:

- head é -1 ou índice válido e ativo;
- todo next é -1 ou índice válido e ativo;
- traversal chega a -1 quando ciclos são proibidos;
- cada node aparece uma única vez quando unicidade é exigida;
- tail.next = -1 quando existe tail explícito.

Um algoritmo que assume aciclicidade pode entrar em loop infinito se a representação contiver ciclo.

Cycle detection é portanto um problema de validação ou um invariante garantido por construção.

## Complexidade de traversal

Percorrer k nodes ligados custa O(k).

Acesso ao i-ésimo elemento custa O(i), pois os links precisam ser seguidos a partir de referência conhecida.

Isso contrasta com indexing O(1) de arrays.

Pointer chasing também prejudica localidade, embora a AST index-linked do ChrisOS mantenha seus nodes contíguos e preserve densidade melhor que nodes individualmente alocados.

## Estruturas intrusivas

Uma estrutura intrusive embute campos de linkage no próprio objeto.

Vantagens:

- sem node allocation separado;
- conversão direta entre link e owner quando layout é conhecido;
- menos objetos auxiliares.

O custo é acoplamento: um objeto precisa de linkage fields distintos para participar de múltiplas coleções independentes.

Os nodes da AST index-linked são semelhantes em espírito, pois o linkage pertence ao próprio Ast, embora use índice inteiro em vez de pointer.

## Stacks

Uma stack segue last-in, first-out.

Operações abstratas:

~~~text
push(x)
pop()
top()
empty()
~~~

Uma stack baseada em array mantém um top ou stack pointer.

Representação comum:

~~~text
storage[capacity]
sp = quantidade de elementos ativos
~~~

Então:

~~~text
push:
    exigir sp < capacity
    storage[sp] = x
    sp++

pop:
    exigir sp > 0
    sp--
    retornar storage[sp]
~~~

Ambas são O(1).

## Invariante da stack

Para capacidade C:

~~~text
0 <= sp <= C
~~~

Elementos ativos ocupam:

~~~text
storage[0:sp]
~~~

O próximo slot livre, quando existe, é storage[sp].

Tentativa de overflow não pode escrever storage[C].

Tentativa de underflow não pode reduzir sp abaixo de zero.

Esses invariantes simples são fundamentais porque erro off-by-one vira acesso out-of-bounds diretamente.

## Operand stack do CLVM

ClvmVm atual contém:

~~~text
int64_t stack[CLVM_STACK_MAX]
uint16_t sp
~~~

com:

~~~text
CLVM_STACK_MAX = 256
~~~

clvm_vm_push64 verifica:

~~~text
sp == CLVM_STACK_MAX
~~~

e rejeita push quando a stack está cheia.

Caso contrário executa:

~~~text
stack[sp++] = value
~~~

clvm_vm_pop64 verifica sp == 0 antes de:

~~~text
*value = stack[--sp]
~~~

A representação é uma stack limitada sobre array com sinalização explícita de overflow e underflow.

## Call stack do CLVM

ClvmVm também contém separadamente:

~~~text
uint32_t calls[CLVM_CALL_MAX]
uint16_t csp
~~~

com:

~~~text
CLVM_CALL_MAX = 64
~~~

Operandos e return addresses ocupam stacks lógicas distintas.

Os limites e falhas são independentes.

Workload guest recursivo pode esgotar call stack mesmo com espaço restante na operand stack.

## Ownership e serialização das stacks

Como as stacks CLVM ficam dentro de ClvmVm, a própria VM é dona do armazenamento.

Consequências:

- conteúdo da stack é parte explícita do estado da VM;
- stack pointers podem ser validados durante restore;
- nesting do guest não depende diretamente do tamanho da C stack do host;
- capacidade é determinística.

O suporte atual de setjmp/longjmp serializa elementos ativos para memória da VM e valida sp/csp restaurados antes de aplicá-los.

É um exemplo concreto de representation invariants atravessando fronteira de state save/restore.

## Queues

Uma queue implementa first-in, first-out.

Operações abstratas:

~~~text
enqueue(x)
dequeue()
front()
empty()
~~~

Uma queue contígua ingênua que remove o elemento 0 deslocando todos os restantes tem dequeue O(n).

Array circular evita esse movimento.

## Queues circulares

Para capacidade C, head e tail fazem wrap por:

~~~text
next(i) = (i + 1) mod C
~~~

Existem várias convenções válidas para full/empty.

Duas formas comuns:

1. count separado:
   - vazia quando count = 0;
   - cheia quando count = C;

2. reservar um slot:
   - vazia quando head = tail;
   - cheia quando next(head) = tail;
   - capacidade útil = C - 1.

O contrato da implementação precisa declarar qual convenção usa.

## Queue de jobs do kernel

kernel/metal/job.h define atualmente:

~~~text
JOB_QUEUE_CAP = 1024
~~~

job.c armazena:

~~~text
Job g_queue[JOB_QUEUE_CAP]
g_q_head
g_q_tail
g_q_count
Spinlock g_q_lock
~~~

Essa queue usa count separado.

job_init zera head, tail e count.

job_submit adquire g_q_lock e rejeita inserção quando:

~~~text
g_q_count == JOB_QUEUE_CAP
~~~

No sucesso escreve em tail, avança tail módulo capacidade e incrementa count.

job_worker_once adquire o mesmo lock, lê head quando count > 0, avança head e decrementa count.

## Invariantes da queue de jobs

Sob operações protegidas por g_q_lock, invariantes pretendidos incluem:

~~~text
0 <= g_q_head < JOB_QUEUE_CAP
0 <= g_q_tail < JOB_QUEUE_CAP
0 <= g_q_count <= JOB_QUEUE_CAP
~~~

A aritmética modular preserva a faixa dos índices.

Count separa cheio de vazio, permitindo usar os 1024 slots físicos.

O lock serializa mutações nos metadados da queue.

A função do job executa após release do lock, mantendo trabalho do caller fora da critical section da queue.

## Complexidade da queue de jobs

Ignorando lock contention:

- enqueue é O(1);
- dequeue é O(1);
- não ocorre deslocamento dos elementos;
- memória é O(JOB_QUEUE_CAP).

A estrutura possui footprint fixo.

Quando cheia, job_submit retorna falha em vez de alocar mais espaço.

O caller escolhe retry, execução local ou propagação da falha.

O self-test atual inclui loops de retry que executam um worker step quando submit temporariamente falha.

## Ring de eventos de input

input.c define:

~~~text
INPUT_QUEUE_CAPACITY = 64
InputEvent g_queue[INPUT_QUEUE_CAPACITY]
g_queue_head
g_queue_tail
g_lost_events
~~~

Diferentemente da job queue, não mantém count.

queue_push calcula:

~~~text
next = (head + 1) mod 64
~~~

e considera full quando:

~~~text
next == tail
~~~

Portanto um slot físico é reservado para distinguir cheio de vazio.

A capacidade útil é 63 eventos.

## Saturação da queue de input

Quando o ring de input está cheio, queue_push incrementa g_lost_events e retorna sem gravar o novo evento.

Ele não sobrescreve o evento mais antigo.

Esse comportamento corresponde a descarte do novo evento nesse path.

A política é semanticamente relevante.

Preservar os eventos antigos já enfileirados enquanto contabiliza perda é diferente de sobrescrever o mais antigo.

## Dequeue de input

input_next_event retorna false quando:

~~~text
tail == head
~~~

Caso contrário copia o evento em tail e avança tail módulo capacidade.

A ordem FIFO segue a progressão circular de índices.

input_clear_events define tail = head, descartando logicamente todos os eventos pendentes sem zerar os bytes do array.

Membership lógico depende dos índices, e não de dados antigos permanecendo em slots inativos.

## Fronteira de concorrência do input ring

O input ring difere da queue de jobs protegida por spinlock.

O source revisado usa head/tail volatile e compiler_barrier ao redor da publicação e consumo.

Ele não usa mutual exclusion semelhante a g_q_lock e também não apresenta a estrutura como queue lock-free portátil genérica.

Sua correção depende do modelo real de producer/consumer e do memory ordering do target.

A documentação não deve transformar “há compiler barriers” em garantia universal lock-free ou wait-free.

Uma prova completa precisaria especificar:

- contextos produtores;
- contextos consumidores;
- arquitetura de CPU;
- relações de interrupt/preemption;
- requisitos de ordering de compilador e hardware.

## Wraparound do ring

Aritmética modular faz com que ordem física dos índices não corresponda à idade lógica.

Exemplo com C = 8:

~~~text
head = 7
enqueue
novo head = 0
~~~

A sequência continua FIFO porque ordem lógica é definida percorrendo de tail a head com wrap.

Ferramentas de debug não podem assumir:

~~~text
tail <= head
~~~

na ordem inteira comum.

A relação é falsa depois do wrap.

## Ambiguidade entre full e empty

Se um ring mantém apenas head/tail e permite ocupar todos os C slots, então:

~~~text
head == tail
~~~

pode significar cheio ou vazio.

Implementações resolvem isso por:

- slot reservado;
- count separado;
- contadores monotônicos mais largos;
- generation bits.

ChrisOS mostra duas escolhas:

- job queue: count separado;
- input ring: slot reservado.

Nenhuma é universalmente superior.

## Ownership de memória

Estruturas sobre arrays fixos evitam allocation por elemento, mas ownership continua relevante.

Job queue:

- armazenamento da queue é estado estático do kernel;
- Job contém function e argument pointers;
- armazenar arg não significa que a queue adquiriu ownership do objeto apontado.

Input queue:

- eventos são copiados por valor;
- consumer recebe uma cópia de InputEvent.

CLVM stack:

- valores são armazenados por valor dentro de ClvmVm.

Shader AST:

- node storage pertence a ShComp;
- índices next são válidos somente em relação àquela instância da AST.

Confundir ownership do armazenamento com ownership do objeto referenciado pode gerar lifetime bugs.

## Comportamento de falha

Estruturas lineares exigem políticas explícitas de saturação e vazio.

| Estrutura | Vazia | Cheia |
|---|---|---|
| CLVM operand stack | pop falha | push falha |
| CLVM call stack | lógica de call/return faulta nos bounds | call overflow fault |
| kernel job ring | worker não retira nada | submit retorna 0 |
| input ring | next_event retorna false | novo evento descartado; lost counter incrementa |
| shader AST node pool | n/a | criação de node falha com erro de parser |

Esses são contratos de implementação, não propriedades genéricas de stack ou queue.

## Implicações de segurança

Erros de bounds e lifetime em estruturas lineares são classes comuns de vulnerabilidade.

Falhas relevantes:

- índice de array out-of-bounds;
- integer overflow no cálculo do índice;
- stack underflow/overflow;
- linked pointer ou index obsoleto;
- race nos metadados de queue;
- use-after-free de payload apontado por job;
- capacity exhaustion usada para denial of service;
- ciclo em lista levando a traversal sem fim.

Capacidade fixa limita crescimento de memória, mas cria superfícies de saturação que ainda precisam de handling explícito.

## Trade-offs de desempenho

Arrays favorecem:

- compactness;
- scans sequenciais;
- cache locality;
- indexing O(1).

Estruturas ligadas favorecem:

- nodes estáveis;
- inserção/remoção local quando posição é conhecida;
- armazenamento não contíguo flexível.

Stacks favorecem:

- LIFO em tempo constante;
- mutação concentrada no topo.

Rings favorecem:

- FIFO em tempo constante;
- memória fixa;
- ausência de relocation dos elementos.

Em software de sistemas, a representação frequentemente é escolhida para limitar allocator e latência, e não apenas para minimizar quantidade abstrata de operações.

## Evidência de validação

O checker determinístico específico valida:

- aritmética de endereço em arrays;
- bounds de array fixo;
- traversal de lista index-linked e rejeição de ciclo no modelo;
- push/pop de stack limitada incluindo overflow e underflow;
- ring com count separado como na job queue;
- ring com slot reservado e capacidade física 64/capacidade útil 63;
- preservação de FIFO através de wraparound;
- descarte de novo evento quando full;
- âncoras de source para CLVM_STACK_MAX, CLVM_CALL_MAX, JOB_QUEUE_CAP, job_submit/job_worker_once, INPUT_QUEUE_CAPACITY, queue_push/input_next_event, SH_AST_MAX e Ast.next.

O checker modela invariantes documentados e valida âncoras do source. Não prova correção concorrente do input ring nem de todos os callers.

## Limitações atuais

Este capítulo não cobre integralmente:

- queues lock-free multi-producer/multi-consumer;
- hazard pointers e epoch reclamation;
- ropes, gap buffers e piece tables;
- persistent functional lists;
- deques em profundidade;
- containers vetorizados;
- internals do allocator;
- provas formais de memory ordering.

Esses assuntos pertencem a capítulos especializados posteriores.

## Fronteira do roadmap

O currículo segue das estruturas lineares para:

~~~text
arrays/lists/stacks/queues
      ↓
hash tables
      ↓
trees/heaps/tries
      ↓
graphs/union-find
      ↓
bitmaps/rings/free lists
      ↓
systems algorithms
~~~

Os capítulos posteriores especializam representação e invariantes introduzidos aqui.

## Proveniência da revisão

As afirmações ligadas à implementação foram conciliadas contra ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

Fontes revisadas:

- compiler/clvm/clvm_vm.h;
- compiler/clvm/clvm_vm.c;
- kernel/metal/job.h;
- kernel/metal/job.c;
- kernel/gfx/input.c;
- kernel/gfx/shader/sh_int.h;
- kernel/gfx/shader/sh_parse.c.

Símbolos revisados:

- ClvmVm;
- clvm_vm_push64;
- clvm_vm_pop64;
- job_init;
- job_submit;
- job_worker_once;
- queue_push;
- input_next_event;
- Ast;
- ShComp;
- sh_parse.

O source sustenta stacks limitadas sobre arrays, duas convenções concretas de ring e sequências de AST ligadas por índices. Nenhuma biblioteca genérica de linked lists do ChrisOS é inferida a partir desses exemplos.
