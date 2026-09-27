---
id: electromagnetic-induction-transformers
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - ac-signals-frequency-impedance
  - capacitance-inductance
related:
  - transmission-lines-differential-signals
  - power-delivery-regulation
  - clock-timing
---

# Indução eletromagnética e transformadores

<div class="abstract">
A indução eletromagnética liga fluxo magnético variável a campo elétrico e tensão. Ela é a base física de transformadores, indutores, geradores, transformadores de corrente, muitos conversores de potência e uma ampla classe de mecanismos de acoplamento indesejado. Este capítulo deriva a lei de Faraday, a lei de Lenz, fluxo concatenado, indutância mútua, modelos de transformador ideal e não ideal, impedância refletida, corrente de magnetização, perdas no núcleo, saturação, indutância de dispersão, capacitâncias parasitas, restrições de isolamento e os limites dos modelos concentrados. Também separa esses mecanismos físicos do comportamento atual do ChrisOS: o sistema operacional não implementa solver de campos nem modelo de transformador.
</div>

## Pré-requisitos e escopo

Os fundamentos necessários são:

- carga elétrica, campo, potencial e energia;
- tensão, corrente, resistência e potência;
- capacitância e indutância;
- leis de Kirchhoff;
- frequência, fase, fasores e impedância em CA;
- orientação vetorial básica e grandezas com sinal.

O capítulo usa a aproximação de circuitos concentrados quando apropriado, mas começa por grandezas de campo porque um transformador não deve ser entendido corretamente como um componente misterioso de relação de tensão.

O código-fonte atual do ChrisOS **não** implementa simulação eletromagnética de campos, projeto de componentes magnéticos nem solver de transformadores. A revisão de fonte analisada é registrada apenas para tornar explícita essa fronteira de implementação.

## Fluxo magnético

O fluxo magnético através de uma superfície orientada (S) é

~~~text
Φ_B = ∫_S B · dA
~~~

onde (B) é a densidade de fluxo magnético e (dA) é o elemento de área orientado.

Para (B) aproximadamente uniforme sobre uma área plana (A),

~~~text
Φ_B = B A cos θ
~~~

onde θ é o ângulo entre o campo e a normal da superfície.

A unidade SI de fluxo magnético é o weber:

~~~text
1 Wb = 1 V·s
~~~

Fluxo, portanto, não é "a quantidade de corrente no núcleo". É uma integral de superfície da densidade de fluxo magnético. Corrente pode produzir campo magnético, mas a geometria e a resposta do material determinam o fluxo resultante.

## Lei de Faraday-Maxwell

A forma integral da lei de Faraday é

~~~text
∮_C E · dl = - d/dt ∫_S B · dA
~~~

para um contorno (C) que limita a superfície (S).

O lado esquerdo é a circulação do campo elétrico ao longo do contorno. O lado direito é a derivada temporal negativa do fluxo magnético.

Para uma espira condutora representada como circuito, a força eletromotriz induzida é

~~~text
e = - dΦ_B/dt
~~~

Para um enrolamento de (N) espiras que concatenam aproximadamente o mesmo fluxo,

~~~text
λ = N Φ_B
e = - dλ/dt = -N dΦ_B/dt
~~~

onde λ é o fluxo concatenado.

O sinal negativo não é decorativo. Ele codifica a orientação e a oposição física resumida pela lei de Lenz.

## Lei de Lenz e consistência de energia

A lei de Lenz afirma que a resposta induzida possui direção que se opõe à mudança de fluxo que a produziu.

Um argumento energético ajuda a explicar o motivo. Se a corrente induzida reforçasse a mudança inicial sem outra fonte de energia, uma pequena variação poderia criar mais campo, que criaria mais corrente, produzindo energia sem trabalho. O sinal negativo na lei de Faraday impede essa interpretação.

"Opõe-se à mudança" não significa que o campo induzido seja sempre oposto ao campo original. Se o fluxo original estiver diminuindo, a resposta induzida tende a sustentar sua direção anterior. A oposição é a (dΦ/dt).

## Fluxo concatenado e autoindutância

Em um sistema magnético linear, o fluxo concatenado pode ser proporcional à corrente do enrolamento:

~~~text
λ = L i
~~~

Então,

~~~text
v = dλ/dt = L di/dt
~~~

sob a convenção passiva de sinais do circuito.

De forma mais geral,

~~~text
v = dλ(i,t)/dt
~~~

e (L) não precisa ser constante. Núcleos ferromagnéticos podem tornar a relação λ versus i não linear e dependente do histórico.

A equação familiar do indutor ideal é, portanto, um modelo de circuito reduzido da indução eletromagnética, não uma lei independente.

## Dois enrolamentos acoplados

Considere dois enrolamentos. Em um modelo linear e recíproco,

~~~text
λ1 = L1 i1 + M i2
λ2 = M i1 + L2 i2
~~~

Derivando,

~~~text
v1 = L1 di1/dt + M di2/dt
v2 = M di1/dt + L2 di2/dt
~~~

O parâmetro (M) é a indutância mútua.

Um coeficiente de acoplamento adimensional comum é

~~~text
k = M / sqrt(L1 L2)
~~~

de modo que

~~~text
M = k sqrt(L1 L2)
~~~

Para indutores acoplados passivos no modelo linear usual,

~~~text
0 ≤ |k| ≤ 1
~~~

O sinal dos termos mútuos depende da orientação dos enrolamentos e das direções de referência adotadas.

## Convenção dos pontos

Diagramas de circuito usam pontos para preservar a polaridade entre enrolamentos sem desenhar a direção física de cada espira.

Uma interpretação consistente é:

~~~text
corrente entrando no terminal pontuado do enrolamento 1
    → tensão mutuamente induzida positiva no terminal pontuado do enrolamento 2
~~~

desde que a referência de tensão seja definida do terminal pontuado para o não pontuado.

Alterar a referência de corrente ou de tensão altera o sinal algébrico. Memorizar o sinal sem declarar as referências é inseguro.

A convenção dos pontos é crítica em conversores flyback, indutores acoplados, transformadores de corrente e enrolamentos de realimentação.

## Hipóteses do transformador ideal

O transformador ideal é um modelo limite com:

- acoplamento perfeito;
- resistência de enrolamento nula;
- indutância de dispersão nula;
- indutância de magnetização infinita;
- ausência de perdas por histerese ou correntes parasitas;
- ausência de capacitâncias parasitas;
- ausência de fuga dielétrica;
- ausência de saturação;
- ausência de atraso de propagação.

Ele é deliberadamente irrealizável. Seu valor é isolar a restrição de relação de espiras das perdas e parasitas.

Defina a relação de espiras como

~~~text
a = N1 / N2
~~~

Com referências compatíveis de ponto e tensão,

~~~text
V1 / V2 = N1 / N2 = a
~~~

Assim,

~~~text
V2 = V1 / a
~~~

para esta definição de (a).

## Relação de corrente e potência

Um transformador ideal não armazena energia líquida nem dissipa potência. O balanço instantâneo de potência, com sinais escolhidos consistentemente, exige

~~~text
p1 + p2 = 0
~~~

Em magnitude para regime senoidal,

~~~text
|V1 I1| = |V2 I2|
~~~

Combinando com a relação de tensão, obtém-se a relação inversa de corrente:

~~~text
I1 / I2 = N2 / N1 = 1/a
~~~

em magnitude.

Um transformador elevador aumenta a tensão e reduz proporcionalmente a capacidade de corrente para a mesma potência aparente transferida. Ele não cria potência.

## Impedância refletida

Suponha uma impedância (Z_L) conectada ao secundário.

~~~text
Z_L = V2 / I2
~~~

Usando as relações ideais, a impedância vista no primário é

~~~text
Z_in = V1 / I1
     = (N1/N2)^2 Z_L
     = a² Z_L
~~~

Essa lei quadrática é fundamental.

Exemplo:

~~~text
N1/N2 = 10
Z_L   = 8 Ω

Z_in = 10² × 8 Ω
     = 800 Ω
~~~

O transformador altera a escala de tensão e corrente pela qual a fonte observa a carga.

## Relação senoidal volts por espira

Para fluxo senoidal no núcleo,

~~~text
Φ(t) = Φ_peak sin(ωt)
~~~

a lei de Faraday fornece

~~~text
v(t) = N ω Φ_peak cos(ωt)
~~~

logo,

~~~text
V_peak = N ω Φ_peak
~~~

e, como (V_rms = V_peak/sqrt(2)),

~~~text
V_rms = (2π/sqrt(2)) f N Φ_peak
      ≈ 4.44288 f N Φ_peak
~~~

Se a densidade de fluxo é aproximadamente uniforme na área efetiva do núcleo (A_e),

~~~text
Φ_peak = B_peak A_e
~~~

então

~~~text
V_rms ≈ 4.44 f N A_e B_peak
~~~

para uma forma de onda senoidal.

Essa equação mostra por que tamanho do transformador, frequência, número de espiras e densidade de fluxo admissível são variáveis de projeto acopladas.

## Volt-segundos e formas de onda arbitrárias

A relação mais geral é

~~~text
ΔΦ = (1/N) ∫ v(t) dt
~~~

ou, em densidade de fluxo sob a aproximação de núcleo uniforme,

~~~text
ΔB = (1/(N A_e)) ∫ v(t) dt
~~~

Portanto, a excitação do núcleo é governada por **volt-segundos**, não somente por tensão.

Um transformador excitado por onda quadrada em um conversor chaveado deve ser dimensionado a partir da forma de onda aplicada e do duty cycle. Aplicar cegamente o coeficiente senoidal 4,44 a uma onda quadrada é incorreto.

Tensão CC é especialmente perigosa: após os transitórios de chaveamento, uma tensão não nula sustentada no enrolamento faz o fluxo crescer aproximadamente como uma integral até saturação ou até outra limitação do circuito intervir.

## Indutância de magnetização

Um transformador real requer corrente para estabelecer fluxo alternado no núcleo.

Um circuito equivalente de primeira ordem coloca uma indutância de magnetização (L_m) em paralelo com o primário do transformador ideal.

Na frequência angular ω,

~~~text
Z_m = jωL_m
I_m = V1 / (jωL_m)
~~~

Mesmo com o secundário aberto, a fonte fornece corrente de magnetização.

Maior (L_m) reduz a corrente de magnetização idealizada para uma dada tensão e frequência, mas perdas reais no núcleo acrescentam um componente de corrente em fase.

## Permeabilidade e relutância magnética

Uma analogia simples de circuito magnético usa relutância

~~~text
ℜ = l / (μ A)
~~~

para uma seção uniforme de comprimento de caminho magnético (l), área (A) e permeabilidade μ.

A força magnetomotriz é

~~~text
F = N i
~~~

e a aproximação linear de circuito magnético fornece

~~~text
Φ = F / ℜ
~~~

Então,

~~~text
L = N² / ℜ
~~~

para um enrolamento cujo fluxo segue o caminho modelado.

A analogia é útil, porém limitada. Núcleos reais têm fringing, dispersão, campos distribuídos, permeabilidade não linear e perdas dependentes da frequência.

## Saturação

Materiais ferromagnéticos não preservam permeabilidade constante indefinidamente.

À medida que a força magnetizante cresce, aumentos incrementais na densidade de fluxo passam a ser muito menores. Em um transformador, isso pode fazer a indutância de magnetização efetiva colapsar.

Consequências incluem:

- crescimento rápido da corrente de magnetização;
- aquecimento dos enrolamentos;
- estresse em chaves ou fusíveis;
- distorção da forma de onda;
- aumento de perdas no núcleo;
- possível falha do conversor.

Saturação não é simplesmente "o núcleo não consegue armazenar mais fluxo". É uma região não linear da relação constitutiva entre intensidade de campo magnético e densidade de fluxo.

## Histerese

Em material ferromagnético, (B) pode depender do histórico magnético, não apenas de (H) instantâneo.

Uma trajetória cíclica (B-H) forma um laço de histerese. A área interna do laço está associada à energia perdida por unidade de volume por ciclo na interpretação magnética usual.

Essa perda aumenta o aquecimento e contribui para a potência em vazio do transformador.

Um modelo linear de (L) constante não representa histerese.

## Correntes parasitas

Um campo magnético variável também induz campos elétricos dentro do material condutor do núcleo. Esses campos podem produzir correntes circulantes que dissipam calor resistivo.

A mitigação depende da frequência e do material:

- chapas laminadas de aço elétrico interrompem grandes laços de corrente em frequências de rede;
- ferrites têm alta resistividade elétrica e são comuns em frequências maiores de chaveamento;
- núcleos de pó distribuem barreiras isolantes.

O melhor material depende da aplicação; alta permeabilidade isoladamente não é critério suficiente.

## Representação de perdas no núcleo

Um circuito equivalente simples costuma colocar uma resistência (R_c) em paralelo com (L_m).

~~~text
            ┌── R_c ──┐
primário ───┤         ├── transformador ideal
            └── jωL_m ┘
~~~

(R_c) é um elemento equivalente de perda, não um resistor literal dentro do núcleo.

O modelo pode representar a potência real total em vazio perto de um ponto operacional, mas perdas de núcleo são não lineares e dependem da frequência. Análise ampla de conversores exige modelos empíricos ou físicos melhores.

## Resistência dos enrolamentos

Cobre ou outro condutor possui resistência finita.

Um enrolamento prático inclui, portanto, resistência série:

~~~text
R_w ≈ ρ l / A_c
~~~

sob uma aproximação CC de corrente uniforme.

Em frequências maiores, efeitos pelicular e de proximidade redistribuem a corrente e aumentam a resistência CA efetiva. Usar apenas a resistência CC pode subestimar a perda.

A resistência do enrolamento produz

~~~text
P_cu ≈ I_rms² R_ac
~~~

com (R_ac) avaliada para o espectro de forma de onda e temperatura relevantes.

## Indutância de dispersão

Nem todo fluxo gerado por um enrolamento concatena o outro.

A parte não compartilhada aparece nos modelos de circuito como indutância de dispersão.

Uma topologia equivalente comum é:

~~~text
fonte
  │
 R1
  │
jωLσ1
  │
[ transformador ideal ]
  │
jωLσ2
  │
 R2
  │
 carga
~~~

A indutância de dispersão causa queda de tensão dependente da carga e armazena energia que pode produzir picos de comutação quando a corrente é interrompida.

Em conversores de potência ela pode ser indesejada, explorada intencionalmente ou ambas, conforme a topologia.

## Capacitâncias parasitas

Condutores separados por dielétrico formam capacitância. Enrolamentos de transformadores possuem:

- capacitância espira-a-espira;
- capacitância camada-a-camada;
- capacitância primário-secundário;
- capacitância enrolamento-núcleo/blindagem.

Em frequência suficientemente alta, essas capacitâncias criam ressonâncias com as indutâncias de dispersão e magnetização.

Elas também oferecem um caminho de corrente de deslocamento através do que seria, em CC, isolamento galvânico.

Assim, "transformador isolado" não significa impedância infinita em alta frequência entre enrolamentos.

## Autorressonância e largura de banda

Um transformador possui largura de banda finita.

Em baixa frequência, a reatância de magnetização pode ser pequena demais e o fluxo no núcleo pode se tornar excessivo.

Em alta frequência:

- a indutância de dispersão importa;
- as capacitâncias parasitas importam;
- a resistência CA dos enrolamentos aumenta;
- a perda no núcleo cresce;
- propagação distribuída pode invalidar o modelo concentrado.

Um transformador de banda larga é, portanto, uma rede eletromagnética acoplada, não apenas uma relação de espiras ideal.

## Isolamento galvânico

Um transformador pode transferir energia e sinais sem conexão condutiva direta entre primário e secundário.

Isso pode estabelecer uma fronteira de isolamento galvânico, mas as propriedades de segurança dependem de construção e certificação, incluindo:

- sistema de isolação;
- distância de escoamento;
- distância de isolação;
- suportabilidade dielétrica;
- tensão de trabalho;
- grau de poluição;
- grupo do material;
- categoria de sobretensão;
- arranjo dos enrolamentos.

O símbolo esquemático de um transformador, por si só, não estabelece isolamento seguro.

Documentação de produto real deve usar a norma de segurança aplicável e as classificações de componentes certificados.

## Acoplamento de modo comum

A capacitância entre enrolamentos permite corrente de modo comum:

~~~text
i_C = C_ps dv_common/dt
~~~

Bordas rápidas de chaveamento podem, portanto, injetar ruído através de um transformador de isolamento mesmo sem caminho de condução CC.

Blindagens eletrostáticas, arranjo de enrolamentos, menor capacitância e controle de (dv/dt) podem reduzir esse acoplamento, com compromissos em tamanho, dispersão, custo e outros parasitas.

## Circuito equivalente do transformador

Um modelo de engenharia útil combina as principais não idealidades:

~~~text
                 R1       Lσ1
V1 ─────────────///────LLLL─────┬────[ ideal N1:N2 ]────Lσ2──///── ZL
                                    │                         L        R2
                                    ├──── Rc ────┤
                                    │            │
                                    └──── Lm ────┘
~~~

A posição exata dos elementos referidos varia conforme a convenção. Grandezas do secundário podem ser refletidas ao primário multiplicando a impedância por (a²), reduzindo o circuito a um único lado para análise.

## Regulação e comportamento sob carga

A tensão secundária de um transformador real varia com a carga porque resistência dos enrolamentos e reatância de dispersão produzem queda interna.

Uma estimativa fasorial simplificada é

~~~text
V2,terminal ≈ V2,ideal - I2 (R2 + jXσ2)
~~~

depois que todas as grandezas são expressas consistentemente no mesmo lado.

O fator de potência da carga importa porque a fase de (I2) altera a queda vetorial. Cargas resistivas, indutivas e capacitivas podem produzir comportamentos diferentes de regulação para a mesma corrente RMS.

## Eficiência

A eficiência é

~~~text
η = P_out / P_in
~~~

com

~~~text
P_in = P_out + P_copper + P_core + P_other
~~~

Os mecanismos de perda dependem de formas diferentes de carga e frequência:

| Perda | Dependência de primeira ordem |
|---|---|
| cobre nos enrolamentos | aproximadamente (I²R) |
| histerese do núcleo | frequência, excursão de fluxo, material |
| correntes parasitas/perda dinâmica do núcleo | frequência e excursão de fluxo |
| dielétrica | tensão, frequência, material |
| perdas estruturais dispersas | campo de dispersão e corrente |

Por isso a eficiência máxima ocorre em um ponto operacional, e não é uma propriedade fixa.

## Autotransformadores

Um autotransformador compartilha eletricamente parte do enrolamento entre entrada e saída.

Ele pode reduzir cobre e tamanho para relações de conversão moderadas, mas **não** fornece isolamento galvânico entre os terminais conectados.

As relações ideais ainda ajudam na escala de tensão e corrente, mas a topologia de segurança é fundamentalmente diferente da de um transformador isolado de dois enrolamentos.

## Transformadores de corrente

Um transformador de corrente usa ação transformadora para escalar corrente para medição ou proteção.

Um modo de falha importante é secundário aberto enquanto há corrente no primário. A corrente do secundário que normalmente contrapõe os ampere-espiras do primário desaparece, de modo que fluxo no núcleo e tensão secundária podem aumentar perigosamente.

Por isso o manuseio do secundário de um transformador de corrente segue práticas de segurança específicas da aplicação. Ele não deve ser tratado como um transformador comum de baixa potência e tensão.

## Transformadores de pulso e chaveamento

Transformadores de pulso transferem formas de onda não senoidais.

Restrições relevantes incluem:

- balanço de volt-segundos;
- corrente de magnetização;
- indutância de dispersão;
- capacitância entre enrolamentos;
- distorção de tempos de subida e descida;
- duty cycle;
- mecanismo de reset;
- isolação.

Uma forma de onda com volt-segundos positivos e negativos desequilibrados pode deslocar progressivamente o ponto de operação do núcleo em direção à saturação.

## Fronteira entre armazenamento de energia e transformação

Um transformador ideal é conceitualmente um elemento de transferência de energia com energia de magnetização líquida desprezível.

Um componente magnético de flyback armazena intencionalmente energia significativa em sua indutância de magnetização durante um intervalo de chaveamento e a libera em outro. Ele é frequentemente chamado fisicamente de transformador porque possui vários enrolamentos, mas seu projeto magnético é mais próximo de um indutor acoplado com entreferro.

A distinção importa para entreferro, densidade de energia, formas de onda e raciocínio sobre circuito equivalente.

## Analogia de fluxo de controle não é uma afirmação de implementação

Diagramas de software às vezes usam "transformador" metaforicamente para estágios de conversão. Essa terminologia não possui implicação física.

Os caminhos atuais de boot, kernel, gráficos, armazenamento e linguagem do ChrisOS são sistemas digitais de software. Este capítulo não atribui equações de transformador a qualquer módulo de código.

Os conceitos físicos tornam-se relevantes ao raciocinar sobre o hardware que alimenta ou conecta a máquina: VRMs, fontes isoladas, magnetismo de Ethernet, interfaces de áudio e conversão externa de potência.

## Memória, propriedade, concorrência e privilégio

O sistema eletromagnético em si não possui propriedade de heap, ordem de locks ou nível de privilégio de CPU.

Se no futuro o ChrisOS controlar um conversor de potência, ADC, magnetômetro ou interface acoplada por transformador, o capítulo de implementação deverá documentar separadamente:

- propriedade de registradores MMIO ou barramento;
- buffers de DMA;
- clocks de amostragem;
- sincronização por interrupção;
- dados de calibração;
- representação numérica;
- acesso usuário/kernel;
- comportamento de desligamento por falha.

Nenhum desses contratos de software pode ser inferido da lei de Faraday.

## Modelagem numérica

Um modelo linear de indutores acoplados pode ser representado por uma matriz de indutâncias:

~~~text
[λ1]   [L1  M][i1]
[λ2] = [M  L2][i2]
~~~

Para (n) enrolamentos:

~~~text
λ = L i
v = dλ/dt
~~~

A matriz deve satisfazer restrições físicas associadas à energia magnética armazenada.

Para o caso linear de dois enrolamentos,

~~~text
W = 1/2 L1 i1² + M i1 i2 + 1/2 L2 i2²
~~~

Um modelo passivo de energia restringe a matriz de indutâncias para que a energia armazenada não possa se tornar arbitrariamente negativa.

Modelos de núcleo não lineares substituem (L) constante por comportamento constitutivo dependente do estado e podem exigir estado de histerese.

## Complexidade computacional

Para um pequeno circuito equivalente de transformador com tamanho fixo, a avaliação fasorial analítica tem tempo constante em relação ao tamanho do circuito.

Para uma rede geral com (n) variáveis nodais desconhecidas, elementos de transformador/indutor acoplado contribuem com estampas na matriz do sistema. Uma solução direta densa custa aproximadamente (O(n³)); solvers esparsos podem ser muito mais baratos dependendo da topologia e do fill-in.

Um solver de campos é outro problema computacional. Análise eletromagnética por elementos finitos discretiza a geometria em muitos graus de liberdade e não pode ser confundida com o modelo concentrado.

## Modos de falha e assinaturas de diagnóstico

| Falha/erro de modelo | Consequência provável |
|---|---|
| convenção dos pontos incorreta | realimentação invertida ou fase inesperada |
| poucas espiras para tensão/frequência | fluxo excessivo e saturação |
| viés CC ignorado | margem de fluxo reduzida |
| secundário de TC aberto | tensão secundária perigosa |
| indutância de dispersão ignorada | sobretensão de chaveamento subestimada |
| capacitância entre enrolamentos ignorada | EMI de modo comum subestimada |
| (R_ac) tratada como (R_dc) | perda no cobre subestimada |
| perda de núcleo tratada como constante | erro de previsão térmica |
| regra senoidal 4,44 usada para forma arbitrária | estimativa de fluxo incorreta |
| isolamento inferido apenas pelo símbolo | hipótese insegura de isolação |
| modelo concentrado usado além da banda | erros de ressonância/propagação |

## Evidência de validação

Um checker determinístico específico do capítulo deve verificar pelo menos estes invariantes:

~~~text
1. Escala de Faraday com N espiras:
   e ∝ N dΦ/dt

2. Relação ideal de espiras:
   V1/V2 = N1/N2

3. Relação ideal de corrente:
   I1/I2 = N2/N1

4. Impedância refletida:
   Zin = (N1/N2)^2 ZL

5. Fluxo senoidal:
   Vrms ≈ 4.44288 f N Φpeak

6. Indutância mútua:
   M = k sqrt(L1 L2)

7. Integração volt-segundo:
   ΔΦ = (1/N) ∫v dt
~~~

Essas equações validam os modelos ideais documentados. Elas não validam um transformador físico, sistema de isolação, projeto térmico nem driver de hardware do ChrisOS.

## Desempenho e compromissos de engenharia

Projeto de transformadores é multiobjetivo.

Aumentar o número de espiras pode reduzir a densidade de fluxo para tensão/frequência fixas, mas aumenta o comprimento do condutor e a resistência do enrolamento. Maior seção do condutor reduz resistência, mas consome área de janela. Acoplamento mais forte reduz indutância de dispersão, porém pode aumentar capacitância entre enrolamentos. Maior frequência de chaveamento pode reduzir o volume magnético necessário, mas aumenta perdas de chaveamento, núcleo e enrolamento em CA.

Não existe um transformador universalmente ótimo independentemente de forma de onda, potência, isolação, temperatura, tamanho, custo e restrições de EMI.

## Relevância atual para o ChrisOS

O ChrisOS executa sobre hardware cujos subsistemas de potência e comunicação podem conter componentes magnéticos, mas o SO normalmente enxerga as interfaces digitais acima deles.

Exemplos:

~~~text
rede / adaptador
    ↓
conversão de potência e magnetismo
    ↓
reguladores de tensão
    ↓
CPU / memória / dispositivos
    ↓
interfaces visíveis ao software ChrisOS
~~~

e potencialmente:

~~~text
PHY Ethernet
    ↕
magnetismo de isolamento
    ↕
cabo
~~~

A camada física pode falhar enquanto registradores visíveis ao software apenas relatam sintomas de link ou alimentação. Compreender a camada inferior evita atribuir incorretamente toda falha ao software.

Nenhum arquivo ou símbolo atual do ChrisOS é citado porque nenhuma afirmação de implementação revisada neste capítulo exige isso.

## Contexto de normas e terminologia

As grandezas metrológicas e os símbolos de unidade deste capítulo seguem o BIPM *International System of Units (SI)*, 9ª edição, versão 4.01 atualizada em 2026. Nesse sistema, weber (Wb), tesla (T), henry (H), volt (V), ampere (A), watt (W) e segundo (s) formam o vocabulário coerente usado pelas equações acima.

Normas de engenharia de transformadores vão muito além deste modelo fundamental. A IEEE C57.12.80-2024 é a norma IEEE ativa de terminologia para transformadores de potência e distribuição, enquanto a IEEE C57.12.00-2021 estabelece requisitos gerais para a classe de transformadores de distribuição, potência e regulação imersos em líquido dentro de seu escopo. Essas normas são usadas aqui somente para ancorar terminologia e a fronteira entre equações didáticas e requisitos de produto. Este capítulo não afirma conformidade com norma de produto, isolação ou ensaio de transformadores.

## Limitações atuais

Este capítulo não fornece:

- derivação completa das equações de Maxwell;
- simulação magnética por elementos finitos;
- ajuste empírico de parâmetros de Steinmetz;
- projeto de rede térmica de transformador;
- valores de escoamento/isolação para uma norma de segurança específica;
- caracterização RF por parâmetros S;
- driver de eletrônica de potência do ChrisOS.

Esses tópicos exigem geometria, materiais, faixa de frequência, contexto regulatório ou código-fonte que não fazem parte da evidência atual.

## Fronteira do roadmap

Os próximos tópicos de fundamentos usam indução, mas acrescentam propagação e parasitas:

~~~text
indução de Faraday
    ↓
indutância mútua / transformador
    ↓
dispersão + capacitância
    ↓
linha de transmissão distribuída
    ↓
reflexões / sinalização diferencial
    ↓
ruído, aterramento e integridade de sinal
    ↓
impedância de distribuição de potência
~~~

Essa sequência é conceitual. Ela não implica que o ChrisOS implementará um simulador eletromagnético.

## Proveniência da revisão

Revisado contra o `main` do ChrisOS em `da3df29cb397932c43d32373871fb9380e688ade`.

`sources` e `symbols` estão intencionalmente vazios porque o código-fonte atual do ChrisOS não implementa os modelos eletromagnéticos documentados aqui. As definições físicas usam grandezas SI e as relações de Maxwell-Faraday/indução; afirmações específicas de implementação foram deliberadamente omitidas em vez de inferidas por analogia com hardware.
