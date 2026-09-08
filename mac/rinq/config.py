from __future__ import annotations

import json
import os
from pathlib import Path

HOME = Path(os.environ.get("RINQ_HOME", Path.home() / ".rinq"))
STATE_PATH = HOME / "state.json"
CONFIG_PATH = HOME / "config.json"

DEFAULT_PORT = 7788

# Vendor ids the app knows about, in default display order. The user reorders
# and toggles these in the Settings UI; vendors with no credential and no
# ChatGPT login are hidden automatically.
VENDOR_IDS = ["codex", "minimax", "deepseek", "openai", "anthropic", "moonshot", "zhipu", "xiaomi"]

DEFAULT_CONFIG = {
    "port": DEFAULT_PORT,
    # 127.0.0.1 = this Mac only. Set to 0.0.0.0 (or "host": "0.0.0.0" here) to
    # open the dashboard to your phone/tablet on the same Wi-Fi. No auth; only
    # enable on trusted networks.
    "host": "127.0.0.1",
    # Per-vendor API keys entered in the Settings UI. Keys live only in this
    # local file (chmod 600); they are sent only to the matching vendor and are
    # never sent to the browser (the /config endpoint masks them).
    "keys": {},
    # Explicitly enabled vendors. When null/empty, a vendor shows up only when
    # it has a usable credential/auto-discovery. Set false to hide even then.
    "enabled": {},
    # Order ring ids are displayed (rings, bars, and the dashboard). Anything
    # not listed follows in default order.
    "ringOrder": ["codex-5h", "codex-week", "minimax-5h", "minimax-week",
                  "deepseek-balance", "openai-api", "anthropic-api",
                  "moonshot-balance", "zhipu-balance", "xiaomi-balance"],
    "budgetUsd": {"openai": 20.0, "anthropic": 20.0},
    # Reference top-up amount (same currency as the vendor's balance) used to
    # turn an absolute prepaid balance into a ring percentage. CNY for the
    # Chinese vendors. Only needed if you want a fill level; without it the
    # watch/dashboard shows the absolute amount on a grey ring.
    "balanceFull": {
        "deepseek": 100.0,
        "moonshot": 100.0,
        "zhipu": 100.0,
        "minimax": 100.0,
        "xiaomi": 100.0,
    },
    # Real collectors auto-discover credentials (cc-switch db, Codex login,
    # and the "keys" block above). Vendors with no credential are omitted from
    # /status entirely. Switch to ["mock"] for synthetic demo data.
    "collectors": ["codex", "minimax", "deepseek", "openai", "anthropic", "moonshot", "zhipu", "xiaomi"],
    "focus": {"breakEveryMins": 50, "breakMins": 10},
    "push": {
        "pushoverToken": os.environ.get("PUSHOVER_TOKEN", ""),
        "pushoverUser": os.environ.get("PUSHOVER_USER", ""),
        "relayUrl": os.environ.get("RINQ_RELAY_URL", ""),
    },
}


def save_config(cfg: dict) -> None:
    ensure_dirs()
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2))
    tmp.replace(CONFIG_PATH)
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass


def ring_sort_key(cfg: dict):
    order = cfg.get("ringOrder") or []

    def key(ring: dict):
        rid = ring.get("id", "")
        if rid in order:
            return (0, order.index(rid))
        vendor = ring.get("vendor", "")
        return (1, VENDOR_IDS.index(vendor) if vendor in VENDOR_IDS else 99)
    return key


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
