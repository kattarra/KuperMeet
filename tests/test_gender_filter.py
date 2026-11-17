import unittest

from gender_filter import are_genders_compatible


class GenderFilterTests(unittest.TestCase):
    def test_opposite_preferences_match_mutually(self):
        self.assertTrue(are_genders_compatible("male", "female", "female", "male"))

    def test_one_sided_interest_is_not_enough(self):
        self.assertFalse(are_genders_compatible("male", "female", "female", "female"))

    def test_all_is_mutual_with_either_gender(self):
        self.assertTrue(are_genders_compatible("male", "all", "female", "all"))
        self.assertTrue(are_genders_compatible("male", "all", "female", "male"))
        self.assertTrue(are_genders_compatible("female", "male", "male", "all"))

    def test_invalid_or_missing_preferences_do_not_match(self):
        self.assertFalse(are_genders_compatible(None, "all", "female", "all"))
        self.assertFalse(are_genders_compatible("male", None, "female", "all"))


if __name__ == "__main__":
    unittest.main()
