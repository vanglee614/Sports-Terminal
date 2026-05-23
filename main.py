import os
import json
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports"
REGIONS = "us"             
ODDS_FORMAT = "american"

TARGET_SPORTS = {
    "basketball_nba": {"icon": "🏀", "title": "NBA", "props": ["player_points", "player_assists", "player_rebounds"]},
    "baseball_mlb": {"icon": "⚾", "title": "MLB", "props": ["batter_hits", "batter_home_runs", "pitcher_strikeouts"]},
    "icehockey_nhl": {"icon": "🏒", "title": "NHL", "props": ["player_goals", "player_assists", "player_shots_on_goal", "player_saves"]}
}

def get_games(sport_key):
    url = f"{BASE_URL}/{sport_key}/odds"
    params = {"apiKey": API_KEY, "regions": REGIONS, "markets": "h2h,totals", "oddsFormat": ODDS_FORMAT}
    res = requests.get(url, params=params)
    return res.json() if res.status_code == 200 else []

def get_props(sport_key, event_id, props):
    url = f"{BASE_URL}/{sport_key}/events/{event_id}/odds"
    params = {"apiKey": API_KEY, "regions": REGIONS, "markets": ",".join(props), "oddsFormat": ODDS_FORMAT}
    res = requests.get(url, params=params)
    return res.json() if res.status_code == 200 else {}

def main():
    now = datetime.now(timezone.utc)
    master_data = {"NBA": [], "MLB": [], "NHL": []}

    for key, cfg in TARGET_SPORTS.items():
        games = get_games(key)
        for g in games:
            commence = datetime.fromisoformat(g['commence_time'].replace('Z', '+00:00'))
            
            # Filter: 24hr Window & Skip Live Games
            if now < commence < (now + timedelta(hours=24)):
                entry = {"match": f"{g['away_team']} @ {g['home_team']}", "lines": []}
                
                # Fetch props ONLY if < 8 hours away
                if commence < (now + timedelta(hours=8)):
                    p_data = get_props(key, g['id'], cfg['props'])
                    # Parsing logic for p_data goes here (omitted for brevity, will provide full block next)
                
                master_data[cfg['title']].append(entry)

    with open("bets.json", "w") as f:
        json.dump(master_data, f, indent=2)

if __name__ == "__main__":
    main()
