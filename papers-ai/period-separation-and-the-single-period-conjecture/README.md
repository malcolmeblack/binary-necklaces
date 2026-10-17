# Period Separation and the Single-Period Conjecture

This is the third paper, following **Consequences of Binary Necklaces** and **The Partitioning of Power Sets Into Graphs**. It develops one application: the single-period conjecture for the binary Ducci map.

Place this entire folder in `ai/papers/`, beside the two existing paper folders. The supplied ZIP contains this folder directly, so extract it into `ai/papers/`.

| File | Role |
|---|---|
| `period-separation-and-the-single-period-conjecture.pdf` | Typeset paper for reading and sharing. |
| `period-separation-and-the-single-period-conjecture.tex` | Authoritative, self-contained source for editing. |

## What the paper establishes

When a power of two is −1 modulo the odd width `n`, an ordinary temporal period determines its spatial period. This separates the temporal spectra of different spatial classes and counts their exact contributions to the power set. Combining that result with the finite-field degree condition excludes every composite width with even multiplicative order of two.

The paper also gives polynomial-gcd certificates of period diversity and exact population counts, including a complete ordinary-period census at Mersenne widths. The full single-period conjecture remains unresolved here. Established prerequisites are attributed, and no claim of priority is made for the derived corollaries.

The paper restates the required definitions and proves its results independently. The earlier manuscripts provide background; no calculator, data files, or external figures are needed to read or rebuild it.

## Editing and rebuilding

Edit the `.tex` file and regenerate the PDF from this directory:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error period-separation-and-the-single-period-conjecture.tex
```

Alternatively, run pdfLaTeX twice:

```sh
pdflatex -interaction=nonstopmode -halt-on-error period-separation-and-the-single-period-conjecture.tex
pdflatex -interaction=nonstopmode -halt-on-error period-separation-and-the-single-period-conjecture.tex
```

Use a standard TeX Live or MiKTeX installation with the AMS packages, Latin Modern, geometry, microtype, booktabs, array, and hyperref. The bibliography is embedded; BibTeX is unnecessary. For Overleaf, upload the `.tex` file and choose pdfLaTeX.

Author and affiliation fields are unassigned, as in the companion manuscripts. Add the intended attribution before circulating an attributed version. Keep the source and its regenerated PDF together when sharing revisions.
