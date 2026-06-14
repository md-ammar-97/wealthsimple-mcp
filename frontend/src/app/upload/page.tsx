'use client';

import { useCallback, useRef, useState } from 'react';
import { usePipelineStatus } from '@/hooks/usePipelineStatus';
import styles from './upload.module.css';

/* ─── Types ─────────────────────────────────────── */
type Stage = 'form' | 'running' | 'done' | 'error';

interface ResultData {
  themes:   { rank: number; theme: string; reviewCount: number; avgRating: number }[];
  quotes:   { theme: string; quote: string; rating: number | null; date: string | null }[];
  actions:  { action: string; linkedTheme: string }[];
  noteText: string;
  emailText: string;
  reviewCount: number;
}

const STEP_LABELS = ['Ingest', 'Redact', 'Classify', 'Rank', 'Quotes', 'Actions', 'Note', 'Email'];
const STEP_ICONS  = ['upload_file', 'policy', 'category', 'leaderboard', 'format_quote', 'lightbulb', 'article', 'email'];

/* ─── CSV validation ────────────────────────────── */
const REQUIRED_HEADERS = ['platform', 'rating', 'title', 'text', 'date'];

async function validateCsv(file: File): Promise<string | null> {
  if (!file.name.endsWith('.csv')) return 'File must be a .csv';
  const header = await file.slice(0, 512).text();
  const firstLine = header.split('\n')[0].toLowerCase();
  const missing = REQUIRED_HEADERS.filter(h => !firstLine.includes(h));
  return missing.length ? `Missing columns: ${missing.join(', ')}` : null;
}

/* ─── Page ──────────────────────────────────────── */
export default function UploadPage() {
  const [stage, setStage] = useState<Stage>('form');
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ResultData | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvError, setCsvError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [email, setEmail] = useState('');
  const [appName, setAppName] = useState('');
  const [launching, setLaunching] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const pipelineStatus = usePipelineStatus(runId);

  /* Poll results when pipeline completes */
  const fetchResults = useCallback(async () => {
    for (let attempt = 0; attempt < 5; attempt++) {
      await new Promise(r => setTimeout(r, attempt * 500));
      try {
        const r = await fetch('/api/results');
        const data = await r.json();
        if (r.ok && !data.error) {
          setResult({
            themes:      (data.themes   ?? []),
            quotes:      (data.quotes   ?? []),
            actions:     (data.actions  ?? []),
            noteText:    data.noteText  ?? '',
            emailText:   data.emailText ?? '',
            reviewCount: data.reviewCount ?? 0,
          });
          setStage('done');
          return;
        }
        if (r.status !== 503) {
          setError(data.error ?? 'Results unavailable');
          setStage('error');
          return;
        }
      } catch {
        // retry
      }
    }
    setError('Results timed out. The pipeline may still be running.');
    setStage('error');
  }, []);

  /* Watch for pipeline completion */
  const prevCompleted = useRef(false);
  if (stage === 'running' && pipelineStatus.completed && !prevCompleted.current) {
    prevCompleted.current = true;
    fetchResults();
  }
  if (stage === 'running' && pipelineStatus.error && !prevCompleted.current) {
    prevCompleted.current = true;
    setError(pipelineStatus.error);
    setStage('error');
  }

  /* File handling */
  const handleFile = useCallback(async (file: File) => {
    const err = await validateCsv(file);
    if (err) { setCsvError(err); setCsvFile(null); return; }
    setCsvError(null);
    setCsvFile(file);
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  /* Submit */
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile || !email.trim()) return;
    setLaunching(true);
    setError(null);

    try {
      // Upload CSV + metadata
      const form = new FormData();
      form.append('file', csvFile);
      form.append('email', email.trim());
      form.append('appName', appName.trim());
      const uploadRes = await fetch('/api/upload', { method: 'POST', body: form });
      if (!uploadRes.ok) {
        const d = await uploadRes.json().catch(() => ({}));
        throw new Error(d.error ?? 'Upload failed');
      }

      // Start pipeline
      const runRes = await fetch('/api/run', { method: 'POST' });
      if (!runRes.ok) {
        const d = await runRes.json().catch(() => ({}));
        throw new Error(d.error ?? 'Failed to start pipeline');
      }
      const { runId: id } = await runRes.json();
      prevCompleted.current = false;
      setRunId(id);
      setStage('running');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLaunching(false);
    }
  }, [csvFile, email, appName]);

  const reset = () => {
    setStage('form');
    setRunId(null);
    setError(null);
    setResult(null);
    setCsvFile(null);
    setCsvError(null);
    setEmail('');
    setAppName('');
    prevCompleted.current = false;
  };

  /* Progress % */
  const doneCount = pipelineStatus.steps.filter(s => s.state === 'done').length;
  const activeIdx = pipelineStatus.steps.findIndex(s => s.state === 'active');
  const progress = stage === 'done' ? 100
    : doneCount * (100 / 8) + (activeIdx >= 0 ? (100 / 8) * 0.5 : 0);

  return (
    <main className={styles.main}>
      <div className="page-content">
        <header className={styles.header}>
          <h1 className={styles.title}>Analyse Any App</h1>
          <p className={styles.subtitle}>
            Upload a CSV of app store reviews. The pipeline classifies themes, selects quotes, generates actions,
            and emails you the report.
          </p>
        </header>

        {/* ── FORM ── */}
        {stage === 'form' && (
          <form onSubmit={handleSubmit} className={styles.form}>
            <div className={styles.fields}>
              <div className={styles.field}>
                <label className="atlas-label" htmlFor="appName">App name</label>
                <input
                  id="appName"
                  type="text"
                  className="atlas-input"
                  placeholder="e.g. Wealthsimple"
                  value={appName}
                  onChange={e => setAppName(e.target.value)}
                />
              </div>
              <div className={styles.field}>
                <label className="atlas-label" htmlFor="email">
                  Your email <span className={styles.required}>*</span>
                </label>
                <input
                  id="email"
                  type="email"
                  className="atlas-input"
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                />
              </div>
            </div>

            {/* Drop zone */}
            <div
              className={`${styles.dropzone} ${dragOver ? styles.dzOver : ''} ${csvError ? styles.dzError : ''} ${csvFile ? styles.dzValid : ''}`}
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              aria-label="Upload CSV file"
              onKeyDown={e => e.key === 'Enter' && fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                className={styles.hiddenInput}
                onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
                aria-hidden
              />

              {csvFile ? (
                <div className={styles.dzContent}>
                  <span className="material-symbols-outlined" style={{ color: 'var(--color-success)', fontSize: 32 }}>check_circle</span>
                  <div>
                    <p className={styles.dzFilename}>{csvFile.name}</p>
                    <p className={styles.dzSub}>{(csvFile.size / 1024).toFixed(0)} KB · Click to change</p>
                  </div>
                </div>
              ) : (
                <div className={styles.dzContent}>
                  <span className="material-symbols-outlined" style={{ color: 'var(--atlas-n100)', fontSize: 36 }}>upload_file</span>
                  <div>
                    <p className={styles.dzHeadline}>Drop reviews.csv here</p>
                    <p className={styles.dzSub}>or click to browse</p>
                    <p className={styles.dzHint}>Required columns: platform, rating, title, text, date</p>
                  </div>
                </div>
              )}
            </div>
            {csvError && (
              <div className="section-msg section-msg-error" style={{ marginTop: 'var(--space-2)' }}>
                <span className="material-symbols-outlined">error</span>
                <span>{csvError}</span>
              </div>
            )}

            {error && (
              <div className="section-msg section-msg-error">
                <span className="material-symbols-outlined">error</span>
                <span>{error}</span>
              </div>
            )}

            <div className={styles.submitRow}>
              <button
                type="submit"
                className="btn btn-primary btn-lg"
                disabled={!csvFile || !email.trim() || launching}
              >
                {launching
                  ? <span className="material-symbols-outlined" style={{ animation: 'spin 1s linear infinite' }}>progress_activity</span>
                  : <span className="material-symbols-outlined">play_arrow</span>
                }
                {launching ? 'Starting…' : 'Run Pipeline'}
              </button>
            </div>
          </form>
        )}

        {/* ── RUNNING ── */}
        {stage === 'running' && (
          <div className={styles.progressSection}>
            <div className={styles.progressHeader}>
              <p className={styles.progressLabel}>Analysing {appName || 'your reviews'}…</p>
              <span className={styles.progressPct}>{Math.round(progress)}%</span>
            </div>
            <div className="atlas-progress-track">
              <div className="atlas-progress-fill" style={{ width: `${progress}%` }} />
            </div>

            <div className={styles.stepGrid}>
              {pipelineStatus.steps.map((step, i) => (
                <div key={step.id} className={`${styles.stepCell} ${styles[`step_${step.state}`]}`}>
                  <span className="material-symbols-outlined">{STEP_ICONS[i]}</span>
                  <span>{STEP_LABELS[i]}</span>
                  {step.state === 'active' && (
                    <span className="material-symbols-outlined" style={{ fontSize: 14, animation: 'spin 1s linear infinite' }}>progress_activity</span>
                  )}
                  {step.state === 'done' && (
                    <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--color-success)' }}>check</span>
                  )}
                </div>
              ))}
            </div>
            <p className={styles.progressNote}>
              This usually takes 1–2 minutes. A report will be emailed to <strong>{email}</strong>.
            </p>
          </div>
        )}

        {/* ── ERROR ── */}
        {stage === 'error' && (
          <div className={styles.errorSection}>
            <div className="section-msg section-msg-error">
              <span className="material-symbols-outlined">error</span>
              <span>{error}</span>
            </div>
            <button className="btn btn-default" onClick={reset} style={{ marginTop: 'var(--space-4)' }}>
              <span className="material-symbols-outlined">restart_alt</span>
              Try again
            </button>
          </div>
        )}

        {/* ── RESULTS ── */}
        {stage === 'done' && result && (
          <div className={styles.results}>
            <div className="section-msg section-msg-success" style={{ marginBottom: 'var(--space-6)' }}>
              <span className="material-symbols-outlined">mark_email_read</span>
              <span>Report emailed to <strong>{email}</strong> · {result.reviewCount} reviews analysed</span>
              <button
                className="btn btn-subtle"
                onClick={reset}
                style={{ marginLeft: 'auto' }}
              >
                <span className="material-symbols-outlined">restart_alt</span>
                New analysis
              </button>
            </div>

            {/* Themes */}
            <section className={styles.resultSection}>
              <h2 className={styles.resultHeading}>Themes</h2>
              <div className={styles.themesGrid}>
                {result.themes.map(t => (
                  <div key={t.rank} className={`${styles.themeCard} atlas-card`}>
                    <div className={styles.themeRank}>#{t.rank}</div>
                    <h3 className={styles.themeName}>{t.theme}</h3>
                    <div className={styles.themeMeta}>
                      <span><span className="material-symbols-outlined" style={{ fontSize: 14 }}>reviews</span> {t.reviewCount} reviews</span>
                      <span><span className="material-symbols-outlined" style={{ fontSize: 14 }}>star</span> {typeof t.avgRating === 'number' ? t.avgRating.toFixed(1) : '—'}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Quotes */}
            {result.quotes.length > 0 && (
              <section className={styles.resultSection}>
                <h2 className={styles.resultHeading}>Representative Quotes</h2>
                <div className={styles.quoteList}>
                  {result.quotes.map((q, i) => (
                    <div key={i} className={`${styles.quoteCard} atlas-card`}>
                      <span className={`badge badge-blue ${styles.quoteTheme}`}>{q.theme}</span>
                      <blockquote className={styles.quoteText}>"{q.quote}"</blockquote>
                      <div className={styles.quoteMeta}>
                        {q.rating !== null && <span>★ {q.rating}</span>}
                        {q.date && <span>{new Date(q.date).toLocaleDateString()}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Actions */}
            {result.actions.length > 0 && (
              <section className={styles.resultSection}>
                <h2 className={styles.resultHeading}>Recommended Actions</h2>
                <ol className={styles.actionList}>
                  {result.actions.map((a, i) => (
                    <li key={i} className={`${styles.actionItem} atlas-card`}>
                      <div className={styles.actionNum}>{i + 1}</div>
                      <div>
                        <p className={styles.actionText}>{a.action}</p>
                        {a.linkedTheme && (
                          <span className="badge badge-neutral">{a.linkedTheme}</span>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              </section>
            )}

            {/* Pulse note */}
            {result.noteText && (
              <section className={styles.resultSection}>
                <h2 className={styles.resultHeading}>Pulse Note</h2>
                <div className={`${styles.noteCard} atlas-card`}>
                  <pre className={styles.noteText}>{result.noteText}</pre>
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
