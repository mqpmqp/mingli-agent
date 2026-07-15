#!/usr/bin/env python3
"""Safe entry point for the MingLi Astro intake transformer.

Run this file with the repository's installed Python environment. All source
data, the project salt, and the validation store must remain outside Git.
"""

from __future__ import annotations

import sys

from mingli.validation_cli import main


if __name__ == "__main__":
    raise SystemExit(main(["astro-intake", *sys.argv[1:]]))
