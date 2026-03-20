"""pytest configuration: make the backend root importable from tests/."""
import sys
from pathlib import Path

# Add the backend directory (parent of tests/) to sys.path so that
# `from checks.general import ...` works without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent))
