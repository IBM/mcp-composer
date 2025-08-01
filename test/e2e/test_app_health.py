import subprocess
import sys
import time
import requests
import os
import signal
import pytest

def wait_for_server(url, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(0.5)
    return False

@pytest.mark.e2e
def test_app_health():
    # Start the FastAPI app in a subprocess
    env = os.environ.copy()
    proc = subprocess.Popen([
        sys.executable, '-m', 'uvicorn', 'mcp_composer_app.app:app', '--host', '127.0.0.1', '--port', '8001'
    ], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert wait_for_server('http://127.0.0.1:8001/', timeout=15), "Server did not start in time"
        resp = requests.get('http://127.0.0.1:8001/')
        assert resp.status_code == 200
        assert "MCP Composer Tool API" in resp.text
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill() 