import { NextRequest, NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import path from 'path';

const LEDGER_PATH = path.resolve(process.cwd(), '..', 'data', 'runs', 'ledger.json');

interface LedgerEntry {
  run_id: string;
  status: string;
  started_at: string;
  completed_at?: string;
  reviews_ingested: number;
  themes_in_note: number;
  note_word_count: number;
  period_key: string;
  delivery?: { mode: string; doc_url?: string; draft_id?: string };
}

export async function GET(req: NextRequest) {
  try {
    const raw = await readFile(LEDGER_PATH, 'utf8');
    const entries: LedgerEntry[] = JSON.parse(raw);

    const days = parseInt(req.nextUrl.searchParams.get('days') ?? '0', 10);
    const cutoff = days > 0 ? new Date(Date.now() - days * 86_400_000) : null;

    const filtered = entries.filter((e) => {
      if (!cutoff) return true;
      const d = new Date(e.started_at);
      return !isNaN(d.getTime()) && d >= cutoff;
    });

    const successful = filtered.filter((e) => e.status === 'success');

    // Build weekly buckets for charts
    const weekMap = new Map<string, { week: string; count: number; reviews: number }>();
    for (const e of successful) {
      const d = new Date(e.started_at);
      const monday = new Date(d);
      monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
      const key = monday.toISOString().slice(0, 10);
      const existing = weekMap.get(key) ?? { week: key, count: 0, reviews: 0 };
      existing.count++;
      existing.reviews += e.reviews_ingested ?? 0;
      weekMap.set(key, existing);
    }
    const weeklyVolume = [...weekMap.values()].sort((a, b) => a.week.localeCompare(b.week));

    const totalReviews = successful.reduce((s, e) => s + (e.reviews_ingested ?? 0), 0);
    const lastRun = successful.at(-1) ?? null;

    const runs = filtered
      .slice()
      .reverse()
      .map((e) => ({
        run_id: e.run_id,
        date: e.started_at,
        reviews: e.reviews_ingested ?? 0,
        themes: e.themes_in_note ?? 0,
        wordCount: e.note_word_count ?? 0,
        status: e.status,
        periodKey: e.period_key,
        delivery: e.delivery ?? null,
      }));

    return NextResponse.json({
      totalRuns: successful.length,
      totalReviews,
      lastRunDate: lastRun?.started_at ?? null,
      lastRunReviews: lastRun?.reviews_ingested ?? 0,
      weeklyVolume,
      runs,
    });
  } catch {
    return NextResponse.json({ error: 'Ledger not found or unreadable' }, { status: 404 });
  }
}
