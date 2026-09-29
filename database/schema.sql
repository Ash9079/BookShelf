-- Book Recommender — Full MySQL Schema
-- Run once: mysql -u root -p book_recommender < database/schema.sql

CREATE DATABASE IF NOT EXISTS book_recommender
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE book_recommender;

-- ─── Users ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    username         VARCHAR(80)  NOT NULL UNIQUE,
    email            VARCHAR(120) NOT NULL UNIQUE,
    password_hash    VARCHAR(256) NOT NULL,
    avatar_url       VARCHAR(512),
    bio              TEXT,
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    is_admin         BOOLEAN      NOT NULL DEFAULT FALSE,
    is_super_admin   BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login       DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─── Genres ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS genres (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─── Books ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS books (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    -- Identifiers
    isbn                VARCHAR(30),
    isbn13              VARCHAR(20),
    external_id         VARCHAR(256),
    -- Core metadata
    title               VARCHAR(512) NOT NULL,
    series              VARCHAR(256),
    author              VARCHAR(512),
    publisher           VARCHAR(256),
    description         TEXT,
    cover_image_url     VARCHAR(1024),
    publication_date    VARCHAR(50),
    page_count          INT,
    language            VARCHAR(50),
    -- Classification
    category            VARCHAR(256),
    region              VARCHAR(100),
    -- External links
    amazon_link         VARCHAR(1024),
    free_source_link    VARCHAR(1024),
    free_source_name    VARCHAR(256),
    -- Stats
    average_rating      FLOAT        DEFAULT 0.0,
    ratings_count       INT          DEFAULT 0,
    text_reviews_count  INT          DEFAULT 0,
    popularity          FLOAT        DEFAULT 0.0,
    -- Timestamps
    created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─── Book ↔ Genre (many-to-many) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS book_genres (
    book_id   INT NOT NULL,
    genre_id  INT NOT NULL,
    PRIMARY KEY (book_id, genre_id),
    FOREIGN KEY (book_id)  REFERENCES books(id)  ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genres(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─── Ratings / Reviews ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ratings (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT   NOT NULL,
    book_id    INT   NOT NULL,
    rating     FLOAT NOT NULL,
    review     TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_book (user_id, book_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─── Read History ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS read_history (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT NOT NULL,
    book_id    INT NOT NULL,
    read_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_count INT      NOT NULL DEFAULT 1,
    UNIQUE KEY uq_user_book_hist (user_id, book_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─── Wishlist ("Want to Read") ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wishlists (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    user_id  INT NOT NULL,
    book_id  INT NOT NULL,
    added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_book_wish (user_id, book_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─── User Genre Preferences ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_genre_prefs (
    user_id  INT   NOT NULL,
    genre_id INT   NOT NULL,
    weight   FLOAT NOT NULL DEFAULT 1.0,
    PRIMARY KEY (user_id, genre_id),
    FOREIGN KEY (user_id)  REFERENCES users(id)  ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genres(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─── Recommendation Cache ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recommendation_cache (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT         NOT NULL UNIQUE,
    book_ids   JSON        NOT NULL,
    algo_used  VARCHAR(50) NOT NULL DEFAULT 'content',
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─── Indexes ─────────────────────────────────────────────────────────────────
CREATE INDEX idx_books_title          ON books(title(255));
CREATE INDEX idx_books_author         ON books(author(255));
CREATE INDEX idx_books_language       ON books(language);
CREATE INDEX idx_books_avg_rating     ON books(average_rating);
CREATE INDEX idx_books_ratings_count  ON books(ratings_count);
CREATE INDEX idx_books_category       ON books(category(100));
CREATE INDEX idx_books_region         ON books(region);
CREATE INDEX idx_ratings_user         ON ratings(user_id);
CREATE INDEX idx_ratings_book         ON ratings(book_id);
CREATE INDEX idx_wishlist_user        ON wishlists(user_id);
CREATE INDEX idx_history_user         ON read_history(user_id);

-- ─── Migration: add new columns to existing books table ──────────────────────
-- Run this block if you already have a books table and need to add the new columns:
-- ALTER TABLE books ADD COLUMN IF NOT EXISTS external_id       VARCHAR(256);
-- ALTER TABLE books ADD COLUMN IF NOT EXISTS series            VARCHAR(256);
-- ALTER TABLE books ADD COLUMN IF NOT EXISTS category          VARCHAR(256);
-- ALTER TABLE books ADD COLUMN IF NOT EXISTS region            VARCHAR(100);
-- ALTER TABLE books ADD COLUMN IF NOT EXISTS amazon_link       VARCHAR(1024);
-- ALTER TABLE books ADD COLUMN IF NOT EXISTS free_source_link  VARCHAR(1024);
-- ALTER TABLE books ADD COLUMN IF NOT EXISTS free_source_name  VARCHAR(256);