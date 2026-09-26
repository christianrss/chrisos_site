---
id: emulator-theory
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- chrisvm/chris_arch.h
- chrisvm/chrisvm.h
- chrisvm/machine/machine.h
- chrisvm/cpu/emulator/chriscpu.c
- chrisvm/cpu/emulator/mmu.c
- chrisvm/cpu/hv/chrishv.c
- chrisvm/tests/test_chrisvm.c
- chrisvm/Makefile
symbols:
- fetch_insn
- cpu_run
- maybe_irq
- cpu_inject
- chris_translate
- chris_va_read
- chris_va_write
depends_on:
- cpu-datapath-isa
- buses-mmio-dma
- virtual-memory
- clock-timing
related:
- chrisvm-chriscpu
- virtualization-chrishv
---

# Emulação de máquinas: estado arquitetural, passos de instrução e falhas

## O contrato reproduzido

Um emulador funcional reproduz em software o comportamento de uma máquina-alvo visível pelo convidado. O hospedeiro não precisa compartilhar seu conjunto de instruções. Um virtualizador por hardware utiliza recursos de um processador compatível para executar instruções convidadas diretamente, mantendo controle sobre transições privilegiadas e eventos selecionados. Ambos precisam de um modelo de memória e dispositivos. Uma janela gráfica, um carregador ELF ou uma interface de terminal não determinam qual mecanismo existe abaixo deles.

O critério relevante para um interpretador é o comportamento arquitetural: registradores, efeitos na memória, exceções, interações com dispositivos e ordem de execução observável. Reproduzir pipeline, caches e previsão de desvios de um processador comercial é um objetivo microarquitetural ou temporal separado. O contador de passos do ChrisCPU não comprova esse modelo mais forte. A distinção permite reconhecer o valor de um interpretador funcional pequeno sem apresentá-lo como simulador preciso em ciclos.

Este capítulo acompanha `chriscpu.c`, `mmu.c`, o cabeçalho de arquitetura compartilhado e os testes da máquina na revisão declarada. Pressupõe ISA, representação inteira, tradução de endereços e diferença entre E/S mapeada em memória e em portas. Os detalhes de cada opcode pertencem ao capítulo de decodificação; aqui o assunto é a estrutura de transição de estados que dá significado às instruções decodificadas.

## Estado como estrutura de dados explícita

Abstratamente, a execução transforma um estado `S` sob uma instrução e uma entrada de eventos externos. O estado inclui registradores, memória e dispositivos, não apenas o ponteiro da próxima instrução. Uma equação conceitual útil é `step(S, entrada) -> (S', resultado)`. O resultado pode ser continuação, exceção convidada, parada do depurador ou saída da máquina informada ao hospedeiro. A implementação precisa distinguir os casos para não confundir uma falha do convidado com uma falha do programa hospedeiro.

`ChrisArchitectureState` representa os registradores e o estado de controle arquitetural compartilhado. Registradores gerais podem ser acessados pelo array `gpr[16]` ou pelos membros nomeados da união. O objeto CPU também mantém mecanismos de execução, como parada, interrupções pendentes, rastreamento e motivo de saída. Esses campos de implementação não são todos registradores x86 visíveis ao convidado. Separá-los evita tratar uma flag de breakpoint como parte da ABI arquitetural convidada.

A tabela `ChrisCpuBackend` oferece operações de ciclo de vida e execução. O interpretador e o backend de hardware reservado usam a mesma interface. Uma estrutura comum de estado é uma fronteira útil para um backend futuro, mas não comprova que todo esse estado já possa ser importado ou exportado de hardware real de virtualização.

## A busca é uma operação de memória convidada

O interpretador precisa obter bytes de instrução usando o endereço de execução e as regras de acesso atuais do convidado. Desreferenciar o valor numérico do ponteiro de instrução como ponteiro hospedeiro ignoraria a tradução convidada e poderia acessar um endereço inválido. O ChrisCPU usa `chris_va_read` com a classe de acesso de execução ao buscar a partir de `cpu->arch.rip`.

O auxiliar atual `fetch_insn` tenta ler 15 bytes, um por vez, antes de decodificar. Quinze é o limite de comprimento de uma instrução x86, mas uma instrução particular pode ser muito menor. Essa escolha cria um caso importante de revisão: uma instrução curta perto do fim de uma página mapeada pode levar o auxiliar a consultar bytes da página seguinte que a instrução não precisa. Uma estratégia incremental de busca e decodificação pode evitar o acesso desnecessário, mas exige tratar prefixos e codificações incompletas. O código estabelece a leitura antecipada; um teste de fronteira é necessário para caracterizar todos os caminhos de exceção resultantes.

A busca também demonstra por que RAM comum e acesso a dispositivos não são intercambiáveis. O mapa físico pode encaminhar um endereço a um callback de dispositivo. Uma leitura adicional pode ter efeito observável se a região possuir semântica de acesso com efeitos colaterais. O comprimento correto da instrução afeta, portanto, tanto a decodificação quanto o limite das operações de memória realizadas em nome do convidado.

## Decodificação e interpretação de operandos

`chris_decode` converte os bytes buscados em `ChrisInsn`. Um resultado negativo leva o laço a solicitar exceção de opcode inválido por `chris_raise`. A decodificação determina comprimento e forma dos operandos; a execução aplica a semântica. A separação permite isolar erros distintos por testes de bytes e testes de transições de estado.

Em x86, tamanhos de operando e endereço, extensões de registradores e endereçamento de memória podem depender de prefixos e campos da codificação. Um deslocamento não é necessariamente um endereço absoluto; um imediato pode exigir extensão de sinal antes de participar de uma operação mais larga. Um decodificador que produz o mnemônico certo com largura errada ainda pode corromper bits superiores de registradores ou calcular flags incorretas. A documentação precisa identificar representação e largura na fronteira entre decodificação e execução, sem tratar texto de disassembly como certificado de correção.

Flags aritméticas também são saídas arquiteturais. Carry descreve transbordamento sem sinal; overflow descreve a condição de faixa com sinal. Em oito bits, `0xff + 1` produz zero com carry; `0x7f + 1` produz `0x80` com overflow com sinal. Os mesmos bits podem receber interpretações de sinal diferentes, mas o emulador precisa calcular as definições da instrução. Os testes existentes de flags incluem fronteiras correspondentes em 64 bits.

## A ordem concreta em `cpu_run`

A função rejeita CPU nula, limpa a flag de parada e normalmente reinicia o motivo de saída, preservando o caso especial de breakpoint tratado no código. Depois repete enquanto a contagem local está abaixo de `max_steps` e a CPU não está parada. Cada iteração verifica o breakpoint configurado em RIP, busca e decodifica bytes, formata a instrução para diagnóstico, opcionalmente registra uma linha e insere uma entrada no histórico de rastreamento.

Antes de executar, limpa `rip_dirty`. O executor pode marcar uma alteração explícita do ponteiro de instrução. Depois da execução, o laço avança RIP pelo comprimento decodificado apenas quando RIP não foi explicitamente alterado e a CPU não está parada. A convenção impede que um desvio tomado, retorno ou transferência por exceção receba também o incremento de execução sequencial.

Em seguida, `maybe_irq` considera entregar uma interrupção pendente. Finalmente, o laço incrementa `steps`, o `tsc` modelado e seu contador local. Saídas anteriores, como falha de busca ou decodificação, não percorrem o mesmo caminho de contagem. O contador deve ser interpretado segundo esse fluxo, sem ser descrito informalmente como número de todas as instruções arquiteturalmente concluídas. Se o orçamento termina sem parada, o motivo passa a `CHRIS_EXIT_STEP_LIMIT`.

![Ramificações e resultados do interpretador](../../assets/diagrams/interpreter-step.svg)

## Interrupções e um estado pendente limitado

`maybe_irq` trata primeiro `sti_delay`: quando definido, limpa o campo e retorna sem entregar interrupção nessa chamada. Depois rejeita entrega para CPU parada ou sem IRQ pendente e verifica o bit de habilitação em RFLAGS. Quando prossegue, limpa a pendência e chama `chris_raise` com o vetor armazenado. O contrato de adiamento precisa ser analisado junto ao executor que define o campo.

`cpu_inject` armazena uma flag e um vetor pendentes. É uma posição única, não uma fila geral de quantidade arbitrária de interrupções. Injeções repetidas antes do consumo podem substituir o vetor armazenado. Um modelo completo precisa especificar se uma linha permanece ativa, se bordas são retidas, como prioridades são representadas e quando ocorre reconhecimento. A existência de um callback que aceita um vetor não comprova esses contratos mais amplos de controlador de interrupções.

A relação entre parada e chamadas posteriores também é uma política explícita: a próxima chamada de `cpu_run` limpa a flag de parada. Tratar HLT convidado, pausa pelo hospedeiro, desligamento e breakpoint como equivalentes esconderia comportamentos importantes. A enumeração de motivos permite distingui-los, e os testes precisam verificar esses valores além dos resultados em registradores.

## Endereço virtual convidado, físico convidado e armazenamento hospedeiro

Um endereço virtual convidado é traduzido segundo registradores de controle e tabelas do convidado. O endereço físico resultante é resolvido pelo mapa de memória da máquina. O armazenamento hospedeiro implementa RAM ou dispositivos. Esses três espaços não podem ser confundidos mesmo quando um mapa identidade inicial faz dois valores numéricos coincidirem.

`chris_translate` ignora paginação quando o bit correspondente em CR0 está limpo. Com paginação ativa, verifica canonicalidade e percorre quatro níveis com deslocamentos 39, 30, 21 e 12, extraindo índices de nove bits. Cada entrada é lida da memória física convidada. O percurso verifica presença e permissões selecionadas de escrita, usuário e execução, atualiza estados accessed e dirty por escritas e reconhece folhas de páginas grandes nos níveis correspondentes. Isso descreve o modelo de quatro níveis do código, não todos os modos opcionais x86 ou todas as regras de bits reservados.

`chris_va_read` e `chris_va_write` dividem operações em partes limitadas pelas fronteiras de página. Uma solicitação que atravessa duas páginas exige tradução de cada parte. O resultado pode diferir: a primeira pode ser gravável e a seguinte ausente. Efeitos parciais e entrega de falha precisam ser examinados para operações que cruzam a fronteira. A estrutura do wrapper não comprova reversão transacional da instrução inteira.

## Falhas, saídas e precisão

Uma página convidada ausente ou proibida deve ser observável pelo mecanismo de exceção quando o modelo oferece sua entrega. Uma faixa inválida de armazenamento hospedeiro pode provocar saída da máquina. No caminho atual de leitura virtual, endereço não canônico solicita proteção geral; falhas comuns de tradução registram CR2 e solicitam page fault; armazenamento inacessível para tabelas pode definir `CHRIS_EXIT_UNMAPPED` e parar. O código também trata especialmente falhas durante a entrega de outra exceção.

Exceções precisas exigem que o estado visível ao tratador corresponda ao ponto arquitetural da falha. Atualizar um registrador cedo demais, avançar RIP duas vezes ou escrever parte do operando antes de uma falha pode violar o contrato. Algumas instruções possuem semântica explícita de progresso parcial, portanto uma regra universal de “desfazer tudo” também é insuficiente. A unidade correta de revisão é a instrução específica, seus acessos e o comportamento arquitetural de exceção documentado.

Por isso, um teste básico que chega a HLT comprova apenas o caminho exercitado. Não estabelece correção de todos os aninhamentos de exceção, transições de privilégio ou escritas entre páginas. O projeto separa entrega de exceções em um módulo próprio, que deve ser lido junto ao executor na auditoria dessas interações.

## Complexidade e fronteiras de otimização

O laço externo é limitado pelo orçamento, mas o trabalho hospedeiro por iteração não é constante para todas as instruções e estados. A decodificação possui entrada de comprimento limitado. Um percurso de quatro níveis lê até quatro entradas por tradução, além de possíveis atualizações. Repetir tradução para cada um dos 15 bytes antecipados acrescenta trabalho mesmo dentro de uma página. Operações de strings, callbacks, rastreamento e exceções introduzem custos diferentes.

Um cache de instruções decodificadas poderia reduzir trabalho, mas precisa ser invalidado quando bytes de código mudam. Um cache de tradução precisa respeitar mudanças nas tabelas convidadas e semântica de invalidação. Um tradutor dinâmico precisa preservar flags, falhas e fronteiras de instrução mesmo ao combinar operações hospedeiras. Otimizações exigem, portanto, contrato de invalidação e testes de regressão semântica; não são seguras apenas por acelerarem um convidado.

A operação `cpu_tlb` incrementa um campo de geração. Trata-se de um mecanismo na interface do backend. Sua presença não comprova cache de tradução completo, todos os escopos de invalidação ou comportamento equivalente ao TLB físico. A documentação precisa rastrear consumidores reais da geração antes de atribuir uma capacidade mais ampla.

## Fronteira atual da virtualização

O backend `chrishv.c` informa explicitamente que a assistência por hardware não está implementada nesta revisão. A inicialização falha; seu caminho de execução não executa uma máquina virtual. O arquivo reserva uma interface para integração futura com VMX ou SVM e não utiliza KVM. Assim, o ramo ChrisHV no diagrama do ecossistema é uma intenção arquitetural, enquanto ChrisCPU fornece o caminho atual do interpretador.

Implementar esse ramo exigiria execução privilegiada no hospedeiro, verificação de capacidades, gerenciamento de estado físico, entrada e saída do convidado, interrupções, virtualização de memória e liberação de recursos. Uma estrutura compartilhada e um nome de backend resolvem a organização da interface, não esses mecanismos. A documentação não pode transformar sua existência em afirmação de que o desktop ChrisOS já inicializa em um hipervisor de hardware funcional.

## Evidências e validação reproduzível

`chrisvm/tests/test_chrisvm.c` inclui fronteiras de flags, execução aritmética, memória e chamadas, serial e portas, instruções inválidas, page faults, endereços não canônicos, divisão por zero e limite de passos. O Makefile também constrói pequenos convidados aritmético e splash e executa verificações sem janela. São definições concretas de testes; relatar sua execução exige informar também resultado da compilação e revisão.

| Camada de validação | Observação útil | Escopo remanescente |
|---|---|---|
| Auxiliar de flags | Resultado e flags para operandos selecionados | Outras larguras e operações |
| Programa convidado curto | Interação entre decodificação, execução e saída | Famílias não exercitadas |
| Caso de page fault | Exceção e CR2 selecionados | Todas as permissões e entregas aninhadas |
| Splash sem janela | Escritas chegam ao framebuffer modelado | Boot completo do desktop e scanout físico |
| Boot do sistema operacional | Interações entre muitos subsistemas | Conformidade exaustiva da ISA ou temporal |

Os [manuais Intel](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) especificam o alvo arquitetural. O código local especifica o subconjunto implementado. Os testes oferecem evidência do comportamento exercitado. Manter os três papéis separados é necessário para expandir o ChrisCPU sem subestimar sua implementação útil nem exagerar sua compatibilidade.
