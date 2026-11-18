"""Offline tests — no device required."""
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zunesync import core  # noqa: E402

FLAC_DIR = Path(r"E:\zune\Music")


class FormatTests(unittest.TestCase):
    def test_known_extensions(self):
        self.assertEqual(core.detect("a.MP3").code, 0x3009)
        self.assertEqual(core.detect("a.flac").code, 0xB906)
        self.assertEqual(core.detect("a.WMA").code, 0xB901)
        self.assertIsNone(core.detect("a.txt"))

    def test_guid_pattern(self):
        g = core.format_guid(0xB906)
        self.assertEqual(g, "{B9060000-AE6C-4804-98BA-C57B46965FE7}")
        self.assertEqual(core.FORMATS[".flac"].object_format, g)

    def test_m4a_override(self):
        self.assertEqual(core.FORMATS[".m4a"].object_format,
                         "{30ABA7AC-6FFD-4C23-A359-3E9B52F3F1C8}")


class TagTests(unittest.TestCase):
    def test_flac_metadata(self):
        if not FLAC_DIR.is_dir():
            self.skipTest("no sample library")
        files = list(FLAC_DIR.rglob("*.flac"))
        if not files:
            self.skipTest("no flac sample")
        t = core.read_track(files[0])
        self.assertIsNotNone(t)
        self.assertFalse(t.error, t.error)
        self.assertTrue(t.title or t.path.stem)
        self.assertGreater(t.size, 0)


class PlanTests(unittest.TestCase):
    def _track(self, name, size=1000):
        class F:
            kind = "audio"
            label = "X"
        t = core.Track(path=Path(name), fmt=F(), size=size)
        return t

    def test_plan_adds_new(self):
        plan = core.build_plan([self._track("a.mp3")], existing=[])
        self.assertEqual(len(plan.to_add), 1)

    def test_plan_skips_existing(self):
        plan = core.build_plan([self._track("a.mp3")], existing=["A.MP3"])
        self.assertEqual(len(plan.to_add), 0)
        self.assertEqual(len(plan.skipped), 1)

    def test_plan_skips_errors(self):
        t = self._track("b.mp3")
        t.error = "boom"
        plan = core.build_plan([t], existing=[])
        self.assertEqual(len(plan.to_add), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
