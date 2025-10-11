import os
import asyncio
from datetime import datetime
from supabase import create_client
from playwright.async_api import async_playwright

# Environment variables (to be configured in Railway or your local environment)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # The service role key
BROWSER_ENDPOINT = os.getenv("BROWSER_PLAYWRIGHT_ENDPOINT")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL or SUPABASE_SERVICE_KEY is not set")
if not BROWSER_ENDPOINT:
    raise ValueError("BROWSER_PLAYWRIGHT_ENDPOINT is not set")

# Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Function to upload a file to Supabase Storage
async def upload_to_supabase(filename, file_data):
    try:
        # Upload the file to Supabase Storage (create bucket if it doesn't exist)
        bucket = supabase.storage.from_("debug_files")  # "debug_files" is the bucket you created in Supabase
        bucket.upload(filename, file_data)
        print(f"[INFO] {filename} uploaded to Supabase.")
    except Exception as e:
        print(f"[ERROR] Failed to upload {filename}: {e}")

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

    # Take a screenshot and save it as bytes
    screenshot = await page.screenshot(full_page=True)  # Save screenshot as bytes
    await upload_to_supabase("scraping_test.png", screenshot)  # Upload screenshot to Supabase

    # Get HTML content for debugging (only save a portion)
    html = await page.content()
    await upload_to_supabase("scraping_dump.html", html.encode('utf-8'))  # Upload HTML dump to Supabase

    print("Screenshot and HTML dump uploaded to Supabase")

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

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
