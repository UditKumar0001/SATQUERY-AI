# SatQuery AI — Backend Deployment Guide (Step 37)

This guide documents the procedures for hosting the SatQuery AI backend on free cloud platforms.

---

## Option A: Hugging Face Spaces (Recommended for Demo & Evaluation)

Hugging Face Spaces provides free hosting using Docker SDK, natively supporting our port `7860` setup.

### Step-by-Step Instructions:

1. **Create Space**:
   - Go to [huggingface.co/new-space](https://huggingface.co/new-space).
   - Space Name: `satquery-backend`
   - License: `mit` or `apache-2.0`
   - Space SDK: Select **Docker** -> **Blank**.
   - Visibility: **Public** (or Private if you prefer).

2. **Add Remote & Push**:
   ```powershell
   git remote add hf https://huggingface.co/spaces/<YOUR_HF_USERNAME>/satquery-backend
   git push hf main
   ```

3. **Configure Secrets**:
   - In your HF Space, navigate to **Settings** -> **Variables and Secrets**.
   - Add Secret:
     - Name: `OPENAI_API_KEY`
     - Value: `<Your OpenAI Platform API Key>`
   - (Optional) Add Secret:
     - Name: `HF_TOKEN`
     - Value: `<Your Hugging Face User Access Token>`

4. **Public API Endpoint**:
   Your backend API will be available at:
   `https://<YOUR_HF_USERNAME>-satquery-backend.hf.space`

---

## Option B: Render Free Web Service

Render offers free web service instances for containerized services.

### Step-by-Step Instructions:

1. Connect your GitHub repository `SATQUERY-AI` to [Render](https://dashboard.render.com/).
2. Create a new **Web Service** -> select **Build and deploy from a Git repository**.
3. Render will auto-detect `render.yaml`.
4. Enter the `OPENAI_API_KEY` in the Environment Variables prompt.
5. Click **Create Web Service**.

---

## Cold Start Optimizations

The SatQuery AI backend includes several zero-cost optimizations:
- **Fast Startup**: Only SQLite metadata tables are initialized on startup (<0.1s lifespan startup time).
- **Lazy Inference Loading**: Vision-language models instantiate on demand during the first query dispatch rather than during container boot.
- **Simulation Fallbacks**: Guarantees sub-second responses and complete pipeline execution even when memory constraints prevent loading 14GB local weights.
