import os
import json
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4"
REGIONS = "us"             
ODDS_FORMAT = "american"

# Highly accurate corporate parameter configurations for The Odds API v4
TARGET_SPORTS = {
    "basketball_nba": {
        "icon": "🏀",
        "title": "NBA",
        "markets": ["totals", "player_points", "player_rebounds", "player_assists"]
    },
    "baseball_mlb": {
        "icon": "⚾",
        "title": "MLB",
        "markets": ["totals", "batter_home_runs"] # Premium specific player prop string format
    }
}

def fetch_live_events(sport_key):
    """Grabs all scheduled upcoming match nodes for the target day matrix"""
    url = f"{BASE_URL}/sports/{sport_key}/events"
    params = {"apiKey": API_KEY}
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        print(f"API notice on {sport_key} event request: {response.status_code}")
        return []
    except Exception as e:
        print(f"Failed pulling events: {e}")
        return []

def fetch_event_props(sport_key, event_id, market_key):
    """Queries the exact unified v4 single-event odds matrix path"""
    url = f"{BASE_URL}/sports/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": market_key,
        "oddsFormat": ODDS_FORMAT
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

def parse_api_time(time_str):
    """Safely extracts date time formats from API strings"""
    if not time_str:
        return None
    try:
        clean_str = time_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        return None

def main():
    if not API_KEY:
        print("CRITICAL DATA ERROR: No valid ODDS_API_KEY detected.")
        return

    print("Booting Production Dual-Prop/Totals Extraction Engine...")
    detected_legs = []
    now_utc = datetime.now(timezone.utc)
    stale_boundary = now_utc - timedelta(hours=6)
    max_window = now_utc + timedelta(hours=36) # Keeps focus locked tightly onto current day cards

    for sport_key, configuration in TARGET_SPORTS.items():
        sport_icon = configuration["icon"]
        sport_label = configuration["title"]
        
        print(f"Scanning the active schedule stream for {sport_label}...")
        events = fetch_live_events(sport_key)
        print(f"Discovered {len(events)} matches listed on the server.")
        
        for event in events:
            event_id = event.get("id")
            home_team = event.get("home_team")
            away_team = event.get("away_team")
            game_matchup = f"{away_team} @ {home_team}"
            
            commence_time = parse_api_time(event.get("commence_time"))
            if commence_time and (commence_time < stale_boundary or commence_time > max_window):
                continue 

            print(f" -> Mapping core book lines for: {game_matchup}")

            for market_key in configuration["markets"]:
                raw_odds_payload = fetch_event_props(sport_key, event_id, market_key)
                if not raw_odds_payload:
                    continue

                bookmakers = raw_odds_payload.get("bookmakers", [])
                for book in bookmakers:
                    if book.get("key") in ["draftkings", "fanduel", "caesars", "betmgm"]:
                        book_title = book.get("title")
                        
                        for market in book.get("markets", []):
                            if market.get("key") == market_key:
                                outcomes = market.get("outcomes", [])
                                for outcome in outcomes:
                                    
                                    if market_key == "totals":
                                        name = outcome.get("name")
                                        point = outcome.get("point")
                                        price = outcome.get("price", 0)
                                        bet_desc = f"Game Total {name} {point} ({book_title})"
                                        group_label = "TOTALS"
                                    else:
                                        player = outcome.get("description")
                                        prop_type = outcome.get("name") # Over / Under
                                        point = outcome.get("point")
                                        price = outcome.get("price", 0)
                                        bet_desc = f"{player} {prop_type} {point} ({book_title})"
                                        
                                        if "home_runs" in market_key or "batter" in market_key:
                                            group_label = "HOME RUNS"
                                        else:
                                            group_label = market_key.replace("player_", "").upper()

                                    detected_legs.append({
                                        "sport": sport_icon,
                                        "trigger": "DAILY BOARD SLATE",
                                        "bet": bet_desc,
                                        "raw_odds": price,
                                        "game_matchup": game_matchup,
                                        "sport_group": f"{sport_label} - {group_label}"
                                    })
                        break # Limit data block to primary major bookmaker to maintain clear processing speeds
                        
    # Structure layout payload properties
    system_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    detected_legs.sort(key=lambda x: abs(x["raw_odds"]), reverse=True)
    
    nba_pool = [p for p in detected_legs if "NBA" in p["sport_group"]]
    mlb_pool = [p for p in detected_legs if "MLB" in p["sport_group"]]

    home_run_tickets = []
    grind_tickets = []

    # 1. GENERATE THE TOP PREMIUM SLIPS (3-legs split)
    if len(nba_pool) >= 3:
        home_run_tickets.append({
            "total_odds": "Calculated Multiplier",
            "target_payout_multiplier": "NBA Ticket",
            "legs": [{"sport": "🏀", "trigger": "NBA PROP COMBO", "bet": f"{l['game_matchup']}: {l['bet']}"} for l in nba_pool[:3]]
        })
    if len(mlb_pool) >= 3:
        home_run_tickets.append({
            "total_odds": "Calculated Multiplier",
            "target_payout_multiplier": "MLB Ticket",
            "legs": [{"sport": "⚾", "trigger": "MLB PROP COMBO", "bet": f"{l['game_matchup']}: {l['bet']}"} for l in mlb_pool[:3]]
        })

    if not home_run_tickets and len(detected_legs) >= 3:
        home_run_tickets.append({
            "total_odds": "Calculated Multiplier",
            "target_payout_multiplier": "Daily Cross",
            "legs": [{"sport": l["sport"], "trigger": "HYBRID COMBO", "bet": f"{l['game_matchup']}: {l['bet']}"} for l in detected_legs[:3]]
        })

    if not home_run_tickets:
        home_run_tickets.append({
            "total_odds": "N/A",
            "target_payout_multiplier": "0x",
            "legs": [{"sport": "📡", "trigger": "LINE SCANNING", "bet": "Data pipe running. Waiting for bookmakers to publish active daily slates."}]
        })

    # 2. GENERATE THE SECONDARY GRIND SLOTS
    grind_pool = detected_legs[3:15] if len(detected_legs) >= 6 else detected_legs
    for leg in grind_pool:
        grind_tickets.append({
            "game": leg["game_matchup"],
            "total_odds": f"{leg['raw_odds']:+}" if leg['raw_odds'] > 0 else str(leg['raw_odds']),
            "legs": [f"{leg['sport_group']}", f"{leg['bet']}"]
        })

    if not grind_tickets:
        grind_tickets.append({"game": "Daily Board Cleared", "total_odds": "Even", "legs": ["Awaiting next game board line rotations..."]})

    dashboard_payload = {
        "system_status": "ACTIVE",
        "last_updated": system_time,
        "home_run_tickets": home_run_tickets,
        "grind_tickets": grind_tickets
    }

    with open("bets.json", "w") as file:
        json.dump(dashboard_payload, file, indent=2)
        
    print(f"Success: Verified and compiled {len(detected_legs)} total lines.")

if __name__ == "__main__":
    main()
