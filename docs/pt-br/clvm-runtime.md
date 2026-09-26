---
title: "10 Runtime CLVM"
description: "Formato do bytecode, memória da VM, modelo de execução, ponte de syscalls e contrato entre programas ChrisC e o kernel."
---

<div class="retro-kicker">LINGUAGENS E FERRAMENTAS · 10</div>

# Runtime CLVM

<div class="lang-switch"><a href="../../clvm-runtime/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

Formato do bytecode, memória da VM, modelo de execução, ponte de syscalls e contrato entre programas ChrisC e o kernel.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>compiler/clvm/ · kernel/lang/clvm_sys.c</code>
</div>

## Modelo de evidência

| Rótulo | Significado |
|---|---|
| **Implemented** | Existe implementação rastreável no código. |
| **Host-tested** | Há teste reproduzível executado fora do guest. |
| **QEMU-proven** | Há gate que prova o comportamento no perfil emulado declarado. |
| **Hardware-proven** | Há evidência em máquina física identificada. |

!!! note "Regra editorial"
    Roadmap, intenção arquitetural e implementação observada são categorias diferentes. Quando houver divergência, registre a revisão e a evidência.

## Próxima leitura

[11 JIT e caminhos de execução](./jit-execution.md)
