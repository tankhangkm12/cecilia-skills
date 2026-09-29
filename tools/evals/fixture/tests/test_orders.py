import unittest

from app.orders import Line, total_cents


class TotalTest(unittest.TestCase):
    def test_no_discount(self):
        self.assertEqual(total_cents([Line("A", 2, 1000)]), 2200)


if __name__ == "__main__":
    unittest.main()
