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


def get_transits() -> dict:
    now = ephem.now()
    yesterday = ephem.Date(now - 1)

    moon = ephem.Moon(now)
    moon_lon = ecliptic_longitude(ephem.Moon, now)
    moon_sign = longitude_to_sign(moon_lon)

    moon_lon_yesterday = ecliptic_longitude(ephem.Moon, yesterday)
    delta = moon_lon - moon_lon_yesterday
    if delta < -180:
        delta += 360
    waxing = delta > 0 and moon.phase < 50 or moon.phase >= 50 and delta > 0

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

    return {
        "moon_sign": moon_sign,
        "moon_phase_pct": phase_pct,
        "moon_phase_label": phase_label,
        "retrogrades": retrogrades,  # empty list if nothing is retrograde today
    }


def main():
    print(json.dumps(get_transits(), indent=2))


if __name__ == "__main__":
    main()