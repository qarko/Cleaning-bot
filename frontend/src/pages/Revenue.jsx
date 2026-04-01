import React, { useState, useEffect } from 'react';
import { fetchApi } from '../api';

const ITEM_LABELS = {
  carseat: '카시트', stroller: '유모차', wagon: '웨건',
  mattress: '매트리스', sofa: '소파', carrier: '아기띠',
};

const METHOD_LABELS = {
  cash: '현금(계좌이체)', card: '카드', naver: '네이버예약',
};

const METHOD_ICONS = {
  cash: '🏦', card: '💳', naver: '🟢',
};

export default function Revenue({ onError }) {
  const [period, setPeriod] = useState('day');
  const [data, setData] = useState(null);

  useEffect(() => {
    setData(null);
    fetchApi(`/api/dashboard/revenue?period=${period}`)
      .then(setData)
      .catch(onError);
  }, [period]);

  if (!data) return (
    <div className="loading-container">
      <div className="loading-spinner" />
      <div className="loading-text">로딩중...</div>
    </div>
  );

  const chartData = data.data || [];
  const maxRevenue = Math.max(...chartData.map(d => d.revenue || 0), 1);
  const totalRevenue = chartData.reduce((sum, d) => sum + (d.revenue || 0), 0);
  const totalCount = chartData.reduce((sum, d) => sum + (d.count || 0), 0);
  const avgRevenue = totalCount > 0 ? Math.round(totalRevenue / totalCount) : 0;

  // Find the max day
  const maxDay = chartData.reduce((max, d) => (d.revenue || 0) > (max.revenue || 0) ? d : max, { revenue: 0 });

  function formatLabel(dateStr) {
    if (!dateStr) return '';
    if (period === 'day') {
      const d = new Date(dateStr);
      return `${d.getMonth() + 1}/${d.getDate()}`;
    }
    if (period === 'week') {
      const d = new Date(dateStr);
      return `${d.getMonth() + 1}/${d.getDate()}~`;
    }
    return dateStr.split('-')[1] + '월';
  }

  function formatRevenue(val) {
    if (!val) return '0';
    if (val >= 10000) return `${(val / 10000).toFixed(0)}만`;
    return val.toLocaleString();
  }

  // Max for by_item bar chart
  const maxItemRevenue = data.by_item
    ? Math.max(...data.by_item.map(i => i.revenue || 0), 1)
    : 1;

  return (
    <>
      <div className="header">
        <div>
          <h1>매출</h1>
          <div className="header-sub">매출 분석 리포트</div>
        </div>
      </div>

      <div className="period-tabs animate-in animate-in-1">
        {[
          { id: 'day', label: '일별' },
          { id: 'week', label: '주별' },
          { id: 'month', label: '월별' },
        ].map(p => (
          <button
            key={p.id}
            className={`period-tab ${period === p.id ? 'active' : ''}`}
            onClick={() => setPeriod(p.id)}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Revenue Hero */}
      <div className="revenue-hero animate-in animate-in-2">
        <div className="revenue-hero-label">총 매출</div>
        <div className="revenue-hero-value">
          {totalRevenue ? `${(totalRevenue / 10000).toFixed(1)}만원` : '0원'}
        </div>
        <div className="revenue-hero-sub">
          <div className="revenue-hero-stat">
            <div className="revenue-hero-stat-value">{totalCount}건</div>
            <div className="revenue-hero-stat-label">총 건수</div>
          </div>
          <div className="revenue-hero-stat">
            <div className="revenue-hero-stat-value" style={{ color: 'var(--green)' }}>
              {avgRevenue ? `${(avgRevenue / 10000).toFixed(1)}만` : '0'}
            </div>
            <div className="revenue-hero-stat-label">건당 평균</div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="card animate-in animate-in-3">
        <div className="card-title">매출 추이</div>
        {chartData.length === 0 ? (
          <div className="empty">
            <div className="empty-icon">📊</div>
            <div className="empty-text">데이터가 없습니다</div>
          </div>
        ) : (
          <div className="chart-container">
            <div className="chart-bar-container">
              {chartData.map((d, i) => {
                const isMax = d === maxDay && d.revenue > 0;
                const heightPct = Math.max((d.revenue / maxRevenue) * 100, 3);
                return (
                  <div key={i} className="chart-bar-item">
                    <div className="chart-value">
                      {d.revenue ? formatRevenue(d.revenue) : '0'}
                    </div>
                    <div className="chart-bar-wrapper">
                      <div
                        className={`chart-bar ${isMax ? 'highlight' : ''}`}
                        style={{
                          height: `${heightPct}%`,
                          animationDelay: `${i * 0.08}s`,
                        }}
                      />
                    </div>
                    <div className="chart-label">{formatLabel(d.date)}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Item Breakdown */}
      {data.by_item && data.by_item.length > 0 && (
        <div className="card animate-in animate-in-4">
          <div className="card-title">품목별 매출</div>
          <div className="item-breakdown">
            {data.by_item.map((item, i) => (
              <div key={i} className="item-row" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="item-name">
                    {ITEM_LABELS[item.item_type] || item.item_type}
                    <span className="item-count">{item.count}건</span>
                  </span>
                  <span className="item-revenue">{(item.revenue || 0).toLocaleString()}원</span>
                </div>
                <div className="item-bar-bg">
                  <div
                    className="item-bar-fill"
                    style={{ width: `${(item.revenue / maxItemRevenue) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Payment Method Breakdown */}
      {data.by_method && data.by_method.length > 0 && (
        <div className="card animate-in animate-in-5">
          <div className="card-title">결제 방법별</div>
          <div className="item-breakdown">
            {data.by_method.map((m, i) => {
              const pct = totalRevenue > 0 ? Math.round((m.revenue / totalRevenue) * 100) : 0;
              return (
                <div key={i} className="item-row">
                  <span className="item-name">
                    <span style={{ fontSize: 16 }}>{METHOD_ICONS[m.method] || '💵'}</span>
                    {METHOD_LABELS[m.method] || m.method}
                    <span className="item-count">{m.count}건 ({pct}%)</span>
                  </span>
                  <span className="item-revenue">{(m.revenue || 0).toLocaleString()}원</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}
