#!/usr/bin/env bash

set -Eeuo pipefail
umask 022

BASE_DIR=/home/admin/LabTif
RELEASES_DIR="$BASE_DIR/releases"
CURRENT_LINK="$BASE_DIR/current"
VENV_DIR="$BASE_DIR/production-venv"
SERVICE=projectlaboran-daphne

SYSTEMCTL=/usr/bin/systemctl
MANAGE_LAUNCHER=/usr/local/sbin/projectlaboran-manage
LOCK_FILE="$BASE_DIR/.deploy.lock"
TRANSACTION_FILE="$BASE_DIR/.deploy-transaction"
TEMP_RELEASE=""
TEMP_LINK=""
TRANSACTION_TEMP=""
REPLACED_RELEASE_BACKUP=""
PREVIOUS_CURRENT=""
RELEASE_DIR=""
HANDLING_FAILURE=false
TX_SHA=""
TX_RELEASE=""
TX_PREVIOUS=""
TX_BACKUP=""
TX_PHASE=""

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
    sync -f "$BASE_DIR"
}

cleanup_ephemeral() {
    set +e
    if [[ -n "$TEMP_LINK" && -L "$TEMP_LINK" ]]; then
        rm -f -- "$TEMP_LINK"
    fi
    if [[ -n "$TEMP_RELEASE" && -d "$TEMP_RELEASE" && ! -L "$TEMP_RELEASE" ]]; then
        safe_remove_internal_tree "$TEMP_RELEASE"
    fi
    if [[ -n "$TRANSACTION_TEMP" && -f "$TRANSACTION_TEMP" && ! -L "$TRANSACTION_TEMP" ]]; then
        rm -f -- "$TRANSACTION_TEMP"
    fi
    return 0
}

validate_journal_path() {
    local path=$1

    [[ "$path" =~ ^/[A-Za-z0-9._/-]+$ ]] || return 1
    [[ "$path" != *"/../"* && "$path" != */.. && "$path" != *"//"* ]] || return 1
    [[ "$(readlink -m -- "$path")" == "$path" ]]
}

write_transaction() {
    local phase=$1
    local backup=${2:--}
    local previous=${PREVIOUS_CURRENT:--}

    [[ "$phase" =~ ^(building|ready|switched|rolling-back|committed)$ ]] || return 1
    [[ ! -L "$TRANSACTION_FILE" ]] || return 1
    validate_journal_path "$RELEASE_DIR" || return 1
    if [[ "$previous" != - ]]; then
        validate_journal_path "$previous" || return 1
    fi
    if [[ "$backup" != - ]]; then
        validate_journal_path "$backup" || return 1
    fi

    TRANSACTION_TEMP=$(mktemp "$BASE_DIR/.deploy-transaction.tmp.XXXXXX")
    chmod 0600 "$TRANSACTION_TEMP"
    printf 'version=1\nsha=%s\nrelease=%s\nprevious=%s\nbackup=%s\nphase=%s\n' \
        "$GITHUB_SHA" "$RELEASE_DIR" "$previous" "$backup" "$phase" >"$TRANSACTION_TEMP"
    sync -f "$TRANSACTION_TEMP"
    mv -Tf -- "$TRANSACTION_TEMP" "$TRANSACTION_FILE"
    TRANSACTION_TEMP=""
    sync -f "$BASE_DIR"
}

rewrite_loaded_transaction() {
    local phase=$1
    local previous=${TX_PREVIOUS:--}
    local backup=${TX_BACKUP:--}

    [[ "$phase" == rolling-back ]] || return 1
    TRANSACTION_TEMP=$(mktemp "$BASE_DIR/.deploy-transaction.tmp.XXXXXX")
    chmod 0600 "$TRANSACTION_TEMP"
    printf 'version=1\nsha=%s\nrelease=%s\nprevious=%s\nbackup=%s\nphase=%s\n' \
        "$TX_SHA" "$TX_RELEASE" "$previous" "$backup" "$phase" >"$TRANSACTION_TEMP"
    sync -f "$TRANSACTION_TEMP"
    mv -Tf -- "$TRANSACTION_TEMP" "$TRANSACTION_FILE"
    TRANSACTION_TEMP=""
    sync -f "$BASE_DIR"
    TX_PHASE=$phase
}

read_transaction() {
    local line key value count=0
    local seen_version=false seen_sha=false seen_release=false
    local seen_previous=false seen_backup=false seen_phase=false
    local version="" previous="" backup=""

    [[ -f "$TRANSACTION_FILE" && ! -L "$TRANSACTION_FILE" ]] || return 1
    [[ "$(stat -c '%a' "$TRANSACTION_FILE")" == 600 ]] || return 1
    TX_SHA=""; TX_RELEASE=""; TX_PREVIOUS=""; TX_BACKUP=""; TX_PHASE=""
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" == *=* && "$line" != *$'\r'* ]] || return 1
        key=${line%%=*}
        value=${line#*=}
        case "$key" in
            version) [[ "$seen_version" == false ]] || return 1; seen_version=true; version=$value ;;
            sha) [[ "$seen_sha" == false ]] || return 1; seen_sha=true; TX_SHA=$value ;;
            release) [[ "$seen_release" == false ]] || return 1; seen_release=true; TX_RELEASE=$value ;;
            previous) [[ "$seen_previous" == false ]] || return 1; seen_previous=true; previous=$value ;;
            backup) [[ "$seen_backup" == false ]] || return 1; seen_backup=true; backup=$value ;;
            phase) [[ "$seen_phase" == false ]] || return 1; seen_phase=true; TX_PHASE=$value ;;
            *) return 1 ;;
        esac
        ((count += 1))
    done <"$TRANSACTION_FILE"

    [[ "$count" -eq 6 && "$version" == 1 ]] || return 1
    [[ "$TX_SHA" =~ ^[0-9a-fA-F]{40}$ ]] || return 1
    [[ "$TX_RELEASE" == "$RELEASES_DIR/$TX_SHA" ]] || return 1
    validate_journal_path "$TX_RELEASE" || return 1
    [[ "$TX_PHASE" =~ ^(building|ready|switched|rolling-back|committed)$ ]] || return 1

    if [[ "$previous" != - ]]; then
        validate_journal_path "$previous" || return 1
        [[ -d "$previous" && -x "$previous/venv/bin/python" ]] || return 1
        TX_PREVIOUS=$previous
    fi
    if [[ "$backup" != - ]]; then
        validate_journal_path "$backup" || return 1
        [[ "$(dirname -- "$backup")" == "$RELEASES_DIR" ]] || return 1
        [[ "$(basename -- "$backup")" =~ ^\.replaced-${TX_SHA}\.[A-Za-z0-9]+$ ]] || return 1
        [[ ! -L "$backup" ]] || return 1
        TX_BACKUP=$backup
    fi
}

remove_transaction() {
    [[ -f "$TRANSACTION_FILE" && ! -L "$TRANSACTION_FILE" ]] || return 1
    rm -f -- "$TRANSACTION_FILE"
    sync -f "$BASE_DIR"
}

remove_provenanced_backup() {
    local expected=$1

    read_transaction || return 1
    [[ "$TX_PHASE" == committed && -n "$TX_BACKUP" && "$TX_BACKUP" == "$expected" ]] || return 1
    safe_remove_internal_tree "$expected"
}

write_success_marker() {
    local marker="$RELEASE_DIR/.deploy-success"
    local temp

    [[ ! -L "$marker" ]] || return 1
    temp=$(mktemp "$RELEASE_DIR/.deploy-success.tmp.XXXXXX")
    printf 'version=1\nsha=%s\n' "$GITHUB_SHA" >"$temp"
    chmod 0644 "$temp"
    sync -f "$temp"
    mv -Tf -- "$temp" "$marker"
    sync -f "$RELEASE_DIR"
}

has_success_marker() {
    local release=$1
    local sha=$2
    local marker="$release/.deploy-success"
    local content

    [[ -f "$marker" && ! -L "$marker" ]] || return 1
    content=$(<"$marker")
    [[ "$content" == $'version=1\nsha='"$sha" ]]
}

safe_remove_transaction_release() {
    local active

    [[ "$TX_RELEASE" == "$RELEASES_DIR/$TX_SHA" ]] || return 1
    [[ -d "$TX_RELEASE" && ! -L "$TX_RELEASE" ]] || return 1
    active=$(current_target_path 2>/dev/null || true)
    [[ "$active" != "$TX_RELEASE" ]] || return 1
    rm -rf --one-file-system -- "$TX_RELEASE"
}

restore_transaction_publication() {
    local failed

    if [[ -n "$TX_BACKUP" && -d "$TX_BACKUP" && ! -L "$TX_BACKUP" ]]; then
        if [[ -e "$TX_RELEASE" || -L "$TX_RELEASE" ]]; then
            [[ -d "$TX_RELEASE" && ! -L "$TX_RELEASE" ]] || return 1
            [[ "$(current_target_path 2>/dev/null || true)" != "$TX_RELEASE" ]] || return 1
            failed="$RELEASES_DIR/.failed-${TX_SHA}.recovery$$"
            [[ ! -e "$failed" && ! -L "$failed" ]] || return 1
            mv -- "$TX_RELEASE" "$failed" || return 1
        else
            failed=""
        fi
        if ! mv -- "$TX_BACKUP" "$TX_RELEASE"; then
            [[ -z "$failed" ]] || mv -- "$failed" "$TX_RELEASE" || true
            return 1
        fi
        [[ -z "$failed" ]] || safe_remove_internal_tree "$failed" || return 1
        return 0
    fi

    if [[ -n "$TX_BACKUP" ]]; then
        if [[ "$TX_PHASE" == building && -d "$TX_RELEASE" && ! -L "$TX_RELEASE" ]]; then
            return 0
        fi
        [[ "$TX_PHASE" =~ ^(rolling-back|committed)$ ]] && return 0
        return 1
    fi

    if [[ -d "$TX_RELEASE" && ! -L "$TX_RELEASE" ]]; then
        safe_remove_transaction_release || return 1
    fi
}

rollback_transaction() {
    local active

    read_transaction || { printf 'Transaction journal is malformed; refusing recovery.\n' >&2; return 1; }
    active=$(current_target_path 2>/dev/null || true)
    if [[ "$active" == "$TX_RELEASE" ]]; then
        printf 'Incomplete transaction switched current to %s; restoring prior target.\n' "$TX_SHA" >&2
    fi
    if [[ -n "$TX_PREVIOUS" ]]; then
        atomic_switch_current "$TX_PREVIOUS" || return 1
    elif [[ "$active" == "$TX_RELEASE" && -L "$CURRENT_LINK" ]]; then
        rm -f -- "$CURRENT_LINK" || return 1
        sync -f "$BASE_DIR" || return 1
    fi

    rewrite_loaded_transaction rolling-back || return 1
    restore_transaction_publication || return 1
    if [[ -n "$TX_PREVIOUS" ]]; then
        sudo -n "$SYSTEMCTL" daemon-reload || return 1
        sudo -n "$SYSTEMCTL" restart "$SERVICE" || return 1
        sudo -n "$SYSTEMCTL" is-active --quiet "$SERVICE" || return 1
        probe_service || return 1
        remove_transaction || return 1
        return 0
    fi

    sudo -n "$SYSTEMCTL" stop "$SERVICE" || return 1
    printf 'Recovered without a prior target; service is stopped and operator action is required.\n' >&2
    return 1
}

committed_release_is_healthy() {
    local active

    active=$(current_target_path 2>/dev/null || true)
    [[ "$active" == "$TX_RELEASE" ]] || return 1
    has_success_marker "$TX_RELEASE" "$TX_SHA" || return 1
    sudo -n "$SYSTEMCTL" is-active --quiet "$SERVICE" || return 1
    probe_service || return 1
}

finish_committed_cleanup() {
    read_transaction || return 1
    [[ "$TX_PHASE" == committed ]] || return 1
    if [[ -n "$TX_BACKUP" && -d "$TX_BACKUP" && ! -L "$TX_BACKUP" ]]; then
        remove_provenanced_backup "$TX_BACKUP" || return 1
    elif [[ -n "$TX_BACKUP" && ( -e "$TX_BACKUP" || -L "$TX_BACKUP" ) ]]; then
        return 1
    fi
    remove_transaction
}

recover_transaction() {
    read_transaction || { printf 'Transaction journal is malformed; refusing deployment.\n' >&2; return 1; }
    printf 'Recovering deployment transaction for %s at phase %s.\n' "$TX_SHA" "$TX_PHASE" >&2
    if [[ "$TX_PHASE" == committed ]]; then
        if committed_release_is_healthy; then
            if finish_committed_cleanup; then
                return 0
            fi
            printf 'Cleanup warning: healthy committed release retained with its transaction journal.\n' >&2
            return 1
        fi
        read_transaction || return 1
    fi
    rollback_transaction
}

handle_failure() {
    local original_status=$1
    local reason=$2
    local rollback_failed=false

    if [[ "$HANDLING_FAILURE" == true ]]; then
        exit "$original_status"
    fi
    HANDLING_FAILURE=true
    trap - ERR
    trap '' TERM INT HUP
    set +e
    printf 'Deployment aborted by %s; preserving exit status %d.\n' "$reason" "$original_status" >&2
    if [[ -e "$TRANSACTION_FILE" || -L "$TRANSACTION_FILE" ]]; then
        recover_transaction || rollback_failed=true
    fi
    cleanup_ephemeral
    if [[ "$rollback_failed" == true ]]; then
        printf 'Rollback was incomplete; transaction journal retained for recovery.\n' >&2
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

preflight_systemctl_sudo() {
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

preflight_manage_sudo() {
    [[ -x "$MANAGE_LAUNCHER" && ! -L "$MANAGE_LAUNCHER" ]] || {
        printf 'Restricted manage launcher is missing or unsafe: %s\n' "$MANAGE_LAUNCHER" >&2
        return 1
    }
    [[ "$(stat -c '%U:%G %a' "$MANAGE_LAUNCHER")" == 'root:root 755' ]] || {
        printf 'Restricted manage launcher ownership or mode is unsafe.\n' >&2
        return 1
    }
    sudo -n -l "$MANAGE_LAUNCHER" "$RELEASE_DIR" migrate >/dev/null
    sudo -n -l "$MANAGE_LAUNCHER" "$RELEASE_DIR" collectstatic >/dev/null
}

reconcile_stale_artifacts() {
    local name path active

    active=$(current_target_path 2>/dev/null || true)
    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        path="$RELEASES_DIR/$name"
        [[ -d "$path" && ! -L "$path" ]] || return 1
        [[ "$path" != "$active" ]] || {
            printf 'Refusing to reconcile an active hidden artifact.\n' >&2
            return 1
        }

        safe_remove_internal_tree "$path" || return 1
    done < <(
        find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d \
            -regextype posix-extended \
            -regex '.*/\.(deploy|failed)-[0-9a-fA-F]{40}\.[A-Za-z0-9]+' \
            -printf '%f\n'
    )

    if find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d \
        -regextype posix-extended \
        -regex '.*/\.replaced-[0-9a-fA-F]{40}\.[A-Za-z0-9]+' -print -quit | grep -q .; then
        printf 'Orphan replacement backup lacks transaction provenance; refusing deployment.\n' >&2
        return 1
    fi

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

    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        path="$BASE_DIR/$name"
        [[ -f "$path" && ! -L "$path" ]] || return 1
        rm -f -- "$path" || return 1
    done < <(
        find "$BASE_DIR" -mindepth 1 -maxdepth 1 -type f \
            -regextype posix-extended -regex '.*/\.deploy-transaction\.tmp\.[A-Za-z0-9]+' -printf '%f\n'
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

[[ -L "$VENV_DIR" && "$(readlink -- "$VENV_DIR")" == "$CURRENT_LINK/venv" ]] || {
    printf 'Production venv path must be a symlink to %s/venv.\n' "$CURRENT_LINK" >&2
    false
}

preflight_systemctl_sudo
if [[ -e "$TRANSACTION_FILE" || -L "$TRANSACTION_FILE" ]]; then
    recover_transaction
fi
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

if [[ -n "$PREVIOUS_CURRENT" ]]; then
    [[ -x "$PREVIOUS_CURRENT/venv/bin/python" ]] || {
        printf 'Current target does not contain a usable per-release venv.\n' >&2
        false
    }
fi

if [[ "$PREVIOUS_CURRENT" == "$RELEASE_DIR" ]]; then
    if has_success_marker "$RELEASE_DIR" "$GITHUB_SHA"; then
        sudo -n "$SYSTEMCTL" is-active --quiet "$SERVICE"
        probe_service
    else
        sudo -n "$SYSTEMCTL" daemon-reload
        sudo -n "$SYSTEMCTL" restart "$SERVICE"
        sudo -n "$SYSTEMCTL" is-active --quiet "$SERVICE"
        probe_service
        write_success_marker
    fi
    trap - ERR TERM INT HUP
    printf 'Release %s is already active and healthy.\n' "$GITHUB_SHA"
    exit 0
fi

preflight_manage_sudo

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
[[ ! -e "$TEMP_RELEASE/.deploy-success" && ! -L "$TEMP_RELEASE/.deploy-success" ]] || {
    printf 'Archive must not contain a deployment success marker.\n' >&2
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
fi

write_transaction building "${REPLACED_RELEASE_BACKUP:--}"
if [[ -n "$REPLACED_RELEASE_BACKUP" ]]; then
    mv -- "$RELEASE_DIR" "$REPLACED_RELEASE_BACKUP"
fi
mv -- "$TEMP_RELEASE" "$RELEASE_DIR"
TEMP_RELEASE=""

python3 -m venv "$RELEASE_DIR/venv"
RELEASE_PYTHON="$RELEASE_DIR/venv/bin/python"
[[ -x "$RELEASE_PYTHON" ]] || { printf 'Per-release virtual environment is invalid.\n' >&2; false; }
"$RELEASE_PYTHON" -m pip install --disable-pip-version-check \
    --requirement "$RELEASE_DIR/requirements.txt"
sudo -n "$MANAGE_LAUNCHER" "$RELEASE_DIR" migrate
sudo -n "$MANAGE_LAUNCHER" "$RELEASE_DIR" collectstatic

write_transaction ready "${REPLACED_RELEASE_BACKUP:--}"
atomic_switch_current "$RELEASE_DIR"
write_transaction switched "${REPLACED_RELEASE_BACKUP:--}"
[[ "$(readlink -f -- "$VENV_DIR")" == "$RELEASE_DIR/venv" ]] || {
    printf 'Stable production venv did not follow the current switch.\n' >&2
    false
}

sudo -n "$SYSTEMCTL" daemon-reload
sudo -n "$SYSTEMCTL" restart "$SERVICE"
sudo -n "$SYSTEMCTL" is-active --quiet "$SERVICE"
probe_service
write_success_marker
write_transaction committed "${REPLACED_RELEASE_BACKUP:--}"
trap - ERR TERM INT HUP

if finish_committed_cleanup; then
    REPLACED_RELEASE_BACKUP=""
    if ! cleanup_old_releases; then
        printf 'Cleanup warning: deployment succeeded but old-release cleanup was incomplete.\n' >&2
    fi
else
    printf 'Cleanup warning: deployment succeeded; committed cleanup will be retried on the next run.\n' >&2
fi

printf 'Deployment completed for release %s.\n' "$GITHUB_SHA"
