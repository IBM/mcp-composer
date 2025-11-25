# sequential_thinking_tool.py

import time
import uuid
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from fastmcp.tools import Tool
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from pydantic import ConfigDict, PrivateAttr

from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()


@dataclass
class ThoughtData:
    """Data structure for individual thoughts in the sequential thinking process"""

    thought: str
    next_thought_needed: bool
    thought_number: int
    total_thoughts: int
    is_revision: bool = False
    revises_thought: Optional[int] = None
    branch_from_thought: Optional[int] = None
    branch_id: Optional[str] = None
    needs_more_thoughts: bool = False


@dataclass
class ThoughtHistory:
    """Maintains the history of thoughts for a thinking session"""

    thoughts: List[ThoughtData] = field(default_factory=list)
    branches: Dict[str, List[ThoughtData]] = field(default_factory=dict)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class ProcessedThought:
    """Response structure for processed thoughts"""

    processed_thought_number: int
    estimated_total_thoughts: int
    next_thought_needed: bool
    coordinator_response: str
    branches: List[str]
    thought_history_length: int
    branch_details: Dict[str, Any]
    is_revision: bool
    revises_thought: Optional[int]
    is_branch: bool
    status: str
    error: Optional[str] = None


class SequentialThinkingTool(Tool):
    """
    Sequential Thinking Tool for dynamic and reflective problem-solving.
    This tool implements a structured approach to complex problem-solving through iterative thinking.
    It enables users to break down complex problems into manageable steps, revise previous thoughts,
    explore alternative reasoning paths, and build comprehensive solutions through guided reflection.

    Key Features:
    - Dynamic thought progression with adjustable estimates
    - Thought revision and branching capabilities
    - Session-based context maintenance across multiple interactions
    - Intelligent coordinator responses with contextual guidance
    - Support for hypothesis generation and verification
    - Multi-user session isolation

    Based on the Model Context Protocol sequential thinking server implementation:
    https://github.com/modelcontextprotocol/servers/blob/main/src/sequentialthinking/index.ts

    Usage:
        tool = SequentialThinkingTool({"name": "sequentialthinking"})
        result = await tool.run({
            "thought": "I need to solve customer churn problem",
            "nextThoughtNeeded": True,
            "thoughtNumber": 1,
            "totalThoughts": 5
        })
    """

    model_config = ConfigDict(extra="allow")

    # Private attributes for session management
    _thinking_sessions: Dict[str, ThoughtHistory] = PrivateAttr(default_factory=dict)
    _active_sessions: Dict[str, str] = PrivateAttr(default_factory=dict)  # user_id -> session_id

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Allow runtime patching of callable attributes (e.g., during testing) while
        delegating standard field assignment back to the Pydantic base implementation.
        """
        if hasattr(type(self), name) and callable(getattr(type(self), name)):
            object.__setattr__(self, name, value)
            return
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        """
        Mirror __setattr__ override so patched callables can be removed without
        triggering Pydantic's attribute restrictions.
        """
        if name in self.__dict__:
            object.__delattr__(self, name)
            return
        if hasattr(type(self), name) and callable(getattr(type(self), name)):
            # Nothing to delete: the class attribute remains intact
            return
        super().__delattr__(name)

    def __init__(self, config: Optional[dict] = None):
        """Initialize the Sequential Thinking Tool"""

        # Define the tool parameters with enhanced schema for better results
        parameters = {
            "type": "object",
            "properties": {
                "thought": {
                    "type": "string",
                    "description": "Your current thinking step. This should be a detailed, specific thought that advances your understanding of the problem. Can include analysis, observations, questions, hypotheses, or conclusions.",
                    "minLength": 10,
                    "maxLength": 2000,
                    "examples": [
                        "The main problem seems to be that customers are leaving after the first month, which suggests an onboarding issue.",
                        "Based on the data, I notice a pattern: 80% of churned users never completed the tutorial.",
                        "I should revise my earlier assumption - the issue might not be pricing but user experience.",
                    ],
                },
                "nextThoughtNeeded": {
                    "type": "boolean",
                    "description": "Whether another thought step is needed to continue the thinking process. Set to false only when you have reached a satisfactory conclusion.",
                    "examples": [True, False],
                },
                "thoughtNumber": {
                    "type": "integer",
                    "description": "Current thought number in the sequence (starting from 1). This should increment with each new thought.",
                    "minimum": 1,
                    "maximum": 100,
                    "examples": [1, 2, 3, 5, 10],
                },
                "totalThoughts": {
                    "type": "integer",
                    "description": "Your current estimate of total thoughts needed to solve this problem. This can be adjusted up or down as you progress and better understand the complexity.",
                    "minimum": 1,
                    "maximum": 100,
                    "examples": [3, 5, 8, 12, 15],
                },
                "isRevision": {
                    "type": "boolean",
                    "description": "Set to true if this thought is revising, correcting, or updating a previous thought with new insights or information.",
                    "default": False,
                    "examples": [False, True],
                },
                "revisesThought": {
                    "type": "integer",
                    "description": "If isRevision is true, specify which thought number (1-based) is being revised. This helps track the evolution of your thinking.",
                    "minimum": 1,
                    "examples": [2, 5, 8],
                },
                "branchFromThought": {
                    "type": "integer",
                    "description": "If you want to explore an alternative line of reasoning, specify which thought number to branch from. This creates a parallel thinking path.",
                    "minimum": 1,
                    "examples": [3, 7, 12],
                },
                "branchId": {
                    "type": "string",
                    "description": "A unique identifier for this branch of thinking. Use descriptive names that indicate the alternative approach being explored.",
                    "pattern": "^[a-zA-Z0-9_-]+$",
                    "minLength": 2,
                    "maxLength": 50,
                    "examples": [
                        "cost_optimization",
                        "user_experience_focus",
                        "technical_solution",
                        "alternative_approach",
                    ],
                },
                "needsMoreThoughts": {
                    "type": "boolean",
                    "description": "Set to true if you realize the problem is more complex than initially estimated and you need to extend beyond your original totalThoughts estimate.",
                    "default": False,
                    "examples": [False, True],
                },
                "userId": {
                    "type": "string",
                    "description": "Identifier for the user/session to maintain separate thinking contexts. Use consistent IDs to maintain session continuity.",
                    "default": "default",
                    "pattern": "^[a-zA-Z0-9_-]+$",
                    "minLength": 1,
                    "maxLength": 100,
                    "examples": ["default", "user123", "session_abc", "analyst_john"],
                },
            },
            "required": ["thought", "nextThoughtNeeded", "thoughtNumber", "totalThoughts"],
            "additionalProperties": False,
            "examples": [
                {
                    "thought": "I need to analyze the customer churn data to identify the root cause of the 40% monthly churn rate.",
                    "nextThoughtNeeded": True,
                    "thoughtNumber": 1,
                    "totalThoughts": 6,
                    "userId": "analyst_session",
                },
                {
                    "thought": "After reviewing the data, I found that 75% of churned customers never engaged with our core feature. This suggests an onboarding problem rather than a product-market fit issue.",
                    "nextThoughtNeeded": True,
                    "thoughtNumber": 3,
                    "totalThoughts": 6,
                    "userId": "analyst_session",
                },
                {
                    "thought": "Actually, let me reconsider the previous analysis. The correlation between feature engagement and churn might be misleading - perhaps the feature itself is the problem.",
                    "nextThoughtNeeded": True,
                    "thoughtNumber": 5,
                    "totalThoughts": 8,
                    "isRevision": True,
                    "revisesThought": 3,
                    "needsMoreThoughts": True,
                    "userId": "analyst_session",
                },
            ],
        }

        # Tool description matching the original specification
        description = """A detailed tool for dynamic and reflective problem-solving through thoughts.
This tool helps analyze problems through a flexible thinking process that can adapt and evolve.
Each thought can build on, question, or revise previous insights as understanding deepens.

When to use this tool:
- Breaking down complex problems into steps
- Planning and design with room for revision
- Analysis that might need course correction
- Problems where the full scope might not be clear initially
- Problems that require a multi-step solution
- Tasks that need to maintain context over multiple steps
- Situations where irrelevant information needs to be filtered out

Key features:
- You can adjust total_thoughts up or down as you progress
- You can question or revise previous thoughts
- You can add more thoughts even after reaching what seemed like the end
- You can express uncertainty and explore alternative approaches
- Not every thought needs to build linearly - you can branch or backtrack
- Generates a solution hypothesis
- Verifies the hypothesis based on the Chain of Thought steps
- Repeats the process until satisfied
- Provides a correct answer

Parameters explained:
- thought: Your current thinking step, which can include regular analytical steps, revisions, questions, realizations, changes in approach, hypothesis generation, hypothesis verification
- nextThoughtNeeded: True if you need more thinking, even if at what seemed like the end
- thoughtNumber: Current number in sequence (can go beyond initial total if needed)
- totalThoughts: Current estimate of thoughts needed (can be adjusted up/down)
- isRevision: A boolean indicating if this thought revises previous thinking
- revisesThought: If isRevision is true, which thought number is being reconsidered
- branchFromThought: If branching, which thought number is the branching point
- branchId: Identifier for the current branch (if any)
- needsMoreThoughts: If reaching end but realizing more thoughts needed

You should:
1. Start with an initial estimate of needed thoughts, but be ready to adjust
2. Feel free to question or revise previous thoughts
3. Don't hesitate to add more thoughts if needed, even at the "end"
4. Express uncertainty when present
5. Mark thoughts that revise previous thinking or branch into new paths
6. Ignore information that is irrelevant to the current step
7. Generate a solution hypothesis when appropriate
8. Verify the hypothesis based on the Chain of Thought steps
9. Repeat the process until satisfied with the solution
10. Provide a single, ideally correct answer as the final output
11. Only set nextThoughtNeeded to false when truly done and a satisfactory answer is reached"""

        # Get tool name from config or use default
        tool_name = "sequentialthinking"
        if config and "name" in config:
            tool_name = config["name"]
        elif config and "id" in config:
            tool_name = config["id"]

        super().__init__(
            name=tool_name,
            description=description,
            parameters=parameters,
        )

        # Initialize private attributes
        self._thinking_sessions = {}
        self._active_sessions = {}

        logger.info("Sequential Thinking Tool '%s' initialized", tool_name)

    def validate_thought_data(self, data: Dict[str, Any]) -> ThoughtData:
        """
        Validate and convert input data to ThoughtData structure.

        Args:
            data: Raw input data from tool call

        Returns:
            ThoughtData: Validated thought data

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Extract and validate required fields with early returns for efficiency
        thought = data.get("thought")
        if not isinstance(thought, str) or not thought.strip():
            raise ValueError("'thought' must be a non-empty string")

        next_thought_needed = data.get("nextThoughtNeeded")
        if not isinstance(next_thought_needed, bool):
            raise ValueError("'nextThoughtNeeded' must be a boolean")

        thought_number = data.get("thoughtNumber")
        if not isinstance(thought_number, int) or thought_number < 1:
            raise ValueError("'thoughtNumber' must be a positive integer >= 1")

        total_thoughts = data.get("totalThoughts")
        if not isinstance(total_thoughts, int) or total_thoughts < 1:
            # Auto-correct if totalThoughts is too low (similar to provided implementation)
            total_thoughts = max(1, thought_number)
        elif total_thoughts < thought_number:
            # Ensure total_thoughts never falls behind the current thought number
            total_thoughts = thought_number

        # Extract optional fields with defaults
        is_revision = bool(data.get("isRevision", False))
        needs_more_thoughts = bool(data.get("needsMoreThoughts", False))

        revises_thought = data.get("revisesThought")
        if revises_thought is not None and (not isinstance(revises_thought, int) or revises_thought < 1):
            raise ValueError("'revisesThought' must be a positive integer >= 1")

        branch_from_thought = data.get("branchFromThought")
        if branch_from_thought is not None and (not isinstance(branch_from_thought, int) or branch_from_thought < 1):
            raise ValueError("'branchFromThought' must be a positive integer >= 1")

        branch_id = data.get("branchId")
        if branch_id is not None:
            if not isinstance(branch_id, str) or not branch_id.strip():
                raise ValueError("'branchId' must be a non-empty string")
            branch_id = branch_id.strip()

        return ThoughtData(
            thought=thought.strip(),
            next_thought_needed=next_thought_needed,
            thought_number=thought_number,
            total_thoughts=total_thoughts,
            is_revision=is_revision,
            revises_thought=revises_thought,
            branch_from_thought=branch_from_thought,
            branch_id=branch_id,
            needs_more_thoughts=needs_more_thoughts,
        )

    def format_thought_data(self, thought: ThoughtData, session: ThoughtHistory) -> Dict[str, Any]:
        """
        Format thought data for response.

        Args:
            thought: The thought data to format
            session: The current thinking session

        Returns:
            Dict: Formatted thought data
        """
        return {
            "thought_number": thought.thought_number,
            "thought_content": thought.thought,
            "total_thoughts": thought.total_thoughts,
            "next_thought_needed": thought.next_thought_needed,
            "is_revision": thought.is_revision,
            "revises_thought": thought.revises_thought,
            "branch_from_thought": thought.branch_from_thought,
            "branch_id": thought.branch_id,
            "needs_more_thoughts": thought.needs_more_thoughts,
            "session_id": session.session_id,
            "timestamp": session.updated_at,
        }

    def process_thought_data(self, thought: ThoughtData, session: ThoughtHistory) -> ProcessedThought:
        """
        Process thought data and generate coordinator response.

        Args:
            thought: The thought to process
            session: The current thinking session

        Returns:
            ProcessedThought: Processed thought with coordinator response
        """
        try:
            # Auto-adjust totalThoughts if we exceed the current estimate
            if thought.thought_number > thought.total_thoughts:
                thought.total_thoughts = thought.thought_number
                logger.info(
                    "Auto-adjusted totalThoughts to %s for thought #%s", thought.total_thoughts, thought.thought_number
                )

            # Handle thought revision - replace existing thought if it's a revision
            if thought.is_revision and thought.revises_thought is not None:
                # Find and replace the thought being revised
                for i, existing_thought in enumerate(session.thoughts):
                    if existing_thought.thought_number == thought.revises_thought:
                        session.thoughts[i] = thought
                        session.updated_at = time.time()
                        logger.info(
                            "Revised thought #%s with new content",
                            thought.revises_thought,
                        )
                        break
                else:
                    # If thought to revise not found, add as new thought
                    session.thoughts.append(thought)
                    session.updated_at = time.time()
            else:
                # Handle branching - create new branch if needed
                if thought.branch_id and thought.branch_from_thought:
                    if thought.branch_id not in session.branches:
                        # Create new branch by copying main thoughts up to branch point
                        session.branches[thought.branch_id] = []
                        for existing_thought in session.thoughts:
                            if existing_thought.thought_number <= thought.branch_from_thought:
                                session.branches[thought.branch_id].append(existing_thought)
                        logger.info(
                            "Created new branch '%s' from thought #%s", thought.branch_id, thought.branch_from_thought
                        )

                # Add thought to appropriate location
                if thought.branch_id:
                    session.branches[thought.branch_id].append(thought)
                else:
                    session.thoughts.append(thought)
                session.updated_at = time.time()

            # Generate coordinator response based on thought content and context
            coordinator_response = self._generate_coordinator_response(thought, session)

            # Create debugging trace (similar to provided implementation)
            debug_trace = [
                "\n=== Sequential Thought ===",
                f"Branch: {thought.branch_id or 'main'}",
                f"Step: {thought.thought_number} / {thought.total_thoughts}",
                f"Revision: {thought.is_revision} (revises {thought.revises_thought})",
                f"Next Thought Needed: {thought.next_thought_needed}",
                f"Needs More Thoughts: {thought.needs_more_thoughts}",
                "---",
                thought.thought[:200] + "..." if len(thought.thought) > 200 else thought.thought,
                "==========================\n",
            ]
            logger.debug("\n".join(debug_trace))

            # Prepare branch details with summary
            branches_summary = {"main": len(session.thoughts)}
            branches_summary.update({bid: len(thoughts) for bid, thoughts in session.branches.items()})

            branch_details = {
                "currentBranchId": thought.branch_id or "main",
                "originThought": thought.branch_from_thought or 1,
                "branchCount": len(session.branches) + 1,  # +1 for main branch
                "branchesSummary": branches_summary,
            }

            return ProcessedThought(
                processed_thought_number=thought.thought_number,
                estimated_total_thoughts=thought.total_thoughts,
                next_thought_needed=thought.next_thought_needed,
                coordinator_response=coordinator_response,
                branches=list(session.branches.keys()),
                thought_history_length=len(session.thoughts),
                branch_details=branch_details,
                is_revision=thought.is_revision,
                revises_thought=thought.revises_thought,
                is_branch=thought.branch_id is not None,
                status="success",
            )

        except Exception as e:
            logger.error("Error processing thought data: %s", e)
            return ProcessedThought(
                processed_thought_number=thought.thought_number,
                estimated_total_thoughts=thought.total_thoughts,
                next_thought_needed=thought.next_thought_needed,
                coordinator_response="Error occurred while processing thought",
                branches=list(session.branches.keys()) if hasattr(session, "branches") else [],
                thought_history_length=len(session.thoughts) if hasattr(session, "thoughts") else 0,
                branch_details={},
                is_revision=thought.is_revision,
                revises_thought=thought.revises_thought,
                is_branch=thought.branch_id is not None,
                status="failed",
                error=str(e),
            )

    def _generate_coordinator_response(self, thought: ThoughtData, session: ThoughtHistory) -> str:
        """
        Generate a coordinator response based on the current thought and session context.

        Args:
            thought: Current thought
            session: Thinking session

        Returns:
            str: Coordinator response with guidance
        """
        # Analyze thought content for keywords and patterns
        thought_content = thought.thought.lower()

        # Base response components
        analysis_parts = []
        guidance_parts = []

        # Analyze thought type and content
        if thought.is_revision:
            analysis_parts.append(f"📝 Revision of thought #{thought.revises_thought} detected.")
            guidance_parts.append("Consider how this revision changes your overall approach.")

        if thought.branch_id:
            analysis_parts.append(f"🌳 Branching into alternative path: {thought.branch_id}")
            guidance_parts.append("Explore this alternative thoroughly before comparing with main path.")

        # Content-based analysis
        if any(word in thought_content for word in ["problem", "issue", "challenge"]):
            analysis_parts.append("🎯 Problem identification detected.")
            if thought.thought_number <= 2:
                guidance_parts.append(
                    "Good start! Continue by gathering relevant information or breaking down the problem further."
                )

        if any(word in thought_content for word in ["data", "information", "research", "evidence"]):
            analysis_parts.append("📊 Information gathering phase identified.")
            guidance_parts.append(
                "Ensure you have sufficient data before moving to analysis. Consider what additional information might be needed."
            )

        if any(word in thought_content for word in ["analyze", "analysis", "pattern", "trend"]):
            analysis_parts.append("🔍 Analysis phase detected.")
            guidance_parts.append("Look for patterns, root causes, and relationships. Consider multiple perspectives.")

        if any(word in thought_content for word in ["solution", "approach", "strategy", "plan"]):
            analysis_parts.append("💡 Solution development identified.")
            guidance_parts.append(
                "Evaluate feasibility, resources needed, and potential risks. Consider alternative solutions."
            )

        if any(word in thought_content for word in ["hypothesis", "theory", "assume"]):
            analysis_parts.append("🧪 Hypothesis formation detected.")
            guidance_parts.append("Test your hypothesis against available evidence. What would prove or disprove it?")

        if any(word in thought_content for word in ["verify", "test", "validate", "check"]):
            analysis_parts.append("✅ Verification phase identified.")
            guidance_parts.append(
                "Systematically check your conclusions. Look for counterevidence or alternative explanations."
            )

        # Progress analysis
        progress_ratio = thought.thought_number / thought.total_thoughts
        if progress_ratio < 0.3:
            guidance_parts.append(
                "You're in the early stages. Focus on understanding and defining the problem clearly."
            )
        elif progress_ratio < 0.7:
            guidance_parts.append(
                "You're making good progress. Continue building on your insights and gathering evidence."
            )
        else:
            guidance_parts.append(
                "You're in the final stages. Focus on synthesis, verification, and reaching conclusions."
            )

        # Uncertainty detection
        if any(word in thought_content for word in ["uncertain", "unclear", "confused", "not sure"]):
            guidance_parts.append(
                "🤔 Uncertainty detected. Consider what additional information or analysis might help clarify your thinking."
            )

        # Needs more thoughts detection
        if thought.needs_more_thoughts:
            guidance_parts.append(
                "📈 Scope expansion detected. Adjust your approach to accommodate the additional complexity."
            )

        # Construct final response
        response_parts = []

        if analysis_parts:
            response_parts.append("**Analysis:** " + " ".join(analysis_parts))

        # Add context about session progress
        response_parts.append(
            f"**Progress:** Thought {thought.thought_number} of {thought.total_thoughts} (Session: {len(session.thoughts)} total thoughts)"
        )

        if guidance_parts:
            response_parts.append("**Guidance:** " + " ".join(guidance_parts))

        # Add continuation guidance
        if thought.next_thought_needed:
            response_parts.append(
                "**Next Steps:** Continue with your next thought, building on current insights or exploring new angles as needed."
            )
        else:
            response_parts.append(
                "**Completion:** You've indicated this thinking process is complete. Review your conclusions for completeness and accuracy."
            )

        return "\n\n".join(response_parts)

    def _get_or_create_session(self, user_id: str = "default") -> ThoughtHistory:
        """Get or create a thinking session for a user"""
        session_id = self._active_sessions.get(user_id)

        if session_id and session_id in self._thinking_sessions:
            return self._thinking_sessions[session_id]

        # Create new session
        session = ThoughtHistory()
        self._thinking_sessions[session.session_id] = session
        self._active_sessions[user_id] = session.session_id

        logger.info(
            "Created new thinking session %s for user %s",
            session.session_id,
            user_id,
        )
        return session

    async def run(self, arguments: Dict[str, Any]) -> ToolResult:
        """
        Execute the sequential thinking tool.

        Args:
            arguments: Tool arguments containing thought data

        Returns:
            ToolResult: Processed thought with coordinator response
        """
        try:
            # Extract user_id from arguments
            user_id = arguments.get("userId", "default")

            # Validate input data
            thought_data = self.validate_thought_data(arguments)

            # Get or create thinking session
            session = self._get_or_create_session(user_id)

            # Process the thought
            processed_thought = self.process_thought_data(thought_data, session)

            # Convert to response format matching original TypeScript implementation
            response = {
                "processedThoughtNumber": processed_thought.processed_thought_number,
                "estimatedTotalThoughts": processed_thought.estimated_total_thoughts,
                "nextThoughtNeeded": processed_thought.next_thought_needed,
                "coordinatorResponse": processed_thought.coordinator_response,
                "branches": processed_thought.branches,
                "thoughtHistoryLength": processed_thought.thought_history_length,
                "branchDetails": processed_thought.branch_details,
                "isRevision": processed_thought.is_revision,
                "revisesThought": processed_thought.revises_thought,
                "isBranch": processed_thought.is_branch,
                "status": processed_thought.status,
            }

            if processed_thought.error:
                response["error"] = processed_thought.error

            logger.info(
                "Processed thought #%s for user %s",
                thought_data.thought_number,
                user_id,
            )

            # Return as JSON string in TextContent
            return ToolResult(content=[TextContent(type="text", text=json.dumps(response, indent=2))])

        except ValueError as e:
            logger.error("Validation error in sequential thinking: %s", e)
            error_response = {
                "processedThoughtNumber": arguments.get("thoughtNumber", 0),
                "estimatedTotalThoughts": arguments.get("totalThoughts", 0),
                "nextThoughtNeeded": arguments.get("nextThoughtNeeded", False),
                "coordinatorResponse": f"Validation Error: {str(e)}",
                "branches": [],
                "thoughtHistoryLength": 0,
                "branchDetails": {},
                "isRevision": arguments.get("isRevision", False),
                "revisesThought": arguments.get("revisesThought"),
                "isBranch": arguments.get("branchId") is not None,
                "status": "validation_error",
                "error": str(e),
            }
            return ToolResult(content=[TextContent(type="text", text=json.dumps(error_response, indent=2))])

        except Exception as e:
            logger.error("Unexpected error in sequential thinking: %s", e)
            error_response = {
                "processedThoughtNumber": arguments.get("thoughtNumber", 0),
                "estimatedTotalThoughts": arguments.get("totalThoughts", 0),
                "nextThoughtNeeded": arguments.get("nextThoughtNeeded", False),
                "coordinatorResponse": f"An unexpected error occurred: {str(e)}",
                "branches": [],
                "thoughtHistoryLength": 0,
                "branchDetails": {},
                "isRevision": arguments.get("isRevision", False),
                "revisesThought": arguments.get("revisesThought"),
                "isBranch": arguments.get("branchId") is not None,
                "status": "failed",
                "error": str(e),
            }
            return ToolResult(content=[TextContent(type="text", text=json.dumps(error_response, indent=2))])
