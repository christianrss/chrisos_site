---
id: graphs-union-find
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_sem.c
  - kernel/fs/cfs.c
symbols:
  - ShComp
  - scope_parent
  - scope_has
  - push_scope
  - pop_scope
  - dir_find
  - walk_full
depends_on:
  - arrays-lists-stacks-queues
  - trees-heaps-tries
  - algorithmic-complexity
  - proof-invariants-induction
related:
  - bitmaps-rings-free-lists
  - graph-algorithms
  - systems-algorithms
  - string-parsing-algorithms
---

# Grafos, conectividade e union-find

<div class="abstract">
Grafos modelam relações arbitrárias em vez de uma única hierarquia. Correção e custo dependem da representação exata de vertices e edges, da direção e dos pesos das edges e dos invariantes exigidos pelo subsistema. Union-find, também chamado disjoint-set union, resolve um problema mais específico: manter uma partição de elementos sob operações repetidas de merge e consultas de conectividade. Este capítulo desenvolve modelos de graph, adjacency representations, reachability, componentes, ciclos, DAGs e disjoint-set forests com path compression e union by rank ou size. A fronteira com o ChrisOS atual é explícita. O semantic analyzer de shaders guarda lexical scopes em um parent array, e ChrisFS percorre uma hierarquia de diretórios enraizada. Ambos são casos especiais tree-shaped; não são generic graph containers nem union-find. A revisão analisada não estabelece implementação reutilizável de graph ou DSU, portanto esses mecanismos são documentados como fundamento, não como recurso implementado do ChrisOS.
</div>

## Graphs além das restrições de trees

Tree impõe forte estrutura:

- uma root;
- cada node não-root possui exatamente um parent;
- não existem cycles;
- existe exatamente um simple path entre nodes conectados.

Graph remove parte ou todas essas restrições.

Escrevemos normalmente:

~~~text
G = (V, E)
~~~

onde V é o conjunto de vertices e E o conjunto de edges.

Em undirected graph, a edge {u, v} não possui direção. Em directed graph, a edge é ordered pair:

~~~text
(u, v)
~~~

representando arco de u para v.

Graphs podem modelar topologia de hardware, dependências, control flow, call relations, networks, relações de filesystem, ownership, routing e synchronization dependencies. O modelo precisa derivar da semântica real do subsystem, não do simples fato de existirem pointers.

## Vocabulário e invariantes

| Termo | Significado |
|---|---|
| vertex | objeto representado como node |
| edge | relação entre vertices |
| path | sequência de vertices adjacentes |
| cycle | path que retorna ao início |
| connected component | conjunto conectado maximal em undirected graph |
| strongly connected component | conjunto dirigido mutuamente alcançável |
| degree | quantidade de incident edges |
| indegree | incoming edges |
| outdegree | outgoing edges |
| DAG | directed acyclic graph |
| forest | coleção disjunta de trees |

Uma representation só é correta quando preserva a semântica das edges.

Para undirected edge armazenada simetricamente:

~~~text
v in adj[u]
u in adj[v]
~~~

deve valer, salvo representation alternativa explícita.

## Adjacency matrix

Com n vertices, adjacency matrix guarda:

~~~text
A[u][v]
~~~

como bit, Boolean, weight ou edge record.

Em directed unweighted graph:

~~~text
A[u][v] = 1  iff  edge u -> v existe
~~~

Memória:

~~~text
Theta(n^2)
~~~

Vantagens: edge-existence O(1), representação simples, adequação a dense graph e possibilidade de operações por machine word em bit matrices.

Custos: desperdício em sparse graph, neighbor enumeration O(n) por vertex e resize caro.

## Adjacency lists

Cada vertex referencia seus outgoing neighbors:

~~~text
adj[0] -> 1, 4
adj[1] -> 2
adj[2] -> 0, 3
~~~

Para n vertices e m directed edges:

~~~text
Theta(n + m)
~~~

de memória.

Em undirected graph simétrico, normalmente há 2m adjacency entries.

É eficiente em graphs sparse e para neighbor iteration. Edge-existence pode exigir scan; linked nodes prejudicam locality. Adjacency list não implica linked list: pode ser vector, fixed array, hash set ou sorted range.

## Edge lists

Edge list guarda pares:

~~~text
(u0, v0)
(u1, v1)
...
~~~

É simples e compacta para batch algorithms. É útil quando o trabalho principal é scan ou sort de todas as edges, como em Kruskal. Sem índice adicional, neighborhood query é ruim.

## Weighted graphs

Weighted edge:

~~~text
(u, v, w)
~~~

w pode significar latency, cost, distance, capacity, probability ou priority.

Weight não é necessariamente distância geométrica. Algoritmos devem declarar se negative weights, parallel edges e overflow de soma são permitidos.

## Paths e reachability

Path de s a t:

~~~text
s = v0, v1, ..., vk = t
~~~

com edge adequada entre cada par consecutivo.

Reachability pergunta se existe pelo menos um path.

Em unweighted graph, BFS também encontra shortest path por número de edges. DFS é útil para structural traversal, cycle detection e components. Os algoritmos completos ficam para graph-algorithms; aqui o foco é representation e invariants.

## Cycles e DAGs

Muitas relações de sistema precisam ser acíclicas: build dependencies, initialization ordering, ownership e lexical parents.

DAG admite topological order.

Cycle inesperado pode fazer recursion nunca terminar ou consumir um guard limit. Por isso parent-chain code frequentemente possui depth bound mesmo quando a estrutura correta não deveria conter cycles.

## Parent arrays versus graphs

Um parent array:

~~~text
parent[v] = p
~~~

pode representar rooted tree ou forest quando cada element possui no máximo um parent. É muito mais restrito que arbitrary graph.

Essa distinção aparece diretamente no shader compiler.

## Hierarquia de scopes do shader compiler

ShComp contém:

~~~text
int cur_scope;
int nscope;
int scope_parent[SH_SCOPE_MAX];
~~~

push_scope cria um scope:

~~~text
scope_parent[new] = cur_scope
cur_scope = new
~~~

pop_scope retorna:

~~~text
cur_scope = scope_parent[cur_scope]
~~~

Isso forma uma parent hierarchy de lexical scopes. Não é generic graph e um scope não possui múltiplos parents.

## Ancestry lookup limitado

scope_has começa em cur_scope e segue:

~~~text
scope_parent[s]
~~~

até scope zero ou até o guard atingir SH_SCOPE_MAX.

O guard limita traversal mesmo sob state inconsistente.

O invariante normal é:

~~~text
cada scope não-root aponta para ancestor criado anteriormente
~~~

Portanto a relação correta é acíclica.

## Hierarquia scope_parent versus union-find

Em DSU, parent[x] é link interno até o representative da equivalence class.

Path compression pode reescrever:

~~~text
parent[x] = root
~~~

sem mudar a semântica externa.

Em lexical scopes, a chain:

~~~text
scope 7 -> scope 4 -> scope 1 -> scope 0
~~~

carrega nesting real. Reduzir 7 diretamente para 0 destruiria informações de visibility.

Logo parent array isolado não prova DSU.

## ChrisFS como outro caso especializado

ChrisFS inicia walk em CFS_ROOT_INODE.

walk_full resolve cada path component via dir_find e avança para o child inode.

Isso expõe rooted namespace.

Na revisão atual, cada directory child é localizado por linear scan de entries, não por generic graph representation.

Filesystems podem tornar-se graph-like com hard links ou outras relações multi-parent, mas esse claim precisa vir do formato e source reais.

## Connected components

Em undirected graph, u e v pertencem ao mesmo connected component quando há path entre eles.

Em graph estático, traversal pode rotular componentes:

1. escolhe unvisited vertex;
2. visita tudo que é reachable;
3. atribui component id;
4. repete.

Com adjacency list, custo total é:

~~~text
O(V + E)
~~~

Para queries online repetidas sob edge additions, DSU é mais apropriado.

## Disjoint-set abstraction

Union-find mantém partition de elementos.

Operações:

~~~text
make_set(x)
find(x)
union(a, b)
~~~

make_set cria singleton; find retorna representative; union combina sets.

Connectivity:

~~~text
find(a) == find(b)
~~~

Representative é label de implementação, não identidade semântica especial.

## Forest representation

Implementação clássica:

~~~text
parent[i]
rank[i]
~~~

ou:

~~~text
parent[i]
size[i]
~~~

Inicialização:

~~~text
parent[i] = i
rank[i] = 0
~~~

Cada set é rooted tree. Root satisfaz:

~~~text
parent[root] = root
~~~

Sem otimização, unions ruins criam chain e find O(n).

## Path compression

Find conceitual:

~~~text
find(x):
    if parent[x] != x:
        parent[x] = find(parent[x])
    return parent[x]
~~~

Antes:

~~~text
7 -> 5 -> 3 -> 1
~~~

Depois de find(7):

~~~text
7 ─┐
5 ─┼──> 1
3 ─┘
~~~

A partition não muda; apenas a representation é achatada.

## Union by rank

~~~text
ra = find(a)
rb = find(b)

if ra == rb:
    return

if rank[ra] < rank[rb]:
    parent[ra] = rb
else if rank[ra] > rank[rb]:
    parent[rb] = ra
else:
    parent[rb] = ra
    rank[ra]++
~~~

Rank não precisa continuar sendo exact height depois de path compression.

## Union by size

~~~text
if size[ra] < size[rb]:
    swap(ra, rb)

parent[rb] = ra
size[ra] += size[rb]
~~~

Small tree fica sob large tree.

Rank e size são heuristics alternativas.

## Complexidade

Com path compression e union by rank ou size, uma sequência de m operations em n elements possui bound amortized:

~~~text
O(m alpha(n))
~~~

alpha é inverse Ackermann function e permanece extremamente pequena em escalas reais.

Isso não significa worst-case O(1) estrito por operação; é bound amortized da sequência.

## Invariantes de DSU

- todo parent index está em range;
- todo tree possui self-parent root;
- parent traversal termina;
- rank ou size relevante pertence ao root;
- union nunca divide sets;
- find retorna mesmo representative exatamente para elements na mesma partition.

Com union by size:

~~~text
size[root] = quantidade de membros
~~~

deve permanecer verdadeiro.

## DSU não preserva graph edges

Depois de:

~~~text
union(A, B)
union(B, C)
~~~

DSU sabe apenas que A, B e C estão conectados.

Ele não preserva se original graph continha A-B e B-C, A-C e B-C ou outra combinação.

Logo DSU não substitui adjacency structure quando path, degree, neighbors ou edge identity importam.

## Usos típicos em sistemas

Possíveis aplicações incluem equivalence classes de resources, Kruskal, incremental topology connectivity, alias analysis, region merging e image component labeling.

São exemplos de design, não claims de implementação ChrisOS.

A revisão analisada não possui reusable DSU.

## Memory layout

Com parent e size de 32 bits:

~~~text
parent[n]
size[n]
~~~

usa aproximadamente:

~~~text
8n bytes
~~~

antes de alignment.

Arrays contíguos favorecem cache. Index width menor pode reduzir memória quando n é rigidamente limitado, mas overflow e truncation precisam ser impossíveis por contrato.

## Falhas e corrupção

Graphs podem falhar por vertex id fora de range, duplicate edges, dangling adjacency, cycle inesperado, stale index ou capacity exhaustion.

DSU pode falhar por parent cycle sem root, invalid parent, corrupted size/rank, union antes de initialization ou races perdendo update.

Exemplo inválido:

~~~text
1 -> 2 -> 3 -> 1
~~~

faz find loopar se não houver guard.

## Concorrência

Naive DSU não é thread-safe.

Concurrent unions disputam roots, parent updates e rank/size.

Coarse lock é solução simples. Algoritmos concorrentes mais sofisticados usam atomic CAS e linking rules específicas.

Path compression escreve durante find, então até uma query aparentemente read-only modifica state.

Graph mutation também exige ownership/synchronization: single writer, graph lock, per-vertex locks, immutable snapshot ou RCU.

## Segurança e complexidade adversarial

Input não confiável pode gerar high-degree vertices, deep paths, enorme edge count, duplicates e cycles em estrutura esperada como DAG.

Defesas incluem limits de V/E, range checks, traversal budgets, visited set e overflow checks em allocation.

DSU otimizado mantém excelente asymptotic behavior, mas ainda requer validação de índices.

## Custos por representação

A escolha entre matrix, adjacency list e edge list precisa ser orientada pelas operações dominantes.

| Operação | Matrix | Adjacency list | Edge list |
|---|---:|---:|---:|
| testar edge u→v | O(1) | O(deg(u)) sem índice extra | O(E) |
| enumerar neighbors de u | O(V) | O(deg(u)) | O(E) |
| percorrer todas as edges | O(V²) | O(V+E) | O(E) |
| memória sparse | O(V²) | O(V+E) | O(E) |
| inserir edge | O(1) em storage fixo | depende do container | append O(1) amortized |

Esses bounds assumem representações básicas. Sorted vectors, hash sets ou compressed sparse row mudam constants e algumas operações.

Em sistemas, memory locality pode ser tão importante quanto o bound assintótico. Matrix é contígua mas grande; pointer adjacency lists são compactas em número de edges, porém podem espalhar nodes. CSR e arrays indexados preservam densidade e são atraentes para graphs quase imutáveis.

## Directed, undirected e multigraph

A mesma lista de pares pode ter semânticas diferentes.

Em directed graph:

~~~text
(u, v) != (v, u)
~~~

Em undirected graph, uma implementação por adjacency list normalmente precisa representar os dois sentidos.

Multigraph permite múltiplas edges entre o mesmo par. Simple graph não permite.

Self-loop:

~~~text
(u, u)
~~~

pode ser válido ou erro de input, dependendo do domain.

Essas decisões afetam degree counts, cycle detection e deduplication. Um parser não pode deduzir a policy depois de construir a estrutura.

## Ownership de vertices e edges

Uma implementação em kernel precisa definir quem possui a memória.

Possibilidades:

- graph possui vertices e edges;
- subsystem externo possui objects, graph guarda apenas ids;
- immutable graph referencia storage estável;
- edges são intrusive records dentro dos próprios objects.

Ids evitam raw pointer lifetime problems, mas introduzem geração/reuse concerns: se slot 12 for liberado e reutilizado para outro object, uma stale edge para 12 pode passar range check e ainda apontar para entidade errada.

Uma solução é combinar index com generation counter.

## Correctness de union-find

O significado matemático de DSU é uma equivalence relation.

Ela deve ser:

- reflexiva: x está conectado a x;
- simétrica: se x está no mesmo set que y, y está no mesmo set que x;
- transitiva: se x~y e y~z, então x~z.

make_set cria classes singleton. union substitui duas classes por sua união. find fornece um canonical representative por classe.

Path compression não altera a partition porque cada node continua apontando para um ancestor dentro do mesmo set.

Union by size também não altera membership: apenas escolhe qual root passa a representar o conjunto combinado.

## Proof intuition para union by size

Quando a tree menor é anexada à maior, sempre que a profundidade de um element aumenta por uma union, o tamanho do set que o contém ao menos dobra.

Assim, sem path compression, um element não pode aumentar de profundidade mais que:

~~~text
floor(log2 n)
~~~

vezes.

Isso explica por que union by size sozinho já impede chains lineares produzidas por unions arbitrárias.

Path compression reduz ainda mais o custo amortizado.

## Rebuild versus incremental connectivity

DSU é especialmente útil quando as edges só são adicionadas.

Quando uma edge é removida, DSU básico não consegue desfazer uma union.

Para dynamic connectivity com deletions, alternativas incluem:

- rebuild periódico;
- offline algorithms com rollback DSU;
- dynamic trees;
- estruturas específicas do workload.

Portanto DSU não é um banco de dados completo de topologia.

## Serialization e ABI

Se graph ou DSU forem persistidos, índices precisam de formato estável.

Itens que devem ser definidos:

- integer width;
- endianness;
- vertex count;
- edge count;
- bounds;
- duplicate policy;
- representative metadata;
- versioning.

Persistir o parent array de uma DSU como se fosse semântica externa é geralmente frágil: path compression pode alterar a representação sem alterar a partition.

Quando o que importa é equivalence class, o formato deve definir o significado lógico, não depender de uma shape específica da forest.

## Concorrência mais detalhada

Coarse locking torna union/find simples, mas serializa queries.

Read-mostly graph pode usar immutable snapshots e publicar uma nova versão depois de mutation.

Per-vertex locking exige lock ordering para operações com duas endpoints; ordenar locks por vertex id evita uma classe de deadlocks.

Concurrent DSU é mais delicado porque find pode modificar parent links por compression. Uma implementação que oferece lock-free reads precisa declarar se find comprime paths, se usa atomic loads/stores e qual consistency model é esperado.

Nenhum desses modelos concorrentes é atribuído ao ChrisOS atual neste capítulo; eles estabelecem o espaço de design.

## Failure containment

Ao consumir graph externo, validação deve ocorrer antes de traversal intensiva.

Uma sequência defensiva típica:

1. validar V e E contra limites;
2. validar cada endpoint;
3. verificar overflow do tamanho de allocation;
4. construir representation;
5. opcionalmente deduplicar edges;
6. executar cycle/component checks necessários ao domain.

Isso evita que malformed metadata transforme uma simples range violation em pointer corruption ou unbounded traversal.

## Modelo de validação

O checker determinístico associado valida adjacency list e matrix em graph pequeno, connected components, directed versus undirected semantics, cycle detection em parent chains, make/find/union, union by size, path compression, representative equality e set sizes.

Também verifica anchors reais de scope_parent, scope_has, push_scope, pop_scope e path traversal do ChrisFS.

A fronteira também é testada: o source atual mostra parent hierarchies especializadas, não reusable DSU API.

## Fronteira do ChrisOS atual

Na revisão da3df29cb397932c43d32373871fb9380e688ade foi comprovado:

- lexical scope hierarchy do shader compiler;
- rooted path hierarchy do ChrisFS.

Não foi estabelecida implementação reutilizável de adjacency list, adjacency matrix, generic graph object, DSU, path compression, union by rank ou union by size.

Esses mecanismos permanecem fundamentos para capítulos posteriores e possíveis designs futuros.

## Relação com capítulos posteriores

Este capítulo estabelece representation e connectivity.

O capítulo graph-algorithms poderá aprofundar BFS, DFS, topological sorting, SCC, shortest paths e minimum spanning trees.

Union-find aparece aqui porque seus invariants e representation são assunto de data structures, ainda que Kruskal pertença à camada de graph algorithms.

## Proveniência da revisão

As afirmações ligadas à implementação foram conciliadas com ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

Source revisado:

- kernel/gfx/shader/sh_int.h;
- kernel/gfx/shader/sh_sem.c;
- kernel/fs/cfs.c.

Símbolos e estado:

- ShComp.scope_parent;
- SH_SCOPE_MAX;
- scope_has;
- push_scope;
- pop_scope;
- dir_find;
- walk_full;
- CFS_ROOT_INODE.

A fronteira é deliberada: specialized trees não são arbitrary graphs, e parent arrays só são union-find quando representative semantics e union/find operations realmente existem.
