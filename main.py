import os
import json
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports"
REGIONS = "us"             
ODDS_FORMAT = "american"

# Focus explicitly on Player Props and Totals
TARGET_SPORTS = {
    "basketball_nba": {
        "icon": "🏀",
        "title": "NBA",
        "markets": ["totals", "player_points", "player_rebounds", "player_assists"]
    },
    "baseball_mlb": {
        "icon": "⚾",
        "title": "MLB",
        "markets": ["totals", "player_hits_over_under", "player_home_runs"]
    }
}

def fetch_live_events(sport_key):
    """Grabs all upcoming game IDs for the sport to target props accurately"""
    url = f"{BASE_URL}/{sport_key}/events"
    params = {"apiKey": API_KEY}
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        print(f"Error fetching events for {sport_key}: {response.status_code}")
        return []
    except Exception as e:
        print(f"Network error events: {e}")
        return []

def fetch_event_props(sport_key, event_id, market_key):
    """Queries the premium props engine for a specific game event ID"""
    url = f"{BASE_URL}/{sport_key}/events/{event_id}/odds"
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

    print("Initializing Unfiltered Player Prop Extraction Engine...")
    detected_legs = []
    now_utc = datetime.now(timezone.utc)
    stale_boundary = now_utc - timedelta(hours=6)
    max_window = now_utc + timedelta(hours=30) # Capture all slate games within a 30hr block

    for sport_key, configuration in TARGET_SPORTS.items():
        sport_icon = configuration["icon"]
        sport_label = configuration["title"]
        
        print(f"Mapping scheduled match nodes for {sport_label}...")
        events = fetch_live_events(sport_key)
        print(f"Found {len(events)} total upcoming events scheduled.")
        
        for event in events:
            event_id = event.get("id")
            home_team = event.get("home_team")
            away_team = event.get("away_team")
            game_matchup = f"{away_team} @ {home_team}"
            
            commence_time = parse_api_time(event.get("commence_time"))
            if commence_time and (commence_time < stale_boundary or commence_time > max_window):
                continue 

            print(f"Scanning deep markets for target game: {game_matchup}")

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
                                        group_label = market_key.replace("player_", "").upper()

                                    # REMOVED OD_FILTERS: Allow standard lines (-110, -115) to pass freely to your UI
                                    label = "SHARP PROP EDGE" if abs(price) > 180 else "DAILY SLATE PROP"
                                    
                                    detected_legs.append({
                                        "sport": sport_icon,
                                        "trigger": label,
                                        "bet": bet_desc,
                                        "raw_odds": price,
                                        "game_matchup": game_matchup,
                                        "sport_group": f"{sport_label} - {group_label}"
                                    })
                        break # Limit data extraction to the primary available bookmaker with lines
                        
    # Process dashboard file payload layout
    system_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Order layout by the most valuable lines
    detected_legs.sort(key=lambda x: abs(x["raw_odds"]), reverse=True)
    
    nba_pool = [p for p in detected_legs if "NBA" in p["sport_group"]]
    mlb_pool = [p for p in detected_legs if "MLB" in p["sport_group"]]

    home_run_tickets = []
    grind_tickets = []

    # 1. BUILD TARGET SLIP PARLAYS (3-legs)
    if len(nba_pool) >= 3:
        home_run_tickets.append({
            "total_odds": "Calculated Multiplier",
            "target_payout_multiplier": "Multi-Leg",
            "legs": [{"sport": "🏀", "trigger": "NBA PROP SLIP", "bet": f"{l['game_matchup']}: {l['bet']}"} for l in nba_pool[:3]]
        })
    elif len(detected_legs) >= 3:
        home_run_tickets.append({
            "total_odds": "Calculated Multiplier",
            "target_payout_multiplier": "Hybrid Multi-Leg",
            "legs": [{"sport": l["sport"], "trigger": "HYBRID COMBO", "bet": f"{l['game_matchup']}: {l['bet']}"} for l in detected_legs[:3]]
        })

    if not home_run_tickets:
        home_run_tickets.append({
            "total_odds": "N/A",
            "target_payout_multiplier": "0x",
            "legs": [{"sport": "📡", "trigger": "BOARD SCANNING", "bet": "Props connection active. Scanning today's slates for live player lines."}]
        })

    # 2. BUILD THE GRIND ENGINE DATA CARDS
    grind_pool = detected_legs[3:12] if len(detected_legs) >= 6 else detected_legs
    for leg in grind_pool:
        grind_tickets.append({
            "game": leg["game_matchup"],
            "total_odds": f"{leg['raw_odds']:+}" if leg['raw_odds'] > 0 else str(leg['raw_odds']),
            "legs": [f"{leg['sport_group']}", f"{leg['bet']}"]
        })

    if not grind_tickets:
        grind_tickets.append({"game": "Daily Board Cleared", "total_odds": "Even", "legs": ["Awaiting next game line release..."]})

    dashboard_payload = {
        "system_status": "ACTIVE",
        "last_updated": system_time,
        "home_run_tickets": home_run_tickets,
        "grind_tickets": grind_tickets
    }

    with open("bets.json", "w") as file:
        json.dump(dashboard_payload, file, indent=2)
        
    print(f"Success: Isolated and saved {len(detected_legs)} total active daily lines.")

if __name__ == "__main__":
    main()
