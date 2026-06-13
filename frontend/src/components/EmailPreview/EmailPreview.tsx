'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { fadeUp } from '@/motion/variants';
import { useClipboard } from '@/hooks/useClipboard';
import styles from './EmailPreview.module.css';

type Props = {
  emailText: string;
  toAddress?: string;
};

const DEFAULT_SUBJECT = 'Weekly Review Pulse — Wealthsimple Canada';

export function EmailPreview({ emailText, toAddress = 'mohdammar97@gmail.com' }: Props) {
  const [editing, setEditing] = useState(false);
  const [senderName, setSenderName] = useState('[Your Name]');
  const [showSnack, setShowSnack] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { copy, copied } = useClipboard();

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const displayText = emailText.replace('[Your Name]', senderName);

  const handleCopy = () => {
    copy(displayText);
    setShowSnack(true);
    setTimeout(() => setShowSnack(false), 4000);
  };

  return (
    <motion.section
      className={styles.root}
      variants={fadeUp}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: '-32px' }}
      aria-label="Email draft preview"
    >
      <header className={styles.header}>
        <div className={styles.titleRow}>
          <span className="material-symbols-outlined" style={{ fontSize: 20, color: 'var(--md-sys-color-primary)' }}>
            email
          </span>
          <span className={styles.title}>Email Draft</span>
        </div>
        <div className={styles.btnRow}>
          <button
            className={styles.actionBtn}
            onClick={handleCopy}
            title="Copy to clipboard"
          >
            <span className="material-symbols-outlined">{copied ? 'check' : 'content_copy'}</span>
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button
            className={`${styles.actionBtn} ${editing ? styles.active : ''}`}
            onClick={() => setEditing(e => !e)}
            title="Edit sender name"
          >
            <span className="material-symbols-outlined">{editing ? 'check' : 'edit'}</span>
            {editing ? 'Done' : 'Edit'}
          </button>
        </div>
      </header>

      <div className={styles.envelope}>
        <table className={styles.metaTable}>
          <tbody>
            <tr>
              <td className={styles.metaKey}>To:</td>
              <td className={styles.metaVal}>{toAddress}</td>
            </tr>
            <tr>
              <td className={styles.metaKey}>Subject:</td>
              <td className={styles.metaVal}>{DEFAULT_SUBJECT}</td>
            </tr>
            {editing && (
              <tr>
                <td className={styles.metaKey}>From name:</td>
                <td className={styles.metaVal}>
                  <input
                    ref={inputRef}
                    className={styles.nameInput}
                    value={senderName}
                    onChange={e => setSenderName(e.target.value)}
                    placeholder="Your name"
                    aria-label="Sender name"
                  />
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <hr className={styles.divider} />
        <pre className={styles.body}>{displayText}</pre>
      </div>

      <AnimatePresence>
        {showSnack && (
          <motion.div
            className={styles.snack}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
            transition={{ duration: 0.25 }}
            role="status"
            aria-live="polite"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>check_circle</span>
            Email draft copied to clipboard
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  );
}
