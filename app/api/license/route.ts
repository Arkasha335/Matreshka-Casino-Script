import { NextRequest, NextResponse } from 'next/server';
import { generateLicenseKey, hashKey } from '@/lib/license-gen';
import * as fs from 'fs';
import * as path from 'path';

const ADMIN_SECRET = process.env.ADMIN_SECRET || 'admin-default-change-me';

function verifyAdmin(req: NextRequest): boolean {
  const auth = req.headers.get('authorization');
  if (!auth || !auth.startsWith('Bearer ')) return false;
  return auth.slice(7) === ADMIN_SECRET;
}

// GET — список всех лицензий
export async function GET(req: NextRequest) {
  if (!verifyAdmin(req)) return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });

  const licensesPath = path.join(process.cwd(), 'lib', 'licenses.json');
  const data = JSON.parse(fs.readFileSync(licensesPath, 'utf-8'));
  return NextResponse.json(data);
}

// POST — создать новую лицензию
export async function POST(req: NextRequest) {
  if (!verifyAdmin(req)) return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });

  const { label } = await req.json();
  const key = generateLicenseKey();
  const hash = hashKey(key);

  const licensesPath = path.join(process.cwd(), 'lib', 'licenses.json');
  const data = JSON.parse(fs.readFileSync(licensesPath, 'utf-8'));

  data.keys.push({
    key,
    hash,
    label: label || 'Unnamed',
    createdAt: Date.now(),
    active: true,
    lastUsed: null,
    sessionsCount: 0,
  });

  fs.writeFileSync(licensesPath, JSON.stringify(data, null, 2));
  return NextResponse.json({ key, label });
}

// PATCH — отозвать/активировать лицензию
export async function PATCH(req: NextRequest) {
  if (!verifyAdmin(req)) return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });

  const { hash: targetHash, active } = await req.json();

  const licensesPath = path.join(process.cwd(), 'lib', 'licenses.json');
  const data = JSON.parse(fs.readFileSync(licensesPath, 'utf-8'));

  const license = data.keys.find((l: any) => l.hash === targetHash);
  if (!license) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  license.active = active;
  fs.writeFileSync(licensesPath, JSON.stringify(data, null, 2));
  return NextResponse.json({ success: true });
}

// DELETE — удалить лицензию
export async function DELETE(req: NextRequest) {
  if (!verifyAdmin(req)) return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });

  const { hash: targetHash } = await req.json();

  const licensesPath = path.join(process.cwd(), 'lib', 'licenses.json');
  const data = JSON.parse(fs.readFileSync(licensesPath, 'utf-8'));

  data.keys = data.keys.filter((l: any) => l.hash !== targetHash);
  fs.writeFileSync(licensesPath, JSON.stringify(data, null, 2));
  return NextResponse.json({ success: true });
}
