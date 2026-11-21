import asyncio
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from dashboard_access import DashboardAccess
from dashboard_events import DashboardEvents
from google_sheet_manager import GoogleSheetManager
from obsidian_rag import ObsidianRAGEngine
from telegram_agent import consume_run_now, mark_run_now


class AccessTests(unittest.TestCase):
    def client(self, password=None, address="127.0.0.1"):
        async def endpoint(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/", endpoint, methods=["GET", "POST"])])
        app.add_middleware(DashboardAccess, password=password)
        return TestClient(app, base_url="http://localhost", client=(address, 50000))

    def test_local_only_and_same_origin(self):
        local = self.client()
        self.assertEqual(local.get("/").status_code, 200)
        self.assertEqual(self.client(address="192.0.2.1").get("/").status_code, 403)
        self.assertEqual(local.get("/", headers={"Host": "dashboard.example"}).status_code, 403)
        self.assertEqual(local.post("/", json={}, headers={"Origin": "https://elsewhere.example"}).status_code, 403)
        self.assertEqual(local.post("/", json={}, headers={"Origin": "http://localhost"}).status_code, 200)

    def test_operator_authentication(self):
        remote = self.client(password="test-password", address="192.0.2.1")
        self.assertEqual(remote.get("/").status_code, 401)
        self.assertEqual(remote.get("/", auth=("admin", "test-password")).status_code, 200)


class EventTests(unittest.IsolatedAsyncioTestCase):
    async def test_many_viewers_share_polls_and_status_serialization(self):
        state = [0, 0]
        snapshot = Mock(side_effect=lambda: tuple(state))
        status = Mock(return_value={"is_running": True})
        feed = DashboardEvents(snapshot, status, interval=0.03)
        streams = [feed.stream() for _ in range(100)]
        reads = asyncio.gather(*(anext(stream) for stream in streams))
        try:
            async with asyncio.timeout(5):
                while not snapshot.called:
                    await asyncio.sleep(0.005)
                state[:] = [1, 1]
                results = await reads
                self.assertTrue(all('"status_update"' in result for result in results))
                graphs = await asyncio.gather(*(anext(stream) for stream in streams))
                self.assertTrue(all('"brain_graph_update"' in result for result in graphs))
                status.assert_called_once()
                self.assertLess(snapshot.call_count, len(streams))
        finally:
            await asyncio.gather(*(stream.aclose() for stream in streams))
        self.assertIsNone(feed.task)


class StorageTests(unittest.TestCase):
    def test_one_pending_signal_and_one_consumer(self):
        with tempfile.TemporaryDirectory() as tmp, patch("telegram_agent.STATE_DIR", tmp), \
                patch("telegram_agent.RUN_NOW_FILE", os.path.join(tmp, "run_now.request")), ThreadPoolExecutor(8) as pool:
            self.assertEqual(sum(pool.map(lambda _: mark_run_now(), range(32))), 1)
            self.assertEqual(sum(pool.map(lambda _: consume_run_now(), range(32))), 1)

    def test_service_account_drive_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            creds = Path(tmp, "service.json")
            creds.touch()
            manager = GoogleSheetManager.__new__(GoogleSheetManager)
            manager.credentials_path = str(creds)
            with patch("google_sheet_manager.ServiceCredentials.from_service_account_file") as auth, \
                    patch("googleapiclient.discovery.build") as build:
                self.assertIs(manager._get_drive_service(), build.return_value)
                auth.assert_called_once_with(str(creds), scopes=[
                    "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive",
                ])
                build.assert_called_once_with("drive", "v3", credentials=auth.return_value)

    def test_cache_reuse_and_legacy_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp, patch("obsidian_rag._EMBEDDING_MODEL", None):
            vault, db = Path(tmp, "vault"), Path(tmp, "db")
            vault.mkdir()
            db.mkdir()
            (db / "index.pkl").write_bytes(b"unused legacy file")
            (vault / "note.md").write_text("first", encoding="utf-8")
            embeddings = Mock()
            embeddings.embed_documents.return_value = [[0.0, 1.0]]
            embeddings.embed_query.return_value = [0.0, 1.0]

            def query(rebuild=False):
                rag = ObsidianRAGEngine(str(vault), str(db))
                rag.embeddings = embeddings
                if rebuild:
                    self.assertTrue(rag.build_or_update_db())
                return rag.retrieve_context("question")

            self.assertIn("first", query())
            self.assertIn("first", query())
            embeddings.embed_documents.assert_called_once()
            (vault / "note.md").write_text("second", encoding="utf-8")
            self.assertIn("first", query())
            embeddings.embed_documents.assert_called_once()
            self.assertIn("second", query(rebuild=True))
            self.assertEqual(embeddings.embed_documents.call_count, 2)
