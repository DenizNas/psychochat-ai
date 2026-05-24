#!/usr/bin/env python
import os
import sys
import argparse
import sqlite3
import logging
from datetime import datetime

# Configure secure logging that does not print user passwords or chat texts
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("migration")

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    logger.critical("Error: 'psycopg2' package is not installed. Please run 'pip install psycopg2-binary'")
    sys.exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Psychochat-AI SQLite to PostgreSQL Idempotent Data Migration Utility."
    )
    parser.add_argument(
        "--sqlite-path",
        default="data/psikochat.db",
        help="Path to the source SQLite database file (default: data/psikochat.db)"
    )
    parser.add_argument(
        "--postgres-url",
        default=os.getenv("DATABASE_URL"),
        help="Target PostgreSQL connection URL. Reads from DATABASE_URL env var if not specified."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the migration without writing any changes to PostgreSQL."
    )
    return parser.parse_args()


def migrate_table(sqlite_conn, pg_conn, table_name, columns, unique_checks, dry_run=False):
    """
    Generic idempotent migration helper.
    Fetches rows from SQLite, checks if they already exist in PostgreSQL, and inserts missing ones.
    """
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    # 1. Fetch all records from SQLite
    try:
        col_list = ", ".join(columns)
        sqlite_cursor.execute(f"SELECT {col_list} FROM {table_name}")
        rows = sqlite_cursor.fetchall()
    except sqlite3.OperationalError as e:
        logger.warning(f"Table '{table_name}' does not exist in SQLite source. Skipping. Detail: {e}")
        return 0, 0, 0

    if not rows:
        logger.info(f"Table '{table_name}' is empty in SQLite source.")
        return 0, 0, 0

    total_records = len(rows)
    inserted_count = 0
    skipped_count = 0
    error_count = 0

    # 2. Build PostgreSQL insert statement
    placeholders = ", ".join(["%s"] * len(columns))
    insert_query = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"

    logger.info(f"Processing table '{table_name}': Found {total_records} source records.")

    for row in rows:
        row_dict = dict(zip(columns, row))
        
        # 3. Idempotency Check: check if record already exists in PostgreSQL
        exists = False
        if unique_checks:
            check_clause = " AND ".join([f"{col} = %s" for col in unique_checks])
            check_vals = [row_dict[col] for col in unique_checks]
            check_query = f"SELECT 1 FROM {table_name} WHERE {check_clause}"
            
            pg_cursor.execute(check_query, check_vals)
            exists = pg_cursor.fetchone() is not None

        if exists:
            skipped_count += 1
            continue

        if dry_run:
            inserted_count += 1
            continue

        # 4. Insert row securely into PostgreSQL
        try:
            insert_vals = [row_dict[col] for col in columns]
            pg_cursor.execute(insert_query, insert_vals)
            inserted_count += 1
        except Exception as e:
            logger.error(f"Error migrating row in '{table_name}': {e}")
            error_count += 1
            pg_conn.rollback()

    if not dry_run and inserted_count > 0:
        pg_conn.commit()

    action = "Simulated" if dry_run else "Migrated"
    logger.info(
        f"[{table_name}] Result: {action} {inserted_count}/{total_records} rows. "
        f"Skipped (already exists): {skipped_count}. Errors: {error_count}."
    )
    return total_records, inserted_count, skipped_count


def main():
    args = parse_arguments()
    
    if not args.postgres_url:
        logger.critical("Error: PostgreSQL connection URL is missing. Set --postgres-url or DATABASE_URL env var.")
        sys.exit(1)

    logger.info("Starting Psychochat-AI database migration...")
    logger.info(f"Source SQLite: {args.sqlite_path}")
    logger.info(f"Target PostgreSQL: {args.postgres_url.split('@')[-1] if '@' in args.postgres_url else args.postgres_url} (credentials hidden)")
    if args.dry_run:
        logger.info("!!! DRY-RUN MODE ACTIVE: No changes will be saved to PostgreSQL !!!")

    # 1. Connect to SQLite
    if not os.path.exists(args.sqlite_path):
        logger.critical(f"SQLite file not found at path: {args.sqlite_path}. Exiting.")
        sys.exit(1)

    try:
        sqlite_conn = sqlite3.connect(args.sqlite_path)
        sqlite_conn.text_factory = lambda x: str(x, 'utf-8', 'replace')
    except Exception as e:
        logger.critical(f"Failed to connect to SQLite: {e}")
        sys.exit(1)

    # 2. Connect to PostgreSQL
    try:
        pg_conn = psycopg2.connect(args.postgres_url)
    except Exception as e:
        logger.critical(f"Failed to connect to PostgreSQL: {e}")
        sqlite_conn.close()
        sys.exit(1)

    # 3. Define tables, columns, and uniquely identifying keys to prevent duplicate copying
    migration_plan = [
        {
            "table": "users",
            "columns": ["id", "username", "password_hash", "created_at"],
            "unique_keys": ["id", "username"]
        },
        {
            "table": "user_profiles",
            "columns": [
                "username", "display_name", "bio", "profile_photo_url", 
                "preferred_language", "response_style", "theme_preference", 
                "notifications_enabled", "privacy_mode", "answer_length_preference", 
                "created_at", "updated_at"
            ],
            "unique_keys": ["username"]
        },
        {
            "table": "analytics",
            "columns": [
                "id", "user_id", "user_text", "emotion", "risk", 
                "language", "latency_ms", "timestamp"
            ],
            "unique_keys": ["id"]
        },
        {
            "table": "chat_history",
            "columns": ["id", "user_id", "role", "content", "timestamp"],
            "unique_keys": ["id"]
        },
        {
            "table": "user_memories",
            "columns": [
                "id", "user_id", "memory_key", "memory_value", "emotion", 
                "created_at", "updated_at", "source_message", "confidence", "source"
            ],
            "unique_keys": ["id"]
        },
        {
            "table": "emotion_events",
            "columns": ["id", "user_id", "message_id", "emotion", "risk", "created_at", "source"],
            "unique_keys": ["id"]
        },
        {
            "table": "scheduled_interventions",
            "columns": [
                "id", "user_id", "intervention_type", "scheduled_for", 
                "status", "priority", "created_at", "source_insight", "delivery_channel"
            ],
            "unique_keys": ["id"]
        },
        {
            "table": "mood_journals",
            "columns": ["id", "user_id", "mood", "intensity", "note", "created_at", "updated_at", "source"],
            "unique_keys": ["id"]
        },
        {
            "table": "notification_events",
            "columns": [
                "id", "user_id", "notification_type", "title", "body", 
                "scheduled_for", "status", "created_at", "delivered_at", "source"
            ],
            "unique_keys": ["id"]
        }
    ]

    total_inserted = 0
    total_skipped = 0

    try:
        for plan in migration_plan:
            _, ins, skp = migrate_table(
                sqlite_conn=sqlite_conn,
                pg_conn=pg_conn,
                table_name=plan["table"],
                columns=plan["columns"],
                unique_checks=plan["unique_keys"],
                dry_run=args.dry_run
            )
            total_inserted += ins
            total_skipped += skp
            
        logger.info("======================================================")
        status_msg = "DRY-RUN COMPLETE" if args.dry_run else "MIGRATION SUCCESSFULLY FINISHED"
        logger.info(f"{status_msg}: Transferred {total_inserted} rows, Skipped {total_skipped} rows.")
        logger.info("======================================================")

    except Exception as e:
        logger.error(f"Migration aborted due to unexpected error: {e}")
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    main()
