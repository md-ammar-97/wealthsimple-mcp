'use client';

import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { THEME_CODES, THEME_CATEGORIES } from '@/types/pipeline';
import styles from './ThemeLegendDrawer.module.css';

const THEME_DESCRIPTIONS: Record<string, string> = {
  'Account access & login':                'Login failures, session expiry, 2FA issues, locked accounts',
  'Onboarding & verification':             'ID verification, KYC delays, account setup friction',
  'Transfers, deposits & withdrawals':     'Failed transfers, slow deposits, withdrawal holds',
  'Trading, investing & crypto':           'Order execution, portfolio view, crypto feature issues',
  'App performance, bugs & reliability':   'Crashes, slow loads, UI errors, data not refreshing',
  'Customer support & issue resolution':   'Support response time, ticket resolution, agent quality',
  'Fees, pricing & product communication': 'Fee transparency, pricing changes, product updates',
  'Tax, statements & documents':           'T5/T3 forms, statements, TFSA/RRSP reporting',
};

const THEMES = Object.keys(THEME_CODES);

type Props = { open: boolean; onClose: () => void; };

export function ThemeLegendDrawer({ open, onClose }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className={styles.backdrop}
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.32 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={onClose}
            aria-hidden
          />
          <motion.aside
            className={styles.drawer}
            role="dialog"
            aria-label="Theme legend"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.5, ease: [0.05, 0.7, 0.1, 1.0] }}
          >
            <header className={styles.header}>
              <h2 className={styles.title}>Theme Legend</h2>
              <button
                className={styles.closeBtn}
                onClick={onClose}
                aria-label="Close theme legend"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </header>

            <ul className={styles.list}>
              {THEMES.map(theme => {
                const code = THEME_CODES[theme];
                const category = THEME_CATEGORIES[theme];
                const desc = THEME_DESCRIPTIONS[theme] ?? '';
                return (
                  <li key={theme} className={styles.row}>
                    <div
                      className={styles.dot}
                      style={{ background: `var(--color-theme-${category})` }}
                      aria-hidden
                    />
                    <div className={styles.rowContent}>
                      <div className={styles.rowTop}>
                        <span
                          className={styles.codeBadge}
                          style={{ background: `var(--color-theme-${category})` }}
                        >
                          {code}
                        </span>
                        <span className={styles.label}>{theme}</span>
                      </div>
                      <p className={styles.desc}>{desc}</p>
                    </div>
                  </li>
                );
              })}
            </ul>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
