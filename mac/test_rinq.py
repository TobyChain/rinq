from __future__ import annotations

import io
import os
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr
from pathlib import Path

os.environ["RINQ_HOME"] = tempfile.mkdtemp(prefix="rinq-test-")
# Isolate collector tests from the user's real credentials/network.
os.environ["RINQ_CCSWITCH_DB"] = os.path.join(os.environ["RINQ_HOME"], "no-ccswitch.db")
os.environ["RINQ_CODEX_AUTH"] = os.path.join(os.environ["RINQ_HOME"], "no-auth.json")
os.environ["ZCODE_HOME"] = os.path.join(os.environ["RINQ_HOME"], "no-zcode")
os.environ["PI_CODING_AGENT_DIR"] = os.path.join(os.environ["RINQ_HOME"], "no-omp")

from rinq import collectors, events, focus, integrations, sources, state as state_mod  # noqa: E402
from rinq import usage
from rinq.server import Handler, ThreadingHTTPServer  # noqa: E402


class EventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = {"push": {}}

    def test_lifecycle_counts(self) -> None:
        s = state_mod.blank_state()
        events.apply_event(s, {"state": "started", "title": "t1"}, self.cfg)
        events.apply_event(s, {"state": "waiting", "title": "t1"}, self.cfg)
        events.apply_event(s, {"state": "completed", "title": "t1"}, self.cfg)
        a = s["agents"]
        self.assertEqual(a["running"], 0)
        self.assertEqual(a["waiting"], 0)
        self.assertEqual(a["doneToday"], 1)
        self.assertEqual(a["failedToday"], 0)

    def test_failed_counts_and_clears_waiting(self) -> None:
        s = state_mod.blank_state()
        events.apply_event(s, {"state": "started", "title": "t"}, self.cfg)
        events.apply_event(s, {"state": "failed", "title": "t"}, self.cfg)
        self.assertEqual(s["agents"]["running"], 0)
        self.assertEqual(s["agents"]["failedToday"], 1)

    def test_invalid_state(self) -> None:
        s = state_mod.blank_state()
        with self.assertRaises(ValueError):
            events.apply_event(s, {"state": "nope", "title": "x"}, self.cfg)

    def test_focus_countdown(self) -> None:
        s = state_mod.blank_state()
        focus.start_focus(s)
        cfg = {"focus": {"breakEveryMins": 50}}
        f = focus.current_focus(s, cfg)
        self.assertEqual(f["mode"], "focus")
        self.assertLessEqual(f["remainingMins"], 50)

    def test_clamp(self) -> None:
        self.assertEqual(state_mod.clamp_pct(140), 100)
        self.assertEqual(state_mod.clamp_pct(-5), 0)
        self.assertIsNone(state_mod.clamp_pct(None))

    def test_codex_hook_accepts_thread_id(self) -> None:
        from rinq import cli

        recorded = {}
        original_post = cli._post
        cli._post = lambda _path, payload: recorded.update(payload) or {"ok": True}
        try:
            args = type("Args", (), {"payload": json.dumps({
                "type": "agent-turn-complete",
                "thread-id": "codex-thread-1",
                "cwd": "/tmp/codex-thread",
            })})()
            self.assertEqual(cli.cmd_hook_codex(args), 0)
        finally:
            cli._post = original_post

        self.assertEqual(recorded["sessionId"], "codex:codex-thread-1")
        self.assertEqual(recorded["cwd"], "/tmp/codex-thread")


class CollectorTests(unittest.TestCase):
    def test_no_key_returns_no_rings(self) -> None:
        os.environ.pop("DEEPSEEK_API_KEY", None)
        self.assertEqual(collectors._deepseek({"balanceFull": {"deepseek": 20.0}}), [])
        self.assertEqual(collectors._minimax({}), [])
        self.assertEqual(collectors._codex({}), [])

    def test_unconfigured_collectors_are_hidden_and_sorted(self) -> None:
        # No credentials in the test env -> real collectors emit nothing.
        cfg = {"collectors": ["codex", "minimax", "deepseek"], "ringOrder": ["deepseek-balance"]}
        rings = collectors.collect(cfg)
        self.assertEqual(rings, [])

    def test_cancelled_vendor_is_not_collected_even_with_a_credential(self) -> None:
        from rinq import settings_api
        cfg = {"collectors": ["anthropic"], "keys": {"anthropic": "test-key"},
               "trackingOff": ["anthropic"]}
        self.assertEqual(collectors.collect(cfg), [])
        original = integrations.discover_integrations
        integrations.discover_integrations = lambda: []
        try:
            vendor = next(v for v in settings_api.public_settings(cfg)["vendors"]
                          if v["id"] == "anthropic")
        finally:
            integrations.discover_integrations = original
        # The credential is still reported so the UI can offer "Resume".
        self.assertTrue(vendor["hasCredential"])
        self.assertFalse(vendor["tracking"])
        self.assertNotIn("test-key", json.dumps(vendor))

    def test_cancel_flag_only_affects_the_named_vendor(self) -> None:
        cfg = {"collectors": [], "keys": {"anthropic": "test-key", "xiaomi": "test-key"},
               "trackingOff": ["anthropic"], "ringOrder": []}
        self.assertEqual([r["id"] for r in collectors.collect(cfg)], ["xiaomi-status"])

    def test_mock_rings_respect_the_cancel_flag(self) -> None:
        cfg = {"collectors": ["mock"], "trackingOff": ["deepseek"]}
        ids = [r["id"] for r in collectors.collect(cfg)]
        self.assertNotIn("deepseek-balance", ids)
        self.assertIn("openai-api", ids)

    def test_legacy_enabled_provider_without_credential_stays_hidden(self) -> None:
        cfg = {"collectors": ["anthropic"], "enabled": {"anthropic": True}, "ringOrder": []}
        rings = collectors.collect(cfg)
        self.assertEqual(rings, [])

    def test_cancel_and_resume_patch_write_only_the_cancellation(self) -> None:
        from rinq import settings_api
        cfg = {"keys": {}, "trackingOff": [], "ringOrder": []}
        settings_api.apply_public_settings(cfg, {"tracking": {"jina": False}})
        self.assertEqual(cfg["trackingOff"], ["jina"])
        settings_api.apply_public_settings(cfg, {"tracking": {"jina": True}})
        self.assertEqual(cfg["trackingOff"], [])

    def test_saving_a_key_resumes_cancelled_tracking(self) -> None:
        from rinq import settings_api
        cfg = {"keys": {}, "trackingOff": ["jina"], "ringOrder": []}
        settings_api.apply_public_settings(cfg, {"keys": {"jina": "new-key"}})
        self.assertEqual(cfg["keys"], {"jina": "new-key"})
        self.assertEqual(cfg["trackingOff"], [])

    def test_retired_enabled_map_does_not_cancel_tracking(self) -> None:
        # Older builds wrote enabled: {vendor: false} for the removed toggle;
        # those values must stay inert instead of silently hiding a vendor.
        cfg = {"collectors": ["anthropic"], "keys": {"anthropic": "test-key"},
               "enabled": {"anthropic": False}, "ringOrder": []}
        self.assertEqual([r["id"] for r in collectors.collect(cfg)], ["anthropic-status"])

    def test_credentialed_provider_with_failed_quota_has_unavailable_status(self) -> None:
        cfg = {
            "collectors": ["zhipu"],
            "keys": {"zhipu": "test-key"}, "ringOrder": [],
        }
        original = collectors._get_json
        collectors._get_json = lambda *_args, **_kwargs: None
        try:
            rings = collectors.collect(cfg)
        finally:
            collectors._get_json = original
        self.assertEqual([ring["id"] for ring in rings], ["zhipu-status"])
        self.assertEqual(rings[0]["status"], "quota_unavailable")

    def test_collector_exception_is_isolated_and_logged(self) -> None:
        # One provider raising must not fail the whole status build: the
        # remaining providers still report, the failed one degrades to its
        # unavailable status ring, and the cause lands on stderr.
        def boom(_cfg: dict) -> list:
            raise RuntimeError("provider exploded")

        cfg = {
            "collectors": ["deepseek", "mock"],
            "keys": {"deepseek": "test-key"},
            "ringOrder": [],
        }
        sentinel = collectors._COLLECTORS.get("deepseek")
        collectors._COLLECTORS["deepseek"] = boom
        try:
            buf = io.StringIO()
            with redirect_stderr(buf):
                rings = collectors.collect(cfg)
        finally:
            if sentinel is None:
                collectors._COLLECTORS.pop("deepseek", None)
            else:
                collectors._COLLECTORS["deepseek"] = sentinel
        ids = [ring["id"] for ring in rings]
        self.assertIn("deepseek-status", ids)
        self.assertEqual(
            rings[ids.index("deepseek-status")]["status"], "quota_unavailable"
        )
        self.assertIn("codex-5h", ids)  # a mock demo ring survived the failure
        out = buf.getvalue()
        self.assertIn("collector deepseek failed", out)
        self.assertIn("RuntimeError", out)

    def test_failed_fetch_logs_cause_without_key_material(self) -> None:
        # A long-lived daemon once lost its outbound network after sleep/wake
        # and showed "quota unavailable" for hours with nothing in the logs;
        # fetch failures must log the URL and exception class (never the key).
        buf = io.StringIO()
        with redirect_stderr(buf):
            data = collectors._get_json(
                "http://127.0.0.1:1/none?api_key=query-secret-must-not-leak",
                "secret-key-that-must-not-leak"
            )
        self.assertIsNone(data)
        out = buf.getvalue()
        self.assertIn("collector fetch failed", out)
        self.assertIn("127.0.0.1:1", out)
        self.assertNotIn("secret-key-that-must-not-leak", out)
        self.assertNotIn("query-secret-must-not-leak", out)

    def test_credential_adds_provider_missing_from_legacy_collector_list(self) -> None:
        cfg = {"collectors": ["codex"], "keys": {"anthropic": "test-key"}, "ringOrder": []}
        rings = collectors.collect(cfg)
        self.assertIn("anthropic-status", [ring["id"] for ring in rings])

    def test_ring_order_applied(self) -> None:
        cfg = {"collectors": ["mock"], "ringOrder": ["openai-api", "codex-5h"]}
        ids = [r["id"] for r in collectors.collect(cfg)]
        self.assertEqual(ids[:2], ["openai-api", "codex-5h"])

    def test_balance_percent_from_reference(self) -> None:
        cfg = {"balanceFull": {"deepseek": 10.0}}
        ring = collectors._balance_ring(
            cfg, vid="deepseek", label="DeepSeek", accent="teal",
            remaining=6.6, currency="CNY",
        )
        self.assertEqual(ring["remainingPercent"], 66)
        self.assertEqual(ring["usedPercent"], 34)
        self.assertEqual(ring["remaining"], 6.6)
        self.assertEqual(ring["usedValue"], 3.4)
        self.assertEqual(ring["totalValue"], 10.0)
        self.assertEqual(ring["valueUnit"], "CNY")

    def test_balance_no_reference_shows_unknown_pct(self) -> None:
        ring = collectors._balance_ring(
            {}, vid="moonshot", label="Kimi", accent="purple",
            remaining=22.5, currency="CNY",
        )
        self.assertIsNone(ring["remainingPercent"])
        self.assertEqual(ring["remaining"], 22.5)

    def test_mock_includes_balance_ring(self) -> None:
        rings = collectors.collect({"collectors": ["mock"]})
        ids = [r["id"] for r in rings]
        self.assertIn("deepseek-balance", ids)
        for ring in rings:
            if ring.get("usedValue") is None or ring.get("totalValue") is None:
                continue
            expected = state_mod.clamp_pct(ring["usedValue"] / ring["totalValue"] * 100)
            self.assertEqual(ring["usedPercent"], expected, ring["id"])

    def test_collect_dispatch_unknown_name_ignored(self) -> None:
        self.assertEqual(collectors.collect({"collectors": ["nope"]}), [])

    def test_sources_missing_ccswitch_db(self) -> None:
        self.assertIsNone(sources.ccswitch_provider_key(app_type="codex", name="MiniMax"))

    def test_sources_missing_codex_auth(self) -> None:
        token, account = sources.codex_chatgpt_token()
        self.assertIsNone(token)
        self.assertIsNone(account)

    def test_codex_no_login_returns_no_rings(self) -> None:
        self.assertEqual(collectors._codex({}), [])

    def test_minimax_no_key_returns_no_rings(self) -> None:
        os.environ.pop("MINIMAX_API_KEY", None)
        self.assertEqual(collectors._minimax({}), [])

    def test_minimax_parses_window_and_week_percent(self) -> None:
        data = {
            "model_remains": [
                {
                    "model_name": "general",
                    "end_time": 1788868800000,
                    "current_interval_remaining_percent": 100,
                    "weekly_end_time": 1789315200000,
                    "current_weekly_remaining_percent": 87,
                }
            ]
        }
        rings = {r["id"]: r for r in collectors._minimax_rings(data)}
        self.assertEqual(rings["minimax-5h"]["usedPercent"], 0)
        self.assertEqual(rings["minimax-5h"]["resetsAt"], 1788868800)
        self.assertEqual(rings["minimax-week"]["usedPercent"], 13)
        self.assertEqual(rings["minimax-week"]["resetsAt"], 1789315200)
        self.assertEqual(rings["minimax-week"]["usedValue"], 13)
        self.assertEqual(rings["minimax-week"]["totalValue"], 100)

    def test_codex_parses_rate_limit_windows(self) -> None:
        data = {
            "rate_limit": {
                "primary_window": {"used_percent": 1, "reset_at": 1000, "limit_window_seconds": 18000},
                "secondary_window": {"used_percent": 0, "reset_at": 2000, "limit_window_seconds": 604800},
            }
        }
        rings = {r["id"]: r for r in collectors._codex_rings(data)}
        self.assertEqual(rings["codex-5h"]["usedPercent"], 1)
        self.assertEqual(rings["codex-5h"]["windowMins"], 300)
        self.assertEqual(rings["codex-5h"]["usedValue"], 1)
        self.assertEqual(rings["codex-5h"]["totalValue"], 100)
        self.assertEqual(rings["codex-week"]["usedPercent"], 0)
        self.assertEqual(rings["codex-week"]["windowMins"], 10080)

    def test_zhipu_parses_credit_limit_windows(self) -> None:
        # GLM coding-plan keys return rolling CREDIT_LIMIT windows, not a balance.
        data = {"data": {"level": "max", "limits": [
            {"type": "CREDIT_LIMIT", "unit": 3, "number": 5, "usage": 28000,
             "remaining": 27499, "nextResetTime": 1789755038034},
            {"type": "CREDIT_LIMIT", "unit": 6, "number": 1, "usage": 140000,
             "remaining": 139499, "nextResetTime": 1790340034980},
        ]}}
        cfg = {"keys": {"zhipu": "id.secret"}}
        original = collectors._get_json
        collectors._get_json = lambda *_a, **_k: data
        try:
            rings = {r["id"]: r for r in collectors._zhipu(cfg)}
        finally:
            collectors._get_json = original
        self.assertIn("zhipu-5h", rings)
        self.assertIn("zhipu-week", rings)
        self.assertEqual(rings["zhipu-5h"]["kind"], "window")
        self.assertEqual(rings["zhipu-5h"]["usedValue"], 501)
        self.assertEqual(rings["zhipu-5h"]["totalValue"], 28000)
        self.assertEqual(rings["zhipu-5h"]["usedPercent"], 2)
        self.assertEqual(rings["zhipu-5h"]["windowMins"], 300)
        self.assertEqual(rings["zhipu-5h"]["resetsAt"], 1789755038)
        self.assertEqual(rings["zhipu-week"]["windowMins"], 10080)
        self.assertEqual(rings["zhipu-week"]["usedValue"], 501)
        self.assertEqual(rings["zhipu-week"]["totalValue"], 140000)

    def test_zhipu_falls_back_to_balance_when_no_windows(self) -> None:
        # A pay-as-you-go key returns a prepaid balance; render as a balance ring.
        data = {"data": {"balance": 42.5}}
        cfg = {"keys": {"zhipu": "id.secret"}, "balanceFull": {"zhipu": 100.0}}
        original = collectors._get_json
        collectors._get_json = lambda *_a, **_k: data
        try:
            rings = collectors._zhipu(cfg)
        finally:
            collectors._get_json = original
        self.assertEqual(rings[0]["id"], "zhipu-balance")
        self.assertEqual(rings[0]["remaining"], 42.5)

    def test_minimax_falls_back_to_first_model_without_general(self) -> None:
        data = {"model_remains": [{
            "model_name": "abab6.5", "end_time": 1788868800000,
            "current_interval_remaining_percent": 40,
            "weekly_end_time": 1789315200000,
            "current_weekly_remaining_percent": 90,
        }]}
        rings = {r["id"]: r for r in collectors._minimax_rings(data)}
        self.assertEqual(rings["minimax-5h"]["usedPercent"], 60)
        self.assertEqual(rings["minimax-week"]["usedPercent"], 10)

    def test_jina_parses_wallet_token_balance(self) -> None:
        data = {"wallet": {"total_balance": 8_200_000, "total_amount": 10_000_000}}
        cfg = {"keys": {"jina": "jina_test_key"}}
        original = collectors._get_json
        captured = {}
        def fake(url, key, *a, **k):
            captured["url"] = url
            return data
        collectors._get_json = fake
        try:
            rings = collectors._jina(cfg)
        finally:
            collectors._get_json = original
        self.assertEqual(rings[0]["id"], "jina-balance")
        self.assertEqual(rings[0]["remaining"], 8_200_000)
        self.assertEqual(rings[0]["usedValue"], 1_800_000)
        self.assertEqual(rings[0]["totalValue"], 10_000_000)
        self.assertEqual(rings[0]["usedPercent"], 18)
        self.assertEqual(rings[0]["valueUnit"], "tokens")
        # Default host is the .cn mirror and the key rides in the query string.
        self.assertIn("embeddings-dashboard-api.jinaai.cn", captured["url"])
        self.assertIn("api_key=jina_test_key", captured["url"])

    def test_jina_host_is_overridable(self) -> None:
        cfg = {"keys": {"jina": "k"}, "hosts": {"jina": "embeddings-dashboard-api.jina.ai"}}
        original = collectors._get_json
        captured = {}
        collectors._get_json = lambda url, *a, **k: (captured.__setitem__("url", url), {"wallet": {"total_balance": 1}})[1]
        try:
            collectors._jina(cfg)
        finally:
            collectors._get_json = original
        self.assertIn("embeddings-dashboard-api.jina.ai", captured["url"])

    def test_jina_no_key_returns_no_rings(self) -> None:
        os.environ.pop("JINA_API_KEY", None)
        self.assertEqual(collectors._jina({}), [])

    def test_unsupported_vendor_shows_not_supported_status(self) -> None:
        # anthropic/xiaomi have no live-quota route; a key must not claim
        # "quota unavailable" (which implies a transient failure).
        cfg = {
            "collectors": ["xiaomi"],
            "keys": {"xiaomi": "test-key"}, "ringOrder": [],
        }
        rings = collectors.collect(cfg)
        self.assertEqual([r["id"] for r in rings], ["xiaomi-status"])
        self.assertEqual(rings[0]["status"], "quota_unsupported")

class IntegrationTests(unittest.TestCase):
    def test_undetected_integrations_are_hidden(self) -> None:
        home = Path(tempfile.mkdtemp(prefix="rinq-no-integrations-"))
        app_root = Path(tempfile.mkdtemp(prefix="rinq-no-apps-"))
        self.assertEqual(
            integrations.discover_integrations(home=home, app_dirs=(app_root,), process_text=""),
            [],
        )

    def test_zcode_metadata_is_discovered_without_reading_credentials(self) -> None:
        home = Path(tempfile.mkdtemp(prefix="rinq-zcode-"))
        root = home / ".zcode" / "v2"
        root.mkdir(parents=True)
        (root / "setting.json").write_text(json.dumps({
            "modelProviderFamilyModes": {"zai": "oauth"},
            "modelProviderFamilySelectedKeys": {"zai": "coding-plan:builtin:zai-start-plan"},
        }))
        (root / "coding-plan-cache.json").write_text(json.dumps({
            "entryStatus": {"items": {"plan": {"status": "available"}}}
        }))
        (root / "credentials.json").write_text("encrypted-secret-must-not-be-read")
        app_root = Path(tempfile.mkdtemp(prefix="rinq-apps-"))
        app = app_root / "ZCode.app" / "Contents"
        app.mkdir(parents=True)
        (app / "Info.plist").write_bytes(__import__("plistlib").dumps({
            "CFBundleIdentifier": "dev.zcode.app",
            "CFBundleShortVersionString": "test",
        }))
        result = integrations.discover_integrations(
            home=home, app_dirs=(app_root,), process_text="ZCode Helper"
        )
        zcode = next(item for item in result if item["id"] == "zcode")
        self.assertTrue(zcode["installed"])
        self.assertTrue(zcode["configured"])
        self.assertTrue(zcode["running"])
        self.assertEqual(zcode["authState"], "connected")
        self.assertEqual(zcode["authMethod"], "oauth")
        self.assertEqual(zcode["planState"], "available")
        self.assertNotIn("credentials", json.dumps(zcode))


class ConfigEndpointTests(unittest.TestCase):
    def test_usage_endpoint_returns_contract(self) -> None:
        previous = {
            name: os.environ.get(name)
            for name in ("CODEX_HOME", "TRAE_HOME", "TRAECLI_HOME", "CLAUDE_CONFIG_DIR", "ZCODE_HOME")
        }
        previous_db_path = usage.USAGE_DB_PATH
        isolated_root = tempfile.mkdtemp(prefix="rinq-usage-http-")
        usage.USAGE_DB_PATH = Path(isolated_root) / "usage.sqlite3"
        for name in previous:
            os.environ[name] = os.path.join(isolated_root, name.lower())
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_address[1]}/usage", timeout=5
            ) as response:
                body = json.loads(response.read().decode())
                self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))
                self.assertEqual(response.headers.get("Cache-Control"), "no-store")
            self.assertEqual(response.status, 200)
            self.assertEqual(body["version"], 1)
            self.assertIn("today", body)
            self.assertIn("week", body)
            self.assertIn("daily", body)
            self.assertIn("apps", body)
            self.assertIn("sources", body)
        finally:
            server.shutdown()
            server.server_close()
            usage.USAGE_DB_PATH = previous_db_path
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_local_config_update_is_allowed(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            data = b'{"ringOrder":["codex-week","codex-5h"]}'
            req = urllib.request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/config",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2) as response:
                self.assertEqual(response.status, 200)
        finally:
            server.shutdown()
            server.server_close()

    def test_remote_config_update_is_rejected(self) -> None:
        handler = object.__new__(Handler)
        handler.client_address = ("192.0.2.10", 12345)
        handler.path = "/config"
        handler.headers = {"Content-Length": "2"}
        handler.rfile = type("Reader", (), {"read": lambda self, _: b"{}"})()
        response = {}
        handler._send_json = lambda code, body: response.update(code=code, body=body)

        handler.do_POST()

        self.assertEqual(response["code"], 403)
        self.assertEqual(response["body"]["error"], "config changes are local-only")

    def test_build_status_does_not_overwrite_event_during_slow_collect(self) -> None:
        from rinq import server as server_mod

        started = threading.Event()
        release = threading.Event()
        event_done = threading.Event()
        original_collect = server_mod.collect
        original_build_sessions = server_mod.build_sessions
        state_mod.update_state(lambda state: state.clear() or state.update(state_mod.blank_state()))
        server_mod.invalidate_sessions_cache()

        def slow_collect(_cfg: dict) -> list[dict]:
            started.set()
            self.assertTrue(release.wait(2))
            return []

        server_mod.collect = slow_collect
        server_mod.build_sessions = lambda state=None: {
            "version": 1,
            "updatedAt": 0,
            "sessions": [],
            "counts": {"running": 0, "subagentsRunning": 0, "waiting": 0},
        }
        try:
            worker = threading.Thread(target=server_mod.build_status, daemon=True)
            worker.start()
            self.assertTrue(started.wait(1))

            def apply_close() -> None:
                state_mod.update_state(lambda state: events.apply_event(state, {
                    "state": "closed", "title": "session closed",
                    "sessionId": "claude:slow", "app": "Claude Code",
                }, {"push": {}}))
                event_done.set()

            closer = threading.Thread(target=apply_close, daemon=True)
            closer.start()
            self.assertTrue(event_done.wait(1))
            release.set()
            worker.join(2)
            closer.join(2)
        finally:
            server_mod.collect = original_collect
            server_mod.build_sessions = original_build_sessions

        saved = state_mod.load_state()
        self.assertIn("claude:slow", saved["closedSessions"])


class UsageTests(unittest.TestCase):
    def test_discovers_omp_sessions_from_agent_dir(self) -> None:
        agent_dir = tempfile.mkdtemp(prefix="rinq-omp-agent-")
        sessions = os.path.join(agent_dir, "sessions")
        os.makedirs(sessions)
        previous = os.environ.get("PI_CODING_AGENT_DIR")
        os.environ["PI_CODING_AGENT_DIR"] = agent_dir
        try:
            sources_found = usage.discover_sources()
        finally:
            if previous is None:
                os.environ.pop("PI_CODING_AGENT_DIR", None)
            else:
                os.environ["PI_CODING_AGENT_DIR"] = previous

        self.assertIn(usage.UsageSource("omp", Path(sessions)), sources_found)

    def test_omp_assistant_usage_shape(self) -> None:
        line = json.dumps({
            "type": "message",
            "id": "assistant-1",
            "timestamp": "2026-09-16T01:00:00Z",
            "message": {
                "role": "assistant",
                "provider": "minimax-code-cn",
                "model": "MiniMax-M3",
                "timestamp": 1789520399123,
                "content": [{"type": "text", "text": "token_count is ordinary text"}],
                "usage": {
                    "input": 120, "output": 30, "cacheRead": 80,
                    "cacheWrite": 4, "reasoningTokens": 5, "totalTokens": 239,
                },
            },
        }).encode()
        event = usage._token_event(
            "omp", line, "OMP", None, None, __import__("datetime").timezone.utc
        )

        self.assertIsNotNone(event)
        self.assertEqual(event[0], 1789520399)
        self.assertEqual(event[2:5], ("OMP", "minimax-code-cn", "MiniMax-M3"))
        self.assertEqual(event[5:10], (120, 30, 80, 4, 5))
        self.assertEqual(event[10], "omp:assistant-1:2026-09-16T01:00:00Z")

    def test_pi_assistant_usage_shape(self) -> None:
        line = json.dumps({
            "type": "message",
            "id": "pi-1",
            "timestamp": "2026-10-19T01:00:00Z",
            "message": {
                "role": "assistant",
                "provider": "pi-cn",
                "model": "Pi Max",
                "usage": {
                    "inputTokens": 55,
                    "outputTokens": 21,
                    "cacheReadTokens": 13,
                    "cacheWriteTokens": 2,
                    "reasoningTokens": 3,
                },
            },
        }).encode()
        event = usage._token_event(
            "pi", line, "Pi", None, None, __import__("datetime").timezone.utc
        )

        self.assertIsNotNone(event)
        self.assertEqual(event[0], 1792371600)
        self.assertEqual(event[2:5], ("Pi", "pi-cn", "Pi Max"))
        self.assertEqual(event[5:10], (55, 21, 13, 2, 3))
        self.assertEqual(event[10], "pi:pi-1:2026-10-19T01:00:00Z")

    def test_omp_ignores_non_assistant_and_unidentified_messages(self) -> None:
        base = {
            "type": "message", "timestamp": "2026-09-16T01:00:00Z",
            "message": {"provider": "devin", "model": "swe-2", "usage": {"input": 10}},
        }
        user = {**base, "id": "user-1", "message": {**base["message"], "role": "user"}}
        assistant_without_id = {**base, "message": {**base["message"], "role": "assistant"}}

        for row in (user, assistant_without_id):
            event = usage._token_event(
                "omp", json.dumps(row).encode(), "OMP", None, None,
                __import__("datetime").timezone.utc,
            )
            self.assertIsNone(event)

    def test_omp_forked_messages_are_counted_once(self) -> None:
        agent_dir = tempfile.mkdtemp(prefix="rinq-omp-fork-")
        sessions = os.path.join(agent_dir, "sessions", "project")
        os.makedirs(os.path.join(sessions, "child"))
        shared = {
            "type": "message", "id": "shared-assistant",
            "timestamp": "2026-09-16T01:00:00Z",
            "message": {
                "role": "assistant", "provider": "devin", "model": "swe-2",
                "usage": {"input": 100, "output": 20, "cacheRead": 50, "cacheWrite": 0},
                "content": [{"type": "text", "text": "must never be retained"}],
            },
        }
        unique = {
            "type": "message", "id": "child-assistant",
            "timestamp": "2026-09-16T01:01:00Z",
            "message": {
                "role": "assistant", "provider": "devin", "model": "swe-2",
                "usage": {"input": 40, "output": 10, "cacheRead": 25, "cacheWrite": 2},
            },
        }
        for path, rows in (
            (os.path.join(sessions, "parent.jsonl"), [shared]),
            (os.path.join(sessions, "child", "worker.jsonl"), [shared, unique]),
        ):
            with open(path, "w", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row) + "\n")

        previous = {name: os.environ.get(name) for name in (
            "CODEX_HOME", "TRAECLI_HOME", "CLAUDE_CONFIG_DIR", "ZCODE_HOME",
            "PI_CODING_AGENT_DIR",
        )}
        test_home = tempfile.mkdtemp(prefix="rinq-omp-db-")
        previous_db_path = usage.USAGE_DB_PATH
        for name in ("CODEX_HOME", "TRAECLI_HOME", "CLAUDE_CONFIG_DIR", "ZCODE_HOME"):
            os.environ[name] = os.path.join(test_home, f"missing-{name.lower()}")
        os.environ["PI_CODING_AGENT_DIR"] = agent_dir
        usage.USAGE_DB_PATH = Path(test_home) / "usage.sqlite3"
        try:
            from datetime import datetime, timezone
            now = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)
            first = usage.build_usage_summary(now)
            second = usage.build_usage_summary(now)
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            usage.USAGE_DB_PATH = previous_db_path

        self.assertEqual(first["today"]["inputTokens"], 140)
        self.assertEqual(first["today"]["outputTokens"], 30)
        self.assertEqual(first["today"]["cachedInputTokens"], 75)
        self.assertEqual(first["today"]["requests"], 2)
        self.assertEqual(first["apps"][0]["app"], "OMP")
        self.assertEqual(second["today"], first["today"])
        self.assertEqual(first["sources"], [{"adapter": "omp", "available": True}])

        with sqlite3.connect(os.path.join(test_home, "usage.sqlite3")) as db:
            columns = [row[1] for row in db.execute("PRAGMA table_info(usage_events)")]
            self.assertNotIn("content", columns)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0], 3)

    def test_usage_schema_adds_event_key_to_existing_index(self) -> None:
        db = sqlite3.connect(":memory:")
        db.executescript(
            """
            CREATE TABLE usage_events (
                path TEXT NOT NULL, byte_offset INTEGER NOT NULL, occurred_at INTEGER NOT NULL,
                local_date TEXT NOT NULL, app TEXT NOT NULL, provider TEXT, model TEXT,
                input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
                cached_input_tokens INTEGER NOT NULL, cache_write_input_tokens INTEGER NOT NULL,
                reasoning_output_tokens INTEGER NOT NULL, PRIMARY KEY (path, byte_offset)
            );
            INSERT INTO usage_events VALUES (
                'old.jsonl', 0, 1789520400, '2026-09-16', 'TraeX', 'trae', 'model',
                10, 2, 0, 0, 0
            );
            """
        )

        usage._ensure_schema(db)

        columns = [row[1] for row in db.execute("PRAGMA table_info(usage_events)")]
        self.assertIn("event_key", columns)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0], 1)

    def test_claude_code_usage_shape(self) -> None:
        line = json.dumps({
            "type": "assistant",
            "timestamp": "2026-09-09T01:00:00Z",
            "message": {
                "model": "claude-sonnet",
                "usage": {
                    "input_tokens": 90,
                    "output_tokens": 15,
                    "cache_read_input_tokens": 30,
                    "cache_creation_input_tokens": 4,
                },
            },
        }).encode()
        event = usage._token_event(
            "claude_code", line, "Claude Code", "anthropic", None, __import__("datetime").timezone.utc
        )
        self.assertIsNotNone(event)
        self.assertEqual(event[5:10], (90, 15, 30, 4, 0))

    def test_zcode_usage_shape(self) -> None:
        line = json.dumps({
            "event": "model.sdk.stream.completed",
            "timestamp": "2026-09-09T01:00:00Z",
            "context": {
                "providerId": "builtin:zai-start-plan",
                "modelId": "GLM-5.3",
                "usage": {
                    "inputTokens": "120", "outputTokens": "30",
                    "cacheReadTokens": "80", "cacheWriteTokens": "4",
                    "reasoningTokens": "5",
                },
            },
        }).encode()
        event = usage._token_event(
            "zcode", line, "ZCode", "zai", None, __import__("datetime").timezone.utc
        )
        self.assertIsNotNone(event)
        self.assertEqual(event[5:10], (120, 30, 80, 4, 5))

    def test_native_jsonl_usage_is_incremental_and_excludes_content(self) -> None:
        root = tempfile.mkdtemp(prefix="rinq-usage-source-")
        sessions = os.path.join(root, "sessions", "2026", "09", "09")
        os.makedirs(sessions)
        path = os.path.join(sessions, "session.jsonl")
        rows = [
            {"type": "session_meta", "payload": {"originator": "codex_work_desktop", "source": "vscode"}},
            {"timestamp": "2026-09-09T01:00:00Z", "type": "event_msg", "payload": {
                "type": "token_count", "info": {"last_token_usage": {
                    "input_tokens": 120, "cached_input_tokens": 80,
                    "output_tokens": 30, "reasoning_output_tokens": 5,
                }}}, "secret_prompt": "must never be retained",
            },
            {"timestamp": "2026-09-09T01:01:00Z", "type": "event_msg", "payload": {
                "type": "token_count", "info": {"last_token_usage": {
                    "input_tokens": 40, "output_tokens": 10,
                }}}, "assistant_text": "must never be retained",
            },
            {"timestamp": "2026-09-09T01:02:00Z", "type": "event_msg", "payload": {
                "type": "token_count", "info": {"last_token_usage": {
                    "input_tokens": 20, "output_tokens": 5,
                }}, "note": "session_meta and turn_context are ordinary text"},
            },
        ]
        with open(path, "w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row) + "\n")

        previous = {name: os.environ.get(name) for name in (
            "RINQ_HOME", "CODEX_HOME", "TRAECLI_HOME", "CLAUDE_CONFIG_DIR",
            "ZCODE_HOME", "PI_CODING_AGENT_DIR",
        )}
        test_home = tempfile.mkdtemp(prefix="rinq-usage-db-")
        previous_db_path = usage.USAGE_DB_PATH
        os.environ["RINQ_HOME"] = test_home
        usage.USAGE_DB_PATH = Path(test_home) / "usage.sqlite3"
        os.environ["CODEX_HOME"] = root
        os.environ["TRAECLI_HOME"] = os.path.join(root, "missing-trae")
        os.environ["CLAUDE_CONFIG_DIR"] = os.path.join(root, "missing-claude")
        os.environ["ZCODE_HOME"] = os.path.join(root, "missing-zcode")
        os.environ["PI_CODING_AGENT_DIR"] = os.path.join(root, "missing-omp")
        try:
            from datetime import datetime, timezone
            now = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
            first = usage.build_usage_summary(now)
            second = usage.build_usage_summary(now)
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            usage.USAGE_DB_PATH = previous_db_path

        self.assertEqual(first["today"]["inputTokens"], 180)
        self.assertEqual(first["today"]["outputTokens"], 45)
        self.assertEqual(first["today"]["requests"], 3)
        self.assertEqual(second["today"], first["today"])
        self.assertEqual(second["apps"][0]["app"], "Codex Desktop")

        with sqlite3.connect(os.path.join(test_home, "usage.sqlite3")) as db:
            columns = [row[1] for row in db.execute("PRAGMA table_info(usage_events)")]
            self.assertNotIn("secret_prompt", columns)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0], 3)


class SessionOverviewTests(unittest.TestCase):
    ENV_NAMES = (
        "CODEX_HOME", "TRAE_HOME", "TRAECLI_HOME", "CLAUDE_CONFIG_DIR",
        "ZCODE_HOME", "PI_CODING_AGENT_DIR", "PI_AGENT_DIR",
    )

    def setUp(self) -> None:
        self.cfg = {"push": {}}
        self.previous = {name: os.environ.get(name) for name in self.ENV_NAMES}
        root = tempfile.mkdtemp(prefix="rinq-sessions-")
        os.environ["CODEX_HOME"] = os.path.join(root, "no-codex")
        os.environ["TRAE_HOME"] = os.path.join(root, "no-trae")
        os.environ["TRAECLI_HOME"] = os.path.join(root, "no-trae-cli")
        os.environ["CLAUDE_CONFIG_DIR"] = os.path.join(root, "claude")
        os.environ["ZCODE_HOME"] = os.path.join(root, "no-zcode")
        os.environ["PI_CODING_AGENT_DIR"] = os.path.join(root, "no-omp")
        os.environ["PI_AGENT_DIR"] = os.path.join(root, "no-pi")
        self.claude_root = os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "projects")

    def tearDown(self) -> None:
        for name, value in self.previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def _write_claude(self, encoded_cwd: str, session_uuid: str, rows: list, mtime_ts: int) -> None:
        directory = os.path.join(self.claude_root, encoded_cwd)
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, session_uuid + ".jsonl")
        with open(path, "w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row) + "\n")
        os.utime(path, (mtime_ts, mtime_ts))

    def test_claude_log_state_and_hook_overlay(self) -> None:
        import time
        from rinq import sessions

        now = int(time.time())
        rows = [
            {"type": "user", "sessionId": "s1", "cwd": "/tmp/demo", "timestamp": now - 60,
             "message": {"role": "user", "content": [
                 {"type": "text", "text": "do the thing"}]}},
            {"type": "assistant", "sessionId": "s1", "cwd": "/tmp/demo", "timestamp": now - 30,
             "message": {"model": "claude-x", "content": [
                 {"type": "text", "text": "working on it"},
                 {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}},
        ]
        self._write_claude("-tmp-demo", "uuid-s1", rows, now)

        snapshot = sessions.build_sessions({}, now)
        session = next(s for s in snapshot["sessions"] if s["id"] == "claude:s1")
        self.assertEqual(session["state"], "running")
        self.assertEqual(session["summary"], "working on it")
        self.assertEqual(session["project"], "demo")
        self.assertEqual(session["source"], "log")
        self.assertEqual(snapshot["counts"]["running"], 1)

        overlay = {"agentSessions": {"claude:s1": {
            "state": "waiting", "title": "needs approval", "app": "Claude Code", "at": now}}}
        overlayed = sessions.build_sessions(overlay, now)
        merged = next(s for s in overlayed["sessions"] if s["id"] == "claude:s1")
        self.assertEqual(merged["state"], "waiting")
        self.assertEqual(merged["source"], "hook")
        self.assertEqual(overlayed["counts"]["waiting"], 1)

    def test_slash_command_markup_is_stripped_from_summary(self) -> None:
        import time
        from rinq import sessions

        now = int(time.time())
        rows = [
            {"type": "user", "sessionId": "s2", "cwd": "/tmp/demo2", "timestamp": now - 100,
             "message": {"role": "user", "content": [
                 {"type": "text",
                  "text": "<command-name>/clear</command-name>\n<command-message>clear</command-message>"}]}},
        ]
        self._write_claude("-tmp-demo2", "uuid-s2", rows, now - 100)

        snapshot = sessions.build_sessions({}, now)
        session = next((s for s in snapshot["sessions"] if s["id"] == "claude:s2"), None)
        self.assertIsNotNone(session)
        self.assertNotIn("<command-name>", session["summary"])

    def test_open_sessions_group_by_cli_then_state(self) -> None:
        import time
        from rinq import sessions

        now = int(time.time())
        state = {"agents": {}, "agentSessions": {
            "claude:idle": {"state": "idle", "app": "Claude Code", "at": now},
            "claude:running": {"state": "started", "app": "Claude Code", "at": now},
            "codex:waiting": {"state": "waiting", "app": "Codex CLI", "at": now},
            "pi:sub": {"state": "subagents_running", "app": "Pi", "at": now},
        }}
        snapshot = sessions.build_sessions(state, now)
        self.assertEqual(
            [session["id"] for session in snapshot["sessions"]],
            ["claude:running", "claude:idle", "codex:waiting", "pi:sub"],
        )
        self.assertEqual(snapshot["counts"]["subagentsRunning"], 1)

    def test_claude_task_tool_is_subagents_running(self) -> None:
        import time
        from rinq import sessions

        now = int(time.time())
        rows = [{
            "type": "assistant", "sessionId": "s-sub", "cwd": "/tmp/subagents",
            "timestamp": now - 10,
            "message": {"model": "claude-x", "content": [
                {"type": "tool_use", "name": "Task", "input": {"description": "inspect"}},
            ]},
        }]
        self._write_claude("-tmp-subagents", "uuid-sub", rows, now)
        snapshot = sessions.build_sessions({}, now)
        session = next(s for s in snapshot["sessions"] if s["id"] == "claude:s-sub")
        self.assertEqual(session["state"], "subagents_running")
        self.assertEqual(session["subagentCount"], 1)

    def test_session_end_clears_open_session_and_suppresses_old_log(self) -> None:
        import time
        from rinq import sessions

        now = int(time.time())
        rows = [{
            "type": "user", "sessionId": "s3", "cwd": "/tmp/demo3", "timestamp": now - 20,
            "message": {"role": "user", "content": [{"type": "text", "text": "still open"}]},
        }]
        self._write_claude("-tmp-demo3", "uuid-s3", rows, now - 20)
        state = state_mod.blank_state()
        events.apply_event(state, {
            "state": "closed", "title": "session closed", "sessionId": "claude:s3",
        }, self.cfg)
        self.assertNotIn("claude:s3", state["agentSessions"])
        snapshot = sessions.build_sessions(state, now)
        self.assertNotIn("claude:s3", [session["id"] for session in snapshot["sessions"]])

        self._write_claude("-tmp-demo3", "uuid-s3", rows + [{
            "type": "assistant", "sessionId": "s3", "cwd": "/tmp/demo3", "timestamp": now + 30,
            "message": {"role": "assistant", "content": [{"type": "text", "text": "tail flush"}]},
        }], now + 30)
        flushed = sessions.build_sessions(state, now + 30)
        self.assertNotIn("claude:s3", [session["id"] for session in flushed["sessions"]])

        events.apply_event(state, {
            "state": "started", "title": "session resumed", "sessionId": "claude:s3", "app": "Claude Code",
        }, self.cfg)
        reopened = sessions.build_sessions(state, now + 31)
        session = next(s for s in reopened["sessions"] if s["id"] == "claude:s3")
        self.assertEqual(session["source"], "hook")
        self.assertEqual(session["state"], "running")

    def test_waiting_falls_back_and_stale_log_disappears_without_close_hook(self) -> None:
        import time
        from rinq import sessions

        now = int(time.time())
        rows = [{
            "type": "assistant", "sessionId": "s4", "cwd": "/tmp/demo4", "timestamp": now - 300,
            "message": {"model": "claude-x", "content": [
                {"type": "tool_use", "name": "Read", "input": {"path": "README.md"}},
            ]},
        }]
        self._write_claude("-tmp-demo4", "uuid-s4", rows, now - 300)
        snapshot = sessions.build_sessions({}, now)
        session = next(s for s in snapshot["sessions"] if s["id"] == "claude:s4")
        self.assertEqual(session["state"], "waiting")

        stale = sessions.build_sessions({}, now + 301)
        self.assertNotIn("claude:s4", [session["id"] for session in stale["sessions"]])

    def test_hook_overlay_does_not_persist_message_text(self) -> None:
        import time
        from rinq import sessions

        now = int(time.time())
        state = state_mod.blank_state()
        events.apply_event(state, {
            "state": "waiting",
            "title": "user secret prompt",
            "detail": "assistant secret output",
            "sessionId": "claude:s5",
            "app": "Claude Code",
            "cwd": "/tmp/demo5",
        }, self.cfg)

        self.assertNotIn("title", state["agentSessions"]["claude:s5"])
        self.assertNotIn("detail", state["agentSessions"]["claude:s5"])
        self.assertEqual(state["agents"]["lastEvent"]["title"], "Claude Code waiting")

        snapshot = sessions.build_sessions(state, now)
        session = next(s for s in snapshot["sessions"] if s["id"] == "claude:s5")
        self.assertEqual(session["summary"], "waiting for approval")

    def test_closed_tombstone_ignores_late_waiting_event(self) -> None:
        import time
        from rinq import sessions

        now = int(time.time())
        state = state_mod.blank_state()
        events.apply_event(state, {
            "state": "closed", "title": "session closed", "sessionId": "claude:s7", "app": "Claude Code",
        }, self.cfg)
        events.apply_event(state, {
            "state": "waiting", "title": "late waiting", "sessionId": "claude:s7", "app": "Claude Code",
        }, self.cfg)

        self.assertNotIn("claude:s7", state["agentSessions"])
        snapshot = sessions.build_sessions(state, now)
        self.assertNotIn("claude:s7", [session["id"] for session in snapshot["sessions"]])

    def test_multiple_subagent_hooks_count_down_per_session(self) -> None:
        import time
        from rinq import sessions

        now = int(time.time())
        state = state_mod.blank_state()
        events.apply_event(state, {
            "state": "subagents_running", "title": "subagent 1", "sessionId": "claude:s6", "app": "Claude Code",
        }, self.cfg)
        events.apply_event(state, {
            "state": "subagents_running", "title": "subagent 2", "sessionId": "claude:s6", "app": "Claude Code",
        }, self.cfg)
        events.apply_event(state, {
            "state": "running", "title": "subagent stopped", "sessionId": "claude:s6", "app": "Claude Code",
        }, self.cfg)

        snapshot = sessions.build_sessions(state, now)
        session = next(s for s in snapshot["sessions"] if s["id"] == "claude:s6")
        self.assertEqual(session["state"], "subagents_running")
        self.assertEqual(session["subagentCount"], 1)

        events.apply_event(state, {
            "state": "running", "title": "all stopped", "sessionId": "claude:s6", "app": "Claude Code",
        }, self.cfg)
        settled = sessions.build_sessions(state, now + 1)
        session = next(s for s in settled["sessions"] if s["id"] == "claude:s6")
        self.assertEqual(session["state"], "running")
        self.assertEqual(session["subagentCount"], 0)

    def test_tail_reads_latest_80_entries_and_honors_terminal_end(self) -> None:
        import time
        from rinq import sessions

        now = int(time.time())
        rows = [{
            "type": "user", "sessionId": "s8", "cwd": "/tmp/demo8", "timestamp": now - 200,
            "message": {"role": "user", "content": [{"type": "text", "text": "start"}]},
        }, {
            "type": "assistant", "sessionId": "s8", "cwd": "/tmp/demo8", "timestamp": now - 199,
            "message": {"model": "claude-x", "content": [
                {"type": "text", "text": "running early tool"},
                {"type": "tool_use", "name": "Bash", "input": {"command": "sleep 1"}},
            ]},
        }]
        for index in range(2, 88):
            rows.append({
                "type": "assistant", "sessionId": "s8", "cwd": "/tmp/demo8", "timestamp": now - 200 + index,
                "message": {"model": "claude-x", "content": [
                    {"type": "text", "text": f"filler {index}"},
                ]},
            })
        rows.append({
            "type": "result", "sessionId": "s8", "cwd": "/tmp/demo8", "timestamp": now - 10,
            "subtype": "success",
        })
        self._write_claude("-tmp-demo8", "uuid-s8", rows, now - 10)

        snapshot = sessions.build_sessions({}, now)
        self.assertNotIn("claude:s8", [session["id"] for session in snapshot["sessions"]])


if __name__ == "__main__":
    unittest.main()
