---
id: ac-signals-frequency-impedance
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - rc-rlc-transients
  - vectors-complex-numbers-systems
related:
  - electromagnetic-induction-transformers
  - transmission-lines-differential-signals
  - noise-grounding-signal-integrity
  - power-delivery-regulation
  - cmos-switching-power
---

# Sinais AC, fase, frequência e impedância

<div class="abstract">
A análise de regime senoidal converte equações diferenciais lineares de circuitos em álgebra sobre números complexos. Frequência, fase, valor RMS, fasores, impedância e admitância permitem resolver resistores, capacitores e indutores com os mesmos métodos de rede usados em DC, preservando o significado físico da energia armazenada e dissipada. Este capítulo deriva o método fasorial, impedância complexa, ressonância, funções de transferência, resposta em frequência, potência complexa passiva, comportamento de filtros, representação numérica e os limites dos modelos de regime senoidal.
</div>

## Pré-requisitos e escopo

Este capítulo assume:

- números complexos e identidade de Euler;
- lei de Ohm, KCL e KVL;
- equações constitutivas de capacitores e indutores;
- comportamento transitório de primeira e segunda ordem;
- distinção entre resposta natural e forçada.

A análise é restrita a **circuitos lineares invariantes no tempo em regime senoidal permanente**, salvo indicação explícita.

Essa expressão contém três hipóteses:

~~~text
linear
    superposição é válida

invariante no tempo
    parâmetros dos componentes não mudam com o tempo

regime permanente
    transitórios naturais decaíram ou são intencionalmente excluídos
~~~

O método não substitui a física no domínio do tempo. Ele é uma representação compacta da resposta de longo prazo à excitação senoidal.

O código atual do ChrisOS não implementa o analisador de circuitos AC descrito aqui.

## Período, frequência e frequência angular

Para um sinal periódico com período (T):

~~~text
f = 1/T
~~~

onde (f) é medido em hertz.

O SI Brochure do BIPM define:

~~~text
1 Hz = 1 s^-1
~~~

A frequência angular é:

~~~text
ω = 2πf
~~~

com unidade rad/s.

Embora o radiano seja adimensional na álgebra dimensional do SI, escrever rad/s ajuda a distinguir frequência angular de ciclos por segundo.

A revisão de 2026 do SI Brochure permanece a referência metrológica para essas unidades derivadas.

## Sinais senoidais

Uma tensão senoidal pode ser escrita:

~~~text
v(t)
=
V_m cos(ωt + φ)
~~~

onde:

~~~text
V_m   amplitude de pico
ω     frequência angular
φ     ângulo de fase
~~~

Formas equivalentes em seno e cosseno diferem apenas por deslocamento de fase.

O sinal se repete após:

~~~text
T = 2π/ω
~~~

O ângulo de fase indica a posição da forma de onda dentro do ciclo em relação a uma referência escolhida.

Fase absoluta sem referência tem significado limitado; a diferença de fase costuma ser a grandeza fisicamente relevante.

## Diferença de fase

Para duas senoides de mesma frequência:

~~~text
v1(t) = A cos(ωt + φ1)
v2(t) = B cos(ωt + φ2)
~~~

a diferença de fase é:

~~~text
Δφ = φ2 - φ1
~~~

Se (Deltaphi>0), a forma de onda 2 adianta a forma de onda 1 na convenção usual.

Se (Deltaphi<0), a forma de onda 2 atrasa.

A diferença de fase também corresponde a um deslocamento temporal:

~~~text
Δt = Δφ / ω
~~~

quando a fase é expressa em radianos.

Como a fase é periódica módulo (2π), qualquer valor reportado deve ser interpretado com uma escolha de ramo e frequência.

## Pico, pico a pico e RMS

Para uma senoide de média zero:

~~~text
v(t)=V_m cos(ωt+φ)
~~~

o valor de pico é (V_m).

O valor pico a pico é:

~~~text
V_pp = 2 V_m
~~~

O valor RMS é:

~~~text
V_rms
=
sqrt[
(1/T) ∫_0^T v²(t) dt
]
~~~

que resulta em:

~~~text
V_rms = V_m / sqrt(2)
~~~

Da mesma forma:

~~~text
I_rms = I_m / sqrt(2)
~~~

para uma corrente senoidal.

RMS não significa "média do módulo". É a raiz quadrada da média do quadrado e é especialmente útil porque um resistor dissipa a mesma potência média sob um valor RMS senoidal e sob um valor DC de mesma magnitude.

## Valor médio e dependência da forma de onda

Para uma senoide de média zero ao longo de um período completo:

~~~text
average(v) = 0
~~~

mas:

~~~text
V_rms != 0
~~~

Relações RMS dependem da forma de onda.

Por exemplo, (V_m/sqrt{2}) é específico de senoides. Onda quadrada, trem de pulsos ou sinal periódico distorcido possuem relações pico/RMS diferentes.

Isso importa para formas de onda digitais e reguladores chaveados, que não são normalmente sinais de uma única frequência.

## Representação por exponencial complexa

A identidade de Euler fornece:

~~~text
e^(jθ) = cos θ + j sin θ
~~~

Uma senoide real pode ser representada como a parte real de uma exponencial complexa rotativa:

~~~text
v(t)
=
Re{ V_m e^(jφ) e^(jωt) }
~~~

Defina a amplitude complexa:

~~~text
V_hat = V_m e^(jφ)
~~~

Então:

~~~text
v(t)=Re{V_hat e^(jωt)}
~~~

Como todo sinal de uma rede linear em regime senoidal compartilha o fator (e^{jωt}), as equações podem ser resolvidas usando apenas amplitudes complexas.

Esse é o núcleo do método fasorial.

## Convenção de fasor

Um fasor pode usar magnitude de pico ou RMS.

Ambas as convenções são válidas se forem mantidas de forma consistente.

Este capítulo usa **fasores RMS** em cálculos de potência e identifica explicitamente grandeza de pico ao derivar sinais no tempo.

Um fasor RMS pode ser escrito:

~~~text
V = V_rms ∠φ
~~~

ou em forma retangular:

~~~text
V = V_rms(cosφ + j sinφ)
~~~

Conversão:

~~~text
retangular:
    a + jb

polar:
    M ∠φ

M = sqrt(a²+b²)
φ = atan2(b,a)
~~~

## Derivação no domínio fasorial

Para:

~~~text
x(t)
=
Re{X e^(jωt)}
~~~

a derivada é:

~~~text
dx/dt
=
Re{jωX e^(jωt)}
~~~

Portanto, em regime senoidal:

~~~text
d/dt
    ↔
jω
~~~

Integração corresponde a:

~~~text
∫ dt
    ↔
1/(jω)
~~~

quando componentes constantes independentes de integração são excluídas; elas pertencem à resposta natural/DC não representada pelo fasor de regime.

## Impedância do resistor

Para um resistor:

~~~text
v = Ri
~~~

e em fasores:

~~~text
V = R I
~~~

Logo:

~~~text
Z_R = R
~~~

Um resistor ideal positivo possui fase nula:

~~~text
∠Z_R = 0
~~~

Tensão e corrente estão em fase.

## Impedância do indutor

Para um indutor ideal:

~~~text
v = L di/dt
~~~

Aplicando a derivada fasorial:

~~~text
V = jωL I
~~~

Logo:

~~~text
Z_L = jωL
~~~

Magnitude:

~~~text
|Z_L| = ωL
~~~

Fase:

~~~text
∠Z_L = +90°
~~~

Assim, a tensão adianta a corrente em (90^circ), ou a corrente atrasa a tensão.

No limite DC (omega	o0), a impedância do indutor ideal tende a zero, coerente com o modelo de curto em regime permanente.

## Impedância do capacitor

Para um capacitor ideal:

~~~text
i = C dv/dt
~~~

portanto:

~~~text
I = jωC V
~~~

e:

~~~text
Z_C
=
V/I
=
1/(jωC)
=
-j/(ωC)
~~~

Magnitude:

~~~text
|Z_C| = 1/(ωC)
~~~

Fase:

~~~text
∠Z_C = -90°
~~~

A corrente adianta a tensão em (90^circ).

Quando (omega	o0), a magnitude da impedância tende ao infinito, coerente com o circuito aberto DC.

## Impedância e admitância

Impedância generaliza resistência:

~~~text
Z = V/I
~~~

com unidade ohm.

Escreva:

~~~text
Z = R + jX
~~~

onde:

~~~text
R   resistência
X   reatância
~~~

Para elementos ideais passivos:

~~~text
X_L = +ωL
X_C = -1/(ωC)
~~~

Admitância é:

~~~text
Y = 1/Z
~~~

com unidade siemens.

Escreva:

~~~text
Y = G + jB
~~~

onde (G) é condutância e (B) susceptância.

Admitância costuma simplificar redes em paralelo, assim como condutância simplifica resistores paralelos.

## KCL e KVL com fasores

Como a transformação fasorial é linear, as leis de Kirchhoff preservam a forma algébrica.

KCL:

~~~text
Σ I_k = 0
~~~

KVL:

~~~text
Σ V_k = 0
~~~

As relações constitutivas tornam-se:

~~~text
V = Z I
~~~

Logo análise nodal pode usar matrizes complexas de admitância:

~~~text
Y V = I
~~~

Os algoritmos são estruturalmente semelhantes à análise nodal DC, exceto pela aritmética complexa e pela dependência dos elementos com a frequência.

## Impedância em série

Para elementos em série, a corrente é comum e as tensões somam:

~~~text
Z_eq = Σ Z_k
~~~

Para RLC série:

~~~text
Z
=
R
+
jωL
+
1/(jωC)
~~~

que se simplifica para:

~~~text
Z
=
R
+
j[
ωL - 1/(ωC)
]
~~~

Magnitude:

~~~text
|Z|
=
sqrt{
R²
+
[ωL - 1/(ωC)]²
}
~~~

Fase:

~~~text
φ_Z
=
atan2(
ωL - 1/(ωC),
R
)
~~~

## Admitância em paralelo

Em paralelo, a tensão é comum e as correntes somam.

Portanto:

~~~text
Y_eq = Σ Y_k
~~~

Para R, L e C ideais em paralelo:

~~~text
Y
=
1/R
+
1/(jωL)
+
jωC
~~~

ou:

~~~text
Y
=
1/R
+
j[
ωC - 1/(ωL)
]
~~~

A análise paralela costuma ser mais clara em admitância do que usando recíprocos de impedâncias repetidamente.

## Ressonância série

Em um RLC série, a ressonância ocorre quando a reatância líquida é zero:

~~~text
ωL - 1/(ωC) = 0
~~~

Logo:

~~~text
ω_0 = 1/sqrt(LC)
~~~

e:

~~~text
f_0 = 1/(2πsqrt(LC))
~~~

Na ressonância ideal:

~~~text
Z = R
~~~

e a magnitude da corrente é máxima para uma fonte senoidal de tensão fixa, com (R>0).

Embora a corrente da fonte seja limitada por (R), as tensões individuais sobre capacitor e indutor podem superar muito a tensão da fonte quando (Q) é elevado.

## Ressonância paralela

Uma rede RLC paralela ideal ressona quando a susceptância líquida é zero:

~~~text
ωC - 1/(ωL) = 0
~~~

produzindo o mesmo valor ideal:

~~~text
ω_0 = 1/sqrt(LC)
~~~

Na ressonância, correntes reativas de ramo podem ser grandes enquanto a corrente líquida da fonte diminui.

Ressonadores paralelos reais possuem perdas e parasitas; frequência de ressonância e pico de impedância dependem da topologia prática.

## Fator Q no RLC série

Para o modelo RLC série ideal na ressonância:

~~~text
Q
=
ω_0 L/R
=
1/(ω_0 R C)
=
(1/R)sqrt(L/C)
~~~

Para amortecimento fraco:

~~~text
Q ≈ 1/(2ζ)
~~~

onde (zeta) é a razão de amortecimento do capítulo de transitórios.

Isso conecta decaimento temporal à seletividade em frequência.

Q mais alto geralmente implica:

- ressonância mais estreita;
- decaimento mais lento da energia oscilatória;
- maior energia reativa relativa à dissipação por ciclo.

## Relação de largura de banda

Para uma ressonância RLC série canônica, a largura de banda de meia potência é:

~~~text
Δω = R/L
~~~

e:

~~~text
Q = ω_0 / Δω
~~~

sob o modelo ideal.

Os pontos de meia potência ocorrem quando a potência dissipada no resistor cai à metade do máximo de ressonância para uma fonte de tensão constante.

Relações equivalentes dependem da topologia e definição e não devem ser transferidas cegamente para filtros arbitrários.

## Funções de transferência

Um circuito linear pode ser descrito por:

~~~text
H(jω)
=
V_out(jω)/V_in(jω)
~~~

ou outra razão de saída/entrada escolhida.

A resposta de magnitude é:

~~~text
|H(jω)|
~~~

e a resposta de fase:

~~~text
∠H(jω)
~~~

A função de transferência descreve a relação forçada de regime senoidal.

Ela não codifica, por si só, condições iniciais arbitrárias; estas pertencem à solução temporal completa ou à transformada de Laplace com termos iniciais.

## Filtro passa-baixas RC

Para um resistor em série seguido por capacitor ao nó de referência, com saída sobre o capacitor:

~~~text
Z_C = 1/(jωC)
~~~

O divisor de tensão fornece:

~~~text
H(jω)
=
Z_C/(R+Z_C)
=
1/(1+jωRC)
~~~

Magnitude:

~~~text
|H|
=
1/sqrt(1+(ωRC)²)
~~~

Fase:

~~~text
φ
=
-atan(ωRC)
~~~

A frequência angular de corte é:

~~~text
ω_c = 1/(RC)
~~~

e:

~~~text
f_c = 1/(2πRC)
~~~

No corte:

~~~text
|H| = 1/sqrt(2)
~~~

correspondendo a aproximadamente (-3.0103) dB em razão de tensão compatível com potência para impedâncias equivalentes.

## Filtro passa-altas RC

Para um capacitor em série seguido por resistor ao nó de referência, com saída sobre o resistor:

~~~text
H(jω)
=
jωRC/(1+jωRC)
~~~

Magnitude:

~~~text
|H|
=
ωRC/sqrt(1+(ωRC)²)
~~~

A fase tende de (+90^circ) em frequência muito baixa para (0^circ) em frequência alta.

A mesma frequência:

~~~text
ω_c = 1/(RC)
~~~

marca a região de transição.

## Decibéis

Uma razão de amplitude adimensional (A) pode ser expressa como:

~~~text
20 log10 |A| dB
~~~

quando (A) é uma razão de amplitude de tensão/corrente sob hipóteses compatíveis de impedância.

Uma razão de potência usa:

~~~text
10 log10(P2/P1) dB
~~~

A diferença entre os fatores existe porque potência frequentemente escala com o quadrado da amplitude.

Decibéis são razões logarítmicas, não unidades físicas absolutas salvo quando associados a uma referência específica, como dBm.

## Assíntotas de Bode

Para um passa-baixas de primeira ordem:

~~~text
H(s)=1/(1+s/ω_c)
~~~

a magnitude é aproximadamente:

~~~text
0 dB/década
    abaixo do canto

-20 dB/década
    bem acima do canto
~~~

Um passa-altas de primeira ordem apresenta a inclinação oposta em baixa frequência.

Cada polo simples contribui aproximadamente (-20) dB/década acima da frequência de quebra; cada zero simples contribui aproximadamente (+20) dB/década.

A resposta exata nas proximidades dos cantos difere das assíntotas lineares.

## Interpretação por polos e zeros

Uma função racional pode ser escrita conceitualmente:

~~~text
H(s)
=
K
Π(s-z_k)
/
Π(s-p_k)
~~~

onde (z_k) são zeros e (p_k) polos.

A avaliação em:

~~~text
s = jω
~~~

fornece a resposta senoidal em frequência.

Polos próximos do eixo imaginário produzem forte seletividade e decaimento lento no tempo.

Os mesmos polos que governam transitórios RLC governam a ressonância AC.

## Potência média em sinais senoidais

Considere:

~~~text
v(t)=sqrt(2)V_rms cos(ωt+φ_v)
i(t)=sqrt(2)I_rms cos(ωt+φ_i)
~~~

Defina:

~~~text
φ = φ_v - φ_i
~~~

A potência real média é:

~~~text
P
=
V_rms I_rms cosφ
~~~

Para resistor puro:

~~~text
φ = 0
P = V_rms I_rms
~~~

Para indutor ou capacitor ideal puro:

~~~text
|φ| = 90°
P = 0
~~~

porque a energia é alternadamente armazenada e devolvida com média líquida zero em um ciclo.

## Potência complexa

Usando fasores RMS e convenção passiva:

~~~text
S = V I*
~~~

onde (I^*) é o conjugado complexo da corrente.

Escreva:

~~~text
S = P + jQ
~~~

onde:

~~~text
P   potência real/ativa [W]
Q   potência reativa [var]
|S| potência aparente [VA]
~~~

Em regime senoidal:

~~~text
P = V_rms I_rms cosφ
Q = V_rms I_rms sinφ
|S| = V_rms I_rms
~~~

Na convenção passiva comum:

~~~text
carga indutiva: Q > 0
carga capacitiva: Q < 0
~~~

## Fator de potência

Para tensão e corrente senoidais:

~~~text
PF = P/|S| = cosφ
~~~

Fator de potência de baixa magnitude exige maior corrente RMS para uma dada potência real, mantendo tensão RMS fixa.

Para formas de onda distorcidas e não senoidais, o ângulo de deslocamento sozinho não basta. O fator de potência total também depende da distorção harmônica.

Portanto (PF=cosphi) deve ser identificado como caso senoidal, não como regra universal.

## Troca de energia reativa

Potência reativa não significa "potência que não faz nada".

Capacitores e indutores trocam energia com a fonte e entre si.

Para elementos ideais, a potência real média em um ciclo é zero, mas a potência instantânea não é.

Corrente reativa ainda causa:

- perdas (I²R) em condutores reais;
- esforço de corrente em fontes e conversores;
- queda de tensão em impedâncias não nulas.

Por isso compensação reativa importa em sistemas AC mesmo que o componente reativo ideal não dissipe potência média.

## Resposta em frequência e resposta transitória

Descrições temporal e frequencial são duas visões da mesma dinâmica linear.

Para passa-baixas de primeira ordem:

~~~text
domínio do tempo:
    τ = RC

domínio da frequência:
    ω_c = 1/(RC)
~~~

logo:

~~~text
ω_c = 1/τ
~~~

Em sistemas de segunda ordem, razão de amortecimento e frequência natural se relacionam da mesma forma com formato da ressonância e posição dos polos.

Não é possível escolher resposta temporal e frequencial de forma arbitrariamente independente; ambas surgem dos mesmos polos e zeros.

## Contexto da série de Fourier

Uma forma de onda periódica suficientemente bem comportada pode ser representada por soma de senoides:

~~~text
x(t)
=
a0
+
Σ[
a_n cos(nω0 t)
+
b_n sin(nω0 t)
]
~~~

Um circuito linear pode processar cada harmônica separadamente e somar as respostas.

Isso torna resposta em frequência útil mesmo para sinais periódicos não senoidais.

Porém:

- circuitos não lineares geram novas frequências;
- descontinuidades de chaveamento podem exigir muitas harmônicas;
- efeitos distribuídos podem se tornar importantes nas harmônicas altas.

## Contexto da transformada de Fourier

Sinais aperiódicos podem ser representados por espectro contínuo sob condições adequadas.

A transformada de Fourier mapeia conceitualmente:

~~~text
forma de onda no tempo
    ↔
espectro em frequência
~~~

Para sistemas lineares invariantes no tempo:

~~~text
Y(jω)
=
H(jω) X(jω)
~~~

Essa relação fundamenta filtragem, análise de canais e integridade de sinal.

A teoria completa de transformadas vai além do método de circuitos senoidais necessário aqui.

## Fronteira de amostragem e aliasing

Se uma forma de onda analógica é amostrada em software ou hardware, a interpretação em frequência precisa considerar a amostragem.

Para um sinal idealmente limitado em banda, com maior frequência (f_{max}), reconstrução exige taxa acima do dobro dessa banda na condição de Nyquist-Shannon:

~~~text
f_s > 2 f_max
~~~

Filtros antialias reais, abertura finita e sinais não limitados em banda complicam essa afirmação ideal.

Isso é relevante para telemetria e osciloscópios, mas não representa uma afirmação sobre código atual de amostragem no ChrisOS.

## Análise nodal complexa

Um solver no domínio da frequência pode montar uma matriz complexa de admitância em cada frequência.

Para um ramo entre nós (a) e (b) com admitância (Y), o stamp contribui:

~~~text
A[a,a] += Y
A[b,b] += Y
A[a,b] -= Y
A[b,a] -= Y
~~~

A equação matricial é:

~~~text
A(ω) V(ω) = b(ω)
~~~

Como admitâncias de capacitores e indutores dependem de (omega), uma varredura altera valores numéricos mesmo quando a topologia permanece fixa.

O solver pode reutilizar a estrutura de esparsidade e recalcular a fatoração numérica.

## Varreduras de frequência

Uma varredura logarítmica é comum porque sistemas eletrônicos frequentemente cobrem várias décadas.

Exemplo:

~~~text
10 Hz
100 Hz
1 kHz
10 kHz
...
~~~

Em cada ponto:

~~~text
montar/atualizar matriz complexa
resolver
medir grandezas solicitadas
registrar magnitude e fase
~~~

O custo computacional é aproximadamente o custo de uma solução complexa multiplicado pelo número de frequências, com possibilidade de reutilização simbólica da esparsidade.

## Problemas numéricos em aritmética complexa

A solução complexa herda problemas usuais de álgebra linear:

- matrizes singulares;
- mau condicionamento;
- separação extrema de escalas;
- cancelamento;
- overflow/underflow.

Problemas adicionais incluem wrapping de fase e escolhas de ramo.

Por exemplo:

~~~text
+179°
-179°
~~~

pode representar uma variação física suave de apenas (2^circ) após desembrulhar a fase.

Software numérico deve separar a fase principal bruta da apresentação contínua desembrulhada.

## Representação em software

Um fasor genérico pode usar:

~~~text
Complex {
    real
    imag
}
~~~

ou magnitude/fase.

Forma retangular é geralmente melhor para soma e solução de sistemas lineares.

Forma polar é conveniente para interpretação, multiplicação e divisão.

Conversões devem usar:

~~~text
magnitude = hypot(real, imag)
phase     = atan2(imag, real)
~~~

em vez de arctan simples de imag/real, que perde informação de quadrante.

Essas são práticas numéricas gerais, não afirmações sobre implementação do ChrisOS.

## Memória e propriedade em um solver de frequência

Um solver genérico pode possuir:

~~~text
topologia
padrão de matriz esparsa
valores dependentes de frequência
lado direito
vetor solução
definições de medição
~~~

A topologia pode permanecer imutável ao longo da varredura enquanto valores numéricos mudam.

Paralelizar frequências independentes costuma ser direto porque cada ponto é independente, desde que cada worker possua estado numérico isolado ou armazenamento seguro de fatoração.

Novamente, isso descreve arquitetura genérica de solver.

## Trade-offs de desempenho

Análise em frequência é eficiente quando:

- o sistema é linear;
- o interesse está no regime permanente;
- seriam necessários muitos ciclos no tempo;
- apenas frequências selecionadas são relevantes.

Simulação temporal é preferível quando:

- chaveamento é não linear;
- condições iniciais importam;
- eventos são aperiódicos;
- saturação ou clipping ocorrem;
- a forma de onda completa é central.

Nenhum domínio é universalmente superior.

## Componentes reais e dependência de frequência

R, L e C ideais possuem parâmetros constantes.

Componentes reais possuem modelos dependentes de frequência.

Exemplos:

~~~text
capacitor:
    ESR + ESL + perda dielétrica

indutor:
    resistência do enrolamento + perda de núcleo + C parasita

resistor:
    L/C parasitas + efeito pelicular em alta frequência
~~~

Um componente pode ultrapassar sua autorressonância e se comportar de modo diferente do rótulo de baixa frequência.

A análise em frequência é tão boa quanto o modelo do componente.

## Fronteira de linha de transmissão

O método concentrado de impedância assume que as dimensões são eletricamente pequenas o suficiente para um único potencial representar cada segmento de condutor.

Quando o atraso de propagação se torna comparável à temporização do sinal, um modelo distribuído é necessário.

Uma linha de transmissão usa parâmetros por unidade de comprimento:

~~~text
R'
L'
G'
C'
~~~

e suporta ondas viajantes, reflexões e impedância característica.

O capítulo correspondente desenvolve esses efeitos.

## Relevância para integridade de sinal

Bordas digitais possuem espectro amplo.

Um clock nominal de "100 MHz" pode exigir modelagem muito acima de 100 MHz porque o tempo de subida determina o conteúdo de alta frequência.

A resposta em frequência ajuda a localizar:

- ressonâncias;
- atenuação;
- distorção de fase;
- acoplamento;
- picos de impedância da distribuição de potência.

A frequência de engenharia relevante nem sempre é a frequência de repetição impressa na especificação digital.

## Relevância para entrega de potência

Uma rede de distribuição de potência é frequentemente caracterizada por impedância versus frequência:

~~~text
Z_PDN(f)
~~~

Elementos diferentes dominam em faixas diferentes:

~~~text
regulador/laço de controle
    baixa frequência

capacitores bulk
    baixa-média frequência

MLCC/desacoplamento local
    média-alta frequência

parasitas de encapsulamento/die
    alta frequência
~~~

Ressonâncias e anti-ressonâncias podem aumentar a impedância em frequências específicas.

O capítulo dedicado de power delivery desenvolverá esses conceitos a partir desta fundação.

## Relação com o ChrisOS

O ChrisOS normalmente observa hardware por interfaces arquiteturais digitais, e não manipulando fasores.

Ainda assim, comportamento AC e em frequência está por trás de:

- distribuição de clock;
- links seriais;
- barramentos de memória;
- redes de alimentação;
- osciladores;
- front-ends de sensores analógicos;
- comportamento EMI/EMC.

O código atual do ChrisOS não fornece o solver genérico fasorial descrito neste capítulo.

Qualquer futura implementação de telemetria, DSP ou análise de hardware deve ser documentada a partir de arquivos-fonte concretos e especificações dos dispositivos.

## Fronteira de privilégio, concorrência e ABI

Frequência, fase e impedância não possuem nível de privilégio de CPU.

Software que mede ou calcula essas grandezas pode possuir:

- APIs de amostragem;
- propriedade de buffers;
- sincronização;
- contratos de formato numérico;
- ABIs de registradores de dispositivos.

Esses contratos são específicos da implementação e não podem ser inferidos das equações de circuitos.

Nenhuma ABI atual desse tipo é atribuída ao ChrisOS aqui.

## Modos de falha

| Falha | Consequência |
|---|---|
| misturar fasores de pico e RMS | erros por (sqrt2) ou fator 2 em potência |
| confundir graus e radianos | conversão fase/tempo incorreta |
| usar impedância senoidal para condições iniciais transitórias | resposta natural é perdida |
| aplicar (PF=cosphi) a formas distorcidas | fator de potência total incorreto |
| ignorar parasitas | ressonância/comportamento de alta frequência incorretos |
| usar modelo concentrado além do limite de propagação | reflexões/efeitos distribuídos omitidos |
| calcular fase sem atan2 | quadrante errado |
| não desembrulhar fase | descontinuidades artificiais em gráficos |
| matriz nodal complexa singular | rede flutuante/inconsistente |
| varredura de frequência esparsa demais | ressonâncias estreitas podem ser perdidas |

## Evidência de validação

O checker executável deste batch verifica exemplos determinísticos de:

- conversão período/frequência/frequência angular;
- RMS senoidal e pico a pico;
- conversão de fase em deslocamento temporal;
- impedância de resistor, capacitor e indutor;
- ressonância RLC série;
- magnitude e fase do passa-baixas RC no corte;
- magnitude do passa-altas RC no corte;
- conversão para decibéis em (1/sqrt2);
- potência real, reativa, aparente e fator de potência;
- equivalência entre (omega_c=1/RC) e (1/	au);
- aritmética nodal complexa em pequena rede;
- âncoras bilíngues da documentação.

As verificações validam equações e invariantes editoriais, não um analisador de impedância calibrado ou sistema de medição RF.

## Limitações atuais

Este capítulo termina antes de:

- modelos de relação de espiras e magnetização de transformadores;
- equações de onda em linhas de transmissão;
- parâmetros S;
- radiação eletromagnética;
- geração harmônica não linear;
- partida de osciladores;
- análise de PLL/laços de controle;
- implementação concreta AC/DSP no ChrisOS.

Esses assuntos exigem evidência adicional de dispositivos, campos ou software.

## Fronteira do roadmap

A cadeia conceitual agora é:

~~~text
dinâmica R/C/L no tempo
    ↓
regime senoidal
    ↓
fasores e impedância complexa
    ↓
resposta em frequência e ressonância
    ↓
indução/transformadores
    ↓
linhas de transmissão e sinalização diferencial
    ↓
ruído, aterramento e integridade de sinal
    ↓
impedância de entrega de potência
~~~

O método fasorial permanece válido apenas dentro das hipóteses de linearidade e regime senoidal.

## Proveniência da revisão

Revisado contra o `main` do ChrisOS na revisão `da3df29cb397932c43d32373871fb9380e688ade`.

`sources` e `symbols` estão intencionalmente vazios porque este capítulo não afirma que o ChrisOS atual implemente um solver fasorial, de impedância ou de circuitos no domínio da frequência. A revisão registra a proveniência do corpus e a fronteira de implementação. As referências metrológicas foram verificadas no SI Brochure do BIPM, 9ª edição, atualizado em junho de 2026.
