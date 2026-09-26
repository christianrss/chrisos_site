---
id: x86-registers-flags
lang: pt-br
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - chrisvm/chris_arch.h
  - chrisvm/cpu/common/state.c
  - chrisvm/cpu/common/cpuid.c
  - chrisvm/cpu/emulator/operands.c
  - chrisvm/cpu/emulator/flags.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/cpu/emulator/chriscpu.c
symbols:
  - ChrisArchitectureState
  - chris_arch_reset
  - chris_cpuid
  - chris_read_gpr
  - chris_write_gpr
  - chris_flags_bin
  - chris_cc_true
  - cr_ptr
  - msr_access
depends_on:
  - cpu-datapath-isa
  - arithmetic-circuits
  - registers-counters
related:
  - machine-code
  - x86-instruction-encoding
  - x86-64-memory-privilege
  - privilege-rings
---

# Registradores, aliases e flags x86-64

## Armazenamento arquitetural e nomes usados pelo software

Um nome de registrador identifica um local de armazenamento visível ao software ou uma visão parcial dele. Não especifica quantas células físicas implementam essa visão. Os capítulos de circuitos sequenciais explicam os elementos de armazenamento; o capítulo de datapath explica como instruções selecionam e transformam valores. Aqui o contrato é o valor observado pelo software, incluindo o destino dos bits fora de um subregistrador selecionado. Esse contrato é indispensável para emuladores, alocadores de registradores de compiladores e trocas de contexto.

ChrisCPU representa dezesseis registradores gerais em uma união que contém `uint64_t gpr[16]` e campos nomeados. A ordem corresponde à codificação arquitetural, não à ordem alfabética. O índice um acessa RCX, não RBX. As visões nomeada e indexada apontam para o mesmo armazenamento; alterar uma muda o valor observado pela outra. É uma conveniência de representação C, não um banco separado de registradores serializados.

| Índice | 64 bits | 32 bits | 16 bits | Byte inferior com REX |
|---|---|---|---|---|
| 0 | RAX | EAX | AX | AL |
| 1 | RCX | ECX | CX | CL |
| 2 | RDX | EDX | DX | DL |
| 3 | RBX | EBX | BX | BL |
| 4 | RSP | ESP | SP | SPL |
| 5 | RBP | EBP | BP | BPL |
| 6 | RSI | ESI | SI | SIL |
| 7 | RDI | EDI | DI | DIL |
| 8–15 | R8–R15 | R8D–R15D | R8W–R15W | R8B–R15B |

Uma ABI atribui papéis adicionais, como passagem de argumentos, retorno de resultados e preservação entre chamadas. Essas convenções não impedem fisicamente que um registrador contenha outro valor. RSP tem papel especial nas instruções de pilha; uma ABI também pode designar RBP como ponteiro de quadro. Um compilador pode omitir esse ponteiro sob uma convenção adequada, mas não pode ignorar a semântica das instruções de pilha. Papéis arquiteturais e convenções de chamada precisam de descrições distintas.

## Escritas parciais são transformações de estado

Considere o valor antigo de 64 bits `0x1122334455667788` e entrada `0xaabbccdd`. O armazenamento resultante depende da largura:

| Escrita | Armazenamento resultante de 64 bits | Regra |
|---|---|---|
| Registrador de 64 bits | `0x00000000aabbccdd` | Substitui todos os 64 bits pela entrada |
| Subregistrador de 32 bits | `0x00000000aabbccdd` | Substitui os 32 inferiores e zera os superiores |
| Subregistrador de 16 bits | `0x112233445566ccdd` | Substitui os 16 inferiores e preserva o restante |
| Byte inferior | `0x11223344556677dd` | Substitui os oito inferiores e preserva o restante |
| Byte alto legado | `0x112233445566dd88` | Substitui bits 15:8 e preserva os demais |

A igualdade dos dois primeiros resultados depende da entrada escolhida. Uma entrada completa com bits superiores não nulos distingue escrita de 64 bits de escrita de 32 bits. Algebricamente, substituir os w bits inferiores preservando o restante corresponde a `(old & ~mask) | (value & mask)`, com máscara 2ʷ − 1. A escrita de 32 bits deliberadamente não usa essa regra de preservação. Aplicar uma única fórmula genérica a todas as larguras implementaria a ISA incorretamente.

`chris_write_gpr` contém essas alternativas explicitamente. `chris_read_gpr` retorna a porção selecionada, limitada pela máscara. Ambas rejeitam índices fora de zero a quinze. Os tamanhos previstos são um, dois, quatro e oito bytes; valores arbitrários não constituem formato público de instrução validado. Decoder e chamadores precisam manter essa pré-condição. O ramo final de largura completa não demonstra que qualquer inteiro fornecido como tamanho é legal.

## Aliases de byte alto e presença de REX

Sem REX, códigos de registrador de byte quatro a sete representam AH, CH, DH e BH, os segundos bytes dos quatro primeiros registradores. Com qualquer REX, representam SPL, BPL, SIL e DIL. O prefixo `40` possui todos os bits de extensão desligados, mas ainda altera a interpretação. Removê-lo por parecer redundante pode mudar o comportamento do programa.

A sequência literal `88 e0` move AH para AL. `40 88 e0` move SPL para AL. Em ambas, o campo de registrador de ModR/M vale quatro, mas o armazenamento selecionado difere. `high8` verifica operando de byte, ausência de REX e faixa do código; `gpr_index8` converte o código legado para um dos quatro primeiros slots. O caminho de escrita substitui bits 15:8 quando esse predicado é verdadeiro.

Esse alias também restringe o compilador. Uma operação de byte que exige REX para outro operando não pode simultaneamente nomear AH pela codificação legada. Alocação precisa considerar se a instrução pode ser codificada, além de verificar se os valores cabem nos bits disponíveis. Um desmontador também precisa preservar o contexto de prefixos para imprimir o nome correto.

## RFLAGS como campos com significados independentes

RFLAGS reúne estado aritmético, controle de execução e estado relacionado ao sistema. Não é um único resultado Booleano de sucesso. A tabela define papéis arquiteturais, sem afirmar que ChrisCPU implementa completamente todos os recursos:

| Bits | Nome | Papel |
|---|---|---|
| 0 | CF | Carry ou empréstimo na aritmética sem sinal |
| 2 | PF | Paridade par do byte inferior do resultado |
| 4 | AF | Carry ou empréstimo atravessando o bit 3 |
| 6 | ZF | Resultado zero na largura da operação |
| 7 | SF | Bit mais significativo na largura do resultado |
| 8 | TF | Controle de execução passo a passo |
| 9 | IF | Habilitação de interrupções mascaráveis |
| 10 | DF | Direção das operações de strings |
| 11 | OF | Overflow aritmético com sinal |
| 12–13 | IOPL | Nível de privilégio de entrada e saída |
| 14 | NT | Estado de tarefas aninhadas |
| 16 | RF | Controle de retomada para depuração |
| 17 | VM | Estado do modo virtual-8086 |
| 18 | AC | Estado de verificação de alinhamento no contexto arquitetural |
| 19–20 | VIF, VIP | Flag virtual de interrupção e pendência |
| 21 | ID | Flag relacionada à identificação por CPUID |

`write_status` limpa e substitui CF, PF, AF, ZF, SF e OF, preserva os demais bits recebidos e força o bit um para um. PF usa o byte inferior mesmo em operação de 64 bits. ZF e SF usam a largura do operando. Preservar bits não relacionados é um invariante: somar inteiros não pode limpar IF ou DF acidentalmente. Entretanto, preservar um campo nesse helper não implementa todas as instruções capazes de modificá-lo.

`chris_flags_bin` calcula resultado mascarado e retorna flags atualizadas. ADD e ADC usam intermediário mais largo para obter carry; subtração compara operandos sem sinal para obter empréstimo e inclui carry anterior em SBB. O capítulo de circuitos aritméticos deriva as equações de overflow. Para operações lógicas, este helper escolhe AF igual a zero. Software não pode transformar essa escolha determinística do emulador em garantia arquitetural para flags que a ISA deixa indefinidas.

## Interpretação condicional e ordenação com sinal

`chris_cc_true` implementa dezesseis condições usando CF, PF, ZF, SF e OF. Igualdade consulta ZF. Inferior sem sinal consulta CF; superior sem sinal exige CF e ZF desligados. Menor com sinal usa `SF != OF`; maior com sinal exige ZF desligado e `SF == OF`. A correção por overflow é necessária porque o sinal de uma subtração que sofreu wraparound não determina sozinho a ordenação com sinal.

Em oito bits, 127 menos −1 produz o padrão truncado `0x80`. SF é um, mas OF também é um; o predicado de menor com sinal é falso, corretamente, pois 127 é maior que −1. Desvios, movimentos condicionais e SETcc consomem esses predicados de maneiras distintas. Produzir o mesmo Booleano não estabelece comportamento idêntico de acesso à memória ou falhas entre essas famílias de instruções.

## Flags de controle e instante dos eventos

CLC e STC modificam CF sem recalcular os demais bits de estado aritmético. CLD e STD alteram DF, consultado por operações de strings para determinar direção de percurso. CLI e STI alteram IF no despacho inspecionado; STI também liga `sti_delay`. O laço consome esse atraso antes de aceitar uma interrupção pendente, portanto atribuir IF isoladamente perderia uma parte temporal do contrato da instrução. Esses controles não tornam as flags uma palavra inteiramente substituível: cada instrução controla um subconjunto especificado. Também mostram por que salvar somente RFLAGS omite estado de eventos guardado pelo emulador em `sti_delay` e `irq_pending`.

## RIP, RSP e completude de contexto

RIP identifica o fluxo de instruções; RSP identifica a posição da pilha usada pelas operações correspondentes. Salvar seus valores numéricos sem salvar ou preservar a memória referenciada não captura um processo executável. A estrutura arquitetural também contém controles e descritores que influenciam a interpretação desses valores. Uma fronteira de contexto precisa especificar qual estado possui, qual permanece compartilhado e qual será reconstruído.

`cpu_get` e `cpu_set` copiam `ChrisArchitectureState`. É uma operação de representação dentro do processo, sem serialização portátil campo a campo. Padding da estrutura, representação de inteiros, evolução de versão e estado de máquina omitido importam para um snapshot persistente. A cópia também não apresenta sincronização visível com uma CPU executando simultaneamente. O chamador precisa de uma fronteira de execução em repouso ou de mecanismo de sincronização definido separadamente.

## Registradores de controle, descritores e MSRs

O modelo armazena CR0, CR2, CR3, CR4 e CR8. `cr_ptr` retorna ponteiros somente para esses números; outros causam falha no tratamento da instrução. CR0 inclui controles de modo e proteção de escrita; CR2 registra endereço linear de falta; CR3 fornece raiz de paginação; CR4 contém extensões arquiteturais; CR8 representa controle de prioridade de tarefa. São definições de papéis: regras detalhadas de bits permitidos e transições pertencem à arquitetura de sistema e não decorrem de um slot de 64 bits.

O handler MOVCR lê ou escreve o slot selecionado. Uma escrita identificada como CR3 incrementa `tlb_gen`. Um contador de geração é controle interno, não prova de TLB associativo modelado, protocolo de invalidação entre CPUs ou validação completa de bits reservados. Não há verificação de CPL visível nesse handler antes da transferência. A mesma observação restrita vale para os caminhos inspecionados de MSR e CLI/STI. É uma limitação concreta desses caminhos, não uma auditoria completa de todas as fronteiras de privilégio do projeto.

`ChrisSeg` contém seletor, base, limite e atributos. `ChrisDtr` contém base e limite de registradores de tabelas de descritores. Essas estruturas C não são descritores arquiteturais compactados: o código que carrega ou salva o operando da tabela manipula explicitamente limite de dois bytes e base de oito. O modelo também mantém TR e LDTR. Reter esses valores não demonstra implementação de todas as regras de troca de tarefa ou validação de segmentos.

`msr_access` seleciona MSR usando ECX inferior. Os slots reconhecidos incluem EFER, STAR, LSTAR, CSTAR, FMASK, bases FS e GS, base GS do kernel e base APIC. Escrita combina EDX:EAX em 64 bits; leitura devolve as duas metades. Índice desconhecido causa exceção de proteção geral. Armazenar LSTAR não implementa SYSCALL, e armazenar bases FS/GS não demonstra que os helpers de endereço as adicionam.

## Reinicialização, descoberta de recursos e evidência executável

`chris_arch_reset` limpa a estrutura, define RFLAGS como dois e CR0 como PE mais NE. Esse é o estado inicial escolhido pelo emulador; não deve ser descrito como reprodução bit a bit da reinicialização elétrica de um x86 físico. A construção de boot acrescenta estado exigido por seu próprio protocolo. Reiniciar essa estrutura também não reinicia memória de dispositivos nem eventos pendentes fora dela.

`chris_cpuid` produz folhas virtuais determinísticas e não repassa CPUID do hospedeiro. A identificação de fabricante é `ChrisCPU` seguida por quatro espaços. A folha padrão um anuncia TSC, MSR, PSE, APIC e CMOV, omitindo FPU e SSE. A folha estendida anuncia modo longo. Embora o modelo reserve dezesseis slots XMM de dezesseis bytes e armazene valores relacionados a EFER, esses campos não justificam anunciar execução completa de vetores ou chamadas de sistema. Descoberta de recursos é uma promessa ao software convidado e precisa acompanhar comportamento implementado.

A sonda de contratos verifica escritas parciais e leitura posterior para os dezesseis índices em 16, 32 e 64 bits, além dos aliases de byte com e sem REX: 80 casos ao todo. Rejeita ainda dois índices inválidos. A sonda aritmética separada compara operações e condições com resultados calculados independentemente. Os testes passaram na revisão declarada. Não validam troca de contexto convidada, entrega de exceções, toda restrição de MSR ou segurança de snapshots concorrentes; cada interface exige sua própria evidência.

Os [manuais de arquitetura Intel](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) definem semântica normativa de registradores e privilégios. Os arquivos listados definem a representação observada de ChrisCPU e seus limites. Trabalho futuro precisa conectar verificações ausentes a casos explícitos de falha, sem tratar a existência de um campo como suporte arquitetural concluído.
