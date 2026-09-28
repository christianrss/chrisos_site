---
id: proof-invariants-induction
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chriso.h
  - chrisvm/cpu/emulator/flags.c
  - kernel/gfx/graphics.c
symbols:
  - parse_u64
  - emit_u8
  - add_sym
  - patch_fixups
  - chris_flags_bin
  - gfx_mark_dirty
depends_on:
  - discrete-math-sets-relations-functions
related:
  - algorithmic-complexity
  - recursion-recurrences-amortization
  - data-structures
  - systems-algorithms
---

# Provas, invariantes e indução para sistemas

<div class="abstract">
Código de sistemas só é correto quando as propriedades exigidas permanecem verdadeiras em todas as transições permitidas. Técnicas de prova tornam esses requisitos explícitos. Prova direta deriva um resultado a partir de definições, contradição elimina estados impossíveis, indução raciocina sobre objetos construídos iterativa ou recursivamente e invariantes caracterizam propriedades preservadas por loops, estruturas de dados e máquinas de estado. Este capítulo desenvolve obrigações de prova em formato útil para sistemas operacionais, compiladores e emuladores e as aplica a código concreto do ChrisOS: parsing numérico limitado, tabelas de símbolos de capacidade fixa, patching de relocações, aritmética finite-width e rastreamento de dirty rectangles. O objetivo não é declarar o ChrisOS formalmente verificado, e sim mostrar como afirmações de implementação podem ser reduzidas a hipóteses precisas, propriedades preservadas e verificações executáveis.
</div>

## Pré-requisitos e escopo

O capítulo anterior define conjuntos, relações e funções. Esses conceitos fornecem a linguagem para declarar:

- conjunto de estados válidos;
- relação de transição entre estados;
- predicado que deve permanecer verdadeiro;
- função que transforma entrada em saída.

Uma prova responde se uma propriedade declarada decorre das hipóteses declaradas.

O padrão básico é:

~~~text
precondição
   ↓
operação ou transição
   ↓
pós-condição
~~~

Um invariante reforça esse padrão ao exigir que uma propriedade permaneça verdadeira também em estados intermediários, não apenas na entrada e saída.

## Proposições

Uma proposição é uma afirmação verdadeira ou falsa sob interpretação definida.

Exemplos:

~~~text
0 <= i < n
g_nloc <= ASM_LOCAL_MAX
result <= mask
todo dirty rectangle armazenado está dentro do framebuffer
~~~

Uma proposição deve ser precisa o suficiente para ser avaliada.

“Índice é seguro” não é preciso enquanto a faixa válida e a operação não forem especificadas.

## Implicação

Muitas obrigações de prova têm a forma:

~~~text
P ⇒ Q
~~~

em que P é uma precondição e Q uma consequência.

Por exemplo:

~~~text
0 <= i < n
⇒
array[i] referencia elemento dentro de array com n posições
~~~

A implicação é tão forte quanto o modelo assumido. Ela não prova que o pointer do array é válido, que outro thread não pode liberar o objeto ou que n corresponde ao tamanho real da alocação.

Provas exigem hipóteses completas.

## Condições necessárias e suficientes

P é suficiente para Q quando P implica Q.

P é necessária para Q quando Q implica P.

Confundir as duas direções é erro frequente de engenharia.

Um bounds check pode ser suficiente para um acesso específico e ainda não ser suficiente para provar lifetime do objeto.

Da mesma forma, pointer não nulo pode ser condição necessária para dereference comum em C, mas não suficiente para demonstrar que aponta para objeto vivo.

## Prova direta

Uma prova direta parte das hipóteses e deriva o resultado.

Considere:

~~~text
0 <= x < 2^n
0 <= y < 2^n
r = (x + y) mod 2^n
~~~

pela definição de módulo:

~~~text
0 <= r < 2^n
~~~

Logo r cabe em n bits unsigned.

Esse é o tipo de argumento por trás do mascaramento de largura na aritmética finite-width.

## Prova por casos

Quando o comportamento se divide por condição finita, cada caso deve ser provado separadamente.

Para valor signed em complemento de dois, a interpretação possui dois casos:

~~~text
U < 2^(n-1)
U >= 2^(n-1)
~~~

Uma prova completa cobre ambos.

Switch statements, dispatch de enums, seleção de níveis de page table e unions erro/resultado frequentemente pedem prova por casos.

Omitir um caso significa deixar parte do domínio sem prova.

## Contradição

Prova por contradição assume a negação do resultado desejado e deriva impossibilidade.

Para unicidade, suponha que duas chaves válidas distintas ocupem o mesmo slot sob um mapeamento que deveria ser injetivo.

Se a definição do mapeamento implica que saídas iguais exigem entradas iguais, a hipótese de entradas distintas contradiz a definição.

Contradição é particularmente útil para unicidade, impossibilidade e argumentos sobre ciclos.

## Contrapositiva

A implicação:

~~~text
P ⇒ Q
~~~

é logicamente equivalente a:

~~~text
not Q ⇒ not P
~~~

Às vezes a contrapositiva é mais simples.

Para estabelecer que toda referência de objeto aceita pertence à tabela de símbolos ativa, um validator pode rejeitar toda referência cujo índice esteja fora da faixa ativa.

O código então demonstra operacionalmente a contrapositiva da propriedade de aceitação.

## Indução matemática

Indução prova propriedade P(n) sobre uma construção semelhante aos naturais.

Duas obrigações são necessárias.

Caso base:

~~~text
P(0)
~~~

Passo indutivo:

~~~text
P(k) ⇒ P(k+1)
~~~

Então P(n) vale para todo n no domínio da indução.

Isso não é raciocínio circular. O passo demonstra preservação a partir de um k arbitrário e o caso base estabelece o primeiro caso alcançável.

## Indução sobre sequências

Considere algoritmo que processa uma sequência elemento por elemento.

Para provar uma propriedade após todos os elementos:

1. prove-a antes de qualquer elemento;
2. suponha que vale após k elementos;
3. prove que processar o elemento k preserva a propriedade.

Esse formato aparece diretamente em parser loops, checksums, cópia de dados, scans de tabelas de símbolos e atualizações de estado.

Loop invariant é indução expressa operacionalmente.

## Indução forte

Indução forte assume:

~~~text
P(0), P(1), ..., P(k)
~~~

para provar:

~~~text
P(k+1)
~~~

Ela é útil quando um passo depende de mais de um tamanho anterior.

Estruturas recursivas e recurrence relations frequentemente usam essa forma.

Sua força lógica sobre naturais é equivalente à indução comum; apenas a hipótese é organizada de forma diferente.

## Indução estrutural

Indução estrutural demonstra propriedades de objetos definidos recursivamente.

Para uma expression tree:

- prove a propriedade nas folhas;
- suponha que vale nas subárvores filhas;
- demonstre-a para o node pai.

ASTs, page-table trees, directory trees e type expressions podem ser tratados assim quando sua implementação realmente segue estrutura recursiva.

A forma da prova deve corresponder à definição do dado, e não ser imposta por analogia.

## Invariantes de loop

Um loop invariant I é um predicado esperado como verdadeiro:

- antes da primeira iteração;
- após cada iteração concluída;
- na terminação.

Uma prova padrão tem três partes.

Inicialização:

~~~text
precondição ⇒ I
~~~

Preservação:

~~~text
I e loop_guard e loop_body ⇒ I'
~~~

Uso na terminação:

~~~text
I e not loop_guard ⇒ pós-condição
~~~

O invariante isoladamente não prova terminação. Pode ser necessário um argumento separado de progresso.

## Terminação e variantes

Uma variant é uma quantidade que progride monotonicamente em direção a um limite bem fundado.

Para loop sobre i de 0 até n:

~~~text
n - i
~~~

diminui a cada iteração e não pode ficar abaixo de zero.

Isso estabelece terminação se toda iteração incrementa i e se a aritmética não pode fazer wrap de forma incompatível com o modelo.

Argumentos de terminação importam no kernel: um invariante correto combinado a loop infinito ainda pode travar o sistema.

## parse_u64: invariante de prefixo

ChrisASM parse_u64 lê um token um dígito por vez.

Um invariante útil é:

~~~text
v é o valor numérico do prefixo válido já processado
e
0 <= v <= UINT64_MAX
~~~

Inicialização:

antes de processar dígitos:

~~~text
v = 0
~~~

que é o valor do prefixo vazio.

Preservação:

para próximo dígito d em base b, o parser verifica primeiro:

~~~text
v <= (UINT64_MAX - d) / b
~~~

somente depois calcula:

~~~text
v' = v·b + d
~~~

Logo v' permanece representável em uint64_t e corresponde ao prefixo anterior estendido por d.

Ao terminar todos os dígitos, v representa o token completo.

Essa é uma obrigação de prova real refletida diretamente pelas verificações do source.

## Verificação de overflow antes da multiplicação

Um padrão inseguro seria:

~~~text
v = v·b + d
if houve overflow:
    falhar
~~~

Se a operação já fez wrap, informação necessária para detectar o overflow matemático pode ter sido perdida.

A precondição do source rearranja:

~~~text
v·b + d <= M
~~~

para:

~~~text
v <= (M - d) / b
~~~

considerando valores não negativos.

Isso transforma uma operação potencialmente excedente em comparação segura antes da mudança de estado.

## emit_u8: invariante de capacidade

ChrisASM mantém buffers estáticos de seção com capacidade ASM_SEC_MAX.

emit_u8 verifica:

~~~text
g_cur identifica uma seção com byte buffer
e
g_len[g_cur] < ASM_SEC_MAX
~~~

antes de escrever e incrementar o comprimento.

Se a condição falha, define g_overflow e retorna sem escrever.

Um invariante útil é:

~~~text
0 <= g_len[s] <= ASM_SEC_MAX
~~~

para cada seção s suportada pelos buffers, sob as transições esperadas.

Quando g_len[s] = ASM_SEC_MAX, nenhum byte adicional é escrito.

Isso sustenta um argumento local contra out-of-bounds no emitter, supondo que o próprio estado de comprimento não tenha sido corrompido por outro caminho.

## Tabelas de símbolos de capacidade fixa

ChrisoImage aloca:

~~~text
sym[CHRISO_SYM_MAX]
~~~

e mantém nsym.

add_sym testa:

~~~text
img->nsym >= CHRISO_SYM_MAX
~~~

antes de append.

Um invariante central é:

~~~text
0 <= nsym <= CHRISO_SYM_MAX
~~~

Para append com nsym < max:

~~~text
new_nsym = old_nsym + 1
~~~

que ainda permanece <= max.

Quando a tabela está cheia, a inserção falha.

A prova de capacidade não demonstra sozinha unicidade dos nomes. Isso depende separadamente de find_sym e das regras de atualização.

## Unicidade de símbolos como invariante relacional

add_sym procura primeiro nome já existente.

Se encontra, reutiliza ou atualiza a entrada sob regras de binding, em vez de simplesmente adicionar uma definição nova.

Um possível invariante é:

~~~text
entre entradas ativas, duas definições independentes não representam a mesma identidade de símbolo aceita
~~~

Provar essa propriedade por completo exigiria analisar truncamento de nomes, regras de comparação, transições undefined→defined e todo writer de ChrisoImage.

Este capítulo não declara essa prova concluída.

A regra importante é: o invariante declarado não deve ser mais forte que a evidência revisada.

## patch_fixups: obrigações de segurança de memória

patch_fixups processa cada fixup local registrado.

Antes de escrever quatro bytes, exige:

~~~text
id existe
label de destino está definido
seção do destino coincide com a do fixup
0 <= sec < 3
at + 4 <= g_len[sec]
~~~

A última condição demonstra que as posições:

~~~text
at
at+1
at+2
at+3
~~~

estão todas abaixo de g_len[sec].

Isso é uma prova local de segurança de memória para o patch de quatro bytes, supondo que g_len[sec] não exceda a capacidade real do buffer.

A mesma função calcula o displacement:

~~~text
target_offset - (patch_offset + 4)
~~~

A faixa e o cast para int32_t são obrigações semânticas separadas da segurança do write.

Uma prova não estabelece automaticamente a outra.

## chris_flags_bin: invariante de largura

Para os operand sizes esperados, chris_flags_bin obtém uma mask e calcula:

~~~text
aa = a & mask
bb = b & mask
~~~

e armazena:

~~~text
result = r & mask
~~~

Um invariante direto é:

~~~text
result não possui bit ligado fora da largura selecionada
~~~

Para máscara M:

~~~text
result & ~M = 0
~~~

Isso permanece verdadeiro independentemente de a operação matemática ter produzido bits superiores.

Carry e overflow preservam informação sobre efeitos não representados no resultado armazenado.

## Invariante de representação versus correção semântica

O invariante do resultado mascarado prova apenas uma propriedade de representação.

Ele não prova:

- semântica correta de carry em ADD;
- polaridade correta de borrow em SUB;
- validade de todo operand size;
- overflow signed correto;
- que o decoder selecionou a operação correta.

Verificação robusta decompõe correção em obrigações independentes em vez de interpretar uma propriedade verdadeira como correção global.

## gfx_mark_dirty: invariante de retângulos

A camada gráfica armazena até GFX_DIRTY_MAX dirty rectangles.

gfx_mark_dirty recorta coordenadas contra os limites do framebuffer, rejeita retângulos vazios, combina retângulos que se tocam e, quando a capacidade é atingida, reduz o estado a um único retângulo cobrindo a tela inteira.

Um invariante útil para cada retângulo armazenado é:

~~~text
0 <= x0 < x1 <= largura do framebuffer
0 <= y0 < y1 <= altura do framebuffer
~~~

O clipping estabelece essas condições antes da inserção.

A lógica de capacidade mantém:

~~~text
0 <= g_dirty_count <= GFX_DIRTY_MAX
~~~

sob transições normais por gfx_mark_dirty.

## Fallback de tela cheia como preservação de invariante

Quando g_dirty_count já atingiu a capacidade, adicionar outro retângulo violaria o limite do array.

A função substitui o estado por:

~~~text
g_dirty_count = 1
dirty[0] = framebuffer inteiro
~~~

Há perda de precisão, mas preservação da correção da cobertura de repaint.

A propriedade abstrata preservada não é “os dirty rectangles permanecem mínimos”.

É:

~~~text
toda região que precisa ser apresentada está contida na união dos dirty rectangles armazenados
~~~

Trocar vários retângulos pela tela inteira mantém essa propriedade e sacrifica desempenho.

É um trade-off de sistemas expresso como enfraquecimento de precisão com preservação de segurança.

## Safety versus liveness

Propriedades de safety afirmam que algo ruim nunca acontece.

Exemplos:

- nenhum write fora de limites;
- contador nunca excede capacidade;
- índice de símbolo inválido não é aceito.

Propriedades de liveness afirmam que algo desejável eventualmente acontece.

Exemplos:

- job enfileirado eventualmente roda;
- thread bloqueada eventualmente se torna runnable;
- dirty data eventualmente é apresentada.

Provar safety não prova liveness.

Ausência de buffer overflow e ausência de starvation são obrigações diferentes.

## Invariantes locais e globais

Um invariante local vale dentro de uma função ou estrutura.

Uma propriedade global atravessa componentes.

Exemplo local:

~~~text
nsym <= CHRISO_SYM_MAX
~~~

Exemplo de propriedade global potencial:

~~~text
todo sym_index de relocação aponta para símbolo ativo durante linking
~~~

Invariantes globais são mais difíceis porque todo caminho mutável precisa preservá-los.

A documentação deve distinguir fatos localmente checados de afirmações arquiteturais amplas.

## Invariantes de representação

Representation invariant caracteriza estados concretos válidos de uma estrutura.

Exemplos:

~~~text
0 <= count <= capacity
head index está na faixa do ring
relação parent/child de tree é acíclica
nodes da free list não estão simultaneamente alocados
~~~

Operações públicas devem:

1. exigir o invariante na entrada;
2. preservá-lo no sucesso;
3. definir o que permanece verdadeiro na falha.

Failure paths fazem parte da obrigação de prova.

## Atomicidade diante de falha

Uma operação é failure-atomic em relação a certo estado quando falha deixa esse estado inalterado ou em forma recuperável definida.

Nem todo helper do ChrisOS revisado aqui é documentado como failure-atomic.

Uma função pode, por exemplo, marcar overflow antes de o chamador rejeitar posteriormente a assembly inteira.

A garantia relevante pode ser:

~~~text
falha deixa estado explicitamente marcado como inválido e o chamador deve rejeitá-lo
~~~

em vez de rollback completo.

A afirmação de prova deve corresponder ao recovery behavior real.

## Concorrência invalida provas sequenciais implícitas

Uma prova sobre transições sequenciais pode falhar sob interleaving concorrente.

Suponha:

~~~text
count < capacity
~~~

verificado por dois threads que depois incrementam count sem sincronização.

O argumento local de cada thread pode parecer válido enquanto a execução combinada excede o limite ou sobrescreve o mesmo slot.

Correção concorrente precisa incluir operações atômicas, locks ou outro modelo de sincronização nas hipóteses.

Nenhuma prova deve assumir silenciosamente single-thread execution para estado compartilhado.

## Invariantes indutivos em máquinas de estado

Para sistema de transição:

~~~text
S --T--> S'
~~~

I é indutivo quando:

Inicialização:

~~~text
todo estado inicial satisfaz I
~~~

Preservação:

~~~text
I(S) e T(S,S') implicam I(S')
~~~

Então todo estado alcançável satisfaz I.

O método escala de loops a schedulers, protocols, allocators e emuladores.

A dificuldade normalmente está em encontrar um invariante forte o suficiente para implicar a propriedade desejada e fraco o suficiente para ser preservado.

## Fortalecimento de um invariante

Suponha que a pós-condição seja:

~~~text
output contém o prefixo processado da entrada
~~~

Um invariante fraco dizendo apenas:

~~~text
i <= n
~~~

não permite demonstrar a relação de conteúdo.

Um invariante mais forte pode ser:

~~~text
0 <= i <= n
e
output[0:i] = transform(input[0:i])
~~~

A relação adicional carrega a informação necessária para a prova final.

Invariantes são artefatos de projeto, não apenas assertions descobertas depois da implementação.

## Assertions e verificações em runtime

Uma runtime assertion testa um único estado de execução.

Uma prova estabelece propriedade sobre todos os estados cobertos pelas hipóteses.

Assertions continuam úteis porque:

- detectam hipóteses violadas;
- codificam representation invariants;
- reduzem a área da falha;
- funcionam como documentação executável.

Testing amostra execuções; proof raciocina sobre um domínio.

Os métodos são complementares.

## Property-based e exhaustive testing

Para domínios finitos pequenos, exhaustive testing pode avaliar todas as entradas.

Para domínios grandes, property-based tests geram muitos exemplos de uma propriedade geral.

Exemplos:

~~~text
mask(result) == result
decode(encode(x)) == x para x válido
count nunca excede capacity em sequências de operações geradas
~~~

Testes aprovados aumentam evidência, mas não se tornam prova a menos que o domínio testado seja exaustivo e o modelo de execução corresponda à especificação.

## Obrigações de prova em trust boundaries

Fronteiras de kernel e parser merecem obrigações explícitas.

Para entrada não confiável, requisitos típicos incluem:

- aritmética de tamanho não pode exceder a faixa;
- todo índice é validado antes do dereference;
- todo enum decodificado é validado antes de dispatch;
- referências apontam para objetos ativos;
- failure paths não deixam estado privilegiado obsoleto;
- cópias respeitam capacidade de origem e destino.

Security review se torna mais precisa quando cada requisito é uma proposição associada a uma transição.

## Propriedades de desempenho também precisam de limites de prova

Afirmações de complexidade são proposições sobre modelos de custo.

Um loop que percorre n entradas pode justificar O(n) comparações se cada iteração executa trabalho limitado.

Isso não prova custo constante de tempo real por iteração sob caches, page faults ou I/O.

Da mesma forma, merge de dirty rectangles pode reduzir cópias posteriores ao custo de mais trabalho na inserção.

Provas algorítmicas precisam declarar quais operações contam como custo unitário.

Os capítulos de complexidade formalizam esses modelos.

## Precondições, pós-condições e contratos

Uma precondição descreve o que deve ser verdadeiro antes de uma operação ser chamada.

Uma pós-condição descreve o que a operação garante ao retornar para um determinado resultado.

Para uma operação de append limitada:

~~~text
pre:
    0 <= count <= capacity

pós-condição de sucesso:
    old_count < capacity
    new_count = old_count + 1
    elementos antigos são preservados

pós-condição de falha:
    old_count = capacity
    count não excede capacity
~~~

Isso é mais forte do que afirmar que “append verifica capacidade”. O contrato identifica a relação entre o estado de entrada e o de saída.

Retornos de erro fazem parte do contrato e não devem ficar fora da prova.

## Raciocínio no estilo Hoare

Uma notação compacta para raciocínio sequencial é a tripla de Hoare:

~~~text
{P} C {Q}
~~~

em que P é precondição, C é comando e Q é pós-condição.

A tripla afirma que, se C começa em estado que satisfaz P e termina, o estado resultante satisfaz Q.

Isso é partial correctness enquanto a terminação não for demonstrada separadamente.

Para mascaramento de largura:

~~~text
{true}
r = x & M
{r & ~M = 0}
~~~

a pós-condição decorre da álgebra bitwise.

Para operações de memória, a precondição também precisa descrever armazenamento válido. Correção aritmética sozinha não justifica dereference.

## Correção parcial e total

Partial correctness significa:

~~~text
se a operação termina,
o resultado satisfaz a pós-condição
~~~

Total correctness também demonstra terminação.

Um parser loop pode ser parcialmente correto e ainda ser defeituoso se determinada entrada fizer o cursor deixar de avançar.

Da mesma forma, loop que sempre termina pode retornar resultado inválido.

As obrigações devem ser revisadas separadamente.

Para loops sobre token finito, total correctness normalmente exige:

- limite no tamanho do token;
- cursor que avança em toda iteração de sucesso;
- ausência de branch que retorne ao mesmo estado sem progresso.

## Frame conditions

Uma prova deve declarar não apenas o que muda, mas também o que precisa permanecer inalterado.

Frame condition descreve estado fora do conjunto de modificações da operação.

Para função que altera um único slot:

~~~text
slot i pode mudar
todos os slots j != i permanecem inalterados
~~~

Frame reasoning é central em kernel code porque uma função pode produzir resultado local correto e ainda corromper estado não relacionado.

O helper write_status em flags.c ilustra a ideia: ele limpa e recalcula bits específicos de status enquanto preserva outros bits de flags recebidos e força o bit 1. Uma prova completa incluiria obrigações sobre bits modificados e preservados.

## Aliasing e hipóteses de ownership

Frame conditions tornam-se mais difíceis quando duas expressões podem apontar para o mesmo armazenamento.

Se pointers p e q podem alias, não é válido provar que write por p deixa o objeto de q intacto sem conhecer essa relação.

Modelos de ownership reduzem a incerteza ao definir qual componente pode modificar determinado armazenamento.

Uma prova de função com output pointer deve declarar se ele pode sobrepor input storage ou global state.

O chris_flags_bin atual recebe operandos escalares por valor e um result pointer opcional. A prova aritmética local não demonstra segurança para result pointer arbitrariamente inválido; validade do pointer é precondição do caller.

## Invariantes abstratos e concretos

Um invariante abstrato descreve propriedade semântica.

Um invariante concreto descreve como a representação implementa essa propriedade.

Para uma tabela de símbolos:

Abstrato:

~~~text
símbolos ativos formam mapeamento finito limitado
~~~

Concreto:

~~~text
0 <= nsym <= CHRISO_SYM_MAX
entradas ativas ocupam sym[0:nsym]
~~~

Um argumento de refinement conecta estado concreto ao modelo abstrato.

Essa separação é importante porque a implementação pode mudar de array fixo para tabela dinâmica sem que o contrato semântico tenha de mudar na mesma proporção.

A documentação não deve confundir uma representação com o único significado possível do subsistema.

## Indução sobre arrays limitados

Muitos loops de sistemas estabelecem propriedades sobre prefixos de arrays.

Considere:

~~~text
for i = 0 .. n-1:
    output[i] = transform(input[i])
~~~

Um invariante útil é:

~~~text
0 <= i <= n
e
para todo j < i:
    output[j] = transform(input[j])
~~~

A inicialização vale em i = 0 porque o prefixo quantificado está vazio.

A preservação decorre do write em output[i] segundo a transformação seguido do incremento de i.

Na terminação i = n, a propriedade cobre o array inteiro.

Esse padrão se aplica a byte emission, inicialização de tabelas, loops de cópia e construção de descriptors.

## Propriedades de fechamento

Um conjunto S é fechado sob operação f quando aplicar f a membros válidos produz outro membro de S.

Fechamento expressa preservação de invariante de forma compacta.

Para o domínio de resultados mascarados de n bits:

~~~text
S = {x | x & ~M = 0}
~~~

a operação:

~~~text
f(x) = x & M
~~~

sempre produz elemento de S.

Free lists, endereços normalizados e índices limitados frequentemente possuem requisitos semelhantes: operações públicas devem mapear estados válidos de volta ao conjunto de estados válidos.

Se uma operação pode sair de S, ou o contrato admite um estado excepcional ou o invariante não é de fato preservado.

## Propriedades monotônicas

Alguns estados evoluem monotonicamente.

Exemplos:

- cursor de parser que apenas avança;
- high-water mark que nunca diminui;
- conjunto de fatos descobertos que apenas cresce;
- generation number que aumenta a cada substituição.

Monotonicidade simplifica provas porque estados antigos não reaparecem sem reset explícito.

Também pode sustentar terminação: índice limitado e monotonicamente crescente só pode avançar um número finito de vezes.

O escopo precisa ser explícito. Um contador que faz wrap não é globalmente monotônico sob a ordem inteira comum.

## Contraexemplos

Uma afirmação universal é refutada por um único contraexemplo válido.

Para o candidato:

~~~text
todo retângulo armazenado é mínimo
~~~

o fallback de tela cheia em gfx_mark_dirty é um contraexemplo imediato: ele armazena propositalmente área maior que a união exata das regiões sujas.

A afirmação mais forte é falsa.

O invariante correto é cobertura, e não minimalidade.

Buscar contraexemplos é forma prática de refinar documentação antes de tentar uma prova.

Valores de fronteira são especialmente úteis:

- zero;
- capacidade máxima;
- um além da capacidade;
- coleção vazia;
- elemento único;
- regiões que se sobrepõem ou não;
- mínimos e máximos signed.

## Descoberta de invariantes a partir do código

Uma revisão disciplinada pode derivar invariantes candidatos sem inventá-los.

1. Identificar variáveis de estado e seus limites de armazenamento.
2. Listar todos os writers.
3. Registrar checks executados antes de cada mutação.
4. Identificar relações assumidas pelos readers.
5. Inspecionar failure paths para estado parcialmente atualizado.
6. Testar transições de fronteira.
7. Declarar a propriedade mais fraca sustentada por todos os writers observados.
8. Adicionar afirmações mais fortes apenas quando todos os caminhos de mutação as justificam.

Esse processo separa evidência de expectativa.

Um comentário dizendo “tabela limitada” é apenas uma pista. O invariante vem do tamanho do array, checks do count e todos os writes sobre o count.

## Assertions como sentinelas de invariantes

Assertions podem ser colocadas em fronteiras de abstração para detectar violações cedo.

Formas úteis incluem:

~~~text
count <= capacity
index < active_count
limites do retângulo estão ordenados
alinhamento de pointer satisfaz potência de dois exigida
state enum pertence ao conjunto legal
~~~

Em kernels de produção algumas assertions podem virar panic paths, retornos de erro ou checks apenas de debug.

Remover uma assertion em runtime não remove o invariante subjacente. Remove apenas um mecanismo de detecção.

O invariante continua precisando ser preservado pela construção do código.

## Granularidade de prova

Provas grandes ficam manejáveis quando decompostas.

Para patch_fixups, obrigações separadas incluem:

- iteração de fixup permanece dentro de g_nfix;
- lookup de label tem sucesso;
- identidade da seção coincide;
- faixa de patch contém quatro bytes;
- cálculo de displacement tem a semântica esperada;
- conversão para int32_t é válida para o caso suportado;
- quatro bytes emitidos representam o encoding escolhido.

Uma frase como “fixups são seguros” esconde todas essas obrigações.

A documentação deve nomear cada uma e distinguir o que é checado diretamente, o que é derivado e o que permanece limitação.


## Evidência de validação

O checker determinístico associado a este capítulo valida obrigações representativas:

- indução sobre prefix sums;
- preservação do loop invariant no parsing de Horner;
- desigualdade de overflow uint64 antes da multiplicação;
- preservação de append com capacidade finita;
- limites para patch de quatro bytes;
- fechamento por width mask;
- clipping de dirty rectangles e limites do contador;
- cobertura do fallback para framebuffer inteiro.

Também verifica âncoras atuais de source para parse_u64, emit_u8, add_sym, patch_fixups, chris_flags_bin e gfx_mark_dirty.

O checker demonstra as propriedades documentadas nos modelos escolhidos. Ele não constitui prova formal do codebase inteiro do ChrisOS.

## Limitações atuais

Este capítulo não fornece:

- provas machine-checked;
- Hoare logic em formalismo completo;
- separation logic;
- temporal logic;
- model checking;
- verificação baseada em SMT;
- lógicas de concorrência;
- compilação verificada;
- proof-carrying code.

Esses métodos podem ser construídos sobre a mesma disciplina de estado explícito, hipóteses e predicados preservados.

## Fronteira do roadmap

A disciplina de prova estabelecida aqui sustenta capítulos posteriores sobre:

- complexidade;
- recurrence relations;
- estruturas de dados;
- allocators;
- schedulers;
- filesystems;
- parsers;
- virtual machines;
- algoritmos concorrentes.

Capítulos posteriores devem declarar diretamente invariantes importantes de representação e transição, em vez de apenas narrar comportamento.

## Proveniência da revisão

As afirmações ligadas à implementação foram conciliadas contra ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

Fontes revisadas:

- compiler/chrisasm/chrisasm.c;
- compiler/chrisld/chriso.h;
- chrisvm/cpu/emulator/flags.c;
- kernel/gfx/graphics.c.

Símbolos revisados:

- parse_u64;
- emit_u8;
- add_sym;
- patch_fixups;
- chris_flags_bin;
- gfx_mark_dirty.

Os exemplos estabelecem obrigações locais apoiadas pelo source inspecionado. Eles não afirmam formal verification global, correção completa sob concorrência ou prova de todos os callers.
