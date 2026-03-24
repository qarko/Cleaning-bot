from telegram import Bot
from sqlalchemy import select
from app.bot.keyboards import ITEM_LABELS, TIME_LABELS, STATUS_LABELS, METHOD_LABELS, AREA_LABELS


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


async def notify_staff(bot: Bot, text: str):
    """직원에게 DM 발송"""
    staff_list = await get_employees_by_role("staff")
    for emp in staff_list:
        try:
            await bot.send_message(chat_id=emp.telegram_user_id, text=text)
        except Exception:
            pass


async def notify_boss(bot: Bot, text: str):
    """사장에게 DM 발송"""
    boss_list = await get_employees_by_role("boss")
    for emp in boss_list:
        try:
            await bot.send_message(chat_id=emp.telegram_user_id, text=text)
        except Exception:
            pass


async def notify_all(bot: Bot, text: str):
    """사장+직원 모두에게 DM 발송"""
    all_employees = await get_employees_by_role()
    for emp in all_employees:
        try:
            await bot.send_message(chat_id=emp.telegram_user_id, text=text)
        except Exception:
            pass


async def notify_group_new_reservation(bot: Bot, reservation, data: dict):
    """새 예약 → 직원에게 알림"""
    item = ITEM_LABELS.get(data["item_type"], data["item_type"])
    subtype = data.get("item_subtype", "")
    subtype_str = f" {subtype}" if subtype else ""
    method = data.get("cleaning_method")
    method_str = f" {METHOD_LABELS.get(method, '')}" if method else ""
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
        f"품목: {item}{subtype_str}{method_str} x {data.get('quantity', 1)}\n"
        f"일시: {data['scheduled_date'].strftime('%Y.%m.%d')} {TIME_LABELS[data['scheduled_time']]}\n"
        f"특이사항: {notes}\n"
        f"금액: {price:,}원\n"
        f"━━━━━━━━━━━━━━"
    )
    # 사장이 등록 → 직원에게 알림
    await notify_staff(bot, text)


async def notify_group_status_change(bot: Bot, reservation, new_status: str, employee_name: str = ""):
    """상태 변경 → 상대방에게 알림 (직원→사장, 사장→직원)"""
    item = ITEM_LABELS.get(reservation.item_type, reservation.item_type)
    status_label = STATUS_LABELS.get(new_status, new_status)

    from datetime import datetime
    now = datetime.now().strftime("%H:%M")

    text = (
        f"━━━━━━━━━━━━━━\n"
        f"🔄 [{status_label}] {reservation.reservation_no}\n"
        f"━━━━━━━━━━━━━━\n"
        f"고객: {reservation.customer.name} | {item} x{reservation.quantity}\n"
        f"처리: {employee_name}\n"
        f"시간: {now}\n"
        f"━━━━━━━━━━━━━━"
    )

    # 업무 완료 단계(수거/세척/배송 완료)는 사장에게 알림
    boss_notify_statuses = {"picked_up", "cleaned", "delivered", "settled"}
    # 예약 확정/출발 등은 직원에게 알림
    staff_notify_statuses = {"confirmed", "picking_up", "cleaning", "delivering"}

    if new_status in boss_notify_statuses:
        await notify_boss(bot, text)
    elif new_status in staff_notify_statuses:
        await notify_staff(bot, text)
    else:
        await notify_all(bot, text)


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
