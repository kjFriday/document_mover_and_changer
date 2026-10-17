"""Start ACME Doc Pipeline from a shortcut or Apps & features (same as `python -m docpipe`, from any folder)."""

import sys

from docpipe.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
