import os
import json
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4"
REGIONS = "us"             
ODDS_FORMAT = "american"

# Streamlined high-priority markets to preserve your monthly API credit limits
TARGET_SPORTS = {
    "basketball_nba": {"icon": "🏀", "title": "NBA", "prop": "player_points"},
    "baseball_mlb": {"icon": "⚾", "title": "MLB", "prop": "batter_home_runs"}
}

def fetch_live_events(sport_key):
    """Grabs today's scheduled match nodes"""
    url = f"{BASE_URL}/sports/{sport_key}/events"
    params = {"apiKey": API_KEY}
    try:
        response = requests.get(url, params=params)
        return response.json() if response.status_code == 200 else []
    except Exception:
        return []

def fetch_event_odds_matrix(sport_key, event_id, market_key):
    """Queries the single event endpoint safely"""
    url = f"{BASE_URL}/sports/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": market_key,
        "oddsFormat": ODDS_FORMAT
    }
    try:
        response = requests.get(url, params=params)
        return response.json() if response.status_code == 200 else None
    except Exception:
        return None

def main():
    if not API_KEY:
        print("CRITICAL DATA ERROR: No valid ODDS_API_KEY detected.")
        return

    print("Executing Credit-Safe Daily Sports Extraction...")
    detected_legs = []
    now_utc = datetime.now(timezone.utc)
    max_window = now_utc + timedelta(hours=30) 

    for sport_key, config in TARGET_SPORTS.items():
        events = fetch_live_events(sport_key)
        
        # Pull up to 5 games max per sport to protect your API limits from getting fried
        for event in events[:5]:
            event_id = event.get("id")
            game_matchup = f"{event.get('away_team')} @ {event.get('home_team')}"
            
            # 1. AGGRESSIVE SEARCH: Attempt to grab the individual player props first
            payload = fetch_event_odds_matrix(sport_key, event_id, config["prop"])
            
            # 2. SMART FALLBACK: If player props aren't live yet, pull the standard Game Totals instantly
            if not list_has_markets(payload):
                payload = fetch_event_odds_matrix(sport_key, event_id, "totals")
                market_used = "totals"
            else:
                market_used = config["prop"]

            if not payload:
                continue

            for book in payload.get("bookmakers", []):
                if book.get("key") in ["draftkings", "fanduel", "betmgm"]:
                    for market in book.get("markets", []):
                        if market.get("key") == market_used:
                            for outcome in market.get("outcomes", []):
                                if market_used == "totals":
                                    bet_desc = f"Game Total {outcome.get('name')} {outcome.get('point')} ({book.get('title')})"
                                    group_lbl = "TOTALS"
                                else:
                                    bet_desc = f"{outcome.get('description')} {outcome.get('name')} {outcome.get('point')} ({book.get('title')})"
                                    group_lbl = "PLAYER PROPS"

                                detected_legs.append({
                                    "sport": config["icon"],
                                    "trigger": "LIVE DAILY BOARD",
                                    "bet": bet_desc,
                                    "raw_odds": outcome.get("price", 0),
                                    "game_matchup": game_matchup,
                                    "sport_group": f"{config['title']} - {group_lbl}"
                                })
                    break

    # Format data for your custom web dashboard frontend UI
    system_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    detected_legs.sort(key=lambda x: abs(x["raw_odds"]), reverse=True)
    
    home_run_tickets = []
    grind_tickets = []

    if len(detected_legs) >= 3:
        home_run_tickets.append({
            "total_odds": "Calculated Multiplier",
            "target_payout_multiplier": "Daily Combo",
            "legs": [{"sport": l["sport"], "trigger": l["sport_group"], "bet": f"{l['game_matchup']}: {l['bet']}"} for l in detected_legs[:3]]
        })
    else:
        home_run_tickets.append({
            "total_odds": "N/A",
            "target_payout_multiplier": "0x",
            "legs": [{"sport": "📡", "trigger": "STANDBY", "bet": "Data line live. Bookmakers are prepping active daily prop slates."}]
        })

    for leg in detected_legs[3:12]:
        grind_tickets.append({
            "game": leg["game_matchup"],
            "total_odds": f"{leg['raw_odds']:+}" if leg['raw_odds'] > 0 else str(leg['raw_odds']),
            "legs": [f"{leg['sport_group']}", f"{leg['bet']}"]
        })

    if not grind_tickets and detected_legs:
        for leg in detected_legs:
            grind_tickets.append({
                "game": leg["game_matchup"],
                "total_odds": f"{leg['raw_odds']:+}" if leg['raw_odds'] > 0 else str(leg['raw_odds']),
                "legs": [f"{leg['sport_group']}", f"{leg['bet']}"]
            })

    if not grind_tickets:
        grind_tickets.append({"game": "Board Rotations Clear", "total_odds": "Even", "legs": ["Awaiting morning line updates..."]})

    with open("bets.json", "w") as file:
        json.dump({"system_status": "ACTIVE", "last_updated": system_time, "home_run_tickets": home_run_tickets, "grind_tickets": grind_tickets}, file, indent=2)
    print(f"Success: Compiled {len(detected_legs)} total lines.")

def list_has_markets(payload):
    if not payload or "bookmakers" not in payload: return False
    for b in payload["bookmakers"]:
        if "markets" in b and len(b["markets"]) > 0: return True
    return False

if __name__ == "__main__":
    main()
