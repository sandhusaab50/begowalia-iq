import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from report import duration_seconds, sample_data, analyze, title_ideas, render_html, keyword_ideas


class ReportTests(unittest.TestCase):
    def test_duration(self):
        self.assertEqual(duration_seconds('PT3M10S'), 190)
        self.assertEqual(duration_seconds('PT1H2M'), 3720)
        self.assertEqual(duration_seconds('P1DT1S'), 86401)

    def test_sample_data_analysis(self):
        channel, raw = sample_data()
        videos, summary = analyze(raw)
        self.assertEqual(len(videos), 4)
        self.assertGreater(summary['recent_median_views_per_day'], 0)
        self.assertIn('BEGOWALIA', render_html(channel, videos, summary, [], True))
        self.assertIn('DEMO DATA ONLY', render_html(channel, videos, summary, [], True))

    def test_title_ideas(self):
        suggestions = title_ideas('Saanh | Begowalia', 'Begowalia')
        self.assertTrue(suggestions)
        self.assertTrue(all('Begowalia' in s for s in suggestions))

    def test_keywords_deduplicated(self):
        keys = keyword_ideas('Saanh | Begowalia', 'Begowalia')
        self.assertEqual(len(keys), len(set(keys)))


if __name__ == '__main__':
    unittest.main()
