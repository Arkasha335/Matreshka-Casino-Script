import type { Metadata } from 'next';
import { Manrope, Space_Grotesk, JetBrains_Mono } from 'next/font/google';
import './globals.css';

const manrope = Manrope({
  subsets: ['latin', 'cyrillic'],
  variable: '--font-sans',
  display: 'swap',
});

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin', 'cyrillic'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Matreshka Quantum v14.0 — Obsidian Terminal',
  description: 'Квантовый тактический терминал управления банкроллом Matreshka Quantum v14.0',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={`${manrope.variable} ${spaceGrotesk.variable} ${jetbrainsMono.variable}`}>
      <body className="bg-[#030304] text-neutral-100 antialiased" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
