from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "setup_picgo.py"
SPEC = importlib.util.spec_from_file_location("setup_picgo", SCRIPT)
assert SPEC and SPEC.loader
setup_picgo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup_picgo)


class SetupPicGoTests(unittest.TestCase):
    def test_version_parser(self):
        completed = mock.Mock(returncode=0, stdout="3.1.2\n", stderr="")
        with mock.patch.object(setup_picgo, "run_capture", return_value=completed):
            version, major = setup_picgo.version_of("picgo")
        self.assertEqual(version, "3.1.2")
        self.assertEqual(major, 3)

    def test_missing_cli_returns_two(self):
        with mock.patch.object(setup_picgo, "find_picgo", return_value=None), mock.patch.object(
            sys, "argv", ["setup_picgo.py", "--status"]
        ):
            self.assertEqual(setup_picgo.main(), 2)

    def test_login_delegates_to_official_cli(self):
        with mock.patch.object(setup_picgo, "find_picgo", return_value="picgo"), mock.patch.object(
            setup_picgo, "version_of", return_value=("2.0.0", 2)
        ), mock.patch.object(setup_picgo, "delegate", return_value=0) as delegate, mock.patch.object(
            sys, "argv", ["setup_picgo.py", "--login"]
        ):
            self.assertEqual(setup_picgo.main(), 0)
        delegate.assert_called_once_with("picgo", ["login"])

    def test_legacy_cli_rejects_oauth(self):
        with mock.patch.object(setup_picgo, "find_picgo", return_value="picgo"), mock.patch.object(
            setup_picgo, "version_of", return_value=("1.7.0", 1)
        ), mock.patch.object(sys, "argv", ["setup_picgo.py", "--login"]):
            self.assertEqual(setup_picgo.main(), 2)


if __name__ == "__main__":
    unittest.main()
