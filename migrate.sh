#!/bin/bash
# MedAI Bot — full server migration script
# Run this on the NEW server after cloning the repo
#
# Usage: ./migrate.sh /path/to/backup.sql.gz

set -euo pipefail

BACKUP_FILE="${1:-}"
ENV_FILE=".env"

if [[ -z "$BACKUP_FILE" ]]; then
    echo "Usage: $0 /path/to/backup.sql.gz"
    echo ""
    echo "Steps for manual migration:"
    echo "1. On OLD server: ./backup.sh"
    echo "2. Copy backup: scp root@OLD_IP:/root/med-ai-bot/backups/latest.sql.gz ."
    echo "3. Copy .env:    scp root@OLD_IP:/root/med-ai-bot/.env ."
    echo "4. On NEW server: git clone https://github.com/IDonRumata/med-ai-bot.git"
    echo "5. On NEW server: ./migrate.sh backup.sql.gz"
    exit 0
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: .env file not found. Copy it from the old server first."
    exit 1
fi

echo "=== MedAI Bot Migration ==="
echo "Backup: $BACKUP_FILE"
echo ""

# Start DB only first
echo "[1/4] Starting database..."
docker-compose up -d db
echo "Waiting for PostgreSQL to be ready..."
sleep 10

# Restore data
echo "[2/4] Restoring data..."
set -a; source "$ENV_FILE"; set +a
zcat "$BACKUP_FILE" | docker-compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"

# Start bot
echo "[3/4] Starting bot..."
docker-compose up -d --build bot

# Verify
echo "[4/4] Checking logs..."
sleep 5
docker-compose logs --tail=10 bot

echo ""
echo "✅ Migration complete!"
echo "Check the bot is responding in Telegram."
