import logging
from datetime import date

from aiogram import Router, F
from aiogram.types import Message

from bot.database.repository import Repository
from bot.services.ai_service import analyze_test_results, analyze_image, analyze_scanned_pdf_pages
from bot.services.pdf_service import extract_text_from_pdf, get_pdf_page_count, pdf_pages_to_images

logger = logging.getLogger(__name__)
router = Router()

MAX_PDF_SIZE_MB = 20
MAX_IMAGE_SIZE_MB = 10
MAX_PDF_PAGES = 50


def _mb(size_bytes: int) -> float:
    return size_bytes / 1024 / 1024


@router.message(F.document)
async def handle_document(message: Message) -> None:
    doc = message.document
    if not doc.file_name:
        await message.answer("Не удалось определить тип файла.")
        return

    ext = doc.file_name.lower().rsplit(".", 1)[-1] if "." in doc.file_name else ""

    if ext == "pdf":
        if doc.file_size and _mb(doc.file_size) > MAX_PDF_SIZE_MB:
            await message.answer(f"PDF слишком большой (макс. {MAX_PDF_SIZE_MB} МБ).")
            return
        await _handle_pdf(message)
    elif ext in ("jpg", "jpeg", "png", "bmp", "tiff"):
        if doc.file_size and _mb(doc.file_size) > MAX_IMAGE_SIZE_MB:
            await message.answer(f"Изображение слишком большое (макс. {MAX_IMAGE_SIZE_MB} МБ).")
            return
        await _handle_photo_file(message)
    else:
        await message.answer(
            "Поддерживаемые форматы: PDF, JPG, PNG.\n"
            "Отправь файл анализов в одном из этих форматов."
        )


@router.message(F.photo)
async def handle_photo(message: Message) -> None:
    photo = message.photo[-1]
    if photo.file_size and _mb(photo.file_size) > MAX_IMAGE_SIZE_MB:
        await message.answer(f"Фото слишком большое (макс. {MAX_IMAGE_SIZE_MB} МБ).")
        return

    await message.answer("📷 Фото получено, анализирую...")

    try:
        file = await message.bot.get_file(photo.file_id)
        data = await message.bot.download_file(file.file_path)
        image_bytes = data.read()

        profile = await Repository.get_user_profile(message.from_user.id)
        result = await analyze_image(image_bytes, profile)

        results_list = result.get("results", [])
        if results_list:
            db_results = []
            for r in results_list:
                try:
                    db_results.append({
                        "metric": r["metric"][:200],
                        "value": float(r["value"]),
                        "unit": r.get("unit", "")[:50] if r.get("unit") else None,
                        "ref_min": float(r["ref_min"]) if r.get("ref_min") is not None else None,
                        "ref_max": float(r["ref_max"]) if r.get("ref_max") is not None else None,
                        "date": _parse_date(r.get("date")),
                        "source": "photo",
                    })
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning("Skipping malformed result: %s", e)

            count = await Repository.save_test_results(message.from_user.id, db_results)
            summary = result.get("summary", "Анализ завершён.")[:2000]
            abnormal = [
                r for r in db_results
                if (r.get("ref_max") and r["value"] > r["ref_max"])
                or (r.get("ref_min") and r["value"] < r["ref_min"])
            ]
            abnormal_text = ""
            if abnormal:
                lines = "\n".join(
                    f"• {r['metric']}: {r['value']} {r.get('unit') or ''} "
                    f"(норма {r.get('ref_min','?')}–{r.get('ref_max','?')})"
                    for r in abnormal
                )
                abnormal_text = f"\n\n⚠️ <b>Вне нормы:</b>\n{lines}"
            await message.answer(f"✅ Сохранено <b>{count}</b> показателей.{abnormal_text}\n\n{summary}")
        else:
            await message.answer(
                "Не удалось распознать показатели на фото. "
                "Попробуй отправить более чёткое изображение или PDF."
            )

    except Exception as e:
        logger.error("Photo analysis failed: %s", type(e).__name__)
        await message.answer(
            "⚠️ Произошла ошибка при анализе фото. Повторите запрос через 5 минут."
        )


async def _handle_pdf(message: Message) -> None:
    doc = message.document
    file = await message.bot.get_file(doc.file_id)
    data = await message.bot.download_file(file.file_path)
    pdf_bytes = data.read()

    page_count = get_pdf_page_count(pdf_bytes)
    if page_count > MAX_PDF_PAGES:
        await message.answer(
            f"PDF содержит {page_count} страниц. Максимум — {MAX_PDF_PAGES}. "
            f"Отправь только нужные страницы с анализами."
        )
        return

    if page_count > 1:
        await message.answer(
            f"📄 PDF получен ({page_count} стр.), анализирую... Это займёт около минуты."
        )
    else:
        await message.answer("📄 PDF получен, анализирую...")

    try:
        text = extract_text_from_pdf(pdf_bytes)

        if len(text.strip()) < 20:
            pages = pdf_pages_to_images(pdf_bytes)
            await message.answer(
                f"Документ выглядит как скан ({len(pages)} стр.), "
                f"использую распознавание изображений..."
            )
            profile = await Repository.get_user_profile(message.from_user.id)
            result = await analyze_scanned_pdf_pages(pages, profile)
        else:
            # Truncate to avoid token limits (~30k chars ≈ ~8k tokens)
            text = text[:30_000]
            profile = await Repository.get_user_profile(message.from_user.id)
            result = await analyze_test_results(text, profile)

        results_list = result.get("results", [])
        if results_list:
            db_results = []
            for r in results_list:
                try:
                    db_results.append({
                        "metric": r["metric"][:200],
                        "value": float(r["value"]),
                        "unit": r.get("unit", "")[:50] if r.get("unit") else None,
                        "ref_min": float(r["ref_min"]) if r.get("ref_min") is not None else None,
                        "ref_max": float(r["ref_max"]) if r.get("ref_max") is not None else None,
                        "date": _parse_date(r.get("date")),
                        "source": doc.file_name[:200],
                    })
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning("Skipping malformed result: %s", e)

            count = await Repository.save_test_results(message.from_user.id, db_results)
            summary = result.get("summary", "Анализ завершён.")[:2000]

            # Highlight out-of-range values
            abnormal = [
                r for r in db_results
                if r.get("ref_max") and r["value"] > r["ref_max"]
                or r.get("ref_min") and r["value"] < r["ref_min"]
            ]
            abnormal_text = ""
            if abnormal:
                lines = "\n".join(
                    f"• {r['metric']}: {r['value']} {r.get('unit') or ''} "
                    f"(норма {r.get('ref_min','?')}–{r.get('ref_max','?')})"
                    for r in abnormal
                )
                abnormal_text = f"\n\n⚠️ <b>Вне нормы:</b>\n{lines}"

            await message.answer(
                f"✅ Сохранено <b>{count}</b> показателей из «{doc.file_name}».{abnormal_text}\n\n{summary}"
            )
        else:
            await message.answer(
                f"Не удалось извлечь показатели из «{doc.file_name}».\n"
                f"Попробуй отправить скриншоты страниц как фото."
            )

    except Exception as e:
        logger.error("PDF analysis failed: %s", type(e).__name__)
        await message.answer(
            "⚠️ Произошла ошибка при анализе PDF. Повторите запрос через 5 минут."
        )


async def _handle_photo_file(message: Message) -> None:
    doc = message.document
    file = await message.bot.get_file(doc.file_id)
    data = await message.bot.download_file(file.file_path)
    image_bytes = data.read()

    await message.answer("📷 Изображение получено, анализирую...")

    try:
        profile = await Repository.get_user_profile(message.from_user.id)
        result = await analyze_image(image_bytes, profile)

        results_list = result.get("results", [])
        if results_list:
            db_results = []
            for r in results_list:
                try:
                    db_results.append({
                        "metric": r["metric"][:200],
                        "value": float(r["value"]),
                        "unit": r.get("unit", "")[:50] if r.get("unit") else None,
                        "ref_min": float(r["ref_min"]) if r.get("ref_min") is not None else None,
                        "ref_max": float(r["ref_max"]) if r.get("ref_max") is not None else None,
                        "date": _parse_date(r.get("date")),
                        "source": doc.file_name[:200],
                    })
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning("Skipping malformed result: %s", e)

            count = await Repository.save_test_results(message.from_user.id, db_results)
            summary = result.get("summary", "Анализ завершён.")[:2000]
            await message.answer(f"✅ Сохранено <b>{count}</b> показателей.\n\n{summary}")
        else:
            await message.answer("Не удалось распознать показатели.")

    except Exception as e:
        logger.error("Image analysis failed: %s", type(e).__name__)
        await message.answer(
            "⚠️ Произошла ошибка при анализе изображения. Повторите запрос через 5 минут."
        )


def _parse_date(date_str: str | None) -> date:
    if not date_str:
        return date.today()
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return date.today()
