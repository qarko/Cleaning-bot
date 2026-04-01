import React, { useState, useEffect } from 'react';
import { fetchApi } from '../api';

const ITEM_LABELS = {
  carseat: '카시트', stroller: '유모차', wagon: '웨건',
  mattress: '매트리스', sofa: '소파', carrier: '아기띠',
};
const STATUS_LABELS = {
  delivered: '배송완료', settled: '정산완료',
};

const METHOD_LABELS = {
  cash: '현금', card: '카드', naver: '네이버',
};

export default function History({ onError }) {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setData(null);
    fetchApi(`/api/dashboard/history?page=${page}`)
      .then(setData)
      .catch(onError);
  }, [page]);

  if (!data) return (
    <div className="loading-container">
      <div className="loading-spinner" />
      <div className="loading-text">로딩중...</div>
    </div>
  );

  const totalPages = Math.ceil(data.total / 20);

  return (
    <>
      <div className="header">
        <div>
          <h1>완료 내역</h1>
          <div className="header-sub">처리 완료된 예약</div>
        </div>
        <div className="header-badge">
          총 {data.total}건
        </div>
      </div>

      {data.reservations.length === 0 ? (
        <div className="empty animate-in">
          <div className="empty-icon">📭</div>
          <div className="empty-text">완료된 예약이 없습니다</div>
        </div>
      ) : (
        <>
          {data.reservations.map((r, idx) => (
            <div
              key={r.reservation_no}
              className="reservation-item animate-in"
              style={{ animationDelay: `${idx * 0.04}s` }}
            >
              <div className="res-info">
                <div className="res-customer">{r.address || r.customer_phone || r.customer_name}</div>
                <div className="res-detail">
                  {r.items && r.items.length > 0
                    ? r.items.map(i => `${ITEM_LABELS[i.item_type] || i.item_type} x${i.quantity || 1}`).join(', ')
                    : r.reservation_no}
                </div>
                <div className="res-detail" style={{ marginTop: 2 }}>
                  {r.scheduled_date}
                  {r.actual_payment_method && r.actual_payment_method !== r.payment_method
                    ? ` · ${METHOD_LABELS[r.payment_method] || ''}→${METHOD_LABELS[r.actual_payment_method] || ''}`
                    : r.actual_payment_method
                      ? ` · ${METHOD_LABELS[r.actual_payment_method] || ''}`
                      : r.payment_method
                        ? ` · ${METHOD_LABELS[r.payment_method] || ''}`
                        : ''}
                </div>
              </div>
              <div className="res-right">
                <div className="res-price">{(r.price || 0).toLocaleString()}원</div>
                <span className="res-status status-completed">
                  {STATUS_LABELS[r.status] || r.status}
                </span>
              </div>
            </div>
          ))}

          {totalPages > 1 && (
            <div className="pagination">
              {page > 1 && (
                <button className="page-btn" onClick={() => setPage(p => p - 1)}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 4, verticalAlign: 'middle' }}>
                    <polyline points="15 18 9 12 15 6"/>
                  </svg>
                  이전
                </button>
              )}
              <span className="page-info">
                {page} / {totalPages}
              </span>
              {page < totalPages && (
                <button className="page-btn" onClick={() => setPage(p => p + 1)}>
                  다음
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: 4, verticalAlign: 'middle' }}>
                    <polyline points="9 18 15 12 9 6"/>
                  </svg>
                </button>
              )}
            </div>
          )}
        </>
      )}
    </>
  );
}
