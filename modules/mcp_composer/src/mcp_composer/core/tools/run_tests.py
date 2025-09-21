#!/usr/bin/env python3
"""
Simple test runner for Sequential Thinking Tool (without pytest dependency)
"""

import asyncio
import json
import sys
import traceback
from typing import Any, Dict

# Add the parent directory to sys.path for imports
sys.path.insert(0, '../../..')

from sequential_thinking_tool import (
    SequentialThinkingTool,
    ThoughtData,
    ThoughtHistory,
)
from mcp.types import TextContent


class SimpleTestRunner:
    """Simple test runner that doesn't require pytest"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def assert_equal(self, actual, expected, message=""):
        """Simple assertion helper"""
        if actual != expected:
            raise AssertionError(f"{message}: Expected {expected}, got {actual}")
    
    def assert_true(self, condition, message=""):
        """Assert that condition is True"""
        if not condition:
            raise AssertionError(f"{message}: Expected True, got {condition}")
    
    def assert_in(self, item, container, message=""):
        """Assert that item is in container"""
        if item not in container:
            raise AssertionError(f"{message}: Expected {item} to be in {container}")
    
    def run_test(self, test_name, test_func):
        """Run a single test function"""
        try:
            print(f"Running {test_name}...", end=" ")
            if asyncio.iscoroutinefunction(test_func):
                asyncio.run(test_func())
            else:
                test_func()
            print("PASSED")
            self.passed += 1
        except Exception as e:
            print(f"FAILED: {e}")
            self.failed += 1
            self.errors.append(f"{test_name}: {e}")
    
    def run_all_tests(self):
        """Run all test methods"""
        print("=" * 50)
        print("Running Sequential Thinking Tool Tests")
        print("=" * 50)
        
        # Test data classes
        self.run_test("test_thought_data_creation", self.test_thought_data_creation)
        self.run_test("test_thought_history_creation", self.test_thought_history_creation)
        
        # Test tool initialization
        self.run_test("test_tool_initialization", self.test_tool_initialization)
        
        # Test validation
        self.run_test("test_validate_thought_data_valid", self.test_validate_thought_data_valid)
        self.run_test("test_validate_thought_data_invalid", self.test_validate_thought_data_invalid)
        
        # Test processing
        self.run_test("test_process_thought_basic", self.test_process_thought_basic)
        self.run_test("test_process_thought_revision", self.test_process_thought_revision)
        
        # Test tool execution
        self.run_test("test_tool_run_basic", self.test_tool_run_basic)
        self.run_test("test_tool_run_validation_error", self.test_tool_run_validation_error)
        
        # Print results
        print("=" * 50)
        print(f"Tests completed: {self.passed} passed, {self.failed} failed")
        if self.errors:
            print("\nErrors:")
            for error in self.errors:
                print(f"  - {error}")
        print("=" * 50)
        
        return self.failed == 0
    
    def test_thought_data_creation(self):
        """Test ThoughtData creation"""
        thought = ThoughtData(
            thought="Test thought",
            next_thought_needed=True,
            thought_number=1,
            total_thoughts=5
        )
        
        self.assert_equal(thought.thought, "Test thought")
        self.assert_equal(thought.next_thought_needed, True)
        self.assert_equal(thought.thought_number, 1)
        self.assert_equal(thought.total_thoughts, 5)
        self.assert_equal(thought.is_revision, False)
    
    def test_thought_history_creation(self):
        """Test ThoughtHistory creation"""
        history = ThoughtHistory()
        
        self.assert_true(isinstance(history.thoughts, list))
        self.assert_equal(len(history.thoughts), 0)
        self.assert_true(isinstance(history.branches, dict))
        self.assert_true(isinstance(history.session_id, str))
        self.assert_true(len(history.session_id) > 0)
    
    def test_tool_initialization(self):
        """Test tool initialization"""
        tool = SequentialThinkingTool()
        
        self.assert_equal(tool.name, "sequentialthinking")
        self.assert_in("dynamic and reflective problem-solving", tool.description)
        self.assert_equal(tool._thinking_sessions, {})
        self.assert_equal(tool._active_sessions, {})
    
    def test_validate_thought_data_valid(self):
        """Test validation with valid data"""
        tool = SequentialThinkingTool()
        
        data = {
            "thought": "This is a test thought",
            "nextThoughtNeeded": True,
            "thoughtNumber": 1,
            "totalThoughts": 5
        }
        
        thought = tool.validate_thought_data(data)
        
        self.assert_true(isinstance(thought, ThoughtData))
        self.assert_equal(thought.thought, "This is a test thought")
        self.assert_equal(thought.next_thought_needed, True)
        self.assert_equal(thought.thought_number, 1)
        self.assert_equal(thought.total_thoughts, 5)
    
    def test_validate_thought_data_invalid(self):
        """Test validation with invalid data"""
        tool = SequentialThinkingTool()
        
        data = {
            "thought": "",  # Invalid empty thought
            "nextThoughtNeeded": True,
            "thoughtNumber": 1,
            "totalThoughts": 5
        }
        
        try:
            tool.validate_thought_data(data)
            raise AssertionError("Expected ValueError but none was raised")
        except ValueError as e:
            self.assert_in("'thought' must be a non-empty string", str(e))
    
    def test_process_thought_basic(self):
        """Test basic thought processing"""
        tool = SequentialThinkingTool()
        
        thought = ThoughtData(
            thought="Test thought",
            next_thought_needed=True,
            thought_number=1,
            total_thoughts=5
        )
        
        session = ThoughtHistory()
        processed = tool.process_thought_data(thought, session)
        
        self.assert_equal(processed.processed_thought_number, 1)
        self.assert_equal(processed.estimated_total_thoughts, 5)
        self.assert_equal(processed.next_thought_needed, True)
        self.assert_equal(processed.status, "success")
        self.assert_equal(len(session.thoughts), 1)
    
    def test_process_thought_revision(self):
        """Test thought revision processing"""
        tool = SequentialThinkingTool()
        
        # Add initial thought
        session = ThoughtHistory()
        original_thought = ThoughtData(
            thought="Original thought",
            next_thought_needed=True,
            thought_number=1,
            total_thoughts=5
        )
        session.thoughts.append(original_thought)
        
        # Create revision
        revision_thought = ThoughtData(
            thought="Revised thought",
            next_thought_needed=True,
            thought_number=2,
            total_thoughts=5,
            is_revision=True,
            revises_thought=1
        )
        
        processed = tool.process_thought_data(revision_thought, session)
        
        self.assert_equal(processed.is_revision, True)
        self.assert_equal(processed.revises_thought, 1)
        self.assert_equal(len(session.thoughts), 1)  # Original replaced
        self.assert_equal(session.thoughts[0].thought, "Revised thought")
    
    async def test_tool_run_basic(self):
        """Test basic tool execution"""
        tool = SequentialThinkingTool()
        
        arguments = {
            "thought": "I need to analyze this problem step by step",
            "nextThoughtNeeded": True,
            "thoughtNumber": 1,
            "totalThoughts": 5,
            "userId": "test_user"
        }
        
        result = await tool.run(arguments)
        
        self.assert_true(hasattr(result, 'content'))
        self.assert_equal(len(result.content), 1)
        self.assert_true(isinstance(result.content[0], TextContent))
        
        # Parse response JSON
        content = result.content[0]
        response_data = json.loads(content.text)
        
        self.assert_equal(response_data["processedThoughtNumber"], 1)
        self.assert_equal(response_data["estimatedTotalThoughts"], 5)
        self.assert_equal(response_data["nextThoughtNeeded"], True)
        self.assert_equal(response_data["status"], "success")
        self.assert_in("coordinatorResponse", response_data)
    
    async def test_tool_run_validation_error(self):
        """Test tool execution with validation error"""
        tool = SequentialThinkingTool()
        
        arguments = {
            "thought": "",  # Invalid empty thought
            "nextThoughtNeeded": True,
            "thoughtNumber": 1,
            "totalThoughts": 5
        }
        
        result = await tool.run(arguments)
        content = result.content[0]
        response_data = json.loads(content.text)
        
        self.assert_equal(response_data["status"], "validation_error")
        self.assert_in("'thought' must be a non-empty string", response_data["error"])


def main():
    """Main test runner"""
    runner = SimpleTestRunner()
    success = runner.run_all_tests()
    
    if success:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
