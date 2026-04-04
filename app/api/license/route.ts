import { NextRequest, NextResponse } from 'next/server';
import { generateLicenseKey, hashKey } from '@/lib/license-gen';
import { get } from '@vercel/edge-config';

const ADMIN_SECRET = process.env.ADMIN_SECRET || 'admin-default';
const API_TOKEN = process.env.VERCEL_API_TOKEN;
const TEAM_ID = process.env.VERCEL_TEAM_ID;
const EDGE_CONFIG_ID = 'ecfg_1ueolsdjxfebxapzihx0yhsq84ug';

interface LicenseEntry {
  key: string;
  hash: string;
  label: string;
  createdAt: number;
  active: boolean;
  lastUsed: number | null;
  sessionsCount: number;
}

function verifyAdmin(req: NextRequest): boolean {
  const auth = req.headers.get('authorization');
  if (!auth || !auth.startsWith('Bearer ')) return false;
  return auth.slice(7) === ADMIN_SECRET;
}

async function edgeConfigWrite(newKeys: LicenseEntry[]) {
  let url = `https://api.vercel.com/v1/edge-config/${EDGE_CONFIG_ID}/items`;
  if (TEAM_ID) {
    url += `?teamId=${TEAM_ID}`;
  }

  const body = JSON.stringify({
    items: {
      keys: newKeys,
    },
  });

  const res = await fetch(url, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${API_TOKEN}`,
      'Content-Type': 'application/json',
    },
    body,
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Edge Config write failed: ${res.status} ${errText}`);
  }

  return res;
}

export async function GET(req: NextRequest) {
  if (!verifyAdmin(req)) return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
  try {
    const data = await get('keys');
    const keys: LicenseEntry[] = Array.isArray(data) ? (data as unknown as LicenseEntry[]) : [];
    return NextResponse.json({ keys });
  } catch (e: any) {
    return NextResponse.json({ error: 'Read failed: ' + (e.message || String(e)) }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  if (!verifyAdmin(req)) return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
  try {
    const { label } = await req.json();
    const key = generateLicenseKey();
    const hash = hashKey(key);
    const existing: LicenseEntry[] = (await get('keys') as unknown as LicenseEntry[]) || [];
    const newEntry: LicenseEntry = {
      key, hash, label: label || 'Unnamed',
      createdAt: Date.now(), active: true, lastUsed: null, sessionsCount: 0
    };
    const allKeys = [...existing, newEntry];
    await edgeConfigWrite(allKeys);
    return NextResponse.json({ key, label });
  } catch (e: any) {
    console.error('License POST error:', e.message);
    return NextResponse.json({ error: 'Write failed: ' + e.message }, { status: 500 });
  }
}

export async function PATCH(req: NextRequest) {
  if (!verifyAdmin(req)) return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
  try {
    const { hash: targetHash, active } = await req.json();
    const existing: LicenseEntry[] = (await get('keys') as unknown as LicenseEntry[]) || [];
    const updated = existing.map((l) => l.hash === targetHash ? { ...l, active } : l);
    await edgeConfigWrite(updated);
    return NextResponse.json({ success: true });
  } catch (e: any) {
    return NextResponse.json({ error: 'Update failed: ' + e.message }, { status: 500 });
  }
}

export async function DELETE(req: NextRequest) {
  if (!verifyAdmin(req)) return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
  try {
    const { hash: targetHash } = await req.json();
    const existing: LicenseEntry[] = (await get('keys') as unknown as LicenseEntry[]) || [];
    const updated = existing.filter((l) => l.hash !== targetHash);
    await edgeConfigWrite(updated);
    return NextResponse.json({ success: true });
  } catch (e: any) {
    return NextResponse.json({ error: 'Delete failed: ' + e.message }, { status: 500 });
  }
}
