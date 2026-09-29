from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, jsonify, abort, current_app)
from flask_login import login_required, current_user
from sqlalchemy import func, text
from app import db
from app.models import Book, User, Rating, Genre, Wishlist, RecommendationCache

admin_bp = Blueprint('admin', __name__)


# ─── Guards ───────────────────────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('books.home'))
        return f(*args, **kwargs)
    return login_required(decorated)


def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_super_admin:
            flash('Super-admin access required.', 'danger')
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return login_required(decorated)


# ─── Dashboard ────────────────────────────────────────────────────────────────
@admin_bp.route('/')
@admin_required
def dashboard():
    from datetime import datetime, timedelta

    book_count   = Book.query.count()
    user_count   = User.query.count()
    rating_count = Rating.query.count()
    genre_count  = Genre.query.count()

    # Extra stats
    wishlist_count  = Wishlist.query.count()
    banned_count    = User.query.filter_by(is_active=False).count()
    active_count    = user_count - banned_count
    avg_rating_row  = db.session.execute(text("SELECT ROUND(AVG(rating),2) FROM ratings")).scalar()
    avg_rating      = float(avg_rating_row) if avg_rating_row else 0.0

    week_ago = datetime.utcnow() - timedelta(days=7)
    new_users_week   = User.query.filter(User.created_at >= week_ago).count()
    new_ratings_week = Rating.query.filter(Rating.created_at >= week_ago).count()

    recent_users   = User.query.order_by(User.created_at.desc()).limit(7).all()
    recent_ratings = Rating.query.order_by(Rating.created_at.desc()).limit(10).all()
    rating_user_ids  = [r.user_id for r in recent_ratings]
    rating_book_ids  = [r.book_id for r in recent_ratings]
    rating_users_map = {u.id: u for u in User.query.filter(User.id.in_(rating_user_ids)).all()}
    rating_books_map = {b.id: b for b in Book.query.filter(Book.id.in_(rating_book_ids)).all()}

    top_books     = Book.query.filter(Book.ratings_count >= 3).order_by(Book.average_rating.desc()).limit(5).all()
    most_reviewed = Book.query.order_by(Book.ratings_count.desc()).limit(5).all()

    try:
        rows = db.session.execute(text(
            "SELECT DATE(created_at) as d, COUNT(*) as c FROM ratings "
            "WHERE created_at >= DATE_SUB(NOW(), INTERVAL 14 DAY) "
            "GROUP BY d ORDER BY d"
        )).fetchall()
    except Exception:
        rows = []
    chart_labels = [str(row[0]) for row in rows]
    chart_data   = [row[1] for row in rows]

    try:
        user_rows = db.session.execute(text(
            "SELECT DATE(created_at) as d, COUNT(*) as c FROM users "
            "WHERE created_at >= DATE_SUB(NOW(), INTERVAL 14 DAY) "
            "GROUP BY d ORDER BY d"
        )).fetchall()
    except Exception:
        user_rows = []
    user_chart_labels = [str(r[0]) for r in user_rows]
    user_chart_data   = [r[1] for r in user_rows]

    try:
        genre_rows = db.session.execute(text(
            "SELECT g.name, COUNT(bg.book_id) as c FROM genres g "
            "LEFT JOIN book_genres bg ON bg.genre_id = g.id "
            "GROUP BY g.id ORDER BY c DESC LIMIT 10"
        )).fetchall()
    except Exception:
        genre_rows = []
    genre_labels = [row[0] for row in genre_rows]
    genre_counts = [row[1] for row in genre_rows]

    try:
        dist_rows = db.session.execute(text(
            "SELECT FLOOR(rating) as star, COUNT(*) as c FROM ratings GROUP BY star ORDER BY star"
        )).fetchall()
    except Exception:
        dist_rows = []
    dist_map    = {int(r[0]): r[1] for r in dist_rows}
    rating_dist = [dist_map.get(i, 0) for i in range(1, 6)]

    return render_template('admin/dashboard.html',
                           book_count=book_count, user_count=user_count,
                           rating_count=rating_count, genre_count=genre_count,
                           wishlist_count=wishlist_count, banned_count=banned_count,
                           active_count=active_count, avg_rating=avg_rating,
                           new_users_week=new_users_week, new_ratings_week=new_ratings_week,
                           recent_users=recent_users, recent_ratings=recent_ratings,
                           rating_users_map=rating_users_map, rating_books_map=rating_books_map,
                           top_books=top_books, most_reviewed=most_reviewed,
                           chart_labels=chart_labels, chart_data=chart_data,
                           user_chart_labels=user_chart_labels, user_chart_data=user_chart_data,
                           genre_labels=genre_labels, genre_counts=genre_counts,
                           rating_dist=rating_dist)


# ─── Books ────────────────────────────────────────────────────────────────────
@admin_bp.route('/books')
@admin_required
def books():
    q    = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    query = Book.query
    if q:
        query = query.filter(Book.title.ilike(f'%{q}%'))
    pagination = query.order_by(Book.id.desc()).paginate(page=page, per_page=30)
    return render_template('admin/books.html', books=pagination.items,
                           pagination=pagination, q=q)


@admin_bp.route('/books/<int:book_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_book(book_id):
    book = db.get_or_404(Book, book_id)
    all_genres = Genre.query.order_by(Genre.name).all()
    if request.method == 'POST':
        book.title           = request.form.get('title', book.title).strip()
        book.author          = request.form.get('author', book.author)
        book.publisher       = request.form.get('publisher', book.publisher)
        book.description     = request.form.get('description', book.description)
        book.cover_image_url = request.form.get('cover_image_url', book.cover_image_url)
        book.page_count      = request.form.get('page_count', type=int) or book.page_count
        book.language        = request.form.get('language', book.language)
        genre_ids = request.form.getlist('genres', type=int)
        book.genres = Genre.query.filter(Genre.id.in_(genre_ids)).all()
        db.session.commit()
        flash('Book updated.', 'success')
        return redirect(url_for('admin.books'))
    return render_template('admin/edit_book.html', book=book, all_genres=all_genres)


@admin_bp.route('/books/<int:book_id>/delete', methods=['POST'])
@admin_required
def delete_book(book_id):
    book = db.get_or_404(Book, book_id)
    db.session.delete(book)
    db.session.commit()
    return jsonify({'status': 'ok'})


# ─── Users ────────────────────────────────────────────────────────────────────
@admin_bp.route('/users')
@admin_required
def users():
    q      = request.args.get('q', '').strip()
    filter_type = request.args.get('filter', 'all')
    page   = request.args.get('page', 1, type=int)
    query  = User.query
    if q:
        query = query.filter(
            (User.username.ilike(f'%{q}%')) | (User.email.ilike(f'%{q}%'))
        )
    if filter_type == 'admins':
        query = query.filter(User.is_admin == True)
    elif filter_type == 'banned':
        query = query.filter(User.is_active == False)
    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=30)
    return render_template('admin/users.html', users=pagination.items,
                           pagination=pagination, q=q, filter_type=filter_type)


@admin_bp.route('/users/<int:user_id>')
@admin_required
def user_detail(user_id):
    user = db.get_or_404(User, user_id)
    ratings = (Rating.query.filter_by(user_id=user_id)
               .order_by(Rating.created_at.desc()).limit(10).all())
    book_ids = [r.book_id for r in ratings]
    books_map = {b.id: b for b in Book.query.filter(Book.id.in_(book_ids)).all()}
    stats = {
        'ratings': Rating.query.filter_by(user_id=user_id).count(),
        'wishlist': Wishlist.query.filter_by(user_id=user_id).count(),
    }
    return render_template('admin/user_detail.html',
                           user=user, ratings=ratings,
                           books_map=books_map, stats=stats)


@admin_bp.route('/users/<int:user_id>/toggle-ban', methods=['POST'])
@admin_required
def toggle_ban(user_id):
    user = db.get_or_404(User, user_id)
    if user.is_super_admin:
        return jsonify({'status': 'error', 'message': 'Cannot ban super admin'}), 403
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'status': 'ok', 'active': user.is_active})


@admin_bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@super_admin_required
def toggle_admin(user_id):
    user = db.get_or_404(User, user_id)
    user.is_admin = not user.is_admin
    db.session.commit()
    return jsonify({'status': 'ok', 'is_admin': user.is_admin})


@admin_bp.route('/users/<int:user_id>/toggle-super', methods=['POST'])
@super_admin_required
def toggle_super(user_id):
    user = db.get_or_404(User, user_id)
    user.is_super_admin = not user.is_super_admin
    if user.is_super_admin:
        user.is_admin = True
    db.session.commit()
    return jsonify({'status': 'ok', 'is_super': user.is_super_admin})


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@super_admin_required
def delete_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.is_super_admin:
        return jsonify({'status': 'error', 'message': 'Cannot delete super admin'}), 403
    db.session.delete(user)
    db.session.commit()
    return jsonify({'status': 'ok'})


# ─── Genres ───────────────────────────────────────────────────────────────────
@admin_bp.route('/genres')
@admin_required
def genres():
    all_genres = Genre.query.order_by(Genre.name).all()
    return render_template('admin/genres.html', genres=all_genres)


@admin_bp.route('/genres/add', methods=['POST'])
@admin_required
def add_genre():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Genre name required.', 'danger')
        return redirect(url_for('admin.genres'))
    if Genre.query.filter_by(name=name).first():
        flash('Genre already exists.', 'warning')
        return redirect(url_for('admin.genres'))
    db.session.add(Genre(name=name))
    db.session.commit()
    flash(f'Genre "{name}" added.', 'success')
    return redirect(url_for('admin.genres'))


@admin_bp.route('/genres/<int:genre_id>/delete', methods=['POST'])
@admin_required
def delete_genre(genre_id):
    genre = db.get_or_404(Genre, genre_id)
    db.session.delete(genre)
    db.session.commit()
    return jsonify({'status': 'ok'})


# ─── Ratings ──────────────────────────────────────────────────────────────────
@admin_bp.route('/ratings')
@admin_required
def ratings():
    page = request.args.get('page', 1, type=int)
    pagination = (Rating.query.order_by(Rating.created_at.desc())
                  .paginate(page=page, per_page=30))
    rating_list = pagination.items
    user_ids = [r.user_id for r in rating_list]
    book_ids = [r.book_id for r in rating_list]
    users_map = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}
    books_map = {b.id: b for b in Book.query.filter(Book.id.in_(book_ids)).all()}
    return render_template('admin/ratings.html',
                           ratings=rating_list,
                           pagination=pagination,
                           users_map=users_map,
                           books_map=books_map)


@admin_bp.route('/ratings/<int:rating_id>/delete', methods=['POST'])
@admin_required
def delete_rating(rating_id):
    r = db.get_or_404(Rating, rating_id)
    db.session.delete(r)
    db.session.commit()
    return jsonify({'status': 'ok'})


# ─── CSV Import ───────────────────────────────────────────────────────────────
@admin_bp.route('/import', methods=['GET', 'POST'])
@admin_required
def import_csv():
    if request.method == 'POST':
        import subprocess, sys, os
        csv_path = request.form.get('csv_path', 'data/goodreads_books_dataset.csv').strip()
        # Prevent path traversal: only allow paths inside the project data/ directory
        safe_base = os.path.abspath('data')
        abs_path  = os.path.abspath(csv_path)
        if not abs_path.startswith(safe_base):
            flash('Invalid file path — must be inside the data/ directory.', 'danger')
            return redirect(url_for('admin.import_csv'))
        if not os.path.exists(abs_path):
            flash(f'File not found: {csv_path}', 'danger')
            return redirect(url_for('admin.import_csv'))
        result = subprocess.run(
            [sys.executable, 'scripts/load_csv.py', '--csv', csv_path],
            capture_output=True, text=True
        )
        output = result.stdout + result.stderr
        flash('Import complete! Check output below.', 'success')
        return render_template('admin/import.html', output=output, csv_path=csv_path)
    return render_template('admin/import.html', output=None, csv_path='data/books.csv')