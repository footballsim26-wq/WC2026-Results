# wc2026-results

Auto-updating match results for Global Football Simulator 2026.

## How it works

A GitHub Action runs every 5 minutes, fetches ESPN's public scoreboard API,
and writes locked match results to `results.json`.

The simulator at `globalfootballsim.com` reads from:
```
https://raw.githubusercontent.com/YOUR_USERNAME/wc2026-results/main/results.json
```

This URL has CORS headers, so it works in both the deployed site and Claude artifacts.

## Priority chain
1. Manually verified results (hardcoded in update_results.py) — never overwritten
2. Previously locked results (preserved from results.json history)  
3. ESPN API completed match data (auto-fetched every 5 minutes)

## Repo must be PUBLIC for raw.githubusercontent.com to work without auth.

## To manually trigger an update:
GitHub repo → Actions tab → "Auto-Update Match Results" → Run workflow
