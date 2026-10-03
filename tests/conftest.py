import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
EXAMPLES = ROOT / "examples"
NEGATIVE = ROOT / "tests" / "negative"
