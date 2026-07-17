import argparse
import gzip
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

from Cython.Build import cythonize
from setuptools import Distribution, Extension
from setuptools.command.build_ext import build_ext

try:
    from deployment.artifact import (
        forbidden_release_reason,
        inspect_release_tree,
        load_protected_modules,
    )
except ModuleNotFoundError:
    from artifact import (
        forbidden_release_reason,
        inspect_release_tree,
        load_protected_modules,
    )


EXCLUDED_NAMES = {
    ".env",
    ".env.backup",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".secrets",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "media",
    "staticfiles",
    "test",
    "tests",
    "venv",
}


def _ignore_source_entries(_directory, names):
    ignored = set()
    for name in names:
        if name in EXCLUDED_NAMES or forbidden_release_reason(name):
            ignored.add(name)
        elif name.endswith((".pyc", ".pyo")):
            ignored.add(name)
        elif name == "tests.py" or name.startswith("test_") and name.endswith(".py"):
            ignored.add(name)
        elif name.endswith("_test.py"):
            ignored.add(name)
    return ignored


def _validate_build_paths(source, staging, output):
    source = Path(source).resolve()
    staging = Path(staging).resolve()
    output = Path(output).resolve()

    if not source.is_dir():
        raise ValueError(f"source must be an existing directory: {source}")
    if staging == source or source.is_relative_to(staging):
        raise ValueError("staging cannot equal or contain source")
    if staging.exists() and not staging.is_dir():
        raise ValueError(f"staging must be a directory path: {staging}")
    if staging.is_relative_to(source):
        relative_staging = staging.relative_to(source)
        if not relative_staging.parts or relative_staging.parts[0] != "build":
            raise ValueError("staging inside source must be under the build directory")

    if output.exists() and output.is_dir():
        raise ValueError(f"output cannot be a directory: {output}")
    if output in {source, staging}:
        raise ValueError("output cannot equal source or staging")
    if output.is_relative_to(staging) or staging.is_relative_to(output):
        raise ValueError("output cannot contain or be contained by staging")
    if output.is_relative_to(source):
        relative_output = output.relative_to(source)
        if not relative_output.parts or relative_output.parts[0] not in {
            "build",
            "dist",
        }:
            raise ValueError("output inside source must be under build or dist")

    return source, staging, output


def _compile_protected_modules(staging, protected):
    extensions = []
    for protected_path in protected:
        source_path = staging.joinpath(*protected_path.parts)
        if not source_path.is_file():
            raise FileNotFoundError(
                f"Protected module does not exist: {protected_path.as_posix()}"
            )
        module_name = ".".join(protected_path.with_suffix("").parts)
        extensions.append(Extension(module_name, [str(source_path)]))

    compiled_extensions = cythonize(
        extensions,
        compiler_directives={"language_level": 3},
    )
    distribution = Distribution(
        {"name": "projectlaboran-protected", "ext_modules": compiled_extensions}
    )
    command = build_ext(distribution)
    command.build_lib = str(staging)
    command.build_temp = str(staging.parent / "temp")
    command.ensure_finalized()
    command.run()

    for protected_path in protected:
        source_path = staging.joinpath(*protected_path.parts)
        tagged_pyds = sorted(source_path.parent.glob(f"{source_path.stem}.*.pyd"))
        plain_pyd = source_path.with_suffix(".pyd")
        if tagged_pyds and not plain_pyd.exists():
            tagged_pyds[0].replace(plain_pyd)

        source_path.unlink()
        generated_c = source_path.with_suffix(".c")
        if generated_c.exists():
            generated_c.unlink()


def _normalized_ustar_info(info):
    if info.type not in {tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE}:
        raise ValueError(
            f"USTAR archive entry must be a regular file or directory: {info.name!r}"
        )

    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    info.mode = 0o755 if info.isdir() else 0o644
    info.pax_headers = {}
    info.linkname = ""
    info.devmajor = 0
    info.devminor = 0
    try:
        info.tobuf(
            format=tarfile.USTAR_FORMAT,
            encoding="utf-8",
            errors="strict",
        )
    except (UnicodeError, ValueError) as error:
        raise ValueError(
            f"Path or metadata is not safely representable in USTAR: {info.name!r}"
        ) from error
    return info


def _write_archive(staging, output):
    staging = Path(staging)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=output.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as raw_output:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw_output,
                compresslevel=9,
                mtime=0,
            ) as compressed:
                with tarfile.open(
                    fileobj=compressed,
                    mode="w|",
                    format=tarfile.USTAR_FORMAT,
                    dereference=False,
                    encoding="utf-8",
                    errors="strict",
                ) as archive:
                    for path in sorted(staging.iterdir()):
                        archive.add(
                            path,
                            arcname=path.name,
                            recursive=True,
                            filter=_normalized_ustar_info,
                        )
            raw_output.flush()
            os.fsync(raw_output.fileno())
        os.replace(temporary, output)
    except ValueError:
        temporary.unlink(missing_ok=True)
        raise
    except (OSError, tarfile.TarError) as error:
        temporary.unlink(missing_ok=True)
        raise ValueError(
            f"Unable to create safe deterministic USTAR archive: {error}"
        ) from error


def build_artifact(source, staging, output, allowlist):
    source, staging, output = _validate_build_paths(source, staging, output)
    protected = load_protected_modules(allowlist)

    if staging.exists():
        shutil.rmtree(staging)
    staging.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, staging, ignore=_ignore_source_entries)

    _compile_protected_modules(staging, protected)
    errors = inspect_release_tree(staging, protected)
    if errors:
        raise RuntimeError("\n".join(errors))

    _write_archive(staging, output)


def _parse_args():
    parser = argparse.ArgumentParser(description="Build a protected release artifact.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--staging", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allowlist", required=True)
    return parser.parse_args()


def main():
    args = _parse_args()
    build_artifact(args.source, args.staging, args.output, args.allowlist)
    print(f"Protected artifact written to {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
