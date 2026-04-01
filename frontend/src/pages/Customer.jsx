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
        <div>
          <h1>고객 조회</h1>
          <div className="header-sub">고객 정보 및 이용 내역</div>
        </div>
      </div>

      <div className="card animate-in animate-in-1">
        <div className="search-container">
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && search()}
            placeholder="연락처 또는 주소 검색"
            className="search-input"
          />
          <button onClick={search} className="search-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: 'middle', marginRight: 4 }}>
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            검색
          </button>
        </div>
      </div>

      {loading && (
        <div className="loading-container">
          <div className="loading-spinner" />
          <div className="loading-text">검색중...</div>
        </div>
      )}

      {notFound && (
        <div className="empty animate-in">
          <div className="empty-icon">🔍</div>
          <div className="empty-text">검색 결과가 없습니다</div>
        </div>
      )}

      {result && (
        <>
          <div className="card animate-in animate-in-2">
            <div className="card-title">고객 정보</div>
            <div className="customer-info-row">
              <span className="customer-info-label">연락처</span>
              <span className="customer-info-value">{result.customer.phone}</span>
            </div>
            {result.customer.address && (
              <div className="customer-info-row">
                <span className="customer-info-label">주소</span>
                <span className="customer-info-value">{result.customer.address}</span>
              </div>
            )}
            {result.customer.memo && (
              <div className="customer-info-row">
                <span className="customer-info-label">메모</span>
                <span className="customer-info-value" style={{ color: 'var(--text-secondary)' }}>{result.customer.memo}</span>
              </div>
            )}

            <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
              <div className="stat-card blue" style={{ flex: 1, padding: 14, marginBottom: 0 }}>
                <div className="stat-value" style={{ fontSize: 22 }}>{result.customer.visit_count}</div>
                <div className="stat-label">방문 횟수</div>
              </div>
              <div className="stat-card green" style={{ flex: 1, padding: 14, marginBottom: 0 }}>
                <div className="stat-value" style={{ fontSize: 22 }}>
                  {result.customer.total_paid ? `${(result.customer.total_paid / 10000).toFixed(0)}만` : '0'}
                </div>
                <div className="stat-label">총 결제</div>
              </div>
            </div>
          </div>

          {result.reservations && result.reservations.length > 0 && (
            <div className="animate-in animate-in-3">
              <div className="section-title">이용 내역 ({result.reservations.length}건)</div>
              {result.reservations.map((r, idx) => (
                <div
                  key={r.reservation_no}
                  className="reservation-item animate-in"
                  style={{ animationDelay: `${0.2 + idx * 0.04}s` }}
                >
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
