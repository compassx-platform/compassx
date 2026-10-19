import os
import tempfile
import json
import unittest
from app.services.framework_detector import FrameworkDetector, detect_framework


class TestFrameworkDetector(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.root = self.test_dir.name

    def tearDown(self):
        self.test_dir.cleanup()

    def test_empty_workspace_returns_not_detected(self):
        report = FrameworkDetector(self.root).detect()
        self.assertFalse(report.detected)
        self.assertFalse(report.has_frontend)
        self.assertFalse(report.has_backend)

        data = detect_framework(self.root)
        self.assertFalse(data["detected"])

    def test_fastapi_backend_detection(self):
        main_py = os.path.join(self.root, "main.py")
        with open(main_py, "w") as f:
            f.write("from fastapi import FastAPI\napp = FastAPI()\n")

        report = FrameworkDetector(self.root).detect()
        self.assertTrue(report.detected)
        self.assertTrue(report.has_backend)
        self.assertIsNotNone(report.backend)
        self.assertEqual(report.backend.framework, "fastapi")
        self.assertIn("uvicorn", report.backend.dev_command)

        data = detect_framework(self.root)
        self.assertTrue(data["detected"])
        self.assertTrue(data["has_backend"])

    def test_vite_frontend_detection(self):
        pkg_json = os.path.join(self.root, "package.json")
        with open(pkg_json, "w") as f:
            json.dump({
                "name": "my-app",
                "scripts": {"dev": "vite", "build": "vite build"},
                "devDependencies": {"vite": "^5.0.0"}
            }, f)

        report = FrameworkDetector(self.root).detect()
        self.assertTrue(report.detected)
        self.assertTrue(report.has_frontend)
        self.assertIsNotNone(report.frontend)
        self.assertEqual(report.frontend.framework, "vite")

        data = detect_framework(self.root)
        self.assertTrue(data["detected"])
        self.assertTrue(data["has_frontend"])


if __name__ == "__main__":
    unittest.main()
