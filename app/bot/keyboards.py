from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta


def role_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("사장", callback_data="role:boss")],
        [InlineKeyboardButton("직원 (초대코드 필요)", callback_data="role:staff")],
    ])


def item_type_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("카시트", callback_data="item:carseat"),
            InlineKeyboardButton("매트리스", callback_data="item:mattress"),
        ],
        [
            InlineKeyboardButton("소파", callback_data="item:sofa"),
            InlineKeyboardButton("기타", callback_data="item:other"),
        ],
    ])


ITEM_LABELS = {
    "carseat": "카시트",
    "mattress": "매트리스",
    "sofa": "소파",
    "other": "기타",
}

SUBTYPE_MAP = {
    "carseat": ["일반", "가죽", "스웨이드"],
    "mattress": ["싱글", "더블", "퀸", "킹"],
    "sofa": ["패브릭", "가죽", "스웨이드"],
    "other": [],
}


def item_subtype_keyboard(item_type: str):
    subtypes = SUBTYPE_MAP.get(item_type, [])
    if not subtypes:
        return None
    buttons = [[InlineKeyboardButton(s, callback_data=f"subtype:{s}")] for s in subtypes]
    return InlineKeyboardMarkup(buttons)


def quantity_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1", callback_data="qty:1"),
            InlineKeyboardButton("2", callback_data="qty:2"),
            InlineKeyboardButton("3", callback_data="qty:3"),
        ],
        [
            InlineKeyboardButton("4", callback_data="qty:4"),
            InlineKeyboardButton("5+", callback_data="qty:more"),
        ],
    ])


def date_keyboard(base_date=None):
    if base_date is None:
        base_date = datetime.now()
    buttons = []
    row = []
    for i in range(7):
        d = base_date + timedelta(days=i)
        label = d.strftime("%m/%d(%a)")
        row.append(InlineKeyboardButton(label, callback_data=f"date:{d.strftime('%Y-%m-%d')}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("다음 주 ▶", callback_data=f"date_next:{(base_date + timedelta(days=7)).strftime('%Y-%m-%d')}")])
    return InlineKeyboardMarkup(buttons)


def time_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("오전 (9-12시)", callback_data="time:morning")],
        [InlineKeyboardButton("오후 (12-18시)", callback_data="time:afternoon")],
        [InlineKeyboardButton("저녁 (18-21시)", callback_data="time:evening")],
    ])


TIME_LABELS = {
    "morning": "오전",
    "afternoon": "오후",
    "evening": "저녁",
}


def special_notes_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("없음", callback_data="notes:none")],
    ])


def confirm_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("등록하기", callback_data="confirm:yes")],
        [InlineKeyboardButton("수정하기", callback_data="confirm:edit")],
        [InlineKeyboardButton("취소", callback_data="confirm:cancel")],
    ])


def reservation_action_keyboard(reservation_no: str, status: str):
    buttons = []
    status_actions = {
        "pending": [("확정", "action:confirm")],
        "confirmed": [("수거 출발", "action:picking_up")],
        "picking_up": [("수거 완료", "action:picked_up")],
        "picked_up": [("세척 시작", "action:cleaning")],
        "cleaning": [("세척 완료", "action:cleaned")],
        "cleaned": [("배송 출발", "action:delivering")],
        "delivering": [("배송 완료", "action:delivered")],
        "delivered": [("정산", "action:settle")],
    }
    actions = status_actions.get(status, [])
    for label, data in actions:
        buttons.append([InlineKeyboardButton(f"✅ {label}", callback_data=f"{data}:{reservation_no}")])

    if status not in ("settled", "cancelled"):
        buttons.append([InlineKeyboardButton("취소", callback_data=f"action:cancel:{reservation_no}")])

    return InlineKeyboardMarkup(buttons)


def payment_method_keyboard(reservation_no: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("현금(계좌이체)", callback_data=f"pay:cash:{reservation_no}"),
            InlineKeyboardButton("카드", callback_data=f"pay:card:{reservation_no}"),
        ],
        [InlineKeyboardButton("네이버예약", callback_data=f"pay:naver:{reservation_no}")],
    ])


def reservation_list_keyboard(reservations):
    buttons = []
    for r in reservations:
        label = f"{r.reservation_no} | {r.customer.name} | {ITEM_LABELS.get(r.item_type, r.item_type)}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"view:{r.reservation_no}")])
    return InlineKeyboardMarkup(buttons)


STATUS_LABELS = {
    "pending": "대기",
    "confirmed": "확정",
    "picking_up": "수거중",
    "picked_up": "수거완료",
    "cleaning": "세척중",
    "cleaned": "세척완료",
    "delivering": "배송중",
    "delivered": "배송완료",
    "settled": "정산완료",
    "cancelled": "취소됨",
}

PAYMENT_LABELS = {
    "cash": "현금(계좌이체)",
    "card": "카드",
    "naver": "네이버예약",
}
