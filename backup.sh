#!/bin/bash
# MedAI Bot — database backup script
# Usage:
#   ./backup.sh            — create backup
#   ./backup.sh restore    — list backups and restore
#
# Add to cron for daily backups at 3:00 AM:
#   0 3 * * * /root/med-ai-bot/backup.sh >> /root/med-ai-bot/backup.log 2>&1

set -euo pipefail

BACKUP_DIR="/root/med-ai-bot/backups"
COMPOSE_DIR="/root/med-ai-bot"
ENV_FILE="$COMPOSE_DIR/.env"
MAX_BACKUPS=30  # keep last 30 days

# Load env vars
set -a
source "$ENV_FILE"
set +a

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/medbot_${TIMESTAMP}.sql.gz"

if [[ "${1:-}" == "restore" ]]; then
    echo "=== Available backups ==="
    ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null || echo "No backups found."
    echo ""
    read -rp "Enter backup filename (e.g. medbot_20260407_030000.sql.gz): " RESTORE_FILE
    RESTORE_PATH="$BACKUP_DIR/$RESTORE_FILE"

    if [[ ! -f "$RESTORE_PATH" ]]; then
        echo "ERROR: File not found: $RESTORE_PATH"
        exit 1
    fi

    echo "Restoring from $RESTORE_PATH ..."
    docker-compose -f "$COMPOSE_DIR/docker-compose.yml" exec -T db \
        psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

    zcat "$RESTORE_PATH" | docker-compose -f "$COMPOSE_DIR/docker-compose.yml" exec -T db \
        psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"

    echo "✅ Restore complete!"
    exit 0
fi

# Create backup
echo "[$(date)] Starting backup..."
docker-compose -f "$COMPOSE_DIR/docker-compose.yml" exec -T db \
    pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_FILE"

SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
echo "[$(date)] Backup saved: $BACKUP_FILE ($SIZE)"

# Rotate old backups
BACKUP_COUNT=$(ls "$BACKUP_DIR"/*.sql.gz 2>/dev/null | wc -l)
if [[ $BACKUP_COUNT -gt $MAX_BACKUPS ]]; then
    ls -t "$BACKUP_DIR"/*.sql.gz | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -f
    echo "[$(date)] Old backups rotated, keeping last $MAX_BACKUPS"
fi

# Send backup to Telegram
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${ALLOWED_USER_ID:-}" ]]; then
    CAPTION="$(printf '🗄 Резервная копия базы данных\n📅 %s\n💾 %s' "$(date '+%d.%m.%Y %H:%M')" "$SIZE")"
    SEND_RESULT=$(curl -s -o /dev/null -w "%{http_code}" \
        -F "chat_id=${ALLOWED_USER_ID}" \
        -F "document=@${BACKUP_FILE}" \
        -F "caption=${CAPTION}" \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendDocument")
    if [[ "$SEND_RESULT" == "200" ]]; then
        echo "[$(date)] Backup sent to Telegram ✓"
    else
        echo "[$(date)] WARNING: Telegram send failed (HTTP $SEND_RESULT)"
    fi
fi

echo "[$(date)] Done."
