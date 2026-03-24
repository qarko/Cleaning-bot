import React, { useState, useEffect } from 'react';
import { fetchApi } from '../api';

const STATUS_LABELS = {
  pending: '대기', confirmed: '확정', picking_up: '수거중',
  picked_up: '수거완료', cleaning: '세척중', cleaned: '세척완료',
  delivering: '배송중', delivered: '배송완료', settled: '정산완료',
};

export default function Calendar({ onError }) {
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [data, setData] = useState(null);
  const [selectedDay, setSelectedDay] = useState(null);

  useEffect(() => {
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

  return (
    <>
      <div className="header">
        <h1>캘린더</h1>
      </div>

      <div className="card">
        <div className="cal-header">
          <button className="cal-nav" onClick={prevMonth}>◀</button>
          <span className="cal-month">{year}년 {month}월</span>
          <button className="cal-nav" onClick={nextMonth}>▶</button>
        </div>

        <div className="cal-weekdays">
          {['일', '월', '화', '수', '목', '금', '토'].map(d => <div key={d}>{d}</div>)}
        </div>

        <div className="cal-grid">
          {Array.from({ length: firstDayOfWeek }, (_, i) => (
            <div key={`e${i}`} className="cal-day empty" />
          ))}
          {Array.from({ length: daysInMonth }, (_, i) => {
            const d = i + 1;
            const key = dayKey(d);
            const hasEvents = !!days[key];
            return (
              <div
                key={d}
                className={`cal-day ${isToday(d) ? 'today' : ''} ${hasEvents ? 'has-events' : ''}`}
                onClick={() => hasEvents && setSelectedDay(key)}
              >
                {d}
              </div>
            );
          })}
        </div>
      </div>

      {selectedDay && days[selectedDay] && (
        <div style={{ marginTop: 12 }}>
          <div className="card-title">{selectedDay} 예약</div>
          {days[selectedDay].map(r => (
            <div key={r.reservation_no} className="reservation-item">
              <div className="res-info">
                <div className="res-customer">{r.customer_name}</div>
                <div className="res-detail">{r.reservation_no}</div>
              </div>
              <div className="res-right">
                <div className="res-price">{(r.price || 0).toLocaleString()}원</div>
                <span className="res-status status-confirmed">
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
