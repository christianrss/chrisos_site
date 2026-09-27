---
id: vectors-complex-numbers-systems
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on: [atom-semiconductor]
related: [electric-charge-field-potential, ac-signals-frequency-impedance, software-3d, matrix-transformations]
---

# Vectors and complex numbers for systems

<div class="abstract">
Vectors encode component quantities and direction; complex numbers encode two coupled real degrees of freedom with an algebra suited to rotation and sinusoidal steady state. These tools connect physical hardware to graphics, signal analysis, control and numerical software. This chapter separates mathematical objects, finite computer representations and later ChrisOS implementation choices.
</div>

## Scalars, vectors and coordinates

A scalar is represented by one value after its unit and reference convention are fixed. Temperature, elapsed time, resistance and energy are scalar examples. A vector requires components relative to a basis. In Cartesian three-space,

~~~text
v = (vx, vy, vz) = vx ex + vy ey + vz ez
~~~

where `ex`, `ey` and `ez` are basis vectors. Components are not the geometric object itself. Rotating the coordinate axes changes the tuple even when the represented displacement or field is unchanged. This distinction later separates world, camera and clip coordinates.

Vector addition and scalar multiplication are component-wise:

~~~text
a + b = (ax+bx, ay+by, az+bz)
k a   = (k ax, k ay, k az)
~~~

The operations obey the vector-space laws: closure, associativity, additive identity and inverse, and distributivity. These properties make larger transformations compositional.

Units remain part of the model. A displacement in metres cannot be added meaningfully to an electric field in volts per metre merely because both have three components. Machine storage may contain only numbers, so an interface must preserve dimensional meaning explicitly.

| Quantity | Example | Unit |
|---|---|---|
| position | `(x,y,z)` | m or scene unit |
| velocity | `(vx,vy,vz)` | m/s |
| electric field | `(Ex,Ey,Ez)` | V/m |
| force | `(Fx,Fy,Fz)` | N |
| linear RGB | `(r,g,b)` | defined dimensionless convention |

## Magnitude and normalization

For a Euclidean vector,

~~~text
||v|| = sqrt(vx² + vy² + vz²)
||v||² = vx² + vy² + vz²
~~~

Squared magnitude is preferable when only relative lengths are required because it avoids a square root. A unit vector is

~~~text
v_hat = v / ||v||
~~~

provided `||v|| != 0`. Normalization is therefore a partial operation. The zero vector has no defined direction. Floating-point software also needs a policy for very small magnitudes because division can amplify error. Robust code uses a scale-appropriate threshold rather than assuming every nonzero bit pattern is numerically safe.

## Dot product and projection

The Euclidean dot product is

~~~text
a · b = ax bx + ay by + az bz
      = ||a|| ||b|| cos(theta)
~~~

Important consequences are

~~~text
a · a = ||a||²
a · b = 0                 for perpendicular nonzero vectors
cos(theta) = (a·b)/(||a|| ||b||)
~~~

Graphics uses dot products for projection, lighting and orientation tests. Physics uses them for work, `W = F·d`, and in continuous flux calculations.

Projection of `a` onto nonzero `b` is

~~~text
proj_b(a) = ((a·b)/(b·b)) b
~~~

The denominator makes the zero-vector failure explicit. For dense n-component vectors a dot product performs n multiplications and n-1 additions: Theta(n) arithmetic and O(1) auxiliary space. Memory layout, SIMD width, accumulation precision and cache behavior can nevertheless dominate real execution cost.

## Cross product and orientation

In three-dimensional Euclidean space,

~~~text
a × b =
(ay bz - az by,
 az bx - ax bz,
 ax by - ay bx)
~~~

The result is perpendicular to both operands and

~~~text
||a × b|| = ||a|| ||b|| sin(theta)
a × b = -(b × a)
~~~

Operand order determines orientation. This matters for triangle winding, face normals and camera bases. Swapping operands can invert a normal while preserving all magnitudes. The familiar cross product is specifically a three-dimensional operation in this curriculum, not a generic operation on arbitrary-dimensional vectors.

## Linear combinations, basis and independence

A linear combination has the form

~~~text
c1 v1 + c2 v2 + ... + ck vk
~~~

All such combinations form the span. A set is linearly independent when no member can be expressed as a combination of the others. A basis must be independent and span the space; coordinates are coefficients relative to that basis.

The operational consequence is important. A degenerate camera basis or transformation can lose a degree of freedom. A triangle whose edge vectors are dependent has zero area. A linear system with dependent constraints may lack a unique solution.

## Matrices as transformations

A matrix is a rectangular scalar array, but its useful systems interpretation is often a transformation between coordinate spaces. For

~~~text
y = A x
~~~

each output component is a dot product between a row of `A` and `x`. Compatible transformations compose:

~~~text
A(Bx) = (AB)x
~~~

Matrix multiplication is generally not commutative:

~~~text
AB != BA
~~~

so transformation order is part of correctness. Rotating then translating is not generally equivalent to translating then rotating.

Conventional dense n by n multiplication requires Theta(n³) scalar work. Fixed 3 by 3 and 4 by 4 graphics matrices are constant-size asymptotically, but layout, vectorization and convention remain important.

## Determinant, inverse and singularity

For

~~~text
A = [a b]
    [c d]
~~~

the determinant is `ad-bc`. If it is nonzero,

~~~text
A^-1 = 1/(ad-bc) [ d -b]
                  [-c  a]
~~~

A zero determinant indicates a singular transformation and no unique inverse. In floating-point computation, merely obtaining a nonzero determinant is insufficient: an ill-conditioned matrix can magnify tiny input or rounding errors. Numerical software must reason about scale and conditioning rather than blindly compare a computed determinant with exact zero.

A linear system is written `Ax=b`. Gaussian elimination transforms its augmented matrix through row operations. Ordinary dense elimination requires Theta(n³) arithmetic and O(n²) matrix storage. Partial pivoting chooses a larger available pivot in the current column before division, reducing a major source of floating-point error. Exact mathematical solvability and stable numerical computation are separate properties.

## Complex numbers

A complex number has real and imaginary components:

~~~text
z = a + j b
j² = -1
~~~

Electrical engineering commonly uses `j` because `i` conventionally denotes current. Addition is component-wise. Multiplication follows

~~~text
(a+jb)(c+jd) = (ac-bd) + j(ad+bc)
~~~

The conjugate is `z* = a-jb`, giving

~~~text
z z* = a²+b² = |z|²
1/z = z*/|z|²
~~~

for nonzero `z`. Complex division therefore has the same essential boundary as vector normalization: a zero or numerically tiny magnitude requires explicit handling.

## Polar form, phase and Euler's relation

A nonzero complex number can be represented as

~~~text
z = r(cos(theta)+j sin(theta))
  = r e^(j theta)
~~~

Therefore

~~~text
(r1 e^(j theta1))(r2 e^(j theta2))
= r1 r2 e^(j(theta1+theta2))
~~~

Multiplication multiplies magnitudes and adds phases. This is why complex numbers are natural for planar rotations and sinusoidal steady-state analysis.

A two-dimensional vector `(x,y)` can be associated with `z=x+jy`. Multiplication by `e^(j theta)` rotates it. The equivalent real transformation is

~~~text
[x']   [cos(theta) -sin(theta)] [x]
[y'] = [sin(theta)  cos(theta)] [y]
~~~

The complex and matrix forms describe the same planar rotation using different algebraic representations.

## Sinusoids and phasors

A real sinusoid can be represented as the real part of a complex exponential:

~~~text
x(t) = A cos(omega t + phi)
     = Re{A e^(j phi) e^(j omega t)}
~~~

For a linear time-invariant system analyzed at one angular frequency, the common time factor can be suppressed and the signal represented by the phasor `X=A e^(j phi)`. Differentiation then becomes multiplication by `j omega`:

~~~text
d/dt [X e^(j omega t)] = j omega X e^(j omega t)
~~~

This turns ideal capacitor and inductor differential relations into algebraic impedance relations:

~~~text
Z_R = R
Z_L = j omega L
Z_C = 1/(j omega C)
~~~

The imaginary component records phase compactly; it is not a separate physical substance. A phasor is also not the time-domain signal itself. It is a frequency-domain representation valid under sinusoidal steady-state assumptions. Applying phasor algebra directly to arbitrary transients is a model error.

## Finite numerical representations

Mathematical real and complex numbers have conceptual precision that computer representations do not. Floating-point operations round exact results to representable values. Consequences include non-associative addition, cancellation when nearly equal values are subtracted, drift across repeated transformations, overflow, underflow, NaNs and infinities.

Mathematically,

~~~text
(a+b)+c = a+(b+c)
~~~

but finite rounding can make the evaluated results differ. Algorithms must distinguish algebraic identities from bitwise guarantees.

Fixed-point arithmetic instead stores a scaled integer:

~~~text
real_value = stored_integer / scale
~~~

It provides explicit range and predictable representation but requires scale and overflow discipline. Integer vector arithmetic is exact only while operations remain in range. Choosing float, double, fixed point or integer is an architectural choice involving precision, range, performance, ABI and hardware support.

## Data layout and machine cost

A vector may be represented as an array or structure:

~~~text
struct Vec3 {
    float x;
    float y;
    float z;
};
~~~

The abstract vector does not prescribe this layout. An implementation must consider scalar width, alignment, padding, SIMD loads, ABI rules, aliasing and cache locality.

Array-of-structures stores all components of one object together. Structure-of-arrays stores corresponding components of many objects together. The latter can suit component-wise SIMD processing; the former can suit code that repeatedly consumes one complete vector. Neither is universally superior.

Coordinate conventions are equally important. A graphics interface must state handedness, row- versus column-vector convention, storage order, multiplication order, angle units, normalized depth range, and screen origin. Row-major storage and row-vector mathematics are not synonyms. Convention is part of the interface contract.

## Validation invariants

Useful deterministic properties include:

| Property | Expected relation |
|---|---|
| norm | `v·v ≈ ||v||²` |
| orthogonality | `a·b ≈ 0` |
| cross orientation | `a×b = -(b×a)` |
| cross perpendicularity | `(a×b)·a ≈ 0` |
| conjugate | `z z* ≈ |z|²` |
| unit complex rotation | `|z e^(jθ)| ≈ |z|` |
| inverse | `A A^-1 ≈ I` for a well-conditioned invertible A |

Approximate floating-point equality needs a scale-aware tolerance. One absolute epsilon is often unsuitable across values spanning many orders of magnitude.

## Failure boundaries

| Operation | Failure or hazard |
|---|---|
| normalize | zero or near-zero magnitude |
| angle from dot product | zero operand or rounded ratio outside [-1,1] |
| matrix inverse | singular or ill-conditioned matrix |
| complex division | zero or tiny denominator |
| accumulated transform | rounding drift |
| cross-product normal | degenerate triangle or reversed winding |
| unit conversion | dimensionally incompatible values |
| coordinate transform | mismatched handedness or multiplication convention |

A robust implementation documents these preconditions and tests the boundaries.

## Relationship to ChrisOS

This chapter is intentionally implementation-neutral. The reviewed ChrisOS revision is recorded for provenance, but no source behavior is asserted because this mathematical foundation has no declared source dependency.

Later electrical chapters use vectors for fields and complex numbers for phase and impedance. Graphics chapters use vectors, matrices, dot products, cross products and coordinate transforms. Software 3D uses finite-precision representations rather than abstract real numbers. Shader and rasterization paths depend on explicit coordinate conventions.

Those chapters must document actual ChrisOS types and symbols instead of assigning a textbook implementation by analogy.

## Scope boundary and revision

This chapter supplies the linear-algebra and complex-number machinery required by the curriculum. It does not replace full treatments of linear algebra, numerical analysis, Fourier analysis or control theory. Later chapters extend it with homogeneous coordinates, projection, interpolation, frequency-dependent circuit behavior and concrete ChrisOS numerical types.

Mathematical truth, numerical representation and current implementation are separate evidence layers.

Reviewed against ChrisOS `main` revision `da3df29cb397932c43d32373871fb9380e688ade`. `sources` and `symbols` are empty because no implementation claim is made here.


## Affine coordinates and translation

Pure linear transformations preserve the origin: for a linear map `A`, `A0=0`. Translation does not preserve the origin and therefore cannot be represented by an ordinary 3 by 3 linear matrix acting on a three-component position. Graphics commonly introduces homogeneous coordinates so affine transformations can be composed uniformly. A position becomes `(x,y,z,1)`, while a direction can be represented as `(x,y,z,0)`. A 4 by 4 matrix can then carry a translation in its final row or column according to the chosen convention.

The distinction between position and direction is semantic, not cosmetic. Translating a point changes its location; translating a direction should not change it. The homogeneous component makes this distinction algebraically visible. Perspective projection also uses the fourth coordinate, followed by a perspective divide. The graphics chapters derive that pipeline in detail; here the important rule is that a coordinate tuple is meaningful only together with the space and convention in which it is interpreted.

## Change of basis

Suppose the columns of an invertible matrix `B` are basis vectors expressed in a reference coordinate system. Coordinates `c` in that basis correspond to the reference vector

~~~text
v = B c
~~~

and conversion back is

~~~text
c = B^-1 v
~~~

A camera transform can be understood as a change of basis plus translation rather than as an arbitrary collection of matrix coefficients. This interpretation is useful for debugging because it exposes which axes and origin a transform claims to represent.

Orthonormal bases are especially convenient. If columns are mutually perpendicular unit vectors, then `B^-1=B^T` in exact arithmetic. Finite precision can gradually destroy orthogonality, so repeated updates may require renormalization or reconstruction depending on the algorithm.

## Numerical accumulation and reproducibility

Reduction order matters in finite arithmetic. A dot product accumulated left-to-right can differ from a tree reduction or SIMD implementation because rounding occurs after different intermediate sums. Parallel code may therefore produce numerically close but bitwise different answers even when every worker is correct.

Systems validation must choose the required contract deliberately. Bitwise reproducibility demands fixed representation and operation order. Numerical equivalence instead permits bounded error and should specify absolute and relative tolerances. Tests should also include zero, near-zero, very large, very small, collinear, perpendicular and nearly singular inputs rather than only ordinary vectors.
