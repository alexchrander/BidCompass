"""Download the tender documents (peças do procedimento) linked from BASE announcements.

Layout, one folder per notice:
    data/raw/dre/<nAnuncio with '-'>/pecas/
        (notice.pdf / notice.txt sit one level up)
        source.json     link, platform, status, HTTP details
        pecas.zip       original download (only if the link returned a zip)
        files/          extracted documents (zip contents or the single file)
        text/           PyMuPDF text for every PDF, mirroring the files/ structure

Run: python -m ingest.pecas 8844/2026 13582/2026 ...   (or --from-csv eval/archive/alvara_prefill.csv --not-yes)
"""

from __future__ import annotations

import argparse
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import pandas as pd
import pymupdf
import requests

from ingest.common import PROJECT_ROOT, RAW_DIR

DRE_DIR = RAW_DIR / "dre"
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def load_links(year: int = 2026) -> dict[str, str]:
    files = sorted((RAW_DIR / "base" / f"anuncios_{year}").glob("*.json"))
    rows = json.loads(files[0].read_text(encoding="utf-8"))
    return {r["nAnuncio"]: r.get("PecasProcedimento") or "" for r in rows if r.get("nAnuncio")}


def extract_text(files_dir: Path, text_dir: Path) -> int:
    count = 0
    for pdf in files_dir.rglob("*.pdf"):
        out = text_dir / pdf.relative_to(files_dir).with_suffix(".txt")
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            with pymupdf.open(pdf) as doc:
                out.write_text("\n".join(page.get_text() for page in doc), encoding="utf-8")
            count += 1
        except Exception as exc:  # corrupt or scanned PDFs should not stop the batch
            out.with_suffix(".error").write_text(str(exc), encoding="utf-8")
    return count


def _save_response(resp, files_dir: Path, i: int) -> str:
    import re

    m = re.search(r"filename\*=UTF-8''([^;]+)", resp.headers.get("content-disposition", ""))
    if not m:
        m = re.search(r'filename="?([^";]+)"?', resp.headers.get("content-disposition", ""))
    name = unquote(m.group(1)) if m else f"document_{i}.bin"
    name = re.sub(r"[\\/]", "_", name)
    dest = files_dir / name
    dest.write_bytes(resp.body())
    if dest.suffix.lower() == ".zip" and zipfile.is_zipfile(dest):
        with zipfile.ZipFile(dest) as zf:
            zf.extractall(files_dir / dest.stem)
    return name


def browser_download(url: str, files_dir: Path, platform: str, timeout_ms: int = 60000) -> list[str]:
    """Platforms whose public page lists documents as links: Vortal (a.buttonDownload) and Anogov (decryptservlet)."""
    import re

    from playwright.sync_api import sync_playwright

    files_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(user_agent=BROWSER_UA, locale="pt-PT")
        try:
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            page.wait_for_timeout(2000)
            if "vortal" in platform:
                page.get_by_text(re.compile(r"^\d+ - DOCUMENTOS$")).first.click()
                page.wait_for_timeout(2000)
                selector = "a.buttonDownload"
            else:
                selector = "a[href*='decryptservlet']"
            links = page.eval_on_selector_all(selector, "els => els.map(e => e.href)")
            for i, link in enumerate(dict.fromkeys(links)):
                resp = ctx.request.get(link, timeout=timeout_ms * 3)
                if resp.ok:
                    saved.append(_save_response(resp, files_dir, i))
        finally:
            browser.close()
    return saved


def save_payload(content: bytes, folder: Path, meta: dict) -> None:
    files_dir = folder / "files"
    if content[:2] == b"PK":
        (folder / "pecas.zip").write_bytes(content)
        files_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(folder / "pecas.zip") as zf:
            zf.extractall(files_dir)
        meta["status"] = "ok"
    elif content[:4] == b"%PDF":
        files_dir.mkdir(exist_ok=True)
        (files_dir / "document.pdf").write_bytes(content)
        meta["status"] = "ok"
    else:
        meta["status"] = "not_a_file"


def download(n_anuncio: str, url: str) -> dict:
    folder = DRE_DIR / n_anuncio.replace("/", "-") / "pecas"
    files_dir, text_dir = folder / "files", folder / "text"
    folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "nAnuncio": n_anuncio,
        "url": url,
        "platform": urlparse(url).netloc,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "failed",
    }
    try:
        if not url:
            raise ValueError("no PecasProcedimento link")
        resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=90, allow_redirects=True)
        meta.update(http_status=resp.status_code, content_type=resp.headers.get("content-type", ""),
                    bytes=len(resp.content))
        resp.raise_for_status()
        save_payload(resp.content, folder, meta)
        if meta["status"] == "not_a_file":
            (folder / "landing.html").write_bytes(resp.content)
            if any(k in meta["platform"] for k in ("vortal", "anogov")):
                try:
                    if browser_download(url, files_dir, meta["platform"]):
                        meta["status"], meta["method"] = "ok", "playwright"
                except Exception as exc:
                    meta["browser_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        if meta["status"] == "ok":
            meta["pdfs_with_text"] = extract_text(files_dir, text_dir)
            meta["files"] = sorted(str(p.relative_to(files_dir)) for p in files_dir.rglob("*") if p.is_file())
    except Exception as exc:
        meta["error"] = f"{type(exc).__name__}: {exc}"
    (folder / "source.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("notices", nargs="*", help="nAnuncio values such as 8844/2026")
    parser.add_argument("--from-csv", type=Path)
    parser.add_argument("--not-yes", action="store_true", help="with --from-csv: only rows where states_alvara != yes")
    parser.add_argument("--force", action="store_true", help="re-download tenders already marked ok")
    args = parser.parse_args()

    ids = list(args.notices)
    if args.from_csv:
        df = pd.read_csv(PROJECT_ROOT / args.from_csv, dtype=str, keep_default_na=False)
        if args.not_yes:
            df = df[df["states_alvara"] != "yes"]
        ids += df["nAnuncio"].tolist()

    links = load_links()
    for n in ids:
        done = DRE_DIR / n.replace("/", "-") / "pecas" / "source.json"
        if done.exists() and json.loads(done.read_text(encoding="utf-8")).get("status") == "ok" and not args.force:
            continue
        meta = download(n, links.get(n, ""))
        print(f"{n:>11}  {meta['platform']:<22} {meta['status']:<11} {meta.get('error', '')}")


if __name__ == "__main__":
    main()
