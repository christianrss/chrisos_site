---
id: x86-64-memory-privilege
lang: pt-br
type: technical-chapter
volume: 02-computer-architecture
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/gdt.c
  - kernel/metal/idt.c
  - kernel/metal/mm.c
  - chrisvm/chris_arch.h
symbols:
  - mm_switch
depends_on:
  - cpu-datapath-isa
related:
  - virtual-memory
  - kernel-model
---

# Memória, privilégio e estado arquitetural x86-64

## Long mode

O long mode x86-64 fornece registradores gerais de 64 bits e grande espaço virtual mantendo partes importantes da herança da arquitetura. Segmentação é reduzida para endereçamento comum, mas seletores, descriptor tables e metadados de privilégio continuam relevantes para transições e exceções.

ChrisOS liga seu kernel no higher half. O linker script define `kstart` como entry point e coloca o kernel em endereço virtual canônico alto, sem assumir identidade entre endereço físico e virtual.

## Endereços canônicos

Nem todo padrão de 64 bits é um endereço virtual x86-64 válido. Implementações suportam uma largura definida e bits superiores não utilizados precisam formar a extensão canônica do bit significativo implementado. "Inteiro de 64 bits" e "endereço virtual válido" não são conceitos idênticos.

O código de processos do ChrisOS rejeita endereços de usuário acima de sua fronteira configurada; o kernel ocupa a região alta.

## Rings e privilégio

A arquitetura define níveis 0 a 3. Sistemas convencionais usam ring 0 para kernel e ring 3 para programas de usuário.

Privilégio faz parte do estado de execução e dos descritores. Um programa ring 3 não pode simplesmente reescrever CR3 ou desabilitar interrupções. A CPU verifica a permissão da operação.

```text
programa de usuário
   │ ring 3
   │ transição controlada
   ▼
entrada no kernel
   │ ring 0
   ├── valida pedido
   ├── acessa estado privilegiado
   └── retorna
```

## Control registers

| Registrador | Papel |
|---|---|
| CR0 | controles globais de modo e proteção, incluindo paging |
| CR2 | endereço linear que causou page fault |
| CR3 | base física da estrutura superior de tradução e bits de controle definidos pela arquitetura |
| CR4 | recursos arquiteturais adicionais, inclusive ligados a paging |

`mm_switch` no ChrisOS escreve CR3 ao trocar address spaces. Uma única instrução de máquina muda o contexto de tradução usado pelos acessos virtuais seguintes.

## Descriptor tables

A GDT fornece descritores e seletores ainda necessários para convenções de código/dados, privilégio e TSS. A IDT associa vetores de exceção e interrupção a descritores de handlers.

Uma entrada da IDT não é apenas um ponteiro de função. Ela codifica offset, selector, gate type e propriedades de presença/privilégio. O processador realiza a transferência conforme esses campos.

## Exceções

Exceções são consequências síncronas da execução: invalid opcode, general protection e page fault. Interrupções de dispositivos são assíncronas em relação ao fluxo atual.

O kernel precisa preservar estado suficiente para diagnosticar ou recuperar, determinar a origem e então retomar, encerrar o processo ou falhar de modo controlado.

## Estado arquitetural no ChrisCPU

ChrisCPU representa o estado observável por instruções guest: registradores gerais, instruction pointer, flags e estado de controle/segmentos exigido pelo subset implementado.

O valor documental é direto: o kernel ChrisOS mostra como **usar** x86-64; ChrisCPU mostra como **implementar o comportamento visível** da mesma arquitetura.

## Arquitetura não é microarquitetura

Esses contratos não obrigam um emulador a reproduzir speculative execution, register renaming ou caches comerciais. Tais mecanismos afetam timing e desempenho, mas não o resultado arquitetural básico das instruções suportadas.
