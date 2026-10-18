"""Build a clean tender pool from the raw Portal BASE announcements (anuncios).

Source: data/raw/base/anuncios_<year>/anuncios<year>.json for 2025 and 2026, downloaded with
`python -m ingest.base anuncios 2025 2026`. Each record is a public procurement notice: buyer,
description, base price, CPV codes, bid deadline and links to the tender documents.
Output: data/processed/tenders.parquet, one row per IdIncm. A procedure and its rectification
have different IdIncm, so both are kept; has_amendment marks procedures that share their nAnuncio
with a non-procedure row. Remaining IdIncm duplicates are resolved by: is_procedure, non-empty url,
latest dataPublicacao.
IdIncm "-1" is a placeholder (306 rows); those rows are deduplicated on nAnuncio + tipoActo instead.

Flag columns:
- is_procedure:    tipoActo == "Anúncio de procedimento" (amendments and other notices are False)
- is_works_type:   tiposContrato contains "Empreitadas de obras públicas"
- has_cpv45:       any CPV code starts with "45" (construction work)
- is_construction: is_works_type OR has_cpv45 (the union of both rules)
- is_open:         DataLimitePropostas >= today
- has_amendment:   procedure whose nAnuncio is shared with a non-procedure row
- price_band:      "<=200k", "200k-400k", "400k-800k", "800k-1M", ">1M" or "unknown"
                   (upper bounds inclusive, e.g. exactly 200,000 is "<=200k")

Run: python -m ingest.tenders
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "base"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "tenders.parquet"
YEARS = (2025, 2026)
WORKS_TYPE = "Empreitadas de obras públicas"
CPV_CODE_RE = re.compile(r"^\s*(\d{8})")


def load_raw(years: tuple[int, ...] = YEARS) -> pd.DataFrame:
    frames = []
    for year in years:
        path = RAW_DIR / f"anuncios_{year}" / f"anuncios{year}.json"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found. Run: python -m ingest.base anuncios {year}")
        frames.append(pd.DataFrame(json.loads(path.read_text(encoding="utf-8"))))
    return pd.concat(frames, ignore_index=True)


def _as_list(value) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def _clean_text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).map(html.unescape).str.strip()


def _cpv_codes(cpvs) -> list[str]:
    codes = []
    for item in _as_list(cpvs):
        match = CPV_CODE_RE.match(str(item))
        if match:
            codes.append(match.group(1))
    return codes


def _price_band(price: float) -> str:
    if pd.isna(price):
        return "unknown"
    if price <= 200_000:
        return "<=200k"
    if price <= 400_000:
        return "200k-400k"
    if price <= 800_000:
        return "400k-800k"
    if price <= 1_000_000:
        return "800k-1M"
    return ">1M"


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["dataPublicacao"] = pd.to_datetime(df["dataPublicacao"], format="%d/%m/%Y", errors="coerce")
    df["DataLimitePropostas"] = pd.to_datetime(df["DataLimitePropostas"], format="%d/%m/%Y", errors="coerce")

    df["nAnuncio"] = df["nAnuncio"].astype(str).str.strip()
    df["IdIncm"] = df["IdIncm"].fillna("").astype(str).str.strip()
    df["nifEntidade"] = df["nifEntidade"].fillna("").astype(str).str.strip()
    df["url"] = df["url"].fillna("")

    # IdIncm "-1" (or empty) is a placeholder for missing ids: those rows fall back to nAnuncio + tipoActo.
    missing = df["IdIncm"].isin(["", "-1"])
    ids = df.loc[~missing, "IdIncm"]
    print(f"Rows before dedup: {len(df)} | placeholder IdIncm (-1/empty): {int(missing.sum())}")
    print(f"Duplicate IdIncm values (real ids): {int(ids.duplicated().sum())}")
    df["_key"] = df["IdIncm"].where(~missing, "n:" + df["nAnuncio"] + "|" + df["tipoActo"].astype(str))
    # Priority: procedure, non-empty url, latest date (the best row sorts last).
    df["_proc"] = df["tipoActo"] == "Anúncio de procedimento"
    df["_url"] = df["url"].astype(str).str.strip() != ""
    df = df.sort_values(["_proc", "_url", "dataPublicacao"], kind="stable")
    df = df.drop_duplicates("_key", keep="last").drop(columns=["_proc", "_url", "_key"])
    print(f"Rows after dedup: {len(df)}")

    for col in ("designacaoEntidade", "descricaoAnuncio"):
        df[col] = _clean_text(df[col])

    df["PrecoBase"] = pd.to_numeric(df["PrecoBase"], errors="coerce").astype(float)
    df["PrazoPropostas"] = pd.to_numeric(df["PrazoPropostas"], errors="coerce").astype("Int64")

    df["CPVs"] = df["CPVs"].map(_as_list)
    df["cpv_codes"] = df["CPVs"].map(_cpv_codes)
    df["tiposContrato"] = df["tiposContrato"].map(_as_list)

    df["is_procedure"] = df["tipoActo"] == "Anúncio de procedimento"
    df["is_works_type"] = df["tiposContrato"].map(lambda types: any(WORKS_TYPE in str(t) for t in types))
    df["has_cpv45"] = df["cpv_codes"].map(lambda codes: any(c.startswith("45") for c in codes))
    df["is_construction"] = df["is_works_type"] | df["has_cpv45"]
    df["is_open"] = df["DataLimitePropostas"] >= pd.Timestamp.today().normalize()
    df["price_band"] = df["PrecoBase"].map(_price_band)

    has_other = df.assign(_o=~df["is_procedure"]).groupby("nAnuncio")["_o"].transform("any")
    df["has_amendment"] = df["is_procedure"] & has_other
    df = df.sort_values(["dataPublicacao", "nAnuncio"], kind="stable").reset_index(drop=True)
    print(f"Remaining duplicate nAnuncio groups: {int(df['nAnuncio'].duplicated().groupby(df['nAnuncio']).any().sum())}")
    print(f"Procedures with has_amendment: {int(df['has_amendment'].sum())}\n")
    return df


def print_summary(df: pd.DataFrame) -> None:
    df = df.assign(pub_year=df["dataPublicacao"].dt.year)
    construction = df[df["is_construction"]]
    construction_procs = construction[construction["is_procedure"]]

    print(f"Total announcements: {len(df)} | procedures: {int(df['is_procedure'].sum())}")
    print("\nAnnouncements and procedures per year (by publication year):")
    print(df.groupby("pub_year").agg(announcements=("nAnuncio", "size"), procedures=("is_procedure", "sum")))

    print("\nConstruction announcements per year (works type only / CPV 45 only / both):")
    split = pd.DataFrame(
        {
            "works_only": construction["is_works_type"] & ~construction["has_cpv45"],
            "cpv45_only": ~construction["is_works_type"] & construction["has_cpv45"],
            "both": construction["is_works_type"] & construction["has_cpv45"],
            "pub_year": construction["pub_year"],
        }
    )
    print(split.groupby("pub_year").sum().assign(total=lambda t: t.sum(axis=1)))

    print("\nConstruction procedures by modeloAnuncio:")
    print(construction_procs["modeloAnuncio"].value_counts(dropna=False).to_string())

    print("\nConstruction procedures by price band:")
    order = ["<=200k", "200k-400k", "400k-800k", "800k-1M", ">1M", "unknown"]
    print(construction_procs["price_band"].value_counts().reindex(order, fill_value=0).to_string())

    print("\nConstruction procedures published per month in 2026:")
    in_2026 = construction_procs[construction_procs["dataPublicacao"].dt.year == 2026]
    print(in_2026.groupby(in_2026["dataPublicacao"].dt.to_period("M")).size().to_string())

    open_construction = construction[construction["is_open"]]
    print(
        f"\nConstruction tenders currently open: {len(open_construction)} "
        f"(procedures only: {int(open_construction['is_procedure'].sum())})"
    )


def main() -> None:
    df = clean(load_raw())
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_FILE, index=False)
    print(f"Saved {len(df)} rows to {OUTPUT_FILE}\n")
    print_summary(df)


if __name__ == "__main__":
    main()
