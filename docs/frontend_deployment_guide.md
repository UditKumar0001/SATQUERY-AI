# SatQuery AI — Frontend Deployment Guide (Step 38)

This guide documents deploying the SatQuery AI interactive Streamlit user interface to **Streamlit Community Cloud** (free tier).

---

## Deploying to Streamlit Community Cloud

### Step-by-Step Instructions:

1. **Log In to Streamlit Community Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io/) and sign in with your GitHub account.

2. **Create New App**:
   - Click **Create App** -> **Deploy a public app from GitHub**.
   - **Repository**: `UditKumar0001/SATQUERY-AI` (or your fork)
   - **Branch**: `main`
   - **Main file path**: `frontend/streamlit_app.py`
   - **App URL**: `satquery-ai.streamlit.app` (or custom name)

3. **Configure Secrets (Advanced Settings)**:
   - Click **Advanced Settings** before deploying (or go to **App Settings -> Secrets** later).
   - In the **Secrets** editor, specify your deployed backend URL:
     ```toml
     BACKEND_API_URL = "https://<YOUR_HF_USERNAME>-satquery-backend.hf.space"
     ```
     *(Or if hosted on Render: `https://satquery-backend.onrender.com`)*
   - Click **Save**.

4. **Deploy**:
   - Click **Deploy!**
   - Streamlit Cloud will automatically install dependencies from `frontend/requirements.txt` and load the dark theme configured in `.streamlit/config.toml`.

---

## Live Features on Streamlit Cloud

- **Dynamic Connection Widget**: Users and judges can change or test connection to any backend URL on the fly using the **⚙️ Connection Settings** in the sidebar.
- **System Health Monitor**: Automatically verifies connectivity, hardware acceleration, and tool availability from the live backend `/health` endpoint.
- **Instant Dual-Image Preview & Analysis**: Supports high-res uploads, question answering, change detection, confidence score display, trace inspection, and report downloading directly from the browser.
