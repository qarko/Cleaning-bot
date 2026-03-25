import React, { useState } from 'react';
import { fetchApi } from '../api';

const ITEM_LABELS = {
  carseat: '카시트', stroller: '유모차', wagon: '웨건',
  mattress: '매트리스', sofa: '소파', carrier: '아기띠',
};

const METHOD_LABELS = {
  cash: '현금', card: '카드', naver: '네이버',
};

export default function Customer({ onError }) {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setNotFound(false);
    setResult(null);
    try {
      const data = await fetchApi(`/api/dashboard/customer?q=${encodeURIComponent(query.trim())}`);
      if (data.customer) {
        setResult(data);
      } else {
        setNotFound(true);
      }
    } catch (err) {
      if (err?.message === 'unauthorized') onError(err);
      else setNotFound(true);
    }
    setLoading(false);
  };

  return (
    <>
      <div className="header">
        <h1>고객 조회</h1>
      </div>

      <div className="card">
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && search()}
            placeholder="연락처 또는 주소 검색"
            style={{
              flex: 1,
              padding: '10px 14px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
              background: 'var(--bg)',
              color: 'var(--text)',
              fontSize: 14,
              outline: 'none',
            }}
          />
          <button
            onClick={search}
            style={{
              padding: '10px 18px',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              background: 'var(--btn)',
              color: 'var(--btn-text)',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            검색
          </button>
        </div>
      </div>

      {loading && <div className="loading">검색중</div>}

      {notFound && <div className="empty">검색 결과가 없습니다</div>}

      {result && (
        <>
          <div className="card">
            <div className="card-title">고객 정보</div>
            <div style={{ fontSize: 15 }}>
              <div style={{ marginBottom: 8 }}>
                <span style={{ color: 'var(--hint)', marginRight: 8 }}>연락처</span>
                <strong>{result.customer.phone}</strong>
              </div>
              {result.customer.address && (
                <div style={{ marginBottom: 8 }}>
                  <span style={{ color: 'var(--hint)', marginRight: 8 }}>주소</span>
                  {result.customer.address}
                </div>
              )}
              <div style={{ display: 'flex', gap: 16, marginTop: 12 }}>
                <div className="stat-card" style={{ flex: 1, padding: 12 }}>
                  <div className="stat-value" style={{ fontSize: 22 }}>{result.customer.visit_count}</div>
                  <div className="stat-label">방문 횟수</div>
                </div>
                <div className="stat-card green" style={{ flex: 1, padding: 12 }}>
                  <div className="stat-value" style={{ fontSize: 22 }}>
                    {result.customer.total_paid ? `${(result.customer.total_paid / 10000).toFixed(0)}만` : '0'}
                  </div>
                  <div className="stat-label">총 결제</div>
                </div>
              </div>
            </div>
          </div>

          {result.reservations && result.reservations.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="card-title">이용 내역 ({result.reservations.length}건)</div>
              {result.reservations.map(r => (
                <div key={r.reservation_no} className="reservation-item">
                  <div className="res-info">
                    <div className="res-customer">
                      {r.items && r.items.length > 0
                        ? r.items.map(i => `${ITEM_LABELS[i.item_type] || i.item_type} x${i.quantity || 1}`).join(', ')
                        : r.reservation_no}
                    </div>
                    <div className="res-detail">
                      {r.scheduled_date}
                      {r.actual_payment_method
                        ? ` · ${METHOD_LABELS[r.actual_payment_method] || r.actual_payment_method}`
                        : r.payment_method
                          ? ` · ${METHOD_LABELS[r.payment_method] || r.payment_method}`
                          : ''}
                    </div>
                  </div>
                  <div className="res-right">
                    <div className="res-price">{(r.price || 0).toLocaleString()}원</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
