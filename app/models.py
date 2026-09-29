from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

# ─── Association table ────────────────────────────────────────────────────────
book_genres = db.Table(
    'book_genres',
    db.Column('book_id',  db.Integer, db.ForeignKey('books.id'),  primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('genres.id'), primary_key=True),
    extend_existing=True
)


# ─── User ─────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}

    id             = db.Column(db.Integer, primary_key=True)
    username       = db.Column(db.String(80), unique=True, nullable=False)
    email          = db.Column(db.String(120), unique=True, nullable=False)
    password_hash  = db.Column(db.String(256), nullable=False)
    avatar_url     = db.Column(db.String(512))
    bio            = db.Column(db.Text)
    is_active      = db.Column(db.Boolean, default=True, nullable=False)
    is_admin       = db.Column(db.Boolean, default=False, nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow,
                               onupdate=datetime.utcnow, nullable=False)
    last_login     = db.Column(db.DateTime)

    ratings        = db.relationship('Rating',       backref='user', lazy='dynamic', cascade='all,delete')
    wishlist_items = db.relationship('Wishlist',      backref='user', lazy='dynamic', cascade='all,delete')
    read_items     = db.relationship('ReadHistory',   backref='user', lazy='dynamic', cascade='all,delete')
    genre_prefs    = db.relationship('UserGenrePref', backref='user', lazy='dynamic', cascade='all,delete')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def rating_count(self):
        return self.ratings.count()

    def __repr__(self):
        return f'<User {self.username}>'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ─── Genre ────────────────────────────────────────────────────────────────────
class Genre(db.Model):
    __tablename__ = 'genres'
    __table_args__ = {'extend_existing': True}

    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    def __repr__(self):
        return f'<Genre {self.name}>'


# ─── Book ─────────────────────────────────────────────────────────────────────
class Book(db.Model):
    __tablename__ = 'books'
    __table_args__ = {'extend_existing': True}

    id                 = db.Column(db.Integer, primary_key=True)
    # Identifiers
    isbn               = db.Column(db.String(30))
    isbn13             = db.Column(db.String(20))
    external_id        = db.Column(db.String(256))          # raw id from CSV e.g. show/1234.Title
    # Core metadata
    title              = db.Column(db.String(512), nullable=False)
    series             = db.Column(db.String(256))          # e.g. "BTTH, #1"
    author             = db.Column(db.String(512))
    publisher          = db.Column(db.String(256))
    description        = db.Column(db.Text)
    cover_image_url    = db.Column(db.String(1024))
    publication_date   = db.Column(db.String(50))
    page_count         = db.Column(db.Integer)
    language           = db.Column(db.String(50))
    # Classification
    category           = db.Column(db.String(256))          # e.g. "Web Novel (Xianxia)"
    region             = db.Column(db.String(100))          # e.g. "China"
    # External links
    amazon_link        = db.Column(db.String(1024))
    free_source_link   = db.Column(db.String(1024))
    free_source_name   = db.Column(db.String(256))          # e.g. "Official Translation"
    # Stats
    average_rating     = db.Column(db.Float, default=0.0)
    ratings_count      = db.Column(db.Integer, default=0)
    text_reviews_count = db.Column(db.Integer, default=0)
    popularity         = db.Column(db.Float, default=0.0)
    # Timestamps
    created_at         = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at         = db.Column(db.DateTime, default=datetime.utcnow,
                                   onupdate=datetime.utcnow, nullable=False)

    genres  = db.relationship('Genre', secondary=book_genres, lazy='subquery',
                              backref=db.backref('books', lazy=True))
    ratings = db.relationship('Rating',      backref='book', lazy='dynamic', cascade='all,delete')
    wishers = db.relationship('Wishlist',    backref='book', lazy='dynamic', cascade='all,delete')
    readers = db.relationship('ReadHistory', backref='book', lazy='dynamic', cascade='all,delete')

    def cover(self):
        if self.cover_image_url and self.cover_image_url.startswith('http'):
            return self.cover_image_url
        if self.isbn13:
            return f'https://covers.openlibrary.org/b/isbn/{self.isbn13}-M.jpg'
        if self.isbn and self.isbn.lower() not in ('n/a', 'na', 'none', ''):
            return f'https://covers.openlibrary.org/b/isbn/{self.isbn}-M.jpg'
        return None

    def __repr__(self):
        return f'<Book {self.title[:40]}>'


# ─── Rating ───────────────────────────────────────────────────────────────────
class Rating(db.Model):
    __tablename__ = 'ratings'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'book_id', name='uq_user_book'),
        {'extend_existing': True},
    )

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id    = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    rating     = db.Column(db.Float, nullable=False)
    review     = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow, nullable=False)


# ─── Read History ─────────────────────────────────────────────────────────────
class ReadHistory(db.Model):
    __tablename__ = 'read_history'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'book_id', name='uq_user_book_hist'),
        {'extend_existing': True},
    )

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id    = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    read_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    read_count = db.Column(db.Integer, default=1, nullable=False)


# ─── Wishlist ─────────────────────────────────────────────────────────────────
class Wishlist(db.Model):
    __tablename__ = 'wishlists'

    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id  = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'book_id', name='uq_user_book_wish'),
        {'extend_existing': True},
    )


# ─── User Genre Preference ───────────────────────────────────────────────────
class UserGenrePref(db.Model):
    __tablename__ = 'user_genre_prefs'
    __table_args__ = {'extend_existing': True}

    user_id  = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    genre_id = db.Column(db.Integer, db.ForeignKey('genres.id'), primary_key=True)
    weight   = db.Column(db.Float, default=1.0, nullable=False)

    genre = db.relationship('Genre')


# ─── Recommendation Cache ─────────────────────────────────────────────────────
class RecommendationCache(db.Model):
    __tablename__ = 'recommendation_cache'
    __table_args__ = {'extend_existing': True}
    
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    book_ids   = db.Column(db.JSON, nullable=False)
    algo_used  = db.Column(db.String(50), default='content', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)