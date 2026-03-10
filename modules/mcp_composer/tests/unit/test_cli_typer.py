import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer

from mcp_composer.core.cli import cli_typer


@pytest.fixture
def sample_results():
    return {
        "servers": {"total": 2, "registered": ["a"], "failed": []},
        "tools": {"total": 1, "registered": [], "failed": ["bad_tool"]},
    }


def _fake_asyncio_run(coro):
    if hasattr(coro, "close"):
        coro.close()
    return None


def test_validate_middleware_command_success():
    with patch("mcp_composer.core.utils.middleware_cli.cmd_validate", return_value=0):
        with pytest.raises(SystemExit) as exc:
            cli_typer.validate_middleware("config.json")
        assert exc.value.code == 0


def test_list_middlewares_command_success():
    with patch("mcp_composer.core.utils.middleware_cli.cmd_list", return_value=0):
        with pytest.raises(SystemExit) as exc:
            cli_typer.list_middlewares("config.json")
        assert exc.value.code == 0


def test_add_middleware_command_success():
    with patch(
        "mcp_composer.core.utils.middleware_cli.cmd_add_middleware", return_value=0
    ):
        with pytest.raises(SystemExit) as exc:
            cli_typer.add_middleware(
                config="config.json",
                name="mw",
                kind="pkg.Class",
            )
        assert exc.value.code == 0


def test_run_composer_invalid_mode():
    with pytest.raises(typer.BadParameter):
        cli_typer.run_composer(mode="invalid")


def test_run_composer_invalid_env_format():
    with pytest.raises(typer.BadParameter):
        cli_typer.run_composer(mode="http", endpoint="http://x", env=["BADENV"])


def test_run_composer_happy_path(monkeypatch):
    called = {}

    monkeypatch.setattr(cli_typer.asyncio, "run", _fake_asyncio_run)
    monkeypatch.setattr(
        cli_typer,
        "build_config_from_args",
        lambda mode, endpoint, script_path, directory, id: [{"id": id, "type": mode}],
    )

    async def _fake_run_dynamic_composer(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(cli_typer, "run_dynamic_composer", _fake_run_dynamic_composer)

    cli_typer.run_composer(mode="http", endpoint="http://x", id="abc")
    assert called == {}


def test_version_and_info_commands(monkeypatch):
    messages = []
    monkeypatch.setattr(
        cli_typer.typer, "echo", lambda message="", **_: messages.append(str(message))
    )

    cli_typer.version()
    cli_typer.info()

    assert any("MCP Composer version" in message for message in messages)
    assert any("Available commands:" in message for message in messages)


def test_init_command_delegates(monkeypatch):
    init_mock = MagicMock()
    monkeypatch.setattr(cli_typer.init_commands, "init_project", init_mock)

    cli_typer.init_command(project_name="demo", defaults=True)
    init_mock.assert_called_once()


def test_main_callback_version_branch():
    with pytest.raises(typer.Exit) as exc:
        cli_typer.main_callback(ctx=MagicMock(), version=True)
    assert exc.value.exit_code == 0


def test_main_callback_config_apply_branch(monkeypatch):
    called = {}
    monkeypatch.setattr(
        cli_typer,
        "_apply_config_and_start_server",
        lambda *args, **kwargs: called.update({"ok": True}),
    )

    cli_typer.main_callback(
        ctx=MagicMock(),
        config="servers",
        mode="http",
        configfilepath="cfg.json",
    )
    assert called.get("ok") is True


def test_main_callback_config_only_branch(monkeypatch):
    called = {}
    monkeypatch.setattr(
        cli_typer,
        "_handle_unified_config_commands",
        lambda *args, **kwargs: called.update({"ok": True}),
    )

    cli_typer.main_callback(ctx=MagicMock(), config="show", configfilepath="cfg.json")
    assert called.get("ok") is True


def test_main_callback_timeout_validation(monkeypatch):
    with pytest.raises(typer.Exit) as exc:
        cli_typer.main_callback(ctx=MagicMock(), mode="http", timeout=0)
    assert exc.value.exit_code == 1


def test_main_callback_run_server_path(monkeypatch):
    monkeypatch.setattr(cli_typer.asyncio, "run", _fake_asyncio_run)
    monkeypatch.setattr(
        cli_typer,
        "build_config_from_args",
        lambda *args, **kwargs: [{"id": "mcp-local", "type": "http"}],
    )

    async def _fake_run_dynamic_composer(**kwargs):
        return None

    monkeypatch.setattr(cli_typer, "run_dynamic_composer", _fake_run_dynamic_composer)

    cli_typer.main_callback(ctx=MagicMock(), mode="http", endpoint="http://x")


def test_build_config_from_args_all_modes():
    http_cfg = cli_typer.build_config_from_args("http", endpoint="http://x", id="id1")
    assert http_cfg[0]["type"] == "http"

    sse_cfg = cli_typer.build_config_from_args("sse", endpoint="http://x/sse", id="id2")
    assert sse_cfg[0]["type"] == "sse"

    stdio_cfg = cli_typer.build_config_from_args(
        "stdio", script_path="/tmp/a.py", id="id3"
    )
    assert stdio_cfg[0]["type"] == "stdio"


def test_build_config_from_args_invalid_mode_and_missing_script():
    with pytest.raises(typer.BadParameter):
        cli_typer.build_config_from_args("unknown")

    with pytest.raises(typer.BadParameter):
        cli_typer.build_config_from_args("stdio")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,method",
    [
        ("stdio", "run_stdio_async"),
        ("sse", "run_sse_async"),
        ("http", "run_http_async"),
    ],
)
async def test_start_server_modes(mode, method):
    composer = MagicMock()
    composer.setup_member_servers = AsyncMock()
    composer.run_stdio_async = AsyncMock()
    composer.run_sse_async = AsyncMock()
    composer.run_http_async = AsyncMock()

    await cli_typer._start_server(composer, mode, "0.0.0.0", 9000, "debug")

    composer.setup_member_servers.assert_awaited_once()
    getattr(composer, method).assert_awaited_once()


@pytest.mark.asyncio
async def test_start_server_invalid_mode():
    composer = MagicMock()
    composer.setup_member_servers = AsyncMock()
    with pytest.raises(ValueError):
        await cli_typer._start_server(composer, "bad", "0.0.0.0", 9000, "debug")


def test_apply_config_and_start_server_dry_run(monkeypatch):
    called = {}
    monkeypatch.setattr(
        cli_typer, "_show_dry_run", lambda *args, **kwargs: called.update({"dry": True})
    )

    cli_typer._apply_config_and_start_server(
        config="all",
        configfilepath="cfg.json",
        config_format=None,
        dry_run=True,
        mode="http",
        id="x",
        endpoint=None,
        config_path=None,
        directory=None,
        script_path=None,
        host=None,
        port=None,
        auth_type=None,
        auth_provider="oidc",
        sse_url=None,
        disable_composer_tools=False,
        disable_composer_tools_specific=None,
        pass_environment=False,
        remote_auth_type=None,
        client_auth_type=None,
        env=None,
        log_level=None,
        timeout=None,
    )

    assert called.get("dry") is True


def test_apply_config_and_start_server_full_flow(monkeypatch, sample_results):
    fake_cm = MagicMock()
    fake_cm.loader = MagicMock()
    fake_cm.loader.composer = None
    fake_cm.load_and_apply = AsyncMock(return_value=sample_results)

    monkeypatch.setattr(cli_typer, "ConfigManager", lambda: fake_cm)
    monkeypatch.setattr(
        cli_typer, "_create_composer_instance", lambda *args, **kwargs: MagicMock()
    )
    monkeypatch.setattr(
        cli_typer, "_display_apply_results", lambda *args, **kwargs: None
    )

    async def _fake_start(*args, **kwargs):
        return None

    monkeypatch.setattr(cli_typer, "_start_server", _fake_start)

    run_calls = {"count": 0}

    def _run_and_close(coro):
        run_calls["count"] += 1
        if hasattr(coro, "close"):
            coro.close()
        return None

    monkeypatch.setattr(cli_typer.asyncio, "run", _run_and_close)

    cli_typer._apply_config_and_start_server(
        config="servers",
        configfilepath="cfg.json",
        config_format=None,
        dry_run=False,
        mode="http",
        id="x",
        endpoint="http://x",
        config_path=None,
        directory=None,
        script_path=None,
        host="0.0.0.0",
        port=9000,
        auth_type=None,
        auth_provider="oidc",
        sse_url=None,
        disable_composer_tools=False,
        disable_composer_tools_specific=None,
        pass_environment=False,
        remote_auth_type=None,
        client_auth_type=None,
        env=None,
        log_level="debug",
        timeout=None,
    )

    assert run_calls["count"] >= 2


def test_create_composer_instance_non_oauth(monkeypatch):
    composer = MagicMock()
    composer.list_tools = AsyncMock(return_value={"a": object()})
    monkeypatch.setattr(cli_typer, "MCPComposer", MagicMock(return_value=composer))

    created = cli_typer._create_composer_instance(
        mode="http",
        id="x",
        endpoint="http://x",
        config_path=None,
        directory=None,
        script_path=None,
        host=None,
        port=None,
        auth_type=None,
        auth_provider="oidc",
        sse_url=None,
        disable_composer_tools=True,
        disable_composer_tools_specific=None,
        pass_environment=False,
        remote_auth_type=None,
        client_auth_type=None,
        env=None,
        log_level=None,
        timeout=None,
    )

    assert created is composer


def test_build_config_from_args_private_function():
    cfg = cli_typer._build_config_from_args("http", "id1", "http://x", None, None)
    assert cfg[0]["type"] == "http"

    with pytest.raises(ValueError):
        cli_typer._build_config_from_args("stdio", "id2", None, None, None)

    with pytest.raises(ValueError):
        cli_typer._build_config_from_args("bad", "id3", None, None, None)


def test_handle_error_raises_exit(monkeypatch):
    out = []
    monkeypatch.setattr(
        cli_typer.typer, "echo", lambda msg="", **kwargs: out.append(msg)
    )
    with pytest.raises(typer.Exit):
        cli_typer._handle_error("boom", "try this")
    assert any("boom" in str(item) for item in out)


def test_handle_validate_and_show_commands(monkeypatch):
    cm = MagicMock()
    cm.validate_config_file.return_value = True
    cm.loader = MagicMock()
    cm.loader.detect_config_type.return_value = "all"
    cm.loader.load_from_file.return_value = SimpleNamespace(
        model_dump=lambda: {"servers": []}
    )

    monkeypatch.setattr(cli_typer, "_show_all_sections", lambda cfg: None)
    cli_typer._handle_validate_command(cm, "cfg.json")
    cli_typer._handle_show_command(cm, "cfg.json")


def test_handle_apply_command(monkeypatch, sample_results):
    cm = MagicMock()
    cm.load_and_apply = AsyncMock(return_value=sample_results)
    monkeypatch.setattr(cli_typer.asyncio, "run", _fake_asyncio_run)
    monkeypatch.setattr(cli_typer, "_display_apply_results", lambda *_: None)
    cli_typer._handle_apply_command(cm, "all", "cfg.json", dry_run=False)


def test_handle_unified_config_commands_routes(monkeypatch):
    cm = MagicMock()
    monkeypatch.setattr(cli_typer, "ConfigManager", lambda: cm)

    called = {"validate": 0, "show": 0, "apply": 0}
    monkeypatch.setattr(
        cli_typer,
        "_handle_validate_command",
        lambda *args, **kwargs: called.__setitem__("validate", 1),
    )
    monkeypatch.setattr(
        cli_typer,
        "_handle_show_command",
        lambda *args, **kwargs: called.__setitem__("show", 1),
    )
    monkeypatch.setattr(
        cli_typer,
        "_handle_apply_command",
        lambda *args, **kwargs: called.__setitem__("apply", 1),
    )

    cli_typer._handle_unified_config_commands("validate", "cfg.json", None, False)
    cli_typer._handle_unified_config_commands("show", "cfg.json", None, False)
    cli_typer._handle_unified_config_commands("all", "cfg.json", None, False)

    assert called == {"validate": 1, "show": 1, "apply": 1}


def test_show_table_helpers(monkeypatch):
    printed = {"count": 0}

    class DummyConsole:
        def print(self, *_args, **_kwargs):
            printed["count"] += 1

    monkeypatch.setattr("rich.console.Console", DummyConsole)

    cli_typer._show_servers_table(
        [{"id": "a", "type": "http", "endpoint": "e", "label": "L"}]
    )
    cli_typer._show_middleware_table(
        [{"name": "mw", "kind": "k", "mode": "enabled", "priority": 1}]
    )
    cli_typer._show_prompts_table(
        [{"name": "p", "description": "d", "template": "t", "arguments": []}]
    )
    cli_typer._show_tools_table({"tool": {"openapi": "3.0", "paths": {"/x": {}}}})

    assert printed["count"] == 4


def test_show_all_sections(monkeypatch):
    calls = {"servers": 0, "middleware": 0, "prompts": 0, "tools": 0}

    monkeypatch.setattr(
        cli_typer,
        "_show_servers_table",
        lambda *args, **kwargs: calls.__setitem__("servers", 1),
    )
    monkeypatch.setattr(
        cli_typer,
        "_show_middleware_table",
        lambda *args, **kwargs: calls.__setitem__("middleware", 1),
    )
    monkeypatch.setattr(
        cli_typer,
        "_show_prompts_table",
        lambda *args, **kwargs: calls.__setitem__("prompts", 1),
    )
    monkeypatch.setattr(
        cli_typer,
        "_show_tools_table",
        lambda *args, **kwargs: calls.__setitem__("tools", 1),
    )

    cli_typer._show_all_sections(
        {
            "servers": [{"id": "s"}],
            "middleware": [{"name": "m"}],
            "prompts": [{"name": "p"}],
            "tools": {"t": {}},
        }
    )

    assert calls == {"servers": 1, "middleware": 1, "prompts": 1, "tools": 1}


def test_show_dry_run_and_display_results(monkeypatch, sample_results):
    cfg_obj = SimpleNamespace(
        servers=[SimpleNamespace(id="s1", type="http")],
        middleware=[SimpleNamespace(name="m1", kind="k")],
        prompts=[SimpleNamespace(name="p1")],
        tools={"t1": {}},
    )
    cm = MagicMock()
    cm.loader = MagicMock()
    cm.loader.load_from_file.return_value = cfg_obj
    monkeypatch.setattr(cli_typer, "ConfigManager", lambda: cm)

    cli_typer._show_dry_run("cfg.json", None, "all")
    cli_typer._display_apply_results(sample_results)


def test_main_preprocess_env(monkeypatch):
    argv = ["mcp-composer", "--env", "KEY", "VALUE", "run"]
    monkeypatch.setattr(cli_typer.sys, "argv", argv)
    app_mock = MagicMock()
    monkeypatch.setattr(cli_typer, "app", app_mock)

    cli_typer.main()

    assert "KEY=VALUE" in cli_typer.sys.argv
    app_mock.assert_called_once()


@pytest.mark.asyncio
async def test_run_dynamic_composer_basic_modes(monkeypatch):
    composer = MagicMock()
    composer.list_tools = AsyncMock(return_value=[])
    composer.setup_member_servers = AsyncMock()
    composer.run_stdio_async = AsyncMock()
    composer.run_sse_async = AsyncMock()
    composer.run_http_async = AsyncMock()
    composer.import_server = AsyncMock()

    monkeypatch.setattr(cli_typer, "MCPComposer", MagicMock(return_value=composer))

    await cli_typer.run_dynamic_composer(mode="stdio", config=[])
    composer.run_stdio_async.assert_awaited_once()

    composer.run_stdio_async.reset_mock()
    await cli_typer.run_dynamic_composer(mode="sse", config=[])
    composer.run_sse_async.assert_awaited_once()

    composer.run_sse_async.reset_mock()
    await cli_typer.run_dynamic_composer(mode="http", config=[])
    composer.run_http_async.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_dynamic_composer_invalid_mode():
    composer = MagicMock()
    composer.list_tools = AsyncMock(return_value=[])
    composer.setup_member_servers = AsyncMock()
    with patch("mcp_composer.core.cli.cli_typer.MCPComposer", return_value=composer):
        with pytest.raises(typer.Exit):
            await cli_typer.run_dynamic_composer(mode="bad", config=[])
