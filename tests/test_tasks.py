import threading
import unittest

from famdtool.tasks import run_background


class FakeWidget:
    def after(self, _delay_ms, callback):
        callback()


class BackgroundTaskTests(unittest.TestCase):
    def test_run_background_dispatches_success(self):
        done = threading.Event()
        results = []

        run_background(FakeWidget(), lambda: 42, lambda value: (results.append(value), done.set()))

        self.assertTrue(done.wait(2))
        self.assertEqual(results, [42])

    def test_run_background_dispatches_error(self):
        done = threading.Event()
        errors = []

        def fail():
            raise ValueError("boom")

        run_background(
            FakeWidget(),
            fail,
            lambda _value: None,
            lambda exc: (errors.append(str(exc)), done.set()),
        )

        self.assertTrue(done.wait(2))
        self.assertEqual(errors, ["boom"])


if __name__ == "__main__":
    unittest.main()
