import { NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import path from 'path';

const CLEAN_CSV = path.resolve(process.cwd(), '..', 'data', 'output', 'reviews_clean.csv');

export async function GET() {
  try {
    const buf = await readFile(CLEAN_CSV);
    return new NextResponse(buf, {
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename="reviews_clean.csv"',
      },
    });
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 404 });
  }
}
