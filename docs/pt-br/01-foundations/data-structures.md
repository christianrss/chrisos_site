---
id: data-structures
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- kernel/metal/pmm.c
symbols:
- scan_usable_for_run
- pmm_alloc
depends_on:
  - data-representation-layout
  - algorithmic-complexity
related:
- systems-algorithms
---

# Estruturas de dados para software de sistemas

<div class="abstract">
Estrutura de dados é uma representação acompanhada de invariantes escolhidos para sustentar um conjunto de operações. Em software de sistemas, complexidade assintótica é apenas parte da decisão: localidade, memória limitada, falha de alocação, estabilidade de endereço, escopo de lock, segurança em interrupções e serialização frequentemente importam tanto quanto Big-O. Este capítulo desenvolve as estruturas recorrentes em kernels, compiladores, filesystems, drivers, gráficos e emuladores.
</div>

## Representação, invariante e operação

Uma estrutura deve ser descrita por três perguntas:

1. **Representação:** como os elementos são armazenados?
2. **Invariante:** o que precisa continuar verdadeiro após toda operação?
3. **Operações:** quais consultas e mutações precisam ser eficientes?

Em uma fila circular, por exemplo, a representação pode ser array fixo mais <code>head</code>, <code>tail</code> e <code>count</code>. O invariante garante índices dentro da capacidade e count nunca acima do limite. Enqueue/dequeue tornam-se atualizações modulares.

Sem invariante, existem apenas campos.

## Arrays

Array armazena elementos iguais contiguamente.

| Operação | Custo típico |
|---|---:|
| acesso por índice | O(1) |
| travessia sequencial | O(n) |
| busca não ordenada | O(n) |
| inserir/remover no meio | O(n) |
| escrever slot livre conhecido | O(1) |

Arrays aparecem intensamente em software de sistemas por oferecerem armazenamento previsível e forte localidade. Arrays de capacidade fixa também eliminam dependência de allocator.

A fraqueza é rigidez: crescer além da capacidade ou inserir no meio pode ser caro.

Tabelas de kernel frequentemente aceitam busca O(n) porque n é pequeno, limitado e a representação é simples.

## Arrays dinâmicos

Vector dinâmico mantém ponteiro, tamanho e capacidade. Ao esgotar a capacidade, aloca região maior e copia elementos.

Crescimento geométrico fornece append amortizado O(1). Porém uma expansão individual é O(n), aloca memória e invalida ponteiros crus para os elementos.

Isso pode tornar vector inadequado para estruturas de kernel cujos endereços precisam permanecer estáveis ou que são alteradas em contexto de interrupção.

## Listas ligadas

Lista simplesmente ligada armazena payload e ponteiro next. Lista duplamente ligada adiciona prev.

Vantagens:

- inserção/remoção O(1) quando nó ou predecessor já é conhecido;
- endereços estáveis;
- dispensa contiguidade.

Custos:

- overhead de ponteiros;
- localidade ruim;
- acesso indexado e busca O(n);
- dependência de alocação, salvo nós embutidos ou pools.

Lista não é automaticamente melhor para coleções muito mutáveis. Em hardware moderno, array compacto frequentemente vence por localidade.

## Listas intrusivas

Kernel pode embutir os links no próprio objeto.

    struct Task {
        ...
        Task *next;
        Task *prev;
    }

Isso elimina alocação de nó separado e torna ownership mais direto. Um objeto só pode participar de múltiplas listas simultâneas se possuir links distintos para cada papel.

O invariante precisa definir se nó pode estar desconectado, ligado uma vez ou em várias coleções.

## Pilhas

Stack segue LIFO.

Com array e stack pointer:

- push: grava no topo e incrementa;
- pop: decrementa e lê;
- ambas O(1).

A call stack da CPU é uma pilha especializada de return addresses, registradores salvos, locais e argumentos conforme ABI.

Pilhas também servem para parsing, DFS, rollback e frames de exceção.

Uma pilha limitada precisa definir overflow; recursão conceitualmente ilimitada pode causar kernel stack overflow.

## Filas

Queue segue FIFO.

Uma fila em array que desloca elementos ao remover custa O(n). Lista ligada evita movimento, porém usa nós e ponteiros. Ring buffer preserva O(1) sem alocação.

Filas aparecem em:

- jobs;
- comandos de dispositivo;
- pacotes;
- eventos;
- pipelines produtor/consumidor.

A disciplina pode ser FIFO, prioridade, deadline, fair queueing ou work stealing.

## Buffers circulares e rings

Ring mapeia posições lógicas crescentes para array fixo com aritmética modular.

Para capacidade C:

    next(i) = (i + 1) mod C

Full e empty podem ser diferenciados por:

- count;
- slot vazio reservado;
- contadores monotônicos mais largos;
- bits de geração.

Rings são adequados para drivers porque produtor e consumidor trocam ownership de descritores sem mover objetos.

Em concorrência ou device sharing, memory ordering faz parte do invariante.

## Deques

Double-ended queue permite inserir e remover dos dois lados.

Implementação em array usa índices circulares; implementação ligada usa lista dupla.

Deques aparecem em work stealing: owner opera de um lado e workers concorrentes roubam do outro. Versões lock-free exigem raciocínio atômico muito mais forte que fila FIFO comum.

## Bitmaps

Bitmap armazena um estado booleano por bit.

Para recurso i:

    byte = i / 8
    bit  = i % 8

Vantagens:

- altíssima densidade;
- teste e update rápidos;
- boa localidade;
- possibilidade de scan por palavra.

Achar bit livre por scan é O(n), salvo índices hierárquicos ou instruções de bit-scan.

Bitmaps são naturais para páginas físicas, CPU affinity, descritores e conjuntos de capabilities.

## Bitsets

Quando o universo é pequeno e fixo, bitset representa conjunto com mais eficiência que hash table.

União, interseção e diferença tornam-se OR, AND e AND-NOT por palavras.

Para até 64 CPUs, um inteiro de 64 bits pode representar membership.

A técnica é excelente quando identificadores são densos e limitados.

## Hash tables

Hash table transforma chave em bucket por função hash.

Lookup esperado pode ser O(1), porém colisões precisam de política:

- chaining;
- open addressing;
- linear/quadratic probing;
- Robin Hood;
- cuckoo.

No kernel importam pior caso, resize, colisões controladas por atacante e alocação.

Tabela fixa com open addressing evita nós dinâmicos, mas precisa de load factor e tombstones.

## Árvores binárias de busca

BST mantém:

    keys(left) < key(node) < keys(right)

Busca segue um ramo por comparação.

Sem balanceamento pode degenerar para O(n). AVL e red-black preservam altura O(log n).

Árvores são úteis quando traversal ordenado, predecessor/successor ou range queries importam além de lookup exato.

## B-trees e B+ trees

Sistemas de armazenamento usam árvores de alto fan-out com vários keys por nó.

B-tree reduz altura aproximando tamanho do nó do tamanho de bloco/cache. B+ tree normalmente mantém records nas folhas e usa nós internos como índice.

Em disco ou SSD, reduzir I/O aleatório costuma importar mais que diminuir comparações.

## Heaps e priority queues

Binary heap é normalmente armazenado em array. Para índice i:

    left   = 2i + 1
    right  = 2i + 2
    parent = floor((i - 1) / 2)

Min-heap mantém parent <= children.

| Operação | Custo |
|---|---:|
| consultar mínimo | O(1) |
| inserir | O(log n) |
| remover mínimo | O(log n) |
| construir heap | O(n) |

Priority queues servem para timers, deadlines e event simulation.

Heap de prioridade não é o mesmo conceito que heap allocator.

## Tries e radix trees

Trie percorre componentes de uma chave. Radix tree comprime caminhos.

Aplicações:

- prefix lookup;
- roteamento;
- índices inteiros esparsos;
- mappings;
- names.

Memória e branching dependem da representação da chave.

## Grafos

Grafo possui vértices e arestas.

Representações:

- matriz de adjacência: O(V²), teste de aresta O(1);
- listas de adjacência: O(V+E);
- formatos esparsos compactados.

Grafos modelam dependências, control flow, recursos e builds.

BFS usa fila e explora por distância. DFS usa recursão ou stack e explora caminhos. Com lista de adjacência ambos são O(V+E).

## Union-find

Disjoint-set union representa partição em conjuntos.

Operações:

- find;
- union.

Path compression + union by rank/size oferece desempenho amortizado próximo de constante, O(alpha(n)).

Serve para conectividade e alguns problemas de alocação/grafos.

## Free lists

Free list encadeia objetos ou blocos reutilizáveis.

Allocation remove entrada; free reinsere. Para blocos de tamanho único, ambas podem ser O(1).

Allocators gerais precisam de política por tamanhos: classes, boundary tags, segregated lists, trees ou buddy.

Free list simples pode fragmentar se tamanhos forem arbitrários.

## Buddy allocator

Buddy gerencia blocos em potências de dois. Split divide um bloco em dois buddies; free pode coalescer dois buddies livres.

Allocation/free são tipicamente logarítmicos na quantidade de ordens e usam metadados previsíveis.

O custo é fragmentação interna por arredondamento.

É comum em sistemas, mas o PMM atual do ChrisOS usa bitmap e scan, não buddy tree.

## Slabs e object caches

Slab reserva páginas e as divide em objetos de tamanho fixo por classe.

Benefícios:

- amortiza page allocation;
- reduz fragmentação;
- reutiliza objetos;
- pode oferecer caches per-CPU.

Serve para objetos frequentes de kernel.

Adiciona metadados e lifecycle em relação a heap simples.

## Arenas

Arena aloca muitos objetos em uma região e libera tudo junto.

Allocation pode ser bump pointer:

    result = cursor
    cursor += aligned_size

É extremamente rápida. Free individual normalmente não existe.

Arenas funcionam quando lifetimes são agrupados, como dados temporários de parser ou uma etapa de build.

## Representação esparsa e densa

Se identificadores ocupam quase todas as posições de intervalo pequeno, arrays e bitsets são eficientes.

Se são esparsos em keyspace enorme, hash, tree ou radix podem economizar memória.

A decisão começa pela densidade do domínio e pelo perfil de operações.

## Endereços estáveis

Alguns subsistemas armazenam ponteiros para elementos. Resize de vector pode mover todos e invalidar referências; estruturas por nós preservam endereço.

Requisito de estabilidade frequentemente domina escolha no kernel.

Outra estratégia é handle indireto: objeto pode mover internamente enquanto entrada estável de tabela continua visível.

## Ownership e lifetime

Toda estrutura precisa definir ownership dos elementos.

Perguntas:

- inserir transfere ownership?
- remover devolve ownership?
- várias estruturas podem referenciar o mesmo objeto?
- existe reference count?
- leitor pode manter ponteiro durante remoção?
- reclaim é imediato ou diferido?

Em concorrência, lifetime costuma ser mais difícil que lookup.

## Concorrência

Lock grosseiro envolvendo toda a estrutura é mais simples. Locks finos melhoram paralelismo, mas aumentam risco de deadlock. Lock-free elimina bloqueio pelo owner, porém exige atomics e reclaim complexo.

RCU, hazard pointers e epochs resolvem cenários específicos de leitura/reclaim, mas aumentam a carga de prova.

Um S.O pequeno não deve adotar tais técnicas apenas por sofisticação.

## Matriz de seleção

| Requisito | Estrutura comum |
|---|---|
| tabela pequena limitada | array fixo |
| FIFO O(1) sem allocation | ring |
| um bit por recurso | bitmap |
| lookup ordenado dinâmico | árvore balanceada |
| lookup exato esperado rápido | hash |
| item de maior prioridade | heap |
| objetos temporários agrupados | arena |
| objetos fixos reutilizáveis | slab/free list |
| índice ordenado em blocos | B-tree/B+ tree |
| busca por prefixo | trie/radix |

Não é tabela normativa. Concorrência, locality e falha podem inverter a escolha.

## Princípio de sistemas

### Uma fila limitada como prova de invariante

Considere uma FIFO didática com capacidade oito, índice de leitura h, índice de escrita t e contagem c. Exigem-se 0 ≤ c ≤ 8, índices entre zero e sete e t = (h + c) mod 8. Fila vazia e cheia podem ter h e t iguais; a contagem as distingue. Inserir primeiro rejeita c = 8, escreve em t, avança t módulo oito e incrementa c. Remover primeiro rejeita c = 0, lê em h, avança h e decrementa c. Substituir cada atualização na equação demonstra a preservação do invariante.

Essa prova sequencial não torna a fila concorrente. Se dois produtores lerem o mesmo t antes de qualquer atualização, poderão sobrescrever uma posição e corromper a contagem. Um lock pode serializar a transição completa; transformar cada campo isoladamente em atômico não produz automaticamente uma fila correta para múltiplos produtores. Publicar carga e índice também exige um contrato de ordenação para os leitores.

O tempo de vida acrescenta outra obrigação. Um ponteiro enfileirado não mantém sozinho sua alocação viva. A fila pode possuir o objeto até a remoção, manter uma referência ou exigir que o chamador o preserve. A API deve escolher. Da mesma forma, devolver um nó livre duas vezes pode inserir o mesmo objeto repetidamente na estrutura de alocação, mesmo com todos os ponteiros dentro dos limites. Validade estrutural, concorrência e propriedade precisam de argumentos separados.

A melhor estrutura é a que torna simples preservar os invariantes importantes sob as restrições reais.

Um array limitado e simples pode ser superior a uma estrutura dinâmica assintoticamente melhor quando:

- cabe na escala conhecida;
- evita alocação;
- mantém endereços;
- reduz locks;
- melhora localidade;
- torna falha explícita.

O próximo capítulo mapeia esses conceitos para as estruturas e algoritmos existentes na branch <code>main</code> do ChrisOS.
