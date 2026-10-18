# Binary Necklace Calculator and Tessellator

On-demand algebra for binary words of length **1–4,096**, with separate calculator and tessellator Lambdas. There is no powerset database, saved catalogue, factorization database, or network access at runtime. The mathematical core uses Python's arbitrary-precision integers; Pillow is needed only for rendering.

## Project layout

The application intended for website and AWS deployment lives at the top level. Historical implementations are preserved under `archive/`. The archived Java and Python versions were not AI-assisted.

| Path | Contents |
|---|---|
| `BNCT.html` | Modernized website frontend |
| `calculator/` | Modernized calculator Lambda source |
| `tessellator/` | Modernized tessellator Lambda source |
| `shared/` | Algebra and request handling shared by the two Lambdas |
| `dist/` | Ready-to-upload Lambda packages |
| `build.py`, `tests/` | Package builder and validation tests |
| `reference/algebra.md` | Mathematical partition and census proofs |
| `archive/calculator/` | Original C, C++, Java, and Python calculators, with their accompanying files |
| `archive/tessellator/` | Original Python tessellator |

Make application changes in the top-level source directories. Preserve retired versions under a named snapshot in `archive/`, keeping their internal layout intact. Deploy the frontend and the packages in `dist/`; the archive is for the project repository, not for website or Lambda deployment. `build.py` packages only the active source directories and never includes `archive/`.

## Deploy

Ready-to-upload packages are included in `dist/` for **Python 3.12, x86_64** (Pillow 12.3.0). To rebuild them, or target a different runtime or architecture, run from this directory:

```bash
python3 build.py --python-version 3.12 --architecture x86_64
```

This downloads a compatible Pillow wheel and creates `dist/calculator-lambda.zip` and `dist/tessellator-lambda.zip`. Use `--architecture arm64` for an ARM Lambda, and match `--python-version` to its runtime (3.12 or newer, on Amazon Linux 2023). The calculator can be built independently with `--service calculator`, without downloading dependencies. The build command does not deploy anything.

1. Upload each package to its corresponding Lambda. Set both handlers to **`main.handler`**. Start with Python 3.12, 1,024 MB memory and a 30-second timeout.
2. Use `/api/bnct/calc` and `/api/bnct/tess`. Map **POST** to the corresponding Lambda, using Lambda proxy integration. GET is also supported; OPTIONS handles preflight. Both API Gateway payload formats 1.0 and 2.0 are supported. If CloudFront fronts these routes, allow POST and OPTIONS there too.
3. Both responses are now **JSON**, including the image. Remove any old response mapping that extracts or decodes a raw GIF. No binary-media configuration is needed for these JSON responses.
4. Replace the deployed `binary-necklaces/bitcalctess.html` with the supplied `BNCT.html`. Its API routes are `/api/bnct/calc` and `/api/bnct/tess`. Its optional stylesheet, favicon and exposition links retain their existing relative locations.

The page and backends use a new versioned response contract and should be deployed together. The previous flat calculator fields and raw image response are not supported by this page. Sources are in `calculator/` and `tessellator/`; `build.py` includes `shared/` in both deployment packages.

## Website

Enter a binary word and select **Submit**. The page calculates its properties and the graph census, and generates its tessellation automatically. The backend supplies a bounded image with labelled bits. The page shows errors only, with buttons to download the results and image. The tessellation window is black before a result arrives, has the same width as the visible graph-table area, and has height √3 times its width. It starts at native pixel size. The two magnifier buttons zoom around the view center; dragging pans within the image boundaries. Zooming and panning do not make network requests. The download contains the complete returned image.

## What is calculated

- **Word and necklace:** weight, parity, complement, reversal, palindrome, primitive root, spatial period, least rotation, chirality, self-complementarity, adjacent-XOR images and immediate preimage necklaces.
- **Dynamics:** exact distance to the periodic part, first periodic word, eventual spatial period and its polynomial annihilator. When order computation completes: eventual word period, necklace cycle length and rotation after one necklace cycle.
- **Tree and component:** root, branching sequence, full tree depth, necklace/word counts and graph name `G{cycle_length}-{branching_sequence}`.
- **Whole power set:** word, necklace and primitive-necklace counts for every accepted width. The algebraic census calculates graph types, multiplicities and exact coverage totals automatically.
- **Rendering:** a finite, labelled tessellation beginning with the first periodic iterate, with enough surrounding rows and columns for zooming and panning. Every row is computed from the full cyclic word.

The adjacent-XOR convention is `D(w)[i] = w[i] XOR w[(i-1) mod n]`. Both backends use this same literal right-rotation convention. Compared with the original tessellator's coordinates, the triangular drawing is horizontally reflected. Time runs upwards in the tessellation.

Census multiplicities count **actual weakly connected components** separately. The old selected-representative symmetry categories and minimum cycle representatives are not calculated. Necklace chirality is retained. Whole-tree and whole-cycle lists become bounded previews (16 entries by default, at most 64). Those previews are not the evidence for the census: the algebraic partition and independent coverage checks provide that accounting.

## Limits and result meanings

Accepting a width does not guarantee that every factorization at that width will finish within an HTTP request. Basic word, necklace, transient and tree properties remain available when expensive order calculations are deferred. Power-set, necklace and primitive-necklace totals are independent of full classification.

The default computation budget is 20 seconds, reduced when Lambda has less time remaining. `BNCT_SECONDS` optionally sets a server-side budget greater than zero and at most 25 seconds. Integer factorization accepts order bounds up to 4,096 bits, covering the field-order bounds for every accepted width. It has a finite work budget and a maximum certificate-recursion depth of 64; primes are certified, not merely treated as probably prime. The census allows at most 10,000 distinct relation lattices. Three seconds of the Lambda invocation are reserved for completing and serializing the response.

| Status | Meaning |
|---|---|
| `exact` | Classification is complete and verified. |
| `deferred` | Exact classification was not completed; unavailable fields are null, with a reason. Other returned properties are still exact. |
| `not_requested` | The census was not requested. |
| `summary_only` | The complete census was calculated, but its table exceeds the row or byte allowance. Exact totals and verification flags remain; `graphs` is null. |

The Lambda retains a graph table only while it fits **1,000 rows and 1 MiB**. These bounds are checked during aggregation, before retaining an oversized table. If either bound is exceeded, calculation continues to obtain exact aggregate counts and verify the partition; no partial table is presented as complete. The browser displays returned graph tables in pages of 100 rows, and JSON downloads contain every returned row.

The entire calculator response, including the escaped Lambda proxy envelope and headers, is capped at **2 MiB**. A final size guard can omit the graph table and then previews while preserving exact scalar results. Binary words, branching sequences and decimal counts are never shortened.

Calling `shared.census.census(n)` locally returns the full catalogue without the HTTP output restriction. No extrapolated period or partial graph list is presented as an exact catalogue. Powers of two are particularly easy; large odd factors can be much harder. The 4,096-bit acceptance limit is an interactive-service limit, not a mathematical boundary.

Images use 28-pixel cells, 192 columns and 384 row intervals, producing a 5,376 × 10,752 PNG. The backend checks at most 384 iterations for an exact temporal period; longer periods remain unspecified. Every displayed row is computed exactly, without repeating an unverified temporal sample. The full circular word is evolved before cropping, so off-screen bits still affect later rows correctly. Lattice rows extend to both image boundaries, eliminating empty top and bottom strips. Labels are drawn after the geometry; partial glyphs at cropped boundaries are omitted.

The PNG is capped at 3,500,000 bytes. If it exceeds that cap, both image dimensions are halved and a smaller exact region is rendered, subject to the same request deadline. The image is closed before retrying. Base64 and the bounded metadata fit within the synchronous response allowance. The normal indexed image uses approximately 58 MB of raster storage before encoding; the recommended 1,024 MB Lambda memory setting remains appropriate.

The browser limits zoom-out to the scale at which the finite image still covers the entire window, and clamps panning at every border. The window keeps its dimensions through loading, errors, zooming and dragging. The initial maximum zoom uses one image pixel per CSS pixel. At the normal 700-pixel window width, the full-size image permits about 7.7× zoom-out. Smaller returned images automatically reduce that range.

## API

POST JSON to `/api/bnct/calc` or `/api/bnct/tess`. GET accepts equivalent query parameters. The API requires a literal binary word; the page additionally removes whitespace before submission.

Calculator request:

```json
{"bitstring":"0001011"}
```

The census is enabled by default. API callers may set `census: false` to skip it or `preview_limit` to change the bounded preview size; the website always requests the census.

The response has `api_version: "BNCT-a1"`, then `word`, `necklace`, `dynamics`, `tree`, `component`, `preview` and `power_set`. The catalogue is `power_set.census`. Counts and temporal periods are **decimal strings**, even when small, so JavaScript and JSON consumers cannot round them. Bounded dimensions/indices remain JSON numbers. `word.value` records the submitted word; polynomial hexadecimal bit `i` is the coefficient of `x^i`, with word character `i` in that same coordinate.

A graph row's `components` is its multiplicity and `necklaces` is the number of vertices **per component**. `total_words`, `total_necklaces` and `total_primitive_necklaces` cover **all components** of that graph type. Equal graph shapes can have different word masses; dividing a graph row's word total by its multiplicity need not describe any individual component's mass.

`dynamics.transient_depth` is the entered word's distance to the cycle; `tree.depth` is the maximum depth of its entire attached tree. `component.word_period` is the period in fixed coordinates after the transient; `component.cycle_length` is the potentially shorter period modulo rotation. The rotation shift is a right shift modulo the periodic word's spatial period.

Tessellator request:

```json
{"bitstring":"0001011"}
```

The word determines the complete rendering request. Former rendering parameters are ignored. The response contains `image` (`mime_type`, `base64`, `width`, `height`) and `diagram` metadata, including the first periodic row, absolute starting step, chosen dimensions and time direction. Decode `image.base64` as PNG. `diagram.temporal_period` is an exact period only when a return is observed within the bounded 384-step check; otherwise it is null. `spatial_period_fits` and `temporal_period_fits` describe whether the returned view contains a complete period in each direction.

## Calculator response fields and bounds

Accepting every word with `1 <= n <= 4096` guarantees bounded inputs and outputs, not complete period or graph classification within one request. The basic fields below do not require integer factorization or a traversal of an entire cycle/tree. Component classification and the census may be deferred; the completed basic fields remain exact. A deferred value is `null`, never a guessed value or an empty list standing in for an unknown result.

Here `q` is the largest power of two dividing `n`. Every mathematical count or period is returned as an exact decimal string (at most 1,234 digits); dimensions, indices and output-limit metadata are small JSON integers. Binary-word strings contain at most 4,096 characters. All four variable-length lists are explicitly covered below.

| Field(s) | Calculation and returned bound |
|---|---|
| `word.value`, `complement`, `reversal`, `adjacent_xor` | Complete n-character words; linear word operations. |
| `word.primitive_root` | Complete shortest repeated word, at most n characters; linear prefix algorithm. |
| `word.length`, `weight`, `spatial_period`, `parity`, `palindrome` | Exact bounded integers, fixed text or boolean; no orbit traversal. |
| `necklace.least_rotation`, `image` | Complete n-character least rotations, using a linear algorithm. |
| `necklace.spatial_period`, `chirality`, `self_complementary` | Exact bounded integer, fixed text or boolean. |
| `necklace.preimages` | **Complete list of 0–2** n-character words. Adjacent-XOR has at most two literal preimages, so this list never needs truncation. |
| `dynamics.transient_depth`, `periodic_spatial_period` | Exact integers bounded by n, calculated from the nilpotent part and periodic word. |
| `dynamics.cycle_entry` | Complete n-character first periodic word, calculated by fast exponentiation rather than stepping through the transient. |
| `dynamics.annihilator` | Complete polynomial in hexadecimal, at most 1,027 characters; polynomial GCD/division. |
| `tree.root` | Complete n-character necklace representative of the attached tree's root. |
| `tree.depth`, `levels` | Exact q and q+1; at most 4,096 and 4,097. |
| `tree.branching_sequence` | **Complete string of q+1 digits**, at most 4,097. It describes levels; it does not list vertices. |
| `tree.necklaces`, `words` | Exact algebraic counts, without enumerating the tree. |
| `component.cycle_length`, `word_period`, `rotation_shift`, `graph_name`, `necklaces`, `words` | Exact when order classification finishes; otherwise all are null. `graph_name` is at most 5,333 characters; `rotation_shift` is an integer below n. |
| `component.status`, `reason` | `exact` or `deferred`, with a short reason for a computation cutoff. |
| `preview.cycle.items` | **At most preview_limit n-character words**, default 16, maximum 64. Deadline checks occur between entries. This is a cycle prefix, not an expanded orbit. |
| `preview.tree.items` | **At most preview_limit objects**, each with an n-character `word` and integer `depth <= q`. Breadth-first traversal uses a bounded queue and checks the deadline between entries. |
| Each preview's `total` | Exact tree total; cycle total is exact if classified or if the bounded preview itself closes the cycle, otherwise null. |
| Each preview's `returned`, `limit`, `status`, `truncated`, `reason` | Actual item count, requested cap, `complete`/`truncated`, boolean and cutoff reason. Reasons are `item_limit`, `time_limit`, or `response_size`; null for a complete list. A zero limit requests no entries. These fields distinguish an omitted preview from an empty mathematical set. |
| `power_set.n`, `words`, `necklaces`, `primitive_necklaces` | Exact for every accepted width, using powers and divisor sums; independent of component/census classification. |
| `power_set.census.graphs` | **Complete table only if at most 1,000 rows and 1 MiB**; otherwise null with `summary_only`. A deferred or unrequested census supplies no table. |
| Each graph's `name`, `cycle_length`, `branching_sequence`, `depth`, `necklaces` | Exact graph description, with the same scalar bounds as component/tree fields. `necklaces` counts vertices per component. |
| Each graph's `components`, `total_words`, `total_necklaces`, `total_primitive_necklaces` | Exact multiplicity and masses across all components of that graph type. |
| Census `n`, `words`, `necklaces`, `primitive_necklaces`, `components`, `graph_types` | Exact only after the entire census finishes, including in `summary_only`. On deferral, components and graph_types are null; the independent parent power_set totals remain available. |
| Census `verification.word_partition`, `necklace_partition`, `primitive_partition` | Three booleans, included only after all independent coverage checks pass. |
| Census `relation_states`, `component_convention` | Completed state count (at most 10,000) and fixed explanatory text. |
| Census `status`, `reason`, `graphs_returned`, `graphs_truncated` | Exact/summary/deferred/not-requested status and table metadata. A completed omitted table has returned=0 and truncated=true; a deferred table has returned=0 and truncated=null. An unrequested census contains only status. |
| `api_version`, `elapsed_ms`, `limits` | Fixed protocol identifier, measured elapsed time and small integer limits (`max_word_length`, `preview_limit`, `max_census_rows`, `max_census_bytes`, `max_response_bytes`). |

Order calculations and the census share the request deadline. Polynomial matrices are packed bit vectors bounded by n; integer proof recursion, factoring work and census state count are also bounded. A summary is returned only after the complete census and its checks finish. If a time or computation limit interrupts the census after its table was omitted, it still returns `deferred`, with no partial aggregate totals.

The 2 MiB response cap leaves room below the [Lambda synchronous response quota](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html). The default 20-second computation allowance and serialization reserve also fit within the [HTTP API integration timeout](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-quotas.html). Actual classification speed depends on the Lambda's CPU allocation and the word's algebraic factors.

## Algebra and verification

Write `n = m q`, with `m` odd and `q` the largest power of two dividing `n`. The nilpotent `(x+1)^q` part determines the transient and attached trees. The invertible part determines periods and components through the relation lattice of `x` and `1+x` modulo the word's annihilator or each irreducible factor power.

The census combines equal relation lattices with exact unit weights; it does not enumerate the power set or component representatives. For an irreducible factor other than `x` and `x+1`, the relation lattice modulo its `e`th power is the field lattice multiplied by `2^ceil(log2(e))`. Exponents with the same lifted lattice are combined before aggregation. Every complete census independently checks word coverage against `2^n`, necklace coverage against Burnside's formula, and primitive-necklace coverage against Möbius inversion.

Run the tests after installing the rendering dependency:

```bash
python3 -m pip install -r tessellator/requirements.txt
BNCT_LARGE_TESTS=1 python3 -m unittest discover -s tests -v
```

The checks enumerate all words through n=10 and all necklace graphs through n=12; compare 18 selected reference widths through n=1024; verify polynomial lifting and integer certification; and exercise API errors, deadlines, precision, previews and image pixels. Boundary tests cover n=4096 with 64-item previews, n=4095 with a simple word, graph-row/byte cutoffs, proxy-envelope size, expired deadlines and certificate-depth limits. These tests do not attempt complete classification at every width.

[The algebra reference](reference/algebra.md) preserves the mathematical proofs from the retired Java research calculator. `tests/reference-census.zip` retains its complete `powersets.csv` and `graphs.csv` results for n=1–1024, unchanged, as independent regression data. The tests use this archive directly; neither the archive nor the mathematical reference is included in the Lambda packages. The active application has no dependency on the retired Java source, JAR, logs, certificate format, or precomputed factor tables.

Deployment references: [AWS Python ZIP packaging](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html) and [API Gateway Lambda proxy integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html).
