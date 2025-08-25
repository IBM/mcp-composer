# utils/health.py

import time
import socket
import platform


class HealthMonitor:
    def __init__(self) -> None:
        self.start_time = time.time()
        self.hostname = socket.gethostname()

    def get_status(self) -> dict:
        uptime_seconds = round(time.time() - self.start_time, 2)
        return {
            "status": "ok",
            "servername": self.hostname,
            "uptime_seconds": uptime_seconds,
            "platform": platform.system(),
            "python_version": platform.python_version(),
        }
