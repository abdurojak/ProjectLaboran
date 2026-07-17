import argparse
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath

try:
    from deployment.artifact import inspect_release_tree, load_protected_modules
except ModuleNotFoundError:
    from artifact import inspect_release_tree, load_protected_modules


def _validate_archive(archive):
    validated_members = []
    for member in archive.getmembers():
        normalized_name = member.name.replace("\\", "/")
        member_path = PurePosixPath(normalized_name)
        if (
            member_path.is_absolute()
            or PureWindowsPath(normalized_name).drive
            or any(":" in part for part in member_path.parts)
            or ".." in member_path.parts
        ):
            raise ValueError(f"Unsafe archive path: {member.name}")
        if member.issym() or member.islnk():
            raise ValueError(f"Unsafe archive link: {member.name}")
        if not (member.isfile() or member.isdir()):
            raise ValueError(f"Unsafe archive entry: {member.name}")
        validated_members.append((member, member_path))
    return validated_members


def _extract_archive(artifact, destination):
    destination = Path(destination)
    with tarfile.open(artifact, "r:gz") as archive:
        validated_members = _validate_archive(archive)
        for member, member_path in validated_members:
            target = destination.joinpath(*member_path.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"Unreadable archive entry: {member.name}")
            with source, target.open("wb") as extracted_file:
                shutil.copyfileobj(source, extracted_file)


def verify_artifact(artifact, allowlist):
    artifact = Path(artifact)
    protected = load_protected_modules(allowlist)

    if artifact.is_dir():
        return inspect_release_tree(artifact, protected)
    if not artifact.is_file():
        return [f"Artifact does not exist: {artifact}"]

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            _extract_archive(artifact, temp_dir)
            return inspect_release_tree(temp_dir, protected)
    except (tarfile.TarError, ValueError) as exc:
        return [str(exc)]


def _parse_args():
    parser = argparse.ArgumentParser(description="Verify a protected release artifact.")
    parser.add_argument("artifact")
    parser.add_argument("--allowlist", required=True)
    return parser.parse_args()


def main():
    args = _parse_args()
    errors = verify_artifact(args.artifact, args.allowlist)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"Protected artifact verified: {Path(args.artifact).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
