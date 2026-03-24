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
            InlineKeyboardButton("카시트 (4만)", callback_data="item:carseat"),
        ],
        [
            InlineKeyboardButton("쌍둥이유모차 (5만)", callback_data="item:stroller"),
            InlineKeyboardButton("웨건 (5만)", callback_data="item:wagon"),
        ],
        [
            InlineKeyboardButton("매트리스", callback_data="item:mattress"),
            InlineKeyboardButton("소파", callback_data="item:sofa"),
        ],
        [
            InlineKeyboardButton("아기띠 (2만/1만)", callback_data="item:carrier"),
        ],
    ])


ITEM_LABELS = {
    "carseat": "카시트",
    "stroller": "쌍둥이유모차",
    "wagon": "웨건",
    "mattress": "매트리스",
    "sofa": "소파",
    "carrier": "아기띠",
}

# 사이즈 선택이 필요한 품목
SUBTYPE_MAP = {
    "carseat": [],  # 전제품 동일가
    "stroller": [],
    "wagon": [],
    "mattress": ["싱글", "더블", "퀸", "킹"],
    "sofa": ["2인", "3인", "4인", "5인"],
    "carrier": ["단독", "카시트/유모차 동시"],
}

# 세척 방식 선택이 필요한 품목
CLEANING_METHOD_ITEMS = {"mattress", "sofa"}


def item_subtype_keyboard(item_type: str):
    subtypes = SUBTYPE_MAP.get(item_type, [])
    if not subtypes:
        return None
    buttons = [[InlineKeyboardButton(s, callback_data=f"subtype:{s}")] for s in subtypes]
    return InlineKeyboardMarkup(buttons)


def cleaning_method_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("건식 세척", callback_data="method:dry"),
            InlineKeyboardButton("습식 세척", callback_data="method:wet"),
        ],
    ])


METHOD_LABELS = {
    "dry": "건식",
    "wet": "습식",
}


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
        weekday = ["월", "화", "수", "목", "금", "토", "일"][d.weekday()]
        label = f"{d.month}/{d.day}({weekday})"
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
        [InlineKeyboardButton("오후 (12-19시)", callback_data="time:afternoon")],
    ])


TIME_LABELS = {
    "morning": "오전",
    "afternoon": "오후",
}


def area_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("대전", callback_data="area:daejeon")],
        [InlineKeyboardButton("세종", callback_data="area:sejong")],
        [InlineKeyboardButton("논산", callback_data="area:nonsan")],
        [InlineKeyboardButton("세종/논산 외곽 (추가비용)", callback_data="area:outer")],
    ])


AREA_LABELS = {
    "daejeon": "대전",
    "sejong": "세종",
    "nonsan": "논산",
    "outer": "외곽(추가비용)",
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
