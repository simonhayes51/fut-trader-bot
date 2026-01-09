# FUT Hub Frontend

Next.js frontend for the FUT Hub trading platform.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Copy `.env.example` to `.env.local` and configure:
```bash
cp .env.example .env.local
```

3. Update `NEXT_PUBLIC_API_URL` in `.env.local` to point to your backend API.

## Development

Run the development server:
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the app.

## Build

Build for production:
```bash
npm run build
```

## Start Production Server

```bash
npm start
```

## Pages

- `/` - Homepage with featured traders and recent signals
- `/traders` - Browse all traders
- `/traders/[id]` - Individual trader profile with reviews and signals
- `/signals` - Browse all trading signals
- `/signals/[id]` - Individual signal detail with comments
- `/community` - Community guides and content
- `/tools` - Free trading tools (price checker, etc.)
- `/servers` - Discord server directory
- `/login` - Login page
- `/signup` - Signup page

## Deployment on Railway

1. Create a new project in Railway
2. Connect your GitHub repository
3. Add environment variable:
   - `NEXT_PUBLIC_API_URL` = your backend service URL
4. Railway will automatically detect Next.js and deploy

## Features

- Server-side rendering with Next.js 14
- Responsive design with TailwindCSS
- Interactive components (reviews, comments, voting)
- Discord OAuth authentication (configured in backend)
- Real-time trading signals
- Trader profiles with statistics
- Community content platform
- Free trading tools
