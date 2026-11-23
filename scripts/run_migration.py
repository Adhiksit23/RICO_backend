#!/usr/bin/env python3
"""
Database Migration Runner for RICO.

Usage:
    python scripts/run_migration.py migrations/005_part_operating_parameters_wide.sql
    python scripts/run_migration.py --all
"""
import sys
import os
from pathlib import Path
import psycopg2

# Ensure RICO_backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.config import DB_CONFIG

def run_migration(sql_path: Path):
    if not sql_path.exists():
        print(f"❌ Error: Migration file not found: {sql_path}")
        return False

    print(f"\n==================================================")
    print(f"🚀 Running migration: {sql_path.name}")
    print(f"Connecting to database {DB_CONFIG.get('dbname')} on {DB_CONFIG.get('host')}...")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()

        sql_content = sql_path.read_text(encoding="utf-8")
        cur.execute(sql_content)

        print(f"✅ Migration {sql_path.name} applied successfully!")
        cur.close()
        conn.close()
        return True
    except Exception as exc:
        print(f"❌ Migration failed: {exc}")
        return False

def main():
    if len(sys.argv) < 2:
        default_file = Path(__file__).resolve().parent.parent / "migrations" / "005_part_operating_parameters_wide.sql"
        print(f"No migration specified, defaulting to: {default_file.name}")
        success = run_migration(default_file)
        sys.exit(0 if success else 1)

    arg = sys.argv[1]
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

    if arg == "--all":
        sql_files = sorted(migrations_dir.glob("*.sql"))
        print(f"Found {len(sql_files)} migrations in {migrations_dir}")
        for sql_file in sql_files:
            if not run_migration(sql_file):
                sys.exit(1)
        print("\n🎉 All migrations completed successfully!")
    else:
        target = Path(arg)
        if not target.is_absolute() and not target.exists():
            target = migrations_dir / target.name
        success = run_migration(target)
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
