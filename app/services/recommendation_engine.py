import numpy as np
import pandas as pd
from scipy.sparse.linalg import svds
from sklearn.preprocessing import MultiLabelBinarizer
from app import db
from app.models import Book, Rating, Genre, UserGenrePref, RecommendationCache


class RecommendationEngine:
    """
    Three-algorithm recommendation engine:
    - Content-based  (<5 ratings)
    - Collaborative  (SVD, ≥5 ratings)
    - Hybrid blend   (default for experienced users)
    """

    def recommend(self, user_id: int, n: int = 20):
        rating_count = Rating.query.filter_by(user_id=user_id).count()

        if rating_count < 5:
            book_ids = self._content_based(user_id, n)
            algo = 'content'
        elif rating_count < 20:
            try:
                book_ids = self._collaborative(user_id, n)
                algo = 'collaborative'
            except Exception:
                book_ids = self._content_based(user_id, n)
                algo = 'content'
        else:
            try:
                book_ids = self._hybrid(user_id, n)
                algo = 'hybrid'
            except Exception:
                book_ids = self._content_based(user_id, n)
                algo = 'content'

        # Cache the result
        existing = RecommendationCache.query.filter_by(user_id=user_id).first()
        if existing:
            existing.book_ids  = book_ids
            existing.algo_used = algo
        else:
            db.session.add(RecommendationCache(
                user_id=user_id, book_ids=book_ids, algo_used=algo))
        db.session.commit()

        return book_ids, algo

    # ── Content-based ─────────────────────────────────────────────────────────
    def _content_based(self, user_id: int, n: int):
        all_books = Book.query.all()
        if not all_books:
            return []

        # Build genre feature matrix
        book_ids = [b.id for b in all_books]
        genre_lists = [[g.name for g in b.genres] for b in all_books]

        mlb = MultiLabelBinarizer()
        genre_matrix = mlb.fit_transform(genre_lists)  # (books, genres)

        # User genre preference vector
        prefs = UserGenrePref.query.filter_by(user_id=user_id).all()
        genre_name_to_idx = {g: i for i, g in enumerate(mlb.classes_)}
        user_vec = np.zeros(len(mlb.classes_))
        if prefs:
            for p in prefs:
                name = p.genre.name
                if name in genre_name_to_idx:
                    user_vec[genre_name_to_idx[name]] = p.weight
        else:
            user_vec[:] = 1.0  # flat prior for cold start

        # Genre score = dot product
        genre_scores = genre_matrix.dot(user_vec)

        # Normalise popularity (log scale)
        popularities = np.array([b.ratings_count or 0 for b in all_books], dtype=float)
        max_pop = popularities.max() if popularities.max() > 0 else 1
        pop_scores = np.log1p(popularities) / np.log1p(max_pop)

        # Already-rated book IDs
        rated_ids = {r.book_id for r in Rating.query.filter_by(user_id=user_id).all()}

        # Blend
        blended = 0.7 * genre_scores + 0.3 * pop_scores
        scored  = [(book_ids[i], float(blended[i]))
                   for i in range(len(book_ids)) if book_ids[i] not in rated_ids]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [bid for bid, _ in scored[:n]]

    # ── Collaborative (SVD) ───────────────────────────────────────────────────
    def _collaborative(self, user_id: int, n: int):
        rows = db.session.execute(
            db.text("SELECT user_id, book_id, rating FROM ratings")
        ).fetchall()
        if len(rows) < 10:
            return self._content_based(user_id, n)

        df = pd.DataFrame(rows, columns=['user_id', 'book_id', 'rating'])
        pivot = df.pivot_table(index='user_id', columns='book_id',
                               values='rating', fill_value=0)

        if user_id not in pivot.index:
            return self._content_based(user_id, n)

        matrix = pivot.values.astype(float)
        k = min(20, min(matrix.shape) - 1)
        if k < 1:
            return self._content_based(user_id, n)

        U, sigma, Vt = svds(matrix, k=k)
        sigma_diag   = np.diag(sigma)
        predicted    = np.dot(np.dot(U, sigma_diag), Vt)
        pred_df      = pd.DataFrame(predicted,
                                    index=pivot.index, columns=pivot.columns)

        user_row   = pred_df.loc[user_id]
        rated_ids  = set(pivot.columns[pivot.loc[user_id] > 0].tolist())
        unrated    = {col: user_row[col]
                      for col in pivot.columns if col not in rated_ids}
        sorted_recs = sorted(unrated.items(), key=lambda x: x[1], reverse=True)
        return [int(bid) for bid, _ in sorted_recs[:n]]

    # ── Hybrid ────────────────────────────────────────────────────────────────
    def _hybrid(self, user_id: int, n: int):
        collab   = self._collaborative(user_id, n * 2)
        content  = self._content_based(user_id, n * 2)

        # Score maps
        collab_score  = {bid: (len(collab) - i) for i, bid in enumerate(collab)}
        content_score = {bid: (len(content) - i) for i, bid in enumerate(content)}

        all_ids = set(collab) | set(content)
        blended = {}
        for bid in all_ids:
            c1 = collab_score.get(bid, 0)
            c2 = content_score.get(bid, 0)
            blended[bid] = 0.6 * c1 + 0.4 * c2

        sorted_ids = sorted(blended.items(), key=lambda x: x[1], reverse=True)
        return [int(bid) for bid, _ in sorted_ids[:n]]
