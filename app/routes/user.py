from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, ValidationError
from app import db
from app.models import Book, Rating, Wishlist, ReadHistory, Genre, UserGenrePref, User

user_bp = Blueprint('user', __name__)


class EditProfileForm(FlaskForm):
    username   = StringField('Username',  validators=[DataRequired(), Length(3, 80)])
    bio        = TextAreaField('Bio',      validators=[Optional(), Length(max=500)])
    avatar_url = StringField('Avatar URL', validators=[Optional(), Length(max=512)])
    submit     = SubmitField('Save Changes')

    def __init__(self, original_username, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, field):
        if field.data != self.original_username:
            if User.query.filter_by(username=field.data).first():
                raise ValidationError('Username already taken.')


@user_bp.route('/profile')
@login_required
def profile():
    ratings    = (Rating.query.filter_by(user_id=current_user.id)
                  .order_by(Rating.updated_at.desc()).limit(20).all())
    wishlist   = (Wishlist.query.filter_by(user_id=current_user.id)
                  .order_by(Wishlist.added_at.desc()).limit(12).all())
    history    = (ReadHistory.query.filter_by(user_id=current_user.id)
                  .order_by(ReadHistory.read_at.desc()).limit(12).all())

    # Genre taste — top 6 prefs
    prefs      = (UserGenrePref.query.filter_by(user_id=current_user.id)
                  .order_by(UserGenrePref.weight.desc()).limit(6).all())
    taste_labels = [p.genre.name for p in prefs]
    taste_data   = [round(p.weight, 2) for p in prefs]

    # Rating distribution for chart
    dist = {i: 0 for i in range(1, 6)}
    for r in Rating.query.filter_by(user_id=current_user.id).all():
        key = round(r.rating)
        if key in dist:
            dist[key] += 1

    book_ids   = [r.book_id for r in ratings]
    books_map  = {b.id: b for b in Book.query.filter(Book.id.in_(book_ids)).all()}

    wish_ids   = [w.book_id for w in wishlist]
    wish_books = {b.id: b for b in Book.query.filter(Book.id.in_(wish_ids)).all()}

    hist_ids   = [h.book_id for h in history]
    hist_books = {b.id: b for b in Book.query.filter(Book.id.in_(hist_ids)).all()}

    return render_template('user/profile.html',
                           ratings=ratings,
                           wishlist=wishlist,
                           history=history,
                           books_map=books_map,
                           wish_books=wish_books,
                           hist_books=hist_books,
                           taste_labels=taste_labels,
                           taste_data=taste_data,
                           dist=dist)


@user_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(original_username=current_user.username, obj=current_user)
    if form.validate_on_submit():
        current_user.username   = form.username.data.strip()
        current_user.bio        = form.bio.data
        current_user.avatar_url = form.avatar_url.data
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('user.profile'))
    return render_template('user/edit_profile.html', form=form)


@user_bp.route('/wishlist')
@login_required
def wishlist():
    items  = (Wishlist.query.filter_by(user_id=current_user.id)
              .order_by(Wishlist.added_at.desc()).all())
    ids    = [w.book_id for w in items]
    books  = {b.id: b for b in Book.query.filter(Book.id.in_(ids)).all()}
    return render_template('user/wishlist.html', wishlist=items, books=books)