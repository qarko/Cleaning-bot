import React, { useState, useEffect } from 'react';

const ITEM_LABELS = {
  carseat: '카시트', stroller: '유모차', wagon: '웨건',
  mattress: '매트리스', sofa: '소파', carrier: '아기띠',
};

export default function Revenue() {
  const [period, setPeriod] = useState('day');
  const [data, setData] = useState(null);

  useEffect(() => {
    fetch(`/api/dashboard/revenue?period=${period}`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {});
  }, [period]);

  if (!data) return <div className="loading">로딩중</div>;

  const chartData = data.data || [];
  const maxRevenue = Math.max(...chartData.map(d => d.revenue || 0), 1);
  const totalRevenue = chartData.reduce((sum, d) => sum + (d.revenue || 0), 0);
  const totalCount = chartData.reduce((sum, d) => sum + (d.count || 0), 0);

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

  return (
    <>
      <div className="header">
        <h1>매출</h1>
      </div>

      <div className="period-tabs">
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

      <div className="stats-grid" style={{ marginBottom: 16 }}>
        <div className="stat-card green">
          <div className="stat-value">{totalRevenue ? `${(totalRevenue / 10000).toFixed(0)}만` : '0'}</div>
          <div className="stat-label">총 매출</div>
        </div>
        <div className="stat-card blue">
          <div className="stat-value">{totalCount}</div>
          <div className="stat-label">총 건수</div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">매출 추이</div>
        {chartData.length === 0 ? (
          <div className="empty">데이터가 없습니다</div>
        ) : (
          <div className="chart-bar-container">
            {chartData.map((d, i) => (
              <div key={i} className="chart-bar-item">
                <div className="chart-value">
                  {d.revenue ? `${(d.revenue / 10000).toFixed(0)}` : '0'}
                </div>
                <div
                  className="chart-bar"
                  style={{ height: `${Math.max((d.revenue / maxRevenue) * 80, 2)}px` }}
                />
                <div className="chart-label">{formatLabel(d.date)}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {data.by_item && data.by_item.length > 0 && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="card-title">품목별 매출</div>
          <div className="item-breakdown">
            {data.by_item.map((item, i) => (
              <div key={i} className="item-row">
                <span className="item-name">{ITEM_LABELS[item.item_type] || item.item_type} ({item.count}건)</span>
                <span className="item-revenue">{(item.revenue || 0).toLocaleString()}원</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
