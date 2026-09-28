---
id: virtualization-chrishv
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - chrisvm/cpu/hv/chrishv.c
  - chrisvm/cpu/hv/vmx/vmx.h
  - chrisvm/cpu/hv/svm/svm.h
symbols: []
depends_on:
  - chrisvm-chriscpu
related:
  - x86-64-memory-privilege
---

# Virtualização assistida por hardware e a fronteira ChrisHV

## Diferença para interpretação

ChrisCPU implementa instruções em software. VT-x e AMD-V permitem executar guest diretamente na CPU até um evento provocar VM exit controlado.

## Estado guest/host

Hardware mantém contexto guest separado do host/hypervisor. VM entry ativa guest; exit retorna motivo e estado.

## Tradução de segundo nível

Guest pode fazer virtual → guest physical. Hypervisor ainda precisa guest physical → host physical via EPT/NPT.

```text
guest virtual
    ↓
guest physical
    ↓ EPT/NPT
host physical
```

## Device model continua necessário

Virtualização de CPU não elimina devices, timers, interrupts e mapa de memória. Por isso ChrisHV é backend de ChrisVM, não substituto da máquina.

## Estado atual

A arquitetura atual deixa VMX/SVM não funcionais. Selecionar ChrisHV deve falhar explicitamente em vez de usar fallback silencioso.

## Implementação futura

São necessários capability detection, inicialização segura, VMCS/VMCB por vCPU, import/export de `ChrisArchitectureState`, virtualização de memória, exit dispatch, injection de IRQ, integração de I/O, teardown e testes de equivalência com ChrisCPU.

O objetivo é intercambiar backend preservando a mesma plataforma virtual.
