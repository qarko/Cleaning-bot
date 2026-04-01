import React, { useState } from 'react';
import Home from './pages/Home';
import Calendar from './pages/Calendar';
import Revenue from './pages/Revenue';
import History from './pages/History';
import Customer from './pages/Customer';

const TABS = [
  { id: 'home', icon: '\u2302', label: '홈' },
  { id: 'calendar', icon: '\u2630', label: '캘린더' },
  { id: 'revenue', icon: '\u2191', label: '매출' },
  { id: 'history', icon: '\u2611', label: '내역' },
  { id: 'customer', icon: '\u263A', label: '고객' },
];

const SVG_ICONS = {
  home: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
      <polyline points="9 22 9 12 15 12 15 22"/>
    </svg>
  ),
  calendar: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
      <line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>
      <line x1="3" y1="10" x2="21" y2="10"/>
    </svg>
  ),
  revenue: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>
    </svg>
  ),
  history: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="16" y1="17" x2="8" y2="17"/>
      <polyline points="10 9 9 9 8 9"/>
    </svg>
  ),
  customer: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
      <circle cx="12" cy="7" r="4"/>
    </svg>
  ),
};

export default function App() {
  const [tab, setTab] = useState('home');
  const [unauthorized, setUnauthorized] = useState(false);

  if (unauthorized) {
    return (
      <div className="app">
        <div className="unauthorized">
          <div className="unauthorized-icon">🔒</div>
          <div className="unauthorized-title">접근 권한이 없습니다</div>
          <div className="unauthorized-desc">대표만 대시보드를 사용할 수 있습니다</div>
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
      {tab === 'customer' && <Customer onError={onError} />}

      <nav className="nav">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`nav-item ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            <span className="nav-icon">{SVG_ICONS[t.id]}</span>
            {t.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
