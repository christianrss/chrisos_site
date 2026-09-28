---
id: sorting-searching
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - APPS/EDITOR/EDITOR.CC
  - compiler/edit/editmodel.c
  - tools/test_pmm_heap_smp.c
  - tools/run_doom_cmp_scan.py
symbols:
  - line_for_pos
  - find_from
  - edit_search
  - cmp_u64
depends_on:
  - algorithmic-complexity
  - arrays-lists-stacks-queues
  - recursion-recurrences-amortization
  - trees-heaps-tries
related:
  - graph-algorithms
  - string-parsing-algorithms
  - systems-algorithms
  - hash-tables
---

# Algoritmos de ordenação e busca

<div class="abstract">
Ordenação e busca não são utilitários intercambiáveis, mas famílias de algoritmos cujos contratos dependem de ordem, representation, mutation policy, stability, distribuição de keys e formato do workload. Este capítulo desenvolve linear e binary search, lower/upper bounds, insertion e selection sort, merge sort, quicksort, heapsort, counting/radix techniques e o lower bound de comparison sorting. Também reconcilia esses fundamentos com o source atual do ChrisOS. O editor ChrisC executa uma busca binária real sobre o índice ordenado de inícios de linha em line_for_pos; suas rotinas de busca textual e o host edit model fazem scans diretos da esquerda para a direita. O teste SMP do PMM chama qsort da C library host apenas para ordenar endereços físicos antes de procurar duplicatas, portanto isso não estabelece uma implementação de qsort do ChrisOS. Um script de diagnóstico cujo docstring diz "Binary-search" não implementa busca binária na revisão analisada: ele percorre uma lista fixa de candidatos. A fronteira de implementação é determinada pelo control flow executado, não por nomes ou comentários.
</div>

## Ordenação como contrato

Sort recebe elementos e produz ordem segundo comparator ou key.

Para a e b, um comparator precisa fornecer relação consistente:

~~~text
a < b
a == b
a > b
~~~

Em comparison sorting, normalmente se exige strict weak ordering:

- irreflexividade;
- assimetria;
- transitividade;
- equivalence induzida por ausência de a<b e b<a também transitiva.

Comparator inconsistente pode invalidar qualquer algoritmo correto.

Em systems software o contrato inclui ainda:

- largura de element;
- key width;
- signed/unsigned order;
- endian interpretation de valores serializados;
- comparação de pointers por address ou pointed content;
- ownership durante swaps/moves.

## Stability

Stable sort preserva a ordem de entrada entre elementos com keys iguais.

Entrada:

~~~text
(5,A) (2,X) (5,B)
~~~

Saída estável:

~~~text
(2,X) (5,A) (5,B)
~~~

Algoritmo instável pode legalmente produzir:

~~~text
(2,X) (5,B) (5,A)
~~~

Stability é importante em ordenação multi-key e dados de UI/diagnóstico.

Kernel tables pequenas frequentemente não precisam disso, mas o requisito deve ser explícito.

## In-place e out-of-place

In-place sort usa O(1) ou O(log n) auxiliary state além da entrada, dependendo de recursion stack.

Out-of-place sort cria buffer auxiliar.

Essa diferença importa em:

- boot;
- interrupt context;
- memory pressure;
- firmware;
- collections muito grandes.

Um algoritmo assintoticamente bom pode ser inadequado se dobrar o peak memory.

## Linear search

Linear search examina candidatos em sequência.

Para n elementos:

~~~text
worst-case comparisons = n
time = O(n)
extra memory = O(1)
~~~

Não exige input ordenado.

~~~text
for i in 0..n-1:
    if a[i] == key:
        return i
return not_found
~~~

Para arrays muito pequenos, linear scan costuma ser melhor que introduzir manutenção de ordem.

## Pré-condição de binary search

Binary search exige search space monotônico.

Em array crescente:

~~~text
a[0] <= a[1] <= ... <= a[n-1]
~~~

Lower-bound search:

~~~text
lo = 0
hi = n

while lo < hi:
    mid = lo + (hi - lo) / 2
    if a[mid] < key:
        lo = mid + 1
    else:
        hi = mid
~~~

Ao terminar, lo é o primeiro index com valor não menor que key.

Um equality test adicional decide se a key está presente.

## Midpoint sem overflow

~~~text
(lo + hi) / 2
~~~

pode overflowar em integers grandes.

Forma mais robusta:

~~~text
lo + (hi - lo) / 2
~~~

Em arrays rigidamente limitados o overflow pode ser impossível, mas essa impossibilidade precisa fazer parte do bound comprovado.

## Lower e upper bound

lower_bound(key) retorna primeiro p em que:

~~~text
a[p] >= key
~~~

upper_bound(key) retorna primeiro p em que:

~~~text
a[p] > key
~~~

Logo todos os elementos iguais a key ocupam:

~~~text
[lower_bound(key), upper_bound(key))
~~~

Essas variantes são especialmente úteis com duplicates.

## Maior elemento não superior à query

Outra busca binária comum encontra:

~~~text
maior i tal que a[i] <= x
~~~

É o contrato do índice de linhas do editor ChrisC.

O midpoint pode ser enviesado para cima:

~~~text
mid = (lo + hi + 1) / 2
~~~

Se a[mid] <= x, lo = mid.

O bias evita loop infinito em intervalos de dois elementos quando lo recebe mid.

## Binary search no editor ChrisC

APPS/EDITOR/EDITOR.CC mantém:

~~~text
g_line_starts[]
g_line_count
~~~

O array é reconstruído em ordem crescente de offsets durante o scan do texto.

line_for_pos faz clamp de p e executa:

~~~text
lo = 0
hi = g_line_count - 1

while lo < hi:
    mid = (lo + hi + 1) / 2
    if g_line_starts[mid] <= p:
        lo = mid
    else:
        hi = mid - 1
~~~

O resultado é a última linha cujo start não ultrapassa p.

É busca binária real porque:

- o array é sorted;
- o predicate start <= p é monotônico;
- cada iteração reduz o intervalo.

Para L linhas:

~~~text
O(log L)
~~~

## Custo de rebuild do índice

Binary search não torna toda consulta sempre O(log L).

Após edição, o editor marca:

~~~text
g_line_index_dirty
~~~

e ensure_line_index pode reconstruir o índice percorrendo todo o buffer.

Assim:

- índice limpo: O(log L);
- índice dirty: O(N) para rebuild + O(log L).

Caches alteram custo amortizado, não eliminam a manutenção.

## Busca direta de substring no editor

find_from testa cada candidate position.

Para cada posição compara bytes do pattern até mismatch ou match completo.

~~~text
i = start
while i + M <= N:
    compare text[i+j] with pattern[j]
    if all match:
        return i
    i++
~~~

O backward mode varre posições em sentido inverso, mantendo comparação direta do pattern.

Worst case:

~~~text
O(N * M)
~~~

Extra state:

~~~text
O(1)
~~~

find_next e find_prev adicionam wraparound.

Não existe evidência aqui de KMP, Boyer-Moore ou suffix index.

## Busca no host edit model

compiler/edit/editmodel.c::edit_search usa a mesma estratégia básica:

- calcula pattern length;
- varre candidate starts;
- compara char por char;
- retorna primeira logical position que combina.

O conteúdo é gap buffer.

char_at traduz logical index para physical position antes/depois do gap.

A lógica de search continua sendo direct scan, e cada logical access é O(1).

## Seleção de estratégia de search

| Condição | Estratégia típica |
|---|---|
| tiny unsorted array | linear |
| sorted static array | binary search |
| equality key hashável | hash table |
| ordered dynamic set | balanced tree |
| prefix lookup | trie/radix |
| substring | direct scan, KMP, Boyer-Moore |
| muitas queries textuais | índices especializados |

O custo do search não pode ser separado do custo de construir/manter o índice.

## Insertion sort

Insertion sort mantém sorted prefix.

Para cada x:

1. guarda x;
2. desloca elementos maiores;
3. coloca x no gap.

~~~text
for i = 1 .. n-1:
    x = a[i]
    j = i
    while j > 0 and x < a[j-1]:
        a[j] = a[j-1]
        j--
    a[j] = x
~~~

Propriedades:

- worst O(n²);
- best O(n) em entrada já sorted;
- O(1) extra memory;
- stable se elementos iguais não forem cruzados;
- constants baixos para arrays pequenos.

Hybrid sorts costumam usá-lo em partitions pequenas.

## Selection sort

Selection sort encontra o minimum restante e o move para a posição atual.

Propriedades:

- O(n²) comparisons em todos os casos;
- O(n) swaps;
- O(1) memory;
- normalmente unstable.

Pode ser interessante quando writes são mais caros que comparisons.

## Merge sort

Merge sort divide a coleção, ordena metades e faz merge.

Recurrence:

~~~text
T(n) = 2T(n/2) + Theta(n)
~~~

Resultado:

~~~text
Theta(n log n)
~~~

Em arrays normalmente usa O(n) auxiliary buffer.

Pode ser stable escolhendo primeiro o elemento da esquerda quando keys são iguais.

Em linked lists, merge pode ser feito relinkando nodes.

## Quicksort

Quicksort particiona em torno de pivot.

Average com pivots adequados:

~~~text
O(n log n)
~~~

Worst:

~~~text
O(n²)
~~~

Pivots ruins em inputs adversariais podem produzir partitions extremamente desequilibradas.

Mitigações práticas:

- randomized pivot;
- median-of-three;
- recursion depth bound;
- fallback para heapsort;
- insertion sort em partitions pequenas.

Essa combinação leva ao padrão introsort.

## Invariantes de partition

Uma forma three-way:

~~~text
[ < pivot | == pivot | unknown | > pivot ]
~~~

Durante a execução, essas regiões precisam permanecer válidas.

Three-way partition ajuda em datasets com muitos duplicates.

Bounds dos índices devem ser provados independentemente da lógica de comparação.

## Heapsort

Heapsort constrói binary heap e extrai repetidamente root.

Propriedades:

- O(n log n) worst-case;
- O(1) auxiliary array memory;
- normalmente unstable;
- bound determinístico;
- locality pior que merge sequencial em muitos workloads.

Bottom-up build-heap é O(n), não O(n log n).

A razão é que a maioria dos nodes está perto das leaves e exige pouco sift-down.

## Counting sort

Com integer keys em range K:

~~~text
O(n + K)
~~~

Memory:

~~~text
O(K)
~~~

Conta ocorrências e reconstrói output.

Escapa do lower bound de comparison sorting porque usa representação das keys.

Se K for muito maior que n, torna-se ineficiente.

## Radix sort

Radix sort processa digits ou grupos de bits.

Para d passes:

~~~text
O(d * (n + base))
~~~

Em machine integers fixed-width, d é bounded.

LSD radix exige stable intermediate passes.

Byte order em memória não define automaticamente digit order numérico.

## Lower bound de comparison sorting

Comparison sorting pode ser representado por decision tree.

Existem n! permutations de n elementos distintos.

Árvore binária de altura h tem no máximo 2^h leaves.

~~~text
2^h >= n!
h >= log2(n!)
h = Omega(n log n)
~~~

Logo nenhuma comparison-only sort garante o(n log n) comparisons em arbitrary input.

Counting/radix usam propriedades adicionais do key domain.

## Invariantes de correção por algoritmo

Cada família possui um invariant diferente, e esse invariant é mais importante que memorizar pseudocode.

Em insertion sort, antes de iniciar iteration i:

~~~text
a[0..i) está ordenado
~~~

A iteration remove conceitualmente a[i], desloca elementos maiores e restaura a propriedade para:

~~~text
a[0..i+1)
~~~

Em merge sort, o merge mantém:

~~~text
output já produzido está ordenado
e
contém exatamente os menores elementos já consumidos das duas runs
~~~

Em binary search, o invariant deve dizer onde a resposta ainda pode estar. Para lower_bound:

~~~text
todos os índices < lo já são estritamente menores que key
todos os índices >= hi já são candidatos não menores
~~~

A cada iteration o intervalo [lo, hi) diminui.

Em quicksort, partition deve preservar regiões de comparação em torno do pivot. Sem esse invariant, um loop que apenas "parece mover índices na direção certa" pode perder elements, duplicar swaps ou não terminar com duplicates.

## Custo de movimentação versus custo de comparação

Big-O de comparisons não descreve todo o custo.

Para records grandes, trocar o payload completo pode ser muito mais caro que comparar keys.

Uma técnica comum é ordenar:

~~~text
array de índices ou pointers
~~~

em vez dos records.

Depois o sistema pode:

- manter a indirect order;
- aplicar permutation ao final;
- iterar na ordem indireta.

Isso reduz bytes movimentados, mas adiciona pointer/index indirection e pode piorar locality durante consumo.

Selection sort, apesar de O(n²) comparisons, realiza apenas O(n) swaps e por isso aparece em cenários em que write cost é excepcionalmente alto.

## Locality e comportamento de cache

Insertion sort acessa regiões próximas e costuma ter ótima locality em arrays pequenos.

Merge sort faz passes relativamente sequenciais, favorecendo prefetch/cache bandwidth, mas precisa de auxiliary buffer em sua forma clássica para arrays.

Heapsort salta entre parent/child positions:

~~~text
i
2i+1
2i+2
~~~

e por isso tende a produzir acesso menos sequencial em heaps grandes.

Quicksort pode ter boa locality dentro de partitions, porém recursive partitioning e pivot behavior determinam o padrão real.

Assim, dois algoritmos com O(n log n) podem ter tempos muito diferentes na mesma CPU.

## Duplicates e comparator equality

Datasets de sistemas frequentemente possuem keys repetidas:

- priorities;
- timestamps truncados;
- device classes;
- status codes.

Em quicksort two-way simples, muitos values iguais ao pivot podem produzir partitions ruins.

Three-way partition separa:

~~~text
< pivot
== pivot
> pivot
~~~

e evita retrabalho sobre a faixa igual.

Em binary search, duplicates exigem decidir se a API quer:

- qualquer occurrence;
- first occurrence;
- last occurrence;
- lower_bound;
- upper_bound;
- equal range.

Sem esse contrato, duas implementações corretas podem retornar índices diferentes e quebrar callers que assumem first match.

## Busca indexada e custo de manutenção

Manter sorted index transforma algumas queries de O(n) para O(log n), mas updates deixam de ser gratuitos.

Em array sorted, inserir no meio pode exigir:

~~~text
O(n)
~~~

movimentos.

Uma balanced tree oferece:

~~~text
O(log n)
~~~

search e update, com maior metadata e pointer cost.

Hash table oferece expected O(1) equality lookup, porém perde ordered traversal natural.

No editor ChrisC, g_line_starts ilustra a mesma troca: line lookup é O(log L) quando o index está válido, mas text edits invalidam o index e podem provocar rebuild O(N).

## Busca em storage não contíguo

Binary search exige random access eficiente ao elemento mid.

Em linked list, localizar o midpoint por traversal custa O(n), eliminando o principal benefício.

Para linked data, alternativas incluem:

- manter auxiliary array/index;
- usar balanced tree;
- reorganizar representação;
- aceitar linear scan.

A estrutura de dados e o algoritmo de busca precisam ser escolhidos juntos.

## Boundary cases e termination proof

Binary search bugs normalmente aparecem em:

- empty range;
- one-element range;
- key abaixo do mínimo;
- key acima do máximo;
- duplicates;
- midpoint bias incompatível com update de lo/hi.

No line_for_pos atual, hi começa em g_line_count-1 e midpoint é biased upward:

~~~text
(lo + hi + 1) / 2
~~~

Quando o predicate é true, lo = mid.

Quando false, hi = mid-1.

Em ambos os casos, se lo < hi, o intervalo diminui estritamente. Essa é a termination proof local.

## qsort no teste do PMM

tools/test_pmm_heap_smp.c coleta physical addresses obtidos em threads host concorrentes.

Depois executa:

~~~text
qsort(all, NCPU * PAGES_PER, sizeof(all[0]), cmp_u64)
~~~

e procura duplicates adjacentes.

Após sorting:

~~~text
if all[i] == all[i - 1]:
    duplicate
~~~

Essa é lógica de validação host.

O source chama qsort da C library; não implementa seu algoritmo.

O C standard define o comportamento da função, não exige que internamente seja quicksort.

Portanto o projeto não deve ser descrito como contendo quicksort apenas pelo nome qsort.

## Divergência entre comentário e control flow

tools/run_doom_cmp_scan.py possui docstring dizendo que faria binary search do primeiro PC de divergência JIT/interpreter.

Na revisão atual, o corpo:

- decodifica instruction starts;
- filtra uma hard-coded candidate list;
- chama probe para cada candidato.

Não existe lo/hi/midpoint narrowing loop.

Logo esse arquivo não é evidência de implementação atual de binary search.

É um caso concreto da hierarquia de evidência: current control flow prevalece sobre comentário.

## Validação de sorting

Um teste robusto valida:

- nondecreasing output;
- permutation preservation;
- stable order quando prometida;
- empty input;
- singleton;
- duplicates;
- reverse-sorted input;
- bounds.

Permutation pode ser validada com independent multiset ou referência.

Comparar apenas com um expected array pequeno não cobre invariantes gerais.

## Validação de binary search

Para lower_bound:

~~~text
para todo i < p: a[i] < key
para todo i >= p: a[i] >= key
~~~

Para o contrato do editor:

~~~text
a[p] <= x
e
p é último índice ou a[p+1] > x
~~~

Boundary tests:

- um elemento;
- minimum;
- maximum;
- query exata;
- query entre entries;
- duplicates;
- valores fora do range segundo clamp policy.

## Concorrência

Sort normalmente muta coleção inteira.

Concurrent readers exigem:

- exclusive ownership;
- copy-and-publish;
- versioning;
- external lock.

Binary search sobre immutable sorted array é naturalmente read-only.

Mas se outro thread alterar order ou lifetime simultaneamente, sortedness pode desaparecer mesmo que loads isolados sejam atomic.

O editor atual não é tratado neste capítulo como concurrent index.

## Segurança e inputs adversariais

Riscos:

- quicksort O(n²) adversarial;
- comparator overflow;
- merge-buffer allocation overflow;
- binary-search bounds inválidos;
- naive substring O(NM);
- repeated invalidation produzindo rebuilds O(N).

Mitigações podem incluir introsort, bounds rígidos, overflow-safe arithmetic e complexity budgets.

## Fronteira da implementação ChrisOS

Na revisão da3df29cb397932c43d32373871fb9380e688ade, o source comprova:

- binary search em line_for_pos;
- direct forward/backward substring scan em find_from;
- direct gap-buffer substring scan em edit_search;
- uso host da C library qsort em PMM SMP validation;
- diagnostic script cujo docstring diz binary-search, mas cujo corpo atual percorre candidatos fixos.

Não há implementação nativa comprovada de:

- merge sort;
- quicksort;
- sorting heapsort;
- counting sort;
- radix sort;
- KMP;
- Boyer-Moore;
- generic binary-search library.

Esses algoritmos são fundamentos e alternativas de design.

## Modelo de validação

O checker determinístico deste capítulo verifica:

- insertion sort ordering e stability;
- merge sort ordering e stability;
- heapsort ordering;
- lower_bound e upper_bound;
- greatest-index-not-above binary search;
- direct substring scan;
- permutation preservation;
- anchors de line_for_pos, find_from e edit_search;
- qsort como external host-library call;
- ausência de midpoint loop em run_doom_cmp_scan.py apesar do docstring.

O checker não tenta inferir o algoritmo interno da implementação qsort da libc.

## Proveniência da revisão

As afirmações de implementação foram conciliadas com ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

Source revisado:

- APPS/EDITOR/EDITOR.CC;
- compiler/edit/editmodel.c;
- tools/test_pmm_heap_smp.c;
- tools/run_doom_cmp_scan.py.

A documentação separa deliberadamente API name, comment intent e algoritmo realmente executado.
