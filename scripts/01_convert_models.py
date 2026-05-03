#!/usr/bin/env python3
"""
Usage:
    python scripts/01_convert_models.py models.py -o models_pg.py

Description:
    Converts a MySQL-oriented SQLAlchemy models.py file into a PostgreSQL-friendly models_pg.py.
    It replaces MySQL dialects, types (like LONGTEXT), and strips incompatible keywords.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


MYSQL_IMPORT_RE = re.compile(
    r"from\s+sqlalchemy\.dialects\.mysql\s+import\s+[^\n]+\n",
    re.MULTILINE,
)

BASE_SQLA_IMPORT_RE = re.compile(
    r"from\s+sqlalchemy\s+import\s+([^\n]+)\n",
    re.MULTILINE,
)

BOOL_NAME_RE = re.compile(
    r"""(?ix)
    ^
    (
        is_[a-z0-9_]+ |
        has_[a-z0-9_]+ |
        can_[a-z0-9_]+ |
        should_[a-z0-9_]+ |
        was_[a-z0-9_]+ |
        formenabled |
        isactive | is_active |
        isarchived | is_archived |
        iswarning | is_warning |
        isstarted | is_started |
        isfinished | is_finished |
        isrevoked | is_revoked |
        isclosed | is_closed |
        iscompleted | is_completed |
        isactivated | is_activated |
        isdefault | is_default |
        isservice | is_service |
        isrealtimeanalyze | is_realtime_analyze |
        ispostanalyze | is_post_analyze |
        ispersonal | is_personal |
        isnative | is_native |
        ismain | is_main |
        iscustomer | is_customer |
        revoked |
        deleted |
        archived |
        active |
        visible |
        public |
        primary |
        result |
        statusflag |
        enabled
    )
    $
    """
)

SMALLINT_NAME_RE = re.compile(
    r"""(?ix)
    ^
    (
        percent |
        percentage |
        score |
        rating |
        weight |
        priority |
        level |
        attempt |
        tries |
        quantitysmall |
        sort |
        ordering |
        position |
        deliverytime |
        resultcode
    )
    $
    """
)


def ensure_sqlalchemy_imports(text: str) -> str:
    m = BASE_SQLA_IMPORT_RE.search(text)
    needed = {
        "Boolean",
        "SmallInteger",
        "Integer",
        "BigInteger",
        "String",
        "Text",
        "Float",
        "DateTime",
        "Enum",
        "JSON",
        "text",
        "func",
    }

    if not m:
        imports = "from sqlalchemy import " + ", ".join(sorted(needed)) + "\n"
        return imports + text

    current = {x.strip() for x in m.group(1).split(",")}
    merged = sorted(current | needed)
    new_line = "from sqlalchemy import " + ", ".join(merged) + "\n"
    return text[:m.start()] + new_line + text[m.end():]


def replace_mysql_imports(text: str) -> str:
    text = MYSQL_IMPORT_RE.sub("", text)
    return ensure_sqlalchemy_imports(text)


def strip_mysql_kwargs(text: str) -> str:
    patterns = [
        r",\s*charset\s*=\s*'[^']*'",
        r',\s*charset\s*=\s*"[^"]*"',
        r",\s*collation\s*=\s*'[^']*'",
        r',\s*collation\s*=\s*"[^"]*"',
        r",\s*ascii\s*=\s*(?:True|False)",
        r",\s*unicode\s*=\s*(?:True|False)",
        r",\s*national\s*=\s*(?:True|False)",
        r",\s*binary\s*=\s*(?:True|False)",
        r",\s*unsigned\s*=\s*(?:True|False)",
        r"\(unsigned\s*=\s*(?:True|False)",
    ]
    for p in patterns:
        if p.startswith(r"\("):
             text = re.sub(p, "(", text)
        else:
             text = re.sub(p, "", text)
    return text


def normalize_timestamp_types(text: str) -> str:
    text = re.sub(r"\bTIMESTAMP\s*\(\s*fsp\s*=\s*\d+\s*\)", "DateTime", text)
    text = re.sub(r"\bTIMESTAMPfsp\d+\b", "DateTime", text)
    text = re.sub(r"\bTIMESTAMP\b", "DateTime", text)
    return text


def replace_mysql_types(text: str) -> str:
    replacements = [
        (r"\bLONGTEXT\b", "Text"),
        (r"\bMEDIUMTEXT\b", "Text"),
        (r"\bTEXT\b", "Text"),
        (r"\bVARCHAR\b", "String"),
        (r"\bCHAR\b", "String"),
        (r"\bDOUBLE\s*\(", "Float("),
        (r"\bDOUBLE\b", "Float"),
        (r"\bDECIMAL\b", "Float"),
        (r"\bINTEGER\s*\(", "Integer("),
        (r"\bINTEGER\b", "Integer"),
        (r"\bBIGINT\s*\(", "BigInteger("),
        (r"\bBIGINT\b", "BigInteger"),
        (r"\bENUM\b", "Enum"),
    ]
    for p, rpl in replacements:
        text = re.sub(p, rpl, text)
    text = normalize_timestamp_types(text)
    return text


def convert_string_collation_style(text: str) -> str:
    text = re.sub(r"String\((\d+)\s*,\s*'[^']+'\)", r"String(\1)", text)
    text = re.sub(r'String\((\d+)\s*,\s*"[^"]+"\)', r"String(\1)", text)
    text = re.sub(r"Text\(\s*\)", "Text", text)
    text = re.sub(r"String\(\s*\)", "String", text)
    return text


def normalize_server_defaults(text: str) -> str:
    text = re.sub(
        r"server_default\s*=\s*text\(\s*'CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'\s*\)",
        "server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now()",
        text,
    )
    text = re.sub(
        r'server_default\s*=\s*text\(\s*"CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"\s*\)',
        "server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now()",
        text,
    )
    return text


def replace_mapped_inner_type(line: str, new_inner: str) -> str:
    return re.sub(r"Mapped\[[^\]]+\]", f"Mapped[{new_inner}]", line, count=1)


def patch_tinyint_line(line: str) -> str:
    if "mapped_column(" not in line:
        return line
    if not re.search(r"\bTINYINT(?:\s*\(\s*1\s*\)|1)?\b", line):
        return line

    m = re.search(
        r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*Mapped\[([^\]]+)\]\s*=\s*mapped_column\(",
        line,
    )
    if not m:
        line = re.sub(r"\bTINYINT\s*\(\s*1\s*\)", "Boolean", line)
        line = re.sub(r"\bTINYINT1\b", "Boolean", line)
        line = re.sub(r"\bTINYINT\b", "SmallInteger", line)
        return line

    field_name, mapped_inner = m.groups()
    is_optional = "Optional[" in mapped_inner or "| None" in mapped_inner

    if BOOL_NAME_RE.search(field_name):
        new_inner = "Optional[bool]" if is_optional else "bool"
        line = replace_mapped_inner_type(line, new_inner)
        line = re.sub(r"\bTINYINT\s*\(\s*1\s*\)", "Boolean", line)
        line = re.sub(r"\bTINYINT1\b", "Boolean", line)
        line = re.sub(r"\bTINYINT\b", "Boolean", line)
        line = re.sub(r"server_default\s*=\s*text\((['\"])0\1\)", "server_default=text('false')", line)
        line = re.sub(r"server_default\s*=\s*text\((['\"])1\1\)", "server_default=text('true')", line)
    else:
        new_inner = "Optional[int]" if is_optional else "int"
        line = replace_mapped_inner_type(line, new_inner)
        line = re.sub(r"\bTINYINT\s*\(\s*1\s*\)", "SmallInteger", line)
        line = re.sub(r"\bTINYINT1\b", "SmallInteger", line)
        line = re.sub(r"\bTINYINT\b", "SmallInteger", line)

    return line


def convert_tinyints(text: str) -> str:
    out = []
    for line in text.splitlines():
        out.append(patch_tinyint_line(line))
    text = "\n".join(out) + "\n"
    return text


def cleanup_artifacts(text: str) -> str:
    text = re.sub(r"\bInteger\(\)", "Integer", text)
    text = re.sub(r"\bBigInteger\(\)", "BigInteger", text)
    text = re.sub(r"\bBoolean\(\)", "Boolean", text)
    text = re.sub(r"\bSmallInteger\(\)", "SmallInteger", text)
    text = re.sub(r"\bDateTime\(\)", "DateTime", text)
    text = re.sub(r"\bFloat\(\)", "Float", text)
    text = re.sub(r"\bText\(([^\)]*charset[^\)]*)\)", "Text", text)
    text = re.sub(r"\bText\(([^\)]*collation[^\)]*)\)", "Text", text)
    text = re.sub(r"\bString\((\d+)\s*,\s*\)", r"String(\1)", text)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"\(\s*,", "(", text)
    text = re.sub(r",\s*\)", ")", text)
    text = re.sub(r"\bInteger\(unsigned=True\)", "Integer", text)
    text = re.sub(r"\bBigInteger\(unsigned=True\)", "BigInteger", text)
    text = re.sub(r"\bSmallInteger\(unsigned=True\)", "SmallInteger", text)
    text = re.sub(r"\bFloat\(unsigned=True\)", "Float", text)
    text = re.sub(r"\btext\(\s*'false'\s*\)", "text('false')", text)
    text = re.sub(r"\btext\(\s*'true'\s*\)", "text('true')", text)
    return text


def add_header(text: str, source_name: str) -> str:
    banner = (
        '"""\n'
        f"Auto-converted from {source_name}.\n\n"
        "This file was transformed from a MySQL-oriented SQLAlchemy model file\n"
        "into a PostgreSQL-friendly version. Manual review is still required for:\n"
        "- boolean vs smallint semantics\n"
        "- enum naming and native postgres enums\n"
        "- identifier names over 63 chars\n"
        "- unsigned constraints/check constraints\n"
        "- server defaults and triggers\n"
        "- composite primary keys and indexes\n"
        '"""\n\n'
    )
    return banner + text


def convert(source: Path, target: Path) -> None:
    text = source.read_text(encoding="utf-8")

    text = replace_mysql_imports(text)
    text = replace_mysql_types(text)
    text = strip_mysql_kwargs(text)
    text = convert_string_collation_style(text)
    text = normalize_server_defaults(text)
    text = convert_tinyints(text)
    text = cleanup_artifacts(text)
    text = add_header(text, source.name)

    target.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert MySQL-oriented SQLAlchemy models.py into PostgreSQL-friendly models file"
    )
    parser.add_argument("input", help="Path to source models.py")
    parser.add_argument("-o", "--output", default="models_pg.py", help="Output file path")
    args = parser.parse_args()

    convert(Path(args.input), Path(args.output))


if __name__ == "__main__":
    main()