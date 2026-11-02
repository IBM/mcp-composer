"""Start a local HTTP member, register it with a bearer token, and read its health."""

import asyncio
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stdio_support import child_env, composer_in, python_bin

HERE = Path(__file__).resolve().parent
SERVER = HERE / "shelf_server.py"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_open(port: int) -> None:
    deadline = time.time() + 20
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError("The HTTP member did not open a port.")


async def main() -> None:
    port = _free_port()
    env = child_env()
    process = subprocess.Popen(
        [python_bin(), str(SERVER), str(port)],
        cwd=str(HERE),
        env=env,
    )
    try:
        _wait_until_open(port)
        with tempfile.TemporaryDirectory() as tmp:
            composer = composer_in(tmp)
            message = await composer.register_mcp_server(
                {
                    "id": "shelf",
                    "type": "http",
                    "endpoint": f"http://127.0.0.1:{port}/mcp",
                    "auth_strategy": "bearer",
                    "auth": {"token": "shelf-local"},
                }
            )
            tools = await composer.list_tools()
            names = sorted(
                tool.name for tool in tools if tool.name.endswith("count_open_boxes")
            )
            health = await composer.member_health()
            print(message)
            print("auth: bearer")
            print("tools: " + ", ".join(names))
            for row in health:
                print(f"health: {row['server_name']} {row['status']}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    asyncio.run(main())
