"""Fetch live GitHub stats and regenerate Pixel Studio SVG cards."""

from __future__ import annotations

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
    pullRequests {
      totalCount
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        name
        description
        stargazerCount
        primaryLanguage {
          name
          color
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
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
        "User-Agent": "pixel-studio-updater",
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


def fetch_recent_commits(limit: int = 5) -> list[str]:
    try:
        events = _request_json(f"https://api.github.com/users/{USERNAME}/events/public?per_page=30")
    except (urllib.error.URLError, TimeoutError):
        return []

    commits: list[str] = []
    for event in events:
        if event.get("type") != "PushEvent":
            continue
        repo_name = event.get("repo", {}).get("name", "").split("/")[-1]
        for commit in event.get("payload", {}).get("commits", []):
            msg = commit.get("message", "").splitlines()[0].strip()
            if msg:
                line = f"{repo_name}: {msg}"
                commits.append(line[:32] + ("..." if len(line) > 32 else ""))
            if len(commits) >= limit:
                return commits
    return commits


def compute_streaks(days: list[dict]) -> tuple[int, int]:
    """Return (current_streak, best_streak) from ordered contributionDays."""
    best = 0
    running = 0
    for day in days:
        if day["contributionCount"] > 0:
            running += 1
            best = max(best, running)
        else:
            running = 0

    # Current streak: count backwards from today (or yesterday if today has 0 so far)
    today_str = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    idx = len(days) - 1
    if idx >= 0 and days[idx]["date"] == today_str and days[idx]["contributionCount"] == 0:
        idx -= 1

    current = 0
    while idx >= 0 and days[idx]["contributionCount"] > 0:
        current += 1
        idx -= 1
    return current, best


def heat_color(count: int) -> str:
    if count <= 0:
        return "#21262d"
    if count <= 2:
        return "#0e4429"
    if count <= 5:
        return "#006d32"
    if count <= 9:
        return "#26a641"
    return "#39d353"


def render_pixel_room(commits: list[str]) -> str:
    lines = commits or [
        "Safe-C: Merge pull request #27",
        "Safe-C: docs: update GitHub Pages",
        "Safe-C: feat: add C89-C23 & C++08",
        "RTOS: feat: scheduler tick ISR",
        "RTOS: fix: ESP32 task stack align",
    ]
    # Duplicate lines for seamless loop
    loop_lines = lines[:5] * 2
    text_nodes = []
    for i, line in enumerate(loop_lines):
        y = 148 + i * 16
        text_nodes.append(f'      <text x="322" y="{y}">{escape(line)}</text>')
    commits_svg = "\n".join(text_nodes)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 380" width="840" height="380" shape-rendering="crispEdges">
  <defs>
    <pattern id="wallpaper" width="24" height="380" patternUnits="userSpaceOnUse">
      <rect width="12" height="380" fill="#181f30"/>
      <rect x="12" width="12" height="380" fill="#1d2538"/>
    </pattern>
    <clipPath id="screen-clip">
      <rect x="316" y="132" width="208" height="104" rx="2"/>
    </clipPath>
    <style>
      .commit-scroll {{ animation: scrollUp 12s linear infinite; }}
      .cat-z1 {{ animation: floatZ 3s ease-in-out infinite; }}
      .cat-z2 {{ animation: floatZ 3s ease-in-out 1.2s infinite; }}
      @keyframes scrollUp {{
        0% {{ transform: translateY(0px); }}
        100% {{ transform: translateY(-80px); }}
      }}
      @keyframes floatZ {{
        0%, 100% {{ opacity: 0.25; transform: translateY(0px); }}
        50% {{ opacity: 0.95; transform: translateY(-5px); }}
      }}
    </style>
  </defs>

  <rect width="840" height="380" rx="12" fill="url(#wallpaper)"/>
  <rect x="0" y="302" width="840" height="8" fill="#2c1d14"/>
  <rect x="0" y="310" width="840" height="70" fill="#462f20"/>
  <rect x="0" y="326" width="840" height="3" fill="#372418"/>
  <rect x="0" y="344" width="840" height="3" fill="#372418"/>
  <rect x="0" y="362" width="840" height="3" fill="#372418"/>

  <!-- Window -->
  <rect x="64" y="64" width="144" height="128" fill="#382519"/>
  <rect x="72" y="72" width="60" height="52" fill="#0b1021"/>
  <rect x="140" y="72" width="60" height="52" fill="#0b1021"/>
  <rect x="72" y="132" width="60" height="52" fill="#0d1428"/>
  <rect x="140" y="132" width="60" height="52" fill="#0d1428"/>
  <rect x="56" y="192" width="160" height="10" fill="#523724"/>
  <rect x="86" y="88" width="4" height="4" fill="#cbd5e1"/>
  <rect x="114" y="106" width="4" height="4" fill="#94a3b8"/>
  <rect x="154" y="84" width="4" height="4" fill="#cbd5e1"/>
  <rect x="92" y="148" width="4" height="4" fill="#64748b"/>
  <rect x="150" y="162" width="4" height="4" fill="#94a3b8"/>
  <rect x="168" y="96" width="16" height="16" fill="#f8fafc"/>
  <rect x="174" y="96" width="12" height="10" fill="#0b1021"/>

  <!-- Signboard -->
  <rect x="278" y="42" width="284" height="52" fill="#3b2618"/>
  <rect x="284" y="48" width="272" height="40" fill="#f3ebd8"/>
  <text x="420" y="75" text-anchor="middle" font-family="'Courier New', Consolas, monospace" font-size="24" font-weight="bold" letter-spacing="3" fill="#18181b">KUSH KELAIYA</text>

  <!-- Clock -->
  <circle cx="676" cy="84" r="26" fill="#2c1e16"/>
  <circle cx="676" cy="84" r="21" fill="#f3ebd8"/>
  <rect x="674" y="69" width="4" height="17" fill="#18181b"/>
  <rect x="674" y="82" width="13" height="4" fill="#18181b"/>

  <!-- Bookshelves -->
  <rect x="606" y="156" width="164" height="10" fill="#5c3d28"/>
  <rect x="616" y="120" width="14" height="36" fill="#e11d48"/>
  <rect x="632" y="126" width="12" height="30" fill="#2563eb"/>
  <rect x="646" y="116" width="14" height="40" fill="#06b6d4"/>
  <rect x="662" y="124" width="12" height="32" fill="#f59e0b"/>
  <rect x="676" y="120" width="14" height="36" fill="#10b981"/>
  <rect x="692" y="128" width="12" height="28" fill="#6366f1"/>
  <rect x="706" y="122" width="14" height="34" fill="#f97316"/>
  <rect x="606" y="216" width="164" height="10" fill="#5c3d28"/>
  <rect x="624" y="200" width="22" height="16" fill="#7c3aed"/>
  <rect x="720" y="196" width="18" height="20" fill="#475569"/>

  <!-- Desk & Lamp -->
  <rect x="242" y="248" width="356" height="14" fill="#68452d"/>
  <rect x="256" y="262" width="14" height="58" fill="#4f3320"/>
  <rect x="570" y="262" width="14" height="58" fill="#4f3320"/>
  <rect x="268" y="236" width="24" height="12" fill="#334155"/>
  <rect x="276" y="170" width="8" height="66" fill="#475569"/>
  <polygon points="262,146 298,146 306,172 254,172" fill="#eab308"/>
  <polygon points="258,172 302,172 314,210 246,210" fill="#fde047" opacity="0.12"/>

  <!-- Monitor -->
  <rect x="404" y="236" width="32" height="12" fill="#334155"/>
  <rect x="386" y="244" width="68" height="4" fill="#475569"/>
  <rect x="308" y="124" width="224" height="116" rx="4" fill="#334155"/>
  <rect x="316" y="132" width="208" height="100" fill="#090d16"/>
  <g clip-path="url(#screen-clip)" font-family="'Courier New', Consolas, monospace" font-size="9.5" fill="#4ade80">
    <g class="commit-scroll">
{commits_svg}
    </g>
  </g>

  <!-- Mug & Chair -->
  <rect x="526" y="226" width="20" height="22" fill="#e2e8f0"/>
  <rect x="546" y="232" width="6" height="10" fill="#cbd5e1"/>
  <rect x="444" y="262" width="52" height="12" fill="#334155"/>
  <rect x="464" y="274" width="12" height="36" fill="#1e293b"/>
  <rect x="446" y="308" width="48" height="6" fill="#1e293b"/>

  <!-- Plant -->
  <rect x="148" y="276" width="36" height="34" fill="#9a4b2b"/>
  <rect x="144" y="270" width="44" height="8" fill="#b45935"/>
  <rect x="163" y="232" width="6" height="38" fill="#15803d"/>
  <rect x="142" y="244" width="22" height="10" fill="#22c55e"/>
  <rect x="169" y="234" width="24" height="10" fill="#22c55e"/>
  <rect x="148" y="224" width="20" height="10" fill="#4ade80"/>

  <!-- Sleeping Cat -->
  <rect x="646" y="294" width="52" height="16" fill="#d97706"/>
  <rect x="692" y="284" width="20" height="18" fill="#f59e0b"/>
  <rect x="694" y="278" width="6" height="6" fill="#f59e0b"/>
  <rect x="706" y="278" width="6" height="6" fill="#f59e0b"/>
  <rect x="632" y="298" width="14" height="6" fill="#b45309"/>
  <text x="722" y="270" font-family="'Courier New', monospace" font-size="14" font-weight="bold" fill="#94a3b8" class="cat-z1">Z</text>
  <text x="734" y="256" font-family="'Courier New', monospace" font-size="11" font-weight="bold" fill="#64748b" class="cat-z2">z</text>
  <text x="822" y="366" text-anchor="end" font-family="'Courier New', monospace" font-size="10" fill="#94a3b8" opacity="0.6">pixel-studio</text>
</svg>
"""


def render_about_card(name: str, location: str, company: str, followers: int, repos: int) -> str:
    parts = [p for p in [location, company, f"{followers} followers", f"{repos} repositories"] if p]
    meta = escape("  ·  ".join(parts))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 165" width="840" height="165" shape-rendering="crispEdges">
  <rect x="1" y="1" width="838" height="163" rx="10" fill="#161b22" stroke="#30363d" stroke-width="1.5"/>
  <text x="28" y="34" font-family="'Courier New', Consolas, monospace" font-size="14" font-weight="bold" letter-spacing="1.5" fill="#4ade80">&gt; ABOUT</text>
  <text x="28" y="68" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="24" font-weight="700" fill="#f0f6fc">{escape(name)}</text>
  <text x="28" y="96" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="14" fill="#c9d1d9">Embedded &amp; OS developer. Building a custom RTOS for Arduino &amp; ESPs right now.</text>
  <text x="28" y="136" font-family="'Courier New', Consolas, monospace" font-size="12" fill="#8b949e">{meta}</text>

  <rect x="706" y="24" width="108" height="108" rx="4" fill="#0d1117" stroke="#30363d" stroke-width="2"/>
  <rect x="714" y="32" width="92" height="92" fill="#ffffff"/>
  <rect x="720" y="38" width="16" height="16" fill="#ec84a7"/>
  <rect x="784" y="38" width="16" height="16" fill="#ec84a7"/>
  <rect x="736" y="54" width="16" height="16" fill="#ec84a7"/>
  <rect x="768" y="54" width="16" height="16" fill="#ec84a7"/>
  <rect x="752" y="70" width="16" height="16" fill="#ec84a7"/>
  <rect x="720" y="86" width="16" height="16" fill="#ec84a7"/>
  <rect x="736" y="86" width="16" height="16" fill="#ec84a7"/>
  <rect x="768" y="86" width="16" height="16" fill="#ec84a7"/>
  <rect x="784" y="86" width="16" height="16" fill="#ec84a7"/>
  <rect x="720" y="102" width="16" height="16" fill="#ec84a7"/>
  <rect x="784" y="102" width="16" height="16" fill="#ec84a7"/>
</svg>
"""


def render_stats_bar(commits: int, prs: int, stars: int, best_streak: int) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 86" width="840" height="86">
  <rect x="1" y="1" width="838" height="84" rx="10" fill="#161b22" stroke="#30363d" stroke-width="1.5"/>
  <text x="40" y="42" font-family="'Courier New', Consolas, monospace" font-size="24" font-weight="bold" fill="#f0f6fc">{commits}</text>
  <text x="40" y="64" font-family="'Courier New', Consolas, monospace" font-size="11" letter-spacing="1.2" fill="#8b949e">COMMITS</text>

  <text x="250" y="42" font-family="'Courier New', Consolas, monospace" font-size="24" font-weight="bold" fill="#f0f6fc">{prs}</text>
  <text x="250" y="64" font-family="'Courier New', Consolas, monospace" font-size="11" letter-spacing="1.2" fill="#8b949e">PULL REQS</text>

  <text x="460" y="42" font-family="'Courier New', Consolas, monospace" font-size="24" font-weight="bold" fill="#f0f6fc">{stars}</text>
  <text x="460" y="64" font-family="'Courier New', Consolas, monospace" font-size="11" letter-spacing="1.2" fill="#8b949e">STARS</text>

  <text x="670" y="42" font-family="'Courier New', Consolas, monospace" font-size="24" font-weight="bold" fill="#f0f6fc">{best_streak}D</text>
  <text x="670" y="64" font-family="'Courier New', Consolas, monospace" font-size="11" letter-spacing="1.2" fill="#8b949e">BEST STREAK</text>
</svg>
"""


def render_project_card(
    title: str,
    description: str,
    stars: int,
    language: str,
    lang_color: str,
    variant: str,
) -> str:
    wrapped = textwrap.wrap(description or "No description provided.", width=34)[:3]
    if len(wrapped) == 3 and len(description or "") > 100:
        wrapped[2] = wrapped[2][:31].rstrip() + "..."
    desc_lines = "\n".join(
        f'  <text x="102" y="{58 + i * 17}" font-family="-apple-system, BlinkMacSystemFont, \'Segoe UI\', Helvetica, Arial, sans-serif" font-size="12" fill="#8b949e">{escape(line)}</text>'
        for i, line in enumerate(wrapped)
    )

    if variant == "pink":
        icon = """  <rect x="20" y="22" width="64" height="64" rx="6" fill="#6b103f"/>
  <rect x="32" y="34" width="12" height="12" fill="#f472b6"/>
  <rect x="60" y="34" width="12" height="12" fill="#f472b6"/>
  <rect x="44" y="46" width="16" height="12" fill="#fbcfe8"/>
  <rect x="32" y="58" width="40" height="12" fill="#f472b6"/>
  <rect x="44" y="70" width="16" height="8" fill="#ec4899"/>"""
    else:
        icon = """  <rect x="20" y="22" width="64" height="64" rx="6" fill="#5c280a"/>
  <rect x="30" y="32" width="44" height="10" fill="#f97316"/>
  <rect x="30" y="42" width="12" height="22" fill="#fb923c"/>
  <rect x="62" y="42" width="12" height="22" fill="#fb923c"/>
  <rect x="42" y="48" width="20" height="10" fill="#fdba74"/>
  <rect x="36" y="66" width="32" height="10" fill="#ea580c"/>"""

    lang_x = max(250, 392 - len(language) * 6 - 12)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 412 140" width="412" height="140" shape-rendering="crispEdges">
  <rect x="1" y="1" width="410" height="138" rx="10" fill="#161b22" stroke="#30363d" stroke-width="1.5"/>
{icon}
  <text x="102" y="38" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="15" font-weight="700" fill="#f0f6fc">{escape(title)}</text>
{desc_lines}
  <text x="102" y="120" font-family="'Courier New', Consolas, monospace" font-size="12" fill="#4ade80">★ {stars}</text>
  <circle cx="{lang_x}" cy="116" r="5" fill="{escape(lang_color)}"/>
  <text x="{lang_x + 11}" y="120" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="12" fill="#8b949e">{escape(language)}</text>
</svg>
"""


def render_activity_card(weeks: list[dict], current_streak: int, best_streak: int, total_year: int) -> str:
    recent_weeks = weeks[-24:]
    cells = []
    for col, week in enumerate(recent_weeks):
        days = week.get("contributionDays", [])
        for row in range(5):
            # Pick 5 days evenly or first 5 weekdays for compact 24x5 pixel grid
            count = days[row]["contributionCount"] if row < len(days) else 0
            x = col * 18
            y = row * 18
            cells.append(f'    <rect x="{x}" y="{y}" width="14" height="14" rx="2" fill="{heat_color(count)}"/>')
    grid_svg = "\n".join(cells)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 165" width="840" height="165" shape-rendering="crispEdges">
  <rect x="1" y="1" width="838" height="163" rx="10" fill="#161b22" stroke="#30363d" stroke-width="1.5"/>
  <text x="28" y="34" font-family="'Courier New', Consolas, monospace" font-size="14" font-weight="bold" letter-spacing="1.5" fill="#4ade80">&gt; ACTIVITY</text>

  <g transform="translate(28, 52)">
{grid_svg}
  </g>

  <text x="530" y="56" font-family="'Courier New', Consolas, monospace" font-size="10" letter-spacing="1" fill="#8b949e">CURRENT STREAK</text>
  <text x="530" y="74" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="16" font-weight="700" fill="#f0f6fc">{current_streak} days</text>

  <text x="530" y="98" font-family="'Courier New', Consolas, monospace" font-size="10" letter-spacing="1" fill="#8b949e">BEST STREAK</text>
  <text x="530" y="116" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="16" font-weight="700" fill="#f0f6fc">{best_streak} days</text>

  <text x="530" y="138" font-family="'Courier New', Consolas, monospace" font-size="10" letter-spacing="1" fill="#8b949e">THIS YEAR</text>
  <text x="530" y="154" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="16" font-weight="700" fill="#f0f6fc">{total_year}</text>
</svg>
"""


def main() -> None:
    user = fetch_graphql_stats()
    commits = fetch_recent_commits(limit=5)

    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    all_days = [d for w in weeks for d in w.get("contributionDays", [])]
    current_streak, best_streak = compute_streaks(all_days)

    repos = user["repositories"]["nodes"]
    total_stars = sum(r.get("stargazerCount", 0) for r in repos)
    total_commits = (
        user["contributionsCollection"]["totalCommitContributions"]
        + user["contributionsCollection"]["restrictedContributionsCount"]
    )
    total_prs = user["pullRequests"]["totalCount"]

    repo_map = {r["name"]: r for r in repos}
    safe_c = repo_map.get("Safe-C") or (repos[0] if repos else {})
    finance = repo_map.get("Finance-and-Risk-Analysis") or (repos[1] if len(repos) > 1 else {})

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    (ASSETS_DIR / "pixel-room.svg").write_text(render_pixel_room(commits), encoding="utf-8")
    (ASSETS_DIR / "about-card.svg").write_text(
        render_about_card(
            name=user.get("name") or USERNAME,
            location=user.get("location") or "India",
            company=user.get("company") or "",
            followers=user["followers"]["totalCount"],
            repos=user["repositories"]["totalCount"],
        ),
        encoding="utf-8",
    )
    (ASSETS_DIR / "stats-bar.svg").write_text(
        render_stats_bar(total_commits, total_prs, total_stars, best_streak),
        encoding="utf-8",
    )
    if safe_c:
        lang = safe_c.get("primaryLanguage") or {}
        (ASSETS_DIR / "project-safe-c.svg").write_text(
            render_project_card(
                title=safe_c.get("name", "Safe-C"),
                description=safe_c.get("description") or "",
                stars=safe_c.get("stargazerCount", 0),
                language=lang.get("name", "C++"),
                lang_color=lang.get("color") or "#f34b7d",
                variant="pink",
            ),
            encoding="utf-8",
        )
    if finance:
        lang = finance.get("primaryLanguage") or {}
        (ASSETS_DIR / "project-finance.svg").write_text(
            render_project_card(
                title=finance.get("name", "Finance-and-Risk-Analysis"),
                description=finance.get("description") or "",
                stars=finance.get("stargazerCount", 0),
                language=lang.get("name", "Jupyter Notebook"),
                lang_color=lang.get("color") or "#da5b0b",
                variant="orange",
            ),
            encoding="utf-8",
        )
    (ASSETS_DIR / "activity-card.svg").write_text(
        render_activity_card(weeks, current_streak, best_streak, cal["totalContributions"]),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
