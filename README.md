# 📚 Book Recommender

A Flask-based book recommendation system powered by a Goodreads dataset with content-based, collaborative, and hybrid recommendation algorithms.

---

## 🗂️ Project Structure

```
book_recommender/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── models.py            # SQLAlchemy models
│   ├── routes/
│   │   ├── auth.py          # Login / Register
│   │   ├── books.py         # Browse, Detail, Rate
│   │   ├── recommendations.py
│   │   ├── user.py          # Profile, Wishlist
│   │   └── admin.py         # Admin dashboard
│   ├── services/
│   │   └── recommendation_engine.py
│   └── templates/
├── data/
│   └── goodreads_books_dataset.csv   ← your dataset
├── database/
│   └── schema.sql           # Run once in MySQL Workbench
├── scripts/
│   ├── load_csv.py          # Import CSV → MySQL
│   └── create_admin.py      # Create admin user
├── config.py
├── run.py
├── .env                     # ← copy from .env.example and fill in
└── requirements.txt
```

---

## ⚙️ Step 1 — Install dependencies

```bash
pip install -r requirements.txt
```

---

## 🗄️ Step 2 — MySQL Workbench Setup

### 2a. Create a new connection

1. Open **MySQL Workbench**
2. Click the **+** next to "MySQL Connections"
3. Fill in:
   - **Connection Name:** `book_recommender`
   - **Hostname:** `localhost`
   - **Port:** `3306`
   - **Username:** `root`
   - **Password:** click *Store in Vault* → enter your MySQL root password
4. Click **Test Connection** → should show *Successfully made the MySQL connection*
5. Click **OK**

### 2b. Run the schema

1. Open the connection you just created
2. Go to **File → Open SQL Script** → select `database/schema.sql`
3. Press **Ctrl+Shift+Enter** (or the lightning bolt ⚡ icon) to run all
4. You should see all tables created: `users`, `books`, `genres`, `book_genres`, `ratings`, `read_history`, `wishlists`, `user_genre_prefs`, `recommendation_cache`

---

## 🔑 Step 3 — Configure environment

Copy `.env.example` to `.env` and fill in your MySQL password:

```bash
cp .env.example .env
```

Edit `.env`:
```
FLASK_ENV=development
SECRET_KEY=pick-a-long-random-string

DB_USER=root
DB_PASSWORD=your_mysql_password_here
DB_HOST=localhost
DB_PORT=3306
DB_NAME=book_recommender
```

---

## 📥 Step 4 — Load the CSV dataset

```bash
# Full import (may take a few minutes for large dataset)
python scripts/load_csv.py --csv data/goodreads_books_dataset.csv

# Quick test with first 1000 rows
python scripts/load_csv.py --csv data/goodreads_books_dataset.csv --limit 1000
```

**What the loader handles automatically:**
- `author` field is a JSON dict → extracts the `name` key
- `ISBN` stored as float (e.g. `9789123926053.0`) → converts to string
- `language` full names (e.g. "English") → normalises to 2-letter codes ("en")
- Open Library cover fallback when `imageURL` is empty
- Genre deduplication across rows

---

## 👤 Step 5 — Create admin user

```bash
python scripts/create_admin.py
```

Follow the prompts to set a username, email, and password.

---

## 🚀 Step 6 — Run the app

```bash
python run.py
```

Open [http://localhost:5000](http://localhost:5000)

---

## 🔌 MySQL Workbench — Verifying the connection

After loading data, verify in Workbench:

```sql
USE book_recommender;

SELECT COUNT(*) FROM books;
SELECT COUNT(*) FROM genres;
SELECT title, author, average_rating FROM books ORDER BY ratings_count DESC LIMIT 10;
SELECT name, COUNT(bg.book_id) as total FROM genres g
  JOIN book_genres bg ON bg.genre_id = g.id
  GROUP BY g.id ORDER BY total DESC LIMIT 10;
```

---

## 📊 Dataset Column Mapping

| CSV Column       | DB Column           | Notes                              |
|------------------|---------------------|------------------------------------|
| `title`          | `title`             | —                                  |
| `author`         | `author`            | JSON dict → extracts `.name`       |
| `ISBN`           | `isbn13`            | Float → string conversion          |
| `imageURL`       | `cover_image_url`   | —                                  |
| `pages`          | `page_count`        | —                                  |
| `publicationDate`| `publication_date`  | —                                  |
| `language`       | `language`          | "English" → "en"                   |
| `rating`         | `average_rating`    | —                                  |
| `ratings`        | `ratings_count`     | —                                  |
| `genres`         | `genres` (M2M)      | JSON list → Genre table            |
| `description`    | `description`       | —                                  |

---

## 🤖 Recommendation Algorithms

| User rating count | Algorithm used |
|-------------------|----------------|
| < 5               | Content-based (genre similarity) |
| 5–19              | Collaborative filtering (SVD) |
| ≥ 20              | Hybrid (blend of both) |

---

## 🐛 Common Issues

**`ModuleNotFoundError: No module named 'app'`**
→ Run all scripts from the project root: `cd book_recommender && python scripts/load_csv.py`

**`Access denied for user 'root'`**
→ Check `DB_PASSWORD` in your `.env` file matches your MySQL root password

**`Unknown database 'book_recommender'`**
→ Run `database/schema.sql` in MySQL Workbench first (Step 2b)

**`sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) Can't connect`**
→ Make sure MySQL service is running: `sudo systemctl start mysql` (Linux) or start MAMP/WAMP
