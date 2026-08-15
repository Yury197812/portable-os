import type { Metadata } from 'next';
import { Inter, Space_Grotesk } from 'next/font/google';
import './globals.css';
import Topbar from '@/components/Topbar';
import Sidebar from '@/components/Sidebar';

const inter = Inter({ subsets: ['latin', 'cyrillic'], variable: '--font-body', display: 'swap' });
const grotesk = Space_Grotesk({ subsets: ['latin'], variable: '--font-head', display: 'swap' });

export const metadata: Metadata = {
  title: 'ArtWeb Studio — Command Center',
  description: 'Каталог моделей с icon-first возможностями и динамическим routing.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={`${inter.variable} ${grotesk.variable}`}>
      <body>
        <div className="app">
          <Topbar />
          <div className="shell">
            <Sidebar />
            <main className="main">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
