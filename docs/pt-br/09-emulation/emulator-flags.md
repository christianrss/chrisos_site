---
id: emulator-flags
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/cpu/common/state.c
  - chrisvm/cpu/emulator/flags.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - chris_flags_bin
  - chris_cc_true
  - write_status
  - parity_even
  - do_alu
  - do_shift
  - do_unary
  - mul_flags
depends_on:
  - x86-decoding
  - x86-registers-flags
  - number-systems-binary-arithmetic
related:
  - emulator-exceptions
  - chrisvm-chriscpu
---

# Flags aritméticas e avaliação de condições no ChrisCPU

## Por que flags fazem parte da semântica da instrução

Para um interpretador x86, a aritmética não termina quando o valor numérico do destino está correto. As status flags são saídas arquiteturais consumidas por branches condicionais, SETcc, CMOVcc, ADC, SBB, código sensível a exceções e muitos padrões gerados por compiladores. Um Carry Flag incorreto pode corromper aritmética multiprecisão. Um Overflow Flag incorreto pode inverter uma comparação signed. Zero ou Sign Flags erradas podem desviar o fluxo de controle mesmo quando o registrador calculado possui o valor numérico correto.

O ChrisCPU centraliza o cálculo de status para operações ALU binárias comuns em flags.c. O helper chris_flags_bin recebe o seletor ALU, dois operandos, tamanho do operando, RFLAGS de entrada e um ponteiro opcional para resultado. Ele devolve a palavra de flags atualizada e, quando solicitado, o resultado aritmético mascarado. chris_cc_true mapeia depois os cinco bits de condição utilizados por Jcc, CMOVcc e SETcc nos dezesseis predicados x86.

Este capítulo descreve a implementação na revisão ChrisOS e05a17fd76333114a3fb5c2452f38ca747d4ac56 e separa o comportamento dos helpers com evidência reproduzível do comportamento de famílias de instruções implementado em execute.c.

## Subconjunto de status modelado

O helper ALU comum atualiza seis bits de status:

| Flag | Bit | Significado no helper |
|---|---:|---|
| CF | 0 | carry de adição ou borrow de subtração |
| PF | 2 | paridade par do byte baixo do resultado |
| AF | 4 | carry/borrow entre bit 3 e bit 4 |
| ZF | 6 | resultado mascarado igual a zero |
| SF | 7 | bit de sinal do resultado mascarado |
| OF | 11 | overflow signed |

write_status primeiro limpa esses seis bits, calcula os novos valores, preserva os demais bits da palavra de entrada e força o bit 1 para um. O reset em chris_arch_reset também inicializa RFLAGS com dois, mantendo a invariável do projeto de que esse bit arquiteturalmente fixo permanece ativo.

O helper não reconstrói RFLAGS do zero. Preservar bits não relacionados importa porque uma operação aritmética não deve apagar silenciosamente IF, DF ou outro estado modelado.

## Largura como parte do domínio aritmético

chris_flags_bin aceita operandos de um, dois, quatro e oito bytes. size_mask restringe operandos e resultados a 8, 16, 32 ou 64 bits. sign_bit seleciona o bit mais significativo da largura.

Para uma largura w, o domínio unsigned é módulo 2^w. Uma adição host de apenas 64 bits não consegue expor o carry de saída de uma operação guest de 64 bits, portanto ADD e ADC usam unsigned __int128 no intermediário. O helper mascara depois os w bits baixos como resultado guest e testa se existe valor acima da largura guest.

Essa fronteira é fundamental: a largura do inteiro do host é detalhe de implementação; a largura do guest define a arquitetura. Todas as fórmulas de flags precisam usar o domínio guest.

## Adição e ADC

Para ADD, o intermediário amplo é:

    wide = a + b

Para ADC:

    wide = a + b + CF_in

Os operandos são mascarados antes da operação. O resultado são os w bits baixos.

Carry é definido quando o valor unsigned amplo ultrapassa a faixa representável na largura guest. Em uma operação de 64 bits, isso é detectado usando a parte superior do intermediário de 128 bits do host.

Signed overflow usa a identidade:

    OF = ((a XOR result) AND (b XOR result) AND sign_bit) != 0

Em adição, ocorre overflow quando os operandos têm o mesmo sinal e o resultado possui sinal diferente. A expressão codifica essa condição sem depender de conversão para um tipo signed do host com a mesma largura.

Auxiliary carry é:

    AF = ((a XOR b XOR result) AND 0x10) != 0

A expressão captura o carry através da fronteira do nibble inferior.

ADC difere de ADD não apenas no resultado numérico, mas em todas as flags influenciadas pelo carry de entrada. O helper lê CF da palavra de entrada antes de reescrever os bits de status.

## Subtração, CMP e SBB

SUB e CMP compartilham a mesma aritmética. CMP impede a escrita no destino em execute.c, mas produz as mesmas flags de uma subtração.

Para SUB:

    result = a - b

Para SBB:

    result = a - b - CF_in

O resultado é mascarado na largura guest.

Em x86, CF após subtração representa borrow unsigned. Sem carry de entrada:

    CF = a < b

Com SBB e carry de entrada igual a um, o lado fonte equivale a b + 1, e a implementação usa:

    CF = (a < b) OR (a == b)

equivalente a a <= b para os operandos mascarados.

Signed overflow é:

    OF = ((a XOR b) AND (a XOR result) AND sign_bit) != 0

A fórmula detecta uma subtração em que os sinais de origem e destino diferem e o sinal resultante não representa o resultado matemático signed.

AF volta a usar a relação XOR do nibble inferior.

## Operações lógicas e TEST

AND, OR, XOR e TEST usam o caminho lógico. TEST impede a escrita do resultado, mas atualiza status como um AND.

Nessas operações o ChrisCPU:

- calcula o resultado normalmente;
- limpa CF;
- limpa OF;
- deriva PF, ZF e SF do resultado;
- grava AF como zero.

O último item é uma escolha determinística específica do projeto. Em x86, AF fica undefined após essas operações lógicas. Um guest que observa AF depois de AND, OR, XOR ou TEST está fora de um contrato arquitetural portável. Os testes não devem transformar o zero do ChrisCPU em garantia geral da arquitetura x86.

## Paridade

parity_even examina somente o byte baixo do resultado, conforme a semântica de PF em x86. O helper dobra o byte com operações XOR até restar um bit de paridade e retorna verdadeiro quando há quantidade par de bits definidos.

PF é, portanto, independente dos bits acima do byte menos significativo. Um resultado de 64 bits e um resultado de 8 bits com o mesmo byte baixo possuem o mesmo PF.

## Zero e sinal

ZF é definido quando o resultado, depois da máscara de largura, é zero. SF copia o sign bit correspondente ao tamanho do operando.

A máscara antes dos testes é indispensável. Por exemplo, uma operação de 8 bits cujo intermediário host seja 0x100 possui resultado arquitetural zero. ZF precisa refletir o resultado de 8 bits, não o intermediário mais largo do host.

## Avaliação de condition codes

chris_cc_true usa CF, PF, ZF, SF e OF para implementar os dezesseis seletores condicionais de x86. O decoder armazena os quatro bits baixos do condition code para Jcc curto, Jcc near, CMOVcc e SETcc.

| cc | Predicado | Interpretação comum |
|---:|---|---|
| 0 | OF | overflow |
| 1 | not OF | no overflow |
| 2 | CF | below/carry |
| 3 | not CF | above-or-equal/no carry |
| 4 | ZF | equal/zero |
| 5 | not ZF | not equal/nonzero |
| 6 | CF or ZF | below-or-equal |
| 7 | not CF and not ZF | above |
| 8 | SF | sign |
| 9 | not SF | not sign |
| 10 | PF | parity |
| 11 | not PF | not parity |
| 12 | SF != OF | less, signed |
| 13 | SF == OF | greater-or-equal, signed |
| 14 | ZF or SF != OF | less-or-equal, signed |
| 15 | not ZF and SF == OF | greater, signed |

Comparações unsigned dependem de CF e ZF. Comparações signed dependem da relação entre SF e OF, com ZF distinguindo igualdade. Por isso, a correção de OF não é um detalhe isolado da ALU: ela controla diretamente branches signed.

O helper mascara cc com quinze, portanto seletores que diferem por dezesseis avaliam de modo idêntico. O probe host verifica explicitamente esse alias.

## Fluxo entre CMP, TEST, Jcc, CMOVcc e SETcc

O decoder classifica CMP e TEST como operações ALU, mas execute.c define write como falso para esses seletores. do_alu ainda lê os dois operandos e chama chris_flags_bin; o status torna-se visível arquiteturalmente enquanto o destino permanece inalterado.

Jcc chama chris_cc_true e altera RIP apenas quando o predicado é verdadeiro. CMOVcc e SETcc usam o mesmo helper. Assim, as três famílias compartilham uma única truth table em vez de duplicar a lógica de comparação signed e unsigned.

Essa centralização reduz uma classe importante de inconsistência: Jcc e SETcc não devem interpretar o mesmo estado de flags de maneiras diferentes.

## NEG, INC, DEC e NOT

Operações unary são implementadas em execute.c usando o helper binário quando possível.

NEG calcula zero menos o operando por CHRIS_ALU_SUB. Isso produz naturalmente as definições de flags de subtração. Em particular, CF fica definido para todo operando diferente de zero e limpo para zero.

INC calcula valor mais um pelo helper ADD, mas em x86 INC deve preservar o CF anterior. A implementação salva CF, atualiza as demais flags aritméticas e depois restaura CF.

DEC segue o mesmo padrão com subtração de um e restauração de CF.

NOT apenas inverte o operando e grava o resultado, sem alterar flags.

Esses wrappers mostram um princípio de implementação: reutilizar um primitivo aritmético só é correto quando exceções específicas da instrução ao comportamento de flags são reaplicadas explicitamente.

## Flags de multiplicação

mul_flags trata as flags que o ChrisCPU modela para MUL e IMUL. Ele limpa CF e OF e define ambas quando o produto não cabe no critério estreito da forma da instrução.

Para MUL unsigned, wide significa que a metade alta do produto não é zero.

Para IMUL signed, wide significa que truncar o produto para a largura do operando e fazer sign extension de volta não reproduz o produto completo.

Somente CF e OF são modificados por mul_flags. As demais status flags mantêm seus valores anteriores no ChrisCPU. Arquiteturalmente, várias delas são undefined após MUL/IMUL. Portanto, os valores preservados são resíduo determinístico da implementação, não comportamento em que software deva confiar.

DIV e IDIV não atualizam status flags no executor atual. As flags correspondentes também são undefined em x86, de modo que bits inalterados não devem ser interpretados como promessa portável.

## Tratamento de flags em shifts e rotates

do_shift implementa ROL, ROR, SHL, SHR e SAR iterando um bit por vez para a contagem efetiva. A contagem é mascarada para seis bits em operandos de 64 bits e cinco bits nos demais. Uma contagem mascarada igual a zero não altera destino nem flags.

A cada iteração, o bit deslocado ou rotacionado para fora é registrado em CF. Em operações à esquerda, sai o bit alto; nas operações à direita, sai o bit zero.

Depois do loop, a implementação atual usa o helper lógico AND para recalcular PF, AF, ZF e SF a partir do valor final, e então restaura CF e, condicionalmente, OF.

O desenho é compacto, mas o comportamento exato não pode ser descrito como compatibilidade plena. Existem lacunas observáveis.

### Lacuna de preservação de status em rotate

Arquiteturalmente, ROL e ROR afetam CF e, para contagem efetiva um, OF. ZF, SF, PF e AF não devem ser recalculados por rotate.

A implementação atual recalcula esses bits porque chama chris_flags_bin no resultado rotacionado antes de restaurar CF e OF. Um guest que dependa de ZF, SF ou PF anteriores sobreviverem a ROL/ROR pode observar comportamento diferente do hardware x86.

### Lacuna de redução da contagem de rotate

Para ROL/ROR de 8 e 16 bits, x86 aplica máscara de contagem e depois reduz a contagem efetiva módulo largura do operando. Uma rotação de uma largura inteira pode ter contagem efetiva zero e deve preservar flags.

O ChrisCPU mascara a contagem, mas executa esse número de rotações unitárias sem uma segunda redução módulo largura. O valor final pode coincidir depois de uma rotação completa, porém as flags podem mudar. Isso é outra diferença arquitetural observável.

### Lacuna de overflow em SHR

Para SHR com contagem efetiva um, x86 define OF com o bit mais significativo original. O ChrisCPU calcula atualmente o teste de OF de SHR usando o valor depois do shift. Em um valor cujo sign bit original era um, isso perde a informação necessária para o OF arquitetural.

### Lacuna de overflow em ROR

Para ROR com contagem efetiva um, x86 define OF como XOR dos dois bits mais significativos do resultado. O caminho atual de do_shift não calcula essa fórmula e deixa OF limpo.

### Flags undefined em shifts

Para contagens de shift maiores que um, OF é undefined arquiteturalmente. O ChrisCPU o limpa no rewrite de status e somente o define em alguns casos de contagem um. AF em shifts também é undefined e é deterministically limpo pelo caminho do helper lógico. Esses valores podem ser decisões internas determinísticas, mas não evidência de conformidade.

## Instruções diretas de controle de flags

O caminho CHRIS_OP_FLAG edita bits individuais de RFLAGS:

- CLC limpa CF;
- STC define CF;
- CLD limpa DF;
- STD define DF;
- CLI limpa IF;
- STI define IF e também sti_delay.

sti_delay participa da entrega de interrupções para que uma interrupção externa não seja entregue imediatamente no mesmo ponto de execução de STI. Trata-se de um contrato de control flow separado das flags aritméticas, mas armazenado no mesmo RFLAGS.

Checks de privilégio para instruções sensíveis são uma questão arquitetural mais ampla. Reconhecer a instrução e alterar o bit não estabelece comportamento completo de CPL/IOPL.

## PUSHF, POPF e IRETQ

PUSHF empilha um subconjunto mascarado do RFLAGS modelado. POPF aceita a forma de 64 bits no executor atual, mascara o valor restaurado e força o bit um. IRETQ também restaura um valor mascarado de flags junto com o estado de controle.

A máscara impede que bits altos arbitrários do host virem estado modelado. Entretanto, isso não constitui uma implementação completa das regras de privilégio de POPF/IRET. Essas instruções interagem com CPL, IOPL e outras restrições que precisam ser avaliadas junto ao mecanismo de exceções e proteção.

## Evidência aritmética reproduzível

O repositório da documentação contém scripts/check_arithmetic.py. Ele compila o flags.c real do ChrisCPU em uma shared library temporária do host e compara chris_flags_bin com um modelo Python independente baseado em faixas inteiras.

O probe executa 752.270 casos aritméticos. Na fase exaustiva de 8 bits, cobre todo par possível de operandos byte para os nove seletores ALU modelados, incluindo os dois estados de carry de entrada para ADC e SBB. Para 16, 32 e 64 bits, adiciona valores de fronteira e casos pseudoaleatórios determinísticos.

O modelo de referência calcula de forma independente overflow unsigned, overflow signed, auxiliary carry/borrow, paridade do byte baixo, zero e sinal.

O mesmo probe testa 1.024 casos de condition codes: todas as combinações de CF, PF, ZF, SF e OF, os dezesseis seletores e seus aliases deslocados por dezesseis. Ele também verifica nove chamadas com ponteiro de resultado nulo, demonstrando que o cálculo de status não depende de armazenar o resultado.

Essa é evidência forte para chris_flags_bin e chris_cc_true na revisão verificada. Não é evidência para decoder, wrapper de shift/rotate, multiplicação, entrada de exceção no guest, retirement completo de instrução, timing ou hardware físico.

## Evidência de integração existente

chrisvm/tests/test_chrisvm.c contém fronteiras aritméticas explícitas. Um teste soma um a um valor de 64 bits com todos os bits definidos e verifica resultado zero, CF definido, ZF definido, SF limpo, OF limpo, PF definido e AF definido. Outro soma um ao maior inteiro signed de 64 bits e verifica overflow signed sem carry unsigned.

Testes de instrução também executam ADD e inspecionam CF/ZF pelo estado da máquina. Testes de multiplicação verificam o produto e CF para um resultado wide.

Esses testes conectam os helpers a algumas instruções decodificadas/executadas, mas são deliberadamente mais estreitos que o probe aritmético.

## Limitações atuais e próximo hardening

O helper central ADD/ADC/SUB/SBB/CMP/AND/OR/XOR/TEST possui cobertura reproduzível incomumente ampla para o projeto, mas a correção de flags no emulador inteiro ainda não está completa.

As prioridades são:

1. corrigir ROL/ROR para preservar ZF, SF, PF e AF;
2. aplicar redução módulo largura na contagem arquitetural de rotates;
3. corrigir OF de SHR com contagem um usando o sign bit original;
4. implementar OF de ROR com contagem um a partir dos dois bits superiores do resultado;
5. adicionar probes dedicados de shift/rotate para todas as larguras e contagens;
6. testar NEG, INC e DEC exaustivamente em 8 bits e por fronteiras nas larguras maiores;
7. adicionar testes explícitos de CF/OF para MUL/IMUL em todas as larguras;
8. distinguir nos testes flags undefined arquiteturalmente de valores determinísticos do projeto;
9. ampliar validação de PUSHF/POPF/IRETQ e CLI/STI com regras de privilégio;
10. manter testes de condition codes presos à mesma revisão de fonte usada no cálculo de flags.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, o ChrisCPU possui um helper de flags para ALU binária verificado contra fonte e uma tabela completa dos dezesseis predicados condicionais para os status bits modelados. O probe independente fornece evidência profunda para esses helpers. O tratamento de shift e rotate continua sendo uma fronteira separada e materialmente menos completa, e não deve herdar por associação o mesmo nível de confiança de conformidade.
