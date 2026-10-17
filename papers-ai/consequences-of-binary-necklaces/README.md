# Managing the introduction

**Consequences of Binary Necklaces** is the introductory companion to [The Partitioning of Power Sets Into Graphs](../the-partitioning-of-power-sets-into-graphs/the-partitioning-of-power-sets-into-graphs.pdf).

| File | Role |
|---|---|
| [consequences-of-binary-necklaces.tex](consequences-of-binary-necklaces.tex) | Authoritative source for editing. Figures and references are embedded. |
| [consequences-of-binary-necklaces.pdf](consequences-of-binary-necklaces.pdf) | Supplied typeset copy for reading and sharing. |

Both files have been preserved exactly as supplied. The PDF was not regenerated during organization.

Edit the `.tex` file and rebuild the PDF from this directory with a standard TeX Live or MiKTeX installation:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error consequences-of-binary-necklaces.tex
```

Alternatively, run pdfLaTeX twice:

```sh
pdflatex -interaction=nonstopmode -halt-on-error consequences-of-binary-necklaces.tex
pdflatex -interaction=nonstopmode -halt-on-error consequences-of-binary-necklaces.tex
```

The source uses standard AMS packages, Latin Modern, geometry, microtype, booktabs, array, TikZ, and hyperref. It needs no external images or bibliography file. For Overleaf, upload the `.tex` file and select pdfLaTeX.

Keep the source and PDF together when sharing a revision. Auxiliary build files can be removed after compilation with `latexmk -c consequences-of-binary-necklaces.tex`.

[Return to the archive guide](../../README.md).
