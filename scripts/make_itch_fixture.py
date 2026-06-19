"""One-off script: fetches live itch.io page and saves a trimmed fixture."""
import requests
from bs4 import BeautifulSoup
from pathlib import Path

resp = requests.get(
    "https://itch.io/games/tag-incremental",
    headers={"User-Agent": "idle-market-analysis/0.1"},
    timeout=30,
)
assert resp.status_code == 200, f"HTTP {resp.status_code}"

soup = BeautifulSoup(resp.text, "lxml")
cells = soup.select("div.game_cell")

free_cells = []
paid_cells = []
for cell in cells:
    price_el = cell.select_one(".price_value")
    if price_el and not paid_cells:
        paid_cells.append(cell)
    elif not price_el and len(free_cells) < 2:
        free_cells.append(cell)
    if len(free_cells) >= 2 and paid_cells:
        break

selected = free_cells + paid_cells
print(f"Selected {len(selected)} cells: {len(free_cells)} free, {len(paid_cells)} paid")

fixture_html = '<!DOCTYPE html><html><body><div class="game_grid_widget">\n'
for c in selected:
    fixture_html += str(c) + "\n"
fixture_html += "</div></body></html>"

out = Path("tests/scrapers/fixtures/itch_browse.html")
out.write_text(fixture_html, encoding="utf-8")
print("Fixture saved:", out)
print("File size:", len(fixture_html), "chars")

# Verify parseable
s2 = BeautifulSoup(fixture_html, "lxml")
cells2 = s2.select("div.game_cell")
print("Cells in fixture:", len(cells2))
for c in cells2:
    t = c.select_one("a.title.game_link")
    p = c.select_one(".price_value")
    print(
        "  name:", t.get_text(strip=True) if t else "NONE",
        " | price:", p.get_text(strip=True) if p else "None",
    )
