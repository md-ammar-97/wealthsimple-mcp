import type { Metadata } from 'next';
import '../styles/tokens.css';
import '../styles/global.css';
import '../styles/print.css';

export const metadata: Metadata = {
  title: 'Weekly Review Pulse — Wealthsimple Canada',
  description: 'Turn app reviews into a 250-word product insight note every week.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
