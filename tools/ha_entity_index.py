#!/usr/bin/env python3
"""
HA Entity Index – generiert eine Markdown-Übersicht aller in den YAML-Paketen definierten
Entitäten & Helper (input_*), inkl. Quelle (Datei) und Basis-Infos.

Nutzung:
  python3 tools/ha_entity_index.py /config/packages  > ENTITY_INDEX.md
  # oder (bei dir):
  python3 tools/ha_entity_index.py /homeassistant/packages > ENTITY_INDEX.md

Unterstützt:
- input_number, input_boolean, input_text, input_datetime, input_select, input_button
- utility_meter (sensor.<meter_name>, inkl. cycle, source)
- template: sensor/binary_sensor/switch/... (Entity-ID aus name → slug)
- einfache Mehrdokument-YAMLs

Keine externen Libraries nötig.
"""
import sys, re, os, datetime, io
from typing import Any, Dict, List, Tuple, Union
import yaml

DOMAINS_HELPERS = [
    "input_number","input_boolean","input_text","input_datetime","input_select","input_button"
]
TEMPLATE_KEYS = ["sensor","binary_sensor","switch","number","button","select","text","binary"]
# Datei-Endungen
YAML_EXT = (".yaml",".yml")

def slugify(name: str) -> str:
    # nahe an HA: klein, umlaute ersetzen, alles Nicht-[a-z0-9_] zu "_", mehrfach "_" zusammenfassen
    s = name.strip().lower()
    # deutsche Umlaute / ß
    s = (s.replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss"))
    # Leerzeichen / Sonderzeichen
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def read_yaml(path: str) -> List[Dict[str, Any]]:
    docs: List[Dict[str,Any]] = []
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            content = f.read()
        for doc in yaml.safe_load_all(content):
            if isinstance(doc, dict):
                docs.append(doc)
    except Exception as e:
        # still include a marker so you notice broken files
        docs.append({"__read_error__": str(e)})
    return docs

def collect_from_helpers(doc: Dict[str,Any], file: str, out: Dict[str,List[Dict[str,Any]]]):
    for dom in DOMAINS_HELPERS:
        section = doc.get(dom)
        if isinstance(section, dict):
            for key, cfg in section.items():
                out.setdefault(dom,[]).append({
                    "entity_id": f"{dom}.{key}",
                    "name": cfg.get("name"),
                    "unit": cfg.get("unit_of_measurement"),
                    "file": file
                })

def collect_from_utility_meter(doc: Dict[str,Any], file: str, out: Dict[str,List[Dict[str,Any]]]):
    um = doc.get("utility_meter")
    if isinstance(um, dict):
        for meter_name, cfg in um.items():
            if not isinstance(cfg, dict): 
                continue
            out.setdefault("sensor",[]).append({
                "entity_id": f"sensor.{meter_name}",
                "name": meter_name.replace("_"," ").title(),
                "unit": "kWh",  # utility_meter ist Energie
                "extra": f"utility_meter | cycle={cfg.get('cycle')} | source={cfg.get('source')}",
                "file": file
            })

def _collect_template_block(domain: str, block: Any, file: str, out: Dict[str,List[Dict[str,Any]]]):
    if isinstance(block, list):
        for entry in block:
            if isinstance(entry, dict):
                name = entry.get("name") or entry.get("unique_id") or ""
                # Wenn "name" leer → überspringen
                if not name:
                    continue
                ent = f"{domain}.{slugify(name)}"
                out.setdefault(domain,[]).append({
                    "entity_id": ent,
                    "name": name,
                    "unit": entry.get("unit_of_measurement"),
                    "extra": "template",
                    "file": file
                })

def collect_from_template(doc: Dict[str,Any], file: str, out: Dict[str,List[Dict[str,Any]]]):
    tpl = doc.get("template")
    if isinstance(tpl, list):
        for tpl_doc in tpl:
            if not isinstance(tpl_doc, dict): 
                continue
            for key, val in tpl_doc.items():
                # key kann "sensor", "binary_sensor", ...
                if key in TEMPLATE_KEYS:
                    _collect_template_block(key, val, file, out)

def scan_paths(paths: List[str]) -> Dict[str,List[Dict[str,Any]]]:
    out: Dict[str,List[Dict[str,Any]]] = {}
    for base in paths:
        for root, _, files in os.walk(base):
            for fn in files:
                if fn.endswith(YAML_EXT):
                    p = os.path.join(root, fn)
                    for doc in read_yaml(p):
                        if "__read_error__" in doc:
                            out.setdefault("__errors__",[]).append({
                                "file": p, "error": doc["__read_error__"]
                            })
                            continue
                        collect_from_helpers(doc, p, out)
                        collect_from_utility_meter(doc, p, out)
                        collect_from_template(doc, p, out)
    return out

def md_header(paths: List[str]) -> str:
    now = datetime.datetime.now().isoformat(timespec="seconds")
    roots = ", ".join(paths)
    return (
f"# Home Assistant – Entity Index (generiert)\n\n"
f"- Stand: **{now}**\n"
f"- Quellen: `{roots}`\n"
f"- Enthalten: **Helper** (input_*), **utility_meter** (sensor.*), **template-Entities** (sensor/binary_sensor/...)\n\n"
"---\n"
)

def md_section(domain: str, entries: List[Dict[str,Any]]) -> str:
    lines = [f"## {domain}\n"]
    # Sortierung nach entity_id
    entries = sorted(entries, key=lambda x: x.get("entity_id",""))
    for e in entries:
        unit = f" `{e.get('unit')}`" if e.get("unit") else ""
        extra = f" — {e.get('extra')}" if e.get("extra") else ""
        lines.append(f"- **{e['entity_id']}**{unit} — *{e.get('name','') or ''}*{extra}  \n  `Quelle:` {e['file']}")
    lines.append("")  # Leerzeile
    return "\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: ha_entity_index.py <dir1> [<dir2> ...]", file=sys.stderr)
        sys.exit(2)
    paths = sys.argv[1:]
    data = scan_paths(paths)
    md = [md_header(paths)]
    for domain in sorted([k for k in data.keys() if not k.startswith("__")]):
        md.append(md_section(domain, data[domain]))
    # Fehler am Ende
    if "__errors__" in data:
        md.append("## Lesefehler\n")
        for err in data["__errors__"]:
            md.append(f"- {err['file']}: {err['error']}")
        md.append("")
    sys.stdout.write("\n".join(md))

if __name__ == "__main__":
    main()
