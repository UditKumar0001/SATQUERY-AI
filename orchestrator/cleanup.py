# orchestrator/cleanup.py
import os
import shutil
import time
from typing import Dict


def purge_old_uploads_and_visualizations(
    max_age_hours: int = 24,
    upload_dir: str = os.path.join("data", "raw", "uploads"),
    vis_dir: str = os.path.join("data", "processed", "visualizations"),
    report_dir: str = os.path.join("data", "processed", "reports")
) -> Dict[str, int]:
    """Purge temporary upload session folders, stale visualizations, and reports older than max_age_hours.

    Args:
        max_age_hours: Maximum age in hours before a file or directory is considered stale.
        upload_dir: Path to raw uploads directory.
        vis_dir: Path to processed visualizations directory.
        report_dir: Path to processed reports directory.

    Returns:
        Summary dictionary with counts of purged items and reclaimed bytes.
    """
    now = time.time()
    cutoff_time = now - (max_age_hours * 3600)

    purged_uploads = 0
    purged_visualizations = 0
    purged_reports = 0
    bytes_reclaimed = 0

    # 1. Clean session folders in upload_dir
    if os.path.exists(upload_dir):
        for entry in os.scandir(upload_dir):
            try:
                mtime = entry.stat().st_mtime
                if mtime < cutoff_time:
                    if entry.is_dir():
                        size = 0
                        for f in os.scandir(entry.path):
                            if f.is_file():
                                size += f.stat().st_size
                        shutil.rmtree(entry.path, ignore_errors=True)
                        purged_uploads += 1
                        bytes_reclaimed += size
                    elif entry.is_file():
                        bytes_reclaimed += entry.stat().st_size
                        os.remove(entry.path)
                        purged_uploads += 1
            except Exception as e:
                print(f"[Cleanup] Error removing upload {entry.path}: {e}")

    # 2. Clean stale visualization files
    if os.path.exists(vis_dir):
        for entry in os.scandir(vis_dir):
            try:
                if entry.is_file():
                    mtime = entry.stat().st_mtime
                    if mtime < cutoff_time:
                        bytes_reclaimed += entry.stat().st_size
                        os.remove(entry.path)
                        purged_visualizations += 1
            except Exception as e:
                print(f"[Cleanup] Error removing visualization {entry.path}: {e}")

    # 3. Clean stale PDF reports
    if os.path.exists(report_dir):
        for entry in os.scandir(report_dir):
            try:
                if entry.is_file():
                    mtime = entry.stat().st_mtime
                    if mtime < cutoff_time:
                        bytes_reclaimed += entry.stat().st_size
                        os.remove(entry.path)
                        purged_reports += 1
            except Exception as e:
                print(f"[Cleanup] Error removing report {entry.path}: {e}")

    return {
        "purged_uploads": purged_uploads,
        "purged_visualizations": purged_visualizations,
        "purged_reports": purged_reports,
        "total_purged": purged_uploads + purged_visualizations + purged_reports,
        "bytes_reclaimed": bytes_reclaimed
    }
