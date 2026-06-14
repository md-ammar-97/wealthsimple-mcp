import styles from './RunSummaryChip.module.css';
import type { RunResult } from '@/types/pipeline';

type Props = { result: RunResult };

export function RunSummaryChip({ result }: Props) {
  const ts = result.generatedAt
    ? new Date(result.generatedAt).toLocaleString('en-CA', { timeZone: 'UTC', dateStyle: 'short', timeStyle: 'short' }) + ' UTC'
    : '';
  const variant = result.lowDataWarning ? styles.warning : styles.success;

  return (
    <div className={`${styles.chip} ${variant}`} role="status">
      <span className="material-symbols-outlined" aria-hidden>
        {result.lowDataWarning ? 'warning' : 'check_circle'}
      </span>
      <span>
        {result.reviewCount} reviews · {(result.themes ?? []).length} themes · {result.wordCount} words
        {ts && ` · ${ts}`}
      </span>
    </div>
  );
}
