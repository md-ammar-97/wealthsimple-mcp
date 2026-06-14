'use client';

import { useEffect, useState, useCallback } from 'react';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import styles from './analytics.module.css';

/* ─── Types ─────────────────────────────────────── */
interface RunEntry {
  run_id: string;
  date: string;
  reviews: number;
  themes: number;
  wordCount: number;
  status: string;
  periodKey: string;
  delivery: { mode: string; doc_url?: string; draft_id?: string } | null;
}

interface AnalyticsData {
  totalRuns: number;
  totalReviews: number;
  lastRunDate: string | null;
  lastRunReviews: number;
  weeklyVolume: { week: string; count: number; reviews: number }[];
  runs: RunEntry[];
}

const DAY_FILTERS = [
  { label: 'Last 30d',  days: 30  },
  { label: 'Last 90d',  days: 90  },
  { label: 'Last 180d', days: 180 },
  { label: 'All time',  days: 0   },
];

const CHART_BLUE    = '#0052CC';
const CHART_PURPLE  = '#6554C0';

/* ─── Page ──────────────────────────────────────── */
export default function AnalyticsPage() {
  const [days, setDays]   = useState(0);
  const [data, setData]   = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr]     = useState<string | null>(null);

  const load = useCallback(async (d: number) => {
    setLoading(true);
    setErr(null);
    try {
      const res = await fetch(`/api/analytics?days=${d}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error ?? 'Failed to load analytics');
      setData(json);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(days); }, [days, load]);

  const fmtDate = (iso: string) => {
    const d = new Date(iso);
    return isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: '2-digit' });
  };

  const fmtWeek = (iso: string) => {
    const d = new Date(iso);
    return isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  };

  return (
    <main className={styles.main}>
      <div className="page-content">

        {/* Header */}
        <header className={styles.header}>
          <div>
            <h1 className={styles.title}>Wealthsimple Analytics</h1>
            <p className={styles.subtitle}>Automated Google Play review analysis · weekly cadence</p>
          </div>
          <div className={styles.filterRow}>
            {DAY_FILTERS.map(f => (
              <button
                key={f.days}
                className={`btn ${days === f.days ? 'btn-primary' : 'btn-default'}`}
                onClick={() => setDays(f.days)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </header>

        {loading && (
          <div className={styles.loading}>
            <span className="material-symbols-outlined" style={{ animation: 'spin 1s linear infinite', fontSize: 32 }}>
              progress_activity
            </span>
            <p>Loading analytics…</p>
          </div>
        )}

        {err && (
          <div className="section-msg section-msg-error">
            <span className="material-symbols-outlined">error</span>
            <span>{err}</span>
          </div>
        )}

        {!loading && data && (
          <>
            {/* Metric cards */}
            <div className={styles.metricGrid}>
              <MetricCard
                icon="checklist"
                label="Total runs"
                value={data.totalRuns.toLocaleString()}
              />
              <MetricCard
                icon="reviews"
                label="Reviews analysed"
                value={data.totalReviews.toLocaleString()}
              />
              <MetricCard
                icon="reviews"
                label="Last run reviews"
                value={data.lastRunReviews.toLocaleString()}
              />
              <MetricCard
                icon="schedule"
                label="Last run"
                value={data.lastRunDate ? fmtDate(data.lastRunDate) : '—'}
              />
            </div>

            {/* Charts */}
            {data.weeklyVolume.length > 0 ? (
              <div className={styles.charts}>
                {/* Review volume */}
                <div className={`${styles.chartCard} atlas-card`}>
                  <h3 className={styles.chartTitle}>Reviews per run</h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={data.weeklyVolume} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                      <XAxis dataKey="week" tickFormatter={fmtWeek} tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        formatter={(v: any) => [v != null ? Number(v).toLocaleString() : '0', 'Reviews'] as any}
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        labelFormatter={(label: any) => fmtWeek(String(label))}
                      />
                      <Bar dataKey="reviews" radius={[3, 3, 0, 0]}>
                        {data.weeklyVolume.map((_, i) => (
                          <Cell key={i} fill={CHART_BLUE} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* Run count over time */}
                <div className={`${styles.chartCard} atlas-card`}>
                  <h3 className={styles.chartTitle}>Runs over time</h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={data.weeklyVolume} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                      <XAxis dataKey="week" tickFormatter={fmtWeek} tick={{ fontSize: 11 }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                      <Tooltip
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        formatter={(v: any) => [v != null ? Number(v) : 0, 'Runs'] as any}
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        labelFormatter={(label: any) => fmtWeek(String(label))}
                      />
                      <Line
                        type="monotone"
                        dataKey="count"
                        stroke={CHART_PURPLE}
                        strokeWidth={2}
                        dot={{ r: 4, fill: CHART_PURPLE }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <div className="section-msg section-msg-info" style={{ margin: 'var(--space-6) 0' }}>
                <span className="material-symbols-outlined">info</span>
                <span>No run data for the selected period. Try "All time".</span>
              </div>
            )}

            {/* Run history table */}
            {data.runs.length > 0 && (
              <section className={styles.historySection}>
                <h2 className={styles.sectionHeading}>Run history</h2>
                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Period</th>
                        <th className={styles.numCol}>Reviews</th>
                        <th className={styles.numCol}>Themes</th>
                        <th className={styles.numCol}>Words</th>
                        <th>Status</th>
                        <th>Delivery</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.runs.map(r => (
                        <tr key={r.run_id}>
                          <td className={styles.dateCell}>{fmtDate(r.date)}</td>
                          <td className={styles.periodCell}>
                            <span className="badge badge-neutral">{r.periodKey}</span>
                          </td>
                          <td className={styles.numCol}>{r.reviews.toLocaleString()}</td>
                          <td className={styles.numCol}>{r.themes}</td>
                          <td className={styles.numCol}>{r.wordCount}</td>
                          <td>
                            <span className={`badge ${r.status === 'success' ? 'badge-green' : 'badge-red'}`}>
                              {r.status}
                            </span>
                          </td>
                          <td className={styles.deliveryCell}>
                            {r.delivery?.mode === 'mcp' ? (
                              <div className={styles.deliveryLinks}>
                                {r.delivery.doc_url && (
                                  <a href={r.delivery.doc_url} target="_blank" rel="noreferrer" className={styles.deliveryLink}>
                                    <span className="material-symbols-outlined" style={{ fontSize: 14 }}>description</span> Doc
                                  </a>
                                )}
                                {r.delivery.draft_id && (
                                  <span className={styles.deliveryTag}>
                                    <span className="material-symbols-outlined" style={{ fontSize: 14 }}>email</span> Draft
                                  </span>
                                )}
                              </div>
                            ) : (
                              <span className="badge badge-neutral">{r.delivery?.mode ?? 'local'}</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </main>
  );
}

function MetricCard({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className={`${styles.metricCard} atlas-card`}>
      <span className={`material-symbols-outlined ${styles.metricIcon}`}>{icon}</span>
      <div>
        <p className={styles.metricLabel}>{label}</p>
        <p className={styles.metricValue}>{value}</p>
      </div>
    </div>
  );
}
