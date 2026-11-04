# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/paths.py
# About: Where the Generic Company Inc. programs keep their files on this computer.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Where the Generic Company Inc. programs keep their files on this computer.

The shared database is the only link between the six programs. Its path is chosen in this order:
the --db flag, the GENERIC_COMPANY_DB environment variable, the program's saved setting, then the default
%LOCALAPPDATA%\\Generic Company Inc\\generic_company.db. Each program keeps its own settings.json in
%LOCALAPPDATA%\\Generic Company Inc\\<app id>\\, holding just that path.

Who calls it: db.py (the default DB_PATH), main.py (--db, File > Database) and installer.py
(%LOCALAPPDATA%). Every function takes an optional env dict instead of os.environ, so tests can
point it at a temporary folder. Start reading at resolve_db().
"""

import json
import os

# the hub's own id (the same as version.APP_ID): the default program for the settings functions
APP_ID = "GenericCompany.DocPipe"
COMPANY = "Generic Company Inc"  # the company folder's name under %LOCALAPPDATA% (no "." after Inc)
SETTINGS_VERSION = 1  # written into every settings.json, for a future change of its layout


def local_appdata(env=None):
    """%LOCALAPPDATA% from env (None: os.environ), or ~\\AppData\\Local when it is unset."""
    env =os.environ if env is None else env
    return env.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")


def base_dir(env=None):
    """%LOCALAPPDATA%\\Generic Company Inc: the shared database and every program's data folder."""
    return os.path.join(local_appdata(env), COMPANY)


def default_db(env=None):
    """The shared database's default path: generic_company.db in base_dir()."""
    return os.path.join(base_dir(env), "generic_company.db")


def data_dir(app_id=APP_ID, env=None):
    """The program's own folder in base_dir(), named by its app id (what --purge removes)."""
    return os.path.join(base_dir(env), app_id)


def settings_path(app_id=APP_ID, env=None):
    """The program's settings.json in its data_dir()."""
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
    """Merge changes into settings.json (unknown keys are kept); written to a temp file, then swapped in.

    os.replace swaps the file in one step, so a crash mid-write never leaves a half-written
    settings.json. Creates the folder when needed. -> the settings as written, "version" included.
    """
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
    """--db, then GENERIC_COMPANY_DB, then the saved setting, then the shared default.

    flag is the --db value or None. A blank or non-string choice is skipped. -> an absolute path;
    nothing is created.
    """
    env = os.environ if env is None else env
    for choice in (flag, env.get("GENERIC_COMPANY_DB"), load_settings(app_id, env).get("db")):
        if isinstance(choice, str) and choice.strip():
            return os.path.abspath(choice.strip())
    return default_db(env)

# ==== stamp v1 | author=kjFriday | hmac-sha256=ef62fcc2c77cb2c630299a1be8cacdee9f263db6a69bff9fc500b0829e20a3aa ====
