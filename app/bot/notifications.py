from telegram import Bot
from sqlalchemy import select
from app.bot.keyboards import (
    ITEM_LABELS, TIME_LABELS, STATUS_LABELS, METHOD_LABELS, AREA_LABELS,
    reservation_action_keyboard,
)


async def get_employees_by_role(role: str = None):
    """역할별 직원 목록 조회. role=None이면 전체"""
    from app.database import async_session
    from app.models.employee import Employee

    async with async_session() as db:
        query = select(Employee)
        if role:
            query = query.where(Employee.role == role)
        result = await db.execute(query)
        return list(result.scalars().all())


async def notify_staff(bot: Bot, text: str, reply_markup=None):
    """직원에게 DM 발송"""
    staff_list = await get_employees_by_role("staff")
    for emp in staff_list:
        try:
            await bot.send_message(chat_id=emp.telegram_user_id, text=text, reply_markup=reply_markup)
        except Exception:
            pass


async def notify_boss(bot: Bot, text: str, reply_markup=None):
    """사장에게 DM 발송"""
    boss_list = await get_employees_by_role("boss")
    for emp in boss_list:
        try:
            await bot.send_message(chat_id=emp.telegram_user_id, text=text, reply_markup=reply_markup)
        except Exception:
            pass


async def notify_all(bot: Bot, text: str, reply_markup=None):
    """사장+직원 모두에게 DM 발송"""
    all_employees = await get_employees_by_role()
    for emp in all_employees:
        try:
            await bot.send_message(chat_id=emp.telegram_user_id, text=text, reply_markup=reply_markup)
        except Exception:
            pass


async def notify_other_role(bot: Bot, sender_role: str, text: str, reply_markup=None):
    """발신자 반대 역할에게 알림 (사장→직원, 직원→사장)"""
    target_role = "staff" if sender_role == "boss" else "boss"
    employees = await get_employees_by_role(target_role)
    for emp in employees:
        try:
            await bot.send_message(chat_id=emp.telegram_user_id, text=text, reply_markup=reply_markup)
        except Exception:
            pass


async def notify_group_new_reservation(bot: Bot, reservation, data: dict):
    """새 예약 → 직원에게 알림 (액션 버튼 포함)"""
    items = data.get("items", [])
    area = AREA_LABELS.get(data.get("area", ""), "")
    notes = data.get("special_notes") or "없음"
    price = data.get("price", 0)

    text = (
        f"━━━━━━━━━━━━━━\n"
        f"📋 [새 예약] {reservation.reservation_no}\n"
        f"━━━━━━━━━━━━━━\n"
        f"고객: {data['name']}\n"
        f"연락처: {data['phone']}\n"
        f"지역: {area}\n"
        f"주소: {data.get('address', '-')}\n"
    )
    for item in items:
        label = ITEM_LABELS.get(item["item_type"], item["item_type"])
        subtype = item.get("item_subtype", "")
        subtype_str = f" {subtype}" if subtype else ""
        method = item.get("cleaning_method")
        method_str = f" {METHOD_LABELS.get(method, '')}" if method else ""
        qty = item.get("quantity", 1)
        iprice = item.get("price", 0)
        text += f"  • {label}{subtype_str}{method_str} x{qty} — {iprice:,}원\n"

    text += (
        f"일시: {data['scheduled_date'].strftime('%Y.%m.%d')} {TIME_LABELS[data['scheduled_time']]}\n"
        f"특이사항: {notes}\n"
        f"합계: {price:,}원\n"
        f"━━━━━━━━━━━━━━"
    )
    # 직원에게 액션 버튼과 함께 전송
    await notify_staff(
        bot, text,
        reply_markup=reservation_action_keyboard(reservation.reservation_no, reservation.status),
    )


async def notify_group_status_change(bot: Bot, reservation, new_status: str, employee_name: str = "", sender_role: str = ""):
    """상태 변경 → 상대방에게 알림 (액션 버튼 포함)"""
    item = ITEM_LABELS.get(reservation.item_type, reservation.item_type)
    status_label = STATUS_LABELS.get(new_status, new_status)

    from datetime import datetime
    now = datetime.now().strftime("%H:%M")

    # 상태별 이모지
    status_emoji = {
        "confirmed": "✅",
        "picking_up": "🚗",
        "picked_up": "📦",
        "cleaning": "🧹",
        "cleaned": "✨",
        "delivering": "🚚",
        "delivered": "🏠",
        "settled": "💰",
        "cancelled": "❌",
    }
    emoji = status_emoji.get(new_status, "🔄")

    text = (
        f"━━━━━━━━━━━━━━\n"
        f"{emoji} [{status_label}] {reservation.reservation_no}\n"
        f"━━━━━━━━━━━━━━\n"
        f"고객: {reservation.customer.name} | {item} x{reservation.quantity}\n"
        f"처리: {employee_name}\n"
        f"시간: {now}\n"
        f"━━━━━━━━━━━━━━"
    )

    # 다음 액션 버튼 포함
    next_action_kb = None
    if new_status not in ("settled", "cancelled"):
        next_action_kb = reservation_action_keyboard(reservation.reservation_no, new_status)

    # 상대방에게 알림 전송
    if sender_role:
        await notify_other_role(bot, sender_role, text, reply_markup=next_action_kb)
    else:
        # sender_role 모르면 모두에게
        await notify_all(bot, text, reply_markup=next_action_kb)


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
        cleaning_count = 0
        delivery_count = 0

        idx = 1
        for r in reservations:
            item = ITEM_LABELS.get(r.item_type, r.item_type)
            time_label = TIME_LABELS.get(r.scheduled_time, "")
            status = STATUS_LABELS.get(r.status, r.status)
            text += f"{idx}. {time_label} {r.customer.name} - {item} x{r.quantity} [{status}]\n"
            idx += 1

            if r.status in ("picked_up", "cleaning"):
                cleaning_count += 1
            if r.status in ("cleaned", "delivering"):
                delivery_count += 1

        if cleaning_count:
            text += f"\n세척 대기: {cleaning_count}건"
        if delivery_count:
            text += f"\n배송 대기: {delivery_count}건"

        text += "\n━━━━━━━━━━━━━━"

    await notify_all(bot, text)
