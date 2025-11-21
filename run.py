import os
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
import asyncpg

# ---------------------------------------------------------
# ENV VARS (Railway / .env)
# ---------------------------------------------------------
DB_URL = os.getenv("DB_AMBIENTAL_URL")              # Postgres connection string
BROWSER_ENDPOINT = os.getenv("BROWSER_PLAYWRIGHT_ENDPOINT")

if not DB_URL:
    raise ValueError("DB_AMBIENTAL_URL is not set")
if not BROWSER_ENDPOINT:
    raise ValueError("BROWSER_PLAYWRIGHT_ENDPOINT is not set")

# ---------------------------------------------------------
# DB HELPERS
# ---------------------------------------------------------
async def get_db():
    return await asyncpg.connect(DB_URL)

async def get_or_create_estacion(conn, name):
    name = name.replace("AMDC ", "").strip()
    row = await conn.fetchrow("SELECT * FROM estacion WHERE nombre=$1", name)
    if row:
        print("[INFO] Station exists:", name)
        return row

    print("[INFO] Creating station:", name)
    return await conn.fetchrow(
        "INSERT INTO estacion (nombre, fuente) VALUES ($1, 'AMDC') RETURNING *",
        name,
    )

async def get_or_create_contaminante(conn, name):
    row = await conn.fetchrow("SELECT * FROM contaminante WHERE nombre=$1", name)
    if row:
        print("[INFO] Contaminant exists:", name)
        return row

    print("[INFO] Creating contaminant:", name)
    return await conn.fetchrow(
        "INSERT INTO contaminante (nombre) VALUES ($1) RETURNING *",
        name,
    )

async def insert_medicion(conn, estacion_id, contaminante_id, value):
    try:
        value = float(str(value).replace(",", "."))
    except:
        print("[ERROR] Invalid value:", value)
        return

    now_utc = datetime.utcnow().isoformat()

    print(f"[INFO] Insert medida: est={estacion_id}, cont={contaminante_id}, value={value}")

    await conn.execute(
        """
        INSERT INTO medicion (estacion_id, contaminante_id, valor, fecha)
        VALUES ($1, $2, $3, $4)
        """,
        estacion_id, contaminante_id, value, now_utc,
    )

# ---------------------------------------------------------
# PAGE SCRAPING
# ---------------------------------------------------------
async def load_grafana_and_scrape(page):
    url = "https://estaciones.simet.amdc.hn/public-dashboards/e4d697a0e31647008370b09a592c0129?orgId=1&from=now-24h&to=now"
    print("Navigating:", url)

    await page.goto(url, timeout=180_000, wait_until="domcontentloaded")
    await page.wait_for_load_state("networkidle", timeout=180_000)

    # PAGE DATA
    stations_data = {}

    # PM2.5
    pm25_st_names = await page.query_selector_all("section[data-testid*='Material Particulado 2.5'] div[style*='text-align: center;']")
    pm25_st_values = await page.query_selector_all("section[data-testid*='Material Particulado 2.5'] span.flot-temp-elem")

    for s, v in zip(pm25_st_names, pm25_st_values):
        name = await s.inner_text()
        value = await v.inner_text()
        stations_data[name] = {"PM2.5": value}

    # PM10
    pm10_st_names = await page.query_selector_all("section[data-testid*='Material Particulado 10'] div[style*='text-align: center;']")
    pm10_st_values = await page.query_selector_all("section[data-testid*='Material Particulado 10'] span.flot-temp-elem")

    for s, v in zip(pm10_st_names, pm10_st_values):
        name = await s.inner_text()
        stations_data.setdefault(name, {})
        stations_data[name]["PM10"] = await v.inner_text()

    # AQI
    try:
        aqi_items = await page.query_selector_all("div[data-testid='data-testid Bar gauge value'] span")
        for idx, station in enumerate(stations_data.keys()):
            try:
                stations_data[station]["AQI"] = int(await aqi_items[idx].inner_text())
            except:
                stations_data[station]["AQI"] = None
    except Exception as e:
        print("AQI error:", e)

    print("Scraped stations:", stations_data)
    return stations_data

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
async def run():
    conn = await get_db()

    async with async_playwright() as p:
        browser = await p.chromium.connect(BROWSER_ENDPOINT)
        page = await browser.new_page(ignore_https_errors=True)
        data = await load_grafana_and_scrape(page)

        # SAVE TO DB
        for station_name, contaminants in data.items():
            est = await get_or_create_estacion(conn, station_name)

            for cont_name, cont_value in contaminants.items():
                cont = await get_or_create_contaminante(conn, cont_name)
                await insert_medicion(conn, est["id"], cont["id"], cont_value)

        await browser.close()
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run())
