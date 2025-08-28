# Deployment Guide - Contour Map Generator

## 🚀 Deploy to Railway (Recommended)

### Step 1: Prepare Your Code
1. **Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin YOUR_GITHUB_REPO_URL
   git push -u origin main
   ```

### Step 2: Deploy to Railway
1. **Go to:** [railway.app](https://railway.app)
2. **Sign up** with GitHub
3. **Click "New Project"**
4. **Select "Deploy from GitHub repo"**
5. **Choose your repository**

### Step 3: Add Environment Variables
In Railway dashboard, go to **Variables** tab and add:

```
SECRET_KEY=your-super-secret-key-here-make-it-long-and-random
STRIPE_SECRET_KEY=sk_live_YOUR_LIVE_SECRET_KEY
STRIPE_PUBLISHABLE_KEY=pk_live_YOUR_LIVE_PUBLISHABLE_KEY
DEBUG=false
```

### Step 4: Add PostgreSQL Database
1. **In Railway dashboard:** Click **"+ New"**
2. **Select:** "Database" → "PostgreSQL" 
3. **Railway automatically** sets `DATABASE_URL` environment variable

### Step 5: Configure Stripe for Live Payments
1. **Go to:** [Stripe Dashboard](https://dashboard.stripe.com)
2. **Get your LIVE API keys** (not test keys)
3. **Update environment variables** in Railway
4. **Add your domain** to Stripe's allowed domains

## 💳 Stripe Live Mode Setup

### Get Live API Keys:
1. Go to Stripe Dashboard
2. Switch to "Live" mode (toggle in left sidebar)
3. Go to "Developers" → "API Keys"
4. Copy your Live Publishable key (`pk_live_...`)
5. Reveal and copy your Live Secret key (`sk_live_...`)

### Update Environment Variables:
```
STRIPE_SECRET_KEY=sk_live_YOUR_ACTUAL_LIVE_KEY
STRIPE_PUBLISHABLE_KEY=pk_live_YOUR_ACTUAL_LIVE_KEY
```

## 🌐 Custom Domain (Optional)

1. **In Railway:** Go to "Settings" → "Domains"
2. **Add your domain** (e.g., `mycontourmaps.com`)
3. **Update DNS** with provided CNAME record
4. **SSL certificate** is automatically provided

## 📊 Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | `your-secret-key-123` |
| `DATABASE_URL` | PostgreSQL URL | Auto-set by Railway |
| `STRIPE_SECRET_KEY` | Stripe secret key | `sk_live_...` |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key | `pk_live_...` |
| `DEBUG` | Debug mode | `false` |
| `PORT` | Server port | Auto-set by Railway |

## 🔧 Troubleshooting

### Common Issues:
1. **Database migrations:** Railway automatically runs them
2. **Static files:** Ensure `static/` folder is committed
3. **Environment variables:** Check they're set correctly
4. **Stripe webhooks:** Configure in Stripe dashboard

### Logs:
- **View logs** in Railway dashboard → "Deployments" tab
- **Debug issues** using deployment logs

## 🎯 Production Checklist

- [ ] Code pushed to GitHub
- [ ] Railway project created
- [ ] Environment variables set
- [ ] PostgreSQL database added
- [ ] Stripe live keys configured
- [ ] Test payment flow
- [ ] Custom domain configured (optional)
- [ ] SSL certificate active
- [ ] Application accessible online

## 💰 Costs

- **Railway:** $5/month (hobby plan)
- **Domain:** ~$10-15/year (optional)
- **Stripe:** 2.9% + 30¢ per transaction

**Total monthly cost:** ~$5-10/month

## 🔒 Security Notes

- Never commit API keys to git
- Use strong SECRET_KEY in production
- Enable Stripe webhook verification
- Monitor transaction logs
- Set up error tracking (optional)
