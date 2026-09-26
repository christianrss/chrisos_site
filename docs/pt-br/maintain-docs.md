---
title: "31 Manter esta documentação"
description: "Como agentes e contribuidores devem atualizar Markdown, verificar a main e evitar transformar roadmap em afirmação factual."
---

<div class="retro-kicker">REFERÊNCIA · 31</div>

# Manter esta documentação

<div class="lang-switch"><a href="../../maintain-docs/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

Como agentes e contribuidores devem atualizar Markdown, verificar a main e evitar transformar roadmap em afirmação factual.

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

[32 Atlas do kernel](./kernel-atlas.md)
