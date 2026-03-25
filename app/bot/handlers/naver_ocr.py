import base64
import logging
import re
from datetime import datetime, date

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select

from app.config import GOOGLE_VISION_API_KEY
from app.database import async_session
from app.models.employee import Employee
from app.services.reservation_service import create_reservation
from app.bot.keyboards import (
    ITEM_LABELS, TIME_LABELS, PAYMENT_LABELS, AREA_LABELS,
)
from app.bot.notifications import notify_group_new_reservation

logger = logging.getLogger(__name__)

# 네이버 상품명 → 봇 item_type 매핑
NAVER_ITEM_MAP = {
    "카시트": "carseat",
    "유모차": "stroller",
    "쌍둥이유모차": "stroller",
    "웨건": "wagon",
    "매트리스": "mattress",
    "소파": "sofa",
    "아기띠": "carrier",
}


async def ocr_google_vision(image_bytes: bytes) -> str | None:
    """Google Cloud Vision API로 이미지에서 텍스트 추출 (무료 티어: 월 1,000건)"""
    if not GOOGLE_VISION_API_KEY:
        logger.error("GOOGLE_VISION_API_KEY not set")
        return None

    b64 = base64.b64encode(image_bytes).decode("utf-8")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}",
            json={
                "requests": [{
                    "image": {"content": b64},
                    "features": [{"type": "TEXT_DETECTION"}],
                }]
            },
        )

    if resp.status_code != 200:
        logger.error(f"Google Vision API error: {resp.status_code} {resp.text}")
        return None

    result = resp.json()
    annotations = result.get("responses", [{}])[0].get("textAnnotations", [])
    if not annotations:
        logger.error("No text detected in image")
        return None

    return annotations[0].get("description", "")


def parse_naver_text(text: str) -> dict:
    """OCR 텍스트에서 네이버 예약 정보를 파싱"""
    extracted = {}

    m = re.search(r'예약자\s+(.+)', text)
    if m:
        extracted["customer_name"] = m.group(1).strip()

    m = re.search(r'전화번호\s+([\d\-]+)', text)
    if m:
        extracted["phone"] = m.group(1).strip()

    m = re.search(r'예약번호\s+(\d+)', text)
    if m:
        extracted["reservation_number"] = m.group(1).strip()

    m = re.search(r'이메일\s+([\w.\-]+@[\w.\-]+)', text)
    if m:
        extracted["email"] = m.group(1).strip()

    m = re.search(r'상품\s+(.+)', text)
    if m:
        extracted["product"] = m.group(1).strip()

    # 이용일시 파싱 - OCR 오차를 고려해 여러 패턴 시도
    date_patterns = [
        # 기본: 이용일시 2026. 3. 25. (화) 오전 10:00
        r'이용일시\s+(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*\([월화수목금토일]\)\s*(오전|오후)\s*(\d{1,2}):(\d{2})',
        # 요일 누락 또는 OCR 미인식
        r'이용일시\s+(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?\s*(?:\([^)]*\))?\s*(오전|오후)\s*(\d{1,2}):(\d{2})',
        # 점 대신 다른 구분자 (/, -)
        r'이용일시\s+(\d{4})[./\-]\s*(\d{1,2})[./\-]\s*(\d{1,2})\.?\s*(?:\([^)]*\))?\s*(오전|오후)\s*(\d{1,2}):(\d{2})',
        # 이용일시가 줄바꿈 후에 날짜
        r'이용일시\s*\n\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?\s*(?:\([^)]*\))?\s*(오전|오후)\s*(\d{1,2}):(\d{2})',
        # 오전/오후 없이 24시간 표기
        r'이용일시\s+(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?\s*(?:\([^)]*\))?\s*(\d{1,2}):(\d{2})',
    ]
    for i, pat in enumerate(date_patterns):
        m = re.search(pat, text)
        if m:
            groups = m.groups()
            year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
            if len(groups) == 6:
                # 오전/오후 포함 패턴
                ampm, hour, minute = groups[3], int(groups[4]), int(groups[5])
                if ampm == "오후" and hour != 12:
                    hour += 12
                elif ampm == "오전" and hour == 12:
                    hour = 0
            else:
                # 24시간 표기 (오전/오후 없음)
                hour, minute = int(groups[3]), int(groups[4])
            extracted["date"] = f"{year}-{month:02d}-{day:02d}"
            extracted["time"] = f"{hour:02d}:{minute:02d}"
            break

    m = re.search(r'인원\s+(\d+)', text)
    if m:
        extracted["people"] = m.group(1).strip()

    # 옵션 (실제 주문 품목) - 여러 줄일 수 있음
    m = re.search(r'옵션\s+([\s\S]+?)(?=요청사항|쿠폰|유입경로)', text)
    if m:
        extracted["option"] = m.group(1).strip()

    # 요청사항
    m = re.search(r'요청사항\s+([\s\S]+?)(?=쿠폰|유입경로)', text)
    if m:
        request_text = m.group(1).strip()
        extracted["request"] = request_text
        phone_m = re.search(r'(\d{3}[-\s]?\d{3,4}[-\s]?\d{4})', request_text)
        if phone_m:
            extracted["alt_phone"] = phone_m.group(1).replace(" ", "")

    m = re.search(r'쿠폰\s+(.+?)(?:\n|$)', text)
    if m:
        coupon_text = m.group(1).strip()
        if coupon_text and "없" not in coupon_text:
            extracted["coupon"] = coupon_text

    m = re.search(r'예약자입력정보.*?\n.*?\n([\s\S]+?)(?=노쇼|예약취소|이용완료|$)', text)
    if m:
        addr = m.group(1).strip()
        if addr and len(addr) > 3:
            extracted["address"] = addr

    # 옵션에서 실제 주문 품목 추출 (핵심!)
    # Google Vision OCR이 옵션/요청사항 텍스트를 섞을 수 있으므로
    # 전체 OCR 텍스트에서 "X 프리미엄 케어 N" 패턴으로 검색
    option_items = []
    found_types = set()
    for keyword, item_type in NAVER_ITEM_MAP.items():
        pattern = rf'{keyword}\s*프리미엄\s*케어\s*(\d+)'
        matches = re.findall(pattern, text)
        for qty_str in matches:
            if keyword not in found_types:
                qty = int(qty_str) if qty_str else 1
                option_items.append({"name": keyword, "type": item_type, "qty": qty})
                found_types.add(keyword)

    # "프리미엄 케어" 패턴 못 찾으면 옵션 텍스트에서 키워드 검색
    if not option_items:
        option_text = extracted.get("option", "")
        for keyword, item_type in NAVER_ITEM_MAP.items():
            if keyword in option_text and keyword not in found_types:
                option_items.append({"name": keyword, "type": item_type, "qty": 1})
                found_types.add(keyword)

    # 그래도 없으면 상품명에서 추출
    if not option_items:
        product = extracted.get("product", "")
        for keyword in NAVER_ITEM_MAP:
            if keyword in product:
                option_items.append({"name": keyword, "type": NAVER_ITEM_MAP[keyword], "qty": 1})

    extracted["items"] = option_items if option_items else [{"name": extracted.get("product", "알 수 없음"), "type": "unknown", "qty": 1}]

    return extracted


def map_items(extracted: dict) -> list[dict]:
    """추출된 옵션 품목을 봇의 품목 형식으로 변환"""
    items = []
    for item_info in extracted.get("items", []):
        if isinstance(item_info, dict):
            items.append({
                "item_type": item_info.get("type", "unknown"),
                "quantity": item_info.get("qty", 1),
                "naver_name": item_info.get("name", "알 수 없음"),
            })
        else:
            matched_type = None
            for keyword, item_type in NAVER_ITEM_MAP.items():
                if keyword in str(item_info):
                    matched_type = item_type
                    break
            items.append({
                "item_type": matched_type or "unknown",
                "quantity": 1,
                "naver_name": str(item_info),
            })

    if not items:
        items.append({
            "item_type": "unknown",
            "quantity": 1,
            "naver_name": extracted.get("product", "알 수 없음"),
        })
    return items


def parse_time_slot(time_str: str) -> str:
    try:
        hour = int(time_str.split(":")[0])
        return "morning" if hour < 12 else "afternoon"
    except (ValueError, IndexError):
        return "afternoon"


def build_naver_confirm_text(extracted: dict, items: list[dict]) -> str:
    items_text = ""
    for i, item in enumerate(items, 1):
        label = item.get("naver_name") or ITEM_LABELS.get(item["item_type"], "알 수 없음")
        items_text += f"  {i}. {label} x{item.get('quantity', 1)}\n"

    coupon = extracted.get("coupon", "")
    coupon_text = f"쿠폰: {coupon}\n" if coupon else ""
    address = extracted.get("address", "")
    address_text = f"주소: {address}\n" if address else ""
    request = extracted.get("request", "")
    request_text = f"요청사항: {request}\n" if request else ""
    alt_phone = extracted.get("alt_phone", "")
    alt_phone_text = f"별도 연락처: {alt_phone}\n" if alt_phone else ""
    user_note = extracted.get("user_note", "")
    user_note_text = f"📝 특이사항: {user_note}\n" if user_note else ""

    return (
        "━━━━━━━━━━━━━━\n"
        "📋 네이버 예약 자동 등록\n"
        "━━━━━━━━━━━━━━\n"
        f"예약자: {extracted.get('customer_name', '-')}\n"
        f"연락처: {extracted.get('phone', '-')}\n"
        f"{alt_phone_text}"
        f"네이버 예약번호: {extracted.get('reservation_number', '-')}\n"
        f"{address_text}"
        f"━━━━━━━━━━━━━━\n"
        f"주문 품목:\n"
        f"{items_text}"
        f"━━━━━━━━━━━━━━\n"
        f"일시: {extracted.get('date', '-')} {extracted.get('time', '-')}\n"
        f"결제: 네이버예약\n"
        f"{coupon_text}"
        f"{request_text}"
        f"{user_note_text}"
        "━━━━━━━━━━━━━━\n"
        "\n이 정보로 예약을 등록할까요?"
    )


def naver_confirm_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 등록", callback_data="naver:yes")],
        [InlineKeyboardButton("📝 특이사항 입력", callback_data="naver:note")],
        [InlineKeyboardButton("❌ 취소", callback_data="naver:cancel")],
    ])


async def naver_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """네이버 예약 캡쳐 사진 수신 → Google Vision OCR → 확인"""
    user_id = update.effective_user.id
    async with async_session() as db:
        result = await db.execute(select(Employee).where(Employee.telegram_user_id == user_id))
        employee = result.scalar_one_or_none()

    if not employee or employee.role != "boss":
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()

    await update.message.reply_text("🔍 네이버 예약 정보를 분석하고 있습니다...")

    ocr_text = await ocr_google_vision(bytes(image_bytes))
    if not ocr_text:
        await update.message.reply_text("이미지에서 텍스트를 인식하지 못했습니다. 다시 시도해주세요.")
        return

    logger.info(f"OCR result:\n{ocr_text}")

    extracted = parse_naver_text(ocr_text)
    if not extracted.get("date"):
        logger.warning(f"날짜 파싱 실패 - OCR 텍스트에서 이용일시를 찾지 못함")

    # 네이버 예약 화면 확인: 핵심 필드 중 하나라도 있으면 통과
    has_info = (
        extracted.get("phone")
        or extracted.get("customer_name")
        or extracted.get("product")
        or extracted.get("option")
        or extracted.get("date")
    )
    if not has_info:
        await update.message.reply_text(
            "네이버 예약 화면이 아니거나 정보를 인식하지 못했습니다.\n"
            "네이버 예약 상세 화면을 캡쳐해서 보내주세요."
        )
        return

    items = map_items(extracted)
    text = build_naver_confirm_text(extracted, items)
    await update.message.reply_text(text, reply_markup=naver_confirm_keyboard())

    context.user_data["naver_reservation"] = {
        "extracted": extracted,
        "items": items,
    }


async def naver_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """특이사항 텍스트 입력 수신"""
    if not context.user_data.get("naver_waiting_note"):
        return  # group=2에서만 동작, 다른 핸들러에 영향 없음

    naver_data = context.user_data.get("naver_reservation")
    if not naver_data:
        context.user_data.pop("naver_waiting_note", None)
        return

    note_text = update.message.text.strip()
    naver_data["extracted"]["user_note"] = note_text
    context.user_data.pop("naver_waiting_note", None)

    items = map_items(naver_data["extracted"])
    naver_data["items"] = items
    text = build_naver_confirm_text(naver_data["extracted"], items)
    await update.message.reply_text(text, reply_markup=naver_confirm_keyboard())


async def naver_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """네이버 예약 확인/취소 콜백"""
    query = update.callback_query
    await query.answer()

    action = query.data.split(":")[1]
    naver_data = context.user_data.get("naver_reservation")

    if action == "cancel" or not naver_data:
        context.user_data.pop("naver_reservation", None)
        await query.edit_message_text("네이버 예약 등록이 취소되었습니다.")
        return

    if action == "note":
        context.user_data["naver_waiting_note"] = True
        await query.edit_message_text(
            query.message.text + "\n\n✏️ 특이사항을 입력해주세요.\n"
            "(누락된 정보나 추가 메모를 자유롭게 입력)"
        )
        return

    extracted = naver_data["extracted"]
    items = naver_data["items"]

    try:
        sched_date = datetime.strptime(extracted["date"], "%Y-%m-%d").date()
    except (KeyError, ValueError):
        sched_date = date.today()

    time_slot = parse_time_slot(extracted.get("time", "14:00"))

    from app.services.reservation_service import get_price
    total_price = 0
    for item in items:
        if item["item_type"] != "unknown":
            async with async_session() as db:
                price = await get_price(db, item["item_type"], item.get("item_subtype"))
            item["price"] = price * item.get("quantity", 1)
            item["unit_price"] = price
            total_price += item["price"]

    notes_parts = []
    if extracted.get("reservation_number"):
        notes_parts.append(f"네이버예약#{extracted['reservation_number']}")
    if extracted.get("request"):
        notes_parts.append(extracted["request"])
    if extracted.get("coupon"):
        notes_parts.append(f"쿠폰: {extracted['coupon']}")
    if extracted.get("customer_name"):
        notes_parts.append(f"예약자: {extracted['customer_name']}")
    if extracted.get("alt_phone"):
        notes_parts.append(f"별도연락처: {extracted['alt_phone']}")
    if extracted.get("user_note"):
        notes_parts.append(f"특이사항: {extracted['user_note']}")
    special_notes = " | ".join(notes_parts) if notes_parts else None

    address = extracted.get("address", "")
    area = "daejeon"
    if "세종" in address:
        area = "sejong"
    elif "논산" in address:
        area = "nonsan"

    phone = extracted.get("alt_phone") or extracted.get("phone", "010-0000-0000")

    reservation_data = {
        "name": address or extracted.get("customer_name", "네이버예약"),
        "phone": phone.replace("-", "").replace(" ", ""),
        "area": area,
        "address": address,
        "items": items,
        "scheduled_date": sched_date,
        "scheduled_time": time_slot,
        "payment_method": "naver",
        "special_notes": special_notes,
        "price": total_price,
    }

    phone = reservation_data["phone"]
    if len(phone) == 11:
        reservation_data["phone"] = f"{phone[:3]}-{phone[3:7]}-{phone[7:]}"

    async with async_session() as db:
        reservation = await create_reservation(db, reservation_data)

    items_text = ", ".join(
        f"{i.get('naver_name') or ITEM_LABELS.get(i['item_type'], '?')} x{i.get('quantity', 1)}"
        for i in items
    )

    await query.edit_message_text(
        f"✅ 네이버 예약 등록 완료!\n\n"
        f"예약번호: {reservation.reservation_no}\n"
        f"예약자: {extracted.get('customer_name', '-')}\n"
        f"연락처: {reservation_data['phone']}\n"
        f"품목: {items_text}\n"
        f"일시: {sched_date.strftime('%Y.%m.%d')} {TIME_LABELS[time_slot]}\n"
        f"결제: 네이버예약\n"
        f"합계: {total_price:,}원"
    )

    await notify_group_new_reservation(context.bot, reservation, reservation_data)
    context.user_data.pop("naver_reservation", None)
