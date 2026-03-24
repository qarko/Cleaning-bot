import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';

const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  tg.enableClosingConfirmation();
}

createRoot(document.getElementById('root')).render(<App />);
