# SatQuery AI — Spatial Evidence Map Integration Plan

> **Feature:** Spatial Evidence Map / Live Map
> **Frontend library:** ~~MapLibre GL JS~~ → **Actually built with Leaflet v1.9.4** (see Status Update below)
> **Status:** Approved for implementation, phased
> **Context:** The SatQuery AI backend and frontend already exist and are working. This is an **addition** to that existing system, not a rebuild.

---

## 🎉 Status Update — This Feature Is Now Built

As of Phase 4 of a separate remediation effort (which also added a real Geo Evidence Engine and SAM 2 segmentation ahead of this plan), the Spatial Evidence Map is **implemented and verified working** — confirmed via a direct code audit:

- **Library used: Leaflet v1.9.4** (CDN-loaded), not MapLibre GL JS as originally specified here. This is a sound substitution — same embedding approach (`streamlit.components.v1.html()`, no build tooling), same architecture split (backend owns GIS math, frontend only renders). Functionally equivalent goal achieved with a different library.
- **Confirmed: only one map system exists** in the codebase — no duplicate/conflicting implementation was created.
- **Confirmed: real GeoJSON + real area-in-hectares** is rendered, sourced genuinely from `geo_engine/` (`quantification.py` for area math with proper CRS handling, `spatial.py` for mask-to-polygon vectorization) — not faked or hardcoded, satisfying Rule 6 below.
- **Layers implemented:** satellite basemap (Esri World Imagery + a dark CartoDB alternate), GeoJSON change-area polygons (red, clickable popups), **SAM 2 segmentation polygons** (cyan, clickable popups with confidence — SAM 2 is now real, see Rule 3 update below), change-mask overlay (via `st.image()`, not a Leaflet tile layer), T1/T2 comparison (via chat cards/static panels, **not** an interactive swipe layer on the map canvas as originally envisioned).
- **Two things from the original plan were done differently than specified**, worth knowing about, not necessarily wrong:
  - T1/T2/Change comparison (Step 7 below) is not an in-map draggable swipe divider — it's static image panels shown alongside the map instead.
  - Change-mask overlay is a separate expandable image view, not a toggleable raster layer inside the map itself.
- **Rule 3 below is now outdated** — SAM 2 exists and is intentionally integrated, per Phase 4. Treat the rule as superseded (see note in place).

**What this means practically:** the phased implementation order further below is now historical record of what was planned, not a to-do list — treat it as reference for what exists and why, not as pending work.

---



> **Rule 1 — Do not rebuild or change the existing architecture.** Do not modify, refactor, rename, or "clean up" any existing file, route, model wrapper, orchestrator node, database table, or GUI component that isn't explicitly part of this map feature. The existing pipeline below stays exactly as it is — this feature only extends its end. If something existing seems like it needs a change to support this feature, **stop and ask first** — do not just make the change.
>
> **Rule 2 — One step at a time.** Build only one step below, then stop and wait for explicit confirmation before beginning the next one. After **Step 1 specifically**, stop and show the exact files changed, and continue only after confirmation — the same reporting standard applies to every step after that too.
>
> **Rule 3 — No new AI models.** ~~Do not add SAM 2...~~ **SUPERSEDED as of Phase 4: SAM 2 is now real, tested, and intentionally integrated for segmentation.** The original intent of this rule (don't casually bolt on new models without a deliberate decision) still applies to *anything beyond* SAM 2 — no further new models should be added to this feature without the same level of explicit review SAM 2 got.
>
> **Rule 4 — Report outside work needed.** After each step, explicitly state if any outside/manual work is needed (new package installs, API keys, accounts) — or say clearly if none is needed. Same as the project-wide rule.
>
> **Rule 5 — No duplicated GIS logic in the frontend.** The backend owns CRS, area, bounds, and all GIS measurements. The frontend must never calculate these itself — it only renders what the backend returns.
>
> **Rule 6 — Never hardcode or invent values.** Change-region popups, evidence panel numbers, and grounding coordinates must always come from the actual backend result. Never use demo/placeholder values, and never invent grounding coordinates that weren't actually returned by the model/backend.

---

## The Goal (read this first)

> **"AI answer ko geographically prove karna."** — The map is not a decorative visualization. It's part of the product's core USP: proving the AI's answer geographically, not just stating it in text.

After the existing AI analysis finishes, the result should automatically visualize geographically on an interactive map — no manual step, no separate page load.

Final flow:

```
User Query
   ↓
AI Analysis
   ↓
Independent Evidence
   ↓
Quantification
   ↓
Spatial Evidence
   ↓
Interactive Map
```

---

## Existing Pipeline — Stays Unchanged

```
Upload
  ↓
Metadata
  ↓
LangGraph
  ↓
Router
  ↓
Specialist Model
  ↓
Result
```

This feature extends the end of it only:

```
Specialist Model
  ↓
Geo Evidence / Spatial Processing
  ↓
Spatial Evidence JSON
  ↓
MapLibre
```

---

## Backend Addition — Spatial Evidence Service

A new module that extracts, from the uploaded georeferenced raster:

- CRS
- Bounds
- Center
- Transform
- Resolution
- Image dimensions

**Do not assume a fixed resolution** (e.g. don't hardcode 10m) — read it from the actual raster.

Expected shape of what the backend returns:

```json
{
  "crs": "EPSG:4326",
  "bounds": {
    "west": 75.70,
    "south": 26.85,
    "east": 75.85,
    "north": 27.00
  },
  "center": [75.775, 26.925],
  "layers": {
    "satellite": "...",
    "change_mask": "...",
    "change_geojson": "...",
    "grounding": "..."
  }
}
```

### API

```
GET /query/{query_id}/spatial-evidence
```

Returns everything the map needs — CRS, bounds, center, and layer data. The frontend must not calculate CRS, area, bounds, or any GIS measurement itself; it only consumes this endpoint.

---

## Change Analysis Integration

> **Status note:** A visualization engine (`orchestrator/visualization.py`) already exists and produces a real 256×256 boolean `change_mask` array plus a rendered PNG heatmap (`render_change_heatmap`). **This map feature still needs that raw array converted into real geo-referenced GeoJSON polygons with area-in-hectares calculated from actual pixel resolution** — that conversion does not exist yet and is the actual remaining prerequisite for Steps 5–6 below, not a full change-detection pipeline from scratch.

Existing workflow:

```
T1 + T2 → GeoLLaVA + Geo Evidence Engine
```

This feature shows that detected change geographically — render the generated change mask/GeoJSON as a map overlay. Clicking a changed region opens a popup:

```
CHANGE EVIDENCE

Type: Built-up Increase
Changed Area: 18.42 ha
Change: +12.8%
Primary Model: GeoLLaVA
Secondary Evidence: Spectral Difference
Agreement: HIGH
```

All values here must come from the real backend result — never hardcoded.

## Grounding Integration

```
GeoChat → grounding coordinates → GeoJSON → MapLibre
```

Render only the boxes/polygons actually returned by GeoChat. Clicking one shows the object/evidence GeoChat returned. Never invent coordinates.

## Evidence Panel

A side panel next to the map, connected to real execution data:

```
SPATIAL EVIDENCE

Change Detected: YES
Changed Area: 18.42 ha
Change: +12.8%
Agreement: HIGH
Evidence Confidence: 91 / 100
Primary Model: GeoLLaVA
Secondary Evidence: Spectral Difference
```

---

## Step 0 — Pre-Flight Verification (must pass before Step 1)

> **Do not start Step 1 until this passes.** This feature depends on two things that aren't confirmed yet — verify both first.

**0a. Verify georeferencing actually survives preprocessing.**
Open a real preprocessed image from `data/processed` (the same one used in the dry run, e.g. `tile_001_s2_optical`) with rasterio, and check its `.crs`, `.bounds`, and `.transform`.

- **If present:** proceed to Step 1 as planned.
- **If missing/None:** check whether the original source file (before Step 7's preprocessing) still has this metadata. If preprocessing is stripping it, this must be fixed first — likely by re-running Step 7 in a way that preserves georeferencing (e.g. keep bounds/CRS as sidecar metadata, or preprocess directly from the original GeoTIFF instead of a stripped PNG) — before any part of this map feature can show real geographic data. Do not fabricate or hardcode bounds to work around missing data — that violates Rule 6.

**0b. Confirm the frontend embedding approach.**
MapLibre GL JS will be embedded into the existing Streamlit result page using `streamlit.components.v1.html()`, loading `maplibre-gl` from a CDN inside the HTML string — no npm/webpack build step needed. The embedded JS calls `GET /query/{query_id}/spatial-evidence` directly via `fetch()`. Confirm this is workable with the current Streamlit setup before Step 1 begins.

---



**Step 1 — Install/configure MapLibre GL JS.**
Add the dependency and basic setup only. *After this step: stop, show the exact files changed, and wait for confirmation before continuing.*

**Step 2 — Add the Map component to the existing result page.**
Integrate into the current analysis/result page — not a new standalone page.

**Step 3 — Connect `GET /query/{query_id}/spatial-evidence`.**
Wire the frontend to call this endpoint after analysis completes.

**Step 4 — Render the satellite image and bounds.**
Load the raster layer and fit the map to the image's real geographic bounds.

**Step 5 — Render the change GeoJSON.**
Display the change-detection polygons as a map overlay.

**Step 6 — Add clickable change regions.**
Clicking a region opens the popup shown above, populated from real backend data.

**Step 7 — Add T1 / T2 / CHANGE comparison.**
Controls: `[T1] [T2] [CHANGE]`, ideally with a before/after swipe comparison. T1 shows the first image, T2 the second, CHANGE shows the evidence mask.

**Step 8 — Add grounding boxes.**
Render GeoChat's actual returned grounding geometry on the map, clickable.

**Step 9 — Add layer toggles + opacity.**

```
☑ Satellite Image
☑ Change Areas
☐ Grounding Boxes
☐ Evidence Points
```

Every analytical layer supports an opacity control.

**Step 10 — Connect the Evidence Panel to actual backend data.**
Wire every value in the side panel to the real execution result — no more placeholders anywhere in the feature.

---

*This file governs the Spatial Evidence Map feature only. It does not replace or override `plan.md` or `rules_and_working_helper.md` — treat all three as complementary, and re-read Rule 1 above before touching any file outside this feature's scope.*
