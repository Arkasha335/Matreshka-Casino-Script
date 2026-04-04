import crypto from 'crypto';

export function generateLicenseKey(): string {
  const segments = Array.from({ length: 4 }, () =>
    Array.from({ length: 4 }, () =>
      'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'[Math.floor(Math.random() * 32)]
    ).join('')
  );
  return `MTQ-${segments.join('-')}`;
}

export function hashKey(key: string): string {
  return crypto.createHash('sha256').update(key).digest('hex');
}

export function verifyKey(input: string, stored: string): boolean {
  return hashKey(input.toUpperCase().trim()) === stored;
}
