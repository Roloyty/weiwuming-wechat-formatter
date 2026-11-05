from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import upload_image  # noqa: E402

SPEC = importlib.util.spec_from_file_location("setup_image_host", SCRIPTS / "setup_image_host.py")
assert SPEC and SPEC.loader
setup_image_host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup_image_host)

GOOD_TOKEN = "good-token"
CLEARED_ENV = {
    "WEIWUMING_IMAGE_BACKEND": "",
    "PICGO_API_URL": "",
    "SUPERBED_TOKEN": "",
    "IMGBB_TOKEN": "",
    "R2_ACCOUNT_ID": "",
    "R2_ACCESS_KEY_ID": "",
    "R2_SECRET_ACCESS_KEY": "",
    "R2_BUCKET": "",
    "R2_DOMAIN": "",
}


class FakeHost(BaseHTTPRequestHandler):
    """按两家官方文档的响应格式模拟聚合图床和 ImgBB。"""

    last_body = b""
    last_path = ""
    last_headers = None
    upload_count = 0

    def _send(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/public/"):
            self._send(200, setup_image_host.TEST_PNG, "image/png")
        elif self.path.startswith("/not-image"):
            self._send(200, b"<html></html>", "text/html")
        else:
            self._send(404, {})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        FakeHost.last_body, FakeHost.last_path, FakeHost.last_headers = body, self.path, self.headers
        base = f"http://127.0.0.1:{self.server.server_port}"
        if self.path.startswith("/superbed/upload"):
            if f'name="token"\r\n\r\n{GOOD_TOKEN}\r\n'.encode() not in body:
                self._send(401, {"detail": "Invalid API key"})
                return
            if b'name="file"' not in body:
                self._send(200, {"err": 1, "msg": "no file"})
                return
            FakeHost.upload_count += 1
            self._send(200, {"err": 0, "url": f"{base}/public/s.png"})
        elif self.path.startswith("/imgbb/upload"):
            if f"key={GOOD_TOKEN}" not in self.path:
                self._send(400, {"status_code": 400, "error": {"message": "Invalid API v1 key.", "code": 100}})
            elif b'name="image"' not in body:
                self._send(400, {"status_code": 400, "error": {"message": "Empty upload source.", "code": 130}})
            else:
                FakeHost.upload_count += 1
                self._send(200, {"data": {"url": f"{base}/public/i.png"}, "success": True, "status": 200})
        else:
            self._send(404, {})

    def log_message(self, *_args):
        pass


class HostTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHost)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        FakeHost.upload_count = 0
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.config_file = self.home / ".weiwuming" / "image-host.json"
        providers = {
            "superbed": {
                **upload_image.TOKEN_PROVIDERS["superbed"],
                "upload_url": f"{self.base}/superbed/upload",
            },
            "imgbb": {
                **upload_image.TOKEN_PROVIDERS["imgbb"],
                "upload_url": f"{self.base}/imgbb/upload",
            },
        }
        env = {**CLEARED_ENV, "APPDATA": str(self.home / "appdata")}
        for patcher in (
            mock.patch.object(upload_image, "CONFIG_FILE", self.config_file),
            mock.patch.object(upload_image, "CACHE_FILE", self.home / "cache.json"),
            # 指向没人监听的端口，不受本机是否开着 PicGo 影响
            mock.patch.object(upload_image, "DEFAULT_API_URL", "http://127.0.0.1:9/upload"),
            mock.patch.object(upload_image, "TOKEN_PROVIDERS", providers),
            mock.patch.object(Path, "home", return_value=self.home),
            mock.patch.dict(os.environ, env, clear=False),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_config(self, value):
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(json.dumps(value), encoding="utf-8")

    def run_save(self, token, provider="superbed"):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(token)), contextlib.redirect_stdout(
            stdout
        ), contextlib.redirect_stderr(stderr):
            code = setup_image_host.save(provider)
        return code, stdout.getvalue(), stderr.getvalue()


class DetectionTests(HostTestCase):
    def test_fresh_machine_is_not_configured_and_points_at_setup(self):
        status = upload_image.detect_status()
        self.assertEqual(status["state"], "not_configured")
        self.assertIn("setup_image_host.py", status["setup_command"])

    def test_picgo_user_with_app_closed_is_not_sent_to_register(self):
        data = self.home / "appdata" / "picgo" / "data.json"
        data.parent.mkdir(parents=True)
        data.write_text("{}", encoding="utf-8")
        status = upload_image.detect_status()
        self.assertEqual(status["state"], "unavailable")
        self.assertIn("PicGo", status["message"])

    def test_explicit_picgo_config_with_app_closed_is_unavailable(self):
        self.write_config({"backend": "picgo"})
        self.assertEqual(upload_image.detect_status()["state"], "unavailable")

    def test_superbed_check_with_good_key_does_not_upload(self):
        self.write_config({"superbed": {"token": GOOD_TOKEN}})
        self.assertEqual(upload_image.detect_status()["state"], "ready")
        self.assertEqual(FakeHost.upload_count, 0)

    def test_half_filled_r2_reports_what_is_missing(self):
        with mock.patch.dict(os.environ, {"R2_BUCKET": "b"}):
            status = upload_image.detect_status()
        self.assertEqual(status["state"], "unavailable")
        self.assertIn("account_id", status["message"])

    def test_saved_token_is_ready(self):
        self.write_config({"superbed": {"token": GOOD_TOKEN}})
        status = upload_image.detect_status()
        self.assertEqual((status["state"], status["backend"]), ("ready", "superbed"))

    def test_revoked_token_is_unavailable_not_unconfigured(self):
        self.write_config({"superbed": {"token": "revoked"}})
        self.assertEqual(upload_image.detect_status()["state"], "unavailable")

    def test_imgbb_empty_post_with_good_key_counts_as_ready(self):
        self.write_config({"imgbb": {"token": GOOD_TOKEN}})
        status = upload_image.detect_status()
        self.assertEqual((status["state"], status["backend"]), ("ready", "imgbb"))
        self.assertEqual(FakeHost.upload_count, 0)

    def test_r2_stays_ahead_of_saved_token_in_auto_selection(self):
        self.write_config({"superbed": {"token": GOOD_TOKEN}})
        env = {
            "R2_ACCOUNT_ID": "a",
            "R2_ACCESS_KEY_ID": "b",
            "R2_SECRET_ACCESS_KEY": "c",
            "R2_BUCKET": "d",
            "R2_DOMAIN": "https://e",
        }
        with mock.patch.dict(os.environ, env):
            self.assertEqual(upload_image.select_backend(), "r2")

    def test_check_json_output_and_exit_code(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = upload_image.run_check(None, True)
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout.getvalue())["state"], "not_configured")

    def test_uploading_without_any_host_shows_guide_instead_of_per_image_errors(self):
        image = self.home / "cover.jpg"
        image.write_bytes(b"x")
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", ["upload_image.py", str(image)]), contextlib.redirect_stderr(stderr):
            code = upload_image.main()
        self.assertEqual(code, 2)
        self.assertIn("setup_image_host.py", stderr.getvalue())
        self.assertNotIn("上传失败", stderr.getvalue())


class TokenUploadTests(HostTestCase):
    def test_superbed_sends_key_in_form_field_with_hashed_filename(self):
        image = self.home / "book_中文书名.JPG"
        image.write_bytes(b"fake image")
        url = upload_image.token_upload({"provider": "superbed", "token": GOOD_TOKEN}, str(image))
        self.assertEqual(url, f"{self.base}/public/s.png")
        self.assertIn(b'name="file"', FakeHost.last_body)
        self.assertIn(b"fake image", FakeHost.last_body)
        self.assertIn(b"Content-Type: image/jpeg", FakeHost.last_body)
        self.assertNotIn("中文书名".encode(), FakeHost.last_body)
        self.assertNotIn(GOOD_TOKEN, FakeHost.last_path)

    def test_imgbb_uses_image_field_and_reads_nested_url(self):
        image = self.home / "cover.png"
        image.write_bytes(b"fake image")
        url = upload_image.token_upload({"provider": "imgbb", "token": GOOD_TOKEN}, str(image))
        self.assertEqual(url, f"{self.base}/public/i.png")
        self.assertIn(b'name="image"', FakeHost.last_body)

    def test_cache_prevents_second_upload(self):
        image = self.home / "cover.png"
        image.write_bytes(b"fake image")
        config = {"provider": "superbed", "token": GOOD_TOKEN}
        cache: dict[str, str] = {}
        first = upload_image.upload_one(str(image), config, cache)
        second = upload_image.upload_one(str(image), config, cache)
        self.assertEqual(first, second)
        self.assertEqual(FakeHost.upload_count, 1)

    def test_rejected_key_raises_auth_error_without_leaking_it(self):
        image = self.home / "cover.png"
        image.write_bytes(b"x")
        with self.assertRaises(upload_image.TokenAuthError) as caught:
            upload_image.token_upload({"provider": "imgbb", "token": "bad-secret"}, str(image))
        self.assertNotIn("bad-secret", str(caught.exception))


class SaveTests(HostTestCase):
    def test_good_token_is_saved_after_trial_upload(self):
        code, stdout, stderr = self.run_save(f"{GOOD_TOKEN}\n")
        self.assertEqual(code, 0, stderr)
        saved = json.loads(self.config_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["backend"], "superbed")
        self.assertEqual(saved["superbed"]["token"], GOOD_TOKEN)
        self.assertEqual(FakeHost.upload_count, 1)
        self.assertNotIn(GOOD_TOKEN, stdout + stderr)

    def test_bad_token_is_not_saved(self):
        code, stdout, stderr = self.run_save("wrong-token")
        self.assertEqual(code, 1)
        self.assertFalse(self.config_file.exists())
        self.assertNotIn("wrong-token", stdout + stderr)

    def test_empty_or_broken_paste_is_rejected(self):
        self.assertEqual(self.run_save("  \n")[0], 1)
        self.assertEqual(self.run_save("two words")[0], 1)
        self.assertFalse(self.config_file.exists())

    def test_bom_from_powershell_pipe_is_stripped(self):
        code, _, stderr = self.run_save(f"﻿{GOOD_TOKEN}\r\n")
        self.assertEqual(code, 0, stderr)

    def test_other_sections_survive_and_backend_change_is_announced(self):
        r2 = {"account_id": "a", "bucket": "b"}
        self.write_config({"backend": "r2", "r2": r2, "picgo": {"timeout": 5}})
        code, stdout, stderr = self.run_save(GOOD_TOKEN)
        self.assertEqual(code, 0, stderr)
        saved = json.loads(self.config_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["r2"], r2)
        self.assertEqual(saved["picgo"], {"timeout": 5})
        self.assertEqual(saved["backend"], "superbed")
        self.assertIn("r2", stdout)

    def test_corrupt_config_is_left_untouched(self):
        self.config_file.parent.mkdir(parents=True)
        self.config_file.write_text("{ not json", encoding="utf-8")
        code, _, stderr = self.run_save(GOOD_TOKEN)
        self.assertEqual(code, 2)
        self.assertEqual(self.config_file.read_text(encoding="utf-8"), "{ not json")
        self.assertIn("没有改动", stderr)

    def test_unreachable_host_does_not_save(self):
        providers = {"superbed": {**upload_image.TOKEN_PROVIDERS["superbed"], "upload_url": "http://127.0.0.1:9/x"}}
        with mock.patch.object(upload_image, "TOKEN_PROVIDERS", providers):
            code, _, _ = self.run_save(GOOD_TOKEN)
        self.assertEqual(code, 2)
        self.assertFalse(self.config_file.exists())

    def test_verify_public_url(self):
        self.assertIsNone(setup_image_host.verify_public_url(f"{self.base}/public/a.png"))
        self.assertIn("不是图片", setup_image_host.verify_public_url(f"{self.base}/not-image"))
        self.assertIn("打不开", setup_image_host.verify_public_url("http://127.0.0.1:9/x"))


class GuideTests(HostTestCase):
    def test_guide_has_direct_links_and_explains_the_term(self):
        expected = {
            "superbed": ["https://www.superbed.cn/login", "https://www.superbed.cn/dashboard/settings"],
            "imgbb": ["https://imgbb.com/signup", "https://api.imgbb.com/"],
        }
        for provider, links in expected.items():
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                setup_image_host.print_guide(provider)
            text = stdout.getvalue()
            self.assertIn("图床是什么", text)
            for link in links:
                self.assertIn(link, text)
            self.assertIn(f"--save --provider {provider}", text)


if __name__ == "__main__":
    unittest.main()
