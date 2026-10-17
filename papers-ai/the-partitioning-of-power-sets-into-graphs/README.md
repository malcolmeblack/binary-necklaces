# Managing the paper files

The manuscript is **The Partitioning of Power Sets Into Graphs**. It is a self-contained mathematical paper: definitions, theorems, proofs, examples, a figure, and references are all in one source file.

## Which file to use

| File | Role |
|---|---|
| `the-partitioning-of-power-sets-into-graphs.tex` | **Authoritative source. Edit this file.** It contains the complete paper, bibliography, and TikZ figure. |
| `the-partitioning-of-power-sets-into-graphs.pdf` | Typeset copy for reading, sharing, and review. |
| `the-partitioning-of-power-sets-into-graphs.md` | Markdown reading copy with the same theorem and equation numbers. Its figure uses Mermaid. |
| `export-markdown.py` | Regenerates the Markdown copy from the LaTeX source and its compiled references. |
| `README.md` | These management instructions; it is not part of the paper. |

Keep these files together in one folder. No earlier reports, data files, certificates, or separate proof appendix are required. All proofs are in the manuscript itself.

## Editing and rebuilding

Make mathematical or editorial changes in the `.tex` file. Do not independently edit the PDF or Markdown copy: regenerate them from the source so that definitions, numbering, and proofs stay consistent.

With a standard TeX Live or MiKTeX installation, run this command from the folder:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error the-partitioning-of-power-sets-into-graphs.tex
```

If `latexmk` is unavailable, run `pdflatex` twice:

```bash
pdflatex the-partitioning-of-power-sets-into-graphs.tex
pdflatex the-partitioning-of-power-sets-into-graphs.tex
```

The source uses standard AMS packages, Latin Modern, geometry, microtype, booktabs, TikZ, and hyperref. The bibliography is embedded; BibTeX and external images are not required. To use Overleaf, upload the `.tex` file and choose pdfLaTeX.

After compiling the PDF, refresh the Markdown copy with Python 3 and Pandoc installed:

```bash
python3 export-markdown.py
```

The exporter reads the `.aux` file produced by LaTeX to preserve the PDF's theorem, equation, figure, and reference numbers. Its figure conversion is tailored to the present figure: if you change the TikZ figure, update the matching Mermaid block in the exporter.

Auxiliary files such as `.aux`, `.log`, `.out`, `.fls`, and `.fdb_latexmk` are temporary build products. Keep the `.aux` file until after the Markdown export. You can subsequently remove build products with:

```bash
latexmk -c the-partitioning-of-power-sets-into-graphs.tex
```

## Sharing and maintaining revisions

Send the PDF to readers. Send the complete folder or ZIP to collaborators who will edit the paper. The Markdown copy is useful in editors that support LaTeX mathematics and Mermaid; the PDF is the reference for typesetting.

For version control, track the `.tex` source, exporter, and this README. Regenerate the reading copies for each shared revision, and keep them with that revision. Do not maintain separate mathematical edits in two formats.

The author and affiliation fields are intentionally unassigned. Add the intended attribution in the LaTeX preamble before circulating an attributed manuscript. The paper cites relevant prior work and does not assert priority for its results; establishing novelty for publication requires a separate literature assessment.
