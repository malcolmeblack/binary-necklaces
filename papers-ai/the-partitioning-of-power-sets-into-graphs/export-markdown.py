#!/usr/bin/env python3
"""Export the paper's LaTeX source to a readable, numbered Markdown copy.

Run latexmk first. Requires Python 3 and Pandoc. The .tex file is authoritative.
"""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
STEM = "the-partitioning-of-power-sets-into-graphs"
source = (ROOT / (STEM + ".tex")).read_text(encoding="utf-8")
aux_path = ROOT / (STEM + ".aux")
if not aux_path.exists():
    raise SystemExit("Build the PDF first with latexmk -pdf " + STEM + ".tex")
aux = aux_path.read_text(encoding="utf-8")
refs = dict(re.findall(r"\\newlabel\{([^}]+)\}\{\{([^}]+)\}", aux))
bib = dict(re.findall(r"\\bibcite\{([^}]+)\}\{([^}]+)\}", aux))
abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", source, re.S).group(1)
source = re.sub(r"\\begin\{abstract\}.*?\\end\{abstract\}", "", source, flags=re.S)

# Substitute cross-references before parsing; the PDF's auxiliary file supplies
# the same section, theorem, equation, table, and figure numbers to both formats.
source = re.sub(r"\\(eqref|ref)\{([^}]+)\}",
                lambda m: "(" + refs[m[2]] + ")" if m[1] == "eqref" else refs[m[2]], source)
source = re.sub(r"\\cite\{([^}]+)\}",
                lambda m: "[" + ", ".join(bib[k] for k in m[1].split(",")) + "]", source)

# A text heading avoids Pandoc's separate theorem-numbering scheme.
envs = "theorem|proposition|lemma|corollary|definition|example|remark"
def theorem_heading(m):
    title = m[1].title() + " " + refs[m[3]]
    if m[2]:
        title += " (" + m[2] + ")"
    return "\n\\noindent\\textbf{" + title + ".}\n\n"
source = re.sub(r"\\begin\{(" + envs + r")\}(?:\[([^\]]*)\])?\s*\\label\{([^}]+)\}",
                theorem_heading, source)
source = re.sub(r"\\end\{(?:" + envs + r")\}", "\n", source)
source = source.replace(r"\begin{proof}", "\n\\noindent\\emph{Proof.} ")
source = source.replace(r"\end{proof}", " \\(\\square\\)\n")

section = subsection = 0
def heading(m):
    global section, subsection
    if m[1] == "section":
        section += 1
        subsection = 0
        number = str(section)
    else:
        subsection += 1
        number = f"{section}.{subsection}"
    return "\\" + m[1] + "{" + number + ". " + m[2] + "}"
source = re.sub(r"\\(section|subsection)\{([^}]+)\}", heading, source)

# Split this paper's two-row align environment into two displays, so each
# equation retains its number in Markdown renderers using KaTeX.
def split_align(m):
    rows = re.split(r"\\\\\s*\n", m[1].strip())
    return "\n".join(r"\begin{equation}" + row.replace("&", "") + r"\end{equation}" for row in rows)
source = re.sub(r"\\begin\{align\}(.*?)\\end\{align\}", split_align, source, flags=re.S)
def numbered_equation(m):
    content = m[1]
    labels = re.findall(r"\\label\{([^}]+)\}", content)
    content = re.sub(r"\\label\{[^}]+\}", "", content).strip()
    if labels:
        content += "\n\\tag{" + refs[labels[0]] + "}"
    return r"\[" + content + r"\]"
source = re.sub(r"\\begin\{equation\}(.*?)\\end\{equation\}", numbered_equation, source, flags=re.S)
source = re.sub(r"\\label\{[^}]+\}", "", source)

# The same two graph types as the TikZ illustration, in portable Mermaid.
source = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}", "PAPERFIGUREPLACEHOLDER", source, flags=re.S)
source = re.sub(r"\\begin\{thebibliography\}\{[^}]+\}", r"\\section*{References}", source)
source = source.replace(r"\end{thebibliography}", "")
source = re.sub(r"\\bibitem\{([^}]+)\}", lambda m: "\n\\noindent\\textbf{[" + bib[m[1]] + "]} ", source)

def pandoc(text):
    return subprocess.run(["pandoc", "--from=latex", "--to=gfm", "--wrap=none",
                           "--shift-heading-level-by=1"], input=text,
                          text=True, capture_output=True, check=True).stdout

result = "# The Partitioning of Power Sets Into Graphs\n\n## Abstract\n\n" + pandoc(abstract) + "\n" + pandoc(source)
figure = """```mermaid
flowchart BT
    subgraph A["G(1; 2, 1) — two components"]
        A2(( )) --> A1(( )) --> A0(( ))
        A0 --> A0
    end
    subgraph B["G(2; 2, 2) — one component"]
        B2(( )) --> B1(( )) --> B0(( ))
        B3(( )) --> B1
        C2(( )) --> C1(( )) --> C0(( ))
        C3(( )) --> C1
        B0 --> C0
        C0 --> B0
    end
```

*Figure 1. The two graph types at $n=6$. The first type occurs twice and the second type once. Arrows indicate the induced symmetric-difference map.*"""
result = result.replace("PAPERFIGUREPLACEHOLDER", figure)
result = result.replace("\nThe complete partitions for odd parts $3$ and $5$.\n",
                        "\n*Table 1. The complete partitions for odd parts $3$ and $5$.*\n")
result = re.sub(r"\\\[([123])\\\]", r"[\1]", result)
result = re.sub(r"\$\$(.*?)\$\$", lambda m: "\n\n$$\n" + m[1].strip() + "\n$$\n\n", result, flags=re.S)
result = re.sub(r"(?m)^[ \t]+$", "", result)
result = re.sub(r"\n{3,}", "\n\n", result).replace("\u00a0", " ")
for forbidden in (r"\label{", "data-reference", "PAPERFIGUREPLACEHOLDER", "<div", r"\ref{"):
    if forbidden in result:
        raise SystemExit("Unresolved export syntax: " + forbidden)
(ROOT / (STEM + ".md")).write_text(result, encoding="utf-8")
print("Wrote " + STEM + ".md")
