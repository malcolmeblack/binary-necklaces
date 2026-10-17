# Output contract — version 2

All counts are exact, nonnegative integers. CSV uses UTF-8, a header row, comma separators, and CRLF record endings. JSON uses exact decimal integer literals. Read large counts using arbitrary-precision integers or decimal text; floating-point JSON/CSV import can lose precision above \(2^{53}\). Graph names and signatures are text, including the 1025-character signature at `n=1024`.

## `powersets.csv`

```csv
n,bitstrings,bitloops,factors,chains,graphs
```

| Column | Meaning |
|---|---|
| `n` | Width, 1..1024; primary key |
| `bitstrings` | All original words, exactly \(2^n\) |
| `bitloops` | All cyclic rotation classes of words |
| `factors` | Bitloops whose least rotation period is exactly `n` |
| `chains` | Actual connected components of the link graph |
| `graphs` | Number of distinct directed graph types at this width |

Rows are sorted by `n`. The term `factors` retains its original calculator meaning: full-period bitloops. It does **not** mean the number of irreducible polynomial factors.

## `graphs.csv`

```csv
n,name,chains,bitloops-per-chain,bitstrings,bitloops,factors,cycle-order,tree-depth,signature
```

The primary key is `(n,name)`. Rows are sorted by `n`, then numerical `cycle-order`, then lexical `signature`.

| Column | Meaning |
|---|---|
| `n` | Width of the power set |
| `name` | `G{cycle-order}-{signature}` |
| `chains` | Number of actual chains of this type at this width |
| `bitloops-per-chain` | Number of vertices in each such chain |
| `bitstrings` | Total original words in **all** chains represented by this row |
| `bitloops` | Total bitloops in all those chains |
| `factors` | Total full-period bitloops in all those chains |
| `cycle-order` | Number of bitloops in the directed cycle of each chain |
| `tree-depth` | Maximum distance of a vertex from its cycle; equals \(q=2^{v_2(n)}\) |
| `signature` | Indegrees by distance from the cycle, including the cycle vertex and terminal leaves |

The signature begins with `2`: the cycle predecessor plus one transient predecessor. Its internal digits give the common number of children at each nonzero depth; the final `0` denotes leaves. Together with the cycle length, it specifies the full directed topology. At a cycle of length one, its self-loop supplies the cycle predecessor.

For each `n`, summing the graph rows' `chains`, `bitstrings`, `bitloops`, and `factors` reproduces `powersets.csv`. Every graph row also satisfies

\[
\text{bitloops}=\text{chains}\times\text{bitloops-per-chain}.
\]

Identical graph topology does not imply identical bitstring mass per chain. At `n=3`, the two chains of type `G1-20` account for two and six words. Their combined row records eight words. The certificate retains the separate weighted states needed to explain this distinction.

## `certificates/{n}.json`

One certificate records the full algebraic accounting for its width. Unknown or missing fields are rejected. Numeric values are exact integer literals; `schema_version` is text.

| Top-level field | Meaning |
|---|---|
| `schema_version` | String `"2"` |
| `n` | Width, 1..1024 |
| `q` | Largest power of two dividing `n` |
| `core_polynomial` | \(P=(x^n+1)/(x+1)^q\), encoded as a polynomial |
| `annihilator_strata` | Number of divisors of \(P\), computed as \((q+1)^r\); these divisors are not enumerated |
| `irreducible_factors` | Distinct irreducible factors, with verified local relations for each nonzero exponent |
| `states` | Final distinct relation lattices and their accumulated weights |
| `totals` | `bitstrings`, `bitloops`, `factors`, `chains`, and `graphs`, matching the powerset row |

Polynomial values are lowercase hexadecimal strings: bit `i` is the coefficient of \(x^i\). For example, `0xb` denotes \(x^3+x+1\). They encode operators, not selected bitstring representatives.

Each irreducible-factor object has exactly `polynomial`, `degree`, `multiplicity`, and `powers`. Factors are sorted by numerical polynomial value. Every multiplicity equals `q`; `powers` lists exponents 1 through `q` in order. Each entry has:

| Local-power field | Meaning |
|---|---|
| `exponent` | Exponent \(e\) of this irreducible factor \(f\) |
| `units` | \(\Phi(f^e)=2^{(e-1)\deg f}(2^{\deg f}-1)\) |
| `rotation_order` | \(d=\operatorname{ord}_{f^e}(x)\) |
| `link_order` | \(a=\operatorname{ord}_{f^e}(1+x)\) |
| `cycle_order` | Least positive \(t\) for which \((1+x)^t\) is a power of \(x\) modulo \(f^e\) |
| `rotation_shift` | Unique \(s\) in \(0\le s<d\) such that \((1+x)^t=x^s\pmod{f^e}\) |

The exponent-zero choice is implicit: unit count 1 and relation `(d,t,s)=(1,1,0)`. Thus every factor's complete set of exponent choices is specified without listing their Cartesian product.

Each final state has:

| State field | Meaning |
|---|---|
| `rotation_order` | \(d\), common rotation period for its divisor families |
| `cycle_order` | \(t\), common bitloop cycle length |
| `rotation_shift` | \(s\), defining the complete relation lattice with \(d,t\) |
| `units` | \(W=\sum_H\Phi(H)\), summed over every divisor producing this lattice |
| `chains` | \(W/(dt)\), total actual chains represented by the state |
| `bitstrings` | \(2^qdt\), original words **per actual chain** |
| `bitloops` | Bitloops **per actual chain** |
| `factors` | Full-period bitloops **per actual chain** |
| `name` | Graph name |
| `signature` | Tree signature |

States are sorted by `rotation_order`, then numerical `cycle_order`, then `rotation_shift`. A state represents a disjoint union of divisor families with the same lattice; it does not assert that those divisors are identical. In particular, the weights are accumulated before division by the common orbit size.

The local relations generate lattices

\[
\Lambda=\langle(d,0),(-s,t)\rangle\subseteq\mathbb Z^2.
\]

The verifier independently combines every exponent choice by lattice intersection and sums its weight. It must recover exactly the final state table. Merging solely by graph name would be insufficient for intermediate steps; the full relation is retained.

At power-of-two widths, `irreducible_factors` is empty and the sole state has `(d,t,s)=(1,1,0)` and weight 1. The state formulas include the nilpotent part of dimension `q`, so the certificate still accounts for all \(2^n\) original words.

Multiply a state's per-chain quantities by `chains` when aggregating. In particular,

\[
\sum_{\text{states}}\text{chains}\times\text{bitstrings}=2^n.
\]

The original disjoint partition is proved in [REFERENCE.md#partition-proof](REFERENCE.md#partition-proof); preservation under compression is proved in [REFERENCE.md#compressed-census](REFERENCE.md#compressed-census). No timestamps or run identifiers enter certificates, so a rerun reproduces the same bytes.

Version-2.1 certificates remain readable for `n <= 64`; see [REFERENCE.md#legacy-certificate-format](REFERENCE.md#legacy-certificate-format). Version-2.2, version-2.3, and version-2.4 certificates retain this compressed structure and are readable for `n <= 128`, `n <= 256`, and `n <= 512`, respectively. New runs always write schema `2` for `n <= 1024`. The schema label `2` identifies this release; it is not an alias for any earlier schema.

The verifier checks the local integer-order bounds using bundled `order-factors.json`, including exact primality proofs for factors outside the 64-bit deterministic test range. See [REFERENCE.md#integer-certificates](REFERENCE.md#integer-certificates).

## `log/{n}.log`

Each line is a complete JSON object. Common fields are `time` (UTC ISO instant), `version`, `run_id` (UUID), `n`, `event`, and `elapsed_ns`.

| Event | Additional information |
|---|---|
| `run_start` | Engine, workers, maximum JVM heap bytes, and `representatives: false` |
| `progress` | `phase: "local-factor-powers"`, `done`, and `total` |
| `census_complete` | `annihilator_strata`, merged `states`, and exact coverage totals |
| `run_end` | `status`; on success, `output_sha256`; on failure, an error `message` |

Multiple executions append to the same width's log. Filter on `run_id` to recover one run. Successful publication, rather than merely finishing the arithmetic census, determines a successful terminal record.

