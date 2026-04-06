#!/usr/bin/env python3
"""Belfast Daily Weather Email — Enhanced Edition v3 (with family schedule + calendar)"""

import os, json, random, smtplib, datetime, urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

RECIPIENTS = ["aarongi13z@gmail.com", "raffertylaura@rocketmail.com", "spmrafferty@yahoo.com"]
SCHEDULE_RECIPIENTS = ["aarongi13z@gmail.com", "raffertylaura@rocketmail.com"]

GMAIL_USER         = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
GCAL_ICS_URL       = os.environ.get("GCAL_ICS_URL", "")

WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=54.5973&longitude=-5.9301"
    "&hourly=temperature_2m,apparent_temperature,precipitation_probability,"
    "precipitation,weathercode,windspeed_10m,uv_index"
    "&daily=weathercode,temperature_2m_max,temperature_2m_min,"
    "apparent_temperature_max,apparent_temperature_min,"
    "precipitation_sum,precipitation_probability_max,"
    "sunrise,sunset,uv_index_max,windspeed_10m_max"
    "&timezone=Europe%2FLondon&forecast_days=7"
)

ROMY_DAILY = [
    ("07:00", "Wake + Feed", {}),
    ("08:45", "Tummy time / independent play", {}),
    ("10:00", "Nap 1 (~1h15, sleep training upstairs)", {
        "wednesday": "Nap 1 finishes at 9:45am",
        "sunday":    "Nap 1 finishes at 9:45am — Aaron leads so Laura can run",
    }),
    ("13:00", "Nap 2 (~1 hour)", {}),
    ("16:00", "Catnap / bridge nap", {
        "tuesday":  "Aaron leads catnap so Laura can run — check if Aaron is WFH",
        "thursday": "Aaron leads catnap so Laura can run — check if Aaron is WFH",
    }),
    ("18:30", "Bed routine: bath / bottle / cuddle", {}),
]

LAURA_EXERCISE = {
    "monday":    None,
    "tuesday":   ("16:30\u201317:15", "During Romy's catnap, after 4pm feed"),
    "wednesday": ("post Nap 1",  "Strength class"),
    "thursday":  ("16:30\u201317:15", "During Romy's catnap, after 4pm feed"),
    "friday":    None,
    "saturday":  ("08:45\u201309:30", "Aaron leads Romy until sleep training more established"),
    "sunday":    None,
}

AARON_NOTES = {
    "monday":    "Gym 12\u20132pm, run with dogs, 4pm activity",
    "tuesday":   "Lead Romy's 4pm catnap so Laura can run",
    "wednesday": None,
    "thursday":  "Lead Romy's 4pm catnap so Laura can run",
    "friday":    None,
    "saturday":  "Lead Romy 8:45\u20139:30am while Laura runs",
    "sunday":    "Lead Romy's Nap 1 (starting ~10am) so Laura can run",
}

CONFLICT_WINDOWS = {
    "monday": [
        (12,  0, 14,  0, "Aaron's gym time",                              "Aaron"),
        (16,  0, 17,  0, "Aaron's 4pm activity",                          "Aaron"),
    ],
    "tuesday": [
        (10,  0, 11, 15, "Romy Nap 1",                                    "both"),
        (13,  0, 14,  0, "Romy Nap 2",                                    "both"),
        (16,  0, 16, 30, "Romy catnap \u2014 Aaron covering so Laura can run", "Aaron"),
        (16, 30, 17, 15, "Laura's run",                                    "Laura"),
    ],
    "wednesday": [
        ( 9, 45, 11,  0, "Laura's strength class (post Nap 1)",           "Laura"),
        (10,  0, 11, 15, "Romy Nap 1",                                    "both"),
        (13,  0, 14,  0, "Romy Nap 2",                                    "both"),
        (16,  0, 16, 30, "Romy catnap",                                   "both"),
    ],
    "thursday": [
        (10,  0, 11, 15, "Romy Nap 1",                                    "both"),
        (13,  0, 14,  0, "Romy Nap 2",                                    "both"),
        (16,  0, 16, 30, "Romy catnap \u2014 Aaron covering so Laura can run", "Aaron"),
        (16, 30, 17, 15, "Laura's run",                                    "Laura"),
    ],
    "friday": [
        (10,  0, 11, 15, "Romy Nap 1",                                    "both"),
        (13,  0, 14,  0, "Romy Nap 2",                                    "both"),
        (16,  0, 16, 30, "Romy catnap",                                   "both"),
    ],
    "saturday": [
        ( 8, 45,  9, 30, "Aaron leading Romy (Laura runs)",               "Aaron"),
        (10,  0, 11, 15, "Romy Nap 1",                                    "both"),
        (13,  0, 14,  0, "Romy Nap 2",                                    "both"),
        (16,  0, 16, 30, "Romy catnap",                                   "both"),
    ],
    "sunday": [
        (10,  0, 11, 15, "Romy Nap 1 \u2014 Aaron leading so Laura can run", "Aaron"),
        (13,  0, 14,  0, "Romy Nap 2",                                    "both"),
        (16,  0, 16, 30, "Romy catnap",                                   "both"),
    ],
}

WMO_CODES = {
    0:  ("Clear sky","☀️"), 1:  ("Mainly clear","🌤️"), 2:  ("Partly cloudy","⛅"), 3:  ("Overcast","☁️"),
    45: ("Fog","🌫️"), 48: ("Icy fog","🌫️"), 51: ("Light drizzle","🌦️"), 53: ("Moderate drizzle","🌦️"),
    55: ("Dense drizzle","🌧️"), 61: ("Light rain","🌧️"), 63: ("Moderate rain","🌧️"), 65: ("Heavy rain","🌧️"),
    71: ("Light snow","❄️"), 73: ("Moderate snow","❄️"), 75: ("Heavy snow","❄️"), 77: ("Snow grains","🌨️"),
    80: ("Light showers","🌦️"), 81: ("Moderate showers","🌧️"), 82: ("Violent showers","⛈️"),
    85: ("Light snow showers","🌨️"), 86: ("Heavy snow showers","🌨️"), 95: ("Thunderstorm","⛈️"),
    96: ("Thunderstorm with hail","⛈️"), 99: ("Thunderstorm, heavy hail","⛈️"),
}

FALLBACK_QUOTES = [
    ("It is not death that a man should fear, but he should fear never beginning to live.", "Marcus Aurelius"),
    ("The impediment to action advances action. What stands in the way becomes the way.", "Marcus Aurelius"),
    ("He who knows others is wise; he who knows himself is enlightened.", "Lao Tzu"),
    ("A gem cannot be polished without friction, nor a man perfected without trials.", "Seneca"),
    ("The happiness of your life depends upon the quality of your thoughts.", "Marcus Aurelius"),
    ("Waste no more time arguing about what a good man should be. Be one.", "Marcus Aurelius"),
    ("We suffer more in imagination than in reality.", "Seneca"),
    ("The first and greatest victory is to conquer yourself.", "Plato"),
    ("He who has a why to live can bear almost any how.", "Nietzsche"),
]

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "BelfastWeatherBot/3.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

def fetch_weather():
    for attempt in range(2):
        try:
            return fetch_json(WEATHER_URL)
        except Exception as e:
            if attempt == 0:
                import time; print(f"Retry... ({e})"); time.sleep(3)
            else:
                raise RuntimeError(f"Weather fetch failed: {e}")

def fetch_wisdom_quote():
    try:
        d = fetch_json("https://zenquotes.io/api/random")
        return d[0]["q"], d[0]["a"]
    except Exception as e:
        print(f"Quote API failed ({e}), using fallback.")
    return random.choice(FALLBACK_QUOTES)

def wmo_info(code):  return WMO_CODES.get(code, (f"Code {code}", "🌡️"))
def wmo_desc(code):  return wmo_info(code)[0]
def wmo_emoji(code): return wmo_info(code)[1]

def temp_color(t):
    if t < 5:  return "#cce5ff"
    if t < 12: return "#e8f4fd"
    if t < 18: return "#ffffff"
    if t < 24: return "#fff3cd"
    return "#f8d7da"

def uv_label(uv):
    if uv <= 2:  return ("Low",       "#d4edda")
    if uv <= 5:  return ("Moderate",  "#fff3cd")
    if uv <= 7:  return ("High",      "#ffd699")
    if uv <= 10: return ("Very High", "#f8d7da")
    return ("Extreme", "#e8b4f8")

def rain_bg(pp):
    if pp > 45:  return "#f8d7da"
    if pp >= 25: return "#fff3cd"
    return "#d4edda"

def fmt_hour(h):   return f"{h:02d}:00"
def fmt_time(iso): return iso[11:16] if len(iso) > 10 else iso
def fmt_block(s, e): return fmt_hour(s) if s == e else f"{fmt_hour(s)} \u2013 {fmt_hour(e + 1)}"

def find_blocks(hours_list):
    if not hours_list: return []
    blocks, start, prev = [], hours_list[0], hours_list[0]
    for h in hours_list[1:]:
        if h == prev + 1: prev = h
        else: blocks.append((start, prev)); start = prev = h
    blocks.append((start, prev))
    return blocks

def conditions_summary(wmo_code, precip_sum, max_pp):
    desc = wmo_desc(wmo_code)
    if max_pp < 20 and precip_sum == 0: return f"{desc} \u2014 Dry day expected"
    if max_pp < 40: return f"{desc} \u2014 Some chance of rain"
    if max_pp < 70: return f"{desc} \u2014 Rainy spells likely"
    return f"{desc} \u2014 Wet day, bring an umbrella"

def generate_headline(d):
    avg = (d["min_temp"] + d["max_temp"]) / 2
    if avg < 5:    temp_desc = "cold"
    elif avg < 10: temp_desc = "chilly"
    elif avg < 15: temp_desc = "mild"
    elif avg < 20: temp_desc = "warm"
    else:          temp_desc = "hot"
    pp = d["peak_prob"]
    if pp < 20 and d["precip_sum"] == 0: rain_desc = "dry throughout"
    elif pp < 40: rain_desc = "mostly dry with slight chance of showers"
    elif pp < 60: rain_desc = f"rain likely around {fmt_hour(d['peak_hour'])}"
    elif pp < 80: rain_desc = f"significant rain, peaking around {fmt_hour(d['peak_hour'])}"
    else:         rain_desc = "heavy rain through much of the day"
    wind_desc = ", very windy" if d["wind_max"] > 50 else ", quite breezy" if d["wind_max"] > 35 else ""
    walks = d["walk_blocks"]
    walk_desc = f" Best walk: {fmt_block(walks[0][0], walks[0][1])}." if walks else " No clear dry windows for walks."
    return f"A {temp_desc} day ({d['min_temp']:.0f}\u2013{d['max_temp']:.0f}\u00b0C), {rain_desc}{wind_desc}.{walk_desc}"

def analyze_day(data, date_str):
    ht    = data["hourly"]["time"]
    idx   = [i for i, t in enumerate(ht) if t.startswith(date_str)]
    times = [ht[i]                                          for i in idx]
    temps = [data["hourly"]["temperature_2m"][i]            for i in idx]
    feels = [data["hourly"]["apparent_temperature"][i]      for i in idx]
    pps   = [data["hourly"]["precipitation_probability"][i] for i in idx]
    prs   = [data["hourly"]["precipitation"][i]             for i in idx]
    winds = [data["hourly"]["windspeed_10m"][i]             for i in idx]
    codes = [data["hourly"]["weathercode"][i]               for i in idx]
    uvs   = [data["hourly"]["uv_index"][i]                  for i in idx]
    display_idx = [i for i, t in enumerate(times) if 5 <= int(t[11:13]) <= 22]
    good_h = sorted(int(times[i][11:13]) for i in range(len(times))
                    if pps[i] < 30 and prs[i] == 0.0 and 6 <= int(times[i][11:13]) <= 21)
    walk_blocks = find_blocks(good_h)
    walk_blocks.sort(key=lambda w: (-(w[1]-w[0]+1), abs((w[0]+w[1])//2-12)))
    bad_blocks = find_blocks(sorted(int(times[i][11:13]) for i in range(len(times)) if pps[i] > 45))
    dd = data["daily"]["time"]
    d  = dd.index(date_str)
    peak_prob = max(pps)
    peak_hour = int(times[pps.index(peak_prob)][11:13])
    result = {
        "date": date_str,
        "max_temp":        data["daily"]["temperature_2m_max"][d],
        "min_temp":        data["daily"]["temperature_2m_min"][d],
        "feels_max":       data["daily"]["apparent_temperature_max"][d],
        "feels_min":       data["daily"]["apparent_temperature_min"][d],
        "wmo":             data["daily"]["weathercode"][d],
        "conditions":      conditions_summary(data["daily"]["weathercode"][d],
                               data["daily"]["precipitation_sum"][d],
                               data["daily"]["precipitation_probability_max"][d]),
        "precip_sum":      data["daily"]["precipitation_sum"][d],
        "max_precip_prob": data["daily"]["precipitation_probability_max"][d],
        "peak_prob":       peak_prob, "peak_hour": peak_hour,
        "wind_min":        min(winds), "wind_max": max(winds),
        "wind_max_daily":  data["daily"]["windspeed_10m_max"][d],
        "sunrise":         fmt_time(data["daily"]["sunrise"][d]),
        "sunset":          fmt_time(data["daily"]["sunset"][d]),
        "uv_max":          data["daily"]["uv_index_max"][d],
        "times": times, "temps": temps, "feels": feels,
        "pps": pps, "prs": prs, "winds": winds, "codes": codes, "uvs": uvs,
        "display_idx": display_idx, "walk_blocks": walk_blocks[:3], "bad_blocks": bad_blocks,
    }
    result["headline"] = generate_headline(result)
    return result

def find_worst_day(data, dates):
    worst_score, worst = -1, None
    for date_str in dates[1:]:
        dd = data["daily"]["time"]
        if date_str not in dd: continue
        d  = dd.index(date_str)
        pp = data["daily"]["precipitation_probability_max"][d]
        ps = data["daily"]["precipitation_sum"][d]
        score = pp * 0.7 + min(ps * 10, 30)
        if score > worst_score:
            worst_score = score
            worst = {"date": date_str, "pp": pp, "ps": ps, "wmo": data["daily"]["weathercode"][d]}
    return worst if worst_score > 50 else None

def fetch_calendar_events(today_str):
    if not GCAL_ICS_URL:
        return []
    try:
        import pytz
        from icalendar import Calendar
        tz_london = pytz.timezone("Europe/London")
        today = datetime.date.fromisoformat(today_str)
        req = urllib.request.Request(GCAL_ICS_URL, headers={"User-Agent": "BelfastWeatherBot/3.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
        cal = Calendar.from_ical(raw)
        events = []
        for component in cal.walk():
            if component.name != "VEVENT": continue
            dtstart = component.get("DTSTART")
            dtend   = component.get("DTEND")
            summary = str(component.get("SUMMARY", "Untitled"))
            if dtstart is None: continue
            sv = dtstart.dt
            ev = dtend.dt if dtend else sv
            if isinstance(sv, datetime.date) and not isinstance(sv, datetime.datetime):
                if sv == today: events.append((summary, None, None))
                continue
            if sv.tzinfo is None: sv = pytz.utc.localize(sv)
            if ev.tzinfo is None: ev = pytz.utc.localize(ev)
            sv = sv.astimezone(tz_london)
            ev = ev.astimezone(tz_london)
            if sv.date() == today or ev.date() == today:
                events.append((summary, sv, ev))
        events.sort(key=lambda x: (x[1] is None, x[1]))
        return events
    except Exception as e:
        print(f"Calendar fetch failed ({e})")
        return []

def detect_conflicts(events, day_of_week):
    windows = CONFLICT_WINDOWS.get(day_of_week, [])
    conflicts = []
    for (title, sv, ev) in events:
        if sv is None or ev is None: continue
        es = sv.hour * 60 + sv.minute
        ee = ev.hour * 60 + ev.minute
        for (wsh, wsm, weh, wem, wdesc, person) in windows:
            ws = wsh * 60 + wsm; we = weh * 60 + wem
            if es < we and ee > ws:
                conflicts.append((title, sv, wdesc, person)); break
    return conflicts

def build_schedule_section(day_of_week):
    rows = []
    for (time_str, label, notes_by_day) in ROMY_DAILY:
        note = notes_by_day.get(day_of_week, "")
        text = label + (f" <span style='color:#6c757d;font-size:13px;'>({note})</span>" if note else "")
        rows.append(f"<tr><td style='padding:6px 10px;width:70px;font-weight:bold;color:#495057;"
                    f"white-space:nowrap;'>{time_str}</td><td style='padding:6px 10px;'>{text}</td></tr>")
    laura = LAURA_EXERCISE.get(day_of_week)
    aaron = AARON_NOTES.get(day_of_week)
    aside = ""
    if laura or aaron:
        parts = []
        if laura: parts.append(f"<b>Laura:</b> {laura[0]} &mdash; {laura[1]}")
        if aaron: parts.append(f"<b>Aaron:</b> {aaron}")
        aside = ("<div style='margin:12px 0 0;padding:10px 14px;background:#e9f5ff;"
                 "border-left:4px solid #3a9fd1;border-radius:4px;font-size:14px;'>"
                 + " &nbsp;|&nbsp; ".join(parts) + "</div>")
    return ("<div style='margin:24px 0;'><h2 style='font-family:sans-serif;font-size:18px;"
            "color:#2c3e50;margin:0 0 10px;'>&#128197; Today's Schedule</h2>"
            "<table style='border-collapse:collapse;width:100%;background:#f8f9fa;"
            "border-radius:8px;overflow:hidden;font-family:sans-serif;font-size:14px;'>"
            "<tbody>" + "".join(rows) + "</tbody></table>" + aside + "</div>")

def build_conflicts_section(events, conflicts):
    sections = []
    if events:
        ev_rows = []
        for (title, sv, ev) in events:
            ts = "All day" if sv is None else f"{sv.strftime('%H:%M')}\u2013{ev.strftime('%H:%M')}"
            ev_rows.append(f"<tr><td style='padding:5px 10px;width:100px;font-weight:bold;"
                           f"white-space:nowrap;color:#495057;'>{ts}</td>"
                           f"<td style='padding:5px 10px;'>{title}</td></tr>")
        sections.append("<b style='font-size:14px;color:#2c3e50;'>&#128197; Google Calendar \u2014 Today</b>"
                        "<table style='border-collapse:collapse;width:100%;margin-top:6px;"
                        "font-family:sans-serif;font-size:14px;background:#f0f7ff;border-radius:6px;'>"
                        "<tbody>" + "".join(ev_rows) + "</tbody></table>")
    else:
        sections.append("<p style='font-size:14px;color:#6c757d;margin:0;'>"
                        "&#128197; No events on Google Calendar today.</p>")
    if conflicts:
        warn_rows = []
        for (title, sv, wdesc, person) in conflicts:
            ts = sv.strftime("%H:%M") if sv else "?"
            warn_rows.append(f"<tr style='background:#fff3cd;'>"
                             f"<td style='padding:6px 10px;width:80px;font-weight:bold;"
                             f"white-space:nowrap;color:#856404;'>{ts}</td>"
                             f"<td style='padding:6px 10px;color:#856404;'>"
                             f"<b>{title}</b> clashes with <em>{wdesc}</em> ({person})</td></tr>")
        sections.append("<b style='font-size:14px;color:#856404;margin-top:14px;display:block;'>"
                        "&#9888;&#65039; Calendar Conflicts</b>"
                        "<table style='border-collapse:collapse;width:100%;margin-top:6px;"
                        "font-family:sans-serif;font-size:14px;border-radius:6px;overflow:hidden;'>"
                        "<tbody>" + "".join(warn_rows) + "</tbody></table>")
    return ("<div style='margin:24px 0;padding:14px;background:#ffffff;"
            "border:1px solid #dee2e6;border-radius:8px;'>"
            + "<div style='margin-bottom:14px;'>".join(sections) + "</div></div>")

def build_day_section(d):
    uv_txt, uv_bg = uv_label(d["uv_max"])
    rows = []
    for i in d["display_idx"]:
        h = int(d["times"][i][11:13])
        bg = rain_bg(d["pps"][i])
        rows.append(
            f"<tr style='background:{bg};'>"
            f"<td style='padding:5px 8px;font-weight:bold;white-space:nowrap;'>{fmt_hour(h)}</td>"
            f"<td style='padding:5px 8px;'>{wmo_emoji(d['codes'][i])} {wmo_desc(d['codes'][i])}</td>"
            f"<td style='padding:5px 8px;text-align:center;background:{temp_color(d['temps'][i])};'>{d['temps'][i]:.0f}\u00b0C</td>"
            f"<td style='padding:5px 8px;text-align:center;color:#6c757d;'>{d['feels'][i]:.0f}\u00b0C</td>"
            f"<td style='padding:5px 8px;text-align:center;'>{d['pps'][i]:.0f}%</td>"
            f"<td style='padding:5px 8px;text-align:center;'>{d['winds'][i]:.0f} km/h</td>"
            f"</tr>"
        )
    walk_str = ", ".join(fmt_block(s,e) for s,e in d["walk_blocks"]) or "No clear windows"
    bad_str  = ", ".join(fmt_block(s,e) for s,e in d["bad_blocks"])  or "None"
    return (f"<div style='margin:0 0 28px;'>"
            f"<div style='padding:14px 16px;background:#2c3e50;border-radius:8px 8px 0 0;'>"
            f"<span style='font-size:28px;'>{wmo_emoji(d['wmo'])}</span>"
            f"<span style='color:#fff;font-size:16px;margin-left:10px;vertical-align:middle;'><b>{d['conditions']}</b></span></div>"
            f"<div style='padding:12px 16px;background:#f8f9fa;border:1px solid #dee2e6;'>"
            f"<table style='width:100%;border-collapse:collapse;font-family:sans-serif;font-size:14px;'><tbody>"
            f"<tr><td style='padding:4px 8px;width:50%;'>&#127777;&#65039; <b>{d['min_temp']:.0f}\u00b0C \u2013 {d['max_temp']:.0f}\u00b0C</b>"
            f" &nbsp;<span style='color:#6c757d;font-size:13px;'>feels {d['feels_min']:.0f}\u2013{d['feels_max']:.0f}\u00b0C</span></td>"
            f"<td style='padding:4px 8px;'>&#127774; Sunrise {d['sunrise']} &nbsp; &#127769; Sunset {d['sunset']}</td></tr>"
            f"<tr><td style='padding:4px 8px;'><span style='background:{uv_bg};padding:2px 8px;border-radius:4px;font-size:13px;'>UV {d['uv_max']:.0f} \u2014 {uv_txt}</span></td>"
            f"<td style='padding:4px 8px;'>&#128168; Wind max {d['wind_max_daily']:.0f} km/h</td></tr>"
            f"<tr><td style='padding:4px 8px;' colspan='2'>&#128062; Best walk windows: <b>{walk_str}</b></td></tr>"
            f"<tr><td style='padding:4px 8px;color:#c0392b;' colspan='2'>&#9928;&#65039; Heavy rain: {bad_str}</td></tr>"
            f"</tbody></table></div>"
            f"<div style='overflow-x:auto;'><table style='border-collapse:collapse;width:100%;font-family:sans-serif;font-size:13px;'>"
            f"<thead><tr style='background:#495057;color:#fff;'>"
            f"<th style='padding:6px 8px;text-align:left;'>Time</th><th style='padding:6px 8px;text-align:left;'>Conditions</th>"
            f"<th style='padding:6px 8px;text-align:center;'>Temp</th><th style='padding:6px 8px;text-align:center;'>Feels</th>"
            f"<th style='padding:6px 8px;text-align:center;'>Rain%</th><th style='padding:6px 8px;text-align:center;'>Wind</th>"
            f"</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div></div>")

def build_weekly_summary(data, dates):
    cells = []
    for ds in dates:
        dd = data["daily"]["time"]
        if ds not in dd: continue
        d   = dd.index(ds)
        wmo = data["daily"]["weathercode"][d]
        hi  = data["daily"]["temperature_2m_max"][d]
        lo  = data["daily"]["temperature_2m_min"][d]
        pp  = data["daily"]["precipitation_probability_max"][d]
        lbl = datetime.date.fromisoformat(ds).strftime("%a %-d")
        bg  = rain_bg(pp)
        cells.append(
            f"<td style='text-align:center;padding:10px 6px;background:{bg};border-right:1px solid #dee2e6;'>"
            f"<div style='font-size:11px;color:#6c757d;'>{lbl}</div>"
            f"<div style='font-size:22px;'>{wmo_emoji(wmo)}</div>"
            f"<div style='font-size:13px;font-weight:bold;'>{hi:.0f}° / {lo:.0f}°</div>"
            f"<div style='font-size:12px;color:#6c757d;'>{pp:.0f}% rain</div></td>"
        )
    return (
        "<div style='margin:0 0 28px;'>"
        "<h2 style='font-family:sans-serif;font-size:16px;color:#2c3e50;margin:0 0 8px;'>&#128197; 7-Day Overview</h2>"
        "<div style='overflow-x:auto;'>"
        "<table style='border-collapse:collapse;width:100%;min-width:500px;font-family:sans-serif;border:1px solid #dee2e6;border-radius:8px;overflow:hidden;'>"
        "<tbody><tr>" + "".join(cells) + "</tr></tbody></table></div></div>"
    )


def build_worst_warning(worst):
    if not worst: return ""
    label = datetime.date.fromisoformat(worst["date"]).strftime("%A %-d %b")
    return (
        f"<div style='margin:0 0 28px;padding:14px 16px;background:#f8d7da;"
        f"border-left:5px solid #dc3545;border-radius:6px;font-family:sans-serif;'>"
        f"<b style='font-size:15px;color:#721c24;'>&#9888;&#65039; Worst day ahead: {label}</b><br>"
        f"<span style='font-size:14px;color:#721c24;'>{wmo_emoji(worst['wmo'])} {wmo_desc(worst['wmo'])} — "
        f"{worst['pp']:.0f}% rain probability, {worst['ps']:.1f}mm expected</span></div>"
    )


def build_forecast_3day(data, dates):
    cards = []
    for ds in dates[1:3]:
        dd = data["daily"]["time"]
        if ds not in dd: continue
        d   = dd.index(ds)
        wmo = data["daily"]["weathercode"][d]
        hi  = data["daily"]["temperature_2m_max"][d]
        lo  = data["daily"]["temperature_2m_min"][d]
        pp  = data["daily"]["precipitation_probability_max"][d]
        sr  = fmt_time(data["daily"]["sunrise"][d])
        ss  = fmt_time(data["daily"]["sunset"][d])
        uv  = data["daily"]["uv_index_max"][d]
        uv_txt, uv_bg = uv_label(uv)
        label = datetime.date.fromisoformat(ds).strftime("%A %-d %b")
        bg = rain_bg(pp)
        cards.append(
            f"<div style='margin:0 0 14px;padding:12px 14px;background:{bg};"
            f"border:1px solid #dee2e6;border-radius:8px;font-family:sans-serif;font-size:14px;'>"
            f"<b>{label}</b> &nbsp; {wmo_emoji(wmo)} {wmo_desc(wmo)}<br>"
            f"&#127777;&#65039; {lo:.0f}–{hi:.0f}°C &nbsp; &#127774; {sr} &#127769; {ss} &nbsp;"
            f"<span style='background:{uv_bg};padding:1px 6px;border-radius:4px;font-size:12px;'>"
            f"UV {uv:.0f} {uv_txt}</span> &nbsp; Rain {pp:.0f}%</div>"
        )
    if not cards: return ""
    return (
        "<div style='margin:0 0 28px;'>"
        "<h2 style='font-family:sans-serif;font-size:16px;color:#2c3e50;margin:0 0 10px;'>&#128197; Next 2 Days</h2>"
        + "".join(cards) + "</div>"
    )


def _html_shell(body_content, quote_text, quote_author):
    return f"""<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{{margin:0;padding:0;background:#f0f2f5;font-family:sans-serif;}}
  .wrap{{max-width:620px;margin:20px auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12);}}
  .header{{background:linear-gradient(135deg,#2c3e50,#3a9fd1);padding:22px 24px;}}
  .header h1{{margin:0;color:#fff;font-size:22px;}}
  .header p{{margin:6px 0 0;color:#cde8f7;font-size:14px;}}
  .body{{padding:20px 24px;}}
  .headline{{padding:14px 16px;background:#eaf6ff;border-left:5px solid #3a9fd1;border-radius:6px;margin-bottom:24px;font-size:15px;color:#1a2a3a;}}
  .quote{{margin-top:24px;padding:14px 16px;background:#f8f9fa;border-left:4px solid #adb5bd;border-radius:6px;font-style:italic;font-size:14px;color:#495057;}}
  .footer{{padding:12px 24px;background:#f0f2f5;font-size:12px;color:#6c757d;text-align:center;}}
  @media(max-width:480px){{.body{{padding:14px 12px;}}.header{{padding:16px 14px;}}td{{padding:4px 5px !important;font-size:12px !important;}}}}
</style></head>
<body><div class="wrap">
<div class="header"><h1>&#127804; Belfast Weather</h1><p id="datestr"></p></div>
<div class="body">
{body_content}
<div class="quote">&ldquo;{quote_text}&rdquo;<br>
<span style="font-size:12px;color:#6c757d;font-style:normal;">— {quote_author}</span>
</div></div>
<div class="footer">Sent automatically via GitHub Actions &bull; Open-Meteo weather data</div>
</div>
<script>document.getElementById('datestr').textContent=new Date().toLocaleDateString('en-GB',{{weekday:'long',day:'numeric',month:'long',year:'numeric'}});</script>
</body></html>"""


def build_html_email(today, data, dates, quote):
    worst = find_worst_day(data, dates)
    body = (
        f"<div class='headline'>{today['headline']}</div>"
        + build_worst_warning(worst)
        + build_day_section(today)
        + build_forecast_3day(data, dates)
        + build_weekly_summary(data, dates)
    )
    return _html_shell(body, quote[0], quote[1])


def build_full_html_email(today, data, dates, quote, day_of_week, cal_events, conflicts):
    worst = find_worst_day(data, dates)
    body = (
        f"<div class='headline'>{today['headline']}</div>"
        + build_worst_warning(worst)
        + build_day_section(today)
        + build_forecast_3day(data, dates)
        + build_weekly_summary(data, dates)
        + build_schedule_section(day_of_week)
        + build_conflicts_section(cal_events, conflicts)
    )
    return _html_shell(body, quote[0], quote[1])


def send_email_to(subject, html, recipients):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_USER, recipients, msg.as_string())
    print(f"Email sent to: {', '.join(recipients)}")


def main():
    import pytz
    tz = pytz.timezone("Europe/London")
    now = datetime.datetime.now(tz)
    today_str   = now.strftime("%Y-%m-%d")
    day_of_week = now.strftime("%A").lower()

    print(f"Running for {today_str} ({day_of_week})")

    data  = fetch_weather()
    quote = fetch_wisdom_quote()
    dates = data["daily"]["time"]
    today = analyze_day(data, today_str)

    emoji = wmo_emoji(today["wmo"])
    subject = (
        f"{emoji} Belfast Weather — "
        f"{datetime.date.fromisoformat(today_str).strftime('%A %-d %b')} — "
        f"{today['min_temp']:.0f}–{today['max_temp']:.0f}°C"
    )

    if SCHEDULE_RECIPIENTS:
        cal_events = fetch_calendar_events(today_str)
        conflicts  = detect_conflicts(cal_events, day_of_week)
        full_html  = build_full_html_email(today, data, dates, quote, day_of_week, cal_events, conflicts)
        send_email_to(subject, full_html, SCHEDULE_RECIPIENTS)

    weather_only = [r for r in RECIPIENTS if r not in SCHEDULE_RECIPIENTS]
    if weather_only:
        weather_html = build_html_email(today, data, dates, quote)
        send_email_to(subject, weather_html, weather_only)


if __name__ == "__main__":
    main()
