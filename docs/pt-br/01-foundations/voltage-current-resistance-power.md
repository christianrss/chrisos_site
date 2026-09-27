---
id: voltage-current-resistance-power
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - electric-charge-field-potential
related:
  - ohm-kirchhoff-circuits
  - capacitance-inductance
  - rc-rlc-transients
  - ac-signals-frequency-impedance
  - power-delivery-regulation
  - cmos-switching-power
---

# Tensão, corrente, resistência, energia e potência

<div class="abstract">
A teoria de circuitos substitui um problema eletromagnético espacial por potenciais de nós, correntes de ramos e relações de componentes. Este capítulo deriva as grandezas que tornam essa abstração útil: tensão como diferença de potencial, corrente como taxa de transporte de carga, resistência como relação constitutiva e potência como taxa de transferência de energia. Também separa modelos lineares ideais de condutores reais, fixa convenções de sinal e estabelece a contabilidade de energia usada posteriormente para chaveamento CMOS, entrega de potência e limites térmicos.
</div>

## Pré-requisitos e escopo

O capítulo anterior estabeleceu carga (Q), potencial elétrico (V), diferença de potencial, campo e energia. A ponte central foi

~~~text
ΔU = q ΔV
~~~

e corrente foi introduzida apenas como a derivada da carga transportada. Aqui essas grandezas tornam-se variáveis de circuito.

Assume-se a abstração de circuito concentrado: cada nó ideal é tratado como aproximadamente equipotencial e a propagação pela estrutura é desprezada na escala do problema. Isso não é válido para toda interconexão física. Comportamento de linha de transmissão, parasitas e efeitos de campo em alta frequência são tratados em capítulos posteriores.

Este capítulo não atribui comportamento de circuito elétrico ao código-fonte do ChrisOS. Ele é um pré-requisito físico para compreender o hardware cujos contratos arquiteturais o ChrisOS consome.

## Definições do SI e estrutura dimensional

O Sistema Internacional de Unidades define o ampere como a unidade básica de corrente elétrica. No SI atual, a carga elementar possui o valor exato

~~~text
e = 1.602176634 × 10^-19 C
~~~

e

~~~text
1 C = 1 A·s
~~~

As unidades derivadas usadas ao longo deste capítulo são

| Grandeza | Símbolo | Unidade SI | Relação dimensional |
|---|---|---|---|
| carga | (Q) | coulomb, C | A·s |
| corrente | (I) | ampere, A | C/s |
| diferença de potencial | (V) | volt, V | J/C |
| resistência | (R) | ohm, Ω | V/A |
| condutância | (G) | siemens, S | A/V |
| energia | (E) ou (U) | joule, J | N·m |
| potência | (P) | watt, W | J/s = V·A |

Análise dimensional é uma verificação mecânica de correção. Por exemplo,

~~~text
V I = (J/C)(C/s) = J/s = W
~~~

portanto tensão multiplicada por corrente possui dimensão de potência.

As referências metrológicas primárias para essas unidades são o *SI Brochure* do BIPM, 9ª edição, versão 4.01 (junho de 2026), e o material atual do NIST sobre unidades básicas do SI.

## Tensão é uma diferença, não uma substância armazenada

Tensão de circuito é diferença de potencial elétrico. Com uma referência escolhida,

~~~text
v_ab = V_a - V_b
~~~

A marcação de polaridade faz parte da definição da variável. Se uma medição resulta em (v_{ab}=-3	ext{ V}), isso significa que o ponto (b) está três volts acima do ponto (a) segundo a convenção adotada. Tensão negativa não é uma tensão inválida.

Uma notação de nó como

~~~text
V_cpu = 1.0 V
~~~

significa implicitamente em relação a um nó de referência especificado. Essa referência pode ser chamada de terra ou ground, mas o ground de circuito é uma referência de modelagem e não corresponde automaticamente ao terra de proteção.

Tensão mede diferença de energia por unidade de carga:

~~~text
ΔU = q ΔV
~~~

Para uma carga positiva, atravessar uma elevação positiva de potencial aumenta a energia potencial. O movimento de elétrons exige atenção adicional porque sua carga é negativa.

## Corrente é transporte de carga por unidade de tempo

A corrente através de uma superfície orientada escolhida é

~~~text
I = dQ/dt
~~~

Para corrente constante,

~~~text
Q = I t
~~~

Um ampere corresponde a um coulomb por segundo. Usando o valor exato da carga elementar, uma corrente de um ampere corresponde em magnitude a aproximadamente

~~~text
1 / e
≈ 6.241509074 × 10^18
~~~

cargas elementares cruzando a superfície de referência por segundo.

A direção da corrente é uma convenção. Corrente convencional é definida na direção em que uma carga positiva se moveria. Em um metal, os elétrons móveis derivam no sentido oposto. A variável de corrente convencional continua útil porque as equações de componentes e redes são escritas de modo consistente nessa direção de referência.

## Densidade de corrente e transporte microscópico

Uma corrente de ramo comprime o transporte espacial em um escalar. A grandeza mais local é a densidade de corrente (mathbf{J}), medida em A/m². Para densidade uniforme normal a uma área (A),

~~~text
I = J A
~~~

De forma mais geral,

~~~text
I = ∫ J · dA
~~~

Para um modelo simples de portadores com densidade numérica (n), carga do portador (q), área transversal (A) e velocidade média de deriva (v_d),

~~~text
I = n q A v_d
~~~

com o sinal determinado pelas direções escolhidas e pela carga do portador.

Essa relação é um modelo, não uma lei microscópica universal para todos os materiais. Metais, semicondutores, plasmas e eletrólitos diferem em populações de portadores e física de transporte. Capítulos posteriores de semicondutores substituem a imagem simplificada de condutor por estrutura de bandas, deriva, difusão e comportamento de dispositivo dependente de campo.

## Movimento de carga não significa propagação do sinal na velocidade de deriva

A velocidade de deriva dos elétrons em um condutor pode ser muito menor do que a velocidade com que uma perturbação elétrica se propaga pela estrutura eletromagnética. Fechar uma chave não exige que um único elétron viaje da fonte até a carga antes de a carga responder.

Um sinal de circuito está associado a campos eletromagnéticos variáveis e redistribuição distribuída de carga. O modelo concentrado oculta essa propagação quando a estrutura é eletricamente pequena o suficiente. A teoria de linhas de transmissão a restaura quando a geometria e o tempo de subida tornam o atraso de propagação importante.

## Relações de componentes e leis constitutivas

A topologia do circuito sozinha não determina o comportamento. Cada componente também precisa de uma relação constitutiva conectando suas variáveis de terminal.

Para um elemento de dois terminais, escolhem-se polaridade de tensão e direção de corrente. Uma lei de componente pode então relacionar (v(t)), (i(t)), carga, fluxo, temperatura ou estado interno.

Exemplos desenvolvidos posteriormente incluem

~~~text
resistor:      v = R i        no modelo linear ideal
capacitor:     i = C dv/dt
indutor:       v = L di/dt
~~~

Essas equações não são intercambiáveis. Elas representam mecanismos físicos distintos de armazenamento e dissipação.

## Resistência e o resistor ideal

Para um resistor linear ideal,

~~~text
v = R i
~~~

onde (R>0) é constante. Portanto,

~~~text
R = v/i
~~~

para corrente não nula, e a condutância é

~~~text
G = 1/R
i = G v
~~~

A frase "resistência é tensão dividida pela corrente" precisa ser usada com cuidado. Para um dispositivo não linear, a razão (v/i) em um ponto de operação não é necessariamente uma propriedade constante do material/componente e não coincide necessariamente com a inclinação local

~~~text
r_d = dv/di
~~~

Um diodo, MOSFET ou elemento de proteção pode ter uma curva (i)-(v) não linear. A lei de Ohm na forma simples (v=Ri) é um modelo para um elemento ôhmico linear em uma faixa de operação declarada.

## Resistividade e geometria

Para um condutor uniforme que possa ser modelado como ôhmico,

~~~text
R = ρ L / A
~~~

onde

~~~text
ρ   resistividade [Ω·m]
L   comprimento do condutor [m]
A   área da seção transversal [m²]
~~~

Condutores mais longos possuem maior resistência; maior área transversal reduz a resistência. Resistividade é uma propriedade do material somente dentro dos limites do modelo e depende de condições como temperatura, composição e microestrutura.

Um modelo de primeira ordem comum próximo a uma temperatura de referência (T_0) é

~~~text
R(T) ≈ R(T0) [1 + α(T - T0)]
~~~

para uma faixa em que um coeficiente linear de temperatura (alpha) seja adequado. Isso não é universal. O comportamento resistivo de semicondutores pode diferir fortemente das tendências metálicas simples.

## Circuito aberto e curto-circuito são modelos-limite

Um circuito aberto ideal não conduz corrente:

~~~text
i = 0
~~~

enquanto sua tensão pode ser diferente de zero.

Um curto-circuito ideal possui tensão nula entre seus terminais:

~~~text
v = 0
~~~

enquanto sua corrente é determinada pelo restante da rede e pelas restrições da fonte.

Nenhuma dessas idealizações permite atribuições arbitrárias simultâneas. Dizer "um curto tem resistência zero, portanto corrente infinita" omite impedância da fonte, resistência das interconexões, proteções e outras restrições da rede. A relação ideal de resistência nula sozinha não fixa a magnitude da corrente.

## Potência instantânea

Potência é a taxa de transferência de energia:

~~~text
p = dE/dt
~~~

Para um elemento elétrico de dois terminais sob uma convenção de referência consistente,

~~~text
p(t) = v(t) i(t)
~~~

O sinal depende de como a polaridade da tensão e a direção da corrente foram definidas.

### Convenção passiva de sinais

Na convenção passiva de sinais, a corrente é definida entrando pelo terminal marcado como positivo para a tensão.

Então,

~~~text
p > 0   o elemento absorve potência
p < 0   o elemento fornece potência
~~~

Essa convenção permite tratar fontes e cargas com a mesma equação. Uma bateria entregando energia terá (p) negativo sob uma orientação passiva; durante a carga, pode apresentar (p) positivo.

## Energia é a integral da potência

A energia transferida ao longo de um intervalo é

~~~text
E = ∫ p(t) dt
~~~

Para potência constante,

~~~text
E = P t
~~~

Potência e energia não devem ser confundidas. Uma carga de 100 W descreve uma taxa. Operando por 10 s, transfere 1000 J. Um dispositivo pode exigir alta potência instantânea e ainda consumir energia total modesta se o intervalo for curto, ou baixa potência e grande energia acumulada ao longo de um período longo.

Essa distinção torna-se central para modos boost, constantes de tempo térmicas, autonomia de bateria e atividade dinâmica de CMOS.

## Aquecimento Joule em um resistor ideal

Para um resistor linear positivo sob convenção passiva,

~~~text
v = R i
p = v i
~~~

logo

~~~text
p = i² R
p = v² / R
~~~

As duas formas são consequências das mesmas equações e valem sob as mesmas hipóteses de modelo.

Como (R>0) e os quadrados são não negativos, um resistor passivo ideal não pode fornecer potência líquida nesse modelo. A energia elétrica é convertida em energia térmica.

Em escala de dispositivo, a elevação de temperatura depende não apenas da potência elétrica, mas também de capacidade térmica, resistência térmica, geometria, fluxo de ar, encapsulamento e tempo.

## Fontes e cargas

Uma fonte ideal de tensão impõe a tensão de terminal independentemente da corrente exigida pela rede ideal. Uma fonte ideal de corrente impõe a corrente independentemente da tensão de terminal. Fontes reais não conseguem manter essas restrições sem limite.

Desvios relevantes do mundo real incluem

- resistência ou impedância de saída finita;
- limite de corrente;
- queda de tensão;
- eficiência menor que 100%;
- desligamento térmico;
- resposta transitória;
- limites de estabilidade do laço de controle.

Os capítulos de entrega de potência tratam reguladores, desacoplamento e transitórios de rail em maior profundidade. A fronteira importante aqui é que "fonte de 5 V" é um modelo de restrição de terminal, não uma afirmação de capacidade infinita de potência.

## Eficiência e perdas

Se um subsistema recebe potência de entrada (P_{in}) e fornece potência útil de saída (P_{out}),

~~~text
η = P_out / P_in
~~~

para uma condição estacionária com médias compatíveis.

A perda é

~~~text
P_loss = P_in - P_out
~~~

Para um subsistema passivo de conversão, (0 ≤ η ≤ 1). Valores aparentes fora desse intervalo normalmente indicam fronteiras de medição inconsistentes, energia armazenada em transiente, erros de sinal ou médias incompatíveis.

Sistemas digitais distribuem potência por vários estágios de conversão; eficiência e perdas locais importam para dimensionamento da fonte e projeto térmico.

## Sinais variáveis no tempo e médias

A identidade

~~~text
p(t) = v(t)i(t)
~~~

é instantânea.

Para sinais periódicos ou variáveis, a potência média ao longo de um intervalo (T) é

~~~text
P_avg = (1/T) ∫_0^T v(t)i(t) dt
~~~

Em geral,

~~~text
average(v i) != average(v) average(i)
~~~

a menos que condições especiais sejam satisfeitas.

Grandezas RMS, ângulo de fase, potência reativa e potência complexa exigem a estrutura de AC desenvolvida posteriormente. Elas não devem ser importadas para formas de onda arbitrárias sem declarar definições e hipóteses.

## Modelos de medição

Um voltímetro ideal mede diferença de potencial sem drenar corrente: resistência de entrada infinita. Um amperímetro ideal mede corrente de ramo sem queda de tensão: resistência série nula.

Instrumentos reais perturbam o circuito.

| Instrumento | Propriedade ideal | Desvio real importante |
|---|---|---|
| voltímetro | resistência de entrada infinita | resistência/capacitância de entrada finitas |
| amperímetro | resistência série zero | burden voltage e limites do shunt/fusível |
| ponta de osciloscópio | carga desprezível | resistência, capacitância, banda, referência de ground |
| sonda de corrente | idealmente não invasiva | limitações de banda, inserção ou acoplamento magnético |

A medição, portanto, faz parte do modelo de circuito. Uma ponta pode alterar um nó de alta impedância ou alta frequência o suficiente para modificar a própria forma de onda observada.

## Direções de referência e sinais algébricos

Para cada ramo, defina

~~~text
polaridade de tensão
seta de corrente
~~~

antes de resolver o circuito.

Uma solução negativa inverte a direção assumida; não invalida as equações.

Por exemplo, se (i) foi definido de A para B e o cálculo produz

~~~text
i = -2 mA
~~~

a corrente física é 2 mA de B para A em relação à referência escolhida.

É a orientação consistente que permite que as equações de Kirchhoff escalem de um único elemento para redes grandes.

## Representação numérica em modelos de software

Um modelo de circuito ou potência em software precisa escolher representações para grandezas e unidades. Ponto flutuante oferece faixa, mas introduz arredondamento. Ponto fixo oferece escala determinística, mas exige análise explícita de overflow. Inteiros podem representar contagens exatas ou unidades escaladas apenas dentro da própria faixa.

Um modelo seguro deve manter as unidades visíveis em nomes, tipos ou interfaces. Confundir milivolts com volts ou miliamperes com amperes pode produzir erros de fatores de (10^3) ou (10^6).

Para potência calculada,

~~~text
P = V I
~~~

a implementação numérica também precisa considerar a faixa da multiplicação. Dois valores individualmente válidos podem causar overflow quando multiplicados em uma representação de largura fixa.

## Estruturas de dados, estado e propriedade

Este capítulo define variáveis físicas, não um subsistema do ChrisOS. Portanto não existe aqui uma estrutura atual de fonte do ChrisOS, grafo de propriedade, alocador, lock, ABI ou sequência de inicialização a documentar.

Se o ChrisOS futuramente ganhar telemetria de energia, gerenciamento de bateria, controle de reguladores ou um simulador em nível de circuito, essa implementação exigirá um capítulo separado e vinculado à fonte, com arquivos, símbolos, estado, propriedade, concorrência e evidência de validação concretos.

Manter essa fronteira explícita evita que conceitos de circuitos de livro-texto sejam relatados como comportamento atual do kernel.

## Fluxo de controle e dados entre camadas de abstração

A dependência física até o software pode ser representada como

~~~text
fonte elétrica
    ↓
tensão do rail e corrente disponível
    ↓
chaveamento de transistores e comportamento de interconexão
    ↓
lógica sincronizada e estado arquitetural
    ↓
contrato de CPU/dispositivo
    ↓
código do ChrisOS observa registradores, memória e interrupções
~~~

O ChrisOS normalmente atua na extremidade arquitetural dessa cadeia. Queda de tensão ou temperatura excessiva pode eventualmente causar reset, throttling, computação corrompida ou falha de hardware, mas um sintoma de software de alto nível não identifica por si só a causa física.

## Concorrência, privilégio e fronteira de ABI

Tensão, corrente e potência não possuem nível de privilégio de CPU. As leis físicas se aplicam independentemente de ring 0 ou ring 3.

Na fronteira de software, acesso a telemetria de hardware ou registradores de controle de energia pode ser privilegiado, concorrente e sensível a ABI, mas esses mecanismos devem ser documentados a partir da interface real do dispositivo e da implementação do ChrisOS. Nenhum deles é afirmado aqui.

Da mesma forma, as grandezas físicas em si não possuem formato de rede ou em disco. Formatos codificados de telemetria pertencem às especificações que os definem.

## Modos de falha e limites de segurança

Modelos elétricos falham quando suas hipóteses são excedidas.

| Modelo ou operação | Limite de falha |
|---|---|
| (v=Ri) | elemento não linear ou dependente de condição |
| (R=ρL/A) | geometria/material não uniformes ou efeitos dependentes de frequência |
| tensão de nó concentrado | atraso de propagação/parasitismos tornam-se relevantes |
| tensão constante da fonte | limite de corrente, térmico ou de controle é atingido |
| interpretação de (p=vi) | referências de polaridade/corrente inconsistentes |
| potência média | intervalo de média não corresponde ao fenômeno |
| cálculo numérico de potência | unidade incorreta, overflow ou perda de precisão |
| curto/aberto ideal | parasitas reais e limites da fonte dominam |

Trabalho elétrico também possui limites físicos de segurança. Corrente alta pode aquecer condutores e iniciar incêndios; tensão alta pode criar risco de choque e ruptura de isolação. As equações deste capítulo são ferramentas analíticas, não substitutos para procedimentos aplicáveis de segurança de laboratório e equipamentos.

## Desempenho e trade-offs de engenharia

Engenharia elétrica frequentemente troca tensão, corrente, resistência, energia, calor e temporização entre si.

Menor resistência de interconexão reduz queda de tensão e perdas (I^2R), mas pode exigir trilhas mais largas, mais área de cobre ou condutores mais pesados. Menor tensão de alimentação pode reduzir energia de chaveamento CMOS, porém margens de tempo e ruído limitam até onde a tensão pode cair. Maior capacidade de corrente pode melhorar resposta transitória, mas aumenta requisitos de regulador, conectores e dissipação térmica.

A camada de sistema operacional percebe os resultados através de contratos de hardware, e não por meio dessas equações diretamente, mas o desempenho do sistema depende, em última instância, desses limites físicos.

## Evidência de validação

O checker executável associado verifica exemplos determinísticos para

- coulombs transportados por corrente constante;
- cargas elementares por segundo em um ampere;
- (R=V/I) para um resistor linear;
- (R=ρL/A);
- (P=VI);
- identidades equivalentes do resistor (P=I^2R=V^2/R);
- energia proveniente de potência constante ao longo do tempo;
- interpretação da convenção passiva de sinais;
- âncoras obrigatórias nos capítulos bilíngues.

Essas verificações validam aritmética e invariantes da documentação. Elas não são simulação SPICE, caracterização de dispositivos, certificação de segurança ou teste de conformidade de hardware.

## Limitações atuais

Este capítulo termina deliberadamente antes da solução de redes e do comportamento dinâmico reativo. Ele ainda não deriva

- leis de corrente e tensão de Kirchhoff como solucionador de rede;
- redes de resistências equivalentes;
- redução de Thévenin ou Norton;
- transitórios de capacitores ou indutores;
- impedância senoidal e fase;
- linhas de transmissão;
- equações (i)-(v) de dispositivos semicondutores;
- laços de controle de reguladores;
- telemetria concreta ou código de gerenciamento de energia do ChrisOS.

Esses tópicos possuem IDs separados no currículo para que suas hipóteses e evidências de implementação permaneçam explícitas.

## Fronteira do roadmap

Os capítulos futuros usam esta fundação para construir a sequência

~~~text
tensão/corrente/resistência/potência
    ↓
Ohm + Kirchhoff para análise de redes
    ↓
armazenamento em C/L e transitórios
    ↓
impedância AC e resposta em frequência
    ↓
integridade de sinal e entrega de potência
    ↓
energia e temporização de chaveamento CMOS
~~~

Um futuro subsistema de gerenciamento de energia do ChrisOS, caso implementado, deverá ser documentado a partir da fonte e das especificações de hardware, não retroativamente atribuído a este capítulo de física.

## Proveniência da revisão

Revisado contra o `main` do ChrisOS na revisão `da3df29cb397932c43d32373871fb9380e688ade`.

`sources` e `symbols` estão intencionalmente vazios porque este capítulo não faz afirmações sobre a implementação atual do ChrisOS. A revisão registrada preserva a proveniência do corpus e a fronteira de implementação. As referências metrológicas primárias foram verificadas no SI Brochure do BIPM, 9ª edição, versão 4.01 (junho de 2026), e nas definições atuais do SI publicadas pelo NIST.
