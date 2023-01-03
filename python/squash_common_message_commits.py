#!/usr/bin/env python3
import fileinput
import os
import subprocess
import sys

# Set to None for no filtering, otherwise commits to squash must start with this
MSG_PREFIX = None


def _reset_master():
    new_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], universal_newlines=True
    ).strip()
    subprocess.check_call(["git", "checkout", "master"])
    subprocess.check_call(["git", "reset", "--hard", new_commit])


def first_run(base):
    os.chdir(base)
    env = os.environ.copy()
    # rerun ourselves to select which actions to do on which commits
    env["GIT_SEQUENCE_EDITOR"] = os.path.abspath(__file__)
    # during reword, mark commits for autosquashing
    env["EDITOR"] = 'sed -i -e "1s/^/squash\!\ /" -e 1q'
    # edit mode
    subprocess.check_call(["git", "rebase", "-i", "--root", "HEAD"], env=env)
    _reset_master()

    # squash everything marked
    del env["GIT_SEQUENCE_EDITOR"]
    env["EDITOR"] = "true"
    subprocess.check_output(
        ["git", "rebase", "--autosquash", "-i", "--root", "HEAD"], env=env
    )
    _reset_master()

    # And another pass to cleanup logs
    # reword every commit, remove "squash! *" and empty lines
    env["GIT_SEQUENCE_EDITOR"] = 'sed -i -e "s/pick/r/g"'
    env["EDITOR"] = "sed -i -n '/squash\!\|^\s*$/!p'"
    subprocess.check_call(["git", "rebase", "-i", "--root", "HEAD"], env=env)
    _reset_master()


def edit_mode(git_input):
    combos = set()
    for line in fileinput.input(files=git_input, inplace=True, backup=".orig"):
        tokens = line.split(" ")
        try:
            verb, commit, message = (  # noqa: F841
                tokens[0],
                tokens[1],
                " ".join(tokens[2:]),
            )
        except IndexError:
            # not a useful line
            continue
        if message in combos and (
            (MSG_PREFIX and message.startswith(MSG_PREFIX)) or MSG_PREFIX is None
        ):
            line = "r {} squash! {}".format(commit, message)
        else:
            combos.add(message)
        print(line)


if __name__ == "__main__":
    try:
        base = sys.argv[1]
    except IndexError:
        base = os.getcwd()
    if os.path.isdir(base):
        first_run(base)
    else:
        edit_mode(base)
