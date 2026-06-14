'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import styles from './AtlasNav.module.css';

const NAV_LINKS = [
  { href: '/analytics', label: 'Wealthsimple Analytics' },
  { href: '/upload',    label: 'Analyze Any App' },
];

export function AtlasNav() {
  const path = usePathname();
  return (
    <nav className={styles.nav} role="navigation" aria-label="Main">
      <div className={styles.inner}>
        <Link href="/" className={styles.brand}>
          <span className={styles.brandIcon}>⚡</span>
          <span className={styles.brandName}>Review Pulse</span>
        </Link>

        <ul className={styles.links} role="list">
          {NAV_LINKS.map(({ href, label }) => (
            <li key={href}>
              <Link
                href={href}
                className={`${styles.link} ${path.startsWith(href) ? styles.active : ''}`}
              >
                {label}
              </Link>
            </li>
          ))}
        </ul>

        <div className={styles.actions}>
          <Link href="/upload" className={`btn btn-default ${styles.ctaBtn}`}>
            + Analyze CSV
          </Link>
        </div>
      </div>
    </nav>
  );
}
