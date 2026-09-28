---
id: mos-capacitor
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - crystal-bands-doping
  - pn-junction
  - electric-charge-field-potential
  - capacitance-inductance
related:
  - transistor-cmos
  - cmos-switching-power
---

# Eletrostática do capacitor MOS

<div class="abstract">
O capacitor metal-óxido-semicondutor é o núcleo eletrostático da tecnologia MOS. Ele converte tensão de gate em redistribuição controlada de carga na superfície do semicondutor sem exigir condução CC direta através do dielétrico. O mesmo mecanismo de controle por campo se torna, no MOSFET, o mecanismo de controle do canal. Este capítulo deriva a estrutura MOS a partir de eletrostática, capacitância do óxido, diferença de função trabalho, tensão de flat-band, potencial de superfície, acumulação, depleção e inversão. Depois desenvolve carga de depleção, conceitos de threshold, comportamento C-V em baixa e alta frequência, cargas de interface, campo no óxido, scaling, equivalent oxide thickness e energia armazenada. A fronteira com o ChrisOS é explícita: a árvore atual não contém solver de dispositivo MOS nem modelo elétrico em nível de transistor; o capítulo é um pré-requisito físico para compreender o hardware sobre o qual o software executa.
</div>

## Pré-requisitos e escopo

São necessários:

- campo elétrico e potencial eletrostático;
- capacitância e energia armazenada no campo elétrico;
- bandas, nível de Fermi e dopagem;
- eletrostática de depleção da junção p-n;
- logaritmos e equações diferenciais unidimensionais.

A estrutura MOS pode ser representada como:

~~~text
condutor do gate
====================
óxido / dielétrico
--------------------
semicondutor
~~~~~~~~~~~~~~~~~~~~
contato de corpo
~~~

O gate é separado do semicondutor por um dielétrico isolante. Idealmente, nenhuma corrente CC permanente de gate é necessária para estabelecer o campo elétrico. A tensão do gate altera o potencial eletrostático próximo à superfície, e esse potencial modifica a concentração de portadores.

Primeiro será usado um modelo planar unidimensional ideal; depois serão introduzidas não idealidades. Isso não implica que transistores modernos sejam literalmente um único óxido clássico sobre substrato uniforme.

## Geometria e sistema de coordenadas

Considere x normal à superfície.

Uma convenção possível é:

~~~text
x < 0        gate
0..t_ox      óxido
x > t_ox     semicondutor
~~~

Para equações compactas, também é comum colocar a superfície do semicondutor em x = 0 e representar o óxido como elemento série separado. A origem é arbitrária desde que sinais sejam definidos consistentemente.

Grandezas importantes:

| Símbolo | Significado |
|---|---|
| t_ox | espessura do dielétrico |
| ε_ox | permissividade do dielétrico |
| ε_s | permissividade do semicondutor |
| C_ox | capacitância do óxido por área |
| V_G | tensão de gate em relação ao corpo |
| ψ_s | potencial de superfície em relação ao bulk |
| Q_s | carga líquida no semicondutor por área |
| Q_g | carga de gate por área |
| V_FB | tensão de flat-band |
| φ_F | magnitude do potencial de Fermi do bulk na convenção adotada |

Os sinais de ψ_s e Q_s dependem do tipo de substrato e da convenção. Acumulação e inversão abaixo usam explicitamente substrato tipo p.

## Capacitância do óxido

Para dielétrico uniforme ideal:

~~~text
C_ox = ε_ox / t_ox
~~~

A capacitância total para área A é:

~~~text
C_ox,total = A ε_ox / t_ox
~~~

O deslocamento elétrico no óxido ideal relaciona-se à carga por:

~~~text
D = ε_ox E_ox

Q_g = D
~~~

com sinal conforme a direção normal escolhida.

Reduzir t_ox ou usar dielétrico de maior permissividade aumenta a capacitância por área.

Isso fortalece o controle eletrostático, mas altera campo elétrico, tunelamento, dificuldade de fabricação e parasitas.

## Neutralidade de carga no empilhamento ideal

Ignorando carga fixa no óxido e na interface:

~~~text
Q_g + Q_s = 0
~~~

Essa é uma relação de capacitor.

A carga Q_s não precisa ser uma folha infinitamente fina. Em depleção, ela se distribui por uma região espacial de dopantes ionizados.

Em inversão, a carga total do semicondutor pode conter depleção e uma camada móvel de inversão.

Portanto o capacitor MOS não é apenas um capacitor de placas paralelas com segunda placa fixa.

## Decomposição da tensão de gate

Uma relação eletrostática útil é:

~~~text
V_G
=
V_FB
+
ψ_s
-
Q_s / C_ox
~~~

em uma convenção comum em que Q_s é carga por área no semicondutor.

A equação separa:

- offset de flat-band;
- variação de potencial dentro do semicondutor;
- queda de tensão no óxido.

Livros podem apresentar sinais equivalentes diferentes conforme a convenção de Q_s e ψ_s. O conteúdo físico é o mesmo: a tensão aplicada é dividida entre o dielétrico e a eletrostática do semicondutor.

## Diferença de função trabalho

Mesmo com tensão externa zero, gate e semicondutor podem ter funções trabalho diferentes.

Defina:

~~~text
Φ_MS = Φ_M - Φ_S
~~~

onde Φ_M e Φ_S representam as funções trabalho do gate e do semicondutor em unidades consistentes.

Para óxido ideal sem carga fixa, a tensão necessária para deixar as bandas planas está relacionada a essa diferença.

Com carga efetiva de óxido/interface Q_ox:

~~~text
V_FB = Φ_MS - Q_ox / C_ox
~~~

como aproximação de primeira ordem.

Em um dispositivo real Q_ox pode representar populações de carga distintas e espacialmente distribuídas.

## Condição de flat-band

Flat-band significa que as bandas do semicondutor não estão encurvadas por campo elétrico macroscópico próximo à superfície no modelo unidimensional.

Em flat-band:

~~~text
ψ_s = 0
~~~

e a região de espaço carregado associada ao bending MOS desaparece no modelo.

Flat-band não significa:

- ausência de movimento microscópico;
- função trabalho idêntica;
- ausência de campos atômicos;
- capacitância zero.

Significa apenas ausência de band bending macroscópico no semicondutor sob a convenção usada.

## Caso de referência com substrato tipo p

Considere substrato uniformemente dopado tipo p com concentração aceitora N_A.

No bulk, buracos são portadores majoritários.

A tensão de gate altera as populações da superfície.

Regimes canônicos:

~~~text
gate negativo
    -> acumulação

gate levemente/moderadamente positivo
    -> depleção

gate mais positivo
    -> inversão
~~~

Para substrato tipo n, papéis dos portadores e polaridades se invertem.

## Acumulação

Gate suficientemente negativo atrai buracos para a interface óxido-semicondutor.

A concentração superficial de buracos supera a do bulk.

~~~text
carga negativa no gate
       ||
óxido  ||
       ||
+++++++    buracos acumulados
semicondutor tipo p
~~~

A carga induzida é majoritariamente móvel e se concentra próximo à superfície.

No limite ideal quase-estático, a capacitância total em forte acumulação aproxima-se de C_ox porque o semicondutor funciona como placa condutora efetiva perto da interface.

## Depleção

Gate positivo repele buracos da superfície.

A região depletada expõe aceitadores ionizados, fixos na rede cristalina.

Na aproximação de depleção unidimensional:

~~~text
ρ(x) ≈ -q N_A
~~~

dentro de largura W_d.

A equação de Poisson é:

~~~text
d²ψ/dx² = -ρ/ε_s
~~~

portanto:

~~~text
d²ψ/dx² = q N_A / ε_s
~~~

na convenção adotada.

## Largura de depleção

Integrando Poisson com campo nulo na borda da região depletada:

~~~text
W_d
=
sqrt(
  2 ε_s ψ_s / (q N_A)
)
~~~

para potencial superficial positivo no caso de substrato tipo p.

A magnitude da carga de depleção por área é:

~~~text
|Q_d|
=
q N_A W_d
=
sqrt(
  2 q ε_s N_A ψ_s
)
~~~

A capacitância de depleção por área é:

~~~text
C_dep
=
ε_s / W_d
~~~

À medida que W_d cresce, C_dep diminui.

## Capacitância série em depleção

O pequeno sinal aplicado ao gate vê C_ox em série com C_dep:

~~~text
1/C_MOS
=
1/C_ox
+
1/C_dep
~~~

ou:

~~~text
C_MOS
=
(C_ox C_dep) / (C_ox + C_dep)
~~~

A capacitância medida cai abaixo de C_ox em depleção.

Esse comportamento mostra que a separação efetiva de carga se estende para dentro do semicondutor.

## Potencial de superfície e concentração de portadores

Em estatística não degenerada e perto do equilíbrio, concentrações variam aproximadamente de forma exponencial com o potencial eletrostático.

No substrato tipo p, aumentar o potencial superficial positivo reduz buracos e aumenta elétrons.

A progressão física é:

~~~text
potencial superficial positivo
        ↓
band bending
        ↓
buracos depletados
        ↓
concentração de elétrons cresce
        ↓
superfície pode tornar-se tipo n em relação ao bulk tipo p
~~~

Isso é inversão.

## Inversão forte

A inversão forte é convencionalmente associada a potencial superficial próximo de duas vezes a magnitude do potencial de Fermi do bulk no modelo clássico de canal longo.

Defina:

~~~text
φ_F
=
V_T ln(N_A / n_i)
~~~

para substrato tipo p não degenerado, onde:

~~~text
V_T = kT/q
~~~

A condição clássica é:

~~~text
ψ_s ≈ 2 φ_F
~~~

Nesse ponto, no modelo idealizado, a concentração superficial de elétrons torna-se comparável à concentração majoritária de buracos do bulk antes da inversão.

Isso é uma convenção de threshold baseada em modelo, não uma transição física abrupta.

## Construção da tensão de threshold

Uma expressão idealizada de canal longo para NMOS é:

~~~text
V_TN
=
V_FB
+
2 φ_F
+
|Q_d,max| / C_ox
~~~

com:

~~~text
|Q_d,max|
=
sqrt(
  4 q ε_s N_A φ_F
)
~~~

para body-source bias zero.

Assim, threshold depende de:

- diferença de função trabalho;
- capacitância do óxido;
- dopagem;
- temperatura;
- carga no óxido/interface;
- body bias.

Dispositivos modernos exigem modelos mais completos.

## Carga de inversão além do threshold

Após formar inversão forte, aumentar V_G não apenas continua alargando a depleção indefinidamente.

Grande parte da carga incremental do gate é balanceada por carga móvel de inversão.

Uma relação simplificada é:

~~~text
Q_inv
≈
-C_ox (V_G - V_TN)
~~~

para referência local adequada e ignorando efeitos de segunda ordem.

Essa relação faz a ponte do capacitor MOS para o canal do MOSFET.

O MOSFET acrescenta source e drain, permitindo condução lateral pela camada de inversão.

## Diagramas de bandas

O diagrama de bandas mostra energia eletrônica em função da posição.

O bending das bandas no semicondutor representa variação do potencial eletrostático.

Como o elétron possui carga negativa, energia potencial eletrônica varia com sinal oposto ao potencial elétrico.

O diagrama não representa literalmente colinas mecânicas.

Três visões são complementares:

| Visão | Objetivo |
|---|---|
| seção transversal | geometria e materiais |
| diagrama de carga | cargas no gate, depleção e inversão |
| diagrama de bandas | energética e potencial de superfície |

Separar essas representações evita confundir geometria, carga e energia.

## Campo elétrico no óxido

Para óxido ideal:

~~~text
E_ox
≈
V_ox / t_ox
~~~

e:

~~~text
V_ox = -Q_s / C_ox
~~~

na convenção adotada.

Campo elevado pode causar:

- tunelamento;
- aprisionamento de carga;
- degradação dependente do tempo;
- breakdown.

Reduzir t_ox melhora acoplamento eletrostático, mas aumenta desafios de campo e leakage.

## Equivalent oxide thickness

Dielétricos high-k permitem espessura física maior com capacitância semelhante à de SiO2 mais fino.

Uma forma idealizada de EOT é:

~~~text
EOT
=
t_high-k
·
(ε_SiO2 / ε_high-k)
~~~

EOT menor corresponde a capacitância maior por área.

Stacks reais podem conter camadas interfaciais, efeitos quânticos e capacitâncias série adicionais.

## Corrente de gate e tunelamento

No capacitor ideal, corrente CC através do dielétrico é zero.

Dielétrico real muito fino pode apresentar tunelamento quântico.

Assim:

~~~text
modelo ideal:
    corrente de gate = 0

stack real escalado:
    corrente de gate pode ser finita
~~~

Essa diferença é importante para potência estática e confiabilidade.

## Estados de interface

A interface óxido-semicondutor pode conter estados eletrônicos dentro do band gap.

Esses estados podem capturar e emitir carga em função de:

- potencial superficial;
- temperatura;
- frequência de medição;
- constantes de tempo de captura/emissão.

Eles podem alterar:

- V_FB;
- threshold;
- subthreshold;
- capacitância medida;
- ruído.

Portanto uma curva C-V real pode divergir da ideal mesmo com t_ox conhecido.

## Carga fixa e carga iônica

Dielétricos reais podem conter carga adicional.

Uma alteração de primeira ordem em tensão aparece como:

~~~text
ΔV = -Q_ox / C_ox
~~~

para carga efetiva adequadamente definida.

Sinal e localização espacial importam.

Processamento controla não apenas geometria, mas também defeitos e contaminação.

## C-V quase-estática

Em frequência suficientemente baixa, portadores minoritários podem responder ao pequeno sinal.

Para substrato tipo p:

~~~text
V_G negativo:
    acumulação
    C ≈ C_ox

V_G crescente:
    depleção
    C diminui

inversão forte quase-estática:
    carga de inversão responde
    C pode voltar em direção a C_ox
~~~

A curva exata depende de área, temperatura, dopagem e não idealidades.

## C-V em alta frequência

Em alta frequência, portadores minoritários podem não acompanhar a perturbação AC.

Então a capacitância em forte inversão pode permanecer próxima do mínimo série:

~~~text
C_min
≈
(C_ox C_dep,max)
/
(C_ox + C_dep,max)
~~~

em vez de retornar a C_ox.

Por isso “a capacitância em inversão” não é um único valor sem especificar a condição de medição.

## Deep depletion

Se V_G é varrido rápido demais para portadores minoritários estabelecerem inversão de equilíbrio, W_d pode crescer temporariamente além do máximo de equilíbrio.

Esse estado é deep depletion.

É uma condição de medição fora de equilíbrio.

Geração de portadores tende a alterar a condição com o tempo.

## Pequeno sinal versus grande sinal

A eletrostática de grande sinal estabelece o ponto operacional.

A capacitância incremental é:

~~~text
C = dQ/dV
~~~

ao redor desse ponto.

Logo um dispositivo não linear pode apresentar capacitância dependente de bias.

A expressão εA/t descreve diretamente o óxido ideal, não necessariamente a capacitância terminal total em todos os regimes.

## Energia armazenada

Para capacitor linear ideal:

~~~text
E = 1/2 C V²
~~~

Para capacitor MOS não linear, energia incremental se relaciona mais geralmente à integral de carga e tensão:

~~~text
E = ∫ V dQ
~~~

ou, em parametrização equivalente:

~~~text
E = ∫ Q dV
~~~

com limites e sinais definidos.

A aproximação 1/2 C V² continua útil para estimativas digitais quando C é tratada como aproximadamente constante no swing.

## Scaling eletrostático

Reduzir dimensões altera várias grandezas simultaneamente.

Reduzir espessura dielétrica tende a:

- aumentar C_ox;
- fortalecer controle do gate;
- aumentar campo para tensão fixa;
- aumentar sensibilidade a tunelamento.

Aumentar dopagem pode:

- reduzir W_d;
- alterar V_T;
- aumentar capacitâncias de junção;
- afetar mobilidade e variabilidade.

Reduzir V_DD diminui campo e energia dinâmica, mas reduz headroom.

Scaling é otimização acoplada.

## Fronteira de short-channel

O capacitor MOS clássico é unidimensional.

MOSFET de canal curto possui campos laterais de source e drain além do controle vertical do gate.

Efeitos como:

- drain-induced barrier lowering;
- velocity saturation;
- short-channel threshold shift;
- interação entre regiões de depleção;

não são capturados pelo capacitor MOS simples.

Ainda assim, ele isola e explica o mecanismo eletrostático vertical.

## Dependência de temperatura

Temperatura altera:

- kT/q;
- n_i;
- mobilidade;
- geração/recombinação;
- leakage;
- threshold.

A expressão de φ_F depende de temperatura tanto por V_T quanto por n_i.

Logo threshold não deve ser tratado como constante universal.

## Variabilidade

Dispositivos reais variam por:

- espessura do dielétrico;
- função trabalho;
- estatística de dopantes;
- densidade de traps;
- line-edge roughness;
- stress local;
- gradientes de processo.

Lógica digital é projetada com margens para sobreviver a uma distribuição caracterizada de parâmetros.

## Falhas e confiabilidade

Stacks MOS podem degradar ou falhar por:

- campo elétrico excessivo;
- breakdown do dielétrico;
- trapping de carga;
- mecanismos associados a hot carriers;
- bias-temperature instability em contextos de transistor;
- contaminação e leakage.

Modelos detalhados dependem de material, geometria, campo, temperatura e tempo.

Nenhum número de vida útil é atribuído aqui a processadores que executem ChrisOS.

## Fronteira de segurança

Eletrostática MOS não possui nível de privilégio de software.

Fenômenos físicos podem participar de:

- fault injection por glitch de tensão;
- leakage dependente de dados;
- canais laterais eletromagnéticos;
- mecanismos de distúrbio em memórias.

Esses temas exigem modelos de ameaça e medições separados.

A física explica por que canais físicos existem, não prova vulnerabilidade específica do ChrisOS.

## Fronteira arquitetural do ChrisOS

Na revisão da3df29cb397932c43d32373871fb9380e688ade, buscas no repositório não encontraram solver elétrico de MOSFET, capacitor MOS ou capacitância de dispositivo.

Portanto este capítulo declara intencionalmente:

~~~text
sources: []
symbols: []
~~~

Nenhuma implementação é atribuída.

A fronteira é:

~~~text
eletrostática MOS
      ↓
transistor no hardware físico
      ↓
gates e células de armazenamento
      ↓
microarquitetura
      ↓
ISA e contratos de dispositivo
      ↓
ChrisOS / ChrisVM
~~~

O software executa sobre a abstração produzida pelas camadas inferiores.

## Inicialização

Um capacitor MOS físico não possui sequência de inicialização de sistema operacional.

O bias estabelece estado eletrostático continuamente conforme materiais, campo e carga.

Não existe função atual do ChrisOS que inicialize óxido, depleção ou inversão.

Logo nenhum fluxo de kernel é atribuído aqui.

## Estado e estruturas de dados

O estado físico inclui:

~~~text
ψ(x)
E(x)
ρ(x)
n(x)
p(x)
Q_g
Q_d
Q_inv
~~~

São variáveis de campo e portadores, não estruturas C do ChrisOS.

Um simulador semicondutor poderia discretizá-las em mesh/arrays.

O ChrisOS atual não faz isso.

## Algoritmos e complexidade

Equações fechadas como C_ox e W_d são avaliadas em tempo constante.

Um solver numérico poderia resolver Poisson e transporte acoplados de forma iterativa em malha espacial.

A complexidade dependeria de:

- tamanho da malha;
- dimensionalidade;
- iterações não lineares;
- esparsidade da matriz;
- solver e precondicionador.

Nenhum algoritmo desses é atribuído ao ChrisOS porque não existe no código revisado.

## Propriedade de memória e ABI

O capacitor MOS físico não possui heap owner nem ABI de software.

Um simulador futuro precisaria definir propriedade para estado de malha e parâmetros.

Nenhuma ABI atual do ChrisOS expõe:

- carga do gate;
- ψ_s;
- W_d;
- campo no óxido;
- densidade de traps.

Essas grandezas estão abaixo da abstração de software.

## Concorrência

A dinâmica de portadores ocorre fisicamente de forma paralela no material.

Isso não equivale a threads ou locks.

Nenhuma ordem de locks do ChrisOS se aplica à eletrostática MOS.

Se simulação fosse implementada futuramente, ela precisaria de contrato próprio de concorrência e determinismo.

## Evidência de validação deste capítulo

O checker determinístico valida relações idealizadas:

~~~text
capacitância do óxido:
    C_ox = ε_ox / t_ox

largura de depleção:
    W_d = sqrt(2 ε_s ψ_s / (q N_A))

carga de depleção:
    |Q_d| = q N_A W_d

capacitância de depleção:
    C_dep = ε_s / W_d

capacitância MOS série:
    C_MOS = C_ox C_dep / (C_ox + C_dep)

potencial de Fermi:
    φ_F = V_T ln(N_A/n_i)

threshold clássico:
    V_TN = V_FB + 2φ_F + |Q_d,max|/C_ox

inversão forte:
    ψ_s ≈ 2φ_F

equivalent oxide thickness:
    EOT = t_high-k ε_SiO2/ε_high-k

energia:
    E = 1/2 C V²
~~~

O checker usa constantes ilustrativas declaradas.

Ele não valida um dispositivo fabricado.

## Limitações atuais

Este capítulo não fornece:

- process deck de foundry;
- modelo compacto BSIM;
- confinamento quântico;
- solução Schrödinger-Poisson;
- simulação short-channel;
- dados C-V medidos;
- previsão de vida útil do dielétrico;
- medições transistor-level de hardware ChrisOS.

Esses temas pertencem a modelagem de dispositivo/processo e caracterização física.

## Fronteira do roadmap

A progressão física é:

~~~text
dopagem e bandas
        ↓
eletrostática da junção p-n
        ↓
eletrostática MOS
        ↓
acumulação / depleção / inversão
        ↓
carga de inversão
        ↓
controle do canal MOSFET
        ↓
lógica CMOS
        ↓
delay e potência de chaveamento
~~~

O capítulo transistor-cmos usa esse fundamento.

O capítulo seguinte, cmos-switching-power, desenvolve energia, delay e atividade ao carregar nós CMOS reais.

## Proveniência da revisão

A fronteira do repositório foi revisada contra ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

Buscas por MOSFET, MOS capacitor e capacitance não encontraram implementação física de dispositivo nessa revisão; por isso sources e symbols permanecem vazios.

A teoria foi conferida com material do MIT 6.012 sobre estrutura MOS, acumulação, depleção e inversão. Grandezas e unidades SI seguem a BIPM SI Brochure, 9ª edição versão 4.01 publicada em junho de 2026.
