# Optimal disassembly sequence planning (gearbox)

This project computes an **ordered removal plan** (a disassembly sequence) for a gearbox given:

- **Precedence constraints** from a directed knowledge graph (edge `A → B` means **B can only be removed after A**).
- **Uncertainty / condition data** from Excel (corrosion, temperatures, tool success, wear, seizure/jamming, removal torque).

You can run it in two ways:

- **Browser webapp** (`webapp.html`): Dijkstra (optimal for the webapp’s deterministic model) or GA (approximate).
- **Python CLI** (`algorithm.py`): includes a GA evaluated by **Monte Carlo** simulation (stochastic attempts + wear).

---

## Quick start (webapp)

### Prerequisites

- **Python 3.x**
- `openpyxl` for reading `gearbox.xlsx`:

```bash
pip install openpyxl
```

- A local web server (recommended on Windows here: **XAMPP Apache**) so the browser can fetch `build_data.json`.

### Generate browser data

From this folder (`research/`):

```bash
python build_data.py
```

This regenerates `build_data.json` from `gearbox_kg.html` + `gearbox.xlsx`.

### Open the UI

Start Apache (XAMPP), then open:

- `http://localhost/research/webapp.html`

In the UI:

- Pick a **Goal** component.
- Adjust **Environment & condition**.
- Choose **Dijkstra** or **GA** and click **Recompute sequence**.

---

## Quick start (Python CLI)

Run Dijkstra-style baseline:

```bash
python algorithm.py --method dijkstra --goal C1
```

Run GA (Monte Carlo evaluated):

```bash
python algorithm.py --method ga --goal C1 --pop 40 --gens 50 --sims 200
```

---

## Model summary (webapp)

Both webapp algorithms (Dijkstra and GA) minimize the same per-step cost:

\[
\text{stepCost}(v)=\frac{F_{\text{eff}}(v)}{p(v)}
\]

- \(p(v)\): modeled **success probability** of removing node \(v\) at the current state (includes environment, wear, difficulty, heat).
- \(F_{\text{eff}}(v)\): **effective torque / effort** (nominal torque scaled up by environment stress, seizure/jamming, wear, difficulty, heat).

Precedence determines which nodes are legal next; sliders only change the numeric model (not the graph).

For the full set of equations and implementation narrative, see:

- `readme/WEBAPP_HOW_IT_WORKS.md`
- `readme/README_webapp.md`

---

## Data flow

1. `gearbox_kg.html` + `gearbox.xlsx`
2. `build_data.py` merges them into `build_data.json`
3. `webapp.html` fetches `./build_data.json` and computes the plan

---

## Repository files

| File / folder | Role |
|---|---|
| `webapp.html` | Browser UI: vis-network graph + Dijkstra + GA |
| `build_data.json` | Generated input for the webapp (rebuild when Excel/graph changes) |
| `build_data.py` | Builds `build_data.json` from HTML graph + Excel |
| `gearbox_kg.html` | Precedence graph (edges, labels, optional step metadata) |
| `gearbox.xlsx` | Uncertainty inputs + BOM mappings (components / fasteners + Sheet5/6 mappings) |
| `algorithm.py` | Python CLI optimizer (includes Monte Carlo GA) |
| `cad_viewer.js` | Optional 3D viewer + goal picking + highlighting |
| `CAD/README_CAD_web.md` | Blender → glTF export guide for the web viewer |
| `components_guide.md` | Node/BOM reference |
| `readme/` | Deeper documentation for the webapp + model |

---

## Common workflows

- **Changed Excel or graph?** Run `python build_data.py` again.
- **Only tweaking environment sliders?** No rebuild needed; just **Recompute** in the webapp.
