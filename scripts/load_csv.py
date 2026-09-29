#!/usr/bin/env python3
"""
scripts/load_csv.py
Loads books from a CSV into MySQL.

Supports two CSV formats:
  1. New format (your custom CSV):
       id, title, series, author, language, category, region,
       description, pages, publicationDate, rating, ratingsCount,
       genres, isbn, imageURL, amazonLink, freeSourceLink,
       freeSourceName, popularReviews

  2. Legacy Goodreads format:
       title, author, ISBN, rating, ratings, description,
       imageURL, pages, publicationDate, language, genres

Usage:
    python scripts/load_csv.py --csv data/books.csv
    python scripts/load_csv.py --csv data/books.csv --limit 1000
    python scripts/load_csv.py --csv data/books.csv --format goodreads
"""
import sys, os, argparse, ast, json, math, re
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
from app import create_app, db
from app.models import Book, Genre


# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_float(val, default=0.0):
    try:
        s = str(val).replace(',', '').strip()
        v = float(s)
        return default if math.isnan(v) else v
    except (TypeError, ValueError):
        return default


def safe_int(val, default=0):
    try:
        s = str(val).replace(',', '').strip()
        f = float(s)
        return default if math.isnan(f) else int(f)
    except (TypeError, ValueError):
        return default


def clean(val, default=None, maxlen=None):
    """Return stripped string or default if empty/NaN."""
    if val is None:
        return default
    if isinstance(val, float) and math.isnan(val):
        return default
    s = str(val).strip()
    if not s or s.lower() in ('nan', 'none', 'n/a', 'na'):
        return default
    return s[:maxlen] if maxlen else s


def parse_genres(raw):
    """Parse genres from string — handles comma-sep, JSON list, Python list."""
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return []
    if isinstance(raw, list):
        return [str(g).strip() for g in raw if g]
    s = str(raw).strip()
    if not s:
        return []
    # Try JSON
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return [str(g).strip() for g in parsed if g]
    except Exception:
        pass
    # Try Python literal
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            return [str(g).strip() for g in parsed if g]
    except Exception:
        pass
    # Comma separated
    return [g.strip() for g in s.split(',') if g.strip()]


def extract_author_name(raw):
    """Author field may be a JSON dict like {'name': 'John Doe'}."""
    if not raw or (isinstance(raw, float) and math.isnan(raw)):
        return ''
    if isinstance(raw, dict):
        return str(raw.get('name', '')).strip()
    s = str(raw).strip()
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(s)
            if isinstance(parsed, dict):
                return str(parsed.get('name', '')).strip()
        except Exception:
            pass
    return s[:512]


def parse_reviews(raw):
    """popularReviews: pipe-separated or JSON list — just return count."""
    if not raw or (isinstance(raw, float) and math.isnan(raw)):
        return 0
    s = str(raw).strip()
    if '|' in s:
        return len([r for r in s.split('|') if r.strip()])
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return len(parsed)
    except Exception:
        pass
    return 0


def detect_format(df):
    """Detect CSV format from column names."""
    cols = set(df.columns.str.lower())
    new_cols = {'category', 'region', 'amazonflink', 'freesourcelink', 'freesourcename'}
    # Check for new format indicators
    if 'category' in cols or 'region' in cols or 'freesourcelink' in cols:
        return 'new'
    if 'isbn' in cols and 'ratings' in cols:
        return 'goodreads'
    return 'new'  # default


def get_col(row, df_cols, *names, default=None):
    """Get first matching column (case-insensitive) from row."""
    col_map = {c.lower(): c for c in df_cols}
    for name in names:
        key = name.lower()
        if key in col_map:
            val = row[col_map[key]]
            if isinstance(val, float) and math.isnan(val):
                return default
            return val
    return default


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Load books CSV into DB')
    parser.add_argument('--csv',    default='data/books.csv', help='Path to CSV')
    parser.add_argument('--limit',  type=int, default=None,   help='Max rows to import')
    parser.add_argument('--batch',  type=int, default=200,    help='Commit every N rows')
    parser.add_argument('--format', default='auto',           help='auto | new | goodreads')
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f'ERROR: File not found: {args.csv}')
        sys.exit(1)

    app = create_app('development')
    with app.app_context():
        print(f'Loading: {args.csv}')
        try:
            df = pd.read_csv(args.csv, encoding='utf-8', on_bad_lines='skip',
                             low_memory=False, nrows=args.limit)
        except Exception:
            df = pd.read_csv(args.csv, encoding='latin-1', on_bad_lines='skip',
                             low_memory=False, nrows=args.limit)

        print(f'Rows   : {len(df):,}')
        print(f'Columns: {list(df.columns)}')

        fmt = args.format if args.format != 'auto' else detect_format(df)
        print(f'Format : {fmt}')

        genre_cache = {}
        inserted = updated = skipped = 0

        for _, row in df.iterrows():
            g = lambda *names, default=None: get_col(row, df.columns, *names, default=default)

            # ── Title (required) ───────────────────────────────────────────
            title = clean(g('title'), maxlen=512)
            if not title:
                skipped += 1
                continue

            # ── Per-format field mapping ───────────────────────────────────
            if fmt == 'new':
                external_id      = clean(g('id'), maxlen=256)
                series           = clean(g('series'), maxlen=256)
                author           = clean(g('author'), maxlen=512) or ''
                language         = clean(g('language'), maxlen=50)
                category         = clean(g('category'), maxlen=256)
                region           = clean(g('region'), maxlen=100)
                description      = clean(g('description'))
                pages            = safe_int(g('pages'))
                pub_date         = clean(g('publicationDate', 'publication_date'), maxlen=50)
                rating           = safe_float(g('rating'))
                ratings_count    = safe_int(g('ratingsCount', 'ratings_count', 'ratingscount'))
                raw_genres       = parse_genres(g('genres'))
                isbn             = clean(g('isbn', 'ISBN'), maxlen=30)
                cover_url        = clean(g('imageURL', 'imageurl', 'image_url', 'cover'), maxlen=1024)
                amazon_link      = clean(g('amazonLink', 'amazonlink', 'amazon_link'), maxlen=1024)
                free_link        = clean(g('freeSourceLink', 'freesourcelink', 'free_source_link'), maxlen=1024)
                free_name        = clean(g('freeSourceName', 'freesourcename', 'free_source_name'), maxlen=256)
                text_reviews     = parse_reviews(g('popularReviews', 'popularreviews'))
                publisher        = None
                isbn13           = None

            else:  # goodreads legacy
                external_id      = None
                series           = None
                raw_isbn         = g('ISBN')
                isbn13 = None
                if raw_isbn is not None:
                    try:
                        isbn13 = str(int(float(str(raw_isbn))))
                    except Exception:
                        isbn13 = clean(raw_isbn, maxlen=20)
                isbn             = isbn13
                author           = extract_author_name(g('author'))[:512]
                language         = clean(g('language'), maxlen=20)
                category         = None
                region           = None
                description      = clean(g('description'))
                pages            = safe_int(g('pages'))
                pub_date         = clean(g('publicationDate', 'publication_date'), maxlen=50)
                rating           = safe_float(g('rating'))
                ratings_count    = safe_int(g('ratings', 'ratingsCount'))
                raw_genres       = parse_genres(g('genres'))
                cover_url        = clean(g('imageURL', 'imageurl'), maxlen=1024)
                amazon_link      = None
                free_link        = None
                free_name        = None
                text_reviews     = 0
                publisher        = clean(g('publisher'), maxlen=256)

            # ── Dedup: find existing book ──────────────────────────────────
            existing = None
            if fmt == 'new' and external_id:
                existing = Book.query.filter_by(external_id=external_id).first()
            if not existing and isbn and isbn.lower() not in ('n/a', 'na', ''):
                existing = Book.query.filter_by(isbn=isbn).first()
            if not existing and isbn13:
                existing = Book.query.filter_by(isbn13=isbn13).first()
            if not existing:
                existing = Book.query.filter_by(title=title).filter(
                    Book.author == (author or None)
                ).first()

            if existing:
                book = existing
                updated += 1
            else:
                book = Book()
                db.session.add(book)
                inserted += 1

            # ── Assign fields ──────────────────────────────────────────────
            book.external_id        = external_id
            book.isbn               = isbn
            book.isbn13             = isbn13
            book.title              = title
            book.series             = series
            book.author             = author or None
            book.publisher          = publisher
            book.description        = description
            book.cover_image_url    = cover_url
            book.publication_date   = pub_date
            book.page_count         = pages if pages > 0 else None
            book.language           = language
            book.category           = category
            book.region             = region
            book.amazon_link        = amazon_link
            book.free_source_link   = free_link
            book.free_source_name   = free_name
            book.average_rating     = rating
            book.ratings_count      = ratings_count
            book.text_reviews_count = text_reviews
            book.popularity         = ratings_count * rating

            # ── Genres ────────────────────────────────────────────────────
            if raw_genres:
                genre_objs = []
                for gname in raw_genres[:12]:
                    gname = gname[:100]
                    if not gname:
                        continue
                    if gname not in genre_cache:
                        g_obj = Genre.query.filter_by(name=gname).first()
                        if not g_obj:
                            g_obj = Genre(name=gname)
                            db.session.add(g_obj)
                            db.session.flush()
                        genre_cache[gname] = g_obj
                    genre_objs.append(genre_cache[gname])
                book.genres = genre_objs

            processed = inserted + updated
            if processed % args.batch == 0:
                db.session.commit()
                print(f'  {processed:,} rows processed  '
                      f'({inserted:,} new · {updated:,} updated · {skipped:,} skipped)')

        db.session.commit()
        print(f'\n✓ Done!')
        print(f'  Inserted : {inserted:,}')
        print(f'  Updated  : {updated:,}')
        print(f'  Skipped  : {skipped:,}')
        print(f'  Books DB : {Book.query.count():,}')
        print(f'  Genres DB: {Genre.query.count():,}')


if __name__ == '__main__':
    main()