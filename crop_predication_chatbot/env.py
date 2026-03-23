import json
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback for environments without python-dotenv installed yet.
    load_dotenv = None


def load_env_file(env_path: str | None = None) -> None:
    base_dir = Path(__file__).resolve().parent.parent
    path = Path(env_path) if env_path else base_dir / '.env'
    if not path.exists():
        return

    if load_dotenv is not None:
        load_dotenv(dotenv_path=path, override=False)
        return

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()

        if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is not None and value.strip():
        return value.strip()
    return default


def get_env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def get_env_list(name: str, default: list[str] | None = None) -> list[str]:
    value = os.getenv(name)
    if not value:
        return list(default or [])
    return [item.strip() for item in value.split(',') if item.strip()]


def _bundle_secret(bundle_name: str, secret_name: str) -> str | None:
    payload = os.getenv(bundle_name, '').strip()
    if not payload:
        return None

    try:
        bundle = json.loads(payload)
    except json.JSONDecodeError:
        return None

    value = bundle.get(secret_name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def get_secret(name: str, default: str | None = None) -> str | None:
    direct_value = get_env(name)
    if direct_value is not None:
        return direct_value

    # Compatibility bridge for future cloud deployments where a platform
    # injects secret bundles or prefixed variables sourced from a vault.
    cloud_candidates = (
        f"AWS_SECRET_{name}",
        f"AZURE_SECRET_{name}",
    )
    for candidate in cloud_candidates:
        value = get_env(candidate)
        if value is not None:
            return value

    for bundle_name in ('AWS_SECRETS_BUNDLE', 'AZURE_KEY_VAULT_BUNDLE'):
        value = _bundle_secret(bundle_name, name)
        if value is not None:
            return value

    return default


def require_secret(name: str, default: str | None = None) -> str:
    value = get_secret(name, default=default)
    if value is None or not str(value).strip():
        raise ImproperlyConfigured(f"Missing required secret: {name}")
    return str(value).strip()
