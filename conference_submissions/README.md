# conference_submissions

| Folder | What it holds |
|---|---|
| `manuscript/` | Journal paper (LaTeX). **Edit `main_1.tex`; keep `build/main_1.pdf` open** — it is the only manuscript PDF and is rebuilt on save (LaTeX Workshop) or with the command below. |
| `manuscript/figures/` | Figures used by `main_1.tex` and the script that makes the validation figure. |
| `manuscript/snapshots/` | Read-only copies kept on purpose (`main_1_2026-11-11.pdf` and earlier `.tex` versions). Annotate these, not `build/`. |
| `manuscript/drafts/` | Earlier drafts the LaTeX text was built from (AE outline, journal draft .docx/.tex). |
| `WISO26/` | Conference paper: final PDF, drafts, template, poster guidelines; `forms/` has the copyright forms. |
| `poster/` | Poster PPTX/PDF versions, `export_poster_hires.py`, and `poster_figures/`. |
| `admin/` | Registration invoice. |
| `archive/` | Superseded drafts. |

Rebuild the manuscript PDF (from `manuscript/`):

```bash
pdflatex -output-directory=build main_1.tex && bibtex build/main_1 && pdflatex -output-directory=build main_1.tex && pdflatex -output-directory=build main_1.tex
```
