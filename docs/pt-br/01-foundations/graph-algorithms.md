---
id: graph-algorithms
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - tools/check_test_gates.py
  - makefile
symbols:
  - ROOTS
  - main
  - rules
  - seen
  - stack
  - host-gates
depends_on:
  - graphs-union-find
  - arrays-lists-stacks-queues
  - trees-heaps-tries
  - algorithmic-complexity
  - sorting-searching
related:
  - systems-algorithms
  - string-parsing-algorithms
  - proof-invariants-induction
---

# Algoritmos de grafos para software de sistemas

<div class="abstract">
Algoritmos de grafos transformam uma graph representation em respostas sobre reachability, ordering, components, paths e spanning structure. A correção depende da direção das edges, dos weights, da policy para cycles, da disciplina de queue/stack e do significado de visited state. Este capítulo desenvolve breadth-first search, depth-first search, topological sorting, strongly connected components, shortest paths, minimum spanning trees e seus modos de falha em software de sistemas. Também reconcilia esses fundamentos com o source atual do ChrisOS. tools/check_test_gates.py interpreta targets do Makefile como um directed dependency graph e executa traversal explícito com LIFO stack a partir de host-gates, mantendo um seen set e reportando test targets que não são reachable. Isso é um algoritmo concreto de depth-first-style reachability. Não é topological sorting, cycle detection, shortest-path search nem uma generic graph library. A revisão analisada portanto comprova um traversal específico; os demais algoritmos permanecem fundamentos para designs posteriores.
</div>

## Entradas e semântica do graph

Antes de executar qualquer algoritmo, é necessário definir o contrato do graph:

~~~text
G = (V, E)
~~~

A implementação precisa saber:

- directed ou undirected;
- weighted ou unweighted;
- simple graph ou multigraph;
- se self-loops são permitidos;
- se vertices são dense integer ids ou objects arbitrários;
- se o graph permanece estável durante traversal;
- se vertices unreachable são erro ou estado válido.

A mesma edge list produz respostas diferentes conforme essa semântica.

Uma dependency edge:

~~~text
target -> prerequisite
~~~

é directed.

Uma physical-link edge entre peers pode ser undirected.

## Estado de traversal

A maioria dos traversals precisa de:

~~~text
frontier
visited
~~~

Frontier determina qual discovered vertex é processado a seguir.

Queue produz breadth-first order.

Stack produz depth-first order.

Visited evita repeated work, loops em cycles e rediscovery infinita.

O momento em que visited é marcado importa.

Marcar no discovery normalmente impede múltiplas inserções do mesmo vertex na frontier. Marcar apenas no removal pode ampliar significativamente queue/stack.

## Breadth-first search

BFS explora por distância em número de edges.

~~~text
visited[s] = true
distance[s] = 0
queue.push(s)

while queue not empty:
    u = queue.pop_front()
    for v in adj[u]:
        if not visited[v]:
            visited[v] = true
            distance[v] = distance[u] + 1
            parent[v] = u
            queue.push_back(v)
~~~

Com adjacency lists:

~~~text
time  = O(V + E)
space = O(V)
~~~

Cada reachable vertex é descoberto uma vez e cada outgoing edge é examinada uma vez.

## Garantia de shortest path do BFS

Em unweighted graph, BFS descobre vertices em nondecreasing edge distance.

Quando v é descoberto a partir de u:

~~~text
distance[v] = distance[u] + 1
~~~

Não pode existir depois um path com menos edges, porque todas as frontiers de menor distância já foram processadas.

Essa garantia não vale para arbitrary weighted graphs.

Com nonnegative unequal weights, Dijkstra é a generalização apropriada.

## Parent reconstruction no BFS

Ao descobrir v:

~~~text
parent[v] = u
~~~

permite reconstruir um path caminhando de target para source.

Esse parent array é resultado do traversal.

Não precisa corresponder à structural parent relation do graph.

Unreachable vertices devem usar sentinel impossível de confundir com valid id.

## Depth-first search

DFS avança por uma branch até não poder prosseguir e então retorna.

Forma iterativa:

~~~text
stack.push(s)

while stack not empty:
    u = stack.pop()
    if visited[u]:
        continue
    visited[u] = true
    for v in adj[u]:
        if not visited[v]:
            stack.push(v)
~~~

Recursive DFS usa call stack para expressar o mesmo search.

Com adjacency lists:

~~~text
O(V + E)
~~~

Iterative DFS torna storage bound explícito e evita deep recursion em kernel/tools.

## Ordem do DFS

DFS order depende da order dos neighbors e da stack discipline.

Se:

~~~text
a, b, c
~~~

forem inseridos nessa ordem em LIFO stack, c será processado primeiro.

Determinism pode exigir:

- canonical adjacency order;
- reverse push;
- sorting prévio.

Quando apenas reachability importa, exact visitation order pode ser irrelevante.

Esse é o caso do audit atual dos host gates.

## Reachability

Reachability pergunta se target t pode ser atingido desde source s.

BFS e DFS resolvem em:

~~~text
O(V + E)
~~~

Para consultas repetidas em static graph, pode ser útil pré-calcular components ou transitive information.

Para dynamic undirected edge additions, union-find pode responder connectivity com custo muito menor que repetir traversal, mas não consegue reconstruir paths.

## Graph atual do Makefile do ChrisOS

tools/check_test_gates.py interpreta rules do Makefile como directed graph.

Uma rule conceitual:

~~~text
A: B C
~~~

vira:

~~~text
rules[A] = [B, C]
~~~

e o audit segue:

~~~text
A -> B
A -> C
~~~

ROOTS contém:

~~~text
host-gates
~~~

O objetivo é descobrir quais test targets são reachable a partir desse aggregate target.

## Traversal explícito do check_test_gates.py

O source cria:

~~~text
seen = set()
stack = list(ROOTS)
~~~

e executa:

~~~text
while stack:
    name = stack.pop()
    if name in seen:
        continue
    seen.add(name)
    stack.extend(rules.get(name, []))
~~~

stack.pop remove o último item.

Logo a frontier é LIFO.

Operacionalmente, isso caracteriza depth-first-style traversal.

seen garante término mesmo se a relation contiver um cycle.

O resultado necessário é apenas o reachable set, então a exact DFS order não participa do contrato.

## Invariante de reachability dos host gates

Depois do traversal, o script examina as parsed rules.

Um target é orphan quando:

- parece host test;
- não pertence a seen.

O invariant pretendido é:

~~~text
todo host test target deve ser reachable desde host-gates
~~~

Isso transforma uma graph property em CI policy.

Adicionar um test target e esquecer de conectá-lo à aggregate gate graph passa a ser erro detectável.

## Complexidade do audit

Se V é o conjunto de nomes alcançados/parses e E as prerequisite relations:

~~~text
traversal = O(V + E)
~~~

com average O(1) para membership no Python set.

Depois o script executa:

~~~text
for name in sorted(rules)
~~~

Esse passo adiciona:

~~~text
O(R log R)
~~~

para R rules.

O sorting existe para inspeção/report determinístico de orphans.

Ele não muda o traversal para BFS ou topological sorting.

## Cycles no audit atual

O audit não detecta cycles.

Com:

~~~text
A -> B -> C -> A
~~~

seen impede expansão infinita.

Isso apenas prova que reachability traversal termina.

Não prova acyclicity.

Cycle validation exigiria state adicional:

- WHITE/GRAY/BLACK;
- recursion-stack membership;
- indegree exhaustion de Kahn.

O script atual não deve ser documentado como cycle detector.

## Directed cycle detection por cores

Em DFS dirigido:

~~~text
WHITE = undiscovered
GRAY  = ativo no current DFS path
BLACK = totalmente processado
~~~

Uma edge u -> v para v GRAY é back edge e prova cycle.

Visited Boolean não basta para essa distinção, pois não separa ancestor ativo de vertex concluído em outra branch.

## Topological sorting

Topological order satisfaz:

~~~text
para toda edge u -> v:
    u aparece antes de v
~~~

Existe se e somente se o graph é DAG.

Dois métodos clássicos:

- reverse DFS postorder;
- Kahn com indegrees.

## Kahn's algorithm

Primeiro calcula indegree de cada vertex.

Inicializa queue com indegree zero.

~~~text
while queue not empty:
    u = pop()
    emit u
    for v in adj[u]:
        indegree[v]--
        if indegree[v] == 0:
            push(v)
~~~

Se menos de V vertices forem emitidos, existe cycle.

Complexidade:

~~~text
O(V + E)
~~~

Build dependencies e initialization graphs frequentemente usam esse padrão para produzir execução válida.

check_test_gates.py atual não calcula topological order.

## Strongly connected components

Em directed graph, ordinary connected components não bastam.

u e v são strongly connected quando:

~~~text
u reaches v
e
v reaches u
~~~

SCC é maximal set com essa propriedade.

Aplicações:

- dependency-cycle condensation;
- call graph analysis;
- module-cycle detection;
- state-machine decomposition.

Tarjan e Kosaraju são algoritmos clássicos O(V+E).

## Tarjan SCC

Tarjan atribui:

~~~text
index[v]
lowlink[v]
~~~

e mantém stack de vertices ativos.

lowlink é o menor DFS index alcançável sem sair da active search structure.

Quando:

~~~text
lowlink[v] == index[v]
~~~

v é root de uma SCC e entries são removidas da stack até v.

A complexidade é:

~~~text
O(V + E)
~~~

Apesar do bound simples, os invariants são delicados e exigem testes específicos.

## Kosaraju

Kosaraju executa:

1. DFS em G para obter finish order;
2. transposição das edges;
3. DFS em reverse finish order sobre o graph transposto.

Cada DFS tree da segunda fase corresponde a uma SCC.

Também é O(V+E), mas precisa de transpose ou incoming adjacency.

## Shortest paths e weights

A escolha depende dos edge weights.

| Pesos | Algoritmo típico |
|---|---|
| unit/unweighted | BFS |
| nonnegative | Dijkstra |
| negative permitido | Bellman-Ford |
| DAG | topological dynamic programming |
| all-pairs, dense/small | Floyd-Warshall |

Dijkstra com negative edge é incorreto.

A seleção do algoritmo faz parte da correctness proof.

## Dijkstra

Inicialização:

~~~text
dist[source] = 0
dist[others] = infinity
~~~

Usa min-priority queue por tentative distance.

Ao retirar u, relaxa cada outgoing edge:

~~~text
candidate = dist[u] + w(u,v)

if candidate < dist[v]:
    dist[v] = candidate
    parent[v] = u
~~~

Com binary heap:

~~~text
O((V + E) log V)
~~~

Em sparse connected graphs é comum escrever O(E log V).

## Invariante de Dijkstra

Ao remover o unsettled vertex com menor tentative distance, dist[u] é final somente se todos os weights são nonnegative.

Negative edge pode produzir melhoria posterior.

Também é necessário impedir integer overflow em:

~~~text
dist[u] + weight
~~~

pois wrap pode gerar distância artificialmente pequena.

## Bellman-Ford

Bellman-Ford relaxa todas as edges repetidamente.

Depois de V-1 passes, todos os shortest simple paths puderam propagar.

Se um pass adicional ainda reduz alguma distance, existe reachable negative cycle.

Complexidade:

~~~text
O(VE)
~~~

É mais lento que Dijkstra, porém lida com negative weights e detecta negative cycles.

## Shortest path em DAG

Para weighted DAG:

1. compute topological order;
2. process vertices nessa ordem;
3. relax outgoing edges uma vez.

Complexidade:

~~~text
O(V + E)
~~~

Negative weights são permitidos porque não existem cycles para repetir melhorias indefinidamente.

## Floyd-Warshall

Para all-pairs shortest paths:

~~~text
for k:
    for i:
        for j:
            d[i][j] = min(d[i][j], d[i][k] + d[k][j])
~~~

Tempo:

~~~text
O(V^3)
~~~

Memória:

~~~text
O(V^2)
~~~

É simples e regular para graphs pequenos/densos, mas inadequado para topologias sparse muito grandes.

## Minimum spanning trees

Em connected undirected weighted graph, MST conecta todos os vertices usando:

~~~text
V - 1 edges
~~~

com minimum total weight.

MST não é shortest-path tree.

Ele minimiza o custo agregado da tree, não as distâncias desde uma source.

## Kruskal

Kruskal:

1. ordena edges por increasing weight;
2. cria um DSU set por vertex;
3. percorre edges;
4. aceita edge quando endpoints pertencem a sets distintos;
5. faz union.

Sorting domina:

~~~text
O(E log E)
~~~

DSU adiciona custo amortized quase linear.

Isso conecta diretamente os capítulos sorting-searching e graphs-union-find.

## Prim

Prim cresce uma tree conectada a partir de um vertex.

Usando min-priority queue, escolhe repetidamente a cheapest boundary connection para um vertex novo.

Com adjacency list + binary heap:

~~~text
O(E log V)
~~~

Kruskal combina bem com edge list.

Prim combina naturalmente com adjacency-based representation.

## Determinismo e tie breaking

Vários algoritmos admitem múltiplas outputs corretas:

- DFS order;
- parent escolhido por BFS em shortest paths equivalentes;
- topological order;
- MST com equal weights.

Reproducible tests/builds podem exigir tie breaker explícito:

- numeric id;
- lexical name;
- insertion order;
- stable heap ordering.

Determinism é contrato adicional à mathematical correctness.

## Memory e locality

Adjacency arrays favorecem sequential scans.

Pointer-linked adjacency pode gerar cache misses.

BFS frontier pode crescer até a width do graph.

DFS frontier costuma refletir depth, mas worst-case continua O(V).

Dijkstra adiciona priority-queue storage.

Floyd-Warshall troca O(V²) memory por acesso denso regular.

Em systems software, peak frontier e allocator behavior importam tanto quanto Big-O.

## Concorrência e mutation

Textbook algorithms normalmente assumem graph imutável durante traversal.

Concurrent mutation pode invalidar:

- adjacency pointers;
- visited state;
- indegrees;
- heap entries;
- shortest-path invariants.

Possíveis policies:

- read lock;
- immutable snapshot;
- generation/version + restart;
- specialized concurrent algorithms.

O host-gate audit lê um Makefile snapshot em processo único; não é concurrent graph engine.

## Failure containment

Graph input deve validar:

- V/E limits;
- endpoint ranges;
- allocation-size overflow;
- weight arithmetic;
- queue/stack capacity;
- recursion depth;
- cycle quando DAG é requisito.

Mesmo O(V+E) pode ser DoS se V/E não tiverem limits.

Resource budgets continuam necessários.

## Modelo de validação

O checker determinístico associado verifica:

- BFS distance e parent reconstruction;
- iterative DFS reachability;
- directed cycle detection com colors;
- topological order e cycle rejection;
- Tarjan SCC partition;
- Dijkstra em nonnegative weights;
- Bellman-Ford com negative edges e negative-cycle detection;
- Kruskal MST usando DSU;
- source anchors do Makefile dependency traversal;
- LIFO stack e seen-set termination;
- fronteira atual: check_test_gates não é topo sort, SCC, shortest path nem cycle validator.

## Fronteira da implementação ChrisOS

Na revisão da3df29cb397932c43d32373871fb9380e688ade, tools/check_test_gates.py comprova:

- parse de targets/prerequisites do Makefile em adjacency relations;
- ROOTS contendo host-gates;
- LIFO stack;
- seen set;
- traversal de prerequisite edges;
- reporte de host tests fora do reachable set.

Não há implementação reusable comprovada de:

- BFS;
- topological sort;
- Tarjan/Kosaraju;
- Dijkstra;
- Bellman-Ford;
- Floyd-Warshall;
- Kruskal;
- Prim.

Esses algoritmos são documentados como fundamentos e design tools, não como kernel features implementadas.

## Proveniência da revisão

As afirmações de implementação foram conciliadas com ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

Source revisado:

- tools/check_test_gates.py;
- makefile.

O claim concreto é deliberadamente estreito: o tooling atual contém depth-first-style dependency reachability a partir de host-gates. Os demais algoritmos permanecem teoria até que o source prove implementação.
