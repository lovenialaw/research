# Mathematical equations (webapp cost model)

This project’s web planner (`webapp.html`) computes an **optimal / near-optimal disassembly sequence** under precedence constraints by minimizing a **risk-aware additive cost**.

The equations below mirror the implementation in `webapp.html` (not the Python Monte‑Carlo variant).

---

## Notation

- **Graph**: directed edges \(u \rightarrow v\) mean **\(v\) cannot be removed until \(u\) is removed**.
- **Nodes**: each node \(v\) is either:
  - component: `kind === 'C'`
  - fastener: `kind === 'F'`
- **State** (for planning): a bitmask \(m\) over nodes (1 = already removed).
- **Goal**: a chosen component node \(g\); planning stops once \(g\) is removed.

Per step, the model computes:
- \(p(v, m, \text{heat})\): modeled probability of successful removal if chosen next.
- \(F_{\text{eff}}(v, m, \text{heat})\): effective removal torque/effort proxy (in Nm for fasteners; unitless-scaled for components).
- **step cost**: \(c(v, m, \text{heat}) = \dfrac{F_{\text{eff}}}{p}\).

---

## 1) Environment normalization and scaling (`buildEnvContext`)

User inputs:
- humidity \(H\) in %
- service years \(Y\)
- storage type \(S \in \{\text{indoor},\text{warehouse},\text{outdoor},\text{coastal}\}\)
- rust protection \(P \in \{\text{good},\text{partial},\text{none}\}\)

### 1.1 Normalized factors

\[
h = \mathrm{clamp}\!\left(\frac{H - 40}{60},\, 0,\, 1\right)
\]
\[
a = \mathrm{clamp}\!\left(\frac{Y}{20},\, 0,\, 1\right)
\]

Observed rust \(r\) is derived from rust protection tier:

\[
r =
\begin{cases}
0.38 & P=\text{none}\\
0.22 & P=\text{partial}\\
0.12 & P=\text{good}
\end{cases}
\]
\[
r = \mathrm{clamp}(r, 0, 1)
\]

### 1.2 Multipliers

Storage multiplier:

\[
M_S =
\begin{cases}
1.35 & S=\text{coastal}\\
1.20 & S=\text{outdoor}\\
1.05 & S=\text{warehouse}\\
1.00 & S=\text{indoor}
\end{cases}
\]

Preservation multiplier:

\[
M_P =
\begin{cases}
1.25 & P=\text{none}\\
1.08 & P=\text{partial}\\
0.90 & P=\text{good}
\end{cases}
\]

### 1.3 Environment outputs

Corrosion scale (used to worsen effective corrosion and “bond stress”):

\[
\text{corrosionScale} =
\mathrm{clamp}\!\Big(
\left(1 + 0.45h + 0.35a + 0.65r\right)\,M_S\,M_P,\;
0.6,\; 3.0
\Big)
\]

Seizure add-on (used to bump fastener seizure/jamming):

\[
\text{seizureAdd} =
\mathrm{clamp}\!\left(0.12h + 0.08a + 0.20r,\; 0,\; 0.4\right)
\]

---

## 2) Precedence feasibility (“available nodes”)

Let \(\text{predMask}(v)\) be the bitmask of predecessors of node \(v\).

Node \(v\) is **available** in state \(m\) iff all predecessors are removed:

\[
\big(\text{predMask}(v) \;\&\; m\big) = \text{predMask}(v)
\]

Environment sliders do **not** change feasibility; they only change \(p\) and \(F_{\text{eff}}\).

---

## 3) Success probability \(p\)

Constants (from `readParams()` defaults in `webapp.html`):

- \(A = \texttt{compA} = 0.25\)
- \(B = \texttt{compB} = 1.0\)
- \(k_w = \texttt{wearK} = 1.25\)
- Task difficulty terms:
  - \(\lambda_P = \texttt{diffP} = 0.05\)
- “Heat” terms (shared-tool repetition penalty, fasteners only):
  - \(\alpha_P = \texttt{heatP} = 0.20\)
  - \(\texttt{heatMax}=3,\ \texttt{heatCool}=1\)

### 3.1 Components (`kind === 'C'`)

From data:
- component corrosion level \(c \in [0,1]\) (`component.corrosion_level`)
- component temperature \(T\)
- dataset temperature range \([T_{\min}, T_{\max}]\) from `build_data.json`

Temperature normalization:

\[
t = \frac{T - T_{\min}}{\max(\varepsilon,\; T_{\max}-T_{\min})}
\]

Environment-scaled corrosion (clamped):

\[
c_{\text{eff}} = \mathrm{clamp01}\big(c \cdot \text{corrosionScale}\big)
\]

Base success probability:

\[
p_{\text{base}} = \exp(-A\,c_{\text{eff}})\;\exp(-B\,t)
\]

Then apply task difficulty and heat (see §3.3):

\[
p = \mathrm{clamp01}\big(p_{\text{base}}\;e^{-\alpha_P\,\text{heatPen}}\;e^{-\lambda_P\,d}\big)
\]

### 3.2 Fasteners (`kind === 'F'`)

From data:
- tool success rate \(s\) (`tool_success_rate`)
- nominal seizure prob \(q_s\) (`bolt_seizure_probability`)
- nominal jamming prob \(q_j\) (`bearing_jamming_probability`)
- tool temperature \(T_{\text{tool}}\) (optional; `temperature`)
- tool wear coefficient \(w\) (`tool_wear`)

Environment-adjusted seizure/jamming:

\[
q'_s = \mathrm{clamp01}(q_s + \text{seizureAdd})
\]
\[
q'_j = \mathrm{clamp01}(q_j + 0.5\cdot\text{seizureAdd})
\]

Base “mechanical” success term:

\[
p_0 = s\,(1-q'_s)\,(1-q'_j)
\]

Tool temperature factor: compute \(t_{\text{tool}}\) by normalizing tool temperatures across fasteners in the dataset to \([0,1]\), then:

\[
\text{tempFactor} = \exp(-B\,t_{\text{tool}})
\]

Wear accumulation: let \(N(m,\text{partCode})\) be the number of already-removed fasteners (bits set in \(m\)) that share the same `partCode` as \(v\). Then

\[
\text{wearState} = w \cdot N(m,\text{partCode})
\]

Wear penalty:

\[
\text{wearFactor} = \exp\big(-k_w \cdot \max(0,\text{wearState})\big)
\]

Base probability:

\[
p_{\text{base}} = p_0 \cdot \text{tempFactor} \cdot \text{wearFactor}
\]

Then apply task difficulty and heat (see §3.3):

\[
p = \mathrm{clamp01}\big(p_{\text{base}}\;e^{-\alpha_P\,\text{heatPen}}\;e^{-\lambda_P\,d}\big)
\]

### 3.3 Task difficulty and heat modifiers (used in both Dijkstra and GA evaluation)

Each node may have task difficulty \(d \ge 0\) from Excel (`taskDifficulty` or lookup by `taskCode`).

For fasteners, the planner tracks a “tool identity” (in `webapp.html` it uses `taskCode` as the shared-tool code) and a heat level \(L\).

Heat penalty:

\[
\text{heatPen} =
\begin{cases}
L & \text{if node is fastener and toolCode equals lastToolCode}\\
0 & \text{otherwise}
\end{cases}
\]

Heat update after selecting a node:
- If next node is a fastener with toolCode \(t\):
  - if \(t\) equals lastToolCode: \(L \leftarrow \min(\texttt{heatMax}, L+1)\)
  - else: \(L \leftarrow 1\), lastToolCode \(\leftarrow t\)
- If next node is a component: \(L \leftarrow \max(0, L-\texttt{heatCool})\) (cooling)

---

## 4) Effective removal force / torque \(F_{\text{eff}}\)

Constants:
- Task difficulty cost term: \(\lambda_F = \texttt{diffCostK} = 0.10\)
- Heat force term: \(\alpha_F = \texttt{heatF} = 0.15\)
- Fastener force scaling coefficients:
  - \(K_{\text{seiz}}=0.9,\ K_{\text{jam}}=0.55,\ K_{\text{env}}=0.4,\ K_{\text{wear}}=0.5\)

### 4.1 Components

Base force:
\[
F_{\text{base}} = 1.0
\]

If component data exists, reuse \(c_{\text{eff}}\) from §3.1 and define:
\[
\text{envBond} = \max(0,\text{corrosionScale}-1) + \text{seizureAdd}
\]
Multiplier:
\[
M = 1 + 0.55\,c_{\text{eff}} + 0.35\,\text{envBond}
\]
So:
\[
F_{\text{eff,base}} = \max(\varepsilon, F_{\text{base}} \cdot M)
\]

If component record is missing, a fallback multiplier is used:
\[
M = 1 + 0.25\left(\max(0,\text{corrosionScale}-1) + \text{seizureAdd}\right)
\]

Then apply heat + task difficulty (same form for all nodes):
\[
F_{\text{eff}} = \max(\varepsilon,\;F_{\text{eff,base}})\,(1+\alpha_F\,\text{heatPen})\,(1+\lambda_F\,d)
\]

### 4.2 Fasteners

Nominal base force from data:
\[
F_{\text{base}} = \texttt{removal\_force\_Nm}\quad(\text{fallback }1.0)
\]

Reuse \(q'_s, q'_j, \text{envBond}\) from above, and define clamped wear stress:

\[
\text{wearStress} = \mathrm{clamp01}(w \cdot N(m,\text{partCode}))
\]

Multiplier:
\[
M = 1
 + K_{\text{seiz}}\,q'_s
 + K_{\text{jam}}\,q'_j
 + K_{\text{env}}\,\text{envBond}
 + K_{\text{wear}}\,\text{wearStress}
\]

Base effective force:
\[
F_{\text{eff,base}} = \max(\varepsilon,\;F_{\text{base}} \cdot M)
\]

Apply heat + task difficulty:
\[
F_{\text{eff}} = F_{\text{eff,base}}\,(1+\alpha_F\,\text{heatPen})\,(1+\lambda_F\,d)
\]

---

## 5) Step cost and total cost

For choosing node \(v\) next from state \(m\):

\[
c(v,m) = \frac{F_{\text{eff}}(v,m)}{p(v,m)}
\]

For a removal sequence \((v_1, v_2, \dots, v_K)\) until the goal is removed:

\[
C = \sum_{k=1}^{K} c\big(v_k, m_{k-1}\big)
\]
where \(m_{k} = m_{k-1} \cup \{v_k\}\) (bitwise OR in code).

---

## 6) What the optimizers do with these equations

### 6.1 Dijkstra (exact optimum for this model)

Define a state graph where each state is a mask \(m\). For every available node \(v\) at \(m\), there is a transition:

\[
m' = m \cup \{v\},\quad \text{edge weight} = c(v,m)
\]

Dijkstra finds the **minimum total** \(C\) path from \(m=0\) to any \(m\) where the goal bit is set.

### 6.2 Genetic algorithm (approximate)

GA encodes a weight \(W(v)\) per node.

A chromosome induces a greedy policy:
- at each step, compute the set of available nodes
- pick the available node with maximum \(W(v)\)
- accumulate the same step cost \(c(v,m)\)

Fitness is the total cost \(C\) (lower is better).

---

## 7) Optional branching-risk benchmark mode

`webapp.html` also includes an optional stress-test mode (`Branching risk benchmark = On`) designed to create a short-term vs long-term trade-off for GA/Dijkstra comparison.

In this mode:

- **Path A (looks easy early):** `C11SX, C11DX, C12, C13, C14`
- **Path B (hard unlock):** `F3SX, F3DX`
- **Final bearing target for trap/safety effect:** `C1`

Conceptually:

1. Path A nodes get a short-term incentive (slightly higher \(p\), lower \(F_{\text{eff}}\)) before Path B is unlocked.
2. Path B nodes get a short-term penalty (lower \(p\), higher \(F_{\text{eff}}\)).
3. If all 5 Path A nodes are taken before Path B is unlocked, a **trap** is armed: final bearing (`C1`) becomes much riskier (lower \(p\), higher \(F_{\text{eff}}\)).
4. If Path B is unlocked early, the remaining sequence gets a safety/ease bonus.

This is implemented as state-dependent multipliers:

\[
p' = \mathrm{clamp01}(p \cdot m_p(v,m))
\quad,\quad
F'_{\text{eff}} = \max(\varepsilon,\;F_{\text{eff}} \cdot m_F(v,m))
\]

where \(m_p\) and \(m_F\) depend on node \(v\) and removed-state \(m\).

---

## Where to look in code

- Environment: `buildEnvContext` in `webapp.html`
- Probability: `makePForNodeIndex` (and helpers) in `webapp.html`
- Effective force: `makeEffectiveForceNmForIndex` in `webapp.html`
- Additive objective: `stepCost = effectiveForce / p` (used in Dijkstra and GA evaluation)

