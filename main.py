import os
import subprocess
import sys
from pathlib import Path

def run_command(command, description=None):
    if description:
        print(f"\n>>> {description}")
    print(f"Running: {command}")
    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        sys.exit(1)

def main():
    print("=== MySQL to PostgreSQL Migration Orchestrator ===\n")

    # Step 0: MySQL Introspection
    print("--- Step 0: MySQL Introspection ---")
    mysql_url = input("Enter MySQL connection string (mysql+pymysql://user:pass@host:port/db_name): ").strip()
    if not mysql_url:
        print("MySQL URL is required.")
        sys.exit(1)
    
    run_command(
        f"uv run --with sqlacodegen --with pymysql sqlacodegen {mysql_url} > models.py",
        "Generating initial models from MySQL"
    )

    # Step 1: Model Conversion
    run_command(
        "python scripts/01_convert_models.py models.py -o models_pg.py",
        "Step 1: Converting models to PostgreSQL format"
    )

    # Step 2: Patch Identifiers
    run_command(
        "python scripts/02_patch_identifiers.py",
        "Step 2: Patching long identifier names"
    )

    # Step 3: Patch Migration
    # Note: This assumes the migration file c243df2c8631_init_schema.py already exists.
    # If it doesn't, we might need to generate it, but the user's flow seems to assume it's there.
    run_command(
        "python scripts/03_patch_migration.py",
        "Step 3: Patching Alembic migration file"
    )

    # Step 4: Split Models
    run_command(
        "python scripts/04_split_models.py models_pg.py -o models",
        "Step 4: Splitting models into individual files"
    )

    # Step 5: .env and Docker Setup
    print("\n--- Step 5: Docker and .env Setup ---")
    if not os.path.exists(".env"):
        pg_user = input("Enter PostgreSQL User [postgres]: ").strip() or "postgres"
        pg_pass = input("Enter PostgreSQL Password [postgres]: ").strip() or "postgres"
        pg_db = input("Enter PostgreSQL Database [app_db]: ").strip() or "app_db"
        
        with open(".env", "w") as f:
            f.write(f"POSTGRES_USER={pg_user}\n")
            f.write(f"POSTGRES_PASSWORD={pg_pass}\n")
            f.write(f"POSTGRES_DB={pg_db}\n")
            f.write("DATABASE_URL=postgresql+psycopg://{}:{}@localhost:5432/{}\n".format(pg_user, pg_pass, pg_db))
        print(".env file created.")
    else:
        print(".env file already exists, skipping creation.")

    start_docker = input("Would you like to start Docker containers now? (y/n): ").lower().strip()
    if start_docker == 'y':
        run_command("docker-compose up -d", "Starting Docker containers")
        print("Waiting for PostgreSQL to be ready...")
        # Simple wait for Postgres
        import time
        time.sleep(5)
    
    # Step 6: Apply Migration
    print("\n--- Step 6: Apply Alembic Migration ---")
    apply_migration = input("Would you like to apply the Alembic migration to PostgreSQL now? (y/n): ").lower().strip()
    if apply_migration == 'y':
        run_command("uv run alembic upgrade head", "Applying migrations")
        print("\n=== All migration steps completed successfully! ===")
    else:
        print("\nSetup complete. Run 'uv run alembic upgrade head' when you are ready.")

    # Step 7: Cleanup
    print("\n--- Step 7: Cleanup ---")
    cleanup = input("Would you like to delete intermediate files (models.py, models_pg.py)? (y/n): ").lower().strip()
    if cleanup == 'y':
        for f in ["models.py", "models_pg.py"]:
            if os.path.exists(f):
                os.remove(f)
                print(f"Removed {f}")
        print("Cleanup complete.")

if __name__ == "__main__":
    main()
