---
id: power-delivery-regulation
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/acpi.c
  - kernel/metal/acpi.h
  - docs/CURRENT_HARDWARE_AUDIT.md
  - docs/REAL_HARDWARE_PLAN.md
symbols:
  - acpi_probe
depends_on:
  - noise-grounding-signal-integrity
  - ac-signals-frequency-impedance
  - rc-rlc-transients
related:
  - cmos-switching-power
  - clock-timing
  - acpi-platform
  - installation-real-hardware
---

# Entrega de potência, regulação e desacoplamento

<div class="abstract">
Um sistema digital requer alimentação estável apenas no sentido lógico; fisicamente, cada evento de chaveamento demanda corrente variável através de uma rede de distribuição com resistência, indutância, capacitância e largura de banda de regulação finitas. Integridade de potência é o problema de manter alimentação e referência dentro dos limites elétricos desde a fonte externa e o laço do regulador até transitórios de encapsulamento e die. Este capítulo desenvolve regulação, conversores, transitórios de carga, impedância-alvo, desacoplamento, ESR/ESL, anti-ressonância, load line, sequenciamento, proteção, eficiência, medição e compromissos térmicos. Em seguida, reconcilia a fronteira de software: a descoberta ACPI atual do ChrisOS pode reportar assinaturas de tabelas selecionadas, mas não implementa controle de VRM da placa-mãe, política completa de estados de energia ACPI, suspend/resume nem um subsistema de telemetria de rails.
</div>

## Pré-requisitos e escopo

Este capítulo pressupõe:

- tensão, corrente, resistência, energia e potência;
- capacitores e indutores;
- transitórios RC/RL/RLC;
- impedância CA e resposta em frequência;
- fundamentos de ruído, aterramento e integridade de sinal;
- terminologia básica de laços de controle.

O caminho físico é maior do que um único regulador:

~~~text
fonte externa
    ↓
fonte / adaptador
    ↓
conversão na placa
    ↓
módulo regulador de tensão
    ↓
planos e vias
    ↓
encapsulamento
    ↓
distribuição no die
    ↓
transistores e lógica
~~~

Cada estágio adiciona impedância e limites dinâmicos.

Entrega de potência e gerenciamento de energia por software são relacionados, mas distintos. Software pode solicitar estados ou alterar carga; ele não elimina a dinâmica elétrica da PDN.

## Desvio de tensão no rail

Para uma corrente de carga i(t) passando por impedância de alimentação não nula Z_PDN,

~~~text
ΔV(ω) = Z_PDN(ω) · ΔI(ω)
~~~

Essa é a relação central de pequenos sinais em integridade de potência.

Um rail permanece dentro da especificação apenas quando o produto entre perturbação de corrente e impedância da rede fica dentro do desvio admissível.

A PDN depende da frequência porque:

- resistência domina certas perdas de baixa frequência;
- o controle do regulador atua em largura de banda finita;
- capacitores dominam faixas selecionadas;
- indutâncias parasitas dominam em frequências suficientemente altas;
- encapsulamento e die adicionam ressonâncias.

Uma única resistência CC não caracteriza a qualidade do rail.

## Droop admissível e impedância-alvo

Suponha desvio máximo permitido ΔV_allowed para um degrau de corrente ΔI_step.

Um critério de primeira ordem comum é:

~~~text
Z_target = ΔV_allowed / ΔI_step
~~~

Exemplo:

~~~text
rail nominal       = 1,0 V
desvio permitido   = 30 mV
degrau de corrente = 20 A

Z_target
=
0,030 / 20
=
1,5 mΩ
~~~

O objetivo é manter a impedância relevante da PDN abaixo do alvo na faixa de frequência que contribui para o transitório de carga.

O critério é útil, porém não suficiente sozinho. Forma de onda de carga, dinâmica do regulador, rede do encapsulamento/die e ponto de medição importam.

## Transitório de carga no tempo

Um aumento abrupto de corrente produz componentes de tensão de primeira ordem:

~~~text
resistivo:
    ΔV_R = ΔI · R

indutivo:
    ΔV_L = L · dI/dt

capacitivo:
    ΔV_C = (1/C) ∫ i_deficit(t) dt
~~~

Os três mecanismos atuam juntos.

Uma sequência simplificada:

~~~text
corrente da carga aumenta
      ↓
capacitores locais respondem primeiro
      ↓
indutância de placa/encapsulamento produz queda L·di/dt
      ↓
capacitância bulk fornece energia intermediária
      ↓
laço do regulador aumenta corrente entregue
      ↓
rail retorna ao ponto regulado
~~~

Nenhum capacitor isolado cobre eficientemente todas as escalas de tempo.

## Regulação

Um regulador compara um sinal relacionado à saída com uma referência e ajusta o estágio de potência para reduzir o erro.

Conceitualmente:

~~~text
referência
   ↓
amplificador de erro / controlador
   ↓
estágio de potência
   ↓
rede LC/saída
   ↓
carga
   └──────── realimentação ────────↑
~~~

O laço possui largura de banda, atraso e margem de estabilidade finitos.

O regulador não responde instantaneamente a mudanças arbitrariamente rápidas.

Energia para transitórios rápidos precisa estar armazenada perto da carga.

## Regulação linear

Um regulador linear controla continuamente um elemento de passagem.

Um limite de eficiência aproximado para regulador linear idealizado é:

~~~text
η ≈ V_out / V_in
~~~

quando a corrente de carga domina a corrente quiescente.

A potência dissipada é aproximadamente:

~~~text
P_loss ≈ (V_in - V_out) · I_load
~~~

Vantagens podem incluir simplicidade e baixo ruído.

A desvantagem é dissipação elevada para grande diferença de tensão ou corrente.

Por isso rails de núcleo/CPU de alta corrente costumam depender de conversão chaveada, não de regulação linear com grande queda.

## Regulação chaveada

Um regulador chaveado transfere energia por estados de comutação e armazenamento reativo.

Topologias incluem:

- buck;
- boost;
- famílias buck-boost;
- conversores multifásicos;
- topologias isoladas a montante.

Para um buck ideal em condução contínua:

~~~text
V_out ≈ D · V_in
~~~

onde D é o duty cycle.

A corrente do indutor muda segundo:

~~~text
di_L/dt = V_L / L
~~~

Durante o intervalo high-side:

~~~text
V_L,on ≈ V_in - V_out
~~~

Durante o intervalo low-side:

~~~text
V_L,off ≈ -V_out
~~~

Em regime periódico, o balanço de volt-segundos exige tensão média aproximadamente nula no indutor por período.

## Ripple de corrente no buck

Para período T_s e duty D:

~~~text
ΔI_L,on
=
(V_in - V_out) · D · T_s / L
~~~

O intervalo de queda deve devolver a corrente do indutor ao mesmo estado periódico em regime.

Frequência de chaveamento maior pode reduzir L necessário para um ripple especificado, porém aumenta perdas de chaveamento e pode piorar EMI.

L maior reduz ripple, mas pode desacelerar resposta transitória e aumentar volume.

## Ripple no capacitor de saída

O capacitor conduz a diferença entre corrente do indutor e da carga:

~~~text
i_C = i_L - i_load
~~~

A tensão segue:

~~~text
dv/dt = i_C / C
~~~

Para ripple triangular de corrente, a capacitância ideal produz ripple correspondente de tensão.

Capacitor real adiciona contribuição de ESR:

~~~text
ΔV_ESR ≈ ΔI_C · ESR
~~~

e efeitos indutivos de borda por ESL/interconexão.

## Regulação multifásica

Rails de alta corrente frequentemente usam fases intercaladas.

Com N fases deslocadas no tempo, correntes de ripple podem se cancelar parcialmente na saída.

Benefícios potenciais:

- menor ripple efetivo;
- distribuição térmica;
- maior corrente total;
- indutores menores por fase;
- melhor resposta transitória.

Custos:

- controlador mais complexo;
- balanceamento de corrente;
- mais nós de chaveamento;
- layout mais complexo.

O cancelamento depende de duty cycle, número de fases e ponto operacional.

## Realimentação e estabilidade

Um laço pode ser representado por função de transferência em malha aberta L(s).

Estabilidade depende do ganho e da fase perto do crossover.

Conceitos úteis:

- frequência de crossover;
- margem de fase;
- margem de ganho;
- polos e zeros;
- ressonância do filtro de saída;
- rede de compensação.

Laço rápido ajuda em transitórios, mas não pode ser arbitrariamente rápido: atrasos, frequência de chaveamento, amostragem e ressonâncias limitam largura de banda estável.

Compensação ruim pode produzir ringing ou instabilidade mesmo com ponto CC correto.

## Bandas de frequência da PDN

Uma hierarquia conceitual é:

~~~text
frequência muito baixa:
    fonte externa e balanço médio de potência

baixa/intermediária:
    laço do VRM e capacitância bulk

mais alta:
    desacoplamento da placa

ainda mais alta:
    encapsulamento

mais alta:
    estruturas no die
~~~

As fronteiras se sobrepõem e dependem da plataforma.

A PDN deve ser analisada como uma única rede de impedância, não como valores isolados de capacitores.

## Modelo do capacitor de desacoplamento

Capacitor ideal:

~~~text
Z_C = 1/(jωC)
~~~

Capacitor real mais montagem:

~~~text
Z(ω)
=
ESR
+
jω·ESL
+
1/(jωC)
~~~

A autorressonância do modelo RLC série ocorre aproximadamente quando:

~~~text
ω_0 = 1 / sqrt(ESL · C)
~~~

ou

~~~text
f_0 = 1 / (2π sqrt(ESL · C))
~~~

Abaixo da ressonância predomina comportamento capacitivo.

Acima, predomina comportamento indutivo.

## Posicionamento e indutância de conexão

Um capacitor conectado por trilhas/vias longas adiciona indutância.

No transitório rápido, o laço relevante é:

~~~text
capacitor
   ↓
caminho de alimentação
   ↓
carga
   ↓
retorno
   ↓
capacitor
~~~

Laço físico pequeno reduz indutância.

Um capacitor grande distante pode armazenar muita energia e ainda assim ser ineficiente para transitório muito rápido por causa da indutância de conexão.

## Hierarquia de capacitância

PDNs costumam usar capacitância em várias escalas:

| Escala | Função principal |
|---|---|
| bulk/fonte | suporte de energia mais lento |
| placa próximo do regulador/carga | transitórios intermediários |
| encapsulamento | suporte local de alta frequência |
| die | frequências ainda maiores |

É uma hierarquia conceitual, não prescrição universal.

Valores dependem da impedância-alvo, modelo de pacote, regulador e espectro de carga.

## Anti-ressonância

Combinar capacitores de valores e parasitas diferentes pode criar picos de anti-ressonância.

Mecanismo simplificado:

~~~text
um ramo parece indutivo
outro ramo parece capacitivo
        ↓
ressonância paralela
        ↓
pico de impedância
~~~

Adicionar mais capacitores pode piorar a PDN em determinadas frequências se a rede não for analisada.

ESR, amortecimento intencional, perdas dos planos e diversidade de componentes alteram a magnitude do pico.

## Indutância de planos e vias

Planos de alimentação e terra formam estrutura distribuída.

Corrente atravessando vias e se espalhando pelos planos produz indutância parasita.

Em alta frequência, um único L escalar costuma ser insuficiente porque a corrente é distribuída.

O princípio local permanece:

~~~text
laço menor
e
conexão mais curta/larga e de baixa indutância
    ↓
menor impedância de alta frequência
~~~

Isso conecta diretamente power integrity ao capítulo de aterramento e signal integrity.

## Load line e droop intencional

Nem todo regulador tenta manter tensão exatamente constante em todas as correntes.

Comportamento load line pode definir:

~~~text
V_target(I)
=
V_no_load
-
R_loadline · I
~~~

Esse droop controlado pode criar margem para overshoot/undershoot e gerenciar guard bands.

A política exata é específica da plataforma/processador.

Nenhum valor de load line é atribuído ao hardware do ChrisOS aqui.

## Remote sensing

Um regulador pode medir tensão perto da carga em vez de nos próprios terminais.

~~~text
saída do regulador
   ↓ resistência dos planos/cabos
ponto de sense na carga
   ↑ realimentação
~~~

Remote sense compensa quedas CC e de frequência intermediária.

Ele não elimina indutância local de alta frequência.

O caminho de sense também precisa ser roteado/filtrado conforme o projeto.

## Medição de corrente

Reguladores podem medir/inferir corrente por:

- resistor shunt;
- DCR do indutor;
- amplificador de corrente;
- telemetria integrada no power stage;
- sensor magnético.

A informação pode servir para:

- limitação;
- balanceamento de fases;
- telemetria;
- load line;
- proteção.

Precisão depende de temperatura, banda, calibração e topologia.

## Sequenciamento de energia

Muitos sistemas exigem rails subindo e descendo em ordem definida.

Motivos:

- limites absolutos dos dispositivos;
- reset;
- evitar back-power por I/O;
- inicialização de PLL/referências;
- dependências entre memória/controlador.

Sequência simplificada:

~~~text
entrada válida
   ↓
rail de standby
   ↓
conversão principal habilitada
   ↓
rail entra na janela power-good
   ↓
reset liberado
   ↓
processador começa a executar
~~~

Sequenciamento é contrato de hardware/firmware.

O kernel começa depois que grande parte do sequenciamento já ocorreu.

## Power-good e reset

Power-good indica que a fonte está dentro de uma janela operacional definida pela plataforma.

Não significa ripple zero nem desempenho transitório perfeito.

Reset pode manter lógica inativa até que rails/clocks sejam aceitáveis.

Brownout pode reassertar reset ou proteção quando tensão cai abaixo do limite.

Implementação exata é específica da plataforma.

## Fonte a montante

Plataformas desktop podem receber rails de uma fonte da família ATX antes que VRMs locais gerem tensões de CPU, memória e dispositivos.

O guia público Intel ATX12VO, datado de 2024-05-01, lista diretrizes ATX12V revisão 3.1.

Esse é um exemplo de contrato de fonte de plataforma, não requisito universal do ChrisOS.

O alvo x86-64 do ChrisOS não justifica assumir uma única topologia de fonte.

## USB Power Delivery como outra camada

USB Power Delivery negocia energia no conector/protocolo antes de reguladores locais converterem a entrada.

A biblioteca USB-IF lista USB Power Delivery Specification Revision 3.2 Version 1.2 datada de 2026-09-14.

Exemplo arquitetural:

~~~text
contrato negociado da fonte
        ↓
tensão/corrente no conector
        ↓
conversão na placa
        ↓
rails locais regulados
~~~

Um contrato negociado não substitui o projeto da PDN local.

## Eficiência

Eficiência do conversor:

~~~text
η = P_out / P_in
~~~

Perdas podem incluir:

- condução dos MOSFETs;
- chaveamento;
- gate drive;
- cobre/núcleo do indutor;
- ESR de capacitores;
- controlador/corrente quiescente;
- condução na PCB.

Em carga alta, perdas de condução podem dominar.

Em carga leve, perdas fixas de controle/chaveamento ficam relativamente importantes.

O power stage pode mudar de modo para otimizar a faixa.

## Acoplamento térmico

Perda elétrica vira calor.

Para potência P_loss e resistência térmica efetiva θ:

~~~text
ΔT ≈ P_loss · θ
~~~

como modelo de primeira ordem em regime.

Sistemas reais têm vários caminhos térmicos, capacitância térmica, fluxo de ar e parâmetros elétricos dependentes da temperatura.

Temperatura maior pode elevar resistência e alterar semicondutores, acoplando comportamento térmico e elétrico.

## Proteção

Mecanismos comuns:

- OCP — sobrecorrente;
- OVP — sobretensão;
- UVLO — bloqueio por subtensão;
- OTP — sobretemperatura;
- proteção de curto;
- soft start;
- limitação de corrente.

Limiares e tempos são específicos do regulador/plataforma.

Um evento de proteção pode aparecer para software como reset, desligamento ou perda de dispositivo, mas o sintoma não identifica a causa física sozinho.

## Brownout e integridade de dados

Tensão insuficiente pode violar temporização antes de o sistema aparentemente desligar.

Consequências possíveis:

- reset de CPU;
- corrupção de memória;
- falha de controlador de armazenamento;
- escritas incompletas;
- perda de dispositivo.

Filesystem e storage precisam considerar perda abrupta de energia salvo se hardware garantir hold-up e software participar de protocolo definido.

Isso não é afirmação de atomicidade power-fail do ChrisFS atual.

## Medição

Medições úteis:

- tensão CC;
- resposta a degrau de carga;
- ripple/ruído no osciloscópio;
- impedância versus frequência;
- nó de chaveamento;
- forma de onda de corrente;
- temperatura;
- telemetria quando disponível.

A qualidade depende da técnica de probe.

Um fio longo de terra no osciloscópio adiciona indutância e pode mostrar ringing parcialmente criado pelo laço de medição.

Para ripple de pequena amplitude e alta frequência, sondagem de baixa indutância é essencial.

## Medição de impedância em frequência

Pode-se excitar a PDN com pequeno sinal conhecido e medir a resposta:

~~~text
Z(ω) = V_response(ω) / I_excitation(ω)
~~~

O método prático depende de frequência, ponto operacional e instrumento.

A excitação não deve levar o regulador para fora da região de pequenos sinais quando se usa interpretação linear.

## Hierarquia de modelos

Análise de potência pode usar:

- redes RLC ideais;
- modelos SPICE de regulador;
- modelos de laço;
- modelos distribuídos de plano;
- modelos de encapsulamento;
- modelos de transistor.

O modelo precisa corresponder à pergunta.

Capacitor ideal não é adequado para prever comportamento de pacote em GHz.

Solver 3D pode ser desnecessário para estimar load line CC.

## Contexto de normas

A BIPM SI Brochure versão 4.01 revisada em junho de 2026 é referência metrológica para as unidades usadas.

O UEFI Forum lista ACPI Specification Version 6.6, lançada em maio de 2025, como a versão ACPI mais recente. ACPI cobre gerenciamento de energia de sistema, dispositivo e processador entre suas áreas funcionais. É uma interface de gerenciamento OS/firmware, não especificação elétrica de VRM.

O guia público Intel ATX12VO datado de 2024-05-01 inclui diretrizes ATX12V revisão 3.1.

A USB-IF lista USB Power Delivery Specification Revision 3.2 Version 1.2 datada de 2026-09-14.

Essas normas ilustram camadas diferentes:

~~~text
ACPI       -> interface OS/firmware de energia
família ATX -> contrato da fonte da plataforma
USB PD     -> contrato negociado no conector
PDN/VRM    -> conversão/distribuição elétrica local
~~~

As camadas não devem ser fundidas.

## Fronteira arquitetural atual do ChrisOS

O código atual revisado contém:

~~~text
kernel/metal/acpi.c
kernel/metal/acpi.h
~~~

com símbolo exportado:

~~~text
acpi_probe
~~~

A implementação percorre regiões do mapa de memória de boot buscando a assinatura RSDP da ACPI.

Para ACPI revisão 2 ou superior, obtém endereço da XSDT, verifica assinatura e percorre um conjunto limitado de ponteiros de tabela.

O código imprime assinaturas selecionadas quando encontra:

~~~text
APIC
MCFG
FACP
~~~

Isso é descoberta/log.

Não é um interpretador ACPI completo nem implementação de power management.

## Limites da evidência da implementação ACPI atual

O acpi_probe citado não mostra:

- parser/execução de AML;
- transições globais de sleep;
- controle de P-states;
- controle de C-states;
- gerenciamento de bateria;
- política térmica;
- telemetria de rails;
- programação de VRM;
- controle do laço do regulador.

A busca de código no repositório na revisão analisada também não encontrou o símbolo _S5.

Esse resultado é evidência de apoio, não prova absoluta sobre qualquer mecanismo fora do escopo revisado.

## Fronteira da auditoria

docs/CURRENT_HARDWARE_AUDIT.md classifica RSDP, MADT e MCFG como EXPERIMENTAL e afirma que nenhuma máquina física foi inicializada naquela auditoria.

Logo a evidência atual não estabelece:

- estabilidade física dos rails;
- resposta transitória de VRM;
- power states ACPI em hardware;
- controle térmico da plataforma;
- comportamento de bateria.

Esses itens requerem implementação e hardware separados.

## Fronteira do plano de hardware real

docs/REAL_HARDWARE_PLAN.md coloca suspend e resume fora de escopo para um projeto posterior.

O plano exige ACPI para o perfil pretendido, mas requisito planejado não é evidência de implementação atual.

~~~text
power management ACPI planejado
!=
power management ACPI implementado
~~~

## Sequência de inicialização atual

O caminho atual de acpi_probe é orientado à descoberta:

~~~text
kernel recebe boot information
        ↓
acpi_probe
        ↓
varre região buscando RSDP
        ↓
lê ponteiro XSDT
        ↓
inspeciona assinaturas
        ↓
imprime assinaturas selecionadas na serial
~~~

Não existe sequência de inicialização de regulador no código citado.

ChrisOS não ajusta compensação, load line ou desacoplamento físico da placa nesse caminho.

## Estado e estruturas de dados

acpi_probe usa variáveis locais para:

- iteração do mapa de memória;
- base/comprimento/tipo;
- endereços RSDP/XSDT;
- ponteiros de tabela;
- strings temporárias de assinatura.

Nenhuma estrutura persistente de PDN é definida nos arquivos citados.

Não há estrutura atual para:

- tensão de rail;
- corrente de rail;
- estado das fases;
- impedância da PDN;
- inventário de capacitores;
- histórico de telemetria.

## Algoritmos e complexidade

O código ACPI atual varre regiões elegíveis em passos de 16 bytes na região legada:

~~~text
0xE0000 .. 0x100000
~~~

e depois percorre entradas da XSDT com limites explícitos no código.

É trabalho de descoberta limitado.

Não possui relação com algoritmos de controle de conversor.

Um regulador real pode executar controle periódico em hardware/firmware na frequência de controle/chaveamento. ChrisOS não implementa esse algoritmo na fonte citada.

## Propriedade de memória

A sondagem ACPI lê tabelas físicas descritas pelo firmware através do mapeamento físico/virtual fornecido pelo boot information.

Ela não aloca nem possui buffers de controle de regulador.

O header citado expõe apenas:

~~~text
void acpi_probe(void);
~~~

Não existe ABI de telemetria de energia nesses arquivos.

## Concorrência

A função atual é uma rotina de probe com estado local.

Não aparecem locks ou sincronização multicore para power management porque esse subsistema não está implementado nesses arquivos.

Código futuro precisaria contratos explícitos para:

- coordenação entre CPUs;
- eventos/interrupções;
- ordenação de suspend de dispositivos;
- registradores compartilhados;
- timeouts e recuperação.

Esses contratos devem ser documentados apenas depois de existir fonte correspondente.

## ABI e fronteira firmware

ACPI é um contrato firmware/OS descrito pela especificação ACPI.

ChrisOS atual inspeciona somente parte limitada da hierarquia de tabelas.

Não estabelece uma ABI geral de interpretador AML.

Rails físicos estão abaixo dessa camada.

~~~text
objeto/estado ACPI
!=
estado elétrico do VRM
~~~

salvo quando uma interface específica expõe a relação e ChrisOS a implementa.

## Falha e recuperação

Falhas de power delivery incluem:

| Falha | Resultado físico possível |
|---|---|
| resistência CC excessiva | droop e aquecimento |
| indutância excessiva | droop/overshoot rápido |
| capacitância insuficiente | transitório intermediário maior |
| anti-ressonância | pico estreito de impedância |
| laço instável | oscilação/ringing no rail |
| OCP | desligamento/reset |
| UVLO/brownout | reset ou mau funcionamento |
| superaquecimento | throttling/proteção/desligamento |
| sequenciamento incorreto | falha de startup |

O sintoma de software não é específico.

Um reset não prova problema no VRM.

## Segurança e privilégio

Equações de regulador não possuem nível de privilégio.

Interfaces de power management podem possuir.

Se ChrisOS futuramente puder:

- solicitar sleep;
- alterar performance state;
- controlar energia de plataforma;
- escrever registradores de gerenciamento;

o acesso deverá ser privilegiado e validado porque transições incorretas podem corromper estado ou causar negação de serviço.

Nenhuma interface generalizada dessas é afirmada como existente no código citado.

## Compromissos de desempenho

Power delivery limita desempenho porque margem de tensão, capacidade de corrente e temperatura restringem atividade.

| Escolha | Benefício | Custo |
|---|---|---|
| frequência maior de chaveamento | L/C menores, resposta rápida | perdas, EMI |
| mais capacitância | menor impedância em certas bandas | área, custo, anti-ressonância |
| ESR menor | menor queda resistiva | menos amortecimento possível |
| load line mais forte | headroom transitório | tensão menor em carga |
| mais fases | compartilhamento/ripple | custo e complexidade |
| laço mais rápido | recuperação | estabilidade/ruído |
| condutores maiores | menor R/L | área/material |

Nenhuma variável deve ser otimizada isoladamente.

## Evidência de validação deste capítulo

O checker determinístico verifica:

~~~text
impedância-alvo:
    Ztarget = ΔVallowed / ΔI

droop resistivo:
    ΔV = I·R

droop indutivo:
    ΔV = L·di/dt

transitório do capacitor:
    ΔV = ΔQ/C

relação buck ideal:
    Vout = D·Vin

ripple do indutor:
    ΔI = (Vin-Vout)·D·Ts/L

autorressonância:
    f0 = 1/(2πsqrt(ESL·C))

load line:
    Vtarget = V0 - Rloadline·I

eficiência:
    η = Pout/Pin
~~~

O checker também valida âncoras atuais de acpi_probe, descoberta RSDP/XSDT, logging APIC/MCFG/FACP e fronteiras de evidência do plano/auditoria.

Esses testes não são medições elétricas de uma placa-mãe.

## Limitações atuais

Este capítulo não fornece:

- stack-up específico de placa;
- rede de compensação de VRM real;
- valores de load line de fornecedor de CPU;
- impedância PDN medida;
- capturas de osciloscópio;
- modelo térmico de uma máquina ChrisOS;
- interpretador AML;
- suspend/resume;
- gerenciamento de bateria;
- telemetria de energia.

Esses itens exigem implementação ou hardware ausente na evidência atual.

## Fronteira do roadmap

A progressão dos fundamentos agora alcança dispositivos semicondutores e lógica digital:

~~~text
circuitos e campos
      ↓
transitórios e impedância CA
      ↓
linhas de transmissão
      ↓
integridade de sinal
      ↓
entrega de potência e regulação
      ↓
eletrostática de dispositivos semicondutores
      ↓
chaveamento CMOS e temporização digital
~~~

Documentação futura de power management do ChrisOS deve ser dirigida pela implementação e citar fontes concretas de ACPI/firmware/controlador quando existirem.

## Proveniência da revisão

Revisado contra o main do ChrisOS na revisão da3df29cb397932c43d32373871fb9380e688ade.

As afirmações de implementação foram conciliadas diretamente contra:

- kernel/metal/acpi.c;
- kernel/metal/acpi.h;
- docs/CURRENT_HARDWARE_AUDIT.md;
- docs/REAL_HARDWARE_PLAN.md.

O símbolo concreto acpi_probe foi inspecionado. O comportamento atual descrito aqui se limita à descoberta/log ACPI estabelecida por esses arquivos.

O contexto externo foi verificado contra BIPM SI Brochure 4.01, UEFI Forum ACPI 6.6, guia público ATX12VO da Intel e biblioteca atual da USB-IF para USB Power Delivery. Limites específicos de produto não são generalizados.
