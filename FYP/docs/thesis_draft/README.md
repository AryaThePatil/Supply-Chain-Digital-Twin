# Thesis Draft - Quick Overleaf Upload Guide

## How to compile this on Overleaf

1. **Zip the entire `thesis_draft` folder** (right-click → Send to → Compressed folder).
2. Go to **[overleaf.com](https://www.overleaf.com)** → New Project → Upload Project.
3. Upload the zip file.
4. Set the **main document** to `main.tex`.
5. Set the **compiler** to `pdfLaTeX` (not XeLaTeX).
6. Click **Recompile**.

## Folder Structure

```
thesis_draft/
├── main.tex                          <- Entry point. Compile this.
├── references.bib                    <- All citations go here (IEEE format)
├── frontmatter/
│   ├── title_page.tex
│   ├── declaration_certificate.tex
│   ├── acknowledgement.tex           <- Write personally
│   └── abstract.tex                  <- Fill in after all chapters are done
├── chapters/
│   ├── chapter1_introduction.tex
│   ├── chapter2_literature_survey.tex
│   ├── chapter3_system_design.tex
│   ├── chapter4_implementation.tex
│   ├── chapter5_results.tex          <- Data tables already filled in
│   └── chapter6_conclusion.tex
└── images/
    └── vnit_logo.png                 <- Add this manually from VNIT website
```

## What is still [PLACEHOLDER]

Search for `[PLACEHOLDER]` in any `.tex` file to find what needs to be written.
Every `[PLACEHOLDER]` has a TODO comment above it explaining exactly what to write.

## VNIT Logo

Download the official VNIT Nagpur logo (PNG format) from the VNIT website and
save it as `images/vnit_logo.png`. The title page will automatically display it.
