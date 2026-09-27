---
id: rc-rlc-transients
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - capacitance-inductance
related:
  - ac-signals-frequency-impedance
  - power-delivery-regulation
  - cmos-switching-power
  - transmission-lines-differential-signals
---

# Transitórios RC, RL e RLC

<div class="abstract">
Resistores dissipam energia, enquanto capacitores e indutores a armazenam. Quando esses elementos são conectados, chaveamentos e variações de fontes produzem respostas transitórias governadas por equações diferenciais, condições iniciais e leis de conservação. Este capítulo deriva respostas RC e RL de primeira ordem, dinâmica RLC de segunda ordem, regimes de amortecimento, resposta natural e forçada, forma em espaço de estados, fluxo de energia, restrições de chaveamento, integração numérica e os limites dos modelos transitórios concentrados antes da análise no domínio da frequência.
</div>

## Pré-requisitos e escopo

Os capítulos anteriores estabeleceram:

- lei de Ohm e leis de Kirchhoff;
- relação do capacitor (i_C=C,dv_C/dt);
- relação do indutor (v_L=L,di_L/dt);
- continuidade da tensão do capacitor sob corrente finita;
- continuidade da corrente do indutor sob tensão finita;
- energias armazenadas (U_C=	frac12CV^2) e (U_L=	frac12LI^2).

Um transitório é a evolução temporal que ocorre quando o estado ou a excitação de um circuito muda.

Gatilhos típicos incluem:

~~~text
uma chave abre ou fecha
uma fonte muda em degrau
a corrente de carga varia
energia inicialmente armazenada é liberada
um sistema de controle muda o estado de um conversor
~~~

Este capítulo trata circuitos lineares concentrados com R, L e C constantes, salvo indicação contrária. Chaveamento semicondutor não linear, linhas de transmissão distribuídas e laços de controle de reguladores exigem modelos adicionais.

Nenhuma implementação atual do ChrisOS é afirmada aqui.

## Estado, variáveis algébricas e memória

Um resistor é algébrico:

~~~text
v_R = R i_R
~~~

Suas variáveis de terminal em um instante não exigem um valor anterior armazenado no modelo ideal.

Capacitores e indutores são dinâmicos:

~~~text
i_C = C dv_C/dt
v_L = L di_L/dt
~~~

Suas variáveis de armazenamento de energia carregam estado ao longo do tempo.

Uma escolha conveniente de estado é:

~~~text
tensão do capacitor
corrente do indutor
~~~

porque essas variáveis obedecem restrições de continuidade sob excitação ordinária finita.

A rede completa continua obedecendo KCL e KVL a todo instante.

## Condições iniciais

Análise transitória exige o estado imediatamente antes do chaveamento.

Para um capacitor ideal:

~~~text
v_C(0+) = v_C(0-)
~~~

Para um indutor ideal:

~~~text
i_L(0+) = i_L(0-)
~~~

Essas igualdades não implicam que toda tensão ou corrente seja contínua.

Por exemplo:

- a tensão em resistor pode saltar se a corrente saltar;
- a corrente no capacitor pode saltar enquanto sua tensão permanece contínua;
- a tensão no indutor pode saltar enquanto sua corrente permanece contínua.

A topologia de chaveamento em (t<0) e (t>0) pode ser diferente, portanto o circuito deve ser analisado em cada lado do evento.

## Raciocínio de valor final

Antes de resolver um problema de chaveamento DC de primeira ordem, é útil determinar o estado final esperado.

Para um circuito estável sob excitação DC constante, quando (t	oinfty):

~~~text
capacitor ideal -> circuito aberto
indutor ideal   -> curto-circuito
~~~

Isso permite encontrar (v_C(infty)) ou (i_L(infty)) antes de resolver a equação diferencial.

A regra vale apenas para regime permanente DC. Ela não significa que capacitores sejam sempre abertos ou indutores sempre curtos.

## Resposta canônica de primeira ordem

Um estado linear estável de primeira ordem (x(t)), conduzido do valor inicial (x_0) ao valor final (x_f), possui a forma:

~~~text
x(t) = x_f + (x_0 - x_f) e^(-t/τ)
~~~

onde (	au>0) é a constante de tempo.

A resposta se separa em:

~~~text
componente forçada/final: x_f
componente natural:       (x_0 - x_f)e^(-t/τ)
~~~

Em (t=	au), a distância até o valor final cai para

~~~text
e^-1 ≈ 0.367879
~~~

da distância inicial.

Frações úteis remanescentes:

| Tempo | Componente natural restante |
|---|---:|
| (1	au) | 36,8% |
| (2	au) | 13,5% |
| (3	au) | 5,0% |
| (4	au) | 1,83% |
| (5	au) | 0,674% |

"Assentado após cinco constantes de tempo" é, portanto, uma aproximação de engenharia, não igualdade exata.

## Circuito RC série em carga

Considere uma fonte (V_s), um resistor (R) e um capacitor (C) em série.

KVL fornece:

~~~text
V_s = v_R + v_C
~~~

com

~~~text
v_R = Ri
i = C dv_C/dt
~~~

logo:

~~~text
RC dv_C/dt + v_C = V_s
~~~

Para (V_s) constante, a constante de tempo é:

~~~text
τ = RC
~~~

e a solução:

~~~text
v_C(t)
=
V_s
+
[v_C(0+) - V_s] e^(-t/RC)
~~~

Para capacitor inicialmente descarregado:

~~~text
v_C(t) = V_s [1 - e^(-t/RC)]
~~~

A corrente é:

~~~text
i(t)
=
(V_s - v_C(0+))/R
* e^(-t/RC)
~~~

Para (v_C(0)=0):

~~~text
i(t) = (V_s/R)e^(-t/RC)
~~~

A maior corrente ideal ocorre imediatamente após o degrau porque a tensão do capacitor não pode saltar.

## Descarga RC

Para um capacitor inicialmente em (V_0) descarregando por (R) sem fonte independente:

~~~text
RC dv_C/dt + v_C = 0
~~~

portanto:

~~~text
v_C(t) = V_0 e^(-t/RC)
~~~

e, segundo uma orientação passiva escolhida:

~~~text
i(t) = C dv_C/dt
     = -(V_0/R)e^(-t/RC)
~~~

O sinal negativo significa que a corrente está no sentido oposto ao escolhido para a carga do capacitor.

A energia armazenada decai como:

~~~text
U_C(t)
=
1/2 C V_0² e^(-2t/RC)
~~~

A energia cai com expoente duas vezes mais rápido porque depende do quadrado da tensão.

## Contabilidade de energia no RC

Carregar um capacitor ideal a partir de uma fonte ideal (V_s) através de um resistor produz um resultado energético importante.

A energia final no capacitor é:

~~~text
U_C = 1/2 C V_s²
~~~

A fonte entrega:

~~~text
E_source = C V_s²
~~~

para um degrau partindo de tensão inicial zero através de qualquer (R>0).

O resistor dissipa a diferença:

~~~text
E_R = 1/2 C V_s²
~~~

Nesse modelo ideal, metade da energia da fonte é armazenada e metade dissipada, independentemente do valor de (R). A resistência altera a escala temporal, não essa divisão total.

Drivers reais, tempo de subida finito da fonte, indutância e circuitos de recuperação de energia podem alterar o fluxo detalhado.

## Constante de tempo RC geral

Um capacitor nem sempre enxerga um único resistor explícito em série.

Para uma rede linear com um capacitor, a constante de tempo natural pode frequentemente ser obtida pela resistência de Thévenin vista pelo capacitor com as fontes independentes zeradas:

~~~text
τ = R_th C
~~~

Fontes dependentes permanecem ativas. Se existirem, pode ser necessário usar uma fonte de teste para obter (R_{th}).

A constante de tempo é uma propriedade da rede, não apenas do resistor rotulado próximo ao capacitor.

## Energização RL série

Considere uma fonte DC (V_s), resistor (R) e indutor (L) em série.

KVL fornece:

~~~text
V_s = Ri + L di/dt
~~~

ou:

~~~text
L di/dt + Ri = V_s
~~~

A constante de tempo é:

~~~text
τ = L/R
~~~

e:

~~~text
i(t)
=
V_s/R
+
[i(0+) - V_s/R]e^(-tR/L)
~~~

Para indutor inicialmente sem corrente:

~~~text
i(t)
=
(V_s/R)[1-e^(-tR/L)]
~~~

A tensão no indutor é:

~~~text
v_L(t)
=
[V_s - R i(0+)] e^(-tR/L)
~~~

e, para corrente inicial zero:

~~~text
v_L(t)=V_s e^(-tR/L)
~~~

A corrente começa continuamente enquanto a tensão no indutor pode mudar imediatamente.

## Decaimento RL

Se um indutor conduzindo corrente (I_0) é conectado a uma resistência (R) sem fonte independente:

~~~text
L di/dt + Ri = 0
~~~

portanto:

~~~text
i(t) = I_0 e^(-tR/L)
~~~

A energia magnética armazenada decai como:

~~~text
U_L(t)
=
1/2 L I_0² e^(-2tR/L)
~~~

e é dissipada no resistor sob o modelo ideal.

Se o caminho da corrente for interrompido sem rota de descarga controlada, o indutor ideal tenta gerar a tensão necessária para manter a continuidade da corrente. Por isso circuitos reais usam caminhos de flyback, clamp ou snubber quando a energia indutiva é relevante.

## Constante de tempo RL geral

Para uma rede linear com um indutor, a constante de tempo natural pode frequentemente ser expressa como:

~~~text
τ = L/R_th
~~~

onde (R_{th}) é a resistência vista pelo indutor após zerar fontes independentes, preservando fontes dependentes.

A dualidade com RC é:

| RC | RL |
|---|---|
| estado (v_C) | estado (i_L) |
| (	au=R_{th}C) | (	au=L/R_{th}) |
| capacitor inicialmente se comporta como fonte de tensão igual a (v_C(0)) | indutor inicialmente se comporta como fonte de corrente igual a (i_L(0)) |
| capacitor aberto no DC final | indutor em curto no DC final |

## Procedimento de chaveamento por trechos

Uma análise disciplinada pode seguir:

~~~text
1. resolver o circuito em t < 0
2. determinar v_C(0-) e i_L(0-)
3. aplicar continuidade:
       v_C(0+) = v_C(0-)
       i_L(0+) = i_L(0-)
4. construir a topologia de t > 0
5. determinar o estado final DC estável, se existir
6. derivar a equação diferencial ou constante de tempo
7. resolver a resposta
8. verificar KCL/KVL e sinais de energia/potência
~~~

Ignorar os passos 2 ou 3 é causa frequente de soluções fisicamente impossíveis.

## Equação RLC série de segunda ordem

Considere um laço RLC série sem fonte.

Usando a carga do capacitor (q):

~~~text
i = dq/dt
v_C = q/C
v_R = R dq/dt
v_L = L d²q/dt²
~~~

KVL fornece:

~~~text
L d²q/dt²
+
R dq/dt
+
q/C
=
0
~~~

Dividindo por (L):

~~~text
d²q/dt²
+
(R/L) dq/dt
+
(1/LC)q
=
0
~~~

Defina:

~~~text
α = R/(2L)
ω_0 = 1/sqrt(LC)
~~~

A equação característica é:

~~~text
s² + 2αs + ω_0² = 0
~~~

com raízes:

~~~text
s = -α ± sqrt(α² - ω_0²)
~~~

A estrutura das raízes determina o regime de amortecimento.

## Razão de amortecimento

Defina:

~~~text
ζ = α/ω_0
  = (R/2) sqrt(C/L)
~~~

para a forma RLC série.

Então:

| Regime | Condição | Comportamento dos polos |
|---|---|---|
| superamortecido | (zeta>1) | dois polos reais negativos distintos |
| criticamente amortecido | (zeta=1) | polo real negativo repetido |
| subamortecido | (0<zeta<1) | polos complexos conjugados com parte real negativa |
| sem perdas | (zeta=0) | polos puramente imaginários no modelo ideal |

Resistência negativa ou rede ativa pode mover polos para o semiplano direito e produzir crescimento em vez de decaimento.

## Resposta superamortecida

Se:

~~~text
α > ω_0
~~~

as raízes (s_1,s_2) são reais, negativas e distintas para (R,L,C>0).

A resposta natural possui forma:

~~~text
x(t) = A e^(s1 t) + B e^(s2 t)
~~~

Não há oscilação.

O polo mais lento, mais próximo de zero, domina para tempos longos.

## Amortecimento crítico

Se:

~~~text
α = ω_0
~~~

o polo repetido é:

~~~text
s = -α
~~~

e a resposta natural:

~~~text
x(t)
=
(A + Bt)e^(-αt)
~~~

O amortecimento crítico marca a fronteira entre comportamento oscilatório e não oscilatório no modelo ideal de segunda ordem.

Ele costuma estar associado a assentamento monotônico rápido, mas o ótimo exato depende da variável observada e do critério de desempenho.

## Resposta subamortecida

Se:

~~~text
α < ω_0
~~~

defina a frequência natural amortecida:

~~~text
ω_d = sqrt(ω_0² - α²)
~~~

A resposta natural pode ser escrita como:

~~~text
x(t)
=
e^(-αt)
[A cos(ω_d t) + B sin(ω_d t)]
~~~

ou como senoide amortecida com amplitude e fase.

A energia troca repetidamente entre campos elétrico e magnético, enquanto a resistência remove parte dela a cada ciclo.

## Oscilação LC sem perdas

Para (R=0):

~~~text
α = 0
ω_d = ω_0
~~~

e a rede LC ideal sem fonte satisfaz:

~~~text
x'' + ω_0² x = 0
~~~

Sua energia total:

~~~text
U =
1/2 C v_C²
+
1/2 L i_L²
~~~

permanece constante.

Circuitos reais sempre possuem mecanismos de perda, portanto oscilação passiva LC sustentada indefinidamente é uma idealização.

## Resposta forçada de segunda ordem

Com uma fonte aplicada, a resposta de segunda ordem contém:

~~~text
resposta natural
+
resposta forçada
~~~

A parte natural depende da energia inicial armazenada e dos polos do circuito.

A parte forçada depende da fonte.

Para degrau DC em sistema estável, a resposta natural decai e o estado converge ao valor final forçado.

Para excitação senoidal, a resposta forçada de longo prazo motiva os métodos de fasores e impedância do próximo capítulo.

## Condições iniciais em circuitos RLC

Um sistema de segunda ordem geralmente exige duas condições iniciais independentes.

Um par conveniente é:

~~~text
v_C(0+)
i_L(0+)
~~~

herdado do circuito pré-chaveamento.

As constantes da solução homogênea são então determinadas aplicando esses estados iniciais e, quando necessário, derivadas obtidas por KCL/KVL.

Zerar arbitrariamente todas as condições iniciais descarta energia armazenada e pode alterar completamente a resposta.

## Formulação em espaço de estados

Um circuito RLC série pode usar o vetor de estado:

~~~text
x =
[ v_C
  i_L ]
~~~

Para uma fonte (u(t)), uma forma possível é:

~~~text
dv_C/dt = i_L/C

di_L/dt =
[u - R i_L - v_C]/L
~~~

Logo:

~~~text
d/dt [v_C] = [ 0      1/C ] [v_C] + [ 0 ]u
     [i_L]   [-1/L  -R/L ] [i_L]   [1/L]
~~~

Isso expõe os dois estados de armazenamento de energia e faz os autovalores da matriz de estado coincidirem com os polos naturais.

Representação em espaço de estados é especialmente útil para simulação, controle e sistemas com muitos estados.

## Métricas de resposta ao degrau

Para sistemas subamortecidos, métricas comuns incluem:

- tempo de subida;
- tempo de pico;
- sobressinal percentual;
- tempo de acomodação.

Para a forma normalizada de segunda ordem:

~~~text
s² + 2ζω_n s + ω_n²
~~~

com (0<zeta<1), a frequência amortecida é:

~~~text
ω_d = ω_n sqrt(1-ζ²)
~~~

e o sobressinal ideal da resposta canônica ao degrau é:

~~~text
M_p
=
exp[-ζπ/sqrt(1-ζ²)]
~~~

como fração do valor final.

Essa fórmula se aplica à forma padrão de segunda ordem com as hipóteses usuais de numerador; não deve ser aplicada cegamente a qualquer variável medida em qualquer topologia RLC.

## Prévia do fator Q

Para um RLC série levemente amortecido:

~~~text
Q ≈ ω_0 L/R
  = 1/(ω_0 R C)
  = (1/R)sqrt(L/C)
~~~

e, para o denominador padrão de segunda ordem:

~~~text
Q = 1/(2ζ)
~~~

sob o modelo correspondente.

Q alto significa amortecimento relativamente fraco e ressonância mais pronunciada.

O significado completo no domínio da frequência é desenvolvido no capítulo de AC.

## Resposta natural e polos

Os modos exponenciais de um circuito linear são determinados pelos polos.

Para sistemas de primeira ordem:

~~~text
polo = -1/τ
~~~

Em sistemas RC/RL passivos estáveis, o polo está no eixo real negativo.

Em sistemas RLC de segunda ordem, os polos podem ser:

~~~text
dois reais negativos
um real negativo repetido
complexos conjugados com parte real negativa
~~~

A posição dos polos cria a ponte entre assentamento no tempo e comportamento em frequência.

## Prévia da transformada de Laplace

A transformada de Laplace converte diferenciação em álgebra preservando condições iniciais.

Por exemplo:

~~~text
L{dx/dt}
=
sX(s) - x(0-)
~~~

e:

~~~text
L{d²x/dt²}
=
s²X(s) - s x(0-) - x'(0-)
~~~

Isso permite transformar equações diferenciais de circuitos em equações algébricas em (s).

O próximo capítulo se concentra em regime senoidal usando (s=jω); métodos completos de Laplace são mais amplos que análise fasorial.

## Convolução e excitação arbitrária

Para um sistema linear invariante no tempo com resposta ao impulso (h(t)), a saída pode ser escrita:

~~~text
y(t)
=
∫ h(τ)u(t-τ)dτ
~~~

no intervalo apropriado.

Isso significa que respostas ao degrau e impulso caracterizam a reação do sistema a entradas mais gerais por superposição.

Simulação de circuitos no tempo também pode integrar diretamente as equações de estado.

## Integração numérica no tempo

Um simulador não manipula tempo contínuo diretamente; aproxima atualizações de estado em instantes discretos.

Para uma equação escalar de primeira ordem:

~~~text
dx/dt = f(x,t)
~~~

Euler explícito usa:

~~~text
x[n+1]
=
x[n] + Δt f(x[n],t[n])
~~~

O método é simples, porém condicionalmente estável.

Para um decaimento RC:

~~~text
dx/dt = -x/τ
~~~

Euler explícito fornece:

~~~text
x[n+1]
=
(1-Δt/τ)x[n]
~~~

Se (Delta t) for grande demais, a solução numérica pode oscilar ou divergir mesmo que o sistema físico seja estável.

## Rigidez e métodos implícitos

Circuitos com constantes de tempo muito separadas podem ser rígidos.

Exemplo:

~~~text
polo parasita rápido: nanossegundos
polo lento de controle/armazenamento: milissegundos
~~~

Um método explícito forçado a usar o menor passo estável pode ficar ineficiente.

Métodos implícitos como Euler para trás trocam custo algébrico por passo por propriedades de estabilidade mais fortes.

Integração trapezoidal oferece outro equilíbrio de precisão/amortecimento e pode exibir ringing numérico em certos problemas rígidos de chaveamento.

Simulação transitória de produção exige, portanto, seleção de método, estimativa de erro local, controle adaptativo de passo e iteração não linear robusta.

## Modelos companheiros

Simuladores de circuitos frequentemente convertem dispositivos dinâmicos em modelos algébricos equivalentes a cada passo de tempo.

Com Euler para trás, a relação do capacitor pode virar uma condutância equivalente mais uma fonte de histórico.

Partindo de:

~~~text
i_C = C dv/dt
~~~

aproxime:

~~~text
dv/dt
≈
[v_n - v_(n-1)]/Δt
~~~

logo:

~~~text
i_n
=
(C/Δt)v_n
-
(C/Δt)v_(n-1)
~~~

No passo atual, (C/Delta t) funciona como uma condutância e o termo de estado anterior torna-se contribuição conhecida de fonte.

Isso permite reutilizar a infraestrutura de montagem matricial no transitório.

## Estado de simulação discreta

Um solver genérico transitório pode manter:

~~~text
ElementState {
    accepted_state
    trial_state
    history_terms
}

SolverState {
    time
    proposed_dt
    matrix
    rhs
    convergence_status
}
~~~

Uma sequência segura de passo é:

~~~text
montar sistema de tentativa
    ↓
resolver
    ↓
verificar resíduo/convergência
    ↓
estimar erro de integração
    ↓
aceitar ou rejeitar passo
    ↓
publicar apenas estado aceito
~~~

Passos rejeitados não devem sobrescrever o último estado físico aceito.

Esses são princípios gerais de solver numérico, não estruturas atuais do ChrisOS.

## Complexidade e esparsidade

Para um circuito com (n) incógnitas, uma fatoração densa custa aproximadamente (O(n^3)), mas matrizes de circuitos costumam ser esparsas.

Simulação transitória resolve repetidamente matrizes com topologia semelhante.

O desempenho depende de:

- ordenação da matriz esparsa;
- reutilização de fatoração;
- número de iterações não lineares;
- quantidade de passos de tempo;
- taxa de aceitação de passos adaptativos;
- densidade de eventos de chaves e modelos por trechos.

O custo total pode ser dominado por muitas soluções sucessivas, e não por uma única solução grande.

## Validação por energia

Energia fornece fortes invariantes de transitório.

Para uma rede RLC série ideal, sem fonte, com (R>0):

~~~text
d/dt
[
1/2 C v_C²
+
1/2 L i_L²
]
=
- R i²
<= 0
~~~

sob a orientação série.

Logo a energia armazenada deve diminuir monotonicamente no modelo passivo sem fonte.

Se uma simulação numérica produz energia total crescente sem fonte ativa, então existe elemento ativo no modelo, convenção de sinais inconsistente ou instabilidade causada por método/passo de integração.

## Fronteiras de chaveamento e impulsos

Chaves ideais podem criar eventos matematicamente singulares.

Exemplos:

- conectar capacitores ideais com tensões diferentes por resistência zero;
- forçar a corrente de um indutor ideal a mudar instantaneamente;
- chavear fontes ideais de tensão incompatíveis diretamente.

Circuitos reais possuem resistência, indutância, capacitância, tempo de transição e radiação eletromagnética finitos.

Um modelo fisicamente útil normalmente exige adicionar essas não idealidades em vez de interpretar corrente ou tensão infinita como previsão literal.

## Banda de medição

O transitório observado depende da banda de medição e da carga da sonda.

Uma borda rápida contém componentes espectrais de alta frequência. Um instrumento com banda limitada pode reportar:

- tempo de subida aparentemente maior;
- sobressinal reduzido;
- ringing alterado.

Capacitância da ponta ou indutância do terra da sonda também podem modificar o circuito.

Validação de transitórios deve, portanto, declarar tanto a banda do modelo quanto a banda de medição.

## Relação com temporização digital

Sinais digitais são interpretados como estados lógicos, mas suas transições físicas são transitórios analógicos.

Uma cadeia simplificada:

~~~text
driver muda estado de condução
    ↓
capacitância do nó carrega/descarrega
    ↓
R/L/C da interconexão moldam a forma de onda
    ↓
limiar do receptor é cruzado
    ↓
estado digital muda
~~~

Atraso de propagação, slew rate, overshoot e ringing surgem dessa dinâmica.

A abstração digital só é válida enquanto o comportamento elétrico permanece dentro das margens de temporização e tensão da interface.

## Relação com entrega de potência

Transitórios de carga são centrais em sistemas de alimentação de computadores.

Um aumento abrupto de corrente pode produzir queda de rail por:

~~~text
ΔV_R = I R
ΔV_L = L dI/dt
ΔV_C = (1/C) ∫ i_deficit dt
~~~

Esses mecanismos atuam simultaneamente através de regulador, placa, encapsulamento e die.

O capítulo específico de power delivery desenvolverá metas de impedância, hierarquia de desacoplamento e resposta do regulador. O presente capítulo fornece a matemática transitória subjacente.

## Relação com o ChrisOS

O ChrisOS opera acima dessas dinâmicas analógicas.

O sistema operacional pode provocar transições de carga que alteram atividade de CPU ou dispositivos, mas a resposta elétrica resultante é implementada por hardware e firmware abaixo da abstração do SO.

O código-fonte atual do ChrisOS não contém um solver RC/RLC documentado por este capítulo.

Se futuramente houver código de gerenciamento de energia, telemetria ou simulação, sua implementação deverá ser documentada separadamente com arquivos, símbolos, propriedade, concorrência e evidências de validação concretas.

## Fronteira de privilégio, concorrência e ABI

Equações diferenciais RC/RL/RLC não possuem nível de privilégio de CPU, ordem de locks ou ABI.

Essas preocupações aparecem apenas quando software representa ou controla estados de hardware.

Um simulador transitório em software exigiria:

- propriedade do vetor de estado;
- sincronização para montagem paralela;
- aceitação/rejeição determinística de passos;
- políticas de propagação de erro numérico;
- formatos de arquivo ou API caso o estado seja externalizado.

Nenhum desses contratos de software é afirmado como existente no ChrisOS aqui.

## Modos de falha

| Falha | Significado |
|---|---|
| condição inicial ausente | estado dinâmico subespecificado |
| topologia de chaveamento errada | equação diferencial descreve circuito incorreto |
| continuidade de (v_C) violada | implica corrente impulsiva não modelada |
| continuidade de (i_L) violada | implica tensão impulsiva não modelada |
| R passivo negativo | modelo torna-se ativo/instável |
| amortecimento zero assumido em circuito real | ringing persiste de modo irrealista |
| passo numérico instável | energia simulada cresce artificialmente |
| passo de tempo grosseiro | polos/eventos rápidos são perdidos |
| parasitas ignorados | previsão de bordas/ringing pode estar errada |
| usar (5	au) como igualdade exata | confunde aproximação com comportamento assintótico |

## Evidência de validação

O checker executável deste batch verifica exemplos determinísticos para:

- carga e descarga RC;
- energização e decaimento RL;
- frações de constante de tempo de primeira ordem;
- invariantes de continuidade de capacitor/indutor;
- classificação de amortecimento RLC série;
- frequência natural amortecida;
- sobressinal padrão de segunda ordem;
- redução de energia em RLC passivo sem fonte;
- exemplo do limite de estabilidade de Euler explícito;
- âncoras bilíngues do capítulo.

Essas verificações validam equações e invariantes editoriais. Elas não constituem um solver SPICE transitório nem validação de forma de onda de hardware.

## Limitações atuais

Este capítulo ainda não desenvolve:

- fasores complexos e redes de impedância;
- decomposição de Fourier;
- RMS e potência complexa;
- acoplamento de transformadores;
- linhas de transmissão distribuídas;
- modelos não lineares de chave/dispositivo;
- ruído estocástico;
- laços de controle de reguladores;
- implementação atual do ChrisOS.

Esses tópicos exigem hipóteses adicionais e permanecem separados no currículo.

## Fronteira do roadmap

A progressão conceitual é:

~~~text
equações constitutivas R/C/L
    ↓
equações diferenciais no tempo
    ↓
resposta natural + forçada
    ↓
polos, amortecimento e acomodação
    ↓
regime senoidal
    ↓
fasores, impedância e resposta em frequência
~~~

O próximo capítulo substitui diferenciações senoidais repetidas por álgebra de impedância complexa, preservando as mesmas equações diferenciais subjacentes.

## Proveniência da revisão

Revisado contra o `main` do ChrisOS na revisão `da3df29cb397932c43d32373871fb9380e688ade`.

`sources` e `symbols` estão intencionalmente vazios porque este capítulo não afirma que o ChrisOS atual implemente um simulador RC/RLC ou subsistema analógico de controle. A revisão registrada preserva a proveniência do corpus e a fronteira de implementação.
