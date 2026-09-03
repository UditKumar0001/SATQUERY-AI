---
title: SatQuery AI Backend
emoji: 🛰️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# SatQuery AI — Earth Observation Orchestration API

Intelligent Multi-Modal Earth Observation Orchestration System powered by **LangGraph**, **FastAPI**, and remote sensing vision-language models (**GeoChat**, **GeoLLaVA**, **EarthGPT**).

## Overview

SatQuery AI routes and validates satellite imagery queries across specialized tools:
1. **Single-Image Analysis**: Visual Question Answering (VQA), scene captioning, and referring object grounding via GeoChat.
2. **Bi-Temporal Change Analysis**: Topological change detection and difference reasoning across timestamps via GeoLLaVA.
3. **Multi-Sensor Fusion**: Joint reasoning over co-registered Optical spectrum and Synthetic Aperture Radar (SAR) backscatter via EarthGPT.

## API Documentation

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **Health & Readiness Check**: `GET /health`
- **Query & Analysis**: `POST /query`
- **Audit History**: `GET /history`
- **PDF Report Download**: `GET /report/{query_id}`

## Deployment

### Deploying to Hugging Face Spaces
1. Create a new Space on [Hugging Face Spaces](https://huggingface.co/new-space) selecting **Docker** SDK.
2. Add your Space remote and push:
   ```bash
   git remote add hf https://huggingface.co/spaces/<your-username>/satquery-backend
   git push hf main
   ```
3. Set your `GEMINI_API_KEY` in the Space's **Settings -> Variables and Secrets**.

### Deploying via Docker Locally or on Cloud VPS
```bash
docker build -t satquery-backend .
docker run -p 7860:7860 -e GEMINI_API_KEY="your-key" satquery-backend
```
