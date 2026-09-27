---
id: algorithmic-complexity
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- kernel/gfx/virtq.c
- kernel/gfx/virtq.h
symbols:
- virtq_alloc
- virtq_publish
- virtq_take
- virtq_reclaim
- virtq_init
depends_on:
  - data-representation-layout
  - proof-invariants-induction
related:
- data-structures
- systems-algorithms
---

# Análise de algoritmos e modelos de custo de sistemas

<div class="abstract">
Análise de algoritmos fornece linguagem para raciocinar sobre crescimento, limites de recursos e trade-offs, mas software de sistemas exige mais que notação Big-O. Localidade de cache, alocação, sincronização, capacidade limitada, contexto de interrupção, pior latência e interação com hardware podem dominar uma implementação cuja complexidade assintótica parece favorável. Este capítulo desenvolve análise de complexidade especificamente para kernels, compiladores, drivers, gráficos e emuladores.
</div>

## Definição de algoritmo

Algoritmo é um procedimento finito que transforma estado de entrada em estado de saída preservando invariantes definidos.

Para documentação de sistemas, descrever um algoritmo exige no mínimo:

- representação da entrada;
- pré-condições;
- sequência de operações;
- invariantes;
- condição de término;
- pós-condição;
- comportamento de falha;
- consumo de recursos.

Nome de função não é descrição algorítmica. “Alocar uma página” não informa como free state é representado, qual busca é feita, qual sincronização protege o estado nem o que ocorre sem páginas livres.

## Tamanho da entrada

Toda complexidade precisa declarar sua variável de tamanho.

Exemplos:

- n = elementos de um array;
- p = páginas físicas;
- h = profundidade de page table;
- v = vértices;
- t = triângulos;
- b = blocos de um arquivo;
- s = comprimento do source;
- q = jobs na fila.

Dizer apenas que algo é “linear” é incompleto.

## Big-O

Big-O expressa classe superior de crescimento. f(n) é O(g(n)) quando não cresce mais rápido que um múltiplo constante de g para n suficientemente grande.

| Classe | Exemplo |
|---|---|
| O(1) | acesso indexado |
| O(log n) | busca em árvore balanceada |
| O(n) | varredura linear |
| O(n log n) | sort por comparação |
| O(n²) | comparação de todos os pares |
| O(2^n) | busca exaustiva de subconjuntos |

Big-O ignora fatores constantes e termos inferiores. Isso é útil para escalabilidade, porém insuficiente para desempenho de baixo nível.

## Omega e Theta

Big-O fornece bound superior. Omega descreve bound inferior. Theta indica crescimento assintoticamente justo.

Se um algoritmo sempre percorre todos os elementos, seu custo é Theta(n), não apenas O(n).

Precisão importa ao comparar designs. Uma rotina O(n) que normalmente encontra resultado no primeiro item apresenta perfil diferente de uma rotina que obrigatoriamente examina todos.

## Pior caso, média e valor esperado

Software de sistemas frequentemente privilegia pior caso.

Hash table pode oferecer O(1) esperado e O(n) no pior caso. Isso pode ser aceitável em ferramenta de desktop e perigoso em caminho de hard real-time.

A documentação deve separar:

- pior caso;
- melhor caso;
- média sob distribuição declarada;
- valor esperado de estrutura probabilística;
- custo amortizado de uma sequência.

## Análise amortizada

Append em array dinâmico ocasionalmente custa O(n) quando a capacidade cresce; se a capacidade dobra, uma longa sequência possui custo amortizado O(1) por append.

Amortizado não significa probabilístico. O custo caro é distribuído contabilmente pela sequência.

No kernel ainda é necessário perguntar onde a operação O(n) individual pode ocorrer. Resize raro dentro de seção crítica com interrupções desabilitadas pode ser inaceitável.

## Complexidade espacial

Memória é recurso de primeira classe.

Algoritmos reduzem tempo armazenando metadados, tabelas precomputadas ou caches. PMM, filesystem, JIT e gráficos trocam memória por velocidade.

Análise espacial deve contar:

- tamanho persistente;
- scratch temporário;
- profundidade de stack/recursão;
- fragmentação;
- padding/alinhamento;
- duplicação e cache.

Em alguns caminhos do kernel, alocação pode ser proibida.

## Localidade

Dois algoritmos O(n) podem ter desempenho muito diferente.

Varredura sequencial de array contíguo aproveita localidade espacial e prefetch. Seguir ponteiros por nós espalhados pode causar misses de cache e TLB.

Modelo de custo de sistemas deve considerar:

    operações algorítmicas
    + misses da hierarquia de memória
    + sincronização
    + latência de dispositivo

A classe assintótica continua útil, mas o processador executa acessos reais à memória.

## Previsibilidade de branch

Controle de fluxo também possui custo. Branch previsível pode ser barato; branches dependentes de dados e imprevisíveis podem descartar trabalho especulativo.

Transformações branchless ajudam alguns loops, mas podem executar mais instruções.

Otimização deve ser medida no workload real.

## Custo de alocação

Uma estrutura que cria um nó por operação depende do alocador.

Perguntas relevantes:

- estratégia de alocação e custo assintótico;
- possibilidade de bloqueio;
- escopo e contenção do lock;
- condições explícitas de falha;
- comportamento de fragmentação;
- exigência de memória física contígua.

Estrutura de dados de livro-texto não pode ser avaliada isoladamente do allocator em kernel.

## Complexidade de locks

Uma operação O(1) pode esperar atrás de spinlock contendido por tempo muito maior que seu trabalho local.

Análise concorrente acrescenta:

- ordem de aquisição;
- domínio de contenção;
- tamanho da seção crítica;
- propriedade de progresso;
- estado de interrupção/preempção;
- cache-line bouncing.

Big-O mede trabalho; sincronização mede coordenação.

## Propriedades de progresso

Algoritmos concorrentes podem ser:

- blocking: proprietário parado pode atrasar outros;
- lock-free: há progresso global;
- wait-free: cada operação termina em número limitado de seus próprios passos;
- obstruction-free: há progresso sem contenção.

Uma fila protegida por spinlock é blocking nessa classificação formal mesmo que a seção crítica seja curta.

Categorias mais fortes não são automaticamente melhores; aumentam complexidade e custo de reclaim.

## Estruturas limitadas versus dinâmicas

Sistemas operacionais frequentemente usam tabelas e rings de capacidade fixa.

Uma estrutura limitada oferece:

- memória previsível;
- independência de allocator;
- falha simples quando cheia;
- endereços estáveis.

O custo é limite rígido e, às vezes, scans lineares.

Árvores ou hash tables dinâmicas escalam, mas introduzem alocação e teardown mais complexos.

A estrutura correta depende da escala e dos invariantes reais.

## Tempo real e bounds de latência

Em real-time, throughput médio é insuficiente. Importa a latência máxima.

Uma árvore O(log n) pode ser inadequada se aloca ou pega lock imprevisível. Um scan O(n) com n pequeno e rigidamente limitado pode oferecer bound melhor.

Notação assintótica supõe crescimento; sistemas frequentemente limitam n propositalmente.

## Latência de dispositivo

Drivers interagem com hardware cujo tempo não acompanha contagem de instruções da CPU.

I/O de storage pode gastar microssegundos ou milissegundos aguardando dispositivo. Complexidade de CPU ainda importa para gerenciar filas, mas latência fim a fim inclui hardware.

Polling consome CPU durante a espera. Interrupções adicionam overhead de entrada/saída e sincronização, mas liberam CPU.

## Throughput versus latência

Latência mede uma operação. Throughput mede operações por unidade de tempo.

Batching pode aumentar throughput e piorar latência individual.

Command buffers gráficos, filas de block I/O e processamento de rede usam batching. Caminhos interativos podem preferir lotes menores.

A documentação deve indicar qual objetivo está sendo otimizado.

## Tail latency

Percentis 99 ou 99,9 podem ser mais relevantes que média.

Pausas longas surgem de:

- contenção;
- slow path de allocator;
- cache miss;
- page fault;
- retry de dispositivo;
- filas acumuladas;
- garbage collection;
- seções críticas grandes.

Média boa não garante sensação de estabilidade.

## Page-table walk

Um walk x86-64 de quatro níveis possui profundidade arquitetural fixa, portanto é O(1) em relação ao tamanho do address space.

Porém cada nível pode exigir acesso dependente à memória. TLBs existem porque quatro acessos adicionais por load/store seriam caros.

O(1) não significa barato.

## Alocação com bitmap

Bitmap registra um bit por recurso. Testar posição conhecida é O(1). Encontrar posição livre por scan é O(n) no número de unidades.

Cursor ou hint melhora comportamento típico evitando recomeçar em zero, mas não remove pior caso.

A densidade de bits torna a representação compacta e amigável ao cache.

## Fila circular

Ring de capacidade fixa com head, tail e count oferece enqueue/dequeue O(1).

O preço é capacidade limitada. Full/empty precisam de representação inequívoca e produtores/consumidores concorrentes exigem sincronização.

É comum em kernel e dispositivos porque índices avançam sem mover elementos.

## Compiladores

Lexer normalmente percorre source aproximadamente em O(s). Complexidade do parser depende da gramática e estratégia. Lookup de símbolos varia conforme array, hash ou árvore.

Passes de otimização podem percorrer IR repetidamente, multiplicando custo por tamanho e quantidade de passes.

A documentação precisa registrar o algoritmo atual, não apenas a teoria geral de compiladores.

## Gráficos

Rasterização depende de geometria e pixels cobertos.

Um algoritmo que testa cada pixel da tela para cada triângulo aproxima O(T × W × H). Bounding boxes reduzem área. Tile binning associa primeiro triângulos a tiles, permitindo trabalho local e paralelo.

Z-buffer adiciona teste O(1) por fragmento candidato, mas também tráfego de memória.

Desempenho real depende de SIMD, cache e overdraw.

## Emulação

Interpretador simples realiza fetch/decode/execute por instrução guest. Tempo cresce aproximadamente com contagem de instruções multiplicada pelo custo do decoder/executor.

JIT paga compilação inicial para reduzir execução repetida. A vantagem depende de reuso.

É um trade-off clássico entre custo inicial, espaço e steady state.

## Medição

Complexidade prevê escala; benchmark observa uma implementação específica.

Processo adequado:

1. derivar expectativa algorítmica;
2. identificar fatores constantes;
3. medir workloads representativos;
4. perfilar hotspots;
5. alterar representação ou algoritmo quando evidência justificar;
6. revalidar correção.

Benchmark sem modelo pode otimizar ruído. Modelo sem medição pode otimizar o custo errado.

## Regra documental

Capítulos concretos devem registrar tabela semelhante:

| Operação | Estrutura | Tempo | Espaço/efeito | Sincronização |
|---|---|---|---|---|
| lookup exemplo | array | O(n) worst | sem alocação | lock do subsistema |
| enqueue exemplo | ring | O(1) | capacidade limitada | lock da fila |

A tabela não substitui a explicação. Ela torna contratos ocultos de desempenho e concorrência visíveis.

O capítulo seguinte apresenta as estruturas de dados fundamentais sobre as quais esses algoritmos são construídos.

## Modelo de custo de fila derivado do código

Em `kernel/gfx/virtq.c`, `virtq_alloc(q, n, head)` não obtém uma cadeia arbitrária em tempo constante. Percorre n links de software, atribui flags NEXT e retira os descritores da lista livre. O trabalho local é O(n), enquanto a rejeição de n maior que `nfree` ocorre antes do percurso. `virtq_publish` escreve uma entrada do anel e avança um índice, portanto seu trabalho local é O(1). `virtq_take` devolve no máximo uma conclusão por chamada. `virtq_reclaim` percorre a cadeia alocada e custa O(n) para uma cadeia válida de n descritores.

| Operação | Parâmetro de escala | Trabalho local | Inclui espera externa? |
|---|---|---|---|
| Inicializar | Capacidade Q | O(Q) | Não |
| Alocar cadeia | Quantidade n | O(n) | Não |
| Preencher descritor | Layout fixo de 16 bytes | O(1) | Não |
| Publicar cabeça | Uma entrada do anel | O(1) | Não |
| Obter conclusão | Uma entrada used | O(1) | Não |
| Recuperar cadeia válida | Quantidade n | O(n) | Não |

Para uma requisição com n descritores, a soma do gerenciamento é O(n), embora a publicação isolada tenha custo constante. Processamento do dispositivo, tráfego do barramento, interrupção e polling do chamador acrescentam termos separados. Se o chamador consulta até concluir, um atraso ilimitado do dispositivo pode produzir uma quantidade ilimitada de chamadas O(1). Custo constante por consulta não estabelece prazo de conclusão.

Os arrays reservam capacidade para `VQ_MAX = 128`, portanto a implementação distribuída tem limite fixo de armazenamento. Descrever a família como O(Q) continua útil para compreender o efeito de aumentar esse limite. Tratar todo programa limitado como O(1) esconderia a diferença entre tocar um descritor e tocar todos os 128. O modelo parametrizado e o limite concreto devem constar da documentação.

Localidade difere de comportamento de alocação. As funções não alocam heap hospedeiro por conta própria e os bytes dos descritores são contíguos. Entretanto, percorrer links de software e publicar memória compartilhada com dispositivo podem ter custos distintos de cache e sincronização. O código não demonstra vantagem medida de vazão sobre toda alternativa; essa conclusão exigiria carga de trabalho e medição.

Um bitmap alternativo poderia buscar descritores livres e reduzir metadados de links, mas obter uma cadeia ainda exigiria identificar n entradas e estabelecer propriedade. Uma API de submissão em lotes poderia amortizar barreiras de publicação entre várias cabeças, ao custo de outro contrato de latência e sincronização. São alternativas de projeto, não afirmações de que a implementação atual já faz publicação em lotes. A análise de complexidade é mais útil quando declara qual contrato a otimização mudaria.
