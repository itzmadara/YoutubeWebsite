import unittest

from backend.app import SEGMENT_PRESETS, is_youtube_url


class UrlValidationTests(unittest.TestCase):
    def test_accepts_standard_youtube_url(self) -> None:
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))

    def test_accepts_shortened_youtube_url(self) -> None:
        self.assertTrue(is_youtube_url("https://youtu.be/dQw4w9WgXcQ"))

    def test_rejects_non_youtube_url(self) -> None:
        self.assertFalse(is_youtube_url("https://example.com/video"))

    def test_rejects_url_without_video_identifier(self) -> None:
        self.assertFalse(is_youtube_url("https://www.youtube.com/watch"))


class PresetTests(unittest.TestCase):
    def test_supported_presets(self) -> None:
        self.assertEqual(SEGMENT_PRESETS["10s"], 10)
        self.assertEqual(SEGMENT_PRESETS["30s"], 30)
        self.assertEqual(SEGMENT_PRESETS["5min"], 300)


if __name__ == "__main__":
    unittest.main()
