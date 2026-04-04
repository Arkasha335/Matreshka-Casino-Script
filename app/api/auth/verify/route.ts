import { NextRequest, NextResponse } from 'next/server';
import { hashKey } from '@/lib/license-gen';
import { get } from '@vercel/edge-config';
import { SignJWT } from 'jose';

const SECRET = process.env.JWT_SECRET || 'matreshka-quantum-secret-2026';

interface LicenseEntry {
  key: string;
  hash: string;
  label: string;
  createdAt: number;
  active: boolean;
  lastUsed: number | null;
  sessionsCount: number;
}

export async function POST(req: NextRequest) {
  try {
    const { key } = await req.json();
    const inputHash = hashKey(key);

    const data = await get('keys');
    const keys: LicenseEntry[] = Array.isArray(data) ? (data as unknown as LicenseEntry[]) : [];

    const license = keys.find((l) => l.hash === inputHash && l.active === true);

    if (!license) {
      return NextResponse.json({ valid: false, error: 'Недействительный ключ' }, { status: 401 });
    }

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
