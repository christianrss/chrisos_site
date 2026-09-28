---
id: hash-tables
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - compiler/chrisc/chrisc.c
  - compiler/clvm/clvm_format.c
symbols:
  - Compiler
  - Symbol
  - hash_str
  - ht_zero
  - ht_find_grid
  - ht_ins_grid
  - lookups_reset
  - sym_find_local
  - sym_find
  - sym_add
  - clvm_fnv1a32
depends_on:
  - arrays-lists-stacks-queues
  - algorithmic-complexity
related:
  - data-structures
  - trees-heaps-tries
  - string-parsing-algorithms
  - compiler-pipeline
---

# Hash tables, hashing and bounded symbol lookup

<div class="abstract">
A hash table maps keys into a finite slot array through a hash function and a collision-resolution policy. Its expected constant-time lookup is useful only when the representation, load factor, collision behavior, deletion rules and adversarial assumptions are explicit. This chapter develops hash functions, open addressing, chaining, load factor, resizing, deletion, complexity, locality, concurrency and security. It then reconciles the theory with the current ChrisC compiler. ChrisC uses fixed-size open-addressed lookup arrays for global identifiers, FNV-1a-style string hashing, linear probing, zero as the empty-slot sentinel, and stored values encoded as identifier index plus one. Its hash capacities are powers of two and are sized at twice the maximum cardinality of the corresponding object arrays. Local variables remain a reverse linear scan because lexical visibility and shadowing differ from global lookup. The CLVM image format separately uses FNV-1a as a checksum; that checksum is not a hash table and is not a cryptographic integrity mechanism.
</div>

## Prerequisites and scope

A hash table combines ideas from arrays, functions and amortized complexity.

The logical operation is a map:

~~~text
key -> value
~~~

The physical representation is usually:

~~~text
hash(key)
   ↓
slot/bucket
   ↓
collision policy
   ↓
candidate key comparison
   ↓
value
~~~

The hash does not establish key equality. It only narrows where a key may be found. The implementation must still compare candidate keys.

This chapter distinguishes four concepts that are often conflated:

- **hash function:** maps arbitrary key bytes into a fixed-width integer;
- **hash table:** data structure that uses a hash to locate keys;
- **checksum:** compact value used to detect accidental changes;
- **cryptographic hash:** designed to resist collision, preimage and related attacks under a specified security model.

ChrisOS currently uses the same FNV-1a family in both table lookup and CLVM checksumming, but the surrounding contracts differ.

## Hash functions

A deterministic hash function maps a key into an integer domain:

~~~text
h: K -> {0, 1, ..., 2^w - 1}
~~~

For a table with m slots, the hash is reduced to an index.

A common reduction is:

~~~text
index = h(key) mod m
~~~

When m is a power of two, modulo can be implemented as:

~~~text
index = h(key) & (m - 1)
~~~

provided m is exactly a power of two.

A good non-cryptographic table hash should be:

- deterministic;
- inexpensive;
- sensitive to all input bytes;
- reasonably well distributed for the actual key population;
- compatible with the reduction used by the table.

Uniform distribution is an analytical model, not something automatically guaranteed for arbitrary keys.

## FNV-1a

ChrisC's hash_str starts from:

~~~text
2166136261
~~~

For every input byte b it performs:

~~~text
h = h XOR b
h = h * 16777619
~~~

with 32-bit unsigned wraparound.

That is the 32-bit FNV-1a recurrence.

Conceptually:

~~~text
h0 = offset_basis
h(i+1) = (hi XOR byte[i]) * prime mod 2^32
~~~

FNV-1a is simple and fast. It is not designed to provide collision resistance against an adversary.

Two different strings can produce the same 32-bit hash. The table therefore must compare the original key after locating candidate slots.

## Table capacity and load factor

If a table contains n live entries in m slots, its load factor is:

~~~text
alpha = n / m
~~~

For open addressing, alpha has a strong effect on probe length.

As alpha approaches 1, empty slots become rare and unsuccessful lookup becomes increasingly expensive.

A common design therefore grows a dynamic table before it becomes too full.

ChrisC takes a different low-level approach: capacities are fixed and the object maxima are chosen so the hash arrays are larger than the corresponding backing collections.

The current constants include:

| Object class | Object maximum | Hash capacity |
|---|---:|---:|
| preprocessor definitions | 4096 | 8192 |
| functions | 4096 | 8192 |
| typedefs | 1024 | 2048 |
| structs | 1024 | 2048 |
| symbols | 16384 | 32768 |
| constants/enums | 4096 | 8192 |

For these paired limits, maximum designed occupancy is at most one half if every live object has one lookup entry.

That is a deliberate fixed-capacity alternative to runtime rehashing.

## Collision resolution

A collision occurs when two distinct keys begin at the same table position.

No practical finite hash can eliminate collisions for an unbounded key domain.

Two major families are:

- **separate chaining:** each bucket references a collection of colliding entries;
- **open addressing:** all entries live directly in the table and a probe sequence searches alternate slots.

ChrisC uses open addressing.

## Linear probing

For initial hash h and power-of-two capacity m, ChrisC examines:

~~~text
slot(i) = (h + i) & (m - 1)
~~~

for:

~~~text
i = 0, 1, ..., m-1
~~~

This is linear probing.

The probe sequence walks consecutive slots with wraparound.

Advantages:

- compact representation;
- no per-entry allocation;
- strong locality compared with pointer chains;
- simple fixed-capacity implementation.

Costs:

- primary clustering;
- performance degradation as occupancy rises;
- deletion requires care;
- worst-case lookup scans the whole table.

## ChrisC slot encoding

The hash arrays contain uint16_t values.

Current code uses:

~~~text
0 = empty slot
id + 1 = occupied slot referring to object id
~~~

The plus-one encoding is necessary because object id zero is valid while zero is reserved as the empty sentinel.

On lookup:

1. compute the string hash;
2. walk the linear probe sequence;
3. read v = table[slot];
4. if v is zero, terminate as not found;
5. decode candidate id = v - 1;
6. compare the original stored name with the requested key;
7. return the id if equal;
8. otherwise continue probing.

The comparison protects correctness when hashes collide.

## Empty-slot termination

ht_find_grid returns not-found immediately on the first empty slot.

That rule is correct only because the current lookup tables do not perform ordinary per-entry deletion that turns a previously occupied slot into an empty hole while later probe-chain entries remain alive.

With standard open addressing, naive deletion can break lookup:

~~~text
A hashes to slot 3
B collides and lands in slot 4
delete A by clearing slot 3
lookup B stops at empty slot 3 -> incorrect not-found
~~~

A deletable open-addressed table normally needs:

- tombstones;
- backward-shift deletion;
- cluster reorganization;
- or full rebuild.

ChrisC's reviewed helper family has no tombstone state. Its lifecycle relies on reset/reconstruction semantics rather than arbitrary removal from these lookup arrays.

## Insertion

ht_ins_grid probes the same sequence.

For each slot:

- if empty, it stores id + 1 and returns;
- if the stored object's key already equals the new key, it returns without duplicating it;
- otherwise it continues.

If every slot is occupied and no matching key is found, the helper reaches the end and returns without insertion.

The surrounding capacity design is therefore important. The compiler's configured object maxima are below the hash capacities, so ordinary valid growth should not require a completely full lookup table.

A future change to those maxima must preserve the capacity relationship or add explicit full-table handling.

## Power-of-two invariant

ChrisC reduces the probe index with:

~~~text
(h + i) & (cap - 1)
~~~

This is equivalent to modulo only when cap is a power of two.

The reviewed hash capacities are:

~~~text
8192, 2048, 32768
~~~

and related powers of two.

Thus a hidden but material representation invariant is:

~~~text
cap > 0
cap is a power of two
~~~

Changing a capacity to an arbitrary integer without changing the reduction would bias or even exclude slots.

## Expected and worst-case complexity

Under a distribution model that spreads keys well and keeps load moderate, hash-table lookup is commonly described as expected O(1).

For linear probing, the actual work is proportional to the probe length.

Worst case is:

~~~text
O(m)
~~~

for a table of m slots.

That can occur when many keys collide or when a long cluster is formed.

Thus “hash lookup is O(1)” is incomplete. The precise statement is closer to:

- expected/amortized constant-time under suitable hash/load assumptions;
- worst-case linear in table capacity.

ChrisC bounds that worst case by fixed capacities, but large bounded work can still matter.

## Locality

Open addressing trades pointer flexibility for contiguous memory.

A linear probe touches neighboring uint16_t slots:

~~~text
tab[s], tab[s+1], tab[s+2], ...
~~~

This is cache-friendly when clusters are short.

Candidate comparison then accesses the backing object array, for example Symbol records or FuncDef records.

The table itself does not duplicate names. It stores compact indices into those arrays.

This creates a two-level representation:

~~~text
hash table: compact index accelerator
           ↓
backing fixed array: authoritative record and key string
~~~

The authoritative object remains in the backing array.

## Global and local symbol lookup in ChrisC

ChrisC does not use one lookup strategy for every identifier.

For local symbols, sym_find_local scans:

~~~text
for i = nsyms - 1 down to 0
~~~

and checks:

- entry is not global;
- its scope is currently visible;
- its name matches.

The reverse order naturally implements recent declaration/shadowing precedence among visible locals.

For globals, sym_find uses ht_sym and ht_find_grid.

This mixed design is important:

| Namespace behavior | Current strategy |
|---|---|
| local lexical symbols | reverse linear scan |
| global symbols | open-addressed hash lookup |
| functions | hash lookup |
| typedefs | hash lookup |
| struct names | hash lookup |
| constants | hash lookup |
| preprocessor definitions | hash lookup |

A hash table is not automatically the right representation for scope resolution. The local scan carries lexical-order semantics that a flat global map would not reproduce by itself.

## Symbol insertion and table synchronization

sym_add appends a new Symbol into the authoritative syms array.

For a global-scope symbol, it then calls ht_ins_grid to add its name-to-index accelerator entry.

This creates a synchronization invariant:

~~~text
for every globally lookup-visible symbol:
    syms[id] contains the record
    ht_sym can reach id by the symbol name
~~~

The backing array and lookup index are separate state.

A mutation that updates one without the other can create stale lookup behavior.

The current compiler largely uses append/build/reset lifecycles, which simplifies this relationship.

## Reset behavior

lookups_reset zeroes every hash array.

An all-zero table means every slot is empty.

The cost is proportional to total configured table capacity:

~~~text
Theta(sum of hash capacities)
~~~

Reset is not O(1).

This is acceptable when reset occurs at compiler initialization or translation-unit lifecycle points rather than on every identifier lookup.

Fixed arrays make reset deterministic and allocator-free.

## Memory cost

The hash arrays use uint16_t slots.

Ignoring alignment, their raw storage is approximately:

~~~text
2 * (
    HT_DEF_N +
    HT_FUNC_N +
    HT_TD_N +
    HT_ST_N +
    HT_SYM_N +
    HT_CONST_N
)
bytes
~~~

With current constants:

~~~text
2 * (8192 + 8192 + 2048 + 2048 + 32768 + 8192)
= 122,880 bytes
~~~

This is only the accelerator memory. The object arrays themselves are much larger.

The design therefore spends about 120 KiB of fixed lookup metadata to avoid repeated global-name scans and dynamic allocation.

## Hash table versus checksum

compiler/clvm/clvm_format.c exposes clvm_fnv1a32.

It computes the same core FNV-1a recurrence over bytecode.

The CLVM writer stores the result in the image header; clvm_parse recomputes it and rejects a mismatch.

That is checksum behavior:

~~~text
stored_hash == recomputed_hash
~~~

It does not use buckets, probing or key/value mapping.

Therefore it is incorrect to describe clvm_fnv1a32 as a hash table.

It is also incorrect to treat the 32-bit FNV value as cryptographic authentication. An attacker capable of modifying both image data and checksum can recompute it.

## Separate chaining

A chained hash table maps each bucket to a collection of entries.

A conceptual bucket is:

~~~text
table[j] -> entry -> entry -> entry
~~~

Advantages:

- deletion is straightforward once the entry is found;
- load factor may exceed 1;
- table slots need only hold bucket heads.

Costs:

- node allocation or embedded links;
- pointer chasing;
- weaker locality;
- more metadata;
- allocator/lifetime complexity.

ChrisC's reviewed lookup implementation does not use separate chaining.

## Tombstones

Open addressing with deletion often distinguishes:

~~~text
EMPTY
OCCUPIED
DELETED
~~~

A DELETED slot cannot terminate an unsuccessful search because later entries may belong to the same probe cluster.

Insertion may reuse tombstones.

Too many tombstones increase probe lengths, so the table may need compaction or rehashing.

ChrisC's current lookup arrays have only the effective EMPTY/OCCUPIED distinction because this helper set is not a general mutable map.

## Resizing and rehashing

A dynamic hash table commonly grows when alpha crosses a threshold.

Growth requires:

1. allocate a larger slot array;
2. initialize it empty;
3. reinsert every live key under the new capacity;
4. publish the new table;
5. release the old table when safe.

Rehashing is O(n) for n live entries.

If capacities grow geometrically, insertion can still have amortized expected O(1), but the individual resize has a latency spike.

ChrisC avoids this operation entirely in the reviewed compiler representation by using fixed maxima and fixed hash arrays.

## Hash flooding and adversarial input

Non-cryptographic table hashes can be vulnerable to chosen-key collision attacks.

An attacker who can generate many colliding identifiers may convert expected constant-time behavior into long probe scans.

Relevant mitigations in general systems include:

- keyed/randomized hashing;
- stronger hash functions;
- collision-count limits;
- balanced-tree fallback;
- input limits;
- fixed capacity and time budgets.

ChrisC currently uses deterministic FNV-1a and fixed capacities.

That makes behavior reproducible and bounded by table capacity, but it does not establish resistance to deliberately constructed collision sets.

The compiler should therefore be documented as using a fast deterministic hash, not a hardened adversarial hash map.

## Concurrency

The reviewed Compiler state is an explicit compiler instance structure, and the hash arrays are fields of that instance.

The helpers themselves do not contain locks or atomics.

Their ordinary contract is therefore single-owner mutation during compilation.

If one Compiler instance were mutated concurrently by multiple threads, operations such as:

~~~text
append object
then insert hash entry
~~~

would need synchronization.

A future concurrent compiler should define whether lookup tables are:

- thread-confined;
- immutable after build;
- protected by locks;
- or rebuilt as concurrent maps.

None of those stronger concurrency models is inferred from the current helpers.

## Failure and saturation

Hash-table-related failure surfaces include:

- backing object array full;
- lookup table full;
- pathological collision sequence;
- inconsistent backing record versus accelerator;
- invalid capacity that is not a power of two;
- corrupted stored id;
- name truncation or key canonicalization mismatch.

ChrisC explicitly reports conditions such as:

~~~text
"symbol table full"
~~~

when the authoritative symbol array reaches SYM_MAX.

The hash insertion helper itself has no distinct diagnostic for probe exhaustion.

The current 2:1 capacity sizing reduces the likelihood that valid compiler growth can reach hash saturation before the corresponding object maximum.

## Validation model

The deterministic checker for this chapter verifies:

- FNV-1a output against an independent Python model;
- power-of-two capacity assumptions;
- linear-probe insertion and lookup;
- collision correctness through original-key comparison;
- first-empty termination;
- id-plus-one encoding;
- table reset;
- maximum designed load factor for each ChrisC table family;
- expected distinction between local reverse scan and global hash lookup;
- current source anchors for hash_str, ht_find_grid, ht_ins_grid, capacities, sym_find_local, sym_find and clvm_fnv1a32.

These checks validate the documented model and reviewed source contract. They do not prove resistance to adversarial hash flooding or every compiler name-resolution path.

## Current limitations

The current ChrisC lookup family is intentionally narrower than a general-purpose map.

It does not provide, in this reviewed helper layer:

- arbitrary key deletion;
- tombstones;
- resize/rehash;
- iterator API;
- generic value storage;
- user-selectable hash function;
- cryptographic collision resistance;
- concurrent mutation semantics.

Those omissions are not defects by themselves. They reflect a fixed-capacity compiler-internal accelerator.

## Roadmap boundary

The curriculum progression is:

~~~text
linear structures
      ↓
hash tables
      ↓
trees, heaps and tries
      ↓
graphs and union-find
      ↓
specialized system structures
~~~

Hash tables optimize exact-key lookup under distribution assumptions.

The next chapter covers ordered and hierarchical structures whose performance depends on height, shape or key prefixes rather than hash distribution.

## Revision provenance

Implementation-facing statements were reconciled against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

Reviewed source:

- compiler/chrisc/chrisc.c;
- compiler/clvm/clvm_format.c.

Reviewed symbols and state:

- Compiler;
- Symbol;
- hash_str;
- ht_zero;
- ht_find_grid;
- ht_ins_grid;
- lookups_reset;
- sym_find_local;
- sym_find;
- sym_add;
- clvm_fnv1a32;
- HT_DEF_N;
- HT_FUNC_N;
- HT_TD_N;
- HT_ST_N;
- HT_SYM_N;
- HT_CONST_N.

The reviewed source demonstrates actual open-addressed hash tables in ChrisC. FNV-1a use in CLVM is documented separately as checksum behavior rather than evidence of another table implementation.
