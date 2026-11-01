import math
import random
import time
import unittest
from pathlib import Path

from red_black_trees import Node, Tree, delete, insert


TEST_SIZES = (256, 1024, 4096, 16384)


class CountedKey:
    """Integer key that counts comparisons made during insertion."""

    comparisons = 0

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        type(self).comparisons += 1
        return self.value < other.value


def insertion_orders(size):
    """Return insertion orders covering common and adversarial inputs."""
    random_order = list(range(size))
    random.Random(0).shuffle(random_order)

    return {
        "ascending": list(range(size)),
        "descending": list(range(size - 1, -1, -1)),
        "random": random_order,
        "duplicates": [0] * size,
    }


def tree_height(node):
    """Return tree height measured in nodes; an empty tree has height zero."""
    if node is None:
        return 0
    return 1 + max(tree_height(node.left), tree_height(node.right))


def measure_insertions(values):
    """Build a tree and return elapsed seconds, comparisons, and height."""
    tree = Tree()
    CountedKey.comparisons = 0
    start = time.perf_counter()

    for value in values:
        insert(tree, Node(CountedKey(value)))

    elapsed = time.perf_counter() - start
    return elapsed, CountedKey.comparisons, tree_height(tree.root)


def measure_deletions(values):
    """Build and empty a tree, returning deletion time and the final root."""
    tree = Tree()
    nodes = [Node(CountedKey(value)) for value in values]

    for node in nodes:
        insert(tree, node)

    start = time.perf_counter()
    for node in nodes:
        delete(tree, node)
    elapsed = time.perf_counter() - start

    return elapsed, tree.root


class RedBlackTreeComplexityTests(unittest.TestCase):
    def test_tree_height_is_logarithmic(self):
        """Check the red-black logarithmic height bound."""
        for size in TEST_SIZES:
            maximum_height = 2 * math.log2(size + 1) + 1
            for case_name, values in insertion_orders(size).items():
                with self.subTest(size=size, case=case_name):
                    _, _, height = measure_insertions(values)
                    self.assertLessEqual(height, maximum_height)

    def test_total_insert_comparisons_are_n_log_n(self):
        """Building n-node trees uses at most O(n log n) comparisons."""
        for size in TEST_SIZES:
            maximum_comparisons = size * (
                2 * math.ceil(math.log2(size + 1)) + 1
            )
            for case_name, values in insertion_orders(size).items():
                with self.subTest(size=size, case=case_name):
                    _, comparisons, _ = measure_insertions(values)
                    self.assertLessEqual(comparisons, maximum_comparisons)

    def test_single_insertion_comparisons_are_logarithmic(self):
        """Check isolated insertion comparisons against the height bound."""
        for size in TEST_SIZES:
            with self.subTest(size=size):
                _, comparisons = measure_single_insertion(size)
                self.assertGreater(comparisons, 0)
                self.assertLessEqual(comparisons, 2 * math.log2(size + 1))

    def test_all_nodes_can_be_deleted(self):
        """Every benchmark scenario can be reduced to an empty tree."""
        for size in TEST_SIZES:
            for case_name, values in insertion_orders(size).items():
                with self.subTest(size=size, case=case_name):
                    _, root = measure_deletions(values)
                    self.assertIsNone(root)


def measure_single_insertion(size, trials=200):
    """Average isolated insertions into a size-node tree; exclude setup/delete.

    Even keys build the tree; odd probe keys fall throughout its key range.
    Each probe is removed before the next trial to preserve the tree size.
    """
    tree = Tree()
    values = list(range(0, 2 * size, 2))
    rng = random.Random(42)
    rng.shuffle(values)
    for value in values:
        insert(tree, Node(CountedKey(value)))

    elapsed = 0.0
    comparisons = 0
    for _ in range(trials):
        node = Node(CountedKey(2 * rng.randrange(size) + 1))
        CountedKey.comparisons = 0
        start = time.perf_counter()
        insert(tree, node)
        elapsed += time.perf_counter() - start
        comparisons += CountedKey.comparisons
        delete(tree, node)

    return elapsed / trials, comparisons / trials


def save_graph(rows):
    """Write dependency-free SVG comparison plots beside this script."""
    width, height = 1120, 480
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<g font-family="sans-serif" font-size="13" fill="#222">',
    ]

    def text(x, y, label, anchor="middle"):
        parts.append(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}">'
            f'{label}</text>'
        )

    panels = (
        ("Build a tree: n insertions", 1,
         [n * math.log2(n) for n, _, _ in rows], "n × log₂(n)"),
        ("One insertion into an existing tree", 2,
         [math.log2(n) for n, _, _ in rows], "log₂(n)"),
    )
    for panel, (title, column, reference, label) in enumerate(panels):
        left, top, plot_width, plot_height = 80 + panel * 550, 80, 440, 270
        measured = [row[column] for row in rows]
        maximum = max(measured + reference) * 1.15
        maximum_n = rows[-1][0]

        def point(n, value):
            return (left + plot_width * n / maximum_n,
                    top + plot_height * (1 - value / maximum))

        text(left + plot_width / 2, 30, title)
        text(left, 60, "Key comparisons", "start")
        for tick in range(5):
            value = maximum * tick / 4
            y = point(0, value)[1]
            parts.append(
                f'<path d="M {left} {y} h {plot_width}" '
                'stroke="#ddd" fill="none"/>'
            )
            text(left - 8, y + 4, f"{value:,.1f}", "end")
        for n, _, _ in rows:
            x = point(n, 0)[0]
            parts.append(
                f'<path d="M {x} {top + plot_height} v 6" '
                'stroke="#222"/>'
            )
            # Rotate labels to keep smaller sizes readable on a linear axis.
            parts.append(
                f'<text transform="translate({x},370) rotate(45)" '
                f'text-anchor="start">{n:,}</text>'
            )
        text(left + plot_width / 2, 425, "Number of nodes (n)")
        for values, color, dashed in (
            (reference, "#d97706", True),
            (measured, "#2563eb", False),
        ):
            points = " ".join(
                f"{x},{y}" for x, y in
                (point(row[0], value) for row, value in zip(rows, values))
            )
            dash = 'stroke-dasharray="7 5"' if dashed else ""
            parts.append(
                f'<polyline points="{points}" fill="none" '
                f'stroke="{color}" stroke-width="2.5" {dash}/>'
            )
            if not dashed:
                for row, value in zip(rows, values):
                    x, y = point(row[0], value)
                    parts.append(
                        f'<circle cx="{x}" cy="{y}" r="4" '
                        f'fill="{color}"/>'
                    )
        text(left, 455, "Blue: measured (random keys)", "start")
        text(left + 260, 455, f"Orange dashed: {label}", "start")

    parts.append('</g></svg>')
    path = Path(__file__).with_name("time_complexity.svg")
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


def print_benchmark():
    """Print insertion/deletion timings and insertion comparison counts."""
    print(
        f"{'case':<12} {'nodes':>7} {'insert (ms)':>12} {'delete (ms)':>12} "
        f"{'comparisons':>14} {'comparisons/(n log2 n)':>25}"
    )
    print("-" * 89)

    rows = []
    single_rows = []
    for size in TEST_SIZES:
        values = insertion_orders(size)["random"]
        insert_elapsed, comparisons, _ = measure_insertions(values)
        delete_elapsed, root = measure_deletions(values)
        assert root is None
        normalized = comparisons / (size * math.log2(size))
        print(
            f"{'random':<12} {size:>7} {insert_elapsed * 1000:>12.3f} "
            f"{delete_elapsed * 1000:>12.3f} {comparisons:>14} "
            f"{normalized:>25.3f}"
        )
        single_elapsed, single_comparisons = measure_single_insertion(size)
        rows.append((size, comparisons, single_comparisons))
        single_rows.append((size, single_elapsed, single_comparisons))

    print("\nOne insertion into an existing n-node tree (200 trials):")
    print(
        f"{'nodes':>7} {'mean insert (µs)':>18} "
        f"{'mean comparisons':>18} {'log2(n)':>10}"
    )
    for size, elapsed, comparisons in single_rows:
        print(
            f"{size:>7} {elapsed * 1_000_000:>18.3f} "
            f"{comparisons:>18.3f} {math.log2(size):>10.3f}"
        )
    print(f"\nGraph saved to: {save_graph(rows)}")
    print("Comparison growth illustrates complexity; it is not a proof.")


if __name__ == "__main__":
    print_benchmark()
