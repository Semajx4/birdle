#!/bin/bash
# Snapshot everything birdle needs to be rebuilt into ./backups:
#   backups/birdle-DATE.sql.gz          Postgres dump (the birdle-db-backup
#                                       container also writes one daily)
#   backups/volumes/media-DATE.tar.gz   birdle-media volume (audio + images)
#   backups/volumes/data-DATE.tar.gz    birdle-data volume (analytics IP salt)
#   backups/config/                     .env, compose file, start.sh, these scripts
# scripts/sync-backup.sh then copies ./backups to the backup PC.
set -uo pipefail

source /home/js/.config/ntfy_token.env
APP_DIR="/home/js/birdle"
BACKUP_DIR="$APP_DIR/backups"
VOL_DIR="$BACKUP_DIR/volumes"
CONFIG_DIR="$BACKUP_DIR/config"
KEEP_VOLUME_SNAPSHOTS=4
DATE=$(date +%F)
NTFY_URL="https://ntfy.birdle2.nz/backups"

fail() {
    echo "$(date): FAILED: $1" >&2
    curl -s -H "Authorization: Bearer $NTFY_TOKEN" -H "Title: Backup FAILED ⚠️" \
        -H "Tags: warning,rotating_light" -H "Priority: high" \
        -d "birdle: $1" "$NTFY_URL" > /dev/null
    exit 1
}

mkdir -p "$VOL_DIR" "$CONFIG_DIR"

# 1. Fresh Postgres dump (local socket inside the db container needs no password)
f="$BACKUP_DIR/birdle-$DATE.sql.gz"
docker exec birdle-db pg_dump -U birdle -d birdle | gzip > "$f.tmp" \
    && mv "$f.tmp" "$f" || { rm -f "$f.tmp"; fail "pg_dump failed"; }
echo "$(date): DB dump: $(basename "$f")"

# 2. Volume snapshots (read-only mounts; tar streams out so files are ours, not root's)
for vol in media data; do
    f="$VOL_DIR/$vol-$DATE.tar.gz"
    docker run --rm -v "birdle-$vol:/v:ro" alpine tar czf - -C /v . > "$f.tmp" \
        && mv "$f.tmp" "$f" || { rm -f "$f.tmp"; fail "birdle-$vol snapshot failed"; }
    echo "$(date): volume snapshot: $(basename "$f") ($(du -h "$f" | cut -f1))"
done
ls -1t "$VOL_DIR"/media-*.tar.gz | tail -n +$((KEEP_VOLUME_SNAPSHOTS + 1)) | xargs -r rm -f
ls -1t "$VOL_DIR"/data-*.tar.gz  | tail -n +$((KEEP_VOLUME_SNAPSHOTS + 1)) | xargs -r rm -f

# 3. Config + the scripts themselves
cp "$APP_DIR/.env" "$APP_DIR/docker-compose.prod.yml" "$APP_DIR/start.sh" \
   "$APP_DIR/scripts/create-backup.sh" "$APP_DIR/scripts/sync-backup.sh" "$CONFIG_DIR/" \
   || fail "config copy failed"
chmod 600 "$CONFIG_DIR/.env"
echo "$(date): config copied"
