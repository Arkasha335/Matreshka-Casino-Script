import { NextRequest, NextResponse } from 'next/server';
import { generateLicenseKey, hashKey } from '@/lib/license-gen';
import { get } from '@vercel/edge-config';

const ADMIN_SECRET = process.env.ADMIN_SECRET || 'admin-default';
const API_TOKEN = process.env.VERCEL_API_TOKEN;
const TEAM_ID = process.env.VERCEL_TEAM_ID;
const EDGE_CONFIG_ID = process.env.EDGE_CONFIG?.split('/')[4]?.split('?')[0] || 'ecfg_1ueolsdjxfebxapzihx0yhsq84ug';

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

async function edgeConfigWrite(items: Record<string, unknown>) {
  const url = `https://api.vercel.com/v1/edge-config/${EDGE_CONFIG_ID}/items?teamId=${TEAM_ID}`;
  const res = await fetch(url, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${API_TOKEN}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ items }),
  });
  if (!res.ok) throw new Error(`Edge Config write failed: ${res.status}`);
}

export async function GET(req: NextRequest) {
  if (!verifyAdmin(req)) return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
  try {
    const data = await get('keys');
    const keys: LicenseEntry[] = Array.isArray(data) ? (data as unknown as LicenseEntry[]) : [];
    return NextResponse.json({ keys });
  } catch {
    return NextResponse.json({ error: 'Read failed' }, { status: 500 });
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
    await edgeConfigWrite({ keys: [...existing, newEntry] });
    return NextResponse.json({ key, label });
  } catch {
    return NextResponse.json({ error: 'Write failed' }, { status: 500 });
  }
}

export async function PATCH(req: NextRequest) {
  if (!verifyAdmin(req)) return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
  try {
    const { hash: targetHash, active } = await req.json();
    const existing: LicenseEntry[] = (await get('keys') as unknown as LicenseEntry[]) || [];
    const updated = existing.map((l) => l.hash === targetHash ? { ...l, active } : l);
    await edgeConfigWrite({ keys: updated });
    return NextResponse.json({ success: true });
  } catch {
    return NextResponse.json({ error: 'Update failed' }, { status: 500 });
  }
}

export async function DELETE(req: NextRequest) {
  if (!verifyAdmin(req)) return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
  try {
    const { hash: targetHash } = await req.json();
    const existing: LicenseEntry[] = (await get('keys') as unknown as LicenseEntry[]) || [];
    const updated = existing.filter((l) => l.hash !== targetHash);
    await edgeConfigWrite({ keys: updated });
    return NextResponse.json({ success: true });
  } catch {
    return NextResponse.json({ error: 'Delete failed' }, { status: 500 });
  }
}
