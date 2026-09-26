---
title: "14 Self-hosting"
description: "O que self-hosting significa no ChrisOS, quais estágios de bootstrap existem e quais provas são necessárias para fechar cada estágio."
---

<div class="retro-kicker">LINGUAGENS E FERRAMENTAS · 14</div>

# Self-hosting

<div class="lang-switch"><a href="../../self-hosting/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

O que self-hosting significa no ChrisOS, quais estágios de bootstrap existem e quais provas são necessárias para fechar cada estágio.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>README.md · docs/ · relevant source and tests on main</code>
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

[15 Bibliotecas, módulos e GC](./libraries-modules-gc.md)
