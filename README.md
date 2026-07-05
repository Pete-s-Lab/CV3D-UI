# CompoundVision3D UI Tutorial RMarkdown bundle

This folder contains an RStudio/RMarkdown-ready tutorial source and placeholder screenshots.

## Render to PDF in RStudio

Open `CompoundVision3D_UI_Tutorial.Rmd`, then use **Knit -> Knit to PDF**.

Or run:

```r
rmarkdown::render("CompoundVision3D_UI_Tutorial.Rmd", output_format = "pdf_document")
```

The YAML header requests PDF output and automatic numbering:

```yaml
output:
  pdf_document:
    toc: true
    toc_depth: 3
    number_sections: true
    fig_caption: true
    latex_engine: xelatex
```

## Replacing figures

All placeholder images are stored in:

```text
docs/images/
```

Replace any placeholder PNG with a real screenshot using the same filename. Keep the Markdown image lines unchanged unless you want to change the caption or order.

Each figure is referenced like this:

```markdown
![Caption text](docs/images/example.png){width=66%}
```

RMarkdown/Pandoc turns the alt text into the figure caption and numbers it automatically in the PDF.
