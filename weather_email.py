#!/usr/bin/env python3
"""
Belfast Daily Weather Email
Fetches Open-Meteo forecast, analyses it, and sends a rich HTML email.
Designed to run as a GitHub Actions scheduled job.
"""

import os
import json
import random
import smtplib
import datetime
import urllib.request
import urllib.error
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=54.5973&longitude=-5.9301"
    "&hourly=temperature_2m,precipitation_probability,precipitation,weathercode,windspeed_10m"
    "&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max"
    "&timezone=Europe%2FLondon&forecast_days=2"
)

RECIPIENTS = "aarongi13z@gmail.com, raffertylaura@rocketmail.com, spmrafferty@yahoo.com"
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

WMO_CODES = {
    0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
    45:"Fog",48:"Icy fog",51:"Light drizzle",53:"Moderate drizzle",
    55:"Dense drizzle",61:"Light rain",63:"Moderate rain",65:"Heavy rain",
    71:"Light snow",73:"Moderate snow",75:"Heavy snow",77:"Snow grains",
    80:"Light showers",81:"Moderate showers",82:"Violent showers",
    85:"Light snow showers",86:"Heavy snow showers",95:"Thunderstorm",
    96:"Thunderstorm with hail",99:"Thunderstorm with heavy hail",
}

FALLBACK_QUOTES = [
    ("It is not death that a man should fear, but he should fear never beginning to live.","Marcus Aurelius"),
    ("The impediment to action advances action. What stands in the way becomes the way.","Marcus Aurelius"),
    ("He who knows others is wise; he who knows himself is enlightened.","Lao Tzu"),
    ("A gem cannot be polished without friction, nor a man perfected without trials.","Seneca"),
    ("Your task is not to seek for love, but merely to seek and find all the barriers within yourself that you have built against it.","Rumi"),
    ("Do not go where the path may lead; go instead where there is no path and leave a trail.","Ralph Waldo Emerson"),
    ("The happiness of your life depends upon the quality of your thoughts.","Marcus Aurelius"),
    ("Waste no more time arguing about what a good man should be. Be one.","Marcus Aurelius"),
    ("We suffer more in imagination than in reality.","Seneca"),
    ("Knowing others is wisdom; knowing yourself is Enlightenment.","Lao Tzu"),
    ("To be yourself in a world that is constantly trying to make you something else is the greatest accomplishment.","Ralph Waldo Emerson"),
]

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "BelfastWeatherBot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())

def fetch_weather():
    last_err = None
    for attempt in range(2):
        try:
            return fetch_json(WEATHER_URL)
        except Exception as exc:
            last_err = exc
            if attempt == 0:
                import time
                print(f"Retrying in 3s… ({exc})")
                time.sleep(3)
    raise RuntimeError(f"Weather fetch failed: {last_err}")

def fetch_wisdom_quote():
    try:
        data = fetch_json("https://zenquotes.io/api/random")
        return data[0]["q"], data[0]["a"]
    except Exception as exc:
        print(f"Quote API unavailable ({exc}), using fallback.")
    return random.choice(FALLBACK_QUOTES)

def wmo_description(code):
    return WMO_CODES.get(code, f"Code {code}")

def conditions_summary(wmo_code, precip_sum, max_precip_prob):
    desc = wmo_description(wmo_code)
    if max_precip_prob < 20 and precip_sum == 0:
        return f"{desc} — Dry day expected"
    elif max_precip_prob < 40:
        return f"{desc} — Some chance of rain"
    elif max_precip_prob < 70:
        return f"{desc} — Rainy spells likely"
    else:
        return f"{desc} — Wet day, bring an umbrella"

def find_contiguous_blocks(hours_list):
    if not hours_list:
        return []
    blocks, start, prev = [], hours_list[0], hours_list[0]
    for h in hours_list[1:]:
        if h == prev + 1:
            prev = h
        else:
            blocks.append((start, prev)); start = prev = h
    blocks.append((start, prev))
    return blocks

def analyze_day(data, date_str):
    ht = data["hourly"]["time"]
    day_idx = [i for i, t in enumerate(ht) if t.startswith(date_str)]
    times = [ht[i] for i in day_idx]
    temps = [data["hourly"]["temperature_2m"][i] for i in day_idx]
    precip_probs = [data["hourly"]["precipitation_probability"][i] for i in day_idx]
    precips = [data["hourly"]["precipitation"][i] for i in day_idx]
    winds = [data["hourly"]["windspeed_10m"][i] for i in day_idx]
    display_idx = [i for i, t in enumerate(times) if 6 <= int(t[11:13]) <= 21]
    good_hours = sorted(int(times[i][11:13]) for i in range(len(times)) if precip_probs[i] < 30 and precips[i] == 0.0)
    walk_blocks = find_contiguous_blocks(good_hours)
    walk_blocks.sort(key=lambda w: (-(w[1]-w[0]+1), abs((w[0]+w[1])//2-12)))
    bad_hours = sorted(int(times[i][11:13]) for i in range(len(times)) if precip_probs[i] > 45)
    bad_blocks = find_contiguous_blocks(bad_hours)
    d = data["daily"]["time"].index(date_str)
    peak_prob = max(precip_probs)
    peak_hour = int(times[precip_probs.index(peak_prob)][11:13])
    return {
        "date": date_str,
        "max_temp": data["daily"]["temperature_2m_max"][d],
        "min_temp": data["daily"]["temperature_2m_min"][d],
        "wmo": data["daily"]["weathercode"][d],
        "conditions": conditions_summary(data["daily"]["weathercode"][d], data["daily"]["precipitation_sum"][d], data["daily"]["precipitation_probability_max"][d]),
        "precip_sum": data["daily"]["precipitation_sum"][d],
        "max_precip_prob": data["daily"]["precipitation_probability_max"][d],
        "peak_prob": peak_prob, "peak_hour": peak_hour,
        "wind_min": min(winds), "wind_max": max(winds),
        "times": times, "temps": temps, "precip_probs": precip_probs,
        "precips": precips, "winds": winds, "display_idx": display_idx,
        "walk_blocks": walk_blocks[:3], "bad_blocks": bad_blocks,
    }

def fmt_hour(h): return f"{h:02d}:00"

def cell_style(pp):
    bg = "#f8d7da" if pp > 45 else "#fff3cd" if pp >= 25 else "#d4edda"
    return f"padding:4px 8px; border:1px solid #dee2e6; text-align:center; background:{bg};"

def fmt_block(s, e): return fmt_hour(s) if s == e else f"{fmt_hour(s)} – {fmt_hour(e+1)}"

def build_day_section(day, label):
    rows = ""
    for i in day["display_idx"]:
        h = int(day["times"][i][11:13])
        pp, pr, temp, wind = day["precip_probs"][i], day["precips"][i], day["temps"][i], day["winds"][i]
        emoji = " 🌧️" if pp > 50 else ""
        rows += f'<tr><td style="padding:4px 8px;border:1px solid #dee2e6">{fmt_hour(h)}</td><td style="padding:4px 8px;border:1px solid #dee2e6;text-align:center">{temp:.1f}°C</td><td style="{cell_style(pp)}">{pp:.0f}%{emoji}</td><td style="padding:4px 8px;border:1px solid #dee2e6;text-align:center">{pr:.1f} mm</td><td style="padding:4px 8px;border:1px solid #dee2e6;text-align:center">{wind:.0f} km/h</td></tr>'
    walk_items = "".join(f"<li>✅ {fmt_block(s,e)}</li>" for s,e in day["walk_blocks"]) or "<li>No clear dry windows</li>"
    bad_items = "".join(f"<li>🚫 {fmt_block(s,e)} — rain likely</li>" for s,e in day["bad_blocks"]) or "<li>No high-risk windows!</li>"
    return f"""<div style="background:#fff;border:1px solid #dee2e6;border-radius:8px;padding:20px;margin-bottom:20px">
<h2 style="color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:8px;margin-top:0">{label}: {day['date']}</h2>
<table style="width:100%;margin-bottom:12px"><tr>
<td style="width:50%;vertical-align:top;padding-right:12px"><strong>🌡️ Temperature:</strong> {day['min_temp']:.1f}°C – {day['max_temp']:.1f}°C<br><strong>☁️ Conditions:</strong> {day['conditions']}<br><strong>🌬️ Wind:</strong> {day['wind_min']:.0f} – {day['wind_max']:.0f} km/h</td>
<td style="width:50%;vertical-align:top"><strong>🌧️ Rain risk:</strong> Max {day['max_precip_prob']:.0f}%, total {day['precip_sum']:.1f} mm<br><strong>⏰ Peak rain:</strong> {day['peak_prob']:.0f}% at {fmt_hour(day['peak_hour'])}</td>
</tr></table>
<h3 style="color:#2c3e50;margin:16px 0 8px">Hourly Forecast (6 am – 9 pm)</h3>
<table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr style="background:#3498db;color:white"><th style="padding:6px 8px;border:1px solid #2980b9;text-align:left">Hour</th><th style="padding:6px 8px;border:1px solid #2980b9;text-align:center">Temp</th><th style="padding:6px 8px;border:1px solid #2980b9;text-align:center">Rain Prob</th><th style="padding:6px 8px;border:1px solid #2980b9;text-align:center">Precip</th><th style="padding:6px 8px;border:1px solid #2980b9;text-align:center">Wind</th></tr></thead><tbody>{rows}</tbody></table>
<h3 style="color:#2c3e50;margin:16px 0 8px">🐕 Dog Walking Windows</h3>
<table style="width:100%"><tr><td style="width:50%;vertical-align:top;padding-right:12px"><strong>Best times:</strong><ul style="margin:8px 0;padding-left:20px;line-height:1.8">{walk_items}</ul></td><td style="width:50%;vertical-align:top"><strong>Times to avoid:</strong><ul style="margin:8px 0;padding-left:20px;line-height:1.8">{bad_items}</ul></td></tr></table>
</div>"""

def build_html_email(today_data, tomorrow_data, quote_text, quote_author, now):
    date_display = now.strftime("%a %-d %b %Y")
    timestamp = now.strftime("%Y-%m-%d %H:%M %Z")
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Belfast Weather Update</title></head>
<body style="font-family:'Helvetica Neue',Arial,sans-serif;background:#f0f4f8;margin:0;padding:20px">
<div style="max-width:700px;margin:0 auto">
<div style="background:linear-gradient(135deg,#1e3c72,#2a5298);color:white;border-radius:12px 12px 0 0;padding:24px 28px;text-align:center">
<h1 style="margin:0;font-size:28px;letter-spacing:1px">&#9729;&#65039; Belfast Weather Update</h1>
<p style="margin:6px 0 0;font-size:15px;opacity:.85">{date_display}</p>
<p style="margin:4px 0 0;font-size:12px;opacity:.65">Data: Open-Meteo · Belfast, Northern Ireland</p></div>
<div style="background:#fdf8f0;border-left:4px solid #c8a96e;padding:20px 28px">
<p style="font-style:italic;font-size:16px;color:#5a4a35;margin:0 0 10px;line-height:1.7">&#8220;{quote_text}&#8221;</p>
<p style="text-align:right;color:#8a7055;font-size:14px;margin:0">&#8212; {quote_author}</p></div>
<div style="padding:20px 0">{build_day_section(today_data,'Today')}{build_day_section(tomorrow_data,'Tomorrow')}</div>
<div style="background:#fff;border:1px solid #dee2e6;border-radius:8px;padding:14px 20px;margin-bottom:16px;font-size:13px">
<strong>Colour key:</strong>
<span style="background:#d4edda;padding:2px 8px;border-radius:3px;margin-left:10px">Low (&lt;25%)</span>
<span style="background:#fff3cd;padding:2px 8px;border-radius:3px;margin-left:6px">Moderate (25–45%)</span>
<span style="background:#f8d7da;padding:2px 8px;border-radius:3px;margin-left:6px">High (&gt;45%)</span> 🌧️ = &gt;50%</div>
<div style="background:#2c3e50;color:#aab8c2;border-radius:0 0 12px 12px;padding:14px 20px;font-size:12px;text-align:center">
Data: <a href="https://open-meteo.com" style="color:#7fb3d3">Open-Meteo</a> · Generated: {timestamp}</div>
</div></body></html>"""

def send_email(subject, html_body):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        raise RuntimeError("GMAIL_USER and GMAIL_APP_PASSWORD must be set.")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject; msg["From"] = GMAIL_USER; msg["To"] = RECIPIENTS
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, [r.strip() for r in RECIPIENTS.split(",")], msg.as_string())
    print(f"Email sent to: {RECIPIENTS}")

def main():
    try:
        import pytz
        tz = pytz.timezone("Europe/London")
        now = datetime.datetime.now(tz)
    except ImportError:
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=1)))
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"Running for {today_str}")
    weather = fetch_weather()
    quote_text, quote_author = fetch_wisdom_quote()
    today_data = analyze_day(weather, today_str)
    tomorrow_data = analyze_day(weather, tomorrow_str)
    html = build_html_email(today_data, tomorrow_data, quote_text, quote_author, now)
    subject = f"Belfast Weather Update - {now.strftime('%a %-d %b %Y')}"
    print(f"Sending: {subject}")
    send_email(subject, html)
    print("Done.")

if __name__ == "__main__":
    main()

