---
id: ohm-kirchhoff-circuits
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - voltage-current-resistance-power
related:
  - capacitance-inductance
  - rc-rlc-transients
  - ac-signals-frequency-impedance
  - noise-grounding-signal-integrity
  - power-delivery-regulation
---

# Ohm's law, Kirchhoff's laws and circuit analysis

<div class="abstract">
Ohm's law supplies a constitutive relation for an ideal linear resistor; Kirchhoff's current and voltage laws connect element relations through circuit topology. Together they convert a network diagram into a solvable system of equations. This chapter develops node and branch models, nodal and mesh analysis, equivalent networks, dependent sources, power checks, singular cases, numerical solution and the boundary between lumped circuit theory and the physical hardware later consumed by ChrisOS.
</div>

## Prerequisites and scope

The prerequisite chapter defined voltage as potential difference, current as charge-transfer rate, resistance, conductance, energy, power and the passive sign convention.

This chapter adds network structure.

A circuit model consists of:

~~~text
components
    terminal constitutive relations

topology
    which terminals share nodes

reference choices
    voltage polarities and current directions
~~~

The equations are not determined by component values alone. Two sets of identical resistors connected differently are different networks.

The analysis below assumes lumped elements. Each ideal node is treated as one potential, wires are ideal unless resistance is explicitly modeled, and electromagnetic propagation is neglected. Later chapters introduce capacitance, inductance, transients, frequency dependence and transmission-line effects.

This is a physics and circuit-theory prerequisite. No current ChrisOS source behavior is claimed here.

## The ideal linear resistor

For an ideal resistor,

~~~text
v = R i
~~~

under a stated voltage polarity and current direction.

Equivalently,

~~~text
i = G v
G = 1/R
~~~

where (G) is conductance.

For (R>0) under passive sign convention,

~~~text
p = vi = i²R = v²/R >= 0
~~~

so the ideal resistor dissipates energy rather than generating it.

This law is linear:

~~~text
i(v1 + v2) = i(v1) + i(v2)
i(kv) = k i(v)
~~~

for fixed (R). That linearity is what later permits superposition and matrix solution.

Real resistive devices may be nonlinear, temperature dependent, frequency dependent or noisy. The symbol "resistor" in a schematic means the selected model, not every microscopic property of the physical object.

## Nodes, branches and loops

A **node** is a set of interconnected ideal conductors treated as one electrical potential.

A **branch** connects two nodes through one or more modeled elements and carries a branch current.

A **path** is an ordered sequence of connected branches.

A **loop** is a closed path.

The topology can be represented as a graph:

~~~text
        R1
  A o--/\/\--o B
    |          |
   R2         R3
    |          |
  C o----------o
~~~

Electrical nodes are graph vertices and branches are graph edges.

This mapping matters because Kirchhoff's laws are fundamentally topological constraints combined with conservation laws.

## Kirchhoff's current law

Kirchhoff's current law, KCL, states that the algebraic sum of currents at an ideal lumped node is zero:

~~~text
Σ i_k = 0
~~~

A sign convention must be chosen. For example, currents entering a node may be positive and currents leaving negative.

Equivalent form:

~~~text
sum of currents entering
=
sum of currents leaving
~~~

KCL is a circuit-scale consequence of charge conservation when charge accumulation at the ideal node is either absent or represented explicitly by storage elements.

For a node with currents (i_1) and (i_2) entering and (i_3) leaving,

~~~text
i1 + i2 - i3 = 0
~~~

therefore

~~~text
i3 = i1 + i2
~~~

KCL does not say currents are physically identical in all branches. It constrains their signed sum at the connection.

## Node charge accumulation

If charge can accumulate in an explicitly modeled capacitive structure, KCL still holds when the capacitor current is included.

The deeper conservation statement is

~~~text
rate of charge accumulation
=
net current into the region
~~~

Ideal nodal analysis treats storage through element branch currents rather than by abandoning charge conservation.

At sufficiently high frequency, displacement current and distributed electromagnetic effects require more careful field models. The lumped equations remain an approximation whose validity depends on scale.

## Kirchhoff's voltage law

Kirchhoff's voltage law, KVL, states that the algebraic sum of voltage changes around a closed lumped loop is zero:

~~~text
Σ v_k = 0
~~~

This follows from consistent node potentials in the ordinary lumped/quasi-static model. If a branch voltage is defined as

~~~text
v_ab = V_a - V_b
~~~

then summing differences around

~~~text
A -> B -> C -> A
~~~

gives

~~~text
(V_A - V_B)
+ (V_B - V_C)
+ (V_C - V_A)
= 0
~~~

by cancellation.

The sign of each term depends on traversal direction and the defined voltage polarity.

## KVL and time-varying magnetic flux

The simple scalar-potential form of KVL has a physical boundary.

Faraday's law states that a time-varying magnetic flux can produce a non-conservative electric field:

~~~text
∮ E · dl = - dΦ_B/dt
~~~

Circuit theory handles such behavior through inductive elements and coupled models. It is therefore more precise to treat ordinary KVL as a property of the selected lumped model rather than as an unrestricted statement that every closed physical path in every electromagnetic condition has zero field integral.

## Series resistors

Two resistors are in series when the same branch current necessarily passes through both and their intermediate node has no other current path in the model.

For

~~~text
V -- R1 -- R2 -- reference
~~~

KVL gives

~~~text
V = iR1 + iR2
  = i(R1 + R2)
~~~

so

~~~text
R_eq = R1 + R2
~~~

For (n) series resistors,

~~~text
R_eq = Σ R_k
~~~

The condition is topological. Components being visually adjacent in a drawing does not prove that they are in series.

## Voltage divider

For two series resistors across source (V),

~~~text
i = V/(R1 + R2)
~~~

and the voltage across (R2) is

~~~text
V2 = i R2
   = V R2/(R1 + R2)
~~~

The familiar divider equation assumes that the output is not loaded by an additional branch.

If a load (R_L) is connected in parallel with (R2), the lower effective resistance becomes

~~~text
R_low = R2 || R_L
~~~

and the divider ratio changes.

A high-impedance measurement instrument approximates the unloaded condition; a low input resistance can materially alter it.

## Parallel resistors

Two resistors are in parallel when both terminals of one connect to the same pair of nodes as the other. They therefore have the same voltage.

KCL gives

~~~text
i_total
=
V/R1 + V/R2
=
V(1/R1 + 1/R2)
~~~

so

~~~text
1/R_eq = 1/R1 + 1/R2
~~~

For two resistors,

~~~text
R_eq = (R1 R2)/(R1 + R2)
~~~

For conductances,

~~~text
G_eq = Σ G_k
~~~

which is often algebraically simpler.

## Current divider

For two parallel resistors with total current (I),

~~~text
I1 = I * G1/(G1 + G2)
~~~

or, expressed in resistance form,

~~~text
I1 = I * R2/(R1 + R2)
I2 = I * R1/(R1 + R2)
~~~

Current preferentially flows through the larger conductance, not because current "chooses the easiest path" as an independent agent, but because the common node voltage and branch constitutive laws jointly determine the branch currents.

## Independent voltage and current sources

An ideal independent voltage source imposes

~~~text
v = V_s
~~~

while an ideal independent current source imposes

~~~text
i = I_s
~~~

The network determines the conjugate quantity.

Real sources have limits and internal dynamics. An ideal voltage source can mathematically supply any current required by a compatible ideal network; that is a modeling abstraction, not a physical capability.

Some ideal source combinations are inconsistent. Two ideal voltage sources of different values connected directly in parallel demand contradictory voltages. Two ideal current sources in series can similarly impose incompatible currents depending on topology.

A solver must detect such contradictions instead of returning arbitrary values.

## Dependent sources

A dependent source has a value controlled by another circuit variable.

Common ideal forms are:

| Type | Relation |
|---|---|
| voltage-controlled voltage source | (v = mu v_x) |
| current-controlled voltage source | (v = r i_x) |
| voltage-controlled current source | (i = g v_x) |
| current-controlled current source | (i = eta i_x) |

Dependent sources model amplification, transconductance and controlled behavior.

They are essential in small-signal device models and cannot generally be "turned off" during superposition in the same way as independent sources.

## Nodal analysis

Nodal analysis chooses one reference node and solves for the remaining node voltages.

For a resistor connecting nodes (a) and (b),

~~~text
i_ab = (V_a - V_b)/R
     = G(V_a - V_b)
~~~

Apply KCL at each unknown node.

Example:

~~~text
        R1
Vs o--/\/\--o Vx
             / \
           R2   R3
           |     |
         ref    ref
~~~

At (V_x),

~~~text
(Vx - Vs)/R1
+ Vx/R2
+ Vx/R3
= 0
~~~

Collecting terms,

~~~text
Vx(1/R1 + 1/R2 + 1/R3)
=
Vs/R1
~~~

This is already a one-equation linear system.

## Conductance-matrix form

For a resistive network, nodal equations can be assembled as

~~~text
G v = b
~~~

where

- (v) is the vector of unknown node voltages;
- (G) is the nodal conductance matrix;
- (b) contains current injections and source contributions.

For an ordinary passive resistor between nodes (i) and (j), conductance (g) contributes:

~~~text
G[i,i] += g
G[j,j] += g
G[i,j] -= g
G[j,i] -= g
~~~

if neither node is the chosen reference.

This local "stamping" rule makes circuit assembly systematic.

For a connected passive resistive network with a proper reference and no contradictory ideal constraints, the conductance matrix has useful structural properties. Degenerate topology or floating subcircuits can make it singular.

## Floating networks and singular matrices

A network has an undefined absolute potential if no reference or equivalent constraint fixes it.

For example, two resistors connected only to each other and to no reference may have determined voltage differences under some source conditions while all node potentials can shift by the same constant.

In matrix form, that gauge freedom appears as singularity.

Solver failure can therefore indicate a modeling problem rather than arithmetic failure.

Typical causes include:

- no reference node;
- disconnected floating component;
- contradictory ideal sources;
- redundant constraints;
- topology that leaves a degree of freedom unconstrained.

## Modified nodal analysis

Pure nodal analysis handles resistors and current sources naturally. Ideal voltage sources between unknown nodes introduce currents that are not directly expressible as conductance times voltage.

Modified nodal analysis, MNA, augments the unknown vector with selected branch currents.

Conceptually:

~~~text
[ G  B ] [v] = [i]
[ C  D ] [j]   [e]
~~~

The added variables let ideal voltage-source constraints coexist with KCL equations.

SPICE-family simulators use variants of this general approach because many practical element models can be assembled through sparse matrix stamps.

The exact matrix formulation depends on the supported devices and analysis mode.

## Mesh and loop analysis

For planar circuits, mesh analysis can instead choose independent loop currents and apply KVL.

If two meshes share a resistor, the resistor current is the algebraic difference of mesh currents.

A two-mesh system may take the form

~~~text
(R1 + R3) I1 - R3 I2 = V1
-R3 I1 + (R2 + R3) I2 = V2
~~~

Mesh analysis can be compact when the number of meshes is smaller than the number of non-reference nodes. It is less universal than nodal/MNA for arbitrary graph structures and many source types.

## Topological independence of equations

Writing KCL at every node creates one redundant equation because the sum of all node equations is zero for a closed network. Choosing a reference and solving the remaining node equations removes that redundancy.

Likewise, not every possible loop equation is independent.

Graph theory explains the counts. For a connected graph with

~~~text
N nodes
B branches
~~~

a spanning tree has (N-1) branches, and the number of independent fundamental loops is

~~~text
B - N + 1
~~~

This is why systematic circuit analysis chooses independent equations rather than indiscriminately writing every possible KCL and KVL relation.

## Superposition in linear circuits

In a linear network, the response caused by multiple independent sources equals the sum of the responses caused by each source separately.

To zero an independent source in an ideal linear model:

~~~text
ideal voltage source -> replace by 0 V -> short circuit
ideal current source -> replace by 0 A -> open circuit
~~~

Dependent sources remain active because they are part of the network's constitutive relations.

Superposition applies to voltages and currents, not directly to nonlinear quantities such as power:

~~~text
P(total response)
!=
Σ P(each response)
~~~

in general.

## Thévenin equivalent

A linear two-terminal network viewed from a port can often be replaced by an ideal voltage source (V_{th}) in series with resistance (R_{th}).

The open-circuit port voltage is

~~~text
V_th = V_oc
~~~

For a network containing only independent sources and resistors, (R_{th}) can be found by zeroing the independent sources and computing the resistance seen into the port.

With dependent sources, a test source is typically required. Apply a test voltage (V_t) and measure resulting current (I_t):

~~~text
R_th = V_t/I_t
~~~

provided the linear port model is well defined.

## Norton equivalent

The Norton equivalent uses a current source (I_n) in parallel with (R_n).

For the same linear port,

~~~text
R_n = R_th
V_th = I_n R_th
~~~

and (I_n) equals the short-circuit current under the appropriate sign convention.

Thévenin and Norton equivalents preserve terminal behavior at the selected port. They do not preserve internal branch currents, internal power distribution or hidden state.

## Maximum power transfer boundary

For a purely resistive source represented by (V_{th}) and (R_{th}>0), a resistive load receives maximum power when

~~~text
R_L = R_th
~~~

This condition does **not** maximize efficiency. At that point the ideal source resistance dissipates the same power as the load, so only half of the power delivered by the Thévenin source reaches the load.

Power-delivery systems normally seek low source impedance rather than deliberate impedance matching for maximum resistive power transfer. The appropriate design goal depends on the domain.

## Source transformation

An ideal voltage source (V_s) in series with (R) has the same external two-terminal (i)-(v) relation as an ideal current source

~~~text
I_s = V_s/R
~~~

in parallel with the same (R).

This transformation is valid at the port under the linear ideal model. It does not imply the internal physical sources are identical.

## Delta-wye transformations

Some resistor networks cannot be reduced using only simple series and parallel combinations.

A delta network with resistances (R_{ab}, R_{bc}, R_{ca}) can be converted to an equivalent wye. Let

~~~text
S = R_ab + R_bc + R_ca
~~~

then

~~~text
R_a = R_ab R_ca / S
R_b = R_ab R_bc / S
R_c = R_bc R_ca / S
~~~

The reverse transformation is also possible.

For large networks, systematic nodal analysis is usually clearer and less error-prone than repeated symbolic topology reduction.

## Power balance as a validation invariant

A solved ideal network should satisfy energy conservation.

Using one consistent sign convention,

~~~text
Σ p_k = 0
~~~

over all elements at each instant for a lumped network with no omitted storage or field term.

Resistors absorb positive power under passive sign convention. Sources delivering energy contribute negative power.

Power balance is an excellent debugging check because a wrong sign, branch current or voltage polarity often appears immediately as a nonzero residual.

In finite-precision computation, the residual is tested against a scale-aware tolerance rather than exact binary zero.

## Linear-system solution

After circuit assembly, numerical solution is a linear algebra problem.

For dense (n 	imes n) systems, ordinary Gaussian elimination requires approximately

~~~text
Theta(n^3)
~~~

arithmetic operations and

~~~text
Theta(n^2)
~~~

storage.

Circuit matrices are often sparse because each component connects only a few nodes. Sparse direct solvers can exploit this structure, though fill-in may create new nonzero matrix entries during factorization.

Large circuit simulators therefore care about:

- sparse storage formats;
- node ordering;
- pivoting;
- fill-reduction heuristics;
- matrix conditioning;
- repeated factorization across related operating points.

The best algorithm depends on network structure and analysis type.

## Conditioning and numerical error

A mathematically solvable circuit can still be numerically difficult.

Large ratios between conductances can produce ill-conditioned matrices. For example, mixing gigaohm and micro-ohm paths in the same network may cause small voltage changes to depend on subtraction of much larger quantities.

Partial pivoting reduces some numerical hazards but cannot make a fundamentally ill-conditioned model well conditioned.

Good numerical practice includes:

- consistent units;
- scale-aware tolerances;
- residual checks;
- avoiding gratuitous extreme ideal values;
- reporting singular or near-singular systems rather than silently regularizing them.

## DC operating point and nonlinear extensions

The equations in this chapter are linear when all elements are linear.

Real transistor circuits contain nonlinear relations. A common strategy for nonlinear DC analysis is to solve

~~~text
F(x) = 0
~~~

iteratively, often by Newton-Raphson or a related method. Each iteration linearizes the nonlinear devices and solves a linear system.

That belongs to device and simulator theory, not to the resistor-only model here.

The key connection is that Kirchhoff topology remains while element constitutive relations become nonlinear.

## Data structures for a software circuit solver

A simple educational solver might represent:

~~~text
Node {
    id
    is_reference
}

Resistor {
    node_a
    node_b
    conductance
}

CurrentSource {
    node_a
    node_b
    current
}

VoltageSource {
    node_a
    node_b
    voltage
}
~~~

Assembly maps node identifiers to matrix rows.

A sparse implementation may use coordinate triplets during stamping and compress them into CSR/CSC storage before factorization.

The important invariants are:

- exactly one reference per connected solved component, unless an equivalent constraint is imposed;
- component endpoints refer to valid nodes;
- matrix dimensions match the unknown vector;
- stamps use one consistent polarity convention;
- units are normalized before assembly.

These are general modeling principles, not current ChrisOS data structures.

## Complexity of topology construction

If a network contains (B) two-terminal branches, building adjacency information is ordinarily (O(B)).

Stamping a resistor adds a constant number of matrix contributions, so raw assembly is also (O(B)) before sparse-structure management.

Solving usually dominates.

For sparse matrices, complexity depends strongly on graph structure and elimination ordering; there is no single (O(n^k)) bound that predicts all practical circuit networks well.

## Failure and recovery behavior in software

A robust circuit solver should distinguish:

| Condition | Appropriate response |
|---|---|
| invalid component value | reject input with location/context |
| missing node | reject topology |
| no reference / floating network | report singular topology |
| conflicting ideal constraints | report inconsistency |
| near-singular matrix | report conditioning warning/failure |
| numerical overflow/NaN | stop and surface the operation |
| power residual too large | mark solution invalid |
| unsupported nonlinear element | reject rather than approximate silently |

Returning numbers from a failed factorization is worse than failing explicitly because the output can look plausible while violating circuit constraints.

## Privilege, concurrency and ABI boundary

Circuit equations have no CPU privilege level and no intrinsic ABI.

A future simulator inside the ChrisOS ecosystem could have concurrency, memory ownership and file-format concerns, but they would belong to that concrete implementation.

Likewise, hardware telemetry registers used by an operating system are not derived from KCL at runtime. The silicon and board implement physical behavior, while software sees abstracted register, interrupt and power-management interfaces.

## Relationship to digital hardware

A digital logic gate is not an ideal resistor network, but circuit analysis remains foundational.

At different abstractions:

~~~text
field/device physics
    ↓
transistor I-V behavior
    ↓
effective pull-up/pull-down networks
    ↓
node capacitance and transient voltage
    ↓
logic threshold crossing
    ↓
digital state
~~~

Static CMOS analysis often reasons about conducting paths and effective resistances, while timing requires capacitance and transient behavior.

The next chapters add that missing storage and time dependence.

## Relationship to ChrisOS

ChrisOS executes after many lower abstraction layers have compressed physical circuit behavior into digital hardware contracts.

Representative chain:

~~~text
power-delivery and transistor network
    ↓
logic gates and storage elements
    ↓
CPU/device architectural state
    ↓
MMIO, memory, interrupts and instructions
    ↓
ChrisOS
~~~

ChrisOS does not solve Kirchhoff equations while servicing an interrupt.

If future ChrisOS components expose sensor values such as voltage, current or power, those values will be interpreted through device specifications and driver code. Such implementation claims must be documented in source-bound subsystem chapters.

## Validation evidence

The executable checker associated with this chapter validates representative deterministic cases:

- series resistance;
- parallel resistance;
- unloaded and loaded voltage dividers;
- current division;
- a two-node nodal solution;
- KCL residual;
- KVL residual;
- Thévenin/Norton equivalence;
- power balance;
- singularity of a deliberately floating conductance matrix using a determinant check for the small teaching case;
- bilingual documentation anchors.

These tests verify arithmetic examples and editorial invariants. They are not a SPICE implementation or physical-hardware conformance suite.

## Current limitations

This chapter intentionally excludes:

- capacitor and inductor state equations;
- differential-equation transients;
- AC phasors and complex impedance;
- transmission-line propagation;
- nonlinear semiconductor device equations;
- noise models;
- stochastic tolerances;
- PCB parasitics;
- concrete ChrisOS source implementation.

Those subjects remain separate so their state, frequency, geometry and source evidence are not hidden inside a generic circuit overview.

## Roadmap boundary

The next curriculum stages extend the network equations rather than replacing them:

~~~text
Ohm + KCL + KVL
    ↓
capacitor and inductor constitutive relations
    ↓
differential equations and transients
    ↓
phasor/impedance representation
    ↓
distributed interconnect and signal integrity
    ↓
semiconductor switching and power delivery
~~~

Every later abstraction must preserve the conservation constraints while adding the state or physical detail required by the problem.

## Revision provenance

Reviewed against ChrisOS `main` revision `da3df29cb397932c43d32373871fb9380e688ade`.

`sources` and `symbols` are intentionally empty because this chapter makes no current ChrisOS implementation claim. The revision records corpus provenance and the implementation boundary.
