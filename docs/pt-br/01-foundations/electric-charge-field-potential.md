---
id: electric-charge-field-potential
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - atom-semiconductor
related:
  - voltage-current-resistance-power
  - ohm-kirchhoff-circuits
  - capacitance-inductance
  - crystal-bands-doping
  - transistor-cmos
  - logic-levels-noise-margins
---

# Carga elétrica, campo, potencial e energia

## Escopo

Um computador digital manipula bits abstratos, mas a máquina física funciona por interações eletromagnéticas.

Antes de usar de forma coerente tensão, corrente, resistência, capacitância ou chaveamento de transistores, quatro ideias precisam ser separadas:

~~~text
carga
    propriedade transportada pela matéria

campo elétrico
    condição local de força por unidade de carga no espaço

potencial elétrico
    energia por unidade de carga associada à posição

diferença de potencial
    diferença de potencial entre dois pontos
~~~

Essas grandezas estão relacionadas, mas não são intercambiáveis.

Um fio não "contém tensão" no mesmo sentido em que uma região pode conter carga. Uma bateria não injeta valores booleanos abstratos em um chip. Um HIGH lógico não é uma partícula microscópica.

O objetivo deste capítulo é estabelecer a linguagem física usada depois para derivar tensão, corrente, capacitância, eletrostática de semicondutores, chaveamento CMOS, integridade de sinal e power delivery.

![Carga, campo e potencial](../../assets/diagrams/electric-charge-field-potential-pt-br.svg)

## Carga elétrica

Carga elétrica é uma propriedade física que determina como a matéria participa da interação eletromagnética.

A unidade SI de carga é o coulomb:

~~~text
Q [C]
~~~

No nível microscópico, elétrons possuem carga elementar negativa e prótons possuem carga positiva de mesma magnitude.

A magnitude da carga elementar é:

~~~text
e = 1.602176634 × 10^-19 C
~~~

pela definição moderna do SI.

Assim, um coulomb corresponde aproximadamente a:

~~~text
1 / e
≈ 6.241509074 × 10^18
~~~

cargas elementares.

É um número enorme porque o coulomb é uma unidade macroscópica.

## Carga possui sinal

Carga possui sinal.

Duas cargas positivas se repelem. Duas cargas negativas também se repelem. Cargas de sinais opostos se atraem.

O sinal não é uma etiqueta adicionada depois do cálculo. Ele participa da relação de força e determina a direção.

Um sistema pode conter quantidades enormes de cargas positivas e negativas e, ainda assim, ter carga líquida quase zero.

Essa distinção é importante em condutores e semicondutores.

Um fio metálico pode conduzir corrente sem acumular uma enorme carga líquida em todo o volume.

Da mesma forma, regiões semicondutoras dopadas podem permanecer quase neutras eletricamente mesmo com populações de portadores muito diferentes.

## Conservação de carga

Em sistemas eletrônicos ordinários, a carga elétrica total é conservada.

Carga pode se mover de um lugar para outro. Portadores positivos e negativos podem recombinar ou se separar conforme processos do material. Porém o modelo precisa contabilizar onde carga líquida se acumula e por onde sai.

Esse princípio é a base física sob a lei das correntes de Kirchhoff.

KCL não é apenas uma convenção de bookkeeping. No modelo de circuitos concentrados, ela é uma expressão macroscópica da conservação de carga.

## Portadores discretos e variáveis contínuas

Na escala microscópica, carga é quantizada.

Na escala de circuitos, engenharia elétrica normalmente trata carga como variável contínua:

~~~text
Q(t)
~~~

porque nodes reais envolvem enormes quantidades de portadores.

As duas descrições são válidas em suas escalas.

Se um node armazena milhões ou bilhões de cargas elementares, a aproximação contínua costuma ser excelente.

Em dispositivos extremamente pequenos ou single-electron devices, a discretização pode se tornar diretamente relevante.

O modelo precisa ser compatível com a escala analisada.

## Lei de Coulomb

Para duas cargas pontuais idealizadas no vácuo, separadas por distância r, a magnitude da força eletrostática é:

~~~text
F = (1 / (4π ε0)) × |q1 q2| / r²
~~~

onde:

~~~text
F   força [N]
q1  carga [C]
q2  carga [C]
r   separação [m]
ε0  permissividade do vácuo [F/m]
~~~

A direção está na linha que une as cargas.

A força é repulsiva para sinais iguais e atrativa para sinais opostos.

A lei de Coulomb é uma relação eletrostática idealizada.

Dispositivos reais possuem distribuições de carga, condutores, dielétricos, interfaces semicondutoras, geometrias complexas e fenômenos eletromagnéticos dependentes do tempo.

Mesmo assim, ela é fundamental porque o conceito de campo elétrico parte da mesma interação.

## Superposição

Nos modelos clássicos lineares utilizados aqui, contribuições de campo se superpõem.

Se várias cargas contribuem para o campo em um ponto:

~~~text
E_total = Σ E_i
~~~

A palavra vetor é essencial.

Campos podem se reforçar ou cancelar conforme a direção.

Somar apenas magnitudes produz resposta errada, exceto em geometrias especiais.

## Campo elétrico

Campo elétrico é definido pela força exercida sobre uma carga de teste positiva:

~~~text
E = F / q
~~~

As unidades SI podem ser escritas como:

~~~text
N/C
~~~

ou, de forma equivalente:

~~~text
V/m
~~~

Campo elétrico é um campo vetorial.

Em cada ponto do espaço ele possui magnitude e direção.

Conceitualmente:

~~~text
posição
    ↓
vetor de campo elétrico
    ↓
força sobre uma carga colocada ali
~~~

Para uma carga q:

~~~text
F = qE
~~~

Se q é negativa, a força aponta no sentido oposto ao vetor de campo.

Por isso a direção de drift dos elétrons pode ser oposta à direção da corrente convencional.

## Campo não é força

Um campo elétrico pode existir em determinado ponto mesmo sem uma carga de teste naquele ponto.

Força exige simultaneamente:

- um campo;
- uma carga submetida a esse campo.

É a mesma diferença conceitual existente entre campo gravitacional e peso de um objeto específico.

## Linhas de campo

Linhas de campo são ferramentas de visualização.

Elas indicam direção tangente ao campo e frequentemente usam densidade de linhas para sugerir intensidade.

Não são fios físicos e não são trajetórias obrigatórias para elétrons.

O movimento real de uma partícula depende de velocidade inicial, campos elétrico e magnético, colisões, estrutura de bandas do material e boundaries.

Linhas de campo representam o campo vetorial.

## Distribuições contínuas de carga

Dispositivos reais usam carga distribuída em volumes, superfícies e interfaces.

Formas usuais de densidade são:

~~~text
densidade linear      λ [C/m]
densidade superficial σ [C/m²]
densidade volumétrica ρ [C/m³]
~~~

O campo é obtido integrando as contribuições sobre a distribuição.

Capítulos posteriores usam densidade espacial de carga para explicar depletion regions e eletrostática MOS.

## Fluxo elétrico

Fluxo elétrico mede a passagem do campo por uma superfície.

Para um pequeno elemento de superfície orientado:

~~~text
dΦ_E = E · dA
~~~

O produto escalar seleciona a componente normal do campo.

Para uma superfície fechada:

~~~text
Φ_E = ∮ E · dA
~~~

Fluxo é útil porque a lei de Gauss conecta o campo integrado sobre uma superfície fechada com a carga contida.

## Lei de Gauss

No eletromagnetismo clássico:

~~~text
∮ E · dA = Q_enclosed / ε0
~~~

A lei se torna especialmente útil para cálculo quando a simetria permite retirar E da integral.

Exemplos idealizados incluem:

- distribuições esféricas;
- linhas infinitas;
- planos infinitos;
- geometrias simples de capacitor.

Uma lei pode ser universal e, ao mesmo tempo, ser computacionalmente conveniente apenas em certos casos.

## Condutores em equilíbrio eletrostático

Um condutor ideal em equilíbrio eletrostático possui propriedades importantes.

No interior do material condutor:

~~~text
E = 0
~~~

Se um campo interno persistente existisse, portadores livres continuariam se movendo e o estado não seria de equilíbrio eletrostático.

Carga estática excedente fica nas superfícies no modelo ideal.

O condutor também é equipotencial.

Esses conceitos serão usados em fios, shielding, capacitores, nodes de referência e condições de contorno.

## Energia potencial elétrica

Uma carga em um campo elétrico possui energia potencial elétrica.

Para duas cargas pontuais:

~~~text
U = (1 / (4π ε0)) × q1 q2 / r
~~~

usando o zero convencional em separação infinita.

Aqui o sinal é diretamente relevante.

U positivo para cargas de mesmo sinal representa trabalho necessário para aproximá-las desde o infinito.

U negativo para cargas opostas representa configuração atrativa ligada sob essa escolha de referência.

## Potencial elétrico

Potencial elétrico é energia potencial por unidade de carga:

~~~text
V = U / q
~~~

A unidade SI é o volt:

~~~text
1 V = 1 J/C
~~~

Potencial é um campo escalar.

Em cada ponto:

~~~text
posição
    ↓
valor de potencial elétrico
~~~

Isso é diferente do campo elétrico, que é vetorial.

## Diferença de potencial

Na maior parte do comportamento de circuitos, o que importa são diferenças de potencial.

Entre pontos A e B:

~~~text
ΔV = V_B - V_A
~~~

A diferença de potencial informa quanto a energia potencial muda por unidade de carga:

~~~text
ΔU = q ΔV
~~~

Essa equação é uma das pontes centrais entre teoria de campos e teoria de circuitos.

Uma carga de um coulomb atravessando um volt de diferença de potencial sofre mudança de energia de magnitude um joule, respeitando a convenção de sinais.

## Tensão é diferença de potencial

Em linguagem de circuitos, tensão significa diferença de potencial elétrico.

Dizer:

~~~text
node A está em 3.3 V
~~~

é incompleto sem uma referência implícita ou explícita.

Normalmente significa:

~~~text
V_A - V_referência = 3.3 V
~~~

Por isso tensão é medida entre dois pontos.

Uma ponta de osciloscópio também estabelece uma referência.

## Referência e ground

O zero de potencial pode ser escolhido.

Se todos os potenciais de um circuito forem aumentados pelo mesmo valor, as diferenças permanecem iguais.

O comportamento ordinário do circuito depende dessas diferenças.

Escolher um node chamado ground costuma definir:

~~~text
V_ground = 0
~~~

como referência conveniente.

Isso não significa automaticamente ligação física com a Terra.

Circuit ground, chassis ground e protective Earth são conceitos diferentes.

O capítulo de grounding e signal integrity irá separá-los.

## Relação entre campo e potencial

Em eletrostática:

~~~text
E = -∇V
~~~

Em uma dimensão:

~~~text
E_x = -dV/dx
~~~

O sinal negativo mostra que o campo aponta no sentido de potencial decrescente.

Para um campo uniforme em um eixo:

~~~text
ΔV = -E Δx
~~~

com sinais definidos pela direção escolhida.

Essa relação explica por que diferença espacial de tensão corresponde a campo elétrico.

É também a ponte para field-effect devices: gate voltage altera potencial eletrostático, que altera campo e distribuição de portadores.

## Gradiente

O gradiente ∇V é um vetor formado pelas taxas espaciais de variação do potencial escalar.

Em coordenadas cartesianas:

~~~text
∇V =
(∂V/∂x, ∂V/∂y, ∂V/∂z)
~~~

Uma grande variação de potencial em distância pequena cria grande campo.

Isso é particularmente importante em dispositivos semicondutores nanométricos, nos quais tensões moderadas podem gerar campos locais intensos.

## Por que potencial costuma ser mais conveniente

Campo elétrico é vetor.

Potencial é escalar.

Em muitos problemas eletrostáticos é mais simples obter o potencial e depois calcular o campo pelo gradiente.

Em semicondutores, potencial e densidade de carga são acoplados pela equação de Poisson.

## Equação de Poisson

Para potencial eletrostático em um meio de permissividade ε:

~~~text
∇²V = -ρ / ε
~~~

onde ρ é a densidade volumétrica de carga.

Se a região não possui carga volumétrica líquida:

~~~text
ρ = 0
~~~

então temos a equação de Laplace:

~~~text
∇²V = 0
~~~

Essas equações se tornam centrais na eletrostática de dispositivos.

Uma solução completa de semicondutor também acopla potencial, estatística de portadores e boundaries de materiais.

Este capítulo estabelece primeiro o significado das grandezas.

## Trabalho e independência de caminho

Em um campo eletrostático, o trabalho entre dois pontos depende apenas dos endpoints.

Equivalentemente:

~~~text
∮ E · dl = 0
~~~

ao redor de um caminho fechado no caso eletrostático.

Essa propriedade permite definir potencial escalar de forma consistente.

Campos magnéticos variáveis no tempo mudam essa situação.

A lei de Faraday introduz campos elétricos não conservativos.

Isso será tratado no capítulo de indução.

## Aproximação eletrostática

Eletrônica de computadores é dinâmica.

Sinais chaveiam, clocks oscilam e correntes mudam.

Por que começar com eletrostática?

Porque muitas relações locais são entendidas inicialmente assumindo que propagação e radiação podem ser desprezadas.

Essa aproximação quase-estática sustenta a teoria de circuitos concentrados.

Quando rise time é curto demais ou o interconnect é longo, propagation delay deixa de ser desprezível e linhas de transmissão passam a ser necessárias.

## Nodes concentrados

Teoria de circuitos comprime um problema espacial em variáveis de node.

Em vez de resolver V(x,y,z) em todo lugar, o modelo atribui potenciais aproximadamente uniformes:

~~~text
node A -> V_A
node B -> V_B
node C -> V_C
~~~

Components conectam nodes e impõem relações tensão-corrente.

A abstração é poderosa porque descarta geometria de campo irrelevante para o problema.

Sua validade é uma assumption que será revisitada em high-speed design.

## Energia ao mover carga por tensão

Se uma carga Q atravessa diferença de potencial ΔV:

~~~text
ΔU = Q ΔV
~~~

Se a carga se move continuamente, definimos corrente:

~~~text
I = dQ/dt
~~~

Derivando energia no tempo:

~~~text
P = dU/dt
  = V dQ/dt
  = VI
~~~

O próximo capítulo desenvolve corrente, resistência e potência.

Essa derivação mostra por que P = VI surge de energia por carga e carga por tempo.

## Electronvolt

Electronvolt é unidade conveniente em física de semicondutores.

Um electronvolt é a magnitude da energia adquirida por uma carga elementar atravessando um volt:

~~~text
1 eV
=
e × 1 V
=
1.602176634 × 10^-19 J
~~~

eV é unidade de energia, não de tensão.

Essa diferença é essencial ao interpretar band gaps.

## Potencial em semicondutores

Capítulos posteriores usam potencial eletrostático para explicar:

- band bending;
- depletion;
- built-in junction potential;
- accumulation;
- inversion;
- MOS threshold.

São consequências de campo, potencial e distribuição de carga no material.

Sem essa camada, afirmar que gate voltage controla o canal de um transistor permanece incompleto.

## Potencial em lógica CMOS

Uma porta CMOS transforma faixas de potencial elétrico em estados lógicos.

Conceitualmente:

~~~text
potencial elétrico no input
    ↓
campo elétrico na estrutura do transistor
    ↓
condutividade do canal muda
    ↓
output node carrega ou descarrega
    ↓
potencial do output entra em uma faixa válida
    ↓
próxima porta interpreta LOW ou HIGH
~~~

O valor booleano é uma abstração construída sobre faixas físicas de potencial.

## Logic level não é uma tensão exata

Uma família lógica define intervalos.

Conceitualmente:

~~~text
região LOW válida
região indefinida / de transição
região HIGH válida
~~~

Os thresholds dependem da tecnologia.

Noise margin mede quanto distúrbio pode existir entre levels garantidos de output e thresholds exigidos pelo input.

O tema será aprofundado depois de CMOS.

## Potencial e capacitância

Condutores separados podem armazenar cargas opostas.

A proporcionalidade:

~~~text
Q = CV
~~~

define capacitância em um modelo linear.

A energia armazenada no campo elétrico é:

~~~text
U = 1/2 C V²
~~~

Isso liga diretamente eletrostática a switching energy.

Um node CMOS tem capacitância mesmo sem capacitor discreto no schematic.

## Por que uma borda digital leva tempo

Mudar um node de LOW para HIGH exige mover carga.

Se existe capacitância, mudar potencial significa mudar carga armazenada.

Corrente finita produz tempo de transição finito.

A cadeia causal é:

~~~text
carga
    ↓
capacitância
    ↓
tensão do node
    ↓
tempo de carga
    ↓
propagation delay
    ↓
timing constraint / frequência máxima
~~~

Esse é um motivo direto para física elétrica importar à arquitetura de computadores.

## Sinalização diferencial

Um sinal single-ended é interpretado contra uma referência.

Um sinal diferencial é interpretado principalmente pela diferença:

~~~text
V_diff = V_plus - V_minus
~~~

Interfaces modernas de alta velocidade, como PCI Express, usam sinalização diferencial.

Impedância característica, common-mode, terminação e reflexões pertencem ao capítulo de transmission lines.

## Shielding eletrostático

Um condutor pode redistribuir carga superficial e restringir fortemente o campo no interior de uma região condutora fechada ideal.

Shielding real depende de frequência, aberturas, geometria e bonding.

Mesmo assim, o princípio eletrostático aparece em chassis, cabos, connector shells e estruturas de referência em PCBs.

## Descarga eletrostática

Separação de carga pode gerar grande diferença de potencial.

Se o campo for suficiente para formar um caminho rápido de descarga, ocorre ESD.

ESD pode danificar semicondutores porque estruturas muito pequenas sofrem campos e correntes locais intensos.

Software não corrige oxide breakdown.

A ISA assume que o hardware físico continua cumprindo o contrato digital.

## Análise dimensional

Unidades são uma primeira ferramenta de validação.

Exemplos:

~~~text
E = F/q
[N/C]

V = U/q
[J/C]

ΔU = qΔV
[C × J/C = J]

P = VI
[J/C × C/s = J/s = W]
~~~

Se as dimensões não se reduzem corretamente, a equação ou substituição provavelmente está errada.

Esse método continuará sendo útil em eletrônica e modelagem de sistemas.

## Convenções de sinal

Cálculos de engenharia escolhem referências.

Por exemplo:

~~~text
v_ab = V_a - V_b
~~~

Uma seta de corrente também pode ser escolhida em qualquer sentido.

Resultado negativo significa que a polaridade/direção física real é oposta à referência.

Não significa erro matemático.

## Grandezas escalares e vetoriais

Exemplos escalares:

~~~text
carga Q
potencial V
energia U
~~~

Exemplos vetoriais:

~~~text
campo elétrico E
força F
~~~

Capítulos posteriores acrescentam campo magnético e densidade de corrente.

Programadores acostumados a valores escalares em registradores não devem assumir que toda grandeza física é escalar.

## Fronteira entre modelo físico e modelo de circuito

Node voltage já é uma abstração.

O condutor real possui estado eletromagnético espacial.

Tratar todo o node com um único potencial pressupõe que propagation interna é desprezível para aquele problema.

Em baixas frequências ou pequenas dimensões, isso funciona muito bem.

Com edges rápidas e traces longas, o condutor precisa ser tratado como estrutura distribuída.

## Fronteira entre circuito e lógica

Uma waveform de tensão continua sendo analógica.

A lógica digital interpreta a waveform usando thresholds e timing windows:

~~~text
waveform contínua
    ↓
amostragem pelo receiver
    ↓
comparação com thresholds
    ↓
estado lógico
~~~

Se a waveform estiver na região inválida ou mudar perto da amostragem, a abstração digital pode falhar.

Metaestabilidade e timing tratam esse problema.

## Fronteira entre lógica e arquitetura

Arquitetura normalmente deixa de falar em volts.

Passa a falar em:

- bits;
- registradores;
- instruções;
- memória;
- interrupts.

Isso só é possível porque as camadas inferiores mantêm estados lógicos dentro dos limites elétricos e temporais.

A ISA é um contrato abstrato construído sobre confiabilidade física.

## Ligação com o ChrisOS

O ChrisOS opera muitas camadas acima de equações de campo, mas seu ambiente depende delas.

Uma cadeia representativa é:

~~~text
redistribuição de carga em transistores
    ↓
transição lógica CMOS
    ↓
bit de registrador muda
    ↓
instrução x86-64 termina
    ↓
write em MMIO torna-se visível
    ↓
device muda de estado
    ↓
ChrisOS observa interrupt ou resultado em memória
~~~

O ChrisOS não calcula a lei de Coulomb dentro de um interrupt handler.

Mas o hardware que ele consome emerge dos fenômenos definidos aqui.

## Ligação com ChrisCPU

ChrisCPU representa architectural state com variáveis de software.

Uma CPU física realiza estado arquitetural equivalente por circuitos.

Assim:

~~~text
campo de registrador no ChrisCPU
    representação de software do estado arquitetural

registrador físico
    realização elétrica do estado arquitetural
~~~

O emulator não precisa modelar carga, campo ou transistor delay enquanto o objetivo for equivalência arquitetural.

Modelagem de circuitos seria outra camada.

## O que este capítulo deixa para depois

Capítulos separados irão derivar:

- corrente em condutores;
- resistência e resistividade;
- lei de Ohm;
- potência;
- análise de circuitos por Kirchhoff;
- dinâmica de capacitores;
- indutância;
- impedância AC;
- indução eletromagnética;
- linhas de transmissão;
- bandas de semicondutores;
- eletrostática MOS;
- chaveamento de transistores.

Mantê-los separados evita reconstruir saltos de abstração dentro de um único capítulo genérico de eletrônica.

## Cálculos reproduzíveis

O checker deste capítulo valida:

- quantidade de cargas elementares por coulomb;
- magnitude de força de Coulomb;
- energia qΔV;
- conversão de electronvolt;
- diferença de potencial em campo uniforme;
- relações dimensionais entre campo, potencial e energia.

Ele não simula geometria real de semicondutores.

O objetivo é impedir drift numérico dos exemplos.

## Limite de validação

Este capítulo estabelece relações de eletrostática clássica usadas como pré-requisitos de circuitos e semicondutores.

As referências externas principais incluem MIT OpenCourseWare 8.02 Electricity and Magnetism, material SI do NIST e o SI Brochure do BIPM.

O próximo capítulo transforma movimento de carga e energia por carga nas grandezas de circuito tensão, corrente, resistência, energia e potência.

## Gatilhos de revisão

Revisar quando:

- a ordem dos fundamentos mudar;
- exemplos numéricos mudarem;
- capítulos posteriores exigirem conceito eletrostático ainda não definido;
- constantes/referências SI usadas pelo corpus mudarem;
- o projeto passar a incorporar simulação em nível de circuito ou dispositivo.
