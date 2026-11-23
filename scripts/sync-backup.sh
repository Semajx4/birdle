#!/bin/bash
# Copy ./backups to the backup PC (same machine/key as the immich backup).
# Wakes it with WOL and shuts it down afterwards, unless --no-power.
# Local retention: DB dumps 30 days (db-backup container), volume snapshots
# 4 (create-backup.sh). Remote keeps DB dumps 90 days, volume snapshots 12.
set -uo pipefail

source /home/js/.config/ntfy_token.env
BACKUP_DIR="/home/js/birdle/backups"
REMOTE_HOST="js@192.168.1.46"
REMOTE_MAC="18:c0:4d:34:27:55"
REMOTE_PATH="/mnt/hdd1/backups/birdle"
SSH_KEY="/home/js/.ssh/backup_key"
REMOTE_KEEP_DB_DAYS=90
REMOTE_KEEP_VOLUME_SNAPSHOTS=12
MAX_WAIT=180
NTFY_URL="https://ntfy.birdle2.nz/backups"

notify() {
    curl -s -H "Authorization: Bearer $NTFY_TOKEN" -H "Title: $1" -H "Tags: $3" \
        -H "Priority: ${4:-default}" -d "$2" "$NTFY_URL" > /dev/null
}
fail() {
    echo "$(date): FAILED: $1" >&2
    notify "Backup FAILED ⚠️" "birdle: $1" "warning,rotating_light" "high"
    exit 1
}
remote() { ssh -i "$SSH_KEY" -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_HOST" "$@"; }

SKIP_POWER=false
[[ "${1:-}" == "--no-power" ]] && SKIP_POWER=true

# If the PC is already on (someone's using it), don't wake it or shut it down.
if [ "$SKIP_POWER" = false ] && remote "echo ok" &>/dev/null; then
    echo "$(date): PC already on — will leave it running afterwards"
    SKIP_POWER=true
    ALREADY_ON=true
fi

if [ "$SKIP_POWER" = false ]; then
    echo "$(date): Sending wake-on-LAN packet..."
    wakeonlan "$REMOTE_MAC"
    elapsed=0
    until remote "echo ok" &>/dev/null; do
        sleep 10
        elapsed=$((elapsed + 10))
        [ "$elapsed" -ge "$MAX_WAIT" ] && fail "PC didn't wake up in time"
    done
else
    remote "echo ok" &>/dev/null || fail "PC unreachable"
fi

echo "$(date): PC online — syncing..."
remote "mkdir -p $REMOTE_PATH" || fail "remote mkdir failed"

# No --delete: the remote keeps its own (longer) history, pruned below.
rsync -av -e "ssh -i $SSH_KEY" --exclude '*.tmp' \
    "$BACKUP_DIR/" "$REMOTE_HOST:$REMOTE_PATH/" || fail "rsync failed"

remote "cd $REMOTE_PATH \
    && find . -maxdepth 1 -name 'birdle-*.sql.gz' -mtime +$REMOTE_KEEP_DB_DAYS -delete \
    && for v in media data; do ls -1t volumes/\$v-*.tar.gz | tail -n +$((REMOTE_KEEP_VOLUME_SNAPSHOTS + 1)) | xargs -r rm -f; done" \
    || fail "remote prune failed"

if [ "$SKIP_POWER" = false ]; then
    echo "$(date): Sync complete — shutting down PC"
    notify "Backup complete ✅" "birdle backup finished at $(date '+%H:%M %Z') — sync + shutdown OK" "white_check_mark,floppy_disk"
    remote "sudo shutdown -h now"
else
    why="--no-power mode"; [ "${ALREADY_ON:-false}" = true ] && why="PC was already on, left running"
    echo "$(date): Sync complete ($why)"
    notify "Backup complete ✅" "birdle backup finished at $(date '+%H:%M %Z') — $why" "white_check_mark,floppy_disk"
fi
