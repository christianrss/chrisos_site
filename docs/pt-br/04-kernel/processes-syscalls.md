---
id: processes-syscalls
lang: pt-br
type: technical-chapter
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/syscall.c
  - kernel/metal/elf.c
  - kernel/metal/user_enter.c
symbols:
  - proc_create
  - proc_destroy
  - proc_switch
depends_on:
  - virtual-memory
  - kernel-model
related:
  - elf-linking
---

# Processos, address spaces e system calls

## Abstração de processo

Processo agrupa identidade de execução, recursos e address space. Isolamento normalmente exige contexto de memória virtual protegido e entrada controlada no kernel.

`Proc` no ChrisOS registra uso/aliveness, estado, CR3, contabilização de memória, heap break, nome e páginas pertencentes ao processo.

## Criação

`proc_create` procura slot livre e chama `mm_clone_kernel_space`. O novo CR3 recebe mappings de kernel necessários para execução privilegiada e uma porção de usuário distinta.

Uma stack de usuário é committed antes do sucesso. Se a inicialização falha, destruction desfaz os recursos já adquiridos. Isso é ownership: toda sequência de alocações precisa de unwind.

## Mapping e ownership

Mapear página física e possuí-la são conceitos diferentes. Uma frame pode aparecer em vários mappings; unmap não determina automaticamente quem deve liberar a frame.

ChrisOS registra leaf frames de usuário no array do processo. `proc_map_owned` grava virtual/physical após mapping bem-sucedido e `proc_destroy` pode depois desfazer e liberar.

## Troca de CR3

Switch de processo altera a raiz ativa de page tables. `proc_switch` atualiza identidade global e chama `mm_switch`.

A implementação atual possui invariante explícita: user process switching é BSP-only. Chamar em AP causa panic. É uma limitação arquitetural atual, não apenas otimização ausente.

## Ponteiros de usuário

Ponteiro recebido de ring 3 não é automaticamente seguro. Pode estar fora da faixa, unmapped, sem bit USER, cruzar página ou não permitir escrita.

O código de syscall valida e traduz spans página a página em `user_copy` e acessa a frame pela região direta do kernel, evitando dereference cego de endereço fornecido pelo processo.

## System calls

Syscall é uma transição controlada para serviço privilegiado. O contrato inclui mecanismo de entrada, número/argumentos, validação, ownership/permissão, erros e retorno ao user mode.

A instrução de transição é apenas parte da ABI.

## Descritores e ownership

Slots de arquivos nativos guardam owner process. Teardown chama `syscall_close_owner`. O mesmo padrão aparece em sockets e outros recursos.

## Contenção de faults

`proc_record_fault` registra PID, thread, CR2 e RIP e marca o processo afetado como não alive. O objetivo é conter falha de usuário em vez de transformar todo fault em kernel panic.

## Escopo do scheduler

Timer pode indicar slice due, mas isso não equivale a scheduler preemptivo multiprocessador completo. Maturidade deve ser descrita pelos estados, caminhos de switch, restrições de CPU e testes reais.

## Processos nativos e CLVM

ChrisOS possui contratos distintos. ELF nativo usa page tables e rings; aplicações ChrisC executam em slots CLVM e usam outra interface de syscalls. Seus modelos de memória e falha não devem ser misturados.
