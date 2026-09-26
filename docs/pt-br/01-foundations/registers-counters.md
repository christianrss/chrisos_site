---
id: registers-counters
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- chrisvm/chris_arch.h
- chrisvm/cpu/emulator/operands.c
- chrisvm/cpu/emulator/chriscpu.c
- kernel/gfx/virtq.c
- kernel/gfx/virtq.h
symbols:
- ChrisArchitectureState
- chris_read_gpr
- chris_write_gpr
- cpu_run
- virtq_publish
- virtq_take
- Virtq
depends_on:
- latches-flipflops
- arithmetic-circuits
- logic-sequential
related:
- clock-timing
- data-representation-layout
- emulator-theory
---

# Registradores, contadores e transições de estado

## Uma palavra armazenada exige um contrato de atualização

Um registrador reúne bits armazenados em uma palavra. Sua definição útil inclui largura, valor de reset, habilitação de escrita, evento de atualização e regras de observação. Um registrador de 64 bits não é apenas um conjunto de sessenta e quatro bits independentes: o circuito ou a semântica das instruções determina quando a palavra pode mudar e quais consumidores podem observá-la. Bancos de registradores acrescentam seleção por endereço e portas de acesso; nomes arquiteturais acrescentam significado visível ao software sobre o armazenamento físico utilizado.

Para um registrador síncrono com dado D, habilitação E e estado atual Q, a equação usual é Q_next = E ? D : Q. Um multiplexador seleciona dado novo ou realimentação antes dos elementos de armazenamento. Se reset tem prioridade, a equação torna-se reset ? initial : (E ? D : Q). Inverter essa prioridade altera o comportamento quando reset e habilitação estão ativos juntos. Um esquema que omite esse caso deixa parte da máquina indefinida.

Habilitação é diferente de clock. Em um projeto com clock enable, o clock pode continuar alternando enquanto a seleção de dados mantém Q. Clock gating apropriado suprime atividade por uma célula projetada para evitar pulsos espúrios. Substituir a habilitação por uma porta combinacional arbitrária no clock pode criar eventos extras de captura. Uma escrita C modela a transição desejada, mas não reproduz nenhum desses circuitos físicos.

## Bancos de registradores e acessos simultâneos

Um banco de N registradores com largura w armazena Nw bits de dados antes de considerar decodificação, portas e proteção. Uma leitura selecionada pode ser representada por um multiplexador entre palavras. Uma escrita combina decodificador de endereço e habilitação por registrador. Portas adicionais aumentam interconexão e seleção, frequentemente com custo maior que alguns bits extras de armazenamento. Área e atraso exatos dependem da organização das células.

Ler e escrever o mesmo endereço no mesmo ciclo exige uma regra: a leitura pode retornar o dado antigo, o novo por encaminhamento ou um valor não especificado em uma colisão proibida. Duas escritas no mesmo registrador exigem prioridade ou rejeição. Um pipeline não deduz essas regras da expressão “banco de registradores”. Redes de encaminhamento e detecção de dependências impõem o contrato escolhido quando instruções se sobrepõem.

Nomes arquiteturais não precisam corresponder permanentemente a células físicas. Renomeação pode atribuir um novo destino físico a cada instrução, preservando os nomes visíveis da ISA. Um emulador pode armazenar apenas o valor atual de cada registrador arquitetural. Essas implementações podem ser funcionalmente equivalentes na fronteira das instruções e ainda diferir profundamente em temporização, potência, especulação e recuperação.

## Representação dos registradores no ChrisCPU

`ChrisArchitectureState` contém dezesseis valores de propósito geral de 64 bits, acessíveis por índice e por nome através de uma união. Os índices iniciais associam RAX, RCX, RDX, RBX, RSP, RBP, RSI e RDI a zero até sete; os demais nomes cobrem R8 até R15. RIP, RFLAGS, registradores de controle, segmentos e outros campos arquiteturais ficam separados. A estrutura também contém TSC e dezesseis posições XMM de 16 bytes. A existência de um campo não demonstra a implementação de todas as instruções associadas.

A união significa que `gpr[4]` e `rsp` nomeado referem-se ao mesmo valor representado, não a duas cópias que exigiriam sincronização manual. A declaração é a evidência dessa relação. Não constitui um formato estável de serialização: layout do compilador, alinhamento e demais campos importam antes de transportar bytes crus por uma ABI. Um formato de intercâmbio de snapshots precisaria de contrato próprio.

`chris_read_gpr` e `chris_write_gpr` rejeitam índices fora de zero a quinze. Pressupõem ponteiros válidos e contexto de tamanho de operando suportado. A largura é informada em bytes. Leituras mascaram a porção solicitada. Escritas aplicam regras diferentes de preservação conforme a largura, razão pela qual substituir toda escrita por uma atribuição de palavra inteira seria incorreto.

| Tamanho de escrita | Atualização do destino | Porção preservada |
|---|---|---|
| 1 byte baixo comum | Substitui bits 7:0 | Bits 63:8 |
| 1 byte alto legado | Substitui bits 15:8 | Bits 63:16 e 7:0 |
| 2 bytes | Substitui bits 15:0 | Bits 63:16 |
| 4 bytes | Atribui valor mascarado de 32 bits | Zera os 32 bits superiores |
| 8 bytes | Substitui a palavra inteira | Nenhuma |

A seleção do byte alto legado ocorre quando a instrução decodificada tem tamanho byte, não possui prefixo REX e usa codificação de registrador de quatro a sete. A função associa essa codificação aos índices zero a três e desloca oito bits. Com REX, essas codificações selecionam bytes baixos. Essa é uma regra de codificação de instruções expressa como seleção de armazenamento, não uma largura diferente do registrador subjacente de 64 bits.

Partindo de RAX = `0x1122334455667788`, escrever `0xaa` no byte baixo produz `0x11223344556677aa`; no byte alto legado produz `0x112233445566aa88`. Escrever `0xbbcc` em 16 bits produz `0x112233445566bbcc`. Escrever `0xaabbccdd` em 32 bits produz `0x00000000aabbccdd`. Esses casos distinguem preservação, deslocamento e extensão por zeros sem depender da ordem de bytes de um dump da memória hospedeira.

## Derivação de contadores a partir de soma e habilitação

Um contador binário sem sinal de largura w implementa Q_next = (Q + 1) mod 2^w quando habilitado. O bit zero alterna a cada incremento. O bit i alterna quando todos os bits menos significativos são um. Assim, cada próximo bit pode ser escrito como Q_i XOR o carry que chega à posição. O contador é um somador especializado com um operando fixo, não uma operação matemática independente.

Um contador ripple utiliza a saída de um estágio como clock de outro, propagando a transição por eventos locais. Um contador síncrono usa um clock comum e calcula combinacionalmente a próxima entrada de cada bit. Padrões intermediários de ripple podem confundir um decodificador que observe a contagem antes da estabilização. Mesmo saídas síncronas têm skew; consumidores assíncronos continuam exigindo protocolo. “Contador síncrono” não estabelece travessia coerente para outro domínio.

Um contador módulo M que não seja potência de dois pode comparar Q com M − 1 e selecionar zero em vez de Q + 1. Comparação e seleção acrescentam lógica ao caminho de próximo estado. Valores M até 2^w − 1 são codificações não utilizadas; o projeto deve definir sua recuperação caso sejam atingidos. Um contador saturante mantém o máximo. Contagem modular, estatística saturante e número de geração atendem a objetivos distintos mesmo com a mesma largura.

## Posição no anel e número de sequência são objetos diferentes

Um anel de N posições frequentemente seleciona slot = sequência mod N. A posição se repete com frequência, enquanto a sequência conserva informação adicional de progresso. Se N é potência de dois, mascarar com N − 1 produz o mesmo resto não negativo, mas o invariante conceitual continua sendo indexação modular. Posições iguais não implicam que produtor e consumidor estejam no mesmo ponto lógico.

A sequência finita também retorna a zero. Em contadores de w bits, a diferença sem sinal `(produtor − consumidor) mod 2^w` equivale à distância pendente real somente sob um limite externo que impeça um módulo inteiro de progresso não observado. Comparações de ordem baseadas no sinal da diferença modular normalmente exigem a restrição mais forte de meio intervalo. São contratos diferentes. Uma fila com capacidade muito menor que o módulo pode impor o limite de distância por propriedade dos itens e controle de saturação.

| Sequência de 16 bits | Posição em oito slots | Significado |
|---|---|---|
| 65534 | 6 | Próxima do retorno modular |
| 65535 | 7 | Última sequência representável |
| 0 | 0 | Evento seguinte após retorno |
| 1 | 1 | Evento posterior |

Se o consumidor está em 65534 e o produtor em 1, a distância modular é três. Considerar o produtor “atrasado” porque seu valor numérico é menor seria incorreto. Por outro lado, um produtor irrestrito poderia avançar 65536 vezes e retornar à mesma sequência; igualdade isolada não detecta esse histórico. A aritmética dos contadores precisa ser explicada junto com capacidade e propriedade.

## Os contadores concretos da fila VirtIO

`Virtq` armazena `qsz`, `nfree`, `free_head` e `last_used` em quantidades de 16 bits, junto dos links de descritores mantidos pelo software. `virtq_bytes` aceita potências de dois entre dois e `VQ_MAX`, definido como 128 no cabeçalho inspecionado. Os índices available e used residem no buffer compartilhado de bytes, separados desses campos locais. As funções leem e escrevem explicitamente suas representações little-endian.

`virtq_publish` lê o índice available, seleciona `idx % qsz`, escreve a cabeça da cadeia naquela posição e publica `(uint16_t)(idx + 1)`. `virtq_take` compara o índice used escrito pelo dispositivo com `last_used`; igualdade significa ausência de nova conclusão. Caso contrário, lê uma entrada em `last_used % qsz`, verifica se o identificador está dentro da fila, devolve identificador e tamanho e avança `last_used` módulo 65536.

![Propriedade da fila e contadores modulares](../../assets/diagrams/register-counter-contract.svg)

A publicação contém barreiras de memória; em x86 a função local emite `mfence`, enquanto o outro ramo contém apenas uma barreira de compilador. A implementação inspecionada não estabelece um contrato portátil de sincronização DMA para qualquer arquitetura. `virtq_publish` também não prova independentemente que o descritor está alocado, é único ou pode ser reutilizado. A checagem de limites é necessária, mas a responsabilidade pela propriedade permanece com o chamador.

A alocação percorre n descritores e custa O(n); publicar uma cabeça e obter uma conclusão executam trabalho local O(1). A recuperação percorre a cadeia de software. Os arrays fixos limitam o armazenamento, mas propriedade malformada ou recuperação repetida ainda podem corromper a lista livre lógica. Um contador numericamente dentro dos limites não prova que cada descritor pertence a exatamente um responsável. O invariante relaciona lista livre, cadeias visíveis ao dispositivo e tratamento das conclusões.

## Contagem de instruções é outro tipo de contador

Em `cpu_run`, `cpu->steps`, `cpu->arch.tsc` e o contador local n são incrementados quando o caminho de execução chega ao final do laço. Breakpoint, falha de busca e falha de decodificação podem sair antes. Portanto, a contagem descreve o progresso de software desse backend, não ciclos físicos do hospedeiro nem uma contagem universal de instruções aposentadas com sucesso. Um caminho que alcance o final após marcar parada ou exceção ainda pode incrementar os valores.

O orçamento da chamada compara n com `max_steps`. Isso limita o progresso do laço em uma chamada, não estabelece um prazo de relógio real. Uma instrução ou operação de dispositivo cara pode consumir mais tempo hospedeiro que outra barata. Um escalonador ou benchmark não deve converter esse orçamento em segundos sem um modelo temporal independente. A mesma distinção separa uma sequência de fila, um divisor de frequência e uma estatística diagnóstica de eventos.

## Interpretação como máquina de estados e reset

Um contador é uma máquina de estados finitos com função de transição especialmente regular. Um controlador pode combiná-lo com fases: ocioso, ativo, aguardando ou falho. Reset deve restaurar uma tupla coerente de fase, contagem, validade e propriedade. Limpar somente a contagem pode fazer entradas antigas parecerem novas. Limpar apenas validade pode abandonar recursos alocados. Correção de reset é uma relação entre campos, não uma lista de atribuições independentes.

Em um banco de registradores, atualizações arquiteturais simultâneas devem ser descritas em termos de estado antigo e próximo estado. Em uma fila, publicação pelo produtor e confirmação pelo consumidor são transições separadas cuja ordenação estabelece transferência de propriedade. Em um emulador, a atualização parcial de registrador é um componente da execução de uma instrução. Esses mecanismos compartilham evolução de estado, mas têm fronteiras distintas de sincronização.

## Evidências e limites

As afirmações sobre implementação vêm dos arquivos declarados na revisão registrada. Os exemplos hexadecimais aplicam diretamente máscaras e deslocamentos de `chris_write_gpr`; os exemplos de fila derivam dos incrementos de 16 bits e da indexação modular inspecionados. Não se afirma ter medido área de banco físico, atraso de portas ou vazão da fila. A verificação aritmética valida a função separada de flags, não essas interfaces de registradores e filas.

As propriedades de integração mais importantes continuam sendo escrita coerente de instruções, larguras decodificadas válidas, propriedade de filas durante acesso do dispositivo e reset no ciclo de vida da máquina completa. Exigem testes de subsistemas e contratos arquiteturais próprios. Registradores e contadores fornecem o vocabulário para declarar essas propriedades precisamente; não as tornam automáticas.
