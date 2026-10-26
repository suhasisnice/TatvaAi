import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_verify_planted_script_passes():
    r = subprocess.run([sys.executable, str(ROOT / "scripts/verify_planted.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-1500:]
    assert "RESULT: PASS" in r.stdout
