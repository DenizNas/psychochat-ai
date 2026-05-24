import os
import sys
import json
import time
import tarfile
import hashlib
import logging
import argparse
from datetime import datetime, timezone

# Ensure project root is in python path
sys.path.append(os.getcwd())

from src.core.config import settings

# Setup isolated logger for backup jobs
logger = logging.getLogger("backup_uploads")
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
            btype = "uploads"
            if success:
                r.incr(f"metrics:backup:success_count:{btype}")
                r.set(f"metrics:backup:last_timestamp:{btype}", str(timestamp))
            else:
                r.incr(f"metrics:backup:failure_count:{btype}")
    except Exception as e:
        logger.warning(f"Telemetry update failed. Details: {e}")

def run_uploads_backup(uploads_dir: str, backup_dir: str) -> bool:
    start_time = time.time()

    # 1. Verify source directory exists. If not, log warning and make an empty archive or skip.
    # To be fully resilient (especially if no uploads exist yet), we will create the directory if missing!
    if not os.path.exists(uploads_dir):
        logger.warning(f"Uploads directory not found at: {uploads_dir}. Creating empty directory to proceed.")
        os.makedirs(uploads_dir, exist_ok=True)

    # 2. Create target directory
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp_str = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M%S")
    backup_id = f"backup_{timestamp_str}"
    
    tar_filename = f"uploads_{backup_id}.tar.gz"
    tar_filepath = os.path.join(backup_dir, tar_filename)
    manifest_filename = f"uploads_{backup_id}.manifest.json"
    manifest_filepath = os.path.join(backup_dir, manifest_filename)

    logger.info(f"Starting secure uploads directory archiving. ID: {backup_id} | Path: {uploads_dir}")

    try:
        # 3. Create .tar.gz archive securely using Python standard tarfile module
        with tarfile.open(tar_filepath, "w:gz") as tar:
            # Add directory recursively with clean relative path basenames
            tar.add(uploads_dir, arcname=os.path.basename(uploads_dir))

        # 4. Calculate SHA256 checksum
        checksum = calculate_sha256(tar_filepath)

        # 5. Generate Manifest JSON
        manifest_data = {
            "backup_id": backup_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "type": "uploads",
            "files": [tar_filename],
            "checksum_sha256": checksum,
            "environment": settings.APP_ENV,
            "status": "completed"
        }

        with open(manifest_filepath, "w", encoding="utf-8") as mfile:
            json.dump(manifest_data, mfile, indent=2)

        duration = time.time() - start_time
        logger.info(f"Success | Uploads archive completed in {duration:.2f}s | File: {tar_filename} | Checksum: {checksum[:12]}...")
        record_telemetry(True, start_time)
        return True

    except Exception as e:
        logger.error(f"Failed | Uploads backup failed. Details: {e}")
        record_telemetry(False, start_time)
        if os.path.exists(tar_filepath):
            try:
                os.remove(tar_filepath)
            except Exception:
                pass
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Psychochat-AI Uploads Backup System")
    parser.add_argument("--uploads-dir", default="uploads/profile_photos", help="Path to the uploads directory")
    parser.add_argument("--backup-dir", default=settings.BACKUP_DIR, help="Directory to save backup archives")
    args = parser.parse_args()

    success = run_uploads_backup(args.uploads_dir, args.backup_dir)
    sys.exit(0 if success else 1)
