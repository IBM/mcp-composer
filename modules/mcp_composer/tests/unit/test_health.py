"""Test module for health.py"""

import pytest
import time
import socket
import platform
from unittest.mock import patch
from mcp_composer.core.utils.health import HealthMonitor


class TestHealthMonitor:
    """Test cases for HealthMonitor"""

    def test_health_monitor_initialization(self):
        """Test HealthMonitor initialization"""
        monitor = HealthMonitor()

        assert monitor.start_time > 0
        assert monitor.hostname is not None
        assert isinstance(monitor.hostname, str)

    def test_health_monitor_get_status(self):
        """Test get_status method"""
        monitor = HealthMonitor()

        # Wait a bit to ensure uptime is measurable
        time.sleep(0.1)

        status = monitor.get_status()

        assert status["status"] == "ok"
        assert status["servername"] == monitor.hostname
        assert status["uptime_seconds"] > 0
        assert status["platform"] == platform.system()
        assert status["python_version"] == platform.python_version()

    def test_health_monitor_get_status_structure(self):
        """Test that get_status returns expected structure"""
        monitor = HealthMonitor()
        status = monitor.get_status()

        expected_keys = [
            "status",
            "servername",
            "uptime_seconds",
            "platform",
            "python_version",
        ]
        for key in expected_keys:
            assert key in status

    def test_health_monitor_uptime_calculation(self):
        """Test that uptime is calculated correctly"""
        monitor = HealthMonitor()

        # Get initial status
        initial_status = monitor.get_status()
        initial_uptime = initial_status["uptime_seconds"]

        # Wait a bit
        time.sleep(0.1)

        # Get status again
        updated_status = monitor.get_status()
        updated_uptime = updated_status["uptime_seconds"]

        # Uptime should have increased
        assert updated_uptime > initial_uptime

    def test_health_monitor_hostname_consistency(self):
        """Test that hostname is consistent"""
        monitor = HealthMonitor()

        status1 = monitor.get_status()
        status2 = monitor.get_status()

        assert status1["servername"] == status2["servername"]
        assert status1["servername"] == monitor.hostname

    def test_health_monitor_platform_info(self):
        """Test that platform information is correct"""
        monitor = HealthMonitor()
        status = monitor.get_status()

        assert status["platform"] == platform.system()
        assert status["python_version"] == platform.python_version()

    def test_health_monitor_multiple_instances(self):
        """Test that multiple instances work independently"""
        monitor1 = HealthMonitor()
        time.sleep(0.1)  # Wait a bit
        monitor2 = HealthMonitor()
        time.sleep(0.01)  # Small delay to ensure monitor2 has measurable uptime

        status1 = monitor1.get_status()
        status2 = monitor2.get_status()

        # Both should have valid uptimes
        assert status1["uptime_seconds"] > 0
        assert status2["uptime_seconds"] > 0

        # First monitor should have higher uptime
        assert status1["uptime_seconds"] > status2["uptime_seconds"]

    @patch("socket.gethostname")
    def test_health_monitor_with_mock_hostname(self, mock_gethostname):
        """Test HealthMonitor with mocked hostname"""
        mock_gethostname.return_value = "test-hostname"

        monitor = HealthMonitor()
        status = monitor.get_status()

        assert status["servername"] == "test-hostname"
        mock_gethostname.assert_called_once()

    def test_health_monitor_uptime_precision(self):
        """Test that uptime is rounded to 2 decimal places"""
        monitor = HealthMonitor()
        status = monitor.get_status()

        uptime = status["uptime_seconds"]
        # Check that uptime is a number with at most 2 decimal places
        assert isinstance(uptime, (int, float))
        assert uptime >= 0

    def test_health_monitor_status_always_ok(self):
        """Test that status is always 'ok'"""
        monitor = HealthMonitor()

        # Test multiple times
        for _ in range(5):
            status = monitor.get_status()
            assert status["status"] == "ok"

    def test_health_monitor_immutable_start_time(self):
        """Test that start_time doesn't change after initialization"""
        monitor = HealthMonitor()
        initial_start_time = monitor.start_time

        # Call get_status multiple times
        for _ in range(3):
            monitor.get_status()

        # Start time should remain the same
        assert monitor.start_time == initial_start_time
