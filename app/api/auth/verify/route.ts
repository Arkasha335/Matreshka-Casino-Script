import { NextRequest, NextResponse } from 'next/server';
import { hashKey } from '@/lib/license-gen';
import * as fs from 'fs';
import * as path from 'path';
import { SignJWT } from 'jose';

const SECRET = process.env.JWT_SECRET || 'matreshka-quantum-secret-2026';

export async function POST(req: NextRequest) {
  const { key } = await req.json();
  const inputHash = hashKey(key);

  const licensesPath = path.join(process.cwd(), 'lib', 'licenses.json');
  const data = JSON.parse(fs.readFileSync(licensesPath, 'utf-8'));

  const license = data.keys.find(
    (l: any) => l.hash === inputHash && l.active === true
  );

  if (!license) {
    return NextResponse.json({ valid: false, error: 'Недействительный ключ' }, { status: 401 });
  }

  // Обновить lastUsed
  license.lastUsed = Date.now();
  license.sessionsCount++;
  fs.writeFileSync(licensesPath, JSON.stringify(data, null, 2));

  // Создать JWT
  const token = await new SignJWT({ key: inputHash, label: license.label })
    .setProtectedHeader({ alg: 'HS256' })
    .setExpirationTime('24h')
    .sign(new TextEncoder().encode(SECRET));

  return NextResponse.json({ valid: true, token, label: license.label });
}
