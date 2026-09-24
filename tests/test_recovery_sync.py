"""Regression: upstream resolves its patches against the caller's cwd."""
import shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('bash'),'Linux bash required')
class RecoverySyncTests(unittest.TestCase):
    def test_sync_uses_own_checkout_from_unrelated_cwd(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);sync=root/'sync with spaces';sync.mkdir()
            (sync/'patches').mkdir()
            (sync/'patches/patch-manifest-fox_12.1.diff').write_text('fixture')
            (sync/'orangefox_sync.sh').write_text('set -eu\ntest -f "$PWD/patches/patch-manifest-fox_12.1.diff"\nprintf "%s\\n" "$PWD" "$@"\n')
            result=subprocess.check_output(['bash',str(ROOT/'tools/run_recovery_sync.sh'),str(sync),str(root/'android')],cwd=root,text=True)
            self.assertEqual(result.splitlines(),[str(sync),'--branch','12.1','--path',str(root/'android')])
    def test_missing_patch_stops_before_sync(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'orangefox_sync.sh').write_text('touch SHOULD_NOT_RUN\n')
            result=subprocess.run(['bash',str(ROOT/'tools/run_recovery_sync.sh'),str(root),str(root/'android')],cwd=root,capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((root/'SHOULD_NOT_RUN').exists())
