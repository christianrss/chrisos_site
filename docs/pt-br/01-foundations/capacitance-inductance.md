---
id: capacitance-inductance
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - ohm-kirchhoff-circuits
related:
  - rc-rlc-transients
  - ac-signals-frequency-impedance
  - electromagnetic-induction-transformers
  - transmission-lines-differential-signals
  - power-delivery-regulation
  - cmos-switching-power
---

# Capacitância, indutância e energia armazenada em campos

<div class="abstract">
Resistores dissipam energia elétrica; capacitores e indutores a armazenam em campos elétricos e magnéticos. Suas relações constitutivas introduzem estado e dependência temporal na análise de circuitos. Este capítulo deriva relações carga-tensão e fluxo-corrente, fórmulas de energia de campo, combinações equivalentes, restrições de condição inicial, comportamento parasita, realizações físicas, representação numérica de estado e os limites dos modelos concentrados ideais de C/L antes da análise transitória e AC.
</div>

## Pré-requisitos e escopo

Os capítulos anteriores estabeleceram tensão, corrente, potência, lei de Ohm, KCL, KVL e análise linear de redes resistivas.

Uma rede puramente resistiva não possui memória ideal: uma vez especificados os valores das fontes independentes, o ponto de operação é determinado algebricamente.

Capacitores e indutores mudam isso.

Seu comportamento terminal atual depende do estado armazenado em campos:

~~~text
estado do capacitor
    carga / campo elétrico
    representado pela tensão

estado do indutor
    fluxo magnético concatenado
    representado pela corrente
~~~

Isso torna equações diferenciais inevitáveis.

Este capítulo deriva as relações de armazenamento e seus limites físicos. Soluções explícitas de transitórios RC, RL e RLC pertencem ao próximo capítulo; impedância senoidal e fasores pertencem ao capítulo de AC.

Nenhuma implementação atual do ChrisOS é afirmada aqui.

## Capacitor: ideia física

Um capacitor consiste conceitualmente em dois condutores separados por uma região isolante ou dielétrica.

Transferir carga de um condutor ao outro cria:

- cargas líquidas opostas nos condutores;
- campo elétrico na região entre eles;
- diferença de potencial entre os condutores;
- energia armazenada no campo elétrico.

Para um capacitor linear,

~~~text
Q = C V
~~~

onde

~~~text
Q   magnitude da carga em um dos condutores [C]
C   capacitância [F]
V   tensão terminal [V]
~~~

Um farad é

~~~text
1 F = 1 C/V
~~~

Capacitância é uma propriedade geométrica e material sob o modelo escolhido. Não é "a quantidade de carga" e não é, por si só, energia.

## Capacitor de placas paralelas

Para duas placas paralelas grandes, de área (A), separação (d) e permissividade dielétrica (epsilon), desprezando campos de borda,

~~~text
C = ε A / d
~~~

Essa relação ideal expõe as dependências de projeto:

- maior área de placa aumenta a capacitância;
- menor separação aumenta a capacitância;
- maior permissividade aumenta a capacitância.

A aproximação falha quando as dimensões das placas não são grandes comparadas à separação, quando campos de borda dominam, quando o dielétrico é não linear ou quando a geometria é mais complexa.

Capacitâncias em circuitos integrados surgem em junções, estruturas de gate, acoplamento entre interconexões e várias outras geometrias; nem toda capacitância se parece com um componente discreto de placas paralelas.

## Dielétricos e polarização

Um dielétrico altera a relação entre campo elétrico e carga armazenada por meio da polarização do material.

Em um material linear isotrópico simples,

~~~text
D = ε E
~~~

onde (D) é deslocamento elétrico e (E) é campo elétrico.

O comportamento de dielétricos reais pode depender de:

- frequência;
- temperatura;
- intensidade do campo;
- processo de fabricação;
- envelhecimento;
- esforço mecânico.

Perdas e absorção dielétrica significam que um capacitor real nem sempre pode ser representado por um único (C) ideal.

O capacitor linear ideal permanece como primeiro modelo fundamental porque sua equação de estado é simples e poderosa.

## Relação de corrente do capacitor

Parta de

~~~text
Q = C V
~~~

para (C) constante.

Corrente é

~~~text
i = dQ/dt
~~~

portanto

~~~text
i = C dV/dt
~~~

sob convenção passiva de sinais.

Equivalentemente,

~~~text
dV/dt = i/C
~~~

e a integração fornece

~~~text
V(t)
=
V(t0)
+
(1/C) ∫[t0..t] i(τ) dτ
~~~

A tensão inicial (V(t0)) faz parte do estado.

Essa é a primeira diferença importante em relação a um resistor: a tensão terminal não pode ser determinada apenas pela corrente instantânea sem conhecer o histórico ou a condição inicial.

## Continuidade da tensão do capacitor

Para capacitância finita,

~~~text
i = C dV/dt
~~~

Um salto instantâneo e finito de tensão exigiria um impulso de corrente de magnitude não limitada no modelo matemático ideal.

Portanto, circuitos comuns com correntes finitas obedecem à restrição de estado útil:

~~~text
V_C(0+) = V_C(0-)
~~~

salvo quando uma fonte/modelo impulsivo é explicitamente incluído.

Essa regra de continuidade é central na solução de transitórios de chaveamento.

Ela não afirma que capacitores reais nunca mudem rapidamente; afirma o que o modelo concentrado ideal com (C) finito exige.

## Regime permanente DC de um capacitor ideal

Se a tensão no capacitor é constante,

~~~text
dV/dt = 0
~~~

então

~~~text
i = 0
~~~

Assim, depois que uma rede DC ideal atinge regime permanente, um capacitor ideal se comporta como circuito aberto em relação à corrente contínua.

Isso **não** significa tensão ou energia nulas.

Um capacitor carregado pode apresentar

~~~text
i = 0
V != 0
U != 0
~~~

em regime permanente.

## Energia armazenada em um capacitor

A potência instantânea absorvida é

~~~text
p = v i
~~~

Usando

~~~text
i = C dv/dt
~~~

obtém-se

~~~text
p = C v dv/dt
~~~

Integrando de tensão zero até (V),

~~~text
U_C
=
∫ C v dv
=
1/2 C V²
~~~

Forma equivalente com (Q=CV):

~~~text
U_C = Q²/(2C)
~~~

para o capacitor linear ideal.

A energia é não negativa porque reside no campo elétrico segundo esse modelo.

## Densidade de energia do campo elétrico

Em um dielétrico linear, a densidade de energia do campo elétrico é

~~~text
u_E = 1/2 E · D
~~~

e, para um meio isotrópico linear simples,

~~~text
u_E = 1/2 ε |E|²
~~~

A energia total armazenada é a integral no volume:

~~~text
U_E = ∫ u_E dV
~~~

A expressão concentrada (1/2CV²) é uma representação comprimida dessa energia de campo para uma geometria cujo comportamento terminal é adequadamente representado por (C).

Isso conecta teoria de circuitos novamente à fundação eletromagnética.

## Capacitores em paralelo

Capacitores em paralelo compartilham a mesma tensão terminal.

A carga total é a soma das cargas dos ramos:

~~~text
Q_total
=
C1 V + C2 V + ...
=
(C1 + C2 + ...) V
~~~

Portanto,

~~~text
C_eq = Σ C_k
~~~

A capacitância em paralelo aumenta porque a estrutura pode armazenar mais carga para a mesma tensão.

## Capacitores em série

Para capacitores ideais em série com um nó interno inicialmente neutro, a magnitude de carga em cada capacitor torna-se igual.

A tensão total é

~~~text
V = V1 + V2 + ...
~~~

com

~~~text
V_k = Q/C_k
~~~

logo

~~~text
1/C_eq = Σ 1/C_k
~~~

Para dois capacitores,

~~~text
C_eq = (C1 C2)/(C1 + C2)
~~~

O menor capacitor recebe maior magnitude de tensão para a mesma carga em série.

Em cadeias reais de capacitores de alta tensão, diferenças de fuga podem impedir a divisão ideal da tensão, exigindo componentes de equalização.

## Compartilhamento de carga

Conectar capacitores carregados pode redistribuir carga.

Para dois capacitores ideais inicialmente em (V_1) e (V_2), conectados em paralelo com polaridade correspondente e isolados de fluxo externo de carga, conservação de carga fornece

~~~text
C1 V1 + C2 V2
=
(C1 + C2) V_f
~~~

logo

~~~text
V_f
=
(C1 V1 + C2 V2)/(C1 + C2)
~~~

Se (V_1 != V_2), a energia final armazenada calculada por (1/2CV²) é, em geral, menor que a soma inicial.

A energia "ausente" não foi destruída. A conexão ideal com resistência zero omite radiação eletromagnética real, resistência dos condutores e outras dinâmicas dissipativas que ocorrem durante a redistribuição. O paradoxo é um alerta sobre os limites da idealização.

## Modelo de capacitor real

Um capacitor prático pode exigir uma rede como

~~~text
        ESR      ESL
---+---/\/\----LLLL---+---
   |                    |
   |         C          |
   +---------||---------+
   |                    |
   +------- Rleak ------+
~~~

Não idealidades importantes incluem:

| Efeito | Consequência |
|---|---|
| ESR | perda, aquecimento, amortecimento |
| ESL | comportamento indutivo em alta frequência |
| fuga | caminho finito de descarga DC |
| absorção dielétrica | recuperação dependente do histórico |
| coeficiente de tensão | capacitância muda com polarização |
| coeficiente de temperatura | capacitância muda com temperatura |
| tolerância | C real difere do nominal |
| tensão de ruptura | limite de campo do dielétrico |
| limite de ripple | restrição térmica/de perdas |

O modelo útil depende da frequência e da condição de operação.

## Interpretação de desacoplamento

Um capacitor de desacoplamento próximo de uma carga digital armazena energia de campo local e pode fornecer corrente transitória enquanto a rede de distribuição a montante responde.

A relação idealizada

~~~text
ΔV = (1/C) ∫ i dt
~~~

mostra por que capacitância maior pode reduzir queda de tensão para um mesmo déficit líquido de carga.

Mas o desempenho real do desacoplamento também depende de ESR, ESL, posicionamento, indutância das interconexões, espectro de frequência e dinâmica do regulador.

"Adicionar mais capacitância" não é, portanto, solução universal de alta frequência.

## Indutor: ideia física

Um indutor armazena energia no campo magnético associado à corrente.

Para um indutor linear ideal,

~~~text
λ = L i
~~~

onde

~~~text
λ   fluxo magnético concatenado [Wb-espira]
L   indutância [H]
i   corrente [A]
~~~

Um henry é

~~~text
1 H = 1 V·s/A
~~~

O fluxo concatenado (lambda) incorpora o fluxo magnético acoplado pelas espiras de um enrolamento. Para uma única espira efetiva, reduz-se ao fluxo relevante sob o modelo.

## Lei de Faraday e tensão no indutor

A lei de Faraday relaciona força eletromotriz induzida à variação do fluxo magnético.

Para o indutor concentrado ideal sob convenção passiva,

~~~text
v = dλ/dt
~~~

Com (L) constante,

~~~text
v = L di/dt
~~~

Equivalentemente,

~~~text
di/dt = v/L
~~~

e

~~~text
i(t)
=
i(t0)
+
(1/L) ∫[t0..t] v(τ) dτ
~~~

A corrente inicial (i(t0)) faz parte do estado do indutor.

## Continuidade da corrente do indutor

Para (L) finito,

~~~text
v = L di/dt
~~~

Um salto instantâneo e finito de corrente exigiria uma tensão impulsiva/não limitada no modelo ideal.

Assim, na análise comum de chaveamento com tensão finita,

~~~text
I_L(0+) = I_L(0-)
~~~

salvo quando um impulso é explicitamente incluído.

Essa é a dual magnética da continuidade da tensão no capacitor.

## Regime permanente DC de um indutor ideal

Se a corrente no indutor é constante,

~~~text
di/dt = 0
~~~

então

~~~text
v = 0
~~~

Logo um indutor ideal se comporta como curto-circuito em regime permanente DC.

Novamente, isso não significa corrente ou energia nulas.

Um indutor ideal pode ter

~~~text
v = 0
i != 0
U != 0
~~~

sob corrente contínua mantida.

Indutores reais possuem resistência de enrolamento e perdas de núcleo, portanto sua tensão de regime pode não ser zero.

## Energia armazenada em um indutor

Sob convenção passiva,

~~~text
p = v i
~~~

e

~~~text
v = L di/dt
~~~

logo

~~~text
p = L i di/dt
~~~

Integrando de corrente zero até (I),

~~~text
U_L
=
∫ L i di
=
1/2 L I²
~~~

O indutor linear ideal armazena energia magnética não negativa.

## Densidade de energia do campo magnético

Em um meio magnético linear,

~~~text
u_B = 1/2 B · H
~~~

e, no comportamento linear isotrópico simples em que (B=mu H),

~~~text
u_B = B²/(2μ)
    = 1/2 μ H²
~~~

A energia magnética total é obtida integrando no volume.

A expressão concentrada (1/2LI²) comprime a distribuição do campo em um parâmetro terminal.

## Aproximação de solenoide

Para um solenoide ideal longo com (N) espiras, comprimento (ell), área transversal (A) e permeabilidade (mu),

~~~text
L ≈ μ N² A / ℓ
~~~

Isso revela dependências de primeira ordem:

- mais espiras aumentam fortemente a indutância;
- maior seção magnética aumenta a indutância;
- caminho magnético mais longo reduz a indutância;
- maior permeabilidade aumenta a indutância.

Componentes magnéticos reais exigem consideração de fringing, entreferros, permeabilidade não linear, geometria do núcleo, fluxo de fuga e estrutura do enrolamento.

## Indutores em série

Para indutores ideais não acoplados em série, a mesma corrente atravessa cada um e as tensões somam:

~~~text
v
=
L1 di/dt + L2 di/dt + ...
~~~

portanto

~~~text
L_eq = Σ L_k
~~~

Isso assume indutância mútua desprezível.

Se houver acoplamento magnético, a indutância equivalente em série pode ser maior ou menor dependendo da orientação dos enrolamentos e da indutância mútua.

## Indutores em paralelo

Para indutores ideais não acoplados em paralelo com condições iniciais compatíveis, a mesma tensão aparece em cada ramo.

A relação equivalente é

~~~text
1/L_eq = Σ 1/L_k
~~~

Para dois indutores não acoplados,

~~~text
L_eq = (L1 L2)/(L1 + L2)
~~~

Correntes iniciais importam porque indutores possuem estado. Substituir cegamente um conjunto chaveado arbitrário de indutores por um (L) equivalente pode apagar restrições de estado.

## Indutância mútua

Dois enrolamentos magneticamente acoplados podem compartilhar fluxo.

Um modelo linear de duas bobinas pode ser escrito

~~~text
λ1 = L1 i1 + M i2
λ2 = M i1 + L2 i2
~~~

com sinal determinado pela orientação dos enrolamentos/convenção dos pontos.

As tensões são

~~~text
v1 = L1 di1/dt + M di2/dt
v2 = M di1/dt + L2 di2/dt
~~~

O coeficiente de acoplamento é normalmente definido por

~~~text
k = M / sqrt(L1 L2)
~~~

com

~~~text
0 <= |k| <= 1
~~~

para acoplamento físico passivo no modelo comum.

Transformadores são desenvolvidos em capítulo posterior porque relação de espiras, fluxo de fuga, indutância magnetizante e comportamento do núcleo exigem tratamento próprio.

## Modelo de indutor real

Um indutor prático inclui efeitos não ideais:

| Efeito | Consequência |
|---|---|
| resistência do enrolamento | perda (I²R) e queda de tensão DC |
| perda no núcleo | aquecimento por histerese/correntes parasitas |
| saturação | indutância diminui em corrente/fluxo altos |
| capacitância parasita | autorressonância |
| fluxo de fuga | acoplamento imperfeito |
| efeitos pelicular/proximidade | resistência do enrolamento dependente de frequência |
| tolerância | L real difere do nominal |
| limite térmico | restrição de temperatura do núcleo/enrolamento |

Um equivalente simples de alta frequência pode incluir resistência série, (L) ideal e capacitância parasita em paralelo.

Acima da frequência de autorressonância, um componente nominalmente indutivo pode parecer capacitivo.

## Chaveamento indutivo e sobretensão

Como a corrente de um indutor ideal não pode mudar descontinuamente, interromper seu caminho de corrente força o circuito a encontrar outro meio de satisfazer a restrição de estado.

De

~~~text
v = L di/dt
~~~

uma variação muito rápida de corrente exige grande tensão.

Circuitos reais usam diodos de flyback, snubbers, clamps ou caminhos controlados de chaveamento para limitar essa tensão e fornecer caminho à energia magnética armazenada.

Isso é diretamente relevante para relés, motores, conversores chaveados e cargas indutivas.

Um comando de software que desliga uma carga real pode, portanto, disparar transitórios físicos governados pelo hardware, embora o software opere em uma camada de abstração superior.

## Dualidade das variáveis de estado

Capacitores e indutores formam um par dual útil:

| Capacitor | Indutor |
|---|---|
| estado normalmente representado pela tensão | estado normalmente representado pela corrente |
| (q=Cv) | (lambda=Li) |
| (i=C dv/dt) | (v=L di/dt) |
| tensão contínua para corrente finita | corrente contínua para tensão finita |
| regime DC: aberto | regime DC: curto |
| (U=1/2CV²) | (U=1/2LI²) |
| energia de campo elétrico | energia de campo magnético |

Essa dualidade ajuda a organizar a análise posterior de transitórios RC e RL.

Ela não é perfeita em toda realização física; dispositivos reais possuem parasitas e perdas assimétricos.

## Troca de energia em um sistema LC ideal

Um capacitor e um indutor ideais podem trocar energia:

~~~text
energia de campo elétrico
    <-> energia de campo magnético
~~~

Para uma rede LC sem perdas,

~~~text
U_total
=
1/2 C v²
+
1/2 L i²
~~~

é conservada.

A dinâmica oscilatória resultante é derivada no capítulo de RLC.

Adicionar resistência dissipa parte dessa energia e produz amortecimento.

## Visão por espaço de estados

Uma rede contendo capacitores e indutores pode ser descrita por um vetor de estado como

~~~text
x =
[ tensões dos capacitores
  correntes dos indutores ]
~~~

sob uma formulação com estados independentes.

Para uma rede linear invariante no tempo, as equações frequentemente podem ser organizadas como

~~~text
dx/dt = A x + B u
y     = C x + D u
~~~

A contagem exata de estados pode ser menor que o número de elementos armazenadores quando restrições topológicas tornam alguns estados dependentes.

Essa visão conecta posteriormente dinâmica de circuitos a teoria de controle, integração numérica e simulação.

## Degenerescências topológicas em circuitos dinâmicos

Nem toda disposição arbitrária de elementos C/L ideais produz um estado independente por elemento.

Exemplos incluem:

- laços compostos apenas de capacitores ideais e fontes ideais de tensão;
- cutsets compostos apenas de indutores ideais e fontes ideais de corrente.

Essas estruturas podem impor restrições algébricas entre variáveis de armazenamento.

Em simulação de circuitos, isso pode produzir equações algébrico-diferenciais em vez de uma equação diferencial ordinária explícita simples.

Essa distinção é importante para solvers numéricos robustos.

## Fronteira da integração numérica

A partir de

~~~text
i_C = C dv_C/dt
v_L = L di_L/dt
~~~

um simulador precisa integrar o estado no tempo.

Atualizações simples por Euler explícito poderiam ser escritas como

~~~text
v_C[n+1]
=
v_C[n] + dt * i_C[n]/C

i_L[n+1]
=
i_L[n] + dt * v_L[n]/L
~~~

mas Euler explícito pode ser instável ou impreciso em circuitos rígidos ou com passos de tempo mal escolhidos.

Simuladores práticos usam esquemas de integração mais sofisticados e controle adaptativo do passo.

Este capítulo registra as equações de estado, não uma recomendação de que Euler explícito seja suficiente para simulação de produção.

## Constantes de tempo como prévia

Quando um capacitor interage com resistência, a escala temporal natural possui unidades

~~~text
τ_RC = R C
~~~

porque

~~~text
Ω·F = s
~~~

Quando um indutor interage com resistência,

~~~text
τ_RL = L/R
~~~

porque

~~~text
H/Ω = s
~~~

Essas relações dimensionais antecipam as respostas exponenciais derivadas no próximo capítulo.

## Prévia da dependência de frequência

Em análise senoidal de regime permanente, derivar equivale a multiplicar por (jω).

O capacitor e o indutor ideais passam a ter impedâncias

~~~text
Z_C = 1/(jωC)
Z_L = jωL
~~~

Essas fórmulas são apenas antecipadas aqui. Sua derivação, interpretação de fase, valores RMS e uso em redes pertencem ao capítulo de AC.

## Capacitância e indutância parasitas

Capacitância e indutância não se limitam a componentes rotulados C e L.

Quaisquer condutores separados podem apresentar capacitância.

Qualquer laço de corrente cria fluxo magnético e, portanto, indutância.

Exemplos em computadores incluem:

- capacitância entre trilha de PCB e plano;
- indutância de trilhas e vias;
- indutância de encapsulamento;
- capacitâncias de gate e junções MOS;
- capacitância e indutância de cabos;
- parasitas de conectores;
- acoplamento em barramentos de memória.

Em frequência suficientemente baixa, esses efeitos podem ser ignorados. Com bordas rápidas, podem dominar o comportamento.

A diferença entre "componente" e "parasita" é intenção de projeto, não física diferente.

## Relevância para entrega de potência

Uma rede de distribuição de potência digital contém R, L e C intencionais e parasitas.

Uma cadeia simplificada pode ser vista como

~~~text
regulador de tensão
    ↓
impedância da placa/interconexão
    ↓
capacitância bulk + desacoplamento local
    ↓
indutância do encapsulamento
    ↓
capacitância do die
    ↓
transistores chaveando
~~~

Mudanças rápidas de corrente de carga interagem com a indutância para produzir variações de tensão, enquanto capacitância fornece ou absorve carga transitória.

Por isso entrega de potência não pode ser entendida apenas por resistência DC.

## Relevância para integridade de sinal

Capacitância e indutância de interconexão determinam propagação, impedância característica e acoplamento em estruturas distribuídas.

Quando o comprimento da interconexão deixa de ser eletricamente pequeno, um único capacitor e um único indutor concentrados deixam de ser suficientes.

Uma linha de transmissão pode ser modelada por parâmetros distribuídos por unidade de comprimento:

~~~text
R'
L'
G'
C'
~~~

O capítulo de linhas de transmissão desenvolve esse modelo.

O capítulo atual fornece o significado físico de (C) e (L) necessário para compreendê-lo.

## Relevância para chaveamento CMOS

Um nó lógico CMOS precisa carregar e descarregar capacitância.

Para uma capacitância levada aproximadamente entre 0 e (V), a energia de campo armazenada no estado alto é

~~~text
1/2 C V²
~~~

Uma análise completa da energia de chaveamento precisa acompanhar de onde a energia vem e onde é dissipada durante ciclos de carga e descarga.

Esse assunto pertence ao capítulo de chaveamento CMOS, mas a dependência quadrática da tensão já aparece aqui.

Isso explica por que a tensão de alimentação é um termo tão forte em engenharia de potência dinâmica.

## Representação de estado em software

Um simulador genérico de circuitos poderia representar:

~~~text
Capacitor {
    node_a
    node_b
    capacitance
    previous_voltage
}

Inductor {
    node_a
    node_b
    inductance
    previous_current
}
~~~

Um solver transitório de produção normalmente mantém mais histórico, dependendo do método de integração.

Invariantes importantes incluem:

- (C > 0) e (L > 0) para elementos passivos ideais comuns;
- unidades consistentes;
- estado corresponde à mesma polaridade/orientação usada no stamp do elemento;
- condições iniciais são explícitas;
- passo de tempo é positivo e finito;
- atualizações não aceitam silenciosamente NaN ou overflow.

Esses são princípios gerais de modelagem, não detalhes de implementação do ChrisOS.

## Memória, propriedade e concorrência em um solver hipotético

Se elementos dinâmicos forem simulados em software, propriedade do estado importa.

Uma instância do solver deve possuir um proprietário claro para cada estado de elemento em cada passo de integração. *Stamping* paralelo pode ser viável porque componentes individuais contribuem localmente, mas escritas em estruturas matriciais esparsas compartilhadas exigem particionamento, operações atômicas, acumulação thread-local ou outra forma de sincronização.

A atualização do estado deve ocorrer em uma fase definida:

~~~text
ler estado anterior aceito
    ↓
montar equações de tentativa
    ↓
resolver
    ↓
verificar convergência/erro
    ↓
aceitar novo estado
~~~

Publicar tensão de capacitor ou corrente de indutor parcialmente atualizada para outra thread pode corromper o método numérico.

Novamente, isso descreve requisitos genéricos de um solver, não código existente do ChrisOS.

## Modos de falha

| Condição | Consequência |
|---|---|
| (C=0) usado como capacitor dinâmico | elemento degenerado; equação de estado inválida |
| (L=0) usado como indutor dinâmico | elemento degenerado; equação de estado inválida |
| C/L passivo negativo sem modelo ativo explícito | não físico para o modelo comum |
| sobretensão em capacitor | risco de ruptura dielétrica |
| sobrecorrente em indutor | saturação/dano térmico |
| ESR/ESL ignorados | previsão incorreta em alta frequência |
| resistência do enrolamento ignorada | previsão incorreta de perdas/DC |
| estado inicial inconsistente | descontinuidade/falha de restrição no solver |
| passo de integração grande demais | instabilidade numérica ou erro excessivo |
| rede de armazenamento flutuante | modelo singular/subdeterminado |
| chaveamento ideal de estados incompatíveis | comportamento impulsivo ocultado pelo modelo |

Uma análise robusta reporta a hipótese violada em vez de forçar uma resposta finita.

## Invariantes de validação

Verificações determinísticas úteis incluem:

~~~text
capacitor:
    Q = C V
    i = C dV/dt
    U = 1/2 C V²

indutor:
    λ = L i
    v = L di/dt
    U = 1/2 L i²
~~~

Para combinações ideais:

~~~text
capacitores em paralelo: C_eq = Σ C
capacitores em série:    1/C_eq = Σ 1/C

indutores em série:      L_eq = Σ L
indutores em paralelo:   1/L_eq = Σ 1/L
~~~

Verificações dimensionais fornecem outro invariante:

~~~text
F · V = C
F · V² = J
H · A² = J
H/Ω = s
Ω·F = s
~~~

## Relação com o ChrisOS

O ChrisOS normalmente observa abstrações digitais, e não variáveis de armazenamento de campos.

Ainda assim, o hardware real sob o sistema operacional depende fortemente de capacitância e indutância:

- bordas de clock e dados carregam capacitâncias de interconexão e de transistores;
- reguladores de tensão usam indutores e capacitores;
- indutâncias de encapsulamento e placa moldam transitórios de rail;
- capacitores de desacoplamento fornecem corrente transitória;
- barramentos e cabos possuem C e L distribuídos.

Um kernel panic, timeout de dispositivo ou erro de memória pode, em certos casos, ter causa última em integridade elétrica, mas sintomas de software não provam uma causa de circuito específica.

Comportamento concreto de monitoramento ou gerenciamento de energia no ChrisOS deve ser documentado a partir do código-fonte e das especificações dos dispositivos nos capítulos de implementação.

## Evidência de validação

O checker associado a este capítulo valida cálculos representativos para:

- capacitância de placas paralelas;
- carga por (Q=CV);
- corrente de capacitor para inclinação constante de tensão;
- energia do capacitor;
- capacitâncias em série e paralelo;
- compartilhamento de carga;
- indutância aproximada de solenoide;
- tensão no indutor para inclinação constante de corrente;
- energia do indutor;
- indutâncias em série e paralelo;
- constantes de tempo dimensionais RC e RL;
- âncoras da documentação bilíngue.

São verificações didáticas determinísticas, não análise eletromagnética por elementos finitos, validação SPICE, qualificação dielétrica ou caracterização de núcleo magnético.

## Limitações atuais

Este capítulo intencionalmente ainda não resolve:

- resposta ao degrau em redes RC/RL;
- sistemas RLC subamortecidos, criticamente amortecidos ou superamortecidos;
- redes em regime senoidal;
- frequência de ressonância e Q em redes práticas;
- relação de espiras de transformadores e projeto de núcleos acoplados;
- equações de linhas de transmissão;
- laços de controle de reguladores chaveados;
- comportamento concreto no código-fonte do ChrisOS.

Esses assuntos estão em capítulos separados porque cada um introduz estado adicional, hipóteses de domínio de frequência, topologia ou evidência de implementação.

## Fronteira do roadmap

A próxima sequência é:

~~~text
armazenamento de campo em C/L
    ↓
equações diferenciais RC, RL e RLC
    ↓
resposta natural e forçada
    ↓
impedância AC e ressonância
    ↓
indução, transformadores e conversão de potência
    ↓
estruturas de transmissão distribuídas
    ↓
potência digital e integridade de sinal
~~~

As equações de armazenamento estabelecidas aqui permanecem como base de estado durante toda essa progressão.

## Proveniência da revisão

Revisado contra o `main` do ChrisOS na revisão `da3df29cb397932c43d32373871fb9380e688ade`.

`sources` e `symbols` estão intencionalmente vazios porque este capítulo não faz afirmação sobre implementação atual do ChrisOS. A revisão registrada estabelece a proveniência do corpus e preserva a fronteira entre teoria física e implementação sustentada por código-fonte.
