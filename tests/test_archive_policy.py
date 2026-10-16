from pathlib import Path
import subprocess
import sys


def test_packager_requires_explicit_release_confirmation(tmp_path):
    script=Path(__file__).resolve().parents[1]/'scripts/package_release.py'
    archive=tmp_path/'must-not-exist.zip'
    result=subprocess.run([sys.executable,str(script),'--output',str(archive)],capture_output=True,text=True)
    assert result.returncode!=0 and '--confirm-release' in result.stderr
    assert not archive.exists()
