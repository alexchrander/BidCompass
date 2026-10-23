"""Review the extracted tender data one row at a time, with the supporting quote shown.

Works on both master tables in data/processed (build them first with extract.build_requirements):
    tender_requirements.csv   alvará requirements
    tender_terms.csv          other terms (price, deadlines, guarantees, award, technical, financial, eligibility)
Goes tender by tender: that tender's alvará rows first, then its terms.

For each row with status 'unreviewed' you choose:
    c  confirm   the row is correct as extracted
    e  edit      fix the content (class rule / value / unit / detail), recorded as 'corrected'
    r  reject    the row is not in the tender (wrong extraction)
    s  skip      decide later
    a  add       something the LLM missed for this tender
    q  quit      (progress is saved after every answer)

Quotes are shown in Portuguese and in English (python -m extract.translate), with a check that the quote
appears verbatim in the source file.

Run: python -m eval.review_requirements [8844-2026 ...] [--only requirements|terms] [--reviewer NAME] [--all]
     --all also shows rows that are already reviewed.
"""

from __future__ import annotations

import argparse
import getpass
import json
import re
from datetime import datetime

import pandas as pd

from extract.build_requirements import COLUMNS, PROMPT_FILE, REQ_CSV, TERMS_COLUMNS, TERMS_CSV, load_cache
from ingest.common import RAW_DIR
from extract.reference import REFERENCE

CLASS_RULES = {"g": "global_value", "w": "work_value", "n": "not_stated", "x": "explicit_class"}
TERM_FIELDS: dict[str, dict[str, str]] = json.loads(PROMPT_FILE.read_text(encoding="utf-8"))["term_fields"]
FIELD_MEANING = {f: m for fields in TERM_FIELDS.values() for f, m in fields.items()}
FIELD_GROUP = {f: g for g, fields in TERM_FIELDS.items() for f in fields}


def subcategory_names() -> dict[str, str]:
    text = REFERENCE.read_text(encoding="utf-8")
    return {code: name.strip() for code, name in re.findall(r"^\|\s*(\d+\.\d+)\s*\|\s*([^|]+?)\s*\|", text, re.M)}


SUBCATEGORIES = subcategory_names()
TRANSLATIONS = load_cache()


def english(text: str) -> str:
    """English for a Portuguese string, empty when there is none (numbers, yes/no)."""
    return "" if re.fullmatch(r"[a-z]+(_[a-z]+)+", text) else TRANSLATIONS.get(text, "")


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_check(row: pd.Series) -> str:
    """Is the quote really in the source file?"""
    path = RAW_DIR / "dre" / row["nAnuncio"] / "pecas" / "text" / row["source_file"]
    if not row["quote"] or not path.exists():
        return "source file not found"
    return "quote found in source file" if squash(row["quote"]) in squash(path.read_text(encoding="utf-8", errors="ignore")) \
        else "WARNING: quote NOT found verbatim in source file"


def keep(prompt: str, current: str) -> str:
    """Ask for a new value; empty input keeps the current one, '-' clears it."""
    answer = input(f"  {prompt} [{current or '-'}]: ").strip()
    return current if answer == "" else ("" if answer == "-" else answer)


# Alvará requirements

def show_requirement(row: pd.Series) -> None:
    print(f"  {row['code']}  {SUBCATEGORIES.get(row['code'], '?')}")
    print(f"  class_rule={row['class_rule']} class_number={row['class_number'] or '-'} "
          f"determinant={row['determinant']} alt_group={row['alternative_group'] or '-'}")


def edit_requirement(row: pd.Series) -> None:
    choice = input("  class rule [g=global_value, w=work_value, x=explicit_class, n=not_stated, enter=keep]: ").strip().lower()
    if choice in CLASS_RULES:
        row["class_rule"] = CLASS_RULES[choice]
    row["class_number"] = input("  class number (1-9): ").strip() if row["class_rule"] == "explicit_class" else ""
    det = input("  determinant? [y/n/enter=keep]: ").strip().lower()
    if det in ("y", "n"):
        row["determinant"] = str(det == "y")
    row["alternative_group"] = keep("alternative group", row["alternative_group"])


def new_requirement(tender: str) -> pd.Series:
    row = pd.Series({c: "" for c in COLUMNS})
    row["nAnuncio"] = tender
    row["code"] = input("  code (e.g. 4.12): ").strip()
    row["category"], row["subcategory"] = row["code"].split(".")
    row["lot"] = input("  lot (enter=none): ").strip()
    row["class_rule"], row["determinant"] = "not_stated", "False"
    edit_requirement(row)
    return row


# Other terms

def show_term(row: pd.Series) -> None:
    print(f"  {row['group']} / {row['field']}  ({FIELD_MEANING.get(row['field'], '?')})")
    print(f"  value={row['value'] or '-'}  unit={row['unit'] or '-'}  detail={row['detail'] or '-'}")
    translated = [f"{label}: {english(row[col])}" for label, col in (("value", "value"), ("detail", "detail")) if english(row[col])]
    if translated:
        print("  in English  " + "   ".join(translated))


def edit_term(row: pd.Series) -> None:
    row["value"] = keep("value", row["value"])
    row["unit"] = keep("unit", row["unit"])
    row["detail"] = keep("detail", row["detail"])


def new_term(tender: str) -> pd.Series:
    row = pd.Series({c: "" for c in TERMS_COLUMNS})
    row["nAnuncio"] = tender
    print("  fields: " + ", ".join(FIELD_MEANING))
    while row["field"] not in FIELD_MEANING:
        row["field"] = input("  field: ").strip()
    row["group"] = FIELD_GROUP[row["field"]]
    row["lot"] = input("  lot (enter=none): ").strip()
    edit_term(row)
    return row


TABLES = {
    "requirements": {"path": REQ_CSV, "show": show_requirement, "edit": edit_requirement, "new": new_requirement},
    "terms": {"path": TERMS_CSV, "show": show_term, "edit": edit_term, "new": new_term},
}


def stamp(row: pd.Series, status: str, reviewer: str, note: str = "") -> None:
    row["status"], row["reviewer"] = status, reviewer
    row["reviewed_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    if note:
        row["review_note"] = note


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tenders", nargs="*")
    parser.add_argument("--only", choices=list(TABLES))
    parser.add_argument("--reviewer", default=getpass.getuser())
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    frames = {name: pd.read_csv(t["path"], dtype=str, keep_default_na=False) for name, t in TABLES.items()
              if args.only in (None, name)}
    known = set().union(*(set(df["nAnuncio"]) for df in frames.values()))
    unknown = [t for t in args.tenders if t not in known]
    if unknown:
        parser.error(f"unknown tender id(s): {', '.join(unknown)} "
                     "(if a --reviewer name has a space, put it in quotes)")
    todo = []  # (tender, table order, row index, table name)
    for order, (name, df) in enumerate(frames.items()):
        for i in df.index[(df["status"] == "unreviewed") | args.all]:
            if not args.tenders or df.at[i, "nAnuncio"] in args.tenders:
                todo.append((df.at[i, "nAnuncio"], order, i, name))
    todo.sort(key=lambda x: x[:3])
    print(f"{len(todo)} rows to review as '{args.reviewer}'")

    def save(name: str) -> None:
        frames[name].to_csv(TABLES[name]["path"], index=False)

    for pos, (tender, _, i, name) in enumerate(todo, 1):
        table, df = TABLES[name], frames[name]
        row = df.loc[i].copy()
        print(f"\n[{pos}/{len(todo)}] {tender}  {name}  lot: {row['lot'] or '-'}  status: {row['status']}")
        table["show"](row)
        print(f"  quote (PT): {row['quote']}")
        print(f"  quote (EN): {row.get('quote_en') or english(row['quote']) or '(no translation)'}")
        print(f"  file: {row['source_file']}  [{quote_check(row)}]")
        while True:
            ans = input("  [c]onfirm / [e]dit / [r]eject / [s]kip / [a]dd / [q]uit > ").strip().lower()
            if ans == "c":
                stamp(row, "confirmed", args.reviewer)
            elif ans == "e":
                table["edit"](row)
                stamp(row, "corrected", args.reviewer, input("  note: ").strip())
            elif ans == "r":
                stamp(row, "rejected", args.reviewer, input("  note: ").strip())
            elif ans == "a":
                kind = name
                if args.only is None:
                    kind = "terms" if input("  add to [r]equirements or [t]erms? ").strip().lower().startswith("t") else "requirements"
                if kind not in frames:
                    frames[kind] = pd.read_csv(TABLES[kind]["path"], dtype=str, keep_default_na=False)
                new = TABLES[kind]["new"](tender)
                new["quote"] = input("  quote from the document: ").strip()
                new["source_file"] = input("  source file: ").strip()
                new["extraction_method"] = "manual"
                new["extracted_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                stamp(new, "added", args.reviewer, input("  note: ").strip())
                frames[kind] = pd.concat([frames[kind], new.to_frame().T], ignore_index=True)
                save(kind)
                continue
            elif ans == "s":
                break
            elif ans == "q":
                for n in frames:
                    save(n)
                return
            else:
                continue
            frames[name].loc[i] = row
            save(name)
            break
    for n in frames:
        save(n)
    print("done")


if __name__ == "__main__":
    main()
