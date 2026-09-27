---
id: latches-flipflops
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- chrisvm/cpu/common/state.c
- chrisvm/chris_arch.h
symbols:
- chris_arch_reset
- ChrisArchitectureState
depends_on:
  - logic-sequential
  - transistor-cmos
related:
- logic-sequential
- clock-timing
- registers-counters
- sram-dram
---

# Latches, flip-flops e metaestabilidade

## De uma função booleana a uma memória física

Uma função combinacional relaciona as entradas atuais a uma saída após um intervalo de propagação. Ela não distingue dois históricos que terminem com as mesmas entradas. Armazenamento exige estado interno cujo futuro dependa do valor anterior. Realimentação positiva fornece essa dependência: dois estágios inversores conectados em laço apresentam configurações estáveis nas quais um nó está alto e o outro baixo. O bit armazenado é uma condição física mantida, não um símbolo independente de tensão, capacitância e alimentação.

Este capítulo pressupõe o inversor CMOS e portas booleanas básicas. Desenvolve mecanismos de armazenamento antes de utilizar registradores como objetos arquiteturais. O ChrisOS não contém uma célula de latch fabricada nem uma simulação de transistores do processador. A conexão direta com o software é o estado representado em `ChrisArchitectureState` e inicializado por `chris_arch_reset`. A teoria física explica as condições e os limites da abstração; não deve ser confundida com a estrutura C que implementa o estado do emulador.

Dois inversores acoplados também admitem um equilíbrio instável próximo à região de comutação. Uma pequena perturbação afastando o circuito desse equilíbrio pode ser amplificada até alcançar um estado estável. Assim, a afirmação booleana ideal “o bit é zero ou um” omite uma possibilidade transitória fisicamente importante. Essa omissão é aceitável somente quando temporização e interfaces tornam suficientemente improvável observar um estado ainda não resolvido.

## O latch SR ativo em nível alto

Um latch SR construído com portas NOR acopladas possui entrada de set S e de reset R. Uma notação consistente é Q = NOT(R OR Qbar) e Qbar = NOT(S OR Q). As equações incluem realimentação; não definem uma ordem acíclica de avaliação. Com S = R = 0, os dois estados complementares estáveis satisfazem as equações e o estado anterior é preservado.

| S | R | Q após estabilização | Significado |
|---|---|---|---|
| 0 | 0 | Q anterior | Manutenção |
| 1 | 0 | 1 | Set |
| 0 | 1 | 0 | Reset |
| 1 | 1 | 0, com Qbar também 0 | Condição proibida da representação complementar |

Quando ambas as entradas são ativadas, as duas saídas NOR são forçadas para baixo. O problema não é a impossibilidade dessas tensões; é a violação da representação complementar e a ausência de uma definição de qual estado válido deve vencer quando as duas entradas forem liberadas juntas. Diferenças de atraso e ruído analógico influenciam o resultado. Uma tabela digital não resolve uma corrida declarando instantânea a liberação simultânea.

Uma implementação NAND normalmente utiliza entradas ativas em nível baixo e, portanto, outra tabela. Transplantar a tabela NOR para o circuito NAND inverte seu contrato operacional. Nomes como reset_n ou uma barra superior carregam informação real de polaridade. A interface deve especificar o nível ativo e as combinações permitidas; a expressão “latch set/reset” isoladamente é insuficiente.

## Controlar dados em vez de expor set e reset

Um latch D impede que a interface normal de dados solicite set e reset simultaneamente. Em um projeto ideal ativo em nível alto, S = E AND D e R = E AND NOT(D), sendo E a habilitação. Quando E está baixo, ambas as entradas ficam inativas e o estado é mantido. Quando E está alto, o latch fica transparente: após o atraso de propagação, Q acompanha D. Transparente é a palavra central, pois várias mudanças de entrada podem atravessar o intervalo aberto.

A equação Q_next = E D OR NOT(E) Q resume o comportamento estabilizado. Não inclui atrasos dos caminhos complementares de D nem substitui a caracterização temporal da célula. O circuito real precisa funcionar adequadamente perto do fechamento. Sua implementação pode usar portas de transmissão e inversores regenerativos em vez de uma rede literal de símbolos AND e NOR separados.

| Intervalo de habilitação | Comportamento da entrada | Contrato observável |
|---|---|---|
| Fechado | D muda | Q mantém o valor anterior |
| Aberto | D estabiliza | Q acompanha após propagação |
| Fronteira de fechamento | D estável no intervalo exigido | Novo valor é retido |
| Fronteira de fechamento | D muda perto demais do fechamento | Captura não é garantida |

## Construção de armazenamento sensível à borda

Uma organização mestre-escravo coloca dois latches em sequência, com fases abertas complementares. Para um dispositivo de borda de subida, o mestre pode ficar aberto durante o nível baixo do clock e fechar na subida; o escravo abre durante o nível alto. O mestre deixa de acompanhar D antes que o escravo apresente o valor capturado. Idealmente, o estado externamente visível muda na fronteira de subida, embora o circuito interno utilize intervalos, não um evento fisicamente sem duração.

A inversão e a distribuição reais do clock têm atraso. Se os dois latches ficarem transparentes durante uma sobreposição indesejada, os dados podem atravessar ambos. Se houver tempo morto excessivo, o desempenho temporal muda. Por isso, conectar diagramas arbitrários de latches não equivale a selecionar uma célula de flip-flop caracterizada. Existem outras implementações sensíveis à borda; essa construção é um modelo explicativo, não uma afirmação sobre um processador específico.

![Armazenamento, temporização e sincronização](../../assets/diagrams/storage-contract.svg)

Um banco de elementos sensíveis à borda pode atualizar vários bits na mesma fronteira de clock. “Na mesma fronteira” continua sendo uma abstração: skew de clock e atraso de saída variam entre os elementos. A lógica seguinte deve tolerar essas diferenças dentro do orçamento temporal. A correção multibit vem do contrato completo dos caminhos, não da suposição de que todas as saídas físicas mudam exatamente juntas.

## Setup, hold e propagação são requisitos diferentes

Setup exige estabilidade da entrada antes do evento de captura. Hold exige que ela permaneça estável depois. O atraso clock-to-Q descreve o intervalo entre captura e saída válida sob condições especificadas. Esses números dependem de célula, tensão, temperatura, carga e transição de entrada. Não existe um setup universal pertencente ao conceito de flip-flop.

Entre um registrador de lançamento e outro de captura, o atraso máximo do caminho determina se o dado chega cedo o bastante para a próxima captura. O atraso mínimo determina se o novo dado chega cedo demais após a captura atual. Reduzir a frequência pode corrigir algumas violações de atraso máximo, mas não corrige automaticamente hold, pois este se refere à mesma fronteira de captura. As equações separadas e a convenção de sinal de skew são desenvolvidas em [Clock e temporização](clock-timing.md).

Adicionar lógica pode melhorar hold e piorar setup. Uma mudança na árvore de clock pode alterar ambos. A análise estática de temporização precisa, portanto, de caminhos mínimos e máximos, não apenas da maior cadeia combinacional. Uma simulação booleana funcional com bordas ideais pode passar enquanto o circuito físico permanece inseguro. O circuito e seu ambiente temporal estabelecem a correção conjuntamente.

## Metaestabilidade é falha de resolução no tempo necessário

Uma transição próxima à captura pode deixar o elemento perto do equilíbrio instável. A saída pode finalmente resolver para zero ou um, mas o tempo de resolução não fica limitado pela garantia nominal de clock-to-Q. O perigo é um consumidor observar tensão inválida ou consumidores diferentes interpretarem a transição de formas distintas. Metaestabilidade não é um terceiro estado lógico útil ao software aplicativo.

Um modelo de engenharia relaciona o tempo médio entre falhas observáveis de sincronização ao tempo de resolução disponível T_res: MTBF é proporcional a exp(T_res / tau), dividido pelo produto da frequência de amostragem do destino pela frequência de transições assíncronas. A constante tau e o prefator dependem do dispositivo e devem vir de caracterização. O modelo explica por que tempo adicional reduz muito o risco; não fornece garantia numérica de confiabilidade sem dados tecnológicos e ambientais.

Um sinal assíncrono não consegue, em geral, prometer setup e hold em relação a um clock independente. Um sincronizador contém esse risco. O primeiro flip-flop amostra o sinal; o seguinte oferece tempo de resolução ao primeiro antes do uso funcional. O roteamento entre os estágios deve preservar tempo suficiente. Lógica intermediária consome esse orçamento. O primeiro estágio não deve alimentar consumidores funcionais que contornem a fronteira de contenção.

## Dois estágios não resolvem toda travessia de domínio

Um nível estável de um bit é o caso simples usual. O destino pode observá-lo após um número variável de ciclos perto da fronteira de amostragem. O protocolo deve tolerar essa latência. Um pulso menor que o intervalo de amostragem do destino pode ser completamente perdido mesmo sem propagação de metaestabilidade. Alongar o pulso, alternar um bit por evento ou utilizar requisição e confirmação resolve captura de eventos sob restrições próprias de taxa e responsabilidade.

Sincronizar independentemente cada bit de uma palavra binária variável não garante uma palavra coerente. Na passagem de `0111` para `1000`, bits diferentes podem ser capturados em instantes diferentes. Um contador Gray muda um bit por contagem adjacente e pode ajudar em travessias de ponteiros cuidadosamente restritas, mas não torna barramentos arbitrários seguros. Os protocolos de origem e destino continuam exigindo hipóteses sobre taxa, skew e interpretação.

Para uma carga multibit, um handshake pode manter os dados estáveis enquanto a requisição é sincronizada. O receptor captura a carga e devolve confirmação; o emissor não a sobrescreve até a confirmação estabelecer a transferência. Uma FIFO assíncrona estende a ideia para taxas independentes com armazenamento e propriedade separada dos ponteiros. A mera existência de células de memória não estabelece nenhum desses protocolos. Ordenação de memória, travessia de domínios e locks são problemas relacionados de coordenação, mas usam mecanismos distintos.

## Reset é uma transição com temporização própria

Um reset síncrono é amostrado na fronteira de clock e precisa de clock ativo para produzir efeito. Um reset assíncrono pode forçar estado independentemente do clock, ajudando a estabelecer uma condição segura com clocks parados. Liberá-lo perto de uma borda pode violar recovery ou removal, restrições análogas a setup e hold. Projetos frequentemente sincronizam a desativação em cada domínio e permitem ativação assíncrona; isso é um padrão de projeto, não uma propriedade automática do fio de reset.

Reset também tem escopo lógico. Um sistema pode reinicializar o controle sem limpar todas as matrizes de dados, desde que bits de validade impeçam acesso aos valores antigos. Por outro lado, reinicializar um produtor enquanto o consumidor conserva números de sequência antigos pode violar o protocolo. O invariante relevante é quais estados e relações de propriedade tornam-se válidos após reset, não se todas as células físicas contêm zero.

No código inspecionado, `chris_arch_reset` zera a estrutura arquitetural recebida, coloca `rflags` em 2 e ativa PE e NE em CR0. Essa é uma política explícita de inicialização por software. Não descreve tensões de energização, circuitos sincronizadores de reset ou todos os campos de ciclo de vida do objeto de CPU que contém a estrutura. Afirmar algo sobre o reset completo da máquina exigiria também examinar os caminhos de backend e dispositivos.

## Relação entre teoria de armazenamento e modelo de software

| Camada | Representação de estado | Origem da validade |
|---|---|---|
| Latch físico | Tensões de nós regenerativos | Faixa elétrica e temporização |
| Registrador síncrono | Conjunto de bits amostrados | Temporização dos caminhos, clock e reset |
| Registrador da ISA | Palavra arquitetural visível | Semântica de instruções e exceções |
| Estado do ChrisCPU | Campos C de `ChrisArchitectureState` | Inicialização e regras do executor |

Escrever um campo C não simula realimentação, metaestabilidade ou propagação de clock. Implementa uma transição no nível de abstração escolhido. Da mesma forma, declarar `volatile` não criaria um sincronizador nem tornaria atômica uma atualização composta. Entradas físicas assíncronas chegam ao software por interfaces de dispositivos e arquitetura; o driver deve segui-las, em vez de tentar reparar temporização analógica com leituras comuns.

No hardware, a potência de armazenamento inclui distribuição de clock, comutação interna e fuga. Habilitações podem evitar atualizações desnecessárias de dados, enquanto células apropriadas de clock gating suprimem atividade de clock. Aplicar AND arbitrariamente entre clock e um sinal mutável controlado por software pode gerar pulsos estreitos e bordas extras. Nenhuma dessas otimizações físicas é demonstrada pela definição de estado do ChrisCPU inspecionada.

## Fronteiras de verificação e aprofundamento

Verificar tabelas verdade estabelece o comportamento estabilizado de SR e D nas combinações permitidas. Simulação temporal e análise estática tratam restrições dos caminhos. A confiabilidade de metaestabilidade exige caracterização analógica e revisão das travessias de domínio. Essas verificações respondem a perguntas diferentes; uma compilação de software bem-sucedida não substitui nenhuma delas.

Neste capítulo, a inspeção do código estabelece os valores de reset citados e a separação entre estrutura arquitetural e armazenamento físico. Não se afirma ter fabricado uma célula, executado simulação analógica ou medido MTBF. As [notas do MIT 6.004](https://ocw.mit.edu/courses/6-004-computation-structures-spring-2009/pages/lecture-notes/) incluem material primário sobre armazenamento e sincronização para aprofundamento. O próximo passo conceitual é reunir bits armazenados em registradores, contadores e transições de estado explicitamente definidas.
