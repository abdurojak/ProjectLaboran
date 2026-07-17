#!/usr/bin/env bash

set -Eeuo pipefail
umask 022
PATH=/usr/sbin:/usr/bin:/sbin:/bin
LC_ALL=C
IFS=$' \t\n'
export PATH LC_ALL
unset CDPATH ENV BASH_ENV

INSTALL_PATH=/usr/local/sbin/projectlaboran-deploy
BASE_DIR=/home/admin/LabTif
RELEASES_DIR="$BASE_DIR/releases"
CURRENT_LINK="$BASE_DIR/current"
VENV_LINK="$BASE_DIR/production-venv"
INCOMING_ENVELOPE="$BASE_DIR/incoming/projectlaboran.deploy.tar"
LOCK_FILE="$BASE_DIR/.deploy.lock"
TRANSACTION_FILE="$BASE_DIR/.deploy-transaction"
OLD_CHECKOUT="$BASE_DIR/ProjectLaboran"

ENV_DIR=/etc/labhub
V1_ENV="$ENV_DIR/labhub-v1.env"
V2_ENV="$ENV_DIR/labhub-v2.env"
CURRENT_ENV="$ENV_DIR/current.env"
TRUSTED_ROOT="$ENV_DIR/trusted_root.jsonl"

APP_USER=labhub-app
APP_GROUP=labhub-app
SERVICE=projectlaboran-daphne
SYSTEMCTL=/usr/bin/systemctl
RUNUSER=/usr/sbin/runuser
GH=/usr/bin/gh

REPOSITORY=abdurojak/ProjectLaboran
SIGNER_WORKFLOW=abdurojak/ProjectLaboran/.github/workflows/test-runner.yml
SOURCE_REF=refs/heads/main

MODE=""
ENVELOPE=""
SHA=""
RELEASE_DIR=""
PREVIOUS_CURRENT=""
PREVIOUS_ENV=""
TARGET_ENV="$V2_ENV"
REPLACED_BACKUP=""
TEMP_ENVELOPE_DIR=""
TEMP_RELEASE=""
TEMP_LINK=""
TRANSACTION_TEMP=""
HANDLING_FAILURE=false

TX_KIND=""
TX_SHA=""
TX_RELEASE=""
TX_PREVIOUS=""
TX_PREVIOUS_ENV=""
TX_TARGET_ENV=""
TX_BACKUP=""
TX_PHASE=""

declare -a RUNTIME_ENV=()
declare -A RUNTIME_KEYS=()
ENV_VALUE_RE='^[A-Za-z0-9_./:@%+=,?&!$^*(){}\[\]|;~-]*$'

usage() {
    printf 'Usage: %s <deployment-envelope.tar>\n' "$INSTALL_PATH" >&2
    printf '       %s --rollback <40-lowercase-hex-sha>\n' "$INSTALL_PATH" >&2
    printf '       %s --check-baseline\n' "$INSTALL_PATH" >&2
}

fail() {
    printf '%s\n' "$1" >&2
    return 1
}

require_root_owned() {
    local path=$1
    local expected_mode=${2:-}

    [[ -e "$path" && ! -L "$path" ]] || return 1
    [[ "$(stat -c '%U:%G' -- "$path")" == root:root ]] || return 1
    if [[ -n "$expected_mode" ]]; then
        [[ "$(stat -c '%a' -- "$path")" == "$expected_mode" ]] || return 1
    fi
}

current_target_path() {
    [[ -L "$CURRENT_LINK" ]] || return 1
    readlink -e -- "$CURRENT_LINK"
}

current_environment_path() {
    local target

    [[ -L "$CURRENT_ENV" ]] || return 1
    target=$(readlink -e -- "$CURRENT_ENV") || return 1
    [[ "$target" == "$V1_ENV" || "$target" == "$V2_ENV" ]] || return 1
    printf '%s\n' "$target"
}

validate_sha() {
    [[ "$1" =~ ^[0-9a-f]{40}$ ]]
}

release_tree_is_locked() {
    local path=$1
    local link resolved mode

    require_root_owned "$path" || return 1
    if find "$path" -xdev \( -not -user root -o -not -group root \
        -o \( -not -type l -a -perm /0022 \) \) \
        -print -quit | grep -q .; then
        return 1
    fi
    if find "$path" -xdev \( \( -not -type d -a -not -type f -a -not -type l \) \
        -o \( -type f -links +1 \) \) -print -quit | grep -q .; then
        return 1
    fi
    while IFS= read -r -d '' link; do
        if [[ "$path" == "$OLD_CHECKOUT" && "$link" == "$OLD_CHECKOUT/media" ]]; then
            continue
        fi
        resolved=$(readlink -e -- "$link") || return 1
        if [[ "$resolved" != "$path"/* ]]; then
            case "$resolved" in
                /bin/*|/lib/*|/lib64/*|/usr/bin/*|/usr/lib/*|/usr/lib64/*|/usr/local/bin/*|/usr/local/lib/*) ;;
                *) return 1 ;;
            esac
        fi
        [[ "$(stat -c '%U:%G' -- "$resolved")" == root:root ]] || return 1
        mode=$(stat -c '%a' -- "$resolved") || return 1
        [[ $((8#$mode & 8#22)) -eq 0 ]] || return 1
    done < <(find "$path" -xdev -type l -print0)
}

validate_release_path() {
    local path=$1
    local name

    if [[ "$path" == "$OLD_CHECKOUT" ]]; then
        [[ -d "$path" && ! -L "$path" && -x "$path/venv/bin/python" ]] || return 1
        release_tree_is_locked "$path" || return 1
        return 0
    fi
    [[ "$(dirname -- "$path")" == "$RELEASES_DIR" ]] || return 1
    name=$(basename -- "$path")
    validate_sha "$name" || return 1
    [[ "$path" == "$RELEASES_DIR/$name" ]] || return 1
    [[ -d "$path" && ! -L "$path" && -x "$path/venv/bin/python" ]] || return 1
    [[ "$(readlink -e -- "$path")" == "$path" ]] || return 1
    release_tree_is_locked "$path" || return 1
}

validate_backup_path() {
    local path=$1
    local sha=$2

    [[ "$(dirname -- "$path")" == "$RELEASES_DIR" ]] || return 1
    [[ "$(basename -- "$path")" =~ ^\.replaced-${sha}\.[A-Za-z0-9]+$ ]] || return 1
    [[ ! -L "$path" ]] || return 1
    [[ ! -e "$path" || -d "$path" ]] || return 1
}

atomic_switch() {
    local link=$1
    local target=$2
    local tag=$3
    local parent candidate

    [[ "$target" == /* && -e "$target" ]] || return 1
    parent=$(dirname -- "$link")
    candidate="$parent/.${tag}.${SHA}.$$"
    [[ ! -e "$candidate" && ! -L "$candidate" ]] || return 1
    ln -s -- "$target" "$candidate"
    TEMP_LINK=$candidate
    mv -Tf -- "$TEMP_LINK" "$link"
    TEMP_LINK=""
    sync -f "$parent"
}

safe_remove_internal_tree() {
    local path=$1
    local active name

    [[ "$(dirname -- "$path")" == "$RELEASES_DIR" ]] || return 1
    [[ -d "$path" && ! -L "$path" ]] || return 1
    name=$(basename -- "$path")
    [[ "$name" =~ ^\.(deploy|replaced|failed)-[0-9a-f]{40}\.[A-Za-z0-9]+$ ]] || return 1
    active=$(current_target_path 2>/dev/null || true)
    [[ "$path" != "$active" ]] || return 1
    rm -rf --one-file-system -- "$path"
}

safe_remove_release() {
    local path=$1
    local name active

    [[ "$(dirname -- "$path")" == "$RELEASES_DIR" ]] || return 1
    name=$(basename -- "$path")
    validate_sha "$name" || return 1
    [[ -d "$path" && ! -L "$path" && "$(readlink -e -- "$path")" == "$path" ]] || return 1
    active=$(current_target_path 2>/dev/null || true)
    [[ "$path" != "$active" && "$path" != "$RELEASE_DIR" ]] || return 1
    rm -rf --one-file-system -- "$path"
}

cleanup_ephemeral() {
    set +e
    if [[ -n "$TEMP_LINK" && -L "$TEMP_LINK" ]]; then
        rm -f -- "$TEMP_LINK"
    fi
    if [[ -n "$TEMP_RELEASE" && -d "$TEMP_RELEASE" && ! -L "$TEMP_RELEASE" ]]; then
        safe_remove_internal_tree "$TEMP_RELEASE"
    fi
    if [[ -n "$TEMP_ENVELOPE_DIR" && -d "$TEMP_ENVELOPE_DIR" && ! -L "$TEMP_ENVELOPE_DIR" ]]; then
        [[ "$(dirname -- "$TEMP_ENVELOPE_DIR")" == "$BASE_DIR" ]] && \
            [[ "$(basename -- "$TEMP_ENVELOPE_DIR")" =~ ^\.envelope\.[A-Za-z0-9]+$ ]] && \
            rm -rf --one-file-system -- "$TEMP_ENVELOPE_DIR"
    fi
    if [[ -n "$TRANSACTION_TEMP" && -f "$TRANSACTION_TEMP" && ! -L "$TRANSACTION_TEMP" ]]; then
        rm -f -- "$TRANSACTION_TEMP"
    fi
    return 0
}

write_transaction() {
    local phase=$1
    local previous=${PREVIOUS_CURRENT:--}
    local previous_env=${PREVIOUS_ENV:--}
    local backup=${REPLACED_BACKUP:--}

    [[ "$MODE" == deploy || "$MODE" == rollback ]] || return 1
    validate_sha "$SHA" || return 1
    [[ "$RELEASE_DIR" == "$RELEASES_DIR/$SHA" ]] || return 1
    [[ "$phase" =~ ^(building|ready|switched|rolling-back|committed)$ ]] || return 1
    validate_release_path "$previous" || return 1
    [[ "$previous_env" == "$V1_ENV" || "$previous_env" == "$V2_ENV" ]] || return 1
    [[ "$TARGET_ENV" == "$V2_ENV" ]] || return 1
    require_root_owned "$previous_env" 600 || return 1
    require_root_owned "$TARGET_ENV" 600 || return 1
    if [[ "$backup" != - ]]; then
        validate_backup_path "$backup" "$SHA" || return 1
    fi
    [[ ! -L "$TRANSACTION_FILE" ]] || return 1

    TRANSACTION_TEMP=$(mktemp "$BASE_DIR/.deploy-transaction.tmp.XXXXXX")
    chmod 0600 "$TRANSACTION_TEMP"
    printf 'version=3\nkind=%s\nsha=%s\nrelease=%s\nprevious=%s\nprevious_env=%s\ntarget_env=%s\nbackup=%s\nphase=%s\n' \
        "$MODE" "$SHA" "$RELEASE_DIR" "$previous" "$previous_env" "$TARGET_ENV" \
        "$backup" "$phase" >"$TRANSACTION_TEMP"
    sync -f "$TRANSACTION_TEMP"
    mv -Tf -- "$TRANSACTION_TEMP" "$TRANSACTION_FILE"
    TRANSACTION_TEMP=""
    sync -f "$BASE_DIR"
}

rewrite_transaction_phase() {
    local phase=$1
    local backup=${TX_BACKUP:--}

    [[ "$phase" == rolling-back ]] || return 1
    TRANSACTION_TEMP=$(mktemp "$BASE_DIR/.deploy-transaction.tmp.XXXXXX")
    chmod 0600 "$TRANSACTION_TEMP"
    printf 'version=3\nkind=%s\nsha=%s\nrelease=%s\nprevious=%s\nprevious_env=%s\ntarget_env=%s\nbackup=%s\nphase=%s\n' \
        "$TX_KIND" "$TX_SHA" "$TX_RELEASE" "$TX_PREVIOUS" "$TX_PREVIOUS_ENV" \
        "$TX_TARGET_ENV" "$backup" "$phase" >"$TRANSACTION_TEMP"
    sync -f "$TRANSACTION_TEMP"
    mv -Tf -- "$TRANSACTION_TEMP" "$TRANSACTION_FILE"
    TRANSACTION_TEMP=""
    sync -f "$BASE_DIR"
    TX_PHASE=$phase
}

read_transaction() {
    local line key value count=0 version=""
    local -A seen=()

    [[ -f "$TRANSACTION_FILE" && ! -L "$TRANSACTION_FILE" ]] || return 1
    require_root_owned "$TRANSACTION_FILE" 600 || return 1
    TX_KIND=""; TX_SHA=""; TX_RELEASE=""; TX_PREVIOUS=""; TX_PREVIOUS_ENV=""
    TX_TARGET_ENV=""; TX_BACKUP=""; TX_PHASE=""
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" == *=* && "$line" != *$'\r'* ]] || return 1
        key=${line%%=*}
        value=${line#*=}
        [[ -z "${seen[$key]:-}" ]] || return 1
        seen[$key]=1
        case "$key" in
            version) version=$value ;;
            kind) TX_KIND=$value ;;
            sha) TX_SHA=$value ;;
            release) TX_RELEASE=$value ;;
            previous) TX_PREVIOUS=$value ;;
            previous_env) TX_PREVIOUS_ENV=$value ;;
            target_env) TX_TARGET_ENV=$value ;;
            backup) TX_BACKUP=$value ;;
            phase) TX_PHASE=$value ;;
            *) return 1 ;;
        esac
        ((count += 1))
    done <"$TRANSACTION_FILE"

    [[ "$count" -eq 9 && "$version" == 3 ]] || return 1
    [[ "$TX_KIND" == deploy || "$TX_KIND" == rollback ]] || return 1
    validate_sha "$TX_SHA" || return 1
    [[ "$TX_RELEASE" == "$RELEASES_DIR/$TX_SHA" ]] || return 1
    validate_release_path "$TX_PREVIOUS" || return 1
    [[ "$TX_PREVIOUS_ENV" == "$V1_ENV" || "$TX_PREVIOUS_ENV" == "$V2_ENV" ]] || return 1
    [[ "$TX_TARGET_ENV" == "$V2_ENV" ]] || return 1
    require_root_owned "$TX_PREVIOUS_ENV" 600 || return 1
    require_root_owned "$TX_TARGET_ENV" 600 || return 1
    [[ "$TX_PHASE" =~ ^(building|ready|switched|rolling-back|committed)$ ]] || return 1
    if [[ "$TX_BACKUP" == - ]]; then
        TX_BACKUP=""
    else
        validate_backup_path "$TX_BACKUP" "$TX_SHA" || return 1
    fi
    if [[ "$TX_KIND" == rollback && -n "$TX_BACKUP" ]]; then
        return 1
    fi
}

remove_transaction() {
    require_root_owned "$TRANSACTION_FILE" 600 || return 1
    rm -f -- "$TRANSACTION_FILE"
    sync -f "$BASE_DIR"
}

write_success_marker() {
    local marker="$RELEASE_DIR/.deploy-success"
    local temp

    [[ "$RELEASE_DIR" == "$RELEASES_DIR/$SHA" && -d "$RELEASE_DIR" && ! -L "$RELEASE_DIR" ]] || return 1
    [[ ! -L "$marker" ]] || return 1
    temp=$(mktemp "$RELEASE_DIR/.deploy-success.tmp.XXXXXX")
    printf 'version=2\nsha=%s\nenvironment=%s\n' "$SHA" "$V2_ENV" >"$temp"
    chown root:root "$temp"
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
    require_root_owned "$marker" 644 || return 1
    content=$(<"$marker")
    [[ "$content" == $'version=2\nsha='"$sha"$'\nenvironment='"$V2_ENV" ]]
}

load_runtime_environment() {
    local file=$1
    local line key value runtime_key

    require_root_owned "$file" 600 || return 1
    RUNTIME_ENV=()
    RUNTIME_KEYS=()
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" != *$'\r'* ]] || return 1
        [[ -n "$line" && "${line:0:1}" != '#' ]] || continue
        [[ "$line" == *=* ]] || return 1
        key=${line%%=*}
        value=${line#*=}
        [[ "$key" =~ ^[A-Z_][A-Z0-9_]*$ ]] || return 1
        case "$key" in
            BASH_ENV|ENV|LD_LIBRARY_PATH|LD_PRELOAD|PATH|PYTHONHOME|PYTHONPATH|VIRTUAL_ENV) return 1 ;;
        esac
        [[ "$value" =~ $ENV_VALUE_RE ]] || return 1
        [[ -z "${RUNTIME_KEYS[$key]:-}" ]] || return 1
        RUNTIME_KEYS[$key]=$value
        RUNTIME_ENV+=("$key=$value")
    done <"$file"

    [[ "${RUNTIME_KEYS[MEDIA_ROOT]:-}" == /var/lib/labhub/media ]] || return 1
    if [[ "$file" == "$V2_ENV" ]]; then
        [[ "${RUNTIME_KEYS[LABHUB_LICENSE_ENFORCED]:-}" == True ]] || return 1
        [[ -n "${RUNTIME_KEYS[LABHUB_LICENSE_KEY]:-}" ]] || return 1
        for runtime_key in "${!RUNTIME_KEYS[@]}"; do
            [[ ! "$runtime_key" =~ ^LABHUB_LICENSE_(VERIFICATION|PRIVATE|SIGNING) ]] || return 1
        done
    fi
}

run_manage() {
    local code_dir=$1
    local env_file=$2
    local operation=$3
    local python="$code_dir/venv/bin/python"
    local -a args

    [[ -d "$code_dir" && ! -L "$code_dir" && -f "$code_dir/manage.py" && -x "$python" ]] || return 1
    load_runtime_environment "$env_file" || return 1
    case "$operation" in
        check) args=(check --deploy) ;;
        migrate) args=(migrate --noinput) ;;
        collectstatic) args=(collectstatic --noinput) ;;
        *) return 1 ;;
    esac
    (
        cd -- "$code_dir"
        exec "$RUNUSER" --user "$APP_USER" -- /usr/bin/env -i \
            HOME=/var/lib/labhub-app PATH=/usr/local/bin:/usr/bin:/bin \
            PYTHONDONTWRITEBYTECODE=1 "${RUNTIME_ENV[@]}" \
            "$python" manage.py "${args[@]}"
    )
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
        ((attempt == 15)) || sleep 2
    done
    printf 'Health check failed after %d attempts.\n' "$attempt" >&2
    return 1
}

verify_service_identity() {
    local expected=$1
    local pid cwd exe cmdline

    "$SYSTEMCTL" is-active --quiet "$SERVICE" || return 1
    pid=$("$SYSTEMCTL" show "$SERVICE" --property=MainPID --value) || return 1
    [[ "$pid" =~ ^[0-9]+$ ]] && ((pid > 1)) || return 1
    [[ "$(stat -c '%U:%G' -- "/proc/$pid")" == "$APP_USER:$APP_GROUP" ]] || return 1
    cwd=$(readlink -e -- "/proc/$pid/cwd") || return 1
    [[ "$cwd" == "$expected" ]] || return 1
    exe=$(readlink -e -- "/proc/$pid/exe") || return 1
    [[ -x "$exe" && "$(stat -c '%U' -- "$exe")" == root ]] || return 1
    [[ $((8#$(stat -c '%a' -- "$exe") & 8#22)) -eq 0 ]] || return 1
    cmdline=$(tr '\0' ' ' <"/proc/$pid/cmdline") || return 1
    [[ "$cmdline" == *daphne*project_laboran.asgi:application* ]]
}

restart_and_verify() {
    local target=$1

    "$SYSTEMCTL" daemon-reload
    "$SYSTEMCTL" restart "$SERVICE"
    verify_service_identity "$target"
    probe_service
}

restore_deploy_publication() {
    local failed=""

    [[ "$TX_KIND" == deploy ]] || return 0
    if [[ -n "$TX_BACKUP" && -d "$TX_BACKUP" && ! -L "$TX_BACKUP" ]]; then
        if [[ -e "$TX_RELEASE" || -L "$TX_RELEASE" ]]; then
            [[ -d "$TX_RELEASE" && ! -L "$TX_RELEASE" ]] || return 1
            [[ "$(current_target_path 2>/dev/null || true)" != "$TX_RELEASE" ]] || return 1
            failed="$RELEASES_DIR/.failed-${TX_SHA}.recovery$$"
            [[ ! -e "$failed" && ! -L "$failed" ]] || return 1
            mv -- "$TX_RELEASE" "$failed"
        fi
        if ! mv -- "$TX_BACKUP" "$TX_RELEASE"; then
            [[ -z "$failed" ]] || mv -- "$failed" "$TX_RELEASE" || true
            return 1
        fi
        [[ -z "$failed" ]] || safe_remove_internal_tree "$failed"
        return 0
    fi
    if [[ -n "$TX_BACKUP" ]]; then
        [[ "$TX_PHASE" == building && -d "$TX_RELEASE" && ! -L "$TX_RELEASE" ]] && return 0
        [[ "$TX_PHASE" == rolling-back ]] && return 0
        return 1
    fi
    if [[ -d "$TX_RELEASE" && ! -L "$TX_RELEASE" ]]; then
        [[ "$(current_target_path 2>/dev/null || true)" != "$TX_RELEASE" ]] || return 1
        rm -rf --one-file-system -- "$TX_RELEASE"
    fi
}

rollback_transaction() {
    read_transaction || { printf 'Transaction journal is malformed; refusing recovery.\n' >&2; return 1; }
    [[ "$TX_PHASE" != committed ]] || return 1
    rewrite_transaction_phase rolling-back || return 1
    SHA=$TX_SHA
    atomic_switch "$CURRENT_LINK" "$TX_PREVIOUS" current || return 1
    atomic_switch "$CURRENT_ENV" "$TX_PREVIOUS_ENV" environment || return 1
    restore_deploy_publication || return 1
    restart_and_verify "$TX_PREVIOUS" || return 1
    remove_transaction
}

finish_committed_cleanup() {
    read_transaction || return 1
    [[ "$TX_PHASE" == committed ]] || return 1
    if [[ -n "$TX_BACKUP" && -d "$TX_BACKUP" && ! -L "$TX_BACKUP" ]]; then
        safe_remove_internal_tree "$TX_BACKUP" || return 1
    elif [[ -n "$TX_BACKUP" && ( -e "$TX_BACKUP" || -L "$TX_BACKUP" ) ]]; then
        return 1
    fi
    remove_transaction
}

recover_transaction() {
    read_transaction || { printf 'Transaction journal is malformed; refusing deployment.\n' >&2; return 1; }
    printf 'Recovering %s transaction for %s at phase %s.\n' "$TX_KIND" "$TX_SHA" "$TX_PHASE" >&2
    SHA=$TX_SHA
    if [[ "$TX_PHASE" == committed ]]; then
        if [[ "$(current_target_path 2>/dev/null || true)" != "$TX_RELEASE" ]] || \
            [[ "$(current_environment_path 2>/dev/null || true)" != "$TX_TARGET_ENV" ]] || \
            ! has_success_marker "$TX_RELEASE" "$TX_SHA" || \
            ! verify_service_identity "$TX_RELEASE" || ! probe_service; then
            printf 'Committed deployment identity or health verification failed; journal retained without rollback.\n' >&2
            return 1
        fi
        if ! finish_committed_cleanup; then
            printf 'Cleanup warning: committed journal retained for a later retry.\n' >&2
            return 1
        fi
        return 0
    fi
    rollback_transaction
}

handle_failure() {
    local original_status=$1
    local reason=$2
    local recovery_failed=false

    if [[ "$HANDLING_FAILURE" == true ]]; then
        exit "$original_status"
    fi
    HANDLING_FAILURE=true
    trap - ERR
    trap '' TERM INT HUP
    set +e
    printf 'Deployment aborted by %s; preserving exit status %d.\n' "$reason" "$original_status" >&2
    if [[ -e "$TRANSACTION_FILE" || -L "$TRANSACTION_FILE" ]]; then
        recover_transaction || recovery_failed=true
    fi
    cleanup_ephemeral
    if [[ "$recovery_failed" == true ]]; then
        printf 'Recovery is incomplete; the transaction journal was retained.\n' >&2
    fi
    exit "$original_status"
}

on_error() {
    handle_failure "$1" "an error"
}

on_signal() {
    handle_failure "$2" "signal $1"
}

extract_envelope() {
    TEMP_ENVELOPE_DIR=$(mktemp -d "$BASE_DIR/.envelope.XXXXXX")
    chmod 0700 "$TEMP_ENVELOPE_DIR"
    python3 - "$ENVELOPE" "$TEMP_ENVELOPE_DIR" <<'PY'
import os
import re
import sys
import tarfile
from pathlib import Path

archive_path = Path(sys.argv[1])
destination = Path(sys.argv[2])
expected = {
    "projectlaboran.protected.tar.gz": 2 * 1024 * 1024 * 1024,
    "attestation.jsonl": 64 * 1024 * 1024,
    "source-sha": 128,
}

with tarfile.open(archive_path, "r:") as archive:
    members = archive.getmembers()
    names = [member.name for member in members]
    if len(names) != len(set(names)) or set(names) != set(expected):
        raise ValueError("deployment envelope must contain exactly the expected files")
    for member in members:
        if not member.isfile() or member.name.startswith(("/", "\\")) or "/" in member.name or "\\" in member.name:
            raise ValueError("unsafe deployment envelope entry")
        if member.mode not in {0o600, 0o640, 0o644} or member.size < 1 or member.size > expected[member.name]:
            raise ValueError("unsafe deployment envelope mode or size")
        source = archive.extractfile(member)
        if source is None:
            raise ValueError("unreadable deployment envelope entry")
        target = destination / member.name
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(target, flags, 0o600)
        with source, os.fdopen(fd, "wb") as output:
            while chunk := source.read(1024 * 1024):
                output.write(chunk)

sha_bytes = (destination / "source-sha").read_bytes()
if re.fullmatch(rb"[0-9a-f]{40}\n?", sha_bytes) is None:
    raise ValueError("invalid source-sha")
PY
    SHA=$(<"$TEMP_ENVELOPE_DIR/source-sha")
    validate_sha "$SHA"
}

verify_attestation() {
    local archive="$TEMP_ENVELOPE_DIR/projectlaboran.protected.tar.gz"
    local bundle="$TEMP_ENVELOPE_DIR/attestation.jsonl"

    if "$GH" attestation verify "$archive" \
        --repo "$REPOSITORY" \
        --bundle "$bundle" \
        --custom-trusted-root "$TRUSTED_ROOT" \
        --signer-workflow "$SIGNER_WORKFLOW" \
        --source-digest "$SHA" \
        --source-ref "$SOURCE_REF" \
        --deny-self-hosted-runners >/dev/null 2>&1; then
        printf 'Artifact attestation verification succeeded.\n'
    else
        printf 'Artifact attestation verification failed.\n' >&2
        return 1
    fi
}

extract_protected_release() {
    local archive="$TEMP_ENVELOPE_DIR/projectlaboran.protected.tar.gz"

    TEMP_RELEASE=$(mktemp -d "$RELEASES_DIR/.deploy-${SHA}.XXXXXX")
    chmod 0700 "$TEMP_RELEASE"
    python3 - "$archive" "$TEMP_RELEASE" <<'PY'
import os
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath, PureWindowsPath

archive_path = Path(sys.argv[1])
destination = Path(sys.argv[2])
max_entries = 200_000
max_total_size = 4 * 1024 * 1024 * 1024

with tarfile.open(archive_path, "r:gz") as archive:
    members = archive.getmembers()
    if len(members) > max_entries:
        raise ValueError("protected archive contains too many entries")
    validated = []
    kinds = {}
    total_size = 0
    for member in members:
        name = member.name
        normalized = name.replace("\\", "/")
        member_path = PurePosixPath(normalized)
        if (
            not name
            or "\\" in name
            or member_path.is_absolute()
            or PureWindowsPath(normalized).drive
            or normalized.startswith("./")
            or "//" in normalized
            or any(ord(character) < 32 or ord(character) == 127 for character in name)
            or not member_path.parts
            or ".." in member_path.parts
            or any(":" in part for part in member_path.parts)
        ):
            raise ValueError("unsafe protected archive path")
        if member.type not in {tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE}:
            raise ValueError("unsafe protected archive entry type")
        if member.mode & 0o7022:
            raise ValueError("unsafe protected archive mode")
        key = tuple(member_path.parts)
        if key in kinds:
            raise ValueError("duplicate protected archive path")
        for index in range(1, len(key)):
            if kinds.get(key[:index]) == "file":
                raise ValueError("protected archive path crosses a file")
        kinds[key] = "dir" if member.isdir() else "file"
        total_size += member.size
        if total_size > max_total_size:
            raise ValueError("protected archive is too large")
        validated.append((member, member_path))

    for member, member_path in validated:
        target = destination.joinpath(*member_path.parts)
        if member.isdir():
            target.mkdir(mode=0o755, parents=True, exist_ok=True)
            continue
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise ValueError("unreadable protected archive entry")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(target, flags, 0o644)
        with source, os.fdopen(fd, "wb") as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)
PY
    [[ -f "$TEMP_RELEASE/manage.py" && -f "$TEMP_RELEASE/requirements.txt" ]] || return 1
    [[ ! -e "$TEMP_RELEASE/venv" && ! -L "$TEMP_RELEASE/venv" ]] || return 1
    [[ ! -e "$TEMP_RELEASE/.deploy-success" && ! -L "$TEMP_RELEASE/.deploy-success" ]] || return 1
    [[ ! -e "$TEMP_RELEASE/.env" && ! -L "$TEMP_RELEASE/.env" ]] || return 1
    [[ ! -e "$TEMP_RELEASE/media" && ! -L "$TEMP_RELEASE/media" ]] || return 1
    chown -R root:root -- "$TEMP_RELEASE"
    chmod -R u=rwX,go=rX -- "$TEMP_RELEASE"
}

lock_release_tree() {
    local release=$1

    chown -R root:root -- "$release"
    chmod -R u=rwX,go=rX -- "$release"
    release_tree_is_locked "$release"
}

prepare_release() {
    local python

    python3 -m venv "$RELEASE_DIR/venv"
    python="$RELEASE_DIR/venv/bin/python"
    [[ -x "$python" ]] || return 1
    chown -R "$APP_USER:$APP_GROUP" -- "$RELEASE_DIR/venv"
    (
        cd -- "$RELEASE_DIR"
        exec "$RUNUSER" --user "$APP_USER" -- /usr/bin/env -i \
            HOME=/var/lib/labhub-app PATH=/usr/local/bin:/usr/bin:/bin \
            PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
            "$python" -m pip install --disable-pip-version-check \
            --requirement "$RELEASE_DIR/requirements.txt"
    )
    chown -R root:root -- "$RELEASE_DIR/venv"
    chmod -R u=rwX,go=rX -- "$RELEASE_DIR/venv"
    release_tree_is_locked "$RELEASE_DIR"
    run_manage "$RELEASE_DIR" "$V2_ENV" migrate
    install -d -o "$APP_USER" -g "$APP_GROUP" -m 0750 "$RELEASE_DIR/staticfiles"
    run_manage "$RELEASE_DIR" "$V2_ENV" collectstatic
    lock_release_tree "$RELEASE_DIR"
}

reconcile_stale_artifacts() {
    local name path active

    active=$(current_target_path 2>/dev/null || true)
    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        path="$RELEASES_DIR/$name"
        [[ "$path" != "$active" ]] || return 1
        safe_remove_internal_tree "$path"
    done < <(
        find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d -regextype posix-extended \
            -regex '.*/\.(deploy|failed)-[0-9a-f]{40}\.[A-Za-z0-9]+' -printf '%f\n'
    )
    if find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d -regextype posix-extended \
        -regex '.*/\.replaced-[0-9a-f]{40}\.[A-Za-z0-9]+' -print -quit | grep -q .; then
        printf 'Orphan replacement backup lacks transaction provenance.\n' >&2
        return 1
    fi

    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        path="$BASE_DIR/$name"
        [[ -d "$path" && ! -L "$path" && "$(stat -c '%U:%G' -- "$path")" == root:root ]] || return 1
        rm -rf --one-file-system -- "$path"
    done < <(
        find "$BASE_DIR" -mindepth 1 -maxdepth 1 -type d -regextype posix-extended \
            -regex '.*/\.envelope\.[A-Za-z0-9]+' -printf '%f\n'
    )

    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        path="$BASE_DIR/$name"
        [[ -f "$path" && ! -L "$path" && "$(stat -c '%U:%G' -- "$path")" == root:root ]] || return 1
        rm -f -- "$path"
    done < <(
        find "$BASE_DIR" -mindepth 1 -maxdepth 1 -type f -regextype posix-extended \
            -regex '.*/\.deploy-transaction\.tmp\.[A-Za-z0-9]+' -printf '%f\n'
    )

    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        path="$BASE_DIR/$name"
        [[ -L "$path" && "$(stat -c '%U:%G' -- "$path")" == root:root ]] || return 1
        rm -f -- "$path"
    done < <(
        find "$BASE_DIR" -mindepth 1 -maxdepth 1 -type l -regextype posix-extended \
            -regex '.*/\.current\.[0-9a-f]{40}\.[0-9]+' -printf '%f\n'
    )

    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        path="$ENV_DIR/$name"
        [[ -L "$path" && "$(stat -c '%U:%G' -- "$path")" == root:root ]] || return 1
        rm -f -- "$path"
    done < <(
        find "$ENV_DIR" -mindepth 1 -maxdepth 1 -type l -regextype posix-extended \
            -regex '.*/\.environment\.[0-9a-f]{40}\.[0-9]+' -printf '%f\n'
    )
}

cleanup_old_releases() {
    local inactive=0 name candidate failed=false

    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        candidate="$RELEASES_DIR/$name"
        [[ "$candidate" != "$RELEASE_DIR" ]] || continue
        if ((inactive < 2)); then
            ((inactive += 1))
            continue
        fi
        safe_remove_release "$candidate" || failed=true
    done < <(
        find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d -regextype posix-extended \
            -regex '.*/[0-9a-f]{40}' -printf '%T@ %f\n' | sort -rn | cut -d' ' -f2-
    )
    [[ "$failed" == false ]]
}

preflight_root_installation() {
    [[ "$EUID" -eq 0 ]] || fail 'The deployment launcher must run as root.'
    [[ "$(readlink -e -- "$0")" == "$INSTALL_PATH" ]] || fail "Run the reviewed root-installed launcher at $INSTALL_PATH."
    require_root_owned "$INSTALL_PATH" 755 || fail 'The installed launcher must be root:root mode 0755.'
    require_root_owned "$BASE_DIR" 755 || fail 'BASE_DIR must be root:root mode 0755.'
    require_root_owned "$RELEASES_DIR" 755 || fail 'RELEASES_DIR must be root:root mode 0755.'
    require_root_owned "$ENV_DIR" 700 || fail 'The environment directory must be root:root mode 0700.'
    [[ -x "$SYSTEMCTL" && -x "$RUNUSER" ]] || fail 'Required system executables are missing.'
    getent passwd "$APP_USER" >/dev/null || fail 'The dedicated application user is missing.'
    [[ "$(id -gn "$APP_USER")" == "$APP_GROUP" ]] || fail 'The application user has an unexpected primary group.'
    [[ "$("$SYSTEMCTL" show "$SERVICE" --property=LoadState --value)" == loaded ]] || fail 'The service unit is not loaded.'
    if [[ -e "$V1_ENV" || -L "$V1_ENV" ]]; then
        require_root_owned "$V1_ENV" 600 || fail 'The v1 environment is unsafe.'
    fi
    require_root_owned "$V2_ENV" 600 || fail 'The v2 environment is missing or unsafe.'
    require_root_owned "$TRUSTED_ROOT" 644 || fail 'The GitHub trusted root is missing or unsafe.'
    [[ -L "$CURRENT_LINK" && "$(stat -c '%U:%G' -- "$CURRENT_LINK")" == root:root ]] || fail 'current must be a root-owned symlink.'
    [[ -L "$CURRENT_ENV" && "$(stat -c '%U:%G' -- "$CURRENT_ENV")" == root:root ]] || fail 'current.env must be a root-owned symlink.'
    [[ -L "$VENV_LINK" && "$(readlink -- "$VENV_LINK")" == "$CURRENT_LINK/venv" ]] || fail 'production-venv is not the stable current/venv symlink.'
    [[ "$(stat -c '%U:%G' -- "$VENV_LINK")" == root:root ]] || fail 'production-venv must be root-owned.'
}

baseline_check() {
    [[ ! -e "$TRANSACTION_FILE" && ! -L "$TRANSACTION_FILE" ]] || fail 'Resolve the deployment transaction before baseline preflight.'
    [[ "$(current_target_path)" == "$OLD_CHECKOUT" ]] || fail 'current does not point to the old checkout.'
    [[ "$(current_environment_path)" == "$V1_ENV" ]] || fail 'current.env does not point to v1.'
    validate_release_path "$OLD_CHECKOUT"
    if find "$OLD_CHECKOUT" -xdev \( -not -user root -o -not -group root \
        -o \( -not -type l -a -perm /0022 \) \) -print -quit | grep -q .; then
        fail 'The old checkout must be root-owned and not writable by admin.'
    fi
    load_runtime_environment "$V1_ENV"
    "$RUNUSER" --user "$APP_USER" -- test -r "$OLD_CHECKOUT/manage.py"
    "$RUNUSER" --user "$APP_USER" -- test -x "$OLD_CHECKOUT/venv/bin/python"
    "$RUNUSER" --user "$APP_USER" -- test -w /var/lib/labhub/media
    run_manage "$OLD_CHECKOUT" "$V1_ENV" check
    printf 'Baseline v1 preflight succeeded without restarting Daphne.\n'
}

activate_release() {
    write_transaction ready
    atomic_switch "$CURRENT_LINK" "$RELEASE_DIR" current
    atomic_switch "$CURRENT_ENV" "$TARGET_ENV" environment
    write_transaction switched
    [[ "$(readlink -e -- "$VENV_LINK")" == "$RELEASE_DIR/venv" ]] || return 1
    restart_and_verify "$RELEASE_DIR"
    write_success_marker
    write_transaction committed
    trap - ERR TERM INT HUP
    if ! finish_committed_cleanup; then
        printf 'Cleanup warning: healthy committed state retained for the next run.\n' >&2
    elif ! cleanup_old_releases; then
        printf 'Cleanup warning: old-release retention cleanup was incomplete.\n' >&2
    fi
}

deploy_envelope() {
    local archive

    [[ "$ENVELOPE" == "$INCOMING_ENVELOPE" ]] || fail "Envelope path must be $INCOMING_ENVELOPE."
    [[ -f "$ENVELOPE" && ! -L "$ENVELOPE" && -r "$ENVELOPE" ]] || fail 'Deployment envelope is missing or unsafe.'
    [[ "$(stat -c '%s' -- "$ENVELOPE")" -le 3221225472 ]] || fail 'Deployment envelope is too large.'
    [[ -x "$GH" ]] || fail 'Root-installed GitHub CLI is missing.'
    extract_envelope
    verify_attestation
    extract_protected_release
    RELEASE_DIR="$RELEASES_DIR/$SHA"
    PREVIOUS_CURRENT=$(current_target_path) || fail 'current is missing or invalid.'
    PREVIOUS_ENV=$(current_environment_path) || fail 'current.env is missing or invalid.'
    validate_release_path "$PREVIOUS_CURRENT"

    if [[ "$PREVIOUS_CURRENT" == "$RELEASE_DIR" ]]; then
        [[ "$PREVIOUS_ENV" == "$V2_ENV" ]] || fail 'Active release uses an unexpected environment.'
        has_success_marker "$RELEASE_DIR" "$SHA" || fail 'Active same-SHA release lacks its durable success marker.'
        verify_service_identity "$RELEASE_DIR" || fail 'Active same-SHA service identity does not match current.'
        probe_service
        printf 'Release %s is already active, identified, and healthy.\n' "$SHA"
        return 0
    fi

    if [[ -e "$RELEASE_DIR" || -L "$RELEASE_DIR" ]]; then
        [[ -d "$RELEASE_DIR" && ! -L "$RELEASE_DIR" && "$(readlink -e -- "$RELEASE_DIR")" == "$RELEASE_DIR" ]] || \
            fail 'Existing release path is unsafe.'
        REPLACED_BACKUP="$RELEASES_DIR/.replaced-${SHA}.$$"
        [[ ! -e "$REPLACED_BACKUP" && ! -L "$REPLACED_BACKUP" ]] || fail 'Replacement backup path already exists.'
    fi

    write_transaction building
    if [[ -n "$REPLACED_BACKUP" ]]; then
        mv -- "$RELEASE_DIR" "$REPLACED_BACKUP"
    fi
    mv -- "$TEMP_RELEASE" "$RELEASE_DIR"
    TEMP_RELEASE=""
    sync -f "$RELEASES_DIR"
    prepare_release
    sync -f "$RELEASE_DIR"
    activate_release
    printf 'Deployment completed for release %s.\n' "$SHA"
}

rollback_release() {
    SHA=$1
    RELEASE_DIR="$RELEASES_DIR/$SHA"
    validate_release_path "$RELEASE_DIR" || fail 'Rollback target is not a valid protected release.'
    has_success_marker "$RELEASE_DIR" "$SHA" || fail 'Rollback target lacks a valid durable success marker.'
    PREVIOUS_CURRENT=$(current_target_path) || fail 'current is missing or invalid.'
    PREVIOUS_ENV=$(current_environment_path) || fail 'current.env is missing or invalid.'
    validate_release_path "$PREVIOUS_CURRENT"

    if [[ "$PREVIOUS_CURRENT" == "$RELEASE_DIR" ]]; then
        [[ "$PREVIOUS_ENV" == "$V2_ENV" ]] || fail 'Active rollback target uses an unexpected environment.'
        verify_service_identity "$RELEASE_DIR" || fail 'Running service identity does not match the rollback target.'
        probe_service
        printf 'Rollback target %s is already active and healthy.\n' "$SHA"
        return 0
    fi

    activate_release
    printf 'Rollback completed for release %s. Database migrations were not reversed.\n' "$SHA"
}

if [[ "$EUID" -ne 0 ]]; then
    printf 'The deployment launcher must run as root.\n' >&2
    exit 1
fi

if [[ $# -eq 1 && "$1" == --check-baseline ]]; then
    MODE=check
elif [[ $# -eq 2 && "$1" == --rollback ]]; then
        MODE=rollback
        validate_sha "$2" || { usage; exit 2; }
elif [[ $# -eq 1 && "$1" != --* ]]; then
    MODE=deploy
    ENVELOPE=$1
else
    usage
    exit 2
fi

preflight_root_installation
[[ ! -L "$LOCK_FILE" ]] || fail 'Deployment lock must not be a symlink.'
exec 9>"$LOCK_FILE"
chown root:root "$LOCK_FILE"
chmod 0600 "$LOCK_FILE"
flock -n 9 || fail 'Another deployment or rollback is running.'

trap 'on_error $?' ERR
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
trap cleanup_ephemeral EXIT

if [[ -e "$TRANSACTION_FILE" || -L "$TRANSACTION_FILE" ]]; then
    recover_transaction
fi
reconcile_stale_artifacts

case "$MODE" in
    check)
        baseline_check
        ;;
    deploy)
        deploy_envelope
        ;;
    rollback)
        rollback_release "$2"
        ;;
esac
