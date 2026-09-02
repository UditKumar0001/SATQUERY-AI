# SatQuery AI — Build It In Order

*Team Debuggers Den · Step-by-Step Build Guide*

Every step from an empty folder to a deployed system, in the order you actually run them.
    Each step says why it happens now, then gives the exact command or code.

**Orchestration: LangGraph · Database: SQLite/SQLAlchemy · Models: GeoChat / GeoLLaVA / EarthGPT · Budget: ₹2,000**

> **Execution rule:** This plan is being developed in Antigravity. Work through it one step at a time — after developing/implementing each step in Antigravity, stop and wait for explicit confirmation ("start step N") before beginning the next one. Do not auto-continue to the next step. This rule applies to every step, from Step 1 all the way through Step 40, with no exceptions until the plan is fully complete.

## Table of Contents

**Stage A — Foundations**

- [Step 1 — Initialize the project folder](#s1)
- [Step 2 — Virtual environment & dependencies](#s2)
- [Step 3 — Environment variables](#s3)
- [Step 4 — Design the database](#s4)
- [Step 5 — Implement the database layer](#s5)

**Stage B — Data**

- [Step 6 — Download dataset subsets](#s6)
- [Step 7 — Preprocess imagery](#s7)

**Stage C — Models**

- [Step 8 — Build the GeoChat wrapper](#s8)
- [Step 9 — Test GeoChat standalone](#s9)
- [Step 10 — Build the GeoLLaVA wrapper](#s10)
- [Step 11 — Test GeoLLaVA standalone](#s11)
- [Step 12 — Build the EarthGPT wrapper](#s12)
- [Step 13 — Fine-tune EarthGPT with LoRA](#s13)
- [Step 14 — Evaluate the fine-tune](#s14)

**Stage D — Orchestration (LangGraph)**

- [Step 15 — Metadata extraction module](#s15)
- [Step 16 — Compatibility checker](#s16)
- [Step 17 — Tool registry](#s17)
- [Step 18 — Install & scaffold LangGraph](#s18)
- [Step 19 — Define the graph state](#s19)
- [Step 20 — Classify node (router LLM)](#s20)
- [Step 21 — Validate node](#s21)
- [Step 22 — Dispatch node](#s22)
- [Step 23 — Combine node + trace](#s23)
- [Step 24 — Wire the graph together](#s24)
- [Step 25 — Test the orchestrator end-to-end](#s25)

**Stage E — API**

- [Step 26 — FastAPI app skeleton](#s26)
- [Step 27 — Build the /query route](#s27)
- [Step 28 — Build the /health route](#s28)
- [Step 29 — Build the /history route](#s29)
- [Step 30 — Report generator](#s30)

**Stage F — Frontend**

- [Step 31 — Streamlit GUI](#s31)
- [Step 32 — CLI tool](#s32)

**Stage G — Testing**

- [Step 33 — Write the test suite](#s33)
- [Step 34 — Run local end-to-end tests](#s34)
- [Step 35 — Benchmark against public datasets](#s35)

**Stage H — Deployment**

- [Step 36 — Dockerize](#s36)
- [Step 37 — Deploy the backend](#s37)
- [Step 38 — Deploy the frontend](#s38)
- [Step 39 — Push model weights to Hugging Face Hub](#s39)
- [Step 40 — Final checks & submission packaging](#s40)

## Stage A — Foundations

### Step 1 — Initialize the project folder

> Why now: everything else — code, data, weights — needs somewhere consistent to live before you write a single line of logic.

```
mkdir satquery-ai && cd satquery-ai
mkdir -p data/raw data/processed models/weights finetune \
         orchestrator backend frontend tests docs
touch README.md requirements.txt .env.example .gitignore
git init
```

```
satquery-ai/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── data/
│   ├── raw/
│   └── processed/
├── models/
│   ├── geochat_wrapper.py
│   ├── geollava_wrapper.py
│   ├── earthgpt_wrapper.py
│   └── weights/
├── finetune/
│   └── lora_earthgpt_bigearthnet.py
├── orchestrator/
│   ├── db.py
│   ├── metadata.py
│   ├── compatibility.py
│   ├── registry.py
│   ├── graph_state.py
│   ├── nodes.py
│   └── graph.py
├── backend/
│   ├── main.py
│   └── report.py
├── frontend/
│   ├── streamlit_app.py
│   └── cli.py
├── tests/
└── docs/
```

### Step 2 — Virtual environment & dependencies

> Why now: every subsequent step imports a library — install them all up front so nothing breaks mid-tutorial.

```
conda create -n satquery python=3.10 -y
conda activate satquery

pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install transformers accelerate peft bitsandbytes datasets
pip install langgraph langchain-core
pip install fastapi uvicorn python-multipart sqlalchemy
pip install streamlit typer[all] rich
pip install rasterio pillow numpy opencv-python
pip install google-generativeai
pip install reportlab pytest
pip freeze > requirements.txt
```

### Step 3 — Environment variables

> Why now: the router LLM (Step 20) and database path (Step 5) both need config that must never be hardcoded into source files.

```
# .env.example
GEMINI_API_KEY=your-key-here
DATABASE_URL=sqlite:///./satquery.db
MODEL_DEVICE=cuda
```

```
cp .env.example .env
# fill in your real key, then load it in Python with:
from dotenv import load_dotenv
load_dotenv()
```

### Step 4 — Design the database

> Why now: before writing orchestrator code, decide what gets persisted — every query, what task it routed to, and the full execution trace — so the "auditable execution summary" the brief requires has a permanent record, not just an in-memory response.

#### Entity-relationship design

```
┌────────────────┐        ┌───────────────────┐
│    queries      │        │  uploaded_images   │
├────────────────┤        ├───────────────────┤
│ id (PK)         │───┐    │ id (PK)             │
│ query_text      │   └───>│ query_id (FK)       │
│ selected_task   │        │ filepath            │
│ model_used      │        │ modality            │
│ mode            │        │ format              │
│ router_conf     │        │ timestamp_tag       │
│ output_conf     │        └───────────────────┘
│ validation_msg  │
│ created_at      │        ┌───────────────────┐
└────────────────┘        │ execution_traces    │
        │                  ├───────────────────┤
        └─────────────────>│ id (PK)             │
                           │ query_id (FK)       │
                           │ trace_json          │
                           │ created_at          │
                           └───────────────────┘
```

| Table | Purpose |
| --- | --- |
| `queries` | One row per user request — the task the router picked, the model used, confidence scores. This is your primary audit table. |
| `uploaded_images` | One row per image in a request — modality, format, timestamp — so you can later analyze which input types are being rejected most. |
| `execution_traces` | Full JSON snapshot of the trace object per query — the raw evidence, kept separately from `queries` so the summary table stays lightweight to query. |

SQLite is the right choice here, not Postgres — zero setup cost, file-based, and this system has no concurrent-write load that would need a real client-server database. If you later need Postgres for a hosted multi-user version, the SQLAlchemy layer in Step 5 makes that a one-line connection-string change.

### Step 5 — Implement the database layer

> Why now: the ORM models must exist before the orchestrator (Stage D) or API (Stage E) can write to them.

```
# orchestrator/db.py
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime, timezone
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./satquery.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Query(Base):
    __tablename__ = "queries"
    id = Column(Integer, primary_key=True)
    query_text = Column(Text)
    selected_task = Column(String)
    model_used = Column(String)
    mode = Column(String, nullable=True)
    router_confidence = Column(Float)
    output_confidence = Column(Float)
    validation_msg = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    images = relationship("UploadedImage", back_populates="query")
    trace = relationship("ExecutionTrace", back_populates="query", uselist=False)

class UploadedImage(Base):
    __tablename__ = "uploaded_images"
    id = Column(Integer, primary_key=True)
    query_id = Column(Integer, ForeignKey("queries.id"))
    filepath = Column(String)
    modality = Column(String)
    format = Column(String)
    timestamp_tag = Column(String, nullable=True)

    query = relationship("Query", back_populates="images")

class ExecutionTrace(Base):
    __tablename__ = "execution_traces"
    id = Column(Integer, primary_key=True)
    query_id = Column(Integer, ForeignKey("queries.id"))
    trace_json = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    query = relationship("Query", back_populates="trace")

def init_db():
    Base.metadata.create_all(engine)
```

```
# run once to create satquery.db
python -c "from orchestrator.db import init_db; init_db()"
```

## Stage B — Data

### Step 6 — Download dataset subsets

> Why now: models can't be tested or fine-tuned without data, and downloading is slow — kick it off before writing more code so it finishes in the background.

```
# data/download_subsets.py
from huggingface_hub import snapshot_download
import os

def get_bigearthnet_subset(n_tiles=4000, out_dir="data/raw/bigearthnet"):
    os.makedirs(out_dir, exist_ok=True)
    # sample n_tiles paired Sentinel-1 (SAR) + Sentinel-2 (optical) patches
    # from the official BigEarthNet download tool, keeping S1/S2 pairs linked
    ...

def get_vrsbench_subset(out_dir="data/raw/vrsbench"):
    snapshot_download(repo_id="VRSBench/VRSBench", repo_type="dataset", local_dir=out_dir)

def get_rsvqa_subset(out_dir="data/raw/rsvqa"):
    ...

def get_cdvqa_subset(out_dir="data/raw/cdvqa"):
    ...

if __name__ == "__main__":
    get_bigearthnet_subset()
    get_vrsbench_subset()
    get_rsvqa_subset()
    get_cdvqa_subset()
```

```
python data/download_subsets.py
```

### Step 7 — Preprocess imagery

> Why now: every model wrapper in Stage C expects a common tensor format — build the converter once here instead of repeating it per model.

```
# data/preprocess.py
import rasterio, numpy as np, torch

def load_geotiff(path: str):
    with rasterio.open(path) as src:
        arr = src.read()
        meta = src.meta
    return torch.from_numpy(arr.astype(np.float32)), meta

def normalize_optical(tensor):
    return (tensor - tensor.mean()) / (tensor.std() + 1e-6)

def normalize_sar(tensor):
    tensor = torch.log1p(torch.clamp(tensor, min=0))   # SAR backscatter is log-scaled
    return (tensor - tensor.mean()) / (tensor.std() + 1e-6)
```

## Stage C — Models

### Step 8 — Build the GeoChat wrapper

> Why now: Task A (single-image VQA/caption/ground) is the mandatory baseline — build and verify it first before touching the harder two-image tasks.

```
# models/geochat_wrapper.py
from transformers import AutoModelForCausalLM, AutoProcessor
import torch

class GeoChatModel:
    def __init__(self, model_id="MBZUAI/GeoChat-7B", device="cuda"):
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, load_in_4bit=True, device_map="auto"
        )
        self.device = device

    def _prompt(self, query, mode):
        if mode == "caption":
            return f"[caption] Describe the land-cover and major objects visible in this image. {query}"
        if mode == "ground":
            return f"[grounding] Locate the region referred to: {query}"
        return f"[vqa] {query}"

    def infer(self, image, query, mode="vqa"):
        prompt = self._prompt(query, mode)
        inputs = self.processor(images=image, text=prompt, return_tensors="pt").to(self.device)
        with torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=256)
        text = self.processor.decode(out[0], skip_special_tokens=True)
        result = {"text": text, "mode": mode}
        if mode == "ground":
            result["bbox"] = self._parse_bbox(text)
        return result

    def _parse_bbox(self, text):
        # GeoChat emits normalized coordinate tokens for grounding mode — parse here
        ...
```

### Step 9 — Test GeoChat standalone

> Why now: confirm the wrapper works in isolation before it's buried inside the orchestrator, where failures are harder to trace.

```
# quick manual smoke test
from models.geochat_wrapper import GeoChatModel
from PIL import Image

m = GeoChatModel()
img = Image.open("data/raw/vrsbench/sample_001.png")
print(m.infer(img, "Describe the land-cover and major objects visible in this image.", mode="caption"))
```

### Step 10 — Build the GeoLLaVA wrapper

> Why now: Task B (bi-temporal change) is the next mandatory item — build it next while the single-image pattern from Step 8 is fresh.

```
# models/geollava_wrapper.py
from transformers import AutoModelForCausalLM, AutoProcessor
import torch

class GeoLLaVAModel:
    def __init__(self, model_id="<geollava-checkpoint>", device="cuda"):
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, load_in_4bit=True, device_map="auto"
        )
        self.device = device

    def infer(self, image_t1, image_t2, query):
        prompt = f"[change] Compare image A (earlier) and image B (later). {query}"
        inputs = self.processor(images=[image_t1, image_t2], text=prompt, return_tensors="pt").to(self.device)
        with torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=256)
        text = self.processor.decode(out[0], skip_special_tokens=True)
        return {"text": text, "change_mask": None}
```

### Step 11 — Test GeoLLaVA standalone

```
from models.geollava_wrapper import GeoLLaVAModel
from PIL import Image

m = GeoLLaVAModel()
t1 = Image.open("data/raw/cdvqa/pair_004_before.png")
t2 = Image.open("data/raw/cdvqa/pair_004_after.png")
print(m.infer(t1, t2, "What changed between these two dates, and where did the change occur?"))
```

### Step 12 — Build the EarthGPT wrapper

> Why now: Task C (optical-SAR fusion) is last because it's the model you'll fine-tune next — build the base wrapper first so the fine-tune in Step 13 has something to load into.

```
# models/earthgpt_wrapper.py
from transformers import AutoModelForCausalLM, AutoProcessor
from peft import PeftModel
import torch, os

class EarthGPTModel:
    def __init__(self, base_model_id="<earthgpt-checkpoint>",
                 lora_adapter_path="models/weights/earthgpt-bigearthnet-lora",
                 device="cuda"):
        self.processor = AutoProcessor.from_pretrained(base_model_id)
        base = AutoModelForCausalLM.from_pretrained(base_model_id, load_in_4bit=True, device_map="auto")
        if os.path.exists(lora_adapter_path):
            self.model = PeftModel.from_pretrained(base, lora_adapter_path)
        else:
            self.model = base   # fall back to zero-shot until Step 13 is done
        self.device = device

    def infer(self, optical_image, sar_image, query):
        prompt = f"[fusion] Jointly analyze the optical and SAR images. {query}"
        inputs = self.processor(images=[optical_image, sar_image], text=prompt, return_tensors="pt").to(self.device)
        with torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=256)
        text = self.processor.decode(out[0], skip_special_tokens=True)
        return {"text": text, "fused_map": None}
```

### Step 13 — Fine-tune EarthGPT with LoRA

> Why now: this satisfies the brief's mandatory "at least one component must be fine-tuned on BigEarthNet.txt or open data" requirement, and it's applied to EarthGPT specifically because BigEarthNet is multisensor (Sentinel-1 SAR + Sentinel-2 optical) by construction — the same modality pairing Task C needs.

```
# finetune/lora_earthgpt_bigearthnet.py
from transformers import AutoModelForCausalLM, AutoProcessor, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model
from datasets import load_dataset

BASE_MODEL = "<earthgpt-checkpoint>"

def build_instruction_dataset(processed_dir="data/processed/bigearthnet"):
    # synthesize (optical, sar, instruction, answer) tuples from BigEarthNet's
    # multi-label land-cover annotations
    return load_dataset("json", data_files=f"{processed_dir}/instructions.jsonl")["train"]

def main():
    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, load_in_4bit=True, device_map="auto")
    lora_config = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                              target_modules=["q_proj", "v_proj"], task_type="CAUSAL_LM")
    model = get_peft_model(model, lora_config)
    train_ds = build_instruction_dataset()

    args = TrainingArguments(
        output_dir="models/weights/earthgpt-bigearthnet-lora",
        per_device_train_batch_size=2, gradient_accumulation_steps=8,
        num_train_epochs=2, learning_rate=2e-4, fp16=True,
        logging_steps=20, save_strategy="epoch", report_to="none",
    )
    Trainer(model=model, args=args, train_dataset=train_ds).train()
    model.save_pretrained("models/weights/earthgpt-bigearthnet-lora")

if __name__ == "__main__":
    main()
```

```
python finetune/lora_earthgpt_bigearthnet.py
```

> ⚠️ **Note:** Keep the subset to ~3,000–5,000 tiles and 2 epochs — this fits inside one free-tier Colab T4 session (~4-hour cap) with 4-bit loading and gradient accumulation.

### Step 14 — Evaluate the fine-tune

> Why now: you need a before/after number to prove adaptation happened — collect it right after training while the zero-shot baseline from Step 12's test is still fresh for comparison.

```
# finetune/evaluate.py
from models.earthgpt_wrapper import EarthGPTModel

model = EarthGPTModel()   # now loads the LoRA adapter automatically (Step 12 logic)
# run against a held-out slice of your BigEarthNet subset, log agreement with
# ground-truth land-cover labels before vs after fine-tuning
```

Record the before/after numbers — this becomes your adaptation-evidence paragraph in the final report.

## Stage D — Orchestration (LangGraph)

### Step 15 — Metadata extraction module

> Why now: the orchestrator can't check "count, modality, format, metadata, compatibility" (a direct brief requirement) without first being able to read that metadata out of an uploaded file.

```
# orchestrator/metadata.py
import rasterio

def extract_metadata(filepath: str) -> dict:
    with rasterio.open(filepath) as src:
        bands, crs, bounds, driver = src.count, src.crs, src.bounds, src.driver
        tags = src.tags()
        timestamp = tags.get("TIFFTAG_DATETIME") or tags.get("acquisition_date")
    modality = "SAR" if bands in (1, 2) else ("optical" if bands >= 3 else "unknown")
    return {"bands": bands, "crs": str(crs), "bounds": bounds, "format": driver,
            "timestamp": timestamp, "modality": modality}
```

### Step 16 — Compatibility checker

> Why now: metadata alone (Step 15) isn't reliable — real uploads often lack geotags — so add an embedding-based sanity check before the validation gate trusts "same location."

```
# orchestrator/compatibility.py
import torch
from remoteclip import RemoteCLIPModel

_clip = RemoteCLIPModel.from_pretrained("remoteclip-vit-b32")
SAME_LOCATION_THRESHOLD = 0.75

def same_location_score(img1, img2) -> float:
    with torch.no_grad():
        e1, e2 = _clip.encode_image(img1), _clip.encode_image(img2)
    return torch.nn.functional.cosine_similarity(e1, e2).item()
```

### Step 17 — Tool registry

> Why now: this is the "predefined registry" the brief explicitly requires the controller to select from — define it before writing any routing logic that depends on it.

```
# orchestrator/registry.py
TOOL_REGISTRY = {
    "vqa_caption_ground": {
        "model": "GeoChat",
        "requires": {"num_images": 1, "modality": ["optical", "SAR"]},
        "params": ["query", "mode"], "output": ["text", "bbox"]
    },
    "change_analysis": {
        "model": "GeoLLaVA",
        "requires": {"num_images": 2, "same_location": True, "different_timestamp": True},
        "params": ["query"], "output": ["text", "change_mask"]
    },
    "optical_sar_fusion": {
        "model": "EarthGPT",
        "requires": {"num_images": 2, "modalities": ["optical", "SAR"], "co_registered": True},
        "params": ["query"], "output": ["text", "fused_map"]
    }
}
```

### Step 18 — Install & scaffold LangGraph

> Why now: everything above this point is a plain function — from here on, the orchestrator becomes a stateful graph, so the state contract must be defined before any node is written.

```
pip install langgraph langchain-core   # already in Step 2, confirming here
```

LangGraph models your controller as nodes (classify → validate → dispatch → combine) connected by edges, with conditional branching for the reject path — this maps directly onto the brief's own description of the controller's steps, and gives you built-in state passing and execution tracing for free.

### Step 19 — Define the graph state

```
# orchestrator/graph_state.py
from typing import TypedDict, Optional, List, Dict, Any

class AgentState(TypedDict):
    query: str
    images_meta: List[Dict[str, Any]]
    images_raw: List[str]
    task: Optional[str]
    mode: Optional[str]
    router_confidence: Optional[float]
    validation_ok: Optional[bool]
    validation_msg: Optional[str]
    result: Optional[Dict[str, Any]]
    trace: Optional[Dict[str, Any]]
```

### Step 20 — Classify node (router LLM)

> Why now: this is the entry node of the graph — it must run first so every downstream node knows which task it's handling.

```
# orchestrator/nodes.py (part 1 of 4)
import google.generativeai as genai
import json, os
from .graph_state import AgentState

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
_router = genai.GenerativeModel("gemini-1.5-flash")

ROUTER_SYSTEM_PROMPT = """
You are a task router for a remote-sensing analysis system with exactly three tools:
  - vqa_caption_ground: single image, VQA/caption/grounding
  - change_analysis: two images, same location, different timestamps
  - optical_sar_fusion: two images, one optical one SAR, co-registered

Output ONLY valid JSON:
{"task": "<tool name or reject>", "mode": "vqa|caption|ground|null",
 "reason": "<short justification>", "confidence": 0.0-1.0}
"""

def classify_node(state: AgentState) -> AgentState:
    summary = {"num_images": len(state["images_meta"]),
               "modalities": [m["modality"] for m in state["images_meta"]]}
    prompt = f"{ROUTER_SYSTEM_PROMPT}\n\nQuery: {state['query']}\nMetadata: {json.dumps(summary)}"
    response = _router.generate_content(prompt)
    try:
        routed = json.loads(response.text)
    except json.JSONDecodeError:
        routed = {"task": "reject", "mode": None, "reason": "invalid router output", "confidence": 0.0}

    state["task"] = routed["task"]
    state["mode"] = routed.get("mode")
    state["router_confidence"] = routed["confidence"]
    return state
```

### Step 21 — Validate node

> Why now: never trust the router's classification alone — this deterministic node runs immediately after classify and is what actually enforces the registry's requires rules.

```
# orchestrator/nodes.py (part 2 of 4)
from .registry import TOOL_REGISTRY
from .compatibility import same_location_score, SAME_LOCATION_THRESHOLD

def validate_node(state: AgentState) -> AgentState:
    task = state["task"]
    if task not in TOOL_REGISTRY:
        state["validation_ok"] = False
        state["validation_msg"] = f"Unknown or rejected task '{task}'"
        return state

    req = TOOL_REGISTRY[task]["requires"]
    meta = state["images_meta"]

    if req.get("num_images") != len(meta):
        state["validation_ok"] = False
        state["validation_msg"] = f"{task} requires {req['num_images']} image(s), got {len(meta)}"
        return state

    if "modality" in req and any(m["modality"] not in req["modality"] for m in meta):
        state["validation_ok"] = False
        state["validation_msg"] = f"Unsupported modality for {task}"
        return state

    if "modalities" in req and sorted(m["modality"] for m in meta) != sorted(req["modalities"]):
        state["validation_ok"] = False
        state["validation_msg"] = f"{task} requires one optical + one SAR image"
        return state

    if req.get("same_location") or req.get("co_registered"):
        score = same_location_score(state["images_raw"][0], state["images_raw"][1])
        if score < SAME_LOCATION_THRESHOLD:
            state["validation_ok"] = False
            state["validation_msg"] = f"Images do not appear to be the same location (score={score:.2f})"
            return state

    state["validation_ok"] = True
    state["validation_msg"] = "ok"
    return state
```

### Step 22 — Dispatch node

> Why now: only after classify + validate both succeed should any model actually run — this node is the one place model wrappers get called, using only the whitelisted params from the registry.

```
# orchestrator/nodes.py (part 3 of 4)
from models.geochat_wrapper import GeoChatModel
from models.geollava_wrapper import GeoLLaVAModel
from models.earthgpt_wrapper import EarthGPTModel

_geochat, _geollava, _earthgpt = GeoChatModel(), GeoLLaVAModel(), EarthGPTModel()

def dispatch_node(state: AgentState) -> AgentState:
    task, imgs, query, mode = state["task"], state["images_raw"], state["query"], state["mode"]
    if task == "vqa_caption_ground":
        state["result"] = _geochat.infer(imgs[0], query, mode or "vqa")
    elif task == "change_analysis":
        state["result"] = _geollava.infer(imgs[0], imgs[1], query)
    elif task == "optical_sar_fusion":
        state["result"] = _earthgpt.infer(imgs[0], imgs[1], query)
    return state

def reject_node(state: AgentState) -> AgentState:
    state["result"] = {"text": f"Request rejected: {state['validation_msg']}"}
    return state
```

### Step 23 — Combine node + trace

> Why now: this is the last node before the graph ends — it builds the exact "auditable execution summary" object the brief requires, and is what both the API and the database will read from.

```
# orchestrator/nodes.py (part 4 of 4)
from datetime import datetime, timezone

def combine_node(state: AgentState) -> AgentState:
    text = state["result"].get("text", "").lower()
    hedges = ["possibly", "unclear", "may", "might", "uncertain"]
    output_conf = max(0.4, min(0.95, 0.9 - sum(0.1 for h in hedges if h in text)))

    state["trace"] = {
        "query": state["query"],
        "selected_task": state["task"],
        "model_used": TOOL_REGISTRY.get(state["task"], {}).get("model", "none"),
        "parameters": {"mode": state["mode"]},
        "validation": state["validation_msg"],
        "router_confidence": state["router_confidence"],
        "output_confidence": output_conf,
        "output_summary": state["result"].get("text", "")[:220],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    return state
```

### Step 24 — Wire the graph together

> Why now: all five nodes exist — connect them into the actual state graph with conditional routing for the reject path.

```
# orchestrator/graph.py
from langgraph.graph import StateGraph, END
from .graph_state import AgentState
from .nodes import classify_node, validate_node, dispatch_node, combine_node, reject_node

def after_classify(state: AgentState) -> str:
    return "validate" if state["task"] != "reject" else "reject"

def after_validate(state: AgentState) -> str:
    return "dispatch" if state["validation_ok"] else "reject"

graph = StateGraph(AgentState)
graph.add_node("classify", classify_node)
graph.add_node("validate", validate_node)
graph.add_node("dispatch", dispatch_node)
graph.add_node("combine", combine_node)
graph.add_node("reject", reject_node)

graph.set_entry_point("classify")
graph.add_conditional_edges("classify", after_classify, {"validate": "validate", "reject": "reject"})
graph.add_conditional_edges("validate", after_validate, {"dispatch": "dispatch", "reject": "reject"})
graph.add_edge("dispatch", "combine")
graph.add_edge("combine", END)
graph.add_edge("reject", END)

orchestrator_app = graph.compile()
```

### Step 25 — Test the orchestrator end-to-end

> Why now: confirm the full graph works before wrapping it in an API — debugging inside FastAPI request/response cycles is slower than debugging a plain function call.

```
# quick manual run
from orchestrator.graph import orchestrator_app
from orchestrator.metadata import extract_metadata

paths = ["data/raw/vrsbench/sample_001.png"]
meta = [extract_metadata(p) for p in paths]

state = {"query": "Describe the land-cover and major objects visible in this image.",
         "images_meta": meta, "images_raw": paths}

final_state = orchestrator_app.invoke(state)
print(final_state["trace"])
```

## Stage E — API

### Step 26 — FastAPI app skeleton

> Why now: the orchestrator is proven — wrap it behind an HTTP interface so the frontend (Stage F) has something to talk to.

```
# backend/main.py (skeleton)
from fastapi import FastAPI
from orchestrator.db import init_db

app = FastAPI(title="SatQuery AI")

@app.on_event("startup")
def startup():
    init_db()
```

### Step 27 — Build the /query route

> Why now: this is the one route that matters most — it receives the upload, runs the full graph, and logs to the database, all in a single request.

```
# backend/main.py (continued)
from fastapi import UploadFile, File, Form
from typing import List
import shutil, uuid, json
from orchestrator.metadata import extract_metadata
from orchestrator.graph import orchestrator_app
from orchestrator.db import SessionLocal, Query, UploadedImage, ExecutionTrace
from backend.report import build_report

@app.post("/query")
async def query_endpoint(query: str = Form(...), images: List[UploadFile] = File(...)):
    paths, meta = [], []
    for img in images:
        path = f"/tmp/{uuid.uuid4()}_{img.filename}"
        with open(path, "wb") as f:
            shutil.copyfileobj(img.file, f)
        paths.append(path)
        meta.append(extract_metadata(path))

    state = {"query": query, "images_meta": meta, "images_raw": paths}
    final_state = orchestrator_app.invoke(state)
    trace = final_state["trace"]

    # persist to database
    db = SessionLocal()
    q_row = Query(
        query_text=query, selected_task=trace["selected_task"], model_used=trace["model_used"],
        mode=trace["parameters"].get("mode"), router_confidence=trace["router_confidence"],
        output_confidence=trace["output_confidence"], validation_msg=trace["validation"]
    )
    db.add(q_row); db.flush()
    for p, m in zip(paths, meta):
        db.add(UploadedImage(query_id=q_row.id, filepath=p, modality=m["modality"],
                              format=m["format"], timestamp_tag=m.get("timestamp")))
    db.add(ExecutionTrace(query_id=q_row.id, trace_json=json.dumps(trace)))
    db.commit()

    report_path = build_report(query, final_state["result"], trace)
    db.close()

    return {"status": "ok" if trace["validation"] == "ok" else "rejected",
            "result": final_state["result"], "trace": trace, "report_url": report_path}
```

### Step 28 — Build the /health route

> Why now: needed before deployment (Stage H) so free-tier hosts and your GUI can detect cold-start readiness.

```
# backend/main.py (continued)
@app.get("/health")
def health():
    return {"status": "ok"}
```

### Step 29 — Build the /history route

> Why now: the database (Step 5) is only useful if something reads it back — add this now so the GUI (Step 31) can show past queries.

```
# backend/main.py (continued)
from orchestrator.db import SessionLocal, Query

@app.get("/history")
def history(limit: int = 20):
    db = SessionLocal()
    rows = db.query(Query).order_by(Query.created_at.desc()).limit(limit).all()
    db.close()
    return [{"id": r.id, "query": r.query_text, "task": r.selected_task,
             "confidence": r.output_confidence, "created_at": r.created_at.isoformat()} for r in rows]
```

### Step 30 — Report generator

```
# backend/report.py
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os, uuid

def build_report(query, result, trace, out_dir="/tmp/reports") -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{uuid.uuid4()}.pdf")
    c = canvas.Canvas(path, pagesize=A4)
    y = 800
    for line in ["SatQuery AI — Execution Report", "", f"Query: {query}",
                 f"Task: {trace['selected_task']}", f"Model: {trace['model_used']}",
                 f"Confidence: {trace['output_confidence']:.2f}", "", "Answer:", result.get("text", "")]:
        c.drawString(50, y, str(line)[:100]); y -= 20
    c.save()
    return path
```

```
uvicorn backend.main:app --reload --port 8000
```

## Stage F — Frontend

### Step 31 — Streamlit GUI

> Why now: the API is complete — build the interactive GUI the brief explicitly requires against it.

```
# frontend/streamlit_app.py
import streamlit as st
import requests

st.set_page_config(page_title="SatQuery AI", layout="wide")
st.title("SatQuery AI")

col1, col2 = st.columns(2)
img1 = col1.file_uploader("Image 1", type=["tif", "tiff", "png", "jpg"])
img2 = col2.file_uploader("Image 2 (optional)", type=["tif", "tiff", "png", "jpg"])
query = st.text_input("Ask a question about the image(s)")

if st.button("Analyze") and img1 and query:
    files = [("images", img1)] + ([("images", img2)] if img2 else [])
    resp = requests.post("http://localhost:8000/query", data={"query": query}, files=files).json()

    if resp["status"] == "rejected":
        st.error(f"Rejected: {resp['trace']['validation']}")
    else:
        st.subheader("Answer")
        st.write(resp["result"]["text"])
        st.metric("Confidence", f"{resp['trace']['output_confidence']:.0%}")
        with st.expander("Execution trace"):
            st.json(resp["trace"])
        st.download_button("Download report", data=open(resp["report_url"], "rb"), file_name="report.pdf")

with st.expander("Recent queries"):
    for row in requests.get("http://localhost:8000/history").json():
        st.write(f"**{row['task']}** — {row['query']} ({row['confidence']:.0%})")
```

```
streamlit run frontend/streamlit_app.py
```

### Step 32 — CLI tool

> Why now: useful from here on for fast iteration in Stage G without clicking through the GUI each time.

```
# frontend/cli.py
import typer
from rich import print
from orchestrator.metadata import extract_metadata
from orchestrator.graph import orchestrator_app

app = typer.Typer()

@app.command()
def analyze(image1: str, query: str, image2: str = None):
    paths = [image1] + ([image2] if image2 else [])
    meta = [extract_metadata(p) for p in paths]
    state = {"query": query, "images_meta": meta, "images_raw": paths}
    final_state = orchestrator_app.invoke(state)
    trace = final_state["trace"]
    print(f"[green]Task:[/green] {trace['selected_task']}  [green]Model:[/green] {trace['model_used']}")
    print(f"[bold]Answer:[/bold] {final_state['result']['text']}")
    print(f"[dim]Confidence: {trace['output_confidence']:.0%}[/dim]")

if __name__ == "__main__":
    app()
```

```
python frontend/cli.py analyze --image1 data/raw/vrsbench/sample_001.png --query "Describe this image."
```

## Stage G — Testing

### Step 33 — Write the test suite

> Why now: the whole system exists — lock in its correctness with automated tests before you start tweaking things for the demo.

```
# tests/test_validation.py
from orchestrator.nodes import validate_node

def test_change_analysis_rejects_single_image():
    state = {"task": "change_analysis", "images_meta": [{"modality": "optical", "format": "GTiff"}]}
    state = validate_node(state)
    assert state["validation_ok"] is False

def test_fusion_requires_optical_and_sar():
    state = {"task": "optical_sar_fusion",
             "images_meta": [{"modality": "optical", "format": "GTiff"}, {"modality": "optical", "format": "GTiff"}]}
    state = validate_node(state)
    assert state["validation_ok"] is False
```

```
pytest tests/
```

### Step 34 — Run local end-to-end tests

> Why now: unit tests confirm individual nodes work — this step confirms the full request/response cycle through FastAPI + database + report generation together.

```
uvicorn backend.main:app --port 8000 &
curl -X POST http://localhost:8000/query \
  -F "query=Describe this image" \
  -F "images=@data/raw/vrsbench/sample_001.png"
```

### Step 35 — Benchmark against public datasets

> Why now: get your accuracy numbers before the judges do, using the exact benchmarks the brief names.

```
# tests/benchmark.py — loop over VRSBench/RSVQA/CDVQA test splits,
# call orchestrator_app.invoke() per sample, compare to ground truth,
# record accuracy/F1 for your submission report
```

## Stage H — Deployment

### Step 36 — Dockerize

```
# Dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

### Step 37 — Deploy the backend

> Why now: everything is tested locally — push to a free host so the GUI can be used by judges without your laptop running.

```
# Hugging Face Spaces (Docker SDK) or Render free web service
git push hf main   # if using an HF Space
```

Load models lazily on first request to survive free-tier cold starts.

### Step 38 — Deploy the frontend

```
# Streamlit Community Cloud — point at your deployed backend URL
# update frontend/streamlit_app.py's localhost:8000 references to the live backend URL first
```

### Step 39 — Push model weights to Hugging Face Hub

```
huggingface-cli login
huggingface-cli upload your-username/earthgpt-bigearthnet-lora models/weights/earthgpt-bigearthnet-lora
```

```
# then in earthgpt_wrapper.py, point lora_adapter_path at:
# "your-username/earthgpt-bigearthnet-lora"
```

### Step 40 — Final checks & submission packaging

- ☐ `pytest tests/` passes clean
- ☐ `/health` returns 200 on the deployed backend
- ☐ GUI reachable at its public URL, all three tasks demoed live
- ☐ One deliberately invalid upload demoed to show the validation gate rejecting it
- ☐ README with architecture diagram, setup steps, and fine-tuning evidence
- ☐ Demo video recorded
- ☐ Repo, weights link, and report zipped for submission

---

SatQuery AI — step-by-step build guide for Team Debuggers Den. Checkpoint IDs for GeoChat/GeoLLaVA/EarthGPT are placeholders — confirm exact Hugging Face repo names at Step 8/10/12 before running, as hosted checkpoint locations can change.