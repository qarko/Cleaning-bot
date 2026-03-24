from datetime import date, timedelta, datetime
from fastapi import APIRouter, Query, Request, HTTPException
from sqlalchemy import select, func, extract
from sqlalchemy.orm import selectinload
from app.database import async_session
from app.models.reservation import Reservation
from app.models.customer import Customer
from app.models.payment import Payment
from app.models.employee import Employee
from app.config import BOT_TOKEN
import json
import hashlib
import hmac
from urllib.parse import parse_qs

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def verify_telegram_init_data(init_data: str) -> dict | None:
    """텔레그램 미니앱 initData 검증 → 사용자 정보 반환"""
    try:
        parsed = parse_qs(init_data)
        check_hash = parsed.get("hash", [None])[0]
        if not check_hash:
            return None

        # hash 제외하고 정렬
        data_check_items = []
        for key, values in sorted(parsed.items()):
            if key != "hash":
                data_check_items.append(f"{key}={values[0]}")
        data_check_string = "\n".join(data_check_items)

        # HMAC 검증
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if computed_hash != check_hash:
            return None

        # user 정보 파싱
        user_data = parsed.get("user", [None])[0]
        if user_data:
            return json.loads(user_data)
        return None
    except Exception:
        return None


async def verify_boss(request: Request):
    """사장 권한 검증 미들웨어"""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        raise HTTPException(status_code=401, detail="인증 정보가 없습니다")

    user = verify_telegram_init_data(init_data)
    if not user:
        raise HTTPException(status_code=401, detail="인증에 실패했습니다")

    user_id = user.get("id")
    async with async_session() as db:
        result = await db.execute(
            select(Employee).where(Employee.telegram_user_id == user_id)
        )
        employee = result.scalar_one_or_none()

    if not employee or employee.role != "boss":
        raise HTTPException(status_code=403, detail="사장만 접근할 수 있습니다")

    return employee


@router.get("/summary")
async def get_summary(request: Request):
    """오늘 요약 카드"""
    await verify_boss(request)
    today = date.today()
    async with async_session() as db:
        # 오늘 예약
        result = await db.execute(
            select(Reservation)
            .options(selectinload(Reservation.customer))
            .where(Reservation.scheduled_date == today)
            .where(Reservation.status != "cancelled")
        )
        today_reservations = list(result.scalars().all())

        # 오늘 매출
        result = await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .where(func.date(Payment.paid_at) == today)
        )
        today_revenue = result.scalar()

        # 전체 통계
        total_pending = len([r for r in today_reservations if r.status in ("pending", "confirmed")])
        total_in_progress = len([r for r in today_reservations if r.status in ("picking_up", "picked_up", "cleaning", "cleaned", "delivering")])
        total_completed = len([r for r in today_reservations if r.status in ("delivered", "settled")])

    reservations_data = []
    for r in today_reservations:
        items = []
        if r.items_json:
            try:
                items = json.loads(r.items_json)
            except Exception:
                pass
        reservations_data.append({
            "reservation_no": r.reservation_no,
            "customer_name": r.customer.name if r.customer else "",
            "items": items,
            "status": r.status,
            "scheduled_time": r.scheduled_time,
            "price": r.price,
        })

    return {
        "date": today.isoformat(),
        "total": len(today_reservations),
        "pending": total_pending,
        "in_progress": total_in_progress,
        "completed": total_completed,
        "revenue": today_revenue,
        "reservations": reservations_data,
    }


@router.get("/calendar")
async def get_calendar(request: Request, year: int = Query(None), month: int = Query(None)):
    """월별 캘린더 데이터"""
    await verify_boss(request)
    today = date.today()
    if not year:
        year = today.year
    if not month:
        month = today.month

    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    async with async_session() as db:
        result = await db.execute(
            select(Reservation)
            .options(selectinload(Reservation.customer))
            .where(Reservation.scheduled_date >= start)
            .where(Reservation.scheduled_date < end)
            .where(Reservation.status != "cancelled")
            .order_by(Reservation.scheduled_date, Reservation.scheduled_time)
        )
        reservations = list(result.scalars().all())

    # 날짜별 그룹핑
    calendar_data = {}
    for r in reservations:
        day = r.scheduled_date.isoformat()
        if day not in calendar_data:
            calendar_data[day] = []
        calendar_data[day].append({
            "reservation_no": r.reservation_no,
            "customer_name": r.customer.name if r.customer else "",
            "status": r.status,
            "scheduled_time": r.scheduled_time,
            "price": r.price,
        })

    return {"year": year, "month": month, "days": calendar_data}


@router.get("/revenue")
async def get_revenue(request: Request, period: str = Query("month")):
    """매출 통계 (day/week/month)"""
    await verify_boss(request)
    today = date.today()
    async with async_session() as db:
        if period == "day":
            # 최근 7일 일별
            start = today - timedelta(days=6)
            result = await db.execute(
                select(
                    func.date(Payment.paid_at).label("day"),
                    func.sum(Payment.amount).label("total"),
                    func.count().label("count"),
                )
                .where(func.date(Payment.paid_at) >= start)
                .group_by(func.date(Payment.paid_at))
                .order_by(func.date(Payment.paid_at))
            )
            data = [{"date": str(row.day), "revenue": row.total, "count": row.count} for row in result]

        elif period == "week":
            # 최근 4주 주별
            start = today - timedelta(weeks=4)
            result = await db.execute(
                select(
                    func.sum(Payment.amount).label("total"),
                    func.count().label("count"),
                    func.date(Payment.paid_at).label("day"),
                )
                .where(func.date(Payment.paid_at) >= start)
                .group_by(func.date(Payment.paid_at))
                .order_by(func.date(Payment.paid_at))
            )
            rows = list(result)
            # 주별로 합산
            weeks = {}
            for row in rows:
                d = datetime.strptime(str(row.day), "%Y-%m-%d").date()
                week_start = d - timedelta(days=d.weekday())
                key = week_start.isoformat()
                if key not in weeks:
                    weeks[key] = {"date": key, "revenue": 0, "count": 0}
                weeks[key]["revenue"] += row.total
                weeks[key]["count"] += row.count
            data = list(weeks.values())

        else:
            # 최근 6개월 월별
            start = today - timedelta(days=180)
            result = await db.execute(
                select(
                    extract("year", Payment.paid_at).label("y"),
                    extract("month", Payment.paid_at).label("m"),
                    func.sum(Payment.amount).label("total"),
                    func.count().label("count"),
                )
                .where(func.date(Payment.paid_at) >= start)
                .group_by("y", "m")
                .order_by("y", "m")
            )
            data = [{"date": f"{int(row.y)}-{int(row.m):02d}", "revenue": row.total, "count": row.count} for row in result]

        # 품목별 매출
        result = await db.execute(
            select(
                Reservation.item_type,
                func.sum(Payment.amount).label("total"),
                func.count().label("count"),
            )
            .join(Payment, Payment.reservation_id == Reservation.id)
            .group_by(Reservation.item_type)
        )
        by_item = [{"item_type": row.item_type, "revenue": row.total, "count": row.count} for row in result]

    return {"period": period, "data": data, "by_item": by_item}


@router.get("/history")
async def get_history(request: Request, page: int = Query(1), status: str = Query(None)):
    """완료 내역"""
    await verify_boss(request)
    limit = 20
    offset = (page - 1) * limit

    async with async_session() as db:
        query = (
            select(Reservation)
            .options(selectinload(Reservation.customer))
            .order_by(Reservation.created_at.desc())
        )
        if status:
            query = query.where(Reservation.status == status)
        else:
            query = query.where(Reservation.status.in_(["delivered", "settled"]))

        result = await db.execute(query.offset(offset).limit(limit))
        reservations = list(result.scalars().all())

        # 전체 개수
        count_query = select(func.count()).select_from(Reservation)
        if status:
            count_query = count_query.where(Reservation.status == status)
        else:
            count_query = count_query.where(Reservation.status.in_(["delivered", "settled"]))
        total = (await db.execute(count_query)).scalar()

    items = []
    for r in reservations:
        parsed_items = []
        if r.items_json:
            try:
                parsed_items = json.loads(r.items_json)
            except Exception:
                pass
        items.append({
            "reservation_no": r.reservation_no,
            "customer_name": r.customer.name if r.customer else "",
            "customer_phone": r.customer.phone if r.customer else "",
            "items": parsed_items,
            "status": r.status,
            "scheduled_date": r.scheduled_date.isoformat() if r.scheduled_date else "",
            "price": r.price,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        })

    return {"total": total, "page": page, "reservations": items}
