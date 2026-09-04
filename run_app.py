"""
SatQuery AI — Unified Launcher
Stitches and coordinates both the FastAPI backend daemon and the Streamlit frontend.
"""
import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error


def wait_for_backend(url: str, timeout: int = 25) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    parser = argparse.ArgumentParser(description="SatQuery AI — Unified Service Launcher")
    parser.add_argument("--host", default="0.0.0.0", help="Backend and frontend host binding (default: 0.0.0.0)")
    parser.add_argument("--backend-port", type=int, default=8000, help="Backend port (default: 8000)")
    parser.add_argument("--frontend-port", type=int, default=8501, help="Frontend port (default: 8501)")
    parser.add_argument("--backend-only", action="store_true", help="Launch backend service only")
    parser.add_argument("--frontend-only", action="store_true", help="Launch frontend service only")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(repo_root)

    check_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    backend_url = f"http://{check_host}:{args.backend_port}"
    health_url = f"{backend_url}/health"

    procs = []

    def cleanup(signum=None, frame=None):
        print("\n[SatQuery Launcher] Shutting down services...")
        for p in procs:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.kill()
        print("[SatQuery Launcher] All services terminated cleanly.")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("=" * 65)
    print("      🛰️  SATQUERY AI — GROUND STATION MISSION CONTROLLER  🛰️")
    print("=" * 65)

    if not args.frontend_only:
        print(f"[Launcher] Starting FastAPI Backend on http://{args.host}:{args.backend_port}...")
        backend_cmd = [
            sys.executable, "-m", "uvicorn",
            "backend.main:app",
            "--host", args.host,
            "--port", str(args.backend_port)
        ]
        backend_proc = subprocess.Popen(backend_cmd, cwd=repo_root)
        procs.append(backend_proc)

        print("[Launcher] Awaiting backend health verification...", end="", flush=True)
        if wait_for_backend(health_url, timeout=25):
            print(" ONLINE (200 OK)")
            print(f"[Launcher] 📡 Swagger Docs: http://localhost:{args.backend_port}/docs")
            print(f"[Launcher] 🏥 Health Check: http://localhost:{args.backend_port}/health")
        else:
            print(" TIMEOUT (Backend did not respond in 25s)")
            if not args.backend_only:
                print("[Launcher] Proceeding anyway, but frontend may show degraded status.")

    if not args.backend_only:
        print(f"[Launcher] Starting Streamlit Frontend on http://{args.host}:{args.frontend_port}...")
        env = os.environ.copy()
        env["BACKEND_API_URL"] = backend_url

        frontend_cmd = [
            sys.executable, "-m", "streamlit", "run",
            os.path.join("frontend", "streamlit_app.py"),
            "--server.port", str(args.frontend_port),
            "--server.address", args.host,
            "--server.headless", "true"
        ]
        frontend_proc = subprocess.Popen(frontend_cmd, cwd=repo_root, env=env)
        procs.append(frontend_proc)
        print(f"[Launcher] 🚀 Ground Station Console: http://localhost:{args.frontend_port}")
        print(f"[Launcher] 🚀 Direct IP Access:      http://127.0.0.1:{args.frontend_port}")

    print("=" * 65)
    print("Press Ctrl+C to terminate all active services.")
    print("=" * 65)

    try:
        while True:
            for p in procs:
                if p.poll() is not None:
                    print(f"\n[Launcher] Process {p.args} exited with code {p.returncode}")
                    cleanup()
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
