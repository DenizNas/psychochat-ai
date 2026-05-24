import os
import sys
import gzip
import json
import time
import sqlite3
import hashlib
import logging
import argparse
from datetime import datetime, timezone

# Ensure project root is in python path
sys.path.append(os.getcwd())

from src.core.config import settings

# Setup isolated logger for backup jobs
logger = logging.getLogger("backup_sqlite")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | BACKUP_JOB | %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def calculate_sha256(filepath: str) -> str:
    """Calculates SHA256 checksum of a file for manifest verification."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def record_telemetry(success: bool, timestamp: float):
    """Safely updates Prometheus metrics variables in Redis for scrape sharing."""
    try:
        from src.core.redis_client import redis_client
        r = redis_client.client
        if r:
            btype = "sqlite"
            if success:
                r.incr(f"metrics:backup:success_count:{btype}")
                r.set(f"metrics:backup:last_timestamp:{btype}", str(timestamp))
            else:
                r.incr(f"metrics:backup:failure_count:{btype}")
    except Exception as e:
        logger.warning(f"Telemetry update failed. Details: {e}")

def run_sqlite_backup(db_path: str, backup_dir: str) -> bool:
    start_time = time.time()
    
    # 1. Resolve raw DB path from SQLite URL
    clean_db_path = db_path
    if clean_db_path.startswith("sqlite:///"):
        clean_db_path = clean_db_path.replace("sqlite:///", "", 1)
    
    if not os.path.exists(clean_db_path):
        logger.error(f"SQLite source database not found at: {clean_db_path}")
        record_telemetry(False, start_time)
        return False

    # 2. Create target directory
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp_str = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M%S")
    backup_id = f"backup_{timestamp_str}"
    
    temp_backup_db = os.path.join(backup_dir, f"sqlite_{backup_id}.db")
    compressed_filename = f"sqlite_{backup_id}.db.gz"
    compressed_filepath = os.path.join(backup_dir, compressed_filename)
    manifest_filename = f"sqlite_{backup_id}.manifest.json"
    manifest_filepath = os.path.join(backup_dir, manifest_filename)

    logger.info(f"Starting secure SQLite point-in-time backup. ID: {backup_id}")

    try:
        # 3. Perform atomic backup using sqlite3.Connection.backup()
        # This handles WAL/shm transaction logs natively and guarantees zero client locks!
        src_conn = sqlite3.connect(clean_db_path)
        dest_conn = sqlite3.connect(temp_backup_db)
        
        with dest_conn:
            src_conn.backup(dest_conn)
            
        dest_conn.close()
        src_conn.close()

        # 4. Compress target database file with Gzip
        with open(temp_backup_db, "rb") as f_in:
            with gzip.open(compressed_filepath, "wb") as f_out:
                f_out.writelines(f_in)

        # Remove temporary uncompressed DB file
        os.remove(temp_backup_db)

        # 5. Calculate SHA256 checksum
        checksum = calculate_sha256(compressed_filepath)

        # 6. Generate Manifest JSON
        manifest_data = {
            "backup_id": backup_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "type": "sqlite",
            "files": [compressed_filename],
            "checksum_sha256": checksum,
            "environment": settings.APP_ENV,
            "status": "completed"
        }

        with open(manifest_filepath, "w", encoding="utf-8") as mfile:
            json.dump(manifest_data, mfile, indent=2)

        duration = time.time() - start_time
        logger.info(f"Success | Backup completed in {duration:.2f}s | File: {compressed_filename} | Checksum: {checksum[:12]}...")
        record_telemetry(True, start_time)
        return True

    except Exception as e:
        logger.error(f"Failed | SQLite Backup failed. Details: {e}")
        record_telemetry(False, start_time)
        # Clean up temporary or partial files if they exist
        if os.path.exists(temp_backup_db):
            try:
                os.remove(temp_backup_db)
            except Exception:
                pass
        if os.path.exists(compressed_filepath):
            try:
                os.remove(compressed_filepath)
            except Exception:
                pass
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Psychochat-AI SQLite Backup System")
    parser.add_argument("--db-path", default=settings.DATABASE_URL, help="Path to the SQLite database file or URL")
    parser.add_argument("--backup-dir", default=settings.BACKUP_DIR, help="Directory to save backup archives")
    args = parser.parse_args()

    success = run_sqlite_backup(args.db_path, args.backup_dir)
    sys.exit(0 if success else 1)
