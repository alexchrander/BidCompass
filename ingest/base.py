"""Portal BASE provides Portuguese public contract and notice ZIP files."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import requests

DATASETS = {
    "contratos": "66d72d488ca4b7cb2de28712",
    "anuncios": "66d72fbc58cd7a63dae28712",
}

API_URL = "https://dados.gov.pt/api/1/datasets/"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "base"
TIMEOUT = 30
RESOURCE_SUFFIXES = {
    "contratos": ".zip",
    "anuncios": ".json",
}


def _find_resource(kind, year):
    if kind not in DATASETS:
        raise ValueError(f"Unknown dataset kind {kind!r}. Choose from: {', '.join(DATASETS)}")

    response = requests.get(f"{API_URL}{DATASETS[kind]}/", timeout=TIMEOUT)
    response.raise_for_status()
    resources = response.json().get("resources", [])
    expected_title = f"{kind}{year}{RESOURCE_SUFFIXES[kind]}"
    for resource in resources:
        if resource.get("title") == expected_title:
            return resource

    available_titles = [resource.get("title", "<untitled>") for resource in resources]
    raise ValueError(
        f"No resource named {expected_title!r} for {kind}. "
        f"Available resource titles: {available_titles}"
    )


def find_url(kind, year, resource=None):
    """Find the official download URL for a dataset resource and year."""
    if resource is None:
        resource = _find_resource(kind, year)
    return f"{API_URL}r/{resource['id']}"


def _sha1(path):
    digest = hashlib.sha1()
    with path.open("rb") as archive:
        for chunk in iter(lambda: archive.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_safely(archive, destination):
    destination = destination.resolve()
    for member in archive.infolist():
        member_path = (destination / member.filename).resolve()
        if member_path != destination and destination not in member_path.parents:
            raise ValueError(f"Unsafe path in BASE archive: {member.filename!r}")
    archive.extractall(destination)


def download(kind, year):
    """Download one BASE ZIP/JSON resource, skipping a matching cached checksum."""
    resource = _find_resource(kind, year)
    url = find_url(kind, year, resource)
    destination = RAW_DIR / f"{kind}_{year}"
    destination.mkdir(parents=True, exist_ok=True)
    resource_path = destination / resource["title"]
    expected_checksum = resource.get("checksum")

    if (
        resource_path.exists()
        and expected_checksum
        and _sha1(resource_path).lower() == expected_checksum.lower()
    ):
        print(f"{kind} {year} up to date")
    else:
        response = requests.get(url, timeout=TIMEOUT, stream=True)
        response.raise_for_status()
        with resource_path.open("wb") as archive_file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    archive_file.write(chunk)

    if resource_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(resource_path) as archive:
            _extract_safely(archive, destination)
            names = archive.namelist()
    elif resource_path.suffix.lower() == ".json":
        with resource_path.open(encoding="utf-8") as json_file:
            json.load(json_file)
        names = [resource_path.name]
    else:
        raise ValueError(f"Unsupported BASE resource format: {resource_path.name}")

    print(f"Files in {resource_path}:")
    for name in names:
        print(name)
    return resource_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download Portal BASE contract datasets.")
    parser.add_argument("kind", nargs="?", choices=DATASETS)
    parser.add_argument("years", nargs="*")
    args = parser.parse_args(argv)

    if args.kind is None:
        if args.years:
            parser.error("Specify a dataset kind before the years.")
        selections = (("contratos", "2025"), ("contratos", "2026"),
                      ("anuncios", "2025"), ("anuncios", "2026"))
    else:
        if not args.years:
            parser.error("Specify at least one year.")
        selections = ((args.kind, year) for year in args.years)

    for kind, year in selections:
        download(kind, year)


if __name__ == "__main__":
    main()
