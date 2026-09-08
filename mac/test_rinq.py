from __future__ import annotations

import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

os.environ["RINQ_HOME"] = tempfile.mkdtemp(prefix="rinq-test-")
# Isolate collector tests from the user's real credentials/network.
os.environ["RINQ_CCSWITCH_DB"] = os.path.join(os.environ["RINQ_HOME"], "no-ccswitch.db")
os.environ["RINQ_CODEX_AUTH"] = os.path.join(os.environ["RINQ_HOME"], "no-auth.json")

from rinq import collectors, events, focus, sources, state as state_mod  # noqa: E402
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

    def test_enabled_false_hides_vendor(self) -> None:
        cfg = {"collectors": ["mock"], "enabled": {"deepseek": False}}
        ids = [r["id"] for r in collectors.collect(cfg)]
        self.assertNotIn("deepseek-balance", ids)

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


class ConfigEndpointTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
