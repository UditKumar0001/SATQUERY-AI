
# SatQuery AI — Earth Observation Orchestration API

Intelligent Multi-Modal Earth Observation Orchestration System powered by **LangGraph**, **FastAPI**, and remote sensing vision-language models (**GeoChat**, **GeoLLaVA**, **EarthGPT**).

## Overview

SatQuery AI routes and validates satellite imagery queries across specialized tools:
1. **Single-Image Analysis**: Visual Question Answering (VQA), scene captioning, and referring object grounding via GeoChat.
2. **Bi-Temporal Change Analysis**: Topological change detection and difference reasoning across timestamps via GeoLLaVA.
3. **Multi-Sensor Fusion**: Joint reasoning over co-registered Optical spectrum and Synthetic Aperture Radar (SAR) backscatter via EarthGPT.

## API Documentation & Endpoints

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **Health & Readiness Check**: `GET /health`
- **Query & Multimodal Analysis**: `POST /query`
- **Conversational Assistant**: `POST /chat` and `GET /chat/{session_id}`
- **Audit History**: `GET /history`
- **PDF Report Download**: `GET /report/{query_id}`

## Running Frontend & Backend Together

### 1. Single Command (Recommended)
Run both FastAPI orchestrator daemon and Streamlit ground station console together:
```bash
python run_app.py
```
This automatically verifies backend health on `http://127.0.0.1:8000/health` before starting the Streamlit console on `http://127.0.0.1:8501`.

### 2. Docker Compose
Launch both containerized services:
```bash
docker-compose up --build
```
- **Backend API**: `http://localhost:8000`
- **Frontend Console**: `http://localhost:8501`

### 3. Deploying to Hugging Face Spaces
1. Create a new Space on [Hugging Face Spaces](https://huggingface.co/new-space) selecting **Docker** SDK.
2. Add your Space remote and push:
   ```bash
   git remote add hf https://huggingface.co/spaces/<your-username>/satquery-backend
   git push hf main
   ```
3. Set your `OPENAI_API_KEY` in the Space's **Settings -> Variables and Secrets**.
