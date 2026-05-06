from pathlib import Path
import subprocess
import sys
import os
import pytest


# A small smoke test to ensure core example scripts remain runnable.
# It executes the example as a separate Python process with PYTHONPATH set
# to the engine source directory so imports work the same way users run them.


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "engine" / "src"

# A short list of representative examples to run quickly in CI. If you add
# more examples, include them here as needed. Keep the timeout small so the
# test suite stays fast.
EXAMPLES = [
    "engine/examples/simple_timeout_demo.py",
    "engine/examples/resource_priority_demo.py",
    "engine/examples/store_demo.py",
    "engine/examples/anyof_timeout_demo.py",
    "engine/examples/carwash.py",
    "engine/examples/clock_demo.py",
    "engine/examples/gas_station.py",
    "engine/examples/interrupt_demo.py",
    "engine/examples/machine_shop.py",
    "engine/examples/preemption_demo.py",
    "engine/examples/preemption_requeue_demo.py",
    "engine/examples/pretty_print_logger_demo.py",
    "engine/examples/pretty_print_logger_hold_demo.py",
    "engine/examples/physics_move_to_demo.py",
]


@pytest.mark.parametrize("example", EXAMPLES)
def test_example_runs(example):
    example_path = REPO_ROOT / example
    assert example_path.exists(), f"Example not found: {example_path}"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_PATH)

    # Run the example as a separate process. Keep timeout short to catch
    # obvious failures but avoid hanging CI.
    proc = subprocess.run(
        [sys.executable, str(example_path)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=12,
    )

    if proc.returncode != 0:
        # Show output to help debugging failures in CI logs.
        stdout = proc.stdout.decode(errors="replace")
        stderr = proc.stderr.decode(errors="replace")
        raise AssertionError(
            f"Example {example} exited with {proc.returncode}\n--- STDOUT ---\n{stdout}\n--- STDERR ---\n{stderr}"
        )
