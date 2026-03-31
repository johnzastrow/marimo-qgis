# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
#     "pandas",
#     "matplotlib",
# ]
# ///
#
# Run with:  uv run marimo edit marimo_tutorial.py
#            uv run marimo run  marimo_tutorial.py
#
# This notebook has no QGIS dependency.  For QGIS notebooks, no wrapper script
# is needed — the init cell adds sys.path and sets QT_QPA_PLATFORM before
# QgsApplication is created, which is the only point at which Qt reads them.

import marimo

__generated_with = "0.21.1"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return pd, plt


@app.cell
def _(mo):
    mo.md("""
    # marimo Notebook Tutorial

    A practical guide to **marimo** — a reactive Python notebook built for
    reproducible, publishable analysis. This notebook covers the features you'll
    use most: the CLI, markdown and callouts, layout primitives, UI elements,
    reactivity, and the full range of export options.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## What Makes marimo Different

    marimo treats every cell as a **pure function**. Cells declare their dependencies
    through function arguments — marimo tracks which cells depend on which variables
    and re-runs only the affected cells when something changes. There is no hidden
    kernel state and no out-of-order execution.

    | Feature | Jupyter | marimo |
    |---|---|---|
    | Execution order | Manual, any order | Automatic, topological |
    | Hidden state | Yes — kernel accumulates mutations | No — cells are pure functions |
    | UI reactivity | Requires ipywidgets boilerplate | Built-in, automatic |
    | Version control | JSON with outputs embedded | Plain `.py` files, git-friendly |
    | Reproducibility | Depends on run order | Guaranteed |
    | Publishing | `nbconvert` | `marimo export` (HTML, PDF, MD, script) |
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## marimo + QGIS: Complementary Coupling

    This project pairs marimo with **QGIS** (PyQGIS) for spatial analysis. QGIS
    handles all spatial work — opening layers, iterating features, measuring geometry
    with geodesic accuracy, managing coordinate reference systems — while marimo
    handles display, reactivity, and tabular analysis. The same PyQGIS APIs used in
    the QGIS desktop application run headlessly here inside a reactive notebook.

    | Responsibility | Tool |
    |---|---|
    | Open and enumerate spatial layers | QGIS — `QgsProviderRegistry`, `QgsVectorLayer` |
    | Iterate features and read attributes | QGIS — `getFeatures()` |
    | Measure geometry (length, area, distance) | QGIS — `QgsDistanceArea` |
    | Coordinate reference system handling | QGIS — `QgsCrs`, `QgsCoordinateTransform` |
    | Tabular summaries and statistics | pandas — fed by QGIS feature data |
    | Display, documentation, interactivity | marimo — `mo.md`, `mo.ui.table`, `mo.vstack` |

    The separation is deliberate. QGIS never touches the UI layer; marimo never
    touches the spatial data directly. Because marimo notebooks are plain Python
    files, the full pipeline is reproducible from the command line and
    version-controllable in git with no hidden kernel state.
    """)
    return


@app.cell
def _(mo):
    mo.vstack([
        mo.md("""
## Running and Editing

All commands use `uv run` to pick up the project virtual environment.
For QGIS notebooks, `./marimo-qgis` additionally sets
`PYTHONPATH=/usr/share/qgis/python` and `QT_QPA_PLATFORM=offscreen`.

```bash
uv run marimo edit  notebook.py          # full browser editor
uv run marimo run   notebook.py          # view-only, no cell editing
uv run python       notebook.py          # headless script, no browser (CI/CD)
./marimo-qgis edit  example/gpkg_summary.py   # QGIS-aware editor
./marimo-qgis run   example/gpkg_summary.py   # QGIS-aware viewer
```
        """),
        mo.callout(mo.md(
            "**Lint before publishing:** `uvx marimo check notebook.py` — catches "
            "undefined variables, empty cells, and dependency cycles."
        ), kind="info"),
    ])
    return


@app.cell
def _(mo):
    mo.vstack([
        mo.md("""
## Exporting and Publishing

marimo can publish a notebook in many formats. The most important distinction
is **with code** (for developers and collaborators) vs **without code**
(clean reports for non-technical audiences). Every format supports `--watch`
to re-export automatically whenever the notebook file is saved.
        """),
        mo.ui.tabs({
            "HTML": mo.md("""
### HTML — interactive, self-contained

The default export. Runs the notebook and bundles everything into a single
`.html` file that can be emailed, hosted on any static web server, or
opened directly in a browser.

```bash
# With code (default) — for sharing with developers
uv run marimo export html notebook.py -o notebook.html

# Without code — clean report for non-technical audiences
uv run marimo export html --no-include-code notebook.py -o report.html

# Force overwrite an existing file
uv run marimo export html --no-include-code -f notebook.py -o report.html

# Re-export automatically whenever the notebook is saved
uv run marimo export html --no-include-code --watch notebook.py -o report.html
```

**When to use:** sharing a single-file report, internal dashboards, archiving
a snapshot with outputs baked in.
            """),
            "PDF": mo.md("""
### PDF — print-ready document or slide deck

Requires **nbformat**, **nbconvert**, and **Chromium** (via Playwright):

```bash
uv pip install nbformat nbconvert
playwright install chromium
```

```bash
# Standard document PDF (code + outputs)
uv run marimo export pdf notebook.py -o report.pdf

# Publication-ready: outputs only, no code
uv run marimo export pdf --no-include-inputs notebook.py -o report.pdf

# Slide deck (reveal.js layout, one slide per marimo slide boundary)
uv run marimo export pdf --as=slides notebook.py -o slides.pdf

# Slides, outputs only, high-res rasterisation
uv run marimo export pdf --as=slides --no-include-inputs \\
    --raster-scale 4.0 notebook.py -o slides.pdf

# Use a live Python kernel for widgets that need server-side rendering
uv run marimo export pdf --as=slides --raster-server=live notebook.py -o slides.pdf

# Re-export on save
uv run marimo export pdf --no-include-inputs --watch notebook.py -o report.pdf
```

**Key flags:**
- `--no-include-inputs` — hide all code cells
- `--no-include-outputs` — hide all outputs (code only)
- `--as=slides` — reveal.js slide layout
- `--raster-scale 1.0–4.0` — screenshot sharpness (default 4.0)
- `--raster-server=live` — needed when widgets require a running kernel
            """),
            "WASM HTML": mo.md("""
### WASM HTML — zero-infrastructure interactive notebook

Exports the notebook as a standalone HTML file that runs entirely in the
browser via **Pyodide** (WebAssembly Python). No server, no Python
installation needed by the reader.

```bash
# Read-only view, code hidden (default for run mode)
uv run marimo export html-wasm --mode=run notebook.py -o site/

# Read-only view, code visible
uv run marimo export html-wasm --mode=run --show-code notebook.py -o site/

# Editable — reader can modify and re-run cells in the browser
uv run marimo export html-wasm --mode=edit notebook.py -o site/

# Include Cloudflare Worker config for one-command deployment
uv run marimo export html-wasm --mode=run --include-cloudflare \\
    notebook.py -o site/
```

**Constraints:** must be served over HTTP (not `file://`). Uses Pyodide,
which supports most but not all packages — QGIS is not available in WASM.

**When to use:** public-facing interactive reports, GitHub Pages, Cloudflare
Pages — anywhere you want readers to interact with the notebook without
running a Python server.
            """),
            "Markdown": mo.md("""
### Markdown — docs sites and version control

Exports the notebook as a code-fenced `.md` file. Code cells become
fenced `python` blocks; markdown cells become plain text. Compatible with
MkDocs, Quarto, Sphinx, and any static site generator that accepts markdown.

```bash
uv run marimo export md notebook.py -o notebook.md

# Watch mode for live docs preview
uv run marimo export md --watch notebook.py -o docs/notebook.md
```

**When to use:** project documentation sites, README content, anything that
needs to live in a git repo alongside the code.
            """),
            "Script / ipynb": mo.md("""
### Flat Python script

Flattens the notebook into a single `.py` file in topological execution order.
No marimo dependency — runs with plain `python`.

```bash
uv run marimo export script notebook.py -o notebook.script.py

# Topological order (default) or top-down source order
uv run marimo export script notebook.py -o notebook.script.py
```

### Jupyter notebook (.ipynb)

For sharing with Jupyter users or running in JupyterHub/Colab.

```bash
# Structure only (no outputs)
uv run marimo export ipynb notebook.py -o notebook.ipynb

# With outputs baked in
uv run marimo export ipynb --include-outputs notebook.py -o notebook.ipynb

# Top-down order instead of topological
uv run marimo export ipynb --sort=top-down notebook.py -o notebook.ipynb
```

**When to use:** hand-off to collaborators on Jupyter, upload to Google Colab,
submit to journals that require `.ipynb`.
            """),
            "Session / Batch": mo.md("""
### Session export — batch processing multiple notebooks

Executes a notebook (or an entire directory of notebooks) and saves execution
snapshots. Useful for scheduled report generation in CI/CD pipelines.

```bash
# Execute and snapshot a single notebook
uv run marimo export session notebook.py

# Process an entire directory
uv run marimo export session reports/

# Force re-execution even if snapshots are up to date
uv run marimo export session reports/ --force-overwrite

# Continue past errors in a batch run
uv run marimo export session reports/ --continue-on-error
```

**When to use:** nightly report generation, CI pipelines that need to verify
all notebooks run clean, batch publishing of a reports directory.
            """),
        }),
    ])
    return


@app.cell
def _(mo):
    mo.vstack([
        mo.md("""
## Markdown and Callouts

`mo.md()` renders GitHub-flavoured markdown anywhere in the notebook.
`mo.callout()` wraps any element in a coloured callout box.
Five kinds are available: `info`, `warn`, `success`, `danger`, `neutral`.
        """),
        mo.callout(mo.md("**Info:** Use `mo.vstack` and `mo.hstack` to compose layouts."), kind="info"),
        mo.callout(mo.md("**Warn:** The last expression of a cell is its output — not `return expr`."), kind="warn"),
        mo.callout(mo.md("**Success:** `uvx marimo check` reported no issues."), kind="success"),
        mo.callout(mo.md("**Danger:** Never mutate a variable defined in another cell."), kind="danger"),
    ])
    return


@app.cell
def _(mo):
    mo.vstack([
        mo.md("""
## Layout Primitives

`mo.vstack` stacks elements vertically; `mo.hstack` places them side-by-side.
`mo.ui.tabs` creates a tabbed interface. `mo.accordion` creates collapsible sections.
All accept any marimo element, including other layouts — they compose freely.
        """),
        mo.ui.tabs({
            "vstack / hstack": mo.md("""
                ```python
                mo.vstack([elem1, elem2], gap=1)          # vertical, gap in rem
                mo.hstack([elem1, elem2], justify="start") # horizontal
                # justify: "start" | "center" | "end" | "space-between"
                ```
            """),
            "tabs": mo.md("""
                ```python
                mo.ui.tabs({
                    "Tab label": some_element,
                    "Another tab": another_element,
                })
                ```
            """),
            "accordion": mo.md("""
                ```python
                mo.accordion({
                    "Section title": some_element,   # collapsed by default
                })
                ```
            """),
        }),
    ])
    return


@app.cell
def _(mo):
    mo.vstack([
        mo.md("## Stat Cards"),
        mo.hstack([
        mo.stat(value="20",  label="Layers",          caption="in example.gpkg"),
        mo.stat(value="3",   label="CRS",             caption="26918 · 4269 · 4326"),
        mo.stat(value="646", label="Buildings",       caption="ny_ytown_buildings"),
        mo.stat(value="214", label="Street segments", caption="ny_ytown_streets"),
        mo.stat(value="12",  label="Culverts",        caption="ny_culverts_clipped"),
        ]),
    ])
    return


@app.cell
def _(mo):
    mo.md("""
    ## UI Elements and Reactivity

    UI elements are Python objects with a `.value` property. Any cell that reads
    `.value` re-executes automatically when the widget changes — no callbacks,
    no observers, no boilerplate. This is marimo's core reactive model.
    """)
    return


@app.cell
def _(mo):
    year_slider = mo.ui.slider(
        start=1990, stop=2020, step=10, value=2020,
        label="Census year",
    )
    year_slider
    return (year_slider,)


@app.cell
def _(mo):
    layer_dropdown = mo.ui.dropdown(
        options=["town", "ny_youngstown", "ny_ytown_streets",
                 "ny_ytown_buildings", "ny_culverts_clipped"],
        value="town",
        label="Layer",
    )
    layer_dropdown
    return (layer_dropdown,)


@app.cell
def _(layer_dropdown, mo, year_slider):
    mo.callout(
        mo.md(
            f"Inspecting **{layer_dropdown.value}** · census year **{year_slider.value}**  \n"
            "_Change the slider or dropdown above — this cell updates instantly._"
        ),
        kind="info",
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Interactive Tables

    `mo.ui.table` renders a DataFrame as a sortable, filterable, selectable table.
    Selected rows are exposed as `.value` (a filtered DataFrame) and automatically
    propagate to downstream cells — no button press required.
    """)
    return


@app.cell
def _(pd):
    pop_data = pd.DataFrame([
        {"entity": "Town",    "name": "Youngstown (town)",    "area_sq_mi": 33.5,
         "pop1990": 9148,  "pop2000": 9017,  "pop2010": 8515,  "pop2020": 8168},
        {"entity": "Village", "name": "Youngstown (village)", "area_sq_mi": 0.8,
         "pop1990": 1920,  "pop2000": 1831,  "pop2010": 1922,  "pop2020": 1812},
    ])
    return (pop_data,)


@app.cell
def _(mo, pop_data):
    pop_table = mo.ui.table(
        pop_data,
        label="Population — select rows to filter the chart below",
    )
    pop_table
    return (pop_table,)


@app.cell
def _(mo, pop_table):
    _selected = pop_table.value
    _msg = (
        f"**{len(_selected)} row(s) selected:** "
        + ", ".join(_selected["name"].tolist())
        if len(_selected) > 0
        else "_No rows selected — select one or more rows above to filter the chart._"
    )
    mo.md(_msg)
    return


@app.cell
def _(plt, pop_table):
    _rows = pop_table.value if len(pop_table.value) > 0 else pop_table.data
    _fig, _ax = plt.subplots(figsize=(7, 3.5))
    _years = [1990, 2000, 2010, 2020]
    for _, _row in _rows.iterrows():
        _vals = [_row[f"pop{_y}"] for _y in _years]
        _ax.plot(_years, _vals, marker="o", label=_row["name"])
    _ax.set_title("Charts — reactive to table selection above")
    _ax.set_xlabel("Year")
    _ax.set_ylabel("Population")
    _ax.legend()
    _ax.grid(True, alpha=0.3)
    plt.tight_layout()
    _fig
    return


@app.cell
def _(mo):
    mo.md("""
    ## Best Practices

    ### Cell output — last expression, not `return expr`
    ```python
    mo.md("Hello")   # correct — last expression is the output
    return

    return mo.md("Hello")   # wrong — marimo check flags this as an empty cell
    ```

    ### Cell-private vs shared variables
    Variables returned from a cell are shared with all cells that list them as
    arguments. Prefix with `_` to keep a variable local to the cell:
    ```python
    _tmp = expensive_intermediate()  # cell-private, not exported
    result = _tmp.summarise()        # exported, available downstream
    return (result,)
    ```

    ### No mutation across cells
    Never append to or modify a variable from another cell. Create a new object:
    ```python
    new_list = old_list + [item]     # good
    old_list.append(item)            # bad — mutates shared state
    ```

    ### Script-mode detection
    `mo.app_meta().mode` is `"script"` when running via `python notebook.py` or
    `marimo export`. UI widgets still exist and hold their default `.value` — no
    special handling needed for most cases:
    ```python
    is_script = mo.app_meta().mode == "script"
    return (is_script,)
    ```

    ### Run `marimo check` before publishing
    ```bash
    uvx marimo check notebook.py   # catches empty cells, cycles, undefined vars
    ```
    """)
    return


if __name__ == "__main__":
    app.run()
