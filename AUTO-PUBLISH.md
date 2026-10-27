# Optional: let the app publish by itself

Only needed if you want **Auto-publish with APIs** in Squad Studio instead of posting from your phone.

## YouTube (~25 min)
1. console.cloud.google.com → new project → APIs & Services → Library → enable **YouTube Data API v3**.
2. OAuth consent screen → External → add ram4utube2026@gmail.com as a test user → **Publish app**
   ("In production"; in Testing mode the sign-in expires after 7 days).
3. Credentials → OAuth client ID → **Desktop app** → copy ID and secret.
4. On a computer: `python3 pipeline/get_youtube_token.py CLIENT_ID CLIENT_SECRET`, sign in, pick the channel.
5. Add secrets `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
6. New API projects upload as **private** until Google approves them — submit the free
   "YouTube API Services – Audit and Quota Extension" form. Quota allows about 6 uploads a day.

## Instagram (~25 min)
1. developers.facebook.com → Create app (Business) → add **Instagram** → "API setup with Instagram login".
2. Add your Instagram creator account → **Generate token** (`instagram_business_basic`,
   `instagram_business_content_publish`).
3. Add secrets `IG_ACCESS_TOKEN` and `IG_USER_ID`.
4. Tokens last 60 days. For auto-renewal add a fine-grained GitHub token with Secrets read/write as
   secret `SECRETS_PAT` and a repository variable `AUTO_REFRESH_IG` = `true`.

Then in Squad Studio: Settings → **Turn on API auto-publish**.
