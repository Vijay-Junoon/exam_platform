from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from services.auth_service import AuthService
from forms import RegistrationForm, LoginForm

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Renders registration page for teachers."""
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('exam.intro'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user, error = AuthService.register_user(
            name=form.name.data,
            email=form.email.data,
            password=form.password.data,
            role='teacher' # default registration is for teachers
        )
        if error:
            flash(error, 'danger')
        else:
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
            
    return render_template('auth/register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Processes user logins (Teachers and Admins)."""
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('exam.intro'))

    form = LoginForm()
    if form.validate_on_submit():
        user = AuthService.authenticate_user(form.email.data, form.password.data)
        if user:
            login_user(user)
            flash(f"Welcome back, {user.name}!", "success")
            
            # Check next parameter
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
                
            # Redirect by role
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('exam.intro'))
        else:
            flash("Invalid email or password.", "danger")
            
    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Logs the user out and clears the session."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))
