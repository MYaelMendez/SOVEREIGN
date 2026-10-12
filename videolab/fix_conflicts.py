#!/usr/bin/env python3
"""Resolve git merge conflict markers in conductor.py.
Keeps the HEAD version (first side) of each conflict."""
import re

path = r"C:\æ\hermes-fork\hermes_cli\conductor.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Pattern: <<<<<<< HEAD\n(head)\n=======\n(other)\n>>>>>>> branch
pattern = re.compile(
    r"<<<<<<< HEAD\n(.*?)\n=======\n.*?>>>>>>> [^\n]+\n",
    re.DOTALL,
)

def keep_head(m):
    return m.group(1) + "\n"

new_content, count = pattern.subn(keep_head, content)

with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"Resolved {count} merge conflicts (kept HEAD side)")
