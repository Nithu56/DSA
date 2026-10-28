"""Python versions of the event scheduler's data structures and algorithms.

Run this file directly for a tiny demonstration, or run ``python -m unittest``
from the project directory to execute the Python tests.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from typing import Callable, Generic, Iterable, Optional, TypeVar

T = TypeVar("T")
K = TypeVar("K")


def intervals_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    """Return whether two ISO date/time intervals overlap; endpoints are exclusive."""
    return start_a < end_b and start_b < end_a


def merge_sort(items: Iterable[T], key: Callable[[T], K] = lambda value: value) -> list[T]:
    """Stable merge sort. Does not modify the input."""
    values = list(items)
    if len(values) < 2:
        return values
    middle = len(values) // 2
    left = merge_sort(values[:middle], key)
    right = merge_sort(values[middle:], key)
    result: list[T] = []
    i = j = 0
    while i < len(left) and j < len(right):
        if key(left[i]) <= key(right[j]):
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    return result + left[i:] + right[j:]


@dataclass
class _AVLNode:
    key: str
    ids: list[int]
    left: Optional["_AVLNode"] = None
    right: Optional["_AVLNode"] = None
    height: int = 1


class AVLIndex:
    """AVL tree from normalized titles to one or more event IDs."""

    def __init__(self) -> None:
        self.root: Optional[_AVLNode] = None

    @staticmethod
    def _height(node: Optional[_AVLNode]) -> int:
        return node.height if node else 0

    def _fix(self, node: _AVLNode) -> _AVLNode:
        node.height = 1 + max(self._height(node.left), self._height(node.right))
        return node

    def _rotate_right(self, top: _AVLNode) -> _AVLNode:
        pivot = top.left
        assert pivot is not None
        top.left = pivot.right
        pivot.right = top
        self._fix(top)
        return self._fix(pivot)

    def _rotate_left(self, top: _AVLNode) -> _AVLNode:
        pivot = top.right
        assert pivot is not None
        top.right = pivot.left
        pivot.left = top
        self._fix(top)
        return self._fix(pivot)

    def _rebalance(self, node: _AVLNode) -> _AVLNode:
        self._fix(node)
        balance = self._height(node.left) - self._height(node.right)
        if balance > 1:
            assert node.left is not None
            if self._height(node.left.left) < self._height(node.left.right):
                node.left = self._rotate_left(node.left)
            return self._rotate_right(node)
        if balance < -1:
            assert node.right is not None
            if self._height(node.right.right) < self._height(node.right.left):
                node.right = self._rotate_right(node.right)
            return self._rotate_left(node)
        return node

    @staticmethod
    def _normalize(title: str) -> str:
        return title.strip().casefold()

    def insert(self, title: str, event_id: int) -> None:
        key = self._normalize(title)

        def add(node: Optional[_AVLNode]) -> _AVLNode:
            if node is None:
                return _AVLNode(key, [event_id])
            if key == node.key:
                if event_id not in node.ids:
                    node.ids.append(event_id)
                return node
            if key < node.key:
                node.left = add(node.left)
            else:
                node.right = add(node.right)
            return self._rebalance(node)

        self.root = add(self.root)

    def search_prefix(self, prefix: str) -> list[int]:
        key = self._normalize(prefix)
        if not key:
            return []
        found: list[int] = []

        def visit(node: Optional[_AVLNode]) -> None:
            if node is None:
                return
            if node.key >= key:
                visit(node.left)
            if node.key.startswith(key):
                found.extend(node.ids)
                visit(node.right)

        visit(self.root)
        return found

    def delete(self, title: str, event_id: int) -> None:
        key = self._normalize(title)

        def remove(node: Optional[_AVLNode]) -> Optional[_AVLNode]:
            if node is None:
                return None
            if key < node.key:
                node.left = remove(node.left)
            elif key > node.key:
                node.right = remove(node.right)
            else:
                node.ids = [value for value in node.ids if value != event_id]
                if node.ids:
                    return node
                if node.left is None:
                    return node.right
                if node.right is None:
                    return node.left
                successor = node.right
                while successor.left:
                    successor = successor.left
                node.key, node.ids = successor.key, successor.ids[:]
                successor_key = successor.key
                node.right = self._delete_key(node.right, successor_key)
            return self._rebalance(node) if node else None

        self.root = remove(self.root)

    def _delete_key(self, node: _AVLNode, key: str) -> Optional[_AVLNode]:
        if key < node.key:
            node.left = self._delete_key(node.left, key)
        elif key > node.key:
            node.right = self._delete_key(node.right, key)
        else:
            if node.left is None:
                return node.right
            if node.right is None:
                return node.left
            successor = node.right
            while successor.left:
                successor = successor.left
            node.key, node.ids = successor.key, successor.ids[:]
            node.right = self._delete_key(node.right, successor.key)
        return self._rebalance(node)


class PriorityQueue:
    """Binary max-heap for event dictionaries (priority, start_time, id)."""

    @staticmethod
    def _higher(a: dict, b: dict) -> bool:
        return (-a["priority"], a["start_time"], a["id"]) < (-b["priority"], b["start_time"], b["id"])

    def __init__(self, events: Iterable[dict] = ()) -> None:
        self._heap: list[dict] = []
        for event in events:
            self.push(event)

    def __len__(self) -> int:
        return len(self._heap)

    def push(self, event: dict) -> None:
        self._heap.append(event)
        index = len(self._heap) - 1
        while index:
            parent = (index - 1) // 2
            if not self._higher(self._heap[index], self._heap[parent]):
                break
            self._heap[index], self._heap[parent] = self._heap[parent], self._heap[index]
            index = parent

    def pop(self) -> Optional[dict]:
        if not self._heap:
            return None
        first = self._heap[0]
        last = self._heap.pop()
        if self._heap:
            self._heap[0] = last
            index = 0
            while True:
                left = index * 2 + 1
                right = left + 1
                best = index
                if left < len(self._heap) and self._higher(self._heap[left], self._heap[best]):
                    best = left
                if right < len(self._heap) and self._higher(self._heap[right], self._heap[best]):
                    best = right
                if best == index:
                    break
                self._heap[index], self._heap[best] = self._heap[best], self._heap[index]
                index = best
        return first

    def ordered(self) -> list[dict]:
        copy = PriorityQueue(self._heap)
        result = []
        while copy:
            result.append(copy.pop())
        return result


class DependencyGraph:
    """Directed graph where an edge A -> B means A is a prerequisite for B."""

    def __init__(self, edges: Iterable[tuple[int, int]] = ()) -> None:
        self._adjacency: dict[int, set[int]] = {}
        for before, after in edges:
            self.add_dependency(before, after)

    def add_node(self, event_id: int) -> None:
        self._adjacency.setdefault(event_id, set())

    def _reaches(self, start: int, target: int) -> bool:
        stack = [start]
        visited: set[int] = set()
        while stack:
            current = stack.pop()
            if current == target:
                return True
            if current not in visited:
                visited.add(current)
                stack.extend(self._adjacency.get(current, ()))
        return False

    def add_dependency(self, before: int, after: int) -> bool:
        if before == after or self._reaches(after, before):
            return False
        self.add_node(before)
        self.add_node(after)
        if after in self._adjacency[before]:
            return False
        self._adjacency[before].add(after)
        return True

    def bfs(self, start: int) -> list[int]:
        if start not in self._adjacency:
            return []
        queue = deque([start])
        visited = {start}
        result = []
        while queue:
            current = queue.popleft()
            result.append(current)
            for neighbor in sorted(self._adjacency[current]):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return result

    def dfs(self, start: int) -> list[int]:
        if start not in self._adjacency:
            return []
        stack = [start]
        visited: set[int] = set()
        result = []
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            result.append(current)
            stack.extend(sorted(self._adjacency[current], reverse=True))
        return result

    def edges(self) -> list[tuple[int, int]]:
        return [(source, target) for source in sorted(self._adjacency)
                for target in sorted(self._adjacency[source])]


class FIFOQueue(Generic[T]):
    def __init__(self, items: Iterable[T] = ()) -> None:
        self._items = deque(items)

    def __len__(self) -> int:
        return len(self._items)

    @property
    def items(self) -> list[T]:
        return list(self._items)

    def enqueue(self, item: T) -> None:
        self._items.append(item)

    def dequeue(self) -> Optional[T]:
        return self._items.popleft() if self._items else None

    def remove_at(self, index: int) -> Optional[T]:
        if index < 0 or index >= len(self._items):
            return None
        self._items.rotate(-index)
        removed = self._items.popleft()
        self._items.rotate(index)
        return removed


class UndoStack(Generic[T]):
    def __init__(self) -> None:
        self._items: list[T] = []

    def __len__(self) -> int:
        return len(self._items)

    def push(self, state: T) -> None:
        self._items.append(deepcopy(state))

    def pop(self) -> Optional[T]:
        return self._items.pop() if self._items else None


if __name__ == "__main__":
    sample_events = [
        {"id": 1, "title": "Algorithms lecture", "priority": 3, "start_time": "2026-11-02T09:00"},
        {"id": 2, "title": "Project review", "priority": 5, "start_time": "2026-11-02T10:00"},
        {"id": 3, "title": "Graph workshop", "priority": 2, "start_time": "2026-11-02T11:00"},
    ]
    titles = AVLIndex()
    for event in sample_events:
        titles.insert(event["title"], event["id"])
    print("AVL title search:", titles.search_prefix("alg"))
    print("Merge-sort by title:", [event["title"] for event in merge_sort(sample_events, key=lambda event: event["title"])])
    print("Priority heap order:", [event["title"] for event in PriorityQueue(sample_events).ordered()])

    requests = FIFOQueue(["lecture", "review"])
    print("FIFO next request:", requests.dequeue())
    history = UndoStack()
    history.push({"events": [1, 2]})
    print("Undo restores:", history.pop())

    graph = DependencyGraph([(1, 2), (1, 3), (3, 4)])
    graph.add_node(5)
    print("BFS from 1:", graph.bfs(1))
    print("DFS from 1:", graph.dfs(1))
    print("Independent event traversal:", graph.bfs(5))
    print("Room-time overlap:", intervals_overlap("09:30", "10:30", "10:00", "11:00"))
