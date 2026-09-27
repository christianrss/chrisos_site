---
id: vectors-complex-numbers-systems
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on: [atom-semiconductor]
related: [electric-charge-field-potential, ac-signals-frequency-impedance, software-3d, matrix-transformations]
---

# Vetores e números complexos para sistemas

<div class="abstract">
Vetores representam grandezas por componentes e direção; números complexos representam dois graus de liberdade reais acoplados por uma álgebra adequada a rotações e ao regime senoidal permanente. Essas ferramentas conectam hardware físico, gráficos, análise de sinais, controle e software numérico. Este capítulo separa objetos matemáticos, representações computacionais finitas e escolhas de implementação posteriores do ChrisOS.
</div>

## Escalares, vetores e coordenadas

Um escalar é representado por um valor depois que sua unidade e referência são definidas. Temperatura, tempo, resistência e energia são exemplos. Um vetor exige componentes relativos a uma base. No espaço cartesiano tridimensional,

~~~text
v = (vx, vy, vz) = vx ex + vy ey + vz ez
~~~

onde `ex`, `ey` e `ez` são vetores da base. Os componentes não são o objeto geométrico. Girar os eixos altera a tupla mesmo quando o deslocamento ou campo representado permanece igual. Essa distinção separa posteriormente coordenadas de mundo, câmera e clip.

Adição e multiplicação por escalar são feitas componente a componente:

~~~text
a + b = (ax+bx, ay+by, az+bz)
k a   = (k ax, k ay, k az)
~~~

As operações obedecem fechamento, associatividade, identidade e inverso aditivos e distributividade. Essas propriedades tornam transformações maiores composicionais.

Unidades continuam pertencendo ao modelo. Um deslocamento em metros não pode ser somado de forma fisicamente significativa a um campo elétrico em volts por metro apenas porque ambos têm três componentes. O armazenamento da máquina pode conter somente números; a interface precisa preservar a dimensão física.

| Grandeza | Exemplo | Unidade |
|---|---|---|
| posição | `(x,y,z)` | m ou unidade da cena |
| velocidade | `(vx,vy,vz)` | m/s |
| campo elétrico | `(Ex,Ey,Ez)` | V/m |
| força | `(Fx,Fy,Fz)` | N |
| RGB linear | `(r,g,b)` | convenção adimensional definida |

## Magnitude e normalização

Para um vetor euclidiano,

~~~text
||v|| = sqrt(vx² + vy² + vz²)
||v||² = vx² + vy² + vz²
~~~

O quadrado da magnitude é preferível quando só se comparam comprimentos, pois evita raiz quadrada. Um vetor unitário é

~~~text
v_hat = v / ||v||
~~~

desde que `||v|| != 0`. Normalização é uma operação parcial. O vetor zero não tem direção definida. Software de ponto flutuante também precisa de uma política para magnitudes muito pequenas, pois a divisão pode amplificar erro. Código robusto usa um limiar coerente com a escala da aplicação.

## Produto escalar e projeção

O produto escalar euclidiano é

~~~text
a · b = ax bx + ay by + az bz
      = ||a|| ||b|| cos(theta)
~~~

Logo,

~~~text
a · a = ||a||²
a · b = 0                 para vetores não nulos perpendiculares
cos(theta) = (a·b)/(||a|| ||b||)
~~~

Gráficos usam produto escalar para projeção, iluminação e orientação. Física o usa para trabalho, `W=F·d`, e em integrais de fluxo.

A projeção de `a` sobre `b` não nulo é

~~~text
proj_b(a) = ((a·b)/(b·b)) b
~~~

O denominador explicita a falha para o vetor zero. Para vetores densos de n componentes, o produto escalar executa n multiplicações e n-1 adições: Theta(n) de trabalho aritmético e O(1) de espaço auxiliar. Layout de memória, SIMD, precisão do acumulador e cache ainda podem dominar o custo real.

## Produto vetorial e orientação

Em três dimensões,

~~~text
a × b =
(ay bz - az by,
 az bx - ax bz,
 ax by - ay bx)
~~~

O resultado é perpendicular aos operandos e

~~~text
||a × b|| = ||a|| ||b|| sin(theta)
a × b = -(b × a)
~~~

A ordem determina a orientação. Isso é crítico para winding de triângulos, normais e bases de câmera. Trocar os operandos pode inverter uma normal preservando as magnitudes. O produto vetorial usado aqui é especificamente tridimensional, não uma operação genérica em qualquer dimensão.

## Combinações lineares, base e independência

Uma combinação linear tem a forma

~~~text
c1 v1 + c2 v2 + ... + ck vk
~~~

O conjunto dessas combinações é o span. Um conjunto é linearmente independente quando nenhum membro pode ser escrito como combinação dos demais. Uma base precisa ser independente e gerar o espaço; coordenadas são coeficientes relativos a essa base.

A consequência operacional é direta. Uma base de câmera degenerada ou uma transformação singular perde um grau de liberdade. Um triângulo cujas arestas são dependentes possui área zero. Um sistema linear com restrições dependentes pode não ter solução única.

## Matrizes como transformações

Uma matriz é um arranjo retangular de escalares, mas em sistemas ela frequentemente representa uma transformação entre espaços. Para

~~~text
y = A x
~~~

cada componente de saída é um produto escalar entre uma linha de `A` e `x`. Transformações compatíveis podem ser compostas:

~~~text
A(Bx) = (AB)x
~~~

Multiplicação de matrizes não é comutativa em geral:

~~~text
AB != BA
~~~

portanto a ordem faz parte da correção. Rotacionar e depois transladar não equivale, em geral, a transladar e depois rotacionar.

Multiplicação convencional de matrizes densas n por n exige Theta(n³) de trabalho escalar. Matrizes gráficas fixas 3 por 3 ou 4 por 4 são constantes assintoticamente, mas layout, vetorização e convenções continuam importantes.

## Determinante, inversa e singularidade

Para

~~~text
A = [a b]
    [c d]
~~~

o determinante é `ad-bc`. Se ele for diferente de zero,

~~~text
A^-1 = 1/(ad-bc) [ d -b]
                  [-c  a]
~~~

Determinante zero indica transformação singular e ausência de inversa única. Em ponto flutuante, obter um determinante não nulo não basta: uma matriz mal condicionada pode amplificar pequenos erros de entrada ou arredondamento. Software numérico precisa considerar escala e condicionamento.

Um sistema linear é escrito `Ax=b`. Eliminação de Gauss transforma a matriz aumentada por operações de linha. A eliminação densa comum requer Theta(n³) de aritmética e O(n²) para armazenar a matriz. Pivotamento parcial escolhe um pivô disponível de maior magnitude antes da divisão, reduzindo uma fonte importante de erro. Solução matemática exata e computação numericamente estável são propriedades diferentes.

## Números complexos

Um número complexo possui componentes real e imaginário:

~~~text
z = a + j b
j² = -1
~~~

Engenharia elétrica normalmente usa `j`, pois `i` representa corrente. A soma é componente a componente. A multiplicação segue

~~~text
(a+jb)(c+jd) = (ac-bd) + j(ad+bc)
~~~

O conjugado é `z*=a-jb`, de modo que

~~~text
z z* = a²+b² = |z|²
1/z = z*/|z|²
~~~

para `z` não nulo. Divisão complexa, portanto, exige tratamento explícito de magnitude zero ou numericamente muito pequena.

## Forma polar, fase e relação de Euler

Um complexo não nulo pode ser representado como

~~~text
z = r(cos(theta)+j sin(theta))
  = r e^(j theta)
~~~

Assim,

~~~text
(r1 e^(j theta1))(r2 e^(j theta2))
= r1 r2 e^(j(theta1+theta2))
~~~

A multiplicação multiplica magnitudes e soma fases. Isso torna números complexos naturais para rotações planares e análise senoidal.

Um vetor bidimensional `(x,y)` pode ser associado a `z=x+jy`. Multiplicá-lo por `e^(j theta)` o rotaciona. A transformação real equivalente é

~~~text
[x']   [cos(theta) -sin(theta)] [x]
[y'] = [sin(theta)  cos(theta)] [y]
~~~

As formas complexa e matricial descrevem a mesma rotação planar por representações algébricas diferentes.

## Senoides e fasores

Uma senoide real pode ser representada pela parte real de uma exponencial complexa:

~~~text
x(t) = A cos(omega t + phi)
     = Re{A e^(j phi) e^(j omega t)}
~~~

Para um sistema linear invariante no tempo analisado em uma frequência angular, o fator temporal comum pode ser omitido e o sinal representado pelo fasor `X=A e^(j phi)`. Derivar passa a equivaler à multiplicação por `j omega`:

~~~text
d/dt [X e^(j omega t)] = j omega X e^(j omega t)
~~~

Isso transforma relações diferenciais de capacitores e indutores ideais em impedâncias algébricas:

~~~text
Z_R = R
Z_L = j omega L
Z_C = 1/(j omega C)
~~~

A componente imaginária registra fase; não é uma substância física separada. Um fasor também não é o próprio sinal no tempo. É uma representação no domínio da frequência válida sob hipóteses de regime senoidal permanente. Aplicá-la diretamente a transitórios arbitrários é erro de modelo.

## Representações numéricas finitas

Números reais e complexos matemáticos possuem precisão conceitual que representações computacionais não possuem. Operações de ponto flutuante arredondam resultados exatos. Isso produz adição não perfeitamente associativa, cancelamento ao subtrair valores próximos, drift em transformações repetidas, overflow, underflow, NaN e infinitos.

Matematicamente,

~~~text
(a+b)+c = a+(b+c)
~~~

mas o arredondamento pode fazer as duas avaliações diferirem. Algoritmos precisam separar identidades algébricas de garantias bit a bit.

Ponto fixo armazena um inteiro escalado:

~~~text
valor_real = inteiro_armazenado / escala
~~~

Ele oferece faixa explícita e representação previsível, mas exige disciplina de escala e overflow. Aritmética vetorial inteira é exata apenas enquanto permanece na faixa. Escolher `float`, `double`, ponto fixo ou inteiro é decisão arquitetural envolvendo precisão, faixa, desempenho, ABI e hardware.

## Layout de dados e custo de máquina

Um vetor pode ser armazenado como array ou estrutura:

~~~text
struct Vec3 {
    float x;
    float y;
    float z;
};
~~~

O objeto matemático não determina esse layout. A implementação precisa considerar largura escalar, alinhamento, padding, loads SIMD, ABI, aliasing e cache.

Array-of-structures mantém componentes de um objeto juntos. Structure-of-arrays mantém o mesmo componente de muitos objetos junto. A segunda organização pode favorecer SIMD por componente; a primeira pode favorecer código que consome repetidamente um vetor completo. Nenhuma é universalmente superior.

Convenções de coordenadas também são parte do contrato. Uma interface gráfica precisa declarar handedness, vetores-linha ou coluna, ordem de armazenamento, ordem de multiplicação, unidade angular, intervalo de profundidade normalizada e origem da tela. Armazenamento row-major e matemática com vetores-linha não são sinônimos.

## Invariantes para validação

Propriedades determinísticas úteis incluem:

| Propriedade | Relação esperada |
|---|---|
| norma | `v·v ≈ ||v||²` |
| ortogonalidade | `a·b ≈ 0` |
| orientação | `a×b = -(b×a)` |
| perpendicularidade | `(a×b)·a ≈ 0` |
| conjugado | `z z* ≈ |z|²` |
| rotação complexa unitária | `|z e^(jθ)| ≈ |z|` |
| inversa | `A A^-1 ≈ I` para A inversível e bem condicionada |

Igualdade aproximada em ponto flutuante exige tolerância sensível à escala. Um único epsilon absoluto normalmente é inadequado para valores distribuídos por muitas ordens de magnitude.

## Fronteiras de falha

| Operação | Falha ou risco |
|---|---|
| normalização | magnitude zero ou quase zero |
| ângulo via produto escalar | operando zero ou razão arredondada fora de [-1,1] |
| inversão | matriz singular ou mal condicionada |
| divisão complexa | denominador zero ou minúsculo |
| transformação acumulada | drift de arredondamento |
| normal por produto vetorial | triângulo degenerado ou winding invertido |
| conversão de unidade | valores dimensionalmente incompatíveis |
| transformação | handedness ou ordem de multiplicação incompatíveis |

Uma implementação robusta documenta essas precondições e testa as fronteiras.

## Relação com o ChrisOS

Este capítulo é intencionalmente independente de implementação. A revisão examinada do ChrisOS é registrada para proveniência, mas nenhum comportamento do código é afirmado porque esta fundação matemática não possui dependência de fonte declarada.

Capítulos elétricos posteriores usam vetores para campos e números complexos para fase e impedância. Capítulos de gráficos usam vetores, matrizes, produtos escalar e vetorial e transformações. Software 3D usa representações finitas em vez de números reais abstratos. Shaders e rasterização dependem de convenções explícitas.

Esses capítulos precisam documentar os tipos e símbolos reais do ChrisOS em vez de atribuir uma implementação de livro-texto por analogia.

## Limite de escopo e revisão

Este capítulo fornece a álgebra linear e os números complexos necessários ao currículo. Não substitui tratamentos completos de álgebra linear, análise numérica, Fourier ou controle. Capítulos posteriores estendem a base com coordenadas homogêneas, projeção, interpolação, comportamento de circuitos dependente de frequência e tipos numéricos concretos do ChrisOS.

Verdade matemática, representação numérica e implementação atual são camadas de evidência distintas.

Revisado contra o `main` do ChrisOS na revisão `da3df29cb397932c43d32373871fb9380e688ade`. `sources` e `symbols` estão vazios porque não há afirmação de implementação neste capítulo.


## Coordenadas afins e translação

Transformações lineares preservam a origem: para um mapa linear `A`, `A0=0`. Translação não preserva a origem e não pode ser representada por uma matriz linear 3 por 3 comum agindo sobre uma posição tridimensional. Gráficos introduzem coordenadas homogêneas para compor transformações afins uniformemente. Uma posição torna-se `(x,y,z,1)`, enquanto uma direção pode ser `(x,y,z,0)`. Uma matriz 4 por 4 passa a transportar a translação em sua última linha ou coluna, conforme a convenção.

A distinção entre posição e direção é semântica. Transladar um ponto muda sua localização; uma direção não deveria mudar. O componente homogêneo torna essa diferença visível na álgebra. Projeção em perspectiva também utiliza a quarta coordenada, seguida pela divisão de perspectiva. Os capítulos de gráficos derivam esse pipeline; aqui a regra essencial é que uma tupla só possui significado junto do espaço e da convenção em que é interpretada.

## Mudança de base

Suponha que as colunas de uma matriz inversível `B` sejam vetores de uma base expressos em um sistema de referência. Coordenadas `c` nessa base correspondem ao vetor

~~~text
v = B c
~~~

e a conversão de volta é

~~~text
c = B^-1 v
~~~

Uma transformação de câmera pode ser entendida como mudança de base combinada com translação, não como uma coleção arbitrária de coeficientes. Essa interpretação ajuda na depuração porque explicita quais eixos e origem a transformação representa.

Bases ortonormais são convenientes. Se as colunas são vetores unitários mutuamente perpendiculares, então `B^-1=B^T` em aritmética exata. Precisão finita pode destruir gradualmente a ortogonalidade; atualizações repetidas podem exigir renormalização ou reconstrução.

## Acumulação numérica e reprodutibilidade

A ordem de redução importa em aritmética finita. Um produto escalar acumulado sequencialmente pode diferir de uma redução em árvore ou SIMD porque o arredondamento ocorre após somas intermediárias diferentes. Código paralelo pode produzir respostas numericamente próximas, mas não idênticas bit a bit, mesmo quando os cálculos estão corretos.

A validação precisa escolher o contrato deliberadamente. Reprodutibilidade bit a bit exige representação e ordem de operações fixas. Equivalência numérica permite erro limitado e deve especificar tolerâncias absolutas e relativas. Testes também precisam incluir entradas zero, quase zero, muito grandes, muito pequenas, colineares, perpendiculares e quase singulares, não apenas vetores ordinários.
