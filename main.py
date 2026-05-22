import os
import json
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports"
REGIONS = "us"             
ODDS_FORMAT = "american"

# Core Target Profiles & Specific Prop Markets
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
        return []
    except Exception:
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

def process_daily_matrix():
    """Scans all scheduled games for today and extracts active player prop targets"""
    detected_legs = []
    now_utc = datetime.now(timezone.utc)
    stale_boundary = now_utc - timedelta(hours=4)
    max_window = now_utc + timedelta(hours=24) # Hard targeted to today's slate

    for sport_key, configuration in TARGET_SPORTS.items():
        sport_icon = configuration["icon"]
        sport_label = configuration["title"]
        
        print(f"Mapping today's scheduled match vectors for {sport_label}...")
        events = fetch_live_events(sport_key)
        
        for event in events:
            event_id = event.get("id")
            home_team = event.get("home_team")
            away_team = event.get("away_team")
            game_matchup = f"{away_team} @ {home_team}"
            
            commence_time = parse_api_time(event.get("commence_time"))
            if commence_time and (commence_time < stale_boundary or commence_time > max_window):
                continue # Lock focus purely onto today's daily board

            # Sweep through every individual prop market for this specific game
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
                                    
                                    # Handle standard game totals vs player specific props
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

                                    # Variance filter optimization (Filter out heavy juice lines)
                                    if (price >= 100 or price <= -145):
                                        label = "SHARP PROP EDGE" if abs(price) > 190 else "DAILY FILTER"
                                        
                                        detected_legs.append({
                                            "sport": sport_icon,
                                            "trigger": label,
                                            "bet": bet_desc,
                                            "raw_odds": price,
                                            "game_matchup": game_matchup,
                                            "sport_group": f"{sport_label} - {group_label}"
                                        })
                        break # Grab lines from primary bookmaker and move to next category
                        
    return detected_legs

def calculate_ticket_payout(legs_slice):
    """Calculates cumulative odds multiplier numbers for multi-leg slips"""
    multiplier = 1
    for leg in legs_slice:
        p = leg.get("raw_odds", 100)
        mult = (p / 100 + 1) if p > 0 else (100 / abs(p) + 1)
        multiplier *= mult
    
    odds_str = f"+{int((multiplier - 1) * 100)}" if multiplier > 2 else "Calculated Match"
    return odds_str, f"{round(multiplier, 1)}x"

def build_dashboard_payload(all_props):
    """Splits collected player milestones perfectly into your custom UI layout"""
    system_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Sort absolute edge lines first
    all_props.sort(key=lambda x: abs(x["raw_odds"]), reverse=True)
    
    nba_pool = [p for p in all_props if "NBA" in p["sport_group"]]
    mlb_pool = [p for p in all_props if "MLB" in p["sport_group"]]

    home_run_tickets = []
    grind_tickets = []

    # 1. BUILD DAILY PROP HOME RUN SLIPS
    if len(nba_pool) >= 3:
        odds_str, multiplier_str = calculate_ticket_payout(nba_pool[:3])
        home_run_tickets.append({
            "total_odds": odds_str,
            "target_payout_multiplier": multiplier_str,
            "legs": [{"sport": "🏀", "trigger": "NBA PROP SLIP", "bet": f"{l['game_matchup']}: {l['bet']}"} for l in nba_pool[:3]]
        })
    if len(mlb_pool) >= 3:
        odds_str, multiplier_str = calculate_ticket_payout(mlb_pool[:3])
        home_run_tickets.append({
            "total_odds": odds_str,
            "target_payout_multiplier": multiplier_str,
            "legs": [{"sport": "⚾", "trigger": "MLB PROP SLIP", "bet": f"{l['game_matchup']}: {l['bet']}"} for l in mlb_pool[:3]]
        })

    if not home_run_tickets and len(all_props) >= 3:
        odds_str, multiplier_str = calculate_ticket_payout(all_props[:3])
        home_run_tickets.append({
            "total_odds": odds_str,
            "target_payout_multiplier": multiplier_str,
            "legs": [{"sport": l["sport"], "trigger": "HYBRID COMBO", "bet": f"{l['game_matchup']}: {l['bet']}"} for l in all_props[:3]]
        })

    if not home_run_tickets:
        home_run_tickets.append({
            "total_odds": "N/A",
            "target_payout_multiplier": "0x",
            "legs": [{"sport": "📡", "trigger": "BOARD CLEAR", "bet": "Props scanning active. Waiting for sportsbooks to update today's game slates."}]
        })

    # 2. BUILD THE GRIND ENGINE CARDS
    grind_pool = all_props[3:9] if len(all_props) >= 6 else all_props
    for leg in grind_pool:
        grind_tickets.append({
            "game": leg["game_matchup"],
            "total_odds": f"{leg['raw_odds']:+}" if leg['raw_odds'] > 0 else str(leg['raw_odds']),
            "legs": [f"{leg['sport_group']}", f"{leg['bet']}"]
        })

    if not grind_tickets:
        grind_tickets.append({"game": "Daily Board Cleared", "total_odds": "Even", "legs": ["Awaiting next game board rotation updates."]})

    return {
        "system_status": "ACTIVE",
        "last_updated": system_time,
        "home_run_tickets": home_run_tickets,
        "grind_tickets": grind_tickets
    }

def main():
    if not API_KEY:
        print("CRITICAL DATA ERROR: No valid ODDS_API_KEY detected.")
        return

    print("Initializing Focused Event-ID Player Prop Extraction Matrix...")
    all_compiled_props = process_player_props() if 'process_player_props' in globals() else process_daily_matrix()
    
    dashboard_payload = build_dashboard_payload(all_compiled_props)
    
    with open("bets.json", "w") as file:
        json.dump(dashboard_payload, file, indent=2)
        
    print(f"Success: Isolated {len(all_compiled_props)} active daily lines.")

if __name__ == "__main__":
    main()
