'use client';

import { useEffect, useRef, useState } from 'react';
import type { PipelineStatus, PipelineStep } from '@/types/pipeline';

const INITIAL_STEPS: PipelineStep[] = [
  { id: 1, label: 'Ingest',    icon: 'upload_file',     state: 'idle' },
  { id: 2, label: 'Redact',    icon: 'policy',          state: 'idle' },
  { id: 3, label: 'Classify',  icon: 'category',        state: 'idle' },
  { id: 4, label: 'Rank',      icon: 'leaderboard',     state: 'idle' },
  { id: 5, label: 'Quotes',    icon: 'format_quote',    state: 'idle' },
  { id: 6, label: 'Actions',   icon: 'lightbulb',       state: 'idle' },
  { id: 7, label: 'Note',      icon: 'article',         state: 'idle' },
  { id: 8, label: 'Email',     icon: 'email',           state: 'idle' },
];

const STEP_MAP: Record<string, number> = {
  ingest: 1, redact: 2, classify: 3, rank_themes: 4,
  quote_select: 5, action_gen: 6, pulse_note: 7, email_draft: 8,
};

export function usePipelineStatus(runId: string | null) {
  const [status, setStatus] = useState<PipelineStatus>({
    steps: INITIAL_STEPS,
    completed: false,
  });
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!runId) return;

    // Reset steps on new run
    setStatus({ steps: INITIAL_STEPS.map(s => ({ ...s })), completed: false });

    const es = new EventSource(`/api/pipeline/status?runId=${runId}`);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.completed) {
          setStatus(prev => ({ ...prev, completed: true }));
          es.close();
          return;
        }

        const { step, state, detail, error } = data as {
          step: number;
          state: 'idle' | 'active' | 'done' | 'error';
          detail?: string;
          error?: string;
        };

        setStatus(prev => {
          const steps = prev.steps.map(s =>
            s.id === step ? { ...s, state, detail } : s
          );
          return { steps, completed: false, error };
        });
      } catch {
        // ignore malformed events
      }
    };

    es.onerror = () => {
      setStatus(prev => ({
        ...prev,
        error: 'Connection lost. The pipeline may have failed.',
      }));
      es.close();
    };

    return () => {
      es.close();
    };
  }, [runId]);

  return status;
}
