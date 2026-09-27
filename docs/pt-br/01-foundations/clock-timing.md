---
id: clock-timing
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- kernel/metal/pit.c
- chrisvm/cpu/emulator/chriscpu.c
symbols:
- pit_init
- pit_irq
- pit_ticks
- cpu_run
depends_on:
  - latches-flipflops
  - rc-rlc-transients
  - transistor-cmos
related:
- cpu-datapath-isa
- timers
- emulator-theory
---

# Clock, atraso de propagação e o significado de tempo

## O estado exige um contrato temporal

Um circuito combinacional calcula saídas a partir das entradas presentes. Um circuito sequencial também contém estado armazenado. Quando existe realimentação, afirmar que “este fio vale um” é insuficiente sem especificar o instante da observação e seu intervalo de validade. Uma tensão demora para atravessar redes de transistores e interconexões; um elemento de armazenamento não distingue com confiabilidade todas as transições possíveis em instantes arbitrariamente próximos. A disciplina síncrona organiza a computação entre eventos de amostragem definidos, permitindo que uma máquina de estados finitos seja uma abstração útil do sistema físico contínuo.

Este capítulo pressupõe chaveamento CMOS, funções booleanas e a distinção entre lógica combinacional e estado armazenado. Desenvolve a temporização independentemente da implementação de um processador comercial específico. O ChrisOS não define o circuito de transistores de um processador x86. Sua ligação com esses fundamentos ocorre por meio de garantias arquiteturais, temporizadores e do modelo explícito de passos do ChrisCPU. Temporização física, frequência de interrupções, escalonamento de software e contagem de instruções emuladas precisam permanecer grandezas distintas.

## Atrasos de propagação e de contaminação

Para um bloco combinacional cuja entrada muda no instante zero, O atraso de contaminação é um limite inferior para quando sua saída pode começar a mudar. O atraso de propagação é um limite superior para quando ela estará estabilizada no valor correto, sob condições de operação e hipóteses de transição especificadas. Entre esses limites, a saída pode estar antiga, transitória ou temporariamente incorreta. Caminhos múltiplos podem produzir pulsos espúrios mesmo quando os valores booleanos inicial e final são iguais.

Esses limites descrevem riscos diferentes. O atraso máximo determina se a próxima amostragem ocorre cedo demais para o novo resultado. O atraso mínimo determina se o dado novo chega tão rapidamente que corrompe um valor ainda em captura. Otimizar um circuito apenas para reduzir o maior atraso pode, portanto, introduzir um problema de atraso mínimo em outro ponto. Nenhum limite é um número universal associado ao símbolo de uma porta: tensão, temperatura, variação de fabricação, capacitância da carga e inclinação da entrada influenciam seu valor.

Um modelo RC de primeira ordem explica a importância da carga. Carregar uma capacitância por uma resistência efetiva produz uma aproximação exponencial à tensão final. A constante de tempo `R*C` fornece uma escala útil, não um atraso exato para qualquer rede de transistores. Limiares lógicos selecionam um ponto da trajetória; fanout e fios longos acrescentam capacitância e resistência. Uma expressão C não contém um capacitor explícito, mas o hardware que a implementa continua sujeito a esses efeitos.

## Armazenamento por borda e janela de amostragem

Um registrador acionado por borda captura um valor lógico próximo à borda ativa do clock e produz a saída correspondente após um atraso clock-to-Q. Para captura confiável, sua entrada precisa permanecer estável durante um intervalo de setup antes da borda e um intervalo de hold depois dela. São restrições físicas do elemento receptor. Não correspondem a instruções adicionais executadas pelo processador.

| Parâmetro | Significado | Papel na análise |
|---|---|---|
| `t_cq,max` | Instante mais tardio da saída válida após o clock de lançamento | Restrição do caminho máximo |
| `t_cq,min` | Primeira mudança possível após o clock de lançamento | Restrição do caminho mínimo |
| `t_pd,max` | Instante mais tardio do resultado combinacional estabilizado | Análise de setup |
| `t_cd,min` | Primeira mudança possível da saída combinacional | Análise de hold |
| `t_setup` | Estabilidade exigida antes da captura | Análise de setup |
| `t_hold` | Estabilidade exigida depois da captura | Análise de hold |

Um latch é sensível a nível: enquanto habilitado, sua saída pode acompanhar a entrada após um atraso. Um flip-flop amostra em uma borda. Tratar um latch como flip-flop pode permitir, por acidente, a propagação por vários estágios na mesma fase de clock. Projetos com latches exploram deliberadamente esse comportamento e exigem análise das fases correspondentes. As equações deste capítulo utilizam registradores por borda, não esse modelo mais geral.

## Derivação da desigualdade de setup

Considere um registrador de lançamento e outro de captura, separados por lógica combinacional. A borda de lançamento ocorre no instante zero e a próxima borda de captura em `T+s`, em que `T` é o período e `s` é o instante de chegada do clock de captura menos o de lançamento. Um `s` positivo significa que o clock de captura chega mais tarde. A chegada mais tardia do dado ocorre em `t_cq,max + t_pd,max`. Para preservar o intervalo de setup:

```text
t_cq,max + t_pd,max + t_setup <= T + s
T >= t_cq,max + t_pd,max + t_setup - s
```

Em um exemplo didático, suponha clock-to-Q de 80 ps, atraso lógico de 600 ps, setup de 70 ps e skew de -30 ps. O período mínimo é 780 ps, antes de adicionar margens de incerteza. Isso corresponde a aproximadamente 1,282 GHz como frequência máxima desse modelo específico. Não é uma especificação da máquina ChrisOS nem de um produto real. O exemplo demonstra como um orçamento de atrasos se transforma em restrição do período.

Jitter e incerteza na chegada do clock reduzem a margem confiável. Uma análise prática utiliza piores condições, modelos de variação e incerteza explícita, em vez de uma única forma de onda ideal. Uma folga de setup negativa identifica uma restrição violada. Observar saída correta em uma simulação de condições típicas não comprova folga positiva em todos os extremos de operação.

## Derivação da desigualdade de hold

O novo dado, em sua chegada mais precoce, não pode perturbar o valor capturado na borda atual. Com a mesma convenção de skew, a borda atual de captura ocorre em `s`. A condição necessária é:

```text
t_cq,min + t_cd,min >= s + t_hold
```

Aumentar o período não corrige diretamente essa desigualdade: ela compara eventos associados à mesma fronteira de ciclo. Acrescentar atraso apropriado ao caminho curto pode corrigir hold, mas também piorar setup. Nessa convenção, skew positivo ajuda setup e prejudica hold. Informar um valor de skew sem definir a convenção de sinal favorece conclusões incorretas.

Suponha clock-to-Q mínimo de 25 ps, atraso lógico mínimo de 15 ps, skew de captura de 30 ps e hold de 20 ps. O dado novo pode chegar após 40 ps, mas deveria permanecer inalterado até 50 ps. Existe uma violação de hold de 10 ps. Reduzir a frequência mantém esses tempos próximos à borda inalterados. Por isso, “diminuir a frequência” não é uma solução universal para falhas de temporização digital.

![Restrições de setup e hold](../../assets/diagrams/clock-window.svg)

## Metastabilidade e travessia entre domínios de clock

Se a entrada muda dentro da janela sensível de amostragem, um elemento de armazenamento pode entrar em estado analógico metastável. Sua saída pode demorar excepcionalmente para resolver em um nível lógico válido. O circuito receptor não pode pressupor qual valor será selecionado, e um modelo digital sem atrasos não representa integralmente o fenômeno. Metastabilidade não é um terceiro valor booleano comum que uma aplicação pode consultar em uma condição.

Um sinal externo assíncrono não tem relação de fase garantida com o clock de destino. Um sincronizador comum de um bit o amostra por uma sequência de registradores, oferecendo tempo adicional de resolução antes do consumo. Isso reduz a probabilidade de falha; não garante matematicamente sua impossibilidade. O modelo qualitativo usual faz a confiabilidade melhorar fortemente com o tempo de resolução e piorar com o aumento das taxas de amostragem e transição. Uma estimativa real de tempo médio entre falhas exige parâmetros específicos do dispositivo.

Vários bits relacionados não podem, em geral, ser sincronizados independentemente e depois considerados uma palavra coerente. Bits diferentes podem ser observados em atualizações distintas da origem. Um handshake pode manter a carga útil estável até a confirmação; FIFOs assíncronas podem utilizar codificações de ponteiros e lógica de travessia cuidadosamente restringidas. São projetos de interfaces, não aplicações intercambiáveis do recurso de dois registradores. No ChrisOS, conclusão visível pelo software e propriedade de descritores operam acima desses contratos de hardware; uma barreira de compilador não é um sincronizador físico.

## Frequência, latência e vazão

O período limita o tempo disponível a um estágio. Latência mede o tempo entre a aceitação de uma operação e seu resultado. Vazão mede a frequência com que operações podem ser concluídas em uma carga sustentada. Um pipeline pode aceitar uma operação por ciclo enquanto cada operação leva vários ciclos para atravessá-lo. Aumentar sua profundidade pode melhorar o limite de frequência, mas acrescentar custo de registradores e aumentar latência ou penalidades de recuperação de desvios.

Uma instrução não equivale necessariamente a um ciclo. Implementações podem sobrepor instruções independentes, esperar por dependências ou memória, executar micro-operações internas e concluir trabalho segundo as regras arquiteturais. Contar comandos do código-fonte, instruções Assembly ou passos de um interpretador não permite convertê-los diretamente em segundos sem um modelo definido. Até instruções com o mesmo efeito arquitetural podem ter tempos muito diferentes entre máquinas.

Medições de software acrescentam perguntas: qual relógio foi consultado, se sua taxa é invariável, quais interrupções ocorreram, se o código medido foi eliminado pelo otimizador e se a memória estava aquecida. Um benchmark exige procedimento controlado e condições informadas. A contagem teórica de operações é valiosa, mas mede outra propriedade.

## Configuração do PIT no ChrisOS: divisão não é tempo exato

`kernel/metal/pit.c` define `PIT_INPUT_HZ` como 1.193.182. `pit_init` rejeita frequência zero, calcula o divisor inteiro por `PIT_INPUT_HZ / frequency_hz` e rejeita divisores fora de 1 a 65.535. Zera `ticks`, instala `pit_irq` na IRQ zero, escreve `0x36` na porta `0x43`, escreve os bytes baixo e alto do divisor em `0x40` e desmascara a IRQ zero pela interface do PIC.

A divisão inteira trunca. Para uma solicitação de 60 Hz, o divisor é 19.886 e a frequência nominal gerada é aproximadamente 60,0001006 Hz. O período nominal é cerca de 16,66664 ms. Esses valores são derivados da constante e do modelo divisor, não de medições de entrega de interrupções. A palavra de controle seleciona canal zero, acesso por byte baixo e alto, contagem binária e modo três. Configura um periférico temporizador, não o clock de execução de instruções do processador.

| Grandeza | Valor para a solicitação de 60 Hz | Significado |
|---|---:|---|
| Taxa de entrada definida no código | 1.193.182 Hz | Modelo de entrada do divisor |
| Divisor inteiro | 19.886 | Contagem programada |
| Saída nominal | Aproximadamente 60,0001006 Hz | Taxa de entrada dividida pela contagem |
| Incremento de `ticks` | Um por execução do tratador | Evento entregue ao software |

O tratador incrementa `ticks` e chama `proc_on_tick`. `pit_ticks` retorna o contador. O qualificador `volatile` informa ao compilador requisitos observáveis dos acessos; não estabelece um protocolo completo de sincronização entre processadores nem converte o contador em tempo de parede calibrado. Mascaramento, latência de entrega e comportamento de atendimento separam eventos de hardware das execuções observadas do tratador. O trabalho fixo local por tick inclui uma chamada à lógica do escalonador, cujo custo exige análise própria.

## Os passos do ChrisCPU são um orçamento de execução

`chrisvm/cpu/emulator/chriscpu.c` fornece um laço `cpu_run` limitado por `max_steps` e pelo estado de parada. A implementação mantém `cpu->steps` conforme a execução progride. Isso permite ao executor limitar o trabalho do convidado e cria uma progressão observável em nível de instrução. Não significa que cada passo representa um ciclo medido da CPU hospedeira ou um ciclo físico do convidado.

Um emulador preciso em ciclos precisaria de um modelo temporal adicional para comportamento de instruções e interações relevantes de microarquitetura e dispositivos. Um interpretador funcional é útil sem esse modelo: pode validar transições de estado arquitetural e executar código convidado. Replay determinístico também exigiria controle das entradas externas e da entrega de temporizadores, não apenas um orçamento fixo de instruções. Os conceitos temporais atuais precisam, portanto, ser separados de qualquer futura alegação de precisão de ciclos.

## Limites de validação e referências

Temporização de circuitos é validada contra o circuito e seus modelos físicos; comportamento de interrupções é validado contra a plataforma e seu caminho de entrega; orçamentos do emulador são validados contra a máquina de estados do interpretador. Inicializar o PIT com sucesso não valida o setup do processador. Um teste de decodificação aprovado não estabelece precisão temporal. São classes de evidência diferentes, apesar do vocabulário compartilhado de ciclos e ticks.

As desigualdades trabalhadas usam valores artificiais declarados, permitindo recomputação direta. O cálculo do PIT é reproduzível por divisão inteira e posterior divisão da taxa de entrada pelo divisor obtido. A verificação em execução precisa observar também roteamento de IRQ, mascaramento e callback do escalonador. O capítulo não afirma ter realizado medição temporal física ou execução de convidado.

Material didático primário sobre circuitos síncronos e sincronização está na [coleção de aulas MIT 6.004](https://ocw.mit.edu/courses/6-004-computation-structures-spring-2009/pages/lecture-notes/). O comportamento arquitetural visível ao processador é especificado separadamente nos [manuais de arquitetura Intel](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html). Essas referências correspondem a camadas distintas de autoridade; nenhuma substitui a leitura do código ChrisOS na revisão registrada.
