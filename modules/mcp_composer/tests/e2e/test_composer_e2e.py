import subprocess
import sys
import time
import requests
import os
import pytest
import signal
import json


def wait_for_server(url, timeout=15):
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
def test_composer_with_example_config():
    config_path = os.path.abspath("example/graphql-to-mcp/config.json")
    env = os.environ.copy()
    env["SERVER_CONFIG_FILE_PATH"] = config_path
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "mcp_composer_app.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8003",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert wait_for_server(
            "http://127.0.0.1:8003/", timeout=20
        ), "Server did not start in time"
        # Get all tools
        resp = requests.get("http://127.0.0.1:8003/tools")
        assert resp.status_code == 200
        tool_names = resp.json()
        assert any("mcp-countries" in t for t in tool_names)
        assert any("mcp-pokemon" in t for t in tool_names)
        # Test mcp-countries GraphQL tool
        for tool in tool_names:
            if "mcp-countries" in tool:
                payload = {"query": "{ countries { code name } }"}
                tool_url = f"http://127.0.0.1:8003/tools/{tool}"
                tool_resp = requests.post(tool_url, json=payload)
                assert tool_resp.status_code == 200
                assert "result" in tool_resp.json()
            if "mcp-pokemon" in tool:
                payload = {"query": "{ getAllPokemon { key } }"}
                tool_url = f"http://127.0.0.1:8003/tools/{tool}"
                tool_resp = requests.post(tool_url, json=payload)
                assert tool_resp.status_code == 200 or tool_resp.status_code == 400
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
