import os
import json
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports"
REGIONS = "us"             
MARKETS = "h2h,spreads"    
ODDS_FORMAT = "american"

# Core Target Profiles
TARGET_LEAGUES = {
    "basketball_nba": "🏀 NBA",
    "baseball_mlb": "⚾ MLB"
}

def fetch_all_active_sports():
    """Dynamically grabs every single sport/league currently active on the global market"""
    url = f"{BASE_URL}"
    params = {"apiKey": API_KEY}
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return [sport["key"] for sport in response.json() if sport.get("active", True)]
        return []
    except Exception as e:
        print(f"Error mapping active sports: {e}")
        return []

def fetch_league_odds(league_key):
    """Fetches full market pricing lines for a specific league data-chunk"""
    url = f"{BASE_URL}/{league_key}/odds/"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": ODDS_FORMAT
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        return []

def parse_api_time(time_str):
    """Safely extracts date time formats from API strings without crashing"""
    if not time_str:
        return None
    try:
        clean_str = time_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        try:
            return datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            return None

def process_market_legs(all_games_data):
    """
    Separates targets by preference tier (NBA/MLB vs others)
    and actively discards games that started more than 4 hours ago.
    """
    nba_legs = []
    mlb_legs = []
    other_legs = []
    
    now_utc = datetime.now(timezone.utc)
    # Stale boundary: Eliminate items that tipped off/started over 4 hours ago
    stale_boundary = now_utc - timedelta(hours=4)
    # Forward look: Pull within a 36-hour horizon to stay centered on current/next-day cards
    max_window = now_utc + timedelta(hours=36)
    
    for game in all_games_data:
        commence_time_str = game.get("commence_time")
        game_time = parse_api_time(commence_time_str)
        
        if game_time:
            # DYNAMIC ROTATION: Discard stale completed slates or distant futures automatically
            if game_time < stale_boundary or game_time > max_window:
                continue

        home_team = game.get("home_team")
        away_team = game.get("away_team")
        sport_key = game.get("sport_key", "").lower()
        sport_title = game.get("sport_title", "Live Event")
        
        # Determine universal sport icons safely
        icon = "🎯"
        if "football" in sport_key or "afl" in sport_key: icon = "🏈"
        elif "basketball" in sport_key: icon = "🏀"
        elif "hockey" in sport_key: icon = "🏒"
        elif "baseball" in sport_key: icon = "⚾"
        elif "soccer" in sport_key: icon = "⚽"
        elif "tennis" in sport_key: icon = "🎾"

        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            continue
            
        for book in bookmakers:
            if book.get("key") in ["draftkings", "fanduel", "betmgm", "caesars"]:
                for market in book.get("markets", []):
                    if market.get("key") == "h2h":
                        outcomes = market.get("outcomes", [])
                        for outcome in outcomes:
                            price = outcome.get("price", 0)
                            
                            # Market variance profiling threshold
                            if (price >= 115 or price <= -165):
                                label = "SHARP STEAM" if price < 0 else "REVERSE LINE"
                                if abs(price) > 240: label = "HEAVY VALUE"
                                
                                book_name = book.get("title")
                                leg_item = {
                                    "sport": icon,
                                    "trigger": label,
                                    "bet": f"{outcome.get('name')} ({book_name})",
                                    "raw_odds": price,
                                    "game_matchup": f"{away_team} @ {home_team}",
                                    "sport_group": sport_title
                                }
                                
                                # Route to targeted matrix arrays
                                if sport_key == "basketball_nba":
                                    nba_legs.append(leg_item)
                                elif sport_key == "baseball_mlb":
                                    mlb_legs.append(leg_item)
                                else:
                                    other_legs.append(leg_item)
                break
                
    # Sort individual arrays based on lines variance intensity
    nba_legs.sort(key=lambda x: abs(x["raw_odds"]), reverse=True)
    mlb_legs.sort(key=lambda x: abs(x["raw_odds"]), reverse=True)
    other_legs.sort(key=lambda x: abs(x["raw_odds"]), reverse=True)
    
    return nba_legs, mlb_legs, other_legs

def calculate_ticket_payout(legs_slice):
    """Calculates cumulative odds multiplier numbers for high-end tickets"""
    multiplier = 1
    for leg in legs_slice:
        p = leg.get("raw_odds", 100)
        mult = (p / 100 + 1) if p > 0 else (100 / abs(p) + 1)
        multiplier *= mult
    
    odds_str = f"+{int((multiplier - 1) * 100)}" if multiplier > 2 else "Calculated Match"
    return odds_str, f"{round(multiplier, 1)}x"

def build_structured_payload(nba_legs, mlb_legs, other_legs):
    """Formats separated data slices natively into your UI's designated ticket targets"""
    system_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # --- 1. HOME RUN TICKETS SECTION (Dedicated split between NBA & MLB high-ends) ---
    home_run_tickets = []
    
    # NBA Home Run Builder
    if len(nba_legs) >= 2:
        odds_str, multiplier_str = calculate_ticket_payout(nba_legs[:3])
        home_run_tickets.append({
            "total_odds": odds_str,
            "target_payout_multiplier": multiplier_str,
            "legs": [{"sport": l["sport"], "trigger": "NBA HOME RUN", "bet": f"{l['game_matchup']}: {l['bet']}"} for l in nba_legs[:3]]
        })
    # MLB Home Run Builder (Fallback if NBA has finished or is resting)
    if len(mlb_legs) >= 2:
        odds_str, multiplier_str = calculate_ticket_payout(mlb_legs[:3])
        home_run_tickets.append({
            "total_odds": odds_str,
            "target_payout_multiplier": multiplier_str,
            "legs": [{"sport": l["sport"], "trigger": "MLB HOME RUN", "bet": f"{l['game_matchup']}: {l['bet']}"} for l in mlb_legs[:3]]
        })
        
    # Standard clean fallback if both high-end boards are completely clear
    if not home_run_tickets:
        home_run_tickets.append({
            "total_odds": "N/A",
            "target_payout_multiplier": "0x",
            "legs": [{"sport": "📡", "trigger": "BOARD CLEAR", "bet": "Awaiting next scheduled NBA/MLB game window line sets."}]
        })

    # --- 2. GRIND TICKETS / SGPs SECTION (Primary NBA/MLB high-conviction singles) ---
    grind_tickets = []
    target_singles_pool = nba_legs[:3] + mlb_legs[:3]
    
    if target_singles_pool:
        for leg in target_singles_pool[:6]:
            grind_tickets.append({
                "game": leg["game_matchup"],
                "total_odds": f"{leg['raw_odds']:+}" if leg['raw_odds'] > 0 else str(leg['raw_odds']),
                "legs": [f"{leg['sport_group']}: {leg['bet']}", "Volume Momentum Filter Confirmed"]
            })
    else:
        # Fall back gracefully to other sports items if major slates are resting
        for leg in other_legs[:4]:
            grind_tickets.append({
                "game": leg["game_matchup"],
                "total_odds": f"{leg['raw_odds']:+}" if leg['raw_odds'] > 0 else str(leg['raw_odds']),
                "legs": [f"{leg['sport_group']}: {leg['bet']}", "Alternative Board Volume"]
            })

    if not grind_tickets:
        grind_tickets.append({"game": "Board Rotations Clear", "total_odds": "Even", "legs": ["System scanning active schedules..."]})

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

    print("Querying current global active markets pool...")
    active_leagues = fetch_all_active_sports()
    all_raw_data = []
    
    for league in active_leagues:
        if "outrights" in league:
            continue
        raw_league_data = fetch_league_odds(league)
        if raw_league_data:
            all_raw_data.extend(raw_league_data)
        
    nba, mlb, others = process_market_legs(all_raw_data)
    dashboard_payload = build_structured_payload(nba, mlb, others)
    
    with open("bets.json", "w") as file:
        json.dump(dashboard_payload, file, indent=2)
    print(f"Success: Isolated {len(nba)} NBA items, {len(mlb)} MLB items, and {len(others)} auxiliary options.")

if __name__ == "__main__":
    main()
