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

def fetch_data(url, params):
    res = requests.get(url, params=params)
    return res.json() if res.status_code == 200 else []

def main():
    now = datetime.now(timezone.utc)
    results = {"NBA": [], "MLB": [], "NHL": []}
    
    for key, cfg in TARGET_SPORTS.items():
        # Fetch games
        games = fetch_data(f"{BASE_URL}/{key}/odds", {"apiKey": API_KEY, "regions": REGIONS, "markets": "h2h,totals", "oddsFormat": ODDS_FORMAT})
        
        for g in games[:4]: # Limit to 4 games
            commence = datetime.fromisoformat(g['commence_time'].replace('Z', '+00:00'))
            
            if now < commence < (now + timedelta(hours=24)):
                entry = {"match": f"{g['away_team']} @ {g['home_team']}", "lines": g.get('bookmakers', []), "props": []}
                
                # Fetch Props if within 8 hours
                if commence < (now + timedelta(hours=8)):
                    p_data = fetch_data(f"{BASE_URL}/{key}/events/{g['id']}/odds", {"apiKey": API_KEY, "regions": REGIONS, "markets": ",".join(cfg['props']), "oddsFormat": ODDS_FORMAT})
                    if p_data:
                        entry["props"] = p_data.get('bookmakers', [])
                
                results[cfg['title']].append(entry)
                
    with open("bets.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
