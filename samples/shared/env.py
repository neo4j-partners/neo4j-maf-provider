# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from __future__ import annotations

import json
import os


def get_env_file_path() -> str | None:
    """
    Get the path to the environment file to load.

    Priorities:
    1. If RUNNING_IN_PRODUCTION is set: returns None (uses system env vars)
    2. Checks for .env in project root (one level up from samples/)
    3. Checks .azure/config.json to find the azd-managed .env

    Returns:
        Absolute path to the environment file, or None.
    """
    # In production, use system environment variables
    if os.getenv("RUNNING_IN_PRODUCTION"):
        return None

    # Get project root (two levels up from shared/)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    samples_dir = os.path.dirname(current_dir)
    project_root = os.path.dirname(samples_dir)

    # Check for .env in project root
    root_env = os.path.join(project_root, '.env')
    if os.path.exists(root_env):
        return root_env

    # Fallback: Try to get path from .azure/{environment}/.env (azd managed)
    try:
        config_path = os.path.join(project_root, '.azure', 'config.json')

        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
                default_env = config.get('defaultEnvironment')

                if default_env:
                    env_file = os.path.join(project_root, '.azure', default_env, '.env')
                    if os.path.exists(env_file):
                        return env_file

    except Exception:
        pass

    return None
