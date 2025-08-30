#!/usr/bin/env python3
"""
Flask web application for the Map Contour Mapper with monetization.
Includes user accounts, credit system, and Stripe payment integration.
"""

import os
import tempfile
import uuid
from datetime import datetime
from typing import Tuple, Optional
import secrets

from flask import Flask, render_template, request, send_file, flash, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, IntegerField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange
import bcrypt
import stripe
import numpy as np

# Import our existing contour mapping logic
from map_contour_mapper.__main__ import (
    build_elevation_mosaic,
    fetch_roads_overpass,
    scale_coordinates_to_output,
    lonlat_to_global_pixel,
    TILE_SIZE
)

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
from PIL import Image

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///contour_mapper.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Fix for Railway PostgreSQL URL format
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
db = SQLAlchemy(app)

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to generate maps.'
login_manager.login_message_category = 'info'

# Stripe configuration
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_51S15WBRvJytiBse44P6cMYlIX9mV47mayc4H8uwclOUf6KCrI05huzz0LdePMWgkiY5BJtTaks4MxwMRne2vKr5C00wFnoR92G')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', 'pk_test_51S15WBRvJytiBse4ko0IKFuSxfdS1E28kMWcSJK7Aex9YXyaARQQGGRN5FV9FFqZ0yAKj9PYSKYZgVnCDBLpLVMt008ahSekfL')
stripe.api_key = STRIPE_SECRET_KEY

# Create uploads directory
UPLOAD_FOLDER = 'static/generated_maps'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Pricing configuration
CREDIT_PRICES = {
    1: {'price': 200, 'description': '1 credit'},        # $2.00
    5: {'price': 1000, 'description': '5 credits'},      # $10.00
    15: {'price': 3000, 'description': '15 credits'},    # $30.00
    50: {'price': 10000, 'description': '50 credits'},   # $100.00
}

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    credits = db.Column(db.Integer, default=1)  # 1 free credit to start
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    maps_generated = db.relationship('GeneratedMap', backref='user', lazy=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash)

class GeneratedMap(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    bbox = db.Column(db.String(100), nullable=False)
    settings = db.Column(db.Text)  # JSON string of settings
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    stripe_payment_intent_id = db.Column(db.String(255), unique=True)
    credits_purchased = db.Column(db.Integer, nullable=False)
    amount_paid = db.Column(db.Integer, nullable=False)  # in cents
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Forms
class RegistrationForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), EqualTo('password')])

class LoginForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])

class PurchaseCreditsForm(FlaskForm):
    credit_package = SelectField('Credit Package', coerce=int, 
                                choices=[(k, f"{v['description']} - ${v['price']/100:.2f}") 
                                        for k, v in CREDIT_PRICES.items()])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def validate_bbox(bbox_str: str) -> Tuple[float, float, float, float]:
    """Validate and parse bounding box string."""
    try:
        parts = [float(p.strip()) for p in bbox_str.split(",")]
        if len(parts) != 4:
            raise ValueError("Bounding box must have 4 values")
        
        min_lon, min_lat, max_lon, max_lat = parts
        
        if not (min_lon < max_lon and min_lat < max_lat):
            raise ValueError("Invalid bbox: ensure min < max for lon and lat")
        
        # Basic coordinate validation
        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        
        if not (-85 <= min_lat <= 85 and -85 <= max_lat <= 85):
            raise ValueError("Latitude must be between -85 and 85")
        
        return min_lon, min_lat, max_lon, max_lat
    
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid bounding box format: {e}")

def generate_contour_map(
    bbox: Tuple[float, float, float, float],
    interval: float,
    background_color: str,
    include_roads: bool,
    width: int,
    height: int,
    user_id: int
) -> str:
    """Generate contour map and return the filename."""
    
    min_lon, min_lat, max_lon, max_lat = bbox
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    filename = f"contour_map_{timestamp}_{unique_id}.png"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        # Calculate appropriate zoom level based on bounding box size
        lon_diff = max_lon - min_lon
        lat_diff = max_lat - min_lat
        area_size = max(lon_diff, lat_diff)
        
        # Auto-select zoom level based on area size
        if area_size > 2.0:
            zoom = 8   # Very large area
        elif area_size > 1.0:
            zoom = 9   # Large area
        elif area_size > 0.5:
            zoom = 10  # Medium-large area
        elif area_size > 0.2:
            zoom = 11  # Medium area
        elif area_size > 0.1:
            zoom = 12  # Medium-small area
        elif area_size > 0.05:
            zoom = 13  # Small area
        else:
            zoom = 14  # Very small area
        
        # Build elevation mosaic
        elev, crop_box, origin = build_elevation_mosaic(bbox, zoom)
        left, top, right, bottom = crop_box
        origin_global_px_x, origin_global_px_y = origin
        
        # Resize elevation to requested output resolution
        src_h, src_w = elev.shape
        scale_y = height / src_h
        scale_x = width / src_w
        elev_img = Image.fromarray(elev, mode="F")
        elev_resized_img = elev_img.resize((width, height), resample=Image.BILINEAR)
        elev_resized = np.array(elev_resized_img, dtype=np.float32)
        
        # Prepare contour levels
        finite_vals = elev_resized[np.isfinite(elev_resized)]
        if finite_vals.size == 0:
            raise ValueError("No finite elevation values found in the area.")
        
        min_e = float(np.nanmin(finite_vals))
        max_e = float(np.nanmax(finite_vals))
        
        if interval <= 0:
            interval = max(1.0, (max_e - min_e) / 15.0)
        
        import math
        start = math.floor(min_e / interval) * interval
        stop = math.ceil(max_e / interval) * interval
        levels = np.arange(start, stop + interval, interval)
        
        # Create the plot
        fig = plt.figure(figsize=(width / 100.0, height / 100.0), dpi=100, facecolor=background_color)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor(background_color)
        
        # Draw contours
        x_coords = np.linspace(0, width, elev_resized.shape[1])
        y_coords = np.linspace(0, height, elev_resized.shape[0])
        ax.contour(x_coords, y_coords, elev_resized, levels=levels, colors="black", linewidths=0.6)
        
        # Add roads if requested
        if include_roads:
            try:
                road_lines_lonlat = fetch_roads_overpass(bbox)
                scaled_lines = scale_coordinates_to_output(
                    road_lines_lonlat,
                    zoom,
                    origin_global_px_x,
                    origin_global_px_y,
                    left,
                    top,
                    scale_x,
                    scale_y,
                )
                for arr in scaled_lines:
                    ax.plot(arr[:, 0], arr[:, 1], color="black", linewidth=1.0, alpha=0.9)
            except Exception as e:
                print(f"Warning: failed to fetch/plot roads: {e}")
        
        ax.set_xlim(0, width)
        ax.set_ylim(height, 0)
        ax.axis("off")
        
        # Save the figure
        fig.savefig(filepath, dpi=100, facecolor=background_color, bbox_inches="tight", pad_inches=0)
        plt.close(fig)
        
        # Save to database
        settings = f"interval:{interval},bg:{background_color},roads:{include_roads},resolution:{width}x{height}"
        generated_map = GeneratedMap(
            user_id=user_id,
            filename=filename,
            bbox=f"{min_lon},{min_lat},{max_lon},{max_lat}",
            settings=settings
        )
        db.session.add(generated_map)
        db.session.commit()
        
        return filename
    
    except Exception as e:
        # Clean up file if it was created
        if os.path.exists(filepath):
            os.remove(filepath)
        raise e

# Routes
@app.route('/')
def index():
    """Main page - show pricing if not logged in, form if logged in."""
    if current_user.is_authenticated:
        return render_template('index_monetized.html', credits=current_user.credits)
    else:
        return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if user already exists
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered. Please log in instead.', 'error')
            return redirect(url_for('login'))
        
        # Create new user
        password_hash = bcrypt.hashpw(form.password.data.encode('utf-8'), bcrypt.gensalt())
        user = User(email=form.email.data, password_hash=password_hash)
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        flash(f'Welcome! You have {user.credits} free credits to get started.', 'success')
        return redirect(url_for('index'))
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            flash(f'Welcome back! You have {user.credits} credits.', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """User logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/pricing')
def pricing():
    """Pricing page."""
    return render_template('pricing.html', credit_prices=CREDIT_PRICES)

@app.route('/purchase', methods=['GET', 'POST'])
@login_required
def purchase_credits():
    """Purchase credits page."""
    form = PurchaseCreditsForm()
    
    if form.validate_on_submit():
        credits = form.credit_package.data
        price = CREDIT_PRICES[credits]['price']
        
        try:
            print(f"Creating Stripe payment intent for {credits} credits at ${price/100:.2f}")
            print(f"Stripe API key configured: {stripe.api_key[:20]}...")
            
            # Create Stripe payment intent
            intent = stripe.PaymentIntent.create(
                amount=price,
                currency='usd',
                metadata={
                    'user_id': current_user.id,
                    'credits': credits,
                },
                automatic_payment_methods={
                    'enabled': True,
                }
            )
            
            print(f"Payment intent created: {intent.id}")
            print(f"Client secret exists: {intent.client_secret is not None}")
            
            # Save transaction to database
            transaction = Transaction(
                user_id=current_user.id,
                stripe_payment_intent_id=intent.id,
                credits_purchased=credits,
                amount_paid=price
            )
            db.session.add(transaction)
            db.session.commit()
            
            return render_template('checkout.html', 
                                 client_secret=intent.client_secret,
                                 stripe_publishable_key=STRIPE_PUBLISHABLE_KEY,
                                 credits=credits,
                                 price=price)
        
        except Exception as e:
            print(f"Stripe error: {str(e)}")
            print(f"Error type: {type(e)}")
            flash(f'Error creating payment: {str(e)}', 'error')
    
    return render_template('purchase.html', form=form, credit_prices=CREDIT_PRICES)

@app.route('/payment-success')
@login_required
def payment_success():
    """Handle successful payment."""
    payment_intent_id = request.args.get('payment_intent')
    
    if payment_intent_id:
        # Find transaction and update user credits
        transaction = Transaction.query.filter_by(
            stripe_payment_intent_id=payment_intent_id,
            user_id=current_user.id
        ).first()
        
        if transaction and transaction.status == 'pending':
            # Verify payment with Stripe
            try:
                intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                if intent.status == 'succeeded':
                    # Update user credits
                    current_user.credits += transaction.credits_purchased
                    transaction.status = 'completed'
                    db.session.commit()
                    
                    flash(f'Payment successful! {transaction.credits_purchased} credits added to your account.', 'success')
                else:
                    flash('Payment verification failed. Please contact support.', 'error')
            except Exception as e:
                flash(f'Error verifying payment: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/generate', methods=['POST'])
@login_required
def generate():
    """Handle form submission and generate the map."""
    # Check if user has credits
    if current_user.credits < 1:
        flash('You need at least 1 credit to generate a map. Please purchase more credits.', 'error')
        return redirect(url_for('purchase_credits'))
    
    try:
        # Get form data
        bbox_str = request.form.get('bbox', '').strip()
        interval = float(request.form.get('interval', 10))
        background_color = request.form.get('background_color', '#ffffff').strip()
        include_roads = 'roads' in request.form
        
        # Safely parse width and height with validation
        try:
            width_str = request.form.get('width', '1600')
            width = int(float(width_str)) if width_str and width_str != 'NaN' else 1600
        except (ValueError, TypeError):
            width = 1600
            
        try:
            height_str = request.form.get('height', '1200')  
            height = int(float(height_str)) if height_str and height_str != 'NaN' else 1200
        except (ValueError, TypeError):
            height = 1200
        
        # Validate inputs
        if not bbox_str:
            flash('Bounding box is required', 'error')
            return redirect(url_for('index'))
        
        bbox = validate_bbox(bbox_str)
        
        if interval <= 0:
            flash('Contour interval must be positive', 'error')
            return redirect(url_for('index'))
        
        if not background_color.startswith('#'):
            background_color = f'#{background_color}'
        
        if width < 100 or width > 5000:
            flash('Width must be between 100 and 5000 pixels', 'error')
            return redirect(url_for('index'))
        
        if height < 100 or height > 5000:
            flash('Height must be between 100 and 5000 pixels', 'error')
            return redirect(url_for('index'))
        
        # Deduct credit before generation
        current_user.credits -= 1
        db.session.commit()
        
        # Generate the map
        filename = generate_contour_map(bbox, interval, background_color, include_roads, 
                                      width, height, current_user.id)
        
        flash(f'Map generated successfully! You have {current_user.credits} credits remaining.', 'success')
        return render_template('result.html', filename=filename, 
                             bbox=bbox_str, interval=interval, 
                             background_color=background_color, roads=include_roads,
                             width=width, height=height, credits=current_user.credits)
    
    except ValueError as e:
        # Refund credit on error
        current_user.credits += 1
        db.session.commit()
        flash(str(e), 'error')
        return redirect(url_for('index'))
    except Exception as e:
        # Refund credit on error
        current_user.credits += 1
        db.session.commit()
        flash(f'Error generating map: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/my-maps')
@login_required
def my_maps():
    """Show user's generated maps."""
    maps = GeneratedMap.query.filter_by(user_id=current_user.id).order_by(GeneratedMap.created_at.desc()).all()
    return render_template('my_maps.html', maps=maps)

@app.route('/download/<filename>')
@login_required
def download(filename):
    """Download a generated map file."""
    try:
        # Check if user owns this map
        generated_map = GeneratedMap.query.filter_by(filename=filename, user_id=current_user.id).first()
        if not generated_map:
            flash('Map not found or access denied', 'error')
            return redirect(url_for('my_maps'))
        
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(filepath):
            flash('File not found', 'error')
            return redirect(url_for('my_maps'))
        
        return send_file(filepath, as_attachment=True, download_name=filename)
    
    except Exception as e:
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(url_for('my_maps'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Migration: Ensure existing users aren't affected by credit default change
        try:
            existing_users = User.query.filter(User.credits.is_(None)).all()
            for user in existing_users:
                user.credits = 1
            if existing_users:
                db.session.commit()
                print(f"Updated {len(existing_users)} users with null credits")
        except Exception as e:
            print(f"Migration warning: {e}")
            
    port = int(os.environ.get('PORT', 8081))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False').lower() == 'true')
