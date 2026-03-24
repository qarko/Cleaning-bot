import React, { useState, useEffect } from 'react';

const ITEM_LABELS = {
  carseat: '카시트', stroller: '유모차', wagon: '웨건',
  mattress: '매트리스', sofa: '소파', carrier: '아기띠',
};
const STATUS_LABELS = {
  delivered: '배송완료', settled: '정산완료',
};

export default function History() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);

  useEffect(() => {
    fetch(`/api/dashboard/history?page=${page}`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {});
  }, [page]);

  if (!data) return <div className="loading">로딩중</div>;

  return (
    <>
      <div className="header">
        <h1>완료 내역</h1>
        <span className="header-date">총 {data.total}건</span>
      </div>

      {data.reservations.length === 0 ? (
        <div className="empty">완료된 예약이 없습니다</div>
      ) : (
        <>
          {data.reservations.map(r => (
            <div key={r.reservation_no} className="reservation-item">
              <div className="res-info">
                <div className="res-customer">{r.customer_name}</div>
                <div className="res-detail">
                  {r.items && r.items.length > 0
                    ? r.items.map(i => `${ITEM_LABELS[i.item_type] || i.item_type} x${i.quantity || 1}`).join(', ')
                    : r.reservation_no}
                </div>
                <div className="res-detail">{r.scheduled_date}</div>
              </div>
              <div className="res-right">
                <div className="res-price">{(r.price || 0).toLocaleString()}원</div>
                <span className="res-status status-completed">
                  {STATUS_LABELS[r.status] || r.status}
                </span>
              </div>
            </div>
          ))}

          {data.total > 20 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 16 }}>
              {page > 1 && (
                <button className="period-tab active" onClick={() => setPage(p => p - 1)}>
                  ◀ 이전
                </button>
              )}
              <span style={{ color: 'var(--hint)', fontSize: 13, padding: '8px 0' }}>
                {page} / {Math.ceil(data.total / 20)}
              </span>
              {page < Math.ceil(data.total / 20) && (
                <button className="period-tab active" onClick={() => setPage(p => p + 1)}>
                  다음 ▶
                </button>
              )}
            </div>
          )}
        </>
      )}
    </>
  );
}
