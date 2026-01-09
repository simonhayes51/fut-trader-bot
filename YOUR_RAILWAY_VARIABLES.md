# Your Railway Environment Variables

Based on your PostgreSQL connection string:
`postgresql://postgres:OLXJFYxjYaMXWdwPHnQkVupXbMOuzQkm@yamanote.proxy.rlwy.net:27813/railway`

---

## 🗄️ BACKEND SERVICE - Environment Variables

Copy and paste these into Railway Backend service → Variables tab:

### Database Connection (Parsed from your PostgreSQL URL)
```env
DB_HOST=yamanote.proxy.rlwy.net
DB_PORT=27813
DB_NAME=railway
DB_USER=postgres
DB_PASSWORD=OLXJFYxjYaMXWdwPHnQkVupXbMOuzQkm
```

### Application Config
```env
NODE_ENV=production
PORT=3001
```

### IMPORTANT: Set these after deployment
```env
FRONTEND_URL=WILL_UPDATE_AFTER_FRONTEND_DEPLOYED
```

### Discord OAuth - YOU NEED TO CREATE DISCORD APP
```env
DISCORD_CLIENT_ID=YOUR_DISCORD_CLIENT_ID_HERE
DISCORD_CLIENT_SECRET=YOUR_DISCORD_CLIENT_SECRET_HERE
DISCORD_REDIRECT_URI=WILL_UPDATE_AFTER_BACKEND_DEPLOYED
```

**How to get Discord credentials:**
1. Go to https://discord.com/developers/applications
2. Click "New Application" → Name it "FUT Hub"
3. Go to OAuth2 section
4. Copy **Client ID** → paste above
5. Click "Reset Secret" → Copy it → paste above
6. Add Redirect URL (after you deploy backend): `https://your-backend-url.up.railway.app/api/auth/discord/callback`

### JWT Secret - GENERATE A RANDOM STRING
```env
JWT_SECRET=PASTE_RANDOM_STRING_HERE
```

**Generate with this command:**
```bash
openssl rand -base64 32
```
Or just use a long random string like: `mY$uP3r$3cR3t!JWT#K3y@2025!FUTHub#R4nD0m`

### Stripe - USE TEST MODE FOR NOW
```env
STRIPE_SECRET_KEY=sk_test_YOUR_STRIPE_TEST_KEY
STRIPE_WEBHOOK_SECRET=whsec_test_YOUR_WEBHOOK_SECRET
STRIPE_PLATFORM_FEE_PERCENTAGE=25
```

**How to get Stripe credentials:**
1. Go to https://stripe.com → Sign up or login
2. Make sure you're in **TEST MODE** (toggle in top right)
3. Go to Developers → API Keys
4. Copy "Secret key" (starts with `sk_test_`) → paste above
5. For webhook (do after backend deploys):
   - Go to Developers → Webhooks
   - Click "Add endpoint"
   - URL: `https://your-backend-url.up.railway.app/api/stripe/webhook`
   - Select all payment events
   - Copy "Signing secret" → paste above

---

## 🎨 FRONTEND SERVICE - Environment Variables

**IMPORTANT:** Deploy backend FIRST, then use its URL here.

```env
NEXT_PUBLIC_API_URL=YOUR_BACKEND_URL_HERE
```

Example: `https://backend-production-a1b2.up.railway.app`

**No trailing slash!**

---

## 📝 STEP-BY-STEP DEPLOYMENT

### Step 1: Initialize Database Schema ✅

First, run the schema on your PostgreSQL database:

```bash
psql postgresql://postgres:OLXJFYxjYaMXWdwPHnQkVupXbMOuzQkm@yamanote.proxy.rlwy.net:27813/railway -f web-platform/database/schema.sql
```

Or use Railway's web interface:
1. Go to Railway → Your PostgreSQL service
2. Click "Data" tab
3. Click "Query"
4. Copy/paste contents of `web-platform/database/schema.sql`
5. Click "Run"

### Step 2: Create Discord App

1. Go to https://discord.com/developers/applications
2. Click "New Application"
3. Name: "FUT Hub" (or your choice)
4. Go to "OAuth2" section
5. Copy **Client ID** - you'll need this
6. Click "Reset Secret" → Copy it - you'll need this
7. Leave redirect URLs blank for now (we'll add after backend deploys)

### Step 3: Create Stripe Account (Test Mode)

1. Go to https://stripe.com
2. Sign up for account (free)
3. Make sure **TEST MODE** is ON (toggle top right)
4. Go to Developers → API Keys
5. Copy "Secret key" (starts with `sk_test_`)
6. Leave webhook for now (we'll add after backend deploys)

### Step 4: Generate JWT Secret

Run this command:
```bash
openssl rand -base64 32
```

Or use: `node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"`

Copy the output.

### Step 5: Deploy Backend to Railway

1. In Railway dashboard, click "New" → "GitHub Repo"
2. Select `simonhayes51/fut-trader-bot`
3. After it's added, click on the service
4. Go to "Settings" tab
5. Find "Root Directory" → Set to: `web-platform/backend`
6. Go to "Variables" tab
7. Click "Raw Editor" and paste:

```env
NODE_ENV=production
PORT=3001
FRONTEND_URL=https://TEMP
DB_HOST=yamanote.proxy.rlwy.net
DB_PORT=27813
DB_NAME=railway
DB_USER=postgres
DB_PASSWORD=OLXJFYxjYaMXWdwPHnQkVupXbMOuzQkm
DISCORD_CLIENT_ID=YOUR_DISCORD_CLIENT_ID
DISCORD_CLIENT_SECRET=YOUR_DISCORD_CLIENT_SECRET
DISCORD_REDIRECT_URI=https://TEMP/api/auth/discord/callback
JWT_SECRET=YOUR_GENERATED_JWT_SECRET
STRIPE_SECRET_KEY=sk_test_YOUR_STRIPE_KEY
STRIPE_WEBHOOK_SECRET=whsec_test_TEMP
STRIPE_PLATFORM_FEE_PERCENTAGE=25
```

8. Replace the `YOUR_...` and `TEMP` placeholders with your actual values
9. Click "Deploy"
10. Wait for deployment to finish
11. Click "Settings" → Copy the domain URL (e.g., `backend-production-xxxx.up.railway.app`)

### Step 6: Update Backend Variables with Real URLs

Now you have the backend URL, go back and update:

1. In Backend Variables, update:
   - `DISCORD_REDIRECT_URI=https://[YOUR_BACKEND_URL]/api/auth/discord/callback`
   - Keep `FRONTEND_URL` as TEMP for now

2. In Discord Developer Portal:
   - Go to OAuth2 → Redirects
   - Add: `https://[YOUR_BACKEND_URL]/api/auth/discord/callback`
   - Save changes

3. In Stripe Dashboard:
   - Go to Developers → Webhooks
   - Add endpoint: `https://[YOUR_BACKEND_URL]/api/stripe/webhook`
   - Select events: `payment_intent.*`, `checkout.session.*`, `customer.subscription.*`
   - Copy "Signing secret"
   - Update `STRIPE_WEBHOOK_SECRET` in Railway backend variables

### Step 7: Deploy Frontend to Railway

1. In Railway, click "New" → "GitHub Repo"
2. Select `simonhayes51/fut-trader-bot` again
3. Click on the new service
4. Go to "Settings" → "Root Directory" → Set to: `web-platform/frontend`
5. Go to "Variables" tab
6. Add ONE variable:

```env
NEXT_PUBLIC_API_URL=https://[YOUR_BACKEND_URL]
```

Replace `[YOUR_BACKEND_URL]` with the backend URL from Step 5.

7. Click "Deploy"
8. Wait for deployment
9. Copy the frontend URL (e.g., `frontend-production-xxxx.up.railway.app`)

### Step 8: Final Backend Update

1. Go to Backend service → Variables
2. Update `FRONTEND_URL=https://[YOUR_FRONTEND_URL]`
3. Backend will auto-redeploy

### Step 9: Update Discord OAuth Again

1. Go to Discord Developer Portal
2. OAuth2 → Redirects
3. Add: `https://[YOUR_FRONTEND_URL]/api/auth/callback` (if needed)
4. Save

---

## ✅ Testing Checklist

1. [ ] Visit your frontend URL
2. [ ] Homepage loads correctly
3. [ ] Click "Browse Traders" → page loads
4. [ ] Click "Login" → redirects to Discord
5. [ ] After Discord auth → redirects back to site
6. [ ] Try navigating to different pages

---

## 🚨 If Something Breaks

### Backend won't start
1. Check Railway logs (Backend service → Deployments → Click on deployment → View logs)
2. Common issues:
   - Database connection failed → Check DB variables
   - Port binding error → Make sure `PORT=3001` or remove it (Railway auto-injects)
   - Module not found → Check `web-platform/backend` is set as root directory

### Frontend shows "API Error" or 404
1. Check `NEXT_PUBLIC_API_URL` is correct (no trailing slash)
2. Check backend is running (visit backend URL directly)
3. Check frontend logs

### Discord login fails
1. Check `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET` are correct
2. Check redirect URI in Discord matches exactly
3. Check `DISCORD_REDIRECT_URI` variable

### Database errors
1. Make sure schema was executed
2. Check database connection (try connecting with provided URL)
3. Check all 5 DB variables are correct

---

## 📊 Your Current Setup

**PostgreSQL Database:**
- Host: `yamanote.proxy.rlwy.net`
- Port: `27813`
- Database: `railway`
- User: `postgres`

**Services to Deploy:**
1. Backend (Node.js/Express) - `web-platform/backend`
2. Frontend (Next.js) - `web-platform/frontend`

**External Services Needed:**
- Discord Application (for OAuth login)
- Stripe Account (for payments - TEST MODE)

---

## 💡 Quick Tips

1. **Always deploy backend first**, then frontend
2. **Use TEST MODE for Stripe** until you're ready to go live
3. **Keep your secrets safe** - never commit them to git
4. **Check logs** if something doesn't work
5. **Railway auto-deploys** when you push to git

---

## 🎯 Next Steps After Deployment

1. Test all pages work
2. Test Discord login
3. Create a test trader account
4. Post a test signal
5. Test commenting and reviews
6. Consider adding custom domain
7. Set up monitoring/alerts

---

**Good luck with deployment! 🚀**
