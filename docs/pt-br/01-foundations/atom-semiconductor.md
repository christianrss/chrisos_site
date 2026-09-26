---
id: atom-semiconductor
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on: []
related:
  - transistor-cmos
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

## Bandas de energia em sólidos

Quando muitos átomos formam um cristal, níveis individuais de energia se combinam em bandas de energias permitidas. Duas são centrais:

- a **banda de valência**, cujos elétrons participam das ligações;
- a **banda de condução**, cujos estados disponíveis permitem portadores móveis.

O intervalo energético entre elas é o **band gap**. Condutores possuem estados móveis prontamente acessíveis. Isolantes possuem gap grande, que reduz fortemente os portadores em condições usuais. Semicondutores ocupam a região útil intermediária: sua população de portadores pode ser controlada por temperatura, impurezas e campos elétricos.

O silício é particularmente útil porque sua estrutura cristalina e a formação de óxido permitem estruturas repetíveis cuja condutividade pode ser modificada localmente.

## Dopagem

Silício cristalino puro é um semicondutor intrínseco. Circuitos integrados introduzem deliberadamente pequenas concentrações de átomos de impureza.

Material **tipo n** fornece elétrons adicionais que podem atuar como portadores majoritários. Material **tipo p** cria ausências de elétrons convencionalmente chamadas de lacunas, modeladas como portadores móveis positivos.

Dopagem não significa simplesmente tornar o silício "positivo" ou "negativo". O material macroscópico permanece aproximadamente neutro. Ela altera a densidade e o tipo de portador móvel e, portanto, o comportamento elétrico de junções e estruturas de efeito de campo.

## Junção p-n

Ao colocar regiões p e n em contato, portadores inicialmente difundem pela fronteira e recombinam. Dopantes ionizados expostos produzem uma região de depleção e um campo elétrico interno. A barreira de potencial resultante torna a corrente fortemente dependente da polaridade aplicada.

A junção p-n explica o comportamento do diodo e continua fundamental dentro de circuitos integrados, embora a lógica CMOS moderna seja controlada principalmente por transistores de efeito de campo.

## Do campo elétrico à condução controlada

Um computador necessita de um dispositivo cujo estado condutivo seja controlado por outro sinal elétrico. O transistor MOS de efeito de campo fornece essa propriedade.

O passo essencial é o controle eletrostático: uma tensão aplicada a uma porta isolada modifica a distribuição de portadores em uma região semicondutora. Acima de uma condição de limiar, um canal condutivo pode surgir ou desaparecer. O terminal de controle não precisa conduzir a mesma corrente contínua que percorre o caminho controlado.

A separação entre **sinal de controle** e **caminho de corrente controlado** viabiliza redes lógicas extensas.

## Abstração binária

Nenhum fio físico contém um 0 ou 1 matemático. Um circuito digital define faixas de tensão interpretadas como níveis lógicos. Entre as faixas válidas existe margem destinada a tolerar ruído.

```text
tensão contínua
       │
       ├── faixa baixa ──> 0 lógico
       │
       ├── região de transição / indefinida
       │
       └── faixa alta  ──> 1 lógico
```

A abstração funciona porque portas posteriores restauram sinais analógicos degradados para níveis válidos. Projeto digital, portanto, depende de física analógica enquanto expõe comportamento discreto.

## Relação com sistemas operacionais

Um kernel manipula registradores, bits de page tables, flags de interrupção e registradores de dispositivos como se cada bit fosse exato. A máquina física armazena esses estados como cargas e tensões em redes de transistores. A confiabilidade da abstração vem de várias camadas de contratos discretos:

```text
dispositivo semicondutor
    ↓
chaveamento de transistor
    ↓
porta lógica
    ↓
latch / flip-flop
    ↓
registrador ou célula de memória
    ↓
bit arquitetural
    ↓
contrato da ISA
    ↓
estrutura do kernel
```

O sistema operacional não resolve equações de semicondutores durante a execução. Entretanto, volatilidade, atraso de propagação, frequência de clock, metastabilidade, estados de energia e falhas de hardware têm origem nesta camada física.

## Limite do modelo

Esta documentação aprofunda física de semicondutores apenas até o necessário para explicar mecanismos computacionais. Mecânica quântica detalhada do estado sólido, química de fabricação e simulação de dispositivos pertencem à engenharia de semicondutores. O próximo capítulo parte da condução controlada para MOSFETs e lógica CMOS.
