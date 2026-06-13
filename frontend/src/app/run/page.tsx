'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { fadeUp } from '@/motion/variants';
import { UploadZone } from '@/components/UploadZone/UploadZone';
import { PipelineTracker } from '@/components/PipelineTracker/PipelineTracker';
import { usePipelineStatus } from '@/hooks/usePipelineStatus';
import styles from './run.module.css';

export default function RunPage() {
  const router = useRouter();
  const [runId, setRunId] = useState<string | null>(null);
  const [uploadedFile, setUploadedFile] = useState<{ name: string; rowCount: number } | null>(null);
  const [launching, setLaunching] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const pipelineStatus = usePipelineStatus(runId);

  const handleUpload = useCallback(async (file: File, rowCount: number) => {
    setUploadedFile({ name: file.name, rowCount });

    const form = new FormData();
    form.append('file', file);
    await fetch('/api/upload', { method: 'POST', body: form });
  }, []);

  const handleRun = useCallback(async () => {
    setLaunching(true);
    setRunError(null);
    try {
      const res = await fetch('/api/run', { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(err.error ?? 'Pipeline failed to start');
      }
      const { runId: id } = await res.json();
      setRunId(id);
    } catch (e) {
      setRunError((e as Error).message);
    } finally {
      setLaunching(false);
    }
  }, []);

  const isRunning = !!runId && !pipelineStatus.completed && !pipelineStatus.error;
  const isDone    = !!runId && pipelineStatus.completed;

  return (
    <main className={styles.main}>
      <nav className={styles.topNav}>
        <a href="/" className={styles.backLink}>
          <span className="material-symbols-outlined">arrow_back</span>
          Back
        </a>
        <h1 className={styles.pageTitle}>Run Pipeline</h1>
      </nav>

      <div className={styles.layout}>
        {/* Left: upload zone */}
        <section className={styles.uploadPanel} aria-label="Upload CSV">
          <UploadZone onUpload={handleUpload} disabled={isRunning || isDone} />

          {uploadedFile && !runId && (
            <motion.div
              className={styles.runCta}
              variants={fadeUp}
              initial="hidden"
              animate="visible"
            >
              <button
                className={styles.runBtn}
                onClick={handleRun}
                disabled={launching}
              >
                {launching
                  ? <span className="material-symbols-outlined" style={{ animation: 'spin 1s linear infinite' }}>progress_activity</span>
                  : <span className="material-symbols-outlined">play_arrow</span>
                }
                {launching ? 'Starting…' : 'Run Pipeline'}
              </button>
              {runError && <p className={styles.runError}>{runError}</p>}
            </motion.div>
          )}
        </section>

        {/* Right: pipeline tracker */}
        <section className={styles.trackerPanel} aria-label="Pipeline progress">
          <PipelineTracker steps={pipelineStatus.steps} />

          {pipelineStatus.error && (
            <motion.div className={styles.errorCard} variants={fadeUp} initial="hidden" animate="visible">
              <span className="material-symbols-outlined" style={{ color: 'var(--md-sys-color-error)' }}>error</span>
              <p>{pipelineStatus.error}</p>
              <button className={styles.retryBtn} onClick={() => { setRunId(null); setRunError(null); }}>
                Retry
              </button>
            </motion.div>
          )}

          <AnimatePresence>
            {isDone && (
              <motion.div
                className={styles.viewResultsCta}
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                exit={{ opacity: 0 }}
              >
                <button className={styles.viewBtn} onClick={() => router.push('/results')}>
                  <span className="material-symbols-outlined">open_in_new</span>
                  View Results
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </section>
      </div>
    </main>
  );
}
