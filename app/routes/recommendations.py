from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app.models import Book, RecommendationCache
from app.services.recommendation_engine import RecommendationEngine

recs_bp = Blueprint('recs', __name__)


@recs_bp.route('/')
@login_required
def index():
    cache = RecommendationCache.query.filter_by(user_id=current_user.id).first()

    if cache:
        books     = Book.query.filter(Book.id.in_(cache.book_ids)).all()
        id_order  = {bid: i for i, bid in enumerate(cache.book_ids)}
        books     = sorted(books, key=lambda b: id_order.get(b.id, 999))
        algo      = cache.algo_used
    else:
        engine    = RecommendationEngine()
        book_ids, algo = engine.recommend(current_user.id)
        books     = Book.query.filter(Book.id.in_(book_ids)).all()
        id_order  = {bid: i for i, bid in enumerate(book_ids)}
        books     = sorted(books, key=lambda b: id_order.get(b.id, 999))

    return render_template('recommendations/index.html',
                           books=books, algo=algo)


@recs_bp.route('/api/refresh', methods=['POST'])
@login_required
def api_refresh():
    from app import db
    cache = RecommendationCache.query.filter_by(user_id=current_user.id).first()
    if cache:
        db.session.delete(cache)
        db.session.commit()

    engine = RecommendationEngine()
    book_ids, algo = engine.recommend(current_user.id)
    books = Book.query.filter(Book.id.in_(book_ids)).all()
    id_order = {bid: i for i, bid in enumerate(book_ids)}
    books = sorted(books, key=lambda b: id_order.get(b.id, 999))

    data = [{'id': b.id, 'title': b.title, 'author': b.author,
              'cover': b.cover(), 'avg': b.average_rating} for b in books]
    return jsonify({'status': 'ok', 'books': data, 'algo': algo})
