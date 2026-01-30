import os
import unittest

from keepliver.ctyun_auto_selenium import _try_ocr_captcha


class TestOcrCaptcha(unittest.TestCase):
    def test_captcha_bind_image(self) -> None:
        try:
            import ddddocr  # noqa: F401
        except Exception:
            self.skipTest("ddddocr unavailable; skipping OCR captcha test")
        base_dir = os.path.dirname(os.path.dirname(__file__))
        image_path = os.path.join(base_dir, "keepliver", "captcha_bind.png")
        self.assertTrue(os.path.exists(image_path), f"missing test image: {image_path}")
        code = _try_ocr_captcha(image_path)
        print(f"OCR code: {code}")
        self.assertIsInstance(code, str)
        self.assertTrue(code.strip())
