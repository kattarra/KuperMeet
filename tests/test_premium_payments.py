import tempfile
import unittest
from pathlib import Path

import db


class PremiumPaymentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "test.db"
        await db.init_db()
        await db.create_user(
            tg_id=101,
            username="test_user",
            name="Test",
            age=25,
            gender="male",
            looking_for="all",
            city="Омск",
            photo_id="test-photo",
        )
        await db.set_user_approved(101, True)

    async def asyncTearDown(self):
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    async def test_payment_activates_premium_once(self):
        status = await db.register_premium_payment(
            101, "charge-1", 299, "XTR"
        )
        self.assertEqual(status, "activated")
        user = await db.get_user(101)
        self.assertEqual(user["is_premium"], 1)
        self.assertEqual(await db.get_user_like_limit(101), 100)

    async def test_same_charge_is_idempotent(self):
        first = await db.register_premium_payment(
            101, "charge-1", 299, "XTR"
        )
        second = await db.register_premium_payment(
            101, "charge-1", 299, "XTR"
        )
        self.assertEqual(first, "activated")
        self.assertEqual(second, "duplicate")

    async def test_second_distinct_purchase_is_not_activated(self):
        await db.register_premium_payment(101, "charge-1", 299, "XTR")
        second = await db.register_premium_payment(
            101, "charge-2", 299, "XTR"
        )
        self.assertEqual(second, "already_premium")

    async def test_unapproved_user_cannot_receive_premium(self):
        await db.set_user_approved(101, False)
        status = await db.register_premium_payment(
            101, "charge-1", 299, "XTR"
        )
        self.assertEqual(status, "unavailable")


if __name__ == "__main__":
    unittest.main()
