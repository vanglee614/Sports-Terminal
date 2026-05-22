import os
import json
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports"
REGIONS = "us"             
ODDS_FORMAT = "american"

# STRICT EXCLUSIVE SPORT & DETAILED PROP PROFILE CONFIGURATION
TARGET_SPORTS = {
    "basketball_nba": {
        "icon": "🏀",
        "title": "NBA",
        "prop_markets": ["player_points", "player_assists", "player_rebounds"]
    },
    "baseball_mlb": {
        "icon": "⚾",
        "title": "MLB",
        "prop_markets": ["batter_hits", "batter_home_runs", "pitcher_strikeouts"]
    },
    "soccer_fifa_world_cup": {
        "icon": "🏆",
        "title": "World Cup",
        "prop_markets": [] # Main tournament match lines only
    }
}

def fetch_main_game_lines(sport_key):
    """Fetches Moneyline and Totals for the entire league slate in 1 credit"""
    url = f"{BASE_URL}/{sport_key}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": "h2h,totals",
        "oddsFormat": ODDS_FORMAT
    }
    try:
        response = requests.get(url, params=params)
        return response.json() if response.status_code == 200 else []
    except Exception:
        return []

def fetch_live_player_props(sport_key, event_id, prop_market):
    """Targets precise multi-prop player data matrices for an upcoming game matchup"""
    url = f"{BASE_URL}/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": prop_market,
        "oddsFormat": ODDS_FORMAT
    }
    try:
        response = requests.get(url, params=params)
        return response.json() if response.status_code == 200 else None
    except Exception:
        return None

def parse_api_time(time_str):
    if not time_str: return None
    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except Exception:
        return None

def main():
    if not API_KEY:
        print("CRITICAL CONFIG ERROR: Missing active API Key token.")
        return

    print("Booting Targeted Prop Engine: ML + Custom NBA/MLB Prop Sheets...")
    compiled_lines = []
    now_utc = datetime.now(timezone.utc)
    max_window = now_utc + timedelta(hours=36) # Keep focus locked strictly onto upcoming slate rotations

    for sport_key, config in TARGET_SPORTS.items():
        print(f"Syncing daily slate data arrays for {config['title']}...")
        games_data = fetch_main_game_lines(sport_key)
        
        if not games_data or not isinstance(games_data, list):
            continue

        for game in games_data:
            event_id = game.get("id")
            home_team = game.get("home_team")
            away_team = game.get("away_team")
            matchup_name = f"{away_team} @ {home_team}"
            
            game_time = parse_api_time(game.get("commence_time"))
            if game_time and game_time > max_window:
                continue 

            # 1. PROCESS CORE MONEYLINE AND GAME TOTALS FIRST
            for book in game.get("bookmakers", []):
                if book.get("key") in ["draftkings", "fanduel", "caesars", "betmgm"]:
                    book_name = book.get("title")
                    for market in book.get("markets", []):
                        if market.get("key") == "h2h":
                            for outcome in market.get("outcomes", []):
                                compiled_lines.append({
                                    "sport": config["icon"],
                                    "trigger": "MONEYLINE PICK",
                                    "bet": f"{outcome.get('name')} Moneyline ({book_name})",
                                    "raw_odds": outcome.get("price", 0),
                                    "game_matchup": matchup_name,
                                    "sport_group": f"{config['title']} - GAME ML"
                                })
                        elif market.get("key") == "totals":
                            for outcome in market.get("outcomes", []):
                                compiled_lines.append({
                                    "sport": config["icon"],
                                    "trigger": "GAME TOTAL O/U",
                                    "bet": f"Game Total {outcome.get('name')} {outcome.get('point')} ({book_name})",
                                    "raw_odds": outcome.get("price", 0),
                                    "game_matchup": matchup_name,
                                    "sport_group": f"{config['title']} - O/U TOTALS"
                                })
                    break # Use primary sportsbook data block

            # 2. SECTOR PROPS MATCHING: If game is today, query every requested prop market
            if config["prop_markets"] and game_time and (game_time - now_utc) < timedelta(hours=16):
                for market_key in config["prop_markets"]:
                    print(f"   -> Pulling market sheet [{market_key}] for: {matchup_name}")
                    props_payload = fetch_live_player_props(sport_key, event_id, market_key)
                    
                    if props_payload and "bookmakers" in props_payload:
                        for book in props_payload.get("bookmakers", []):
                            if book.get("key") in ["draftkings", "fanduel"]:
                                for market in book.get("markets", []):
                                    if market.get("key") == market_key:
                                        for outcome in market.get("outcomes", []):
                                            p_name = outcome.get("description")
                                            o_type = outcome.get("name") # Over / Under
                                            o_point = outcome.get("point")
                                            
                                            # Clean front-end visual labels
                                            label_cleanup = market_key.replace("player_", "").replace("batter_", "").replace("pitcher_", "").upper()
                                            
                                            compiled_lines.append({
                                                "sport": config["icon"],
                                                "trigger": "PLAYER PROP SELECTION",
                                                "bet": f"{p_name} {o_type} {o_point} ({book.get('title')})",
                                                "raw_odds": outcome.get("price", 0),
                                                "game_matchup": matchup_name,
                                                "sport_group": f"{config['title']} - {label_cleanup}"
                                            })
                                break

    # SORT AND CONSTRUCT DASHBOARD PAYLOAD FILE
    system_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Sort order: Priorities individual props to display above moneylines
    compiled_lines.sort(key=lambda x: "GAME ML" not in x["sport_group"], reverse=True)

    home_run_tickets = []
    grind_tickets = []

    # Compile Top Parlay Cards
    if len(compiled_lines) >= 3:
        home_run_tickets.append({
            "total_odds": "Calculated Multiplier",
            "target_payout_multiplier": "Daily Slate Ticket",
            "legs": [{"sport": l["sport"], "trigger": l["sport_group"], "bet": f"{l['game_matchup']}: {l['bet']}"} for l in compiled_lines[:3]]
        })
    else:
        home_run_tickets.append({
            "total_odds": "N/A",
            "target_payout_multiplier": "0x",
            "legs": [{"sport": "📡", "trigger": "STANDBY", "bet": "Data link secure. Waiting for sportsbooks to issue lines."}]
        })

    # Compile Secondary Grid Layout Blocks
    for leg in compiled_lines[3:18]:
        grind_tickets.append({
            "game": leg["game_matchup"],
            "total_odds": f"{leg['raw_odds']:+}" if leg['raw_odds'] > 0 else str(leg['raw_odds']),
            "legs": [f"{leg['sport_group']}", f"{leg['bet']}"]
        })

    if not grind_tickets and compiled_lines:
        for leg in compiled_lines:
            grind_tickets.append({
                "game": leg["game_matchup"],
                "total_odds": f"{leg['raw_odds']:+}" if leg['raw_odds'] > 0 else str(leg['raw_odds']),
                "legs": [f"{leg['sport_group']}", f"{leg['bet']}"]
            })

    if not grind_tickets:
        grind_tickets.append({"game": "Board Rotations Resetting", "total_odds": "Even", "legs": ["Awaiting active morning line updates..."]})

    output_payload = {
        "system_status": "ACTIVE",
        "last_updated": system_time,
        "home_run_tickets": home_run_tickets,
        "grind_tickets": grind_tickets
    }

    with open("bets.json", "w") as file:
        json.dump(output_payload, file, indent=2)
        
    print(f"Success: Isolated and pushed {len(compiled_lines)} targeted rows.")

if __name__ == "__main__":
    main()
