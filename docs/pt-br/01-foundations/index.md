---
id: volume-01-foundations
lang: pt-br
type: volume-index
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Fundamentos físicos, elétricos, digitais e algorítmicos

<div class="abstract">Este volume percorre a cadeia causal da matéria e da carga elétrica até campos, circuitos, dispositivos semicondutores, lógica digital, estado armazenado, representação matemática, estruturas de dados e algoritmos. Os capítulos posteriores de kernel, compiladores, gráficos, redes e emulação não devem depender de uma primitiva não explicada.</div>

## Escopo

Este volume não é um panorama introdutório. Ele é a camada de pré-requisitos de todo o corpus do ChrisOS.

A progressão pretendida é:

~~~text
matéria
  ↓
carga
  ↓
campo elétrico e potencial
  ↓
tensão / corrente / resistência / potência
  ↓
leis de circuitos
  ↓
capacitores / indutores / transientes / CA
  ↓
integridade de sinal e alimentação
  ↓
bandas / junções / eletrostática MOS
  ↓
MOSFET / CMOS
  ↓
níveis lógicos e noise margins
  ↓
lógica booleana
  ↓
circuitos combinacionais
  ↓
circuitos aritméticos
  ↓
lógica sequencial
  ↓
registradores / clocks / células de memória
  ↓
representação
  ↓
estruturas de dados
  ↓
algoritmos
  ↓
arquitetura de computadores
  ↓
ChrisOS
~~~

<figure class="figure">
<img src="../../assets/diagrams/foundations-chain.svg" alt="Cadeia de fundamentos">
<figcaption>A documentação progride de portadores físicos para estado estruturado e algoritmos executáveis.</figcaption>
</figure>

## Sequência física e elétrica

O currículo passa a tratar os seguintes assuntos como pré-requisitos explícitos, e não assumptions escondidas:

1. Matéria, estrutura atômica e carga elétrica.
2. Campo elétrico, força, potencial elétrico e energia potencial.
3. Tensão, corrente, resistência, resistividade, energia e potência.
4. Lei de Ohm, leis de Kirchhoff e modelos de circuitos concentrados.
5. Capacitância, indutância e energia armazenada em campos elétricos/magnéticos.
6. Transientes RC, RL e RLC e significado de constante de tempo.
7. Senoides, frequência, fase, impedância e raciocínio no domínio da frequência.
8. Indução eletromagnética e fundamentos de transformadores.
9. Linhas de transmissão, sinalização diferencial, reflexões e terminação.
10. Ruído, grounding, corrente de retorno, crosstalk e signal integrity.
11. Power delivery, regulação, desacoplamento e transientes de alimentação.
12. Estrutura cristalina, bandas de energia e estatística de portadores.
13. Dopagem, junções p-n e interfaces semicondutoras.
14. Eletrostática do capacitor MOS.
15. MOSFET e chaveamento CMOS.
16. Potência dinâmica/estática, capacitância e delay CMOS.
17. Thresholds lógicos, noise margins, fan-out e restauração elétrica.

## Sequência digital

Somente depois da camada elétrica explícita o currículo avança por:

1. Álgebra booleana.
2. Lógica combinacional.
3. Somadores, circuitos aritméticos e ULA.
4. Lógica sequencial.
5. Latches e flip-flops.
6. Metaestabilidade e restrições de timing.
7. Registradores, contadores e máquinas de estados.
8. Clock, propagação, setup/hold e clock domains.
9. Células SRAM e DRAM.

## Sequência matemática e de software

A ponte seguinte torna explícita a matemática necessária para software:

1. Sistemas numéricos e aritmética binária.
2. Conjuntos, relações e funções.
3. Provas, invariantes e indução.
4. Vetores e números complexos quando sistemas/eletrônica precisarem deles.
5. Representação de dados, layout e ponteiros.
6. Análise de complexidade.
7. Recorrências e análise amortizada.
8. Arrays, listas, stacks e queues.
9. Hash tables.
10. Trees, heaps e tries.
11. Grafos e union-find.
12. Bitmaps, rings e free lists.
13. Sorting e searching.
14. Algoritmos de grafos.
15. Algoritmos de strings e parsing.
16. Algoritmos aplicados ao ChrisOS.

## Modelo obrigatório de raciocínio

Todo capítulo posterior deve poder ser lido pela cadeia:

~~~text
mecanismo físico
    ↓
comportamento elétrico
    ↓
abstração digital
    ↓
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
comportamento observável do ChrisOS
~~~

Um subsistema não está documentado completamente quando apenas sua API é descrita.

## Ferramentas matemáticas entram quando se tornam necessárias

O corpus não precisa se tornar um curso genérico de matemática.

Álgebra, análise dimensional, vetores, números complexos, derivadas, integrais e equações diferenciais são introduzidos quando passam a ser necessários para derivar um resultado elétrico, algorítmico ou arquitetural.

A regra é que nenhuma equação pode depender de matemática essencial não explicada.

## Regra de ligação com o ChrisOS

Todo fundamento deve reencontrar a implementação.

Exemplos:

~~~text
campo elétrico
  -> controle do canal MOS
  -> porta CMOS
  -> flip-flop
  -> registrador
  -> registrador arquitetural
  -> estado do ChrisCPU

capacitância
  -> energia de chaveamento / delay
  -> timing de clock e memória
  -> comportamento de cache/DRAM
  -> assumptions de performance visíveis ao ChrisOS

bitmap
  -> representação de recurso
  -> estado de páginas do PMM
  -> pmm_alloc()

ring buffer
  -> invariante produtor/consumidor
  -> VirtIO queues / job queues

tree / graph
  -> hierarquia / dependências
  -> algoritmos de filesystem, compiler e build
~~~

Teoria que nunca retorna a um subsystem implementado ou explicitamente futuro não é suficiente.

## Regra de leitura

As camadas inferiores não precisam ser memorizadas. Precisam estar disponíveis, precisas e ligadas quando uma camada superior depender delas.

O currículo machine-readable é a autoridade para a ordem dos capítulos. Capítulos ausentes são intencionalmente contabilizados como gaps até existirem nos dois idiomas.
