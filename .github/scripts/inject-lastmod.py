#!/usr/bin/env python3
"""
Inject lastmod dates into Hugo content frontmatter based on git history.
Run in CI after a commit to persist accurate last-modified timestamps.
Skips bot commits when determining lastmod and last_editor.
"""
import subprocess
import os
import re
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    _OSLO_TZ = ZoneInfo("Europe/Oslo")
except ImportError:
    _OSLO_TZ = None


def get_lastmod(rel_path):
    """Finn timestamp for siste ikke-bot-commit som berørte denne filen."""
    result = subprocess.run(
        ['git', 'log', '--format=%cI|%ae', '--', rel_path],
        capture_output=True, text=True
    )
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        timestamp, _, email = line.partition('|')
        if '[bot]' not in email:
            ts = timestamp.strip()
            if _OSLO_TZ:
                try:
                    return datetime.fromisoformat(ts).astimezone(_OSLO_TZ).isoformat()
                except Exception:
                    pass
            return ts
    return ''


def get_last_human_author(rel_path):
    """Finn siste ikke-bot-commit-autor. Returnerer 'login (navn)' eller 'navn'."""
    result = subprocess.run(
        ['git', 'log', '--format=%aN|%aE', '--', rel_path],
        capture_output=True, text=True
    )
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        name, _, email = line.partition('|')
        if '[bot]' in name or '[bot]' in email:
            continue
        m = re.match(r'^\d+\+(.+)@users\.noreply\.github\.com$', email.strip())
        if m:
            return f'{m.group(1)} ({name.strip()})'
        return name.strip()
    return None


def inject_lastmod(filepath, lastmod, author):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if not content.startswith('---'):
        return False

    end = content.find('\n---', 3)
    if end == -1:
        return False

    frontmatter = content[3:end]
    rest = content[end:]

    if re.search(r'^lastmod:', frontmatter, re.MULTILINE):
        frontmatter = re.sub(r'^lastmod:.*$', f'lastmod: {lastmod}', frontmatter, flags=re.MULTILINE)
    else:
        frontmatter = frontmatter.rstrip('\n') + f'\nlastmod: {lastmod}\n'

    if author:
        existing = re.search(r'^last_editor:\s*(.*)$', frontmatter, re.MULTILINE)
        if existing and '[bot]' not in existing.group(1):
            pass  # behold eksisterende menneskelig verdi
        elif existing:
            frontmatter = re.sub(r'^last_editor:.*$', f'last_editor: {author}', frontmatter, flags=re.MULTILINE)
        else:
            frontmatter = frontmatter.rstrip('\n') + f'\nlast_editor: {author}\n'

    new_content = '---' + frontmatter + rest
    if new_content == content:
        return False

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    return True


changed = 0
for root, dirs, files in os.walk('content'):
    for filename in files:
        if not filename.endswith('.md'):
            continue
        filepath = os.path.join(root, filename)
        rel_path = os.path.relpath(filepath)

        lastmod = get_lastmod(rel_path)
        author = get_last_human_author(rel_path)
        if lastmod:
            if inject_lastmod(filepath, lastmod, author):
                print(f'  {rel_path}: lastmod={lastmod}, last_editor={author}')
                changed += 1

print(f'Oppdaterte {changed} filer.')
