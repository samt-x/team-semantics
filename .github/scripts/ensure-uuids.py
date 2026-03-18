#!/usr/bin/env python3
"""ensure-uuids.py

Sikrer at alle _index.nb.md / _index.en.md-par i content/
har ett felles UUID i frontmatter-feltet 'id'.

Logikk per par:
  - Begge har samme UUID        → ok, ingenting gjøres
  - nb har UUID, en mangler     → kopier UUID fra nb til en
  - en har UUID, nb mangler     → kopier UUID fra en til nb
  - Ingen av dem har UUID       → generer ny UUID, sett begge
  - Forskjellige UUID-er        → bruk nb som fasit, skriv til en (advarsel)

Kjøres av GitHub Actions ved push til main.
"""

import os
import re
import sys
import uuid

CONTENT_DIR = "content"

# Matcher en gyldig UUID-verdi på en id:-linje
_UUID_RE = re.compile(
    r'^id:\s*["\']?'
    r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
    r'["\']?\s*$',
    re.MULTILINE | re.IGNORECASE,
)

# Matcher en hvilken som helst id:-linje (for erstatning)
_ID_LINE_RE = re.compile(r'^id:.*$', re.MULTILINE)

# Matcher YAML-frontmatter-blokk (mellom --- og ---)
_FM_RE = re.compile(r'\A---\n(.*?)\n---\n', re.DOTALL)


def _split(content):
    """Splitter fil i (frontmatter_str, body_str). Returnerer (None, content) hvis ingen frontmatter."""
    m = _FM_RE.match(content)
    return (m.group(1), content[m.end():]) if m else (None, content)


def get_uuid(content):
    """Leser UUID fra frontmatter. Returnerer None hvis ikke funnet."""
    if not content:
        return None
    fm, _ = _split(content)
    m = _UUID_RE.search(fm or "")
    return m.group(1).lower() if m else None


def set_uuid(path, uid, content):
    """Skriver UUID til frontmatter og lagrer filen."""
    fm, body = _split(content)
    if fm is None:
        # Ingen frontmatter – legg til
        new_content = f"---\nid: {uid}\n---\n{content}"
    elif _ID_LINE_RE.search(fm):
        # Erstatt eksisterende id:-linje
        new_fm = _ID_LINE_RE.sub(f"id: {uid}", fm, count=1)
        new_content = f"---\n{new_fm}\n---\n{body}"
    else:
        # Sett inn id som første felt i frontmatter
        new_content = f"---\nid: {uid}\n{fm}\n---\n{body}"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)


def main():
    if not os.path.isdir(CONTENT_DIR):
        print(f"FEIL: Finner ikke '{CONTENT_DIR}'-mappe", file=sys.stderr)
        sys.exit(1)

    changed = []
    warnings = []

    for root, _dirs, files in os.walk(CONTENT_DIR):
        if "_index.nb.md" not in files:
            continue

        nb = os.path.join(root, "_index.nb.md")
        en = os.path.join(root, "_index.en.md")

        try:
            nb_txt = open(nb, encoding="utf-8").read()
        except OSError as e:
            print(f"  FEIL ved lesing av {nb}: {e}", file=sys.stderr)
            continue

        try:
            en_txt = open(en, encoding="utf-8").read()
            en_exists = True
        except FileNotFoundError:
            en_txt = None
            en_exists = False

        nb_id = get_uuid(nb_txt)
        en_id = get_uuid(en_txt)

        if nb_id and en_id:
            if nb_id != en_id:
                warnings.append(
                    f"  ⚠  UUID-konflikt i {root}\n"
                    f"       nb: {nb_id}\n"
                    f"       en: {en_id}\n"
                    f"       → bruker nb som fasit"
                )
                set_uuid(en, nb_id, en_txt)
                changed.append(en)
            # else: begge ok

        elif nb_id and en_exists:
            # en mangler UUID – kopier fra nb
            set_uuid(en, nb_id, en_txt)
            changed.append(en)
            print(f"  + Kopiert UUID til en: {en}")

        elif en_id:
            # nb mangler UUID – kopier fra en
            set_uuid(nb, en_id, nb_txt)
            changed.append(nb)
            print(f"  + Kopiert UUID til nb: {nb}")

        else:
            # Ingen av dem har UUID – generer ny
            new_id = str(uuid.uuid4())
            set_uuid(nb, new_id, nb_txt)
            changed.append(nb)
            print(f"  + Ny UUID: {root}")
            if en_exists:
                set_uuid(en, new_id, en_txt)
                changed.append(en)

    for w in warnings:
        print(w)

    if changed:
        print(f"\n✔ Oppdaterte {len(changed)} fil(er) med UUID")
    else:
        print("✔ Alle UUID-er er på plass – ingen endringer")


if __name__ == "__main__":
    main()
