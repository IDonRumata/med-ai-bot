"""
One-time script to normalize duplicate metric names in the database.
Run: docker-compose exec bot python scripts/normalize_metrics.py
"""
import asyncio
import re
from sqlalchemy import text
from bot.database.connection import get_engine

# Mapping: old name pattern (regex) → canonical name
NORMALIZATIONS = [
    # TSH
    (r"(?i)тиреотропный гормон.*|ТТГ.*\(ТТГ\).*", "ТТГ"),
    # SOE
    (r"(?i)СОЭ по Вестергрену.*|СОЭ/.*", "СОЭ"),
    # Iron
    (r"(?i)Сывороточное железо.*|Железо сыворотки.*", "Железо"),
    # Neutrophils absolute
    (r"(?i)Нейтрофилы абс\.?\s*[/#].*|Нейтрофилы абс\. количество[/#].*", "Нейтрофилы абс."),
    # Neutrophils %
    (r"(?i)Нейтрофилы[/%].*", "Нейтрофилы %"),
    # Eosinophils absolute
    (r"(?i)Эозинофилы абс\.?\s*[/#].*|Эозинофилы абс\. количество[/#].*", "Эозинофилы абс."),
    # Eosinophils %
    (r"(?i)Эозинофилы[/%].*", "Эозинофилы %"),
    # Basophils
    (r"(?i)Базофилы абс\.?\s*[/#].*", "Базофилы абс."),
    (r"(?i)Базофилы[/%].*", "Базофилы %"),
    # Lymphocytes
    (r"(?i)Лимфоциты абс\.?\s*[/#].*", "Лимфоциты абс."),
    (r"(?i)Лимфоциты[/%].*", "Лимфоциты %"),
    # Monocytes
    (r"(?i)Моноциты абс\.?\s*[/#].*", "Моноциты абс."),
    (r"(?i)Моноциты[/%].*", "Моноциты %"),
    # MCV
    (r"(?i)Средн\.?\s*(объем|конц\.).*эритроцит.*/(MCV|MCH|MCHC).*|Средний объем эритроцита/.*",
     None),  # handle below
    # Cholesterol
    (r"(?i)Холестерин\s*/\s*Cholesterol.*|Холестерин общий.*", "Холестерин"),
    # Triglycerides
    (r"(?i)Триглицериды\s*/\s*Triglyceride.*", "Триглицериды"),
    # Alkaline phosphatase
    (r"(?i)Щелочная фосфатаза\s*/\s*ALP.*", "ЩФ"),
    # Total protein
    (r"(?i)Общий белок\s*/\s*Total Protein.*", "Общий белок"),
    # Calcium
    (r"(?i)Общий кальций\s*/\s*Total calcium.*", "Кальций"),
    # Phosphate
    (r"(?i)Неорганический фосфат\s*/\s*Inorganic phosphate.*", "Фосфат"),
    # Free T4
    (r"(?i)Свободный Т4|Свободный T4", "Т4 свободный"),
    # FSH
    (r"(?i)Фолликулостимулирующий гормон.*|ФСГ.*", "ФСГ"),
    # Carotid arteries — keep as is but strip duplicates
]

# Specific MCV/MCH/MCHC mappings
SPECIFIC = {
    r"(?i)Средн\.?\s*объем эритроцитов?/(MCV).*|Средний объем эритроцита/MCV.*": "MCV",
    r"(?i)Средн\.?\s*конц\. гемоглобина.*/(MCHC).*": "MCHC",
    r"(?i)Средн\.?\s*содерж\. гемоглобина.*/(MCH).*": "MCH",
    r"(?i)Ширина распределения эритроцитов.*/(RDW).*": "RDW",
}


def canonical(name: str) -> str | None:
    for pattern, canon in SPECIFIC.items():
        if re.match(pattern, name):
            return canon
    for pattern, canon in NORMALIZATIONS:
        if canon is not None and re.match(pattern, name):
            return canon
    return None


async def main():
    engine = get_engine()
    async with engine.connect() as conn:
        # Fetch all distinct metric names
        result = await conn.execute(text("SELECT DISTINCT metric_name FROM test_results ORDER BY metric_name"))
        metrics = [row[0] for row in result.fetchall()]

    print(f"Total distinct metrics: {len(metrics)}")
    renames: dict[str, str] = {}
    for m in metrics:
        c = canonical(m)
        if c and c != m:
            renames[m] = c
            print(f"  RENAME: {m!r} → {c!r}")

    if not renames:
        print("Nothing to rename.")
        return

    confirm = input(f"\nRename {len(renames)} metric(s)? [y/N] ")
    if confirm.lower() != "y":
        print("Aborted.")
        return

    async with engine.begin() as conn:
        for old, new in renames.items():
            # Move all rows with old name to new name, keeping latest if conflict
            await conn.execute(
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
            # Delete remaining duplicates (same user/date already has the canonical)
            await conn.execute(
                text("DELETE FROM test_results WHERE metric_name = :old"),
                {"old": old}
            )
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
