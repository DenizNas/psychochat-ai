import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime, timedelta, timezone

# Ensure project root is in python path
sys.path.append(os.getcwd())

from src.core.config import settings

# Setup isolated logger for cleanup jobs
logger = logging.getLogger("cleanup_backups")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | CLEANUP_JOB | %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def record_telemetry(success: bool):
    """Safely updates Prometheus metrics variables in Redis for scrape sharing."""
    try:
        from src.core.redis_client import redis_client
        r = redis_client.client
        if r:
            btype = "cleanup"
            if success:
                r.incr(f"metrics:backup:success_count:{btype}")
                r.set(f"metrics:backup:last_timestamp:{btype}", str(time.time()))
            else:
                r.incr(f"metrics:backup:failure_count:{btype}")
    except Exception as e:
        logger.warning(f"Telemetry update failed. Details: {e}")

def parse_date_from_manifest(manifest_path: str) -> datetime:
    """Reads created_at date from manifest file."""
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        created_str = data.get("created_at")
        if created_str:
            return datetime.fromisoformat(created_str.replace("Z", "+00:00"))
    except Exception:
        pass
    return None

def parse_date_from_filename(filename: str) -> datetime:
    """Fallback parsing to extract date from format _YYYY_MM_DD_HHMMSS."""
    try:
        # Expected formats containing timestamp like backup_2026_05_23_033000
        parts = filename.split("_")
        for i, part in enumerate(parts):
            if len(part) == 4 and part.isdigit(): # Possible Year YYYY
                if i + 3 <= len(parts):
                    year = int(part)
                    month = int(parts[i+1])
                    day = int(parts[i+2])
                    return datetime(year, month, day, tzinfo=timezone.utc)
    except Exception:
        pass
    return None

def evaluate_retention(created_date: datetime, now: datetime, retention_days: int) -> bool:
    """
    Evaluates GFS (Grandfather-Father-Son) retention policy.
    Returns True if the backup should be DELETED, and False if it should be PRESERVED.
    
    Preservation Rules:
    1. Keep everything within standard retention days (default 7 days).
    2. Keep weekly backups (taken on Sunday) for up to 4 weeks (28 days).
    3. Keep monthly backups (taken on the 1st of the month) for up to 3 months (90 days).
    4. Delete anything older than 3 months (90 days).
    """
    age = now - created_date
    
    # Rule 4: Delete anything older than 3 months
    if age > timedelta(days=90):
        return True # Delete
        
    # Rule 3: Keep monthly backups up to 3 months (90 days)
    if age > timedelta(days=28):
        is_monthly = (created_date.day == 1)
        return not is_monthly # Delete if not a monthly backup
        
    # Rule 2: Keep weekly backups up to 4 weeks (28 days)
    if age > timedelta(days=retention_days):
        is_weekly = (created_date.weekday() == 6) # 6 is Sunday in Python weekday()
        is_monthly = (created_date.day == 1)
        return not (is_weekly or is_monthly) # Delete if neither weekly nor monthly
        
    # Rule 1: Keep daily backups <= retention days (7 days)
    return False # Preserve

def run_cleanup(backup_dir: str, retention_days: int, dry_run: bool) -> bool:
    if not os.path.exists(backup_dir):
        logger.info(f"Backup directory does not exist: {backup_dir}. Nothing to clean.")
        record_telemetry(True)
        return True

    logger.info(
        f"Starting backup retention cleanup. Dir: {backup_dir} | "
        f"Retention Days: {retention_days} | Dry Run: {dry_run}"
    )

    now = datetime.now(timezone.utc)
    all_files = os.listdir(backup_dir)
    
    # We will identify backup groups by parsing manifests or backup archive files
    manifest_files = [f for f in all_files if f.endswith(".manifest.json")]
    
    pruned_count = 0
    total_scanned = 0

    try:
        # Group file cleanup: each manifest owns a set of backup archive files
        for m_file in manifest_files:
            total_scanned += 1
            manifest_path = os.path.join(backup_dir, m_file)
            
            # 1. Resolve creation date
            created_date = parse_date_from_manifest(manifest_path)
            if not created_date:
                created_date = parse_date_from_filename(m_file)
            if not created_date:
                # Fallback to file modification time
                mtime = os.path.getmtime(manifest_path)
                created_date = datetime.fromtimestamp(mtime, tz=timezone.utc)

            # 2. Determine GFS retention action
            should_delete = evaluate_retention(created_date, now, retention_days)
            
            if should_delete:
                # Resolve backup files belonging to this manifest
                backup_files_to_delete = [m_file]
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    files_list = data.get("files", [])
                    for f_name in files_list:
                        backup_files_to_delete.append(f_name)
                except Exception:
                    # Fallback to deleting corresponding database archives matching prefix
                    prefix = m_file.replace(".manifest.json", "")
                    for f in all_files:
                        if f.startswith(prefix) and f != m_file:
                            backup_files_to_delete.append(f)

                # 3. Perform cleanup or dry run print
                for file_to_delete in backup_files_to_delete:
                    file_path = os.path.join(backup_dir, file_to_delete)
                    if os.path.exists(file_path):
                        if dry_run:
                            logger.info(f"[DRY-RUN] Would delete file: {file_to_delete} (Created: {created_date.date()})")
                        else:
                            os.remove(file_path)
                            logger.info(f"Deleted expired backup file: {file_to_delete}")
                pruned_count += len(backup_files_to_delete)

        # Standalone archive files check (files without manifests that might have accumulated)
        for f in all_files:
            # Check files that are .sql.gz, .db.gz or .tar.gz
            if any(f.endswith(ext) for ext in [".sql.gz", ".db.gz", ".tar.gz"]):
                manifest_name = f.split(".")[0] + ".manifest.json"
                # If a manifest is supposed to exist but doesn't, clean up using filename date evaluation
                if manifest_name not in all_files:
                    created_date = parse_date_from_filename(f)
                    if not created_date:
                        mtime = os.path.getmtime(os.path.join(backup_dir, f))
                        created_date = datetime.fromtimestamp(mtime, tz=timezone.utc)
                    
                    should_delete = evaluate_retention(created_date, now, retention_days)
                    if should_delete:
                        file_path = os.path.join(backup_dir, f)
                        if dry_run:
                            logger.info(f"[DRY-RUN] Would delete standalone file: {f} (Created: {created_date.date()})")
                        else:
                            os.remove(file_path)
                            logger.info(f"Deleted expired standalone file: {f}")
                        pruned_count += 1

        logger.info(f"Success | Scanned {total_scanned} backup manifests. Pruned {pruned_count} files.")
        record_telemetry(True)
        return True

    except Exception as e:
        logger.error(f"Failed | Cleanup failed. Details: {e}")
        record_telemetry(False)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Psychochat-AI GFS Backup Retention Cleanup System")
    parser.add_argument("--backup-dir", default=settings.BACKUP_DIR, help="Directory containing backup archives")
    parser.add_argument("--retention-days", type=int, default=settings.BACKUP_RETENTION_DAYS, help="Standard retention period in days")
    parser.add_argument("--dry-run", action="store_true", help="Print cleanup targets without deleting files")
    args = parser.parse_args()

    success = run_cleanup(args.backup_dir, args.retention_days, args.dry_run)
    sys.exit(0 if success else 1)
