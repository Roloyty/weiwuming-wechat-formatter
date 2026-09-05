from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "upload_image.py"
SPEC = importlib.util.spec_from_file_location("upload_image", SCRIPT)
assert SPEC and SPEC.loader
upload_image = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upload_image)


class PicGoHandler(BaseHTTPRequestHandler):
    upload_count = 0
    last_payload = None
    last_authorization = None

    def do_POST(self):
        type(self).last_authorization = self.headers.get("Authorization")
        if self.path == "/heartbeat":
            self._json({"success": True, "result": "alive"})
            return
        if self.path == "/upload":
            length = int(self.headers.get("Content-Length", "0"))
            type(self).last_payload = json.loads(self.rfile.read(length))
            type(self).upload_count += 1
            self._json({"success": True, "result": ["https://cdn.example/image.jpg"]})
            return
        self.send_error(404)

    def _json(self, body):
        data = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args):
        pass


class UploadImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), PicGoHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.api_url = f"http://127.0.0.1:{cls.server.server_port}/upload"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        PicGoHandler.upload_count = 0
        PicGoHandler.last_payload = None
        PicGoHandler.last_authorization = None

    def test_load_config_prefers_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "image-host.json"
            config_file.write_text(
                json.dumps({"picgo": {"api_url": "http://old.example/upload", "timeout": 10}}),
                encoding="utf-8",
            )
            with mock.patch.object(upload_image, "CONFIG_FILE", config_file), mock.patch.dict(
                os.environ,
                {
                    "PICGO_API_URL": self.api_url,
                    "PICGO_SERVER_SECRET": "secret",
                    "PICGO_TIMEOUT": "12",
                },
                clear=False,
            ):
                config = upload_image.load_config()
        self.assertEqual(config["api_url"], self.api_url)
        self.assertEqual(config["server_secret"], "secret")
        self.assertEqual(config["timeout"], 12.0)

    def test_heartbeat_upload_and_cache(self):
        config = {"api_url": self.api_url, "server_secret": "secret", "timeout": 5}
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "cover.jpg"
            image.write_bytes(b"fake image bytes")
            cache = {}

            upload_image.check_picgo(config)
            first = upload_image.upload_one(str(image), config, cache)
            second = upload_image.upload_one(str(image), config, cache)

        self.assertEqual(first, "https://cdn.example/image.jpg")
        self.assertEqual(second, first)
        self.assertEqual(PicGoHandler.upload_count, 1)
        self.assertEqual(PicGoHandler.last_authorization, "Bearer secret")
        self.assertEqual(PicGoHandler.last_payload, {"list": [str(image.resolve())]})

    def test_remote_url_is_not_uploaded(self):
        config = {"api_url": self.api_url, "server_secret": "", "timeout": 5}
        url = "https://example.com/already-hosted.png"
        self.assertEqual(upload_image.upload_one(url, config, {}), url)
        self.assertEqual(PicGoHandler.upload_count, 0)

    def test_rejects_invalid_endpoint_and_response(self):
        with self.assertRaises(upload_image.PicGoError):
            upload_image.validate_config({"api_url": "file:///tmp/upload"})
        with self.assertRaises(upload_image.PicGoError):
            upload_image._extract_url({"success": True, "result": ["local.png"]})

    def test_cache_write_failure_does_not_raise(self):
        with mock.patch.object(Path, "mkdir", return_value=None), mock.patch.object(
            Path, "write_text", side_effect=PermissionError("denied")
        ):
            self.assertFalse(upload_image.save_cache({"key": "https://example.com/image.jpg"}))



class R2Handler(BaseHTTPRequestHandler):
    put_count = 0
    head_count = 0
    last_path = None
    last_authorization = None
    last_body = None
    last_content_type = None
    last_amz_sha = None
    fail_status = None

    def _respond(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_PUT(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        R2Handler.last_body = self.rfile.read(length)
        R2Handler.last_path = self.path
        R2Handler.last_authorization = self.headers.get("Authorization")
        R2Handler.last_content_type = self.headers.get("Content-Type")
        R2Handler.last_amz_sha = self.headers.get("x-amz-content-sha256")
        R2Handler.put_count += 1
        self._respond(R2Handler.fail_status or 200)

    def do_HEAD(self):  # noqa: N802
        R2Handler.head_count += 1
        R2Handler.last_path = self.path
        R2Handler.last_authorization = self.headers.get("Authorization")
        self._respond(R2Handler.fail_status or 200)

    def log_message(self, *args):
        return


class R2BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), R2Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.host = f"127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        R2Handler.put_count = 0
        R2Handler.head_count = 0
        R2Handler.last_path = None
        R2Handler.last_authorization = None
        R2Handler.last_body = None
        R2Handler.last_content_type = None
        R2Handler.last_amz_sha = None
        R2Handler.fail_status = None

    def config(self):
        return {
            "account_id": "acct123",
            "access_key_id": "AKIATEST",
            "secret_access_key": "s3cret",
            "bucket": "my-bucket",
            "domain": "https://img.example.com",
        }

    def test_missing_keys_are_reported(self):
        config = self.config()
        config["bucket"] = ""
        config["domain"] = ""
        self.assertEqual(upload_image.r2_missing_keys(config), ["bucket", "domain"])
        with self.assertRaises(upload_image.R2Error):
            upload_image.r2_validate(config)

    def test_object_key_uses_content_hash_and_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "cover.JPG"
            image.write_bytes(b"fake image bytes")
            key = upload_image.r2_object_key(str(image))
        digest = hashlib.sha256(b"fake image bytes").hexdigest()[:16]
        self.assertEqual(key, f"weiwuming/{digest}.jpg")

    def test_public_url_adds_scheme_and_strips_slash(self):
        config = self.config()
        config["domain"] = "img.example.com/"
        self.assertEqual(
            upload_image.r2_public_url(config, "weiwuming/a.jpg"),
            "https://img.example.com/weiwuming/a.jpg",
        )

    def test_upload_signs_request_and_returns_public_url(self):
        payload = b"fake image bytes"
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "cover.jpg"
            image.write_bytes(payload)
            with mock.patch.object(upload_image, "R2_SCHEME", "http"), mock.patch.object(
                upload_image, "r2_endpoint", return_value=self.host
            ):
                url = upload_image.r2_upload(self.config(), str(image))

        digest = hashlib.sha256(payload).hexdigest()
        self.assertEqual(url, f"https://img.example.com/weiwuming/{digest[:16]}.jpg")
        self.assertEqual(R2Handler.put_count, 1)
        self.assertEqual(R2Handler.last_path, f"/my-bucket/weiwuming/{digest[:16]}.jpg")
        self.assertEqual(R2Handler.last_body, payload)
        self.assertEqual(R2Handler.last_content_type, "image/jpeg")
        # 负载哈希必须真实，R2 会据此校验
        self.assertEqual(R2Handler.last_amz_sha, digest)
        self.assertRegex(
            R2Handler.last_authorization or "",
            r"^AWS4-HMAC-SHA256 Credential=AKIATEST/\d{8}/auto/s3/aws4_request, "
            r"SignedHeaders=content-type;host;x-amz-content-sha256;x-amz-date, "
            r"Signature=[0-9a-f]{64}$",
        )

    def test_check_sends_signed_head_to_bucket(self):
        with mock.patch.object(upload_image, "R2_SCHEME", "http"), mock.patch.object(
            upload_image, "r2_endpoint", return_value=self.host
        ):
            upload_image.check_r2(self.config())
        self.assertEqual(R2Handler.head_count, 1)
        self.assertEqual(R2Handler.last_path, "/my-bucket")
        self.assertIn("SignedHeaders=host;x-amz-content-sha256;x-amz-date", R2Handler.last_authorization)

    def test_http_error_is_wrapped(self):
        R2Handler.fail_status = 403
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "cover.jpg"
            image.write_bytes(b"x")
            with mock.patch.object(upload_image, "R2_SCHEME", "http"), mock.patch.object(
                upload_image, "r2_endpoint", return_value=self.host
            ):
                with self.assertRaises(upload_image.R2Error) as caught:
                    upload_image.r2_upload(self.config(), str(image))
        self.assertIn("403", str(caught.exception))

    def test_cache_prevents_second_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "cover.jpg"
            image.write_bytes(b"fake image bytes")
            cache: dict[str, str] = {}
            with mock.patch.object(upload_image, "R2_SCHEME", "http"), mock.patch.object(
                upload_image, "r2_endpoint", return_value=self.host
            ):
                first = upload_image.upload_one(str(image), self.config(), cache)
                second = upload_image.upload_one(str(image), self.config(), cache)
        self.assertEqual(first, second)
        self.assertEqual(R2Handler.put_count, 1)

    def test_cache_key_differs_between_backends(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "cover.jpg"
            image.write_bytes(b"fake image bytes")
            picgo_key = upload_image.cache_key(
                {"api_url": "http://127.0.0.1:36677/upload"}, str(image)
            )
            r2_key = upload_image.cache_key(self.config(), str(image))
        self.assertNotEqual(picgo_key, r2_key)

    def test_remote_url_skips_r2(self):
        url = "https://example.com/already.png"
        self.assertEqual(upload_image.upload_one(url, self.config(), {}), url)
        self.assertEqual(R2Handler.put_count, 0)


class BackendSelectionTests(unittest.TestCase):
    R2_ENV = {
        "R2_ACCOUNT_ID": "acct",
        "R2_ACCESS_KEY_ID": "key",
        "R2_SECRET_ACCESS_KEY": "secret",
        "R2_BUCKET": "bucket",
        "R2_DOMAIN": "https://img.example.com",
    }
    CLEARED = {
        key: ""
        for key in (
            "WEIWUMING_IMAGE_BACKEND",
            "R2_ACCOUNT_ID",
            "R2_ACCESS_KEY_ID",
            "R2_SECRET_ACCESS_KEY",
            "R2_BUCKET",
            "R2_DOMAIN",
        )
    }

    def empty_config(self):
        return mock.patch.object(upload_image, "CONFIG_FILE", Path(os.devnull))

    def test_defaults_to_picgo_when_r2_absent(self):
        with self.empty_config(), mock.patch.dict(os.environ, self.CLEARED, clear=False):
            self.assertEqual(upload_image.select_backend(), "picgo")

    def test_auto_selects_r2_when_fully_configured(self):
        env = dict(self.CLEARED)
        env.update(self.R2_ENV)
        with self.empty_config(), mock.patch.dict(os.environ, env, clear=False):
            self.assertEqual(upload_image.select_backend(), "r2")

    def test_partial_r2_config_stays_on_picgo(self):
        env = dict(self.CLEARED)
        env.update(self.R2_ENV)
        env["R2_DOMAIN"] = ""
        with self.empty_config(), mock.patch.dict(os.environ, env, clear=False):
            self.assertEqual(upload_image.select_backend(), "picgo")

    def test_explicit_argument_overrides_full_r2_config(self):
        env = dict(self.CLEARED)
        env.update(self.R2_ENV)
        with self.empty_config(), mock.patch.dict(os.environ, env, clear=False):
            self.assertEqual(upload_image.select_backend("picgo"), "picgo")

    def test_environment_variable_selects_backend(self):
        env = dict(self.CLEARED)
        env["WEIWUMING_IMAGE_BACKEND"] = "r2"
        with self.empty_config(), mock.patch.dict(os.environ, env, clear=False):
            self.assertEqual(upload_image.select_backend(), "r2")

    def test_config_file_backend_field_is_honoured(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "image-host.json"
            config_file.write_text(json.dumps({"backend": "r2"}), encoding="utf-8")
            with mock.patch.object(upload_image, "CONFIG_FILE", config_file), mock.patch.dict(
                os.environ, self.CLEARED, clear=False
            ):
                self.assertEqual(upload_image.select_backend(), "r2")

    def test_unknown_backend_raises(self):
        with self.empty_config(), mock.patch.dict(os.environ, self.CLEARED, clear=False):
            with self.assertRaises(ValueError):
                upload_image.select_backend("qiniu")

if __name__ == "__main__":
    unittest.main()
