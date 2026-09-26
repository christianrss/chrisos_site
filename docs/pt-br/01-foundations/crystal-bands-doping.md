---
id: crystal-bands-doping
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - atom-semiconductor
related:
  - pn-junction
  - transistor-cmos
---

# Estrutura cristalina, bandas de energia e dopagem

<div class="abstract">
O comportamento de um semicondutor não é explicado adequadamente pela frase de que o silício está “entre um condutor e um isolante”. O modelo de engenharia útil começa na estrutura cristalina periódica, nos estados eletrônicos permitidos e proibidos, no nível de Fermi, nas estatísticas de portadores e na forma como dopantes alteram a concentração de portadores sem destruir a neutralidade elétrica macroscópica. Essa cadeia é necessária para compreender junções, MOSFETs, leakage, limiar de condução e, por consequência, lógica digital.
</div>

## Do átomo isolado ao sólido

Um átomo isolado de silício possui estados quânticos discretos. Um cristal macroscópico contém enorme quantidade de átomos cujos estados eletrônicos interagem. O princípio de exclusão de Pauli impede que todos os elétrons ocupem um único estado, e o potencial periódico do cristal modifica o conjunto de estados de onda permitidos. Níveis atômicos discretos dividem-se, portanto, em conjuntos extremamente próximos que, em escala macroscópica, são tratados como bandas de energia.

A estrutura de bandas completa é resultado de mecânica quântica, mas a engenharia de sistemas digitais normalmente precisa de três consequências. Primeiro, elétrons só podem ocupar estados permitidos. Segundo, podem existir intervalos de energia sem estados possíveis. Terceiro, a capacidade de um material conduzir depende de quais estados estão ocupados e de haver estados vazios próximos para os quais portadores possam se mover quando submetidos a um campo elétrico.

No silício cristalino, cada átomo participa de ligações covalentes com seus vizinhos. Em baixa excitação, estados ligados formam a banda de valência. Estados de energia maior, nos quais os portadores podem deslocar-se pelo material, formam a banda de condução. Entre ambas existe uma faixa proibida: o band gap.

## Banda de valência, banda de condução e band gap

A banda de valência encontra-se normalmente quase preenchida. Uma banda completamente cheia não conduz da mesma maneira que uma banda parcialmente preenchida porque faltam estados próximos disponíveis. A banda de condução é, em condições usuais, muito menos ocupada. Elétrons promovidos para ela podem responder ao campo elétrico e atuar como portadores móveis.

O band gap, frequentemente representado por Eg, é a separação de energia entre o topo da banda de valência e a base da banda de condução.

| Classe de material | Condição eletrônica | Consequência de engenharia |
|---|---|---|
| condutor | muitos estados acessíveis próximos dos ocupados | corrente flui facilmente |
| semicondutor | faixa proibida moderada | densidade de portadores pode ser controlada |
| isolante | faixa proibida grande | densidade de portadores é muito pequena |

Essa classificação não é uma divisão absoluta da natureza. Temperatura, intensidade de campo, impurezas, defeitos cristalinos e geometria modificam o comportamento observado. A utilidade tecnológica dos semicondutores está justamente na possibilidade de controlar a população de portadores por muitas ordens de grandeza.

## Elétrons e lacunas

Quando um elétron é excitado para fora de um estado da banda de valência, permanece um estado desocupado. Rastrear cada ausência individual é pouco prático; a física do estado sólido introduz então a **lacuna**, um portador efetivo positivo que representa esse estado vazio.

A lacuna não é uma nova partícula elementar dentro do chip. É uma descrição quase-particular do comportamento coletivo dos elétrons em uma banda quase cheia. O modelo é útil porque permite representar correntes e transporte por densidades e mobilidades de elétrons e lacunas.

Três quantidades aparecem com frequência:

| Quantidade | Significado |
|---|---|
| n | concentração de elétrons |
| p | concentração de lacunas |
| ni | concentração intrínseca de portadores |

Em material intrínseco próximo do equilíbrio térmico, as concentrações são iguais: n = p = ni. O silício em temperatura comum possui alguma geração térmica de portadores, mas o material intrínseco sozinho não oferece o grau de controle necessário para circuitos digitais densos.

## Nível de Fermi

O nível de Fermi é uma referência energética associada à probabilidade de ocupação dos estados eletrônicos. Não deve ser interpretado simplesmente como “a energia dos elétrons”. Em equilíbrio, ele fornece uma maneira compacta de descrever a população de portadores.

Quando o nível de Fermi se aproxima da banda de condução, as condições favorecem maior população de elétrons. Quando se aproxima da banda de valência, favorecem maior população de lacunas. A dopagem altera essa relação de equilíbrio.

Esse conceito reaparece em diagramas de bandas de junções e estruturas MOS. Curvatura das bandas em relação ao nível de Fermi representa, de forma compacta, potencial eletrostático e redistribuição de portadores.

## Silício intrínseco, geração e recombinação

Mesmo um cristal ideal em temperatura acima do zero absoluto apresenta excitação térmica. Alguns elétrons recebem energia suficiente para atravessar o band gap e produzir pares elétron-lacuna. Recombinação é o processo inverso: um elétron de condução perde energia e ocupa um estado vazio da banda de valência.

No equilíbrio, geração e recombinação se compensam estatisticamente. O aumento de temperatura tende a elevar fortemente a concentração intrínseca de portadores. Isso ajuda a explicar por que leakage cresce com temperatura e por que projeto térmico interfere não apenas na confiabilidade, mas também no comportamento elétrico dos transistores.

Uma abstração digital pode nomear um nó como HIGH ou LOW, mas correntes de fuga e correntes de junção continuam sendo consequências de populações físicas de portadores.

## Dopagem como controle da densidade de portadores

Dopagem introduz pequenas concentrações controladas de átomos de impureza no silício. O dopante é escolhido para alterar a quantidade de portadores que podem ser disponibilizados com pouca energia.

Dopantes doadores fornecem elétrons adicionais; o material no qual elétrons são portadores majoritários é chamado **tipo n**. Dopantes aceitadores criam estados que favorecem lacunas; o material resultante é **tipo p**.

Os nomes não significam que uma região n carregue grande carga elétrica líquida negativa ou que uma região p esteja macroscopicamente positiva. No volume do material, dopantes ionizados e portadores móveis quase se compensam. A dopagem altera a concentração e o tipo dominante de portador, mantendo neutralidade aproximada longe de junções e regiões de depleção.

## Portadores majoritários e minoritários

Em material n, elétrons são majoritários e lacunas são minoritárias. Em material p, ocorre o inverso.

Portadores minoritários continuam fisicamente importantes. Corrente reversa de junções, recombinação, efeitos bipolares e diversos fenômenos transitórios dependem deles. Para construir a intuição inicial da lógica digital, entretanto, a concentração de majoritários explica por que uma região dopada pode se tornar muito mais condutiva do que silício intrínseco.

Uma relação de equilíbrio útil em condições não degeneradas é:

n × p ≈ ni²

Aumentar a população de um tipo de portador está associado à redução da população do outro. O modelo completo depende de temperatura, densidade de estados e nível de dopagem, mas essa relação ajuda a visualizar o caráter acoplado das duas populações.

## Condutividade e mobilidade

Concentração não determina sozinha a condutividade. Mobilidade representa quão eficientemente um portador adquire velocidade média de deriva quando submetido a um campo elétrico. Uma aproximação de primeira ordem é:

condutividade ≈ q × (n μn + p μp)

em que q é a magnitude da carga elementar e μn e μp são as mobilidades de elétrons e lacunas.

Dopagem eleva a quantidade de portadores, porém dopagem muito intensa também aumenta espalhamento e pode reduzir mobilidade. Projeto de semicondutores não consiste em maximizar um único parâmetro. É um compromisso entre condutividade, forma das junções, tensão de limiar, campo elétrico, capacitância, leakage e restrições de fabricação.

## Perfis espaciais de dopagem

Circuitos reais não possuem regiões uniformes e infinitas. A concentração de dopantes varia no espaço. Implantação iônica, difusão e etapas térmicas produzem perfis com profundidade e extensão lateral específicas.

O limite abrupto entre p e n é uma abstração útil, mas junções fabricadas apresentam transição finita. Transistores modernos empregam poços, extensões de source/drain, engenharia de canal e diversas estruturas adicionais para controlar campos elétricos e efeitos de canal curto.

A lição para a cadeia de abstrações de um sistema operacional é importante: um transistor não é uma chave ideal construída diretamente a partir de álgebra booleana. Ele é um dispositivo analógico cuidadosamente projetado para que camadas superiores possam tratá-lo, dentro de margens, como elemento lógico discreto.

## Diagramas de bandas como mapas de engenharia

Diagramas de bandas apresentam as bordas das bandas de condução e valência em função da posição. Eles não representam montanhas físicas existentes dentro do silício. Representam energias permitidas e potencial eletrostático.

Bandas aproximadamente planas indicam potencial espacialmente uniforme no modelo simplificado. Quando as bandas se curvam, a energia dos portadores varia com a posição. Em uma junção p-n ou superfície MOS, essa curvatura torna visível a barreira de potencial e ajuda a explicar atração, repulsão ou depleção de portadores.

É importante distinguir representações diferentes:

| Diagrama | Eixo horizontal | Explica |
|---|---|---|
| rede cristalina | posição física | arranjo atômico |
| estrutura E(k) | vetor de onda | estados de energia permitidos |
| bordas E(x) | posição física | barreiras eletrostáticas |

Misturar esses diagramas produz interpretações incorretas mesmo quando a terminologia parece correta.

## Por que a dopagem é a ponte para os dispositivos

Lógica digital precisa de regiões com tipos de portador previsíveis e de regiões cuja concentração possa ser alterada por campo elétrico. Dopagem fornece o pano de fundo fixo que viabiliza tanto junções quanto canais MOS.

    cristal de silício
        ↓
    bandas de energia
        ↓
    população térmica de portadores
        ↓
    dopagem doadora ou aceitadora
        ↓
    regiões n e p
        ↓
    junções e controle por campo
        ↓
    transistores
        ↓
    portas digitais

O próximo capítulo combina regiões dopadas para derivar região de depleção, potencial interno, polarização direta e reversa e a relação entre junções físicas e o comportamento de diodos.
