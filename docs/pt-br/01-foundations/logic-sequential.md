---
id: logic-sequential
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- chrisvm/cpu/emulator/chriscpu.c
- chrisvm/cpu/common/state.c
symbols:
- cpu_run
- maybe_irq
- chris_arch_reset
depends_on:
  - combinational-logic
related:
- cpu-datapath-isa
---

# Lógica, estado e circuitos sequenciais

## Lógica combinacional

Um circuito combinacional não possui memória intencional: sua saída é função das entradas presentes. Decoders, multiplexadores, comparadores, encoders e unidades aritméticas pertencem a essa classe.

Um full adder de um bit recebe `A`, `B` e carry-in `Cin` e produz soma `S` e carry-out `Cout`:

```text
S    = A XOR B XOR Cin
Cout = (A AND B) OR (Cin AND (A XOR B))
```

A repetição e otimização desse elemento produz adição inteira de várias larguras. Subtração pode ser representada por complemento de dois e reutilizar hardware de soma.

## Multiplexadores e fluxo controlado

Um multiplexador escolhe um valor entre vários conforme bits de controle. CPUs os utilizam para selecionar operandos da ALU, próximo program counter, valores de writeback e vetores de exceção.

Um datapath pode ser entendido como armazenamento de dados, transformação combinacional e roteamento multiplexado.

## Realimentação e estado armazenado

Quando a saída influencia a entrada futura, um circuito pode preservar informação. Portas realimentadas podem produzir bistabilidade: duas configurações estáveis representam um bit.

Latch é sensível a nível. Flip-flop é normalmente modelado como captura na borda de clock. Implementações físicas variam, mas o objetivo arquitetural é controlar a transição de estado em um evento definido.

O agrupamento de elementos forma um **registrador**. Um registrador arquitetural de 64 bits representa conceitualmente 64 bits de estado, embora CPUs de alto desempenho possam renomear e reorganizar o armazenamento físico.

## Sistemas síncronos

Em projeto síncrono, estado muda em eventos de clock enquanto lógica combinacional calcula entre eles.

```text
registradores ──> lógica combinacional ──> registradores
     ▲                                      │
     └────────────── clock ─────────────────┘
```

O maior caminho combinacional relevante limita a frequência máxima junto com setup time, incerteza de clock e margens.

Clock não torna a física intrinsecamente discreta; ele fornece disciplina para coordenar circuitos analógicos com propagação finita.

## Máquinas de estados

Uma máquina de estados combina estado armazenado e lógica de próximo estado:

```text
next_state = F(current_state, input)
output     = G(current_state, input)
```

Unidades de controle, protocolos de barramento e controladores de dispositivos podem ser descritos assim. O mesmo conceito reaparece em drivers, que espelham estados como reset, negotiated, ready, active e failed.

## Matrizes de memória

Registradores são adequados para estado pequeno e muito acessado. Armazenamento maior utiliza células mais densas em matrizes. SRAM aparece tipicamente em caches; DRAM usa células mais densas e exige refresh.

Software vê endereços e bytes, não células individuais. Controladores, caches, coerência e MMUs ficam entre uma instrução e os dispositivos físicos de memória.

## Da máquina de estados ao processador

Um processador precisa repetir conceitualmente:

```text
buscar instrução
      ↓
decodificar operação
      ↓
ler estado necessário
      ↓
executar transformação
      ↓
acessar memória quando necessário
      ↓
gravar resultado arquitetural
      ↓
selecionar próximo endereço
```

Uma CPU simples pode representar esse fluxo diretamente como estados. Um core out-of-order moderno sobrepõe e reordena trabalho internamente, preservando o comportamento exigido pela ISA.

Essa distinção é central para emulação. ChrisCPU não precisa reproduzir pipelines, preditores, caches ou timing de uma CPU comercial; precisa reproduzir o **contrato arquitetural** suficiente para que o guest observe registradores, memória, flags e exceções corretos.

## Estado arquitetural e microarquitetural

Estado arquitetural é visível ao software pela ISA: registradores gerais, RIP, RFLAGS, control registers, MSRs selecionados e memória.

Estado microarquitetural é específico da implementação: reorder buffers, caches de micro-ops, tabelas de predição, registradores físicos e filas internas.

Um sistema operacional é escrito contra estado arquitetural. Desempenho depende fortemente da microarquitetura, mas correção funcional não deve depender de detalhes ocultos salvo quando uma especificação de plataforma os expõe.

## Um contrato completo de transição

As equações de F e G tornam-se úteis somente após definir o evento de observação. Considere um controlador didático com entradas de requisição, conclusão e erro, amostradas na mesma borda de subida. Ele aceita no máximo uma operação, emite uma indicação de início por um ciclo e mantém uma indicação de conclusão até que o solicitante libere a requisição. Esse exemplo é um controlador abstrato especificado, não uma afirmação de que o ChrisOS contém exatamente esse circuito.

São utilizados quatro estados: IDLE, ISSUE, WAIT e DONE. Reset seleciona IDLE e limpa o resultado de erro capturado. ISSUE avança incondicionalmente para WAIT. Em WAIT, erro tem prioridade sobre conclusão; ambos encerram a operação e levam a DONE. DONE permanece até requisição ficar baixa. O resultado de erro é armazenado ao sair de WAIT, porque uma entrada transitória de erro deve continuar reportável após desaparecer.

| Estado atual | Condição amostrada | Próximo estado | Saída derivada do estado |
|---|---|---|---|
| IDLE | Sem requisição | IDLE | Pronto |
| IDLE | Com requisição | ISSUE | Pronto antes da transição |
| ISSUE | Qualquer | WAIT | Iniciar |
| WAIT | Sem erro nem conclusão | WAIT | Ocupado |
| WAIT | Erro | DONE, armazena falha | Ocupado antes da transição |
| WAIT | Conclusão sem erro | DONE, armazena sucesso | Ocupado antes da transição |
| DONE | Requisição mantida | DONE | Conclusão mantida |
| DONE | Requisição ausente | IDLE | Conclusão antes da transição |

A tabela torna uma limitação importante visível: um pulso de conclusão durante ISSUE é ignorado. O ambiente deve garantir que a conclusão permaneça disponível em WAIT, ou o controlador deve ser reprojetado para amostrá-la também em ISSUE. Ocultar esse caso atrás de uma seta “executar” esconderia uma lacuna de protocolo. Uma máquina de estados só é correta em relação às suas hipóteses de entrada.

![Transições do controlador e retenção da conclusão](../../assets/diagrams/sequential-controller.svg)

## Saídas Moore e Mealy

No exemplo, iniciar depende apenas de estar em ISSUE e concluir depende apenas de estar em DONE. São saídas do tipo Moore. Uma saída Mealy de início poderia depender de IDLE AND requisição, permitindo resposta no intervalo combinacional atual. Isso reduz um ciclo de latência da interface, mas introduz um caminho de entrada até saída. Encadear esses caminhos entre módulos pode criar um caminho temporal longo ou um laço combinacional se sinais ready e valid dependerem um do outro sem armazenamento.

Moore não significa ausência de glitches por definição. Vários bits de estado codificado podem mudar com atrasos distintos e sua decodificação combinacional pode produzir uma saída transitória indesejada. Uma saída registrada tem contrato temporal diferente de uma decodificação combinacional arbitrária de registrador. Mealy não significa incorreto: exige descrição precisa de estabilidade da entrada, propagação e amostragem. A distinção útil é onde as entradas atuais participam da função de saída.

A indicação de início dura um intervalo de estado, não um instante infinitesimal. Um receptor no mesmo clock pode amostrá-la sob o contrato temporal especificado. Um receptor em outro clock precisa de protocolo de travessia. Um diagrama não pode transformar silenciosamente um pulso de um ciclo em um evento assíncrono observado de forma confiável.

## Codificação, alcançabilidade e recuperação

Quatro estados exigem pelo menos dois bits de codificação. A codificação binária minimiza essa quantidade, enquanto one-hot utiliza um bit por estado e pode simplificar algumas decodificações. One-hot não é inerentemente mais seguro: padrões sem nenhum bit ativo ou com vários ativos são inválidos e exigem uma política. Codificações binárias também podem ter combinações não utilizadas quando a quantidade de estados não é potência de dois. Recuperação pode selecionar reset, registrar erro ou interromper novas operações, conforme as consequências de perder o estado da transação.

A análise de alcançabilidade começa no reset e segue todas as transições permitidas. Uma codificação inalcançável só pode ser tratada como don't-care de síntese sob as hipóteses relevantes do projeto; não se torna impossível simplesmente porque o software normal não a solicita. Injeção de falhas, reset incompleto e entradas assíncronas podem invalidar essas hipóteses. Um controlador seguro deve considerar se um estado ilegal poderia habilitar acidentalmente uma ação privilegiada.

Dois invariantes do controlador didático são a ocorrência de no máximo um intervalo de início antes de DONE e a manutenção da conclusão até a liberação da requisição. Uma propriedade de progresso é que uma requisição aceita finalmente chega a DONE se o ambiente fornecer conclusão ou erro. A condição ambiental é indispensável: a tabela isolada não garante saída de WAIT. Segurança afirma que um evento proibido nunca ocorre; vivacidade afirma que um evento exigido finalmente ocorre sob hipóteses declaradas.

## Estado antigo e próximo estado devem permanecer separados

Uma transição síncrona avalia F a partir do estado antigo e das entradas amostradas, depois efetiva o estado resultante. Em um modelo de software, atribuições sequenciais podem usar valores recém-escritos quando deveriam usar os antigos. Uma troca simultânea exige `next_a = old_b` e `next_b = old_a`; executar `a = b; b = a` perde o valor original de a. Armazenamento temporário de próximo estado ou uma ordenação equivalente cuidadosamente demonstrada faz parte da correção.

O mesmo problema aparece em contadores com condições terminais. Testar a contagem antes de incrementar pode emitir um pulso em evento diferente de incrementar antes do teste. Ambos são algoritmos válidos se o contrato os especificar, mas não são intercambiáveis. Um diagrama deve indicar se a condição usa contagem atual, próxima contagem calculada ou entrada amostrada independentemente.

A simulação de software também precisa definir a granularidade da transição. Um passo do emulador pode representar uma instrução arquitetural inteira enquanto o hardware utiliza muitos ciclos internos. A equivalência deve comparar as fronteiras de observação escolhidas, não exigir que cada variável hospedeira corresponda a um flip-flop físico. Por outro lado, a abstração de instrução precisa preservar exceções e efeitos de memória arquiteturalmente visíveis.

## A fronteira real do laço do ChrisCPU

`cpu_run` fornece um exemplo concreto de progressão explícita. Antes de executar, limpa `rip_dirty`. Após `chris_execute`, incrementa RIP pelo tamanho decodificado apenas quando `rip_dirty` é falso e a CPU não está parada. Uma instrução que redirecione o controle deve comunicar esse fato ao laço. Sem a condição, um destino de salto tomado poderia receber um incremento adicional incorreto pelo tamanho da instrução.

O laço verifica breakpoints antes da busca. Falhas de busca e de decodificação podem sair antes da execução. Após o caminho de execução, considera interrupções e incrementa contadores de software. Essas posições importam: definem quais observações compartilham a fronteira de um passo e quais falhas saem antes dela. A implementação não é uma atribuição atômica de um objeto completo de próximo estado. Sua correção depende da ordem e dos contratos das rotinas chamadas.

`maybe_irq` primeiro consome `sti_delay` e retorna quando ele está ativo. Caso contrário, impede entrega quando a CPU está parada, não há interrupção pendente ou a flag de habilitação está limpa. Somente após essas condições limpa a marca pendente e chama `chris_raise`. Esse é um predicado de controle sobre estado armazenado. Não demonstra modelagem de fio de interrupção, sincronizador analógico ou temporização física do controlador.

## Inicialização, concorrência e evidência

O exemplo também separa validade do resultado e valor do resultado. Um bit de sucesso armazenado em IDLE não significa que uma operação acabou de concluir; somente DONE torna esse bit significativo para o receptor. O padrão impede interpretar dados antigos como um novo evento. Limpar todos os bytes da carga é desnecessário quando a validade é imposta corretamente, mas manter validade ativa durante reset pode expor resultados antigos. Em interfaces de sistema operacional, a obrigação análoga é distinguir objeto alocado, objeto inicializado e objeto publicado, mesmo quando os três ocupam o mesmo endereço.

`chris_arch_reset` limpa a estrutura arquitetural e define os valores iniciais explícitos de flags e CR0. O reset do backend possui responsabilidades adicionais fora dessa estrutura. Um diagrama da máquina inteira deve incluir dispositivos, eventos pendentes e propriedade da memória, em vez de equiparar reset arquitetural à construção de todos os objetos. Da mesma forma, a ordem sequencial de uma thread hospedeira não autoriza acesso concorrente irrestrito por outras threads.

Para um circuito, a verificação compararia transições, reset e temporização das saídas às hipóteses de entrada. Para o código discutido, a evidência é a inspeção de `cpu_run`, `maybe_irq` e `chris_arch_reset` na revisão registrada. Não se afirma uma prova formal do emulador completo. Um teste de integração significativo deve distinguir avanço linear de RIP, transferência explícita de controle, falha de busca ou decodificação e adiamento de interrupção; tratar todos como um resultado indiferenciado “a CPU executou” esconderia o contrato de estado.
