import React, { useState, useEffect } from 'react';
import { fetchApi } from '../api';

const STATUS_LABELS = {
  pending: '대기', confirmed: '확정', picking_up: '수거중',
  picked_up: '수거완료', cleaning: '세척중', cleaned: '세척완료',
  delivering: '배송중', delivered: '배송완료', settled: '정산완료',
};

function statusClass(status) {
  if (['pending'].includes(status)) return 'status-pending';
  if (['confirmed'].includes(status)) return 'status-confirmed';
  if (['picking_up', 'picked_up', 'cleaning', 'cleaned', 'delivering'].includes(status)) return 'status-progress';
  return 'status-completed';
}

export default function Calendar({ onError }) {
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [data, setData] = useState(null);
  const [selectedDay, setSelectedDay] = useState(null);

  useEffect(() => {
    setData(null);
    fetchApi(`/api/dashboard/calendar?year=${year}&month=${month}`)
      .then(setData)
      .catch(onError);
  }, [year, month]);

  const prevMonth = () => {
    if (month === 1) { setMonth(12); setYear(y => y - 1); }
    else setMonth(m => m - 1);
    setSelectedDay(null);
  };
  const nextMonth = () => {
    if (month === 12) { setMonth(1); setYear(y => y + 1); }
    else setMonth(m => m + 1);
    setSelectedDay(null);
  };

  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDayOfWeek = new Date(year, month - 1, 1).getDay();
  const today = new Date();
  const isToday = (d) => today.getFullYear() === year && today.getMonth() + 1 === month && today.getDate() === d;
  const days = data?.days || {};

  const dayKey = (d) => `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;

  // Count total reservations this month
  const totalMonthReservations = Object.values(days).reduce((sum, arr) => sum + arr.length, 0);

  return (
    <>
      <div className="header">
        <div>
          <h1>캘린더</h1>
          <div className="header-sub">월별 예약 현황</div>
        </div>
        {totalMonthReservations > 0 && (
          <div className="header-badge">
            {totalMonthReservations}건
          </div>
        )}
      </div>

      <div className="card animate-in animate-in-1">
        <div className="cal-header">
          <button className="cal-nav" onClick={prevMonth}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
          </button>
          <span className="cal-month">{year}년 {month}월</span>
          <button className="cal-nav" onClick={nextMonth}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          </button>
        </div>

        <div className="cal-weekdays">
          {['일', '월', '화', '수', '목', '금', '토'].map(d => <div key={d}>{d}</div>)}
        </div>

        {!data ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
            <div className="loading-spinner" />
          </div>
        ) : (
          <div className="cal-grid">
            {Array.from({ length: firstDayOfWeek }, (_, i) => (
              <div key={`e${i}`} className="cal-day empty" />
            ))}
            {Array.from({ length: daysInMonth }, (_, i) => {
              const d = i + 1;
              const key = dayKey(d);
              const hasEvents = !!days[key];
              const dayOfWeek = (firstDayOfWeek + i) % 7;
              const isSunday = dayOfWeek === 0;
              const isSaturday = dayOfWeek === 6;
              const isSelected = selectedDay === key;
              return (
                <div
                  key={d}
                  className={[
                    'cal-day',
                    isToday(d) && !isSelected ? 'today' : '',
                    isSelected ? 'selected' : '',
                    hasEvents ? 'has-events' : '',
                    isSunday ? 'sunday' : '',
                    isSaturday ? 'saturday' : '',
                  ].filter(Boolean).join(' ')}
                  onClick={() => hasEvents && setSelectedDay(isSelected ? null : key)}
                >
                  {d}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {selectedDay && days[selectedDay] && (
        <div className="animate-in" style={{ marginTop: 4 }}>
          <div className="section-title">{selectedDay} 예약 ({days[selectedDay].length}건)</div>
          {days[selectedDay].map((r, idx) => (
            <div
              key={r.reservation_no}
              className="reservation-item animate-in"
              style={{ animationDelay: `${idx * 0.05}s` }}
            >
              <div className="res-info">
                <div className="res-customer">{r.customer_name}</div>
                <div className="res-detail">{r.reservation_no}</div>
              </div>
              <div className="res-right">
                <div className="res-price">{(r.price || 0).toLocaleString()}원</div>
                <span className={`res-status ${statusClass(r.status)}`}>
                  {STATUS_LABELS[r.status] || r.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
