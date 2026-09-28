---
id: number-systems-binary-arithmetic
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - chrisvm/cpu/emulator/flags.c
  - chrisvm/chris_arch.h
  - compiler/chrisasm/chrisasm.c
  - kernel/gfx/graphics.c
symbols:
  - chris_flags_bin
  - chris_cc_true
  - ChrisArchitectureState
  - parse_u64
  - emit_u32
  - emit_u64
  - gfx_rgb
depends_on:
  - boolean-algebra
related:
  - arithmetic-circuits
  - data-representation-layout
  - machine-code
  - x86-registers-flags
---

# Sistemas numéricos e aritmética binária

<div class="abstract">
Computadores operam sobre vetores finitos de bits interpretados por contratos numéricos explícitos. Notação posicional, conversão de base, faixas sem sinal, interpretação com complemento de dois, aritmética modular, carries, borrows, shifts, máscaras, extensão de sinal e overflow formam a camada matemática que conecta bits booleanos à aritmética de máquina. Este capítulo desenvolve essa camada e a reconcilia com o código atual do ChrisOS: ChrisCPU mascara operações para a largura do operando e calcula flags arquiteturais, ChrisASM interpreta constantes decimais e hexadecimais e emite words little-endian, ChrisArchitectureState armazena campos arquiteturais de largura fixa e o código gráfico empacota canais de cor de um byte.
</div>

## Pré-requisitos e escopo

O pré-requisito necessário é álgebra booleana. Bits individuais já possuem valores 0 ou 1 e as operações booleanas já possuem tabelas-verdade definidas.

Este capítulo acrescenta interpretação numérica.

~~~text
bits booleanos
    ↓
vetor ordenado de bits
    ↓
interpretação numérica posicional
    ↓
aritmética de largura finita
    ↓
instruções e formatos de dados
~~~

O mesmo vetor pode representar inteiro sem sinal, inteiro com sinal, máscara, endereço, cor, campo de instrução ou dados opacos. A aritmética só é definida depois de conhecer interpretação e largura.

## Notação posicional

Um numeral em base b com dígitos d_n ... d_1 d_0 representa:

~~~text
valor = Σ d_i · b^i
~~~

em que cada dígito satisfaz 0 <= d_i < b.

Em decimal:

~~~text
472 = 4·10² + 7·10¹ + 2·10⁰
~~~

Em binário:

~~~text
101101₂
= 1·2⁵ + 0·2⁴ + 1·2³ + 1·2² + 0·2¹ + 1·2⁰
= 45
~~~

Em hexadecimal:

~~~text
0x2D = 2·16 + 13 = 45
~~~

O numeral é notação. O inteiro matemático independe da notação usada para escrevê-lo.

## Pesos posicionais binários

Para um vetor de n bits b_(n-1)...b_0, o valor sem sinal é:

~~~text
U = Σ_(i=0)^(n-1) b_i 2^i
~~~

O bit i possui peso 2^i.

| Bit | Peso |
|---:|---:|
| 7 | 128 |
| 6 | 64 |
| 5 | 32 |
| 4 | 16 |
| 3 | 8 |
| 2 | 4 |
| 1 | 2 |
| 0 | 1 |

O bit menos significativo possui o menor peso. O bit mais significativo possui o maior peso no word de largura fixa.

## Potências de dois e capacidade

Um vetor de n bits possui 2^n padrões distintos.

Na interpretação sem sinal:

~~~text
0 .. 2^n - 1
~~~

| Largura | Padrões | Faixa sem sinal |
|---:|---:|---:|
| 1 | 2 | 0..1 |
| 4 | 16 | 0..15 |
| 8 | 256 | 0..255 |
| 16 | 65.536 | 0..65.535 |
| 32 | 2^32 | 0..4.294.967.295 |
| 64 | 2^64 | 0..18.446.744.073.709.551.615 |

A largura faz parte do contrato. O padrão 11111111 vale 255 apenas sob interpretação sem sinal de 8 bits.

## Agrupamento binário, hexadecimal e octal

Um dígito hexadecimal corresponde exatamente a quatro bits:

~~~text
0xA  = 1010₂
0x3F = 0011 1111₂
~~~

Um dígito octal corresponde a três bits:

~~~text
7₈ = 111₂
~~~

Hexadecimal se alinha naturalmente a words orientados a bytes porque um byte corresponde a dois dígitos hexadecimais.

## Conversão decimal para outra base

Para converter inteiro não negativo para base b, divide-se repetidamente por b e coleta-se o resto.

Para 45 em binário:

~~~text
45 / 2 = 22 resto 1
22 / 2 = 11 resto 0
11 / 2 = 5  resto 1
 5 / 2 = 2  resto 1
 2 / 2 = 1  resto 0
 1 / 2 = 0  resto 1
~~~

Lendo os restos de baixo para cima resulta em 101101₂.

O algoritmo exige O(log_b N) divisões para N positivo.

## Avaliação por Horner

Um numeral pode ser interpretado sem calcular explicitamente cada potência:

~~~text
valor = 0
para cada dígito:
    valor = valor · base + dígito
~~~

Para k dígitos, são O(k) passos aritméticos e O(1) de estado auxiliar.

O parse_u64 atual do ChrisASM segue essa forma para base 10 ou 16 e verifica overflow antes de cada multiplicação-soma.

## Overflow durante parsing

Com valor atual v, próximo dígito d e máximo M, o novo valor seria:

~~~text
v_novo = v·base + d
~~~

Uma precondição segura é:

~~~text
v <= (M - d) / base
~~~

ChrisASM usa esse padrão com M = 18446744073709551615, equivalente a 2^64 - 1.

Esse é o contrato concreto do parser, não uma API universal de parsing de inteiros.

## Aritmética de largura fixa como aritmética modular

Para um word sem sinal de n bits:

~~~text
armazenado(a + b) = (a + b) mod 2^n
~~~

Exemplo em oito bits:

~~~text
250 + 10 = 260
260 mod 256 = 4
~~~

O byte armazenado é 00000100.

O resultado matemático completo e o resultado armazenado de largura finita são objetos diferentes.

## Carry

Para soma sem sinal:

~~~text
a + b = q·2^n + r
~~~

com 0 <= r < 2^n.

O resultado armazenado é r e q representa o carry-out para dois operandos de n bits sem outro carry-in.

Para 250 + 10:

~~~text
260 = 1·256 + 4
~~~

logo o resultado é 4 e o carry é 1.

## Subtração e borrow

Subtração de largura finita também opera módulo 2^n:

~~~text
armazenado(a - b) = (a - b) mod 2^n
~~~

Assim, em oito bits:

~~~text
0 - 1 mod 256 = 255
~~~

Na interpretação sem sinal, uma subtração comum exige borrow quando a < b. A polaridade da flag de carry/borrow é contrato da ISA.

## Interpretação com complemento de dois

Para um padrão de n bits com valor sem sinal U:

~~~text
signed(U) = U             se U < 2^(n-1)
signed(U) = U - 2^n       caso contrário
~~~

A faixa com sinal é:

~~~text
-2^(n-1) .. 2^(n-1)-1
~~~

Para oito bits:

~~~text
0x00 = 0
0x01 = 1
0x7F = 127
0x80 = -128
0xFF = -1
~~~

Os bits não mudam entre interpretações signed e unsigned. O mapeamento muda.

## Negação em complemento de dois

Para um word de n bits x:

~~~text
-x = (~x + 1) mod 2^n
~~~

Exemplo:

~~~text
00000101 = 5
11111010 = complemento bit a bit
11111011 = -5 após somar 1
~~~

O menor valor signed não possui contraparte positiva na mesma largura. Em oito bits, negar -128 não pode produzir +128 representável em signed de 8 bits.

## Overflow signed

Overflow signed é diferente de carry sem sinal.

Na soma, overflow signed ocorre quando os operandos têm o mesmo sinal e o resultado armazenado apresenta sinal oposto.

Exemplo:

~~~text
0x7F + 0x01 = 0x80
~~~

Unsigned 127 + 1 = 128 cabe em oito bits e não gera carry. Signed 127 + 1 excede o máximo 127 e gera overflow signed.

## Independência entre carry e overflow

| Operação de 8 bits | Resultado | Carry | Overflow signed |
|---|---:|---:|---:|
| 1 + 1 | 0x02 | 0 | 0 |
| 0xFF + 1 | 0x00 | 1 | 0 |
| 0x7F + 1 | 0x80 | 0 | 1 |
| 0x80 + 0x80 | 0x00 | 1 | 1 |

Nenhuma flag isolada responde simultaneamente às questões de faixa unsigned e signed.

## Extensão de sinal

Sign extension preserva um valor signed ao aumentar a largura.

~~~text
8 bits:
11111011 = -5

extensão para 16 bits:
11111111 11111011 = -5
~~~

Se o bit de sinal é zero, os novos bits altos são zero. Se é um, os novos bits altos são um.

## Zero extension

Zero extension preserva um valor unsigned:

~~~text
8 bits:
11111011 = 251 unsigned

extensão para 16 bits:
00000000 11111011 = 251
~~~

Aplicar zero extension a um padrão signed negativo muda sua interpretação signed.

## Truncamento

Reduzir largura conserva os bits menos significativos no raciocínio modular comum:

~~~text
truncate_n(x) = x mod 2^n
~~~

Exemplo:

~~~text
0x1234 truncado para 8 bits = 0x34
~~~

Truncamento só é seguro quando perda dos bits altos é impossível ou intencional. Narrowing acidental de endereços, comprimentos ou tamanhos é risco de correção e segurança.


## Operações bitwise versus aritmética

Operações bitwise atuam independentemente em cada posição:

~~~text
AND
OR
XOR
NOT
~~~

Operações aritméticas interpretam o vetor como word numérico e propagam carries ou borrows entre posições.

Por exemplo:

~~~text
0011 + 0001 = 0100
0011 XOR 0001 = 0010
~~~

XOR equivale à soma de um único bit sem carry, mas soma inteira multi-bit não é XOR.

## Máscaras e campos

Uma máscara seleciona ou modifica campos de bits.

Para testar bit k:

~~~text
value & (1 << k)
~~~

Para ligar bit k:

~~~text
value | (1 << k)
~~~

Para limpar bit k:

~~~text
value & ~(1 << k)
~~~

Para extrair um campo:

~~~text
field = (value >> shift) & mask
~~~

A operação é mecânica; o significado vem do contrato de layout do campo.

## Shift à esquerda

Para word unsigned de n bits, deslocar k posições à esquerda corresponde à multiplicação por 2^k módulo a largura quando os bits que saem são descartados:

~~~text
(x << k) mod 2^n
=
x · 2^k mod 2^n
~~~

Bits que saem da largura são perdidos.

Linguagem ou ISA pode impor regras adicionais para o valor do shift count; essas regras vêm do contrato real de execução.

## Shift lógico à direita

Shift lógico à direita insere zeros no topo.

Para valores unsigned:

~~~text
x >> k = floor(x / 2^k)
~~~

na interpretação usual de largura fixa.

## Shift aritmético à direita

Em comportamento típico de x86, shift aritmético de um valor negativo em complemento de dois replica o bit de sinal.

~~~text
11110000 arithmetic >> 2
=
11111100
~~~

Logo shift lógico e aritmético diferem quando o bit mais alto é um.

## Rotações

Rotate recoloca os bits que saem no lado oposto.

~~~text
10000001 rotate-left 1
=
00000011
~~~

Rotação preserva a população de bits, mas não representa multiplicação ou divisão ordinária.

## Notação posicional fracionária

A notação binária se estende abaixo do ponto radix.

~~~text
101.101₂
=
1·2² + 0·2¹ + 1·2⁰ + 1·2^-1 + 0·2^-2 + 1·2^-3
=
5,625
~~~

Nem toda fração decimal possui representação binária finita. O decimal 0,1 é periódico em binário, uma das origens do erro de representação em ponto flutuante.

## Representação fixed-point

Um word fixed-point adota escala implícita.

Se o padrão inteiro I representa:

~~~text
valor = I / 2^F
~~~

então F bits representam precisão fracionária.

Fixed-point pode reutilizar hardware inteiro, mas o contrato precisa definir:

- escala;
- signedness;
- arredondamento;
- largura de multiplicação;
- comportamento de overflow.

A árvore atual revisada do ChrisOS não define uma ABI numérica fixed-point universal.

## Fronteira de floating-point

Floating-point representa sinal, expoente e significando, em vez de um único ponto binário fixo.

Exige tratamento separado de:

- números normalizados e subnormais;
- infinitos;
- NaNs;
- arredondamento;
- exceções.

ChrisArchitectureState contém armazenamento em bytes para XMM, mas isso isoladamente não estabelece semântica completa de floating-point no ChrisCPU.

## Endianness e significância são conceitos distintos

O inteiro de 32 bits:

~~~text
0x12345678
~~~

possui pesos numéricos fixos.

Em memória little-endian, seus bytes aparecem em endereços crescentes como:

~~~text
78 56 34 12
~~~

O valor numérico continua sendo 0x12345678 quando carregado segundo o contrato de byte order correspondente.

Endianness altera a ordem de armazenamento dos bytes; não redefine a significância posicional do inteiro abstrato.

## ChrisArchitectureState e largura numérica

O main atual do ChrisOS define muitos campos arquiteturais como uint64_t em ChrisArchitectureState.

O array de registradores gerais é:

~~~text
uint64_t gpr[16]
~~~

e campos como rax, rcx e rip também usam armazenamento de 64 bits.

Isso não significa que toda operação x86 seja de 64 bits. A semântica da instrução seleciona a largura ativa, enquanto o container permanece largo o suficiente para armazenar o estado arquitetural.

Largura do container e largura do operando são contratos distintos.

## Máscaras de operando no ChrisCPU

O flags.c revisado define conceitualmente:

~~~text
1 byte -> 0xFF
2 bytes -> 0xFFFF
4 bytes -> 0xFFFFFFFF
demais -> 0xFFFFFFFFFFFFFFFF
~~~

chris_flags_bin mascara ambos os operandos antes da aritmética.

Para os valores esperados de operand size, o helper modela:

~~~text
8
16
32
64
~~~

bits.

Ele não é uma biblioteca de inteiros de largura arbitrária.

## Soma alargada no ChrisCPU

Para ADD e ADC, ChrisCPU usa intermediário host unsigned de 128 bits:

~~~text
wide = aa + bb + carry_in
~~~

O código preserva os bits baixos da largura arquitetural e deriva carry dos bits acima dessa largura.

Isso é uma técnica de implementação em software para manter o resultado matemático completo tempo suficiente para calcular resultado e carry arquiteturais menores.

Não significa que um ADD comum do guest produza destino arquitetural de 128 bits.

## Predicados de overflow signed no ChrisCPU

Para soma, o código atual usa predicado equivalente a:

~~~text
((aa XOR r) AND (bb XOR r) AND sign_bit) != 0
~~~

Para subtração:

~~~text
((aa XOR bb) AND (aa XOR r) AND sign_bit) != 0
~~~

São expressões booleanas sobre padrões finite-width em complemento de dois.

Elas separam overflow signed de carry ou borrow unsigned.

## Condições e interpretação numérica

chris_cc_true usa combinações distintas de status para ordenação unsigned e signed.

Conceitualmente:

- CF participa de comparações unsigned;
- SF e OF em conjunto participam de comparações signed;
- ZF representa igualdade.

Os mesmos bits armazenados podem ser ordenados de forma diferente conforme a interpretação.

Signedness não fica permanentemente anexada ao padrão do registrador.

## Parsing numérico no ChrisASM

O parse_u64 revisado aceita texto decimal por padrão e hexadecimal com prefixo 0x ou 0X.

Essa função atualmente não aceita prefixo binário 0b.

Cada dígito é acumulado por:

~~~text
v = v·base + d
~~~

depois da checagem de overflow.

É uma implementação direta da avaliação de numeral posicional.

## Emissão little-endian no ChrisASM

emit_u32 decompõe um valor como:

~~~text
byte 0 = v & 0xFF
byte 1 = (v >> 8) & 0xFF
byte 2 = (v >> 16) & 0xFF
byte 3 = (v >> 24) & 0xFF
~~~

emit_u64 aplica o mesmo princípio a oito bytes.

Assim:

~~~text
interpretação numérica
!=
codificação da ordem dos bytes
~~~

O valor numérico é estabelecido primeiro e depois serializado conforme o contrato de byte order.

## Empacotamento gráfico como aritmética posicional

gfx_rgb empacota três canais de um byte:

~~~text
(red << 16) | (green << 8) | blue
~~~

Os campos ocupam:

~~~text
bits 16..23  red
bits  8..15  green
bits  0..7   blue
~~~

Como não se sobrepõem, o mesmo valor pode ser escrito numericamente como:

~~~text
red·2^16 + green·2^8 + blue
~~~

É aritmética posicional aplicada a layout de dados de software.

## Inicialização e fronteira de fluxo de controle

Sistemas numéricos não possuem inicialização em runtime.

Os fluxos de software relevantes consomem contratos numéricos:

~~~text
texto assembly
    ↓
parse_u64
    ↓
valor uint64_t
    ↓
emit_u32 / emit_u64
    ↓
bytes codificados
~~~

e:

~~~text
operandos decodificados
    ↓
chris_flags_bin
    ↓
resultado mascarado + flags
    ↓
estado da execução da instrução
~~~

A matemática é stateless; os caminhos de software que a usam não são.

## Estado e estruturas de dados

Estruturas relevantes revisadas incluem:

- ChrisArchitectureState para armazenamento de registradores e estado arquitetural;
- buffers estáticos e contadores do assembler;
- armazenamento de resultado fornecido pelo chamador de chris_flags_bin;
- valores uint32_t empacotados por gfx_rgb.

A interpretação do inteiro continua sendo um contrato sobre bits.

Não existe objeto de runtime separado chamado sistema numérico.

## Algoritmos e complexidade

| Operação | Complexidade |
|---|---:|
| parsing de k dígitos com Horner | O(k) |
| formatar inteiro positivo N em base b | O(log_b N) extrações |
| mask/shift de um word nativo | O(1) nesta abstração |
| sign/zero extension de word nativo | O(1) |
| aritmética de precisão arbitrária | fora deste capítulo |

ChrisASM parse_u64 usa O(k) tempo e O(1) estado auxiliar para um token limitado.

## Propriedade de memória

Valores numéricos não possuem memória; o armazenamento possui.

No código revisado:

- ChrisArchitectureState faz parte do estado da CPU emulada;
- chris_flags_bin recebe valores e opcionalmente escreve em ponteiro de resultado fornecido pelo chamador;
- parse_u64 escreve em uint64_t fornecido pelo chamador;
- emitters do assembler alteram buffers estáticos do assembler;
- gfx_rgb retorna um valor e não aloca memória.

A regra aritmética e a regra de ownership são separadas.

## Fronteira de ABI e formato

Uma ABI ou formato persistente precisa definir informação suficiente para reconstruir o significado inteiro:

- largura;
- signedness;
- byte order;
- posição do campo;
- escala em fixed-point;
- valores reservados;
- comportamento de wrap/overflow quando relevante.

A expressão "campo inteiro" é insuficiente para um contrato binário durável.

O capítulo de representação de dados aplica essas regras a pointers, estruturas, objetos, filesystems e dispositivos.

## Concorrência

Aritmética pura sobre valores locais não possui race de estado compartilhado.

Atualização em memória compartilhada é outro problema.

~~~text
x = x + 1
~~~

não é automaticamente atômico só porque a adição tem semântica matemática definida.

A implementação realiza leitura, cálculo e escrita, salvo quando uma primitiva atômica ou sincronização fornece contrato mais forte.

Portanto:

~~~text
semântica aritmética
!=
atomicidade de memória
~~~

## Modos de falha

| Erro | Consequência |
|---|---|
| largura errada | truncamento ou máscara errada |
| signedness errada | comparação/faixa incorreta |
| wrap unsigned não verificado | erro de tamanho/endereço |
| sign extension incorreta | valor negativo errado |
| zero extension incorreta | interpretação signed alterada |
| shift count inválido | fault/resultado dependente da ISA/linguagem |
| byte order errado | valor codificado corrompido |
| overflow no parser | constante inválida aceita ou rejeitada incorretamente |
| escalas fixed-point misturadas | resultado plausível, porém incorreto |

Os bits podem parecer válidos mesmo quando a interpretação está errada.

## Implicações de segurança

Erros inteiros são uma fronteira central de segurança em sistemas.

Padrões perigosos incluem:

- overflow na multiplicação do tamanho de alocação;
- truncamento em bounds check;
- mistura signed/unsigned em comparações;
- narrowing de pointers;
- erros em máscaras derivadas de shifts;
- wrap ao somar comprimentos.

Comportamento modular unsigned pode ser determinístico e ainda assim semanticamente inseguro.

Código que controla tamanhos de memória ou endereços deve demonstrar a faixa antes de depender de resultado finite-width.

## Considerações de desempenho

Para inteiros nativos de largura fixa, operações individuais são tratadas como O(1) no nível algorítmico deste capítulo, embora latência e throughput reais dependam da microarquitetura.

Conversão de base depende do comprimento da entrada.

Parsing de k dígitos é O(k); formatação de inteiro positivo N em base b exige O(log_b N) extrações de dígito.

Bit tricks não devem substituir aritmética mais clara apenas por parecerem de baixo nível. Código gerado e medições são a evidência correta para otimização.

## Contexto arquitetural Intel atual

O conjunto público Intel 64 and IA-32 Software Developer's Manual foi atualizado em setembro de 2026, e a página da Intel lista a versão 093.

O Volume 1 descreve arquitetura básica e ambiente de programação; o Volume 2 define a semântica das instruções.

Esses manuais estabelecem contratos arquiteturais para larguras de registradores, aritmética, shifts e flags em processadores Intel 64/IA-32.

ChrisCPU deve ser validado contra a semântica arquitetural específica que pretende emular, e não contra uma intuição genérica sobre aritmética binária.

## Evidência de validação deste capítulo

O checker determinístico específico valida:

~~~text
101101₂ = 45
0x2D = 45

máximo unsigned de n bits = 2^n - 1

(250 + 10) mod 256 = 4

signed_8(0xFF) = -1
signed_8(0x80) = -128

sign_extend_8_to_16(0xFB) = 0xFFFB
zero_extend_8_to_16(0xFB) = 0x00FB

left shift unsigned módulo a largura

parsing por Horner

empacotamento RGB:
red·2^16 + green·2^8 + blue
~~~

O checker também verifica âncoras atuais em flags.c, chris_arch.h, chrisasm.c e graphics.c.

Ele não afirma conformidade completa da aritmética x86.

## Limitações atuais

Este capítulo não cobre integralmente:

- algoritmos de inteiros de precisão arbitrária;
- semântica IEEE 754;
- decimal floating-point;
- aritmética multiprecisão criptográfica;
- aritmética SIMD por lanes;
- saturating arithmetic;
- modelo completo de conversão de inteiros da linguagem C;
- todas as instruções aritméticas x86.

Esses temas pertencem a capítulos posteriores ou especializados.

## Fronteira do roadmap

A transição curricular é:

~~~text
níveis lógicos
    ↓
álgebra booleana
    ↓
sistemas numéricos e aritmética finite-width
    ↓
representação e layout de dados
    ↓
circuitos aritméticos combinacionais
    ↓
registradores e machine code visíveis pela ISA
~~~

O capítulo de representação de dados já existente depende deste porque largura, signedness, máscaras e byte order exigem modelo numérico explícito de bits finitos.

## Proveniência da revisão

As afirmações ligadas à implementação foram conciliadas contra ChrisOS main da3df29cb397932c43d32373871fb9380e688ade.

Fontes revisadas:

- chrisvm/cpu/emulator/flags.c;
- chrisvm/chris_arch.h;
- compiler/chrisasm/chrisasm.c;
- kernel/gfx/graphics.c.

Símbolos revisados:

- chris_flags_bin;
- chris_cc_true;
- ChrisArchitectureState;
- parse_u64;
- emit_u32;
- emit_u64;
- gfx_rgb.

A página atual dos Intel 64 and IA-32 Software Developer's Manuals foi consultada como referência arquitetural primária; a Intel lista o conjunto como versão 093 em setembro de 2026. Material do comitê WG14 foi consultado para contexto contemporâneo de representação de inteiros em C23, mas este capítulo não usa discussões do comitê como substituto de um tratamento completo da norma da linguagem.
