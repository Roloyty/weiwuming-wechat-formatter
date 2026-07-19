from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
