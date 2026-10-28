import unittest
from dsa import AVLIndex, DependencyGraph, FIFOQueue, PriorityQueue, UndoStack, intervals_overlap, merge_sort


class DSATests(unittest.TestCase):
    def test_avl_prefix_search_duplicate_and_delete(self):
        index = AVLIndex()
        for title, event_id in [("mango", 1), ("apple", 2), ("pear", 3), ("apricot", 4), ("plum", 5), ("apricot", 6)]:
            index.insert(title, event_id)
        self.assertEqual(set(index.search_prefix("ap")), {2, 4, 6})
        index.delete("apricot", 4)
        self.assertEqual(set(index.search_prefix("ap")), {2, 6})
        index.delete("apple", 2)
        self.assertEqual(index.search_prefix("apple"), [])

    def test_merge_sort_is_stable_and_keeps_input(self):
        values = [(2, "first"), (1, "middle"), (2, "last")]
        self.assertEqual(merge_sort(values, key=lambda value: value[0]), [(1, "middle"), (2, "first"), (2, "last")])
        self.assertEqual(values, [(2, "first"), (1, "middle"), (2, "last")])

    def test_priority_heap_orders_priority_then_start(self):
        events = [
            {"id": 1, "priority": 2, "start_time": "2026-01-01T10:00"},
            {"id": 2, "priority": 4, "start_time": "2026-01-02T10:00"},
            {"id": 3, "priority": 4, "start_time": "2026-01-01T10:00"},
        ]
        queue = PriorityQueue(events)
        self.assertEqual([event["id"] for event in queue.ordered()], [3, 2, 1])
        self.assertEqual(queue.pop()["id"], 3)

    def test_graph_traversal_cycles_and_isolated_nodes(self):
        graph = DependencyGraph([(1, 2), (1, 3), (2, 4)])
        graph.add_node(5)
        self.assertFalse(graph.add_dependency(4, 1))
        self.assertFalse(graph.add_dependency(5, 5))
        self.assertEqual(graph.bfs(1), [1, 2, 3, 4])
        self.assertEqual(graph.dfs(1), [1, 2, 4, 3])
        self.assertEqual(graph.bfs(5), [5])

    def test_fifo_and_remove(self):
        queue = FIFOQueue(["first", "second", "third"])
        self.assertEqual(queue.remove_at(1), "second")
        self.assertEqual(queue.dequeue(), "first")
        self.assertEqual(queue.dequeue(), "third")
        self.assertIsNone(queue.dequeue())

    def test_undo_stack_copies_snapshots(self):
        history = UndoStack()
        state = {"events": [1]}
        history.push(state)
        state["events"].append(2)
        self.assertEqual(history.pop(), {"events": [1]})
        self.assertIsNone(history.pop())

    def test_half_open_time_intervals(self):
        self.assertTrue(intervals_overlap("09:30", "10:30", "10:00", "11:00"))
        self.assertFalse(intervals_overlap("09:00", "10:00", "10:00", "11:00"))


if __name__ == "__main__":
    unittest.main()
