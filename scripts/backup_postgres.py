import os
import sys
import gzip
import json
import time
import hashlib
import logging
import argparse
import subprocess
from datetime import datetime, timezone
from urllib.parse import urlparse

# Ensure project root is in python path
sys.path.append(os.getcwd())

from src.core.config import settings

# Setup isolated logger for backup jobs
logger = logging.getLogger("backup_postgres")
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
            btype = "postgres"
            if success:
                r.incr(f"metrics:backup:success_count:{btype}")
                r.set(f"metrics:backup:last_timestamp:{btype}", str(timestamp))
            else:
                r.incr(f"metrics:backup:failure_count:{btype}")
    except Exception as e:
        logger.warning(f"Telemetry update failed. Details: {e}")

def run_backup(env_name: str, backup_dir: str) -> bool:
    start_time = time.time()
    db_url = settings.DATABASE_URL
    
    # 1. Skip run if using SQLite in current environment
    if db_url.startswith("sqlite"):
        logger.info("SQLite database detected in configuration. Skipping PostgreSQL backup.")
        return True

    # 2. Parse DATABASE_URL
    try:
        url = urlparse(db_url)
        username = url.username
        password = url.password
        hostname = url.hostname
        port = url.port or 5432
        database = url.path[1:]
    except Exception as e:
        logger.error(f"Failed to parse database connection URL. Details: {e}")
        record_telemetry(False, start_time)
        return False

    # 3. Create target directory
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp_str = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M%S")
    backup_id = f"backup_{timestamp_str}"
    
    backup_filename = f"postgres_{backup_id}.sql.gz"
    backup_filepath = os.path.join(backup_dir, backup_filename)
    manifest_filename = f"postgres_{backup_id}.manifest.json"
    manifest_filepath = os.path.join(backup_dir, manifest_filename)

    logger.info(f"Starting secure PostgreSQL backup. ID: {backup_id} | Env: {env_name}")

    # 4. Run pg_dump securely with PGPASSWORD environment isolation
    process_env = os.environ.copy()
    if password:
        process_env["PGPASSWORD"] = password

    cmd = ["pg_dump", "-h", hostname, "-p", str(port), "-U", username, "-F", "p", database]

    try:
        # Run dump and pipe output to gzip directly
        with gzip.open(backup_filepath, "wb") as gfile:
            process = subprocess.Popen(
                cmd,
                env=process_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                # Scrape out potential password details from raw connection error logs
                clean_err = error_msg.replace(password, "********") if password else error_msg
                raise Exception(f"pg_dump failed (code {process.returncode}): {clean_err}")
            
            gfile.write(stdout)

        # 5. Calculate SHA256 checksum
        checksum = calculate_sha256(backup_filepath)

        # 6. Generate Manifest JSON
        manifest_data = {
            "backup_id": backup_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "type": "postgres",
            "files": [backup_filename],
            "checksum_sha256": checksum,
            "environment": env_name,
            "status": "completed"
        }

        with open(manifest_filepath, "w", encoding="utf-8") as mfile:
            json.dump(manifest_data, mfile, indent=2)

        duration = time.time() - start_time
        logger.info(f"Success | Backup completed in {duration:.2f}s | File: {backup_filename} | Checksum: {checksum[:12]}...")
        record_telemetry(True, start_time)
        return True

    except Exception as e:
        logger.error(f"Failed | Backup failed. Details: {e}")
        record_telemetry(False, start_time)
        # Clean up partial backup files if they exist
        if os.path.exists(backup_filepath):
            try:
                os.remove(backup_filepath)
            except Exception:
                pass
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Psychochat-AI Production PostgreSQL Backup System")
    parser.add_argument("--env", default=settings.APP_ENV, help="Deployment environment name")
    parser.add_argument("--backup-dir", default=settings.BACKUP_DIR, help="Directory to save backup archives")
    args = parser.parse_args()

    success = run_backup(args.env, args.backup_dir)
    sys.exit(0 if success else 1)
