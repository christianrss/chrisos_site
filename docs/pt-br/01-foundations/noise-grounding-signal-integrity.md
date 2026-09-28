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
  - docs/CURRENT_HARDWARE_AUDIT.md
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
V_L=Lrac{di}{dt}
]

explica por que pequena indutância compartilhada gera tensão transitória. Para impedância de retorno (Z_g),

[
V_{shift}(omega)=Z_g(omega)sum_k I_k(omega).
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
i_C=C_mrac{dV_a}{dt},qquad V_M=Mrac{dI_a}{dt}.
]

Bordas mais rápidas aumentam ambos os termos. A largura de banda relevante depende fortemente dos tempos de subida e descida, não apenas da taxa de bits. Crosstalk exato em PCB exige parâmetros derivados da geometria ou medidos; código de driver não os fornece.

## Reflexões, temporização e olho

Para impedância característica (Z_0) e carga (Z_L),

[
Gamma_L=rac{Z_L-Z_0}{Z_L+Z_0}.
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
Delta Vapprox L_sNrac{Delta I}{Delta t}.
]

Indutâncias de encapsulamento e distribuição importam mesmo com correntes individuais modestas. Desacoplamento fornece carga local, limitado por ESR, ESL, posicionamento e impedância dos planos.

Para o par,

[
V_d=V_p-V_n,qquad V_{cm}=rac{V_p+V_n}{2}.
]

Receptores reais têm rejeição de modo comum finita. Skew, perdas desiguais, vias assimétricas e descontinuidades de retorno convertem energia diferencial em modo comum; casamento preserva equilíbrio e temporização.

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
