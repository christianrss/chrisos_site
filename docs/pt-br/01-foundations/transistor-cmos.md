---
id: transistor-cmos
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - atom-semiconductor
related:
  - logic-sequential
---

# Transistores e lógica CMOS

## MOSFET como dispositivo controlado

Um MOSFET possui terminais gate, source, drain e body. A porta é separada do semicondutor por um dielétrico isolante. A tensão no gate modifica o campo elétrico na região do canal e controla se source e drain ficam ligados por um caminho suficientemente condutivo.

Para raciocínio digital, o transistor é aproximado como uma chave controlada por tensão. A aproximação é deliberadamente incompleta: dispositivos reais possuem tensão de limiar, resistência finita, capacitância, fuga, tempo de transição e comportamento corrente-tensão não linear. Essas propriedades analógicas determinam potência e velocidade, enquanto o projeto lógico normalmente trabalha com o estado binário restaurado.

## NMOS e PMOS

Lógica CMOS combina dispositivos complementares.

- Um **NMOS** conduz fortemente quando seu gate está alto em relação ao source.
- Um **PMOS** conduz fortemente na condição complementar.

O inversor CMOS canônico usa uma rede PMOS de pull-up e uma rede NMOS de pull-down.

```text
             VDD
              │
            PMOS
entrada ───── gate
              │──── saída
entrada ───── gate
            NMOS
              │
             GND
```

Com entrada baixa, o PMOS tende a conduzir e o NMOS tende a bloquear, levando a saída para a alimentação alta. Com entrada alta ocorre o inverso. A propriedade central é a restauração: uma entrada baixa válida produz saída fortemente alta e uma entrada alta válida produz saída fortemente baixa.

## Comportamento estático e dinâmico

CMOS estático idealmente consome pouca corrente direta entre os rails quando estabilizado porque um lado da rede complementar está desligado. Chips reais possuem fuga, mas grande parte da potência ativa vem de carregar e descarregar capacitâncias durante transições.

Uma aproximação útil é

```text
P_dynamic ≈ α C V² f
```

onde `α` representa atividade de chaveamento, `C` capacitância efetiva, `V` tensão de alimentação e `f` frequência. Isso explica por que frequência, tensão e quantidade de transistores interagem fortemente com consumo de CPUs.

Propagação não é instantânea. Uma mudança na entrada leva tempo finito para modificar a saída. Caminhos combinacionais possuem atraso máximo e circuitos síncronos escolhem um período de clock que permita estabilização antes da próxima captura de estado.

## Redes CMOS e funções booleanas

Redes de transistores em série e paralelo implementam condições lógicas. NAND e NOR são particularmente naturais em CMOS. Como qualquer uma delas é funcionalmente completa, funções booleanas arbitrárias podem ser compostas.

Álgebra booleana abstrai tensão e geometria. Variáveis assumem 0 ou 1 e operações NOT, AND e OR descrevem relações lógicas estáveis.

| Forma booleana | Significado |
|---|---|
| `¬A` | NOT |
| `A ∧ B` | AND |
| `A ∨ B` | OR |
| `¬(A ∧ B)` | NAND |
| `¬(A ∨ B)` | NOR |

Uma expressão booleana não é a mesma coisa que sua implementação física. Um somador pode ser descrito com XOR, AND e OR; uma biblioteca de células transforma depois essas portas em redes de transistores caracterizadas por timing e potência.

## Fan-out, carga e integridade

A saída de uma porta dirige capacitância finita. Muitos destinos aumentam carga e tornam transições mais lentas. Projeto físico usa buffers, dimensionamento e células caracterizadas.

Margem de ruído permite perturbações pequenas sem mudar o nível interpretado. Se um sinal entra na região indefinida próximo ao instante de amostragem, elementos sequenciais podem entrar em metastabilidade. Sincronização reduz o risco, mas não elimina a origem analógica.

## De CMOS a máquinas com estado

Lógica combinacional produz saídas em função apenas das entradas atuais. Um computador precisa preservar estado anterior. Realimentação entre portas cria circuitos biestáveis; elementos de armazenamento controlados por clock restringem quando novos valores são aceitos. Surgem latches, flip-flops, registradores, contadores, caches e interfaces de memória.

No nível visível ao software, RAX parece conter 64 bits exatos. Fisicamente ele depende de circuitos de retenção de estado dentro de uma microarquitetura muito maior. A ISA oculta essa topologia.

## Fronteira do ChrisOS

ChrisOS começa acima dessa fronteira. O kernel e o ChrisCPU não modelam MOSFETs individuais. ChrisCPU emula **estado arquitetural**: registradores, flags, registradores de controle, efeitos de memória e exceções. Isso é possível porque a ISA x86-64 define uma abstração estável sobre o circuito físico.

O próximo capítulo constrói o caminho entre portas, armazenamento de estado, unidades aritméticas e máquinas sincronizadas.
