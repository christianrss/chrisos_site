---
id: atom-semiconductor
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- kernel/gfx/graphics.c
symbols:
- gfx_rgb
depends_on: []
related:
- crystal-bands-doping
- transistor-cmos
- pixels-framebuffer
---


# Átomo, carga elétrica e física de semicondutores

<div class="abstract">
Computadores digitais são máquinas de estados discretos construídas sobre fenômenos físicos contínuos. Este capítulo estabelece a cadeia física mínima necessária para compreender por que um transistor pode representar e transformar estado binário sem tratar uma porta lógica como um elemento inexplicado.
</div>

## Matéria e carga

Hardware eletrônico é constituído por átomos: núcleos contendo prótons e nêutrons, cercados por estados quânticos ocupados por elétrons. Para engenharia de computadores, o aspecto relevante não é um modelo planetário do átomo, mas a existência de partículas eletricamente carregadas e estados de energia permitidos.

O elétron possui carga elementar negativa. O próton possui carga de mesma magnitude e sinal positivo. Um corpo é eletricamente neutro quando sua carga líquida se equilibra. Uma diferença de potencial estabelece um campo elétrico; portadores móveis submetidos a esse campo podem produzir corrente.

Três grandezas aparecem continuamente no hardware:

| Grandeza | Significado | Unidade SI |
|---|---|---|
| carga `Q` | carga elétrica líquida | coulomb |
| tensão `V` | diferença de potencial, energia por unidade de carga | volt |
| corrente `I` | taxa de fluxo de carga, `dQ/dt` | ampere |

Resistência descreve a oposição ao fluxo de corrente. A lei de Ohm, `V = IR`, é uma relação macroscópica útil para condutores e elementos resistivos; a operação de transistores exige a física adicional de semicondutores e campos elétricos.

## Modelos, escalas e o significado de um estado eletrônico

Um orbital é um estado quântico, não uma pequena órbita clássica ao redor do núcleo. O quadrado do módulo de sua função de onda determina uma densidade de probabilidade para medições de posição segundo o modelo. Níveis de energia e ocupação dos estados disponíveis restringem o comportamento dos elétrons. Em um sólido, a organização coletiva dos átomos modifica os estados permitidos; transportar diretamente a imagem de um átomo isolado para um transistor produz um modelo incorreto.

Descrições diferentes são úteis em escalas diferentes. O tratamento quântico explica estados permitidos e bandas. Um modelo semiclássico de transporte descreve populações de portadores em movimento. A teoria de circuitos agrega tensão e corrente nos terminais. A lógica atribui valores discretos a faixas de condições elétricas. Passar entre essas descrições exige hipóteses; suas variáveis não se tornam intercambiáveis. Um booleano C não é um elétron, e um bit particular geralmente não corresponde a um elétron identificável atravessando o processador.

A distinção entre modelo e medição também é essencial. Um desenho de bandas representa intervalos permitidos e proibidos de energia. Não representa a altura física dos elétrons acima de uma superfície de silício. Um diagrama de energia potencial usa eixo espacial e eixo energético com unidades diferentes. Confundir os eixos transforma uma explicação de movimento dos portadores em uma imagem geométrica incorreta.

## Campos, força e energia potencial

O campo elétrico representa força por unidade de carga de teste positiva. Em uma descrição quase estática, um portador de carga `q` sofre força `F = qE`. Como o elétron possui carga negativa, sua força aponta no sentido oposto ao campo. A corrente convencional é definida pelo sentido do fluxo de cargas positivas, portanto deriva eletrônica e corrente podem apontar em sentidos opostos sem contradição.

Diferença de potencial mede variação de energia por carga. Para uma carga deslocada por `ΔV`, a variação de energia potencial é `ΔU = q ΔV`. Um volt corresponde a um joule por coulomb. Essa relação dimensional permite conferir cálculos: tensão multiplicada por carga fornece energia, enquanto tensão multiplicada por corrente fornece potência. Tensão não é quantidade de corrente, e carga não é uma taxa.

| Expressão | Dimensões | Interpretação |
|---|---|---|
| `I = dQ/dt` | C/s | Taxa de fluxo de carga |
| `ΔU = q ΔV` | C · J/C | Variação de energia potencial |
| `P = VI` | J/C · C/s | Potência elétrica |
| `C = Q/V` | C/V | Capacitância no modelo linear |
| `R = V/I` | V/A | Resistência para a relação operacional especificada |

As últimas linhas descrevem modelos de componentes. Capacitância ou resistência constantes podem ser adequadas em uma faixa e inadequadas em outra. Dispositivos não lineares exigem suas relações reais de terminais; os símbolos não garantem linearidade. Por isso, a lei de Ohm isoladamente não explica chaveamento MOSFET ou retificação por diodo.

## Armazenamento de carga e energia de comutação

Para um capacitor linear ideal, `Q = CV`. A energia eletrostática armazenada é `U = C V² / 2`, obtida pela integração do trabalho de acrescentar carga enquanto a tensão aumenta. Se uma capacitância de carga parte de zero e é carregada até uma alimentação `V` por um caminho resistivo, a fonte fornece `C V²`: metade é armazenada e metade dissipada no caminho simplificado. A descarga perde a metade armazenada, a menos que o circuito recupere energia deliberadamente.

O cálculo explica a dependência quadrática da energia de comutação em relação à tensão. Uma carga hipotética de 10 fF a 1 V armazena 5 fJ. Um ciclo completo de carga e descarga no modelo simples retira 10 fJ da fonte. São valores ilustrativos explícitos, não parâmetros medidos do processador do usuário. Demonstram por que reduzir tensão pode alterar substancialmente a energia mesmo sem mudar a operação booleana.

Um isolante ideal de gate bloqueia condução contínua, mas sua capacitância precisa ser carregada e descarregada quando a entrada muda. “Controlado por tensão” não significa, portanto, “sem necessidade de energia”. Fuga, corrente de curto-circuito durante transições e interconexões acrescentam custos. O comportamento energético visível ao software está várias camadas acima, mas não pode ser compreendido contando apenas resultados aritméticos e ignorando a frequência de comutação dos nós elétricos.

## Bandas de energia em sólidos

Quando muitos átomos formam um cristal, níveis individuais de energia se combinam em bandas de energias permitidas. Duas são centrais:

- a **banda de valência**, cujos elétrons participam das ligações;
- a **banda de condução**, cujos estados disponíveis permitem portadores móveis.

O intervalo energético entre elas é o **band gap**. Condutores possuem estados móveis prontamente acessíveis. Isolantes possuem gap grande, que reduz fortemente os portadores em condições usuais. Semicondutores ocupam a região útil intermediária: sua população de portadores pode ser controlada por temperatura, impurezas e campos elétricos.

O silício é particularmente útil porque sua estrutura cristalina e a formação de óxido permitem estruturas repetíveis cuja condutividade pode ser modificada localmente.

## Concentração de portadores, mobilidade e condutividade

Considere `n` como concentração de elétrons móveis, `p` como concentração de lacunas, `μ_n` como mobilidade eletrônica e `μ_p` como mobilidade de lacunas. Em um modelo simples de baixo campo, a condutividade é `σ = q(n μ_n + p μ_p)`, tomando `q` como o módulo positivo da carga elementar. Em material uniforme sob as hipóteses correspondentes, a densidade de corrente de deriva é proporcional ao campo. A relação separa quantidade de portadores disponíveis da facilidade com que respondem ao campo.

A separação importa porque acrescentar dopantes pode aumentar uma população e modificar simultaneamente espalhamento e mobilidade. A condutividade não é dedutível apenas de “mais elétrons” sem indicar o regime. Campos intensos, não uniformidade, interfaces e dimensões pequenas podem exigir modelos além da mobilidade constante. Uma equação introdutória é útil quando acompanhada desses limites.

Lacunas descrevem ausência de ocupação eletrônica em uma banda quase preenchida. Sua descrição como carga positiva efetiva resume a resposta coletiva sem exigir uma partícula positiva literal, idêntica a um próton, movendo-se pela rede. É uma linguagem econômica e precisa: lacuna é uma descrição por quasipartícula, enquanto um íon dopante é outra entidade física. Separá-los esclarece por que uma região tipo p não precisa possuir grande carga positiva líquida no volume.

## Dopagem

Silício cristalino puro é um semicondutor intrínseco. Circuitos integrados introduzem deliberadamente pequenas concentrações de átomos de impureza.

Material **tipo n** fornece elétrons adicionais que podem atuar como portadores majoritários. Material **tipo p** cria ausências de elétrons convencionalmente chamadas de lacunas, modeladas como portadores móveis positivos.

Dopagem não significa simplesmente tornar o silício "positivo" ou "negativo". O material macroscópico permanece aproximadamente neutro. Ela altera a densidade e o tipo de portador móvel e, portanto, o comportamento elétrico de junções e estruturas de efeito de campo.

## Deriva, difusão e equilíbrio

Um campo pode impulsionar portadores, produzindo deriva. Um gradiente de concentração também pode produzir fluxo líquido, denominado difusão. Em uma junção em equilíbrio térmico, contribuições opostas de transporte se equilibram, sem corrente externa líquida, embora o movimento microscópico continue. Equilíbrio é balanço de processos, não imobilidade dos elétrons.

O campo interno se desenvolve conforme a redistribuição de carga deixa dopantes ionizados expostos perto da interface. Cargas e potencial eletrostático estão acoplados: a distribuição de carga afeta o campo, e o campo afeta populações e movimento. A análise de dispositivos resolve condições eletrostáticas e de transporte compatíveis com hipóteses de contorno. Descrever uma junção apenas como dois blocos coloridos omite o mecanismo de seu comportamento elétrico.

A polarização aplicada muda condições nos terminais e altera o fluxo. A temperatura também modifica disponibilidade de portadores e transporte. O ponto de operação e o ambiente, portanto, importam. Não existe uma corrente universal associada a “uma junção de silício”, independente de geometria, dopagem, tensão e temperatura.

## Junção p-n

Ao colocar regiões p e n em contato, portadores inicialmente difundem pela fronteira e recombinam. Dopantes ionizados expostos produzem uma região de depleção e um campo elétrico interno. A barreira de potencial resultante torna a corrente fortemente dependente da polaridade aplicada.

A junção p-n explica o comportamento do diodo e continua fundamental dentro de circuitos integrados, embora a lógica CMOS moderna seja controlada principalmente por transistores de efeito de campo.

## Do campo elétrico à condução controlada

Um computador necessita de um dispositivo cujo estado condutivo seja controlado por outro sinal elétrico. O transistor MOS de efeito de campo fornece essa propriedade.

O passo essencial é o controle eletrostático: uma tensão aplicada a uma porta isolada modifica a distribuição de portadores em uma região semicondutora. Acima de uma condição de limiar, um canal condutivo pode surgir ou desaparecer. O terminal de controle não precisa conduzir a mesma corrente contínua que percorre o caminho controlado.

A separação entre **sinal de controle** e **caminho de corrente controlado** viabiliza redes lógicas extensas.

## Abstração binária

Nenhum fio físico contém um 0 ou 1 matemático. Um circuito digital define faixas de tensão interpretadas como níveis lógicos. Entre as faixas válidas existe margem destinada a tolerar ruído.

![Voltage ranges / faixas de tensão](../../assets/diagrams/voltage-levels.svg)

A abstração funciona porque portas posteriores restauram sinais analógicos degradados para níveis válidos. Projeto digital, portanto, depende de física analógica enquanto expõe comportamento discreto.

## Relação com sistemas operacionais

Um kernel manipula registradores, bits de page tables, flags de interrupção e registradores de dispositivos como se cada bit fosse exato. A máquina física armazena esses estados como cargas e tensões em redes de transistores. A confiabilidade da abstração vem de várias camadas de contratos discretos:

![From matter to code / da matéria ao código](../../assets/diagrams/foundations-chain.svg)

O sistema operacional não resolve equações de semicondutores durante a execução. Entretanto, volatilidade, atraso de propagação, frequência de clock, metastabilidade, estados de energia e falhas de hardware têm origem nesta camada física.

## Da confiabilidade física aos invariantes de software

A abstração de bit estável depende de margens elétricas, temporização apropriada e armazenamento funcional. Camadas superiores acrescentam invariantes próprios. O controlador mantém seu protocolo; a ISA define acessos observáveis; o alocador mantém propriedade; a função de framebuffer interpreta bytes como pixels. Essas obrigações se compõem, mas não se substituem.

Um pixel `0x00123456`, por exemplo, pode ser armazenado corretamente nas células e aparecer com canais trocados porque o software usou formato errado. Inversamente, empacotamento inteiro correto não repara uma falha física. No ChrisOS, `gfx_rgb` é o ponto de código onde vermelho, verde e azul se tornam campos de bits. A função implementa uma codificação acima da eletrônica; não modela movimento de portadores. A ligação com sua implementação exata é desenvolvida no capítulo de framebuffer.

A sequência de aprendizado precisa, portanto, preservar unidades, hipóteses e validação de cada modelo. Semicondutores explicam a possibilidade de estados elétricos controláveis e persistentes. Circuitos e lógica explicam sua composição. A arquitetura especifica o contrato consumido pelo kernel e emulado pelo ChrisCPU. Uma afirmação de uma camada só pode ser levada à seguinte quando a interface de ligação tiver sido explicada.

## Referências primárias

- [MIT 6.012 — Microelectronic Devices and Circuits](https://ocw.mit.edu/courses/6-012-microelectronic-devices-and-circuits-spring-2009/pages/lecture-notes/).
