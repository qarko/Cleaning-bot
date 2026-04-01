import React, { useState, useEffect } from 'react';
import { fetchApi } from '../api';

const ITEM_LABELS = {
  carseat: '카시트', stroller: '쌍둥이유모차', wagon: '웨건',
  mattress: '매트리스', sofa: '소파', carrier: '아기띠',
};
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

function formatItems(items) {
  if (!items || items.length === 0) return '';
  return items.map(i => `${ITEM_LABELS[i.item_type] || i.item_type} x${i.quantity || 1}`).join(', ');
}

export default function Home({ onError }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    fetchApi('/api/dashboard/summary').then(setData).catch(onError);
    const interval = setInterval(() => {
      fetchApi('/api/dashboard/summary').then(setData).catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  if (!data) return (
    <div className="loading-container">
      <div className="loading-spinner" />
      <div className="loading-text">로딩중...</div>
    </div>
  );

  const today = new Date();
  const dateStr = `${today.getMonth() + 1}월 ${today.getDate()}일 ${['일', '월', '화', '수', '목', '금', '토'][today.getDay()]}요일`;

  const completionRate = data.total > 0
    ? Math.round((data.completed / data.total) * 100)
    : 0;

  return (
    <>
      <div className="header">
        <div>
          <h1>올그린</h1>
          <div className="header-sub">{dateStr}</div>
        </div>
        <div className="header-badge">
          <span className="dot" />
          실시간
        </div>
      </div>

      {/* Progress overview */}
      {data.total > 0 && (
        <div className="card-glass animate-in animate-in-1">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>오늘 진행률</span>
            <span style={{ fontSize: 20, fontWeight: 800, color: 'var(--green)' }}>{completionRate}%</span>
          </div>
          <div className="progress-bar-bg">
            <div
              className="progress-bar-fill green"
              style={{ width: `${completionRate}%` }}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
            <span style={{ fontSize: 12, color: 'var(--hint)' }}>완료 {data.completed}건</span>
            <span style={{ fontSize: 12, color: 'var(--hint)' }}>전체 {data.total}건</span>
          </div>
        </div>
      )}

      <div className="stats-grid animate-in animate-in-2">
        <div className="stat-card">
          <div className="stat-icon">📋</div>
          <div className="stat-value">{data.total}</div>
          <div className="stat-label">오늘 예약</div>
        </div>
        <div className="stat-card green">
          <div className="stat-icon">✅</div>
          <div className="stat-value">{data.completed}</div>
          <div className="stat-label">완료</div>
        </div>
        <div className="stat-card orange">
          <div className="stat-icon">🔄</div>
          <div className="stat-value">{data.in_progress}</div>
          <div className="stat-label">진행중</div>
        </div>
        <div className="stat-card blue">
          <div className="stat-icon">💰</div>
          <div className="stat-value">{data.revenue ? `${(data.revenue / 10000).toFixed(0)}만` : '0'}</div>
          <div className="stat-label">오늘 매출</div>
        </div>
      </div>

      <div style={{ marginTop: 20 }} className="animate-in animate-in-3">
        <div className="section-title">오늘 예약</div>
        {data.reservations.length === 0 ? (
          <div className="empty">
            <div className="empty-icon">📭</div>
            <div className="empty-text">오늘 예약이 없습니다</div>
          </div>
        ) : (
          data.reservations.map((r, idx) => (
            <div
              key={r.reservation_no}
              className="reservation-item animate-in"
              style={{ animationDelay: `${0.2 + idx * 0.05}s` }}
            >
              <div className="res-info">
                <div className="res-customer">{r.customer_name}</div>
                <div className="res-detail">{formatItems(r.items)}</div>
              </div>
              <div className="res-right">
                <div className="res-price">{(r.price || 0).toLocaleString()}원</div>
                <span className={`res-status ${statusClass(r.status)}`}>
                  {STATUS_LABELS[r.status] || r.status}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </>
  );
}
