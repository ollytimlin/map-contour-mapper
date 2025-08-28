# 💰 Map Contour Mapper - Monetization Setup Guide

This guide will help you set up the monetized version of your contour mapping app with user accounts, credits, and Stripe payments.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd /Users/olivertimlin/map-contour-mapper
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Set Up Stripe Account

1. **Sign up for Stripe**: Go to [stripe.com](https://stripe.com) and create an account
2. **Get your API keys**: 
   - Go to Stripe Dashboard > Developers > API Keys
   - Copy your **Publishable Key** (starts with `pk_test_...`)
   - Copy your **Secret Key** (starts with `sk_test_...`)

### 3. Configure Environment Variables

Create a `.env` file in your project root:

```bash
# In your terminal
cat > .env << EOF
SECRET_KEY=your-super-secret-key-here-change-this
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key_here
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key_here
EOF
```

### 4. Run the Monetized App

```bash
python3 app_monetized.py
```

Open `http://localhost:8080` in your browser!

## 💳 Credit System Overview

### **Pricing Structure**
- **Free Trial**: 3 credits for new users
- **Starter Pack**: 5 credits for $4.99 ($1.00 per map)
- **Popular Pack**: 15 credits for $12.99 ($0.87 per map)
- **Value Pack**: 50 credits for $39.99 ($0.80 per map)
- **Pro Pack**: 100 credits for $69.99 ($0.70 per map)

### **How It Works**
1. Users sign up and get 3 free credits
2. Each map generation costs 1 credit
3. When credits run low, users purchase more
4. Credits never expire
5. Failed generations are automatically refunded

## 🗄️ Database Schema

The app automatically creates these tables:

### **Users Table**
- `id`: Primary key
- `email`: User's email (unique)
- `password_hash`: Bcrypt hashed password
- `credits`: Available credits (default: 3)
- `created_at`: Registration timestamp

### **Generated Maps Table**
- `id`: Primary key
- `user_id`: Foreign key to users
- `filename`: Generated map filename
- `bbox`: Bounding box coordinates
- `settings`: JSON string of map settings
- `created_at`: Generation timestamp

### **Transactions Table**
- `id`: Primary key
- `user_id`: Foreign key to users
- `stripe_payment_intent_id`: Stripe payment ID
- `credits_purchased`: Number of credits bought
- `amount_paid`: Amount in cents
- `status`: Payment status
- `created_at`: Transaction timestamp

## 🔧 Key Features

### **User Authentication**
- Secure registration and login
- Session management with Flask-Login
- Password hashing with bcrypt

### **Credit Management**
- Automatic credit deduction
- Error refunds
- Low credit warnings
- Credit purchase flow

### **Payment Processing**
- Stripe integration for secure payments
- Support for all major credit/debit cards
- Automatic credit addition after successful payment
- Payment verification

### **Map Protection**
- Users can only download their own maps
- Credit checking before generation
- Personal map gallery

## 🎨 Customization Options

### **Modify Pricing**
Edit the `CREDIT_PRICES` dictionary in `app_monetized.py`:

```python
CREDIT_PRICES = {
    5: {'price': 499, 'description': '5 credits'},      # $4.99
    15: {'price': 1299, 'description': '15 credits'},   # $12.99
    50: {'price': 3999, 'description': '50 credits'},   # $39.99
    100: {'price': 6999, 'description': '100 credits'}, # $69.99
}
```

### **Change Free Credits**
Modify the `User` model in `app_monetized.py`:

```python
credits = db.Column(db.Integer, default=3)  # Change 3 to your desired amount
```

### **Adjust Credit Cost**
To change the cost per map, modify the credit deduction in the `generate()` route:

```python
current_user.credits -= 1  # Change 1 to your desired cost
```

## 🚀 Deployment Considerations

### **Production Environment Variables**
```bash
SECRET_KEY=your-production-secret-key-64-characters-long
STRIPE_PUBLISHABLE_KEY=pk_live_your_live_publishable_key
STRIPE_SECRET_KEY=sk_live_your_live_secret_key
DATABASE_URL=postgresql://user:pass@host:port/dbname  # For PostgreSQL
```

### **Database Migration**
For production, consider using PostgreSQL:

```python
# In app_monetized.py, change:
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///contour_mapper.db')
```

### **Security Enhancements**
1. Use strong secret keys
2. Enable HTTPS in production
3. Set up proper CORS headers
4. Add rate limiting
5. Implement email verification

### **Scaling Considerations**
1. Use a proper WSGI server (gunicorn)
2. Set up Redis for session storage
3. Use cloud storage for generated maps
4. Add background job processing for map generation
5. Implement caching

## 📊 Analytics & Monitoring

### **Key Metrics to Track**
- User registrations
- Credit purchases
- Map generations
- Revenue per user
- Conversion rates

### **Recommended Tools**
- Google Analytics for user behavior
- Stripe Dashboard for payment analytics
- Custom database queries for business metrics

## 🔒 Security Features

### **Authentication**
- Secure password hashing with bcrypt
- Session management
- CSRF protection with Flask-WTF

### **Payment Security**
- Stripe handles all payment processing
- No credit card data stored locally
- PCI compliance through Stripe

### **Data Protection**
- User isolation (users can't access others' maps)
- Input validation and sanitization
- SQL injection prevention with SQLAlchemy ORM

## 🎯 Marketing Strategies

### **Free Trial Strategy**
- 3 free credits to let users experience the value
- Clear upgrade prompts when credits are low
- Showcase map quality to encourage purchases

### **Pricing Psychology**
- "Most Popular" badge on 15-credit package
- Volume discounts to encourage larger purchases
- Clear per-map pricing to show value

### **User Retention**
- Credits never expire (reduces urgency anxiety)
- Personal map gallery (creates attachment)
- Easy repurchasing flow

## 🆘 Support & Troubleshooting

### **Common Issues**

1. **Stripe webhook setup**: For production, set up webhooks to handle edge cases
2. **Database locks**: Consider connection pooling for high traffic
3. **File storage**: Move to cloud storage (AWS S3) for scalability
4. **Memory usage**: Monitor for memory leaks during map generation

### **Testing Payments**
Use Stripe's test credit cards:
- Success: `4242424242424242`
- Declined: `4000000000000002`

### **Monitoring Health**
- Database connection status
- Stripe API connectivity
- File system space
- Map generation success rates

## 💡 Future Enhancements

### **Potential Features**
1. **Subscription plans** for heavy users
2. **Team accounts** for organizations
3. **API access** for developers
4. **Custom branding** for enterprise
5. **Bulk upload** for multiple locations
6. **Map sharing** and public galleries
7. **Email notifications** for completed maps
8. **Mobile app** for map viewing

### **Revenue Optimization**
1. **A/B testing** for pricing
2. **Referral programs** for user acquisition
3. **Corporate packages** for businesses
4. **Educational discounts** for schools
5. **Seasonal promotions** and sales

---

## 🏃‍♂️ Getting Started Checklist

- [ ] Install dependencies
- [ ] Set up Stripe account
- [ ] Configure environment variables
- [ ] Test with Stripe test cards
- [ ] Customize pricing if desired
- [ ] Deploy to production server
- [ ] Set up monitoring and analytics
- [ ] Create marketing materials
- [ ] Launch! 🚀

---

**Ready to monetize your beautiful contour mapping tool? This system provides everything you need to start generating revenue while delivering value to your users!**
