# Begowalia IQ — a simple vidIQ-style YouTube dashboard

A working first-version YouTube growth report built for **Begowalia Music**.

## What it does

- Tracks public subscriber count, lifetime channel views and number of videos.
- Reviews up to 50 recent uploads with views, likes, comments, and simple average lifetime views/day.
- Labels comparatively strong/weak uploads relative to recent uploads' median views/day.
- Offers basic title improvements, contextual keyword starting points and description checklists.
- Stores daily subscriber snapshots and plots a growth chart after two or more runs.
- Creates a mobile-friendly static website (`docs/index.html`) and a daily text report (`reports/latest.md`).
- Refreshes automatically each morning using GitHub Actions.

The dashboard **does not have access to private YouTube Studio statistics** from an API key alone. It cannot show real YouTube impressions, click-through rate, audience retention or recommendations. The rules-based advice is not vidIQ's proprietary keyword search volume/competition score or an AI model.

## First setup from iPhone / GitHub (about 7 steps)

1. Create a new GitHub repository called `begowalia-iq`. Use a public repository if you want a no-cost GitHub Pages site (your report will be publicly visible). Avoid storing private Studio exports in it.
2. Upload **the contents of this ZIP**, including the hidden `.github` folder, to the root of the repository. The easiest desktop route is GitHub **Add file → Upload files**; to preserve folders and hidden files, you can instead unzip and push with Git. On mobile, GitHub's upload interface may be fiddly, so using the browser in desktop mode is often easier.
3. Go to [Google Cloud Console](https://console.cloud.google.com/), create or choose a project, **APIs & Services → Library**, enable **YouTube Data API v3**.
4. Go to **APIs & Services → Credentials → Create credentials → API key**. Restrict that key to **YouTube Data API v3** (API restrictions). For GitHub Actions' changing outbound IPs, don't use a single static IP allowlist. Never put the key in repository files or chats.
5. In GitHub repository: **Settings → Secrets and variables → Actions → New repository secret**. Name: `YOUTUBE_API_KEY`. Paste the API key there.
6. In GitHub repository: **Actions → Begowalia IQ — daily YouTube analysis → Run workflow**. Refresh after it finishes; the action adds a real `docs/index.html`, `reports/latest.md`, and `data/history.json` to the repository. If the Action cannot commit, go to **Settings → Actions → General → Workflow permissions** and select **Read and write permissions**, then rerun.
7. To view on a website, open **Settings → Pages → Build and deployment → Deploy from a branch**. Choose the default branch (`main`), folder `/docs`, then **Save**. GitHub will display the Pages URL when the site is published. Pages may be public depending on your GitHub plan and repo visibility.

**Default channel:** `UCUUhi6u0FzDn2L7mizyog8g` (Begowalia / @begowaliamusic). Change it in `.github/workflows/daily-report.yml` if you want another channel.

**Schedule:** 8:00 AM Brisbane time (22:00 UTC previous calendar date); GitHub scheduled tasks can be delayed. Run manually anytime from Actions.

## Demo preview

The included `docs/index.html` starts with **clearly fictional demo data**. It is replaced by the live channel metrics after the first successful GitHub Actions run.

To recreate it locally:

```bash
python src/report.py --demo
```

## Private YouTube Studio metrics (optional local workflow)

If you privately export and prepare a CSV with these exact columns:

```csv
video_id,impressions,ctr,avg_view_duration_seconds
YOUTUBE_VIDEO_ID,1000,4.2,91
```

Run `python src/report.py --studio-csv /local/private/studio.csv` with `YOUTUBE_API_KEY` set in your shell. This enriches rows **locally**. **Do not upload the CSV, your private analytics or the locally generated report to a public repo** unless you're comfortable with their visibility. The GitHub scheduled run never accesses it.

## Why this is safe for YouTube

- Read-only YouTube Data API access with an API key.
- No fake accounts, buying views, bot comments, mass subscriptions or spam.
- You review title ideas yourself. Nothing edits a video automatically.

## Developer commands

```bash
python -m unittest discover -s tests -v
python src/report.py --demo
```

Dependencies: Python 3.10+ standard library only. No Python packages required.

## Important metric caveats

- Public subscriber counts may be rounded, and hiding subscribers can remove the public figure.
- Views/day divides current lifetime views by age. It is **not** a direct measurement of views gained today and is not an SEO score.
- Comparing Shorts, long-form music videos and old content without separating formats can be misleading; treat this as an overview, not a cause-and-effect diagnosis.
- For a genuine private CTR, retention and traffic-source dashboard, a future version needs YouTube Analytics OAuth access and specific authorization from the channel owner.
