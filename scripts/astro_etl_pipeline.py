#!/usr/bin/env python3
from __future__ import annotations

import sys

from mingli.validation_cli import main


if __name__ == "__main__":
    raise SystemExit(main(["astro-intake", *sys.argv[1:]]))
