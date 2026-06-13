'use client';

import { useEffect, useState } from 'react';
import { EmailPreview } from '@/components/EmailPreview/EmailPreview';
import type { RunResult } from '@/types/pipeline';
import styles from './email.module.css';

export default function EmailPage() {
  const [result, setResult] = useState<RunResult | null>(null);

  useEffect(() => {
    fetch('/api/results')
      .then(r => r.ok ? r.json() : null)
      .then(setResult);
  }, []);

  return (
    <main className={styles.main}>
      <nav className={styles.nav}>
        <a href="/results" className={styles.backLink}>
          <span className="material-symbols-outlined">arrow_back</span>
          Back to Results
        </a>
      </nav>
      <div className={styles.content}>
        {result
          ? <EmailPreview emailText={result.emailText} />
          : <p className={styles.loading}>Loading…</p>
        }
      </div>
    </main>
  );
}
