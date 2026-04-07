import { NextRequest, NextResponse } from 'next/server';
import { hashKey } from '@/lib/license-gen';
import { SignJWT } from 'jose';

const SECRET = process.env.JWT_SECRET || 'matreshka-quantum-secret-2026';
const API_TOKEN = process.env.VERCEL_API_TOKEN;
const TEAM_ID = process.env.VERCEL_TEAM_ID;
const EDGE_CONFIG_ID = 'ecfg_1ueolsdjxfebxapzihx0yhsq84ug';

export async function POST(req: NextRequest) {
  try {
    const { key } = await req.json();
    const inputHash = hashKey(key);

    let url = `https://api.vercel.com/v1/edge-config/${EDGE_CONFIG_ID}/items/keys`;
    if (TEAM_ID) url += `?teamId=${TEAM_ID}`;

    const res = await fetch(url, {
      headers: { 'Authorization': `Bearer ${API_TOKEN}` },
    });

    if (res.status === 404) {
      return NextResponse.json({ valid: false, error: 'Система не настроена' }, { status: 401 });
    }
    if (!res.ok) {
      console.error('Edge Config read failed:', res.status);
      return NextResponse.json({ valid: false, error: 'Server error' }, { status: 500 });
    }

    const data = await res.json();
    const keys = data.result?.value || [];

    const license = keys.find((l: any) => l.hash === inputHash && l.active === true);

    if (!license) {
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