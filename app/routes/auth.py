from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlsplit
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app import db
from app.models import User
from datetime import datetime

auth_bp = Blueprint('auth', __name__)


# ─── Forms ────────────────────────────────────────────────────────────────────
class LoginForm(FlaskForm):
    email    = StringField('Email',    validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember me')
    submit   = SubmitField('Sign In')


class RegisterForm(FlaskForm):
    username  = StringField('Username',  validators=[DataRequired(), Length(3, 80)])
    email     = StringField('Email',     validators=[DataRequired(), Email()])
    password  = PasswordField('Password', validators=[DataRequired(), Length(8, 128)])
    password2 = PasswordField('Confirm Password',
                              validators=[DataRequired(), EqualTo('password')])
    submit    = SubmitField('Create Account')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')


# ─── Routes ───────────────────────────────────────────────────────────────────
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('books.home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been suspended.', 'danger')
                return redirect(url_for('auth.login'))
            login_user(user, remember=form.remember.data)
            user.last_login = datetime.utcnow()
            db.session.commit()
            next_page = request.args.get('next')
            # Prevent open redirect: only allow relative URLs
            if next_page and urlsplit(next_page).netloc:
                next_page = None
            return redirect(next_page or url_for('books.home'))
        flash('Invalid email or password.', 'danger')
    return render_template('auth/login.html', form=form, title='Sign In')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('books.home'))
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.lower().strip(),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Welcome to BookShelf! Start by rating some books.', 'success')
        return redirect(url_for('books.browse'))
    return render_template('auth/register.html', form=form, title='Create Account')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('books.home'))