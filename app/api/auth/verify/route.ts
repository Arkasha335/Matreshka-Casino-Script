import { NextRequest, NextResponse } from 'next/server';
import { hashKey } from '@/lib/license-gen';
import { get } from '@vercel/edge-config';
import { SignJWT } from 'jose';

const SECRET = process.env.JWT_SECRET || 'matreshka-quantum-secret-2026';

export async function POST(req: NextRequest) {
  try {
    const { key } = await req.json();
    const inputHash = hashKey(key);

    // Читаем из Edge Config
    const data = await get('keys');
    const keys = Array.isArray(data) ? data : [];

    const license = keys.find((l: any) => l.hash === inputHash && l.active === true);

    if (!license) {
      return NextResponse.json({ valid: false, error: 'Недействительный ключ' }, { status: 401 });
    }

    // Обновляем lastUsed (запись через API, здесь только чтение для верификации)
    // Для простоты не обновляем lastUsed при каждом входе, чтобы не нагружать API
    // Или можно добавить асинхронное обновление в фоне

    const token = await new SignJWT({ key: inputHash, label: license.label })
      .setProtectedHeader({ alg: 'HS256' })
      .setExpirationTime('24h')
      .sign(new TextEncoder().encode(SECRET));

    return NextResponse.json({ valid: true, token, label: license.label });
  } catch (error) {
    console.error('Auth Error:', error);
    return NextResponse.json({ valid: false, error: 'Server error' }, { status: 500 });
  }
}