'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await fetch('/api/auth/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key }),
      });

      const data = await res.json();

      if (data.valid) {
        document.cookie = `mq_token=${data.token}; path=/; max-age=86400; SameSite=Strict`;
        router.push('/');
      } else {
        setError(data.error || 'Недействительный ключ');
      }
    } catch {
      setError('Ошибка соединения');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center p-4 font-sans text-white">
      <div className="max-w-md w-full bg-gray-900 p-8 rounded-2xl border border-gray-800 shadow-2xl">
        <h1 className="text-2xl font-black text-white mb-2 text-center tracking-widest uppercase">
          Matreshka Quantum
        </h1>
        <p className="text-gray-500 text-center text-sm mb-8">Введите лицензионный ключ</p>

        <form onSubmit={handleLogin} className="space-y-6">
          <div>
            <input
              type="text"
              value={key}
              onChange={(e) => setKey(e.target.value.toUpperCase())}
              className="w-full bg-black border border-gray-800 text-emerald-400 text-2xl p-4 rounded-xl focus:outline-none focus:border-emerald-500 transition-colors font-mono text-center tracking-[0.3em] uppercase"
              placeholder="MTQ-XXXX-XXXX-XXXX"
              maxLength={19}
            />
          </div>

          {error && (
            <div className="text-red-500 text-sm text-center font-bold">{error}</div>
          )}

          <button
            type="submit"
            disabled={loading || key.length < 19}
            className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-black py-4 rounded-xl uppercase tracking-widest disabled:opacity-50 transition-colors"
          >
            {loading ? 'Проверка...' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  );
}
