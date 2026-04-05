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
    console.log('Input key:', key.substring(0, 6) + '...' + key.substring(key.length - 4));
    console.log('Input key length:', key.length);
    const inputHash = hashKey(key);

    const data = await get('keys');
    console.log('Edge Config keys type:', typeof data, 'isArray:', Array.isArray(data));

    const keys: LicenseEntry[] = Array.isArray(data) ? (data as unknown as LicenseEntry[]) : [];

    if (keys.length === 0) {
      console.warn('No keys found in Edge Config');
      return NextResponse.json({ valid: false, error: 'Система не настроена' }, { status: 401 });
    }

    console.log('Total keys in config:', keys.length);

    const license = keys.find((l) => l.hash === inputHash && l.active === true);

    if (!license) {
      console.warn('License not found. Input hash:', inputHash.substring(0, 10));
      console.log('Stored hashes:', keys.map(k => k.hash.substring(0, 10)));
      return NextResponse.json({ valid: false, error: 'Недействительный ключ' }, { status: 401 });
    }

    const token = await new SignJWT({ key: inputHash, label: license.label })
      .setProtectedHeader({ alg: 'HS256' })
      .setExpirationTime('24h')
      .sign(new TextEncoder().encode(SECRET));

    return NextResponse.json({ valid: true, token, label: license.label });
  } catch (error: any) {
    console.error('Auth Error:', error.message);
    return NextResponse.json({ valid: false, error: 'Server error' }, { status: 500 });
  }
}