---
id: volume-01-foundations
lang: pt-br
type: volume-index
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Fundamentos

<div class="abstract">Esta coleção contém os pré-requisitos físicos, elétricos, digitais, matemáticos e algorítmicos utilizados pelo restante do corpus do ChrisOS. Sua ordem interna segue o currículo canônico, não a cronologia dos diretórios do repositório.</div>

## Posição no corpus

Os fundamentos estabelecem as camadas de abstração exigidas pelos capítulos posteriores de arquitetura, kernel, compiladores, gráficos, redes e emulação.

~~~text
matéria e modelos físicos
    ↓
ferramentas matemáticas exigidas pelo modelo físico
    ↓
carga, campo e potencial elétrico
    ↓
grandezas de circuito e leis de rede
    ↓
armazenamento de energia, transientes e comportamento AC
    ↓
sinalização de alta velocidade, ruído e alimentação
    ↓
eletrostática de semicondutores
    ↓
MOSFET e CMOS
    ↓
níveis lógicos e abstração booleana
    ↓
aritmética combinacional
    ↓
estado sequencial, clocks e células de memória
    ↓
representação
    ↓
complexidade
    ↓
estruturas de dados
    ↓
algoritmos de sistemas
~~~

## Fundamentos físicos e elétricos

A sequência canônica é:

1. matéria, átomos e modelos físicos;
2. vetores e números complexos necessários posteriormente à análise de campos e circuitos;
3. carga, campo, potencial e energia;
4. tensão, corrente, resistência, energia e potência;
5. lei de Ohm, leis de Kirchhoff e análise de circuitos;
6. capacitância e indutância;
7. transientes RC, RL e RLC;
8. sinais AC, fase, frequência e impedância;
9. indução eletromagnética e transformadores;
10. linhas de transmissão e sinalização diferencial;
11. ruído, grounding e integridade de sinal;
12. power delivery, regulação e desacoplamento.

Esses tópicos definem as hipóteses físicas usadas depois para semicondutores e comportamento digital.

## Fundamentos de semicondutores e lógica digital

A sequência de dispositivos é:

1. estrutura cristalina, bandas e dopagem;
2. junções p-n;
3. eletrostática do capacitor MOS;
4. MOSFET e CMOS;
5. delay e potência CMOS;
6. thresholds lógicos, fan-out e noise margins;
7. álgebra booleana;
8. sistemas numéricos binários;
9. lógica combinacional;
10. circuitos aritméticos;
11. lógica sequencial;
12. latches e flip-flops;
13. registradores, contadores e máquinas de estados;
14. temporização de clock;
15. SRAM e DRAM.

A transição entre faixas elétricas de tensão e estado booleano abstrato permanece explícita.

## Representação e algoritmos

A sequência de fundamentos de software é:

1. matemática discreta: conjuntos, relações e funções;
2. prova, invariantes e indução;
3. representação de dados, layout e ponteiros;
4. complexidade algorítmica e modelos de custo;
5. recursão, recorrências e análise amortizada;
6. arrays, listas, stacks e queues;
7. hash tables;
8. trees, heaps e tries;
9. grafos e disjoint-set union;
10. bitmaps, rings e free lists;
11. sorting e searching;
12. algoritmos de grafos;
13. algoritmos de strings e parsing;
14. algoritmos implementados pelo ChrisOS.

## Regra de dependência

Um capítulo posterior pode assumir um conceito somente quando:

- o conceito foi definido em capítulo curricular anterior;
- o próprio capítulo contém uma derivação local limitada e suficiente;
- o conceito aparece explicitamente como referência futura, sem ser tratado como conhecimento já estabelecido.

Essa regra elimina saltos implícitos entre abstrações físicas, matemáticas e de software.

## Ligação com a implementação

A teoria fundamental é conectada à implementação atual na primeira fronteira adequada.

| Fundamento | Implementação posterior |
|---|---|
| aritmética de largura finita e flags | semântica aritmética do ChrisCPU |
| registradores e máquinas de estado | ChrisArchitectureState |
| bitmaps | estado de alocação do PMM |
| ring buffers | filas VirtIO e job queues do kernel |
| trees/grafos | estruturas de filesystem, compiler e dependências |
| carga/capacitância/timing | limites físicos sob modelos de memória e CPU |

Um capítulo de fundamentos não afirma que o ChrisOS implementa diretamente o dispositivo físico subjacente.

## Regra de evidência

Capítulos físicos e matemáticos distinguem:

- equações e definições normativas;
- hipóteses do modelo;
- exemplos numéricos ilustrativos;
- limites do modelo;
- consequências arquiteturais posteriores;
- ligação com o ChrisOS atual.

Afirmações vinculadas ao source são revision-bound. Afirmações de dispositivos físicos usam referências técnicas primárias, não inferências do código do kernel.
