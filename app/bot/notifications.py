from telegram import Bot
from app.config import GROUP_CHAT_ID
from app.bot.keyboards import ITEM_LABELS, TIME_LABELS, STATUS_LABELS, METHOD_LABELS, AREA_LABELS


async def notify_group_new_reservation(bot: Bot, reservation, data: dict):
    if not GROUP_CHAT_ID:
        return

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
    await bot.send_message(chat_id=GROUP_CHAT_ID, text=text)


async def notify_group_status_change(bot: Bot, reservation, new_status: str, employee_name: str = ""):
    if not GROUP_CHAT_ID:
        return

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
    await bot.send_message(chat_id=GROUP_CHAT_ID, text=text)


async def send_daily_schedule(bot: Bot):
    """매일 아침 오늘의 일정 발송"""
    if not GROUP_CHAT_ID:
        return

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
        # 상태별 분류
        pickup_list = [r for r in reservations if r.status in ("confirmed", "picking_up")]
        cleaning_list = [r for r in reservations if r.status in ("picked_up", "cleaning")]
        delivery_list = [r for r in reservations if r.status in ("cleaned", "delivering")]

        idx = 1
        for r in reservations:
            item = ITEM_LABELS.get(r.item_type, r.item_type)
            time_label = TIME_LABELS.get(r.scheduled_time, "")
            status = STATUS_LABELS.get(r.status, r.status)
            text += f"{idx}. {time_label} {r.customer.name} - {item} x{r.quantity} [{status}]\n"
            idx += 1

        waiting_clean = len(cleaning_list)
        if waiting_clean:
            text += f"\n세척 대기: {waiting_clean}건"
        waiting_delivery = len(delivery_list)
        if waiting_delivery:
            text += f"\n배송 대기: {waiting_delivery}건"

        text += "\n━━━━━━━━━━━━━━"

    await bot.send_message(chat_id=GROUP_CHAT_ID, text=text)
