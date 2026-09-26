---
id: pn-junction
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: maintained
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
