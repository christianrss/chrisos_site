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
