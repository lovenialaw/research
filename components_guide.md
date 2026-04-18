# Gearbox: Full Connection and Disassembly Sequence to Base

Based on **gearbox.xlsx** (Sheets 3, 4, 5, 6) — DPM, BOM, Component and Fastener mappings.

---

## 1. Code Mappings (Sheets 4, 5, 6)

### Fasteners (F) → Part Description

| Code   | BOM # | Part Description            | Qty | Removal Dir |
|--------|-------|-----------------------------|-----|-------------|
| **F1** | 16    | Screw M12×30 ISO 4016       | 8   | 100         |
| F2     | 17    | Positioning Pin ISO 2338    | 2   | 100         |
| F3SX   | 19    | Flange screws (left)        | 24  | 1           |
| F3DX   | 19    | Flange screws (right)       | 24  | 10          |
| F4     | 21    | Shaft 3 key                 | 1   | 100         |
| F5     | 22    | Shaft 4 key RH              | 1   | 100         |
| F6     | 23    | Shaft 4 key                 | 1   | 100         |
| F7     | 24    | Shaft 5 key                 | 1   | 100         |

### Components (C) → Part Description

| Code    | BOM # | Part Description                          | Qty |
|---------|-------|-------------------------------------------|-----|
| **C1**  | 1     | **Base**                                  | 1   |
| C2SX/DX | 2     | Bearings 12 (left/right)                  | 4   |
| C3SX/DX | 3     | Bearings 14 (left/right)                  | 2   |
| C4      | 4     | Shaft 5                                   | 1   |
| C5      | 5     | Shaft 4                                   | 1   |
| C6      | 6     | Shaft 3                                   | 1   |
| C7      | 7     | Shaft Sprocket 3                          | 1   |
| C8      | 8     | Shaft Sprocket 4 RH                       | 1   |
| C9      | 9     | Shaft Sprocket 4                          | 1   |
| C10     | 10    | Shaft Sprocket 5                          | 1   |
| C11SX/DX| 11    | Flange 4 with bearing sealing holes       | 3   |
| C12     | 12    | Flange 5 with bearing sealing holes       | 1   |
| C13     | 13    | Bearing sealing flange (no hole)         | 1   |
| C14     | 14    | Bearing sealing flange (with hole)       | 1   |
| C15     | 15    | Cover                                     | 1   |
| C16     | 18    | Hook                                      | 4   |
| C17     | 20    | Spacer                                    | 1   |

*SX = sinistra (left), DX = destra (right). Removal direction: 1, 10, 100 = binary codes for axes.*

---

## 2. DPM Logic: Why F1 Is Removed First

- **Sheet 3** contains the Disassembly Precedence Matrix (DPM).
- **F1** (Screw M12×30 ISO 4016) has a **row of all zeros** → no dependencies on any other element.
- Therefore F1 is the **first removable fastener**.

**Update rule after removing F1:**
1. Delete the **row** for F1
2. Delete the **column** for F1

Repeat: find the next component with an all-zero row in the reduced DPM, remove it, and update the matrix. This yields the full disassembly sequence.

---

## 3. Full Disassembly Sequence (to Expose Base C1)

Base (C1) is removed **last** (step 28). Below is the complete order from first to last:

| Step | Code   | Part Removed                                |
|------|--------|---------------------------------------------|
| 1    | **F1** | Screw M12×30 ISO 4016 (8 screws)            |
| 2    | F3SX   | Flange screws (left)                        |
| 3    | F3DX   | Flange screws (right)                       |
| 4    | C11SX  | Flange 4 with bearing sealing holes (left)  |
| 5    | C11DX  | Flange 4 with bearing sealing holes (right)|
| 6    | C12    | Flange 5 with bearing sealing holes         |
| 7    | C13    | Bearing sealing flange (no hole)           |
| 8    | C14    | Bearing sealing flange (with hole)         |
| 9    | C2SX   | Bearings 12 (left)                          |
| 10   | C16    | Hook (4 hooks)                              |
| 11   | F2     | Positioning Pin ISO 2338 (2 pins)           |
| 12   | C15    | Cover                                       |
| 13   | F7     | Shaft 5 key                                 |
| 14   | C2DX   | Bearings 12 (right)                          |
| 15   | C3SX   | Bearings 14 (left)                          |
| 16   | C3DX   | Bearings 14 (right)                         |
| 17   | C7     | Shaft Sprocket 3                            |
| 18   | C6     | Shaft 3                                     |
| 19   | C8     | Shaft Sprocket 4 RH                         |
| 20   | F6     | Shaft 4 key                                 |
| 21   | C9     | Shaft Sprocket 4                            |
| 22   | F5     | Shaft 4 key RH                              |
| 23   | C5     | Shaft 4                                     |
| 24   | C17    | Spacer                                      |
| 25   | C10    | Shaft Sprocket 5                            |
| 26   | F4     | Shaft 3 key                                 |
| 27   | C4     | Shaft 5                                     |
| 28   | **C1** | **Base**                                   |

---

## 4. Dependency Flow

### Phase 1 — Independent (all-zero rows)
- **F1** (Screw M12×30)
- **F3SX, F3DX** (Flange screws)
- **C11SX, C11DX, C12, C13, C14** (Flanges)
- **C16** (Hook)

### Phase 2 — Depends on F1
- **F2** (Positioning Pin): needs F1 removed (100 in F1 column)

### Phase 3 — Depends on F1, F2, Flange screws
- **C15** (Cover): needs F2 and F3 removed
- **C1** (Base): needs F1, F2, F3 — anchors everything

### Phase 4 — Shaft assembly chain

```
F7 removed → C2DX, C3SX, C3DX freed
    → C7 (Sprocket 3) freed
    → C6 (Shaft 3) freed
    → F6 removed → C9 (Sprocket 4) freed
    → F5 removed → C5 (Shaft 4) freed
    → C17 (Spacer), C10 (Sprocket 5) freed
    → F4 removed → C4 (Shaft 5) freed
    → C1 (Base) freed last
```

---

## 5. Connection Summary Table

| Element      | Blocks / Depends On           | Unblocks / Unblocked By          |
|-------------|-------------------------------|----------------------------------|
| **F1**      | None                          | F2, Cover, Base                  |
| F2          | F1                            | Cover, Base                      |
| F3SX, F3DX  | None                          | Flanges, Bearings, Shaft keys, Base |
| C11–C14     | F3 only                       | Bearings, shafts                 |
| C16 (Hook)  | None                          | —                                |
| C15 (Cover) | F2, F3                        | Shaft assembly access            |
| C1 (Base)   | F1, F2, F3, all shafts, bearings | — (removed last)              |
| F4–F7       | F3, C1                        | Shaft keys free shafts           |
| C2, C3      | F3, flanges                   | Shafts                           |
| C4–C6       | Keys (F4–F7), bearings        | Base                             |
| C7–C10      | Shafts, bearings              | Keys (F4–F7)                     |

---

## 6. Dependency Diagram (Simplified)

```
[F1] Screw M12×30 ──┬──► [F2] Positioning Pin ──► [C15] Cover
                    └──► [C1] Base (anchors all)
                    
[F3SX/DX] Flange screws ──► [C11–C14] Flanges
                    ──► [C2,C3] Bearings
                    ──► [F4–F7] Shaft keys ──► [C4–C6] Shafts
                    ──► [C7–C10] Sprockets
                    ──► [C1] Base

[C16] Hook — independent (all zeros)
```

---

## 7. Conclusion

- **First fastener:** F1 (Screw M12×30 ISO 4016) — all-zero row in DPM.
- **DPM update:** Remove F1 row and column, then iterate on the next all-zero row.
- **Base exposure:** Remove 27 other elements in the sequence above; Base (C1) is freed last as step 28.
- **Main connections:** F1 and F3 (flange screws) unlock F2 (positioning pin), flanges, bearings, shaft keys, and eventually the whole shaft/sprocket assembly anchored to the Base.
