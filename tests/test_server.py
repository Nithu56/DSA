import unittest
from pathlib import Path
from unittest.mock import patch

import server


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.data_file = Path(server.__file__).resolve().parent / "scheduler_test_state.json"
        self.data_file.unlink(missing_ok=True)
        self.file_patch = patch.object(server, "DATA_FILE", self.data_file)
        self.file_patch.start()
        self.scheduler = server.Scheduler()

    def tearDown(self):
        self.file_patch.stop()
        self.data_file.unlink(missing_ok=True)
        self.data_file.with_suffix(".json.tmp").unlink(missing_ok=True)

    def test_first_launch_seeds_demo_and_python_graph_includes_isolated_nodes(self):
        view = self.scheduler.view({"start": "5"})
        self.assertEqual(len(view["graph"]["nodes"]), 5)
        self.assertEqual(view["graph"]["bfs"], ["Design sprint"])
        self.assertEqual(view["graph"]["dfs"], ["Design sprint"])

    def test_room_conflict_and_undo_are_server_side(self):
        with self.assertRaisesRegex(ValueError, "Resource conflict"):
            self.scheduler.save_event({
                "title": "Overlapping lecture", "start_time": "2026-11-02T09:30",
                "end_time": "2026-11-02T10:30", "priority": "0",
                "status": "scheduled", "resource": "lecture hall a",
            })
        message = self.scheduler.save_event({
            "title": "New campus event", "start_time": "2026-11-02T16:30",
            "end_time": "2026-11-02T17:30", "priority": "0",
            "status": "scheduled", "resource": "",
        })
        self.assertIn("created", message)
        self.assertEqual(len(self.scheduler.events), 6)
        self.scheduler.undo()
        self.assertEqual(len(self.scheduler.events), 5)
        self.assertEqual(len(server.Scheduler().events), 5)

    def test_graph_rejects_cycles(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.scheduler.add_dependency(4, 1)
        self.assertIn((1, 2), self.scheduler.dependencies)

    def test_queue_processes_first_available_request(self):
        message = self.scheduler.queue_action("process")
        self.assertIn("Project review", message)
        self.assertEqual(len(self.scheduler.waiting), 0)
        self.assertEqual(len(server.Scheduler().waiting), 0)

    def test_invalid_import_does_not_replace_events(self):
        before = [event["title"] for event in self.scheduler.events]
        with self.assertRaisesRegex(ValueError, "Invalid time or priority"):
            self.scheduler.import_data({
                "events": [{"id": 1, "title": "Bad event", "start_time": "not-a-time", "end_time": "also-bad", "priority": 0, "status": "scheduled"}],
                "dependencies": [],
            })
        self.assertEqual([event["title"] for event in self.scheduler.events], before)


if __name__ == "__main__":
    unittest.main()
