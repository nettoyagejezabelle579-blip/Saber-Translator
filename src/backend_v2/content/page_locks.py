"""Page-level view of the chapter write lock held by background jobs.

A translation job reserves its whole chapter so pages cannot be added,
removed or reordered underneath it.  Editing a single page only conflicts
with the job while the job still has unfinished work on that page, so
pages the job has already finished (or never touches) stay editable.
"""

from __future__ import annotations

from sqlalchemy import select

from src.backend_v2.storage.schema import chapter_write_locks, job_items

_FINISHED_ITEM_STATUSES = frozenset({"completed", "failed", "skipped", "cancelled"})


def page_reserved_by_job(connection: object, chapter_id: str, page_id: str) -> bool:
    """True when the chapter's lock-holding job may still write this page."""
    job_id = connection.execute(  # type: ignore[attr-defined]
        select(chapter_write_locks.c.job_id).where(
            chapter_write_locks.c.chapter_id == chapter_id
        )
    ).scalar_one_or_none()
    if job_id is None:
        return False
    items = connection.execute(  # type: ignore[attr-defined]
        select(job_items.c.page_id, job_items.c.status).where(
            job_items.c.job_id == job_id
        )
    ).all()
    if not items:
        # Chapter-level work without per-page items keeps the whole chapter.
        return True
    return any(
        str(item_page) == page_id and status not in _FINISHED_ITEM_STATUSES
        for item_page, status in items
    )
