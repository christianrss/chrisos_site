---
id: volume-01-foundations
lang: pt-br
type: volume-index
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Fundamentos físicos, digitais e algorítmicos

<div class="abstract">O volume de fundamentos percorre a cadeia completa de abstrações: matéria e carga, dispositivos semicondutores, lógica booleana, estado, memória e clock; em seguida avança para representação de dados, estruturas de dados e análise de algoritmos. O objetivo é impedir que capítulos posteriores de kernel, compiladores, gráficos e emulação dependam de primitivas não explicadas.</div>

## Escopo

Este volume não é um resumo introdutório. Ele estabelece os modelos necessários para reconstruir como um computador evolui de estado físico para estado de software. A metade física explica por que estado discreto confiável pode existir. A metade de software explica como esse estado é representado, organizado e transformado com eficiência.

<figure class="figure">
<img src="../../assets/diagrams/foundations-chain.svg" alt="Cadeia dos fundamentos">
<figcaption>A documentação avança de portadores físicos para manipulação algorítmica de estado estruturado.</figcaption>
</figure>

## Sequência física e digital

1. Átomo, carga elétrica e física de semicondutores.
2. Estrutura cristalina, bandas de energia e dopagem.
3. Junções P-N e interfaces semicondutoras.
4. MOSFETs e CMOS.
5. Álgebra booleana e representação lógica.
6. Circuitos combinacionais.
7. Somadores, ULAs e aritmética binária.
8. Lógica sequencial e estado armazenado.
9. Latches, flip-flops e metaestabilidade.
10. Registradores, contadores e máquinas de estados.
11. Clock, propagação e temporização.
12. SRAM, DRAM e células de memória.

## Sequência de fundamentos de software

13. Representação de dados, layout de memória e ponteiros.
14. Análise de algoritmos e modelos de custo de sistemas.
15. Estruturas de dados para software de sistemas.
16. Algoritmos utilizados pelo ChrisOS.

## Modelo obrigatório de raciocínio

Todo capítulo posterior de implementação deve ser legível pela mesma cadeia:

    representação
        ↓
    estrutura de dados
        ↓
    invariante
        ↓
    algoritmo
        ↓
    complexidade e localidade
        ↓
    sincronização / ownership
        ↓
    comportamento observável

Um subsistema não está completamente documentado quando apenas sua API é descrita. O leitor precisa compreender por que a representação interna suporta a operação, quanto o algoritmo custa, como concorrência altera os invariantes e qual código fonte concretiza o mecanismo.

## Regra de leitura

As camadas inferiores não precisam ser memorizadas, porém os termos são definidos antes do uso. Diagramas mostram topologia e transições; tabelas registram contratos e complexidade; equações representam relações quantitativas; capítulos ligados ao código separam teoria geral da implementação atual do ChrisOS.
