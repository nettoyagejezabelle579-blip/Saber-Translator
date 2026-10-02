"""
CPU 线程预算（CPU 版专用）

PyTorch / OpenCV 默认会占满所有物理核心。在轻薄本（如 Galaxy Book3 Pro）上，
这会让风扇狂转、触发降频，反而更慢，同时整机卡顿。没有可用 GPU 时，这里把
深度学习推理限制在一部分核心上，并把 Worker 进程优先级调低，让前台保持流畅。

环境变量：
- SABER_CPU_THREADS: 推理线程数。未设置时自动取物理核心数的一半（2~6）；
  设为 0 表示不做限制（恢复原始行为）。
- SABER_CPU_LOW_PRIORITY: 设为 0 时不降低 Worker 进程优先级。
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger("CpuThreads")

THREADS_ENV = "SABER_CPU_THREADS"
LOW_PRIORITY_ENV = "SABER_CPU_LOW_PRIORITY"

_MIN_AUTO_THREADS = 2
_MAX_AUTO_THREADS = 6

_configured_threads: int | None = None


def _physical_cores() -> int:
    try:
        import psutil

        cores = psutil.cpu_count(logical=False)
        if cores:
            return int(cores)
    except Exception:
        pass
    return max(1, (os.cpu_count() or 2) // 2)


def resolve_cpu_thread_budget(environ=os.environ) -> int | None:
    """返回推理线程数；None 表示不限制。"""
    raw = str(environ.get(THREADS_ENV, "")).strip()
    if raw:
        try:
            value = int(raw)
        except ValueError:
            logger.warning("%s=%r 不是整数，改用自动值", THREADS_ENV, raw)
        else:
            if value <= 0:
                return None
            return value
    return max(_MIN_AUTO_THREADS, min(_MAX_AUTO_THREADS, _physical_cores() // 2))


def _lower_process_priority() -> None:
    try:
        import psutil

        process = psutil.Process()
        if sys.platform == "win32":
            process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            process.nice(max(process.nice(), 10))
    except Exception:
        logger.debug("降低进程优先级失败", exc_info=True)


def configure_cpu_threads(environ=os.environ) -> int | None:
    """在没有可用 GPU 时限制推理线程数。可重复调用。"""
    global _configured_threads
    try:
        import torch
    except Exception:
        return None
    try:
        has_gpu = torch.cuda.is_available() or (
            hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        )
    except Exception:
        has_gpu = False
    if has_gpu:
        return None

    budget = resolve_cpu_thread_budget(environ)
    if budget is None:
        return None

    torch.set_num_threads(budget)
    try:
        # 只能在第一次并行计算之前设置，之后调用会抛异常
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    try:
        import cv2

        cv2.setNumThreads(budget)
    except Exception:
        pass

    if _configured_threads is None and str(
        environ.get(LOW_PRIORITY_ENV, "1")
    ).strip() != "0":
        _lower_process_priority()

    _configured_threads = budget
    logger.info("CPU 推理线程已限制为 %s（%s 可调整）", budget, THREADS_ENV)
    return budget
