from flask import (Blueprint, render_template, request, jsonify,
                   redirect, url_for, flash, abort, current_app)
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from app import db, cache
from app.models import Book, Genre, Rating, Wishlist, ReadHistory, RecommendationCache, UserGenrePref

books_bp = Blueprint('books', __name__)


# ─── Home ─────────────────────────────────────────────────────────────────────
@books_bp.route('/')
def home():
    featured    = Book.query.order_by(Book.ratings_count.desc()).limit(8).all()
    top_rated   = Book.query.filter(Book.ratings_count > 50)\
                      .order_by(Book.average_rating.desc()).limit(8).all()
    newest      = Book.query.order_by(Book.id.desc()).limit(8).all()
    genres      = Genre.query.order_by(Genre.name).all()

    user_ratings = {}
    user_wishlist = set()
    if current_user.is_authenticated:
        rated = Rating.query.filter_by(user_id=current_user.id).all()
        user_ratings = {r.book_id: r.rating for r in rated}
        wished = Wishlist.query.filter_by(user_id=current_user.id).all()
        user_wishlist = {w.book_id for w in wished}

    return render_template('home.html',
                           featured=featured,
                           top_rated=top_rated,
                           newest=newest,
                           genres=genres,
                           user_ratings=user_ratings,
                           user_wishlist=user_wishlist)


# ─── Browse ───────────────────────────────────────────────────────────────────
@books_bp.route('/books')
def browse():
    q        = request.args.get('q', '').strip()
    genre_id = request.args.get('genre', type=int)
    lang     = request.args.get('lang', '').strip()
    year_from = request.args.get('year_from', type=int)
    year_to  = request.args.get('year_to', type=int)
    sort     = request.args.get('sort', 'popular')
    page     = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('BOOKS_PER_PAGE', 24)

    query = Book.query

    if q:
        like = f'%{q}%'
        query = query.filter(or_(
            Book.title.ilike(like),
            Book.author.ilike(like),
        ))
    if genre_id:
        query = query.join(Book.genres).filter(Genre.id == genre_id)
    if lang:
        query = query.filter(Book.language == lang)
    if year_from:
        query = query.filter(Book.publication_date >= str(year_from))
    if year_to:
        query = query.filter(Book.publication_date <= str(year_to))

    sort_map = {
        'popular':   Book.ratings_count.desc(),
        'top_rated': Book.average_rating.desc(),
        'newest':    Book.publication_date.desc(),
        'az':        Book.title.asc(),
    }
    query = query.order_by(sort_map.get(sort, Book.ratings_count.desc()))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    books      = pagination.items
    genres     = Genre.query.order_by(Genre.name).all()

    # Language list — plain Python list of (code, code) tuples
    lang_rows = db.session.execute(
        db.text("SELECT DISTINCT language FROM books WHERE language IS NOT NULL ORDER BY language")
    ).fetchall()
    languages = [row[0] for row in lang_rows if row[0]]

    user_ratings  = {}
    user_wishlist = set()
    if current_user.is_authenticated:
        ids   = [b.id for b in books]
        rated = Rating.query.filter(Rating.user_id == current_user.id,
                                    Rating.book_id.in_(ids)).all()
        user_ratings = {r.book_id: r.rating for r in rated}
        wished = Wishlist.query.filter(Wishlist.user_id == current_user.id,
                                       Wishlist.book_id.in_(ids)).all()
        user_wishlist = {w.book_id for w in wished}

    return render_template('books/browse.html',
                           books=books,
                           pagination=pagination,
                           genres=genres,
                           languages=languages,
                           selected_genre=genre_id,
                           selected_lang=lang,
                           q=q,
                           sort=sort,
                           year_from=year_from,
                           year_to=year_to,
                           user_ratings=user_ratings,
                           user_wishlist=user_wishlist)


# ─── Book Detail ──────────────────────────────────────────────────────────────
@books_bp.route('/book/<int:book_id>')
def detail(book_id):
    book = db.get_or_404(Book, book_id)

    # Track read history
    if current_user.is_authenticated:
        hist = ReadHistory.query.filter_by(
            user_id=current_user.id, book_id=book_id).first()
        if hist:
            hist.read_count += 1
        else:
            hist = ReadHistory(user_id=current_user.id, book_id=book_id)
            db.session.add(hist)
        db.session.commit()

    # User's existing rating + review + wishlist state
    user_rating  = None
    user_review  = None
    in_wishlist  = False
    if current_user.is_authenticated:
        r = Rating.query.filter_by(user_id=current_user.id, book_id=book_id).first()
        user_rating = r.rating if r else None
        user_review = r.review if r else None
        in_wishlist = bool(Wishlist.query.filter_by(
            user_id=current_user.id, book_id=book_id).first())

    # Similar books by shared genre
    genre_ids = [g.id for g in book.genres]
    similar = []
    if genre_ids:
        similar = (Book.query
                   .join(Book.genres)
                   .filter(Genre.id.in_(genre_ids), Book.id != book_id)
                   .order_by(Book.average_rating.desc())
                   .limit(6).all())

    # Other users' reviews (exclude current user — shown separately)
    current_uid = current_user.id if current_user.is_authenticated else None
    reviews_q = Rating.query.filter(
        Rating.book_id == book_id,
        Rating.review.isnot(None),
        Rating.review != '')
    if current_uid:
        reviews_q = reviews_q.filter(Rating.user_id != current_uid)
    reviews = reviews_q.order_by(Rating.created_at.desc()).limit(20).all()

    return render_template('books/detail.html',
                           book=book,
                           user_rating=user_rating,
                           user_review=user_review,
                           in_wishlist=in_wishlist,
                           similar=similar,
                           reviews=reviews)


# ─── AJAX: Rate ───────────────────────────────────────────────────────────────
@books_bp.route('/api/rate', methods=['POST'])
@login_required
def api_rate():
    data    = request.get_json()
    book_id = data.get('book_id')
    rating  = data.get('rating')

    if not book_id or rating is None:
        return jsonify({'status': 'error', 'message': 'Missing fields'}), 400
    if not (0.5 <= float(rating) <= 5.0):
        return jsonify({'status': 'error', 'message': 'Rating out of range'}), 400

    book = db.get_or_404(Book, book_id)
    existing = Rating.query.filter_by(user_id=current_user.id, book_id=book_id).first()

    if existing:
        existing.rating = float(rating)
        existing.review = data.get('review', existing.review)
        db.session.flush()
        # Recalculate book average
        avg = db.session.query(func.avg(Rating.rating)).filter_by(book_id=book_id).scalar()
        book.average_rating = round(avg, 2)
    else:
        new_r = Rating(user_id=current_user.id, book_id=book_id,
                       rating=float(rating), review=data.get('review'))
        db.session.add(new_r)
        db.session.flush()
        count = Rating.query.filter_by(book_id=book_id).count()
        avg   = db.session.query(func.avg(Rating.rating)).filter_by(book_id=book_id).scalar()
        book.average_rating = round(avg, 2)
        book.ratings_count  = count

    # Update genre preference weights
    delta = (float(rating) - 3.0) * 0.1
    for genre in book.genres:
        pref = UserGenrePref.query.filter_by(
            user_id=current_user.id, genre_id=genre.id).first()
        if pref:
            pref.weight = max(0.1, min(5.0, pref.weight + delta))
        else:
            db.session.add(UserGenrePref(
                user_id=current_user.id, genre_id=genre.id,
                weight=max(0.1, min(5.0, 1.0 + delta))))

    # Invalidate recommendation cache
    cache_entry = RecommendationCache.query.filter_by(user_id=current_user.id).first()
    if cache_entry:
        db.session.delete(cache_entry)

    db.session.commit()
    review_text = data.get('review', '')
    return jsonify({'status': 'ok', 'rating': float(rating),
                    'avg': book.average_rating, 'count': book.ratings_count,
                    'review': review_text})


# ─── AJAX: Wishlist ───────────────────────────────────────────────────────────
@books_bp.route('/api/wishlist', methods=['POST'])
@login_required
def api_wishlist():
    data    = request.get_json()
    book_id = data.get('book_id')
    if not book_id:
        return jsonify({'status': 'error'}), 400

    db.get_or_404(Book, book_id)
    existing = Wishlist.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'status': 'removed'})
    else:
        db.session.add(Wishlist(user_id=current_user.id, book_id=book_id))
        db.session.commit()
        return jsonify({'status': 'added'})