import os
import sys
import gzip
import json
import logging
import argparse
import subprocess
import hashlib
from urllib.parse import urlparse

# Ensure project root is in python path
sys.path.append(os.getcwd())

from src.core.config import settings

# Setup isolated logger for restore jobs
logger = logging.getLogger("restore_postgres")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | RESTORE_JOB | %(message)s")
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

def run_restore(backup_path: str, confirm_restore: bool, dry_run: bool) -> bool:
    db_url = settings.DATABASE_URL
    
    # 1. Check if backup file exists
    if not os.path.exists(backup_path):
        logger.error(f"Backup file not found: {backup_path}")
        return False

    # 2. Try to locate manifest
    base_path = backup_path
    if base_path.endswith(".gz"):
        base_path = base_path[:-3]
    for ext in [".sql", ".db", ".tar"]:
        if base_path.endswith(ext):
            base_path = base_path[:-len(ext)]
    manifest_path = base_path + ".manifest.json"
    manifest_exists = os.path.exists(manifest_path)
    
    logger.info(f"Initiating validation for backup file: {backup_path}")
    
    # 3. Verify SHA256 Checksum if manifest is available
    if manifest_exists:
        logger.info("Found associated JSON manifest. Verifying checksum...")
        try:
            with open(manifest_path, "r", encoding="utf-8") as mfile:
                manifest = json.load(mfile)
            
            expected_checksum = manifest.get("checksum_sha256")
            actual_checksum = calculate_sha256(backup_path)
            
            if expected_checksum != actual_checksum:
                logger.error(
                    f"CHECKSUM MISMATCH! Manifest expected {expected_checksum[:12]}, "
                    f"but file checksum is {actual_checksum[:12]}"
                )
                return False
            logger.info("Checksum verification successful! Integrity guaranteed.")
        except Exception as e:
            logger.error(f"Error parsing manifest or validating checksum: {e}")
            return False
    else:
        logger.warning("No JSON manifest found in the same folder. Proceeding without checksum integrity check.")

    # 4. Parse DATABASE_URL
    try:
        url = urlparse(db_url)
        username = url.username
        password = url.password
        hostname = url.hostname
        port = url.port or 5432
        database = url.path[1:]
    except Exception as e:
        logger.error(f"Failed to parse database connection URL. Details: {e}")
        return False

    # 5. Verify database connection
    logger.info(f"Testing connectivity to target database: {database} at {hostname}:{port}")
    try:
        test_env = os.environ.copy()
        if password:
            test_env["PGPASSWORD"] = password
        
        # Run a simple query to verify db is reachable
        subprocess.run(
            ["pg_isready", "-h", hostname, "-p", str(port), "-U", username, "-d", database],
            env=test_env,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        logger.info("Database connectivity test successful.")
    except Exception as e:
        logger.error(f"Target database is unreachable. Connection test failed. Details: {e}")
        return False

    # 6. Dry Run Bypass
    if dry_run:
        logger.info("=== DRY-RUN VERIFICATION COMPLETED SUCCESSFULLY ===")
        logger.info(f"Target: psql -h {hostname} -p {port} -U {username} -d {database}")
        logger.info("No modifications were executed on the database.")
        return True

    # 7. Check Confirm Restore Flag
    if not confirm_restore:
        logger.error(
            "CRITICAL: Destructive database restore aborted! "
            "You MUST explicitly pass the '--confirm-restore' flag to execute a restore."
        )
        return False

    # 8. Extra Manual Prompt for Production/Staging environments
    active_env = settings.APP_ENV.lower()
    if active_env in ["production", "staging"]:
        logger.warning(
            f"!!! WARNING !!! YOU ARE ABOUT TO RESTORE A DATABASE ON A '{active_env.upper()}' ENVIRONMENT!"
        )
        logger.warning("This is a destructive operation that will overwrite existing database records!")
        logger.warning(f"Target database: {database}")
        
        # Prompt only if running in an interactive terminal
        if sys.stdin.isatty():
            confirm = input(f"Are you absolutely sure you want to restore to {active_env.upper()}? (Type 'YES' to proceed): ")
            if confirm.strip() != "YES":
                logger.error("Destructive restore aborted by operator confirmation.")
                return False
        else:
            logger.info("Non-interactive production restore detected. Proceeding with automated confirmation.")

    # 9. Perform Destructive Restore
    logger.info(f"Performing destructive database restore from: {backup_path}")
    
    process_env = os.environ.copy()
    if password:
        process_env["PGPASSWORD"] = password

    cmd = ["psql", "-h", hostname, "-p", str(port), "-U", username, "-d", database]

    try:
        # Extract gzip data and feed it directly to psql's standard input
        with gzip.open(backup_path, "rb") as gfile:
            sql_content = gfile.read()

        process = subprocess.Popen(
            cmd,
            env=process_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(input=sql_content)

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            clean_err = error_msg.replace(password, "********") if password else error_msg
            raise Exception(f"psql failed (code {process.returncode}): {clean_err}")

        logger.info("Success | Database restore successfully completed!")
        return True

    except Exception as e:
        logger.error(f"Failed | Restore failed. Details: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Psychochat-AI Production PostgreSQL Restore System")
    parser.add_argument("--backup-path", required=True, help="Path to the compressed backup file (.sql.gz)")
    parser.add_argument("--confirm-restore", action="store_true", help="Explicitly approve destructive restore execution")
    parser.add_argument("--dry-run", action="store_true", help="Validate backup archive integrity and exit without writing")
    args = parser.parse_args()

    success = run_restore(args.backup_path, args.confirm_restore, args.dry_run)
    sys.exit(0 if success else 1)
