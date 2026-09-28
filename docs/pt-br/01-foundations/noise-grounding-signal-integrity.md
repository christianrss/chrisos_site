---
id: noise-grounding-signal-integrity
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/pci.c
  - kernel/metal/pci.h
symbols: [pci_read, pci_write]
depends_on: [transmission-lines-differential-signals, ac-signals-frequency-impedance]
related: [power-delivery-regulation, clock-timing, buses-mmio-dma, pci-pcie]
---

# Ruído, aterramento e integridade de sinal

<div class="abstract">
A lógica digital é fisicamente analógica: receptores decidem estados a partir de tensões com subida finita, atraso, ruído e incerteza de referência. Integridade de sinal preserva margens de tensão e tempo do transmissor, pelo interconector e retorno, até o receptor. Este capítulo cobre margens, retorno, crosstalk, reflexões, jitter e comutação simultânea e fixa a fronteira do ChrisOS: o PCI atual executa E/S de configuração e não valida sinalização elétrica da placa.
</div>

## Pré-requisitos e escopo

São necessários tensão, corrente, impedância, capacitância, indutância, espectro das bordas, linhas de transmissão e sinalização diferencial. Terra não é zero volts em todos os pontos: condutores reais têm impedância. Integridade de sinal pergunta se a forma de onda continua decodificável com margem de tensão e tempo diante de transmissor, encapsulamento, placa, conectores, retorno, receptor e atividade vizinha. Integridade de potência está acoplada porque alimentação e referência móveis alteram os limiares efetivos.

## Níveis lógicos e margens

Para níveis garantidos do transmissor e limiares do receptor,

[
NM_H=V_{OH(min)}-V_{IH(min)},qquad NM_L=V_{IL(max)}-V_{OL(max)}.
]

Margem estática positiva é necessária, mas insuficiente. Um glitch pode cruzar um limiar; uma borda pode violar setup ou hold; movimento da referência desloca o próprio limiar.

| Margem | Significado | Esgotamento |
|---|---|---|
| tensão | distância saída-limiar | estado lógico incorreto |
| setup/hold | estabilidade ao redor da amostragem | erro ou metaestabilidade |
| slew | faixa de velocidade da borda | incerteza, EMI, crosstalk |
| referência | tolerância ao movimento de alimentação/terra | limiar relativo se desloca |

O receptor observa o sinal contra sua referência local no instante da amostragem.

## Terra e corrente de retorno

A lei de Kirchhoff exige caminho de retorno. Em baixa frequência a distribuição é fortemente resistiva; em frequências maiores a impedância indutiva importa e a corrente de retorno se concentra perto do sinal sobre plano contínuo, reduzindo indutância do laço.

[
V_L = L · di/dt
]

explica por que pequena indutância compartilhada gera tensão transitória. Para impedância de retorno (Z_g),

[
V_shift(ω) = Z_g(ω) · Σ I_k(ω).
]

Esse é o ground bounce. O controle vem de geometria de corrente, referências de baixa impedância, conexões adequadas e desacoplamento. Uma interrupção no plano força desvios, ampliando laço, indutância, radiação e suscetibilidade. Pares diferenciais reduzem sensibilidade a modo comum, mas desequilíbrios ainda geram corrente de modo comum.

## Mecanismos de acoplamento

| Mecanismo | Modelo | Controle típico |
|---|---|---|
| impedância comum | R ou Z compartilhado | reduzir caminho comum |
| capacitivo | capacitância mútua | espaçamento, plano, borda |
| indutivo | indutância mútua | reduzir laço, preservar retorno |
| radiado | campo eletromagnético | geometria, blindagem, filtro |
| alimentação/referência | impedância PDN × corrente transitória | desacoplamento |
| reflexão | descontinuidade de impedância | impedância controlada, terminação |

Para um agressor,

[
i_C = C_m · dV_a/dt,    V_M = M · dI_a/dt.
]

Bordas mais rápidas aumentam ambos os termos. A largura de banda relevante depende fortemente dos tempos de subida e descida, não apenas da taxa de bits. Crosstalk exato em PCB exige parâmetros derivados da geometria ou medidos; código de driver não os fornece.

## Reflexões, temporização e olho

Para impedância característica (Z_0) e carga (Z_L),

[
Γ_L = (Z_L - Z_0) / (Z_L + Z_0).
]

Aberto tende a +1, curto a -1 e carga casada a 0. Reflexões criam overshoot, undershoot, ringing e cruzamentos repetidos de limiar. Terminações série, paralela e diferencial trocam potência, topologia e forma de onda; a especificação elétrica determina a estratégia válida.

Jitter é variação do instante de transição. Interferência intersimbólica ocorre quando símbolos anteriores alteram o atual. O diagrama de olho sobrepõe intervalos unitários: abertura vertical aproxima margem de tensão e horizontal, margem temporal.

~~~text
amplitude
 ^       \      /
 | \      \____/      /
 |  \     /    \     /
-+---\---/------\---/---- limiar
 |    \_/        \_/
 +-----------------------> tempo
           < olho >
~~~

O olho é diagnóstico, não automaticamente conformidade: padrões definem pontos, máscaras, fixtures e equalização.

## Comutação simultânea e modo diferencial

Se N saídas alteram cada corrente em delta-I durante delta-t através de (L_s),

[
ΔV ≈ L_s · N · ΔI/Δt.
]

Indutâncias de encapsulamento e distribuição importam mesmo com correntes individuais modestas. Desacoplamento fornece carga local, limitado por ESR, ESL, posicionamento e impedância dos planos.

Para o par,

[
V_d = V_p - V_n,    V_cm = (V_p + V_n)/2.
]

Receptores reais têm rejeição de modo comum finita. Skew, perdas desiguais, vias assimétricas e descontinuidades de retorno convertem energia diferencial em modo comum; casamento preserva equilíbrio e temporização.

## Modelo de sinal e perturbação

Um modelo útil na referência local do receptor é:

~~~text
V_observado(t)
=
V_intencional(t)
+
V_acoplado(t)
+
V_erro_alimentação(t)
-
V_erro_referência(t)
~~~

Os termos não precisam ser estatisticamente independentes. Por exemplo, uma transição de saída pode simultaneamente gerar crosstalk em uma linha vizinha e deslocar o terra local por indutância compartilhada do encapsulamento.

Perturbações podem ser classificadas como:

- determinísticas, como chaveamento periódico ou interferência dependente de dados;
- aleatórias, como ruído térmico/de dispositivo;
- de modo comum;
- de modo diferencial;
- conduzidas por impedância compartilhada;
- acopladas capacitivamente ou indutivamente;
- radiadas;
- geradas pela rede de distribuição de potência.

A grandeza de engenharia útil é a margem remanescente depois que as perturbações são combinadas segundo o modelo de medição da interface. Medir tensão de ruído diferente de zero, isoladamente, não estabelece falha.

## Margem estática versus dinâmica

Margem estática responde a uma pergunta CC. Correção em alta velocidade acrescenta a dimensão temporal da amostragem.

Um receptor pode falhar apesar de tensão final correta quando:

- a borda chega depois do limite de setup;
- ringing cruza o limiar várias vezes;
- a referência local se move durante a janela de amostragem;
- a transição é lenta a ponto de aumentar incerteza temporal;
- símbolos anteriores deixam resposta residual no canal.

Assim, robustez digital pode ser representada conceitualmente como:

~~~text
região útil de decisão
=
margem de tensão
×
margem temporal
~~~

O diagrama de olho é uma visualização dessa região bidimensional.

## Velocidade de borda e largura de banda relevante

Frequência de clock e taxa de bits não definem sozinhas a largura de banda de integridade de sinal.

Uma transição rápida contém componentes espectrais muito acima da frequência de repetição. Uma escala genérica de primeira ordem é:

~~~text
largura de banda relevante ∝ 1 / tempo_de_subida
~~~

O coeficiente depende do modelo da forma de onda e da definição do tempo de subida; por isso nenhum coeficiente universal é afirmado aqui.

A consequência física é robusta:

~~~text
borda mais rápida
    ↓
mais conteúdo de alta frequência
    ↓
maior sensibilidade a descontinuidades, perdas, crosstalk e radiação
~~~

Reduzir a velocidade da borda pode melhorar a integridade quando os requisitos de slew e temporização do receptor continuam satisfeitos. Bordas lentas demais podem consumir margem temporal ou violar a interface.

## Acoplamento por impedância comum

Dois circuitos podem se acoplar mesmo com trilhas de sinal afastadas.

Se compartilham impedância de retorno Z_s, a corrente do circuito A cria erro de referência visto pelo circuito B:

~~~text
V_erro,B(ω) = Z_s(ω) · I_A(ω)
~~~

Exemplos comuns:

- pinos de terra compartilhados no encapsulamento;
- estreitamentos de plano;
- pinos de retorno de conectores;
- trilhas compartilhadas longas;
- conexões de blindagem;
- caminhos compartilhados da distribuição de potência.

Reduzir a impedância compartilhada ou separar caminhos de corrente reduz esse mecanismo.

## Estratégia de aterramento depende de frequência e geometria

Uma ligação em estrela pode ser útil para impedir que correntes compartilhadas de baixa frequência atravessem uma referência sensível.

Um plano de referência contínuo costuma ser superior em alta frequência porque cria retorno curto, distribuído e de baixa indutância.

Essas regras não são contraditórias. Aplicam-se a regimes físicos diferentes.

O objetivo é:

~~~text
controlar o caminho real da corrente de retorno
e minimizar impedância compartilhada prejudicial
~~~

e não reproduzir um desenho específico de símbolos de terra.

## Impedância de desacoplamento e integridade de sinal

Movimento de alimentação e referência acopla diretamente na qualidade do sinal.

Para um capacitor ideal:

~~~text
Z_C = 1 / (jωC)
~~~

Um capacitor de desacoplamento real pode ser aproximado em uma faixa por:

~~~text
Z_dec(ω)
=
ESR
+
jω·ESL
+
1/(jωC)
~~~

onde ESR é resistência série equivalente e ESL representa indutância série/montagem efetiva.

Abaixo da autorressonância, o termo capacitivo pode dominar. Acima dela, a indutância pode dominar.

Capacitância nominal, portanto, não é suficiente. Posicionamento, geometria de montagem, indutância dos planos e distribuição dos capacitores afetam o laço de corrente.

O próximo capítulo desenvolve diretamente PDN e regulação.

## Equilíbrio diferencial e conversão de modo comum

Para tensões do par:

~~~text
V_diff = V_p - V_n

V_cm = (V_p + V_n) / 2
~~~

Um canal perfeitamente simétrico preserva separação modal.

Assimetrias reais incluem:

- skew do par;
- perdas desiguais;
- vias assimétricas;
- desequilíbrio em conectores;
- estruturas ESD/filtros diferentes;
- mudanças de plano de referência.

Elas podem converter energia:

~~~text
diferencial -> modo comum
modo comum  -> diferencial
~~~

Conversão para modo comum importa porque reduz margem do receptor e pode aumentar emissões mesmo quando a amplitude diferencial nominal parece correta.

## Rejeição de modo comum

Uma relação conceitual de rejeição de modo comum é:

~~~text
CMRR = |A_diff / A_cm|
~~~

frequentemente expressa como:

~~~text
CMRR_dB = 20 log10(CMRR)
~~~

CMRR depende da frequência.

Um receptor pode rejeitar fortemente perturbações de baixa frequência e apresentar desempenho muito pior em alta frequência.

A faixa admissível de tensão de modo comum também é finita. Excursão grande de modo comum pode causar falha mesmo com tensão diferencial adequada.

## Jitter e incerteza temporal

Jitter é a variação do instante de transição em relação a uma referência ideal ou recuperada.

Modelos de medição costumam distinguir:

- jitter determinístico;
- jitter aleatório;
- jitter dependente dos dados;
- jitter periódico;
- distorção de duty cycle.

São modelos de análise, não leis físicas independentes.

No ponto de amostragem, o resultado relevante é quanto da abertura horizontal permanece depois de contabilizar a incerteza temporal.

## Interferência intersimbólica

Um canal de banda limitada possui memória.

A resposta a bits anteriores pode continuar presente durante o símbolo atual:

~~~text
amostra_atual
=
resposta(símbolo atual)
+
Σ resposta residual(símbolos anteriores)
+
ruído
~~~

Isso é interferência intersimbólica (ISI).

Contribuições incluem:

- perdas no dielétrico/condutor;
- reflexões;
- dispersão;
- filtragem;
- equalização insuficiente.

ISI pode deslocar tanto tensão quanto instante de cruzamento do limiar.

## Taxa de erro de bits e evidência

Taxa de erro de bits é:

~~~text
BER = bits_errados / bits_observados
~~~

Um teste sem erros observados não prova BER real igual a zero.

A confiança depende do tempo de observação e do modelo estatístico assumido.

Da mesma forma:

~~~text
um boot bem-sucedido
!=
qualificação do canal físico
~~~

Qualificação elétrica exige o procedimento de medição e conformidade específico da interface.

## Blindagem e retorno de chassi

Blindagem de cabo ou gabinete adiciona outra estrutura condutora que pode carregar corrente de modo comum.

O desempenho da blindagem depende de:

- impedância da ligação;
- geometria do conector;
- continuidade;
- aberturas;
- método de terminação;
- frequência.

Uma conexão longa tipo pigtail pode apresentar indutância suficiente para ser ineficaz em frequências onde uma ligação larga e de baixa indutância funcionaria melhor.

A frase "ligado ao terra" é, portanto, incompleta sem frequência e geometria.

## Integridade de sinal e EMC

Integridade de sinal e compatibilidade eletromagnética são relacionadas, porém distintas.

Integridade de sinal pergunta se o receptor pretendido recebe uma forma de onda válida.

EMC pergunta se o sistema emite e tolera perturbações dentro dos limites exigidos.

Uma borda rápida pode simultaneamente:

- melhorar tempo de transição;
- aumentar sensibilidade a perdas de alta frequência;
- aumentar crosstalk;
- aumentar sensibilidade a reflexão;
- aumentar emissões conduzidas/radiadas.

Bom projeto físico frequentemente melhora ambos, mas conformidade EMC exige o teste regulatório ou de produto aplicável.

## Fronteira entre amostragem e metaestabilidade

Degradação do canal pode colocar a entrada do receptor próxima ao limiar durante a janela de amostragem.

Em lógica síncrona isso consome margem de setup/hold e pode aumentar a chance de um elemento de armazenamento entrar em metaestabilidade.

A cadeia conceitual é:

~~~text
incerteza de tensão/tempo do canal
        ↓
margem de setup/hold
        ↓
elemento de amostragem
        ↓
possível metaestabilidade
        ↓
contenção por sincronizador/sistema
~~~

O comportamento interno de metaestabilidade pertence aos capítulos de lógica sequencial e temporização. Este capítulo fornece as causas do lado do canal.

## Contexto de normas

A BIPM SI Brochure, 9ª edição versão 4.01 revisada em junho de 2026, é a referência metrológica atual para grandezas e unidades SI usadas aqui.

A PCI-SIG lista a PCI Express Base Specification Revision 7.1, datada de 2026-09-17, como a especificação Base aprovada atual. A PCI-SIG descreve essa especificação como incluindo elementos elétricos, de protocolo, arquitetura de plataforma e interface de programação. Essa separação é diretamente relevante: acesso de software ao espaço de configuração não implica propriedade do canal elétrico.

IEEE 802.3-2022 continua sendo uma norma Ethernet IEEE aprovada enquanto projetos ativos de emenda e revisão prosseguem. Ela abrange comportamento MAC, informações de gerenciamento e várias mídias/velocidades de camada física.

Este capítulo usa essas normas somente para estabelecer fronteiras arquiteturais. Orçamentos de insertion loss, máscaras de olho, limites de jitter, equalização do receptor e fixtures de conformidade continuam regidos pela revisão e pelo meio específicos da interface.

## Fronteira de inicialização e fluxo de controle

Não existe rotina de inicialização de integridade de sinal no código revisado do ChrisOS.

O fluxo de software relevante é:

~~~text
chamador solicita valor de configuração PCI
        ↓
bus / slot / function / offset codificados
        ↓
pci_read ou pci_write
        ↓
acesso a porta de E/S x86
        ↓
comportamento da plataforma/controlador
        ↓
enlace físico, se houver hardware real
~~~

Serializador, recuperação de clock/dados, equalizador de lane ou terminação analógica pertencem abaixo da interface atual do software.

## Estado e estruturas de dados

A fonte citada não armazena:

- resposta ao impulso do canal;
- histograma de olho;
- forma de onda amostrada;
- matriz de parâmetros S;
- estado de equalizador;
- perfil de impedância.

Os valores PCI visíveis são estado escalar de transação de software:

~~~text
bus
slot
function
offset
endereço de configuração
valor de configuração
~~~

A invariante é:

~~~text
estado de configuração != estado do canal físico
~~~

## Fronteira de ABI e formato físico

As declarações revisadas do kernel são conceitualmente:

~~~text
pci_read(bus, slot, func, off) -> valor de configuração de 32 bits

pci_write(bus, slot, func, off, value)
~~~

Elas formam uma interface de software para acesso à configuração PCI.

A codificação elétrica de um enlace serial físico é regida pela especificação física/de link, e não por essa API em C.

Da mesma forma, nenhum formato de amostras de forma de onda ou ABI de telemetria de integridade de sinal existe nos arquivos citados do ChrisOS.

## Fronteira de concorrência

As funções revisadas pci_read e pci_write realizam acessos diretos por portas de E/S e não contêm lock internamente.

Este capítulo não infere garantia global de serialização pela ausência de lock local.

Se múltiplas CPUs puderem emitir operações de configuração em paralelo, a documentação do subsistema PCI deve estabelecer o contrato real de ordenação/serialização a partir de evidência explícita de código.

Essa questão de concorrência de software é separada do canal eletromagnético.

## Hierarquia de diagnóstico

Falhas elétricas e falhas de software podem produzir sintomas externos semelhantes.

Uma investigação disciplinada percorre as camadas de evidência:

~~~text
invariante / retorno de software
        ↓
estado do controlador e do enlace
        ↓
contadores ou analisador de protocolo
        ↓
medição elétrica
        ↓
causa em encapsulamento / conector / PCB
~~~

Pular diretamente de um timeout para "problema de integridade de sinal" não é justificado.

## Fronteira física/software

~~~text
requisição do driver
    |
configuração/registrador
    |
controlador e protocolo
    |
PHY
    |
encapsulamento + canal + retorno
    |
receptor
~~~

Somente a parte superior visível por software aparece no PCI atual do ChrisOS revisado aqui.

## Implementação atual do ChrisOS

Na revisão `da3df29cb397932c43d32373871fb9380e688ade`, `kernel/metal/pci.c` constrói um endereço de configuração PCI legado, grava-o em `0xCF8` e transfere 32 bits por `0xCFC`. Logo, `pci_read` e `pci_write` são transações de software na fronteira do mecanismo de configuração.

A fonte varre o barramento 0 para dispositivos selecionados e habilita bits de espaço de E/S e bus master quando aplicável. Ela não configura swing, equalização, terminação, treinamento de lanes, impedância da PCB, perdas de conectores ou planos de referência. A auditoria afirma que nenhuma máquina física foi inicializada naquela passagem e não fornece TDR, osciloscópio, BER ou diagrama de olho.

| Fonte | Evidência |
|---|---|
| `kernel/metal/pci.c` | E/S de configuração e varreduras |
| `kernel/metal/pci.h` | interface PCI exportada |
| `docs/CURRENT_HARDWARE_AUDIT.md` | estado de validação e ausência de prova física |

## Algoritmos, estado, propriedade e complexidade

ChrisOS não possui algoritmo de integridade de sinal nem estado de canal elétrico pertencente ao kernel. O algoritmo adjacente é descoberta PCI limitada: barramento 0, até 32 slots e 8 funções. Enumeração generalizada é O(BSF). Propagação elétrica segue dinâmica distribuída e não possui propriedade de heap ou ordenação de locks no ChrisOS.

A invariante documental é: transação visível por software nunca constitui evidência de conformidade do canal elétrico.

## Falha, recuperação e isolamento

Defeitos elétricos podem aparecer como retries, desaparecimento de dispositivo, timeouts, tráfego corrompido ou link down. Protocolo, firmware, controlador ou driver podem produzir sintomas semelhantes.

~~~text
teste de software
        |
estado do controlador/enlace
        |
contadores/analisador
        |
medição elétrica
        |
causa no canal/placa
~~~

TDR, sondagem de alta largura de banda, análise de olho e BER pertencem à validação física. Software pode repetir ou reiniciar um controlador, mas não repara canal fora da especificação.

## Segurança, desempenho e compromissos

Driver privilegiado deve validar comprimentos, descritores e estados visíveis do dispositivo mesmo presumindo canal confiável; entrada instável pode virar falha do kernel. Isso não substitui conformidade elétrica.

Bordas rápidas reduzem transição, mas ampliam espectro, crosstalk, sensibilidade a reflexões e emissões. Terminação melhora a forma de onda ao custo de potência. Espaçamento e planos contínuos consomem roteamento. Equalização recupera canais com perdas ao custo de complexidade, latência e potência.

## Validação e limitações

Uma plataforma física deve combinar revisão de esquema/layout, verificação de impedância, análise da PDN, simulação quando justificada, medições especificadas, contadores de enlace, testes ambientais e isolamento por software. Nesta revisão, somente as fontes declaradas foram inspecionadas; nenhuma nova medição física foi executada.

ChrisOS não expõe atualmente medição de integridade de sinal, não modela canais de PCB, não executa treinamento de PHY PCIe em software e não fornece conformidade física na auditoria revisada. O PCI atual é E/S de configuração legada mais descoberta selecionada. Este capítulo não alega conformidade elétrica PCI/PCIe.

## Roadmap

Perfis futuros podem associar placa-mãe, estado de enlace, contadores de erro e artefatos medidos a registros reproduzíveis. AER PCIe nativo ou telemetria mais rica melhorariam diagnóstico, mas não substituiriam medição em placa.

## Proveniência da revisão

As alegações foram reconciliadas contra ChrisOS `main` `da3df29cb397932c43d32373871fb9380e688ade`; os arquivos revisados são exatamente os declarados no frontmatter. Teoria e comportamento observado permanecem separados.
