---
id: cmos-switching-power
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
  - transistor-cmos
  - capacitance-inductance
  - power-delivery-regulation
related:
  - logic-levels-noise-margins
  - combinational-logic
  - clock-timing
  - latches-flipflops
---

# Chaveamento CMOS, atraso e potência

<div class="abstract">
A lógica CMOS produz comportamento digital útil carregando e descarregando capacitâncias físicas através de redes de transistores com resistência e tempo de transição finitos. A função booleana estável é apenas uma camada do mecanismo. Desempenho depende de movimento de carga, força de drive, fan-out, capacitâncias parasitas, slew de entrada e topologia do caminho; potência depende de atividade de chaveamento, tensão, frequência, corrente de curto-circuito e leakage. Este capítulo deriva modelos de primeira ordem de atraso e energia CMOS, explica glitches, sizing, fan-out, carga de clock, compromissos entre potência e delay e o acoplamento entre atividade lógica e a rede de distribuição de energia. Em seguida, reconcilia a fronteira com o ChrisOS: atualizações de estado arquitetural no ChrisCPU e operações bitwise no kernel são comportamento visível por software, não contagens de transições de transistores, capacitância física ou potência medida do processador.
</div>

## Pré-requisitos e escopo

Este capítulo pressupõe:

- acumulação, depleção e inversão no capacitor MOS;
- funcionamento de MOSFET e inversor CMOS;
- capacitância e energia armazenada;
- resistência e transitórios RC;
- impedância da PDN e droop de alimentação;
- lógica booleana e atraso de propagação.

A pilha central de abstrações é:

~~~text
transição booleana
      ↓
rede de transistores muda condução
      ↓
capacitâncias de nós carregam ou descarregam
      ↓
forma de onda analógica cruza o limiar
      ↓
novo valor lógico torna-se válido
~~~

A tabela-verdade descreve apenas os estados finais.

Atraso e potência exigem modelar a transição contínua entre eles.

## O inversor CMOS como sistema de chaveamento

Um inversor CMOS possui:

- caminho PMOS pull-up até V_DD;
- caminho NMOS pull-down até terra;
- nó de saída com capacitância efetiva C_L.

~~~text
V_DD
 |
PMOS
 |
 +------ saída ---- C_L
 |
NMOS
 |
GND
~~~

Na transição low-to-high, a rede PMOS fornece carga a C_L.

Na transição high-to-low, a rede NMOS remove essa carga.

O resultado lógico ideal é NOT(input), mas a mudança física leva tempo finito.

## Capacitância efetiva de carga

C_L não é necessariamente um único capacitor.

Pode incluir:

- capacitância de entrada dos gates seguintes;
- capacitância de junção nos drains;
- capacitância de interconexão;
- acoplamento;
- capacitância de package ou I/O quando relevante.

Modelo concentrado de primeira ordem:

~~~text
C_L = C_gate + C_diffusion + C_wire + C_other
~~~

A decomposição depende do layout.

Em interconexões longas ou rápidas, um modelo RC distribuído ou de linha de transmissão pode ser mais adequado.

## Carregamento de um nó capacitivo

Para capacitor ideal carregado de 0 até V_DD:

~~~text
Q = C_L V_DD
~~~

Energia armazenada ao final:

~~~text
E_stored = 1/2 C_L V_DD²
~~~

Uma fonte ideal carregando através de caminho resistivo fornece:

~~~text
E_from_supply = C_L V_DD²
~~~

A outra metade:

~~~text
E_dissipated_charge = 1/2 C_L V_DD²
~~~

é dissipada no caminho de carga no modelo RC simples.

Na descarga posterior, a energia armazenada é dissipada pelo pull-down.

Assim, um ciclo completo 0→1→0 consome aproximadamente da fonte:

~~~text
E_cycle = C_L V_DD²
~~~

no modelo dinâmico CMOS de primeira ordem.

## Potência dinâmica de chaveamento

Se um nó apresenta fator de atividade α para transições 0→1 por oportunidade de clock e as oportunidades ocorrem a frequência f:

~~~text
P_dynamic = α C_L V_DD² f
~~~

A convenção de α varia entre referências.

Algumas contam todas as transições em vez de apenas eventos de carga 0→1.

Qualquer uso numérico precisa declarar a convenção.

As dependências robustas são:

~~~text
P_dynamic ∝ atividade
P_dynamic ∝ capacitância
P_dynamic ∝ V_DD²
P_dynamic ∝ frequência
~~~

A dependência quadrática em tensão torna a redução de V_DD especialmente eficaz para energia dinâmica.

## Exemplo numérico

Considere:

~~~text
C_L = 10 fF
V_DD = 1,0 V
α = 0,2
f = 1 GHz
~~~

Então:

~~~text
P_dynamic
=
0,2 · 10e-15 · 1² · 1e9
=
2 µW
~~~

para esse nó modelado.

Um chip real possui muitos nós com atividades e capacitâncias diferentes; a potência total é soma das contribuições.

O exemplo não é estimativa de potência para processadores que executem ChrisOS.

## Energia de transição e corrente de alimentação

Uma transição low-to-high requer:

~~~text
ΔQ = C_L ΔV
~~~

Se ocorre em tempo Δt, a corrente média de carga é aproximadamente:

~~~text
I_avg ≈ ΔQ / Δt
~~~

Transições mais rápidas exigem maior corrente transitória para a mesma capacitância e swing.

Essa corrente percorre a PDN.

Portanto atividade lógica acopla diretamente a:

- droop local;
- indutância de package;
- ground bounce;
- resposta do regulador.

Timing CMOS e power integrity não podem ser completamente separados.

## Atraso RC de primeira ordem

Modele a rede condutora por resistência efetiva R_eq carregando ou descarregando C_L.

Resposta de carga:

~~~text
V_charge(t)
=
V_DD (1 - e^(-t/(R_eq C_L)))
~~~

O tempo até 50 por cento de V_DD é:

~~~text
t_50
=
ln(2) R_eq C_L
≈
0,693 R_eq C_L
~~~

Logo:

~~~text
t_p ∝ R_eq C_L
~~~

como aproximação de primeira ordem.

O coeficiente depende do limiar e da forma de onda.

## Atrasos de subida e descida

Pull-up e pull-down podem possuir resistências efetivas diferentes.

Aproximadamente:

~~~text
t_pLH
≈
0,69 R_p C_L

t_pHL
≈
0,69 R_n C_L
~~~

e:

~~~text
t_p
=
(t_pLH + t_pHL) / 2
~~~

Esse é um modelo pedagógico.

Standard cells modernas usam modelos caracterizados em função de slew, carga, tensão, processo e temperatura.

## Slew de entrada

A entrada não muda instantaneamente.

Entrada lenta mantém NMOS e PMOS em regiões intermediárias por mais tempo.

Consequências:

- maior atraso;
- maior corrente de curto-circuito;
- maior incerteza temporal;
- slew de saída diferente.

Portanto atraso deve ser tratado como:

~~~text
delay
=
F(
  slew de entrada,
  carga de saída,
  alimentação,
  processo,
  temperatura
)
~~~

e não como constante única por gate.

## Corrente de curto-circuito

Durante a transição da entrada, NMOS e PMOS podem conduzir simultaneamente.

~~~text
V_DD
  ↓
PMOS parcialmente ligado
  ↓
NMOS parcialmente ligado
  ↓
GND
~~~

Essa corrente crowbar adiciona potência ao termo puramente capacitivo.

Depende de:

- slew;
- sizing;
- V_DD;
- thresholds;
- carga de saída.

Uma entrada ideal infinitamente rápida reduziria o intervalo de sobreposição; bordas reais são finitas.

## Potência de leakage

CMOS não é perfeitamente estático.

Mecanismos incluem:

- subthreshold;
- leakage de junções reversamente polarizadas;
- tunelamento de gate;
- efeitos como gate-induced drain leakage em tecnologias escaladas.

Uma relação de primeira ordem é:

~~~text
P_leak ≈ V_DD I_leak
~~~

I_leak depende fortemente de:

- temperatura;
- threshold;
- processo;
- estado do dispositivo;
- geometria.

Em tecnologias avançadas, leakage pode representar parcela significativa da potência.

## Realimentação térmica

Potência elétrica vira calor.

Temperatura maior pode aumentar leakage.

~~~text
mais potência
   ↓
temperatura maior
   ↓
mais leakage
   ↓
mais potência
~~~

Projeto térmico e elétrico precisam manter ponto operacional estável.

A relação exata é específica da tecnologia.

## Fan-out

Um gate que dirige mais entradas vê capacitância total maior.

Se cada carga possui aproximadamente C_in:

~~~text
C_load
≈
N C_in + C_wire + C_parasitic
~~~

para fan-out N.

Fan-out maior aumenta:

- atraso;
- energia de carga;
- corrente transitória.

Um único valor booleano pode ser fisicamente caro de distribuir.

## Sizing de transistores

Aumentar largura tende a aumentar capacidade de drive e reduzir resistência efetiva.

Mas também aumenta:

- capacitância de gate para o estágio anterior;
- capacitância de difusão;
- área;
- energia dinâmica.

~~~text
transistor mais largo
    ↓
mais drive
mas
mais capacitância
~~~

Sizing precisa ser otimizado no caminho completo.

## Cadeias de buffers

Um gate muito pequeno nem sempre deve dirigir diretamente uma carga enorme.

Uma cadeia de buffers crescentes pode distribuir a razão de capacitâncias:

~~~text
gate pequeno
  ↓
buffer médio
  ↓
buffer maior
  ↓
carga grande
~~~

Cada estágio adiciona atraso próprio, mas reduz a carga extrema do estágio anterior.

O ótimo depende do modelo de atraso, parasitas e biblioteca física.

## Logical effort como abstração

Logical effort separa dificuldade topológica do gate e fan-out elétrico.

Modelo simplificado:

~~~text
d = g h + p
~~~

onde:

- g é logical effort;
- h é electrical effort ou razão de capacitâncias;
- p é atraso parasita.

É útil para raciocínio de sizing.

Não substitui signoff transistor-level.

## Intuição de Elmore delay

Em uma rede RC distribuída, atraso depende da localização da capacitância em relação às resistências anteriores.

A aproximação de primeira ordem pode ser escrita:

~~~text
t_delay
≈
Σ_i R_common,i C_i
~~~

Cada capacitância é ponderada pela resistência comum ao caminho da fonte.

Isso explica por que interconexão longa e resistiva pode dominar o atraso.

Ferramentas físicas usam modelos mais completos, mas Elmore fornece intuição útil.

## Pilhas de transistores em série

NAND CMOS pode possuir vários NMOS em série no pull-down.

A resistência efetiva aumenta em relação a um único transistor de mesmo tamanho.

NOR pode apresentar PMOS em série no pull-up.

Isso cria diferenças de:

- delay;
- sizing;
- logical effort;
- capacitância parasita.

A tabela-verdade não mostra esse custo.

## Capacitâncias de nós internos

Gates complexos podem conter nós de difusão internos.

Esses nós podem carregar ou descarregar mesmo sem transição rail-to-rail na saída.

Atividade interna também consome energia e afeta delay.

Contar apenas transições da saída pode subestimar atividade física.

## Glitches e hazards

Caminhos combinacionais raramente têm atrasos exatamente iguais.

Entradas logicamente correlacionadas podem chegar em momentos diferentes e produzir transição temporária na saída.

Esse glitch pode:

- consumir energia;
- propagar;
- reduzir margem temporal;
- ser capturado indevidamente.

A tabela-verdade final não representa essa atividade.

## Fator de atividade

Para estimativa de potência, cada nó pode ter fator α_i:

~~~text
α_i
=
eventos esperados de carga por intervalo de referência
~~~

Então:

~~~text
P_dynamic,total
≈
Σ_i α_i C_i V_DD² f
~~~

A atividade depende de:

- workload;
- estatística dos dados;
- clock gating;
- topologia lógica;
- glitches;
- transições de estado arquitetural.

Ela não pode ser inferida genericamente de código-fonte estático.

## Potência de clock

Redes de clock comutam regularmente e dirigem muitos elementos sequenciais.

Podem contribuir significativamente para potência dinâmica.

Uma clock tree contém:

- buffers;
- capacitância de fios;
- pinos de clock;
- estruturas de gating.

Quando habilitada, a atividade do clock é altamente regular.

Clock gating reduz chaveamento desnecessário na árvore e em lógica sequencial downstream.

## Data gating e isolamento de operandos

Atividade combinacional desnecessária pode ser reduzida impedindo entradas irrelevantes de alternarem lógica interna.

Técnicas:

- operand isolation;
- enable gating;
- clock gating;
- power gating em granularidade maior.

Essas técnicas precisam preservar correção.

Economia de energia não pode alterar semântica de atualização de estado.

## Power gating

Power gating desconecta um bloco da alimentação por sleep transistors ou mecanismo equivalente.

Benefício:

- forte redução de leakage no bloco inativo.

Custos:

- latência de wake-up;
- retenção/perda de estado;
- inrush;
- área;
- isolamento entre domínios;
- sequenciamento.

É uma característica física de projeto, não uma suposição de sistema operacional salvo quando hardware expõe interface controlável.

## Dynamic voltage and frequency scaling

Modelo simplificado:

~~~text
P_dynamic = α C V² f
~~~

Reduzir V reduz potência dinâmica quadraticamente.

Reduzir f reduz aproximadamente linearmente.

Mas a frequência máxima segura depende de V porque menor tensão reduz overdrive e capacidade de corrente.

~~~text
V menor
    ↓
menos energia dinâmica
mas
circuitos mais lentos / menor margem temporal
~~~

A tabela real tensão-frequência é específica do processador/plataforma.

## Energia por operação

Se uma operação causa um conjunto de transições:

~~~text
E_operation
≈
Σ_i transitions_i · C_i V_DD²
+
energia de curto-circuito
+
energia de leakage durante a execução
~~~

Esse modelo é mais informativo que potência isolada ao comparar operações com tempos diferentes.

Mas mapear instruções de software para nós físicos exige conhecimento microarquitetural e de circuito.

## Power-delay product

Um indicador simples:

~~~text
PDP = potência · delay
~~~

possui unidade de energia.

Outro:

~~~text
EDP = energia · delay
~~~

pondera desempenho e eficiência de forma diferente.

Nenhum é universalmente ótimo.

Bateria, densidade térmica, throughput e latência podem exigir objetivos distintos.

## Caminhos críticos

O período de clock síncrono precisa superar o pior caminho relevante mais margens.

Relação simplificada:

~~~text
T_clk
>=
t_clk-q
+
t_logic,max
+
t_setup
+
margem de skew/jitter
~~~

O termo lógico é composto por atrasos de transistores, gates e interconexões.

Reduzir potência média não necessariamente melhora pior caso de timing.

Um caminho raramente ativado ainda pode limitar a frequência máxima.

## Variação de processo, tensão e temperatura

Atraso e leakage dependem de PVT:

~~~text
processo
tensão
temperatura
~~~

Exemplos:

- corner mais lento aumenta delay;
- tensão menor tende a aumentar delay;
- temperatura altera mobilidade e leakage.

Signoff usa corners e modelos caracterizados.

Uma estimativa RC nominal é didática, não evidência de signoff.

## Interação entre ruído e delay

Droop reduz drive dos transistores durante transições.

Isso aumenta delay e altera slew.

Ground bounce move limiares locais.

Crosstalk pode acelerar ou atrasar transição dependendo da direção/timing do agressor.

Logo:

~~~text
signal integrity
+
power integrity
+
timing
~~~

são acoplados.

## Conservação de energia e PDN

Cada transição 0→1 demanda energia da alimentação.

Muitas transições simultâneas produzem corrente:

~~~text
I_total(t)
=
Σ_i C_i dV_i/dt
+
corrente de curto-circuito
+
leakage
+
correntes analógicas/de suporte
~~~

Regulador e desacoplamento precisam fornecer essa corrente mantendo o rail.

Isso liga diretamente o capítulo anterior de power delivery à atividade de gates.

## Armazenamento de estado e chaveamento

Latches e flip-flops contêm nós realimentados e redes transistorizadas comandadas por clock.

Sua potência inclui:

- clock interno;
- atividade dependente dos dados;
- carga de saída;
- leakage.

Um registrador mantendo o mesmo valor pode continuar consumindo energia na clock tree se não houver gating.

Os capítulos de lógica sequencial desenvolvem a semântica; este explica o custo físico das transições.

## Potência CMOS não é contagem de operações do código

Uma expressão como:

~~~text
(red << 16) | (green << 8) | blue
~~~

pode compilar para diversas instruções.

O processador pode realizá-las usando:

- pipeline;
- registradores físicos renomeados;
- caches;
- branch prediction;
- múltiplas unidades;
- clock gating;
- especulação.

Logo operadores do código não mapeiam um-para-um para:

- gates CMOS;
- transições de transistores;
- capacitância carregada;
- joules.

A fronteira precisa permanecer explícita.

## Reconciliação com o código do ChrisOS

Na revisão da3df29cb397932c43d32373871fb9380e688ade, o ChrisOS expõe estado arquitetural e de software, não estado físico de potência em nível de transistor.

Fontes revisadas:

~~~text
chrisvm/chris_arch.h
chrisvm/cpu/emulator/chriscpu.c
kernel/gfx/graphics.c
~~~

Símbolos:

~~~text
ChrisArchitectureState
cpu_run
gfx_rgb
~~~

Esses arquivos estabelecem a fronteira superior.

## ChrisArchitectureState

ChrisArchitectureState representa grandezas visíveis pela arquitetura como:

- registradores de propósito geral;
- RIP;
- RFLAGS;
- control registers;
- segmentos;
- MSRs selecionados;
- estado XMM;
- TSC modelado.

Não representa:

- capacitância de transistor;
- delay de gate;
- corrente de rail;
- atividade de clock tree;
- temperatura do die;
- leakage.

Vetor de estado arquitetural não é vetor de estado elétrico.

## cpu_run

O loop cpu_run do ChrisCPU:

- busca bytes;
- decodifica instrução;
- executa semântica modelada;
- atualiza RIP;
- trata interrupções modeladas;
- incrementa contadores de steps e TSC.

Os incrementos:

~~~text
cpu->steps++
cpu->arch.tsc++
~~~

não representam transições físicas de clock nem joules consumidos por uma CPU real.

São contadores do modelo do emulador.

## gfx_rgb

gfx_rgb empacota canais de 8 bits com shifts e OR.

A regra de representação é:

~~~text
red   -> bits 16..23
green -> bits 8..15
blue  -> bits 0..7
~~~

Isso não diz quantos gates o compilador ou processador usa.

Diferentes CPUs e sequências compiladas podem produzir o mesmo valor com atividades físicas diferentes.

## Fronteira de inicialização

Não existe inicialização de modelo de potência CMOS nas fontes citadas.

ChrisCPU inicializa estado arquitetural emulado.

Graphics inicializa buffers e metadados.

Nenhum deles inicializa:

- tabelas de capacitância;
- bibliotecas de timing;
- curvas V-f;
- modelos de leakage.

Nenhuma inicialização transistor-level é inferida.

## Estado e estruturas de dados

Estado físico relevante inclui:

~~~text
tensões de nós
cargas
estados de condução
corrente de alimentação
temperatura local
fase de clock
~~~

Essas grandezas não estão em ChrisArchitectureState.

A invariante é:

~~~text
estado arquitetural
!=
estado microarquitetural
!=
estado elétrico de transistores
~~~

## Algoritmos e complexidade

Avaliar P = αCV²f para um nó é O(1).

Somar N atividades conhecidas é O(N).

Simulação de circuito detalhada resolve sistemas diferenciais/algebraicos não lineares ao longo do tempo e pode ser muito mais custosa.

A complexidade do emulador de instruções ChrisCPU é outro problema.

Seu loop não pode ser usado como evidência de complexidade de simulação transistor-level.

## Propriedade de memória

ChrisOS não possui estrutura atual para potência física CMOS.

O emulador possui estado arquitetural e de máquina.

Graphics possui framebuffer/backbuffer.

Nenhum desses buffers é uma waveform de potência ou netlist de gates.

Uma ferramenta futura precisaria ownership explícito para:

- traces de eventos;
- modelos de capacitância;
- contadores de atividade;
- estado V-f;
- estado térmico.

## Fronteira de ABI

ISA e ABIs de dispositivos expõem comportamento funcional.

Normalmente não expõem cada transição interna.

Mesmo performance counters, quando disponíveis, são eventos microarquiteturais agregados.

As fontes citadas não definem ABI para:

- watts medidos;
- joules por instrução;
- capacitância;
- corrente de rail;
- leakage de transistor.

## Concorrência

Silício real comuta muitos nós simultaneamente.

ChrisCPU executa um loop de CPU modelada conforme controle do software.

Concorrência elétrica e concorrência de threads são conceitos distintos.

Nenhum lock do kernel serializa comutação física dentro da CPU host.

Em sentido inverso, mais threads de software podem aumentar atividade física indiretamente.

## Falhas e recuperação

| Mecanismo | Efeito possível |
|---|---|
| delay excessivo | violação de timing |
| droop | transição lenta ou erro lógico |
| leakage elevado | violação térmica/potência |
| superaquecimento | throttling, fault ou dano |
| campo excessivo | degradação |
| clock instável | erro de amostragem |
| crosstalk | erro de timing/ruído |

Software pode observar:

- cálculo incorreto;
- reset;
- machine check;
- timeout;
- throttling.

Esses sintomas não identificam uma causa física única.

## Segurança e privilégio

Timing e potência podem vazar informação sobre o processamento.

Exemplos de pesquisa:

- timing side channels;
- power analysis;
- análise eletromagnética;
- fault injection por tensão/clock.

Este capítulo não afirma exploit específico contra ChrisOS.

A lição arquitetural é que comportamento de software pode modular atividade física mesmo sem endereçar transistores diretamente.

## Compromissos de desempenho

| Decisão | Efeito em velocidade | Efeito em potência/energia |
|---|---|---|
| aumentar largura | mais drive | mais capacitância/leakage |
| aumentar V_DD | mais rápido | energia dinâmica quadrática |
| aumentar frequência | mais throughput | potência dinâmica aproximadamente linear |
| adicionar buffers | reduz fan-out extremo | mais capacitância interna |
| clock gating | pouco efeito ativo quando habilitado | reduz switching ocioso |
| power gating | wake-up maior | reduz leakage |
| borda mais lenta | pode reduzir ruído | pode aumentar delay |

O ótimo depende de workload, biblioteca física e restrições do produto.

## Evidência de validação deste capítulo

O checker determinístico valida:

~~~text
energia armazenada:
    E = 1/2 C V²

energia de um ciclo:
    E_cycle = C V²

potência dinâmica:
    P = α C V² f

carga:
    Q = C V

corrente média:
    I = ΔQ/Δt

delay RC até 50%:
    t_50 = ln(2) R C

capacitância de fan-out:
    C_load = N C_in + C_wire

acoplamento com PDN:
    ΔV = Z_PDN ΔI
~~~

A parte de source contract verifica os símbolos atuais do ChrisOS e a ausência de alegação transistor-level.

O checker não é caracterização de potência de silício.

## Limitações atuais

Este capítulo não fornece:

- standard-cell library de foundry;
- netlists SPICE;
- parasitas extraídos;
- parâmetros BSIM;
- potência medida da CPU host;
- calibração energética de performance counters;
- tabelas DVFS reais;
- simulação transistor-level no ChrisCPU;
- timing signoff.

Esses itens exigem evidência de processo, implementação ou hardware.

## Fronteira do roadmap

A progressão conceitual é:

~~~text
eletrostática MOS
      ↓
condução MOSFET
      ↓
lógica CMOS pull-up/pull-down
      ↓
capacitância e delay RC
      ↓
potência dinâmica + curto + leakage
      ↓
fan-out e timing
      ↓
níveis lógicos e noise margins
      ↓
timing sequencial e clock
~~~

O próximo capítulo ausente, logic-levels-noise-margins, formaliza thresholds, loading e restauração sobre a base física desenvolvida aqui.

## Proveniência da revisão

As alegações ligadas à implementação foram conciliadas contra ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

As fontes exatas são chrisvm/chris_arch.h, chrisvm/cpu/emulator/chriscpu.c e kernel/gfx/graphics.c, com símbolos ChrisArchitectureState, cpu_run e gfx_rgb.

A teoria física foi conferida com material do MIT 6.012 sobre capacitores MOS, inversores CMOS e scaling CMOS. Grandezas SI seguem a BIPM SI Brochure 9ª edição versão 4.01.

Nenhum mapeamento entre step count do ChrisCPU ou operadores do kernel e energia real de transistores é afirmado.
