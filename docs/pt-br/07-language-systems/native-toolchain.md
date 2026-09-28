---
id: native-toolchain
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chrisld.c
symbols:
  - kcc_compile_source
depends_on:
  - compiler-pipeline
  - elf-linking
related:
  - self-hosting-bootstrap
---

# KCC, ChrisAsm, ChrisO e ChrisLd

## Objetivo

O toolchain nativo busca reduzir dependência de GCC/NASM/ld do host para código x86-64 nativo, culminando no kernel.

```text
subset C de kernel
      ↓
     KCC
      ↓
assembly / objeto
      ↓
ChrisAsm / ChrisO
      ↓
   ChrisLd
      ↓
    ELF64
```

## Evidência atual do KCC

`docs/KCC_STATUS.md` atual está à frente de auditorias antigas. O host gate compila todos os `kernel/metal/*.c` e verifica símbolos e propriedades de machine code.

Também cobre volatile, layout de structs, parte de control flow, templates de inline assembly e builtins atômicos usados pelo kernel.

Ainda assim, o mesmo documento registra probe de apenas 50 dos 112 C units do makefile.

## Por que isso não é SH4

Kernel bootável exige todas as translation units, assembly stubs e linkedição correta. Restam constructs de linguagem, unidades gráficas, `idt_stubs.asm`, colocação das Limine requests e ELF final interno.

```text
"compila kernel/metal" ≠ "compila o kernel inteiro"
"gera ELF"             ≠ "gera ELF equivalente"
"host gate passa"      ≠ "self-host bootado"
```

## ChrisAsm

Assembler precisa mapear instruções para bytes exatos e registrar symbols/relocations. Para kernel deve cobrir instruções privilegiadas, tamanhos, addressing modes, sections e relocations realmente usadas.

## ChrisO

ChrisO é o formato de objeto próprio. Ele precisa representar seções, símbolos e relocations suficientes para combinar unidades independentes.

Formato próprio torna a semântica de linker explícita e controlável pelo projeto.

## ChrisLd

Linker combina objetos, resolve símbolos, aplica relocations e produz program headers ELF compatíveis com Limine e o layout do kernel.

O objetivo é equivalência semântica de boot, endereços, permissões e símbolos, não necessariamente bytes idênticos ao GNU ld.

## Validação diferencial

Comparação forte inclui símbolos, relocations, headers ELF, alinhamento, markers Limine, entry point e comportamento no QEMU.

## Fronteira de self-hosting

A auditoria atual mantém SH4, SH5 e SH6 como não provados. O status só deve mudar após gates de kernel internamente produzido, instalação/reboot e reprodução mais ampla definida pelos níveis do projeto.
