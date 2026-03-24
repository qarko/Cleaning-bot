import React, { useState } from 'react';
import Home from './pages/Home';
import Calendar from './pages/Calendar';
import Revenue from './pages/Revenue';
import History from './pages/History';

const TABS = [
  { id: 'home', icon: '🏠', label: '홈' },
  { id: 'calendar', icon: '📅', label: '캘린더' },
  { id: 'revenue', icon: '💰', label: '매출' },
  { id: 'history', icon: '📋', label: '내역' },
];

export default function App() {
  const [tab, setTab] = useState('home');
  const [unauthorized, setUnauthorized] = useState(false);

  if (unauthorized) {
    return (
      <div className="app">
        <div className="empty" style={{ paddingTop: 100 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔒</div>
          <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>접근 권한이 없습니다</div>
          <div style={{ color: 'var(--hint)' }}>대표만 대시보드를 사용할 수 있습니다</div>
        </div>
      </div>
    );
  }

  const onError = (err) => {
    if (err?.message === 'unauthorized') setUnauthorized(true);
  };

  return (
    <div className="app">
      {tab === 'home' && <Home onError={onError} />}
      {tab === 'calendar' && <Calendar onError={onError} />}
      {tab === 'revenue' && <Revenue onError={onError} />}
      {tab === 'history' && <History onError={onError} />}

      <nav className="nav">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`nav-item ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            <span className="nav-icon">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
