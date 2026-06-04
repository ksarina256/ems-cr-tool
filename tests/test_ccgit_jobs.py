import tempfile
import time
import unittest
from pathlib import Path

from ccgit.jobs import JobStore


class JobStoreTest(unittest.TestCase):
    def test_persists_jobs_and_lists_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "jobs.json"
            store = JobStore(path)
            first = store.create("snapshot", {"branch": "master"})
            second = store.create("compare", {"base": "master", "target": "dev"})
            store.update(first.id, status="succeeded", result={"ok": True})

            reloaded = JobStore(path)
            jobs = reloaded.list()

            self.assertEqual([job.id for job in jobs], [second.id, first.id])
            self.assertEqual(reloaded.get(first.id).result, {"ok": True})

    def test_background_success_and_failure_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "jobs.json")
            success = store.create("snapshot")
            failure = store.create("snapshot")

            store.start_background(success, lambda: {"done": True})

            def fail():
                raise RuntimeError("boom")

            store.start_background(failure, fail)

            for _ in range(50):
                success_job = store.get(success.id)
                failure_job = store.get(failure.id)
                if success_job.status == "succeeded" and failure_job.status == "failed":
                    break
                time.sleep(0.02)

            self.assertEqual(store.get(success.id).result, {"done": True})
            self.assertEqual(store.get(failure.id).status, "failed")
            self.assertIn("boom", store.get(failure.id).error)


if __name__ == "__main__":
    unittest.main()
