import argparse
import filecmp
import hashlib
import json
import itertools
import pathlib
import re
import shutil
from pathlib import Path
from typing import List, Callable, Optional


NO_INTERACTION = False


def get_decision_factory(msg_fstring: str) -> Callable[[Path], bool]:
    global NO_INTERACTION
    if NO_INTERACTION:
        def get_decision(*args, **kwargs):
            return True

        return get_decision

    forall = None

    def get_decision(path: Path, format_extras: Optional[List[str]] = None):
        nonlocal forall
        if forall is not None:
            return forall

        user_input = input(
            msg_fstring % tuple([path] + (format_extras or [])) + "\n[(Y)es to all | (y)es | (n)o | (N)o to all] > "
        )
        assert user_input in "YyNn"

        if user_input in "YN":
            forall = user_input == "Y"

        return user_input.lower() == "y"

    return get_decision


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        help="Operation to perform",
        choices=["copy_missing", "remove_duplicates", "remove_versions", "remove_empty", "remove_temporary", "fix_access", "fix_names"],
        nargs=1,
    )
    parser.add_argument("x", help="Target dir", type=pathlib.Path)
    parser.add_argument(
        "y",
        nargs="*",
        help="Additional dirs to check against the target",
        type=pathlib.Path,
    )
    parser.add_argument("--no-interaction", action="store_true", help="Answer 'yes' to all questions")
    parser.add_argument("-c", "--config", help="Path to config file", type=Path, default=Path("~/.clean_files"))
    return parser.parse_args()


def _remove_empty(dirs: List[Path]):
    get_decision = get_decision_factory("Remove empty file %s?")

    for path in itertools.chain(*[d.rglob("*") for d in dirs]):
        if not path.is_file() or path.stat().st_size != 0:
            continue

        if get_decision(path):
            path.unlink()
            print(f"Deleted file {path}")
        else:
            print(f"Skipped file {path}")


def _remove_tmp(dirs: List[Path], extensions: List[str]):
    get_decision = get_decision_factory("Remove temporary file %s?")

    for path in itertools.chain(*[d.rglob(f"*{ext}") for ext in extensions for d in dirs]):
        if not path.is_file():
            continue

        if get_decision(path):
            path.unlink()
            print(f"Deleted file {path}")
        else:
            print(f"Skipped file {path}")


def _fix_mode(dirs: List[Path], desired: int):
    get_decision = get_decision_factory(f"Set access {desired:o}" + " on %s? (current %s)")

    for path in itertools.chain(*[d.rglob("*") for d in dirs]):
        mode = path.stat().st_mode & 0o777

        if not path.is_file() or mode == desired:
            continue

        if get_decision(path, [f"{mode:o}"]):
            path.chmod(desired)
            print(f"Adjusted mode of {path}")
        else:
            print(f"Skipped file {path}")


def _fix_filenames(dirs: List[Path], illegal_chars: str, subst_char: str):
    assert len(subst_char) == 1

    get_decision = get_decision_factory("Rename %s to %s?")

    illegal_chars = str(set(illegal_chars))
    regexp = re.compile(rf"[{re.escape(illegal_chars)}]")
    for path in itertools.chain(*[d.rglob("*") for d in dirs]):
        if not path.is_file() or not regexp.search(path.stem):
            continue

        new_name = regexp.sub(subst_char, path.stem) + path.suffix
        if get_decision(path, [new_name]):
            path_str = str(path)
            path.rename(path.parent / new_name)
            print(f"Renamed {path_str} to {path.name}")
        else:
            print(f"Skipped file {path}")


def _get_digest(file: Path):
    checksum = hashlib.sha256(file.read_bytes()).hexdigest()
    filesize = file.stat().st_size

    return checksum, filesize


def _remove_duplicates(paths: List[Path]):
    get_decision = get_decision_factory("Remove duplicate file %s?")

    files = [file for path in paths for file in path.rglob("*") if file.is_file()]

    unique = {}
    duplicates = []
    for file in files:
        checksum = _get_digest(file)
        if checksum not in unique:
            unique[checksum] = file
        else:
            if file.stat().st_mtime < unique[checksum].stat().st_mtime:
                duplicates.append(unique[checksum])
                unique[checksum] = file
            else:
                duplicates.append(file)

    for file in duplicates:
        if get_decision(file):
            file.unlink()
            print(f"Deleted file {file}")
        else:
            print(f"Skipped file {file}")


def _remove_versions(x: Path, y: List[Path]):
    get_decision = get_decision_factory("Remove old file %s?")

    files = [file for path in [x] + y for file in path.rglob("*") if file.is_file()]
    versions = {}
    for file in files:
        if file.name not in versions:
            versions[file.name] = []
        versions[file.name].append(file)

    for name, versions in versions.items():
        newest = max(versions, key=lambda version: version.stat().st_mtime,
               default=None)
        older = [version for version in versions if version != newest]
        for old in older:
            if get_decision(old):
                old.unlink()
                print(f"Deleted file {file}")
            else:
                print(f"Skipped file {file}")



def _copy_all_to_x(x: Path, y: List[Path]):
    get_decision = get_decision_factory("Copy %s to %s?")

    files_to_copy = []
    common_subdirs = {}
    for ydir in y:
        diff = filecmp.dircmp(x, ydir)
        for f in diff.right_only:
            if (ydir / Path(f)).is_dir():
                files_to_copy.extend(
                    [(ydir, Path(f).relative_to(ydir)) for f in (ydir / Path(f)).rglob("*") if f.is_file()]
                )

            if not (ydir / Path(f)).is_file():
                continue

            files_to_copy.append((Path(f)))

        common_subdirs = {**common_subdirs, **{Path(d): (df, ydir) for d, df in diff.subdirs.items()}}

    for d, (diff, ydir) in common_subdirs.items():
        for f in diff.right_only:
            f = d / f
            if (ydir / f).is_dir():
                files_to_copy.extend(
                    [(ydir, Path(f).relative_to(ydir)) for f in (ydir / Path(f)).rglob("*") if f.is_file()]
                )

            if not (ydir / f).is_file():
                continue

            files_to_copy.append(Path(f))

        common_subdirs = {**common_subdirs, **{f / Path(d): (df, ydir) for d, df in diff.subdirs.items()}}

    for ydir, file in files_to_copy:
        new_file = x / file
        if get_decision(ydir / file, [new_file]):
            new_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ydir / file, new_file)
            print(f"Copied {ydir / file} to {new_file}")
        else:
            print(f"Skipped file {file}")


def main():
    args = parse_args()
    if args.no_interaction:
        global NO_INTERACTION
        NO_INTERACTION = True

    with open(args.config.expanduser(), mode="r", encoding="utf-8") as fp:
        config = json.load(fp)

    if not (
        config.get("desired_attrs")
        and config.get("illegal_chars")
        and config.get("subst_char")
        and config.get("tmp_extensions")
    ):
        print("Malformed config")
        exit(1)
    config["desired_attrs"] = int(f"0o{config['desired_attrs']}", base=8)

    mode = args.mode[0]

    assert all([d.is_dir() for d in [args.x] + args.y])

    if mode == "copy_missing":
        _copy_all_to_x(args.x, args.y)
    elif mode == "remove_duplicates":
        _remove_duplicates([args.x] + args.y)
    elif mode == "remove_versions":
        _remove_versions(args.x, args.y)
    elif mode == "remove_empty":
        _remove_empty([args.x] + args.y)
    elif mode == "remove_temporary":
        _remove_tmp([args.x] + args.y, extensions=config["tmp_extensions"])
    elif mode == "fix_access":
        _fix_mode([args.x] + args.y, desired=config["desired_attrs"])
    elif mode == "fix_names":
        _fix_filenames([args.x] + args.y, illegal_chars=config["illegal_chars"], subst_char=config["subst_char"])

    print("DONE!")


if __name__ == "__main__":
    main()
