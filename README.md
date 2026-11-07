# The Narrata

A self-updating news hub for Uganda, East Africa, Africa and the world. No server and no database: a scheduled job collects headlines into `docs/news.json`, and a static page displays them.

## Files

- `feeds.json`: the sources. Add or remove feeds here.
- `fetch_news.py`: fetches the feeds, cleans, removes duplicates, tags region and topic, and writes `docs/news.json`.
- `docs/index.html`: the public website (reads `news.json`). `narrata-wordmark.png` and `narrata-icon.png` are the logo and tab icon.
- `.github/workflows/update.yml`: runs the fetcher every 30 minutes and saves the result.

## Go live (about 10 minutes, free)

1. Create a GitHub repository and upload everything in this folder (keep the `.github` folder).
2. Repository **Settings → Pages**: set the source to the `main` branch and the `/docs` folder. Your site appears at `https://<your-username>.github.io/<repo>/`.
3. **Actions** tab: open "Update news" and click **Run workflow** once. This creates the first `news.json`. After that it refreshes itself every 30 minutes.
4. Optional: add your own domain under Settings → Pages.

## Test on your computer

```
pip install feedparser
python fetch_news.py
cd docs && python -m http.server 8000
```

Then open http://localhost:8000. The fetch prints one line per feed. A feed marked `ZERO` or `FAIL` has a wrong or changed URL: open the outlet's site, find its RSS link, and update `feeds.json`.

## Before you promote it

- Set a real contact URL in `USER_AGENT` in `fetch_news.py`.
- Keep showing only headline, short snippet and link. Don't copy full articles.
- Check each outlet's terms. Most allow headline linking; a few restrict images, so remove the `image` field in `fetch_news.py` if an outlet objects.
- GitHub Actions' schedule can lag by several minutes and may pause after 60 days without repository activity. Re-enable it from the Actions tab if that happens.

## Ideas for next steps

- Add GDELT or NewsData.io as extra sources for broader coverage.
- Add an "AI summary of the day" step after fetching.
- Add a weekly email digest.
