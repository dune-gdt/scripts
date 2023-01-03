#!/usr/bin/env python3

"""Find 0-byte files recursively in dir tree.

Usage:
  find_zero_byte_files.py [DIRECTORY] [PATTERN]

Options:
  -h --help     Show this screen.
  -d --delete   print delete command.
"""
from docopt import docopt
import os
import fnmatch


def get_zero_files(dir, pattern):
    zeroes = []
    for path, dirs, files in os.walk(dir):
        for filename in fnmatch.filter(files, pattern):
            fn = os.path.join(path, filename)
            size = os.path.getsize(fn)
            if os.path.isfile(fn) and size == 0:
                zeroes.append(fn)
    return zeroes


if __name__ == "__main__":
    arguments = docopt(__doc__)
    directory = arguments["DIRECTORY"] or os.getcwd()
    pattern = arguments["PATTERN"] or "*"
    print(" ".join(get_zero_files(directory, pattern)))
    if arguments.get("--delete"):
        print("\nrm -rf ".join(get_zero_files(directory, pattern)))
