---
id: combinational-logic
lang: en
type: technical-chapter
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - boolean-algebra
related:
  - arithmetic-circuits
  - logic-sequential
---

# Combinational circuits

<div class="abstract">
Combinational logic converts Boolean functions into connected hardware whose outputs depend on present inputs but not intentionally on previous state. The important structures are not isolated gates but reusable networks: multiplexers, decoders, encoders, comparators, shifters and arithmetic slices. These structures form the data-routing and transformation fabric from which processor datapaths are built.
</div>

## Definition and assumptions

A combinational circuit implements a function:

Y = F(X)

where X is the current input vector and Y the resulting output vector. There is no intended storage element in the function definition.

Physical circuits still have propagation delay. During an input transition, intermediate nodes may temporarily reflect old and new values at different times. Therefore “depends only on present inputs” is a logical steady-state statement, not a claim of instantaneous physical response.

A combinational block is usually characterized by:

- logic function;
- input and output width;
- propagation delay;
- input capacitance and output drive;
- power;
- permitted loading and operating conditions.

## Gates as networks rather than primitives

AND, OR, XOR and NOT provide a convenient symbolic vocabulary. In a cell-based implementation, larger gates and compound functions may be available directly. A synthesis tool maps a Boolean network into a technology-specific set of cells.

Therefore a diagram containing an XOR symbol is an abstraction over potentially many transistors. Conversely, a library may provide an AOI or OAI cell that computes a multi-operation expression in one characterized structure.

The engineering unit at this layer is the **logic function plus timing**, not a philosophical commitment to one gate vocabulary.

## Multiplexers

A multiplexer selects one of several input values according to a select signal.

For a two-input one-bit multiplexer:

Y = (¬S ∧ A) ∨ (S ∧ B)

If S = 0, Y = A. If S = 1, Y = B.

Wide multiplexers apply the same selection to vectors. They are fundamental to CPUs because a datapath constantly chooses sources:

- register versus immediate operand;
- sequential RIP versus branch target;
- ALU result versus loaded memory;
- normal writeback versus exception state;
- one execution-unit result among several producers.

A crossbar is conceptually a larger routing network built from related selection structures.

## Decoders

A decoder converts an encoded input into one-of-many select lines. A 2-to-4 decoder, for example, maps two input bits into four mutually exclusive outputs.

| A1 | A0 | D0 | D1 | D2 | D3 |
|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 1 | 0 | 0 | 0 |
| 0 | 1 | 0 | 1 | 0 | 0 |
| 1 | 0 | 0 | 0 | 1 | 0 |
| 1 | 1 | 0 | 0 | 0 | 1 |

Decoders select registers, memory rows, execution cases and control paths. Instruction decoding is a far more complex form in which opcode bits, prefixes, mode and current privilege all influence the resulting control signals.

## Encoders and priority encoders

An encoder performs the inverse abstraction: several input lines are represented by a smaller binary code.

A simple encoder assumes that at most one input is active. A **priority encoder** defines which code wins when multiple inputs are asserted.

Priority encoding appears naturally in interrupt controllers, arbitration and exception-selection logic. The priority relation is part of architectural behavior; if two events occur simultaneously, the system must know which one is handled first.

## Comparators

Equality of two n-bit vectors can be computed by checking every corresponding bit and combining results:

equal = AND over all i of NOT(Ai XOR Bi)

Magnitude comparison can be constructed from the most significant bit downward: the first differing bit determines which unsigned value is larger.

Signed comparison requires interpreting the sign bit and the two's-complement ordering rules. CPUs expose these distinctions through condition codes and branch instructions.

## Shifters

A logical shifter moves bit positions while inserting zeros. An arithmetic right shift preserves the sign bit for two's-complement signed values. Rotates move bits around the end.

A simple shift-by-one can be hardwired. Variable shifts require selection among multiple displacement distances. A **barrel shifter** commonly uses staged multiplexing so an n-bit value can be shifted by an arbitrary amount in logarithmic selection depth.

This structure demonstrates a central hardware idea: an operation that appears atomic in an instruction set is often a carefully organized combinational network.

## Adders as combinational networks

A half adder produces:

sum = A XOR B

carry = A AND B

A full adder includes carry-in:

sum = A XOR B XOR Cin

carry-out = (A AND B) OR (Cin AND (A XOR B))

Chaining full adders yields a ripple-carry adder. Its worst-case delay grows with word width because carry may propagate through every stage.

Faster adders reorganize the Boolean problem. Carry-lookahead, prefix adders and related structures compute generate and propagate information so distant carries can be resolved with lower depth.

## Two's-complement subtraction

For fixed-width two's-complement arithmetic:

A − B = A + (¬B + 1)

A datapath can therefore reuse its adder by complementing B and setting carry-in to 1. The same physical unit can support addition, subtraction, increment, comparison-related flag generation and address arithmetic.

This reuse is typical of datapath design: multiplexing around a powerful shared combinational block reduces area at the cost of routing and scheduling complexity.

## ALU slice concept

An arithmetic logic unit combines arithmetic and Boolean functions selected by control signals.

A conceptual one-bit slice may compute candidate results for AND, OR, XOR and addition, then select one result through a multiplexer. Wide ALUs repeat or restructure slices while managing carry and flags.

The architectural instruction “ADD RAX,RBX” is therefore several abstractions above the circuit: instruction decode generates control, register storage presents operands, the ALU transforms them and writeback captures the result.

## Propagation delay

Every gate has finite delay. In a multi-level network, the longest sensitized path from an input transition to a required stable output is the critical combinational path.

If a path passes through many dependent logic stages, clock frequency may need to be lowered or the computation split across pipeline stages.

Delay is not determined by gate count alone. Fan-out, wire capacitance, cell size, placement and signal slew matter. This is why a Boolean-minimal expression is not automatically a timing-optimal implementation.

## Hazards and glitches

Different logic paths can have different delays. When inputs change, the output may briefly take an incorrect intermediate value even if initial and final Boolean states are correct. These temporary pulses are hazards or glitches.

Synchronous systems often tolerate internal combinational glitches provided outputs settle before sampling and the glitches do not reach asynchronous controls or cause excessive power. Some circuits require hazard-free design because even a short pulse can trigger an event.

The distinction between logical correctness and temporal correctness is fundamental.

## Fan-out and buffering

An output drives the gate capacitance and wire capacitance of downstream inputs. Large fan-out slows transitions and may violate timing.

Buffers create a staged drive tree. Clock networks are an extreme example: one logical clock source must reach enormous numbers of state elements with tightly controlled skew, so specialized clock-tree structures are used.

Control signals such as reset and enable can face similar distribution problems.

## Tri-state logic and buses

Traditional shared buses may use tri-state outputs that can drive 0, drive 1 or enter a high-impedance state. Only one source should actively drive a shared line at a time.

Inside modern integrated logic, multiplexers often replace large internal tri-state buses because they are easier to synthesize and time. Board-level buses and specific interfaces may still use tri-state behavior.

A bus is not inherently a protocol. It is a collection of signal paths; protocol rules define ownership, timing and meaning.

## Combinational feedback is special

A combinational network is normally expected to be acyclic. Uncontrolled feedback can oscillate or settle unpredictably. Deliberately adding feedback changes the problem into sequential or asynchronous state-holding behavior.

This boundary is important for both hardware description languages and reasoning. A loop in software control flow is normal; a zero-delay loop in a combinational netlist is usually an error unless modeling a specific analog or asynchronous structure.

## Connection to CPU datapaths

A simple processor datapath can be decomposed into storage plus combinational blocks:

    register file
        ↓
    operand multiplexers
        ↓
    ALU / shifter / comparator
        ↓
    address or result selection
        ↓
    writeback multiplexer
        ↓
    register file

The combinational fabric answers “what should the next values be?” Sequential storage answers “when do those values become the machine's state?”

The next chapters therefore split in two directions: arithmetic circuits deepen the transformation blocks, while latches and flip-flops explain how computed values are captured and preserved.
