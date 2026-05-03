#!/usr/bin/env python3
"""
Usage:
    python scripts/04_split_models.py models_pg.py -o models

Description:
    Splits a monolithic SQLAlchemy models file (like models_pg.py) into multiple files,
    one per class, and places them into the specified output directory.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

COMMON_IMPORTS = '''from __future__ import annotations

from .base import Base
from typing import Optional
import datetime
import decimal
import enum
from sqlalchemy import BigInteger, Boolean, CHAR, Column, DECIMAL, Date, DateTime, Enum, Float, ForeignKeyConstraint, Index, Integer, JSON, SmallInteger, String, TIMESTAMP, Table, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
'''

BASE_FILE = '''from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
'''


def get_source_segment(lines, node):
    start = node.lineno - 1
    end = node.end_lineno
    return "".join(lines[start:end])


def split_file(src: Path, out_dir: Path) -> None:
    text = src.read_text(encoding="utf-8")
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "base.py").write_text(BASE_FILE, encoding="utf-8")

    enums = []
    classes = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bases = [getattr(b, 'id', None) or getattr(getattr(b, 'func', None), 'id', None) for b in node.bases]
            segment = get_source_segment(lines, node)
            if 'enum.Enum' in segment:
                enums.append((node.name, segment))
            elif 'Base' in bases or '(Base)' in segment:
                classes.append((node.name, segment))

    init_exports = []
    enum_text = "\n\n".join(seg for _, seg in enums)

    for class_name, segment in classes:
        file_name = []
        for i, ch in enumerate(class_name):
            if i > 0 and ch.isupper() and class_name[i-1].islower():
                file_name.append('_')
            file_name.append(ch.lower())
        module_name = ''.join(file_name)
        body = COMMON_IMPORTS
        if enum_text:
            body += "\n\n" + enum_text + "\n"
        body += "\n\n" + segment + "\n"
        (out_dir / f"{module_name}.py").write_text(body, encoding="utf-8")
        init_exports.append((module_name, class_name))

    init_lines = ["from .base import Base\n"]
    for module_name, class_name in init_exports:
        init_lines.append(f"from .{module_name} import {class_name}\n")
    init_lines.append("\n__all__ = [\n    'Base',\n")
    for _, class_name in init_exports:
        init_lines.append(f"    '{class_name}',\n")
    init_lines.append("]\n")
    (out_dir / "__init__.py").write_text("".join(init_lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split a single SQLAlchemy models file into per-class modules")
    parser.add_argument("input", help="Path to models_pg.py")
    parser.add_argument("-o", "--output-dir", default="models", help="Target directory")
    args = parser.parse_args()
    split_file(Path(args.input), Path(args.output_dir))
