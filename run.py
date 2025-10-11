import os
import asyncio
from datetime import datetime
from supabase import create_client
from playwright.async_api import async_playwright

# Environment variables (to be configured in Railway or your local environment)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  
BROWSER_ENDPOINT = os.getenv("BROWSER_PLAYWRIGHT_ENDPOINT")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL or SUPABASE_SERVICE_KEY is not set")
if not BROWSER_ENDPOINT:
    raise ValueError("BROWSER_PLAYWRIGHT_ENDPOINT is not set")

# Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Function to normalize station names (removes unwanted parts)
def normalize_station_name(name: str) -> str:
    return name.replace("AMDC ", "").strip()

# Function to load Grafana and capture screenshot
async def load_grafana_and_grab(page):
    url = "https://estaciones.simet.amdc.hn/public-dashboards/e4d697a0e31647008370b09a592c0129?orgId=1&from=now-24h&to=now"
    print("Navigating to:", url)

    # Go to Grafana dashboard and wait for the page to load
    await page.goto(url, timeout=180_000, wait_until="domcontentloaded")
    await page.wait_for_load_state("networkidle", timeout=180_000)

    # Set viewport size for better clarity
    await page.set_viewport_size({"width": 5120, "height": 2880})

    html = await page.content()
    with open("scraping_dump.html", "w", encoding="utf-8") as f:
        f.write(html[:200000])  # Save a portion of HTML
    print("HTML dump saved as scraping_dump.html")

# Function to get or create a station in Supabase
def get_or_create_estacion(station_name):
    station_name = normalize_station_name(station_name)
    response = supabase.table("estacion").select("*").eq("nombre", station_name).maybe_single().execute()
    row = response.data
    if not row:
        print(f"[INFO] Creating station: {station_name}")
        insert = supabase.table("estacion").insert({"nombre": station_name, "fuente": "AMDC"}).execute()
        row = insert.data[0]
    else:
        print(f"[INFO] Station already exists: {station_name}")
    return row

# Function to get or create a contaminant in Supabase
def get_or_create_contaminante(contaminante_name):
    response = supabase.table("contaminante").select("*").eq("nombre", contaminante_name).maybe_single().execute()
    row = response.data
    if not row:
        print(f"[INFO] Creating contaminant: {contaminante_name}")
        insert = supabase.table("contaminante").insert({"nombre": contaminante_name}).execute()
        row = insert.data[0]
    else:
        print(f"[INFO] Contaminant already exists: {contaminante_name}")
    return row

# Function to create a measurement in Supabase
def create_medicion(estacion_id, contaminante_id, contaminante_value):
    try:
        value = float(str(contaminante_value).replace(",", "."))
    except Exception as e:
        print(f"[ERROR] Invalid value: {contaminante_value}, Error: {e}")
        return
    now_utc = datetime.now().isoformat()
    print(f"[INFO] Inserting measurement: Station ID={estacion_id}, Contaminant ID={contaminante_id}, Value={value}")
    supabase.table("medicion").insert({
        "estacion_id": estacion_id,
        "contaminante_id": contaminante_id,
        "valor": value,
        "fecha": now_utc
    }).execute()

# Main function to scrape data from Grafana and capture necessary data
async def run():
    stations_data = {}

    # Connect to Browserless using the environment variable
    async with async_playwright() as p:
        browser = await p.chromium.connect(BROWSER_ENDPOINT)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080}, ignore_https_errors=True)

        # Load Grafana and capture debug info
        await load_grafana_and_grab(page)

        # Scraping PM2.5 data
        pm25_stations = await page.query_selector_all("section[data-testid*='Material Particulado 2.5'] div[style*='text-align: center;']")
        pm25_values = await page.query_selector_all("section[data-testid*='Material Particulado 2.5'] span.flot-temp-elem")
        for s, v in zip(pm25_stations, pm25_values):
            station_name = await s.inner_text()
            pm25_value = await v.inner_text()
            stations_data[station_name] = {"PM2.5": pm25_value}

        # Scraping PM10 data
        pm10_stations = await page.query_selector_all("section[data-testid*='Material Particulado 10'] div[style*='text-align: center;']")
        pm10_values = await page.query_selector_all("section[data-testid*='Material Particulado 10'] span.flot-temp-elem")
        for s, v in zip(pm10_stations, pm10_values):
            name = await s.inner_text()
            stations_data.setdefault(name, {})  # Create station if not exist
            stations_data[name]["PM10"] = await v.inner_text()

        # Scraping AQI data
        try:
            aqi_stations = await page.query_selector_all("div[data-testid='data-testid Bar gauge value'] span")
            for idx, station in enumerate(stations_data.keys()):
                try:
                    stations_data[station]["AQI"] = int(await aqi_stations[idx].inner_text())
                except:
                    stations_data[station]["AQI"] = None
        except Exception as e:
            print("Error AQI:", e)

        # Print out the scraped data for debugging
        print("Stations scraped:", stations_data)

        # Save the data to the Supabase database
        for station_name, data in stations_data.items():
            normalized_name = normalize_station_name(station_name)

            # Get or create the station in Supabase
            estacion = get_or_create_estacion(station_name)

            for contaminante_name, contaminante_value in data.items():
                # Get or create the contaminant in Supabase
                contaminante = get_or_create_contaminante(contaminante_name)

                # Insert the measurement data into Supabase
                create_medicion(estacion["id"], contaminante["id"], contaminante_value)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
