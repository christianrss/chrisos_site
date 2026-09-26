---
title: "07 Processos e syscalls"
description: "Fronteiras de execução nativa, espaços de endereçamento, syscalls e o contrato separado de execução da CLVM."
---

<div class="retro-kicker">FUNDAMENTOS DO SISTEMA · 07</div>

# Processos e syscalls

<div class="lang-switch"><a href="../../processes-syscalls/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

Fronteiras de execução nativa, espaços de endereçamento, syscalls e o contrato separado de execução da CLVM.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>kernel/metal/proc.c · kernel/metal/syscall.c · kernel/metal/elf.c</code>
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

[08 ChrisFS e persistência](./chrisfs-persistence.md)
