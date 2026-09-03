#!/usr/bin/env python3
"""
Compute today's real astronomical transits — Moon sign, Moon phase, and
retrograde status of Mercury/Venus/Mars — for feeding real facts into the
horoscope prompt instead of letting the LLM invent one.

Fully offline: pyephem is self-contained (no external data file, no network
call), so this is safe to run in an unattended daily job with zero risk of
a third-party API being down at 7am.

Usage:
    python get_transits.py

Prints JSON: {moon_sign, moon_phase_pct, moon_phase_label, retrogrades: [...]}
"""
import json
import ephem

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


def ecliptic_longitude(body_class, date) -> float:
    body = body_class(date)
    eq = ephem.Ecliptic(body)
    return eq.lon * 180.0 / ephem.pi


def longitude_to_sign(lon_deg: float) -> str:
    return SIGNS[int(lon_deg // 30) % 12]


def moon_phase_label(illumination_pct: float, waxing: bool) -> str:
    if illumination_pct < 2:
        return "new moon"
    if illumination_pct > 98:
        return "full moon"
    return "waxing" if waxing else "waning"


# Whole-sign aspects: how many signs apart two signs are determines the
# aspect between them. This is a fixed, internally-consistent astrological
# convention (unlike "lucky colors", which contradict each other across
# sources) — same rule for every sign, every day.
ASPECT_BY_DISTANCE = {
    0: "conjunction", 1: "semisextile", 2: "sextile", 3: "square",
    4: "trine", 5: "quincunx", 6: "opposition",
}
HARMONIOUS_ASPECTS = {"trine", "sextile"}
FRICTION_ASPECTS = {"square", "opposition"}


def sign_distance(a: str, b: str) -> int:
    d = abs(SIGNS.index(a) - SIGNS.index(b))
    return min(d, 12 - d)


def aspect_between(a: str, b: str) -> str:
    return ASPECT_BY_DISTANCE[sign_distance(a, b)]


def compatibility_for_sign(sign: str) -> dict:
    """For a given target account sign (e.g. Sagittarius), bucket all other 11 signs
    by their whole-sign aspect to it, then deterministically pick one 'easier' sign
    (trine preferred over sextile) and one 'harder' sign (opposition preferred over
    square) for use in the daily compatibility beat."""
    buckets = {"trine": [], "sextile": [], "square": [], "opposition": []}
    for s in SIGNS:
        if s == sign:
            continue
        asp = aspect_between(sign, s)
        if asp in buckets:
            buckets[asp].append(s)

    def pick(*bucket_names):
        for name in bucket_names:
            if buckets[name]:
                return sorted(buckets[name], key=SIGNS.index)[0]
        return None

    return {
        "harmonious_pick": pick("trine", "sextile"),
        "friction_pick": pick("opposition", "square"),
        "trine": buckets["trine"],
        "sextile": buckets["sextile"],
        "square": buckets["square"],
        "opposition": buckets["opposition"],
    }


def own_aspect_to_moon(sign: str, moon_sign: str) -> str:
    """The single aspect between a given account's own sign and today's Moon
    sign — this is the personalized line, separate from the general
    harmonious/friction picks above."""
    return aspect_between(sign, moon_sign)


def get_transits(sign: str = None) -> dict:
    now = ephem.now()
    yesterday = ephem.Date(now - 1)

    moon = ephem.Moon(now)
    moon_lon = ecliptic_longitude(ephem.Moon, now)
    moon_sign = longitude_to_sign(moon_lon)

    # Waxing/waning is about position in the ~29.53-day synodic cycle, not
    # day-over-day ecliptic longitude change (the Moon's longitude increases
    # almost every day regardless of phase, so that check was nearly always
    # true — it was misreporting "waxing" through the second half of the
    # cycle). Age since the last new moon < half the cycle == waxing.
    prev_new_moon = ephem.previous_new_moon(now)
    moon_age_days = round(float(now - prev_new_moon), 2)
    waxing = moon_age_days < 14.765

    phase_pct = round(moon.phase, 1)
    phase_label = moon_phase_label(phase_pct, waxing)

    retrogrades = []
    for name, body_class in [("Mercury", ephem.Mercury), ("Venus", ephem.Venus), ("Mars", ephem.Mars)]:
        lon_today = ecliptic_longitude(body_class, now)
        lon_yesterday = ecliptic_longitude(body_class, yesterday)
        d = lon_today - lon_yesterday
        if d > 180:
            d -= 360
        if d < -180:
            d += 360
        if d < 0:
            retrogrades.append(name)

    result = {
        "moon_sign": moon_sign,
        "moon_phase_pct": phase_pct,
        "moon_phase_label": phase_label,
        "moon_age_days": moon_age_days,
        "retrogrades": retrogrades,  # empty list if nothing is retrograde today
    }
    if sign:
        result["compatibility"] = compatibility_for_sign(sign)
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sign", default=None, help="Target account sign for sign-centric compatibility")
    args = parser.parse_args()
    print(json.dumps(get_transits(args.sign), indent=2))


if __name__ == "__main__":
    main()