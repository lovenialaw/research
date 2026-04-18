# Optimal Disassembly Sequence Planning — Gearbox webapp

This tool supports **optimal disassembly sequence planning**: given a **precedence knowledge graph** and **uncertainty data**, it computes a **removal order** (a disassembly priority sequence, **DSP**) toward a chosen **goal component** while minimizing a **risk-aware cost model** in the browser.

You choose **Dijkstra** (globally minimum total cost for this model) or **Genetic algorithm** (evolved per-node priorities), then **Recompute sequence** to refresh the plan and graph.

**Data chain:** `gearbox_kg.html` + `gearbox.xlsx` → `build_data.py` → **`build_data.json`** → **`webapp.html`** (loaded in the browser).

---

## The knowledge graph

The **knowledge graph** is the **directed precedence graph** for this gearbox: it encodes *who must come before whom* in disassembly, not how hard each step is.

- **Vertices (nodes)** — Things that can be removed as one step in the plan:
  - **`C` (component)** — e.g. covers, shafts, bearings (your **Goal** is always a component id like `C1`).
  - **`F` (fastener)** — screws, pins, etc., linked to BOM / tool data from Excel.
- **Directed edges** — An edge **`from` → `to`** reads: **`to` is only removable after `from` has been removed** (all predecessors of `to` must already be in the “removed” set). This is the only meaning of an arrow in the UI and in the algorithms.
- **What the graph does *not* define** — It does **not** set cost or risk by itself. Numeric **success probability `p(v)`** and **effective torque `F_eff(v)`** come from **Excel-backed fields** on each node plus **environment & condition** sliders. The graph only restricts **which** nodes are **available** at each step; the cost model scores **choosing** among those legal moves.

**Where it comes from:** The structure is authored in **`gearbox_kg.html`** (visual / export source); **`build_data.py`** merges it with **`gearbox.xlsx`** into **`build_data.json`**, which the webapp loads to draw **vis-network** and to run Dijkstra / GA on the same edges.

---

## Environment & condition (control bar)

In the **left sidebar**, under **Planning method** and **Goal node**, the block titled **Environment & condition** is the **environmental condition control bar**: it does **not** edit the knowledge graph or Excel data; it drives a **live overlay** on the cost model so you can ask “what if this unit lived in harsher conditions?”

### Controls (what you set)

| Control | Type | Role |
|--------|------|------|
| **Service life (years)** | Slider `0 … 30` (step 0.5) | Proxy for **age / exposure time**; higher values push the model toward worse bond condition (via normalized age in the env formulas). |
| **Humidity (%)** | Slider `10 … 100` | Proxy for **moisture exposure**; higher humidity increases stress in the env model. |
| **Storage** | Dropdown | **Indoor controlled** · **Warehouse** · **Outdoor** · **Coastal/marine** — each applies a **storage multiplier** on top of the other factors (harsher storage → stronger corrosion scaling). |
| **Rust protection** | Dropdown | **Good preservation** · **Partial protection** · **No preservation** — sets both a **preservation multiplier** and an **implicit observed rust level** (there is no separate “rust slider”; protection tier stands in for how corroded the assembly looks). |

Below these controls, the **environment summary** line shows the derived scalars **`corrosion scale`** and **`seizure add`** (and reminds you that effective removal torque reacts to bond condition). Those numbers are computed in the browser by `buildEnvContext` from your selections.

### What they change in the math

- **`corrosionScale`** (clamped roughly 0.6–3.0) scales how strongly **component corrosion** and **environment stress** feed into **`p(v)`** and **`F_eff(v)`** (e.g. effective corrosion on components, torque multipliers on fasteners).
- **`seizureAdd`** (up to ~0.4) **adds** to effective seizure / jamming pressure in fastener success and torque terms.

So the bar adjusts **risk** (lower `p`) and **effort** (higher torque) together; it can change **which** sequence is optimal when you **Recompute**.

### When the plan refreshes

- Changing **Storage** or **Rust protection** triggers an automatic **Recompute** (same as changing goal or branching-risk mode).
- Changing **Service life** or **Humidity** only updates the **numeric labels** next to the sliders until you click **Recompute sequence** — so you can dial both in, then refresh the plan once.

*(Branching-risk benchmark and noise test live in the separate **Benchmarks & robustness testing** card; they are not part of this environment bar.)*

---

## The Dijkstra method

In this webapp, **Dijkstra** does **not** mean “shortest path through the picture of the gearbox graph” using arrow lengths on screen. It means **shortest path on a different graph**: the **state graph of disassembly progress**.

### What is being optimized?

- You fixed a **goal component** (e.g. `C1`). The planner builds an **order of removals** that respects **precedence** (the knowledge graph) and ends with that goal removed.
- Each step removes one **currently legal** node `v` and pays a **non-negative step cost**  
  **`cost(v) = F_eff(v) / p(v)`**  
  where **`p(v)`** and **`F_eff(v)`** are evaluated **at that moment** (what is already removed, tool heat, environment bar, branching-risk mode, etc.).
- **Total cost** = sum of those step costs along the path from “nothing removed” to “goal removed.” **Dijkstra minimizes that total.**

### States and transitions

- **State** ≈ “which nodes have already been removed,” encoded as a **bitmask** over nodes (the gearbox instance is small enough for this in the browser).
- The implementation also tracks **shared-tool heat** (last tool / heat level) because that affects **`p`** and **`F_eff`** on fastener steps — so a state is effectively **(removed set, tool context)**, not the bitmask alone.
- **Transition:** from a state, pick any **available** node `v` (all its predecessors already removed), move to the state where `v` is removed, add **`F_eff(v)/p(v)`** as the edge weight.

### Why Dijkstra applies

Step costs are **non-negative**. The objective is **additive** along the path. So **Dijkstra’s algorithm** on this state graph yields a **globally minimum-cost** removal plan for the **same deterministic model** the UI implements (within the code’s **state expansion budget** — if the search hits that cap, the UI reports failure instead of a wrong optimum).

### What you get in the UI

- **Default method** when you open the app; usually **fast** for this graph size.
- **Ordered sequence** plus **`p` at selection** for each step, graph colouring, and yellow **overlay path** for consecutive steps in that sequence.
- When you run the **GA**, the app still computes **Dijkstra** internally to show **optimal cost vs GA cost** (the **gap**).

For the same formulas in the full pipeline narrative, see **§2.3** below.

---

## The genetic algorithm (GA) method

The **genetic algorithm** in this webapp is **not** a second shortest-path solver on the removal state graph. It **searches in a space of simple decision rules**: fixed **numeric priorities** on nodes, combined with a **greedy** rule that always respects precedence.

### Chromosome and policy

- **Chromosome** = one **real weight per graph node** (same ids as the vis-network diagram). These weights are **not** the same thing as step cost or as `p`.
- **Policy (how a plan is built):** Start with nothing removed. Repeatedly look at the set of **available** nodes (predecessors already removed). Remove the available node with the **largest** weight; break ties by **lower node index**. Stop when the chosen **goal component** has been removed.
- So the GA never “sees” the full state graph explicitly; it only **simulates** this greedy walk and totals the cost.

### Fitness (what the GA minimizes)

- **Fitness** = **total plan cost** = sum over the simulated sequence of **`F_eff(v) / p(v)`**, using the **same** `p` and `F_eff` formulas and state-dependent effects (wear, tool heat, environment bar, branching-risk mode) as **Dijkstra**.
- If the greedy policy gets **stuck** before reaching the goal, that individual is treated as **invalid** (very bad fitness).

So GA and Dijkstra share **one cost model**; they differ in **how** they choose the order. Dijkstra **optimizes** that total over all legal orders; GA **evolves** weights and only explores orders that this **fixed greedy template** can produce.

### Evolution mechanics (browser)

- **Elite fraction** is fixed in the UI (e.g. **25%** of the population kept each generation). The underlying **model exponents** match **`algorithm.py`** defaults for comparability.
- Each generation: **score** every chromosome by simulating the greedy walk; **sort** by fitness; **copy** the best few as elites; **fill** the rest by **blend crossover** between random elite parents, then **mutation** (see below). The **best-ever** individual across all generations is returned.
- **Population size**, **number of generations**, and **mutation strength σ** are **not** user sliders: they are computed from the **size of the relevant subgraph** (see next subsection).

### Population size, generation count, and mutation strength (automatic)

All three use the same complexity input **`n_rel`**: the number of nodes that lie on **some** precedence path backward from the **current goal** (nodes that can matter for reaching that goal). This is smaller than the full graph if the goal isolates a subgraph.

| Hyperparameter | Rule in `webapp.html` | Intent |
|----------------|------------------------|--------|
| **Population** | `raw = 20 + 2 × n_rel`, then clamp to **`[30, 200]`**, then round **down to a multiple of 5** | Larger subgraph → more candidate weight vectors per generation, within a **browser-safe** cap. |
| **Generations** | `raw = 30 + 2 × n_rel`, clamp to **`[30, 300]`**, multiple of 5 | More nodes → more iterations of select / crossover / mutate. |
| **Mutation strength σ** | `0.20 + 0.01 × n_rel`, clamp to **`[0.10, 0.80]`**, rounded to **steps of 0.05** | Slightly **stronger** perturbations when the graph is larger, to help **explore** a bigger weight space; capped so steps do not dominate crossover. |

Inside the GA runner, **population** and **generations** are also **hard-clamped** again (e.g. population in **`[10, 200]`**, generations in **`[1, 500]`**) as a safety net.

**Initial population (generation 0):** each individual gets, for **every** node id, an independent weight drawn **uniformly from `[-1, 1]`** — wide spread so the first generation samples many different greedy orderings.

**How σ is used in mutation:** for each child after crossover, each node’s weight is considered in turn: with probability **20%**, that weight is incremented by **`(U₁+U₂+U₃+U₄ − 2) × σ`** where each **`Uᵢ`** is uniform on **`[0,1]`** (same construction as in code: a compact random perturbation scaled by **σ**). Most weights stay unchanged in a given mutation; a few jump enough to escape local basins when **σ** is larger.

You see the realized **population** and **generations** in the **GA stats** line after a run; **σ** is not printed in the UI but follows the rule above for the current goal and graph.

### Optimality and comparison

- The GA is **heuristic**: it is **not guaranteed** to match **Dijkstra’s** optimal total cost. On some instances the greedy-by-weights class **can** reach the optimum (then **gap ≈ 0%**); on others it cannot.
- After a GA run, the UI runs **Dijkstra** on the same inputs and shows **GA cost**, **Dijkstra cost**, and the **gap** (absolute and %).
- The **noise test** also builds a **GA sequence** (same policy) and compares how that **fixed** sequence behaves vs the **fixed Dijkstra** sequence under **±10%** input noise — that is about **robustness of two plans**, not about GA search quality per se.

For the compact bullet list in the pipeline narrative, see **§2.4** below.

---

## Robustness testing (noise test)

**Robustness testing** in the webapp is the **Noise test (±10%)** control in the **Benchmarks & robustness testing** card (left sidebar, separate from **Environment & condition**). It answers a different question than **Dijkstra vs GA nominal cost**:

> *If the **same two plans** were evaluated under **slightly wrong** corrosion and torque inputs—like real measurement or datasheet spread—which plan’s **total cost** becomes **worse on average** (or in the tail)?*

### What it does (high level)

1. **Freeze two sequences** under the **current** sliders and graph:
   - the **Dijkstra** optimal sequence for this model, and  
   - the **GA** best sequence (full GA run with the same automatic hyperparameters as **Recompute** in GA mode).
2. Do **not** re-run the optimizers inside each trial. The **order of removal stays fixed**; only the **numbers** feeding **`p`** and **`F_eff`** jitter.
3. Run many **Monte Carlo trials** (default **300**). Each trial builds a **temporary copy** of the data where, **independently per part**:
   - every **component** **`corrosion_level`** is multiplied by a factor drawn **uniformly in `[0.9, 1.1]`** (±10%), and  
   - every **fastener** **`removal_force_Nm`** gets its **own** independent factor in **`[0.9, 1.1]`** (if both `fastener` and `tool` objects exist on a node, the same draw is applied to both so they stay consistent).
4. For each trial, compute **total plan cost** \(\sum F_{\mathrm{eff}}/p\) along **each** fixed sequence on that noisy copy.
5. Summarise **nominal** costs (no noise), **noisy mean ± std**, **mean % change vs nominal**, **95th percentile % change**, and a short **verdict** on which sequence’s mean cost **rises more** under this noise.

### How to read the results

- **Nominal** row = both sequences evaluated on the **original** data (same as a deterministic replay).
- **Noisy** statistics = distribution of those totals when inputs are perturbed. Because **`cost = F/p`**, **higher** corrosion and **higher** torque usually **hurt**, so means often sit **above** nominal; the comparison is **which plan is more sensitive**, not whether noise helps.
- This is **not** a test of whether **GA search** is good; it is a test of **two specific orderings** under **input uncertainty**.
- **Recompute sequence** clears the **per-trial line chart** in **Result charts** so you are not looking at stale Monte Carlo data after changing goal, environment, or method. Run **Noise test** again to refresh plots.

### Relation to other benchmarks

- **Branching-risk benchmark** (same card) changes **model structure** (Path A vs B trap multipliers). **Noise test** does **not** toggle that; it only jitters corrosion and nominal torque fields.
- **Result charts** (below CAD): after a noise run, the right-hand plot shows **per-trial** noisy costs for both sequences plus **dashed nominal** reference lines.

For a short pointer inside the end-to-end section, see **§2.6** below.

---

## 1. User journey map

| Stage | User goal | What the user does | What the system does |
|-------|-----------|--------------------|----------------------|
| **Prepare** | Have up-to-date graph + uncertainties | Edit Excel / graph sources if needed; run `python build_data.py` | Regenerates `build_data.json` (nodes, edges, component/tool fields) |
| **Enter** | Open the tool | Open `webapp.html` via local server (e.g. Apache) | Loads `build_data.json`; draws the vis-network graph; fills **Goal** dropdown from component nodes |
| **Situate** | Describe current product condition | Set **Environment & condition** (service life, humidity, storage, preservation) | Derives summary factors (e.g. corrosion scale, seizure add) that feed into `p(v)`; rust level is implied from **Rust protection** |
| **Choose method** | Pick optimizer | Select **Dijkstra** or **Genetic algorithm** | Shows a short GA note when GA is selected; updates hint text |
| **GA effort** *(if GA)* | *(no extra controls)* | Click **Recompute sequence** | Population, generations, and mutation σ are chosen automatically from graph size; elite fraction and model exponents match `algorithm.py` defaults |
| **Compute** | Get a planned sequence | Click **Recompute sequence** | Runs the chosen algorithm in JavaScript; updates list, node colours, yellow overlay path, and (GA) stats vs Dijkstra |
| **Interpret** | Decide if the sequence is acceptable | Read ordered list with `p` per step; compare GA cost vs Dijkstra when GA ran | Colours encode success probability; gap line shows how close GA is to the optimal cost under the same model |

**Typical paths**

- **Fast what-if:** change environment sliders → **Recompute** (Dijkstra is default and instant).
- **Policy comparison:** same settings → run **Dijkstra** → switch to **GA** → **Recompute** → read **GA cost / Dijkstra cost / gap**.
- **Deep tweak:** open **Advanced calibration**, adjust exponents, **Recompute**.
- **Robustness:** set goal and environment → **Noise test (±10%)** → read nominal vs noisy stats (and **Result charts** trial plot).

---

## 2. How the result is found (end-to-end)

### 2.1 Static inputs (from `build_data.json`)

1. **Directed edges** `from → to`: *`to` is only removable after `from`* (precedence).
2. **Per node:** kind (`C` / `F`), labels, BOM `partCode`, and embedded **`component`** or **`tool`** records from Excel (temperature, corrosion, tool success, wear, seizure, jamming, `removal_force_Nm`, etc.).

Nothing in this step depends on the sliders; it is fixed until you rebuild JSON.

### 2.2 Live model (sliders + environment)

For each **candidate removal** of node `v` at a given **already-removed set**:

1. **Success probability `p(v)`** is computed from:
   - Excel-backed fields (and normalization of component / tool temperatures).
   - **Fixed calibration** (same defaults as `algorithm.py`): exponents `a`, `b`, `wear_k`, and **wear accumulation** on fasteners (same part code).
   - **Environment & condition:** adjusts effective corrosion and adds to seizure/jamming pressure (shown in the small environment summary line).

2. **Effective removal torque** `F_eff(v)` (live model): nominal `removal_force_Nm` from data is **scaled up** when bond condition is worse — effective seizure/jamming, environment stress (`corrosionScale`, `seizureAdd`), and (for fasteners with wear on) accumulated wear. Component steps use base cost `1.0` with a mild corrosion/env multiplier.

3. **Step cost** (used by both algorithms in the browser):

   `cost(v) = F_eff(v) / p(v)`

4. **Feasibility:** only nodes whose **all predecessors are already removed** are **available** for the next step.

So: **precedence picks the legal set**; **`p` and effective torque pick the numeric cost** of choosing `v` next. Changing environment sliders therefore changes both **risk** (`p`) and **required torque** (`F_eff`), which can change the optimal sequence and GA fitness (and which evolved weights win).

### 2.3 Dijkstra — how the optimal sequence is found

*(Introductory overview: **The Dijkstra method** section above.)*

- **State** = which nodes are removed (bitmask).
- **Transition** = remove one **available** node `v`; pay `cost(v) = F_eff(v)/p(v)` with both **at that state** (wear can change `p` and fastener `F_eff`).
- **Goal** = selected **goal component** appears in the removed set (you remove everything up to and including reaching that goal in the simulated order).
- **Algorithm:** shortest-path (Dijkstra) over states by total cost → **unique globally minimum total cost** for this additive model (within the implementation’s state budget).

**Output:** one **optimal** removal order and its total cost (sum of step costs).

### 2.4 Genetic algorithm — how the GA sequence is found

*(Introductory overview: **The genetic algorithm (GA) method** section above.)*

- **Chromosome:** one numeric **weight per node** (not the same as cost).
- **Policy:** repeat until goal is removed: among **available** nodes, pick the one with **largest weight** (ties → lower index).
- **Fitness:** total cost = sum of `F_eff / p` along that **greedy** sequence (same formula as Dijkstra’s edges, but order comes from weights, not from state-space DP).
- **Search:** evolve population over generations (crossover, mutation, elite fraction); optional **random seed** for repeatability. **Population size**, **generation count**, and **mutation σ** are set automatically from **`n_rel`** (see **Population size, generation count, and mutation strength (automatic)** under the GA method section above).

**Output:** best-found policy and its total cost. The UI also runs **Dijkstra** on the same inputs to show **gap** vs optimal cost.

**Note:** On small, tightly ordered graphs, GA often **matches** Dijkstra’s cost; that means the greedy policy class **reaches** the optimum, not that GA is broken.

### 2.5 What you see on screen

- **Text list:** removal index, node id, label, `p` at selection.
- **Graph:** base edges = precedence; **yellow dashed overlay** = consecutive steps in the returned sequence (not necessarily the same as a single edge in the DPM).
- **GA stats line:** runtime, population, generations, and **GA vs Dijkstra cost and gap %** when applicable.

### 2.6 Robustness testing (noise test)

*(Full introduction: **Robustness testing (noise test)** section above.)*

- **Input:** current goal, environment, branching-risk mode, and `build_data.json`.
- **Output:** Monte Carlo summary (**~300** trials) comparing **fixed Dijkstra** vs **fixed GA** sequences under **±10%** multiplicative noise on **per-component corrosion** and **per-fastener removal torque**; optional charts in **Result charts**.
- **Purpose:** compare **sensitivity** of two plans to **measurement / data** error, not to re-rank optimizers.

---

## 3. Files (same folder as `webapp.html`)

| File | Role |
|------|------|
| `webapp.html` | UI + vis-network; Dijkstra + GA |
| `build_data.json` | Generated by `build_data.py`; fetched as `./build_data.json` |
| `build_data.py` | Builds JSON from `gearbox_kg.html` + `gearbox.xlsx` |
| `gearbox_kg.html` | Knowledge graph HTML (edges, `partNames`, optional `disassemblyStep`) |
| `gearbox.xlsx` | Uncertainties + mappings (`components`, `tools`, `Sheet5`, `Sheet6`) |
| `algorithm.py` | Optional CLI optimizer (different MC options for GA) |
| `components_guide.md` | Human reference for nodes / BOM |

---

## 4. Data generation (`build_data.py`)

`build_data.py` writes `build_data.json` with:

1. **Graph edges** — from `const edges = ...` in `gearbox_kg.html` (`from → to`: `to` after `from`).
2. **Node metadata** — `F*` / `C*`, `partCode`, `label`, optional `step`, plus `component` / `tool` objects from Excel.
3. **Temperature range** — `componentTempMin` / `componentTempMax` for normalisation in the webapp.

---

## 5. UI areas (reference)

- **DSP algorithm** — Dijkstra vs GA.
- **Goal node** — target component (e.g. `C1`).
- **Environment & condition** — scenario inputs driving extra corrosion / seizure effects.
- **GA note** *(visible in GA mode)* — explains automatic population / generations / mutation; no separate tuning panel.
- **Recompute sequence** — runs the active algorithm.
- **Benchmarks & robustness testing** — branching-risk benchmark (A-vs-B trap model); **Noise test (±10%)** (Monte Carlo robustness vs Dijkstra/GA **fixed** sequences).
- **Result charts** *(main column, below CAD)* — nominal cost bars; per-trial noise plot after a noise test.

---

## 6. Uncertainty → `p(node)` (summary)

### Components (`C*`)

- Uses `corrosion_level` and `temperature` from data; `tempNorm` vs min/max in JSON.
- With calibration:  
  `p(C) = exp(-a · effectiveCorr) · exp(-b · tempNorm)`  
  (`effectiveCorr` can be scaled by environment.)

### Fasteners (`F*`)

- Base from tool success, seizure, jamming (environment can increase effective seizure/jamming).
- Tool temperature via same `b` as component temp scaling (`tempFactor`).
- With wear:  
  `p(F) = p0 · tempFactor · exp(-wear_k · wearState)`  
  where `wearState` depends on removed same–part-code fasteners.

Full formulas match the implementation in `webapp.html`.

---

## 7. Precedence

A node `v` is **available** iff every predecessor on an incoming edge is already **removed**. Both Dijkstra and GA **only** choose among available nodes.

---

## 8. Limits & Python counterpart

- Browser Dijkstra uses a **state budget** (`MAX_STATES`) to stay responsive.
- Browser GA uses **deterministic** total cost along the greedy sequence.
- **`algorithm.py --method ga`** can use **Monte Carlo** fitness (wear + stochastic attempts); not identical to the browser GA, but useful for heavier experiments.

---

## 9. How to run

1. Place **`gearbox.xlsx`** next to `build_data.py` / `webapp.html`.
2. `python build_data.py` → refreshes **`build_data.json`**.
3. Serve the folder (e.g. XAMPP Apache).
4. Open **`http://localhost/research/webapp.html`**  
   - GA-first bookmark: **`webapp.html#ga`**

---

## 10. Interpreting the visualization

- **Blue / green base** — default; **C1** highlighted as base-style node.
- **Sequence nodes** — colour from `p` (greener = higher success probability at removal).
- **Yellow dashed links** — order of removal in the returned plan (step *i* → step *i+1*), overlaid on the precedence graph.

---

*Product name: **Optimal Disassembly Sequence Planning**. Document aligned with `webapp.html` + `build_data.py` (`build_data.json`, `gearbox_kg.html`).*
