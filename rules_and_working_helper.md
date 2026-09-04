# SatQuery AI — Rules & Working Agreement (for Antigravity)

> **Read this file first, before touching `plan.md` or any code.**
> This file is the shared source of truth for how Antigravity should behave on this project — on anyone's machine, in any session.

---

## 1. Token & Efficiency Rules

Antigravity should work lean. Specifically:

- Don't re-explain or re-summarize files that haven't changed since the last message.
- When editing a file, make a targeted edit/patch — don't reprint the whole file unless the user asks to see it in full.
- Don't repeat the full plan back to the user each time — reference it by step number (e.g. "Step 7 done").
- Don't regenerate existing working code unless the user asked for a change.
- Keep responses short and direct: no filler preamble, no restating the request back.
- Batch related file edits/commands together instead of doing them one at a time across many turns.
- Don't re-run tests, builds, or installs that already passed and haven't changed.
- Ask before doing large/expensive operations (big downloads, model downloads, long fine-tunes) — don't just start them.

---

## 2. API Keys, URLs & Secrets — Single Source

- **All API keys, tokens, database URLs, and endpoints belong in `.env`**, based on `.env.example`. Nowhere else.
- Never hardcode a key, token, or URL directly into any `.py`, `.js`, or config file — always read it from environment variables (`os.getenv(...)`).
- `.env` must always stay listed in `.gitignore` and must **never** be committed or pushed to GitHub.
- If a step needs a new credential that hasn't been provided yet:
  1. Add a placeholder line for it to `.env.example` (e.g. `NEW_KEY_NAME=your-key-here`).
  2. Add a row for it in the **Pending Credentials** table below.
  3. Stop and ask the user for the real value — do not invent a fake key or proceed with a dummy one.
- When the user provides a key/URL, it goes into `.env` only, and the Pending Credentials table below gets marked as done.

### Pending Credentials

| Name | Used for | Status |
|---|---|---|
| `OPENAI_API_KEY` | Router LLM (Stage 1) | Done (Configured in `.env`) |
| `DATABASE_URL` | Database path (Step 5) | Done (`sqlite:///./satquery.db`) |
| `MODEL_DEVICE` | Model loading (`cuda`/`cpu`) | Done (`cuda`) |
| `HF_TOKEN` | Hugging Face datasets & model weights (Step 6, Steps 8-12, Step 39) | Done (Configured in `.env`) |
| `BACKEND_API_URL` | Backend API URL for frontend (Step 31) | Done (`http://localhost:8000`) |
| _(add new rows here as new steps require new keys/URLs)_ | | |

---

## 3. Step-by-Step Execution Rule

- Work through `plan.md` **one step at a time**, in order.
- After implementing/developing a step in Antigravity, **stop**.
- Do **not** automatically continue to the next step.
- Wait for explicit confirmation from the user — e.g. "start step 5" — before beginning the next step.
- This rule applies to **every step, Step 1 through Step 40, with no exceptions**, until the project is fully complete.

### After Each Step — Report Outside Work Needed

- Every time a step finishes, Antigravity must tell the user clearly if there is any **outside/manual work** needed before the next step can run — for example:
  - Creating an account somewhere (e.g. Hugging Face, Google Cloud, a hosting platform)
  - Generating or fetching an API key
  - Getting a URL/endpoint (e.g. a deployed service URL, a webhook URL, a dataset link)
  - Any manual download, signup, or approval that Antigravity itself cannot do
- This should be stated explicitly, even if the step "worked" — don't bury it in a summary.
- If a step needs no outside work, Antigravity should say so briefly (e.g. "No outside setup needed for this step.") so the user always knows where things stand.
- Anything flagged this way should also be added to the **Pending Credentials** table above if it's a key/URL, so it isn't lost.

---

## 4. Collaboration Note (for teammates)

- This file is meant to travel with the repo. Anyone who opens this project in Antigravity — on their own laptop — should have Antigravity read this file first, before continuing any work.
- If there's ever a conflict between this file and `plan.md`: **this file governs process/behavior rules**, `plan.md` governs the technical build steps.
- Keep this file updated as the project evolves (new rules, new pending credentials, etc.) and commit it to the repo so it stays in sync for everyone.

---

*Last updated alongside `plan.md`. Keep both files in the repo root.*
