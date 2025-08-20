#!/usr/bin/env python3
"""
Script to run middleware examples easily.
Usage: python run_example.py <example_name>
"""

import sys
import subprocess
import asyncio
import time
from pathlib import Path


BASE_DIR = Path(__file__).parent.resolve()

EXAMPLES = {
    "circuit-breaker": {
        "server": "circuit-breaker-server.py",
        "client": "circuit-breaker-client.py",
        "description": "Circuit Breaker Pattern - handles failing services",
    },
    "concurrency": {
        "server": "concurrency-server.py",
        "client": "concurrency-client.py",
        "description": "Concurrency Limiter - limits concurrent requests",
    },
    "rate-limit": {
        "server": "rate-limit-server.py",
        "client": "rate-limit-client.py",
        "description": "Rate Limiter - token bucket rate limiting",
    },
    "prompt-injection": {
        "server": "promptinjectionserver.py",
        "client": "pinj-client.py",
        "description": "Prompt Injection Protection - blocks malicious prompts",
    },
    "pii-stop": {
        "server": "pii-stop-server.py",
        "client": "pii-stop-client.py",
        "description": "PII/Secrets Redaction - redacts sensitive data",
    },
    "xml2json": {
        "server": "xml2json-server.py",
        "client": "xml2json-client.py",
        "description": "XML to JSON Converter - converts XML responses",
    },
}


def list_examples():
    """List all available examples."""
    print("Available middleware examples:")
    print("=" * 50)
    for name, info in EXAMPLES.items():
        print(f"{name:20} - {info['description']}")
    print("\nUsage: python run_example.py <example_name>")
    print("Example: python run_example.py circuit-breaker")


def run_server(server_file):
    """Run the server in a subprocess."""
    print(f"Starting server: {server_file}")
    try:
        process = subprocess.Popen(
            ["uv", "run", "python", server_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait a bit for server to start
        time.sleep(2)

        if process.poll() is None:
            print("✅ Server started successfully")
            return process
        else:
            stdout, stderr = process.communicate()
            print("❌ Server failed to start:")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return None
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return None


def run_client(client_file):
    """Run the client."""
    print(f"Running client: {client_file}")
    try:
        result = subprocess.run(
            ["uv", "run", "python", client_file],
            capture_output=True,
            text=True,
            timeout=30,
        )

        print("Client output:")
        print("-" * 30)
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)

        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("❌ Client timed out")
        return False
    except Exception as e:
        print(f"❌ Error running client: {e}")
        return False


def main():
    if len(sys.argv) != 2:
        list_examples()
        return

    example_name = sys.argv[1]

    if example_name not in EXAMPLES:
        print(f"❌ Unknown example: {example_name}")
        list_examples()
        return

    example = EXAMPLES[example_name]
    print(f"Running example: {example_name}")
    print(f"Description: {example['description']}")
    print("=" * 50)

    # Check if files exist
    server_file = BASE_DIR / example["server"]
    client_file = BASE_DIR / example["client"]

    if not server_file.exists():
        print(f"❌ Server file not found: {server_file}")
        return

    if not client_file.exists():
        print(f"❌ Client file not found: {client_file}")
        return

    # Run server
    server_process = run_server(server_file)
    if not server_process:
        return

    try:
        # Run client
        success = run_client(client_file)
        if success:
            print("✅ Example completed successfully")
        else:
            print("❌ Example failed")
    finally:
        # Clean up server
        if server_process:
            print("Stopping server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()


if __name__ == "__main__":
    main()
