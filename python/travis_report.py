#!/usr/bin/env python3

import os
import traceback
import subprocess

import format_check as fc

README = """
The code you have published does not conform to the project's coding style
 (see also https://github.com/{slug}/blob/master/CONTRIBUTING.md).
We have automatically applied clang-format for your published code, for your convenience.
Please consider applying clang-format locally before commiting the next time (for instance by installing a pre-commit
hook found in https://github.com/wwu-numerik/git-hooks).

In order to incorporate these changes, open up a terminal and
* go to the location which contains the code you are trying to publish,
* download the prepared patch, for instance by executing
    wget THIS_FILES_URL
* make sure the patch can be applied
    git apply --check diff.txt
* apply the patch
    git apply diff.txt

You can now commit these changes in the usual way or amend your previous commits to immediately include the correct code formatting.

If you have any questions, please add a comment in the pull request.


"""  # noqa: E501


def get_patch_for_dir(basedir):
    """
    :param basedir: absolute path to git root
    :param mode: anyof 'staged', 'modified' or 'all' to select which files to check. Note
                    staged files do not count as modified
    :return: diff string
    """
    os.chdir(basedir)
    # alternative clang-format binary given?
    try:
        clangformat = subprocess.check_output(
            ["git", "config", "hooks.clangformat"], universal_newlines=True
        ).strip()
    except subprocess.CalledProcessError as _:  # noqa: F841
        clangformat = "clang-format"

    files = [
        f
        for f in subprocess.check_output(
            ["git", "ls-files"], universal_newlines=True
        ).splitlines()
        if os.path.splitext(f)[-1] in fc.CPP_EXTENSIONS
    ]
    for filename in files:
        subprocess.check_output(
            [clangformat, "-i", "-style=file", filename], universal_newlines=True
        )
    return subprocess.check_output(["git", "diff"], universal_newlines=True)


def clang_format_status(dirname):
    import requests

    token = os.environ["STATUS_TOKEN"]
    auth = ("dune-community-bot", token)
    pr = os.environ["TRAVIS_PULL_REQUEST"]
    slug = os.environ["TRAVIS_REPO_SLUG"]
    if pr == "false":
        statuses_url = "https://api.github.com/repos/{}/statuses/{}".format(
            slug, os.environ["TRAVIS_COMMIT"]
        )
    else:
        r = requests.get(
            "https://api.github.com/repos/{}/pulls/{}".format(slug, pr), auth=auth
        )
        statuses_url = r.json()["statuses_url"]

    r = requests.post(
        statuses_url,
        auth=auth,
        json={
            "state": "pending",
            "description": "Checking if clang-format has been applied to all source files",
            "context": "ci/clang-format",
        },
    )
    target_url = None
    try:
        fails = fc.check_dir(dirname, mode="all")
    except Exception as e:
        state = "error"
        fails = [str(e)]
        traceback.print_exc()
        msg = "the check itself errored out"
    else:
        state = "failure" if len(fails) > 0 else "success"
        msg = "All good"
        if len(fails) > 0:
            patchname = "diff.txt"
            if pr != "false":
                desc = "clang-format git diff for {} PR {}".format(slug, pr)
            else:
                desc = "clang-format git diff for {} Commit {}".format(
                    slug, os.environ["TRAVIS_COMMIT"]
                )
            r = requests.post(
                "https://api.github.com/gists",
                auth=auth,
                json={
                    "public": "true",
                    "description": desc,
                    "files": {
                        patchname: {
                            "content": README.format(slug=slug)
                            + get_patch_for_dir(dirname)
                        }
                    },
                },
            )
            print(r)
            print(r.json())
            target_url = r.json()["files"][patchname]["raw_url"]
            msg = "Found unformatted files"

    r = requests.post(
        statuses_url,
        auth=auth,
        json={
            "state": state,
            "description": msg,
            "context": "ci/clang-format",
            "target_url": target_url,
        },
    )
