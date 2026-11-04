import argparse
import csv
import gc
import math
import random
import statistics
import time
import unittest
from dataclasses import asdict, dataclass
from pathlib import Path

from red_black_trees import Node, Tree, delete, insert


TEST_SIZES = (256, 1024, 4096, 16384)
BENCHMARK_SIZES = tuple(2 ** power for power in range(8, 18))
LINEAR_BENCHMARK_SIZES = tuple(range(5000, 100001, 5000))

# Explicit colors keep exported text readable even with a custom Matplotlib theme.
PLOT_STYLE = {
    "font.size": 10,
    "text.color": "#111827",
    "axes.labelcolor": "#111827",
    "axes.titlecolor": "#111827",
    "xtick.color": "#111827",
    "ytick.color": "#111827",
    "axes.edgecolor": "#475569",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "savefig.transparent": False,
    "legend.facecolor": "white",
    "legend.edgecolor": "#94a3b8",
    "legend.labelcolor": "#111827",
    "legend.framealpha": 1,
    "svg.fonttype": "none",
    "svg.hashsalt": "rb-insertion-complexity",
}


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


def tree_height(tree, node):
    """Return tree height measured in nodes; an empty tree has height zero."""
    if node is tree.nil:
        return 0
    return 1 + max(tree_height(tree, node.left), tree_height(tree, node.right))


def measure_insertions(values):
    """Build a tree and return elapsed seconds, comparisons, and height."""
    tree = Tree()
    CountedKey.comparisons = 0
    start = time.perf_counter()

    for value in values:
        insert(tree, Node(CountedKey(value)))

    elapsed = time.perf_counter() - start
    return elapsed, CountedKey.comparisons, tree_height(tree, tree.root)


def measure_deletions(values):
    """Build and empty a tree, returning deletion time and the empty tree."""
    tree = Tree()
    nodes = [Node(value) for value in values]

    for node in nodes:
        insert(tree, node)

    start = time.perf_counter()
    for node in nodes:
        delete(tree, node)
    elapsed = time.perf_counter() - start

    return elapsed, tree


def measure_build_time(values):
    """Time only insertion of preallocated nodes with ordinary integer keys."""
    tree = Tree()
    nodes = [Node(value) for value in values]
    # Cyclic garbage collection can otherwise interrupt a large timed build.
    gc_enabled = gc.isenabled()
    gc.disable()
    try:
        start = time.perf_counter()
        for node in nodes:
            insert(tree, node)
        return time.perf_counter() - start
    finally:
        if gc_enabled:
            gc.enable()


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
                    _, tree = measure_deletions(values)
                    self.assertIs(tree.root, tree.nil)


def measure_single_insertion(size, trials=200, *, count_comparisons=True):
    """Average isolated insertions into a size-node tree; exclude setup/delete.

    Even keys build the tree; odd probe keys fall throughout its key range.
    Each probe is removed before the next trial to preserve the tree size.
    """
    tree = Tree()
    values = list(range(0, 2 * size, 2))
    rng = random.Random(42)
    rng.shuffle(values)
    for value in values:
        insert(tree, Node(CountedKey(value) if count_comparisons else value))

    elapsed = 0.0
    comparisons = 0
    for _ in range(trials):
        value = 2 * rng.randrange(size) + 1
        node = Node(CountedKey(value) if count_comparisons else value)
        if count_comparisons:
            CountedKey.comparisons = 0
        start = time.perf_counter()
        insert(tree, node)
        elapsed += time.perf_counter() - start
        if count_comparisons:
            comparisons += CountedKey.comparisons
        delete(tree, node)

    return elapsed / trials, comparisons / trials


@dataclass
class BenchmarkRow:
    nodes: int
    build_ms: float
    delete_ms: float
    single_insert_ms: float
    build_comparisons: int
    single_insert_comparisons: float


@dataclass
class SingleInsertionRow:
    nodes: int
    single_insert_ms: float
    single_insert_comparisons: float


def plot_panel(ax, sizes, measured, reference, label, title, units, *, scaled, logarithmic):
    if scaled:
        # Fit a multiplier to illustrate shape, rather than an exact time bound.
        multiplier = sum(m * r for m, r in zip(measured, reference)) / sum(r * r for r in reference)
        reference = [multiplier * value for value in reference]
        label = f"Scaled {label} (shape guide)"
    ax.plot(sizes, measured, "o-", color="#0057b8", linewidth=2,
            markersize=5, label="Measured (random keys)")
    ax.plot(sizes, reference, "--", color="#9f1239", linewidth=2, label=label)
    scale = "log₂" if logarithmic else "linear"
    ax.set(title=title, xlabel=f"Number of nodes n ({scale} scale)", ylabel=units)
    if logarithmic:
        ax.set_xscale("log", base=2)
        ax.set_xticks(sizes, [f"{n:,}" for n in sizes], rotation=45, ha="right")
    else:
        ax.set_xlim(0, max(sizes) * 1.03)
        ax.locator_params(axis="x", nbins=6)
        ax.xaxis.set_major_formatter("{x:,.0f}")
    ax.set_ylim(bottom=0)
    ax.grid(color="#cbd5e1", alpha=0.7)
    ax.legend(fontsize=8)
    if scaled:
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)


def save_figure(figure, filename):
    """Export SVG and PNG with fixed colors, plus clean SVG whitespace."""
    path = Path(__file__).with_name(filename)
    figure.savefig(path, metadata={"Date": None}, facecolor="white", transparent=False)
    figure.savefig(path.with_suffix(".png"), dpi=160, facecolor="white", transparent=False)
    path.write_text("\n".join(line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()) + "\n",
                    encoding="utf-8")
    return path


def save_graph(rows):
    """Plot measured comparisons and median elapsed milliseconds as SVG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sizes = [row.nodes for row in rows]
    n_log_n = [n * math.log2(n) for n in sizes]
    log_n = [math.log2(n) for n in sizes]
    panels = (
        ("Build a tree: n insertions", "Key comparisons",
         [row.build_comparisons for row in rows], n_log_n, "n log₂(n)", False),
        ("One insertion into an existing tree", "Mean key comparisons",
         [row.single_insert_comparisons for row in rows], log_n, "log₂(n)", False),
        ("Build time: n insertions", "Median elapsed time (ms)",
         [row.build_ms for row in rows], n_log_n, "n log₂(n)", True),
        ("One insertion into an existing tree", "Median mean insertion time (ms)",
         [row.single_insert_ms for row in rows], log_n, "log₂(n)", True),
    )
    with plt.rc_context(PLOT_STYLE):
        figure, axes = plt.subplots(2, 2, figsize=(13, 9), layout="constrained")
        for ax, (title, units, measured, reference, label, scaled) in zip(axes.flat, panels):
            plot_panel(ax, sizes, measured, reference, label, title, units,
                       scaled=scaled, logarithmic=True)
        figure.suptitle("Red-black tree insertion growth", fontsize=16)
        path = save_figure(figure, "time_complexity.svg")
        plt.close(figure)
    return path


def save_linear_graph(rows):
    """Show evenly spaced tree sizes on a linear node-count axis."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sizes = [row.nodes for row in rows]
    reference = [math.log2(n) for n in sizes]
    with plt.rc_context(PLOT_STYLE):
        figure, axes = plt.subplots(1, 2, figsize=(13, 5), layout="constrained")
        plot_panel(axes[0], sizes, [row.single_insert_comparisons for row in rows],
                   reference, "log₂(n)", "One insertion: comparison growth",
                   "Mean key comparisons", scaled=False, logarithmic=False)
        plot_panel(axes[1], sizes, [row.single_insert_ms for row in rows],
                   reference, "log₂(n)", "One insertion: elapsed time",
                   "Insertion time (ms), median of run means", scaled=True, logarithmic=False)
        figure.suptitle("One insertion into an existing tree · linear node-count axis", fontsize=16)
        path = save_figure(figure, "time_complexity_linear.svg")
        plt.close(figure)
    return path


def save_measurements(rows, filename):
    path = Path(__file__).with_name(filename)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=asdict(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    return path


def median_sample(operation, repeats):
    samples = []
    for _ in range(repeats):
        # Tree links form cycles. Collect previous samples outside the timer.
        gc.collect()
        samples.append(operation())
    return statistics.median(samples)


def growth(current, previous):
    return "—" if previous is None or previous <= 0 else f"{current / previous:.2f}×"


def print_benchmark(sizes=BENCHMARK_SIZES, repeats=5, trials=1000,
                    linear_sizes=LINEAR_BENCHMARK_SIZES):
    """Report comparison growth and ordinary-key insertion time separately."""
    print(f"Random keys; median of {repeats} timing runs per size.", flush=True)
    print("Build time excludes node allocation; deletion time excludes tree setup.")
    print(
        f"{'nodes':>9} {'build (ms)':>12} {'growth':>8} {'delete (ms)':>12} "
        f"{'comparisons':>14} {'comparisons/(n log2 n)':>25}", flush=True
    )
    print("-" * 86, flush=True)
    rows = []
    for size in sizes:
        values = insertion_orders(size)["random"]
        # Warm the insertion path, and count comparisons in a separate run.
        _, comparisons, _ = measure_insertions(values)
        build_ms = median_sample(lambda: measure_build_time(values), repeats) * 1000

        def deletion_sample():
            elapsed, tree = measure_deletions(values)
            assert tree.root is tree.nil
            return elapsed

        delete_ms = median_sample(deletion_sample, repeats) * 1000
        _, single_comparisons = measure_single_insertion(size, trials)
        single_ms = median_sample(
            lambda: measure_single_insertion(size, trials, count_comparisons=False)[0], repeats
        ) * 1000
        previous = rows[-1].build_ms if rows else None
        rows.append(BenchmarkRow(size, build_ms, delete_ms, single_ms, comparisons, single_comparisons))
        print(
            f"{size:>9,} {build_ms:>12.3f} {growth(build_ms, previous):>8} "
            f"{delete_ms:>12.3f} {comparisons:>14,} "
            f"{comparisons / (size * math.log2(size)):>25.3f}", flush=True
        )

    print(f"\nOne insertion into an existing n-node tree ({trials} trials/run):")
    print("Setup, node allocation, and probe removal are outside the insertion timer.")
    print(
        f"{'nodes':>9} {'insert (ms)':>14} {'growth':>8} "
        f"{'mean comparisons':>18} {'log2(n)':>10}"
    )
    previous = None
    for row in rows:
        print(
            f"{row.nodes:>9,} {row.single_insert_ms:>14.6f} "
            f"{growth(row.single_insert_ms, previous):>8} "
            f"{row.single_insert_comparisons:>18.3f} {math.log2(row.nodes):>10.3f}"
        )
        previous = row.single_insert_ms
    print("Growth is elapsed time divided by elapsed time at the previous size.")
    csv_path = save_measurements(rows, "time_complexity.csv")
    print(f"\nMeasurements saved to: {csv_path}")
    print("\nSingle insertion with linearly increasing tree sizes:", flush=True)
    print(f"{'nodes':>9} {'insert (ms)':>14} {'mean comparisons':>18}", flush=True)
    linear_rows = []
    for size in linear_sizes:
        _, comparisons = measure_single_insertion(size, trials)
        elapsed = median_sample(
            lambda: measure_single_insertion(size, trials, count_comparisons=False)[0], repeats
        )
        linear_rows.append(SingleInsertionRow(size, elapsed * 1000, comparisons))
        print(f"{size:>9,} {elapsed * 1000:>14.6f} {comparisons:>18.3f}", flush=True)
    print(f"Measurements saved to: {save_measurements(linear_rows, 'time_complexity_linear.csv')}")
    try:
        graph = save_graph(rows)
        linear_graph = save_linear_graph(linear_rows)
    except ModuleNotFoundError as error:
        if error.name != "matplotlib":
            raise
        print("To generate the graph, install: python -m pip install -r requirements-benchmark.txt")
    else:
        print(f"Graph saved to: {graph}")
        print(f"Linear graph saved to: {linear_graph}")
        print("Both graphs also have PNG copies with the same filenames.")
    print("Timing uses ordinary integer keys; comparison counts use a separate instrumented run.")
    print("Timings include timer overhead and machine noise; growth curves illustrate complexity, not a proof.")


def positive_integer(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return number


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Measure RB insertion growth in comparisons and milliseconds.")
    parser.add_argument("--sizes", type=positive_integer, nargs="+", default=BENCHMARK_SIZES)
    parser.add_argument("--linear-sizes", type=positive_integer, nargs="+", default=LINEAR_BENCHMARK_SIZES,
                        help="tree sizes for the additional single-insertion plot with a linear x-axis")
    parser.add_argument("--repeats", type=positive_integer, default=5)
    parser.add_argument("--trials", type=positive_integer, default=1000,
                        help="single-insertion probes per timing run")
    args = parser.parse_args()
    if min([*args.sizes, *args.linear_sizes]) < 2:
        parser.error("sizes must be at least 2")
    print_benchmark(tuple(sorted(set(args.sizes))), args.repeats, args.trials,
                    tuple(sorted(set(args.linear_sizes))))
