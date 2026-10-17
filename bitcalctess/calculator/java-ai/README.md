# Bitloop Calculator 2

An exact graph catalogue for the power set of every **n-element set with 1 <= n <= 1024**, computed from polynomial arithmetic. Each result describes the graph types, their actual chain multiplicities, and a disjoint algebraic partition accounting for all \(2^n\) bitstrings. Chain representatives are not required or generated.

The archive includes a runnable Java 17 JAR, Java source, a separate Python verifier, the mathematical proof, and acceptance tests. No external packages are required.

## Run

From the `java-ai` directory, run:

```sh
java -jar java-ai.jar
```

This calculates every `n` from 1 through 1024, in ascending order, and writes to `./output` and `./log`. There is no interactive prompt or launcher script. The calculation uses ordinary JVM memory settings; no memory flags are required. [VALIDATION.md](VALIDATION.md) records the measured heap limit and resource use of the acceptance tests.

To select one width or a range:

```sh
java -jar java-ai.jar 1023
java -jar java-ai.jar --from 513 --to 1024
```

If running alongside version 1, select new directories to keep its different CSV schemas separate:

```sh
java -jar java-ai.jar --output output-v2 --log log-v2
```

Version 2 refuses to overwrite aggregates with incompatible version-1 headers. Existing chain files are neither imported nor removed.

## What is calculated

A **bitloop** is a rotation class of binary words. The **link** operation is adjacent XOR, \(L=I+R\), with \(R\) a cyclic rotation. An **actual chain** is one connected component of the directed link graph on bitloops, including its cycle and all incoming trees. A **graph type** groups actual chains with the same directed topology.

The calculation uses the partition theorem in [REFERENCE.md#partition-proof](REFERENCE.md#partition-proof). Write \(n=qm\), with \(m\) odd and \(q\) a power of two, and set

\[
P=\frac{x^n+1}{(x+1)^q}.
\]

For each divisor \(H\mid P\), the actual chains are described by the quotient

\[
(\mathbb F_2[x]/H)^\times/\langle x,1+x\rangle.
\]

The program computes its cardinality and graph shape using unit counts and modular orders. This is a symbolic family of chains; it does not materialize the family or select a representative from each member. The proof establishes that these families are disjoint and exhaustive. The calculator additionally verifies the resulting word, necklace, and full-period necklace totals.

The census combines divisor strata with identical rotation/link relations using a weighted dynamic program. Its certificate contains local factor-power relations and the resulting merged states, rather than every divisor. No annihilator divisor grid or chain family is enumerated by the new engine. The exact compression is proved in [REFERENCE.md#compressed-census](REFERENCE.md#compressed-census).

Polynomial arithmetic, orders, and coverage counts use arbitrary-precision integers. At `n=1024`, one state describes the single actual chain containing all \(2^{1024}\) bitstrings. No values are extrapolated from previous widths. Integer order bounds are factored using a bundled, checked data set. Factors below 2^64 use deterministic primality testing; larger factors carry independently checkable Pocklington certificates. Factor products and proofs are verified, and no online data lookup is needed. See [REFERENCE.md#integer-certificates](REFERENCE.md#integer-certificates).

The mathematical theorem applies more generally, but this implementation deliberately accepts only `1 <= n <= 1024`. It does not provide an interface to expand a selected chain into explicit words.

## Output

Saved logs and output for n = 1–1024 are bundled in `results.zip`. Extract it in this directory to restore `log/` and `output/` before verifying or continuing the saved results. New runs still write individual files.

| File | Contents |
|---|---|
| `output/powersets.csv` | One row per computed `n`: bitstrings, bitloops, full-period bitloops, actual chains, and graph types |
| `output/graphs.csv` | One row per `(n, graph type)`: topology, multiplicity, and exact coverage totals |
| `output/certificates/{n}.json` | Polynomial factorization, local relations, and weighted states for independent verification |
| `log/{n}.log` | Appended JSON Lines records, with a distinct `run_id` for each execution |

Both CSVs are structured rectangular tables with headers. [OUTPUT.md](OUTPUT.md) defines every field and the certificate format.

`chains` always counts actual connected components. Version 1's reversal-paired rows and representative-dependent `symmetric` flags are not part of this format. Consequently, compare against the sum of version-1 chain multiplicities, not its number of chainrep rows.

Graph names retain the `G{cycle-order}-{signature}` convention. Coverage totals are calculated separately for every width, so `graphs.csv` has one integer `n` per row. A graph type appearing at several widths has a row at each width.

## Verify

With Python 3.9 or newer:

```sh
python3 verify_output.py output
```

The verifier independently checks polynomial irreducibility and factorization, minimal local modular orders, the complete weighted relation calculation, graph shapes, component counts, and coverage. It then checks both CSVs against the certificates. It reads no Java classes and enumerates no words or chain representatives. Invalid data produces a nonzero exit status; verification does not modify files.

The verifier checks an arithmetic instance of the included partition theorem. It is not a formal proof assistant. [VALIDATION.md](VALIDATION.md) records the additional comparisons against explicit small graphs and previous completed runs.

## Existing version-2 output

The CSV schemas are unchanged. This release reads and validates certificates from 2.1 (`n <= 64`), 2.2 (`n <= 128`), 2.3 (`n <= 256`), and 2.4 (`n <= 512`), preserving their aggregate rows. Rerunning a width replaces its certificate with schema `2`. The default command updates every width from 1 through 1024. Mixed `2.1`, `2.2`, `2.3`, `2.4`, and `2` certificates are supported by the calculator and verifier.

The public release and new certificate schema are named `2`; this is the successor to the numbered 2.1–2.4 iterations. The schema retains their compressed fields. See [OUTPUT.md](OUTPUT.md). The version-2.1 format is retained in [REFERENCE.md#legacy-certificate-format](REFERENCE.md#legacy-certificate-format). Use the verifier supplied with this release after upgrading; earlier verifiers do not accept schema `2`.

## Reruns, logs, and recovery

Rerunning a width replaces its certificate and aggregate rows deterministically, preserving all other certified widths. Output from one worker and 32 workers is byte-identical. Existing certificates are validated before being used to rebuild the aggregates.

Logs append to `log/{n}.log`. Every event includes `version`, `n`, and a UUID `run_id`, so multiple runs can be distinguished reliably. A successful run ends with `run_end`, `status: "SUCCESS"`, and SHA-256 hashes of the files as published at that moment. Later runs may change the aggregate CSV hashes. A forcibly terminated process may leave a run without a terminal event.

Writers serialize through a stable `.bitloops-output.lock` file in the output directory. Keep that file in place while programs may be running. Each published file is replaced atomically, but the three-file update is not a single transaction. If a process stops between replacements, rebuild the CSV projections from the validated certificates:

```sh
java -jar java-ai.jar --rebuild-aggregates
python3 verify_output.py output
```

Rebuilding uses only certificates currently present. Restore a missing certificate, or rerun its width, to include it. A rerun can repair that width's corrupt certificate; corruption in another width's certificate causes an error until it is repaired. The output filesystem must support atomic file replacement.

## Options

| Option | Default | Purpose |
|---|---|---|
| Positional `n` | All 1..1024 | Calculate one width |
| `--from A --to B` | All 1..1024 | Calculate a complete inclusive range |
| `--threads N` | `32` | Use up to N workers for independent factor powers; accepts 1..256 |
| `--output DIR` | `./output` | Certificates and CSV aggregates |
| `--log DIR` | `./log` | JSON Lines run logs |
| `--progress-seconds S` | `2` | Progress interval; accepts 0.1..3600 |
| `--plan` | Off | Perform the arithmetic census and print totals without writing files |
| `--rebuild-aggregates` | Off | Regenerate both CSVs from validated certificates |
| `--help` | — | Show usage |

Widths run sequentially; the selected worker count applies within a width. The default matches 32 physical CPU cores. Widths with fewer factor powers use fewer workers. With this small workload, using 64 logical cores need not be faster. Progress counts measured local factor powers; short runs can finish before an intermediate progress event is due.

Omitting the width and range always selects all supported widths, including when other options are supplied. `--rebuild-aggregates` is a separate operation and cannot be combined with a width, range, or `--plan`. Version-1 memory, scan, engine, and field-table options are no longer applicable.

## Build and test

The supplied JAR runs on Java 17 or newer. To compile the source, use a JDK 17 or newer:

```sh
mkdir -p build
javac --release 17 -d build *.java
java -cp build Main
```

To rebuild the executable JAR:

```sh
jar --create --file java-ai.jar --main-class Main -C build .
```

To run the acceptance suite, with a JDK and Python 3.9+:

```sh
python3 test/validate.py
```

Keep `order-factors.json` beside `verify_output.py`; it supplies the verifier's independently checked integer factor data. The JAR embeds the same data and runs without companion files.

Test fixtures are read directly from `test/fixtures.zip`. Tests use temporary directories. Explicit word enumeration is confined to the small-case test oracle (`n <= 16`); it is not part of the production calculator or output verifier.

The implementation is organized as follows:

| Source | Responsibility |
|---|---|
| `Census.java` | Local relations, weighted lattice intersections, graph shapes, and coverage |
| `BinaryPolynomial.java` | Arbitrary-precision binary polynomial arithmetic and factorization |
| `ExactInteger.java`, `OrderFactorData.java` | Verified integer factors and primality certificates |
| `LegacyCensus21.java`, `LegacyCertificate21.java`, `GF2.java` | Read-only validation of version-2.1 certificates |
| `Certificate.java` | Certificate schema and serialization fields |
| `Catalogue.java` | CSV aggregation, validation of existing certificates, publication, and locking |
| `RunLog.java` | Distinguishable appended JSON Lines runs |
| `Json.java` | Exact-integer JSON reading and writing |
| `Main.java` | Command-line options and execution |
| `verify_output.py`, `verify_v21.py`, `order-factors.json` | Independent verification of current and earlier certificates |

