#!/usr/bin/env python
"""Convert JPEG thermal images to TIFF"""
# Copyright (c) 2025 Eric Langlois
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
import tifffile
from gooey import Gooey, GooeyParser
from thermal_base import ThermalImage, get_exif_binary

logger = logging.getLogger(__name__)


def parse_args(
    argv: Optional[Sequence[str]] = None,
) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: A list of argument strings to use instead of sys.argv.

    Returns:
        An `argparse.Namespace` object containing the parsed arguments.
    """
    parser = GooeyParser(
        description=__doc__.splitlines()[0] if __doc__ else None,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input",
        default=str(Path.cwd() / "input"),
        nargs="?",
        widget="DirChooser",
        help="input directory",
    )
    parser.add_argument(
        "output",
        default=str(Path.cwd() / "output"),
        nargs="?",
        widget="DirChooser",
        help="output directory",
    )
    parser.add_argument(
        "-t",
        "--type",
        choices=["dji", "flir"],
        default="dji",
        help="input camera type",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=IMAGE_WRITERS.keys(),
        default="celsius",
        help="output image data format",
    )
    parser.add_argument(
        "--no-copy-exif",
        action="store_false",
        dest="copy_exif",
        help="copy EXIF metadata from source file",
    )
    parser.add_argument(
        "-l",
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="set the log level",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level.upper())
    return args


PROGRESS_MSG = "Completed Files"


@Gooey(
    progress_regex=rf"^{PROGRESS_MSG}: (?P<current>\d+)/(?P<total>\d+)$",
    progress_expr="current / total * 100",
    hide_progress_msg=True,
)
def main(argv: Optional[Sequence[str]] = None) -> None:
    """Run script.

    Args:
        argv: A list of argument strings to use instead of sys.argv.
    """
    args = parse_args(argv)

    in_dir = Path(args.input)
    in_files = [f for f in in_dir.iterdir() if f.is_file()]

    out_dir = Path(args.output)
    out_dir.mkdir(exist_ok=True)

    image_writer = IMAGE_WRITERS[args.format]

    exif = Exif() if args.copy_exif else None

    total = len(in_files)
    print(f"{PROGRESS_MSG}: 0/{total}")
    for i, file in enumerate(in_files):
        logger.info("Reading %s", file)
        image = ThermalImage(
            image_path=str(file),
            camera_manufacturer=args.type,
        )

        dest = out_dir / file.with_suffix(".tiff").name
        logger.info("Saving to %s", dest)
        image_writer(dest, image)
        print(f"{PROGRESS_MSG}: {i + 1}/{total}")

        if exif is not None:
            logger.info("Copying EXIF to %s", dest)
            exif.copy_exif(src=file, dest=dest)


def write_f32_celsius(dest: Path, image: ThermalImage) -> None:
    """Save `image` to `dest` as a float32 Celsius TIFF file."""
    data = image.thermal_np.astype(np.float32)
    tifffile.imwrite(str(dest), data, compression="LZW")


def write_u16_centikelvin(dest: Path, image: ThermalImage) -> None:
    data = image.thermal_np.copy()
    data += 273.15
    data *= 100
    data = data.clip(0, 2**16 - 1).astype(np.uint16)

    tifffile.imwrite(dest, data, compression="LZW")


IMAGE_WRITERS = {
    "celsius": write_f32_celsius,
    "centikelvin": write_u16_centikelvin,
}


class Exif:
    def __init__(self):
        self._exif = get_exif_binary()

    def copy_exif(self, src: Path, dest: Path) -> None:
        """Copy EXIF metadata from `src` to `dest`."""
        subprocess.run(
            [
                self._exif,
                "-tagsfromfile",
                str(src),
                "-wm cg",
                "-all:all",
                "-overwrite_original",
                str(dest),
            ],
            check=True,
        )


if __name__ == "__main__":
    try:
        _np = sys.modules["numpy"]
    except KeyError:
        pass
    else:
        _np.set_printoptions(  # type: ignore
            linewidth=shutil.get_terminal_size().columns
        )
    main()
