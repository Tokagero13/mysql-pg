"""
Usage:
    python scripts/02_patch_identifiers.py

Description:
    Scans 'models_pg.py' and truncates any identifiers (table names, indexes, foreign keys)
    that exceed the 63-character PostgreSQL limit. It uses md5 hashing to ensure uniqueness.
"""
import re
import hashlib
from pathlib import Path

def truncate_identifier(name, max_len=63):
    if len(name) <= max_len:
        return name
    
    # Use a hash to keep it unique but short
    hash_suffix = hashlib.md5(name.encode()).hexdigest()[:8]
    return name[:max_len - 9] + '_' + hash_suffix

def patch_models_identifiers(file_path: Path):
    if not file_path.exists():
        print(f"File {file_path} not found.")
        return

    content = file_path.read_text(encoding="utf-8")

    # 1. Patch Table names in __tablename__
    def fix_tablename(match):
        name = match.group(1)
        new_name = truncate_identifier(name)
        if new_name != name:
            print(f"Truncating table: {name} -> {new_name}")
        return f"__tablename__ = '{new_name}'"

    content = re.sub(r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]", fix_tablename, content)

    # 2. Patch Index names
    def fix_index_name(match):
        name = match.group(1)
        new_name = truncate_identifier(name)
        if new_name != name:
            print(f"Truncating index: {name} -> {new_name}")
        return f"Index('{new_name}'"

    content = re.sub(r"Index\(['\"]([^'\"]+)['\"]", fix_index_name, content)
    
    # 3. Patch ForeignKeyConstraint names
    def fix_fk_name(match):
        name = match.group(1)
        new_name = truncate_identifier(name)
        if new_name != name:
            print(f"Truncating FK constraint: {name} -> {new_name}")
        return f"name='{new_name}'"

    content = re.sub(r"name=['\"]([^'\"]+_foreign)['\"]", fix_fk_name, content)

    # 4. Patch CheckConstraint names (if any)
    def fix_check_name(match):
        name = match.group(1)
        new_name = truncate_identifier(name)
        if new_name != name:
            print(f"Truncating Check constraint: {name} -> {new_name}")
        return f"name='{new_name}'"

    content = re.sub(r"CheckConstraint\([^,]+,\s*name=['\"]([^'\"]+)['\"]", fix_check_name, content)

    file_path.write_text(content, encoding="utf-8")
    print(f"Successfully patched {file_path}")

if __name__ == "__main__":
    patch_models_identifiers(Path("models_pg.py"))
