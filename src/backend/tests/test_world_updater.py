import unittest
import sys
import os

# Đảm bảo có thể import từ backend (cwd) khi chạy test trực tiếp
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from hagent.world.schema import WorldState
from hagent.world.updater import apply_tool_output

class TestWorldUpdater(unittest.TestCase):

    def setUp(self):
        self.state = WorldState(user_id="test_user")

    def test_apply_list_datasets(self):
        payload = {"datasets": [{"id": "ds1", "name": "My Data"}]}
        patch = apply_tool_output(self.state, "list_datasets", payload)
        self.assertIn("datasets", patch)
        self.assertIn("ds1", patch["datasets"])
        self.assertEqual(patch["datasets"]["ds1"]["name"], "My Data")

    def test_apply_get_dataset_info(self):
        self.state.datasets["ds1"] = {"id": "ds1", "name": "Old Name"}
        payload = {"id": "ds1", "n_rows": 100}
        patch = apply_tool_output(self.state, "get_dataset_info", payload)
        self.assertIn("datasets", patch)
        self.assertEqual(patch["datasets"]["ds1"]["n_rows"], 100)

    def test_apply_list_jobs(self):
        payload = {"jobs": [{"id": "job1", "status": "running"}]}
        patch = apply_tool_output(self.state, "list_jobs", payload)
        self.assertIn("jobs", patch)
        self.assertIn("job1", patch["jobs"])
        self.assertEqual(patch["jobs"]["job1"]["status"], "running")

    def test_apply_get_job_info(self):
        self.state.jobs["job1"] = {"id": "job1", "status": "running"}
        payload = {"id": "job1", "status": "completed"}
        patch = apply_tool_output(self.state, "get_job_info", payload)
        self.assertIn("jobs", patch)
        self.assertEqual(patch["jobs"]["job1"]["status"], "completed")

    def test_apply_start_training(self):
        payload = {"job_id": "job2", "dataset_id": "ds1"}
        patch = apply_tool_output(self.state, "start_training", payload)
        self.assertIn("jobs", patch)
        self.assertIn("job2", patch["jobs"])
        self.assertEqual(patch["jobs"]["job2"]["status"], "starting")

    def test_world_state_to_dict_serializes_datetimes(self):
        result = self.state.to_dict()
        self.assertIsInstance(result["created_at"], str)
        self.assertIsInstance(result["updated_at"], str)

if __name__ == '__main__':
    unittest.main()
