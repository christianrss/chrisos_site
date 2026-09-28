---
id: trees-heaps-tries
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - compiler/chrisc/chrisc.c
  - kernel/fs/cfs.c
  - kernel/metal/heap.c
symbols:
  - Node
  - Compiler
  - node
  - gen_expr
  - dir_find
  - walk_parent
  - walk_full
  - kmalloc
  - kfree
depends_on:
  - arrays-lists-stacks-queues
  - recursion-recurrences-amortization
related:
  - hash-tables
  - graphs-union-find
  - string-parsing-algorithms
  - compiler-pipeline
  - chrisfs
---

# Trees, binary heaps e tries

<div class="abstract">
Trees representam relações hierárquicas, binary heaps impõem uma ordem parcial sobre uma complete tree e tries organizam chaves por prefixos compartilhados. Essas estruturas resolvem problemas diferentes, embora todas possam ser desenhadas como diagramas ramificados. Este capítulo desenvolve rooted trees, traversal, binary search trees, balanceamento, priority heaps, tries, radix trees comprimidas, complexidade, representação em memória, falhas e concorrência. A teoria é então conciliada com o source atual do ChrisOS sem inventar estruturas inexistentes. ChrisC armazena sua AST em um array contíguo e fixo de Node, com links inteiros left, right e third e links next para chains de statements/siblings; isso é uma syntax tree indexada real, e não uma binary-search tree. ChrisFS expõe uma hierarquia de paths enraizada, mas cada componente é localizado por scan linear de diretório, e não por balanced tree ou trie. O arquivo kernel/metal/heap.c implementa allocator de memória por arenas e blocos sequenciais; ele não é binary heap nem priority queue.
</div>

## Pré-requisitos e escopo

Este capítulo pressupõe arrays, estruturas ligadas, recursão e análise de complexidade.

Três famílias são abordadas:

- **trees:** relações parent/child hierárquicas;
- **binary heaps:** complete binary trees com invariante de ordem;
- **tries:** árvores cujas edges codificam prefixos.

A palavra "heap" também é usada para dynamic memory allocation. Esse significado é diferente do binary heap de estruturas de dados.

No ChrisOS:

~~~text
kernel/metal/heap.c
~~~

é allocator do kernel, não priority heap.

## Rooted trees

Uma rooted tree contém:

- uma root;
- zero ou mais child edges por node;
- exatamente um parent para cada node não-root;
- ausência de ciclos;
- exatamente um simple path da root até qualquer node.

Terminologia:

| Termo | Significado |
|---|---|
| root | node sem parent |
| parent | predecessor imediato |
| child | descendente imediato |
| leaf | node sem children |
| depth | quantidade de edges da root ao node |
| height | maior caminho descendente até leaf |
| subtree | node e todos os descendentes |
| sibling | nodes com mesmo parent |

Se ciclos são permitidos, a estrutura é graph, não tree.

## Tamanho, altura e shape

Uma tree com n nodes pode possuir alturas muito diferentes.

Uma chain tem:

~~~text
height = n - 1
~~~

Uma balanced binary tree possui:

~~~text
height = Theta(log n)
~~~

Muitas operações de tree são O(h), com h sendo a altura.

Portanto shape faz parte do modelo de custo.

Dizer "tree lookup é O(log n)" só é correto quando há invariante que garante altura logarítmica.

## Representações de tree

Representações comuns:

- pointers de parent para children;
- parent pointers;
- first-child/next-sibling;
- arrays de child indices;
- campos fixos left/right;
- índices implícitos por aritmética, como binary heaps.

Em systems software, índices podem ser preferíveis quando:

- storage é pool fixo;
- serialização importa;
- objetos se movem como bloco;
- bounds checking é desejável;
- pointer width seria desperdício.

## Trees indexadas

Suponha:

~~~text
Node nodes[N]
~~~

e child references por índices inteiros.

Sentinel -1 significa ausência de child.

Invariantes:

~~~text
child == -1
ou
0 <= child < nnode
~~~

Para uma tree verdadeira:

- todo node exceto root possui um parent;
- não há cycles;
- todo child aponta para node ativo;
- root pertence ao objeto que possui a tree.

Índice inválido é equivalente indexado de bad pointer.

## Traversal

Depth-first traversal pode ser:

- preorder: node, depois children;
- inorder: left, node, right em binary tree;
- postorder: children, depois node.

Breadth-first visita por nível.

DFS recursiva usa O(h) de call stack.

DFS iterativa usa explicit stack.

BFS usa queue e pode consumir O(w), com w sendo maximum width.

Traversal completa custa Theta(n) para n nodes visitados.

## AST do ChrisC

ChrisC atual define:

~~~text
#define NODE_MAX 131072

typedef struct Node {
    NodeKind kind;
    int left, right, third, next;
    ...
} Node;
~~~

Compiler contém:

~~~text
Node nodes[NODE_MAX];
int nnode;
~~~

node aloca o próximo slot e inicializa:

~~~text
left = right = third = next = -1
~~~

É um node pool indexado e contíguo.

Os relacionamentos não são pointers C; são índices no próprio array do Compiler.

## Semântica da AST

Os campos mudam de significado conforme NodeKind.

Nodes de expressão normalmente usam:

- left para primeiro operando;
- right para segundo;
- third para ternary ou metadata adicional;
- next para chains de statements/argumentos.

A AST não é necessariamente binary tree estrita.

A classificação mais adequada é:

~~~text
syntax tree indexada + linked chains por índices
~~~

Há nodes com um, dois ou três children e nodes ligados por next.

## Ownership da AST

Todo armazenamento Node pertence a uma instância Compiler.

Consequências:

- child indices só fazem sentido naquela instância;
- não há per-node heap allocation;
- nodes ficam contíguos;
- NODE_MAX limita o tamanho total;
- referências por índice permanecem estáveis enquanto o pool não é reconstruído.

node rejeita nova alocação quando:

~~~text
nnode == NODE_MAX
~~~

e gera erro de AST cheia.

Isso converte crescimento ilimitado em failure explícita.

## Traversal da AST no code generation

gen_expr recebe node id e gera código recursivamente para child expressions.

Em operação binária, o padrão conceitual é:

~~~text
generate(left)
generate(right)
emit(operator)
~~~

Isso se aproxima de postorder traversal para avaliação de expressões.

Custo é proporcional aos nodes visitados mais trabalho específico de cada operator.

Peak recursion do host depende da profundidade da expressão, não do total de nodes.

## Tree geral não é search tree

Syntax tree não satisfaz:

~~~text
keys(left subtree) < key(node) < keys(right subtree)
~~~

Esse é o invariante de BST.

left/right no ChrisC significam operandos sintáticos, não partições ordenadas por key.

Portanto nomes de fields não bastam para classificar uma estrutura.

## Binary search trees

BST associa ordered key a cada node.

Invariante:

~~~text
keys(left subtree) < key(node)
keys(right subtree) > key(node)
~~~

ou política explícita para duplicates.

Lookup, insert e delete custam:

~~~text
O(h)
~~~

Se a inserção gerar chain, h pode chegar a n.

BST não balanceada tem worst case O(n).

## Balanced trees

Self-balancing trees mantêm constraints de altura.

Exemplos:

- AVL;
- red-black;
- B-tree;
- B+ tree.

AVL mantém balance relation mais rígida.

Red-black usa color invariants e garante O(log n) com menos restrições locais.

B-tree usa vários keys por node para reduzir height e combinar com block/cache geometry.

Escolha depende de ordered lookup, range queries, persistence, I/O e locality.

## Rotations

Balanced binary trees ajustam forma por rotations.

Right rotation:

~~~text
        y                x
       / \              / \
      x   C    ->       A   y
     / \                  / \
    A   B                B   C
~~~

A sequência inorder permanece a mesma.

Rotations mudam links e podem exigir atualização de parent pointers e metadata.

O source revisado do ChrisOS não demonstra generic AVL ou red-black implementation.

## Binary heaps

Binary heap não é BST.

Possui dois invariantes:

1. shape: complete binary tree;
2. order: parent domina children.

Min-heap:

~~~text
parent <= child
~~~

Max-heap:

~~~text
parent >= child
~~~

Apenas a root é globalmente mínima ou máxima.

Buscar arbitrary key continua O(n).

## Representação em array

Complete binary tree mapeia naturalmente para array.

Com index zero-based i:

~~~text
parent(i) = floor((i - 1) / 2)
left(i)   = 2i + 1
right(i)  = 2i + 2
~~~

Não são necessários child pointers.

A heap ativa ocupa normalmente:

~~~text
a[0:n]
~~~

Isso oferece alta localidade e baixo overhead.

## Inserção em heap

Em min-heap:

1. append x no fim;
2. incrementa n;
3. compara com parent;
4. enquanto menor que parent, troca para cima.

É sift-up.

Altura é O(log n), logo insert é O(log n).

peek-min é O(1) em a[0].

## Remove-min

Passos:

1. salva root;
2. move último elemento para root;
3. decrementa n;
4. troca para baixo com o menor child enquanto o order invariant estiver violado.

É sift-down.

Custo O(log n).

Priority queue costuma usar binary heap porque precisa localizar rapidamente o item de maior prioridade, não fazer ordered search arbitrária.

## Build-heap

Inserir n elementos um por um custa O(n log n).

Bottom-up build, fazendo sift-down a partir do último internal node, custa:

~~~text
Theta(n)
~~~

A maioria dos nodes está perto das leaves e desce poucas posições.

É exemplo clássico em que somar alturas produz bound mais justo.

## O heap do kernel ChrisOS não é binary heap

kernel/metal/heap.c define:

~~~text
struct heap_block {
    uint64_t size;
    uint32_t used;
    ...
}

struct heap_arena {
    uint8_t *base;
    uint64_t limit;
}
~~~

kmalloc_in_arenas percorre blocks dentro das arenas em busca de free block grande o suficiente.

O allocator:

- divide blocks;
- marca blocks usados;
- cresce adicionando arenas;
- faz forward coalescing em free;
- protege estado por heap_lock.

Isso é dynamic-memory heap no sentido de allocator.

Não há:

- complete-tree shape;
- parent/child index formula;
- sift-up;
- sift-down;
- min/max root invariant.

Classificá-lo como binary heap seria incorreto.

## Complexidade do allocator versus priority heap

A sobreposição de nomes pode esconder custos distintos.

kmalloc atual procura por scan de arenas e blocks até achar fit.

Não há balanced search tree nem binary heap indexando free blocks nesse source.

Portanto não existe garantia O(log n) derivada de tree height.

Binary heap de priority queue, ao contrário, usa O(log n) em insert/remove.

## Tries

Trie armazena keys por prefixos.

Para:

~~~text
car
cat
dog
~~~

a estrutura pode compartilhar:

~~~text
c
└─ a
   ├─ r
   └─ t

d
└─ o
   └─ g
~~~

Lookup percorre uma edge por unidade da key.

Para key length L:

~~~text
O(L)
~~~

quando child selection possui custo bounded.

## Representação de trie

Children podem ser armazenados como:

- fixed fanout array;
- sorted vector;
- linked list;
- hash map;
- balanced tree;
- bitmap + compact child array.

A melhor escolha depende do alphabet e sparsity.

Para bytes ASCII, 256 pointers permitem direct lookup mas consomem muita memória por node.

Representações sparse economizam memória ao custo de procurar child.

## Semântica de prefixos

Trie precisa distinguir:

~~~text
key termina aqui
~~~

de:

~~~text
prefixo continua
~~~

Se "net" e "network" existem, o node após t precisa indicar que net é complete key e também possuir children.

Sem terminal marker ou stored value, prefixos não são distinguíveis de keys completas.

## Compressed tries e radix trees

Path compression combina chains de single child.

Em vez de:

~~~text
c -> o -> m -> p -> i -> l -> e -> r
~~~

uma edge pode armazenar:

~~~text
"compiler"
~~~

Isso reduz node count e pointer overhead.

Patricia trie é representação comprimida relacionada, frequentemente por bits.

Radix trees servem para:

- route tables;
- prefix lookup;
- path indexes;
- dictionaries;
- IP prefixes.

O source revisado não demonstra generic trie/radix implementation no ChrisOS.

## Namespace ChrisFS como hierarchy enraizada

Paths do ChrisFS são hierárquicos.

walk_full começa em:

~~~text
CFS_ROOT_INODE
~~~

e processa components em ordem.

Para cada component:

- chama dir_find;
- lê inode;
- exige CFS_INODE_DIR para intermediários;
- verifica walk permission;
- atualiza cur para o child inode.

Conceitualmente:

~~~text
root
  ↓ component 0
directory
  ↓ component 1
directory
  ↓ component 2
target
~~~

É rooted namespace traversal.

Mas o lookup de cada directory não usa trie nem balanced tree.

## Custo de lookup de diretório no ChrisFS

dir_find percorre:

- directory blocks;
- slots CFS_DIRENTS_PER_SECTOR;
- compara name length e bytes.

É linear scan.

Para path com d components e diretórios com populações k1...kd, modelo simplificado:

~~~text
O(k1 + k2 + ... + kd)
~~~

mais cache/storage access.

Isso difere de:

- O(log k) com balanced-tree index;
- O(L) com trie sobre todo path.

A namespace é tree-shaped, mas a procura por child é linear.

## Modelo abstrato versus storage

Filesystem pode expor tree sem armazenar uma pointer tree monolítica.

ChrisFS representa membership com directory entries que apontam para inode identifiers.

walk_full reconstrói a relação percorrendo desde a root.

Princípio:

~~~text
abstract data model != physical storage representation
~~~

Hierarchical API não implica generic tree container.

## Falhas em traversal hierárquica

Possíveis falhas:

- component ausente;
- intermediate inode não-directory;
- permission denied;
- inode id inválido;
- directory data corrupta;
- path depth excessiva;
- cycles por metadata corrompida.

dir_find verifica range do inode e walk_full rejeita intermediate non-directory.

Consistência total pertence aos capítulos de ChrisFS/fsck.

## Segurança

Trees:

- pathological height;
- recursion exhaustion;
- cycles;
- invalid pointers/indices;
- use-after-free.

Priority heaps:

- capacity overflow;
- comparator inconsistente;
- stale position index;
- race durante swap.

Tries:

- memory amplification;
- keys excessivamente longas;
- canonicalization ambiguity;
- deep traversal.

Systems code precisa explicitar bounds, ownership e validation.

## Concorrência

Mutable tree pode alterar múltiplos links em uma operação.

Balanced insertion pode tocar:

- parent;
- child;
- grandparent;
- balance/color metadata.

Heap mutation troca múltiplos slots.

Trie insertion pode alocar vários nodes.

Estratégias:

- coarse lock;
- lock coupling;
- immutable nodes;
- RCU;
- versioning;
- thread confinement.

A AST atual é compiler-owned; este capítulo não infere suporte a concurrent AST mutation.

ChrisFS possui locking próprio tratado nos capítulos de storage.

## Localidade e desempenho

Pointer tree pode causar:

- cache misses;
- TLB misses;
- allocator fragmentation.

AST indexada do ChrisC concentra nodes em array.

Binary heap é muito cache-friendly por ser contiguous.

Trie pode ter metadata maior que payload, especialmente com fanout largo.

Compressed radix reduz node count em troca de mais comparação por edge.

## Guia de seleção

| Requisito | Estrutura típica |
|---|---|
| exact unordered lookup | hash table |
| ordered lookup/range | balanced search tree |
| priority min/max | binary heap |
| prefix lookup | trie/radix |
| syntax hierarchy | general tree/AST |
| filesystem namespace | rooted hierarchy com index específico |
| persistent ordered block index | B-tree/B+ tree |

A escolha segue operations e invariants, não nomes.

## Evidência de validação

O checker determinístico valida:

- bounds e traversal de indexed tree;
- preorder/inorder/postorder;
- BST ordering e worst-case height não balanceada;
- fórmulas de parent/child de binary heap;
- min-heap insert, peek e remove;
- bottom-up build;
- trie insert, exact lookup e prefix behavior;
- anchors do ChrisC para NODE_MAX, left/right/third/next, node initialization e gen_expr;
- anchors do ChrisFS para CFS_ROOT_INODE, dir_find com nested scans, walk_parent e walk_full;
- anchors do allocator mostrando heap_block/heap_arena, sequential block scan, split/coalesce e ausência de priority-heap contract.

Os modelos não constituem prova formal do compiler, filesystem ou allocator completos.

## Fronteira da implementação atual

Na revisão da3df29cb397932c43d32373871fb9380e688ade o source demonstra:

- syntax tree indexada no ChrisC;
- namespace hierárquica no ChrisFS com lookup linear por diretório;
- dynamic-memory allocator chamado heap.

Não foi demonstrada uma implementação genérica de:

- BST;
- AVL;
- red-black tree;
- B-tree;
- binary priority heap;
- trie;
- radix tree.

Essas estruturas permanecem fundamentos e possíveis representações futuras, não claims do ChrisOS atual.

## Fronteira do roadmap

O currículo segue:

~~~text
hash tables
      ↓
trees / heaps / tries
      ↓
graphs / union-find
      ↓
bitmaps / rings / free lists
      ↓
systems algorithms
~~~

A próxima etapa generaliza hierarquia acíclica para relações de graph e conectividade por disjoint sets.

## Proveniência da revisão

As afirmações ligadas à implementação foram conciliadas contra ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

Fontes:

- compiler/chrisc/chrisc.c;
- kernel/fs/cfs.c;
- kernel/metal/heap.c.

Símbolos/estado:

- Node;
- Compiler;
- node;
- gen_expr;
- NODE_MAX;
- dir_find;
- walk_parent;
- walk_full;
- CFS_ROOT_INODE;
- heap_block;
- heap_arena;
- kmalloc;
- kfree.

As classificações são deliberadamente estritas: left/right na AST não implicam BST, namespace hierárquica não implica trie e dynamic-memory heap não é binary priority heap.
