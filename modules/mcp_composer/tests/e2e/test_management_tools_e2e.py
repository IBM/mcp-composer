import subprocess
import sys
import time
import requests
import os
import pytest
import uuid


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
def test_management_tools_e2e():
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
            "8005",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert wait_for_server(
            "http://127.0.0.1:8005/", timeout=20
        ), "Server did not start in time"
        # Register a new server
        new_id = f"test-server-{uuid.uuid4().hex[:8]}"
        register_payload = {
            "id": new_id,
            "type": "stdio",
            "command": "uv",
            "args": ["run"],
        }
        reg_resp = requests.post(
            "http://127.0.0.1:8005/tools/register_mcp_server",
            json={"config": register_payload},
        )
        assert reg_resp.status_code == 200
        # List servers
        list_resp = requests.post(
            "http://127.0.0.1:8005/tools/list_member_servers", json={}
        )
        assert list_resp.status_code == 200
        servers = list_resp.json().get("result", [])
        assert any(s.get("id") == new_id for s in servers)
        # Deactivate the server
        deact_resp = requests.post(
            "http://127.0.0.1:8005/tools/deactivate_mcp_server",
            json={"server_id": new_id},
        )
        assert deact_resp.status_code == 200
        # Activate the server
        act_resp = requests.post(
            "http://127.0.0.1:8005/tools/activate_mcp_server",
            json={"server_id": new_id},
        )
        assert act_resp.status_code == 200
        # Delete the server
        del_resp = requests.post(
            "http://127.0.0.1:8005/tools/delete_mcp_server", json={"server_id": new_id}
        )
        assert del_resp.status_code == 200
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
