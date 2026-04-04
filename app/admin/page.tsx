'use client';

import { useState, useEffect } from 'react';

const ADMIN_SECRET = process.env.NEXT_PUBLIC_ADMIN_SECRET || '';

export default function AdminPage() {
  const [authenticated, setAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [licenses, setLicenses] = useState<any[]>([]);
  const [newLabel, setNewLabel] = useState('');
  const [newKey, setNewKey] = useState('');
  const [loading, setLoading] = useState(false);

  const authHeader = `Bearer ${ADMIN_SECRET}`;

  const fetchLicenses = async () => {
    const res = await fetch('/api/license', { headers: { authorization: authHeader } });
    if (res.ok) {
      const data = await res.json();
      setLicenses(data.keys || []);
    }
  };

  const handleAdminLogin = () => {
    if (password === ADMIN_SECRET) {
      setAuthenticated(true);
      fetchLicenses();
    } else {
      setError('Неверный пароль');
    }
  };

  const createLicense = async () => {
    setLoading(true);
    const res = await fetch('/api/license', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', authorization: authHeader },
      body: JSON.stringify({ label: newLabel }),
    });
    if (res.ok) {
      const data = await res.json();
      setNewKey(data.key);
      setNewLabel('');
      fetchLicenses();
    }
    setLoading(false);
  };

  const toggleLicense = async (hash: string, active: boolean) => {
    await fetch('/api/license', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', authorization: authHeader },
      body: JSON.stringify({ hash, active: !active }),
    });
    fetchLicenses();
  };

  const deleteLicense = async (hash: string) => {
    if (!confirm('Удалить эту лицензию?')) return;
    await fetch('/api/license', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json', authorization: authHeader },
      body: JSON.stringify({ hash }),
    });
    fetchLicenses();
  };

  if (!authenticated) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center p-4">
        <div className="max-w-sm w-full bg-gray-900 p-8 rounded-2xl border border-gray-800">
          <h1 className="text-xl font-black text-white mb-4 text-center uppercase">Admin Panel</h1>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdminLogin()}
            className="w-full bg-black border border-gray-800 text-white p-3 rounded-xl font-mono mb-4"
            placeholder="Admin password"
          />
          {error && <div className="text-red-500 text-sm mb-4">{error}</div>}
          <button
            onClick={handleAdminLogin}
            className="w-full bg-red-600 hover:bg-red-500 text-white font-black py-3 rounded-xl uppercase"
          >
            Войти
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050505] text-white p-6">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-black uppercase mb-8">🔐 Admin Panel</h1>

        {/* Создание ключа */}
        <div className="bg-gray-900 p-6 rounded-2xl border border-gray-800 mb-6">
          <h2 className="text-lg font-bold mb-4">Создать лицензию</h2>
          <div className="flex gap-3">
            <input
              type="text"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              placeholder="Имя пользователя"
              className="flex-1 bg-black border border-gray-800 text-white p-3 rounded-xl"
            />
            <button
              onClick={createLicense}
              disabled={loading}
              className="bg-emerald-600 hover:bg-emerald-500 px-6 rounded-xl font-bold uppercase"
            >
              {loading ? '...' : 'Создать'}
            </button>
          </div>
          {newKey && (
            <div className="mt-4 bg-black p-4 rounded-xl border border-emerald-500/30">
              <div className="text-xs text-gray-500 mb-1">Ключ скопирован:</div>
              <div className="text-xl font-mono text-emerald-400 tracking-widest">{newKey}</div>
            </div>
          )}
        </div>

        {/* Список лицензий */}
        <div className="bg-gray-900 p-6 rounded-2xl border border-gray-800">
          <h2 className="text-lg font-bold mb-4">Лицензии ({licenses.length})</h2>
          <div className="space-y-2">
            {licenses.map((l) => (
              <div key={l.hash} className="flex items-center justify-between bg-black p-4 rounded-xl border border-gray-800">
                <div>
                  <div className="font-mono text-sm text-emerald-400">{l.key}</div>
                  <div className="text-xs text-gray-500">{l.label} • Создан: {new Date(l.createdAt).toLocaleDateString('ru-RU')}</div>
                  <div className="text-xs text-gray-600">
                    Сессий: {l.sessionsCount} • Последнее использование: {l.lastUsed ? new Date(l.lastUsed).toLocaleString('ru-RU') : 'Никогда'}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => toggleLicense(l.hash, l.active)}
                    className={`px-3 py-1 rounded text-xs font-bold uppercase ${l.active ? 'bg-red-600/20 text-red-400 hover:bg-red-600/40' : 'bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/40'}`}
                  >
                    {l.active ? 'Отозвать' : 'Активировать'}
                  </button>
                  <button
                    onClick={() => deleteLicense(l.hash)}
                    className="px-3 py-1 rounded text-xs font-bold uppercase bg-gray-800 text-gray-400 hover:bg-red-900 hover:text-red-400"
                  >
                    Удалить
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
