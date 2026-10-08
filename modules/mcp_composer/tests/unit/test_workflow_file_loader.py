"""Tests for workflow JSON file loading and catalog conversion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp_composer.core.catalog.catalog_manager import CatalogResourceListFilter
from mcp_composer.core.catalog.workflow_manager import WorkflowManager
from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.core.workflow_file_loader import (
    build_execution_plan,
    build_workflow_execution_guidance,
    file_entry_to_workflow_json,
    load_workflow_entries_from_directory,
    parse_workflow_file_entries,
    parse_workflows_from_json_string,
    prefixed_tool_name,
    resolve_tool_prefix,
    slug_from_instruction,
    sync_workflow_files_to_catalog,
)
from mcp_composer.store.catalog_in_memory_database import CatalogInMemoryDatabase


def test_slug_from_instruction_strips_product_tag():
    slug = slug_from_instruction("[scanner] List all open issues across data stores")
    assert slug.startswith("list-all-open")
    assert "[" not in slug


def test_resolve_tool_prefix_step_override():
    assert (
        resolve_tool_prefix(
            "scanner",
            entry_prefixes={"scanner": "scanner"},
            step_prefix="custom-srv",
        )
        == "custom-srv"
    )


def test_prefixed_tool_name():
    assert prefixed_tool_name("scanner", "list_issues") == ("scanner_list_issues")


def test_file_entry_to_workflow_json():
    entry = {
        "name": "list-open-issues",
        "instruction": "List open issues",
        "prefixes": {"scanner": "scanner"},
        "output": [
            {
                "step": 1,
                "product": "scanner",
                "tool": "list_issues",
                "input": {"filter": {"status": "OPEN"}},
            }
        ],
    }
    wf = file_entry_to_workflow_json(entry, source_file="test.json", used_names=set())
    assert wf.name == "list-open-issues"
    assert wf.description == "List open issues"
    assert wf.steps[0].toolname == "scanner"
    plan = build_execution_plan(wf)
    assert plan["steps"][0]["mcp_tool_name"] == "scanner_list_issues"
    assert plan["steps"][0]["layered_make_tool_call"] == "scanner_make_tool_call"
    assert plan["execution_guidance"]["pattern"] == "discover_plan_execute_sequentially"


def test_build_workflow_execution_guidance_structure():
    guide = build_workflow_execution_guidance()
    assert guide["pattern"] == "discover_plan_execute_sequentially"
    assert len(guide["phases"]) >= 4
    assert any(p["id"] == "layered" for p in guide["invocation_patterns"])


def test_parse_workflows_from_json_string_accepts_bundle_array():
    raw = json.dumps(
        [
            {
                "name": "wf-a",
                "instruction": "Do A",
                "output": [
                    {
                        "step": 1,
                        "product": "scanner",
                        "tool": "list_issues",
                        "input": {},
                    }
                ],
            },
            {
                "name": "wf-b",
                "instruction": "Do B",
                "output": [
                    {
                        "step": 1,
                        "product": "scanner",
                        "tool": "get_asset_list",
                        "input": {},
                    }
                ],
            },
        ]
    )
    workflows = parse_workflows_from_json_string(raw)
    assert len(workflows) == 2
    assert workflows[0].name == "wf-a"
    assert workflows[1].name == "wf-b"


def test_parse_workflows_from_json_string_accepts_single_catalog_document():
    raw = json.dumps(
        {
            "name": "wf-single",
            "description": "Single workflow",
            "version": "1.0.0",
            "goal": "Single workflow",
            "steps": [
                {
                    "step": 1,
                    "toolname": "scanner",
                    "tool": "list_issues",
                    "input": {},
                }
            ],
        }
    )
    workflows = parse_workflows_from_json_string(raw)
    assert len(workflows) == 1
    assert workflows[0].name == "wf-single"


def test_parse_workflow_file_entries_bundle_array():
    entries = parse_workflow_file_entries(
        [{"name": "a", "instruction": "A"}, {"name": "b", "instruction": "B"}],
        source_file="workflows_easy.json",
    )
    assert len(entries) == 2


def test_parse_workflow_file_entries_single_object():
    entries = parse_workflow_file_entries(
        {"name": "wf", "instruction": "Do it", "output": []},
        source_file="workflows_test.json",
    )
    assert entries[0]["name"] == "wf"


@pytest.mark.asyncio
async def test_sync_writes_one_catalog_row_per_file(tmp_path: Path):
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    (workflows_dir / "workflows_test.json").write_text(
        json.dumps(
            [
                {
                    "name": "wf-alpha",
                    "instruction": "Run wf-alpha",
                    "output": [
                        {
                            "step": 1,
                            "product": "scanner",
                            "tool": "list_issues",
                            "input": {},
                        }
                    ],
                },
                {
                    "name": "wf-beta",
                    "instruction": "Run wf-beta",
                    "output": [
                        {
                            "step": 1,
                            "product": "scanner",
                            "tool": "list_issues",
                            "input": {},
                        }
                    ],
                },
            ]
        ),
        encoding="utf-8",
    )
    db = CatalogInMemoryDatabase()
    mgr = WorkflowManager(db)
    result = await sync_workflow_files_to_catalog(workflows_dir, workflow_manager=mgr)
    assert result["published_count"] == 2
    assert len(result["published"]) == 2
    listed = await mgr.list(
        CatalogResourceListFilter(
            kind=RegistryResourceKind.WORKFLOW,
            is_latest_only=True,
            status_filter="active",
            start=0,
            limit=50,
        )
    )
    assert len(listed.workflows) == 2


@pytest.mark.asyncio
async def test_sync_workflow_files_to_catalog(tmp_path: Path):
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    (workflows_dir / "workflows_one.json").write_text(
        json.dumps(
            {
                "name": "wf-one",
                "instruction": "Do one thing",
                "output": [
                    {
                        "step": 1,
                        "product": "scanner",
                        "tool": "list_issues",
                        "input": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    db = CatalogInMemoryDatabase()
    mgr = WorkflowManager(db)
    result = await sync_workflow_files_to_catalog(workflows_dir, workflow_manager=mgr)
    assert result["published_count"] == 1
    assert result["one_row_per_workflow"] is True
    assert result["published"][0]["name"] == "wf-one"
    latest = await mgr.get_latest("wf-one")
    assert latest.workflow.steps[0].toolname == "scanner"


def test_load_workflow_entries_from_directory():
    """Load shipped workflow fixtures from tests/data/workflows (CI-safe)."""
    workflows_dir = Path(__file__).resolve().parent / "../data/workflows"
    entries = load_workflow_entries_from_directory(workflows_dir)

    assert len(entries) == 3
    assert {workflow.name for _, workflow, _ in entries} == {
        "wf-alpha",
        "wf-beta",
        "wf-single",
    }
    assert {source for source, _, _ in entries} == {
        "workflows_bundle.json",
        "workflows_single.json",
    }
