"""Stage a map and HTTP artifact bundle or publish it after review."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from road_safety_command import run


def stage(output, inputs, approvals):
    from phase4_staging import stage_visualizations

    stage_visualizations(output, inputs, approvals)


def main(argv=None):
    run("visualizations", stage, argv)


if __name__ == "__main__":
    main()
