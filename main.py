import os
import json
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports"
REGIONS = "us"             
ODDS_FORMAT = "american"

# Core Target Profiles & Specific Prop Markets
PROP_MARKETS = {
    "basketball_nba": [
        {"market": "player_points", "label": "POINTS OVER/UNDER", "icon": "🏀"},
        {"market": "player_rebounds", "label": "REBOUNDS OVER/UNDER", "icon": "🏀"},
        {"market": "player_assists", "label": "ASSISTS OVER/UNDER", "icon": "🏀"}
    ],
    "baseball_mlb": [
        {"market": "player_hits_over_under", "label": "BASE HITS PROP", "icon": "⚾"},
        {"market": "player_home_runs", "label": "HOME RUN BLITZ", "icon": "⚾"}
    ]
}

def fetch_prop_odds(sport_key, market_key):
    """Fetches high-density player prop lines for specific targeted categories"""
    url = f"{BASE_URL}/{sport_key}/odds-events/"
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
        print(f"API Error fetching {market_key} for {sport_key}: {response.status_code}")
        return []
    except Exception as e:
        print(f"Connection error: {e}")
        return []

def parse_api_time(time_str):
    """Safely extracts date time formats from API strings without crashing"""
    if not time_str:
        return None
    try:
        clean_str = time_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        return None

def process_player_props():
    """Loops through targeted sports and compiles deep player prop markets"""
    detected_props = []
    now_utc = datetime.now(timezone.utc)
    stale_boundary = now_utc - timedelta(hours=4)
    max_window = now_utc + timedelta(hours=36)

    for sport_key, markets_list in PROP_MARKETS.items():
        for item in markets_list:
            market_key = item["market"]
            market_label = item["label"]
            sport_icon = item["icon"]

            print(f"Pulling {market_key} stream vectors for {sport_key}...")
            raw_data = fetch_prop_odds(sport_key, market_key)
            
            if not raw_data:
                continue

            for game in raw_data:
                commence_time_str = game.get("commence_time")
                game_time = parse_api_time(commence_time_str)
                
                # Dynamic schedule rotations
                if game_time and (game_time < stale_boundary or game_time > max_window):
                    continue

                home_team = game.get("home_team")
                away_team = game.get("away_team")
                game_matchup = f"{away_team} @ {home_team}"
                sport_title = game.get("sport_title", "Live Prop")

                bookmakers = game.get("bookmakers", [])
                for book in bookmakers:
                    if book.get("key") in ["draftkings", "fanduel", "caesars", "betmgm"]:
                        book_title = book.get("title")
                        
                        for market in book.get("markets", []):
                            if market.get("key") == market_key:
                                outcomes = market.get("outcomes", [])
                                
                                for outcome in outcomes:
                                    player_name = outcome.get("description")
                                    bet_type = outcome.get("name") # Over or Under
                                    line_value = outcome.get("point") # e.g., 25.5, 0.5
                                    price = outcome.get("price", 0)

                                    # Sharp line filter optimization
                                    if (price >= 105 or price <= -155):
                                        label = "PROJECTION UNDER" if bet_type.lower() == "under" else "VOLUME OVER"
                                        if abs(price) > 230: label = "SHARP PROP EDGE"

                                        detected_props.append({
                                            "sport": sport_icon,
                                            "trigger": label,
                                            "bet": f"{player_name} {bet_type} {line_value} ({book_title})",
                                            "raw_odds": price,
                                            "game_matchup": game_matchup,
                                            "sport_group": f"{sport_title} - {market_label}"
                                        })
                        break # Limit data extraction to the first major available bookmaker per game to keep layout clean
                        
    return detected_props

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
    
    # Extract structural layers
    nba_pool = [p for p in all_props if p["sport"] == "🏀"]
    mlb_pool = [p for p in all_props if p["sport"] == "⚾"]

    home_run_tickets = []
    grind_tickets = []

    # 1. COMPILE HOME RUN PROP TICKETS (Highly correlated 3-leg player parlays)
    if len(nba_pool) >= 3:
        odds_str, multiplier_str = calculate_ticket_payout(nba_pool[:3])
        home_run_tickets.append({
            "total_odds": odds_str,
            "target_payout_multiplier": multiplier_str,
            "legs": [{"sport": "🏀", "trigger": "NBA PROP COMBO", "bet": f"{l['game_matchup']}: {l['bet']}"} for l in nba_pool[:3]]
        })
    if len(mlb_pool) >= 3:
        odds_str, multiplier_str = calculate_ticket_payout(mlb_pool[:3])
        home_run_tickets.append({
            "total_odds": odds_str,
            "target_payout_multiplier": multiplier_str,
            "legs": [{"sport": "⚾", "trigger": "MLB MILESTONE PARLAY", "bet": f"{l['game_matchup']}: {l['bet']}"} for l in mlb_pool[:3]]
        })

    # Fallback to general blend if pools are limited
    if not home_run_tickets and len(all_props) >= 2:
        odds_str, multiplier_str = calculate_ticket_payout(all_props[:3])
        home_run_tickets.append({
            "total_odds": odds_str,
            "target_payout_multiplier": multiplier_str,
            "legs": [{"sport": l["sport"], "trigger": "PROP SLIP", "bet": f"{l['game_matchup']}: {l['bet']}"} for l in all_props[:3]]
        })

    if not home_run_tickets:
        home_run_tickets.append({
            "total_odds": "N/A",
            "target_payout_multiplier": "0x",
            "legs": [{"sport": "📡", "trigger": "BOARD CLEAR", "bet": "Scanning lines. Awaiting bookmaker player milestone releases."}]
        })

    # 2. COMPILE THE GRIND ENGINE (High probability single prop items)
    grind_pool = all_props[3:9] if len(all_props) >= 6 else all_props
    for leg in grind_pool:
        grind_tickets.append({
            "game": leg["game_matchup"],
            "total_odds": f"{leg['raw_odds']:+}" if leg['raw_odds'] > 0 else str(leg['raw_odds']),
            "legs": [f"{leg['sport_group']}", f"{leg['bet']}"]
        })

    if not grind_tickets:
        grind_tickets.append({"game": "Line Rotations Clear", "total_odds": "Even", "legs": ["Awaiting next game board data..."]})

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

    print("Initializing Player Prop Processing Algorithm...")
    all_compiled_props = process_player_props()
    
    dashboard_payload = build_dashboard_payload(all_compiled_props)
    
    with open("bets.json", "w") as file:
        json.dump(dashboard_payload, file, indent=2)
        
    print(f"Success: Compiled {len(all_compiled_props)} total verified player prop data nodes.")

if __name__ == "__main__":
    main()
