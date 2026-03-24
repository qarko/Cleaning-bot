from datetime import date, datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.reservation import Reservation
from app.models.customer import Customer
from app.models.task_update import TaskUpdate
from app.models.payment import Payment
from app.models.pricing import Pricing


async def generate_reservation_no(db: AsyncSession, d: date = None) -> str:
    if d is None:
        d = date.today()
    prefix = f"CL-{d.strftime('%Y%m%d')}"
    result = await db.execute(
        select(func.count()).where(Reservation.reservation_no.like(f"{prefix}%"))
    )
    count = result.scalar() + 1
    return f"{prefix}-{count:03d}"


async def get_or_create_customer(db: AsyncSession, name: str, phone: str, address: str = None) -> Customer:
    result = await db.execute(select(Customer).where(Customer.phone == phone))
    customer = result.scalar_one_or_none()
    if customer:
        customer.name = name
        if address:
            customer.address = address
        customer.visit_count += 1
        await db.flush()
        return customer

    customer = Customer(name=name, phone=phone, address=address, visit_count=1)
    db.add(customer)
    await db.flush()
    return customer


async def create_reservation(db: AsyncSession, data: dict) -> Reservation:
    customer = await get_or_create_customer(db, data["name"], data["phone"], data.get("address"))

    reservation_no = await generate_reservation_no(db, data.get("scheduled_date", date.today()))

    import json
    items = data.get("items", [])
    # 대표 품목 (첫 번째)
    first_item = items[0] if items else {}
    total_qty = sum(i.get("quantity", 1) for i in items) if items else data.get("quantity", 1)

    reservation = Reservation(
        reservation_no=reservation_no,
        customer_id=customer.id,
        item_type=first_item.get("item_type", data.get("item_type", "")),
        item_subtype=first_item.get("item_subtype", data.get("item_subtype")),
        quantity=total_qty,
        scheduled_date=data["scheduled_date"],
        scheduled_time=data["scheduled_time"],
        pickup_address=data.get("address"),
        cleaning_method=first_item.get("cleaning_method", data.get("cleaning_method")),
        area=data.get("area"),
        payment_method=data.get("payment_method"),
        items_json=json.dumps(items, ensure_ascii=False) if items else None,
        special_notes=data.get("special_notes"),
        status="pending",
        price=data.get("price", 0),
    )
    db.add(reservation)
    await db.commit()
    await db.refresh(reservation, ["customer"])
    return reservation


async def get_reservation(db: AsyncSession, reservation_no: str) -> Reservation | None:
    result = await db.execute(
        select(Reservation)
        .options(selectinload(Reservation.customer), selectinload(Reservation.task_updates))
        .where(Reservation.reservation_no == reservation_no)
    )
    return result.scalar_one_or_none()


async def get_today_reservations(db: AsyncSession) -> list[Reservation]:
    today = date.today()
    result = await db.execute(
        select(Reservation)
        .options(selectinload(Reservation.customer))
        .where(Reservation.scheduled_date == today)
        .where(Reservation.status != "cancelled")
        .order_by(Reservation.scheduled_time)
    )
    return list(result.scalars().all())


async def get_tomorrow_reservations(db: AsyncSession) -> list[Reservation]:
    tomorrow = date.today() + timedelta(days=1)
    result = await db.execute(
        select(Reservation)
        .options(selectinload(Reservation.customer))
        .where(Reservation.scheduled_date == tomorrow)
        .where(Reservation.status != "cancelled")
        .order_by(Reservation.scheduled_time)
    )
    return list(result.scalars().all())


async def get_all_reservations(db: AsyncSession, limit: int = 20) -> list[Reservation]:
    result = await db.execute(
        select(Reservation)
        .options(selectinload(Reservation.customer))
        .where(Reservation.status != "cancelled")
        .order_by(Reservation.scheduled_date.desc(), Reservation.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_reservation_status(db: AsyncSession, reservation_no: str, status: str) -> Reservation | None:
    reservation = await get_reservation(db, reservation_no)
    if not reservation:
        return None
    reservation.status = status
    await db.commit()
    await db.refresh(reservation, ["customer"])
    return reservation


async def add_task_update(db: AsyncSession, reservation_id: int, stage: str, employee_id: int, photo_url: str = None, memo: str = None) -> TaskUpdate:
    task = TaskUpdate(
        reservation_id=reservation_id,
        stage=stage,
        updated_by=employee_id,
        photo_url=photo_url,
        memo=memo,
    )
    db.add(task)
    await db.commit()
    return task


async def settle_reservation(db: AsyncSession, reservation_no: str, method: str) -> Payment | None:
    reservation = await get_reservation(db, reservation_no)
    if not reservation:
        return None

    amount = reservation.final_price or reservation.price
    payment = Payment(
        reservation_id=reservation.id,
        amount=amount,
        method=method,
    )
    db.add(payment)
    reservation.status = "settled"

    # 고객 총 결제 금액 업데이트
    reservation.customer.total_paid += amount
    await db.commit()
    return payment


async def get_price(db: AsyncSession, item_type: str, item_subtype: str = None, cleaning_method: str = None) -> int:
    # 건식/습식 동일가이므로 method는 참고용, subtype으로 가격 조회
    query = select(Pricing).where(Pricing.item_type == item_type, Pricing.is_active == True)
    if item_subtype:
        query = query.where(Pricing.item_subtype == item_subtype)
    result = await db.execute(query)
    pricing = result.scalar_one_or_none()
    return pricing.price if pricing else 0


async def get_customer_info(db: AsyncSession, search: str) -> Customer | None:
    result = await db.execute(
        select(Customer).where(
            (Customer.name == search) | (Customer.phone == search)
        )
    )
    return result.scalar_one_or_none()


async def get_customer_reservations(db: AsyncSession, customer_id: int) -> list[Reservation]:
    result = await db.execute(
        select(Reservation)
        .where(Reservation.customer_id == customer_id)
        .order_by(Reservation.created_at.desc())
        .limit(10)
    )
    return list(result.scalars().all())
