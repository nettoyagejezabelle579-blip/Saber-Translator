"""Backend-first v2 role dispatcher. 

This module must stay dependency-light.  Role-specific imports happen only after
``multiprocessing.freeze_support()`` and argument parsing so the API process
never imports Worker-only model, vector, or plugin modules as a side effect.
"""

from __future__ import annotations

import multiprocessing


def main() -> int:
    from src.backend_v2.standard_streams import restore_standard_streams

    restore_standard_streams()
    multiprocessing.freeze_support()

    # 舊版留下、缺少 METADATA 的 *.dist-info 不會再讓第三方套件匯入時崩潰
    from src.backend_v2.metadata_compat import install as install_metadata_compat

    install_metadata_compat()

    from src.backend_v2.dispatch import dispatch

    return dispatch()


if __name__ == "__main__":
    raise SystemExit(main())
