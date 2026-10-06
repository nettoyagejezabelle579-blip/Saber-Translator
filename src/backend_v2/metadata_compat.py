"""Make importlib.metadata.version() robust in the packaged app.

Third-party packages read their dependencies' versions at import time
(openai 3.24+: ``metadata.version("aiohttp") >= "3.10.0"``). In an install
updated in place, a leftover ``*.dist-info`` folder from an older build can
hold licence files but no METADATA; Python then finds that folder first and
returns ``None``, and the comparison crashes the Worker on start.

``install()`` wraps ``importlib.metadata.version`` so that a missing or empty
answer falls back to the package's own ``__version__``.
"""

from __future__ import annotations

import importlib
import importlib.metadata as metadata

_INSTALLED_FLAG = "_saber_version_fallback"


def _module_version(name: str) -> str | None:
    for candidate in (name, name.replace("-", "_"), name.lower().replace("-", "_")):
        try:
            module = importlib.import_module(candidate)
        except Exception:
            continue
        value = getattr(module, "__version__", None)
        if isinstance(value, str) and value:
            return value
    return None


def install() -> None:
    original = metadata.version
    if getattr(original, _INSTALLED_FLAG, False):
        return

    def version(distribution_name: str):
        try:
            value = original(distribution_name)
        except metadata.PackageNotFoundError:
            fallback = _module_version(distribution_name)
            if fallback is None:
                raise
            return fallback
        if value:
            return value
        return _module_version(distribution_name) or value

    setattr(version, _INSTALLED_FLAG, True)
    metadata.version = version  # type: ignore[assignment]
