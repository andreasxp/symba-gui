from argparse import ArgumentParser
from pathlib import Path


def window_pos(wp_str):
    result = [int(x) for x in wp_str.split(",")]

    if len(result) != 2:
        raise ValueError("incorrect number of dimensions")

    return result


def parse_args():
    """Parse command-line arguments for symba."""
    parser = ArgumentParser()
    parser.add_argument("path", nargs='?', type=Path, help="path to a .symba file that will be opened at launch")
    parser.add_argument("--window-pos", type=window_pos, help="X,Y - override window position on the screen")

    return parser.parse_args()
