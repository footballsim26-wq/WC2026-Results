#!/usr/bin/env python3
"""
Global Football Simulator 2026 — Auto-Result Updater
Runs via GitHub Actions every 5 minutes during the tournament.
Fetches ESPN → normalizes team names → writes results.json
The simulator reads results.json from raw.githubusercontent.com (CORS-free).
"""

import json, urllib.request, urllib.error, os, sys
from datetime import datetime, timezone

# ── OFFICIAL MATCH SCHEDULE (mirrors JS OFFICIAL_MATCHES) ──
GROUPS = {
    "A": ["Mexico","South Africa","South Korea","Czechia"],
    "B": ["Canada","Bosnia & Herzegovina","Qatar","Switzerland"],
    "C": ["Brazil","Morocco","Haiti","Scotland"],
    "D": ["USA","Paraguay","Australia","Türkiye"],
    "E": ["Germany","Curaçao","Côte d'Ivoire","Ecuador"],
    "F": ["Netherlands","Japan","Sweden","Tunisia"],
    "G": ["Belgium","Egypt","IR Iran","New Zealand"],
    "H": ["Spain","Cabo Verde","Saudi Arabia","Uruguay"],
    "I": ["France","Senegal","Iraq","Norway"],
    "J": ["Argentina","Algeria","Austria","Jordan"],
    "K": ["Portugal","Congo DR","Uzbekistan","Colombia"],
    "L": ["England","Croatia","Ghana","Panama"],
}
PAIRS = [(0,1),(2,3),(0,2),(1,3),(0,3),(1,2)]

OFFICIAL_MATCHES = {}
match_id = 1
for group, teams in GROUPS.items():
    for a, b in PAIRS:
        OFFICIAL_MATCHES[match_id] = {
            "id": match_id, "stage": "group",
            "group": group, "home": teams[a], "away": teams[b]
        }
        match_id += 1

# ── ESPN → OUR TEAM NAME MAP ──
ESPN_NAME_MAP = {
    "United States": "USA",
    "Iran": "IR Iran",
    "Korea Republic": "South Korea",
    "Republic of Korea": "South Korea",
    "DR Congo": "Congo DR",
    "Democratic Republic of Congo": "Congo DR",
    "DRC": "Congo DR",
    "Bosnia-Herzegovina": "Bosnia & Herzegovina",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Turkey": "Türkiye",
    "Turkiye": "Türkiye",
    "Ivory Coast": "Côte d'Ivoire",
    "Cote d'Ivoire": "Côte d'Ivoire",
    "Côte D'Ivoire": "Côte d'Ivoire",
    "Curacao": "Curaçao",
    "Cape Verde": "Cabo Verde",
    "Czech Republic": "Czechia",
    "New Zealand": "New Zealand",
    "Saudi Arabia": "Saudi Arabia",
}

def normalize(name: str) -> str:
    return ESPN_NAME_MAP.get(name, name)

def find_match(t1: str, t2: str):
    """Find official match by two team names (order-independent)."""
    for m in OFFICIAL_MATCHES.values():
        if (m["home"] == t1 and m["away"] == t2) or \
           (m["home"] == t2 and m["away"] == t1):
            return m
    return None

# ── MANUALLY VERIFIED RESULTS (these NEVER get overwritten by API) ──
# Update this list as you personally verify results from reliable sources.
# Source priority: Manual override > ESPN API
MANUAL_VERIFIED = {
    1:  {"id":1,  "home":"Mexico",  "away":"South Africa",      "homeScore":2,"awayScore":0, "homeAdvances":True,  "source":"Verified (Reuters/CBS)"},
    2:  {"id":2,  "home":"South Korea","away":"Czechia",         "homeScore":2,"awayScore":1, "homeAdvances":True,  "source":"Verified (Reuters/CBS)"},
    7:  {"id":7,  "home":"Canada",  "away":"Bosnia & Herzegovina","homeScore":1,"awayScore":1,"homeAdvances":False, "source":"Verified (Canada Soccer/CBS)"},
    8:  {"id":8,  "home":"Qatar",   "away":"Switzerland",        "homeScore":1,"awayScore":1, "homeAdvances":False, "source":"Verified (Yahoo Sports/ESPN)"},
    13: {"id":13, "home":"Brazil",  "away":"Morocco",            "homeScore":1,"awayScore":1, "homeAdvances":False, "source":"Verified (Yahoo Sports/ESPN)"},
    19: {"id":19, "home":"USA",     "away":"Paraguay",           "homeScore":4,"awayScore":1, "homeAdvances":True,  "source":"Verified (Reuters/CBS)"},
    # ── ADD NEW RESULTS HERE AS THEY COMPLETE ──
    # Format: MATCH_ID: {"id":X,"home":"Team A","away":"Team B","homeScore":N,"awayScore":N,"homeAdvances":True/False,"source":"Verified (source)"},
}

def fetch_espn():
    """Fetch ESPN scoreboard API. Returns list of events or empty list on failure."""
    url = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GlobalFootballSim/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data.get("events", [])
    except Exception as e:
        print(f"ESPN fetch error: {e}", file=sys.stderr)
        return []

def process_events(events):
    """Convert ESPN events into our result format."""
    results = {}

    for ev in events:
        comp = (ev.get("competitions") or [{}])[0]
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            continue

        home_comp = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away_comp = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        t1n = normalize(home_comp.get("team", {}).get("displayName", ""))
        t2n = normalize(away_comp.get("team", {}).get("displayName", ""))

        status = comp.get("status", {}).get("type", {}).get("state", "pre")
        if status != "post":
            continue  # only process completed matches

        match = find_match(t1n, t2n)
        if not match:
            continue  # not a match we track

        flipped = match["home"] == t2n  # ESPN home/away may differ from ours

        home_raw = away_comp if flipped else home_comp
        away_raw = home_comp if flipped else away_comp

        home_score = int(home_raw.get("score") or 0)
        away_score = int(away_raw.get("score") or 0)

        # ESPN winner field (reliable for KO matches with extra time/pens)
        home_winner = home_raw.get("winner") is True
        away_winner = away_raw.get("winner") is True
        home_pens = int(home_raw.get("shootoutScore") or home_raw.get("penaltyScore") or 0)
        away_pens = int(away_raw.get("shootoutScore") or away_raw.get("penaltyScore") or 0)
        is_ko = match["stage"] != "group"
        penalties = is_ko and home_score == away_score and (home_pens > 0 or away_pens > 0)

        if home_winner or away_winner:
            home_advances = home_winner
        elif penalties:
            home_advances = home_pens > away_pens
        else:
            home_advances = home_score > away_score

        results[match["id"]] = {
            "id":           match["id"],
            "home":         match["home"],
            "away":         match["away"],
            "homeScore":    home_score,
            "awayScore":    away_score,
            "locked":       True,
            "status":       "post",
            "source":       "ESPN (auto)",
            "updatedAt":    datetime.now(timezone.utc).isoformat(),
            "penalties":    penalties,
            "homePens":     home_pens,
            "awayPens":     away_pens,
            "homeAdvances": home_advances,
        }

    return results

def main():
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}] Fetching ESPN...")

    # 1. Fetch ESPN
    events = fetch_espn()
    print(f"  Got {len(events)} ESPN events")

    # 2. Process into our format
    espn_results = process_events(events)
    print(f"  Processed {len(espn_results)} completed matches from ESPN")

    # 3. Load existing results.json (to preserve history)
    existing = {}
    results_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results.json")
    if os.path.exists(results_path):
        with open(results_path) as f:
            existing_data = json.load(f)
            existing = {int(k): v for k, v in existing_data.get("results", {}).items()}

    # 4. Merge: ESPN < existing locked < MANUAL_VERIFIED
    merged = {}
    merged.update({k: v for k, v in espn_results.items()})        # ESPN first
    merged.update({k: v for k, v in existing.items()})             # existing locked wins over ESPN
    merged.update({k: {**v, "locked": True} for k, v in          # manual ALWAYS wins
                   {**{k: v for k, v in existing.items() 
                       if v.get("source", "").startswith("Verified")},
                    **MANUAL_VERIFIED}.items()})

    # 5. Build output
    output = {
        "updatedAt":    datetime.now(timezone.utc).isoformat(),
        "source":       "ESPN public API + verified manual results",
        "totalLocked":  len(merged),
        "espnEvents":   len(events),
        "results":      {str(k): v for k, v in sorted(merged.items())}
    }

    # 6. Write results.json
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  ✅ Written {len(merged)} locked results to results.json")
    for match_id, r in sorted(merged.items()):
        print(f"     Match {match_id}: {r['home']} {r['homeScore']}-{r['awayScore']} {r['away']} [{r['source']}]")

if __name__ == "__main__":
    main()
