---
id: logic-sequential
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - transistor-cmos
related:
  - cpu-datapath-isa
---

# Lógica, estado e circuitos sequenciais

## Lógica combinacional

Um circuito combinacional não possui memória intencional: sua saída é função das entradas presentes. Decoders, multiplexadores, comparadores, encoders e unidades aritméticas pertencem a essa classe.

Um full adder de um bit recebe `A`, `B` e carry-in `Cin` e produz soma `S` e carry-out `Cout`:

```text
S    = A XOR B XOR Cin
Cout = (A AND B) OR (Cin AND (A XOR B))
```

A repetição e otimização desse elemento produz adição inteira de várias larguras. Subtração pode ser representada por complemento de dois e reutilizar hardware de soma.

## Multiplexadores e fluxo controlado

Um multiplexador escolhe um valor entre vários conforme bits de controle. CPUs os utilizam para selecionar operandos da ALU, próximo program counter, valores de writeback e vetores de exceção.

Um datapath pode ser entendido como armazenamento de dados, transformação combinacional e roteamento multiplexado.

## Realimentação e estado armazenado

Quando a saída influencia a entrada futura, um circuito pode preservar informação. Portas realimentadas podem produzir bistabilidade: duas configurações estáveis representam um bit.

Latch é sensível a nível. Flip-flop é normalmente modelado como captura na borda de clock. Implementações físicas variam, mas o objetivo arquitetural é controlar a transição de estado em um evento definido.

O agrupamento de elementos forma um **registrador**. Um registrador arquitetural de 64 bits representa conceitualmente 64 bits de estado, embora CPUs de alto desempenho possam renomear e reorganizar o armazenamento físico.

## Sistemas síncronos

Em projeto síncrono, estado muda em eventos de clock enquanto lógica combinacional calcula entre eles.

```text
registradores ──> lógica combinacional ──> registradores
     ▲                                      │
     └────────────── clock ─────────────────┘
```

O maior caminho combinacional relevante limita a frequência máxima junto com setup time, incerteza de clock e margens.

Clock não torna a física intrinsecamente discreta; ele fornece disciplina para coordenar circuitos analógicos com propagação finita.

## Máquinas de estados

Uma máquina de estados combina estado armazenado e lógica de próximo estado:

```text
next_state = F(current_state, input)
output     = G(current_state, input)
```

Unidades de controle, protocolos de barramento e controladores de dispositivos podem ser descritos assim. O mesmo conceito reaparece em drivers, que espelham estados como reset, negotiated, ready, active e failed.

## Matrizes de memória

Registradores são adequados para estado pequeno e muito acessado. Armazenamento maior utiliza células mais densas em matrizes. SRAM aparece tipicamente em caches; DRAM usa células mais densas e exige refresh.

Software vê endereços e bytes, não células individuais. Controladores, caches, coerência e MMUs ficam entre uma instrução e os dispositivos físicos de memória.

## Da máquina de estados ao processador

Um processador precisa repetir conceitualmente:

```text
buscar instrução
      ↓
decodificar operação
      ↓
ler estado necessário
      ↓
executar transformação
      ↓
acessar memória quando necessário
      ↓
gravar resultado arquitetural
      ↓
selecionar próximo endereço
```

Uma CPU simples pode representar esse fluxo diretamente como estados. Um core out-of-order moderno sobrepõe e reordena trabalho internamente, preservando o comportamento exigido pela ISA.

Essa distinção é central para emulação. ChrisCPU não precisa reproduzir pipelines, preditores, caches ou timing de uma CPU comercial; precisa reproduzir o **contrato arquitetural** suficiente para que o guest observe registradores, memória, flags e exceções corretos.

## Estado arquitetural e microarquitetural

Estado arquitetural é visível ao software pela ISA: registradores gerais, RIP, RFLAGS, control registers, MSRs selecionados e memória.

Estado microarquitetural é específico da implementação: reorder buffers, caches de micro-ops, tabelas de predição, registradores físicos e filas internas.

Um sistema operacional é escrito contra estado arquitetural. Desempenho depende fortemente da microarquitetura, mas correção funcional não deve depender de detalhes ocultos salvo quando uma especificação de plataforma os expõe.
