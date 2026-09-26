---
title: "29 Fontes e política de revisão"
description: "A regra de que código e gates reproduzíveis têm prioridade sobre documentação antiga, sempre vinculando a documentação a branch e revisão."
---

<div class="retro-kicker">REFERÊNCIA · 29</div>

# Fontes e política de revisão

<div class="lang-switch"><a href="../../sources-policy/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

A regra de que código e gates reproduzíveis têm prioridade sobre documentação antiga, sempre vinculando a documentação a branch e revisão.

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

[30 Glossário técnico](./glossary.md)
