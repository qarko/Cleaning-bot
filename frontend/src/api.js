const tg = window.Telegram?.WebApp;

export async function fetchApi(path) {
  const headers = {};
  if (tg?.initData) {
    headers['X-Telegram-Init-Data'] = tg.initData;
  }

  const res = await fetch(path, { headers });

  if (res.status === 401 || res.status === 403) {
    throw new Error('unauthorized');
  }

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}
