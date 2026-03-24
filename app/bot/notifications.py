import json
import logging
from telegram import Bot
from sqlalchemy import select
from app.bot.keyboards import (
    ITEM_LABELS, TIME_LABELS, STATUS_LABELS, METHOD_LABELS, AREA_LABELS,
    reservation_action_keyboard,
)

logger = logging.getLogger(__name__)


async def get_employees_by_role(role: str = None):
    from app.database import async_session
    from app.models.employee import Employee

    async with async_session() as db:
        query = select(Employee)
        if role:
            query = query.where(Employee.role == role)
        result = await db.execute(query)
        return list(result.scalars().all())


def build_reservation_card(reservation, items_data=None, status_history=None) -> str:
    """예약 카드 메시지 생성 (하나의 메시지로 계속 업데이트)"""
    import json as _json

    # 품목 정보
    if items_data:
        items = items_data
    elif reservation.items_json:
        try:
            items = _json.loads(reservation.items_json)
        except Exception:
            items = []
    else:
        items = [{"item_type": reservation.item_type, "quantity": reservation.quantity}]

    items_text = ""
    for item in items:
        label = ITEM_LABELS.get(item.get("item_type", ""), item.get("item_type", ""))
        subtype = item.get("item_subtype", "")
        subtype_str = f" {subtype}" if subtype else ""
        method = item.get("cleaning_method")
        method_str = f" {METHOD_LABELS.get(method, '')}" if method else ""
        qty = item.get("quantity", 1)
        price = item.get("price", 0)
        if price:
            items_text += f"  • {label}{subtype_str}{method_str} x{qty} — {price:,}원\n"
        else:
            items_text += f"  • {label}{subtype_str}{method_str} x{qty}\n"

    # 상태 진행 바
    status = reservation.status if hasattr(reservation, 'status') else "pending"
    stages = [
        ("pending", "대기"),
        ("confirmed", "확정"),
        ("picking_up", "수거중"),
        ("picked_up", "수거완료"),
        ("cleaning", "세척중"),
        ("cleaned", "세척완료"),
        ("delivering", "배송중"),
        ("delivered", "배송완료"),
        ("settled", "정산완료"),
    ]

    status_emoji = {
        "pending": "⏳", "confirmed": "✅", "picking_up": "🚗",
        "picked_up": "📦", "cleaning": "🧹", "cleaned": "✨",
        "delivering": "🚚", "delivered": "🏠", "settled": "💰",
        "cancelled": "❌",
    }

    # 진행 상태 바 생성
    current_idx = next((i for i, (s, _) in enumerate(stages) if s == status), -1)
    if status == "cancelled":
        progress = "❌ 취소됨"
    else:
        progress_parts = []
        for i, (s, label) in enumerate(stages):
            if i <= current_idx:
                progress_parts.append(f"{status_emoji[s]}{label}")
            else:
                break
        progress = " → ".join(progress_parts)

    customer_name = reservation.customer.name if hasattr(reservation, 'customer') and reservation.customer else "?"
    customer_phone = reservation.customer.phone if hasattr(reservation, 'customer') and reservation.customer else ""
    notes = reservation.special_notes or ""
    area = AREA_LABELS.get(reservation.area or "", "")
    sched = ""
    if hasattr(reservation, 'scheduled_date') and reservation.scheduled_date:
        sched = f"{reservation.scheduled_date.strftime('%Y.%m.%d')} {TIME_LABELS.get(reservation.scheduled_time or '', '')}"

    text = (
        f"━━━━━━━━━━━━━━\n"
        f"📋 {reservation.reservation_no}\n"
        f"━━━━━━━━━━━━━━\n"
        f"고객: {customer_name}"
    )
    if customer_phone:
        text += f" ({customer_phone})"
    text += f"\n"

    if area:
        text += f"지역: {area}\n"
    if reservation.pickup_address:
        text += f"주소: {reservation.pickup_address}\n"

    text += f"\n{items_text}\n"

    if sched:
        text += f"일시: {sched}\n"
    if notes:
        text += f"메모: {notes}\n"

    text += (
        f"금액: {reservation.price:,}원\n"
        f"\n{progress}\n"
        f"━━━━━━━━━━━━━━"
    )
    return text


async def save_notify_message(reservation_no: str, chat_id: int, message_id: int):
    """알림 메시지 ID를 DB에 저장"""
    from app.database import async_session
    from app.services.reservation_service import get_reservation

    async with async_session() as db:
        r = await get_reservation(db, reservation_no)
        if not r:
            return

        try:
            msgs = json.loads(r.notify_messages) if r.notify_messages else {}
        except Exception:
            msgs = {}

        msgs[str(chat_id)] = message_id
        r.notify_messages = json.dumps(msgs)
        await db.commit()


async def get_notify_messages(reservation_no: str) -> dict:
    """저장된 알림 메시지 ID 조회"""
    from app.database import async_session
    from app.services.reservation_service import get_reservation

    async with async_session() as db:
        r = await get_reservation(db, reservation_no)
        if not r or not r.notify_messages:
            return {}
        try:
            return json.loads(r.notify_messages)
        except Exception:
            return {}


async def send_or_update_card(bot: Bot, reservation, target_role: str = None, items_data=None):
    """예약 카드를 전송하거나, 기존 메시지가 있으면 수정"""
    text = build_reservation_card(reservation, items_data=items_data)
    kb = reservation_action_keyboard(reservation.reservation_no, reservation.status)
    if reservation.status in ("settled", "cancelled"):
        kb = None

    saved_msgs = await get_notify_messages(reservation.reservation_no)

    if target_role:
        employees = await get_employees_by_role(target_role)
    else:
        employees = await get_employees_by_role()

    for emp in employees:
        chat_id = emp.telegram_user_id
        existing_msg_id = saved_msgs.get(str(chat_id))

        try:
            if existing_msg_id:
                # 기존 메시지 수정
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=existing_msg_id,
                    text=text,
                    reply_markup=kb,
                )
            else:
                # 새 메시지 전송
                sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
                await save_notify_message(reservation.reservation_no, chat_id, sent.message_id)
        except Exception as e:
            # 수정 실패하면 새 메시지 전송
            try:
                sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
                await save_notify_message(reservation.reservation_no, chat_id, sent.message_id)
            except Exception:
                logger.error(f"Failed to notify {chat_id}: {e}")


async def notify_group_new_reservation(bot: Bot, reservation, data: dict):
    """새 예약 → 직원에게 카드 전송"""
    items = data.get("items", [])

    # 직원에게 카드 전송
    await send_or_update_card(bot, reservation, target_role="staff", items_data=items)


async def notify_group_status_change(bot: Bot, reservation, new_status: str, employee_name: str = "", sender_role: str = ""):
    """상태 변경 → 양쪽 모두 카드 업데이트"""
    # 모든 사용자의 카드를 업데이트
    await send_or_update_card(bot, reservation)


async def send_daily_schedule(bot: Bot):
    """매일 아침 오늘의 일정 → 사장+직원 모두에게 발송"""
    from app.database import async_session
    from app.services.reservation_service import get_today_reservations
    from datetime import date

    async with async_session() as db:
        reservations = await get_today_reservations(db)

    today = date.today().strftime("%Y.%m.%d")

    if not reservations:
        text = (
            f"━━━━━━━━━━━━━━\n"
            f"📅 [오늘의 일정] {today}\n"
            f"━━━━━━━━━━━━━━\n"
            f"오늘 예약이 없습니다.\n"
            f"━━━━━━━━━━━━━━"
        )
    else:
        text = (
            f"━━━━━━━━━━━━━━\n"
            f"📅 [오늘의 일정] {today}\n"
            f"━━━━━━━━━━━━━━\n"
        )
        for idx, r in enumerate(reservations, 1):
            items_text = ""
            if r.items_json:
                try:
                    items = json.loads(r.items_json)
                    items_text = ", ".join(
                        f"{ITEM_LABELS.get(i['item_type'], i['item_type'])} x{i.get('quantity', 1)}"
                        for i in items
                    )
                except Exception:
                    items_text = ITEM_LABELS.get(r.item_type, r.item_type)
            else:
                items_text = f"{ITEM_LABELS.get(r.item_type, r.item_type)} x{r.quantity}"

            time_label = TIME_LABELS.get(r.scheduled_time, "")
            status = STATUS_LABELS.get(r.status, r.status)
            text += f"{idx}. {time_label} {r.customer.name} - {items_text} [{status}]\n"

        text += "━━━━━━━━━━━━━━"

    all_employees = await get_employees_by_role()
    for emp in all_employees:
        try:
            await bot.send_message(chat_id=emp.telegram_user_id, text=text)
        except Exception:
            pass
