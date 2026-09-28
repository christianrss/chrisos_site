---
id: transmission-lines-differential-signals
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/pci.c
  - kernel/metal/pci.h
symbols:
  - pci_read
  - pci_write
depends_on:
  - electromagnetic-induction-transformers
  - ac-signals-frequency-impedance
related:
  - noise-grounding-signal-integrity
  - power-delivery-regulation
  - clock-timing
  - buses-mmio-dma
  - pci-pcie
---

# Linhas de transmissão e sinalização diferencial

<div class="abstract">
Um condutor deixa de se comportar como um fio equipotencial quando atraso de propagação, indutância distribuída e capacitância distribuída tornam-se significativos em relação à transição do sinal transportado. A teoria de linhas de transmissão substitui a aproximação de fio concentrado por ondas eletromagnéticas viajantes caracterizadas por constante de propagação, impedância característica, atenuação e atraso. Este capítulo deriva as equações dos telegrafistas, reflexões e terminações, modos diferencial e comum, impedância de pares acoplados, perdas, crosstalk, caminhos de retorno, descontinuidades e a relação entre enlaces físicos e protocolos digitais. Em seguida, fixa precisamente a fronteira do ChrisOS: o código PCI atual realiza transações de espaço de configuração visíveis ao software e não implementa o PHY elétrico PCI Express, equalização ou modelo de linha de transmissão da placa.
</div>

## Pré-requisitos e escopo

Este capítulo pressupõe:

- tensão, corrente, resistência e potência;
- capacitância e indutância;
- impedância em regime senoidal;
- indução eletromagnética;
- notação básica de números complexos;
- distinção entre estado de protocolo visível ao software e comportamento elétrico físico.

O objetivo não é transformar toda interconexão em um problema completo de campos eletromagnéticos. O objetivo é identificar quando a aproximação concentrada comum

~~~text
tensão no nó A ≈ tensão no nó B no mesmo instante
~~~

deixa de ser adequada.

Uma linha de transmissão não é definida por ser fisicamente longa em centímetros. Ela é definida por comprimento elétrico: atraso de propagação e comportamento distribuído em relação à escala de tempo e ao espectro da forma de onda.

## De fios concentrados para circuitos distribuídos

Uma interconexão curta e lenta pode frequentemente ser aproximada por uma resistência, uma capacitância e talvez uma indutância.

Uma interconexão fisicamente extensa contém resistência, indutância, capacitância e fuga dielétrica continuamente ao longo do comprimento.

Para uma seção diferencial de comprimento (dx), definem-se parâmetros por unidade de comprimento:

| Símbolo | Significado | Unidade SI |
|---|---|---|
| R' | resistência série por comprimento | Ω/m |
| L' | indutância série por comprimento | H/m |
| G' | condutância transversal por comprimento | S/m |
| C' | capacitância transversal por comprimento | F/m |

Um modelo infinitesimal é

~~~text
       R'dx        L'dx
----////--------LLLL----->
        |                      |
        | G'dx                 | C'dx
        |                      |
-------+----------------------+--- referência
~~~

Nenhuma seção isolada explica propagação. A propagação emerge do contínuo de seções acopladas.

## Equações dos telegrafistas

Aplicando KVL e KCL a um segmento infinitesimal e tomando o limite, obtêm-se as equações dos telegrafistas:

~~~text
∂V/∂x = -R' I - L' ∂I/∂t

∂I/∂x = -G' V - C' ∂V/∂t
~~~

São equações diferenciais distribuídas. Tensão e corrente dependem simultaneamente de posição e tempo.

Em regime senoidal, substitui-se derivação temporal por (jω):

~~~text
dV/dx = -(R' + jωL') I

dI/dx = -(G' + jωC') V
~~~

Derivando novamente, surgem equações de onda:

~~~text
d²V/dx² = γ² V

d²I/dx² = γ² I
~~~

com constante de propagação

~~~text
γ = sqrt[(R' + jωL')(G' + jωC')]
~~~

Escreva

~~~text
γ = α + jβ
~~~

onde:

~~~text
α = constante de atenuação
β = constante de fase
~~~

A solução geral de tensão é a soma de uma onda direta e uma onda reversa:

~~~text
V(x) = V+ e^(-γx) + V- e^(+γx)
~~~

O termo reverso representa matematicamente a reflexão.

## Impedância característica

A razão entre tensão e corrente de uma única onda viajante é a impedância característica:

~~~text
Z0 = sqrt[(R' + jωL') / (G' + jωC')]
~~~

Z0 não é a resistência CC do condutor.

É a relação tensão/corrente de uma onda eletromagnética viajante suportada pela estrutura.

Para uma linha de baixa perda ou idealmente sem perdas, desprezando R' e G':

~~~text
Z0 = sqrt(L'/C')
~~~

e

~~~text
γ = jω sqrt(L'C')
~~~

portanto

~~~text
β = ω sqrt(L'C')
~~~

e a velocidade de fase é

~~~text
v_p = ω/β = 1/sqrt(L'C')
~~~

O atraso de ida de uma linha uniforme de comprimento (l) é

~~~text
t_d = l / v_p
~~~

ou, de forma equivalente,

~~~text
t_d = l sqrt(L'C')
~~~

na aproximação ideal sem perdas.

## Propagação é finita

Uma transição lançada em uma extremidade não aparece simultaneamente em todos os pontos.

Uma linha temporal simplificada é:

~~~text
driver altera tensão
      |
      v
onda direta é lançada
      |
      |  atraso de propagação t_d
      v
carga recebe primeira borda incidente
      |
      v
pode surgir reflexão
      |
      |  atraso de propagação t_d
      v
fonte recebe reflexão de retorno
~~~

Uma ida e volta completa requer aproximadamente (2 t_d).

Esse fato é central para temporização digital. Um receptor pode temporariamente observar uma tensão determinada por ondas incidente e refletida antes de a fonte possuir qualquer informação sobre a incompatibilidade da carga.

## Comprimento elétrico e tempo de subida

Para uma senoide, comprimento elétrico pode ser comparado ao comprimento de onda:

~~~text
λ = v_p / f
~~~

Para uma borda digital, a escala mais relevante normalmente é o tempo de subida/descida, porque uma borda rápida contém harmônicos muito acima da frequência nominal do bit ou do clock.

Não existe uma lei física universal dizendo que uma trilha se torna linha de transmissão exatamente em uma fração específica do tempo de subida. Regras de engenharia que comparam atraso de ida a uma fração do tempo de borda são critérios aproximados.

A sequência de raciocínio segura é:

~~~text
obter tempo de borda / espectro relevante
      ↓
estimar atraso de propagação
      ↓
comparar os dois
      ↓
se o atraso for material, usar análise distribuída
~~~

Baixa frequência de clock não garante comportamento concentrado quando as transições de borda são rápidas.

## Coeficiente de reflexão

Considere uma linha de impedância característica (Z0) terminada por uma carga (ZL).

Na carga, o coeficiente de reflexão de tensão é

~~~text
Γ_L = (Z_L - Z0) / (Z_L + Z0)
~~~

A tensão refletida é

~~~text
V_reflected = Γ_L V_incident
~~~

e a tensão na carga no instante de chegada é

~~~text
V_load = V_incident + V_reflected
       = V_incident (1 + Γ_L)
~~~

Casos ideais importantes:

| Carga | ΓL | Consequência |
|---|---:|---|
| ZL = Z0 | 0 | nenhuma onda refletida |
| circuito aberto | +1 | tensão refletida com mesma polaridade |
| curto-circuito | -1 | tensão refletida com polaridade oposta |
| ZL > Z0, finita | entre 0 e +1 | reflexão positiva parcial |
| 0 < ZL < Z0 | entre -1 e 0 | reflexão negativa parcial |

A reflexão de corrente possui sinal oposto para a onda reversa porque a corrente da onda reversa se propaga na direção oposta.

## Coeficiente de reflexão da fonte

Uma onda refletida que retorna à fonte encontra a impedância de fonte (ZS).

O coeficiente de reflexão de tensão na fonte é

~~~text
Γ_S = (Z_S - Z0) / (Z_S + Z0)
~~~

Se nem fonte nem carga estiverem casadas, ondas podem ricochetear repetidamente:

~~~text
fonte -> carga -> fonte -> carga -> ...
~~~

Cada ida e volta é escalada pelos produtos dos coeficientes de reflexão e pela atenuação da linha.

É por isso que ringing pode persistir depois de uma transição digital mesmo quando o valor lógico já é conhecido.

## Amplitude inicialmente lançada

Uma fonte com tensão de Thévenin (VS) e impedância de fonte (ZS), ao lançar em uma linha, inicialmente vê (Z0):

~~~text
V+ = VS Z0 / (ZS + Z0)
~~~

Somente depois que reflexões retornam a fonte recebe informação sobre a carga remota.

Exemplo:

~~~text
VS = 1.0 V
ZS = 50 Ω
Z0 = 50 Ω

V+ = 0.5 V
~~~

Se a extremidade remota estiver aberta, ΓL = +1 e a tensão na carga torna-se 1,0 V quando a borda incidente chega.

## Ondas estacionárias e VSWR

Em uma linha senoidal com magnitude de reflexão |Γ|, a interferência entre ondas direta e reversa produz máximos e mínimos estacionários.

A relação de onda estacionária de tensão é

~~~text
VSWR = (1 + |Γ|) / (1 - |Γ|)
~~~

para |Γ| < 1.

Uma linha casada tem

~~~text
Γ = 0
VSWR = 1
~~~

VSWR é útil para comportamento periódico de RF. Para transições digitais isoladas, diagramas de reflexão no domínio do tempo costumam ser mais intuitivos.

## Impedância de entrada de linha sem perdas

Uma linha sem perdas de comprimento (l), constante de fase (β) e carga (ZL) apresenta impedância de entrada

~~~text
Z_in =
Z0 [ZL + j Z0 tan(βl)]
   -------------------
   [Z0 + j ZL tan(βl)]
~~~

Portanto, uma linha pode transformar impedância em função de seu comprimento elétrico.

Uma seção de quarto de onda pode inverter impedância no caso ideal:

~~~text
l = λ/4

Z_in = Z0² / ZL
~~~

Isso é conceitualmente relacionado à transformação de impedância por transformador, porém o mecanismo físico é propagação distribuída de ondas, e não indução magnética mútua.

## Estratégias de terminação

Terminação tenta controlar reflexões fazendo uma ou mais descontinuidades parecerem iguais à impedância da linha sobre o espectro relevante.

Estratégias comuns incluem:

| Estratégia | Princípio | Compromisso típico |
|---|---|---|
| terminação paralela | carga aproxima Z0 | potência CC contínua |
| terminação série/na fonte | ZS + R adicionado aproxima Z0 | carga pode acomodar após uma reflexão |
| terminação Thévenin | rede resistiva cria impedância/polarização alvo | potência estática e mais componentes |
| terminação CA | C-R série casa principalmente as transições | dependência de baseline/forma de onda |
| terminação diferencial | resistor entre o par aproxima Zdiff | dissipa potência diferencial |

Valores de terminação não são escolhidos apenas pela tensão lógica. Dependem da impedância da interconexão, topologia, impedância do driver, comportamento do receptor e norma da interface aplicável.

## Linhas com perdas

Linhas reais atenuam e distorcem.

A constante de propagação

~~~text
γ = α + jβ
~~~

contém perda e fase.

Mecanismos de perda incluem:

- resistência do condutor;
- efeito pelicular;
- efeito de proximidade;
- perda dielétrica;
- radiação ou fuga;
- descontinuidades de conectores e vias;
- rugosidade do condutor em frequências suficientemente altas.

À medida que a frequência aumenta, R' e G' não precisam permanecer constantes, então atenuação e impedância característica podem depender da frequência.

Uma borda digital é, portanto, filtrada enquanto se propaga.

## Dispersão

Se a velocidade de fase varia com a frequência, componentes espectrais diferentes de uma borda chegam com atrasos diferentes.

Isso é dispersão.

Consequências incluem:

- bordas aparentemente mais lentas;
- alargamento de pulsos;
- interferência intersimbólica;
- distorção de fase.

Uma linha sem perdas e não dispersiva é idealização. Estruturas reais de placa, cabo e encapsulamento são apenas aproximadamente não dispersivas dentro de faixas limitadas.

## Sinalização diferencial

Sinalização diferencial utiliza dois condutores e codifica informação principalmente em sua diferença de tensão.

Defina tensões dos condutores em relação a uma referência:

~~~text
V_p
V_n
~~~

Então

~~~text
V_diff = V_p - V_n

V_cm = (V_p + V_n) / 2
~~~

De forma equivalente,

~~~text
V_p = V_cm + V_diff/2
V_n = V_cm - V_diff/2
~~~

Essas definições separam modo diferencial de modo comum.

Uma transição puramente diferencial ideal altera os dois condutores simetricamente em torno de um nível de modo comum constante.

## Corrente diferencial e campo de retorno

Em um par simétrico ideal, as correntes diferenciais possuem mesma magnitude e direções opostas:

~~~text
I_p = +I
I_n = -I
~~~

Os campos eletromagnéticos acoplam fortemente entre os condutores, de modo que grande parte do caminho de retorno está associada ao outro membro do par.

Mas "diferencial" não significa que planos de referência e estruturas ao redor sejam irrelevantes.

Enlaces reais também suportam corrente de modo comum, corrente de deslocamento e acoplamento a chassis/planos. Assimetrias podem converter energia diferencial em modo comum.

## Modos par e ímpar

Linhas acopladas suportam soluções modais.

Para um par simétrico:

- modo ímpar corresponde a tensões/correntes opostas;
- modo par corresponde a excitação de mesma polaridade.

Uma convenção comum relaciona impedância diferencial à impedância de modo ímpar por

~~~text
Z_diff = 2 Z_odd
~~~

e relaciona impedância de modo comum à impedância de modo par conforme a normalização escolhida para tensão/corrente.

As convenções de fatores importam. Um simulador ou relatório de medição deve definir se a impedância é por condutor, modal ou porta-a-porta.

## Acoplamento altera impedância

Duas trilhas não possuem a mesma distribuição de campo quando afastadas e quando fortemente acopladas.

Reduzir a distância do par pode:

- aumentar capacitância mútua;
- alterar indutância mútua;
- alterar impedâncias de modos par/ímpar;
- alterar crosstalk para estruturas vizinhas;
- alterar sensibilidade a variações geométricas.

Portanto, impedância diferencial é uma propriedade de toda a seção transversal:

~~~text
largura da trilha
espaçamento
espessura do cobre
altura do dielétrico
constante dielétrica
geometria do plano de referência
máscara/materiais de cobertura
~~~

Ela não é determinada somente pelo espaçamento.

## Skew

Se os dois membros de um par diferencial possuem atrasos diferentes, suas transições não chegam simultaneamente.

Defina aproximadamente o skew do par como

~~~text
t_skew = |t_p - t_n|
~~~

Skew pode temporariamente converter energia diferencial em tensão de modo comum e reduzir a margem de amostragem disponível.

Casar comprimentos é uma forma de controlar skew, porém comprimentos geométricos iguais são apenas uma aproximação. Diferentes ambientes dielétricos locais ou descontinuidades ainda podem produzir atrasos elétricos distintos.

## Conversão de modo comum

Simetria perfeita mantém modos diferencial e comum separados.

Assimetrias reais incluem:

- geometrias diferentes entre as trilhas;
- transições por vias em apenas um lado;
- desequilíbrio de pinos em conectores;
- interrupções de plano de referência;
- caminhos de encapsulamento distintos;
- componentes ESD ou filtros assimétricos;
- skew do par.

Isso pode gerar conversão modal:

~~~text
diferencial -> modo comum
modo comum   -> diferencial
~~~

Energia de modo comum pode aumentar emissões eletromagnéticas e estresse do receptor mesmo quando o sinal diferencial lógico aparenta funcionar.

## Crosstalk

Mudanças de tensão e corrente em uma interconexão acoplam eletromagneticamente em interconexões próximas.

Acoplamento capacitivo está associado ao campo elétrico variável; acoplamento indutivo está associado ao campo magnético variável.

Um par distribuído de linhas agressor/vítima pode apresentar crosstalk na extremidade próxima e na extremidade distante.

Sinal e magnitude exatos dependem de:

- geometria;
- comprimento de acoplamento;
- velocidade da borda;
- terminações;
- velocidade de propagação;
- balanço entre acoplamento capacitivo e indutivo.

É inseguro atribuir uma porcentagem universal de NEXT ou FEXT sem a geometria e as condições da interface.

## Continuidade do caminho de retorno

Um sinal single-ended exige um caminho de retorno.

Em alta frequência, a corrente de retorno tende a seguir um caminho de baixa impedância eletromagnética associado ao campo do sinal, frequentemente próximo à trilha sobre um plano de referência.

Uma fenda ou vazio nesse plano pode forçar um laço maior.

Consequências podem incluir:

- maior indutância;
- laço maior de radiação;
- descontinuidade de impedância;
- crosstalk;
- conversão modal.

O esquema elétrico pode continuar mostrando "ground" como um único nó enquanto o caminho físico de retorno em alta frequência é ruim. Conectividade lógica não é suficiente para integridade de sinal.

## Vias, conectores e descontinuidades

Qualquer transição geométrica pode perturbar a impedância característica.

Exemplos:

- vias;
- stubs de via;
- conectores;
- encapsulamentos;
- estreitamentos de trilha;
- pads de teste;
- mudanças de camada;
- mudanças de plano de referência;
- capacitores de acoplamento CA;
- dispositivos ESD.

Uma descontinuidade pode ser aproximada localmente por excesso de capacitância, excesso de indutância ou pequena seção distribuída, mas o comportamento de banda larga pode exigir modelo derivado de campos ou parâmetros S medidos.

## Stubs

Um ramo não utilizado ou stub de via pode refletir energia.

Um stub se comporta como uma impedância dependente da frequência porque a onda percorre o ramo até sua extremidade e retorna.

Em certos comprimentos elétricos ele pode criar notches ou ressonâncias fortes.

Essa é uma das razões para projetos de alta velocidade controlarem barris de vias não utilizados e topologia de ramificação.

## Parâmetros S

Em alta frequência, descrições diretas por tensão/corrente podem ficar pouco convenientes porque ondas incidentes e refletidas são as grandezas naturais de medição.

Parâmetros de espalhamento descrevem relações entre ondas viajantes nas portas.

Para uma rede de duas portas:

~~~text
S11  reflexão de entrada
S21  transmissão direta
S12  transmissão reversa
S22  reflexão de saída
~~~

Os valores dependem das impedâncias de referência das portas e da frequência.

Pequeno |S11| geralmente corresponde a bom casamento para a referência adotada, enquanto |S21| caracteriza amplitude/fase transmitida. A interpretação completa exige a convenção da medição ou simulação.

Este capítulo não substitui um tratamento completo de redes de micro-ondas.

## Reflectometria no domínio do tempo

A reflectometria no domínio do tempo lança uma borda e observa energia retornada em função do tempo.

Conceitualmente:

~~~text
lançar borda conhecida
     ↓
medir reflexão versus atraso
     ↓
converter atraso em distância usando velocidade de propagação
     ↓
inferir descontinuidades de impedância
~~~

Polaridade positiva ou negativa da reflexão pode indicar se a impedância local sobe ou desce em relação à linha de referência.

A resolução espacial é limitada pelo tempo de subida da fonte, largura de banda do instrumento e características de propagação.

## Diagramas de olho e margem de amostragem

Um receptor não se importa apenas com uma transição isolada. Um fluxo de símbolos produz uma distribuição de tensões e tempos de transição.

Um diagrama de olho sobrepõe muitos intervalos unitários.

Ele visualiza efeitos como:

- interferência intersimbólica;
- ruído;
- jitter determinístico/aleatório;
- atenuação;
- reflexões;
- distorção de duty cycle;
- crosstalk.

O olho, isoladamente, não prova conformidade de protocolo. Normas definem máscaras específicas, fixtures de teste, estados de equalização e procedimentos de medição.

## Equalização

Canais com perdas podem atenuar componentes de alta frequência mais fortemente que componentes de baixa frequência.

Enlaces seriais de alta velocidade podem compensar com:

- pré-ênfase/de-ênfase no transmissor;
- equalização linear contínua no receptor;
- equalização por realimentação de decisão;
- treinamento adaptativo.

Equalização remodela deliberadamente o espectro; ela não remove a física subjacente da linha de transmissão.

Um dispositivo PCIe visível ao software pode operar corretamente enquanto esses mecanismos são tratados integralmente pela lógica PHY abaixo do sistema operacional.

## Sinalização diferencial não é automaticamente imune a ruído

Um receptor diferencial rejeita perturbação de modo comum apenas na medida em que:

- a perturbação acopla de modo semelhante aos dois condutores;
- a faixa de modo comum do receptor não é excedida;
- a rejeição de modo comum, finita, é suficiente;
- o balanço do par é preservado;
- o skew permanece aceitável.

Ruído que acopla de forma assimétrica torna-se erro diferencial e não pode ser removido por subtração de modo comum.

"Usar diferencial" não substitui controle de impedância, caminho de retorno e simetria.

## Codificação e protocolo são camadas diferentes

Um protocolo digital define símbolos, enquadramento, transições de estado e tratamento de erros.

O canal físico determina se a forma de onda codificada alcança o receptor com amplitude e margem temporal adequadas.

Uma hierarquia útil é:

~~~text
transação visível ao software
        ↓
enquadramento de link/protocolo
        ↓
codificação / serialização
        ↓
transmissor PHY
        ↓
encapsulamento + conector + linha de placa/cabo
        ↓
receptor PHY
        ↓
recuperação de clock/dados e decodificação
        ↓
resultado visível ao software
~~~

Um driver de sistema operacional normalmente entra nessa hierarquia acima da maior parte do comportamento analógico do PHY.

## Contexto de normas

A PCI-SIG PCI Express Base Specification inclui requisitos elétricos, de protocolo, arquitetura de plataforma e interface de programação. Na data de revisão desta documentação, a PCI-SIG lista a PCI Express Base Specification Revision 7.1, datada de 2026-09-17, como a especificação Base aprovada atual.

IEEE 802.3-2022 permanece a norma-base de Ethernet identificada atualmente pelo IEEE enquanto um projeto ativo P802.3 de revisão, que a sucederá, está em desenvolvimento. IEEE 802.3 separa a arquitetura MAC de entidades de camada física específicas por velocidade e meio.

Essas normas demonstram que enlaces práticos especificam muito mais do que um Z0 abstrato. Elas definem transmissores, receptores, canais, codificação, treinamento e métodos de conformidade específicos.

Nenhum limite numérico de insertion loss, máscara de olho, jitter, return loss ou equalização de uma interface deve ser transplantado para outra. Esses limites dependem da revisão e do meio físico.

## Fronteira arquitetural do ChrisOS

O código atual do ChrisOS expõe acesso ao espaço de configuração PCI por:

~~~text
pci_read(bus, slot, func, off)
pci_write(bus, slot, func, off, value)
~~~

em:

~~~text
kernel/metal/pci.c
kernel/metal/pci.h
~~~

A implementação forma o endereço de configuração PCI legado na porta de E/S 0xCF8 e transfere dados pela 0xCFC.

Isso é um mecanismo de configuração visível ao software. Não é serializador PCI Express, equalizador de lane, modelo de canal, TDR, analisador de olho nem solver de linhas de transmissão.

As funções atuais não recebem parâmetros para:

~~~text
geometria de trilha
Z0 / Zdiff
insertion loss
return loss
presets de lane
coeficientes de equalização
máscaras de olho
parâmetros S
atraso de propagação
~~~

Portanto, este capítulo não pode inferir comportamento da placa ou do PHY PCIe a partir de pci_read/pci_write.

## Fronteira de evidência de hardware atual

O arquivo revisado docs/CURRENT_HARDWARE_AUDIT.md afirma explicitamente que nada naquele audit está classificado como PROVEN-HARDWARE e que nenhuma máquina física foi inicializada naquele passe.

Isso é relevante aqui.

Uma transação PCI de configuração bem-sucedida sob QEMU não pode validar:

- impedância física de lanes;
- abertura de olho no receptor;
- perda de conector;
- caminhos de retorno na PCB;
- convergência de equalização;
- compatibilidade eletromagnética.

Essas são classes de evidência separadas.

## Inicialização e fluxo de controle no ChrisOS

Não existe uma sequência de inicialização de linha de transmissão no código atual do ChrisOS revisado para este capítulo.

Na fronteira de software, um acesso PCI simplificado é:

~~~text
chamador seleciona BDF + offset de configuração
        ↓
pci_read / pci_write
        ↓
transação por portas de E/S x86
        ↓
abstração de plataforma / root complex
        ↓
estado de configuração do dispositivo
~~~

O enlace físico PCIe, quando há hardware PCIe real, opera abaixo dessa API.

O código inspecionado aqui não expõe a máquina de estados do PHY ao ChrisOS.

## Estado e estruturas de dados

A física da linha de transmissão possui estado contínuo distribuído no espaço:

~~~text
V(x,t)
I(x,t)
estado de campo eletromagnético
estado de polarização/perda do material
~~~

Um modelo de software concentrado ou discretizado poderia representar esse estado por amostras, seções ou buffers de ondas viajantes.

O ChrisOS atual não define tal estrutura de dados nos arquivos citados por este capítulo.

O estado visível ao software em pci.c é estado de transação de configuração: bus, slot, function, offset, endereço e valor de registrador retornado. Ele não deve ser rebatizado como estado do enlace físico.

## Algoritmos e complexidade

Para uma linha uniforme ideal, calcular grandezas fechadas como

~~~text
Z0
v_p
t_d
Γ
~~~

é aritmética de tempo constante.

Um modelo amostrado no domínio do tempo com (N) amostras espaciais ou temporais exige pelo menos O(N) de armazenamento para histórico explícito da forma de onda, salvo uso de representação especializada comprimida/recursiva.

Um solver geral de campos possui outro perfil de complexidade, dependente de discretização, esparsidade de matrizes, modelo de material e método numérico.

O loop de configuração de um driver não pode ser usado como evidência da complexidade de um solver eletromagnético.

## Propriedade de memória, ABI e fronteira de formato físico

As equações dos telegrafistas não possuem proprietário de heap no kernel nem ABI.

Quando software interage com um dispositivo real de alta velocidade, propriedade se aplica a objetos visíveis ao software como:

- registradores MMIO ou de configuração;
- rings de DMA;
- descritores;
- estado de interrupção;
- estruturas de mailbox de firmware.

Esses objetos pertencem a camadas superiores.

Símbolos elétricos em uma lane serial são uma codificação física governada pela especificação da interface, e não uma ABI C do ChrisOS.

## Concorrência e temporização

Múltiplas CPUs podem acessar simultaneamente estruturas de software, porém propagação física não é uma thread de software.

Um enlace físico evolui continuamente de acordo com dinâmica eletromagnética e máquinas de estado do PHY.

Concorrência de software torna-se relevante quando um driver coordena:

- inicialização de dispositivo;
- mudanças de status do link;
- interrupções;
- conclusão de DMA;
- reset e recuperação.

Nenhum desses contratos de sincronização deve ser inventado em um capítulo de fundamentos sem evidência do código atual.

## Fronteira de privilégio e segurança

Impedância característica e coeficiente de reflexão não possuem nível de privilégio de CPU.

Segurança aparece em camadas superiores por propriedade de dispositivos, isolamento de DMA, autenticação de protocolo e verificações de privilégio.

Injeção física de falhas ou canais laterais eletromagnéticos são assuntos de segurança distintos. Eles exigem modelos de ameaça e medições que não estão estabelecidos pela evidência atual do ChrisOS.

## Modos de falha

| Falha ou erro de modelagem | Consequência observável |
|---|---|
| ZL materialmente diferente de Z0 | reflexão e ringing |
| fonte também descasada | re-reflexões repetidas |
| tempo de borda ignorado | barramento nominalmente lento analisado incorretamente |
| ruptura de plano de referência | descontinuidade do retorno e maior indutância de laço |
| assimetria do par | conversão diferencial/modo comum |
| skew excessivo | menor margem temporal diferencial |
| descontinuidade de conector/via | reflexão localizada |
| stub longo | notch/ressonância |
| perdas ignoradas | degradação de borda e olho subestimada |
| crosstalk ignorado | ruído/erro temporal no sinal vítima |
| faixa de modo comum ignorada | receptor diferencial pode falhar apesar de Vdiff válido |
| sucesso de protocolo tratado como prova de SI | margem física permanece desconhecida |
| sucesso no emulador tratado como prova de hardware | canal real permanece não validado |

## Recuperação e diagnóstico

Um canal físico puro não "tenta novamente" sozinho, a menos que o protocolo ao redor forneça recuperação.

Recuperação em nível de sistema pode incluir:

- retreinamento de link;
- negociação de taxa menor;
- retreinamento de equalização;
- replay de pacotes;
- código corretor de erros;
- reset de dispositivo.

A disponibilidade de cada mecanismo depende da interface e de sua implementação.

Acesso de configuração do ChrisOS por si só não estabelece qual caminho físico de recuperação foi executado.

## Evidência de validação

O checker determinístico associado a este capítulo verifica:

~~~text
linha sem perdas:
    Z0 = sqrt(L'/C')
    vp = 1/sqrt(L'C')
    td = comprimento/vp

reflexão na carga:
    Γ = (ZL-Z0)/(ZL+Z0)

carga casada:
    Γ = 0

aberto:
    Γ = +1

curto:
    Γ = -1

lançamento da fonte:
    V+ = VS Z0/(ZS+Z0)

decomposição diferencial/comum:
    Vdiff = Vp-Vn
    Vcm = (Vp+Vn)/2

VSWR:
    (1+|Γ|)/(1-|Γ|)
~~~

Ele também verifica âncoras dos capítulos bilíngues, revisão analisada e os caminhos/símbolos exatos do ChrisOS citados no frontmatter.

Esses são testes de equações e documentação. Não são ensaios de osciloscópio, VNA, TDR, conformidade PCIe ou conformidade Ethernet.

## Desempenho e compromissos

Engenharia de interconexões é multiobjetivo.

Terminação mais forte pode reduzir reflexão, porém consumir potência ou reduzir amplitude. Acoplamento diferencial mais forte pode melhorar confinamento de campo, mas alterar restrições de roteamento e impedância do par. Bordas mais rápidas reduzem incerteza de transição no receptor, porém aumentam conteúdo de alta frequência, crosstalk e sensibilidade a EMI. Equalização pode recuperar canais com perdas, mas consome potência e pode amplificar ruído.

O projeto físico correto segue o orçamento de canal e o modelo de conformidade da interface-alvo, em vez de maximizar uma métrica isolada.

## Limitações atuais

Este capítulo não fornece:

- derivação de campo de Maxwell completa para geometria arbitrária;
- implementação de solver 2D/3D;
- extração de propriedades dielétricas;
- modelos S de conectores/encapsulamentos;
- máscaras e fixtures de conformidade PCIe ou Ethernet;
- matemática detalhada de CDR de SerDes;
- algoritmos de equalização adaptativa em profundidade;
- dados medidos do canal de hardware do ChrisOS.

Esses tópicos exigem geometria específica, normas, instrumentação ou evidência de implementação.

## Fronteira do roadmap

A progressão conceitual é:

~~~text
indutância + capacitância
        ↓
L' e C' distribuídos
        ↓
ondas viajantes e Z0
        ↓
reflexão / terminação
        ↓
modos diferencial e comum
        ↓
crosstalk / retorno / descontinuidades
        ↓
integridade de sinal e ruído
        ↓
distribuição de potência e restrições de plataforma de alta velocidade
~~~

O próximo capítulo desenvolve mecanismos de ruído, aterramento e integridade de sinal sobre esses fundamentos de linhas de transmissão.

Este roadmap é ordem documental, não uma afirmação de que o ChrisOS implementará um solver de campos.

## Proveniência da revisão

Revisado contra o main do ChrisOS na revisão da3df29cb397932c43d32373871fb9380e688ade.

A fronteira de implementação foi conciliada com kernel/metal/pci.c, kernel/metal/pci.h e docs/CURRENT_HARDWARE_AUDIT.md. Os símbolos concretos pci_read e pci_write foram inspecionados como primitivas de configuração PCI em nível de software. Não se afirma que eles implementem ou exponham equalização do PHY PCI Express, linhas de transmissão de placa ou estado de conformidade física.

O contexto externo de normas foi verificado contra o catálogo atual de especificações Base da PCI-SIG e o programa de normas IEEE 802.3. As equações deste capítulo são relações gerais de linhas de transmissão; limites elétricos específicos de uma interface continuam sendo regidos pela revisão da especificação e pelo meio aplicáveis.
