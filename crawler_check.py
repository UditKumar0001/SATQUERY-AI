"""
SatQuery AI — Live Web & API Feature Crawler
Crawls and validates all live frontend and backend services on localhost.
"""
import io
import json
import os
import sys
import time
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def log_result(test_name: str, status: bool, detail: str = ""):
    icon = "✅ PASS" if status else "❌ FAIL"
    print(f"{icon:<9} | {test_name:<38} | {detail}")


def crawl_live_services(backend_url: str = "http://127.0.0.1:8000", frontend_url: str = "http://127.0.0.1:8501"):
    print("=" * 80)
    print("      🛰️  SATQUERY AI — AUTOMATED LIVE CRAWLER & FEATURE AUDITOR  🛰️")
    print(f"Backend Target:  {backend_url}")
    print(f"Frontend Target: {frontend_url}")
    print("=" * 80)

    all_passed = True

    # --- 1. Backend Root Check ---
    try:
        with urllib.request.urlopen(f"{backend_url}/", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
            ok = (r.status == 200 and data.get("app") == "SatQuery AI")
            log_result("Backend Root Endpoint (GET /)", ok, f"HTTP {r.status} // {data.get('status')}")
            if not ok: all_passed = False
    except Exception as e:
        log_result("Backend Root Endpoint (GET /)", False, str(e))
        all_passed = False

    # --- 2. Backend Health & Readiness ---
    try:
        with urllib.request.urlopen(f"{backend_url}/health", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
            tools_cnt = len(data.get("registered_tools", []))
            ok = (r.status == 200 and data.get("database") == "connected")
            log_result("System Health Telemetry (/health)", ok, f"DB: {data.get('database')} | Tools: {tools_cnt}")
            if not ok: all_passed = False
    except Exception as e:
        log_result("System Health Telemetry (/health)", False, str(e))
        all_passed = False

    # --- 3. OpenAPI Schema & Swagger Docs ---
    try:
        with urllib.request.urlopen(f"{backend_url}/openapi.json", timeout=5) as r:
            schema = json.loads(r.read().decode("utf-8"))
            paths = list(schema.get("paths", {}).keys())
            ok = (r.status == 200 and "/query" in paths and "/chat" in paths)
            log_result("OpenAPI Spec (/openapi.json)", ok, f"{len(paths)} routes defined")
            if not ok: all_passed = False
    except Exception as e:
        log_result("OpenAPI Spec (/openapi.json)", False, str(e))
        all_passed = False

    try:
        with urllib.request.urlopen(f"{backend_url}/docs", timeout=5) as r:
            html = r.read().decode("utf-8")
            ok = (r.status == 200 and len(html) > 200)
            log_result("Swagger Interactive UI (/docs)", ok, f"HTTP {r.status} ({len(html)} bytes)")
            if not ok: all_passed = False
    except Exception as e:
        log_result("Swagger Interactive UI (/docs)", False, str(e))
        all_passed = False

    # --- 4. Chat Conversational Endpoint ---
    try:
        payload = json.dumps({"message": "Hello SatQuery, explain SAR backscatter"}).encode("utf-8")
        req = urllib.request.Request(
            f"{backend_url}/chat",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            c_data = json.loads(r.read().decode("utf-8"))
            ok = (r.status == 200 and "response" in c_data and "session_id" in c_data)
            resp_preview = c_data.get("response", "")[:45] + "..."
            log_result("Conversational LLM Assistant (/chat)", ok, f"Reply: '{resp_preview}'")
            if not ok: all_passed = False
    except Exception as e:
        log_result("Conversational LLM Assistant (/chat)", False, str(e))
        all_passed = False

    # --- 4b. Chat Conversational Hello Greeting Check ---
    try:
        payload = json.dumps({"message": "Hello"}).encode("utf-8")
        req = urllib.request.Request(
            f"{backend_url}/chat",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            c_data = json.loads(r.read().decode("utf-8"))
            resp = c_data.get("response", "")
            ok = (r.status == 200 and len(resp) > 5 and not resp.startswith("<div"))
            log_result("Chat Greeting Response (/chat 'Hello')", ok, f"Length: {len(resp)} chars | '{resp[:40]}...'")
            if not ok: all_passed = False
    except Exception as e:
        log_result("Chat Greeting Response (/chat 'Hello')", False, str(e))
        all_passed = False

    # --- 4c. Conversation Sessions Listing Check ---
    try:
        with urllib.request.urlopen(f"{backend_url}/conversations?limit=5", timeout=5) as r:
            conv_data = json.loads(r.read().decode("utf-8"))
            total_convs = conv_data.get("total", 0)
            ok = (r.status == 200 and isinstance(conv_data.get("conversations"), list))
            log_result("Conversation Sessions List (/conversations)", ok, f"{total_convs} total recorded sessions")
            if not ok: all_passed = False
    except Exception as e:
        log_result("Conversation Sessions List (/conversations)", False, str(e))
        all_passed = False

    # --- 5. Multimodal Query Pipeline Dispatch ---
    test_img = os.path.join("data", "raw", "vrsbench", "sample_001.png")
    created_qid = None
    vis_output_url = None
    if os.path.exists(test_img):
        try:
            import requests
            with open(test_img, "rb") as f:
                files = [("files", ("sample_001.png", f.read(), "image/png"))]
            q_res = requests.post(f"{backend_url}/query", data={"query": "Locate aircraft on runway"}, files=files, timeout=30)
            if q_res.status_code == 200:
                q_json = q_res.json()
                created_qid = q_json.get("query_id")
                vis_output_url = q_json.get("visual_output_url")
                ok = bool(q_json.get("validation_ok") and created_qid)
                log_result("Multimodal Query Dispatch (/query)", ok, f"Record #{created_qid} | Task: {q_json.get('selected_task')}")
                if not ok: all_passed = False
            else:
                log_result("Multimodal Query Dispatch (/query)", False, f"HTTP {q_res.status_code}")
                all_passed = False
        except Exception as e:
            log_result("Multimodal Query Dispatch (/query)", False, str(e))
            all_passed = False
    else:
        log_result("Multimodal Query Dispatch (/query)", False, "Sample image not found")
        all_passed = False

    # --- 6. Static Visual Output Serving ---
    if vis_output_url:
        try:
            with urllib.request.urlopen(f"{backend_url}{vis_output_url}", timeout=5) as r:
                content_type = r.headers.get("Content-Type", "")
                ok = (r.status == 200 and "image" in content_type)
                log_result("Visual Output Rendering (/static/...)", ok, f"HTTP {r.status} ({content_type})")
                if not ok: all_passed = False
        except Exception as e:
            log_result("Visual Output Rendering (/static/...)", False, str(e))
            all_passed = False
    else:
        log_result("Visual Output Rendering (/static/...)", True, "Skipped (no visual URL generated)")

    # --- 7. PDF Report Download ---
    if created_qid:
        try:
            with urllib.request.urlopen(f"{backend_url}/report/{created_qid}", timeout=5) as r:
                ct = r.headers.get("Content-Type", "")
                body = r.read()
                ok = (r.status == 200 and "application/pdf" in ct and body.startswith(b"%PDF"))
                log_result("Audit PDF Report (/report/{id})", ok, f"HTTP {r.status} ({len(body)} bytes PDF)")
                if not ok: all_passed = False
        except Exception as e:
            log_result("Audit PDF Report (/report/{id})", False, str(e))
            all_passed = False

    # --- 8. Telemetry History Endpoint ---
    try:
        with urllib.request.urlopen(f"{backend_url}/history?limit=5", timeout=5) as r:
            h_data = json.loads(r.read().decode("utf-8"))
            hist_count = len(h_data.get("history", []))
            ok = (r.status == 200 and hist_count > 0)
            log_result("Telemetry Audit Log (/history)", ok, f"{hist_count} records retrieved")
            if not ok: all_passed = False
    except Exception as e:
        log_result("Telemetry Audit Log (/history)", False, str(e))
        all_passed = False

    # --- 9. Admin Maintenance Cleanup ---
    try:
        req = urllib.request.Request(f"{backend_url}/admin/cleanup?max_age_hours=24", data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            cl_data = json.loads(r.read().decode("utf-8"))
            ok = (r.status == 200 and cl_data.get("status") == "success")
            log_result("Admin Maintenance Purge (/admin/cleanup)", ok, f"Cleaned metrics: {cl_data.get('metrics')}")
            if not ok: all_passed = False
    except Exception as e:
        log_result("Admin Maintenance Purge (/admin/cleanup)", False, str(e))
        all_passed = False

    # --- 10. Frontend Streamlit Web Server ---
    try:
        with urllib.request.urlopen(f"{frontend_url}/", timeout=5) as r:
            html = r.read().decode("utf-8", errors="ignore")
            ok = (r.status == 200 and ("Streamlit" in html or "satquery" in html.lower() or "title" in html.lower()))
            log_result("Streamlit Web Server (GET /)", ok, f"HTTP {r.status} ({len(html)} bytes HTML)")
            if not ok: all_passed = False
    except Exception as e:
        log_result("Streamlit Web Server (GET /)", False, str(e))
        all_passed = False

    # --- 11. Frontend Health Endpoint ---
    try:
        with urllib.request.urlopen(f"{frontend_url}/_stcore/health", timeout=5) as r:
            body = r.read().decode("utf-8")
            ok = (r.status == 200 and "ok" in body.lower())
            log_result("Streamlit Core Health (/_stcore/health)", ok, f"HTTP {r.status} // {body.strip()}")
            if not ok: all_passed = False
    except Exception as e:
        log_result("Streamlit Core Health (/_stcore/health)", False, str(e))
        all_passed = False

    print("=" * 80)
    if all_passed:
        print("🎉 ALL 11 CRAWLER AUDIT CHECKS PASSED PERFECTLY!")
    else:
        print("⚠️ SOME CRAWLER AUDIT CHECKS FAILED. Review details above.")
    print("=" * 80)
    return all_passed


if __name__ == "__main__":
    b_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    f_url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8501"
    success = crawl_live_services(backend_url=b_url, frontend_url=f_url)
    sys.exit(0 if success else 1)
