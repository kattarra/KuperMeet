import unittest

from age_filter import age_segment, are_ages_compatible, max_age_gap


class AgeFilterTests(unittest.TestCase):
    def test_segments(self):
        self.assertEqual(age_segment(17), "teen")
        self.assertEqual(age_segment(18), "adult")
        self.assertIsNone(age_segment(13))
        self.assertIsNone(age_segment(100))

    def test_cross_segment_is_never_allowed(self):
        self.assertFalse(are_ages_compatible(17, 18, teen_segment_enabled=True, both_ages_verified=True))

    def test_teen_segment_is_closed_by_default(self):
        self.assertFalse(are_ages_compatible(16, 17))
        self.assertTrue(are_ages_compatible(
            16, 17, teen_segment_enabled=True, both_ages_verified=True
        ))

    def test_age_gap_boundaries(self):
        self.assertEqual(max_age_gap(20, 20), 3)
        self.assertEqual(max_age_gap(21, 21), 4)
        self.assertEqual(max_age_gap(25, 25), 6)
        self.assertEqual(max_age_gap(30, 30), 8)
        self.assertEqual(max_age_gap(40, 40), 12)
        self.assertEqual(max_age_gap(50, 50), 15)

    def test_adult_compatibility(self):
        self.assertTrue(are_ages_compatible(24, 28))
        self.assertFalse(are_ages_compatible(24, 29))
        self.assertTrue(are_ages_compatible(35, 43))
        self.assertFalse(are_ages_compatible(35, 44))

    def test_invalid_ages_are_rejected(self):
        self.assertFalse(are_ages_compatible(13, 18))
        self.assertFalse(are_ages_compatible(18, 100))


if __name__ == "__main__":
    unittest.main()
