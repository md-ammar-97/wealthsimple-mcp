import { NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import path from 'path';

const OUTPUTS_DIR   = path.resolve(process.cwd(), '..', 'outputs');
const SUMMARY_FILE  = path.join(OUTPUTS_DIR, 'run_summary.json');
const NOTE_FILE     = path.join(OUTPUTS_DIR, 'weekly_note.md');
const EMAIL_FILE    = path.join(OUTPUTS_DIR, 'email_draft.txt');

export async function GET() {
  try {
    const [summaryRaw, noteText, emailText] = await Promise.all([
      readFile(SUMMARY_FILE, 'utf8'),
      readFile(NOTE_FILE, 'utf8'),
      readFile(EMAIL_FILE, 'utf8'),
    ]);

    const summary = JSON.parse(summaryRaw);

    return NextResponse.json({
      runId:          summary.run_id ?? summary.runId ?? 'unknown',
      periodStart:    summary.period_start ?? '',
      periodEnd:      summary.period_end ?? '',
      reviewCount:    summary.review_count ?? 0,
      themes:         (summary.top_themes ?? []).map((t: Record<string, unknown>, i: number) => ({
        theme:       t.theme,
        reviewCount: t.count ?? t.review_count ?? 0,
        avgRating:   t.avg_rating ?? 0,
        rank:        i + 1,
      })),
      quotes:         (summary.quotes ?? []).map((q: Record<string, unknown>) => ({
        theme:    q.theme,
        quote:    q.quote,
        reviewId: q.review_id ?? 0,
        verified: q.verified ?? true,
        platform: q.platform ?? 'App Store',
        rating:   q.rating ?? null,
        date:     q.date ?? null,
      })),
      actions:        (summary.actions ?? []).map((a: Record<string, unknown>) => ({
        action:      a.action,
        linkedTheme: a.linked_theme ?? a.linkedTheme ?? '',
      })),
      noteText,
      wordCount:      summary.word_count ?? noteText.split(/\s+/).length,
      emailText,
      lowDataWarning: summary.low_data_warning ?? false,
      generatedAt:    summary.generated_at ?? null,
    });
  } catch (e) {
    return NextResponse.json(
      { error: `Results not found: ${(e as Error).message}` },
      { status: 404 }
    );
  }
}
