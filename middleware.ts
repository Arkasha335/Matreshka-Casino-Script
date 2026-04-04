import { NextRequest, NextResponse } from 'next/server';
import { jwtVerify } from 'jose';
import { get } from '@vercel/edge-config';

const SECRET = process.env.JWT_SECRET || 'matreshka-quantum-secret-2026';

export async function middleware(req: NextRequest) {
  const token = req.cookies.get('mq_token')?.value;
  const pathname = req.nextUrl.pathname;

  // /welcome — возвращает приветствие из Edge Config
  if (pathname === '/welcome') {
    const greeting = await get('greeting');
    return NextResponse.json(greeting);
  }

  // /login — всегда доступен
  if (pathname === '/login') {
    if (token) {
      try {
        await jwtVerify(token, new TextEncoder().encode(SECRET));
        return NextResponse.redirect(new URL('/', req.url));
      } catch {
        return NextResponse.next();
      }
    }
    return NextResponse.next();
  }

  // /api/auth/verify — всегда доступен
  if (pathname.startsWith('/api/auth/')) {
    return NextResponse.next();
  }

  // /admin - всегда доступен (защищен внутри)
  if (pathname.startsWith('/admin')) {
    return NextResponse.next();
  }

  // Проверка токена для всех остальных страниц
  if (!token) {
    return NextResponse.redirect(new URL('/login', req.url));
  }

  try {
    await jwtVerify(token, new TextEncoder().encode(SECRET));
    return NextResponse.next();
  } catch {
    const res = NextResponse.redirect(new URL('/login', req.url));
    res.cookies.delete('mq_token');
    return res;
  }
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|api/license).*)'],
};
