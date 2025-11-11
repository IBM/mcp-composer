# deep_research_tool.py

import time
import uuid
import json
import asyncio
import inspect
import aiohttp
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, AsyncGenerator, Callable
from dataclasses import dataclass, field
from enum import Enum
import re
from urllib.parse import urlparse

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS = None
    DDGS_AVAILABLE = False

from fastmcp.tools import Tool
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from pydantic import PrivateAttr

from mcp_composer.core.utils import LoggerFactory, load_json_sync
from mcp_composer.core.resources.resource_manager import MCPResourceManager

logger = LoggerFactory.get_logger()

RESOURCE_RELEVANCE_THRESHOLD = 0.15


def load_deep_research_schema() -> Dict[str, Any]:
    """Load the deep research tool parameter schema from JSON resource file"""
    try:
        # Get the current file's directory and navigate to resources
        current_dir = Path(__file__).parent
        # Navigate up to the project root and then to resources
        schema_path = current_dir.parent.parent.parent.parent / "resources" / "schemas" / "deep_research_tool_schema.json"

        if not schema_path.exists():
            logger.warning(f"Schema file not found at {schema_path}, using fallback schema")
            return _get_fallback_schema()

        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
            logger.info(f"Loaded deep research schema from {schema_path}")
            return schema

    except Exception as e:
        logger.error(f"Error loading deep research schema: {e}")
        logger.info("Using fallback schema")
        return _get_fallback_schema()


def _get_fallback_schema() -> Dict[str, Any]:
    """Fallback schema if JSON file cannot be loaded"""
    fallback_json_file_path = Path(__file__).parent / "deep_research_tool_fallback_schema.json"
    return load_json_sync(fallback_json_file_path)


class ResearchStage(Enum):
    """Enum for research stages"""
    PLANNING = "planning"
    SOURCE_FINDING = "source_finding"
    SUMMARIZATION = "summarization"
    REVIEW = "review"
    WRITING = "writing"
    COMPLETED = "completed"


@dataclass
class SubQuestion:
    """Data structure for research sub-questions"""
    question: str
    question_number: int
    search_terms: Optional[List[str]] = None
    sources: List[Dict[str, Any]] = field(default_factory=list)
    summary: Optional[str] = None
    is_answered: bool = False


@dataclass
class ResearchSource:
    """Data structure for research sources"""
    title: str
    url: str
    summary: str
    content: str
    relevance_score: float = 0.0
    sub_question_number: int = 1
    citation_id: str = ""
    access_date: str = field(default_factory=lambda: time.strftime('%Y-%m-%d'))


@dataclass
class ResearchSession:
    """Maintains the state of a research session"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    main_question: str = ""
    sub_questions: List[SubQuestion] = field(default_factory=list)
    sources: List[ResearchSource] = field(default_factory=list)
    summaries: Dict[int, str] = field(default_factory=dict)  # sub_question_number -> summary
    gaps_identified: List[str] = field(default_factory=list)
    additional_questions: List[str] = field(default_factory=list)
    final_report: Optional[str] = None
    current_stage: ResearchStage = ResearchStage.PLANNING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed: bool = False
    citation_counter: int = 1  # For generating citation IDs
    allowed_domains: Optional[List[str]] = None
    excluded_domains: Optional[List[str]] = None
    domain_priority: Optional[Dict[str, float]] = None


@dataclass
class ResearchResult:
    """Response structure for research operations"""
    stage: str
    session_id: str
    main_question: str
    sub_questions_count: int
    sources_count: int
    current_stage_result: str
    next_stage: Optional[str]
    progress_percentage: float
    is_completed: bool
    final_report: Optional[str] = None
    gaps_identified: List[str] = field(default_factory=list)
    status: str = "success"
    error: Optional[str] = None
    is_streaming: bool = False
    stream_complete: bool = False


@dataclass
class StreamingUpdate:
    """Streaming update structure for progressive results"""
    stage: str
    session_id: str
    progress_percentage: float
    stage_status: str  # "started", "in_progress", "completed"
    stage_result: Optional[str] = None
    sources_found: int = 0
    sub_questions_processed: int = 0
    total_sub_questions: int = 0
    timestamp: float = field(default_factory=time.time)
    is_final: bool = False


class DeepResearchTool(Tool):
    """
    Deep Research Tool implementing a 5-agent research workflow.
    
    This tool performs comprehensive research by breaking down complex questions into
    manageable sub-questions, finding relevant sources, summarizing findings, reviewing
    for gaps, and synthesizing a final research report.
    
    Based on the Langflow deep research multi-agent system:
    https://www.langflow.org/blog/how-to-build-a-deep-research-multi-agent-system
    
    The 5-stage workflow:
    1. Research Planner: Breaks main question into 3-7 sub-questions
    2. Source Finder: Searches web for relevant sources for each sub-question
    3. Summarization: Extracts key information relevant to each sub-question
    4. Reviewer: Identifies gaps and suggests additional questions
    5. Research Writer: Synthesizes structured final report
    
    Key Features:
    - Multi-stage research workflow with automatic progression
    - Web search integration for source discovery
    - Session-based context maintenance
    - Gap analysis and iterative improvement
    - Structured report generation with citations
    - Progress tracking and stage management
    
    Usage:
        tool = DeepResearchTool({"name": "deepresearch"})
        result = await tool.run({
            "question": "What are the impacts of AI on employment?",
            "stage": "planning",  # or let it auto-progress
            "max_sources_per_question": 3,
            "search_enabled": True
        })
    """

    # Private attributes for session management
    _research_sessions: Dict[str, ResearchSession] = PrivateAttr(default_factory=dict)
    _active_sessions: Dict[str, str] = PrivateAttr(default_factory=dict)  # user_id -> session_id
    _streaming_callback: Optional[Callable[[StreamingUpdate], None]] = PrivateAttr(default=None)
    _resource_manager: Optional[MCPResourceManager] = PrivateAttr(default=None)

    def __init__(self, config: Optional[dict] = None):
        """Initialize the Deep Research Tool"""

        # Load parameters from JSON schema resource
        parameters = load_deep_research_schema()

        # Tool description
        description = """A comprehensive deep research tool that implements a structured 5-stage research workflow.

This tool performs thorough research by systematically breaking down complex questions, finding relevant sources, 
analyzing information, identifying gaps, and synthesizing findings into a comprehensive report.

Research Workflow Stages:
1. **Planning**: Breaks your main question into 3-7 focused sub-questions that together cover the topic comprehensively
2. **Source Finding**: Searches for high-quality, relevant sources for each sub-question using DuckDuckGo web search
3. **Summarization**: Extracts and summarizes key information from sources relevant to each sub-question  
4. **Review**: Analyzes coverage for gaps, missing perspectives, and suggests additional research directions
5. **Writing**: Synthesizes all findings into a structured, well-cited research report

Key Features:
- **Systematic Approach**: Follows proven research methodology for comprehensive coverage
- **Source Discovery**: Automatically finds and evaluates relevant sources using DuckDuckGo search
- **Content Extraction**: Retrieves and previews content from web sources for analysis
- **Relevance Scoring**: Ranks sources by relevance to research questions
- **Gap Analysis**: Identifies missing information and suggests additional research directions
- **Session Management**: Maintains research context across multiple interactions
- **Progress Tracking**: Shows research progress and allows stage-by-stage execution
- **Citation Management**: Properly cites all sources in the final report
- **Quality Control**: Reviews findings for completeness and accuracy

When to use this tool:
- Complex research questions requiring multiple sources and perspectives
- Academic or professional research projects
- Market research and competitive analysis  
- Policy research and impact analysis
- Literature reviews and knowledge synthesis
- Fact-finding and investigative research
- Document Search for products and services

Parameters:
- **question**: Your main research question (required)
- **stage**: Research stage to execute ('auto' for full workflow, or specific stage)
- **max_sources_per_question**: Number of sources to find per sub-question (1-10)
- **search_enabled**: Whether to search for sources online
- **streaming**: Enable real-time progress updates (default: true, set to false to disable)
- **session_id**: Continue existing research session
- **user_id**: Identifier for maintaining separate research contexts
- **additional_context**: Extra guidance or constraints for the research
- **force_new_session**: Start fresh research session

The tool automatically progresses through all stages when stage='auto', or you can execute stages individually for more control.
Streaming is enabled by default to provide real-time feedback during research."""

        # Get tool name from config or use default
        tool_name = "deepresearch"
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
        self._research_sessions = {}
        self._active_sessions = {}
        self._streaming_callback = None
        self._resource_manager = None

        if config:
            potential_resource_manager = None
            if isinstance(config, dict):
                potential_resource_manager = config.get("resource_manager")
            elif isinstance(config, MCPResourceManager):
                potential_resource_manager = config
            elif hasattr(config, "resource_manager"):
                potential_resource_manager = getattr(config, "resource_manager")

            if isinstance(potential_resource_manager, MCPResourceManager):
                self._resource_manager = potential_resource_manager
                logger.info("Deep Research Tool configured with MCPResourceManager integration")
            elif potential_resource_manager is not None:
                logger.warning(
                    "Provided resource_manager is not an MCPResourceManager instance; integration disabled"
                )

        logger.info(f"Deep Research Tool '{tool_name}' initialized")

    def set_streaming_callback(self, callback: Callable[[StreamingUpdate], None]) -> None:
        """Set callback function for streaming updates"""
        self._streaming_callback = callback

    def _emit_streaming_update(self, update: StreamingUpdate) -> None:
        """Emit streaming update if callback is set"""
        if self._streaming_callback:
            try:
                self._streaming_callback(update)
            except Exception as e:
                logger.warning(f"Error in streaming callback: {e}")

    def _create_streaming_update(self, session: ResearchSession, stage: str,
                                stage_status: str, stage_result: Optional[str] = None,
                                sources_found: int = 0, sub_questions_processed: int = 0,
                                is_final: bool = False) -> StreamingUpdate:
        """Create a streaming update object"""
        return StreamingUpdate(
            stage=stage,
            session_id=session.session_id,
            progress_percentage=self._calculate_progress(session),
            stage_status=stage_status,
            stage_result=stage_result,
            sources_found=sources_found,
            sub_questions_processed=sub_questions_processed,
            total_sub_questions=len(session.sub_questions),
            is_final=is_final
        )

    def _generate_citation_id(self, session: ResearchSession) -> str:
        """Generate a unique citation ID for a source"""
        citation_id = f"[{session.citation_counter}]"
        session.citation_counter += 1
        return citation_id

    def _get_or_create_session(self, user_id: str = "default", session_id: Optional[str] = None,
                              force_new: bool = False) -> ResearchSession:
        """Get existing session or create a new one"""

        if force_new:
            session = ResearchSession()
            self._research_sessions[session.session_id] = session
            self._active_sessions[user_id] = session.session_id
            logger.info(f"Created new research session {session.session_id} for user {user_id}")
            return session

        if session_id and session_id in self._research_sessions:
            return self._research_sessions[session_id]

        active_session_id = self._active_sessions.get(user_id)
        if active_session_id and active_session_id in self._research_sessions:
            return self._research_sessions[active_session_id]

        # Create new session
        session = ResearchSession()
        self._research_sessions[session.session_id] = session
        self._active_sessions[user_id] = session.session_id

        logger.info(f"Created new research session {session.session_id} for user {user_id}")
        return session

    async def _stage_planning(self, session: ResearchSession, question: str,
                            additional_context: Optional[str] = None,
                            streaming: bool = False) -> str:
        """Stage 1: Research Planning - Break down main question into sub-questions"""

        logger.info(f"Starting research planning for: {question}")

        session.main_question = question
        session.current_stage = ResearchStage.PLANNING
        session.updated_at = time.time()

        # Emit streaming update - planning started
        if streaming:
            update = self._create_streaming_update(session, "planning", "started")
            self._emit_streaming_update(update)

        # Generate sub-questions based on the main question
        # This is a simplified version - in a real implementation, you might use an LLM API
        sub_questions = self._generate_sub_questions(question, additional_context)

        session.sub_questions = [
            SubQuestion(question=q, question_number=i+1)
            for i, q in enumerate(sub_questions)
        ]

        planning_result = f"""**Research Planning Complete**

**Main Question:** {question}

**Sub-questions identified ({len(sub_questions)}):**
{chr(10).join([f"{i+1}. {q}" for i, q in enumerate(sub_questions)])}

**Next Stage:** Source Finding - Will search for relevant sources for each sub-question."""

        # Emit streaming update - planning completed
        if streaming:
            update = self._create_streaming_update(session, "planning", "completed", planning_result)
            self._emit_streaming_update(update)

        logger.info(f"Generated {len(sub_questions)} sub-questions for research")
        return planning_result

    def _generate_sub_questions(self, main_question: str, context: Optional[str] = None) -> List[str]:
        """Generate sub-questions for the main research question"""

        # This is a simplified heuristic-based approach
        # In production, this would use an LLM API for better results

        question_lower = main_question.lower()
        sub_questions = []

        # Base sub-questions that apply to most research topics
        sub_questions.append(f"What is the current state and definition of the topic in: {main_question}?")
        sub_questions.append(f"What are the main factors, causes, or drivers related to: {main_question}?")
        sub_questions.append(f"What are the effects, impacts, or consequences of: {main_question}?")

        # Add specific sub-questions based on question content
        if any(word in question_lower for word in ["impact", "effect", "influence"]):
            sub_questions.append(f"What are the positive and negative aspects of: {main_question}?")
            sub_questions.append(f"Who or what is most affected by: {main_question}?")

        if any(word in question_lower for word in ["future", "trend", "prediction"]):
            sub_questions.append(f"What are the future trends and predictions related to: {main_question}?")

        if any(word in question_lower for word in ["solution", "approach", "strategy"]):
            sub_questions.append(f"What are the current approaches or solutions for: {main_question}?")
            sub_questions.append(f"What are the challenges and limitations in addressing: {main_question}?")

        if any(word in question_lower for word in ["economic", "financial", "cost"]):
            sub_questions.append(f"What are the economic implications of: {main_question}?")

        # Limit to 3-7 sub-questions as recommended
        return sub_questions[:7]

    async def _stage_source_finding(self, session: ResearchSession, max_sources: int = 3,
                                  search_enabled: bool = True, streaming: bool = False) -> str:
        """Stage 2: Source Finding - Find relevant sources for each sub-question"""

        logger.info("Starting source finding stage")

        session.current_stage = ResearchStage.SOURCE_FINDING
        session.updated_at = time.time()

        # Emit streaming update - source finding started
        if streaming:
            update = self._create_streaming_update(session, "source_finding", "started")
            self._emit_streaming_update(update)

        if not search_enabled:
            return "**Source Finding Skipped** - Search disabled. Please provide sources manually."

        total_sources_found = 0

        for i, sub_question in enumerate(session.sub_questions):
            sources = await self._search_sources(
                sub_question.question,
                max_sources,
                allowed_domains=session.allowed_domains if hasattr(session, 'allowed_domains') else None,
                excluded_domains=session.excluded_domains if hasattr(session, 'excluded_domains') else None,
                domain_priority=session.domain_priority if hasattr(session, 'domain_priority') else None
            )
            sub_question.sources = sources

            # Add to session sources with sub-question reference and citations
            for source_data in sources:
                citation_id = self._generate_citation_id(session)
                research_source = ResearchSource(
                    title=source_data.get("title", "Unknown Title"),
                    url=source_data.get("url", ""),
                    summary=source_data.get("summary", ""),
                    content=source_data.get("content", ""),
                    relevance_score=source_data.get("relevance_score", 0.0),
                    sub_question_number=sub_question.question_number,
                    citation_id=citation_id
                )
                session.sources.append(research_source)
                total_sources_found += 1

            # Emit streaming update for progress
            if streaming:
                update = self._create_streaming_update(
                    session, "source_finding", "in_progress",
                    f"Processed {i+1}/{len(session.sub_questions)} sub-questions",
                    sources_found=total_sources_found,
                    sub_questions_processed=i+1
                )
                self._emit_streaming_update(update)

        source_summary = []
        source_summary.append(f"**Source Finding Complete** - Found {total_sources_found} sources")
        source_summary.append("")

        for sub_question in session.sub_questions:
            source_summary.append(f"**Sub-question {sub_question.question_number}:** {sub_question.question}")
            source_summary.append(f"Sources found: {len(sub_question.sources)}")
            for i, source in enumerate(sub_question.sources, 1):
                source_summary.append(f"  {i}. {source.get('title', 'Unknown')} - {source.get('url', 'No URL')}")
            if not sub_question.sources:
                source_summary.append("  - No matching resources found.")
            source_summary.append("")

        if total_sources_found == 0:
            source_summary.append("**No resource-backed sources were found for any sub-questions.**")
            source_summary.append("Ensure the resource manager is populated with relevant resources for this topic.")
            source_summary.append("")

        source_summary.append("**Next Stage:** Summarization - Will extract key information from sources.")

        final_result = "\n".join(source_summary)

        # Emit streaming update - source finding completed
        if streaming:
            update = self._create_streaming_update(
                session, "source_finding", "completed", final_result,
                sources_found=total_sources_found,
                sub_questions_processed=len(session.sub_questions)
            )
            self._emit_streaming_update(update)

        logger.info(f"Found {total_sources_found} total sources across {len(session.sub_questions)} sub-questions")
        return final_result

    async def _get_resource_based_sources(
        self, query: str, max_sources: int
    ) -> List[Dict[str, Any]]:
        """Retrieve sources from the registered resources that match the query."""

        if not self._resource_manager:
            return []

        try:
            available_resources = await self._resource_manager.list_resources()
        except Exception as exc:
            logger.warning("Unable to list resources from resource manager: %s", exc)
            return []

        if not available_resources:
            return []

        matched_sources: List[Dict[str, Any]] = []

        for resource in available_resources:
            uri = getattr(resource, "uri", None)
            if not uri:
                continue

            uri_str = str(uri)
            name = getattr(resource, "name", uri_str)
            description = getattr(resource, "description", "")

            tags = getattr(resource, "tags", None)
            if isinstance(tags, (set, list, tuple)):
                tags_text = " ".join(str(tag) for tag in tags)
            elif tags:
                tags_text = str(tags)
            else:
                tags_text = ""

            metadata_body = " ".join(part for part in [description, tags_text] if part)
            pseudo_result = {"title": name, "body": metadata_body}

            score = self._calculate_relevance_score(query, pseudo_result, None, uri_str)
            content_text = ""

            if score < RESOURCE_RELEVANCE_THRESHOLD:
                content_text = await self._read_resource_content(resource)
                if content_text:
                    pseudo_result["body"] = " ".join(
                        part for part in [metadata_body, content_text] if part
                    )
                    score = self._calculate_relevance_score(
                        query, pseudo_result, None, uri_str
                    )
            else:
                # Still attempt to read content for downstream summarization
                content_text = await self._read_resource_content(resource)

            if score < RESOURCE_RELEVANCE_THRESHOLD:
                continue

            final_content = content_text or pseudo_result["body"]
            if not final_content:
                continue

            summary_text = (
                description
                if description
                else (final_content[:200] + "..." if len(final_content) > 200 else final_content)
            )

            matched_sources.append(
                {
                    "title": name,
                    "url": uri_str,
                    "summary": summary_text,
                    "content": final_content,
                    "relevance_score": score,
                }
            )

        matched_sources.sort(key=lambda item: item["relevance_score"], reverse=True)
        return matched_sources[:max_sources]

    async def _read_resource_content(self, resource) -> str:
        """Safely read content from a resource if available."""

        read_method = getattr(resource, "read", None)
        if not read_method:
            return ""

        result = None
        try:
            if inspect.iscoroutinefunction(read_method):
                result = await read_method()
            else:
                invocation_result = read_method()
                if inspect.isawaitable(invocation_result):
                    result = await invocation_result
                else:
                    result = invocation_result
        except TypeError as exc:
            logger.debug(
                "Resource read() signature mismatch for %s: %s",
                getattr(resource, "name", "unknown"),
                exc,
            )
            return ""
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "Failed to read content from resource %s: %s",
                getattr(resource, "name", "unknown"),
                exc,
            )
            return ""

        if result is None:
            return ""

        if isinstance(result, bytes):
            try:
                result = result.decode("utf-8")
            except Exception:  # pylint: disable=broad-except
                result = result.decode("latin-1", errors="ignore")

        text_result = str(result)
        return text_result[:2000]

    async def _search_sources(self, query: str, max_sources: int,
                            allowed_domains: Optional[List[str]] = None,
                            excluded_domains: Optional[List[str]] = None,
                            domain_priority: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        """Search for sources related to a query using DuckDuckGo"""

        logger.info(f"Searching for sources: {query}")

        resource_based_sources = await self._get_resource_based_sources(query, max_sources)

        if self._resource_manager:
            if resource_based_sources:
                logger.info(
                    "Using %s resource-backed sources for query '%s'",
                    len(resource_based_sources),
                    query,
                )
            else:
                logger.info(
                    "Resource manager configured but no matching resources found for query '%s'",
                    query,
                )
            return resource_based_sources

        logger.info(
            "Resource manager not configured; skipping external web search for query '%s'",
            query,
        )
        return []

    async def _fallback_mock_sources(self, query: str, max_sources: int) -> List[Dict[str, Any]]:
        """Fallback mock sources when DuckDuckGo search fails"""

        mock_sources = [
            {
                "title": f"Research Study on: {query[:50]}...",
                "url": f"https://example.com/research/{abs(hash(query)) % 1000}",
                "summary": f"This study examines {query.lower()} and provides comprehensive analysis of the topic.",
                "content": f"Detailed research content about {query}. This would contain the full text of the source in a real implementation.",
                "relevance_score": 0.85
            },
            {
                "title": f"Analysis Report: {query[:40]}...",
                "url": f"https://example.com/analysis/{abs(hash(query)) % 2000}",
                "summary": f"An analytical report covering various aspects of {query.lower()}.",
                "content": f"Comprehensive analysis content for {query}. Real implementation would scrape or retrieve actual content.",
                "relevance_score": 0.78
            },
            {
                "title": f"Expert Opinion on {query[:30]}...",
                "url": f"https://example.com/expert/{abs(hash(query)) % 3000}",
                "summary": f"Expert perspectives and opinions regarding {query.lower()}.",
                "content": f"Expert commentary and insights on {query}. Would contain real expert opinions in production.",
                "relevance_score": 0.72
            }
        ]

        return mock_sources[:max_sources]

    def _calculate_relevance_score(self, query: str, result: Dict[str, Any],
                                 domain_priority: Optional[Dict[str, float]] = None,
                                 url: Optional[str] = None) -> float:
        """Calculate relevance score for a search result"""

        try:
            # Extract text fields
            title = result.get('title', '').lower()
            body = result.get('body', '').lower()
            query_lower = query.lower()

            # Split query into keywords
            query_keywords = re.findall(r'\b\w+\b', query_lower)
            query_keywords = [kw for kw in query_keywords if len(kw) > 2]  # Filter short words

            if not query_keywords:
                return 0.5  # Default score if no meaningful keywords

            # Count keyword matches in title and body
            title_matches = sum(1 for kw in query_keywords if kw in title)
            body_matches = sum(1 for kw in query_keywords if kw in body)

            # Calculate weighted score (title matches worth more)
            title_weight = 0.7
            body_weight = 0.3

            title_score = (title_matches / len(query_keywords)) * title_weight
            body_score = (body_matches / len(query_keywords)) * body_weight

            total_score = title_score + body_score

            # Boost score for exact phrase matches
            if query_lower in title:
                total_score += 0.2
            elif query_lower in body:
                total_score += 0.1

            # Apply domain priority weight
            if domain_priority and url:
                domain_weight = self._get_domain_priority_weight(url, domain_priority)
                total_score *= domain_weight

            # Ensure score is between 0 and 1
            return min(max(total_score, 0.0), 1.0)

        except Exception as e:
            logger.warning(f"Error calculating relevance score: {e}")
            return 0.5

    async def _extract_content_preview(self, url: str) -> str:
        """Extract content preview from URL"""

        if not url or not self._is_valid_url(url):
            return "No content available"

        try:
            # Simple content extraction with timeout
            timeout = aiohttp.ClientTimeout(total=10)  # 10 second timeout

            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }

                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        html_content = await response.text()

                        # Basic text extraction (remove HTML tags)
                        text_content = re.sub(r'<[^>]+>', ' ', html_content)
                        text_content = re.sub(r'\s+', ' ', text_content).strip()

                        # Return first 500 characters as preview
                        return text_content[:500] + "..." if len(text_content) > 500 else text_content
                    else:
                        return f"Content not accessible (HTTP {response.status})"

        except asyncio.TimeoutError:
            logger.warning(f"Timeout extracting content from: {url}")
            return "Content extraction timed out"
        except Exception as e:
            logger.warning(f"Error extracting content from {url}: {e}")
            return "Content extraction failed"

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and accessible"""
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc and parsed.scheme in ['http', 'https'])
        except Exception:
            return False

    def _build_search_query(self, query: str, allowed_domains: Optional[List[str]] = None) -> str:
        """Build search query with domain restrictions if specified"""
        if not allowed_domains:
            return query

        # Add site: operators for allowed domains
        domain_queries = []
        for domain in allowed_domains:
            if domain:
                domain_queries.append(f"site:{domain}")

        if domain_queries:
            # Combine original query with domain restrictions
            domain_restriction = " OR ".join(domain_queries)
            return f"{query} ({domain_restriction})"

        return query

    def _is_domain_allowed(self, url: str, allowed_domains: Optional[List[str]] = None,
                          excluded_domains: Optional[List[str]] = None) -> bool:
        """Check if a URL's domain is allowed based on filtering rules"""
        if not url:
            return False

        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()

            # Remove 'www.' prefix if present
            if domain.startswith('www.'):
                domain = domain[4:]

            # Check excluded domains first (takes precedence)
            if excluded_domains:
                for excluded in excluded_domains:
                    if excluded.lower() in domain:
                        return False

            # If allowed domains specified, check if domain matches
            if allowed_domains:
                for allowed in allowed_domains:
                    allowed_lower = allowed.lower()
                    # Support both exact matches and TLD matches (e.g., "edu", "gov")
                    if (allowed_lower in domain or
                        domain.endswith(f'.{allowed_lower}') or
                        domain == allowed_lower):
                        return True
                return False  # Not in allowed list

            # If no restrictions, allow by default
            return True

        except Exception as e:
            logger.warning(f"Error checking domain for URL {url}: {e}")
            return False

    def _get_domain_priority_weight(self, url: str, domain_priority: Optional[Dict[str, float]] = None) -> float:
        """Get priority weight for a domain based on its type"""
        if not domain_priority or not url:
            return 1.0

        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()

            # Academic domains
            academic_domains = ['.edu', 'scholar.google', 'pubmed.ncbi.nlm.nih.gov', 'arxiv.org',
                              'researchgate.net', 'jstor.org', 'springer.com', 'sciencedirect.com']
            if any(academic in domain for academic in academic_domains):
                return domain_priority.get('academic', 1.0)

            # Government domains
            if '.gov' in domain:
                return domain_priority.get('government', 1.0)

            # Organization domains
            if '.org' in domain:
                return domain_priority.get('organization', 1.0)

            # News domains (simplified list)
            news_domains = ['reuters.com', 'bbc.com', 'cnn.com', 'nytimes.com', 'washingtonpost.com',
                           'theguardian.com', 'npr.org', 'apnews.com', 'bloomberg.com']
            if any(news in domain for news in news_domains):
                return domain_priority.get('news', 1.0)

            return 1.0  # Default weight

        except Exception:
            return 1.0

    async def _stage_summarization(self, session: ResearchSession, streaming: bool = False) -> str:
        """Stage 3: Summarization - Extract key information from sources"""

        logger.info("Starting summarization stage")

        session.current_stage = ResearchStage.SUMMARIZATION
        session.updated_at = time.time()

        # Emit streaming update - summarization started
        if streaming:
            update = self._create_streaming_update(session, "summarization", "started")
            self._emit_streaming_update(update)

        summaries = []

        for sub_question in session.sub_questions:
            # Create summary for each sub-question based on its sources
            sub_summary = self._summarize_sources_for_question(sub_question)
            session.summaries[sub_question.question_number] = sub_summary
            sub_question.summary = sub_summary
            sub_question.is_answered = len(sub_question.sources) > 0

            summaries.append(f"**Sub-question {sub_question.question_number}:** {sub_question.question}")
            summaries.append("")
            summaries.append("**Key Findings:**")
            summaries.append(sub_summary)
            summaries.append("")

        summary_result = "**Summarization Complete**\n\n" + "\n".join(summaries)
        summary_result += "\n**Next Stage:** Review - Will analyze coverage for gaps and missing information."

        # Emit streaming update - summarization completed
        if streaming:
            update = self._create_streaming_update(session, "summarization", "completed", summary_result)
            self._emit_streaming_update(update)

        logger.info(f"Completed summarization for {len(session.sub_questions)} sub-questions")
        return summary_result

    def _summarize_sources_for_question(self, sub_question: SubQuestion) -> str:
        """Create a summary of sources for a specific sub-question"""

        if not sub_question.sources:
            return "No sources found for this sub-question."

        # This is a simplified summarization approach
        # In production, this would use advanced NLP/LLM techniques

        summary_points = []

        for i, source in enumerate(sub_question.sources, 1):
            title = source.get("title", "Unknown Source")
            content_preview = source.get("summary", source.get("content", ""))[:200]

            summary_points.append(f"• **{title}**: {content_preview}...")

        return "\n".join(summary_points)

    async def _stage_review(self, session: ResearchSession, streaming: bool = False) -> str:
        """Stage 4: Review - Identify gaps and suggest additional research"""

        logger.info("Starting review stage")

        session.current_stage = ResearchStage.REVIEW
        session.updated_at = time.time()

        # Emit streaming update - review started
        if streaming:
            update = self._create_streaming_update(session, "review", "started")
            self._emit_streaming_update(update)

        # Analyze coverage and identify gaps
        gaps = self._identify_research_gaps(session)
        session.gaps_identified = gaps

        # Suggest additional questions if significant gaps found
        additional_questions = self._suggest_additional_questions(session)
        session.additional_questions = additional_questions

        review_result = ["**Review Complete**", ""]

        # Coverage analysis
        answered_questions = sum(1 for q in session.sub_questions if q.is_answered)
        total_questions = len(session.sub_questions)
        coverage_percentage = (answered_questions / total_questions * 100) if total_questions > 0 else 0

        review_result.append("**Coverage Analysis:**")
        review_result.append(f"- Sub-questions answered: {answered_questions}/{total_questions} ({coverage_percentage:.1f}%)")
        review_result.append(f"- Total sources found: {len(session.sources)}")
        review_result.append("")

        # Gaps identified
        if gaps:
            review_result.append("**Gaps Identified:**")
            for i, gap in enumerate(gaps, 1):
                review_result.append(f"{i}. {gap}")
            review_result.append("")

        # Additional questions suggested
        if additional_questions:
            review_result.append("**Additional Research Suggested:**")
            for i, question in enumerate(additional_questions, 1):
                review_result.append(f"{i}. {question}")
            review_result.append("")

        if not gaps and not additional_questions:
            review_result.append("**Assessment:** Research coverage appears comprehensive with no major gaps identified.")
            review_result.append("")

        review_result.append("**Next Stage:** Writing - Will synthesize findings into final research report.")

        final_review_result = "\n".join(review_result)

        # Emit streaming update - review completed
        if streaming:
            update = self._create_streaming_update(session, "review", "completed", final_review_result)
            self._emit_streaming_update(update)

        logger.info(f"Review complete - identified {len(gaps)} gaps and {len(additional_questions)} additional questions")
        return final_review_result

    def _identify_research_gaps(self, session: ResearchSession) -> List[str]:
        """Identify gaps in the current research"""

        gaps = []

        # Check for unanswered sub-questions
        unanswered = [q for q in session.sub_questions if not q.is_answered]
        if unanswered:
            gaps.append(f"Insufficient sources for {len(unanswered)} sub-questions")

        # Check for low source count
        avg_sources = sum(len(q.sources) for q in session.sub_questions) / len(session.sub_questions) if session.sub_questions else 0
        if avg_sources < 2:
            gaps.append("Low average source count per sub-question - may need more diverse sources")

        # Check for missing perspectives (simplified heuristic)
        main_question_lower = session.main_question.lower()

        if "impact" in main_question_lower or "effect" in main_question_lower:
            # Check if both positive and negative impacts are covered
            positive_coverage = any("positive" in q.question.lower() or "benefit" in q.question.lower()
                                  for q in session.sub_questions)
            negative_coverage = any("negative" in q.question.lower() or "risk" in q.question.lower() or "challenge" in q.question.lower()
                                  for q in session.sub_questions)

            if not positive_coverage:
                gaps.append("Missing analysis of positive impacts or benefits")
            if not negative_coverage:
                gaps.append("Missing analysis of negative impacts or challenges")

        if "economic" in main_question_lower or "financial" in main_question_lower:
            economic_coverage = any("economic" in q.question.lower() or "financial" in q.question.lower() or "cost" in q.question.lower()
                                  for q in session.sub_questions)
            if not economic_coverage:
                gaps.append("Missing economic or financial analysis")

        return gaps

    def _suggest_additional_questions(self, session: ResearchSession) -> List[str]:
        """Suggest additional research questions based on gaps"""

        additional_questions = []

        # Suggest questions based on identified gaps
        if session.gaps_identified:
            for gap in session.gaps_identified:
                if "positive impacts" in gap:
                    additional_questions.append(f"What are the positive impacts and benefits of {session.main_question}?")
                elif "negative impacts" in gap:
                    additional_questions.append(f"What are the risks and challenges associated with {session.main_question}?")
                elif "economic" in gap:
                    additional_questions.append(f"What are the economic implications and costs of {session.main_question}?")

        # Suggest methodological questions
        if not any("method" in q.question.lower() or "approach" in q.question.lower()
                  for q in session.sub_questions):
            additional_questions.append(f"What methodologies or approaches are used to study {session.main_question}?")

        # Suggest comparative questions
        if not any("compar" in q.question.lower() or "versus" in q.question.lower()
                  for q in session.sub_questions):
            additional_questions.append(f"How does {session.main_question} compare to alternative approaches or solutions?")

        return additional_questions[:3]  # Limit to top 3 suggestions

    async def _stage_writing(self, session: ResearchSession, streaming: bool = False) -> str:
        """Stage 5: Writing - Synthesize final research report"""

        logger.info("Starting writing stage")

        session.current_stage = ResearchStage.WRITING
        session.updated_at = time.time()

        # Emit streaming update - writing started
        if streaming:
            update = self._create_streaming_update(session, "writing", "started")
            self._emit_streaming_update(update)

        # Generate comprehensive final report
        final_report = self._generate_final_report(session)
        session.final_report = final_report
        session.completed = True
        session.current_stage = ResearchStage.COMPLETED

        # Emit streaming update - writing completed (final)
        if streaming:
            update = self._create_streaming_update(session, "writing", "completed", final_report, is_final=True)
            self._emit_streaming_update(update)

        logger.info("Final research report generated")
        return final_report

    def _generate_final_report(self, session: ResearchSession) -> str:
        """Generate the final comprehensive research report"""

        report = []

        # Title and introduction
        report.append(f"# Research Report: {session.main_question}")
        report.append("")
        report.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session.updated_at))}")
        report.append(f"**Session ID:** {session.session_id}")
        report.append("")

        # Executive summary
        report.append("## Executive Summary")
        report.append("")
        report.append(f"This research report addresses the question: *{session.main_question}*")
        report.append(f"The investigation was structured around {len(session.sub_questions)} key sub-questions, ")
        report.append(f"drawing from {len(session.sources)} sources to provide comprehensive coverage of the topic.")
        report.append("")

        # Methodology
        report.append("## Research Methodology")
        report.append("")
        report.append("This research followed a systematic 5-stage approach:")
        report.append("1. **Planning**: Breaking down the main question into focused sub-questions")
        report.append("2. **Source Finding**: Identifying relevant and credible sources for each sub-question")
        report.append("3. **Summarization**: Extracting key information from sources")
        report.append("4. **Review**: Analyzing coverage and identifying gaps")
        report.append("5. **Synthesis**: Compiling findings into this comprehensive report")
        report.append("")

        # Main findings organized by sub-question
        report.append("## Key Findings")
        report.append("")

        for i, sub_question in enumerate(session.sub_questions, 1):
            report.append(f"### {i}. {sub_question.question}")
            report.append("")

            if sub_question.summary:
                report.append(sub_question.summary)
            else:
                report.append("*No specific findings available for this sub-question.*")

            report.append("")

            # Add source citations for this sub-question
            if sub_question.sources:
                report.append("**Sources:**")
                for j, source in enumerate(sub_question.sources, 1):
                    title = source.get("title", "Unknown Title")
                    url = source.get("url", "No URL")
                    report.append(f"{j}. [{title}]({url})")
                report.append("")

        # Gaps and limitations
        if session.gaps_identified:
            report.append("## Research Gaps and Limitations")
            report.append("")
            for i, gap in enumerate(session.gaps_identified, 1):
                report.append(f"{i}. {gap}")
            report.append("")

        # Future research directions
        if session.additional_questions:
            report.append("## Suggested Future Research")
            report.append("")
            report.append("Based on this analysis, the following areas warrant additional investigation:")
            report.append("")
            for i, question in enumerate(session.additional_questions, 1):
                report.append(f"{i}. {question}")
            report.append("")

        # Conclusion
        report.append("## Conclusion")
        report.append("")
        answered_count = sum(1 for q in session.sub_questions if q.is_answered)
        total_count = len(session.sub_questions)

        report.append(f"This research successfully addressed {answered_count} of {total_count} sub-questions ")
        report.append(f"related to: *{session.main_question}*. ")

        if session.gaps_identified:
            report.append(f"The analysis identified {len(session.gaps_identified)} areas for potential ")
            report.append("further investigation, indicating opportunities for deeper research.")
        else:
            report.append("The research appears to provide comprehensive coverage of the topic area.")

        report.append("")
        report.append("---")
        report.append(f"*Report generated by Deep Research Tool - Session {session.session_id}*")

        return "\n".join(report)

    def _calculate_progress(self, session: ResearchSession) -> float:
        """Calculate research progress percentage"""

        stage_weights = {
            ResearchStage.PLANNING: 0.15,
            ResearchStage.SOURCE_FINDING: 0.25,
            ResearchStage.SUMMARIZATION: 0.25,
            ResearchStage.REVIEW: 0.15,
            ResearchStage.WRITING: 0.15,
            ResearchStage.COMPLETED: 0.05
        }

        completed_weight = 0.0

        # Add weight for completed stages
        if session.current_stage == ResearchStage.PLANNING:
            completed_weight = 0.0
        elif session.current_stage == ResearchStage.SOURCE_FINDING:
            completed_weight = stage_weights[ResearchStage.PLANNING]
        elif session.current_stage == ResearchStage.SUMMARIZATION:
            completed_weight = stage_weights[ResearchStage.PLANNING] + stage_weights[ResearchStage.SOURCE_FINDING]
        elif session.current_stage == ResearchStage.REVIEW:
            completed_weight = (stage_weights[ResearchStage.PLANNING] +
                              stage_weights[ResearchStage.SOURCE_FINDING] +
                              stage_weights[ResearchStage.SUMMARIZATION])
        elif session.current_stage == ResearchStage.WRITING:
            completed_weight = (stage_weights[ResearchStage.PLANNING] +
                              stage_weights[ResearchStage.SOURCE_FINDING] +
                              stage_weights[ResearchStage.SUMMARIZATION] +
                              stage_weights[ResearchStage.REVIEW])
        elif session.current_stage == ResearchStage.COMPLETED:
            completed_weight = 1.0

        return min(completed_weight * 100, 100.0)

    async def run(self, arguments: Dict[str, Any]) -> ToolResult:
        """
        Execute the deep research tool.
        
        Args:
            arguments: Tool arguments containing research parameters
            
        Returns:
            ToolResult: Research results with current stage output
        """
        try:
            # Extract parameters
            question = arguments.get("question", "").strip()
            if not question:
                raise ValueError("Research question is required")

            stage = arguments.get("stage", "auto")
            max_sources = arguments.get("max_sources_per_question", 3)
            search_enabled = arguments.get("search_enabled", True)
            user_id = arguments.get("user_id", "default")
            session_id = arguments.get("session_id")
            additional_context = arguments.get("additional_context")
            force_new_session = arguments.get("force_new_session", False)
            allowed_domains = arguments.get("allowed_domains")
            excluded_domains = arguments.get("excluded_domains")
            domain_priority = arguments.get("domain_priority")
            streaming = arguments.get("streaming", True)  # Default to streaming enabled

            # Get or create research session
            session = self._get_or_create_session(user_id, session_id, force_new_session)

            # Automatically start a fresh session for full auto runs when the previous session
            # is complete or targeted at a different question and the caller did not supply a session id.
            if (
                stage == "auto"
                and not session_id
                and not force_new_session
                and session
                and (
                    session.completed
                    or (session.main_question and session.main_question != question)
                )
            ):
                logger.info(
                    "Starting new research session for user '%s' to avoid reusing completed session %s",
                    user_id,
                    session.session_id,
                )
                session = self._get_or_create_session(user_id, None, True)

            # Store domain filtering settings in session
            if allowed_domains is not None:
                session.allowed_domains = allowed_domains
            if excluded_domains is not None:
                session.excluded_domains = excluded_domains
            if domain_priority is not None:
                session.domain_priority = domain_priority

            # Execute research stages
            if stage == "auto":
                # Execute all stages in sequence
                results = []

                # Stage 1: Planning
                if session.current_stage == ResearchStage.PLANNING or not session.sub_questions:
                    planning_result = await self._stage_planning(session, question, additional_context, streaming)
                    results.append(f"**STAGE 1 - PLANNING:**\n{planning_result}")

                # Stage 2: Source Finding
                if session.current_stage in [ResearchStage.PLANNING, ResearchStage.SOURCE_FINDING]:
                    source_result = await self._stage_source_finding(session, max_sources, search_enabled, streaming)
                    results.append(f"**STAGE 2 - SOURCE FINDING:**\n{source_result}")

                # Stage 3: Summarization
                if session.current_stage in [ResearchStage.PLANNING, ResearchStage.SOURCE_FINDING, ResearchStage.SUMMARIZATION]:
                    summary_result = await self._stage_summarization(session, streaming)
                    results.append(f"**STAGE 3 - SUMMARIZATION:**\n{summary_result}")

                # Stage 4: Review
                if session.current_stage in [ResearchStage.PLANNING, ResearchStage.SOURCE_FINDING,
                                           ResearchStage.SUMMARIZATION, ResearchStage.REVIEW]:
                    review_result = await self._stage_review(session, streaming)
                    results.append(f"**STAGE 4 - REVIEW:**\n{review_result}")

                # Stage 5: Writing
                writing_result = await self._stage_writing(session, streaming)
                results.append(f"**STAGE 5 - FINAL REPORT:**\n{writing_result}")

                current_stage_result = "\n\n".join(results)
                next_stage = None

            else:
                # Execute specific stage
                if stage == "planning":
                    current_stage_result = await self._stage_planning(session, question, additional_context, streaming)
                    next_stage = "source_finding"
                elif stage == "source_finding":
                    current_stage_result = await self._stage_source_finding(session, max_sources, search_enabled, streaming)
                    next_stage = "summarization"
                elif stage == "summarization":
                    current_stage_result = await self._stage_summarization(session, streaming)
                    next_stage = "review"
                elif stage == "review":
                    current_stage_result = await self._stage_review(session, streaming)
                    next_stage = "writing"
                elif stage == "writing":
                    current_stage_result = await self._stage_writing(session, streaming)
                    next_stage = None
                else:
                    raise ValueError(f"Invalid stage: {stage}")

            # Create response
            result = ResearchResult(
                stage=session.current_stage.value,
                session_id=session.session_id,
                main_question=session.main_question,
                sub_questions_count=len(session.sub_questions),
                sources_count=len(session.sources),
                current_stage_result=current_stage_result,
                next_stage=next_stage,
                progress_percentage=self._calculate_progress(session),
                is_completed=session.completed,
                final_report=session.final_report if session.completed else None,
                gaps_identified=session.gaps_identified,
                status="success",
                is_streaming=streaming,
                stream_complete=session.completed if streaming else False
            )

            # Format response
            response = {
                "stage": result.stage,
                "sessionId": result.session_id,
                "mainQuestion": result.main_question,
                "subQuestionsCount": result.sub_questions_count,
                "sourcesCount": result.sources_count,
                "currentStageResult": result.current_stage_result,
                "nextStage": result.next_stage,
                "progressPercentage": result.progress_percentage,
                "isCompleted": result.is_completed,
                "finalReport": result.final_report,
                "gapsIdentified": result.gaps_identified,
                "status": result.status,
                "isStreaming": result.is_streaming,
                "streamComplete": result.stream_complete
            }

            logger.info(f"Deep research executed - Stage: {result.stage}, Progress: {result.progress_percentage:.1f}%")

            return ToolResult(content=[TextContent(type="text", text=json.dumps(response, indent=2))])

        except ValueError as e:
            logger.error(f"Validation error in deep research: {e}")
            error_response = {
                "stage": "error",
                "sessionId": "",
                "mainQuestion": arguments.get("question", ""),
                "subQuestionsCount": 0,
                "sourcesCount": 0,
                "currentStageResult": f"Validation Error: {str(e)}",
                "nextStage": None,
                "progressPercentage": 0.0,
                "isCompleted": False,
                "finalReport": None,
                "gapsIdentified": [],
                "status": "validation_error",
                "error": str(e)
            }
            return ToolResult(content=[TextContent(type="text", text=json.dumps(error_response, indent=2))])

    async def run_streaming(self, arguments: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute research with streaming updates via async generator.
        
        This method provides real-time streaming of research progress through an async generator.
        Each yielded dict contains a streaming update with stage progress and results.
        
        Args:
            arguments: Tool arguments (same as run method)
            
        Yields:
            Dict[str, Any]: Streaming updates with stage progress and results
            
        Example:
            async for update in tool.run_streaming({"question": "AI impacts?", "stage": "auto"}):
                print(f"Stage: {update['stage']}, Status: {update['stageStatus']}")
                if update['isFinal']:
                    print("Research complete!")
        """

        # Store streaming updates for generator
        streaming_updates = []

        def capture_update(update: StreamingUpdate):
            """Capture streaming update for generator"""
            update_dict = {
                "stage": update.stage,
                "sessionId": update.session_id,
                "progressPercentage": update.progress_percentage,
                "stageStatus": update.stage_status,
                "stageResult": update.stage_result,
                "sourcesFound": update.sources_found,
                "subQuestionsProcessed": update.sub_questions_processed,
                "totalSubQuestions": update.total_sub_questions,
                "timestamp": update.timestamp,
                "isFinal": update.is_final
            }
            streaming_updates.append(update_dict)

        # Set up streaming callback
        self.set_streaming_callback(capture_update)

        try:
            # Force streaming mode
            arguments = arguments.copy()
            arguments["streaming"] = True

            # Execute research
            final_result = await self.run(arguments)
            # Ensure we have TextContent
            if final_result.content and isinstance(final_result.content[0], TextContent):
                final_response = json.loads(final_result.content[0].text)
            else:
                raise Exception("Invalid response format from research execution")

            # Yield all captured updates
            for update in streaming_updates:
                yield update

            # Yield final result
            final_update = {
                "stage": final_response["stage"],
                "sessionId": final_response["sessionId"],
                "progressPercentage": final_response["progressPercentage"],
                "stageStatus": "completed",
                "stageResult": final_response["currentStageResult"],
                "sourcesFound": final_response["sourcesCount"],
                "subQuestionsProcessed": final_response["subQuestionsCount"],
                "totalSubQuestions": final_response["subQuestionsCount"],
                "timestamp": time.time(),
                "isFinal": True,
                "finalReport": final_response.get("finalReport"),
                "isCompleted": final_response["isCompleted"]
            }
            yield final_update

        except Exception as e:
            logger.error(f"Unexpected error in streaming research: {e}")
            # Yield error update
            error_update = {
                "stage": "error",
                "sessionId": "",
                "progressPercentage": 0.0,
                "stageStatus": "failed",
                "stageResult": f"An unexpected error occurred: {str(e)}",
                "sourcesFound": 0,
                "subQuestionsProcessed": 0,
                "totalSubQuestions": 0,
                "timestamp": time.time(),
                "isFinal": True,
                "error": str(e)
            }
            yield error_update
        finally:
            # Clean up callback
            self._streaming_callback = None
