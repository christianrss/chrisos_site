---
id: chrisc-clvm
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - compiler/chrisc/chrisc.c
  - compiler/clvm/clvm_vm.c
  - compiler/lang_pipeline.c
  - kernel/lang/clvm_sys.c
symbols: []
depends_on:
  - compiler-pipeline
related:
  - native-toolchain
---

# ChrisC e o modelo de execução CLVM

## Caminho da linguagem

ChrisC é a linguagem do projeto usada por aplicações e pela direção de tooling/self-hosting. Seu caminho principal compila para bytecode CLVM, não para o mesmo pipeline nativo do KCC.

```text
fonte ChrisC
     ↓
compiler / language pipeline
     ↓
imagem CLVM
     ↓
interpreter ou JIT
     ↓
bridge de syscalls
     ↓
kernel
```

## Por que bytecode

VM de bytecode oferece alvo menor que uma ISA completa. O compiler emite operações CLVM e runtime escolhe interpretação ou JIT.

Isso facilita memória guest controlada e instrumentação, mas cria obrigação de equivalência semântica entre backends.

## Memória guest

Endereços CLVM são offsets guest, não ponteiros do kernel. Syscalls precisam validar ranges antes de tocar memória privilegiada. É uma fronteira de proteção implementada por runtime.

## Interpreter e JIT

Interpreter atualiza estado da VM operação por operação. JIT traduz subset para x86-64. ADD, memória, faults e demais semânticas precisam coincidir; testes diferenciais são especialmente importantes.

## Syscalls

`kernel/lang/clvm_sys.c` liga aplicações a gráficos, arquivos, input, tempo, áudio e outros serviços. Números e layouts formam uma ABI do ecossistema ChrisC.

## Ownership por slot

File descriptors, shaders, mouse capture e outros recursos associados ao slot precisam ser destruídos no fechamento. Teardown faz parte da arquitetura da VM.

## CLVM e processo nativo

Processo ELF usa page tables e ring boundary. App CLVM usa guest memory e boundary de runtime. Ambos isolam por mecanismos diferentes e não devem ser descritos como equivalentes.
