"""Install the pinned third-party Windows Hadoop build used by the Delta demo."""

import hashlib
import shutil
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1] / ".tools" / "hadoop"
URL = "https://github.com/zehelh/winutils/releases/download/hadoop-3.4.2/hadoop-3.4.2.zip"
SHA256 = "d1506fc26a1509019b0884a9f27de6eb8b8058c29adb9688801ac3f24e1d77f5"


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    archive = ROOT / "hadoop-3.4.2.zip"
    with urlopen(URL, timeout=60) as source, archive.open("wb") as target:
        shutil.copyfileobj(source, target)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError("Hadoop archive checksum mismatch; nothing was extracted.")
    with ZipFile(archive) as bundle:
        for member in bundle.infolist():
            destination = (ROOT / member.filename).resolve()
            if not destination.is_relative_to(ROOT.resolve()):
                raise ValueError("Archive entry escapes the installation directory.")
        bundle.extractall(ROOT)
    print(f"Installed verified Hadoop archive under {ROOT}")


if __name__ == "__main__":
    main()
