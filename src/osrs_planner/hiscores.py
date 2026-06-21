import httpx
from osrs_planner.models import Account, AccountMode, Skill


class PlayerNotFoundError(Exception):
    pass


class HiscoresError(Exception):
    pass


def fetch_stats(rsn: str, mode: AccountMode) -> Account:
    """Fetch a player's stats from the OSRS hiscores."""
    if mode == AccountMode.normal:
        suffix = ""
    elif mode == AccountMode.ultimate_ironman:
        suffix = "_ultimate"          # OSRS board is "_ultimate", NOT "_ultimate_ironman"
    else:
        suffix = f"_{mode.name}"
    try:
        response = httpx.get(f"https://secure.runescape.com/m=hiscore_oldschool{suffix}/index_lite.json?player={rsn}")
    except httpx.HTTPError:
        raise HiscoresError("Cannot reach Hiscores page")
    
    if response.status_code == 404:
        raise PlayerNotFoundError("Player not found")
    data = response.json()
    skills = {}
    
    for skill in data["skills"]:
        if skill["name"] == "Overall":
            continue
        skills[skill["name"].lower()] = Skill(name=skill["name"], level=skill["level"], xp=skill["xp"])
    return Account(rsn=data["name"], mode=mode, skills=skills)
