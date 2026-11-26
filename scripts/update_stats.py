"""Fetch live GitHub stats and regenerate Solar System SVG cards."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import textwrap
import urllib.error
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

USERNAME = os.environ.get("GITHUB_USER", "Kush-Kelaiya22")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    location
    company
    followers {
      totalCount
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        name
        description
        stargazerCount
        forkCount
        primaryLanguage {
          name
          color
        }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
              color
            }
          }
        }
      }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


def _request_json(url: str, payload: dict | None = None) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "solar-system-updater",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_graphql_stats() -> dict:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required for the GitHub GraphQL API.")
    result = _request_json(
        "https://api.github.com/graphql",
        {"query": GRAPHQL_QUERY, "variables": {"login": USERNAME}},
    )
    if "errors" in result:
        raise RuntimeError(f"GraphQL error: {result['errors']}")
    return result["data"]["user"]


def fetch_latest_push_repo() -> str:
    try:
        events = _request_json(f"https://api.github.com/users/{USERNAME}/events/public?per_page=15")
    except (urllib.error.URLError, TimeoutError):
        return "Safe-C"

    for event in events:
        if event.get("type") == "PushEvent":
            return event.get("repo", {}).get("name", "").split("/")[-1] or "Safe-C"
    return "Safe-C"


def compute_streaks(days: list[dict]) -> tuple[int, int]:
    best = 0
    running = 0
    for day in days:
        if day["contributionCount"] > 0:
            running += 1
            best = max(best, running)
        else:
            running = 0

    today_str = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    idx = len(days) - 1
    if idx >= 0 and days[idx]["date"] == today_str and days[idx]["contributionCount"] == 0:
        idx -= 1

    current = 0
    while idx >= 0 and days[idx]["contributionCount"] > 0:
        current += 1
        idx -= 1
    return current, best


def compute_top_languages(repos: list[dict], limit: int = 5) -> list[dict]:
    totals: dict[str, dict] = {}
    for repo in repos:
        for edge in repo.get("languages", {}).get("edges", []):
            node = edge["node"]
            name = node["name"]
            if name not in totals:
                totals[name] = {"name": name, "color": node.get("color") or "#60a5fa", "size": 0}
            totals[name]["size"] += edge["size"]

    grand_total = sum(v["size"] for v in totals.values()) or 1
    ranked = sorted(totals.values(), key=lambda x: x["size"], reverse=True)[:limit]
    for item in ranked:
        item["pct"] = max(1, round(item["size"] * 100 / grand_total))
    return ranked


def space_stars_svg(seed: int = 17, width: int = 840, height: int = 165, count: int = 45) -> str:
    stars = []
    val = seed
    for i in range(count):
        val = (val * 1103515245 + 12345) & 0x7FFFFFFF
        x = (val % (width - 20)) + 10
        val = (val * 1103515245 + 12345) & 0x7FFFFFFF
        y = (val % (height - 20)) + 10
        r = 0.8 + (i % 3) * 0.45
        op = 0.25 + (i % 4) * 0.18
        stars.append(f'  <circle cx="{x}" cy="{y}" r="{r:.1f}" fill="#cbd5e1" opacity="{op:.2f}"/>')
    return "\n".join(stars)


def orbit_heat_color(count: int) -> str:
    if count <= 0:
        return "#141a2e"
    if count <= 2:
        return "#1e3a8a"
    if count <= 5:
        return "#2563eb"
    if count <= 9:
        return "#3b82f6"
    return "#facc15"


def render_solar_system(languages: list[dict], comet_repo: str) -> str:
    stars = space_stars_svg(seed=42, width=840, height=440, count=90)
    radii = [72, 108, 144, 180, 214]
    durations = ["18s", "26s", "34s", "44s", "56s"]
    start_angles = [25, 145, 225, 315, 70]

    orbit_rings = "\n".join(
        f'  <ellipse cx="420" cy="220" rx="{r}" ry="{int(r * 0.68)}" fill="none" stroke="#1e293b" stroke-width="1" stroke-dasharray="3 5"/>'
        for r in radii[: len(languages)]
    )

    planet_nodes = []
    anim_rules = []
    for idx, lang in enumerate(languages[:5]):
        r = radii[idx]
        ry = int(r * 0.68)
        dur = durations[idx]
        ang = start_angles[idx]
        color = escape(lang["color"])
        label = escape(f"{lang['name']} {lang['pct']}%")
        short = escape(lang["name"][:2].upper())

        anim_rules.append(
            f"""      .orbit-{idx} {{
        transform-origin: 420px 220px;
        animation: spin-{idx} {dur} linear infinite;
      }}
      .counter-{idx} {{
        transform-origin: {420 + r}px 220px;
        animation: counter-spin-{idx} {dur} linear infinite;
      }}
      @keyframes spin-{idx} {{
        from {{ transform: rotate({ang}deg); }}
        to {{ transform: rotate({ang + 360}deg); }}
      }}
      @keyframes counter-spin-{idx} {{
        from {{ transform: rotate(-{ang}deg); }}
        to {{ transform: rotate(-{ang + 360}deg); }}
      }}"""
        )

        # Place planet at (420 + r, 220) and rotate around sun (420, 220)
        # Note: circular orbit scaled vertically to match elliptical visual nicely via wrapper
        planet_nodes.append(
            f"""  <g class="orbit-{idx}">
    <g class="counter-{idx}">
      <circle cx="{420 + r}" cy="220" r="14" fill="#0f172a" stroke="{color}" stroke-width="2.5"/>
      <circle cx="{420 + r}" cy="220" r="9" fill="{color}" opacity="0.9"/>
      <text x="{420 + r}" y="223.5" text-anchor="middle" font-family="'Courier New', monospace" font-size="8.5" font-weight="bold" fill="#070a13">{short}</text>
      <text x="{420 + r}" y="247" text-anchor="middle" font-family="'Courier New', Consolas, monospace" font-size="10" fill="#cbd5e1">{label}</text>
    </g>
  </g>"""
        )

    styles = "\n".join(anim_rules)
    planets_svg = "\n".join(planet_nodes)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 440" width="840" height="440">
  <defs>
    <radialGradient id="sun-glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#facc15" stop-opacity="0.55"/>
      <stop offset="45%" stop-color="#f59e0b" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#070a13" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="comet-tail" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#94a3b8" stop-opacity="0"/>
      <stop offset="100%" stop-color="#f8fafc" stop-opacity="0.95"/>
    </linearGradient>
    <clipPath id="sun-avatar-clip">
      <circle cx="420" cy="220" r="24"/>
    </clipPath>
    <style>
{styles}
      .comet-fly {{
        animation: cometGlide 9s ease-in-out infinite;
      }}
      @keyframes cometGlide {{
        0%, 100% {{ transform: translate(0px, 0px); opacity: 0.9; }}
        50% {{ transform: translate(18px, 6px); opacity: 1; }}
      }}
    </style>
  </defs>

  <!-- Deep Space -->
  <rect width="840" height="440" rx="12" fill="#070a13"/>
{stars}

  <!-- Top Header & Bottom Legend -->
  <text x="24" y="30" font-family="'Courier New', Consolas, monospace" font-size="11" letter-spacing="1.4" fill="#94a3b8">SOLAR SYSTEM  ·  @{escape(USERNAME.upper())}</text>
  <text x="816" y="422" text-anchor="end" font-family="'Courier New', Consolas, monospace" font-size="10" fill="#64748b">planets = languages · moons = repos · comets = recent pushes</text>

  <!-- Comet (Recent Push) -->
  <g class="comet-fly">
    <line x1="72" y1="68" x2="152" y2="92" stroke="url(#comet-tail)" stroke-width="2" stroke-linecap="round"/>
    <circle cx="154" cy="92.5" r="3.5" fill="#ffffff"/>
    <text x="163" y="88" font-family="'Courier New', Consolas, monospace" font-size="10.5" fill="#e2e8f0">{escape(comet_repo)}</text>
  </g>

  <!-- Orbit Rings -->
{orbit_rings}

  <!-- Sun Glow & Pixel Identicon Core -->
  <circle cx="420" cy="220" r="76" fill="url(#sun-glow)"/>
  <circle cx="420" cy="220" r="26" fill="#facc15"/>
  <g clip-path="url(#sun-avatar-clip)">
    <rect x="396" y="196" width="48" height="48" fill="#ffffff"/>
    <rect x="401" y="201" width="7" height="7" fill="#ec84a7"/>
    <rect x="432" y="201" width="7" height="7" fill="#ec84a7"/>
    <rect x="409" y="209" width="7" height="7" fill="#ec84a7"/>
    <rect x="424" y="209" width="7" height="7" fill="#ec84a7"/>
    <rect x="416.5" y="216.5" width="7" height="7" fill="#ec84a7"/>
    <rect x="401" y="224" width="7" height="7" fill="#ec84a7"/>
    <rect x="409" y="224" width="7" height="7" fill="#ec84a7"/>
    <rect x="424" y="224" width="7" height="7" fill="#ec84a7"/>
    <rect x="432" y="224" width="7" height="7" fill="#ec84a7"/>
    <rect x="401" y="232" width="7" height="7" fill="#ec84a7"/>
    <rect x="432" y="232" width="7" height="7" fill="#ec84a7"/>
  </g>

  <!-- Orbiting Planets -->
{planets_svg}
</svg>
"""


def render_the_sun(name: str, location: str, company: str, followers: int, repos: int) -> str:
    stars = space_stars_svg(seed=101, width=840, height=165, count=36)
    parts = [p for p in [location, company, f"{followers} followers", f"{repos} repositories"] if p]
    meta = escape("  ·  ".join(parts))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 165" width="840" height="165">
  <defs>
    <clipPath id="sun-card-avatar">
      <circle cx="758" cy="82" r="46"/>
    </clipPath>
  </defs>
  <rect x="1" y="1" width="838" height="163" rx="10" fill="#0a0f1e" stroke="#1e293b" stroke-width="1.5"/>
{stars}
  <text x="28" y="34" font-family="'Courier New', Consolas, monospace" font-size="12" font-weight="bold" letter-spacing="1.8" fill="#facc15">THE SUN</text>
  <text x="28" y="68" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="24" font-weight="700" fill="#f8fafc">{escape(name)}</text>
  <text x="28" y="96" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="14" fill="#cbd5e1">Embedded &amp; OS developer. Building a custom RTOS for Arduino &amp; ESPs right now.</text>
  <text x="28" y="136" font-family="'Courier New', Consolas, monospace" font-size="12" fill="#64748b">{meta}</text>

  <circle cx="758" cy="82" r="49" fill="none" stroke="#facc15" stroke-width="3"/>
  <g clip-path="url(#sun-card-avatar)">
    <rect x="712" y="36" width="92" height="92" fill="#ffffff"/>
    <rect x="720" y="44" width="15" height="15" fill="#ec84a7"/>
    <rect x="781" y="44" width="15" height="15" fill="#ec84a7"/>
    <rect x="735" y="59" width="15" height="15" fill="#ec84a7"/>
    <rect x="766" y="59" width="15" height="15" fill="#ec84a7"/>
    <rect x="750" y="74" width="16" height="16" fill="#ec84a7"/>
    <rect x="720" y="90" width="15" height="15" fill="#ec84a7"/>
    <rect x="735" y="90" width="15" height="15" fill="#ec84a7"/>
    <rect x="766" y="90" width="15" height="15" fill="#ec84a7"/>
    <rect x="781" y="90" width="15" height="15" fill="#ec84a7"/>
    <rect x="720" y="105" width="15" height="15" fill="#ec84a7"/>
    <rect x="781" y="105" width="15" height="15" fill="#ec84a7"/>
  </g>
</svg>
"""


def render_moon_card(
    moon_label: str,
    title: str,
    description: str,
    stars_count: int,
    forks_count: int,
    language: str,
    lang_color: str,
    planet_color: str,
) -> str:
    stars_bg = space_stars_svg(seed=55 if moon_label == "MOON 01" else 88, width=412, height=150, count=18)
    wrapped = textwrap.wrap(description or "No description provided.", width=40)[:2]
    if len(wrapped) == 2 and len(description or "") > 78:
        wrapped[1] = wrapped[1][:37].rstrip() + "..."
    desc_svg = "\n".join(
        f'  <text x="24" y="{88 + i * 17}" font-family="-apple-system, BlinkMacSystemFont, \'Segoe UI\', Helvetica, Arial, sans-serif" font-size="12" fill="#94a3b8">{escape(line)}</text>'
        for i, line in enumerate(wrapped)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 412 150" width="412" height="150">
  <rect x="1" y="1" width="410" height="148" rx="10" fill="#0a0f1e" stroke="#1e293b" stroke-width="1.5"/>
{stars_bg}
  <text x="24" y="32" font-family="'Courier New', Consolas, monospace" font-size="11" font-weight="bold" letter-spacing="1.4" fill="#facc15">{escape(moon_label)}</text>
  <!-- Ringed Moon Icon -->
  <ellipse cx="374" cy="30" rx="16" ry="5" fill="none" stroke="{escape(planet_color)}" stroke-width="1.5" opacity="0.6" transform="rotate(-18 374 30)"/>
  <circle cx="374" cy="30" r="8" fill="{escape(planet_color)}"/>

  <text x="24" y="64" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="16" font-weight="700" fill="#f8fafc">{escape(title)}</text>
{desc_svg}

  <text x="24" y="130" font-family="'Courier New', Consolas, monospace" font-size="12" fill="#94a3b8">★ {stars_count}   ⑂ {forks_count}</text>
  <circle cx="110" cy="126" r="5" fill="{escape(lang_color)}"/>
  <text x="121" y="130" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="12" fill="#cbd5e1">{escape(language)}</text>
</svg>
"""


def render_planets_card(languages: list[dict]) -> str:
    stars_bg = space_stars_svg(seed=202, width=840, height=225, count=36)
    rows = []
    for i, lang in enumerate(languages[:5]):
        y = 74 + i * 32
        color = escape(lang["color"])
        name = escape(lang["name"])
        pct = lang["pct"]
        bar_w = max(12, int(450 * pct / 100))
        rows.append(
            f"""  <circle cx="34" cy="{y - 4}" r="6" fill="{color}"/>
  <text x="50" y="{y}" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="13" font-weight="600" fill="#e2e8f0">{name}</text>
  <rect x="230" y="{y - 10}" width="490" height="10" rx="5" fill="#161f36"/>
  <rect x="230" y="{y - 10}" width="{bar_w}" height="10" rx="5" fill="{color}"/>
  <text x="812" y="{y}" text-anchor="end" font-family="'Courier New', Consolas, monospace" font-size="12" fill="#94a3b8">{pct}%</text>"""
        )
    rows_svg = "\n".join(rows)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 225" width="840" height="225">
  <rect x="1" y="1" width="838" height="223" rx="10" fill="#0a0f1e" stroke="#1e293b" stroke-width="1.5"/>
{stars_bg}
  <text x="28" y="34" font-family="'Courier New', Consolas, monospace" font-size="12" font-weight="bold" letter-spacing="1.8" fill="#facc15">PLANETS</text>
{rows_svg}
</svg>
"""


def render_orbit_log_card(weeks: list[dict], current_streak: int, best_streak: int, total_year: int) -> str:
    stars_bg = space_stars_svg(seed=303, width=840, height=175, count=32)
    recent_weeks = weeks[-26:]
    cells = []
    for col, week in enumerate(recent_weeks):
        days = week.get("contributionDays", [])
        for row in range(5):
            count = days[row]["contributionCount"] if row < len(days) else 0
            x = col * 17
            y = row * 17
            cells.append(f'    <rect x="{x}" y="{y}" width="13" height="13" rx="2" fill="{orbit_heat_color(count)}"/>')
    grid_svg = "\n".join(cells)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 175" width="840" height="175">
  <rect x="1" y="1" width="838" height="173" rx="10" fill="#0a0f1e" stroke="#1e293b" stroke-width="1.5"/>
{stars_bg}
  <text x="28" y="34" font-family="'Courier New', Consolas, monospace" font-size="12" font-weight="bold" letter-spacing="1.8" fill="#facc15">ORBIT LOG · 26 WEEKS</text>

  <g transform="translate(28, 56)">
{grid_svg}
  </g>

  <text x="530" y="62" font-family="'Courier New', Consolas, monospace" font-size="10" letter-spacing="1" fill="#64748b">DAYS IN ORBIT</text>
  <text x="530" y="80" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="16" font-weight="700" fill="#f8fafc">{current_streak} days</text>

  <text x="530" y="104" font-family="'Courier New', Consolas, monospace" font-size="10" letter-spacing="1" fill="#64748b">LONGEST ORBIT</text>
  <text x="530" y="122" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="16" font-weight="700" fill="#f8fafc">{best_streak} days</text>

  <text x="530" y="146" font-family="'Courier New', Consolas, monospace" font-size="10" letter-spacing="1" fill="#64748b">REVOLUTIONS THIS YEAR</text>
  <text x="530" y="162" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="16" font-weight="700" fill="#f8fafc">{total_year}</text>
</svg>
"""


def fallback_data() -> tuple[dict, str]:
    sample_weeks = [{"contributionDays": [{"date": "2026-01-01", "contributionCount": (c + r) % 4} for r in range(5)]} for c in range(26)]
    sample_weeks[2]["contributionDays"][3]["contributionCount"] = 12
    user = {
        "name": "Kush Kelaiya",
        "location": "India",
        "company": "Ahmedabad University",
        "followers": {"totalCount": 20},
        "repositories": {
            "totalCount": 7,
            "nodes": [
                {
                    "name": "Safe-C",
                    "description": "Safe-C: Native compile-time memory safety plugin and toolchain addon for GCC and G++",
                    "stargazerCount": 1,
                    "forkCount": 0,
                    "primaryLanguage": {"name": "C++", "color": "#f34b7d"},
                    "languages": {"edges": [{"size": 5900, "node": {"name": "C++", "color": "#f34b7d"}}]},
                },
                {
                    "name": "Finance-and-Risk-Analysis",
                    "description": "This project covers how probability and algorithms plays a crucial role in finance and risk...",
                    "stargazerCount": 1,
                    "forkCount": 0,
                    "primaryLanguage": {"name": "Jupyter Notebook", "color": "#da5b0b"},
                    "languages": {"edges": [{"size": 900, "node": {"name": "Jupyter Notebook", "color": "#da5b0b"}}]},
                },
                {
                    "name": "RTOS",
                    "description": "Custom RTOS for Arduino and ESPs",
                    "stargazerCount": 0,
                    "forkCount": 0,
                    "primaryLanguage": {"name": "C", "color": "#555555"},
                    "languages": {
                        "edges": [
                            {"size": 1400, "node": {"name": "Python", "color": "#3572A5"}},
                            {"size": 500, "node": {"name": "C", "color": "#8b949e"}},
                            {"size": 400, "node": {"name": "JavaScript", "color": "#f1e05a"}},
                            {"size": 300, "node": {"name": "Go", "color": "#00ADD8"}},
                        ]
                    },
                },
            ],
        },
        "contributionsCollection": {
            "contributionCalendar": {"totalContributions": 786, "weeks": sample_weeks}
        },
    }
    return user, "Safe-C"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fallback", action="store_true", help="Use seed data when GITHUB_TOKEN is unavailable.")
    args = parser.parse_args()

    if args.fallback and not TOKEN:
        user, comet_repo = fallback_data()
        current_streak, best_streak = 0, 6
    else:
        user = fetch_graphql_stats()
        comet_repo = fetch_latest_push_repo()
        all_days = [d for w in user["contributionsCollection"]["contributionCalendar"]["weeks"] for d in w.get("contributionDays", [])]
        current_streak, best_streak = compute_streaks(all_days)

    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    repos = user["repositories"]["nodes"]
    languages = compute_top_languages(repos, limit=5)

    repo_map = {r["name"]: r for r in repos}
    moon_1 = repo_map.get("Safe-C") or (repos[0] if repos else {})
    moon_2 = repo_map.get("Finance-and-Risk-Analysis") or (repos[1] if len(repos) > 1 else {})

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    (ASSETS_DIR / "solar-system.svg").write_text(render_solar_system(languages, comet_repo), encoding="utf-8")
    (ASSETS_DIR / "the-sun.svg").write_text(
        render_the_sun(
            name=user.get("name") or USERNAME,
            location=user.get("location") or "India",
            company=user.get("company") or "",
            followers=user["followers"]["totalCount"],
            repos=user["repositories"]["totalCount"],
        ),
        encoding="utf-8",
    )
    if moon_1:
        lang = moon_1.get("primaryLanguage") or {}
        (ASSETS_DIR / "moon-1.svg").write_text(
            render_moon_card(
                moon_label="MOON 01",
                title=moon_1.get("name", "Safe-C"),
                description=moon_1.get("description") or "",
                stars_count=moon_1.get("stargazerCount", 0),
                forks_count=moon_1.get("forkCount", 0),
                language=lang.get("name", "C++"),
                lang_color=lang.get("color") or "#f34b7d",
                planet_color="#f472b6",
            ),
            encoding="utf-8",
        )
    if moon_2:
        lang = moon_2.get("primaryLanguage") or {}
        (ASSETS_DIR / "moon-2.svg").write_text(
            render_moon_card(
                moon_label="MOON 02",
                title=moon_2.get("name", "Finance-and-Risk-Analysis"),
                description=moon_2.get("description") or "",
                stars_count=moon_2.get("stargazerCount", 0),
                forks_count=moon_2.get("forkCount", 0),
                language=lang.get("name", "Jupyter Notebook"),
                lang_color=lang.get("color") or "#da5b0b",
                planet_color="#f97316",
            ),
            encoding="utf-8",
        )
    (ASSETS_DIR / "planets.svg").write_text(render_planets_card(languages), encoding="utf-8")
    (ASSETS_DIR / "orbit-log.svg").write_text(
        render_orbit_log_card(weeks, current_streak, best_streak, cal["totalContributions"]),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
