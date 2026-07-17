import argparse
import shutil
import tarfile
from pathlib import Path

from Cython.Build import cythonize
from setuptools import Distribution, Extension
from setuptools.command.build_ext import build_ext

try:
    from deployment.artifact import inspect_release_tree, load_protected_modules
except ModuleNotFoundError:
    from artifact import inspect_release_tree, load_protected_modules


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
        if name in EXCLUDED_NAMES:
            ignored.add(name)
        elif name.endswith((".pyc", ".pyo", ".pem")):
            ignored.add(name)
        elif name == "tests.py" or name.startswith("test_") and name.endswith(".py"):
            ignored.add(name)
        elif name.endswith("_test.py"):
            ignored.add(name)
    return ignored


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


def build_artifact(source, staging, output, allowlist):
    source = Path(source).resolve()
    staging = Path(staging).resolve()
    output = Path(output).resolve()
    protected = load_protected_modules(allowlist)

    if staging.exists():
        shutil.rmtree(staging)
    staging.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, staging, ignore=_ignore_source_entries)

    _compile_protected_modules(staging, protected)
    errors = inspect_release_tree(staging, protected)
    if errors:
        raise RuntimeError("\n".join(errors))

    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz") as archive:
        for path in sorted(staging.iterdir()):
            archive.add(path, arcname=path.name)


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
