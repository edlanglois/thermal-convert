#!/usr/bin/env python
"""Install python environmnt for thermal-convert"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
import venv
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional, Sequence
from zipfile import ZipFile


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: A list of argument strings to use instead of sys.argv.

    Returns:
        An `argparse.Namespace` object containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else None,
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path(__file__).parent,
        help="source directory containing files to install",
    )
    parser.add_argument(
        "--install-dir",
        type=Path,
        default=Path(__file__).parent / "install",
        help="base install directory",
    )
    parser.add_argument(
        "--venv-dir",
        type=Path,
        default=None,
        help=(
            "virtual environment install directory "
            "(default: INSTALL_DIR/venv)"
        ),
    )
    parser.add_argument(
        "--system-site-packages",
        action="store_true",
        help="include system site packages in venv",
    )
    parser.add_argument(
        "--force-install-exiftool",
        action="store_true",
        help="install exiftool even if it is found on the PATH",
    )
    parser.add_argument(
        "--exiftool-version",
        type=str,
        default="13.27",
        help="exiftool version to install",
    )
    args = parser.parse_args(argv)
    return args


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Run script.

    Args:
        argv: A list of argument strings to use instead of sys.argv.
    """
    args = parse_args(argv)
    source_dir = args.source_dir
    install_dir = args.install_dir
    venv_dir = (
        args.venv_dir if args.venv_dir is not None else install_dir / "venv"
    )
    if sys.platform == "win32":
        venv_python_bin = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python_bin = venv_dir / "bin" / "python"

    if venv_dir.exists():
        if not venv_python_bin.exists():
            print(
                f"Virtual environment directory {venv_dir} exists "
                f"but {venv_python_bin} does not."
            )
            print("Remove the virtual environment directory or specify another")
            sys.exit(1)

        print(
            f"{venv_dir} already exists; "
            "skipping virtual environment creation"
        )
    else:
        print(f"Creating virtual environment at {venv_dir}")
        venv.create(
            venv_dir,
            with_pip=True,
            upgrade_deps=True,
            system_site_packages=args.system_site_packages,
        )
        if not venv_python_bin.exists():
            print(f"Created virtual environmnt but {venv_python_bin} not found")
            sys.exit(0)

    venv_python_bin = venv_python_bin.absolute()

    exiftool = None
    if not args.force_install_exiftool:
        if sys.platform == "win32":
            # Prevent the CWD from being included in the search path
            os.environ["NoDefaultCurrentDirectoryInExePath"] = "1"
        exiftool = shutil.which("exiftool")

    if exiftool is not None:
        print(
            f"Found existing exiftool on PATH: `{exiftool}`; skipping install"
        )
    else:
        install_exiftool = {
            "win32": install_exiftool_windows,
        }[sys.platform]
        install_exiftool(install_dir, args.exiftool_version)

    print("Installing packages in virtual environment...")
    requirements_path = source_dir / "requirements.txt"
    subprocess.run(
        [
            venv_python_bin,
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements_path),
        ],
        check=True,
    )

    if sys.platform == "win32":
        python_shebang = shebang_windows(venv_python_bin)
    else:
        python_shebang = shebang_linux(venv_python_bin)

    scripts = [Path("src/thermal-convert.py")]
    for script in scripts:
        src_path = source_dir / script
        dest_path = install_dir / script.name
        print(f"Installing {dest_path}")
        if not (dest_path.exists() and src_path.samefile(dest_path)):
            shutil.copy2(src_path, dest_path)
        # Replace shebang lines
        if dest_path.suffix == ".py":
            with open(dest_path, "r") as f:
                lines = f.readlines()
                if lines and lines[0].startswith("#!"):
                    lines[0] = python_shebang
                else:
                    continue
        print(f"Replacing shebang with {lines[0]}", end="")
        with open(dest_path, "w") as f:
            f.writelines(lines)

    print(f"Creating default input & output directories in {install_dir}")
    install_input = install_dir / "input"
    install_input.mkdir(exist_ok=True)
    install_output = install_dir / "output"
    install_output.mkdir(exist_ok=True)

    print(f"Done installing to {install_dir}")


def install_exiftool_windows(dest: Path, version: str) -> None:
    bits = 64 if sys.maxsize > 2**32 else 32
    basename = f"exiftool-{version}_{bits}"
    filename = f"{basename}.zip"
    url = f"https://exiftool.org/{filename}"
    with TemporaryDirectory() as tempdir_:
        tempdir = Path(tempdir_)
        filepath = tempdir / filename
        print(f"Downloading {url} ...")
        _ = urllib.request.urlretrieve(url, filepath)
        print(f"Downloaded to {filepath}")

        zfile = ZipFile(filepath)

        print(f"Extracting inside {tempdir}")
        zfile.extractall(tempdir)

        dest_exe = dest / "exiftool.exe"
        print(f"Installing {dest_exe}")
        shutil.copy2(tempdir / basename / "exiftool(-k).exe", dest_exe)

        dest_files = dest / "exiftool_files"
        print(f"Installing {dest_files}")
        shutil.copytree(
            tempdir / basename / "exiftool_files",
            dest_files,
            dirs_exist_ok=True,
        )


def shebang_linux(path: Path) -> str:
    path_str = str(path)
    if " " in path_str:
        raise ValueError(
            f"Virtual environment path cannot contain spaces: {path}"
        )
    return f"#!{path}\n"


def shebang_windows(path: Path) -> str:
    return f'#!"{path}"\n'


if __name__ == "__main__":
    main()
