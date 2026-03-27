# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo as mo

app = mo.App()


@app.cell
def _():
    import marimo as _mo

    _mo.md("# Simple Test")
    return


@app.cell
def _():
    result = {"message": "Hello from marimo!"}
    return (result,)
