"""
Unit tests for Sequential Thinking Tool

To run these tests, install pytest:
    pip install pytest pytest-asyncio

Then run:
    pytest test_sequential_thinking_tool.py -v
"""

import pytest
import json
import time
from unittest.mock import patch, MagicMock
from typing import Dict, Any

from mcp_composer.core.tools.sequential_thinking_tool import (
    SequentialThinkingTool,
    ThoughtData,
    ThoughtHistory,
    ProcessedThought
)
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent


class TestThoughtData:
    """Test ThoughtData dataclass"""
    
    def test_thought_data_creation(self):
        """Test basic ThoughtData creation"""
        thought = ThoughtData(
            thought="Test thought",
            next_thought_needed=True,
            thought_number=1,
            total_thoughts=5
        )
        
        assert thought.thought == "Test thought"
        assert thought.next_thought_needed is True
        assert thought.thought_number == 1
        assert thought.total_thoughts == 5
        assert thought.is_revision is False
        assert thought.revises_thought is None
        assert thought.branch_from_thought is None
        assert thought.branch_id is None
        assert thought.needs_more_thoughts is False
    
    def test_thought_data_with_optional_fields(self):
        """Test ThoughtData with optional fields"""
        thought = ThoughtData(
            thought="Revision thought",
            next_thought_needed=False,
            thought_number=3,
            total_thoughts=5,
            is_revision=True,
            revises_thought=2,
            branch_from_thought=1,
            branch_id="alternative",
            needs_more_thoughts=True
        )
        
        assert thought.is_revision is True
        assert thought.revises_thought == 2
        assert thought.branch_from_thought == 1
        assert thought.branch_id == "alternative"
        assert thought.needs_more_thoughts is True


class TestThoughtHistory:
    """Test ThoughtHistory dataclass"""
    
    def test_thought_history_creation(self):
        """Test basic ThoughtHistory creation"""
        history = ThoughtHistory()
        
        assert isinstance(history.thoughts, list)
        assert len(history.thoughts) == 0
        assert isinstance(history.branches, dict)
        assert len(history.branches) == 0
        assert isinstance(history.session_id, str)
        assert len(history.session_id) > 0
        assert isinstance(history.created_at, float)
        assert isinstance(history.updated_at, float)


class TestSequentialThinkingTool:
    """Test SequentialThinkingTool class"""
    
    @pytest.fixture
    def tool(self):
        """Create a SequentialThinkingTool instance for testing"""
        return SequentialThinkingTool()
    
    @pytest.fixture
    def tool_with_config(self):
        """Create a SequentialThinkingTool with custom config"""
        return SequentialThinkingTool({"name": "custom_thinking"})
    
    def test_tool_initialization_default(self, tool):
        """Test tool initialization with default settings"""
        assert tool.name == "sequentialthinking"
        assert "dynamic and reflective problem-solving" in tool.description
        assert tool._thinking_sessions == {}
        assert tool._active_sessions == {}
    
    def test_tool_initialization_with_config(self, tool_with_config):
        """Test tool initialization with custom config"""
        assert tool_with_config.name == "custom_thinking"
    
    def test_tool_initialization_with_id_config(self):
        """Test tool initialization with id in config"""
        tool = SequentialThinkingTool({"id": "thinking_tool_id"})
        assert tool.name == "thinking_tool_id"
    
    def test_validate_thought_data_valid_input(self, tool):
        """Test validation with valid input data"""
        data = {
            "thought": "This is a test thought",
            "nextThoughtNeeded": True,
            "thoughtNumber": 1,
            "totalThoughts": 5
        }
        
        thought = tool.validate_thought_data(data)
        
        assert isinstance(thought, ThoughtData)
        assert thought.thought == "This is a test thought"
        assert thought.next_thought_needed is True
        assert thought.thought_number == 1
        assert thought.total_thoughts == 5
    
    def test_validate_thought_data_with_optional_fields(self, tool):
        """Test validation with optional fields"""
        data = {
            "thought": "Revision thought",
            "nextThoughtNeeded": False,
            "thoughtNumber": 3,
            "totalThoughts": 5,
            "isRevision": True,
            "revisesThought": 2,
            "branchFromThought": 1,
            "branchId": "alternative",
            "needsMoreThoughts": True
        }
        
        thought = tool.validate_thought_data(data)
        
        assert thought.is_revision is True
        assert thought.revises_thought == 2
        assert thought.branch_from_thought == 1
        assert thought.branch_id == "alternative"
        assert thought.needs_more_thoughts is True
    
    def test_validate_thought_data_empty_thought(self, tool):
        """Test validation fails with empty thought"""
        data = {
            "thought": "",
            "nextThoughtNeeded": True,
            "thoughtNumber": 1,
            "totalThoughts": 5
        }
        
        with pytest.raises(ValueError, match="'thought' must be a non-empty string"):
            tool.validate_thought_data(data)
    
    def test_validate_thought_data_invalid_thought_number(self, tool):
        """Test validation fails with invalid thought number"""
        data = {
            "thought": "Valid thought",
            "nextThoughtNeeded": True,
            "thoughtNumber": 0,
            "totalThoughts": 5
        }
        
        with pytest.raises(ValueError, match="'thoughtNumber' must be a positive integer >= 1"):
            tool.validate_thought_data(data)
    
    def test_validate_thought_data_auto_correct_total_thoughts(self, tool):
        """Test auto-correction of totalThoughts when too low"""
        data = {
            "thought": "Valid thought",
            "nextThoughtNeeded": True,
            "thoughtNumber": 5,
            "totalThoughts": 3
        }
        
        thought = tool.validate_thought_data(data)
        assert thought.total_thoughts == 5  # Auto-corrected to match thought_number
    
    def test_validate_thought_data_invalid_revises_thought(self, tool):
        """Test validation fails with invalid revisesThought"""
        data = {
            "thought": "Valid thought",
            "nextThoughtNeeded": True,
            "thoughtNumber": 1,
            "totalThoughts": 5,
            "revisesThought": 0
        }
        
        with pytest.raises(ValueError, match="'revisesThought' must be a positive integer >= 1"):
            tool.validate_thought_data(data)
    
    def test_validate_thought_data_invalid_branch_id(self, tool):
        """Test validation fails with invalid branchId"""
        data = {
            "thought": "Valid thought",
            "nextThoughtNeeded": True,
            "thoughtNumber": 1,
            "totalThoughts": 5,
            "branchId": ""
        }
        
        with pytest.raises(ValueError, match="'branchId' must be a non-empty string"):
            tool.validate_thought_data(data)
    
    def test_format_thought_data(self, tool):
        """Test formatting thought data for response"""
        thought = ThoughtData(
            thought="Test thought",
            next_thought_needed=True,
            thought_number=1,
            total_thoughts=5,
            is_revision=True,
            revises_thought=2,
            branch_id="test_branch"
        )
        
        session = ThoughtHistory()
        session.updated_at = 1234567890.0
        
        formatted = tool.format_thought_data(thought, session)
        
        assert formatted["thought_number"] == 1
        assert formatted["thought_content"] == "Test thought"
        assert formatted["total_thoughts"] == 5
        assert formatted["next_thought_needed"] is True
        assert formatted["is_revision"] is True
        assert formatted["revises_thought"] == 2
        assert formatted["branch_id"] == "test_branch"
        assert formatted["session_id"] == session.session_id
        assert formatted["timestamp"] == 1234567890.0
    
    def test_get_or_create_session_new_user(self, tool):
        """Test creating new session for new user"""
        session = tool._get_or_create_session("test_user")
        
        assert isinstance(session, ThoughtHistory)
        assert "test_user" in tool._active_sessions
        assert session.session_id in tool._thinking_sessions
    
    def test_get_or_create_session_existing_user(self, tool):
        """Test getting existing session for user"""
        # Create first session
        session1 = tool._get_or_create_session("test_user")
        session1_id = session1.session_id
        
        # Get same session
        session2 = tool._get_or_create_session("test_user")
        
        assert session1.session_id == session2.session_id
        assert session1_id == session2.session_id
    
    def test_process_thought_data_basic(self, tool):
        """Test basic thought processing"""
        thought = ThoughtData(
            thought="Test thought",
            next_thought_needed=True,
            thought_number=1,
            total_thoughts=5
        )
        
        session = ThoughtHistory()
        
        processed = tool.process_thought_data(thought, session)
        
        assert isinstance(processed, ProcessedThought)
        assert processed.processed_thought_number == 1
        assert processed.estimated_total_thoughts == 5
        assert processed.next_thought_needed is True
        assert processed.status == "success"
        assert len(session.thoughts) == 1
        assert session.thoughts[0] == thought
    
    def test_process_thought_data_auto_adjust_total(self, tool):
        """Test auto-adjustment of totalThoughts"""
        thought = ThoughtData(
            thought="Test thought",
            next_thought_needed=True,
            thought_number=10,
            total_thoughts=5
        )
        
        session = ThoughtHistory()
        
        processed = tool.process_thought_data(thought, session)
        
        assert processed.estimated_total_thoughts == 10
        assert thought.total_thoughts == 10
    
    def test_process_thought_data_revision(self, tool):
        """Test thought revision processing"""
        # Add initial thoughts
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
        
        assert processed.is_revision is True
        assert processed.revises_thought == 1
        assert len(session.thoughts) == 1  # Original replaced
        assert session.thoughts[0].thought == "Revised thought"
    
    def test_process_thought_data_branching(self, tool):
        """Test thought branching processing"""
        # Add initial thoughts
        session = ThoughtHistory()
        for i in range(3):
            thought = ThoughtData(
                thought=f"Thought {i+1}",
                next_thought_needed=True,
                thought_number=i+1,
                total_thoughts=5
            )
            session.thoughts.append(thought)
        
        # Create branch
        branch_thought = ThoughtData(
            thought="Branch thought",
            next_thought_needed=True,
            thought_number=4,
            total_thoughts=5,
            branch_id="alternative",
            branch_from_thought=2
        )
        
        processed = tool.process_thought_data(branch_thought, session)
        
        assert processed.is_branch is True
        assert "alternative" in session.branches
        assert len(session.branches["alternative"]) == 3  # Copied thoughts 1-2 + new branch thought
    
    def test_generate_coordinator_response_problem_identification(self, tool):
        """Test coordinator response for problem identification"""
        thought = ThoughtData(
            thought="We have a major problem with customer churn",
            next_thought_needed=True,
            thought_number=1,
            total_thoughts=5
        )
        
        session = ThoughtHistory()
        
        response = tool._generate_coordinator_response(thought, session)
        
        assert "Problem identification detected" in response
        assert "Analysis:" in response
        assert "Progress:" in response
        assert "Guidance:" in response
    
    def test_generate_coordinator_response_revision(self, tool):
        """Test coordinator response for revision"""
        thought = ThoughtData(
            thought="Let me revise my previous analysis",
            next_thought_needed=True,
            thought_number=3,
            total_thoughts=5,
            is_revision=True,
            revises_thought=2
        )
        
        session = ThoughtHistory()
        
        response = tool._generate_coordinator_response(thought, session)
        
        assert "📝 Revision of thought #2 detected" in response
        assert "Consider how this revision changes your overall approach" in response
    
    def test_generate_coordinator_response_branching(self, tool):
        """Test coordinator response for branching"""
        thought = ThoughtData(
            thought="Let me explore an alternative approach",
            next_thought_needed=True,
            thought_number=4,
            total_thoughts=5,
            branch_id="alternative_approach"
        )
        
        session = ThoughtHistory()
        
        response = tool._generate_coordinator_response(thought, session)
        
        assert "🌳 Branching into alternative path: alternative_approach" in response
        assert "Explore this alternative thoroughly" in response
    
    @pytest.mark.asyncio
    async def test_run_valid_input(self, tool):
        """Test successful tool execution"""
        arguments = {
            "thought": "I need to analyze this problem step by step",
            "nextThoughtNeeded": True,
            "thoughtNumber": 1,
            "totalThoughts": 5,
            "userId": "test_user"
        }
        
        result = await tool.run(arguments)
        
        assert isinstance(result, ToolResult)
        assert len(result.content) == 1
        assert isinstance(result.content[0], TextContent)
        
        # Parse response JSON
        content = result.content[0]
        assert isinstance(content, TextContent)
        response_data = json.loads(content.text)
        
        assert response_data["processedThoughtNumber"] == 1
        assert response_data["estimatedTotalThoughts"] == 5
        assert response_data["nextThoughtNeeded"] is True
        assert response_data["status"] == "success"
        assert "coordinatorResponse" in response_data
    
    @pytest.mark.asyncio
    async def test_run_validation_error(self, tool):
        """Test tool execution with validation error"""
        arguments = {
            "thought": "",  # Invalid empty thought
            "nextThoughtNeeded": True,
            "thoughtNumber": 1,
            "totalThoughts": 5
        }
        
        result = await tool.run(arguments)
        
        assert isinstance(result, ToolResult)
        content = result.content[0]
        assert isinstance(content, TextContent)
        response_data = json.loads(content.text)
        
        assert response_data["status"] == "validation_error"
        assert "'thought' must be a non-empty string" in response_data["error"]
    
    @pytest.mark.asyncio
    async def test_run_with_revision(self, tool):
        """Test tool execution with revision"""
        # First thought
        arguments1 = {
            "thought": "Initial analysis shows X",
            "nextThoughtNeeded": True,
            "thoughtNumber": 1,
            "totalThoughts": 3,
            "userId": "test_user"
        }
        await tool.run(arguments1)
        
        # Revision
        arguments2 = {
            "thought": "Actually, revised analysis shows Y",
            "nextThoughtNeeded": True,
            "thoughtNumber": 2,
            "totalThoughts": 3,
            "isRevision": True,
            "revisesThought": 1,
            "userId": "test_user"
        }
        
        result = await tool.run(arguments2)
        content = result.content[0]
        assert isinstance(content, TextContent)
        response_data = json.loads(content.text)
        
        assert response_data["isRevision"] is True
        assert response_data["revisesThought"] == 1
    
    @pytest.mark.asyncio
    async def test_run_with_branching(self, tool):
        """Test tool execution with branching"""
        # Setup initial thoughts
        for i in range(2):
            arguments = {
                "thought": f"Initial thought {i+1}",
                "nextThoughtNeeded": True,
                "thoughtNumber": i+1,
                "totalThoughts": 5,
                "userId": "test_user"
            }
            await tool.run(arguments)
        
        # Branch
        branch_arguments = {
            "thought": "Alternative approach",
            "nextThoughtNeeded": True,
            "thoughtNumber": 3,
            "totalThoughts": 5,
            "branchId": "alternative",
            "branchFromThought": 2,
            "userId": "test_user"
        }
        
        result = await tool.run(branch_arguments)
        content = result.content[0]
        assert isinstance(content, TextContent)
        response_data = json.loads(content.text)
        
        assert response_data["isBranch"] is True
        assert "alternative" in response_data["branches"]
    
    @pytest.mark.asyncio
    async def test_run_multiple_users(self, tool):
        """Test tool execution with multiple users"""
        # User 1
        arguments1 = {
            "thought": "User 1 thought",
            "nextThoughtNeeded": True,
            "thoughtNumber": 1,
            "totalThoughts": 3,
            "userId": "user1"
        }
        result1 = await tool.run(arguments1)
        
        # User 2
        arguments2 = {
            "thought": "User 2 thought",
            "nextThoughtNeeded": True,
            "thoughtNumber": 1,
            "totalThoughts": 3,
            "userId": "user2"
        }
        result2 = await tool.run(arguments2)
        
        # Verify separate sessions
        content1 = result1.content[0]
        content2 = result2.content[0]
        assert isinstance(content1, TextContent)
        assert isinstance(content2, TextContent)
        response1 = json.loads(content1.text)
        response2 = json.loads(content2.text)
        
        assert response1["thoughtHistoryLength"] == 1
        assert response2["thoughtHistoryLength"] == 1
        
        # Verify sessions are isolated
        assert len(tool._active_sessions) == 2
        assert "user1" in tool._active_sessions
        assert "user2" in tool._active_sessions
    
    @pytest.mark.asyncio
    async def test_run_exception_handling(self, tool):
        """Test tool execution with unexpected exception"""
        # Mock the validate_thought_data to raise an unexpected exception
        with patch.object(tool, 'validate_thought_data', side_effect=RuntimeError("Unexpected error")):
            arguments = {
                "thought": "Test thought",
                "nextThoughtNeeded": True,
                "thoughtNumber": 1,
                "totalThoughts": 3
            }
            
            result = await tool.run(arguments)
            content = result.content[0]
            assert isinstance(content, TextContent)
            response_data = json.loads(content.text)
            
            assert response_data["status"] == "failed"
            assert "Unexpected error" in response_data["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
