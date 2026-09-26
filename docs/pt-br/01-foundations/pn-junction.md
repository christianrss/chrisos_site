---
id: pn-junction
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
- crystal-bands-doping
related:
- transistor-cmos
---

# Junções P-N e interfaces semicondutoras

<div class="abstract">
A junção p-n é a primeira estrutura semicondutora em que regiões com dopagens distintas geram espontaneamente um campo elétrico autoconsistente. Ela introduz difusão, depleção, potencial interno, polarização, fuga reversa e breakdown. Esses mecanismos são necessários para compreender diodos, junções parasitas existentes dentro de CMOS, isolamento eletrostático e as restrições físicas que cercam a operação de MOSFETs.
</div>

## União de material tipo p e tipo n

Considere uma região tipo p colocada em contato com uma região tipo n. Antes do contato, cada volume é aproximadamente neutro, mas as concentrações de portadores móveis são diferentes. O lado n possui grande concentração de elétrons; o lado p possui grande concentração de lacunas.

Logo após a formação da interface, gradientes de concentração provocam difusão. Elétrons tendem estatisticamente a atravessar do lado n para o lado p, enquanto lacunas se deslocam do lado p para o lado n. Próximo da fronteira, portadores de sinais opostos recombinam.

Essa recombinação remove portadores móveis majoritários da região próxima à interface, mas deixa expostos íons dopantes fixos na rede cristalina. Doadores do lado n permanecem como carga positiva fixa; aceitadores do lado p permanecem como carga negativa fixa.

## Região de depleção

A região próxima da junção com baixa densidade de portadores majoritários móveis é chamada **região de depleção**. Ela não está vazia. Continua contendo a rede cristalina e dopantes ionizados; o que foi reduzido é a população de portadores móveis predominantes.

As cargas fixas separadas criam um campo elétrico orientado das cargas doadoras positivas para as aceitadoras negativas. Esse campo produz forças de deriva que se opõem à difusão original.

O equilíbrio surge quando a tendência de difusão, causada pelo gradiente de concentração, é compensada pela deriva causada pelo campo elétrico interno.

    volume p      região de depleção       volume n
    lacunas      - - - | + + +          elétrons
                    ← campo elétrico

Convenções de sinal em diagramas de potencial exigem cuidado, mas o fato físico central é simples: carga espacial fixa cria um campo que dificulta nova difusão de portadores majoritários.

## Potencial interno

A diferença de potencial eletrostático formada através da região de depleção é o **potencial interno** ou built-in potential. Sua magnitude depende das concentrações de dopagem, da temperatura e da concentração intrínseca de portadores.

Uma relação ideal comum é:

Vbi = (kT/q) ln(NA ND / ni²)

onde k é a constante de Boltzmann, T a temperatura absoluta, q a magnitude da carga elementar, NA a concentração de aceitadores, ND a concentração de doadores e ni a concentração intrínseca.

Mais importante do que memorizar a fórmula é entender a dependência: dopagem modifica a barreira de equilíbrio, enquanto temperatura altera tanto a tensão térmica kT/q quanto a concentração intrínseca.

## Corrente líquida nula não significa ausência de movimento

Em equilíbrio térmico, a corrente líquida nos terminais é zero, mas o movimento microscópico não cessou. Correntes estatísticas de difusão e deriva se compensam.

Essa distinção reaparece em muitas camadas da computação. Um estado estável não implica ausência de processos físicos. Células de memória, rails de alimentação e nós lógicos podem permanecer macroscopicamente estáveis enquanto correntes de fuga, movimento térmico e transições microscópicas continuam presentes.

## Polarização direta

Polarização direta reduz a barreira efetiva para injeção de portadores majoritários. Em uma junção p-n convencional, tornar o lado p mais positivo em relação ao lado n reduz a barreira.

Mais portadores atravessam a junção. Elétrons injetados no lado p tornam-se minoritários ali; lacunas injetadas no lado n tornam-se minoritárias. Esses portadores difundem e posteriormente recombinam. A corrente cresce rapidamente com a tensão aplicada.

A relação ideal do diodo é frequentemente escrita como:

I = Is (e^(V/(nVT)) − 1)

onde Is é a corrente de saturação, VT a tensão térmica e n um fator de idealidade. Dispositivos reais desviam desse modelo devido a resistência série, recombinação, alta injeção, geometria e temperatura.

Por isso a frase “diodo de silício conduz a 0,7 V” deve ser entendida como aproximação para determinada faixa de corrente e temperatura, não como um limiar físico universal.

## Polarização reversa

Polarização reversa aumenta a barreira e amplia a região de depleção. A condução por portadores majoritários torna-se muito pequena, mas geração e transporte de portadores minoritários mantêm uma corrente reversa finita.

Em campos elétricos suficientemente intensos surge breakdown. Em determinadas junções fortemente dopadas predomina tunelamento Zener; em outras condições predomina multiplicação por avalanche. Breakdown não é necessariamente destrutivo se corrente e potência forem limitadas, embora junções de lógica sejam normalmente mantidas muito abaixo de condições danosas.

## Capacitância de junção

A região de depleção separa cargas fixas e, por isso, apresenta comportamento capacitivo. Alterar a polarização reversa muda a largura da depleção e a distribuição de carga, produzindo capacitância dependente da tensão.

Em circuitos rápidos, capacitâncias não são detalhes secundários. Elas determinam energia de comutação, atraso e acoplamento. Junções source-body e drain-body de transistores contribuem com capacitâncias parasitas que precisam ser carregadas e descarregadas durante o chaveamento.

Essa é uma ponte direta entre física de dispositivos e timing digital: atrasos de propagação existem, em parte, porque nós reais armazenam energia elétrica.

## Armazenamento de portadores e recuperação

Uma junção fortemente polarizada diretamente pode acumular portadores minoritários em excesso. Ao retornar para polarização reversa, parte dessa carga precisa ser removida antes que a corrente seja bloqueada completamente. Esse fenômeno produz reverse recovery em diversas estruturas de diodo.

Lógica CMOS moderna não utiliza junções p-n comuns como elemento primário de chaveamento porque controle por efeito de campo é mais apropriado para lógica densa e baixo consumo estático. Junções, entretanto, continuam inevitavelmente presentes nas fronteiras entre regiões dopadas.

## Junções dentro de CMOS

Um NMOS fabricado em corpo tipo p possui source e drain tipo n. Cada uma dessas regiões forma uma junção p-n com o body. Em operação normal, essas junções são mantidas reversamente polarizadas. Relações complementares aparecem em PMOS construídos em poços tipo n.

Essas junções parasitas afetam:

- corrente de leakage;
- capacitância;
- isolamento eletrostático;
- risco de latch-up;
- caminhos de descarga eletrostática;
- body bias e tensão de limiar;
- limites admissíveis de tensão entre terminais.

O modelo ideal de quatro terminais de um MOSFET, portanto, está inserido em uma rede física maior de junções.

## Imperfeições de interface

Junções reais não são fronteiras matemáticas perfeitas. Defeitos cristalinos, estados de interface, contaminação e tensão mecânica podem criar centros de recombinação e geração e aumentar leakage.

A exigência extrema da fabricação de semicondutores decorre em parte disso. Arquiteturas digitais dependem de bilhões de dispositivos operando dentro de faixas estatísticas caracterizadas. Margens elétricas e regras de projeto existem porque variação microscópica não pode ser completamente removida.

## Da eletrostática da junção à eletrostática MOS

A junção p-n estabelece um princípio que será reutilizado: distribuição espacial de carga cria campo elétrico; campo elétrico altera distribuição de portadores; distribuição de portadores determina condutividade.

Uma estrutura MOS aplica o mesmo raciocínio em geometria diferente. Em vez de depender apenas da carga fixa exposta pela difusão, usa uma porta isolada para impor um campo elétrico na superfície do semicondutor.

    perfil de dopagem
        ↓
    difusão de portadores
        ↓
    carga espacial fixa
        ↓
    campo elétrico e barreira
        ↓
    transporte controlado por polarização
        ↓
    comportamento da junção
        ↓
    eletrostática da superfície MOS

O capítulo de transistores pode então ser entendido como continuação desse mesmo modelo de campo, carga e portadores, e não como uma troca abrupta de assunto.

## Derivação da largura de depleção pela equação de Poisson

Considere uma junção abrupta com densidade uniforme de aceitadores N_A no lado p e de doadores N_D no lado n. A junção metalúrgica fica em x = 0. Na aproximação de depleção, desprezam-se portadores móveis entre −x_p e x_n, enquanto as regiões neutras adjacentes têm campo desprezível. Aceitadores ionizados contribuem com densidade −qN_A e doadores com +qN_D. Isso aproxima um perfil contínuo de portadores, não significa ausência literal de todos eles.

A eletrostática unidimensional fornece dE/dx = rho/epsilon_s e E = −dphi/dx. Partindo de E = 0 na borda p da depleção, a integração dá E(x) = −qN_A(x + x_p)/epsilon_s no lado p. No lado n, E(x) = qN_D(x − x_n)/epsilon_s. A continuidade do campo em zero exige N_A x_p = N_D x_n: os módulos das cargas positivas e negativas descobertas devem coincidir.

O campo é negativo nessa escolha de coordenadas, apontando de n para p. Integrar −E pela depleção produz uma elevação positiva do potencial de p para n. Seu módulo é V_dep = q(N_A x_p² + N_D x_n²)/(2 epsilon_s). Com W = x_p + x_n e balanço de carga, resulta W = sqrt((2 epsilon_s/q)(1/N_A + 1/N_D)V_dep). Também x_p = W N_D/(N_A + N_D) e x_n = W N_A/(N_A + N_D).

![Carga, campo e potencial no modelo normalizado de junção abrupta](../../assets/diagrams/junction-profiles.svg)

O lado menos dopado contém, portanto, maior largura de depleção. Larguras iguais só são corretas para dopagens iguais nesse modelo. O módulo máximo do campo é qN_A x_p/epsilon_s, equivalentemente qN_D x_n/epsilon_s. Seu valor e distribuição espacial importam para ruptura; a tensão total não especifica isoladamente a intensidade local do campo.

## Exemplo dimensional e dependência da polarização

Adotem-se entradas ilustrativas N_A = 10^16 cm⁻³, N_D = 10^15 cm⁻³, n_i = 10^10 cm⁻³, epsilon_s = 1,04 × 10⁻¹² F/cm, q = 1,602 × 10⁻¹⁹ C e V_T = 0,02585 V. A expressão ideal de equilíbrio dá V_bi = V_T ln(N_A N_D/n_i²), aproximadamente 0,655 V. A substituição produz W aproximadamente 0,967 micrômetros, sendo cerca de 0,088 no lado p e 0,879 no lado n. São exemplos calculados com entradas declaradas, não parâmetros medidos de hardware do ChrisOS.

Sob polarização reversa moderada V_R, utiliza-se V_dep = V_bi + V_R. Três volts de polarização reversa aumentam a largura do exemplo para aproximadamente 2,285 micrômetros. Sob polarização direta V_F, a barreira eletrostática simples torna-se V_bi − V_F, mas extrapolar a fórmula até atravessar barreira zero é inválido. Injeção forte, resistência série e populações fora do equilíbrio exigem um modelo mais completo.

O potencial interno é uma diferença eletrostática interna, não uma bateria gratuita disponível nos terminais em equilíbrio térmico. Potenciais de contato e condições eletroquímicas de equilíbrio também devem integrar a análise do circuito completo de medição. Ignorar essa distinção implicaria incorretamente uma fonte perpétua de corrente em uma junção sem alimentação.

## Capacitância e condutância incrementais

O módulo da carga por área de cada lado é Q_A = qN_A x_p = qN_D x_n. Derivando em relação ao módulo da polarização reversa, obtém-se capacitância de depleção por área C_A = epsilon_s/W para a junção abrupta. Conforme a polarização reversa amplia a depleção, a capacitância diminui. Multiplicar pela área fornece a capacitância total antes de efeitos de borda e parasitas.

A condução direta introduz carga minoritária armazenada e, portanto, capacitância de difusão, um mecanismo diferente. Um modelo de pequenos sinais lineariza em torno de um ponto de operação. Para a exponencial ideal, a condutância incremental é g_d = I_S exp(V/(nV_T))/(nV_T), aproximadamente I/(nV_T) quando a corrente direta supera muito I_S. A resistência incremental correspondente é aproximadamente nV_T/I. Nenhuma delas é uma resistência constante do diodo em toda a faixa de tensão.

| Regime | Aspecto dominante do modelo | Atalho inválido |
|---|---|---|
| Equilíbrio térmico | Balanço de deriva e difusão | Tratar barreira interna como fonte externa |
| Reverso moderado | Ampliação da depleção e corrente de geração | Presumir corrente exatamente zero |
| Direto com baixa injeção | Injeção e difusão de minoritários | Atribuir uma tensão universal de condução |
| Direto intenso | Resistência série, aquecimento, alta injeção | Extrapolar indefinidamente a exponencial |
| Ruptura | Campo alto, multiplicação ou tunelamento | Presumir qualquer tensão reversa não destrutiva |

Essas distinções conectam junções aos elementos parasitas de CMOS e à carga vista por circuitos de comutação. Não estabelecem um simulador de diodos, modelo de processo ou proteção elétrica implementados pelo ChrisOS. A teoria é pré-requisito para interpretar dispositivos; afirmações de implementação posteriores devem retornar às próprias evidências de código. As [notas do MIT 6.012](https://ocw.mit.edu/courses/6-012-microelectronic-devices-and-circuits-spring-2009/pages/lecture-notes/) fornecem material primário sobre equilíbrio, características de terminais e capacitância de pequenos sinais.
