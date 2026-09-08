from __future__ import annotations

import json
import os
from pathlib import Path

HOME = Path(os.environ.get("RINQ_HOME", Path.home() / ".rinq"))
STATE_PATH = HOME / "state.json"
CONFIG_PATH = HOME / "config.json"

DEFAULT_PORT = 7788

DEFAULT_CONFIG = {
    "port": DEFAULT_PORT,
    # 127.0.0.1 = this Mac only. Set to 0.0.0.0 (or "host": "0.0.0.0" here) to
    # open the dashboard to your phone/tablet on the same Wi-Fi. No auth; only
    # enable on trusted networks.
    "host": "127.0.0.1",
    "budgetUsd": {"openai": 20.0, "anthropic": 20.0},
    # Reference top-up amount (same currency as the vendor's balance) used to
    # turn an absolute prepaid balance into a ring percentage. CNY for the
    # Chinese vendors. Only needed if you want a fill level; without it the
    # watch shows the absolute remaining amount on a grey ring.
    "balanceFull": {
        "deepseek": 100.0,
        "moonshot": 100.0,
        "zhipu": 100.0,
        "minimax": 100.0,
        "xiaomi": 100.0,
    },
    # Real collectors auto-discover credentials. codex/minimax/deepseek read
    # cc-switch's database and the Codex ChatGPT login with no setup; the rest
    # read env keys and show "unknown" until a key is present. Switch to
    # ["mock"] for synthetic demo data with no network calls.
    "collectors": ["codex", "minimax", "deepseek", "openai", "anthropic", "moonshot", "zhipu", "xiaomi"],
    "focus": {"breakEveryMins": 50, "breakMins": 10},
    "push": {
        # Pushover is the zero-account path that works without a paid Apple
        # developer account. APNs direct push needs the watch app's bundle id
        # + a provider token; see mac/rinq/push.py.
        "pushoverToken": os.environ.get("PUSHOVER_TOKEN", ""),
        "pushoverUser": os.environ.get("PUSHOVER_USER", ""),
        "relayUrl": os.environ.get("RINQ_RELAY_URL", ""),
    },
}


def ensure_dirs() -> None:
    HOME.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    ensure_dirs()
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    if CONFIG_PATH.exists():
        try:
            user = json.loads(CONFIG_PATH.read_text())
            _deep_update(cfg, user)
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def _deep_update(base: dict, overlay: dict) -> None:
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
