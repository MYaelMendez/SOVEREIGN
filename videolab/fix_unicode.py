#!/usr/bin/env python3
"""Fix all non-ASCII characters in conductor.py that cause SyntaxError.
Pure ASCII script - uses \\u escapes to avoid encoding issues."""
import re

path = r"C:\æ\hermes-fork\hermes_cli\conductor.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace all non-ASCII chars with ASCII equivalents
replacements = {
    "\u00b2": "^2", "\u00b3": "^3", "\u2192": "->", "\u2190": "<-",
    "\u2014": "-", "\u2013": "-", "\u2026": "...", "\u2022": "*",
    "\u00d7": "x", "\u00f7": "/", "\u2264": "<=", "\u2265": ">=",
    "\u2260": "!=", "\u2248": "~", "\u00b1": "+/-",
    "\u221e": "inf", "\u221a": "sqrt", "\u222b": "int",
    "\u2211": "sum", "\u220f": "prod",
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u00a0": " ",
}

for old, new in replacements.items():
    content = content.replace(old, new)

# Catch any remaining non-ASCII chars
def replace_nonascii(m):
    ch = m.group(0)
    if ch in "\n\r\t":
        return ch
    return "?"

content = re.sub(r"[^\x00-\x7f]", replace_nonascii, content)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed all non-ASCII characters in conductor.py")
