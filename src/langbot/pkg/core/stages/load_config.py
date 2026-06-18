from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from langbot.pkg.utils import constants
import yaml
import importlib.resources as resources
import uuid
import time

from .. import stage, app
from ..bootutils import config


_SENSITIVE_ENV_KEY_PARTS = ('password', 'secret', 'token', 'key')
_LOCAL_ENV_FILES = ('.env.local', '.env')


def _parse_local_env_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        return None

    key, value = line.split('=', 1)
    key = key.strip()
    if not key:
        return None

    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return key, value


def _load_local_env_files() -> list[Path]:
    """Load local .env files without overriding real environment variables."""
    loaded: list[Path] = []
    for env_file_name in _LOCAL_ENV_FILES:
        env_file = Path(env_file_name)
        if not env_file.is_file():
            continue

        with env_file.open('r', encoding='utf-8') as f:
            for line in f:
                parsed = _parse_local_env_line(line)
                if parsed is None:
                    continue
                key, value = parsed
                os.environ.setdefault(key, value)
        loaded.append(env_file)

    if loaded:
        loaded_names = ', '.join(str(path) for path in loaded)
        print(f'loaded local env files: {loaded_names}')
    return loaded


def _mask_env_value_for_log(env_key: str, env_value: str) -> str:
    key_parts = env_key.lower().split('__')
    if any(part in key_part for key_part in key_parts for part in _SENSITIVE_ENV_KEY_PARTS):
        return '***'
    return env_value


def _apply_env_overrides_to_config(cfg: dict) -> dict:
    """Apply environment variable overrides to data/config.yaml

    Environment variables should be uppercase and use __ (double underscore)
    to represent nested keys. For example:
    - CONCURRENCY__PIPELINE overrides concurrency.pipeline
    - PLUGIN__RUNTIME_WS_URL overrides plugin.runtime_ws_url

    Arrays and dict types are ignored.

    Args:
        cfg: Configuration dictionary

    Returns:
        Updated configuration dictionary
    """

    def convert_value(value: str, original_value: Any) -> Any:
        """Convert string value to appropriate type based on original value

        Args:
            value: String value from environment variable
            original_value: Original value to infer type from

        Returns:
            Converted value (falls back to string if conversion fails)
        """
        if isinstance(original_value, bool):
            return value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(original_value, int):
            try:
                return int(value)
            except ValueError:
                # If conversion fails, keep as string (user error, but non-breaking)
                return value
        elif isinstance(original_value, float):
            try:
                return float(value)
            except ValueError:
                # If conversion fails, keep as string (user error, but non-breaking)
                return value
        else:
            return value

    # Process environment variables
    for env_key, env_value in os.environ.items():
        # Check if the environment variable is uppercase and contains __
        if not env_key.isupper():
            continue
        if '__' not in env_key:
            continue

        log_value = _mask_env_value_for_log(env_key, env_value)
        print(f'apply env overrides to config: env_key: {env_key}, env_value: {log_value}')

        # Convert environment variable name to config path
        # e.g., CONCURRENCY__PIPELINE -> ['concurrency', 'pipeline']
        keys = [key.lower() for key in env_key.split('__')]

        # Navigate to the target value and validate the path
        current = cfg

        for i, key in enumerate(keys):
            if not isinstance(current, dict):
                break

            if i == len(keys) - 1:
                # At the final key
                if key in current:
                    if isinstance(current[key], list):
                        # Convert comma-separated string to list
                        # e.g., SYSTEM__DISABLED_ADAPTERS="aiocqhttp,dingtalk"
                        current[key] = [item.strip() for item in env_value.split(',') if item.strip()]
                    elif isinstance(current[key], dict):
                        # Skip dict types
                        pass
                    else:
                        # Valid scalar value - convert and set it
                        converted_value = convert_value(env_value, current[key])
                        current[key] = converted_value
                else:
                    # Key doesn't exist yet - create it as string
                    current[key] = env_value
            else:
                # Navigate deeper - create intermediate dict if needed
                if key not in current:
                    current[key] = {}
                current = current[key]

    return cfg


def _apply_database_url_to_config(cfg: dict) -> dict:
    env_key = 'DATABASE_URL'
    database_url = os.environ.get(env_key, '').strip()
    if not database_url:
        env_key = 'DATABASE_PUBLIC_URL'
        database_url = os.environ.get(env_key, '').strip()
    if not database_url:
        return cfg

    parsed = urlparse(database_url)
    if parsed.scheme not in ('postgres', 'postgresql', 'postgresql+asyncpg'):
        return cfg

    database_cfg = cfg.setdefault('database', {})
    postgresql_cfg = database_cfg.setdefault('postgresql', {})
    database_cfg['use'] = 'postgresql'
    postgresql_cfg['host'] = parsed.hostname or postgresql_cfg.get('host', '127.0.0.1')
    postgresql_cfg['port'] = parsed.port or postgresql_cfg.get('port', 5432)
    postgresql_cfg['user'] = unquote(parsed.username or postgresql_cfg.get('user', 'postgres'))
    postgresql_cfg['password'] = unquote(parsed.password or postgresql_cfg.get('password', ''))
    postgresql_cfg['database'] = unquote(parsed.path.lstrip('/') or postgresql_cfg.get('database', 'postgres'))
    print(f'apply {env_key} to config: database.use=postgresql, env_value: ***')
    return cfg


@stage.stage_class('LoadConfigStage')
class LoadConfigStage(stage.BootingStage):
    """Load config file stage"""

    async def run(self, ap: app.Application):
        """Load config file"""

        # # ======= deprecated =======
        # if os.path.exists('data/config/command.json'):
        #     ap.command_cfg = await config.load_json_config(
        #         'data/config/command.json',
        #         'templates/legacy/command.json',
        #         completion=False,
        #     )

        # if os.path.exists('data/config/pipeline.json'):
        #     ap.pipeline_cfg = await config.load_json_config(
        #         'data/config/pipeline.json',
        #         'templates/legacy/pipeline.json',
        #         completion=False,
        #     )

        # if os.path.exists('data/config/platform.json'):
        #     ap.platform_cfg = await config.load_json_config(
        #         'data/config/platform.json',
        #         'templates/legacy/platform.json',
        #         completion=False,
        #     )

        # if os.path.exists('data/config/provider.json'):
        #     ap.provider_cfg = await config.load_json_config(
        #         'data/config/provider.json',
        #         'templates/legacy/provider.json',
        #         completion=False,
        #     )

        # if os.path.exists('data/config/system.json'):
        #     ap.system_cfg = await config.load_json_config(
        #         'data/config/system.json',
        #         'templates/legacy/system.json',
        #         completion=False,
        #     )

        # # ======= deprecated =======

        ap.instance_config = await config.load_yaml_config('data/config.yaml', 'config.yaml', completion=False)
        _load_local_env_files()

        # Apply environment variable overrides to data/config.yaml
        ap.instance_config.data = _apply_database_url_to_config(ap.instance_config.data)
        ap.instance_config.data = _apply_env_overrides_to_config(ap.instance_config.data)

        await ap.instance_config.dump_config()

        # load or generate instance id
        # Priority:
        # 1. system.instance_id from config.yaml (can be set via SYSTEM__INSTANCE_ID env var)
        # 2. data/labels/instance_id.json (if file exists)
        # 3. Generate new and save to file
        config_instance_id = ap.instance_config.data.get('system', {}).get('instance_id', '')

        if config_instance_id:
            # Use the instance_id from config.yaml
            constants.instance_id = config_instance_id
            # Still load/create the file for backward compat, but don't use its value
            ap.instance_id = await config.load_json_config(
                'data/labels/instance_id.json',
                template_data={
                    'instance_id': f'instance_{str(uuid.uuid4())}',
                    'instance_create_ts': int(time.time()),
                },
                completion=False,
            )
        else:
            # Try loading file-based instance id
            instance_id_path = os.path.join('data', 'labels', 'instance_id.json')
            if os.path.exists(instance_id_path):
                # File exists, read it
                ap.instance_id = await config.load_json_config(
                    'data/labels/instance_id.json',
                    template_data={
                        'instance_id': '',
                        'instance_create_ts': 0,
                    },
                    completion=False,
                )
                constants.instance_id = ap.instance_id.data['instance_id']
            else:
                # Neither config nor file, generate new and save to file
                new_id = f'instance_{str(uuid.uuid4())}'
                ap.instance_id = await config.load_json_config(
                    'data/labels/instance_id.json',
                    template_data={
                        'instance_id': new_id,
                        'instance_create_ts': int(time.time()),
                    },
                    completion=False,
                )
                constants.instance_id = new_id
        constants.edition = ap.instance_config.data.get('system', {}).get('edition', 'community')

        print(f'LangBot instance id: {constants.instance_id}')
        print(f'LangBot edition: {constants.edition}')

        await ap.instance_id.dump_config()

        ap.sensitive_meta = await config.load_json_config(
            'data/metadata/sensitive-words.json',
            'metadata/sensitive-words.json',
        )
        await ap.sensitive_meta.dump_config()

        async def load_resource_yaml_template_data(resource_name: str) -> dict:
            with resources.files('langbot.templates').joinpath(resource_name).open('r', encoding='utf-8') as f:
                return yaml.load(f, Loader=yaml.FullLoader)

        ap.pipeline_config_meta_trigger = await load_resource_yaml_template_data('metadata/pipeline/trigger.yaml')
        ap.pipeline_config_meta_safety = await load_resource_yaml_template_data('metadata/pipeline/safety.yaml')
        ap.pipeline_config_meta_ai = await load_resource_yaml_template_data('metadata/pipeline/ai.yaml')
        ap.pipeline_config_meta_output = await load_resource_yaml_template_data('metadata/pipeline/output.yaml')
