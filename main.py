import os
import json
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports"
REGIONS = "us"             
ODDS_FORMAT = "american"

# EXCLUSIVE TARGET PROFILES WITH EXACT API MARKET STRINGS
TARGET_SPORTS = {
    "basketball_nba": {
        "icon": "🏀",
        "title": "NBA",
        "markets": "h2h,totals,player_points,player_assists,player_rebounds"
    },
    "baseball_mlb": {
        "icon": "⚾",
        "title": "MLB",
        "markets": "h2h,totals,batter_hits,batter_home_runs,pitcher_strikeouts"
    },
    "soccer_fifa_world_cup": {
        "icon": "🏆",
        "title": "World Cup",
        "markets": "h2h,totals"
    }
}

def fetch_live_events(sport_key):
    """Grabs today's scheduled match nodes to get game IDs"""
    url = f"{BASE_URL}/{sport_key}/events"
    params = {"apiKey": API_KEY}
    try:
        response = requests.get(url, params=params)
        return response.json() if response.status_code == 200 else []
    except Exception:
        return []

def fetch_explicit_markets(sport_key, event_id, markets_string):
    """Queries the exact targeted multi-market list for a game to force prop generation"""
    url = f"{BASE_URL}/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": markets_string,
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

    print("Booting Target-Driven Multi-Prop Extraction Engine...")
    compiled_lines = []
    now_utc = datetime.now(timezone.utc)
    max_window = now_utc + timedelta(hours=36) # Keep focus locked on upcoming daily cards

    for sport_key, config in TARGET_SPORTS.items():
        print(f"Tracking active schedule for {config['title']}...")
        events = fetch_live_events(sport_key)
        
        if not events or not isinstance(events, list):
            continue

        # Process a maximum of 6 games to prevent credit starvation on free tier keys
        target_games = events[:6]
        print(f" -> Extracting precise prop matrices for {len(target_games)} upcoming matches.")

        for game in target_games:
            event_id = game.get("id")
            matchup_name = f"{game.get('away_team')} @ {game.get('home_team')}"
            
            game_time = parse_api_time(game.get("commence_time"))
            if game_time and game_time > max_window:
                continue 

            # Hit the combined parameters URL to extract player details in one fetch call
            payload = fetch_explicit_markets(sport_key, event_id, config["markets"])
            if not payload or "bookmakers" not in payload:
                continue

            for book in payload.get("bookmakers", []):
                if book.get("key") in ["draftkings", "fanduel", "betmgm", "caesars"]:
                    book_title = book.get("title")
                    
                    for market in book.get("markets", []):
                        market_key = market.get("key", "")
                        
                        for outcome in market.get("outcomes", []):
                            price = outcome.get("price", 0)
                            
                            # Identify market type and map clean display tags for your frontend layout
                            if market_key == "h2h":
                                label = "GAME ML"
                                desc = f"{outcome.get('name')} Moneyline ({book_title})"
                            elif market_key == "totals":
                                label = "O/U TOTALS"
                                desc = f"Game Total {outcome.get('name')} {outcome.get('point')} ({book_title})"
                            else:
                                # This handles all custom player metrics seamlessly
                                label = market_key.replace("player_", "").replace("batter_", "").replace("pitcher_", "").upper()
                                desc = f"{outcome.get('description')} {outcome.get('name')} {outcome.get('point')} ({book_title})"

                            compiled_lines.append({
                                "sport": config["icon"],
                                "bet": desc,
                                "raw_odds": price,
                                "game_matchup": matchup_name,
                                "sport_group": f"{config['title']} - {label}"
                            })
                    break # Break after pulling from the first high-priority available bookmaker

    # SORT AND CONSTRUCT STRUCTURED MAIN DASHBOARD DATA PAYLOAD
    system_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Sort Rule: Pushes explicit player props to the absolute top of your UI terminal view
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
            "legs": [{"sport": "📡", "trigger": "STANDBY", "bet": "Data pipe running. Waiting for bookmakers to publish active lines."}]
        })

    for leg in compiled_lines[3:25]:
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
        grind_tickets.append({"game": "Board Cleared", "total_odds": "Even", "legs": ["Awaiting next daily game schedule loop..."]})

    output_payload = {
        "system_status": "ACTIVE",
        "last_updated": system_time,
        "home_run_tickets": home_run_tickets,
        "grind_tickets": grind_tickets
    }

    with open("bets.json", "w") as file:
        json.dump(output_payload, file, indent=2)
        
    print(f"Success: Isolated and pushed {len(compiled_lines)} total rows.")

if __name__ == "__main__":
    main()
