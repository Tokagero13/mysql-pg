"""
Usage:
    python scripts/03_patch_migration.py

Description:
    Patches the first Alembic migration file (init_schema) to be PostgreSQL compatible.
    Fixes include:
    - Converting mysql.TINYINT to sa.Boolean or sa.SmallInteger
    - Fixing Boolean server defaults ('0'/'1' to 'false'/'true')
    - De-duplicating index names by prefixing them with table names
    - Truncating long index names (> 63 chars)
    - Fixing empty index column lists
"""
import re
import sys
from pathlib import Path

# Dynamically find the init_schema migration file
versions_dir = Path('alembic/versions')
migration_files = list(versions_dir.glob('*_init_schema.py'))

if not migration_files:
    print("Error: No migration file matching '*_init_schema.py' found in alembic/versions")
    sys.exit(1)

file_path = migration_files[0]
print(f"Patching migration file: {file_path}")

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace mysql.TINYINT(display_width=1) with sa.Boolean()
content = re.sub(r'mysql\.TINYINT\(display_width=1\)', 'sa.Boolean()', content)

# Replace mysql.TINYINT(unsigned=True) with sa.SmallInteger()
content = re.sub(r'mysql\.TINYINT\(unsigned=True\)', 'sa.SmallInteger()', content)

# Replace mysql.TINYINT() with sa.SmallInteger()
content = re.sub(r'mysql\.TINYINT\(\)', 'sa.SmallInteger()', content)

# Handle server_default='0' and '1' for Boolean
def fix_server_default(match):
    val = match.group(1)
    if val == '1':
        return "server_default=sa.text('true')"
    else:
        return "server_default=sa.text('false')"

content = re.sub(r"server_default=sa\.text\('([01])'\)", fix_server_default, content)

import hashlib

# De-duplicate index names in Postgres (global namespace)
def fix_index_name(match):
    idx_name = match.group(1)
    table_name = match.group(2)
    # Prefix index names with table name to be safe in Postgres
    if not idx_name.startswith(f'idx_{table_name}_'):
        new_name = f'idx_{table_name}_{idx_name}'
    else:
        new_name = idx_name
    
    # Truncate if too long (Postgres limit is 63)
    if len(new_name) > 63:
        # Use a hash to keep it unique but short
        hash_suffix = hashlib.md5(new_name.encode()).hexdigest()[:8]
        new_name = new_name[:54] + '_' + hash_suffix
        
    return f"op.create_index('{new_name}', '{table_name}'"

content = re.sub(r"op\.create_index\('([^']+)',\s*'([^']+)'", fix_index_name, content)

# Fix empty index column lists
def fix_empty_index_columns(match):
    idx_name = match.group(1)
    table_name = match.group(2)
    # The original index name (before our prefixing) might be the column name
    col_name = idx_name.replace(f'idx_{table_name}_', '')
    return f"op.create_index('{idx_name}', '{table_name}', ['{col_name}']"

content = re.sub(r"op\.create_index\('([^']+)',\s*'([^']+)',\s*\[\s*\]", fix_empty_index_columns, content)

# Replace other mysql types with sa equivalents (simple rename)
content = re.sub(r'mysql\.(LONGTEXT|MEDIUMTEXT|DOUBLE|TIMESTAMP|BIGINT|INTEGER|DECIMAL|ENUM|VARCHAR|CHAR)', r'sa.\1', content)

# Final cleanup for mysql.
content = content.replace('mysql.TINYINT', 'sa.SmallInteger')

# Remove mysql dialect import if it exists and maybe add postgresql if needed (though sa should suffice)
content = content.replace('from sqlalchemy.dialects import mysql', '')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Migration file patched successfully.")
