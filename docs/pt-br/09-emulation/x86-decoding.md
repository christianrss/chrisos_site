---
id: x86-decoding
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/cpu/common/state.c
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/cpu/emulator/operands.c
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/tests/test_chrisvm.c
  - chrisvm/Makefile
symbols:
  - ChrisInsn
  - chris_decode
  - read_modrm
  - imm_n
  - chris_format_insn
  - chris_imm_sx
  - chris_eff_addr
  - chris_read_gpr
  - chris_write_gpr
  - fetch_insn
depends_on:
  - emulator-theory
  - x86-instruction-encoding
  - x86-registers-flags
related:
  - emulator-flags
  - emulator-exceptions
  - chrisvm-chriscpu
---

# Decodificação de instruções x86-64 no ChrisCPU

## Escopo e fronteira de evidência

A decodificação de instruções é a fronteira entre um fluxo de bytes e uma intenção arquitetural executável. No ChrisCPU, o decoder não executa instruções nem lê diretamente a memória convidada. Ele recebe um buffer de bytes, classifica prefixos e formas de opcode, interpreta ModR/M e SIB quando necessários, extrai deslocamentos e imediatos e grava uma representação compacta em ChrisInsn. O executor consome essa representação depois.

A separação é importante para validação. Um decoder pode reconhecer corretamente o mnemônico e ainda produzir largura de operando, extensão de registrador, deslocamento, imediato, modo de endereçamento ou comprimento incorretos. Da mesma forma, a execução pode estar errada mesmo quando o parsing está correto. A implementação atual precisa, portanto, ser avaliada como parser mais camada de descrição de operandos, e não apenas como uma função que gera assembly reconhecível.

O código inspecionado neste capítulo é o main do ChrisOS na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56. A implementação é um subconjunto x86-64 deliberadamente limitado para o ChrisVM. Não é um decoder Intel/AMD completo e não afirma cobertura da ISA inteira.

## Contrato de fetch em runtime

O helper fetch_insn do interpretador lê exatamente quinze bytes convidados antes de chamar chris_decode. Quinze bytes é o comprimento arquitetural máximo de uma instrução x86. Cada byte é obtido por chris_va_read com classe de acesso de execução, começando no RIP atual.

Esse desenho entrega ao decoder uma janela fixa e completa, mas torna o fetch antecipado em vez de sob demanda. Uma instrução curta localizada no final de uma página mapeada pode fazer o interpretador ler a página seguinte mesmo quando a instrução real não precisa desses bytes. Se a página seguinte estiver ausente, protegida ou representar uma região com efeitos colaterais no mapa da máquina, o acesso adicional pode afetar o comportamento antes que o decoder determine o comprimento verdadeiro. Um fetch incremental ou consciente de página evitaria esse tipo de acesso desnecessário, mas exigiria um protocolo explícito para entrada incompleta de prefixos, ModR/M, SIB, deslocamentos e imediatos.

O decoder aceita qualquer quantidade positiva de bytes disponíveis. Retorna menos um quando falta um byte estrutural obrigatório. Para uma codificação completa, porém desconhecida ou classificada como inválida no subconjunto implementado, o resultado normal é um comprimento positivo com a operação classificada como CHRIS_OP_UD. Assim, truncamento e invalid opcode permanecem resultados diferentes.

## ChrisInsn como representação intermediária

ChrisInsn é o registro intermediário compartilhado entre decode e execute. Ele preserva campos semânticos em vez de simplesmente copiar os bytes originais.

| Classe | Campos representativos | Significado |
|---|---|---|
| operação | op, alu, shift_kind, unary, muldiv, flag_op, desc_op | família semântica selecionada por opcode ou grupo |
| larguras | os, asz, src_os | tamanhos de operando, endereço e origem de extensão |
| prefixos | rex, rex_w/r/x/b, lock, rep | estado efetivo dos prefixos |
| ModR/M | mod, reg, rm, rm_field, digit, has_modrm | seleção register/memory e dígito de grupo |
| SIB | scale, index, base, no_index, no_base, has_sib | componentes de endereçamento indexado |
| deslocamento | disp, has_disp, rip_rel | deslocamento com sinal e classificação RIP-relative |
| imediato | imm, imm_bytes | bits crus do imediato e sua largura codificada |
| controle | cc, vector, form, cr_to_reg | condição, interrupção e forma dos operandos |
| comprimento | len | quantidade de bytes consumidos |

A representação distingue deliberadamente reg de digit. O campo reg do ModR/M recebe extensão REX.R quando nomeia um registrador, enquanto digit mantém os três bits originais para opcodes agrupados. Isso impede que uma extensão REX transforme um seletor de grupo como /0 em outra operação.

A estrutura é pequena e adequada à stack. chris_decode zera uma instância local, preenche os campos proceduralmente, define len e copia o valor para o caller. Não existe alocação de heap durante a decodificação.

## Varredura de prefixos

is_prefix reconhece override de tamanho de operando 66, override de tamanho de endereço 67, LOCK F0, prefixos de repetição F2 e F3, segment overrides legacy 26/2E/36/3E/64/65 e bytes REX de 40 a 4F.

O loop de prefixos consome bytes somente enquanto o índice permanece abaixo de quatorze, preservando espaço para pelo menos um opcode dentro do máximo de quinze bytes.

O tamanho padrão de operando é 32 bits e o tamanho padrão de endereço é 64 bits. REX.W seleciona operando de 64 bits. O prefixo 66 seleciona 16 bits quando não há um REX.W efetivo. O prefixo 67 seleciona endereçamento de 32 bits.

Um detalhe importante é a retenção de REX. Quando um prefixo legacy aparece depois de um REX, o estado REX armazenado é limpo. Um REX posterior pode se tornar efetivo novamente. Isso corresponde à regra de long mode em que o REX efetivo ocupa a posição final apropriada entre prefixos, em vez de ser tratado como prefixo legacy livremente comutativo.

LOCK e o estado REP são preservados. Prefixos de segmento são consumidos, mas sua identidade não é guardada em ChrisInsn. Essa é uma limitação material: aceitar 64 ou 65 não significa que endereçamento geral relativo a FS ou GS esteja implementado, porque a camada de execução não consegue reconstruir qual override de segmento estava presente.

## Tamanho de operando e endereço

Após processar prefixos, a largura normal do operando é:

    REX.W efetivo -> 8 bytes
    senão 66     -> 2 bytes
    senão        -> 4 bytes

A largura do endereço é:

    67 presente -> 4 bytes
    senão       -> 8 bytes

Famílias de instruções podem substituir esses padrões. Operações de byte usam os igual a um. PUSH e POP usam operando de stack de oito bytes por padrão e dois bytes com 66. Transfers de control register forçam oito bytes. MOVSX e MOVZX usam src_os para distinguir a largura da origem da largura do destino.

Essa informação de largura é arquiteturalmente importante. chris_write_gpr preserva bits não afetados em writes de 8 e 16 bits, zera os 32 bits superiores depois de um write de 32 bits em registrador geral e substitui o registrador inteiro em write de 64 bits. Um decoder que classifique os incorretamente altera semântica visível ao guest mesmo se o nome do opcode estiver correto.

## High-byte registers e REX

A codificação de registradores de oito bits possui uma divisão especial em long mode. Sem REX, códigos quatro a sete podem representar AH, CH, DH e BH. Com qualquer prefixo REX efetivo, os mesmos códigos numéricos representam SPL, BPL, SIL e DIL.

ChrisInsn mantém informação suficiente para operands.c implementar a diferença. high8 seleciona aliases high-byte legacy somente quando a largura é um byte, REX está ausente e o código de registrador está entre quatro e sete.

Isso também explica por que um REX cujos bits W/R/X/B são todos zero não pode ser simplesmente descartado. O prefixo 40 ainda modifica a identidade dos byte registers.

## Mapas de opcode de um e dois bytes

O parser implementa o mapa primário de um byte e um subconjunto do mapa de dois bytes iniciado por 0F. Ao encontrar 0F, ele consome um segundo opcode e muda para o caminho de dispatch de dois bytes.

Não existe parser para os mapas 0F 38, 0F 3A, VEX, XOP ou EVEX. Decodificação vector/SIMD geral está fora da implementação atual.

As famílias implementadas incluem:

| Família | Formas representativas tratadas |
|---|---|
| ALU inteira | linhas ADD, OR, ADC, SBB, AND, SUB, XOR, CMP; grupos 80-83; TEST |
| movimentação | MOV register/memory/immediate, MOVZX, MOVSX, LEA, XCHG |
| stack | PUSH, POP, PUSHF, POPF, LEAVE |
| fluxo de controle | Jcc short e near, JMP, CALL, RET |
| shifts/rotates | ROL, ROR, SHL, SHR, SAR via C0/C1/D0-D3 |
| unary/mul/div | NOT, NEG, INC, DEC, MUL, IMUL, DIV, IDIV e IMUL de dois operandos |
| port I/O | IN e OUT |
| interrupções | INT3, INT imm8, IRETQ |
| controle/sistema | MOV CR, CPUID, RDMSR, WRMSR, subset SGDT/SIDT/LGDT/LIDT |
| dados condicionais | CMOVcc e SETcc |
| strings | STOS com estado REP |
| flags | CLC, STC, CLI, STI, CLD, STD |
| diversos | NOP e HLT |

Reconhecimento no decoder não comprova que toda combinação de prefixos, regra de privilégio, condição de exceção, atomicidade ou variação de operandos esteja implementada corretamente. Essas propriedades atravessam execute.c e o mecanismo de entrega de exceções.

## Parsing de ModR/M

read_modrm divide ModR/M nos campos arquiteturais:

    bits 7..6 -> mod
    bits 5..3 -> reg ou group digit
    bits 2..0 -> r/m

reg é estendido com REX.R e rm com REX.B. O campo intermediário sem extensão é preservado separadamente como digit para grupos de opcode.

mod igual a três seleciona operando de registrador. Formas de memória podem consumir displacement:

- mod igual a um usa displacement signed de 8 bits;
- mod igual a dois usa displacement signed de 32 bits;
- codificações especiais com mod igual a zero usam displacement signed de 32 bits.

O decoder armazena o deslocamento em um campo signed de 64 bits. Displacements de oito e trinta e dois bits recebem sign extension quando entram nesse campo.

## Endereçamento RIP-relative

Com address size de 64 bits, ModR/M mod 00 com r/m 101 é classificado como RIP-relative. O decoder marca rip_rel e consome um displacement signed de 32 bits.

chris_eff_addr calcula depois:

    effective address = RIP atual + comprimento decodificado + displacement

O comprimento decodificado é essencial porque endereçamento RIP-relative usa o endereço da próxima instrução, e não o endereço de seu primeiro byte.

## Endereçamento SIB

Um operando de memória com r/m igual a quatro consome um byte SIB. Seus campos são scale nos bits 7..6, index nos bits 5..3 e base nos bits 2..0. REX.X estende index e REX.B estende base.

O helper de effective address combina depois:

    base + (index << scale) + displacement

respeitando no_index, no_base e address-size handling.

Index field quatro sem REX.X é classificado como ausência de index. Base field cinco com mod 00 é classificado como ausência de base na forma SIB. Essas flags impedem o executor de ler um GPR quando a codificação representa um componente omitido.

## Uma limitação concreta do address-size override

O decoder registra modo de endereço de 32 bits e chris_eff_addr mascara o effective address final para trinta e dois bits. Isso não significa que todos os special cases de ModR/M em 32 bits estejam implementados.

Em particular, a forma não-SIB mod 00, r/m 101 torna-se RIP-relative apenas quando o address size é 64 bits. Em endereçamento de 32 bits, a forma arquitetural é disp32 sem base. O parser atual não marca explicitamente esse caso como no-base, de modo que o caminho posterior de effective address pode incluir o registrador selecionado por rm em vez de tratar a codificação como displacement-only.

O probe atual da documentação verifica um caso simples 67 8B 00, mas não cobre esse caso especial não-SIB com r/m cinco. A afirmação correta é, portanto, suporte parcial a effective addressing de 32 bits, e não suporte completo ao address-size override.

## Representação de imediatos e sign extension

imm_n lê um, dois, quatro ou oito bytes para um campo bruto de 64 bits e registra separadamente a largura codificada.

A sign extension é deliberadamente adiada. chris_imm_sx interpreta o valor bruto de acordo com imm_bytes. Branches relativos, formas imediatas de PUSH e formas ALU usam esse helper quando um imediato codificado mais estreito representa um valor signed mais largo.

Isso importa em formas de 64 bits cuja codificação contém imm32 com sign extension para a largura da operação. Preservar separadamente bits crus e largura evita perder essa distinção durante o parsing.

## Truncamento, UD e UNIMPL

Truncamento estrutural e invalidade arquitetural são resultados diferentes. Se estiver ausente um segundo opcode, ModR/M, SIB, displacement ou immediate obrigatório, o decoder retorna menos um.

Se a sequência estiver completa mas for unsupported ou classificada como inválida, o decoder pode retornar comprimento positivo com CHRIS_OP_UD. O probe de contrato verifica 0F 0B como classificação UD explícita de dois bytes.

Alguns membros de grupo reconhecidos porém ainda não implementados tornam-se CHRIS_OP_UNIMPL. Isso expõe uma distinção interna entre uma codificação inválida e uma codificação reconhecida pelo projeto mas ainda não executada. A política precisa permanecer consistente conforme a cobertura cresce, pois o comportamento visível ao guest depende de como o executor trata cada classe.

O guard final impede que uma instrução reporte comprimento superior a quinze bytes.

## Legalidade no decode versus execução

O decoder não é um verificador completo de legalidade arquitetural. Algumas restrições são aplicadas depois.

LOCK é um exemplo útil. O decode guarda o prefixo genericamente. execute.c aplica lock_ok a operações ALU selecionadas e rejeita LOCK quando o operando escolhido é um registrador ou não há ModR/M. Outras famílias não executam todas uma validação equivalente, e a implementação atual não estabelece atomicidade geral de memória para operações locked.

Da mesma forma, instruções privilegiadas como CLI, STI, MOV CR, RDMSR e WRMSR exigem checks de privilégio e estado em tempo de execução. Fazer parsing de sua forma não prova que elas possam executar legalmente no CPL atual.

## Formatação é diagnóstico, não disassembly canônico

chris_format_insn produz texto compacto para trace. Existe formatação dedicada para operações ALU, Jcc, várias formas de MOV e STOS, com fallback para chris_op_name em outras operações.

A função não é um disassembler completo. Ela não preserva ou exibe todos os prefixos, seleção de segmento, expressão de endereço ou interpretação de immediate. O texto de trace é útil para debug, mas não deve ser tratado como reconstrução lossless da codificação original.

## Complexidade e comportamento de memória

chris_decode opera sobre no máximo quinze bytes relevantes. Prefix scan, ModR/M, SIB, displacement e parsing de immediate são limitados por esse máximo fixo. O tempo é O(L) no comprimento da instrução, com L no máximo quinze, portanto constante em relação ao tamanho do programa convidado.

O decoder não faz alocação de heap. Leituras de largura fixa usam memcpy em vez de dereference tipado potencialmente desalinhado.

O custo maior do interpretador ocorre antes do parsing: o fetch antecipado pode fazer quinze guest virtual reads para cada instrução, e cada leitura pode envolver address translation. Micro-otimizar apenas o decoder não elimina esse custo de fronteira em determinados workloads.

## Evidência de validação

O repositório de documentação inclui scripts/check_instruction_contracts.py. Esse probe host compila os helpers reais de state, decoder e operands do checkout do ChrisOS, em vez de reimplementar a lógica em Python.

Ele valida:

- 20 fixtures literais de instruções;
- 69 casos de truncamento;
- 80 casos de largura e aliases de registradores;
- dois índices inválidos de registrador;
- quatro casos de effective address;
- uma classificação UD explícita.

As fixtures cobrem operandos de 16, 32 e 64 bits, branches short e near, SIB, RIP-relative addressing, um address-size override básico, registradores estendidos por REX, aliases high-byte versus REX byte, SIB sem base/index, NOP e HLT.

chrisvm/tests/test_chrisvm.c também executa 2.000 chamadas pseudoaleatórias determinísticas ao decoder. Esse loop verifica uma propriedade de segurança: o retorno é menos um ou um comprimento positivo entre um e quinze, e insn.len coincide com o retorno. Ele não prova independentemente que o significado x86 de instruções aleatórias esteja correto.

Testes de integração executam byte streams literais cobrindo ALU, MOV, calls, memory access, port I/O, exceções, CPUID/MSR, multiplicação/divisão, STOS e control flow. Eles validam decode em conjunto com execution, memory e exception machinery.

## Limitações atuais

Na revisão inspecionada, o decoder deve ser tratado como um subconjunto x86-64 útil e específico do projeto, com fronteiras explícitas de compatibilidade:

- sem VEX, EVEX, XOP ou mapas vetoriais gerais;
- sem decodificação x87;
- sem famílias SSE/AVX abrangentes;
- sem mapas de opcode de três bytes;
- apenas um pequeno subconjunto de string instructions;
- identidade de segment override é descartada;
- sem representação geral de endereçamento relativo a FS/GS;
- special cases incompletos para address size de 32 bits;
- legalidade de LOCK e atomicidade de memória incompletas;
- legalidade de combinações de prefixos não é validada exaustivamente;
- muitas instruções de sistema e privilegiadas estão ausentes;
- formatter não é um disassembler completo;
- random testing verifica bounds, não semântica de ISA;
- fetch em runtime lê quinze bytes antecipadamente e pode cruzar página sem necessidade.

Esses limites são fronteiras de compatibilidade, não defeitos da documentação. Eles definem trabalho concreto antes que o ChrisCPU possa afirmar compatibilidade binária mais ampla.

## Prioridades de hardening e expansão

Os próximos passos de maior valor são:

1. adicionar testes exatos para todos os special cases de ModR/M e SIB em address size de 64 e 32 bits;
2. preservar e executar semântica de overrides FS/GS;
3. tornar fetch demand-driven ou page-aware para que instruções curtas não exijam quinze bytes legíveis;
4. separar tabelas de opcode do parsing procedural conforme a cobertura crescer;
5. adicionar validação sistemática da legalidade de LOCK, REP e combinações de prefixos;
6. ampliar fixtures independentes para cada família de opcode e group digit implementado;
7. adicionar mutation/fuzz testing comparando o subset com uma referência externa confiável;
8. caracterizar de modo consistente a política UD versus UNIMPL;
9. gerar uma tabela explícita de ISA suportada a partir dos testes do decoder, e não do roadmap;
10. manter cobertura de decode e execute sincronizada para que toda forma aceita possua comportamento guest-visible definido.

## Nota de revisão

Este capítulo documenta o decoder do ChrisCPU na revisão ChrisOS e05a17fd76333114a3fb5c2452f38ca747d4ac56. Nessa revisão, o parser possui desenho limitado a quinze bytes, representação explícita em ChrisInsn, tratamento de REX/ModR/M/SIB, subconjuntos integer/control/system e probes host de contrato. Ele permanece intencionalmente incompleto em relação à arquitetura x86-64 completa.
