import os
import json
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports"
REGIONS = "us"             
ODDS_FORMAT = "american"

# Strictly defined target profiles
TARGET_SPORTS = {
    "basketball_nba": {
        "icon": "🏀",
        "title": "NBA",
        "keywords": ["POINTS", "ASSISTS", "REBOUNDS"]
    },
    "baseball_mlb": {
        "icon": "⚾",
        "title": "MLB",
        "keywords": ["HITS", "HOME_RUNS", "STRIKEOUTS", "STRIKE_OUTS"]
    },
    "soccer_fifa_world_cup": {
        "icon": "🏆",
        "title": "World Cup",
        "keywords": []
    }
}

def fetch_main_game_lines(sport_key):
    """Fetches Moneyline and Totals for the entire league slate"""
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

def fetch_all_event_props(sport_key, event_id):
    """Queries the event endpoint without market restrictions to pull ALL live props at once"""
    url = f"{BASE_URL}/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
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

    print("Booting Unified Prop Harvest Engine...")
    compiled_lines = []
    now_utc = datetime.now(timezone.utc)
    max_window = now_utc + timedelta(hours=36) 

    for sport_key, config in TARGET_SPORTS.items():
        print(f"Syncing daily slate data arrays for {config['title']}...")
        games_data = fetch_main_game_lines(sport_key)
        
        if not games_data or not isinstance(games_data, list):
            continue

        # Cap processing to today's active matches to preserve credit pools
        active_games = [g for g in games_data if parse_api_time(g.get("commence_time")) and parse_api_time(g.get("commence_time")) <= max_window]
        print(f" -> Found {len(active_games)} upcoming matches within the daily schedule window.")

        for game in active_games:
            event_id = game.get("id")
            matchup_name = f"{game.get('away_team')} @ {game.get('home_team')}"
            
            # 1. HARVEST CORE LINES FIRST (Moneyline & Game Totals)
            for book in game.get("bookmakers", []):
                if book.get("key") in ["draftkings", "fanduel", "caesars", "betmgm"]:
                    book_name = book.get("title")
                    for market in book.get("markets", []):
                        if market.get("key") == "h2h":
                            for outcome in market.get("outcomes", []):
                                compiled_lines.append({
                                    "sport": config["icon"],
                                    "bet": f"{outcome.get('name')} Moneyline ({book_name})",
                                    "raw_odds": outcome.get("price", 0),
                                    "game_matchup": matchup_name,
                                    "sport_group": f"{config['title']} - GAME ML"
                                })
                        elif market.get("key") == "totals":
                            for outcome in market.get("outcomes", []):
                                compiled_lines.append({
                                    "sport": config["icon"],
                                    "bet": f"Game Total {outcome.get('name')} {outcome.get('point')} ({book_name})",
                                    "raw_odds": outcome.get("price", 0),
                                    "game_matchup": matchup_name,
                                    "sport_group": f"{config['title']} - O/U TOTALS"
                                })
                    break 

            # 2. DEEP UNFILTERED HARVEST: Fetch ALL available player prop arrays for this match
            if config["keywords"]:
                print(f"   -> Extracting full prop payload sheet for: {matchup_name}")
                props_payload = fetch_all_event_props(sport_key, event_id)
                
                if props_payload and "bookmakers" in props_payload:
                    for book in props_payload.get("bookmakers", []):
                        if book.get("key") in ["draftkings", "fanduel", "betmgm"]:
                            book_title = book.get("title")
                            
                            for market in book.get("markets", []):
                                market_key_upper = market.get("key", "").upper()
                                
                                # Text-match check against our prioritized keyword lists
                                match_found = any(keyword in market_key_upper for keyword in config["keywords"])
                                
                                if match_found:
                                    clean_label = market_key_upper.replace("PLAYER_", "").replace("BATTER_", "").replace("PITCHER_", "").replace("_OVER_UNDER", "")
                                    
                                    for outcome in market.get("outcomes", []):
                                        p_name = outcome.get("description", "Player")
                                        o_type = outcome.get("name", "")
                                        o_point = outcome.get("point", "")
                                        
                                        compiled_lines.append({
                                            "sport": config["icon"],
                                            "bet": f"{p_name} {o_type} {o_point} ({book_title})",
                                            "raw_odds": outcome.get("price", 0),
                                            "game_matchup": matchup_name,
                                            "sport_group": f"{config['title']} - {clean_label}"
                                        })
                            break # Core book processing successful

    # CONSTRUCT SYSTEM WEB PAYLOAD DESTINATION
    system_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Sort order: Guarantees your player props jump right to the top of the interface screen
    compiled_lines.sort(key=lambda x: "GAME ML" not in x["sport_group"] and "TOTALS" not in x["sport_group"], reverse=True)

    home_run_tickets = []
    grind_tickets = []

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
            "legs": [{"sport": "📡", "trigger": "STANDBY", "bet": "Data pipe secure. Awaiting bookmaker prop boards."}]
        })

    for leg in compiled_lines[3:20]:
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
        grind_tickets.append({"game": "Board Rotations Active", "total_odds": "Even", "legs": ["Awaiting next line updates..."]})

    output_payload = {
        "system_status": "ACTIVE",
        "last_updated": system_time,
        "home_run_tickets": home_run_tickets,
        "grind_tickets": grind_tickets
    }

    with open("bets.json", "w") as file:
        json.dump(output_payload, file, indent=2)
        
    print(f"Success: Isolated and pushed {len(compiled_lines)} perfect filtered data rows.")

if __name__ == "__main__":
    main()
