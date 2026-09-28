---
id: hash-tables
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - compiler/chrisc/chrisc.c
  - compiler/clvm/clvm_format.c
symbols:
  - Compiler
  - Symbol
  - hash_str
  - ht_zero
  - ht_find_grid
  - ht_ins_grid
  - lookups_reset
  - sym_find_local
  - sym_find
  - sym_add
  - clvm_fnv1a32
depends_on:
  - arrays-lists-stacks-queues
  - algorithmic-complexity
related:
  - data-structures
  - trees-heaps-tries
  - string-parsing-algorithms
  - compiler-pipeline
---

# Hash tables, hashing e lookup limitado de símbolos

<div class="abstract">
Uma hash table mapeia chaves para um array finito de slots por meio de uma hash function e de uma política de resolução de colisões. A expectativa de lookup em tempo constante só é útil quando representação, load factor, colisões, deleção e hipóteses adversariais são explícitas. Este capítulo desenvolve hash functions, open addressing, chaining, load factor, resizing, deletion, complexidade, localidade, concorrência e segurança. Em seguida reconcilia a teoria com o compilador ChrisC atual. ChrisC usa arrays de lookup fixed-size com open addressing para identificadores globais, hashing de strings no estilo FNV-1a, linear probing, zero como sentinel de slot vazio e valores armazenados como índice do identificador mais um. As capacidades são potências de dois e foram dimensionadas em dobro em relação às cardinalidades máximas dos arrays correspondentes. Variáveis locais continuam sendo procuradas por reverse linear scan porque lexical visibility e shadowing possuem semântica diferente. O formato de imagem CLVM usa FNV-1a separadamente como checksum; esse checksum não é uma hash table e não é mecanismo criptográfico de integridade.
</div>

## Pré-requisitos e escopo

Hash table combina arrays, funções e análise de complexidade.

A operação lógica é um mapa:

~~~text
chave -> valor
~~~

A representação física costuma ser:

~~~text
hash(chave)
   ↓
slot/bucket
   ↓
política de colisão
   ↓
comparação da chave candidata
   ↓
valor
~~~

O hash não estabelece igualdade. Ele apenas reduz a região na qual a chave pode estar. A implementação ainda precisa comparar a chave original.

É importante separar quatro conceitos:

- **hash function:** converte bytes da chave em inteiro de largura fixa;
- **hash table:** estrutura que usa hash para localizar pares chave/valor;
- **checksum:** valor compacto para detectar alteração acidental;
- **cryptographic hash:** construção projetada para resistir a colisão, preimage e propriedades relacionadas sob modelo de segurança definido.

ChrisOS usa hoje a família FNV-1a tanto em lookup quanto em checksum CLVM, mas os contratos são diferentes.

## Hash functions

Uma função determinística mapeia uma chave para um domínio inteiro:

~~~text
h: K -> {0, 1, ..., 2^w - 1}
~~~

Para tabela de m slots, o resultado é reduzido a índice.

Forma comum:

~~~text
index = h(key) mod m
~~~

Quando m é potência de dois:

~~~text
index = h(key) & (m - 1)
~~~

desde que m seja exatamente potência de dois.

Uma boa hash não criptográfica para tabela deve ser:

- determinística;
- barata;
- sensível a todos os bytes;
- razoavelmente distribuída para as chaves reais;
- compatível com a redução usada.

Distribuição uniforme é modelo analítico, não garantia automática.

## FNV-1a

hash_str do ChrisC parte de:

~~~text
2166136261
~~~

Para cada byte b executa:

~~~text
h = h XOR b
h = h * 16777619
~~~

com wraparound unsigned de 32 bits.

É a recorrência FNV-1a de 32 bits:

~~~text
h0 = offset_basis
h(i+1) = (hi XOR byte[i]) * prime mod 2^32
~~~

FNV-1a é simples e rápida. Não foi projetada para resistência a colisões adversariais.

Strings diferentes podem gerar o mesmo hash de 32 bits. Por isso a tabela compara a chave armazenada após localizar um candidate slot.

## Capacidade e load factor

Com n entradas vivas em m slots:

~~~text
alpha = n / m
~~~

é o load factor.

Em open addressing, alpha afeta diretamente o comprimento de probing.

Quando alpha se aproxima de 1, slots vazios ficam raros e lookup malsucedido fica caro.

Uma tabela dinâmica normalmente cresce antes de ficar cheia.

ChrisC usa estratégia diferente: capacidades fixas maiores que os máximos das estruturas autoritativas.

Constantes atuais:

| Classe | Máximo de objetos | Capacidade hash |
|---|---:|---:|
| defines do preprocessor | 4096 | 8192 |
| funções | 4096 | 8192 |
| typedefs | 1024 | 2048 |
| structs | 1024 | 2048 |
| symbols | 16384 | 32768 |
| constants/enums | 4096 | 8192 |

Nesses pares, ocupação projetada máxima é de 50% se cada objeto ativo corresponder a uma entrada.

Isso evita rehash dinâmico.

## Resolução de colisões

Colisão ocorre quando chaves distintas começam na mesma posição.

Nenhuma hash finita pode eliminar colisões em domínio de chaves ilimitado.

As duas famílias principais são:

- **separate chaining:** bucket referencia coleção de entradas;
- **open addressing:** todas as entradas residem no próprio array e probing encontra slots alternativos.

ChrisC usa open addressing.

## Linear probing

Para hash inicial h e capacidade m potência de dois, o código examina:

~~~text
slot(i) = (h + i) & (m - 1)
~~~

para:

~~~text
i = 0, 1, ..., m-1
~~~

Isso é linear probing.

Vantagens:

- representação compacta;
- sem allocation por entry;
- boa localidade;
- implementação fixed-size simples.

Custos:

- primary clustering;
- piora quando occupancy cresce;
- deletion exige cuidado;
- pior caso linear na capacidade.

## Codificação dos slots no ChrisC

Os arrays hash armazenam uint16_t.

A convenção atual é:

~~~text
0 = slot vazio
id + 1 = slot ocupado apontando para object id
~~~

Somar um é necessário porque id zero é válido e zero já é sentinel.

Lookup:

1. calcula hash;
2. percorre probe sequence;
3. lê v;
4. se v == 0, retorna not-found;
5. candidate id = v - 1;
6. compara o nome original;
7. retorna id quando igual;
8. continua se houve colisão.

A comparação de string é o que garante correção sob collision.

## Terminação no primeiro slot vazio

ht_find_grid interrompe lookup ao encontrar primeiro zero.

Esse comportamento é correto porque as tabelas revisadas não fazem deleção individual comum que transforme um slot antes ocupado em vazio enquanto preserve entradas posteriores do mesmo cluster.

Em open addressing geral, apagar ingenuamente quebra lookup.

Exemplo:

~~~text
A -> slot 3
B colide -> slot 4
apaga A zerando slot 3
lookup B encontra 0 em slot 3 -> falha incorreta
~~~

Soluções usuais:

- tombstones;
- backward-shift deletion;
- reconstrução do cluster;
- rebuild completo.

Os helpers atuais não possuem estado TOMBSTONE. O lifecycle é baseado em reset/rebuild, não em mutable map arbitrário.

## Inserção

ht_ins_grid percorre a mesma sequência.

Em cada slot:

- se vazio, grava id + 1;
- se a key já for a mesma, retorna sem duplicar;
- caso contrário continua.

Se não houver slot vazio e não houver match, a função encerra depois de cap probes sem inserir.

Por isso a relação entre object maxima e table capacity faz parte do contrato.

Os limites configurados tornam a tabela pelo menos duas vezes maior que a população máxima correspondente.

## Invariante de potência de dois

O índice usa:

~~~text
(h + i) & (cap - 1)
~~~

Esse masking só equivale a modulo quando cap é potência de dois.

Capacidades atuais:

~~~text
8192, 2048, 32768
~~~

e outras relacionadas são potências de dois.

Logo o invariante material é:

~~~text
cap > 0
cap é potência de dois
~~~

Alterar esses valores para números arbitrários sem mudar a redução pode excluir slots e distorcer distribuição.

## Complexidade esperada e pior caso

Com hash razoavelmente distribuída e load factor moderado, lookup é descrito como expected O(1).

O trabalho real é proporcional ao probe length.

Pior caso:

~~~text
O(m)
~~~

para m slots.

Isso ocorre com long cluster ou conjunto altamente colidente.

Portanto dizer “hash lookup é O(1)” sem hipótese é incorreto.

A formulação correta distingue:

- esperado O(1) sob distribuição/load adequados;
- pior caso O(m).

No ChrisC m é fixo e limitado, mas 32768 probes ainda são custo significativo.

## Localidade

Open addressing usa memória contígua.

Linear probing lê:

~~~text
tab[s], tab[s+1], tab[s+2], ...
~~~

o que favorece cache enquanto clusters permanecem curtos.

Ao encontrar candidato, o código acessa o backing array de Symbol, FuncDef etc.

A representação tem duas camadas:

~~~text
hash table: índice compacto de aceleração
           ↓
backing array: registro autoritativo e key
~~~

A hash table não duplica todos os nomes.

## Lookup global e local no ChrisC

ChrisC usa estratégias diferentes.

sym_find_local percorre:

~~~text
i = nsyms - 1 até 0
~~~

e verifica:

- symbol não é global;
- scope é visível;
- nome é igual.

A ordem reversa preserva precedence de declarações mais recentes e shadowing.

sym_find, para globals, usa ht_sym.

Assim:

| Namespace | Estratégia atual |
|---|---|
| local lexical symbols | reverse linear scan |
| global symbols | hash open-addressed |
| functions | hash |
| typedefs | hash |
| structs | hash |
| constants | hash |
| defines | hash |

Isso mostra por que uma estrutura de lookup não deve ser escolhida ignorando semântica.

## Sincronização entre array e índice hash

sym_add insere o Symbol no array autoritativo.

Quando o symbol é global, chama ht_ins_grid.

O invariante é:

~~~text
todo global visível por lookup:
    possui registro em syms[id]
    possui entrada alcançável por nome em ht_sym
~~~

São dois estados relacionados.

Atualizar apenas um cria lookup inconsistente.

O lifecycle append/build/reset do compilador reduz essa complexidade.

## Reset

lookups_reset zera todos os arrays de hash.

Tabela all-zero significa vazia.

O custo é:

~~~text
Theta(soma das capacidades)
~~~

e não O(1).

É aceitável em inicialização/reset, não seria barato por lookup.

Arrays estáticos também eliminam dependência de allocator.

## Custo de memória

Cada slot tem uint16_t.

Memória bruta:

~~~text
2 * (
  HT_DEF_N +
  HT_FUNC_N +
  HT_TD_N +
  HT_ST_N +
  HT_SYM_N +
  HT_CONST_N
)
~~~

Com valores atuais:

~~~text
2 * (8192 + 8192 + 2048 + 2048 + 32768 + 8192)
= 122880 bytes
~~~

Aproximadamente 120 KiB de metadata de lookup, sem contar os backing arrays.

É uma troca deliberada de memória fixa por menor custo de busca global.

## Hash table versus checksum

compiler/clvm/clvm_format.c implementa clvm_fnv1a32.

A mesma recorrência FNV-1a é aplicada ao bytecode.

O writer grava esse valor no header; clvm_parse recalcula e rejeita mismatch.

Isso é checksum:

~~~text
stored == recomputed
~~~

Não existem buckets, keys, values ou probing.

Portanto não é outra hash table.

Também não fornece authentication criptográfica. Quem altera os bytes pode recalcular FNV.

## Separate chaining

Em chaining:

~~~text
table[j] -> entry -> entry -> entry
~~~

Vantagens:

- deletion simples;
- load factor pode superar 1;
- buckets guardam heads.

Custos:

- allocation/nodes;
- pointer chasing;
- pior localidade;
- lifetime e allocator mais complexos.

A implementação ChrisC revisada não usa chaining.

## Tombstones

Open addressing mutável frequentemente distingue:

~~~text
EMPTY
OCCUPIED
DELETED
~~~

DELETED não pode encerrar busca malsucedida porque pode haver entries posteriores no probe cluster.

Muitos tombstones aumentam probe length e podem exigir rehash.

ChrisC não possui essa terceira categoria nesses helpers.

## Resizing e rehash

Hash table dinâmica normalmente cresce quando alpha cruza um threshold.

Passos:

1. alocar array maior;
2. inicializar vazio;
3. reinserir live entries;
4. publicar novo table;
5. liberar antigo com segurança.

Rehash custa O(n).

Com crescimento geométrico, insert pode continuar amortized expected O(1), mas resize individual tem latency spike.

ChrisC evita essa operação usando limites fixos.

## Hash flooding

Hash não criptográfica determinística pode ser atacada com chaves colidentes.

Efeito: expected O(1) se transforma em long scans.

Mitigações possíveis:

- keyed/randomized hashing;
- função mais forte;
- limite de colisões;
- fallback para balanced tree;
- limite de input;
- time budget.

ChrisC atual usa FNV-1a determinística e capacidades fixas.

Isso torna comportamento reprodutível e limitado, mas não prova resistência a collision sets construídos.

## Concorrência

As hash arrays pertencem à instância Compiler.

Os helpers não usam locks nem atomics.

O contrato observado é single-owner mutation durante compilação.

Se a mesma instância fosse compartilhada por múltiplas threads, operações compostas como:

~~~text
adicionar objeto
depois inserir índice hash
~~~

precisariam de sincronização.

Não se deve inferir thread safety desses helpers.

## Falha e saturação

Falhas relevantes:

- backing object array cheio;
- hash table cheia;
- collision cluster patológico;
- backing record e accelerator inconsistentes;
- cap não potência de dois;
- id corrompido;
- truncamento/canonicalization inconsistente de nomes.

ChrisC diagnostica:

~~~text
"symbol table full"
~~~

quando SYM_MAX é atingido.

ht_ins_grid não possui diagnostic próprio para table exhaustion.

O dimensionamento 2:1 reduz essa possibilidade durante crescimento válido.

## Evidência de validação

O checker determinístico deste capítulo valida:

- FNV-1a por modelo independente;
- capacidades power-of-two;
- linear probing;
- colisões com comparação da key original;
- terminação no primeiro empty;
- encoding id+1;
- reset;
- load factor máximo projetado <= 0.5;
- diferença entre local reverse scan e global hash lookup;
- anchors de source para hash_str, ht_find_grid, ht_ins_grid, capacities, sym_find_local, sym_find e clvm_fnv1a32.

O checker valida o modelo e a fronteira de source, não resistência criptográfica ou adversarial completa.

## Limitações atuais

Essa família de lookup do ChrisC não é um generic map.

Não oferece neste layer:

- arbitrary deletion;
- tombstones;
- resize/rehash;
- generic iterator;
- generic value type;
- selectable hash;
- cryptographic collision resistance;
- concurrent mutation contract.

Essas ausências são coerentes com um accelerator interno fixed-capacity.

## Fronteira do roadmap

A sequência curricular é:

~~~text
estruturas lineares
      ↓
hash tables
      ↓
trees, heaps e tries
      ↓
graphs e union-find
      ↓
estruturas especializadas
~~~

Hash tables priorizam exact-key lookup sob hipóteses de distribuição.

O próximo capítulo trata estruturas ordenadas e hierárquicas nas quais custo depende de altura, shape ou prefixos.

## Proveniência da revisão

Afirmações de implementação foram conciliadas contra ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

Source revisado:

- compiler/chrisc/chrisc.c;
- compiler/clvm/clvm_format.c.

Símbolos/estado revisados:

- Compiler;
- Symbol;
- hash_str;
- ht_zero;
- ht_find_grid;
- ht_ins_grid;
- lookups_reset;
- sym_find_local;
- sym_find;
- sym_add;
- clvm_fnv1a32;
- HT_DEF_N;
- HT_FUNC_N;
- HT_TD_N;
- HT_ST_N;
- HT_SYM_N;
- HT_CONST_N.

O source demonstra hash tables open-addressed reais no ChrisC. O uso de FNV-1a no CLVM é checksum, não evidência de outra tabela hash.
