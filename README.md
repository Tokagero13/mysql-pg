# MySQL to PostgreSQL Migration Tool

This project is designed for automated database schema migration from MySQL to PostgreSQL using SQLAlchemy and Alembic.

## Overview

The toolkit provides functionality to:
1. Introspect an existing MySQL database and generate SQLAlchemy models.
2. Convert MySQL data types (TINYINT, LONGTEXT, UNSIGNED, etc.) to PostgreSQL equivalents.
3. Fix identifier names (tables, indexes, FKs) that exceed the 63-character PostgreSQL limit.
4. Patch Alembic migrations for PostgreSQL compatibility (boolean fixes, index de-duplication).
5. Split a monolithic models file into individual class files.

---

## Conversion Details (01_convert_models.py)

The script performs a deep transformation of the models to ensure full compatibility with PostgreSQL:

### Type and Attribute Mapping Table

| MySQL / Specific Code | PostgreSQL / SQLAlchemy | Comment |
| :--- | :--- | :--- |
| `LONGTEXT`, `MEDIUMTEXT` | `Text` | Converted to universal text type |
| `VARCHAR(N)`, `CHAR(N)` | `String(N)` | `charset` and `collation` are removed |
| `DOUBLE`, `DECIMAL` | `Float` | PostgreSQL prefers `Float` or `Numeric` for these |
| `TIMESTAMP`, `TIMESTAMP(fsp)` | `DateTime` | Standard date and time type |
| `TINYINT(1)` (flags) | `Boolean` | Applied if the field name matches patterns like `is_`, `has_`, etc. |
| `TINYINT` (numbers) | `SmallInteger` | Applied if the field name doesn't match flag patterns |
| `unsigned=True` | *(removed)* | PostgreSQL does not have a native `unsigned` modifier |
| `charset='...'`, `collation='...'` | *(removed)* | MySQL encoding parameters are incompatible with Postgres |
| `text('0')` / `text('1')` | `text('false')` / `text('true')` | Only for fields defined as `Boolean` |

### TINYINT Handling Logic
The script automatically determines whether a `TINYINT` field is logical (Boolean) or numeric (SmallInteger) by analyzing its name. Fields considered logical include:
*   Prefixes: `is_`, `has_`, `can_`, `should_`, `was_`.
*   Special names: `active`, `visible`, `public`, `enabled`, `deleted`, `revoked`, `archived`, etc.

### Timestamp Handling (Triggers)
MySQL-specific construction:
`server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')`
is automatically replaced with the SQLAlchemy standard:
`server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now()`

### Cleanup and Imports
*   **Imports**: The script removes `from sqlalchemy.dialects.mysql import ...` and ensures all necessary types are present in `from sqlalchemy import ...`.
*   **Syntax**: Removes unnecessary empty parentheses in types (e.g., `Integer()` -> `Integer`) for PEP8 compliance.

---

## Technical Patch Details

### 02_patch_identifiers.py (Long Names)
PostgreSQL has a strict **63-character** limit on identifier lengths (tables, indexes, FKs). The script:
1.  Scans `models_pg.py` for names exceeding this limit.
2.  Applies the algorithm: `name_up_to_54_chars + _ + 8_char_md5_hash`.
3.  Hashing ensures that names remain unique across the entire database even after truncation.

### 03_patch_migration.py (Alembic Patch)
This script is critical for "fixing" generated migrations that are originally tailored for MySQL:
*   **Bulk Type Replacement**: Replaces `mysql.TINYINT` in the migration file with `sa.Boolean()` or `sa.SmallInteger()`.
*   **Index De-duplication**: In PostgreSQL, index names must be unique within the schema. The script renames indexes like `school_id` to `idx_table_name_school_id`.
*   **Empty Index Fix**: Fixes erroneous `op.create_index(..., [])` constructs by inserting the column name derived from the index name.
*   **Server Default Translation**: Changes `'0'/'1'` to `'false'/'true'` for boolean columns at the DDL level.

### 04_split_models.py (Splitting)
Splits the monolithic file into a modular structure:
*   Creates `models/base.py` with the declarative base class.
*   Generates one `.py` file per table.
*   Creates `models/__init__.py` for convenient importing of all models.

---

## How to Use (Automated Mode)

The easiest way is to run the orchestrator, which will guide you through all steps:

### Windows (PowerShell):
```powershell
.\migrate.ps1
```

### Linux / macOS (Bash):
```bash
chmod +x migrate.sh
./migrate.sh
```

**The orchestrator will perform the following steps:**
1. Prompt for MySQL connection string and generate `models.py`.
2. Convert models to `models_pg.py`.
3. Fix long identifier names.
4. Patch the Alembic migration file.
5. Split models into individual files in the `models/` directory.
6. Assist in creating `.env` and starting PostgreSQL in Docker.
7. Apply migrations (`alembic upgrade head`).
8. Prompt for cleanup of intermediate files.

---

## How to Use (Manual Mode)

If you prefer to run steps individually, use the scripts in the `scripts/` directory in order:

### 1. Generate Models
```bash
uv run --with sqlacodegen --with pymysql sqlacodegen mysql+pymysql://user:pass@host:port/db_name > models.py
```

### 2. Convert Types
```bash
python scripts/01_convert_models.py models.py -o models_pg.py
```

### 3. Fix Long Names
```bash
python scripts/02_patch_identifiers.py
```

### 4. Patch Alembic Migration
```bash
python scripts/03_patch_migration.py
```

### 5. Split Models
```bash
python scripts/04_split_models.py models_pg.py -o models
```

### 6. Infrastructure and Migration
1. Configure `.env` (see `env.example`).
2. Start DB: `docker-compose up -d`.
3. Apply schema: `uv run alembic upgrade head`.

---

## Project Structure

* `main.py` — Main migration orchestrator.
* `scripts/` — Toolkit for code transformation.
* `alembic/` — Configuration and migration history.
* `models/` — Final models directory (generated automatically).
* `docker-compose.yml` — PostgreSQL 16 environment.
* `.gitignore` — Properly configured to exclude generated and sensitive data.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
