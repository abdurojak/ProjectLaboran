#!/usr/bin/env bash

set -Eeuo pipefail
umask 022

BASE_DIR=/home/admin/LabTif
RELEASES_DIR="$BASE_DIR/releases"
CURRENT_LINK="$BASE_DIR/current"
VENV_DIR="$BASE_DIR/production-venv"
SERVICE=projectlaboran-daphne

LOCK_FILE="$BASE_DIR/.deploy.lock"
TEMP_RELEASE=""
TEMP_LINK=""
REPLACED_RELEASE_BACKUP=""
FAILED_RELEASE=""
PREVIOUS_CURRENT=""
CURRENT_SWITCHED=false

usage() {
    printf 'Usage: %s <protected-release.tar.gz>\n' "$0" >&2
}

safe_remove_internal_tree() {
    local path=$1
    local name

    [[ -n "$path" && "$(dirname -- "$path")" == "$RELEASES_DIR" ]] || return 1
    name=$(basename -- "$path")
    case "$name" in
        ".deploy-${GITHUB_SHA}."*|".replaced-${GITHUB_SHA}."*|".failed-${GITHUB_SHA}."*) ;;
        *) return 1 ;;
    esac
    rm -rf --one-file-system -- "$path"
}

safe_remove_release() {
    local path=$1
    local resolved parent name active

    [[ -d "$path" && ! -L "$path" ]] || return 1
    resolved=$(readlink -f -- "$path") || return 1
    parent=$(dirname -- "$resolved")
    name=$(basename -- "$resolved")
    [[ "$parent" == "$RELEASES_DIR" ]] || return 1
    [[ "$name" =~ ^[0-9a-fA-F]{40}$ ]] || return 1
    [[ "$resolved" != "$RELEASE_DIR" ]] || return 1

    active=""
    if [[ -e "$CURRENT_LINK" || -L "$CURRENT_LINK" ]]; then
        active=$(readlink -f -- "$CURRENT_LINK") || return 1
    fi
    [[ "$resolved" != "$active" ]] || return 1
    rm -rf --one-file-system -- "$resolved"
}

atomic_switch_current() {
    local target=$1

    TEMP_LINK="$BASE_DIR/.current.${GITHUB_SHA}.$$"
    [[ ! -e "$TEMP_LINK" && ! -L "$TEMP_LINK" ]] || return 1
    ln -s -- "$target" "$TEMP_LINK"
    mv -Tf -- "$TEMP_LINK" "$CURRENT_LINK"
    TEMP_LINK=""
}

restore_replaced_release() {
    [[ -n "$REPLACED_RELEASE_BACKUP" ]] || return 0
    [[ -d "$REPLACED_RELEASE_BACKUP" && ! -L "$REPLACED_RELEASE_BACKUP" ]] || return 1

    if [[ -e "$RELEASE_DIR" || -L "$RELEASE_DIR" ]]; then
        [[ -d "$RELEASE_DIR" && ! -L "$RELEASE_DIR" ]] || return 1
        FAILED_RELEASE="$RELEASES_DIR/.failed-${GITHUB_SHA}.$$"
        mv -- "$RELEASE_DIR" "$FAILED_RELEASE" || return 1
    fi
    if ! mv -- "$REPLACED_RELEASE_BACKUP" "$RELEASE_DIR"; then
        if [[ -n "$FAILED_RELEASE" && -d "$FAILED_RELEASE" ]]; then
            mv -- "$FAILED_RELEASE" "$RELEASE_DIR" || true
        fi
        return 1
    fi
    REPLACED_RELEASE_BACKUP=""
    if [[ -n "$FAILED_RELEASE" ]]; then
        safe_remove_internal_tree "$FAILED_RELEASE" || return 1
        FAILED_RELEASE=""
    fi
}

cleanup_ephemeral() {
    set +e
    if [[ -n "$TEMP_LINK" && ! -e "$TEMP_LINK" && -L "$TEMP_LINK" ]]; then
        rm -f -- "$TEMP_LINK"
    elif [[ -n "$TEMP_LINK" && -L "$TEMP_LINK" ]]; then
        rm -f -- "$TEMP_LINK"
    fi
    if [[ -n "$TEMP_RELEASE" && -d "$TEMP_RELEASE" && ! -L "$TEMP_RELEASE" ]]; then
        safe_remove_internal_tree "$TEMP_RELEASE"
    fi
}

on_error() {
    local original_status=$?
    local rollback_failed=false

    trap - ERR
    set +e
    printf 'Deployment failed; preserving the original error status (%d).\n' "$original_status" >&2

    if [[ "$CURRENT_SWITCHED" == true ]]; then
        if ! restore_replaced_release; then
            printf 'Rollback warning: could not restore the replaced release directory.\n' >&2
            rollback_failed=true
        fi

        if [[ -n "$PREVIOUS_CURRENT" ]]; then
            if atomic_switch_current "$PREVIOUS_CURRENT"; then
                if ! sudo -n systemctl restart "$SERVICE"; then
                    printf 'Rollback warning: restored current but service restart failed.\n' >&2
                    rollback_failed=true
                fi
            else
                printf 'Rollback warning: could not restore the previous current symlink.\n' >&2
                rollback_failed=true
            fi
        else
            if [[ -L "$CURRENT_LINK" ]]; then
                rm -f -- "$CURRENT_LINK" || rollback_failed=true
            else
                printf 'Rollback warning: failed current path is not a removable symlink.\n' >&2
                rollback_failed=true
            fi
            if ! sudo -n systemctl stop "$SERVICE"; then
                printf 'Rollback warning: no prior release exists and the service could not be stopped.\n' >&2
                rollback_failed=true
            else
                printf 'No prior release exists; removed current and stopped %s.\n' "$SERVICE" >&2
            fi
        fi
    elif ! restore_replaced_release; then
        printf 'Cleanup warning: could not restore the inactive release that was replaced.\n' >&2
        rollback_failed=true
    fi

    cleanup_ephemeral
    if [[ "$rollback_failed" == true ]]; then
        printf 'Rollback was incomplete; operator intervention is required.\n' >&2
    fi
    exit "$original_status"
}

probe_service() {
    local attempt status

    for attempt in {1..15}; do
        if status=$(curl --silent --show-error --output /dev/null \
            --write-out '%{http_code}' --connect-timeout 2 --max-time 5 \
            'http://127.0.0.1:8000/'); then
            if [[ "$status" =~ ^[0-9]{3}$ ]] && ((10#$status < 500)); then
                return 0
            fi
        fi
        if ((attempt < 15)); then
            sleep 2
        fi
    done
    printf 'Health check failed after %d attempts.\n' "$attempt" >&2
    return 1
}

cleanup_old_releases() {
    local inactive_kept=0
    local name candidate cleanup_failed=false

    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        candidate="$RELEASES_DIR/$name"
        if [[ "$candidate" == "$RELEASE_DIR" ]]; then
            continue
        fi
        if [[ "$inactive_kept" -lt 2 ]]; then
            ((inactive_kept += 1))
            continue
        fi
        if ! safe_remove_release "$candidate"; then
            printf 'Cleanup warning: retained release %s because it could not be removed safely.\n' "$name" >&2
            cleanup_failed=true
        fi
    done < <(
        find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d \
            -regextype posix-extended -regex '.*/[0-9a-fA-F]{40}' \
            -printf '%T@ %f\n' | sort -rn | cut -d' ' -f2-
    )

    [[ "$cleanup_failed" == false ]]
}

if [[ $# -ne 1 ]]; then
    usage
    exit 2
fi

if [[ -z "${GITHUB_SHA:-}" || ! "$GITHUB_SHA" =~ ^[0-9a-fA-F]{40}$ ]]; then
    printf 'GITHUB_SHA must be exactly 40 hexadecimal characters.\n' >&2
    exit 2
fi

ARCHIVE=$1
if [[ ! -f "$ARCHIVE" || ! -r "$ARCHIVE" ]]; then
    printf 'Protected release archive must be a readable regular file.\n' >&2
    exit 2
fi
ARCHIVE=$(readlink -f -- "$ARCHIVE")

[[ -d "$BASE_DIR" ]] || { printf 'Base directory is missing: %s\n' "$BASE_DIR" >&2; exit 1; }
[[ -d "$RELEASES_DIR" && ! -L "$RELEASES_DIR" ]] || {
    printf 'Releases directory is missing or unsafe: %s\n' "$RELEASES_DIR" >&2
    exit 1
}
RELEASES_DIR=$(readlink -f -- "$RELEASES_DIR")
[[ "$RELEASES_DIR" == "$BASE_DIR/releases" ]] || {
    printf 'Releases directory must resolve to %s/releases.\n' "$BASE_DIR" >&2
    exit 1
}

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    printf 'Another deployment is already running.\n' >&2
    exit 1
fi

RELEASE_DIR="$RELEASES_DIR/$GITHUB_SHA"
if [[ -e "$CURRENT_LINK" || -L "$CURRENT_LINK" ]]; then
    PREVIOUS_CURRENT=$(readlink -f -- "$CURRENT_LINK") || {
        printf 'Current is present but cannot be resolved safely.\n' >&2
        exit 1
    }
    case "$PREVIOUS_CURRENT" in
        "$RELEASES_DIR"/*) ;;
        *) printf 'Current resolves outside the releases directory.\n' >&2; exit 1 ;;
    esac
    [[ "$(dirname -- "$PREVIOUS_CURRENT")" == "$RELEASES_DIR" ]] || {
        printf 'Current must resolve to a direct child of the releases directory.\n' >&2
        exit 1
    }
    [[ "$(basename -- "$PREVIOUS_CURRENT")" =~ ^[0-9a-fA-F]{40}$ ]] || {
        printf 'Current must resolve to a SHA-named release directory.\n' >&2
        exit 1
    }
fi

if [[ "$PREVIOUS_CURRENT" == "$RELEASE_DIR" ]]; then
    printf 'Release %s is already active; refusing to replace it in place.\n' "$GITHUB_SHA" >&2
    exit 1
fi

trap on_error ERR
trap cleanup_ephemeral EXIT

TEMP_RELEASE=$(mktemp -d "$RELEASES_DIR/.deploy-${GITHUB_SHA}.XXXXXX")
chmod 0700 "$TEMP_RELEASE"

python3 - "$ARCHIVE" "$TEMP_RELEASE" <<'PY'
import os
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath, PureWindowsPath

archive_path = Path(sys.argv[1])
destination = Path(sys.argv[2])

with tarfile.open(archive_path, "r:gz") as archive:
    members = archive.getmembers()
    validated = []
    seen = set()
    for member in members:
        name = member.name
        normalized = name.replace("\\", "/")
        member_path = PurePosixPath(normalized)
        if (
            not name
            or "\\" in name
            or member_path.is_absolute()
            or PureWindowsPath(normalized).drive
            or ".." in member_path.parts
            or any(":" in part for part in member_path.parts)
        ):
            raise ValueError("unsafe archive path")
        if member.type not in {tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE}:
            raise ValueError("unsafe archive entry type")
        key = tuple(member_path.parts)
        if key in seen:
            raise ValueError("duplicate archive path")
        seen.add(key)
        validated.append((member, member_path))

    for member, member_path in validated:
        target = destination.joinpath(*member_path.parts)
        if member.isdir():
            target.mkdir(mode=0o755, parents=True, exist_ok=False)
            continue
        if member_path == PurePosixPath("."):
            raise ValueError("archive contains an invalid file path")
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise ValueError("unreadable archive entry")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(target, flags, 0o644)
        with source, os.fdopen(fd, "wb") as output:
            shutil.copyfileobj(source, output)
PY

[[ -f "$TEMP_RELEASE/requirements.txt" && -f "$TEMP_RELEASE/manage.py" ]] || {
    printf 'Archive does not contain the expected release root.\n' >&2
    false
}

if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi
[[ -x "$VENV_DIR/bin/python" ]] || {
    printf 'Production virtual environment is invalid: %s\n' "$VENV_DIR" >&2
    false
}

"$VENV_DIR/bin/python" -m pip install --disable-pip-version-check \
    --requirement "$TEMP_RELEASE/requirements.txt"
(
    cd "$TEMP_RELEASE"
    "$VENV_DIR/bin/python" manage.py migrate --noinput
    "$VENV_DIR/bin/python" manage.py collectstatic --noinput
)

if [[ -e "$RELEASE_DIR" || -L "$RELEASE_DIR" ]]; then
    [[ -d "$RELEASE_DIR" && ! -L "$RELEASE_DIR" ]] || {
        printf 'Existing release path is not a safe directory.\n' >&2
        false
    }
    [[ "$(readlink -f -- "$RELEASE_DIR")" == "$RELEASE_DIR" ]] || {
        printf 'Existing release directory does not resolve safely.\n' >&2
        false
    }
    REPLACED_RELEASE_BACKUP="$RELEASES_DIR/.replaced-${GITHUB_SHA}.$$"
    mv -- "$RELEASE_DIR" "$REPLACED_RELEASE_BACKUP"
fi

mv -- "$TEMP_RELEASE" "$RELEASE_DIR"
TEMP_RELEASE=""
atomic_switch_current "$RELEASE_DIR"
CURRENT_SWITCHED=true

sudo -n systemctl daemon-reload
sudo -n systemctl restart "$SERVICE"
sudo -n systemctl is-active --quiet "$SERVICE"
probe_service

if [[ -n "$REPLACED_RELEASE_BACKUP" ]]; then
    if safe_remove_internal_tree "$REPLACED_RELEASE_BACKUP"; then
        REPLACED_RELEASE_BACKUP=""
    else
        printf 'Cleanup warning: retained replaced release backup %s.\n' \
            "$REPLACED_RELEASE_BACKUP" >&2
    fi
fi
if ! cleanup_old_releases; then
    printf 'Cleanup warning: deployment succeeded but old-release cleanup was incomplete.\n' >&2
fi

trap - ERR
printf 'Deployment completed for release %s.\n' "$GITHUB_SHA"
