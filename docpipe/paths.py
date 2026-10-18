# ==== ACME Inc. portfolio ===============================================
# Project: document_mover_and_changer | File: docpipe/paths.py
# About: Where the ACME Inc. programs keep their files on this computer.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Where the ACME Inc. programs keep their files on this computer.

The shared database is the only link between the six programs. Its path is chosen in this order:
the --db flag, the ACME_DB environment variable, the program's saved setting, then the default
%LOCALAPPDATA%\\ACME Inc\\acme.db. Each program keeps its own settings.json in
%LOCALAPPDATA%\\ACME Inc\\<app id>\\, holding just that path.
"""

import json
import os

APP_ID = "ACME.DocPipe"
COMPANY = "ACME Inc"
SETTINGS_VERSION = 1


def local_appdata(env=None):
    env = os.environ if env is None else env
    return env.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")


def base_dir(env=None):
    """%LOCALAPPDATA%\\ACME Inc: the shared database and every program's data folder."""
    return os.path.join(local_appdata(env), COMPANY)


def default_db(env=None):
    return os.path.join(base_dir(env), "acme.db")


def data_dir(app_id=APP_ID, env=None):
    return os.path.join(base_dir(env), app_id)


def settings_path(app_id=APP_ID, env=None):
    return os.path.join(data_dir(app_id, env), "settings.json")


def load_settings(app_id=APP_ID, env=None):
    """The saved settings, or {} when the file is missing or not a JSON object."""
    try:
        with open(settings_path(app_id, env), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(changes, app_id=APP_ID, env=None):
    """Merge changes into settings.json (unknown keys are kept); written to a temp file, then swapped in."""
    data = load_settings(app_id, env)
    data.update(changes)
    data["version"] = SETTINGS_VERSION
    path = settings_path(app_id, env)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)
    return data


def resolve_db(flag=None, app_id=APP_ID, env=None):
    """--db, then ACME_DB, then the saved setting, then the shared default."""
    env = os.environ if env is None else env
    for choice in (flag, env.get("ACME_DB"), load_settings(app_id, env).get("db")):
        if isinstance(choice, str) and choice.strip():
            return os.path.abspath(choice.strip())
    return default_db(env)

# ==== stamp v1 | author=kjFriday | hmac-sha256=6e682249b7d0dcd6acc615feebbcc46d6f0d7968a982663993a2c4b873dd465b ====
