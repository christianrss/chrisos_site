---
id: logic-levels-noise-margins
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - chrisvm/chris_arch.h
  - chrisvm/cpu/emulator/chriscpu.c
  - kernel/gfx/graphics.c
symbols:
  - ChrisArchitectureState
  - cpu_run
  - gfx_rgb
depends_on:
  - transistor-cmos
  - cmos-switching-power
  - noise-grounding-signal-integrity
related:
  - boolean-algebra
  - combinational-logic
  - clock-timing
  - transmission-lines-differential-signals
---

# Níveis lógicos, limiares, fan-out e margens de ruído

<div class="abstract">
Um valor binário não é uma tensão. Hardware digital atribui faixas de tensão contínua a estados lógicos e deixa uma região de transição na qual não há garantia de que um receptor interprete a entrada como qualquer um dos dois estados. Este capítulo define limites de entrada e saída, margem de ruído estática, corrente de acionamento, fan-out, carregamento, histerese, tradução de nível e a interação entre integridade de sinal e temporização. Também delimita a fronteira de abstração do ChrisOS: as fontes inspecionadas do ChrisCPU e do kernel manipulam bits arquiteturais e valores inteiros; elas não modelam limiares VIH/VIL em nível de placa, capacidade de drive CMOS nem margens de ruído analógicas.
</div>

## Pré-requisitos e escopo

Os pré-requisitos são a operação de MOSFET/CMOS, energia e atraso de comutação CMOS e as origens elétricas de ruído e deslocamento de referência de terra. O objetivo aqui é conectar o comportamento em nível de transistor à abstração booleana utilizada pela arquitetura digital.

A fronteira de abstração é:

~~~text
forma de onda contínua de tensão/corrente
                 |
                 v
       limiares de entrada do receptor
                 |
                 v
        LOW ou HIGH reconhecido
                 |
                 v
       estado booleano / arquitetural
~~~

Uma interface digital robusta deve garantir que a faixa de saída do driver no pior caso permaneça dentro da faixa de entrada garantida do receptor, ao mesmo tempo em que atende às restrições de corrente, temporização e valores máximos absolutos.

## Quatro limites, não um único limiar

Folhas de dados normalmente distinguem garantias de entrada das garantias de saída.

| Símbolo | Significado | Direção da garantia |
|---|---|---|
| V_IL(max) | maior tensão de entrada garantida como LOW | entrada <= limite é LOW |
| V_IH(min) | menor tensão de entrada garantida como HIGH | entrada >= limite é HIGH |
| V_OL(max) | maior tensão de saída garantida para LOW sob a carga declarada | saída <= limite |
| V_OH(min) | menor tensão de saída garantida para HIGH sob a carga declarada | saída >= limite |

O intervalo entre V_IL(max) e V_IH(min) não é um terceiro valor lógico. Ele é uma **região de entrada indefinida** para o contrato estático da interface. Um dispositivo específico comutará em algum ponto de sua característica de transferência, mas esse ponto real varia com processo, tensão, temperatura, taxa de variação do sinal e topologia do circuito. Um projeto que dependa de um ponto de comutação típico, em vez de limites garantidos, perde sua prova de pior caso.

Para uma entrada CMOS comum, sem Schmitt trigger, uma curva conceitual útil é:

~~~text
LOW reconhecido       indefinido          HIGH reconhecido
<----------------|------------------|-------------------->
               V_IL(max)          V_IH(min)
0 V                                                   V_CC
~~~

Os limites exatos pertencem à família lógica e às condições de operação selecionadas. Eles não devem ser deduzidos de uma fração genérica de V_CC quando a folha de dados do componente estabelece outro contrato.

O *Logic Guide* da Texas Instruments, por exemplo, mostra que entradas compatíveis com TTL a 5 V e entradas CMOS a 5 V têm faixas garantidas diferentes; a Nexperia documenta igualmente limites de entrada e saída dependentes da família e da tensão de alimentação. A consequência arquitetural é direta: "0" e "1" são contratos de interface, não tensões universais.

## Margens de ruído estáticas

Um driver e um receptor são estaticamente compatíveis quando o pior HIGH conduzido é suficientemente alto para o receptor e o pior LOW conduzido é suficientemente baixo:

[
V_{OH(min,driver)} ge V_{IH(min,receiver)}
]

[
V_{OL(max,driver)} le V_{IL(max,receiver)}
]

O orçamento de tensão restante é a margem de ruído estática:

[
NM_H = V_{OH(min)} - V_{IH(min)}
]

[
NM_L = V_{IL(max)} - V_{OL(max)}
]

Ambas devem ser positivas para uma conexão direta convencional nas condições especificadas. Se um driver garante V_OH(min)=2,4 V e o receptor exige V_IH(min)=2,0 V, a margem estática de nível alto é 0,4 V. Isso **não** significa que qualquer transiente arbitrário de 0,4 V seja inofensivo: duração do pulso, largura de banda do receptor, ringing, overshoot, ground bounce e abertura temporal de amostragem continuam relevantes.

Margem de ruído é, portanto, um orçamento no domínio da tensão, não uma prova completa de integridade de sinal.

## Dependência dos níveis de saída em relação à carga

Uma saída não é uma fonte de tensão ideal. As redes de pull-up e pull-down têm impedância finita. Por isso, folhas de dados especificam V_OH e V_OL juntamente com condições de corrente de saída.

Um modelo de primeira ordem, semelhante a Thévenin, para uma saída HIGH é uma fonte próxima de V_CC com resistência efetiva R_OH. Sob magnitude de corrente fornecida I_OH:

[
V_{OH} approx V_{CC} - |I_{OH}|R_{OH}
]

Para uma saída LOW drenando corrente I_OL através da resistência efetiva R_OL:

[
V_{OL} approx I_{OL}R_{OL}
]

Essas são aproximações explicativas, não substitutos para os limites da folha de dados. Elas mostram por que a carga reduz a margem: fornecer corrente desloca HIGH para baixo e drenar corrente desloca LOW para cima.

O carregamento DC inclui corrente de fuga das entradas receptoras, resistores de pull, redes de terminação e qualquer outro caminho estático. O carregamento dinâmico é frequentemente dominado por capacitância.

## Fan-out: limites DC e dinâmicos

Historicamente, fan-out frequentemente significava o número de entradas lógicas que uma saída podia acionar permanecendo dentro dos limites de corrente DC. Uma verificação conservadora baseada em corrente é:

[
N_H le \frac{|I_{OH,max}|}{|I_{IH,max}|}, qquad
N_L le \frac{I_{OL,max}}{I_{IL,max}}
]

e o fan-out DC fica limitado pelo menor valor admissível. A corrente de fuga muito baixa das entradas CMOS pode tornar esse número grande, mas isso não implica que uma saída possa acionar um número arbitrário de entradas na velocidade desejada.

Cada receptor acrescenta capacitância de entrada, e o roteamento acrescenta capacitância de interconexão. Com carga total C_L, o tempo de transição de primeira ordem escala com a resistência efetiva do driver:

[
\tau approx R_{out} C_L
]

Aumentar o fan-out, portanto, aumenta o tempo de borda e o atraso de propagação mesmo quando os limites de corrente estática são satisfeitos. Redes grandes de clock, reset ou enable normalmente são distribuídas por árvores de buffers porque uma única fonte carregando toda a capacitância diretamente produz atraso, slew e corrente de comutação simultânea excessivos.

Uma sequência útil de projeto é:

1. verificar compatibilidade absoluta de tensão;
2. verificar V_OH/V_OL contra V_IH/V_IL;
3. verificar corrente estática fornecida/drenada;
4. somar capacitâncias de entrada e interconexão;
5. verificar requisitos de taxa de borda e tempo de propagação;
6. avaliar comportamento de linha de transmissão quando o comprimento elétrico da interconexão for significativo;
7. verificar overshoot, undershoot e limites de corrente de clamp.

## Limiar, ganho e restauração

Portas CMOS são úteis não apenas porque classificam uma tensão, mas porque **restauram** níveis lógicos. Na região de transição, um inversor apresenta alto ganho de tensão: uma pequena variação de entrada pode causar grande variação de saída. Fora da transição, a saída se aproxima de um dos trilhos de alimentação, limitada pela carga e pelas características do dispositivo.

Essa restauração impede que pequenos desvios analógicos se acumulem indefinidamente através de uma cadeia de portas adequadamente projetadas. Cada estágio mapeia uma faixa válida de entrada de volta para uma faixa válida de saída.

A restauração tem limites. Se uma entrada permanecer na região de transição, os dispositivos de pull-up e pull-down podem conduzir simultaneamente de maneira significativa. As consequências incluem aumento de corrente de alimentação, transições mais lentas ou múltiplas nos estágios seguintes e maior sensibilidade a ruído acoplado. Entradas CMOS comuns, portanto, não devem ser deliberadamente mantidas em uma tensão indefinida, salvo quando a especificação do dispositivo autorizar explicitamente esse uso.

## Histerese e entradas Schmitt trigger

Um receptor Schmitt trigger utiliza limiares de comutação diferentes para entradas crescentes e decrescentes:

- V_T+ para uma entrada crescente;
- V_T- para uma entrada decrescente;
- histerese V_H = V_T+ - V_T-.

~~~text
borda crescente:    LOW -------- V_T+ --------> HIGH
borda decrescente:  HIGH <------- V_T- -------- LOW
                           <--- V_H --->
~~~

Dentro da banda de histerese, o estado depende tanto da tensão presente quanto do histórico da transição. Isso suprime múltiplas comutações quando uma forma de onda lenta ou ruidosa atravessa a região de decisão. A documentação da Nexperia para o 74LV14 define explicitamente esse comportamento de dois limiares e posiciona as entradas Schmitt para sinais com variação lenta ou sujeitos a ruído.

Histerese não autoriza ignorar tempos máximos de transição de entrada, limites de proteção ou largura de banda analógica. A folha de dados específica do dispositivo continua sendo a autoridade.

## Interfaces compatíveis com TTL e CMOS

Nomes de famílias lógicas codificam contratos elétricos diferentes. Uma saída CMOS de 5 V pode acionar confortavelmente uma entrada compatível com TTL, enquanto a garantia de HIGH de uma saída TTL legada pode ser insuficiente para uma entrada CMOS de 5 V que exija V_IH muito mais elevado. Igualdade de tensão de alimentação, por si só, não prova compatibilidade.

Da mesma forma, famílias modernas de baixa tensão podem oferecer entradas tolerantes a 5 V sem produzir saídas de 5 V. "Tolerante a 5 V" descreve a capacidade da entrada de suportar determinada tensão sob condições especificadas; não significa que o dispositivo opere internamente a 5 V nem que realize tradução automática nos dois sentidos.

A relação correta de compatibilidade é direcional:

~~~text
especificação de saída do driver
          |
          +--> limiares de entrada do receptor
          +--> valores máximos absolutos do receptor
          +--> restrições de corrente / clamp
          +--> restrições de temporização / slew
~~~

Para um barramento bidirecional, a direção inversa deve ser verificada separadamente.

## Tradução de nível

Quando os contratos de saída e entrada não se sobrepõem com margem adequada, é necessário um tradutor de nível. Estratégias incluem tradutores dedicados de alimentação dupla, lógica tradutora com uma única alimentação, interfaces open-drain/open-collector com pull-up apropriado, redes resistivas em casos unidirecionais adequados e transceptores específicos de protocolo.

O tradutor deve ser selecionado considerando direção, domínios de tensão, taxa de borda, corrente de drive, sequenciamento de alimentação, comportamento em desligamento parcial e natureza push-pull ou open-drain do sinal. Um divisor resistivo aceitável para uma entrada CMOS lenta e unidirecional não é substituto genérico para um tradutor bidirecional de alta velocidade.

O 74LV1T08 da Nexperia é um exemplo de lógica tradutora de alimentação única: sua configuração de limiares de entrada permite combinações especificadas de tradução, enquanto o nível de saída acompanha sua alimentação. Esse comportamento é propriedade da especificação do dispositivo, não de uma porta AND abstrata.

## Referência de terra, ground bounce e comutação simultânea

Limiar lógico é medido em relação a uma referência. O "terra" do transmissor e a referência local do receptor não permanecem perfeitamente idênticos durante rápidas variações de corrente. Indutância de encapsulamento, indutância do caminho de retorno e impedância da rede de alimentação produzem movimento transitório dessa referência.

Se um receptor observa uma tensão de sinal V_signal e tem referência local V_GND,RX, sua entrada single-ended relevante é aproximadamente:

[
V_{IN,RX}=V_{signal}-V_{GND,RX}
]

Assim, uma excursão positiva do sinal pode perder margem efetiva se o terra do receptor se mover para cima. Comutação simultânea de muitas saídas pode produzir ground bounce e queda de alimentação, reduzindo tanto margens de ruído quanto margens temporais.

Desacoplamento, caminhos de retorno curtos, impedância controlada, atribuição adequada de pinos e taxas de borda limitadas fazem parte da preservação da abstração digital.

## Efeitos de linha de transmissão e taxa de borda

Uma trilha eletricamente curta em relação ao tempo de transição pode frequentemente ser tratada como uma capacitância concentrada. Quando o atraso de propagação deixa de ser desprezível diante do tempo de borda, reflexões precisam ser consideradas. Um receptor pode observar temporariamente uma tensão diferente do valor DC final.

A pergunta relevante não é apenas a frequência do clock. Um barramento de baixa frequência com bordas subnanosegundo pode apresentar comportamento de linha de transmissão porque o conteúdo espectral da borda se estende muito acima da frequência fundamental de alternância.

Terminação e topologia, portanto, são escolhidas a partir da impedância da interconexão, impedância da fonte, distribuição de cargas e requisitos temporais. Compatibilidade estática V_OH/V_OL continua necessária, mas não suficiente.

## Interação com temporização

Um flip-flop receptor exige que sua entrada permaneça estável ao redor da borda de amostragem de acordo com restrições de setup e hold. Ruído pode se converter em erro temporal mesmo sem alterar permanentemente o estado DC: ringing ou cruzamento lento do limiar modifica o instante em que o receptor reconhece a transição.

Para uma entrada monotônica V(t), uma incerteza de limiar Delta V se converte aproximadamente em incerteza temporal:

[
Delta t approx \frac{Delta V}{|dV/dt|}
]

Uma taxa de slew menor, portanto, transforma a mesma incerteza de tensão em maior incerteza no instante da borda. Essa é uma das razões pelas quais integridade de sinal e fechamento temporal não podem ser completamente separados.

## Estados indefinido, alta impedância e contenção

A camada elétrica contém condições que a álgebra booleana sozinha não representa.

**Região de entrada indefinida:** a tensão está entre as faixas garantidas de LOW e HIGH.

**Alta impedância (Z):** um driver de saída está desabilitado e não conduz intencionalmente para nenhum trilho. A tensão do nó passa então a ser determinada por outros drivers, resistores de pull, fugas e capacitância.

**Contenção:** dois drivers push-pull habilitados tentam impor valores opostos. A corrente pode tornar-se excessiva e a tensão resultante pode ficar indefinida.

**Entrada flutuante:** nenhuma fonte de baixa impedância estabelece um nível válido. Correntes de fuga e carga acoplada podem mover o nó através da região de transição.

Essas condições precisam ser resolvidas por propriedade do barramento, protocolos de output-enable, pulls e projeto elétrico.

## Fronteira arquitetural do ChrisOS

A revisão do ChrisOS revisada para este capítulo é `da3df29cb397932c43d32373871fb9380e688ade`.

As fontes inspecionadas estabelecem uma fronteira de abstração de software, e não um modelo de implementação elétrica:

| Fonte | Abstração observada relevante |
|---|---|
| `chrisvm/chris_arch.h` | `ChrisArchitectureState` representa o estado arquitetural da máquina como dados de software |
| `chrisvm/cpu/emulator/chriscpu.c` | `cpu_run` avança a execução arquitetural emulada |
| `kernel/gfx/graphics.c` | `gfx_rgb` constrói um valor digital de pixel |

Esses arquivos não especificam V_IH/V_IL de pads do processador, V_OH/V_OL, fan-out de placa, capacidade de drive do encapsulamento, terminação de padrão de I/O ou margens de ruído medidas. Nenhum desses comportamentos é inferido aqui.

Conceitualmente:

~~~text
máquina física
tensão -> receptor -> bit -> estado arquitetural
                         ^
                         |
ChrisCPU começa aqui ----+

software do kernel opera sobre o modelo de bit/valor arquitetural
~~~

A distinção torna-se importante à medida que o ChrisOS avança para bring-up em hardware físico. Firmware e drivers podem configurar controladores de I/O, mas compatibilidade elétrica continua sendo propriedade das especificações do processador, chipset, placa e layout.

## Estado, algoritmos, propriedade e complexidade

Não existe, nas fontes inspecionadas, uma estrutura de dados de runtime do ChrisOS para limiares lógicos analógicos; atribuir uma seria fictício. No nível de projeto elétrico, a verificação de compatibilidade pode ser expressa como um conjunto limitado de desigualdades por conexão.

Para cada aresta driver-receptor:

~~~text
assert VOH_min(driver, load) >= VIH_min(receiver)
assert VOL_max(driver, load) <= VIL_max(receiver)
assert receiver absolute limits are respected
assert source/sink current limits are respected
assert edge/timing limits are respected
~~~

Para E conexões elétricas, uma verificação estática dirigida por tabela é O(E) em tempo e O(1) em armazenamento de trabalho adicional, além do banco de dados de interfaces e do relatório. Simulação completa de integridade de sinal é um problema diferente e pode exigir modelos distribuídos de interconexão e modelos não lineares de dispositivos.

Em runtime, a propriedade de uma rede pertence ao hardware que a dirige; protocolos de barramento determinam qual saída pode ser habilitada. No estado arquitetural de software, propriedade e sincronização são governadas pelas estruturas de dados do emulador/kernel e pelas regras de concorrência documentadas em seus capítulos próprios.

## Modos de falha e contenção

| Falha | Mecanismo elétrico | Consequência típica |
|---|---|---|
| margem de ruído negativa | faixas garantidas incompatíveis | interpretação lógica não determinística |
| fan-out DC excessivo | corrente de saída supera a condição válida de carga | degradação de V_OH/V_OL |
| fan-out capacitivo excessivo | carga RC elevada | bordas lentas, falha temporal |
| entrada CMOS flutuante | fuga/acoplamento controla o nó | alternância indevida, corrente excessiva |
| contenção push-pull | drivers opostos habilitados | sobrecorrente, tensão indefinida |
| ground bounce | retorno indutivo compartilhado | cruzamento aparente de limiar |
| ringing | descontinuidade de impedância | cruzamentos falsos ou múltiplos |
| borda lenta sem Schmitt | longa permanência próxima do limiar | jitter, corrente excessiva |
| over/undershoot | transiente de interconexão | corrente de clamp ou estresse de confiabilidade |

A contenção começa com interfaces compatíveis com especificação, pulls explícitos e propriedade definida; depois se estende a layout, terminação, desacoplamento e validação com instrumentação apropriada.

## Implicações de privilégio e segurança

Níveis lógicos estão abaixo do modelo de privilégio da CPU, mas falhas elétricas podem atravessar fronteiras de segurança indiretamente. Uma interface marginal de clock, reset, memória ou periférico pode corromper estado arquitetural antes que mecanismos de proteção de software sejam executados. Pesquisas de injeção de falhas exploram deliberadamente distúrbios de tensão, clock ou eletromagnéticos por esse motivo.

Este capítulo não afirma que o ChrisOS implementa defesas contra injeção física de falhas. As fontes de software inspecionadas não estabelecem tal mecanismo.

## Desempenho e trade-offs

Maior capacidade de drive pode carregar capacitâncias mais rapidamente, mas aumenta corrente de comutação simultânea, emissão eletromagnética e risco de ringing. Terminação mais forte pode melhorar a forma de onda ao custo de maior potência estática ou dinâmica. Maior margem de ruído aumenta robustez, mas a redução de tensão de alimentação diminui o espaço de tensão disponível mesmo quando reduz energia de comutação.

Entradas Schmitt melhoram tolerância a transições lentas e ruidosas, mas introduzem histerese e limiares específicos da família. Tradutores de nível restabelecem compatibilidade entre domínios de tensão, porém acrescentam atraso de propagação, potência, custo e restrições de sequenciamento.

Não existe ótimo universal; a interface deve satisfazer simultaneamente restrições de tensão, corrente, temporização, potência e integridade.

## Evidência de validação

Para a camada teórica, este capítulo foi confrontado com documentação primária atual de fabricantes: o *Logic Guide* da Texas Instruments, SDYU001AC, revisado em novembro de 2025, para terminologia de níveis lógicos e compatibilidade; e documentação da Nexperia para o 74LV14 e o 74LV1T08 para níveis garantidos, histerese e tradução.

Para o ChrisOS, a evidência desta revisão é exclusivamente inspeção de código-fonte. Este capítulo não relata medições de osciloscópio, caracterização de pads de I/O, relatórios temporais de FPGA nem validação em placa física.

Um plano de validação em hardware mediria pelo menos:

- alimentação e terra na referência do receptor;
- V_OH/V_OL sob a carga especificada;
- tempo de subida/descida e atraso de propagação;
- overshoot, undershoot e ringing;
- perturbação por comutação simultânea;
- margem de setup/hold nas interfaces de amostragem;
- comportamento nas faixas suportadas de tensão e temperatura.

## Limitações atuais

A fronteira documental atual não possui banco de dados específico de tensões de I/O de placa nem corpus medido de integridade de sinal do hardware ChrisOS. Exemplos genéricos TTL/CMOS não substituem a folha de dados do processador, FPGA, memória ou periférico efetivamente usado em um futuro alvo físico.

As equações acima são instrumentos de raciocínio de primeira ordem. Elas não substituem modelos IBIS/SPICE, parasitas de encapsulamento, extração de linhas de transmissão ou caracterização do fabricante quando essas técnicas forem necessárias.

## Roadmap

A futura documentação de hardware físico deve vincular cada interface de placa implementada à sua especificação elétrica autoritativa, domínio de tensão, terminação, configuração de pulls e evidência de validação medida. Se o ChrisVM adquirir posteriormente um modelo explícito de placa ou de falhas elétricas, esse modelo deve ser documentado separadamente da semântica arquitetural da CPU.

Nenhum item deste roadmap é apresentado como comportamento atual do ChrisOS.

## Proveniência da revisão

- Revisão de implementação do ChrisOS inspecionada: `da3df29cb397932c43d32373871fb9380e688ade`.
- Fontes atuais de implementação inspecionadas: `chrisvm/chris_arch.h`, `chrisvm/cpu/emulator/chriscpu.c`, `kernel/gfx/graphics.c`.
- Referências elétricas primárias revisadas: TI *Logic Guide* SDYU001AC; Nexperia 74LV14 e 74LV1T08.
- Conclusão arquitetural: o software atual do ChrisOS inspecionado consome a abstração digital; ele não modela limiares elétricos de transistor/pad.
