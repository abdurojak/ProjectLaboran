#!/usr/bin/bash

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
DEPLOYMENT_STATE="$BASE_DIR/.deploy-history"
OLD_CHECKOUT="$BASE_DIR/ProjectLaboran"

ENV_DIR=/etc/labhub
V1_ENV="$ENV_DIR/labhub-v1.env"
V2_ENV="$ENV_DIR/labhub-v2.env"
CURRENT_ENV="$ENV_DIR/current.env"
ARTIFACT_SIGNING_PUBLIC_KEY="$ENV_DIR/artifact-signing-public.pem"

APP_USER=labhub-app
APP_GROUP=labhub-app
BUILD_USER=labhub-build
BUILD_GROUP=labhub-build
SERVICE=projectlaboran-daphne
SYSTEMCTL=/usr/bin/systemctl
RUNUSER=/usr/sbin/runuser
CURL=/usr/bin/curl
OPENSSL=/usr/bin/openssl
SHA256SUM=/usr/bin/sha256sum
PYTHON3=/usr/bin/python3
RESTORECON=/usr/sbin/restorecon

REPOSITORY=abdurojak/ProjectLaboran
WORKFLOW=.github/workflows/test-runner.yml
SOURCE_REF=refs/heads/main
MAX_ENVELOPE_BYTES=838860800

MODE=""
ENVELOPE=""
SHA=""
RELEASE_DIR=""
PREVIOUS_CURRENT=""
PREVIOUS_ENV=""
TARGET_ENV="$V2_ENV"
REPLACED_BACKUP=""
TEMP_ENVELOPE_DIR=""
ENVELOPE_SNAPSHOT=""
ENVELOPE_DIGEST=""
ARCHIVE_DIGEST=""
RUN_ATTEMPT=""
RUN_ID=""
RUN_NUMBER=""
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
    if [[ "$link" == "$CURRENT_LINK" ]]; then
        "$RESTORECON" -F "$link"
    fi
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
    [[ "$ENVELOPE_DIGEST" =~ ^[0-9a-f]{64}$ ]] || return 1
    [[ "$ARCHIVE_DIGEST" =~ ^[0-9a-f]{64}$ ]] || return 1
    [[ "$RUN_NUMBER" =~ ^[1-9][0-9]*$ ]] || return 1
    [[ "$RUN_ID" =~ ^[1-9][0-9]*$ ]] || return 1
    [[ "$RUN_ATTEMPT" =~ ^[1-9][0-9]*$ ]] || return 1
    printf 'version=4\nsha=%s\nenvironment=%s\nenvelope_sha256=%s\narchive_sha256=%s\nrun_number=%s\nrun_id=%s\nrun_attempt=%s\n' \
        "$SHA" "$V2_ENV" "$ENVELOPE_DIGEST" "$ARCHIVE_DIGEST" \
        "$RUN_NUMBER" "$RUN_ID" "$RUN_ATTEMPT" >"$temp"
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
    local -a lines=()

    [[ -f "$marker" && ! -L "$marker" ]] || return 1
    require_root_owned "$marker" 644 || return 1
    mapfile -t lines <"$marker"
    [[ "${lines[*]}" != *$'\r'* ]] || return 1
    [[ "${#lines[@]}" -eq 3 || "${#lines[@]}" -eq 5 || "${#lines[@]}" -eq 8 ]] || return 1
    [[ "${lines[0]}" == version=2 || "${lines[0]}" == version=3 || "${lines[0]}" == version=4 ]] || return 1
    [[ "${lines[1]}" == "sha=$sha" && "${lines[2]}" == "environment=$V2_ENV" ]] || return 1
    if [[ "${lines[0]}" == version=2 ]]; then
        [[ "${#lines[@]}" -eq 3 ]]
    elif [[ "${lines[0]}" == version=3 ]]; then
        [[ "${#lines[@]}" -eq 5 ]] || return 1
        [[ "${lines[3]}" =~ ^envelope_sha256=[0-9a-f]{64}$ ]] || return 1
        [[ "${lines[4]}" =~ ^archive_sha256=[0-9a-f]{64}$ ]]
    else
        [[ "${#lines[@]}" -eq 8 ]] || return 1
        [[ "${lines[3]}" =~ ^envelope_sha256=[0-9a-f]{64}$ ]] || return 1
        [[ "${lines[4]}" =~ ^archive_sha256=[0-9a-f]{64}$ ]] || return 1
        [[ "${lines[5]}" =~ ^run_number=[1-9][0-9]*$ ]] || return 1
        [[ "${lines[6]}" =~ ^run_id=[1-9][0-9]*$ ]] || return 1
        [[ "${lines[7]}" =~ ^run_attempt=[1-9][0-9]*$ ]]
    fi
}

ensure_deployment_state() {
    "$PYTHON3" -I - "$DEPLOYMENT_STATE" <<'PY'
import errno
import os
import stat
import sys

path = sys.argv[1]
flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
if hasattr(os, "O_NOFOLLOW"):
    flags |= os.O_NOFOLLOW
try:
    fd = os.open(path, flags, 0o600)
except OSError as error:
    if error.errno != errno.EEXIST:
        raise
else:
    os.close(fd)

st = os.lstat(path)
if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_gid != 0:
    raise ValueError("unsafe deployment state file")
if stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1:
    raise ValueError("unsafe deployment state permissions")
PY
}

deployment_state_contains() {
    local wanted_state=$1
    local wanted_sha=$2
    local wanted_envelope=$3
    local wanted_archive=$4
    local line state sha envelope archive

    ensure_deployment_state || return 1
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" =~ ^version=1\ state=(consumed|deployed)\ sha=([0-9a-f]{40})\ envelope_sha256=([0-9a-f]{64})\ archive_sha256=([0-9a-f]{64})$ ]]; then
            state=${BASH_REMATCH[1]}
            sha=${BASH_REMATCH[2]}
            envelope=${BASH_REMATCH[3]}
            archive=${BASH_REMATCH[4]}
        elif [[ "$line" =~ ^version=2\ run_number=([1-9][0-9]*)\ run_id=([1-9][0-9]*)\ run_attempt=([1-9][0-9]*)\ sha=([0-9a-f]{40})\ envelope_sha256=([0-9a-f]{64})\ archive_sha256=([0-9a-f]{64})$ ]]; then
            state=deployed
            sha=${BASH_REMATCH[4]}
            envelope=${BASH_REMATCH[5]}
            archive=${BASH_REMATCH[6]}
        else
            return 2
        fi
        if [[ "$state" == "$wanted_state" && "$sha" == "$wanted_sha" && \
            "$envelope" == "$wanted_envelope" && "$archive" == "$wanted_archive" ]]; then
            return 0
        fi
    done <"$DEPLOYMENT_STATE"
    return 1
}

reject_replayed_artifact() {
    ensure_deployment_state || return 1
    "$PYTHON3" -I - "$DEPLOYMENT_STATE" "$RUN_NUMBER" "$RUN_ID" "$RUN_ATTEMPT" \
        "$ENVELOPE_DIGEST" "$ARCHIVE_DIGEST" <<'PY'
import hmac
import re
import sys

path, run_number_text, run_id_text, run_attempt_text, envelope_digest, archive_digest = sys.argv[1:]
run_number = int(run_number_text)
run_id = int(run_id_text)
run_attempt = int(run_attempt_text)
legacy = re.compile(
    r"version=1 state=(consumed|deployed) sha=([0-9a-f]{40}) "
    r"envelope_sha256=([0-9a-f]{64}) archive_sha256=([0-9a-f]{64})"
)
current = re.compile(
    r"version=2 run_number=([1-9][0-9]*) run_id=([1-9][0-9]*) "
    r"run_attempt=([1-9][0-9]*) sha=([0-9a-f]{40}) "
    r"envelope_sha256=([0-9a-f]{64}) archive_sha256=([0-9a-f]{64})"
)
highest_run_number = 0
for raw_line in open(path, "rb"):
    try:
        line = raw_line.decode("ascii")
        if line.endswith("\n"):
            line = line[:-1]
    except UnicodeDecodeError as error:
        raise ValueError("deployment state is not ASCII") from error
    legacy_match = legacy.fullmatch(line)
    current_match = current.fullmatch(line)
    if legacy_match is None and current_match is None:
        raise ValueError("deployment state is malformed")
    if legacy_match is not None:
        old_envelope, old_archive = legacy_match.group(3, 4)
    else:
        old_run_number, old_run_id, old_run_attempt = map(int, current_match.group(1, 2, 3))
        old_envelope, old_archive = current_match.group(5, 6)
        highest_run_number = max(highest_run_number, old_run_number)
        if old_run_id == run_id and old_run_attempt == run_attempt:
            raise ValueError("signed workflow run and attempt were already deployed")
        if old_run_id == run_id:
            raise ValueError("signed workflow run_id was already deployed")
    if hmac.compare_digest(old_envelope, envelope_digest):
        raise ValueError("deployment envelope was already deployed")
    if hmac.compare_digest(old_archive, archive_digest):
        raise ValueError("protected archive was already deployed")
if run_number <= highest_run_number:
    raise ValueError("signed run_number is not newer than the committed deployment state")
PY
}

record_deployment_state() {
    validate_sha "$SHA" || return 1
    [[ "$RUN_NUMBER" =~ ^[1-9][0-9]*$ ]] || return 1
    [[ "$RUN_ID" =~ ^[1-9][0-9]*$ ]] || return 1
    [[ "$RUN_ATTEMPT" =~ ^[1-9][0-9]*$ ]] || return 1
    [[ "$ENVELOPE_DIGEST" =~ ^[0-9a-f]{64}$ ]] || return 1
    [[ "$ARCHIVE_DIGEST" =~ ^[0-9a-f]{64}$ ]] || return 1
    ensure_deployment_state || return 1
    "$PYTHON3" -I - "$DEPLOYMENT_STATE" "$RUN_NUMBER" "$RUN_ID" "$RUN_ATTEMPT" \
        "$SHA" "$ENVELOPE_DIGEST" "$ARCHIVE_DIGEST" <<'PY'
import os
import re
import stat
import sys
import tempfile

path, run_number, run_id, run_attempt, sha, envelope_digest, archive_digest = sys.argv[1:]
for name, value in (("run_number", run_number), ("run_id", run_id), ("run_attempt", run_attempt)):
    if re.fullmatch(r"[1-9][0-9]*", value) is None:
        raise ValueError(f"invalid {name}")
if re.fullmatch(r"[0-9a-f]{40}", sha) is None:
    raise ValueError("invalid deployment sha")
if any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in (envelope_digest, archive_digest)):
    raise ValueError("invalid deployment digest")
state_path = os.path.abspath(path)
with open(state_path, "rb") as source:
    existing = source.read()
if existing and not existing.endswith(b"\n"):
    raise ValueError("deployment state has a truncated final record")
record = (
    f"version=2 run_number={run_number} run_id={run_id} run_attempt={run_attempt} "
    f"sha={sha} envelope_sha256={envelope_digest} archive_sha256={archive_digest}\n"
).encode("ascii")
fd, temporary = tempfile.mkstemp(prefix=".deploy-history.tmp.", dir=os.path.dirname(state_path))
try:
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_gid != 0:
            raise ValueError("unsafe temporary deployment state file")
        os.fchmod(fd, 0o600)
        payload = existing + record
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short deployment state write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, state_path)
    directory_fd = os.open(os.path.dirname(state_path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
except BaseException:
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass
    raise
PY
}

marker_matches_deployment_state() {
    local release=$1
    local sha=$2
    local marker="$release/.deploy-success"
    local envelope archive state_status
    local -a lines=()

    [[ -f "$marker" && ! -L "$marker" ]] || return 1
    require_root_owned "$marker" 644 || return 1
    mapfile -t lines <"$marker"
    [[ "${#lines[@]}" -eq 5 || "${#lines[@]}" -eq 8 ]] || return 1
    [[ "${lines[*]}" != *$'\r'* ]] || return 1
    [[ "${lines[0]}" == version=3 || "${lines[0]}" == version=4 ]] || return 1
    [[ "${lines[1]}" == "sha=$sha" ]] || return 1
    [[ "${lines[2]}" == "environment=$V2_ENV" ]] || return 1
    [[ "${lines[3]}" =~ ^envelope_sha256=([0-9a-f]{64})$ ]] || return 1
    envelope=${BASH_REMATCH[1]}
    [[ "${lines[4]}" =~ ^archive_sha256=([0-9a-f]{64})$ ]] || return 1
    archive=${BASH_REMATCH[1]}
    if [[ "${lines[0]}" == version=3 ]]; then
        [[ "${#lines[@]}" -eq 5 ]] || return 1
    else
        [[ "${#lines[@]}" -eq 8 ]] || return 1
        [[ "${lines[5]}" =~ ^run_number=[1-9][0-9]*$ ]] || return 1
        [[ "${lines[6]}" =~ ^run_id=[1-9][0-9]*$ ]] || return 1
        [[ "${lines[7]}" =~ ^run_attempt=[1-9][0-9]*$ ]] || return 1
    fi
    if deployment_state_contains deployed "$sha" "$envelope" "$archive"; then
        return 0
    else
        state_status=$?
    fi
    [[ "$state_status" -eq 1 && "${lines[0]}" == version=4 && "${#lines[@]}" -eq 8 ]] || return "$state_status"
    [[ "${lines[5]}" =~ ^run_number=([1-9][0-9]*)$ ]] || return 1
    RUN_NUMBER=${BASH_REMATCH[1]}
    [[ "${lines[6]}" =~ ^run_id=([1-9][0-9]*)$ ]] || return 1
    RUN_ID=${BASH_REMATCH[1]}
    [[ "${lines[7]}" =~ ^run_attempt=([1-9][0-9]*)$ ]] || return 1
    RUN_ATTEMPT=${BASH_REMATCH[1]}
    SHA=$sha
    ENVELOPE_DIGEST=$envelope
    ARCHIVE_DIGEST=$archive
    record_deployment_state
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
        if status=$("$CURL" --silent --show-error --output /dev/null \
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
            if [[ "$(current_target_path 2>/dev/null || true)" == "$TX_RELEASE" && \
                "$TX_PREVIOUS" != "$TX_RELEASE" ]]; then
                return 1
            fi
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
    local original_phase current_code current_env
    local restart_required=false
    local publication_restored=false

    read_transaction || { printf 'Transaction journal is malformed; refusing recovery.\n' >&2; return 1; }
    [[ "$TX_PHASE" != committed ]] || return 1
    original_phase=$TX_PHASE
    current_code=$(current_target_path 2>/dev/null || true)
    current_env=$(current_environment_path 2>/dev/null || true)
    if [[ "$original_phase" == switched || "$original_phase" == rolling-back || \
        "$current_code" != "$TX_PREVIOUS" || \
        "$current_env" != "$TX_PREVIOUS_ENV" ]]; then
        restart_required=true
    fi
    rewrite_transaction_phase rolling-back || return 1
    SHA=$TX_SHA
    if [[ "$TX_KIND" == deploy && "$TX_PREVIOUS" == "$TX_RELEASE" ]]; then
        restore_deploy_publication || return 1
        publication_restored=true
    fi
    if [[ "$current_code" != "$TX_PREVIOUS" ]]; then
        atomic_switch "$CURRENT_LINK" "$TX_PREVIOUS" current || return 1
    fi
    if [[ "$current_env" != "$TX_PREVIOUS_ENV" ]]; then
        atomic_switch "$CURRENT_ENV" "$TX_PREVIOUS_ENV" environment || return 1
    fi
    if [[ "$publication_restored" == false ]]; then
        restore_deploy_publication || return 1
    fi
    if [[ "$restart_required" == true ]]; then
        restart_and_verify "$TX_PREVIOUS" || return 1
    fi
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
    local marker_valid=false

    read_transaction || { printf 'Transaction journal is malformed; refusing deployment.\n' >&2; return 1; }
    printf 'Recovering %s transaction for %s at phase %s.\n' "$TX_KIND" "$TX_SHA" "$TX_PHASE" >&2
    SHA=$TX_SHA
    if [[ "$TX_PHASE" == committed ]]; then
        if [[ "$TX_KIND" == deploy ]]; then
            marker_matches_deployment_state "$TX_RELEASE" "$TX_SHA" && marker_valid=true
        else
            has_success_marker "$TX_RELEASE" "$TX_SHA" && marker_valid=true
        fi
        if [[ "$(current_target_path 2>/dev/null || true)" != "$TX_RELEASE" ]] || \
            [[ "$(current_environment_path 2>/dev/null || true)" != "$TX_TARGET_ENV" ]] || \
            [[ "$marker_valid" != true ]] || \
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
    ENVELOPE_SNAPSHOT="$TEMP_ENVELOPE_DIR/envelope.snapshot.tar"
    "$PYTHON3" -I - "$ENVELOPE" "$ENVELOPE_SNAPSHOT" "$TEMP_ENVELOPE_DIR" "$MAX_ENVELOPE_BYTES" <<'PY'
import os
import re
import stat
import sys
import tarfile
from pathlib import Path

source_path = Path(sys.argv[1])
snapshot_path = Path(sys.argv[2])
destination = Path(sys.argv[3])
max_envelope_bytes = int(sys.argv[4])
expected = {
    "projectlaboran.protected.tar.gz": 768 * 1024 * 1024,
    "deployment-manifest.json": 4096,
    "deployment-manifest.sig": 64,
}

source_flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
if hasattr(os, "O_NOFOLLOW"):
    source_flags |= os.O_NOFOLLOW
source_fd = os.open(source_path, source_flags)
snapshot_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
if hasattr(os, "O_NOFOLLOW"):
    snapshot_flags |= os.O_NOFOLLOW
snapshot_fd = os.open(snapshot_path, snapshot_flags, 0o600)
try:
    source_stat = os.fstat(source_fd)
    if not stat.S_ISREG(source_stat.st_mode):
        raise ValueError("deployment envelope source is not a regular file")
    copied = 0
    while True:
        chunk = os.read(source_fd, 1024 * 1024)
        if not chunk:
            break
        copied += len(chunk)
        if copied > max_envelope_bytes:
            raise ValueError("deployment envelope snapshot is too large")
        view = memoryview(chunk)
        while view:
            written = os.write(snapshot_fd, view)
            if written <= 0:
                raise OSError("short deployment envelope snapshot write")
            view = view[written:]
    if copied == 0:
        raise ValueError("deployment envelope snapshot is empty")
    os.fsync(snapshot_fd)
finally:
    os.close(source_fd)
    os.close(snapshot_fd)

raw_seen = set()
raw_header_count = 0
raw_size = snapshot_path.stat().st_size
zero_block = b"\0" * tarfile.BLOCKSIZE
extension_types = {
    tarfile.XHDTYPE,
    tarfile.XGLTYPE,
    tarfile.GNUTYPE_LONGNAME,
    tarfile.GNUTYPE_LONGLINK,
    tarfile.GNUTYPE_SPARSE,
}
with open(snapshot_path, "rb") as raw_envelope:
    while True:
        header = raw_envelope.read(tarfile.BLOCKSIZE)
        if len(header) != tarfile.BLOCKSIZE:
            raise ValueError("deployment envelope is truncated before its tar end marker")
        if header == zero_block:
            if raw_envelope.read(tarfile.BLOCKSIZE) != zero_block:
                raise ValueError("deployment envelope has an incomplete tar end marker")
            for chunk in iter(lambda: raw_envelope.read(1024 * 1024), b""):
                if chunk.strip(b"\0"):
                    raise ValueError("deployment envelope has nonzero trailing content")
            break
        raw_header_count += 1
        if raw_header_count > 3:
            raise ValueError("deployment envelope contains more than three raw entries")
        try:
            raw_member = tarfile.TarInfo.frombuf(header, encoding="ascii", errors="strict")
        except (tarfile.HeaderError, UnicodeError, ValueError) as error:
            raise ValueError("deployment envelope contains an invalid raw tar header") from error
        if raw_member.type in extension_types:
            raise ValueError("deployment envelope contains forbidden PAX or GNU extension metadata")
        if raw_member.type not in {tarfile.REGTYPE, tarfile.AREGTYPE}:
            raise ValueError("deployment envelope raw entry is not a regular file")
        if raw_member.name not in expected or raw_member.name in raw_seen:
            raise ValueError("deployment envelope contains a duplicate or unexpected raw entry")
        if raw_member.size < 1 or raw_member.size > expected[raw_member.name]:
            raise ValueError("deployment envelope raw entry has an unsafe size")
        padded_size = (
            (raw_member.size + tarfile.BLOCKSIZE - 1) // tarfile.BLOCKSIZE
        ) * tarfile.BLOCKSIZE
        if raw_envelope.tell() + padded_size + (2 * tarfile.BLOCKSIZE) > raw_size:
            raise ValueError("deployment envelope raw entry is truncated")
        raw_envelope.seek(padded_size, os.SEEK_CUR)
        raw_seen.add(raw_member.name)

if raw_header_count != 3 or raw_seen != set(expected):
    raise ValueError("deployment envelope must contain exactly three raw regular entries")

seen = set()
total_size = 0
header_count = 0
with tarfile.open(snapshot_path, "r|") as archive:
    for member in archive:
        header_count += 1
        if header_count > 3:
            raise ValueError("deployment envelope contains more than three entries")
        if member.name not in expected or member.name in seen:
            raise ValueError("deployment envelope contains a duplicate or unexpected entry")
        if (
            not member.isfile()
            or member.name.startswith(("/", "\\"))
            or "/" in member.name
            or "\\" in member.name
            or member.pax_headers
            or getattr(member, "sparse", None) is not None
            or member.offset_data != member.offset + tarfile.BLOCKSIZE
        ):
            raise ValueError("unsafe deployment envelope entry")
        if member.mode != 0o644 or member.size < 1 or member.size > expected[member.name]:
            raise ValueError("unsafe deployment envelope mode or size")
        if member.name == "deployment-manifest.sig" and member.size != 64:
            raise ValueError("deployment manifest signature must be exactly 64 bytes")
        total_size += member.size
        if total_size > sum(expected.values()):
            raise ValueError("deployment envelope content is too large")
        source = archive.extractfile(member)
        if source is None:
            raise ValueError("unreadable deployment envelope entry")
        target = destination / member.name
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(target, flags, 0o600)
        with source, os.fdopen(fd, "wb") as output:
            remaining = member.size
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("truncated deployment envelope member")
                output.write(chunk)
                remaining -= len(chunk)
            output.flush()
            os.fsync(output.fileno())
        seen.add(member.name)

if header_count != 3 or seen != set(expected):
    raise ValueError("deployment envelope must contain exactly the expected files")
PY
    ENVELOPE_DIGEST=$($SHA256SUM -- "$ENVELOPE_SNAPSHOT")
    ENVELOPE_DIGEST=${ENVELOPE_DIGEST%% *}
    [[ "$ENVELOPE_DIGEST" =~ ^[0-9a-f]{64}$ ]]
}

verify_manifest_signature() {
    local manifest="$TEMP_ENVELOPE_DIR/deployment-manifest.json"
    local signature="$TEMP_ENVELOPE_DIR/deployment-manifest.sig"

    if "$OPENSSL" pkeyutl -verify -pubin -inkey "$ARTIFACT_SIGNING_PUBLIC_KEY" \
        -rawin -in "$manifest" -sigfile "$signature" >/dev/null 2>&1; then
        printf 'Artifact manifest signature verification succeeded.\n'
    else
        printf 'Artifact manifest signature verification failed.\n' >&2
        return 1
    fi
}

parse_signed_manifest() {
    local archive="$TEMP_ENVELOPE_DIR/projectlaboran.protected.tar.gz"
    local manifest="$TEMP_ENVELOPE_DIR/deployment-manifest.json"
    local claims
    local -a fields=()

    claims=$("$PYTHON3" -I - "$manifest" "$archive" "$REPOSITORY" "$WORKFLOW" "$SOURCE_REF" <<'PY'
import hashlib
import hmac
import json
import re
import sys

manifest_path, archive_path, repository, workflow, source_ref = sys.argv[1:]
manifest_bytes = open(manifest_path, "rb").read()
if not manifest_bytes or len(manifest_bytes) > 4096:
    raise ValueError("deployment manifest has an unsafe size")
try:
    manifest_text = manifest_bytes.decode("utf-8", "strict")
except UnicodeDecodeError as error:
    raise ValueError("deployment manifest is not valid UTF-8") from error

def object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("deployment manifest contains a duplicate JSON key")
        result[key] = value
    return result

try:
    payload = json.loads(manifest_text, object_pairs_hook=object_without_duplicates)
except json.JSONDecodeError as error:
    raise ValueError("deployment manifest is not valid JSON") from error
expected_keys = {
    "archive_name", "archive_sha256", "repository", "run_attempt", "run_id",
    "run_number", "source_ref", "source_sha", "version", "workflow",
}
if type(payload) is not dict or set(payload) != expected_keys:
    raise ValueError("deployment manifest schema is invalid")
canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8") + b"\n"
if not hmac.compare_digest(manifest_bytes, canonical):
    raise ValueError("deployment manifest is not canonical JSON")
if payload["archive_name"] != "projectlaboran.protected.tar.gz":
    raise ValueError("deployment manifest archive_name is invalid")
if payload["repository"] != repository:
    raise ValueError("deployment manifest repository is invalid")
if payload["workflow"] != workflow:
    raise ValueError("deployment manifest workflow is invalid")
if payload["source_ref"] != source_ref:
    raise ValueError("deployment manifest source_ref is invalid")
if type(payload["version"]) is not int or payload["version"] != 1:
    raise ValueError("deployment manifest version is invalid")
for key in ("run_attempt", "run_id", "run_number"):
    if type(payload[key]) is not int or payload[key] <= 0:
        raise ValueError(f"deployment manifest {key} is invalid")
if type(payload["source_sha"]) is not str or re.fullmatch(r"[0-9a-f]{40}", payload["source_sha"]) is None:
    raise ValueError("deployment manifest source_sha is invalid")
if type(payload["archive_sha256"]) is not str or re.fullmatch(r"[0-9a-f]{64}", payload["archive_sha256"]) is None:
    raise ValueError("deployment manifest archive_sha256 is invalid")
digest = hashlib.sha256()
with open(archive_path, "rb") as archive:
    for chunk in iter(lambda: archive.read(1024 * 1024), b""):
        digest.update(chunk)
actual_digest = digest.hexdigest()
if not hmac.compare_digest(actual_digest, payload["archive_sha256"]):
    raise ValueError("protected archive digest does not match signed manifest")
print(payload["source_sha"])
print(payload["archive_sha256"])
print(payload["run_attempt"])
print(payload["run_id"])
print(payload["run_number"])
PY
    ) || return 1
    mapfile -t fields <<<"$claims"
    [[ "${#fields[@]}" -eq 5 ]] || return 1
    SHA=${fields[0]}
    ARCHIVE_DIGEST=${fields[1]}
    RUN_ATTEMPT=${fields[2]}
    RUN_ID=${fields[3]}
    RUN_NUMBER=${fields[4]}
    validate_sha "$SHA"
    [[ "$ARCHIVE_DIGEST" =~ ^[0-9a-f]{64}$ ]]
    [[ "$RUN_ATTEMPT" =~ ^[1-9][0-9]*$ && "$RUN_ID" =~ ^[1-9][0-9]*$ && "$RUN_NUMBER" =~ ^[1-9][0-9]*$ ]]
}

extract_protected_release() {
    local archive="$TEMP_ENVELOPE_DIR/projectlaboran.protected.tar.gz"

    TEMP_RELEASE=$(mktemp -d "$RELEASES_DIR/.deploy-${SHA}.XXXXXX")
    chmod 0700 "$TEMP_RELEASE"
    "$PYTHON3" -I - "$archive" "$TEMP_RELEASE" <<'PY'
import gzip
import os
import sys
import tarfile
from pathlib import Path, PurePosixPath, PureWindowsPath

archive_path = Path(sys.argv[1])
destination = Path(sys.argv[2])
max_entries = 100_000
max_total_size = 1024 * 1024 * 1024
max_member_size = 512 * 1024 * 1024
max_trailing_size = 1024 * 1024
max_raw_size = (
    max_total_size
    + (max_entries * 2 * tarfile.BLOCKSIZE)
    + (2 * tarfile.BLOCKSIZE)
    + max_trailing_size
)
zero_block = b"\0" * tarfile.BLOCKSIZE
extension_types = {
    tarfile.XHDTYPE,
    tarfile.XGLTYPE,
    tarfile.GNUTYPE_LONGNAME,
    tarfile.GNUTYPE_LONGLINK,
    tarfile.GNUTYPE_SPARSE,
}

with gzip.open(archive_path, "rb") as raw_archive:
    raw_header_count = 0
    raw_file_data = 0
    raw_bytes_processed = 0

    def bounded_read(size):
        global raw_bytes_processed
        data = raw_archive.read(size)
        raw_bytes_processed += len(data)
        if raw_bytes_processed > max_raw_size:
            raise ValueError("protected archive decompressed data is too large")
        return data

    def discard_exact(size):
        remaining = size
        while remaining:
            chunk = bounded_read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError("truncated protected archive raw entry")
            remaining -= len(chunk)

    while True:
        header = bounded_read(tarfile.BLOCKSIZE)
        if len(header) != tarfile.BLOCKSIZE:
            raise ValueError("protected archive is truncated before its tar end marker")
        if header == zero_block:
            if bounded_read(tarfile.BLOCKSIZE) != zero_block:
                raise ValueError("protected archive has an incomplete tar end marker")
            trailing_size = 0
            while True:
                chunk = bounded_read(1024 * 1024)
                if not chunk:
                    break
                trailing_size += len(chunk)
                if trailing_size > max_trailing_size:
                    raise ValueError("protected archive has excessive trailing padding")
                if chunk.strip(b"\0"):
                    raise ValueError("protected archive has nonzero trailing content")
            break
        raw_header_count += 1
        if raw_header_count > max_entries:
            raise ValueError("protected archive contains too many raw headers")
        try:
            raw_member = tarfile.TarInfo.frombuf(header, encoding="utf-8", errors="strict")
        except (tarfile.HeaderError, UnicodeError, ValueError) as error:
            raise ValueError("protected archive contains an invalid raw tar header") from error
        if raw_member.type in extension_types:
            raise ValueError("protected archive contains forbidden PAX or GNU extension metadata")
        if raw_member.type not in {tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE}:
            raise ValueError("protected archive contains an unsafe raw entry type")
        if raw_member.isdir():
            if raw_member.size != 0:
                raise ValueError("protected archive raw directory has data")
        else:
            if raw_member.size < 0 or raw_member.size > max_member_size:
                raise ValueError("protected archive raw member size is unsafe")
            raw_file_data += raw_member.size
            if raw_file_data > max_total_size:
                raise ValueError("protected archive declared file data is too large")
        padded_size = (
            (raw_member.size + tarfile.BLOCKSIZE - 1) // tarfile.BLOCKSIZE
        ) * tarfile.BLOCKSIZE
        discard_exact(padded_size)

with tarfile.open(archive_path, "r|gz") as archive:
    kinds = {}
    total_size = 0
    entry_count = 0
    for member in archive:
        entry_count += 1
        if entry_count > max_entries:
            raise ValueError("protected archive contains too many entries")
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
        if member.pax_headers or getattr(member, "sparse", None) is not None:
            raise ValueError("unsupported protected archive metadata")
        if member.mode & 0o7022 or member.size > max_member_size:
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
        target = destination.joinpath(*member_path.parts)
        if member.isdir():
            target.mkdir(mode=0o755, parents=True, exist_ok=True)
            continue
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise ValueError("unreadable protected archive entry")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(target, flags, 0o644)
        with source, os.fdopen(fd, "wb") as output:
            remaining = member.size
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("truncated protected archive member")
                output.write(chunk)
                remaining -= len(chunk)
            output.flush()
            os.fsync(output.fileno())
PY
    [[ -f "$TEMP_RELEASE/manage.py" && ! -L "$TEMP_RELEASE/manage.py" ]] || return 1
    [[ -s "$TEMP_RELEASE/requirements.lock" && ! -L "$TEMP_RELEASE/requirements.lock" ]] || return 1
    [[ -d "$TEMP_RELEASE/wheelhouse" && ! -L "$TEMP_RELEASE/wheelhouse" ]] || return 1
    find "$TEMP_RELEASE/wheelhouse" -xdev -type f -name '*.whl' -print -quit | grep -q . || return 1
    if find "$TEMP_RELEASE/wheelhouse" -xdev -type f ! -name '*.whl' -print -quit | grep -q .; then
        return 1
    fi
    if find "$TEMP_RELEASE/wheelhouse" -mindepth 1 -xdev ! -type f -print -quit | grep -q .; then
        return 1
    fi
    "$PYTHON3" -I - "$TEMP_RELEASE/requirements.lock" <<'PY'
import re
import sys
from pathlib import Path

lock_path = Path(sys.argv[1])
if lock_path.stat().st_size > 4 * 1024 * 1024:
    raise ValueError("requirements lock is too large")
lock = lock_path.read_bytes()
if not lock or b"\x00" in lock or b"\r" in lock:
    raise ValueError("unsafe requirements lock")
text = lock.decode("utf-8")
for raw_line in text.splitlines():
    line = raw_line.split("#", 1)[0].strip()
    if not line:
        continue
    if re.search(r"(?i)(?:https?|ftp)://|file:|--(?:extra-)?index-url|--find-links|--trusted-host|--editable", line):
        raise ValueError("requirements lock may not select a network or external source")
    if re.search(r"(^|\s)-e(?:\s|=|$)|\s@\s|(^|\s)(?:\.\.?/|/)", line):
        raise ValueError("requirements lock may not select a local or direct source")
    if "${" in line or "%(" in line:
        raise ValueError("requirements lock may not expand environment or config values")
PY
    [[ ! -e "$TEMP_RELEASE/venv" && ! -L "$TEMP_RELEASE/venv" ]] || return 1
    [[ ! -e "$TEMP_RELEASE/staticfiles" && ! -L "$TEMP_RELEASE/staticfiles" ]] || return 1
    [[ ! -e "$TEMP_RELEASE/.deploy-success" && ! -L "$TEMP_RELEASE/.deploy-success" ]] || return 1
    [[ ! -e "$TEMP_RELEASE/.env" && ! -L "$TEMP_RELEASE/.env" ]] || return 1
    [[ ! -e "$TEMP_RELEASE/media" && ! -L "$TEMP_RELEASE/media" ]] || return 1
    chown -R root:root -- "$TEMP_RELEASE"
    chmod -R u=rwX,go=rX -- "$TEMP_RELEASE"
    [[ "$(stat -c '%U:%G' -- "$TEMP_RELEASE/requirements.lock")" == root:root ]] || return 1
    if find "$TEMP_RELEASE/wheelhouse" -xdev \( -not -user root -o -not -group root \) -print -quit | grep -q .; then
        return 1
    fi
    chown root:"$BUILD_GROUP" "$TEMP_RELEASE"
    chmod 0710 "$TEMP_RELEASE"
}

lock_release_tree() {
    local release=$1

    chown -R root:root -- "$release"
    chmod -R u=rwX,go=rX -- "$release"
    release_tree_is_locked "$release"
}

build_candidate() {
    local candidate=$TEMP_RELEASE
    local python="$TEMP_RELEASE/venv/bin/python"
    local build_uid build_gid

    [[ -d "$candidate" && ! -L "$candidate" ]] || return 1
    [[ "$(stat -c '%U:%G %a' -- "$candidate")" == "root:$BUILD_GROUP 710" ]] || return 1
    install -d -o "$BUILD_USER" -g "$BUILD_GROUP" -m 0700 "$candidate/venv"
    "$RUNUSER" --user "$BUILD_USER" -- /usr/bin/env -i \
        HOME=/var/lib/labhub-build PATH=/usr/local/bin:/usr/bin:/bin \
        PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
        "$PYTHON3" -I -m venv "$candidate/venv"
    [[ -x "$python" ]] || return 1
    (
        cd -- "$candidate"
        exec "$RUNUSER" --user "$BUILD_USER" -- /usr/bin/env -i \
            HOME=/var/lib/labhub-build PATH=/usr/local/bin:/usr/bin:/bin \
            PIP_CONFIG_FILE=/dev/null PIP_NO_INDEX=1 \
            PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
            "$python" -m pip install --no-index \
            --find-links "$candidate/wheelhouse" --require-hashes \
            -r "$candidate/requirements.lock"
    )
    install -d -o "$BUILD_USER" -g "$BUILD_GROUP" -m 0700 "$candidate/staticfiles"
    (
        cd -- "$candidate"
        exec "$RUNUSER" --user "$BUILD_USER" -- /usr/bin/env -i \
            HOME=/var/lib/labhub-build PATH=/usr/local/bin:/usr/bin:/bin \
            PYTHONDONTWRITEBYTECODE=1 \
            SECRET_KEY=cs7Yz6BLj2Vp4uX9Qf8Na3Km5Rw1Hg0Dt6Ec9Ps4Wv2Jx7Lb8Mn5 \
            DEBUG=False \
            LABHUB_LICENSE_ENFORCED=False \
            "$python" manage.py collectstatic --noinput
    )
    build_uid=$(id -u "$BUILD_USER")
    build_gid=$(getent group "$BUILD_GROUP" | cut -d: -f3)
    "$PYTHON3" -I - "$candidate/staticfiles" "$build_uid" "$build_gid" <<'PY'
import os
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1])
expected_uid = int(sys.argv[2])
expected_gid = int(sys.argv[3])
max_entries = 100_000
max_total_size = 1024 * 1024 * 1024
max_file_size = 64 * 1024 * 1024
entries = 0
total_size = 0

root_stat = root.lstat()
if not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_uid != expected_uid or root_stat.st_gid != expected_gid:
    raise ValueError("unsafe static root")

for current, directories, files in os.walk(root, topdown=True, followlinks=False):
    current_path = Path(current)
    for name in directories + files:
        path = current_path / name
        item = path.lstat()
        entries += 1
        if entries > max_entries:
            raise ValueError("static tree contains too many entries")
        if item.st_uid != expected_uid or item.st_gid != expected_gid:
            raise ValueError("static tree has unexpected ownership")
        if stat.S_ISDIR(item.st_mode):
            continue
        if not stat.S_ISREG(item.st_mode) or item.st_nlink != 1:
            raise ValueError("static tree contains an unsafe entry")
        if item.st_size > max_file_size:
            raise ValueError("static file is too large")
        total_size += item.st_size
        if total_size > max_total_size:
            raise ValueError("static tree is too large")
if entries == 0:
    raise ValueError("static tree is empty")
PY
    chown -R root:root -- "$candidate"
    chmod -R u=rwX,go=rX -- "$candidate"
    chmod 0700 "$candidate"
    release_tree_is_locked "$candidate"
}

prepare_published_release() {
    release_tree_is_locked "$RELEASE_DIR" || return 1
    [[ -d "$RELEASE_DIR/staticfiles" && ! -L "$RELEASE_DIR/staticfiles" ]] || return 1
    "$RESTORECON" -F "$RELEASE_DIR"
    "$RESTORECON" -RF "$RELEASE_DIR/staticfiles"
    release_tree_is_locked "$RELEASE_DIR" || return 1
    run_manage "$RELEASE_DIR" "$V2_ENV" check
    run_manage "$RELEASE_DIR" "$V2_ENV" migrate
    release_tree_is_locked "$RELEASE_DIR"
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
    local build_gid

    [[ "$EUID" -eq 0 ]] || fail 'The deployment launcher must run as root.'
    [[ "$(readlink -e -- "$0")" == "$INSTALL_PATH" ]] || fail "Run the reviewed root-installed launcher at $INSTALL_PATH."
    require_root_owned "$INSTALL_PATH" 755 || fail 'The installed launcher must be root:root mode 0755.'
    require_root_owned "$BASE_DIR" 755 || fail 'BASE_DIR must be root:root mode 0755.'
    require_root_owned "$RELEASES_DIR" 755 || fail 'RELEASES_DIR must be root:root mode 0755.'
    require_root_owned "$ENV_DIR" 700 || fail 'The environment directory must be root:root mode 0700.'
    [[ -x "$SYSTEMCTL" && -x "$RUNUSER" && -x "$CURL" && -x "$OPENSSL" && \
        -x "$SHA256SUM" && -x "$PYTHON3" && -x "$RESTORECON" ]] || \
        fail 'Required system executables are missing.'
    getent passwd "$APP_USER" >/dev/null || fail 'The dedicated application user is missing.'
    [[ "$(id -gn "$APP_USER")" == "$APP_GROUP" ]] || fail 'The application user has an unexpected primary group.'
    getent passwd "$BUILD_USER" >/dev/null || fail 'The dedicated build user is missing.'
    [[ "$(id -gn "$BUILD_USER")" == "$BUILD_GROUP" ]] || fail 'The build user has an unexpected primary group.'
    [[ "$BUILD_USER" != "$APP_USER" ]] || fail 'Build and runtime users must be distinct.'
    build_gid=$(getent group "$BUILD_GROUP" | cut -d: -f3)
    [[ "$build_gid" =~ ^[0-9]+$ ]] || fail 'The build group is invalid.'
    [[ " $(id -G admin) " != *" $build_gid "* ]] || fail 'Runner admin must not belong to the build group.'
    [[ " $(id -G "$APP_USER") " != *" $build_gid "* ]] || fail 'Runtime user must not belong to the build group.'
    [[ "$("$SYSTEMCTL" show "$SERVICE" --property=LoadState --value)" == loaded ]] || fail 'The service unit is not loaded.'
    if [[ -e "$V1_ENV" || -L "$V1_ENV" ]]; then
        require_root_owned "$V1_ENV" 600 || fail 'The v1 environment is unsafe.'
    fi
    require_root_owned "$V2_ENV" 600 || fail 'The v2 environment is missing or unsafe.'
    require_root_owned "$ARTIFACT_SIGNING_PUBLIC_KEY" 644 || fail 'The artifact signing public key is missing or unsafe.'
    "$OPENSSL" pkey -pubin -in "$ARTIFACT_SIGNING_PUBLIC_KEY" -noout >/dev/null 2>&1 || \
        fail 'The artifact signing public key or OpenSSL Ed25519 support is invalid.'
    [[ -L "$CURRENT_LINK" && "$(stat -c '%U:%G' -- "$CURRENT_LINK")" == root:root ]] || fail 'current must be a root-owned symlink.'
    [[ -L "$CURRENT_ENV" && "$(stat -c '%U:%G' -- "$CURRENT_ENV")" == root:root ]] || fail 'current.env must be a root-owned symlink.'
    [[ -L "$VENV_LINK" && "$(readlink -- "$VENV_LINK")" == "$CURRENT_LINK/venv" ]] || fail 'production-venv is not the stable current/venv symlink.'
    [[ "$(stat -c '%U:%G' -- "$VENV_LINK")" == root:root ]] || fail 'production-venv must be root-owned.'
    ensure_deployment_state || fail 'The root-owned deployment state is unsafe.'
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
    if [[ "$MODE" == deploy ]]; then
        write_success_marker
    fi
    write_transaction committed
    if [[ "$MODE" == deploy ]]; then
        record_deployment_state
    fi
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
    [[ "$(stat -c '%s' -- "$ENVELOPE")" -le "$MAX_ENVELOPE_BYTES" ]] || fail 'Deployment envelope is too large.'
    extract_envelope
    verify_manifest_signature
    parse_signed_manifest
    RELEASE_DIR="$RELEASES_DIR/$SHA"
    PREVIOUS_CURRENT=$(current_target_path) || fail 'current is missing or invalid.'
    PREVIOUS_ENV=$(current_environment_path) || fail 'current.env is missing or invalid.'
    validate_release_path "$PREVIOUS_CURRENT"
    if [[ "$PREVIOUS_CURRENT" == "$RELEASE_DIR" ]]; then
        fail 'The current main SHA is already active; normal redeployment of an active SHA is prohibited.'
    fi
    reject_replayed_artifact
    extract_protected_release
    build_candidate

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
    chmod 0755 "$RELEASE_DIR"
    sync -f "$RELEASES_DIR"
    prepare_published_release
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
