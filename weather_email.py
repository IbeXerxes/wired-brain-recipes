#!/usr/bin/env python3
"""Belfast Daily Weather Email — Enhanced Edition v2"""

import os, json, random, smtplib, datetime, urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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

RECIPIENTS = "aarongi13z@gmail.com, raffertylaura@rocketmail.com, spmrafferty@yahoo.com"
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

WMO_CODES = {
    0:  ("Clear sky",                "☀️"),
    1:  ("Mainly clear",             "🌤️"),
    2:  ("Partly cloudy",            "⛅"),
    3:  ("Overcast",                 "☁️"),
    45: ("Fog",                      "🌫️"),
    48: ("Icy fog",                  "🌫️"),
    51: ("Light drizzle",            "🌦️"),
    53: ("Moderate drizzle",         "🌦️"),
    55: ("Dense drizzle",            "🌧️"),
    61: ("Light rain",               "🌧️"),
    63: ("Moderate rain",            "🌧️"),
    65: ("Heavy rain",               "🌧️"),
    71: ("Light snow",               "❄️"),
    73: ("Moderate snow",            "❄️"),
    75: ("Heavy snow",               "❄️"),
    77: ("Snow grains",              "🌨️"),
    80: ("Light showers",            "🌦️"),
    81: ("Moderate showers",         "🌧️"),
    82: ("Violent showers",          "⛈️"),
    85: ("Light snow showers",       "🌨️"),
    86: ("Heavy snow showers",       "🌨️"),
    95: ("Thunderstorm",             "⛈️"),
    96: ("Thunderstorm with hail",   "⛈️"),
    99: ("Thunderstorm, heavy hail", "⛈️"),
}

FALLBACK_QUOTES = [
    ("It is not death that a man should fear, but he should fear never beginning to live.", "Marcus Aurelius"),
    ("The impediment to action advances action. What stands in the way becomes the way.", "Marcus Aurelius"),
    ("He who knows others is wise; he who knows himself is enlightened.", "Lao Tzu"),
    ("A gem cannot be polished without friction, nor a man perfected without trials.", "Seneca"),
    ("Your task is not to seek for love, but merely to seek and find all the barriers within yourself that you have built against it.", "Rumi"),
    ("Do not go where the path may lead; go instead where there is no path and leave a trail.", "Ralph Waldo Emerson"),
    ("The happiness of your life depends upon the quality of your thoughts.", "Marcus Aurelius"),
    ("Waste no more time arguing about what a good man should be. Be one.", "Marcus Aurelius"),
    ("We suffer more in imagination than in reality.", "Seneca"),
    ("Knowing others is wisdom; knowing yourself is Enlightenment.", "Lao Tzu"),
    ("What we achieve inwardly will change outer reality.", "Plutarch"),
    ("To be yourself in a world that is constantly trying to make you something else is the greatest accomplishment.", "Ralph Waldo Emerson"),
    ("The first and greatest victory is to conquer yourself.", "Plato"),
    ("He who has a why to live can bear almost any how.", "Nietzsche"),
]

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "BelfastWeatherBot/2.0"})
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

def fmt_block(s, e):
    return fmt_hour(s) if s == e else f"{fmt_hour(s)} – {fmt_hour(e + 1)}"

def find_blocks(hours_list):
    if not hours_list: return []
    blocks, start, prev = [], hours_list[0], hours_list[0]
    for h in hours_list[1:]:
        if h == prev + 1:
            prev = h
        else:
            blocks.append((start, prev)); start = prev = h
    blocks.append((start, prev))
    return blocks

def conditions_summary(wmo_code, precip_sum, max_pp):
    desc = wmo_desc(wmo_code)
    if max_pp < 20 and precip_sum == 0: return f"{desc} — Dry day expected"
    if max_pp < 40: return f"{desc} — Some chance of rain"
    if max_pp < 70: return f"{desc} — Rainy spells likely"
    return f"{desc} — Wet day, bring an umbrella"

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
    return f"A {temp_desc} day ({d['min_temp']:.0f}–{d['max_temp']:.0f}°C), {rain_desc}{wind_desc}.{walk_desc}"

def analyze_day(data, date_str):
    ht   = data["hourly"]["time"]
    idx  = [i for i, t in enumerate(ht) if t.startswith(date_str)]
    times = [ht[i]                                        for i in idx]
    temps = [data["hourly"]["temperature_2m"][i]          for i in idx]
    feels = [data["hourly"]["apparent_temperature"][i]    for i in idx]
    pps   = [data["hourly"]["precipitation_probability"][i] for i in idx]
    prs   = [data["hourly"]["precipitation"][i]           for i in idx]
    winds = [data["hourly"]["windspeed_10m"][i]           for i in idx]
    codes = [data["hourly"]["weathercode"][i]             for i in idx]
    uvs   = [data["hourly"]["uv_index"][i]                for i in idx]

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
        "max_temp":       data["daily"]["temperature_2m_max"][d],
        "min_temp":       data["daily"]["temperature_2m_min"][d],
        "feels_max":      data["daily"]["apparent_temperature_max"][d],
        "feels_min":      data["daily"]["apparent_temperature_min"][d],
        "wmo":            data["daily"]["weathercode"][d],
        "conditions":     conditions_summary(data["daily"]["weathercode"][d],
                              data["daily"]["precipitation_sum"][d],
                              data["daily"]["precipitation_probability_max"][d]),
        "precip_sum":     data["daily"]["precipitation_sum"][d],
        "max_precip_prob":data["daily"]["precipitation_probability_max"][d],
        "peak_prob":      peak_prob,
        "peak_hour":      peak_hour,
        "wind_min":       min(winds),
        "wind_max":       max(winds),
        "wind_max_daily": data["daily"]["windspeed_10m_max"][d],
        "sunrise":        fmt_time(data["daily"]["sunrise"][d]),
        "sunset":         fmt_time(data["daily"]["sunset"][d]),
        "uv_max":         data["daily"]["uv_index_max"][d],
        "times": times, "temps": temps, "feels": feels,
        "pps": pps, "prs": prs, "winds": winds, "codes": codes, "uvs": uvs,
        "display_idx":  display_idx,
        "walk_blocks":  walk_blocks[:3],
        "bad_blocks":   bad_blocks,
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

def build_recommended_walk(day):
    if not day["walk_blocks"]:
        return '<p style="background:#fff3cd;border:1px solid #ffc107;border-radius:6px;padding:10px 14px;margin:0;">⚠️ No clear dry windows found for dog walking today.</p>'
    best = day["walk_blocks"][0]
    dur  = best[1] - best[0] + 1
    return (f'<div style="background:#d4edda;border:1px solid #c3e6cb;border-radius:8px;padding:14px 18px;">'
            f'<span style="font-size:20px;">🐕</span>'
            f' <strong style="font-size:16px;color:#155724;">Recommended Walk: {fmt_block(best[0], best[1])}</strong>'
            f'<span style="color:#155724;font-size:14px;"> — {dur}h dry window</span></div>')

def build_hourly_rows(day):
    rows = ""
    for i in day["display_idx"]:
        hour  = int(day["times"][i][11:13])
        pp    = day["pps"][i]
        rows += (f'<tr>'
                 f'<td style="padding:4px 8px;border:1px solid #dee2e6;white-space:nowrap;">{fmt_hour(hour)}</td>'
                 f'<td style="padding:4px 8px;border:1px solid #dee2e6;text-align:center;">{wmo_emoji(day["codes"][i])}</td>'
                 f'<td style="padding:4px 8px;border:1px solid #dee2e6;text-align:center;background:{temp_color(day["temps"][i])};">{day["temps"][i]:.1f}°C</td>'
                 f'<td style="padding:4px 8px;border:1px solid #dee2e6;text-align:center;color:#666;">{day["feels"][i]:.1f}°C</td>'
                 f'<td style="padding:4px 8px;border:1px solid #dee2e6;text-align:center;background:{rain_bg(pp)};">{pp:.0f}%{"🌧️" if pp > 50 else ""}</td>'
                 f'<td style="padding:4px 8px;border:1px solid #dee2e6;text-align:center;">{day["prs"][i]:.1f} mm</td>'
                 f'<td style="padding:4px 8px;border:1px solid #dee2e6;text-align:center;">{day["winds"][i]:.0f} km/h</td>'
                 f'</tr>')
    return rows

def build_day_section(day, label):
    uv_lbl, uv_bg = uv_label(day["uv_max"])
    walk_li = "".join(f"<li>✅ {fmt_block(s,e)}</li>" for s,e in day["walk_blocks"]) or "<li>No dry windows found</li>"
    bad_li  = "".join(f"<li>🚫 {fmt_block(s,e)} — rain likely</li>" for s,e in day["bad_blocks"]) or "<li>No high-risk windows — looks manageable!</li>"
    return f"""
    <div style="background:#fff;border:1px solid #dee2e6;border-radius:8px;padding:20px;margin-bottom:20px;">
      <h2 style="color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:0;">{wmo_emoji(day['wmo'])} {label}: {day['date']}</h2>
      <div style="background:#f0f4f8;border-radius:6px;padding:12px 16px;margin-bottom:14px;font-size:15px;color:#2c3e50;line-height:1.5;">{day['headline']}</div>
      <div style="margin-bottom:14px;">{build_recommended_walk(day)}</div>
      <table style="width:100%;border-collapse:collapse;margin-bottom:14px;font-size:14px;">
        <tr>
          <td style="width:50%;vertical-align:top;padding-right:12px;">
            <strong>🌡️ Temperature:</strong> {day['min_temp']:.1f}°C – {day['max_temp']:.1f}°C<br>
            <strong>🤔 Feels like:</strong> {day['feels_min']:.1f}°C – {day['feels_max']:.1f}°C<br>
            <strong>🌬️ Wind:</strong> {day['wind_min']:.0f}–{day['wind_max']:.0f} km/h (max {day['wind_max_daily']:.0f})
          </td>
          <td style="width:50%;vertical-align:top;">
            <strong>🌧️ Rain:</strong> Max {day['max_precip_prob']:.0f}%, total {day['precip_sum']:.1f} mm<br>
            <strong>🔆 UV:</strong> <span style="background:{uv_bg};padding:1px 6px;border-radius:3px;">{day['uv_max']:.1f} — {uv_lbl}</span><br>
            <strong>🌅</strong> {day['sunrise']} &nbsp; <strong>🌇</strong> {day['sunset']}
          </td>
        </tr>
      </table>
      <h3 style="color:#2c3e50;margin:0 0 8px;">Hourly Forecast (5 am – 10 pm)</h3>
      <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;font-size:13px;min-width:480px;">
          <thead>
            <tr style="background:#3498db;color:white;">
              <th style="padding:6px 8px;border:1px solid #2980b9;text-align:left;">Hour</th>
              <th style="padding:6px 8px;border:1px solid #2980b9;text-align:center;">Sky</th>
              <th style="padding:6px 8px;border:1px solid #2980b9;text-align:center;">Temp</th>
              <th style="padding:6px 8px;border:1px solid #2980b9;text-align:center;">Feels</th>
              <th style="padding:6px 8px;border:1px solid #2980b9;text-align:center;">Rain %</th>
              <th style="padding:6px 8px;border:1px solid #2980b9;text-align:center;">Precip</th>
              <th style="padding:6px 8px;border:1px solid #2980b9;text-align:center;">Wind</th>
            </tr>
          </thead>
          <tbody>{build_hourly_rows(day)}</tbody>
        </table>
      </div>
      <h3 style="color:#2c3e50;margin:16px 0 8px;">🐕 All Dog Walking Windows</h3>
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="width:50%;vertical-align:top;padding-right:12px;"><strong>Best times:</strong><ul style="margin:6px 0;padding-left:20px;line-height:1.8;">{walk_li}</ul></td>
          <td style="width:50%;vertical-align:top;"><strong>Times to avoid:</strong><ul style="margin:6px 0;padding-left:20px;line-height:1.8;">{bad_li}</ul></td>
        </tr>
      </table>
    </div>"""

def build_weekly_summary(data, dates, today_str):
    rows = ""
    dd = data["daily"]["time"]
    for date_str in dates:
        if date_str not in dd: continue
        d   = dd.index(date_str)
        dt  = datetime.date.fromisoformat(date_str)
        lbl = "Today" if date_str == today_str else dt.strftime("%a %-d %b")
        pp  = data["daily"]["precipitation_probability_max"][d]
        ps  = data["daily"]["precipitation_sum"][d]
        bold = "<strong>" if date_str == today_str else ""
        endb = "</strong>" if date_str == today_str else ""
        bg   = 'style="background:#f0f4f8;"' if date_str == today_str else ''
        rows += (f'<tr {bg}>'
                 f'<td style="padding:6px 10px;border:1px solid #dee2e6;white-space:nowrap;">{bold}{lbl}{endb}</td>'
                 f'<td style="padding:6px 10px;border:1px solid #dee2e6;text-align:center;">{wmo_emoji(data["daily"]["weathercode"][d])}</td>'
                 f'<td style="padding:6px 10px;border:1px solid #dee2e6;text-align:center;">{data["daily"]["temperature_2m_min"][d]:.0f}–{data["daily"]["temperature_2m_max"][d]:.0f}°C</td>'
                 f'<td style="padding:6px 10px;border:1px solid #dee2e6;text-align:center;background:{rain_bg(pp)};">{pp:.0f}%</td>'
                 f'<td style="padding:6px 10px;border:1px solid #dee2e6;text-align:center;">{ps:.1f} mm</td>'
                 f'</tr>')
    return f"""
    <div style="background:#fff;border:1px solid #dee2e6;border-radius:8px;padding:20px;margin-bottom:20px;">
      <h2 style="color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:0;">📅 7-Day Overview</h2>
      <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;font-size:14px;min-width:350px;">
          <thead><tr style="background:#3498db;color:white;">
            <th style="padding:6px 10px;border:1px solid #2980b9;text-align:left;">Day</th>
            <th style="padding:6px 10px;border:1px solid #2980b9;text-align:center;">Sky</th>
            <th style="padding:6px 10px;border:1px solid #2980b9;text-align:center;">Temp</th>
            <th style="padding:6px 10px;border:1px solid #2980b9;text-align:center;">Rain %</th>
            <th style="padding:6px 10px;border:1px solid #2980b9;text-align:center;">Precip</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>"""

def build_worst_warning(worst):
    if not worst: return ""
    dt  = datetime.date.fromisoformat(worst["date"])
    lbl = dt.strftime("%A %-d %b")
    return (f'<div style="background:#f8d7da;border:1px solid #f5c6cb;border-radius:8px;padding:14px 20px;margin-bottom:20px;">'
            f'<strong>⚠️ Worst day ahead: {lbl} {wmo_emoji(worst["wmo"])}</strong><br>'
            f'<span style="font-size:14px;">Rain probability up to {worst["pp"]:.0f}%, {worst["ps"]:.1f} mm expected.</span>'
            f'</div>')

def build_html_email(day_analyses, all_data, all_dates, quote_text, quote_author, now):
    today_str    = now.strftime("%Y-%m-%d")
    date_display = now.strftime("%a %-d %b %Y")
    timestamp    = now.strftime("%Y-%m-%d %H:%M %Z")
    labels       = ["Today", "Tomorrow", "Day After Tomorrow"]
    day_sections = "".join(build_day_section(d, labels[i]) for i, d in enumerate(day_analyses))
    weekly       = build_weekly_summary(all_data, all_dates, today_str)
    warning      = build_worst_warning(find_worst_day(all_data, all_dates))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Belfast Weather Update</title>
  <style>body{{font-family:'Helvetica Neue',Arial,sans-serif;background:#f0f4f8;margin:0;padding:16px;}}@media(max-width:600px){{body{{padding:6px;}}}}</style>
</head>
<body><div style="max-width:700px;margin:0 auto;">
  <div style="background:linear-gradient(135deg,#1e3c72,#2a5298);color:white;border-radius:12px 12px 0 0;padding:24px 28px;text-align:center;">
    <h1 style="margin:0;font-size:26px;letter-spacing:1px;">&#9729;&#65039; Belfast Weather Update</h1>
    <p style="margin:6px 0 0;font-size:15px;opacity:0.85;">{date_display}</p>
    <p style="margin:4px 0 0;font-size:12px;opacity:0.6;">Open-Meteo · Belfast, Northern Ireland</p>
  </div>
  <div style="background:#fdf8f0;border-left:4px solid #c8a96e;padding:18px 24px;">
    <p style="font-style:italic;font-size:15px;color:#5a4a35;margin:0 0 8px;line-height:1.7;">&#8220;{quote_text}&#8221;</p>
    <p style="text-align:right;color:#8a7055;font-size:13px;margin:0;">&#8212; {quote_author}</p>
  </div>
  <div style="padding:16px 0;">{warning}{day_sections}{weekly}</div>
  <div style="background:#fff;border:1px solid #dee2e6;border-radius:8px;padding:12px 18px;margin-bottom:14px;font-size:12px;">
    <strong>Rain %:</strong>
    <span style="background:#d4edda;padding:1px 6px;border-radius:3px;margin-left:8px;">Low &lt;25%</span>
    <span style="background:#fff3cd;padding:1px 6px;border-radius:3px;margin-left:4px;">Moderate 25–45%</span>
    <span style="background:#f8d7da;padding:1px 6px;border-radius:3px;margin-left:4px;">High &gt;45%</span>
    &nbsp;<strong>Temp:</strong>
    <span style="background:#cce5ff;padding:1px 6px;border-radius:3px;margin-left:4px;">&lt;5°C</span>
    <span style="background:#fff3cd;padding:1px 6px;border-radius:3px;margin-left:4px;">18–24°C</span>
    <span style="background:#f8d7da;padding:1px 6px;border-radius:3px;margin-left:4px;">&gt;24°C</span>
  </div>
  <div style="background:#2c3e50;color:#aab8c2;border-radius:0 0 12px 12px;padding:12px 20px;font-size:12px;text-align:center;">
    Data: <a href="https://open-meteo.com" style="color:#7fb3d3;">Open-Meteo</a> · Generated: {timestamp}
  </div>
</div></body></html>"""

def send_email(subject, html_body):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        raise RuntimeError("GMAIL_USER and GMAIL_APP_PASSWORD must be set.")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENTS
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    recipients = [r.strip() for r in RECIPIENTS.split(",")]
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        s.sendmail(GMAIL_USER, recipients, msg.as_string())
    print(f"Sent to: {RECIPIENTS}")

def main():
    try:
        import pytz
        tz  = pytz.timezone("Europe/London")
        now = datetime.datetime.now(tz)
    except ImportError:
        now = datetime.datetime.utcnow().replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=1)))

    today_str    = now.strftime("%Y-%m-%d")
    all_dates    = [(now + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    detail_dates = all_dates[:3]

    print(f"Running for {today_str}")
    weather = fetch_weather()
    quote_text, quote_author = fetch_wisdom_quote()
    day_analyses = [analyze_day(weather, d) for d in detail_dates if d in weather["daily"]["time"]]
    html = build_html_email(day_analyses, weather, all_dates, quote_text, quote_author, now)

    date_display = now.strftime("%a %-d %b %Y")
    subject = f"Belfast Weather Update - {date_display}"
    send_email(subject, html)
    print("Done!")

if __name__ == "__main__":
    main()

