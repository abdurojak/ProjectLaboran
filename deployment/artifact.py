from pathlib import Path, PurePosixPath


FORBIDDEN_NAMES = {".env", ".env.backup", ".git", ".secrets"}
FORBIDDEN_SUFFIXES = {".pem"}


def load_protected_modules(allowlist_path):
    protected = []
    for line_number, raw_entry in enumerate(
        Path(allowlist_path).read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        entry = raw_entry.strip().replace("\\", "/")
        if not entry:
            continue

        path = PurePosixPath(entry)
        has_windows_drive = bool(path.parts and path.parts[0].endswith(":"))
        if path.is_absolute() or has_windows_drive or ".." in path.parts:
            raise ValueError(
                f"Invalid protected module at line {line_number}: {raw_entry!r}"
            )
        if path == PurePosixPath(".") or path.suffix != ".py":
            raise ValueError(
                f"Invalid protected module at line {line_number}: {raw_entry!r}"
            )

        protected.append(path)

    return protected


def inspect_release_tree(release_root, protected):
    release_root = Path(release_root)
    errors = []

    for path in sorted(release_root.rglob("*")):
        relative_path = path.relative_to(release_root).as_posix()
        if path.name in FORBIDDEN_NAMES:
            errors.append(f"Forbidden release entry: {relative_path}")
        if path.suffix in FORBIDDEN_SUFFIXES:
            errors.append(f"Forbidden release suffix: {relative_path}")

    for protected_path in protected:
        source_path = release_root.joinpath(*protected_path.parts)
        if source_path.exists():
            errors.append(f"Protected source is present: {protected_path.as_posix()}")

        stem = protected_path.stem
        extension_dir = source_path.parent
        has_extension = any(
            extension.is_file() for extension in extension_dir.glob(f"{stem}.*.so")
        ) or (extension_dir / f"{stem}.pyd").is_file()
        if not has_extension:
            errors.append(
                f"Native extension is missing for: {protected_path.as_posix()}"
            )

    return errors
