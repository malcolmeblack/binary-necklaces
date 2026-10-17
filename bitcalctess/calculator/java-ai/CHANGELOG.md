# Changelog

## 2

- Supports `1 <= n <= 1024`; no-argument startup calculates the complete range.
- Consolidates the numbered 2.1–2.4 iterations under the release name `java-ai.zip`.
- Expands the checked integer factor data and recursive primality certificates to the new range.
- Retains the compressed relation-lattice census, CSV schemas, direct Java startup, and default 32-worker operation.
- Writes schema `2` and reads validated certificates from 2.1, 2.2, 2.3, and 2.4 within their original ranges.
- Extends independent verification, output regression, and compatibility tests to the new range.

## 2.4

- Doubles the supported range to `1 <= n <= 512`; no-argument startup calculates the complete range.
- Expands the checked integer factor data and recursive primality certificates to every required order bound in the new range.
- Preserves compressed certificates, CSV schemas, direct Java startup, and default 32-worker operation.
- Reads validated version-2.1, version-2.2, and version-2.3 certificates alongside new schema-2.4 certificates.
- Extends independent verification, output regression, and compatibility tests to all 512 widths.

## 2.3

- Doubles the supported range to `1 <= n <= 256`; no-argument startup calculates the complete range.
- Extends exact integer-order arithmetic with bundled factorization data and independently checkable primality certificates for larger prime factors.
- Retains the compressed relation-lattice census, both CSV schemas, and direct Java startup with 32 workers.
- Reads validated version-2.1 and version-2.2 certificates alongside new schema-2.3 certificates.
- Extends regression and independent verification coverage to all 256 widths.

## 2.2

- Doubles the supported range to `1 <= n <= 128`; no-argument startup calculates the complete range.
- Uses arbitrary-precision binary polynomials, orders, and counts.
- Combines equivalent algebraic divisor families using exact weighted relation-lattice intersections, keeping certificates compact.
- Preserves both CSV schemas and supports validated version-2.1 certificates alongside new schema-2.2 certificates.
- Extends the independent verifier and acceptance suite to all 128 widths and adds a proof of the compressed census.
- Retains direct Java startup, default 32 workers, and distinguishable appended JSON Lines logs.

## 2.1

- Supports every width from 1 through 64 using the same algebraic census.
- Replaces chainrep generation with a graph catalogue and verifiable polynomial partition certificates.
- Counts actual connected components directly; removes representative-dependent symmetry fields and reversal-paired row conventions.
- Publishes structured `powersets.csv` and `graphs.csv`, plus one compact JSON certificate per width.
- Defaults to all supported widths with direct Java startup and 32 workers; removes prompts, launcher scripts, large-heap relaunches, and enumeration tuning flags.
- Adds exact integer JSON, a separate Python verifier, deterministic output, synchronized publication, aggregate recovery, and UUID-tagged appended logs.
- Includes the partition proof and acceptance coverage of all 64 widths, with explicit graph checks confined to small cases.

Version 2.1 changes the output contract. Use a separate output directory when retaining version-1 results.

