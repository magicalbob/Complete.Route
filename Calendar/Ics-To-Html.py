#!/usr/bin/env python3
"""
ics_to_html.py
Takes a .ics file exported from Google Calendar and outputs WePress-safe HTML.
- Only includes events in the future
- Optional window: how far ahead to include (default 3 months)
- Outputs inline-styled cards that won't be stripped by WordPress multisite

Usage:
  python ics_to_html.py blackpoolandfyldegreenpartyuk@gmail.com.ics
  python ics_to_html.py calendar.ics --months 6 --output events.html
  python ics_to_html.py calendar.ics --days 60
"""

import argparse
import calendar
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    LONDON = ZoneInfo("Europe/London")
except ImportError:
    LONDON = None  # fallback to UTC+1 in summer approx

def add_months(dt, months):
    """Add months accurately (handles year rollover and month length)."""
    m = dt.month - 1 + months
    y = dt.year + m // 12
    m = m % 12 + 1
    d = min(dt.day, calendar.monthrange(y, m)[1])
    return dt.replace(year=y, month=m, day=d)

def unfold_ics(text):
    """Unfold folded lines per RFC5545: CRLF + SPACE/TAB -> joined."""
    # Remove CRLF followed by space or tab
    return re.sub(r'\r?\n[ \t]', '', text)

def unescape_ics(s):
    """Unescape \, \; \\ \n \\N etc."""
    return s.replace('\\,', ',').replace('\\;', ';').replace('\\\\', '\\').replace('\\n', '\n').replace('\\N', '\n').strip()

def parse_dt(value, params=""):
    """
    Parse DTSTART/DTEND value.
    Returns aware datetime in UTC, and also datetime in London for display.
    Supports:
      20260830T090000Z
      20260830T100000
      20260830 (all-day)
      With TZID param
    """
    is_all_day = False
    tzid = None
    if 'TZID=' in params:
        m = re.search(r'TZID=([^;:]+)', params)
        if m:
            tzid = m.group(1)

    # DATE only: YYYYMMDD
    if re.match(r'^\d{8}$', value):
        is_all_day = True
        dt = datetime.strptime(value, "%Y%m%d")
        # treat as London midnight
        if LONDON:
            dt_london = dt.replace(tzinfo=LONDON)
            dt_utc = dt_london.astimezone(timezone.utc)
        else:
            dt_london = dt
            dt_utc = dt.replace(tzinfo=timezone.utc)
        return dt_utc, dt_london, is_all_day

    # DATE-TIME
    fmt = "%Y%m%dT%H%M%SZ" if value.endswith('Z') else "%Y%m%dT%H%M%S"
    try:
        dt = datetime.strptime(value, fmt)
        if value.endswith('Z'):
            dt_utc = dt.replace(tzinfo=timezone.utc)
            dt_london = dt_utc.astimezone(LONDON) if LONDON else dt_utc
        else:
            # floating or TZID - assume London
            if LONDON:
                # try to use TZID if valid zone
                try:
                    tz = ZoneInfo(tzid) if tzid else LONDON
                except:
                    tz = LONDON
                dt_london = dt.replace(tzinfo=tz)
                dt_utc = dt_london.astimezone(timezone.utc)
            else:
                dt_london = dt
                dt_utc = dt.replace(tzinfo=timezone.utc)
        return dt_utc, dt_london, is_all_day
    except ValueError:
        # fallback
        return None, None, False

def parse_ics_file(path):
    text = Path(path).read_text(encoding='utf-8', errors='ignore')
    text = unfold_ics(text)
    events = []
    # Find VEVENT blocks
    for block in re.findall(r'BEGIN:VEVENT(.*?)END:VEVENT', text, re.DOTALL):
        ev = {}
        # parse lines
        for line in block.splitlines():
            if not line.strip():
                continue
            if ':' not in line:
                continue
            prop, val = line.split(':', 1)
            prop_name = prop.split(';')[0]
            if prop_name in ('DTSTART','DTEND','SUMMARY','LOCATION','DESCRIPTION','UID'):
                ev[prop_name] = (prop, val)  # keep prop for params
        
        if 'DTSTART' not in ev:
            continue
        
        # parse dates
        dtstart_prop, dtstart_val = ev['DTSTART']
        dtend_prop, dtend_val = ev.get('DTEND', (None, None))
        dtstart_utc, dtstart_london, is_all_day = parse_dt(dtstart_val.strip(), dtstart_prop)
        dtend_utc, dtend_london, _ = parse_dt(dtend_val.strip(), dtend_prop) if dtend_val else (None, None, False)

        if not dtstart_utc:
            continue

        summary = unescape_ics(ev.get('SUMMARY', ('',''))[1]) if 'SUMMARY' in ev else 'Untitled'
        location = unescape_ics(ev.get('LOCATION', ('',''))[1]) if 'LOCATION' in ev else ''
        description = unescape_ics(ev.get('DESCRIPTION', ('',''))[1]) if 'DESCRIPTION' in ev else ''

        events.append({
            'summary': summary,
            'location': location,
            'description': description,
            'dtstart_utc': dtstart_utc,
            'dtstart_london': dtstart_london,
            'dtend_london': dtend_london,
            'is_all_day': is_all_day,
            'raw': block
        })
    return sorted(events, key=lambda e: e['dtstart_utc'])

def format_event_html(ev):
    """Return card HTML like the previous example."""
    dl = ev['dtstart_london']
    dl_end = ev['dtend_london']
    
    # Format date
    day_name = dl.strftime('%A')
    date_str = dl.strftime(f'{day_name} %d %B %Y').replace(' 0',' ')
    # Time
    if ev['is_all_day']:
        time_str = 'All day'
        end_time_str = ''
    else:
        # Show BST/GMT suffix
        tz_suffix = dl.strftime('%Z') or 'UK'
        time_str = dl.strftime('%-I:%M%p').lower() if sys.platform != 'win32' else dl.strftime('%#I:%M%p').lower()
        # fix - python %I gives 10:00am, we want 10:00am
        time_str = time_str.replace(':00am','am').replace(':00pm','pm') if ':00' in time_str else time_str
        # Actually keep minutes
        time_str_fmt = dl.strftime('%I:%M%p').lstrip('0').lower()
        if dl_end and dl_end.date() == dl.date():
            end_fmt = dl_end.strftime('%I:%M%p').lstrip('0').lower()
            time_display = f"{time_str_fmt} – {end_fmt} {tz_suffix}"
        else:
            time_display = f"{time_str_fmt} {tz_suffix}"
    
    location = ev['location']
    maps_url = f"https://www.google.com/maps/search/?api=1&query={location}" if location else ""
    # Escape HTML
    def esc(s):
        return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')
    
    loc_html = f'📍 {esc(location)}<br><a href="{maps_url}" target="_blank" rel="noopener" style="color:#6ABF4B; text-decoration:underline;">View map</a>' if location else ''

    if ev['is_all_day']:
        full_time = f"{date_str} • All day"
    else:
        full_time = f"{date_str} • {time_display}"

    card = f'''<div style="border-left:5px solid #6ABF4B; background:#ffffff; padding:18px 20px; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.06); font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width:700px; margin-bottom:20px;">
  <div style="font-size:12px; text-transform:uppercase; letter-spacing:0.08em; color:#666; margin-bottom:6px;">{esc(full_time)}</div>
  <div style="font-size:20px; font-weight:700; color:#111; margin-bottom:8px;">{esc(ev['summary'])}</div>
  <div style="font-size:14px; color:#333; line-height:1.5;">{loc_html}</div>
</div>'''
    return card

def main():
    parser = argparse.ArgumentParser(description='Convert .ics to WePress-safe HTML (future events only)')
    parser.add_argument('ics_file', help='Path to .ics file (or .ical.zip contents)')
    parser.add_argument('-o', '--output', help='Output HTML file (default: stdout)', default=None)
    parser.add_argument('--months', type=int, default=3, help='How many months ahead to include (default 3)')
    parser.add_argument('--days', type=int, default=None, help='Override months with exact days ahead (e.g. --days 60)')
    parser.add_argument('--include-past', action='store_true', help='Include past events too (for debugging)')
    args = parser.parse_args()

    ics_path = Path(args.ics_file)
    if not ics_path.exists():
        sys.exit(f"File not found: {ics_path}")

    events = parse_ics_file(ics_path)

    # Time window
    now_utc = datetime.now(timezone.utc)
    now_london = now_utc.astimezone(LONDON) if LONDON else now_utc

    if args.days is not None:
        future_cutoff = now_utc + timedelta(days=args.days)
        window_label = f"{args.days} days"
    else:
        # add months in London time for user expectation
        future_cutoff_london = add_months(now_london, args.months)
        future_cutoff = future_cutoff_london.astimezone(timezone.utc) if LONDON else future_cutoff_london.replace(tzinfo=timezone.utc)
        window_label = f"{args.months} months"

    filtered = []
    for ev in events:
        if not args.include_past and ev['dtstart_utc'] < now_utc:
            continue
        if ev['dtstart_utc'] > future_cutoff:
            continue
        filtered.append(ev)

    if not filtered:
        html_body = f'<p style="font-family:sans-serif; color:#666;">No upcoming events in the next {window_label}.</p>\n'
    else:
        cards = [format_event_html(ev) for ev in filtered]
        html_body = "\n".join(cards)

    footer = f'<p style="font-size:12px; color:#888; font-family:sans-serif;">Last updated: {now_london.strftime("%d %b %Y")} • Showing next {window_label} • {len(filtered)} event(s)</p>\n'

    full_html = f"""<!-- WePress-safe event list - paste this into Custom HTML block -->
<!-- Generated from {ics_path.name} on {now_london.isoformat()} -->
{html_body}
{footer}
"""

    if args.output:
        Path(args.output).write_text(full_html, encoding='utf-8')
        print(f"Wrote {len(filtered)} events to {args.output}")
    else:
        print(full_html)

if __name__ == '__main__':
    main()
