---
id: ohm-kirchhoff-circuits
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - voltage-current-resistance-power
related:
  - capacitance-inductance
  - rc-rlc-transients
  - ac-signals-frequency-impedance
  - noise-grounding-signal-integrity
  - power-delivery-regulation
---

# Lei de Ohm, leis de Kirchhoff e análise de circuitos

<div class="abstract">
A lei de Ohm fornece uma relação constitutiva para um resistor linear ideal; as leis de corrente e tensão de Kirchhoff conectam as relações dos elementos por meio da topologia do circuito. Juntas, transformam um diagrama de rede em um sistema de equações solucionável. Este capítulo desenvolve modelos de nós e ramos, análise nodal e de malhas, redes equivalentes, fontes dependentes, verificações de potência, casos singulares, solução numérica e a fronteira entre teoria de circuitos concentrados e o hardware físico posteriormente consumido pelo ChrisOS.
</div>

## Pré-requisitos e escopo

O capítulo anterior definiu tensão como diferença de potencial, corrente como taxa de transferência de carga, resistência, condutância, energia, potência e a convenção passiva de sinais.

Este capítulo adiciona estrutura de rede.

Um modelo de circuito é composto por:

~~~text
componentes
    relações constitutivas de terminal

topologia
    quais terminais compartilham nós

escolhas de referência
    polaridades de tensão e sentidos de corrente
~~~

As equações não são determinadas apenas pelos valores dos componentes. Dois conjuntos de resistores idênticos conectados de maneira diferente formam redes distintas.

A análise abaixo assume elementos concentrados. Cada nó ideal é tratado como um único potencial, fios são ideais salvo quando sua resistência é explicitamente modelada, e a propagação eletromagnética é desprezada. Capítulos posteriores introduzem capacitância, indutância, transitórios, dependência de frequência e efeitos de linha de transmissão.

Este é um pré-requisito de física e teoria de circuitos. Nenhum comportamento atual do código-fonte do ChrisOS é afirmado aqui.

## O resistor linear ideal

Para um resistor ideal,

~~~text
v = R i
~~~

sob uma polaridade de tensão e direção de corrente declaradas.

Equivalentemente,

~~~text
i = G v
G = 1/R
~~~

onde (G) é a condutância.

Para (R>0) sob convenção passiva de sinais,

~~~text
p = vi = i²R = v²/R >= 0
~~~

portanto o resistor ideal dissipa energia em vez de gerá-la.

Essa lei é linear:

~~~text
i(v1 + v2) = i(v1) + i(v2)
i(kv) = k i(v)
~~~

para (R) fixo. É essa linearidade que permite superposição e solução matricial posteriormente.

Dispositivos resistivos reais podem ser não lineares, dependentes de temperatura, frequência ou possuir ruído. O símbolo "resistor" em um esquema significa o modelo escolhido, não todas as propriedades microscópicas do objeto físico.

## Nós, ramos e laços

Um **nó** é um conjunto de condutores ideais interconectados tratado como um único potencial elétrico.

Um **ramo** conecta dois nós por um ou mais elementos modelados e transporta uma corrente de ramo.

Um **caminho** é uma sequência ordenada de ramos conectados.

Um **laço** é um caminho fechado.

A topologia pode ser representada como um grafo:

~~~text
        R1
  A o--/\/\--o B
    |          |
   R2         R3
    |          |
  C o----------o
~~~

Nós elétricos são vértices do grafo e ramos são arestas.

Esse mapeamento é importante porque as leis de Kirchhoff são, fundamentalmente, restrições topológicas combinadas com leis de conservação.

## Lei das correntes de Kirchhoff

A lei das correntes de Kirchhoff, KCL, afirma que a soma algébrica das correntes em um nó ideal concentrado é zero:

~~~text
Σ i_k = 0
~~~

Uma convenção de sinais deve ser escolhida. Por exemplo, correntes entrando no nó podem ser positivas e correntes saindo negativas.

Forma equivalente:

~~~text
soma das correntes entrando
=
soma das correntes saindo
~~~

KCL é uma consequência, em escala de circuito, da conservação de carga quando o acúmulo de carga no nó ideal é inexistente ou representado explicitamente por elementos de armazenamento.

Para um nó com correntes (i_1) e (i_2) entrando e (i_3) saindo,

~~~text
i1 + i2 - i3 = 0
~~~

logo

~~~text
i3 = i1 + i2
~~~

KCL não diz que as correntes são fisicamente iguais em todos os ramos. Ela restringe a soma com sinais na conexão.

## Quando a carga do nó importa

Se carga puder se acumular em uma estrutura capacitiva explicitamente modelada, KCL continua válida quando a corrente do capacitor é incluída.

A afirmação de conservação mais profunda é

~~~text
taxa de acúmulo de carga
=
corrente líquida entrando na região
~~~

A análise nodal ideal representa o armazenamento por correntes de ramo dos elementos, e não abandonando a conservação de carga.

Em frequências suficientemente altas, corrente de deslocamento e efeitos eletromagnéticos distribuídos exigem modelos de campo mais cuidadosos. As equações concentradas continuam sendo uma aproximação cuja validade depende da escala.

## Lei das tensões de Kirchhoff

A lei das tensões de Kirchhoff, KVL, afirma que a soma algébrica das variações de tensão ao redor de um laço fechado no modelo concentrado é zero:

~~~text
Σ v_k = 0
~~~

Isso decorre de potenciais de nó consistentes no modelo concentrado/quase-estático comum. Se uma tensão de ramo é definida como

~~~text
v_ab = V_a - V_b
~~~

então somar diferenças ao redor de

~~~text
A -> B -> C -> A
~~~

produz

~~~text
(V_A - V_B)
+ (V_B - V_C)
+ (V_C - V_A)
= 0
~~~

por cancelamento.

O sinal de cada termo depende do sentido de percurso e da polaridade de tensão definida.

## KVL e fluxo magnético variável no tempo

A forma simples de KVL baseada em potencial escalar possui uma fronteira física.

A lei de Faraday afirma que fluxo magnético variável no tempo pode produzir um campo elétrico não conservativo:

~~~text
∮ E · dl = - dΦ_B/dt
~~~

A teoria de circuitos representa esse comportamento por elementos indutivos e modelos acoplados. Portanto, é mais preciso tratar KVL comum como propriedade do modelo concentrado selecionado, e não como uma afirmação irrestrita de que toda integral de campo em qualquer caminho físico fechado e sob qualquer condição eletromagnética seja nula.

## Resistores em série

Dois resistores estão em série quando a mesma corrente de ramo necessariamente atravessa ambos e o nó intermediário não possui outro caminho de corrente no modelo.

Para

~~~text
V -- R1 -- R2 -- referência
~~~

KVL fornece

~~~text
V = iR1 + iR2
  = i(R1 + R2)
~~~

logo

~~~text
R_eq = R1 + R2
~~~

Para (n) resistores em série,

~~~text
R_eq = Σ R_k
~~~

A condição é topológica. Componentes aparecerem visualmente lado a lado em um diagrama não prova que estejam em série.

## Divisor de tensão

Para dois resistores em série ligados a uma fonte (V),

~~~text
i = V/(R1 + R2)
~~~

e a tensão sobre (R2) é

~~~text
V2 = i R2
   = V R2/(R1 + R2)
~~~

A equação familiar do divisor assume que a saída não é carregada por um ramo adicional.

Se uma carga (R_L) é conectada em paralelo com (R2), a resistência efetiva inferior passa a ser

~~~text
R_low = R2 || R_L
~~~

e a razão do divisor muda.

Um instrumento de medição de alta impedância aproxima a condição sem carga; uma resistência de entrada baixa pode alterá-la de forma relevante.

## Resistores em paralelo

Dois resistores estão em paralelo quando ambos os terminais de um se conectam ao mesmo par de nós do outro. Portanto, possuem a mesma tensão.

KCL fornece

~~~text
i_total
=
V/R1 + V/R2
=
V(1/R1 + 1/R2)
~~~

logo

~~~text
1/R_eq = 1/R1 + 1/R2
~~~

Para dois resistores,

~~~text
R_eq = (R1 R2)/(R1 + R2)
~~~

Em termos de condutâncias,

~~~text
G_eq = Σ G_k
~~~

o que frequentemente simplifica a álgebra.

## Divisor de corrente

Para dois resistores em paralelo com corrente total (I),

~~~text
I1 = I * G1/(G1 + G2)
~~~

ou, em termos de resistência,

~~~text
I1 = I * R2/(R1 + R2)
I2 = I * R1/(R1 + R2)
~~~

A corrente tende a ser maior no ramo de maior condutância, não porque a corrente "escolha o caminho mais fácil" como um agente independente, mas porque a tensão comum dos nós e as relações constitutivas dos ramos determinam conjuntamente as correntes.

## Fontes independentes de tensão e corrente

Uma fonte independente ideal de tensão impõe

~~~text
v = V_s
~~~

enquanto uma fonte independente ideal de corrente impõe

~~~text
i = I_s
~~~

A rede determina a grandeza conjugada.

Fontes reais possuem limites e dinâmica interna. Uma fonte ideal de tensão pode matematicamente fornecer qualquer corrente exigida por uma rede ideal compatível; isso é uma abstração de modelagem, não uma capacidade física.

Algumas combinações de fontes ideais são inconsistentes. Duas fontes ideais de tensão com valores diferentes ligadas diretamente em paralelo exigem tensões contraditórias. Duas fontes ideais de corrente em série também podem impor correntes incompatíveis dependendo da topologia.

Um solucionador deve detectar essas contradições em vez de retornar valores arbitrários.

## Fontes dependentes

Uma fonte dependente possui valor controlado por outra variável do circuito.

Formas ideais comuns são:

| Tipo | Relação |
|---|---|
| fonte de tensão controlada por tensão | (v = mu v_x) |
| fonte de tensão controlada por corrente | (v = r i_x) |
| fonte de corrente controlada por tensão | (i = g v_x) |
| fonte de corrente controlada por corrente | (i = eta i_x) |

Fontes dependentes modelam amplificação, transcondutância e comportamento controlado.

Elas são essenciais em modelos de pequenos sinais e não podem, em geral, ser "desligadas" durante superposição da mesma forma que fontes independentes.

## Análise nodal

A análise nodal escolhe um nó de referência e resolve os potenciais dos demais nós.

Para um resistor conectando nós (a) e (b),

~~~text
i_ab = (V_a - V_b)/R
     = G(V_a - V_b)
~~~

Aplica-se KCL em cada nó desconhecido.

Exemplo:

~~~text
        R1
Vs o--/\/\--o Vx
             / \
           R2   R3
           |     |
         ref    ref
~~~

No nó (V_x),

~~~text
(Vx - Vs)/R1
+ Vx/R2
+ Vx/R3
= 0
~~~

Agrupando termos,

~~~text
Vx(1/R1 + 1/R2 + 1/R3)
=
Vs/R1
~~~

Isso já é um sistema linear de uma equação.

## Forma de matriz de condutância

Para uma rede resistiva, as equações nodais podem ser montadas como

~~~text
G v = b
~~~

onde

- (v) é o vetor de tensões de nó desconhecidas;
- (G) é a matriz nodal de condutância;
- (b) contém injeções de corrente e contribuições das fontes.

Para um resistor comum entre nós (i) e (j), com condutância (g), a contribuição é:

~~~text
G[i,i] += g
G[j,j] += g
G[i,j] -= g
G[j,i] -= g
~~~

quando nenhum dos nós é a referência escolhida.

Essa regra local de *stamping* torna a montagem do circuito sistemática.

Para uma rede resistiva passiva conectada, com referência adequada e sem restrições ideais contraditórias, a matriz de condutância possui propriedades estruturais úteis. Topologia degenerada ou subcircuitos flutuantes podem torná-la singular.

## Redes flutuantes e matrizes singulares

Uma rede possui potencial absoluto indefinido se nenhuma referência ou restrição equivalente o fixa.

Por exemplo, dois resistores conectados apenas entre si e sem referência podem ter diferenças de potencial determinadas sob certas condições de fonte, enquanto todos os potenciais dos nós podem ser deslocados pela mesma constante.

Na forma matricial, essa liberdade de gauge aparece como singularidade.

Uma falha do solver pode, portanto, indicar um problema de modelagem em vez de uma falha aritmética.

Causas típicas incluem:

- ausência de nó de referência;
- componente desconectado e flutuante;
- restrições ideais contraditórias;
- restrições redundantes;
- topologia que deixa um grau de liberdade sem restrição.

## Análise nodal modificada

Análise nodal pura lida naturalmente com resistores e fontes de corrente. Fontes ideais de tensão entre nós desconhecidos introduzem correntes que não podem ser expressas diretamente como condutância vezes tensão.

A análise nodal modificada, MNA, amplia o vetor de incógnitas com correntes de ramos selecionados.

Conceitualmente:

~~~text
[ G  B ] [v] = [i]
[ C  D ] [j]   [e]
~~~

As variáveis adicionais permitem que restrições de fontes ideais de tensão coexistam com equações de KCL.

Simuladores da família SPICE usam variantes dessa abordagem geral porque muitos modelos práticos de elementos podem ser montados por *stamps* esparsos.

A formulação matricial exata depende dos dispositivos suportados e do modo de análise.

## Análise de malhas e laços

Para circuitos planares, análise de malhas pode escolher correntes independentes de malha e aplicar KVL.

Se duas malhas compartilham um resistor, a corrente no resistor é a diferença algébrica das correntes de malha.

Um sistema de duas malhas pode assumir a forma

~~~text
(R1 + R3) I1 - R3 I2 = V1
-R3 I1 + (R2 + R3) I2 = V2
~~~

A análise de malhas pode ser compacta quando o número de malhas é menor que o número de nós não referenciais. Ela é menos universal que análise nodal/MNA para grafos arbitrários e vários tipos de fontes.

## Independência topológica das equações

Escrever KCL em todos os nós cria uma equação redundante porque a soma de todas as equações nodais é zero em uma rede fechada. Escolher uma referência e resolver os demais nós remove essa redundância.

Da mesma forma, nem toda equação de laço possível é independente.

A teoria de grafos explica as contagens. Para um grafo conectado com

~~~text
N nós
B ramos
~~~

uma árvore geradora possui (N-1) ramos, e o número de laços fundamentais independentes é

~~~text
B - N + 1
~~~

Por isso a análise sistemática escolhe equações independentes em vez de escrever indiscriminadamente toda relação possível de KCL e KVL.

## Superposição em circuitos lineares

Em uma rede linear, a resposta causada por várias fontes independentes é igual à soma das respostas produzidas por cada fonte separadamente.

Para zerar uma fonte independente no modelo linear ideal:

~~~text
fonte ideal de tensão -> substituir por 0 V -> curto-circuito
fonte ideal de corrente -> substituir por 0 A -> circuito aberto
~~~

Fontes dependentes permanecem ativas porque fazem parte das relações constitutivas da rede.

Superposição aplica-se a tensões e correntes, não diretamente a grandezas não lineares como potência:

~~~text
P(resposta total)
!=
Σ P(cada resposta)
~~~

em geral.

## Equivalente de Thévenin

Uma rede linear de dois terminais vista por uma porta pode frequentemente ser substituída por uma fonte ideal de tensão (V_{th}) em série com uma resistência (R_{th}).

A tensão de circuito aberto na porta é

~~~text
V_th = V_oc
~~~

Para uma rede contendo apenas fontes independentes e resistores, (R_{th}) pode ser obtida zerando as fontes independentes e calculando a resistência vista pela porta.

Com fontes dependentes, normalmente utiliza-se uma fonte de teste. Aplica-se uma tensão (V_t) e mede-se a corrente resultante (I_t):

~~~text
R_th = V_t/I_t
~~~

desde que o modelo linear da porta esteja bem definido.

## Equivalente de Norton

O equivalente de Norton usa uma fonte de corrente (I_n) em paralelo com (R_n).

Para a mesma porta linear,

~~~text
R_n = R_th
V_th = I_n R_th
~~~

e (I_n) corresponde à corrente de curto-circuito sob a convenção de sinais adotada.

Equivalentes de Thévenin e Norton preservam o comportamento de terminal na porta selecionada. Eles não preservam correntes internas de ramos, distribuição interna de potência ou estado oculto.

## Fronteira da máxima transferência de potência

Para uma fonte puramente resistiva representada por (V_{th}) e (R_{th}>0), uma carga resistiva recebe potência máxima quando

~~~text
R_L = R_th
~~~

Essa condição **não** maximiza eficiência. Nesse ponto, a resistência interna ideal da fonte dissipa a mesma potência que a carga, portanto apenas metade da potência fornecida pela fonte de Thévenin chega à carga.

Sistemas de entrega de potência normalmente buscam baixa impedância de fonte em vez de casamento deliberado para máxima transferência resistiva. O objetivo correto depende do domínio.

## Transformação de fontes

Uma fonte ideal de tensão (V_s) em série com (R) possui a mesma relação externa (i)-(v) de dois terminais que uma fonte ideal de corrente

~~~text
I_s = V_s/R
~~~

em paralelo com o mesmo (R).

Essa transformação é válida na porta sob o modelo linear ideal. Ela não implica que as fontes físicas internas sejam idênticas.

## Transformações delta-estrela

Algumas redes resistivas não podem ser reduzidas apenas por combinações simples série/paralelo.

Uma rede delta com resistências (R_{ab}, R_{bc}, R_{ca}) pode ser convertida em uma estrela equivalente. Defina

~~~text
S = R_ab + R_bc + R_ca
~~~

então

~~~text
R_a = R_ab R_ca / S
R_b = R_ab R_bc / S
R_c = R_bc R_ca / S
~~~

A transformação inversa também é possível.

Para redes grandes, análise nodal sistemática normalmente é mais clara e menos sujeita a erro que sucessivas reduções simbólicas de topologia.

## Balanço de potência como invariante de validação

Uma rede ideal solucionada deve satisfazer conservação de energia.

Usando uma convenção de sinais consistente,

~~~text
Σ p_k = 0
~~~

sobre todos os elementos a cada instante para uma rede concentrada sem termo de armazenamento ou campo omitido.

Resistores absorvem potência positiva sob convenção passiva. Fontes entregando energia contribuem com potência negativa.

O balanço de potência é uma excelente verificação de depuração porque um sinal incorreto, uma corrente de ramo errada ou uma polaridade invertida normalmente aparecem imediatamente como um resíduo diferente de zero.

Em computação com precisão finita, o resíduo é comparado com uma tolerância dependente de escala em vez de zero binário exato.

## Solução de sistemas lineares

Depois da montagem do circuito, a solução numérica é um problema de álgebra linear.

Para sistemas densos (n 	imes n), eliminação de Gauss comum requer aproximadamente

~~~text
Theta(n^3)
~~~

operações aritméticas e

~~~text
Theta(n^2)
~~~

de armazenamento.

Matrizes de circuitos costumam ser esparsas porque cada componente conecta poucos nós. Solvers diretos esparsos exploram essa estrutura, embora o processo de fatoração possa produzir *fill-in*, criando novos elementos não nulos.

Simuladores grandes, portanto, se preocupam com:

- formatos de armazenamento esparso;
- ordenação de nós;
- pivotamento;
- heurísticas para reduzir fill-in;
- condicionamento da matriz;
- fatorações repetidas em pontos de operação relacionados.

O melhor algoritmo depende da estrutura da rede e do tipo de análise.

## Condicionamento e erro numérico

Um circuito matematicamente solucionável ainda pode ser numericamente difícil.

Razões muito grandes entre condutâncias podem gerar matrizes mal condicionadas. Por exemplo, misturar caminhos de gigaohms e micro-ohms na mesma rede pode fazer pequenas tensões dependerem da subtração de quantidades muito maiores.

Pivotamento parcial reduz alguns riscos numéricos, mas não transforma um modelo fundamentalmente mal condicionado em bem condicionado.

Boas práticas incluem:

- unidades consistentes;
- tolerâncias sensíveis à escala;
- verificação de resíduos;
- evitar valores ideais extremos sem necessidade;
- reportar sistemas singulares ou quase singulares em vez de regularizá-los silenciosamente.

## Ponto de operação DC e extensões não lineares

As equações deste capítulo são lineares quando todos os elementos são lineares.

Circuitos reais de transistores possuem relações não lineares. Uma estratégia comum para análise DC não linear é resolver

~~~text
F(x) = 0
~~~

iterativamente, frequentemente por Newton-Raphson ou método relacionado. Cada iteração lineariza os dispositivos não lineares e resolve um sistema linear.

Isso pertence à teoria de dispositivos e simuladores, não ao modelo puramente resistivo deste capítulo.

A conexão importante é que a topologia de Kirchhoff permanece, enquanto as relações constitutivas dos elementos tornam-se não lineares.

## Estruturas de dados para um solver em software

Um solver educacional simples poderia representar:

~~~text
Node {
    id
    is_reference
}

Resistor {
    node_a
    node_b
    conductance
}

CurrentSource {
    node_a
    node_b
    current
}

VoltageSource {
    node_a
    node_b
    voltage
}
~~~

A montagem mapeia identificadores de nós para linhas da matriz.

Uma implementação esparsa pode usar triplas de coordenadas durante o *stamping* e compactá-las em CSR/CSC antes da fatoração.

Invariantes importantes são:

- exatamente uma referência por componente conectado resolvido, salvo quando uma restrição equivalente a substitui;
- terminais de componentes referenciam nós válidos;
- dimensões da matriz coincidem com o vetor de incógnitas;
- *stamps* usam uma única convenção de polaridade;
- unidades são normalizadas antes da montagem.

Esses são princípios gerais de modelagem, não estruturas de dados atuais do ChrisOS.

## Complexidade da construção topológica

Se uma rede contém (B) ramos de dois terminais, construir informações de adjacência normalmente custa (O(B)).

O *stamping* de um resistor acrescenta um número constante de contribuições à matriz, portanto a montagem bruta também é (O(B)) antes do gerenciamento da estrutura esparsa.

A solução normalmente domina o custo.

Para matrizes esparsas, a complexidade depende fortemente da estrutura do grafo e da ordem de eliminação; não existe um único limite (O(n^k)) que preveja bem todas as redes práticas.

## Falhas e comportamento de recuperação em software

Um solver robusto deve distinguir:

| Condição | Resposta apropriada |
|---|---|
| valor de componente inválido | rejeitar entrada com localização/contexto |
| nó inexistente | rejeitar topologia |
| rede sem referência/flutuante | reportar topologia singular |
| restrições ideais conflitantes | reportar inconsistência |
| matriz quase singular | reportar aviso/falha de condicionamento |
| overflow/NaN numérico | interromper e expor a operação |
| resíduo de potência excessivo | marcar solução como inválida |
| elemento não linear não suportado | rejeitar em vez de aproximar silenciosamente |

Retornar números após uma fatoração fracassada é pior que falhar explicitamente, pois a saída pode parecer plausível enquanto viola as restrições do circuito.

## Fronteira de privilégio, concorrência e ABI

Equações de circuito não possuem nível de privilégio de CPU nem ABI intrínseca.

Um futuro simulador no ecossistema ChrisOS poderia ter preocupações de concorrência, propriedade de memória e formato de arquivo, mas elas pertenceriam à implementação concreta.

Da mesma forma, registradores de telemetria de hardware usados por um sistema operacional não são derivados de KCL em tempo de execução. O silício e a placa implementam o comportamento físico, enquanto software observa interfaces abstratas de registradores, interrupções e gerenciamento de energia.

## Relação com hardware digital

Uma porta lógica digital não é uma rede ideal de resistores, mas a análise de circuitos continua fundamental.

Em diferentes abstrações:

~~~text
física de campo/dispositivo
    ↓
comportamento I-V de transistores
    ↓
redes efetivas de pull-up/pull-down
    ↓
capacitância de nó e tensão transitória
    ↓
cruzamento de limiar lógico
    ↓
estado digital
~~~

Análise estática de CMOS frequentemente raciocina sobre caminhos condutores e resistências efetivas, enquanto temporização exige capacitância e comportamento transitório.

Os próximos capítulos adicionam esse armazenamento e dependência temporal.

## Relação com o ChrisOS

O ChrisOS executa depois que várias camadas inferiores comprimem o comportamento físico de circuitos em contratos de hardware digital.

Uma cadeia representativa é:

~~~text
entrega de potência e rede de transistores
    ↓
portas lógicas e elementos de armazenamento
    ↓
estado arquitetural de CPU/dispositivo
    ↓
MMIO, memória, interrupções e instruções
    ↓
ChrisOS
~~~

O ChrisOS não resolve equações de Kirchhoff ao atender uma interrupção.

Se componentes futuros do ChrisOS expuserem valores de sensores como tensão, corrente ou potência, esses valores serão interpretados por especificações de dispositivos e código de drivers. Essas afirmações de implementação deverão ser documentadas em capítulos de subsistemas ligados ao código-fonte.

## Evidência de validação

O checker executável associado a este capítulo valida casos determinísticos representativos:

- resistência em série;
- resistência em paralelo;
- divisores de tensão sem e com carga;
- divisão de corrente;
- solução nodal de dois nós;
- resíduo de KCL;
- resíduo de KVL;
- equivalência de Thévenin/Norton;
- balanço de potência;
- singularidade de uma matriz de condutância propositalmente flutuante usando determinante no pequeno caso didático;
- âncoras obrigatórias da documentação bilíngue.

Esses testes verificam exemplos aritméticos e invariantes editoriais. Eles não constituem uma implementação de SPICE nem uma suíte de conformidade de hardware físico.

## Limitações atuais

Este capítulo exclui intencionalmente:

- equações de estado de capacitores e indutores;
- transitórios por equações diferenciais;
- fasores AC e impedância complexa;
- propagação em linhas de transmissão;
- equações não lineares de dispositivos semicondutores;
- modelos de ruído;
- tolerâncias estocásticas;
- parasitas de PCB;
- implementação concreta no código-fonte do ChrisOS.

Esses assuntos permanecem separados para que estado, frequência, geometria e evidência de fonte não sejam ocultados em uma visão genérica de circuitos.

## Fronteira do roadmap

Os próximos estágios do currículo estendem as equações de rede, em vez de substituí-las:

~~~text
Ohm + KCL + KVL
    ↓
relações constitutivas de capacitor e indutor
    ↓
equações diferenciais e transitórios
    ↓
representação por fasores/impedância
    ↓
interconexão distribuída e integridade de sinal
    ↓
chaveamento semicondutor e entrega de potência
~~~

Cada abstração posterior deve preservar as restrições de conservação enquanto adiciona o estado ou detalhe físico necessário ao problema.

## Proveniência da revisão

Revisado contra o `main` do ChrisOS na revisão `da3df29cb397932c43d32373871fb9380e688ade`.

`sources` e `symbols` estão intencionalmente vazios porque este capítulo não faz afirmação sobre implementação atual do ChrisOS. A revisão registra a proveniência do corpus e a fronteira de implementação.
