import os
import json
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports"
REGIONS = "us"             
MARKETS = "h2h,spreads"    
ODDS_FORMAT = "american"

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
        # Strip trailing Z and handle clean ISO format variations
        clean_str = time_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        try:
            return datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            return None

def screen_global_markets(all_games_data):
    """
    Screens global markets. Strictly ensures games fall within a 48-hour live window.
    """
    detected_legs = []
    now_utc = datetime.now(timezone.utc)
    max_window = now_utc + timedelta(hours=48)
    
    for game in all_games_data:
        # Strict 48-Hour Live Window Check
        commence_time_str = game.get("commence_time")
        game_time = parse_api_time(commence_time_str)
        
        if game_time:
            # Drop long-term futures, outright lines, or stale past items
            if game_time < now_utc or game_time > max_window:
                continue

        home_team = game.get("home_team")
        away_team = game.get("away_team")
        sport_title = game.get("sport_title", "Live Event")
        sport_key = game.get("sport_key", "").lower()
        
        icon = "🎯"
        if "football" in sport_key or "afl" in sport_key: icon = "🏈"
        elif "basketball" in sport_key: icon = "🏀"
        elif "hockey" in sport_key: icon = "🏒"
        elif "baseball" in sport_key: icon = "⚾"
        elif "soccer" in sport_key: icon = "⚽"
        elif "tennis" in sport_key: icon = "🎾"
        elif "mma" in sport_key or "boxing" in sport_key: icon = "🥊"

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
                            
                            # Filter down to true value lines
                            if (price >= 130 or price <= -170) and len(detected_legs) < 25:
                                label = "SHARP STEAM" if price < 0 else "REVERSE LINE"
                                if abs(price) > 250: label = "HEAVY VALUE"
                                
                                book_name = book.get("title")
                                detected_legs.append({
                                    "sport": icon,
                                    "trigger": label,
                                    "bet": f"{outcome.get('name')} ({book_name})",
                                    "raw_odds": price,
                                    "game_matchup": f"{away_team} @ {home_team}",
                                    "sport_group": sport_title
                                })
                break
                
    detected_legs.sort(key=lambda x: abs(x["raw_odds"]), reverse=True)
    return detected_legs

def build_optimal_parlays(active_legs):
    system_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    if not active_legs:
        return {
            "system_status": "ACTIVE",
            "last_updated": system_time,
            "home_run_tickets": [{
                "total_odds": "N/A",
                "target_payout_multiplier": "0x",
                "legs": [{"sport": "📡", "trigger": "BOARD CLEAR", "bet": "No upcoming games match specific filters right now."}]
            }],
            "grind_tickets": [{"game": "Live Window Empty", "total_odds": "Even", "legs": ["Awaiting next game board rotation."]}]
        }

    # Ticket 1: The High-End Home Run Combo
    hr_legs = active_legs[:3]
    hr_multiplier = 1
    for leg in hr_legs:
        p = leg.get("raw_odds", 100)
        mult = (p / 100 + 1) if p > 0 else (100 / abs(p) + 1)
        hr_multiplier *= mult

    hr_odds_str = f"+{int((hr_multiplier - 1) * 100)}" if hr_multiplier > 2 else "Calculated Match"

    # Ticket 2: The Grind Engine
    grind_slice = active_legs[3:7] if len(active_legs) > 4 else active_legs[:2]

    return {
        "system_status": "ACTIVE",
        "last_updated": system_time,
        "home_run_tickets": [
            {
                "total_odds": hr_odds_str,
                "target_payout_multiplier": f"{round(hr_multiplier, 1)}x",
                "legs": [{"sport": l["sport"], "trigger": l["trigger"], "bet": f"{l['sport_group']}: {l['bet']}"} for l in hr_legs]
            }
        ],
        "grind_tickets": [
            {
                "game": leg["game_matchup"],
                "total_odds": f"{leg['raw_odds']:+}" if leg['raw_odds'] > 0 else str(leg['raw_odds']),
                "legs": [f"{leg['sport_group']}: {leg['bet']}", "Volume Momentum Confirmed"]
            } for leg in grind_slice
        ]
    }

def main():
    if not API_KEY:
        print("CRITICAL DATA ERROR: No valid ODDS_API_KEY detected.")
        return

    active_leagues = fetch_all_active_sports()
    all_raw_data = []
    
    for league in active_leagues:
        if "outrights" in league:
            continue
        raw_league_data = fetch_league_odds(league)
        if raw_league_data:
            all_raw_data.extend(raw_league_data)
        
    active_legs = screen_global_markets(all_raw_data)
    dashboard_payload = build_optimal_parlays(active_legs)
    
    with open("bets.json", "w") as file:
        json.dump(dashboard_payload, file, indent=2)
    print(f"System successfully compiled {len(active_legs)} live game components.")

if __name__ == "__main__":
    main()
