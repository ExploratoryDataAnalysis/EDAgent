"""Stage historical screening where supported or publish reviewed results."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from road_safety_command import run


def stage(output, inputs, approvals):
    from phase4_staging import stage_screening

    stage_screening(output, inputs, approvals)


def main(argv=None):
    run("concentration", stage, argv)


if __name__ == "__main__":
    main()
