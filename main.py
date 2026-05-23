import os
import json
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports"
REGIONS = "us"             
ODDS_FORMAT = "american"

TARGET_SPORTS = {
    "basketball_nba": {"title": "NBA", "props": ["player_points", "player_assists", "player_rebounds"]},
    "baseball_mlb": {"title": "MLB", "props": ["batter_hits", "batter_home_runs", "pitcher_strikeouts"]},
    "icehockey_nhl": {"title": "NHL", "props": ["player_goals", "player_assists", "player_shots_on_goal", "player_saves"]}
}

def get_games(sport_key):
    res = requests.get(f"{BASE_URL}/{sport_key}/odds", params={"apiKey": API_KEY, "regions": REGIONS, "markets": "h2h,totals", "oddsFormat": ODDS_FORMAT})
    return res.json() if res.status_code == 200 else []

def get_props(sport_key, event_id, props):
    res = requests.get(f"{BASE_URL}/{sport_key}/events/{event_id}/odds", params={"apiKey": API_KEY, "regions": REGIONS, "markets": ",".join(props), "oddsFormat": ODDS_FORMAT})
    return res.json() if res.status_code == 200 else {}

def main():
    now = datetime.now(timezone.utc)
    results = {"NBA": [], "MLB": [], "NHL": []}
    for key, cfg in TARGET_SPORTS.items():
        games = get_games(key)
        for g in games[:4]: # Limit to top 4 games per league
            commence = datetime.fromisoformat(g['commence_time'].replace('Z', '+00:00'))
            if now < commence < (now + timedelta(hours=24)):
                entry = {"match": f"{g['away_team']} @ {g['home_team']}", "data": g, "props": None}
                if commence < (now + timedelta(hours=8)):
                    entry["props"] = get_props(key, g['id'], cfg['props'])
                results[cfg['title']].append(entry)
    with open("bets.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
