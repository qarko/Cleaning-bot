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

  return (
    <div className="app">
      {tab === 'home' && <Home />}
      {tab === 'calendar' && <Calendar />}
      {tab === 'revenue' && <Revenue />}
      {tab === 'history' && <History />}

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
