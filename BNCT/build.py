#!/usr/bin/env python3
"""Build two Lambda ZIPs; never deploy or alter cloud resources."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent


def package(service, python_version, architecture, with_dependencies=True):
    if re.fullmatch(r"3\.[0-9]+", python_version) is None or int(python_version.split(".")[1]) < 12:
        raise ValueError("Target Python 3.12 or newer (Amazon Linux 2023).")
    stage = ROOT / "build" / service
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    source = ROOT / service
    shutil.copytree(ROOT / "shared", stage / "shared", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for path in source.glob("*.py"):
        shutil.copy2(path, stage / path.name)
    requirements = source / "requirements.txt"
    if requirements.exists() and requirements.read_text().strip() and with_dependencies:
        machine = "x86_64" if architecture == "x86_64" else "aarch64"
        # Amazon Linux 2023 supports modern Pillow's glibc 2.28 wheels as well
        # as the older manylinux2014 baseline. Do not build against the host OS.
        subprocess.run([
            sys.executable, "-m", "pip", "install", "--only-binary=:all:",
            "--platform", "manylinux_2_28_" + machine,
            "--platform", "manylinux2014_" + machine, "--implementation", "cp",
            "--python-version", python_version, "--target", str(stage),
            "-r", str(requirements), "--no-compile",
        ], check=True)
    out = ROOT / "dist" / f"{service}-lambda.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(stage.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                archive.write(path, path.relative_to(stage))
    print(out)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-version", default="3.12", help="Target Lambda Python version (default: 3.12)")
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), default="x86_64")
    parser.add_argument("--service", choices=("calculator", "tessellator", "both"), default="both")
    args = parser.parse_args()
    for service in (("calculator", "tessellator") if args.service == "both" else (args.service,)):
        package(service, args.python_version, args.architecture)


if __name__ == "__main__":
    main()
