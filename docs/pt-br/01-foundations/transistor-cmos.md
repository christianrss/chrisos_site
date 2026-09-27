---
id: transistor-cmos
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
  - mos-capacitor
  - pn-junction
related:
- logic-sequential
---


# Transistores e lógica CMOS

## MOSFET como dispositivo controlado

Um MOSFET possui terminais gate, source, drain e body. A porta é separada do semicondutor por um dielétrico isolante. A tensão no gate modifica o campo elétrico na região do canal e controla se source e drain ficam ligados por um caminho suficientemente condutivo.

Para raciocínio digital, o transistor é aproximado como uma chave controlada por tensão. A aproximação é deliberadamente incompleta: dispositivos reais possuem tensão de limiar, resistência finita, capacitância, fuga, tempo de transição e comportamento corrente-tensão não linear. Essas propriedades analógicas determinam potência e velocidade, enquanto o projeto lógico normalmente trabalha com o estado binário restaurado.

## Tensões de terminal e modelo do canal

No NMOS, o controle costuma ser descrito por `V_GS`, tensão do gate relativa ao source, e não por uma tensão absoluta em relação à origem arbitrária do desenho. `V_DS` é a tensão entre drain e source. O body também importa, pois sua polarização altera as condições eletrostáticas. No PMOS, pode-se usar uma convenção de módulos referidos ao source, mas os sinais precisam ser consistentes. Afirmar apenas que o gate está “alto” esconde a referência da qual a condução depende.

Um modelo simples de canal longo divide a operação NMOS em regiões. Abaixo do limiar, o modelo de chave ideal considera o dispositivo desligado, mas o dispositivo real ainda apresenta corrente subthreshold. Com sobretensão suficiente `V_GS - V_T`, um `V_DS` pequeno produz um canal aproximadamente resistivo e controlável. Conforme `V_DS` cresce, as condições perto do drain mudam; a aproximação de saturação descreve outra relação de corrente e tensão. Saturação nesse modelo MOSFET não significa a mesma coisa que em qualquer outro modelo de transistor.

Nas hipóteses idealizadas de canal longo e inversão forte, uma expressão comum na região linear é `I_D = μ C_ox (W/L) [(V_GS-V_T)V_DS - V_DS²/2]`. A aproximação de saturação é `I_D = μ C_ox (W/L)(V_GS-V_T)²/2`, desprezando modulação do comprimento do canal. Mobilidade, capacitância de óxido por área e razão largura/comprimento determinam a escala. As equações expõem dependências de projeto; não são uma simulação universal precisa dos dispositivos modernos de canal curto.

O limiar, em particular, não é um evento infinitamente abrupto em que toda a corrente surge instantaneamente. A abstração de chave descarta intencionalmente parte da característica contínua. É adequada para raciocinar sobre o valor booleano final sob faixas especificadas, mas insuficiente para estimar toda a fuga, ganho analógico ou temporização. Uma explicação digital torna-se mais confiável quando explicita o limite da simplificação.

## NMOS e PMOS

Lógica CMOS combina dispositivos complementares.

- Um **NMOS** conduz fortemente quando seu gate está alto em relação ao source.
- Um **PMOS** conduz fortemente na condição complementar.

O inversor CMOS canônico usa uma rede PMOS de pull-up e uma rede NMOS de pull-down.

![CMOS inverter / inversor CMOS](../../assets/diagrams/cmos-inverter.svg)

Com entrada baixa, o PMOS tende a conduzir e o NMOS tende a bloquear, levando a saída para a alimentação alta. Com entrada alta ocorre o inverso. A propriedade central é a restauração: uma entrada baixa válida produz saída fortemente alta e uma entrada alta válida produz saída fortemente baixa.

## Redes CMOS e funções booleanas

Redes de transistores em série e paralelo implementam condições lógicas. NAND e NOR são particularmente naturais em CMOS. Como qualquer uma delas é funcionalmente completa, funções booleanas arbitrárias podem ser compostas.

Álgebra booleana abstrai tensão e geometria. Variáveis assumem 0 ou 1 e operações NOT, AND e OR descrevem relações lógicas estáveis.

| Forma booleana | Significado |
|---|---|
| `¬A` | NOT |
| `A ∧ B` | AND |
| `A ∨ B` | OR |
| `¬(A ∧ B)` | NAND |
| `¬(A ∨ B)` | NOR |

Uma expressão booleana não é a mesma coisa que sua implementação física. Um somador pode ser descrito com XOR, AND e OR; uma biblioteca de células transforma depois essas portas em redes de transistores caracterizadas por timing e potência.

## Construção de uma rede NAND

Uma NAND CMOS estática de duas entradas possui dois NMOS em série na rede pull-down e dois PMOS em paralelo na rede pull-up. A saída encontra um caminho condutor até o terra apenas quando ambos os gates NMOS estão altos. Uma entrada baixa habilita o caminho PMOS correspondente até a alimentação. Com entradas válidas e estabilizadas, a saída realiza o complemento de AND.

| A | B | Caminho pull-down em série | Caminho pull-up em paralelo | Saída |
|---|---|---|---|---|
| 0 | 0 | Aberto | Condutor | 1 |
| 0 | 1 | Aberto | Condutor | 1 |
| 1 | 0 | Aberto | Condutor | 1 |
| 1 | 1 | Condutor | Aberto | 0 |

A derivação explica a porta por condições de condução, em vez de associar uma tabela a um símbolo sem mecanismo. A NOR usa a organização dual: NMOS em paralelo e PMOS em série. Sua saída fica baixa quando qualquer ramo pull-down conduz e alta somente quando ambas as entradas permitem o caminho pull-up em série.

A complementaridade evita um caminho condutor ideal permanente entre os trilhos em um estado válido e estabilizado. Durante transições, ambas as redes podem conduzir parcialmente, portanto existe componente de curto-circuito na comutação real. Empilhamentos em série também alteram a capacidade de acionamento e os nós intermediários. Expressões booleanamente equivalentes não precisam possuir a mesma área, atraso ou energia depois de implementadas.

## Restauração e margens de ruído

A curva de transferência de um inversor relaciona tensão de entrada contínua com tensão de saída. Nas regiões estáveis baixa e alta, variações de entrada não precisam destruir a interpretação lógica da saída. Perto da transição, o ganho pode ser elevado e ambos os dispositivos participam do resultado. Interfaces digitais especificam limites de entrada e saída para que a saída válida de uma porta continue sendo entrada válida para a seguinte, apesar de tolerâncias e perturbações.

Na nomenclatura usual, a margem de ruído baixa é `V_IL,max - V_OL,max`, e a alta é `V_OH,min - V_IH,min`. Margens positivas oferecem espaço entre níveis de saída garantidos e limites aceitáveis de entrada. A região indefinida não é outro símbolo booleano: é uma faixa na qual a interface não garante nenhuma das duas interpretações.

Em uma interface hipotética de 1 V, considere `V_OL,max = 0,1 V`, `V_IL,max = 0,3 V`, `V_IH,min = 0,7 V` e `V_OH,min = 0,9 V`. Ambas as margens são 0,2 V. Os números ilustram desigualdades; não especificam o hardware do ChrisOS. Um projeto correto utiliza os limites reais de sua biblioteca ou dispositivo, sem transplantar valores de exemplo.

## Comportamento estático e dinâmico

CMOS estático idealmente consome pouca corrente direta entre os rails quando estabilizado porque um lado da rede complementar está desligado. Chips reais possuem fuga, mas grande parte da potência ativa vem de carregar e descarregar capacitâncias durante transições.

Uma aproximação útil é

```text
P_dynamic ≈ α C V² f
```

onde `α` representa atividade de chaveamento, `C` capacitância efetiva, `V` tensão de alimentação e `f` frequência. Isso explica por que frequência, tensão e quantidade de transistores interagem fortemente com consumo de CPUs.

Propagação não é instantânea. Uma mudança na entrada leva tempo finito para modificar a saída. Caminhos combinacionais possuem atraso máximo e circuitos síncronos escolhem um período de clock que permita estabilização antes da próxima captura de estado.

## Fan-out, carga e integridade

A saída de uma porta dirige capacitância finita. Muitos destinos aumentam carga e tornam transições mais lentas. Projeto físico usa buffers, dimensionamento e células caracterizadas.

Margem de ruído permite perturbações pequenas sem mudar o nível interpretado. Se um sinal entra na região indefinida próximo ao instante de amostragem, elementos sequenciais podem entrar em metastabilidade. Sincronização reduz o risco, mas não elimina a origem analógica.

## Carga, fanout e a existência de buffers

A saída de uma porta encontra capacitância dos fios e das entradas seguintes. Para mudar a tensão, precisa transferir carga para esse conjunto ou retirá-la. Uma estimativa de atraso cresce, portanto, com resistência efetiva de saída e capacitância de carga. Aumentar a largura dos transistores pode elevar a corrente disponível, mas aumenta a capacitância vista pelo estágio anterior e consome área. Otimizar uma porta isolada pode transferir o problema para trás.

Uma cadeia de buffers distribui uma grande necessidade de acionamento em estágios. Seu projeto depende da razão entre carga final e capacitância inicial e de um modelo de atraso caracterizado. O objetivo não é mudar o valor lógico, mas entregá-lo respeitando restrições elétricas e temporais. Da mesma forma, um sinal destinado a milhares de elementos de armazenamento exige uma rede de distribuição; não é uma conexão sem custo apenas porque todos recebem o mesmo clock booleano.

Glitches acrescentam custo. Atrasos diferentes podem fazer um nó comutar brevemente mesmo quando seu valor final não muda entre duas observações. Essas transições carregam capacitâncias e consomem energia. Uma tabela-verdade descreve funcionalidade estável, portanto não prevê sozinha toda a atividade necessária ao modelo `α C V² f`.

## De CMOS a máquinas com estado

Lógica combinacional produz saídas em função apenas das entradas atuais. Um computador precisa preservar estado anterior. Realimentação entre portas cria circuitos biestáveis; elementos de armazenamento controlados por clock restringem quando novos valores são aceitos. Surgem latches, flip-flops, registradores, contadores, caches e interfaces de memória.

No nível visível ao software, RAX parece conter 64 bits exatos. Fisicamente ele depende de circuitos de retenção de estado dentro de uma microarquitetura muito maior. A ISA oculta essa topologia.

## Realimentação, partida e estado controlado

Conectar saídas de inversores às entradas um do outro cria duas configurações lógicas estáveis. Essa realimentação positiva fundamenta o armazenamento biestável, mas a partida não garante qual configuração será escolhida. Um reset ou uma sequência explícita de inicialização é necessário quando o estado inicial conhecido importa. Existe uma relação conceitual com inicialização de software, embora os mecanismos operem em níveis distintos.

Quando entradas externas tentam alterar o estado perto de uma amostragem sensível, o circuito analógico pode demorar mais para resolver. Contratos temporais e sincronizadores tratam o comportamento; álgebra booleana comum não comprova sua ausência. Por isso, lógica sequencial e temporização seguem a derivação combinacional, sem tratar registradores como caixas inexplicadas.

Na fronteira arquitetural, o software recebe garantias de operações e estado de reset, não uma lista de nós de transistores. `ChrisArchitectureState`, em `chrisvm/chris_arch.h`, representa essas grandezas em campos C. `cpu_run` manipula o estado pela semântica das instruções. Nenhum dos arquivos contém netlist, modelo de capacitância ou solucionador de dispositivos. O emulador reproduz o contrato superior e depende da máquina hospedeira para realizar a computação elétrica.

## Fronteira do ChrisOS

ChrisOS começa acima dessa fronteira. O kernel e o ChrisCPU não modelam MOSFETs individuais. ChrisCPU emula **estado arquitetural**: registradores, flags, registradores de controle, efeitos de memória e exceções. Isso é possível porque a ISA x86-64 define uma abstração estável sobre o circuito físico.

O próximo capítulo constrói o caminho entre portas, armazenamento de estado, unidades aritméticas e máquinas sincronizadas.

## Do raciocínio sobre portas à revisão de código

A conexão com o kernel ocorre pela composição de contratos. AND pode mascarar campos, deslocamentos podem posicionar bits e OR pode combinar campos sem sobreposição. Na lógica, as operações possuem definições por tabelas-verdade. Na ISA, instruções definem larguras e resultados. Fisicamente, a implementação pode empregar diferentes arranjos de portas desde que respeite o comportamento arquitetural e a temporização.

O codificador RGB em `graphics.c`, por exemplo, combina três canais de oito bits em um inteiro sem sinal mais largo. Compreender AND, OR e deslocamentos permite reconstruir a representação. Isso não permite concluir que a CPU executa a expressão com exatamente três portas particulares, pois compilação e microarquitetura intervêm. Correção do código e correção do circuito exigem evidências distintas, mesmo descrevendo a mesma computação final.

A validação deve, portanto, corresponder à afirmação. Enumerar a tabela-verdade verifica uma relação booleana finita. Análise temporal verifica setup e hold sob um modelo físico. Caracterização elétrica verifica limites de tensão e correntes. Um teste no hospedeiro da função RGB verifica codificação de software. Nenhum substitui todos os outros. Essa separação conecta teoria de transistores ao ChrisOS sem afirmar que seu código especifica o processador físico.

## Referências primárias

- [MIT 6.012 — Microelectronic Devices and Circuits](https://ocw.mit.edu/courses/6-012-microelectronic-devices-and-circuits-spring-2009/pages/lecture-notes/).
