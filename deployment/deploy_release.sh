#!/usr/bin/env bash

set -Eeuo pipefail
umask 022

BASE_DIR=/home/admin/LabTif
RELEASES_DIR="$BASE_DIR/releases"
CURRENT_LINK="$BASE_DIR/current"
VENV_DIR="$BASE_DIR/production-venv"
SERVICE=projectlaboran-daphne

SYSTEMCTL=/usr/bin/systemctl
LOCK_FILE="$BASE_DIR/.deploy.lock"
TEMP_RELEASE=""
TEMP_LINK=""
REPLACED_RELEASE_BACKUP=""
FAILED_RELEASE=""
PREVIOUS_CURRENT=""
RELEASE_DIR=""
PUBLICATION_STARTED=false
PUBLISHED=false
CURRENT_SWITCHED=false
HANDLING_FAILURE=false

usage() {
    printf 'Usage: %s <protected-release.tar.gz>\n' "$0" >&2
}

current_target_path() {
    local raw

    if [[ -L "$CURRENT_LINK" ]]; then
        raw=$(readlink -- "$CURRENT_LINK") || return 1
        if [[ "$raw" == /* ]]; then
            readlink -m -- "$raw"
        else
            readlink -m -- "$BASE_DIR/$raw"
        fi
    elif [[ -e "$CURRENT_LINK" ]]; then
        readlink -f -- "$CURRENT_LINK"
    else
        return 1
    fi
}

safe_remove_internal_tree() {
    local path=$1
    local name active

    [[ -n "$path" && "$(dirname -- "$path")" == "$RELEASES_DIR" ]] || return 1
    [[ -d "$path" && ! -L "$path" ]] || return 1
    name=$(basename -- "$path")
    [[ "$name" =~ ^\.(deploy|replaced|failed)-[0-9a-fA-F]{40}\.[A-Za-z0-9]+$ ]] || return 1
    active=$(current_target_path 2>/dev/null || true)
    [[ "$path" != "$active" ]] || return 1
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
    active=$(current_target_path 2>/dev/null || true)
    [[ "$resolved" != "$active" ]] || return 1
    rm -rf --one-file-system -- "$resolved"
}

safe_remove_deployed_release() {
    local active

    [[ -n "$RELEASE_DIR" ]] || return 1
    [[ "$(dirname -- "$RELEASE_DIR")" == "$RELEASES_DIR" ]] || return 1
    [[ "$(basename -- "$RELEASE_DIR")" =~ ^[0-9a-fA-F]{40}$ ]] || return 1
    [[ -d "$RELEASE_DIR" && ! -L "$RELEASE_DIR" ]] || return 1
    active=$(current_target_path 2>/dev/null || true)
    [[ "$RELEASE_DIR" != "$active" ]] || return 1
    rm -rf --one-file-system -- "$RELEASE_DIR"
}

atomic_switch_current() {
    local target=$1
    local candidate

    [[ "$target" == /* && -d "$target" ]] || return 1
    candidate="$BASE_DIR/.current.${GITHUB_SHA}.$$"
    [[ ! -e "$candidate" && ! -L "$candidate" ]] || return 1
    ln -s -- "$target" "$candidate"
    TEMP_LINK="$candidate"
    mv -Tf -- "$TEMP_LINK" "$CURRENT_LINK"
    TEMP_LINK=""
}

cleanup_ephemeral() {
    set +e
    if [[ -n "$TEMP_LINK" && -L "$TEMP_LINK" ]]; then
        rm -f -- "$TEMP_LINK"
    fi
    if [[ -n "$TEMP_RELEASE" && -d "$TEMP_RELEASE" && ! -L "$TEMP_RELEASE" ]]; then
        safe_remove_internal_tree "$TEMP_RELEASE"
    fi
    return 0
}

restore_publication() {
    local backup_exists=false

    if [[ -n "$REPLACED_RELEASE_BACKUP" && -d "$REPLACED_RELEASE_BACKUP" && ! -L "$REPLACED_RELEASE_BACKUP" ]]; then
        backup_exists=true
    fi

    if [[ "$backup_exists" == true ]]; then
        if [[ -e "$RELEASE_DIR" || -L "$RELEASE_DIR" ]]; then
            [[ -d "$RELEASE_DIR" && ! -L "$RELEASE_DIR" ]] || return 1
            [[ "$(current_target_path 2>/dev/null || true)" != "$RELEASE_DIR" ]] || return 1
            FAILED_RELEASE="$RELEASES_DIR/.failed-${GITHUB_SHA}.$$"
            [[ ! -e "$FAILED_RELEASE" && ! -L "$FAILED_RELEASE" ]] || return 1
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
        PUBLISHED=false
        PUBLICATION_STARTED=false
        return 0
    fi

    if [[ -n "$REPLACED_RELEASE_BACKUP" ]]; then
        if [[ -d "$RELEASE_DIR" && ! -L "$RELEASE_DIR" && "$PUBLICATION_STARTED" == false ]]; then
            REPLACED_RELEASE_BACKUP=""
            return 0
        fi
        return 1
    fi

    if [[ "$PUBLICATION_STARTED" == true && -d "$RELEASE_DIR" && ! -L "$RELEASE_DIR" ]]; then
        safe_remove_deployed_release || return 1
    fi
    PUBLISHED=false
    PUBLICATION_STARTED=false
}

deployment_has_switched() {
    local active

    [[ -n "$RELEASE_DIR" ]] || return 1
    active=$(current_target_path 2>/dev/null || true)
    [[ "$CURRENT_SWITCHED" == true || ( "$active" == "$RELEASE_DIR" && "$PREVIOUS_CURRENT" != "$RELEASE_DIR" ) ]]
}

handle_failure() {
    local original_status=$1
    local reason=$2
    local rollback_failed=false
    local switched=false
    local current_restored=false

    if [[ "$HANDLING_FAILURE" == true ]]; then
        exit "$original_status"
    fi
    HANDLING_FAILURE=true
    trap - ERR
    trap '' TERM INT HUP
    set +e
    printf 'Deployment aborted by %s; preserving exit status %d.\n' "$reason" "$original_status" >&2

    if deployment_has_switched; then
        switched=true
        if [[ -n "$PREVIOUS_CURRENT" ]]; then
            if atomic_switch_current "$PREVIOUS_CURRENT"; then
                current_restored=true
            else
                printf 'Rollback warning: could not restore the previous current symlink.\n' >&2
                rollback_failed=true
            fi
        else
            if [[ -L "$CURRENT_LINK" && "$(current_target_path 2>/dev/null || true)" == "$RELEASE_DIR" ]]; then
                rm -f -- "$CURRENT_LINK" || rollback_failed=true
                current_restored=true
            else
                printf 'Rollback warning: failed current path is not the deployed symlink.\n' >&2
                rollback_failed=true
            fi
        fi
    fi

    if ! restore_publication; then
        printf 'Rollback warning: could not restore publication state safely.\n' >&2
        rollback_failed=true
    fi

    if [[ "$switched" == true && -n "$PREVIOUS_CURRENT" && "$current_restored" == true ]]; then
        if ! sudo -n "$SYSTEMCTL" restart "$SERVICE"; then
            printf 'Rollback warning: restored current but service restart failed.\n' >&2
            rollback_failed=true
        fi
    elif [[ "$switched" == true && -z "$PREVIOUS_CURRENT" && "$current_restored" == true ]]; then
        if ! sudo -n "$SYSTEMCTL" stop "$SERVICE"; then
            printf 'Rollback warning: no prior release exists and the service could not be stopped.\n' >&2
            rollback_failed=true
        else
            printf 'No prior release exists; removed current and stopped %s.\n' "$SERVICE" >&2
        fi
    fi

    cleanup_ephemeral
    if [[ "$rollback_failed" == true ]]; then
        printf 'Rollback was incomplete; operator intervention is required.\n' >&2
    fi
    exit "$original_status"
}

on_error() {
    handle_failure "$1" "an error"
}

on_signal() {
    handle_failure "$2" "signal $1"
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

preflight_sudo() {
    local load_state

    [[ -x "$SYSTEMCTL" ]] || {
        printf 'Required systemctl executable is missing: %s\n' "$SYSTEMCTL" >&2
        return 1
    }
    sudo -n -l "$SYSTEMCTL" daemon-reload >/dev/null
    sudo -n -l "$SYSTEMCTL" restart "$SERVICE" >/dev/null
    sudo -n -l "$SYSTEMCTL" stop "$SERVICE" >/dev/null
    sudo -n -l "$SYSTEMCTL" is-active --quiet "$SERVICE" >/dev/null
    sudo -n -l "$SYSTEMCTL" show "$SERVICE" --property=LoadState --value >/dev/null
    load_state=$(sudo -n "$SYSTEMCTL" show "$SERVICE" --property=LoadState --value)
    [[ "$load_state" == loaded ]] || {
        printf 'Service unit is not loaded: %s\n' "$SERVICE" >&2
        return 1
    }
}

reconcile_stale_artifacts() {
    local line name path active sha target

    active=$(current_target_path 2>/dev/null || true)
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        name=${line#* }
        path="$RELEASES_DIR/$name"
        [[ -d "$path" && ! -L "$path" ]] || return 1
        [[ "$path" != "$active" ]] || {
            printf 'Refusing to reconcile an active hidden artifact.\n' >&2
            return 1
        }

        if [[ "$name" =~ ^\.replaced-([0-9a-fA-F]{40})\.[A-Za-z0-9]+$ ]]; then
            sha=${BASH_REMATCH[1]}
            target="$RELEASES_DIR/$sha"
            if [[ -e "$target" || -L "$target" ]]; then
                [[ -d "$target" && ! -L "$target" && "$(readlink -f -- "$target")" == "$target" ]] || return 1
                safe_remove_internal_tree "$path" || return 1
            else
                mv -- "$path" "$target" || return 1
            fi
        else
            safe_remove_internal_tree "$path" || return 1
        fi
    done < <(
        find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d \
            -regextype posix-extended \
            -regex '.*/\.(deploy|replaced|failed)-[0-9a-fA-F]{40}\.[A-Za-z0-9]+' \
            -printf '%T@ %f\n' | sort -rn
    )

    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        path="$BASE_DIR/$name"
        [[ -L "$path" && "$path" != "$CURRENT_LINK" ]] || return 1
        rm -f -- "$path" || return 1
    done < <(
        find "$BASE_DIR" -mindepth 1 -maxdepth 1 -type l \
            -regextype posix-extended \
            -regex '.*/\.current\.[0-9a-fA-F]{40}\.[0-9]+' -printf '%f\n'
    )
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

[[ ! -L "$LOCK_FILE" ]] || { printf 'Deployment lock must not be a symlink.\n' >&2; exit 1; }
exec 9>"$LOCK_FILE"
chmod 0600 "$LOCK_FILE"
if ! flock -n 9; then
    printf 'Another deployment is already running.\n' >&2
    exit 1
fi

RELEASE_DIR="$RELEASES_DIR/$GITHUB_SHA"
trap 'on_error $?' ERR
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
trap cleanup_ephemeral EXIT

reconcile_stale_artifacts

if [[ -L "$CURRENT_LINK" ]]; then
    PREVIOUS_CURRENT=$(readlink -f -- "$CURRENT_LINK") || {
        printf 'Current is present but cannot be resolved safely.\n' >&2
        false
    }
    [[ -d "$PREVIOUS_CURRENT" ]] || { printf 'Current target is not a directory.\n' >&2; false; }
elif [[ -e "$CURRENT_LINK" ]]; then
    printf 'Current must be a symlink.\n' >&2
    false
fi

[[ -L "$VENV_DIR" && "$(readlink -- "$VENV_DIR")" == "$CURRENT_LINK/venv" ]] || {
    printf 'Production venv path must be a symlink to %s/venv.\n' "$CURRENT_LINK" >&2
    false
}
if [[ -n "$PREVIOUS_CURRENT" ]]; then
    [[ -x "$PREVIOUS_CURRENT/venv/bin/python" ]] || {
        printf 'Current target does not contain a usable per-release venv.\n' >&2
        false
    }
fi

preflight_sudo

if [[ "$PREVIOUS_CURRENT" == "$RELEASE_DIR" ]]; then
    sudo -n "$SYSTEMCTL" is-active --quiet "$SERVICE"
    probe_service
    trap - ERR TERM INT HUP
    printf 'Release %s is already active and healthy.\n' "$GITHUB_SHA"
    exit 0
fi

[[ "${MEDIA_ROOT:-}" == /var/lib/labhub/media ]] || {
    printf 'MEDIA_ROOT must be exported as /var/lib/labhub/media for deployment commands.\n' >&2
    false
}
[[ -d "$MEDIA_ROOT" && -w "$MEDIA_ROOT" ]] || {
    printf 'Persistent MEDIA_ROOT is missing or not writable.\n' >&2
    false
}

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
[[ ! -e "$TEMP_RELEASE/venv" && ! -L "$TEMP_RELEASE/venv" ]] || {
    printf 'Archive must not contain a virtual environment.\n' >&2
    false
}

if [[ -e "$RELEASE_DIR" || -L "$RELEASE_DIR" ]]; then
    [[ -d "$RELEASE_DIR" && ! -L "$RELEASE_DIR" ]] || {
        printf 'Existing release path is not a safe directory.\n' >&2
        false
    }
    [[ "$(readlink -f -- "$RELEASE_DIR")" == "$RELEASE_DIR" ]] || {
        printf 'Existing release directory does not resolve safely.\n' >&2
        false
    }
    BACKUP_CANDIDATE="$RELEASES_DIR/.replaced-${GITHUB_SHA}.$$"
    [[ ! -e "$BACKUP_CANDIDATE" && ! -L "$BACKUP_CANDIDATE" ]] || false
    REPLACED_RELEASE_BACKUP="$BACKUP_CANDIDATE"
    mv -- "$RELEASE_DIR" "$REPLACED_RELEASE_BACKUP"
fi

PUBLICATION_STARTED=true
mv -- "$TEMP_RELEASE" "$RELEASE_DIR"
TEMP_RELEASE=""
PUBLISHED=true

python3 -m venv "$RELEASE_DIR/venv"
RELEASE_PYTHON="$RELEASE_DIR/venv/bin/python"
[[ -x "$RELEASE_PYTHON" ]] || { printf 'Per-release virtual environment is invalid.\n' >&2; false; }
"$RELEASE_PYTHON" -m pip install --disable-pip-version-check \
    --requirement "$RELEASE_DIR/requirements.txt"
(
    cd "$RELEASE_DIR"
    "$RELEASE_PYTHON" manage.py migrate --noinput
    "$RELEASE_PYTHON" manage.py collectstatic --noinput
)

atomic_switch_current "$RELEASE_DIR"
CURRENT_SWITCHED=true
[[ "$(readlink -f -- "$VENV_DIR")" == "$RELEASE_DIR/venv" ]] || {
    printf 'Stable production venv did not follow the current switch.\n' >&2
    false
}

sudo -n "$SYSTEMCTL" daemon-reload
sudo -n "$SYSTEMCTL" restart "$SERVICE"
sudo -n "$SYSTEMCTL" is-active --quiet "$SERVICE"
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

trap - ERR TERM INT HUP
printf 'Deployment completed for release %s.\n' "$GITHUB_SHA"
