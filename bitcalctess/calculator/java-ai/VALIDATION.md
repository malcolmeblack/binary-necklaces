# Validation — version 2

The acceptance suite passed before release. Its console transcript is included as [validation/acceptance-v2.txt](validation/acceptance-v2.txt). Reproduce it with a JDK 17+ and Python 3.9+:

```sh
python3 test/validate.py
```

The suite compiles the supplied source and builds a fresh executable JAR in a temporary directory. It checks:

- **Every supported width:** no-argument startup calculates `n=1..1024` with a 512 MiB heap and the default 32 workers. A separate one-worker run must produce byte-identical certificates and CSVs.
- **Independent verification:** the Python verifier validates all 1,024 certificates and both complete CSV aggregates, using its own polynomial/order calculations and weighted relation intersections.
- **Version-2.4 agreement:** every powerset and graph row through `n=512` matches the uploaded version-2.4 output. These fixtures contain all 512 powerset rows and all 5,073 graph rows, preserved byte-for-byte with SHA-256 provenance.
- **Earlier agreement:** every powerset and graph row through `n=256`, `n=128`, and `n=64` matches the uploaded version-2.3, version-2.2, and version-2.1 output respectively. Their frozen fixtures retain provenance.
- **Lattice correctness:** 3,600 small pairs are checked against direct integer-relation search, including a case at `n=7` where discarding rotation shifts would produce the wrong graph.
- **Wide arithmetic:** checks cover polynomial and prime-order boundaries and the upper limit `n=1024`. The final width accounts for exactly \(2^{1024}\) words, with one actual chain.
- **Compression:** selected checks include `n=252,254,255,504,508,510,511,1008,1016,1020,1022,1023`. Independent divisor arithmetic establishes the expected number of implicit annihilator strata. At `n=1023`, this count is 81,129,638,414,606,681,695,789,005,144,064. The calculator aggregates relation states without enumerating that divisor grid.
- **Exact factor proofs:** the embedded Java data equals the Python data file. Both validators independently accept its complete factors and Pocklington certificates and reject 16 mutations, including missing factors, invalid witnesses, incomplete degree coverage, malformed proof structure, an overlong decimal, a 1,025-bit integer, and an excessive exponent.
- **Explicit small graphs:** an independent word/rotation/link oracle checks `n=1..16`, totaling 131,070 words. It compares actual components, graph shapes, and weighted word/bitloop/full-period counts. This is the only exhaustive word enumeration in the acceptance suite.
- **Historical results:** completed version-1 log totals and actual graph counts for `n=1..49` agree. The supplied `n=50` arithmetic forecast is separately identified as a forecast.
- **Command-line behavior:** `--plan` creates no files; invalid widths, ranges, and options fail before creating output or logs.
- **Reruns:** selected widths are replaced deterministically, other widths are preserved, and successive log runs have distinct identifiers.
- **Concurrent publication:** four processes preserve every certificate and aggregate entry in a shared output directory.
- **Compatibility:** mixed schema-2.1, schema-2.2, schema-2.3, schema-2.4, and schema-2 certificates can be verified, aggregated, and selectively upgraded by rerunning a width. Each historical schema retains its original supported range. Incompatible version-1 CSV headers are refused; old chain files are untouched.
- **Recovery:** rebuilding from valid certificates restores exact CSV bytes after missing or stale aggregates.
- **Corruption detection:** the verifier rejects 28 mutations affecting local orders, rotation shifts, weighted states, certificate structure, historical range limits, and aggregate contents.

The recorded suite took **656.66 seconds** in the test environment. This includes compilation, both full Java runs, independent verification, compatibility and recovery checks, intentional corruptions, and the small-case oracles. The full Java runs themselves covered `n=1..1024` in logged intervals of 75.28 seconds with one worker and 58.71 seconds with the default 32 workers; these intervals exclude JVM startup. These measurements are not predictions for another machine. No large chain enumeration was run.

The resource summary is [validation/resources-v2.txt](validation/resources-v2.txt). Its maximum reported resident set was 449,324 KiB, measured across the test process tree as described there. The 512 MiB setting is the calculator heap limit, not a claim about total process memory.

## Exactness and scope

The proof in [REFERENCE.md#partition-proof](REFERENCE.md#partition-proof) establishes the disjoint chain partition. [REFERENCE.md#compressed-census](REFERENCE.md#compressed-census) proves that retaining complete relation lattices and accumulating their weights preserves the graph census.

A coverage sum alone would not prove disjointness; that comes from the partition theorem. The Java calculator and Python verifier instantiate both proofs using exact arithmetic and separately check the Burnside necklace and Möbius full-period counts. These are reproducible arithmetic checks, not a machine-checked formal proof of the implementation.

Orders and some prime factors exceed 64 bits. The release contains exact factorizations for every required integer order bound through `n=1024`, covering 215 irreducible degrees with maximum 1018. Every factor product is checked. Factors below `2^64` use a deterministic primality test within its proven range. The 184 wider order-bound primes have recursively checked Pocklington certificates; the data contains 301 proofs, including 117 auxiliary primes. The largest proved prime has 388 bits. The independent arithmetic audit checked all 1,546 distinct primes appearing in the order bounds and their proof factors.

Both Java and Python check these proofs independently, without a network connection or an assumption that a probable prime is prime. Ten certificates use only a sufficiently large factored portion of `p-1`; their remaining cofactors are not asserted prime. The acceptance suite includes tampering with a partial proof. The certification method and provenance are documented in [REFERENCE.md#integer-certificates](REFERENCE.md#integer-certificates).

Unsupported widths are rejected. Increasing an input limit alone does not extend the factor-data coverage or establish a new supported range.
