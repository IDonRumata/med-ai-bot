"""
One-time script to normalize duplicate metric names in the database.
Run: docker-compose exec bot python scripts/normalize_metrics.py
"""
import sys
sys.path.insert(0, "/app")

import asyncio
import re
from sqlalchemy import text
from bot.database.engine import async_session

# Explicit mappings: regex pattern → canonical name
EXPLICIT = [
    (r"(?i)тиреотропный гормон.*", "ТТГ"),
    (r"(?i)СОЭ по Вестергрену.*|СОЭ[/\\].*", "СОЭ"),
    (r"(?i)сывороточное железо.*", "Железо"),
    (r"(?i)нейтрофилы абс\.?\s*(количество)?[/#%].*", "Нейтрофилы абс."),
    (r"(?i)нейтрофилы\s*[/%].*", "Нейтрофилы %"),
    (r"(?i)эозинофилы абс\.?\s*(количество)?[/#%].*", "Эозинофилы абс."),
    (r"(?i)эозинофилы\s*[/%].*", "Эозинофилы %"),
    (r"(?i)базофилы абс\.?\s*(количество)?[/#%].*", "Базофилы абс."),
    (r"(?i)базофилы\s*[/%].*", "Базофилы %"),
    (r"(?i)лимфоциты абс\.?\s*(количество)?[/#%].*", "Лимфоциты абс."),
    (r"(?i)лимфоциты\s*[/%].*", "Лимфоциты %"),
    (r"(?i)моноциты абс\.?\s*(количество)?[/#%].*", "Моноциты абс."),
    (r"(?i)моноциты\s*[/%].*", "Моноциты %"),
    (r"(?i)средн\.?\s*объем эритроцитов?.*|средний объем эритроцита.*", "MCV"),
    (r"(?i)средн\.?\s*конц\. гемоглобина.*", "MCHC"),
    (r"(?i)средн\.?\s*содерж\. гемоглобина.*", "MCH"),
    (r"(?i)ширина распределения эритроцитов.*", "RDW"),
    (r"(?i)фолликулостимулирующий гормон.*", "ФСГ"),
    (r"(?i)лютеинизирующий гормон.*", "ЛГ"),
    (r"(?i)свободный [тt]4", "Т4 свободный"),
    (r"(?i)глюкоза сыворотки.*", "Глюкоза"),
    (r"(?i)кальций ионизированный расчетный.*", "Кальций ионизированный"),
    (r"(?i)общий кальций.*", "Кальций"),
    (r"(?i)неорганический фосфат.*", "Фосфат"),
    (r"(?i)мочевая кислота\s*/.*", "Мочевая кислота"),
    (r"(?i)билирубин общий\s*/.*", "Билирубин общий"),
    (r"(?i)билирубин прямой\s*/.*", "Билирубин прямой"),
]

# Generic strip: "Русское название / Latin name" → "Русское название"
SLASH_STRIP = re.compile(r"^(.+?)\s*/\s*[A-Za-zА-Яα-ωΑ-Ω].+$")


def canonical(name: str) -> str | None:
    # Explicit rules first
    for pattern, canon in EXPLICIT:
        if re.match(pattern, name):
            return canon if canon != name else None
    # Generic: strip " / Latin" suffix
    m = SLASH_STRIP.match(name)
    if m:
        stripped = m.group(1).strip()
        if stripped != name:
            return stripped
    return None


async def main():
    async with async_session() as session:
        result = await session.execute(
            text("SELECT DISTINCT metric_name FROM test_results ORDER BY metric_name")
        )
        metrics = [row[0] for row in result.fetchall()]

    print(f"Total distinct metrics: {len(metrics)}")
    renames: dict[str, str] = {}
    for m in metrics:
        c = canonical(m)
        if c and c != m:
            renames[m] = c
            print(f"  RENAME: {m!r} -> {c!r}")

    if not renames:
        print("Nothing to rename.")
        return

    confirm = input(f"\nRename {len(renames)} metric(s)? [y/N] ")
    if confirm.lower() != "y":
        print("Aborted.")
        return

    async with async_session() as session:
        for old, new in renames.items():
            # Update rows that don't conflict with existing canonical entry
            await session.execute(
                text("""
                    UPDATE test_results SET metric_name = :new
                    WHERE metric_name = :old
                      AND NOT EXISTS (
                        SELECT 1 FROM test_results t2
                        WHERE t2.user_id = test_results.user_id
                          AND t2.metric_name = :new
                          AND t2.test_date = test_results.test_date
                      )
                """),
                {"old": old, "new": new}
            )
            # Delete remaining old-name rows (duplicates on same user+date)
            await session.execute(
                text("DELETE FROM test_results WHERE metric_name = :old"),
                {"old": old}
            )
        await session.commit()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
