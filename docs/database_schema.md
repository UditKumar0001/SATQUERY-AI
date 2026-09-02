# SatQuery AI — Database Architecture & Schema Design

## 1. Overview
The persistence layer provides an auditable execution summary for all queries, images, model inferences, and execution traces. SQLite with SQLAlchemy ORM is selected for local, zero-setup, reproducible execution with portability to PostgreSQL.

## 2. Entity-Relationship Diagram

```
┌─────────────────────────────────┐           ┌─────────────────────────────────┐
│             queries             │           │         uploaded_images         │
├─────────────────────────────────┤           ├─────────────────────────────────┤
│ id (INTEGER, PK)                │───(1:N)──>│ id (INTEGER, PK)                │
│ query_text (TEXT)               │           │ query_id (INTEGER, FK)          │
│ selected_task (VARCHAR)         │           │ filepath (VARCHAR)              │
│ model_used (VARCHAR)            │           │ modality (VARCHAR)              │
│ mode (VARCHAR, nullable)        │           │ format (VARCHAR)                │
│ router_confidence (FLOAT)       │           │ timestamp_tag (VARCHAR, nullable)│
│ output_confidence (FLOAT)       │           └─────────────────────────────────┘
│ validation_msg (VARCHAR)        │
│ created_at (DATETIME)           │           ┌─────────────────────────────────┐
└─────────────────────────────────┘           │        execution_traces         │
                 │                            ├─────────────────────────────────┤
                 └────────────────────(1:1)──>│ id (INTEGER, PK)                │
                                              │ query_id (INTEGER, FK)          │
                                              │ trace_json (TEXT)               │
                                              │ created_at (DATETIME)           │
                                              └─────────────────────────────────┘
```

## 3. Table Specifications

### `queries`
Primary audit log table tracking user intent, routing decisions, confidence calibrations, and validation statuses.
- `id`: Unique integer identifier (Primary Key, autoincrementing).
- `query_text`: The raw text prompt submitted by the user.
- `selected_task`: Classification output (`vqa_caption_ground`, `change_analysis`, `optical_sar_fusion`, or `reject`).
- `model_used`: The specific vision-language model dispatched (`GeoChat`, `GeoLLaVA`, `EarthGPT`, or `none`).
- `mode`: Task operational mode (e.g., `vqa`, `caption`, `ground`, or `null`).
- `router_confidence`: Confidence score (0.0 – 1.0) emitted by the router LLM.
- `output_confidence`: Calibrated confidence score (0.0 – 1.0) based on model response hedging analysis.
- `validation_msg`: Deterministic compatibility validation feedback (e.g. `ok`, or reason for rejection).
- `created_at`: UTC timestamp of query execution.

### `uploaded_images`
Detailed ledger of imagery passed per query, supporting auditability of rejection rates by sensor type and format.
- `id`: Unique integer identifier (Primary Key).
- `query_id`: Foreign Key referencing `queries.id`.
- `filepath`: On-disk path to the stored image file.
- `modality`: Extracted image modality (`optical`, `SAR`, or `unknown`).
- `format`: Raster driver / format (e.g., `GTiff`, `PNG`, `JPEG`).
- `timestamp_tag`: Extracted acquisition timestamp (from EXIF/TIFF metadata or filename tags).

### `execution_traces`
Full, uncompressed JSON dump of the end-to-end LangGraph state and execution diagnostics.
- `id`: Unique integer identifier (Primary Key).
- `query_id`: Foreign Key referencing `queries.id` (1:1 relationship).
- `trace_json`: Complete JSON string serialized from the execution trace object.
- `created_at`: UTC timestamp when trace was finalized.

## 4. Technical Justification
- **SQLite:** Serverless, zero-configuration local storage stored at `satquery.db`, ideal for edge and workstation evaluation.
- **SQLAlchemy ORM:** Provides database-agnostic abstractions, allowing instantaneous transition to PostgreSQL if hosted deployment is desired without changing business logic.
