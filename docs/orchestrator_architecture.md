# SatQuery AI — LangGraph Orchestration Architecture

## 1. Concept & Rationale
The SatQuery orchestrator manages multi-modal remote-sensing query execution via a stateful directed acyclic graph built on LangGraph. This satisfies the requirement for deterministic validation gates, auditable state passing, and granular execution tracing.

## 2. Graph Topology

```
                  ┌──────────────┐
                  │ [User Query] │
                  └──────┬───────┘
                         ▼
               ┌──────────────────┐
               │  Classify Node   │ (Router LLM: intent classification & parameter extraction)
               └─────────┬────────┘
                         │
           ┌─────────────┴─────────────┐
     (valid task)                (task == "reject")
           ▼                           │
 ┌──────────────────┐                  │
 │  Validate Node   │                  │ (deterministic rules check)
 └─────────┬────────┘                  │
           │                           │
     ┌─────┴─────┐                     │
  (valid)    (invalid)                 │
     │           └──────────┐          │
     ▼                      ▼          ▼
┌──────────┐          ┌───────────────────┐
│ Dispatch │          │    Reject Node    │ (structured rejection message)
└────┬─────┘          └─────────┬─────────┘
     │                          │
     ▼                          │
┌──────────┐                    │
│ Combine  │ (confidence calc,  │
│  Trace   │  trace generation) │
└────┬─────┘                    │
     │                          │
     ▼                          ▼
   [END]                      [END]
```

## 3. Node Responsibilities
1. **Classify Node (`classify`):**
   - Inputs: User natural language query and uploaded imagery metadata summary.
   - Model: Gemini 1.5 Flash (via `google-generativeai`).
   - Outputs: Selected tool name (`vqa_caption_ground`, `change_analysis`, `optical_sar_fusion`, or `reject`), mode, justification reason, and router confidence score.
2. **Validate Node (`validate`):**
   - Deterministic verification against `TOOL_REGISTRY` capability requirements.
   - Enforces image count, modality compatibility, and cross-image geospatial co-location via `same_location_score` (threshold $\ge 0.75$).
3. **Dispatch Node (`dispatch`):**
   - Dispatches validated parameters only to the appropriate model wrapper (`GeoChat`, `GeoLLaVA`, `EarthGPT`).
4. **Combine Node (`combine`):**
   - Calculates calibrated output confidence based on lexical hedging analysis.
   - Packages comprehensive execution trace for SQLite persistence and API response.
5. **Reject Node (`reject`):**
   - Formulates explainable rejection message whenever routing or validation fails.
