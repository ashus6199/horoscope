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

Prints JSON: {moon_sign, moon_phase_pct, moon_phase_label, retrogrades: [...], event_alert: {...}|null}
"""
import json
import ephem
from pathlib import Path

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


def ecliptic_longitude(body_class, date) -> float:
    body = body_class(date)
    eq = ephem.Ecliptic(body, epoch=date)
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


def compatibility_for_sign(sign: str, moon_sign: str = None, date_num: int = 0) -> dict:
    """For a given target account sign (e.g. Sagittarius) and today's Moon sign (e.g. Gemini),
    compute dynamic daily compatibility that shifts naturally as the Moon moves.
    Target account sign is strictly excluded from being picked."""
    ref_sign = moon_sign if moon_sign else sign
    moon_idx = SIGNS.index(ref_sign) if ref_sign in SIGNS else 0
    sign_idx = SIGNS.index(sign) if sign in SIGNS else 0

    buckets = {"trine": [], "sextile": [], "square": [], "opposition": []}
    for s in SIGNS:
        if s.lower() == sign.lower():
            continue
        asp = aspect_between(ref_sign, s)
        if asp in buckets:
            buckets[asp].append(s)

    def pick(*bucket_names):
        candidates = []
        for name in bucket_names:
            for c in buckets[name]:
                if c.lower() != sign.lower() and c not in candidates:
                    candidates.append(c)
        if not candidates:
            # Fallback: check aspects from target sign
            for name in bucket_names:
                for s in SIGNS:
                    if s.lower() != sign.lower() and aspect_between(sign, s) == name and s not in candidates:
                        candidates.append(s)
        if candidates:
            # Rotate pick dynamically based on moon position and date offset
            idx = (moon_idx + sign_idx + date_num) % len(candidates)
            return candidates[idx]
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


def calculate_retrograde_progress(now, body_class) -> dict | None:
    yesterday = ephem.Date(now - 1)
    lon_today = ecliptic_longitude(body_class, now)
    lon_yesterday = ecliptic_longitude(body_class, yesterday)
    d = lon_today - lon_yesterday
    if d > 180: d -= 360
    if d < -180: d += 360
    if d >= 0:
        return None

    start_day = 0
    t = float(now)
    for i in range(1, 90):
        t_curr = ephem.Date(t - i)
        t_prev = ephem.Date(t - i - 1)
        delta = ecliptic_longitude(body_class, t_curr) - ecliptic_longitude(body_class, t_prev)
        if delta > 180: delta -= 360
        if delta < -180: delta += 360
        if delta >= 0:
            start_day = i
            break

    end_day = 0
    for i in range(1, 90):
        t_curr = ephem.Date(t + i)
        t_prev = ephem.Date(t + i - 1)
        delta = ecliptic_longitude(body_class, t_curr) - ecliptic_longitude(body_class, t_prev)
        if delta > 180: delta -= 360
        if delta < -180: delta += 360
        if delta >= 0:
            end_day = i
            break

    total_days = start_day + end_day
    day_num = start_day + 1
    return {
        "day_num": day_num,
        "total_days": total_days,
        "label": f"Day {day_num} of {total_days}"
    }


def get_transits(sign: str = None, date_str: str = None) -> dict:
    if date_str:
        from datetime import datetime
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        now = ephem.Date(dt)
    else:
        now = ephem.now()

    yesterday = ephem.Date(now - 1)

    moon = ephem.Moon(now)
    moon_lon = ecliptic_longitude(ephem.Moon, now)
    moon_sign = longitude_to_sign(moon_lon)

    prev_new_moon = ephem.previous_new_moon(now)
    moon_age_days = round(float(now - prev_new_moon), 2)
    waxing = moon_age_days < 14.765

    phase_pct = round(moon.phase, 1)
    phase_label = moon_phase_label(phase_pct, waxing)

    retrogrades = []
    sky_weather_details = []
    body_map = {"Mercury": ephem.Mercury, "Venus": ephem.Venus, "Mars": ephem.Mars}
    for name, body_class in body_map.items():
        lon_today = ecliptic_longitude(body_class, now)
        lon_yesterday = ecliptic_longitude(body_class, yesterday)
        d = lon_today - lon_yesterday
        if d > 180:
            d -= 360
        if d < -180:
            d += 360
        if d < 0:
            retrogrades.append(name)
            prog = calculate_retrograde_progress(now, body_class)
            if prog:
                sky_weather_details.append(f"{name} Retrograde ({prog['label']})")
            else:
                sky_weather_details.append(f"{name} Retrograde")

    result = {
        "moon_sign": moon_sign,
        "moon_phase_pct": phase_pct,
        "moon_phase_label": phase_label,
        "moon_age_days": moon_age_days,
        "retrogrades": retrogrades,  # empty list if nothing is retrograde today
        "sky_weather": {
            "active_retrogrades": retrogrades,
            "details": sky_weather_details,
            "summary": ", ".join(sky_weather_details) if sky_weather_details else f"Moon in {moon_sign} ({phase_label})"
        },
        "event_alert": resolve_event_alert(now, moon, phase_pct),
    }
    if sign:
        date_num = int(float(now))
        result["compatibility"] = compatibility_for_sign(sign, moon_sign=moon_sign, date_num=date_num)
    return result


# ─── 3-Tier Astronomical Event Detection ─────────────────────────
# Tier 3 (rare, ~6-10 days/year): Eclipses, Supermoons, Retrograde Station Days
# Tier 2 (monthly, ~4-6 days/month): Full/New Moon countdowns within 3 days
# Tier 1 (daily baseline): no event_alert, just the standard transit data
# Waterfall precedence: Tier 3 > Tier 2 > None (Tier 1 is implicit)

# Supermoon threshold: Full Moon at perigee ≤ 361,867 km (90th percentile
# of lunar perigee distances). This is one of the more conservative,
# commonly-cited thresholds — chosen for consistency over competing
# definitions. Documented here so the rule is auditable.
SUPERMOON_MAX_KM = 361867.0
AU_TO_KM = 149597870.7


def _load_eclipses() -> list:
    """Read verified NASA eclipse dates from data/eclipses.json.
    Returns empty list if file is missing or malformed — the pipeline
    simply won't flag eclipses rather than crashing."""
    eclipses_path = Path(__file__).resolve().parent.parent / "data" / "eclipses.json"
    if not eclipses_path.exists():
        return []
    try:
        with open(eclipses_path, "r") as f:
            return json.load(f)
    except Exception:
        return []


def _check_retrograde_stations(now) -> dict | None:
    """Detect if any personal planet (Mercury, Venus, Mars) is stationing
    today — i.e. its apparent ecliptic motion flipped direction between
    yesterday→today vs. the-day-before→yesterday.
    Returns a Tier 3 event dict on the exact transition day, else None."""
    yesterday = ephem.Date(now - 1)
    day_before = ephem.Date(now - 2)
    for name, body_class in [("Mercury", ephem.Mercury), ("Venus", ephem.Venus), ("Mars", ephem.Mars)]:
        d_today = ecliptic_longitude(body_class, now) - ecliptic_longitude(body_class, yesterday)
        d_prev  = ecliptic_longitude(body_class, yesterday) - ecliptic_longitude(body_class, day_before)
        # Wrap-around correction for ecliptic longitude crossing 0°/360°
        for d in [d_today, d_prev]:
            pass  # handled inline below
        if d_today > 180:  d_today -= 360
        if d_today < -180: d_today += 360
        if d_prev > 180:   d_prev -= 360
        if d_prev < -180:  d_prev += 360

        if d_prev >= 0 and d_today < 0:
            return {
                "tier": 3,
                "type": "STATION_RETROGRADE",
                "planet": name,
                "label": f"{name.upper()} STATIONS RETROGRADE",
                "badgeAccent": "#F59E0B",
            }
        if d_prev < 0 and d_today >= 0:
            return {
                "tier": 3,
                "type": "STATION_DIRECT",
                "planet": name,
                "label": f"{name.upper()} STATIONS DIRECT",
                "badgeAccent": "#10B981",
            }
    return None


def resolve_event_alert(now, moon, phase_pct) -> dict | None:
    """Waterfall resolver: returns the highest-priority active event, or None."""

    today_str = ephem.Date(now).datetime().strftime("%Y-%m-%d")

    # ── Tier 3: Eclipse (verified lookup) ──
    for ecl in _load_eclipses():
        if ecl.get("date") == today_str:
            is_lunar = "LUNAR" in ecl.get("type", "")
            return {
                "tier": 3,
                "type": ecl["type"],
                "sign": ecl.get("sign", ""),
                "label": ecl.get("label", "ECLIPSE TODAY"),
                "badgeAccent": "#EF4444" if is_lunar else "#F59E0B",
            }

    # ── Tier 3: Supermoon (full moon + perigee) ──
    moon_dist_km = moon.earth_distance * AU_TO_KM
    if phase_pct >= 95.0 and moon_dist_km <= SUPERMOON_MAX_KM:
        return {
            "tier": 3,
            "type": "SUPERMOON",
            "label": "SUPERMOON TONIGHT",
            "badgeAccent": "#38BDF8",
        }

    # ── Tier 3: Retrograde station day ──
    station = _check_retrograde_stations(now)
    if station:
        return station

    # ── Tier 2: Full Moon countdown (0-3 days) ──
    next_full = ephem.next_full_moon(now)
    days_to_full = round(float(next_full - now), 1)
    if 0 <= days_to_full <= 3.0:
        if days_to_full < 0.5:
            label = "FULL MOON TODAY"
        elif days_to_full < 1.5:
            label = "FULL MOON TOMORROW"
        else:
            label = f"FULL MOON IN {int(round(days_to_full))} DAYS"
        return {
            "tier": 2,
            "type": "FULL_MOON_COUNTDOWN",
            "label": label,
            "daysRemaining": days_to_full,
            "badgeAccent": "#E8D9C0",
        }

    # ── Tier 2: New Moon countdown (0-3 days) ──
    next_new = ephem.next_new_moon(now)
    days_to_new = round(float(next_new - now), 1)
    if 0 <= days_to_new <= 3.0:
        if days_to_new < 0.5:
            label = "NEW MOON TODAY"
        elif days_to_new < 1.5:
            label = "NEW MOON TOMORROW"
        else:
            label = f"NEW MOON IN {int(round(days_to_new))} DAYS"
        return {
            "tier": 2,
            "type": "NEW_MOON_COUNTDOWN",
            "label": label,
            "daysRemaining": days_to_new,
            "badgeAccent": "#C4C9D4",
        }

    # ── Tier 2: Ongoing Retrograde Alert (Mercury, Venus, Mars) ──
    yesterday = ephem.Date(now - 1)
    for name, body_class in [("Mercury", ephem.Mercury), ("Venus", ephem.Venus), ("Mars", ephem.Mars)]:
        d = ecliptic_longitude(body_class, now) - ecliptic_longitude(body_class, yesterday)
        if d > 180: d -= 360
        if d < -180: d += 360
        if d < 0:
            return {
                "tier": 2,
                "type": "RETROGRADE_ACTIVE",
                "planet": name,
                "label": f"{name.upper()} RETROGRADE",
                "badgeAccent": "#F59E0B",
            }

    # ── Tier 1: No special event today ──
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sign", default=None, help="Target account sign for sign-centric compatibility")
    parser.add_argument("--date", default=None, help="Override date (YYYY-MM-DD)")
    args = parser.parse_args()
    print(json.dumps(get_transits(args.sign, args.date), indent=2))


if __name__ == "__main__":
    main()