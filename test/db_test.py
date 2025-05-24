# tests/test_gateway_restart.py
import pytest
import logging

from mcp_gateway import MCPGateway
from mcp_gateway.member_servers.server_manager import ServerManager


###############################################################################
# Fake Cloudant – implements only what ServerManager uses
###############################################################################
class _Response:
    def __init__(self, result):
        self._result = result
    def get_result(self):
        return self._result


class FakeCloudantV1:
    def __init__(self):
        self._dbs: dict[str, dict[str, dict]] = {}

    # ---------- convenience ----------
    def reset(self):
        self._dbs.clear()

    # ---------- meta ----------
    def get_all_dbs(self):
        return _Response(list(self._dbs))
    def put_database(self, db_name):
        self._dbs.setdefault(db_name, {})
        return _Response({"ok": True})

    # ---------- CRUD ----------
    def get_document(self, db, doc_id):
        try:
            return _Response(self._dbs[db][doc_id])
        except KeyError:
            raise Exception("doc_not_found")

    def post_document(self, db, document):
        # if we get an IBM `Document` object, convert it
        if not isinstance(document, dict):
            document = getattr(document, "to_dict", lambda: vars(document))()
        self._dbs.setdefault(db, {})[document["id"]] = document
        return _Response({"ok": True})

    def delete_document(self, db, doc_id, rev=None):
        self._dbs[db].pop(doc_id, None)
        return _Response({"ok": True})

    # ---------- queries ----------
    def post_find(self, db, selector):
        sid = selector["id"]["$eq"]
        doc = self._dbs.get(db, {}).get(sid)
        return _Response({"docs": [doc] if doc else []})

    def post_all_docs(self, db, include_docs=True):
        rows = [{"doc": d.copy()} for d in self._dbs.get(db, {}).values()]
        return _Response({"rows": rows})


###############################################################################
# Autouse fixture that **guarantees** every test sees the fake DB
###############################################################################
@pytest.fixture(autouse=True)
def fake_cloudant(monkeypatch):
    """
    1. Builds a fresh FakeCloudantV1 for *this* test.
    2. Zeros out any previously cached real client.
    3. Monkey‑patches ServerManager so it returns our fake.
    4. After the test, clears state so nothing leaks.
    """
    fake = FakeCloudantV1()

    # 1️⃣ blow away a Cloudant client that might already be cached
    ServerManager._cloudant_client = None

    # 2️⃣ patch the factory so *future* calls get the fake
    monkeypatch.setattr(
        ServerManager,
        "_cloudant",
        classmethod(lambda cls: fake),
        raising=True,
    )

    yield fake          # << test runs here, sharing the fake DB

    # 3️⃣ reset for the next test
    fake.reset()

###############################################################################
# 3. Your original test logic (unchanged)
###############################################################################
@pytest.mark.asyncio
async def test_gateway_restart_persists_and_restores_server(caplog):
    """
    1. Register a server with config (first run)
    2. Simulate gateway restart (load from fake DB)
    3. Ensure the server and tool are still available
    """
    caplog.set_level(logging.DEBUG)
    logger = logging.getLogger(__name__)

    server_id = "mcp-server-fetch"
    config = [{
        "id": server_id,
        "type": "sse",
        "endpoint": "https://dummy.endpoint/sse"  # A dummy endpoint is fine
    }]

    # -------- First run --------
    gateway_1 = MCPGateway("gateway", config=config)
    await gateway_1.setup_member_servers()
    tools_1 = await gateway_1.get_tools()
    logger.debug("[First run] Tools: %s", tools_1)
    assert any(server_id in t for t in tools_1), \
        "Server tools not available after registration"

    # -------- Simulate restart --------
    gateway_2 = MCPGateway("gateway")
    await gateway_2.setup_member_servers()
    tools_2 = await gateway_2.get_tools()
    logger.debug("[After restart] Tools: %s", tools_2)
    assert any(server_id in t for t in tools_2), \
        "Server tool not found after restart"

@pytest.mark.asyncio
async def test_duplicate_registration_skips_duplicate(fake_cloudant, caplog):
    server_id = "duplicate-server"
    config = [{
        "id": server_id,
        "type": "sse",
        "endpoint": "http://dummy/endpoint"
    }]

    caplog.set_level(logging.INFO)
    gateway = MCPGateway("gateway", config=config)
    await gateway.setup_member_servers()

    # Register again with same config
    await gateway.setup_member_servers()

    db = fake_cloudant._dbs["mcp_servers"]
    assert len(db) == 1, "Duplicate registration should not add a second entry"
    assert server_id in db

@pytest.mark.asyncio
async def test_corrupt_entry_does_not_crash_gateway(fake_cloudant):
    db = fake_cloudant._dbs.setdefault("mcp_servers", {})
    db["corrupt-entry"] = {"type": "sse", "endpoint": "http://bad"}

    gateway = MCPGateway("gateway")
    # Should not raise error even though one entry is invalid
    await gateway.setup_member_servers()

    tools = await gateway.get_tools()
    assert isinstance(tools, dict), "Gateway should recover from bad DB entries"

@pytest.mark.asyncio
async def test_empty_database_loads_no_servers():
    gateway = MCPGateway("gateway")
    await gateway.setup_member_servers()
    mounted_servers = gateway.list_member_servers()
    assert mounted_servers == [], "Gateway should start cleanly with empty DB"
