from pathlib import Path, PurePosixPath, PureWindowsPath


FORBIDDEN_NAMES = {
    ".env",
    ".env.backup",
    ".git",
    ".secrets",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "labhub.env",
    "license.key",
    "private-key",
    "private_key",
    "privatekey",
    "tmp",
}
FORBIDDEN_PREFIXES = (".codex", ".env", ".git", ".secrets")
FORBIDDEN_SUFFIXES = {
    ".cer",
    ".cert",
    ".crt",
    ".csr",
    ".der",
    ".jks",
    ".key",
    ".keystore",
    ".license",
    ".p12",
    ".p7b",
    ".pem",
    ".pfx",
    ".ppk",
}


def forbidden_release_reason(relative_path):
    path = PurePosixPath(str(relative_path).replace("\\", "/"))
    for part in path.parts:
        normalized_part = part.casefold()
        if normalized_part in FORBIDDEN_NAMES:
            return f"forbidden name {part}"
        if normalized_part.startswith(FORBIDDEN_PREFIXES):
            return f"forbidden metadata name {part}"
        if PurePosixPath(normalized_part).suffix in FORBIDDEN_SUFFIXES:
            return f"forbidden sensitive suffix in {part}"
    return None


def load_protected_modules(allowlist_path):
    protected = []
    for line_number, raw_entry in enumerate(
        Path(allowlist_path).read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        entry = raw_entry.strip()
        if not entry:
            continue

        path = PurePosixPath(entry)
        has_windows_semantics = (
            "\\" in entry
            or bool(PureWindowsPath(entry).drive)
            or any(":" in part for part in path.parts)
        )
        if path.is_absolute() or has_windows_semantics or ".." in path.parts:
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
        reason = forbidden_release_reason(relative_path)
        if reason:
            errors.append(f"Forbidden release entry: {relative_path} ({reason})")

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
