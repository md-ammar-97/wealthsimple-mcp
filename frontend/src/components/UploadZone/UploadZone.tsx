'use client';

import { useCallback, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { scaleIn, fadeUp } from '@/motion/variants';
import type { UploadState } from '@/types/pipeline';
import styles from './UploadZone.module.css';

const REQUIRED_HEADERS = ['platform', 'rating', 'text', 'date'];

async function estimateRows(file: File): Promise<number> {
  const sample = await file.slice(0, 8192).text();
  const lines = sample.split('\n').filter(l => l.trim()).length;
  const fraction = 8192 / file.size;
  return Math.round((lines - 1) / fraction);
}

async function validateCsv(file: File): Promise<{ valid: true; rowCount: number } | { valid: false; error: string }> {
  if (!file.name.endsWith('.csv')) return { valid: false, error: 'File must be a .csv' };
  const header = await file.slice(0, 512).text();
  const firstLine = header.split('\n')[0].toLowerCase();
  const missing = REQUIRED_HEADERS.filter(h => !firstLine.includes(h));
  if (missing.length) return { valid: false, error: `Missing columns: ${missing.join(', ')}` };
  const rowCount = await estimateRows(file);
  return { valid: true, rowCount };
}

type Props = {
  onUpload: (file: File, rowCount: number) => void;
  disabled?: boolean;
};

export function UploadZone({ onUpload, disabled }: Props) {
  const [state, setState] = useState<UploadState>({ status: 'idle' });
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(async (file: File) => {
    setState({ status: 'validating' });
    const result = await validateCsv(file);
    if (!result.valid) {
      setState({ status: 'invalid', error: result.error });
      return;
    }
    setState({ status: 'valid', filename: file.name, rowCount: result.rowCount });
    onUpload(file, result.rowCount);
  }, [onUpload]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const onInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const isValid = state.status === 'valid';
  const isError = state.status === 'invalid';

  return (
    <div
      className={`${styles.root} ${dragOver ? styles.dragOver : ''} ${isError ? styles.hasError : ''} ${disabled ? styles.disabled : ''}`}
      onDragOver={e => { e.preventDefault(); if (!disabled) setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={disabled ? undefined : onDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      role="button"
      tabIndex={0}
      aria-label="Upload reviews CSV file"
      onKeyDown={e => e.key === 'Enter' && !disabled && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className={styles.hiddenInput}
        onChange={onInputChange}
        aria-hidden
      />

      <AnimatePresence mode="wait">
        {state.status === 'idle' || state.status === 'validating' ? (
          <motion.div
            key="idle"
            className={styles.placeholder}
            variants={scaleIn}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
          >
            <span className={`material-symbols-outlined ${styles.uploadIcon}`}>upload_file</span>
            <p className={styles.headline}>Drop reviews.csv here</p>
            <p className={styles.sub}>or click to browse</p>
            <div className={styles.columnHint}>
              <span className={styles.hintLabel}>Required:</span>
              <span className={styles.hintValue}>platform, rating, title, text, date</span>
            </div>
            <div className={styles.columnHint}>
              <span className={styles.hintLabel}>Optional:</span>
              <span className={styles.hintValue}>app_version, country, helpful_votes</span>
            </div>
          </motion.div>
        ) : isError ? (
          <motion.div
            key="error"
            className={styles.errorState}
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
          >
            <span className={`material-symbols-outlined ${styles.errorIcon}`}>error</span>
            <p className={styles.errorText}>{(state as { status: 'invalid'; error: string }).error}</p>
            <button
              className={styles.retryBtn}
              onClick={e => { e.stopPropagation(); setState({ status: 'idle' }); }}
            >
              Try another file
            </button>
          </motion.div>
        ) : isValid ? (
          <motion.div
            key="valid"
            className={styles.validState}
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
            onClick={e => e.stopPropagation()}
          >
            <span className={`material-symbols-outlined ${styles.successIcon}`}>check_circle</span>
            <div className={styles.fileChip}>
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>description</span>
              {(state as { status: 'valid'; filename: string; rowCount: number }).filename}
            </div>
            <p className={styles.rowCount}>
              ~{(state as { status: 'valid'; filename: string; rowCount: number }).rowCount.toLocaleString()} rows detected
            </p>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
