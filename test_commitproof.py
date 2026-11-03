import unittest
from commitproof import evaluate, optimistic, verified


class BenchmarkTests(unittest.TestCase):
    def test_verified_agent_preserves_store_state(self):
        results = evaluate(verified)
        self.assertEqual(len(results), 8)
        self.assertTrue(all(result["passed"] for result in results))

    def test_false_completion_is_detected(self):
        results = {result["case"]: result for result in evaluate(optimistic)}
        for case in ("network failure before commit", "database transaction rolled back",
                     "HTTP 200 with rejected operation", "wrong order acknowledged"):
            self.assertFalse(results[case]["passed"], case)
            self.assertEqual(results[case]["claims"], ["completed"])

    def test_lost_response_and_retry_leave_one_record(self):
        results = {result["case"]: result for result in evaluate(verified)}
        for case in ("response lost after commit", "duplicate user request"):
            self.assertEqual(results[case]["observed_orders"], ["A-100"])


if __name__ == "__main__":
    unittest.main()
