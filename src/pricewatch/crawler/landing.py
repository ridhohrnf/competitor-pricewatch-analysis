import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


@dataclass
class LandedPage:
    page: int
    url: str
    fetched_at: str
    file: str
    html_sha256: str


@dataclass
class RunManifest:
    run_id: str
    platform: str
    crawler_version: str
    started_at: str
    pages: list[LandedPage] = field(default_factory=list)
    result: dict | None = None


class LandingWriter:
    def __init__(self, landing_dir: Path, platform: str, crawl_date: str, manifest: RunManifest):
        self.folder = Path(landing_dir) / platform / crawl_date / manifest.run_id
        self.folder.mkdir(parents=True, exist_ok=True)
        self.manifest = manifest

    def save_page(self, page: int, url: str, content: bytes, fetched_at: datetime) -> LandedPage:
        path = self.folder / f"page_{page}.html"
        write_atomic(path, content)
        landed = LandedPage(page, url, fetched_at.isoformat(), path.name, sha256_bytes(content))
        self.manifest.pages.append(landed)
        self._write_manifest()
        return landed

    def finalize(self, result: dict) -> None:
        self.manifest.result = result
        self._write_manifest()

    def _write_manifest(self) -> None:
        text = json.dumps(asdict(self.manifest), indent=2)
        write_atomic(self.folder / "run.json", text.encode("utf-8"))


def iter_manifests(landing_dir: Path, platform: str | None = None):
    pattern = f"{platform or '*'}/*/*/run.json"
    for path in sorted(Path(landing_dir).glob(pattern)):
        data = json.loads(path.read_text(encoding="utf-8"))
        pages = [LandedPage(**p) for p in data.pop("pages")]
        yield path.parent, RunManifest(**data, pages=pages)
