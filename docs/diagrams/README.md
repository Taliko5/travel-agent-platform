# Diagrams

Each diagram has two files: a `.mmd` (Mermaid source, the editable origin) and a
rendered `.svg` beside it. The `.svg` is what gets embedded — GitHub renders fenced
` ```mermaid ` blocks in `README.md` natively, but GitHub Pages'
`jekyll-theme-minimal` does not, so a committed SVG is what actually works in both
places.

- `architecture-current.mmd` / `.svg` — what's deployed today (Step 9).
- `architecture-planned.mmd` / `.svg` — the target state tracked by
  `docs/plan.md` Steps 11–14. Not deployed. Styled distinctly (dashed orange
  borders, a warning banner) so it can't be mistaken for the current diagram.

## Re-rendering after editing a `.mmd`

Requires Node 18+ (the `@mermaid-js/mermaid-cli` package needs it; this repo's own
`.nvmrc` pins Node 24, which works):

```bash
nvm use 24   # or any Node 18+
npx --yes @mermaid-js/mermaid-cli -i docs/diagrams/<name>.mmd -o docs/diagrams/<name>.svg -b white
```

The `-b white` flag is not optional — it's what gives the SVG its explicit light
background (`background-color: white` on the root `<svg>` element). Without it the
background is transparent, and the diagram becomes unreadable on GitHub's dark
theme (dark strokes/text with nothing behind them). After re-rendering, open the
SVG and confirm `background-color: white` is still present on the root element
before committing.
