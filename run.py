import os
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from supabase import create_client

# Variables de entorno (debes configurarlas en Railway o en tu entorno local)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # La clave con rol de servicio
GRAFANA_URL = os.getenv("GRAFANA_URL", "https://estaciones.simet.amdc.hn/public-dashboards/e4d697a0e31647008370b09a592c0129?orgId=1&from=now-24h&to=now")

# Conexión a Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Función para normalizar el nombre de la estación
def normalize_station_name(name: str) -> str:
    return name.replace("AMDC ", "").strip()

# Función para cargar el dashboard de Grafana
async def load_grafana_and_grab(page):
    await page.goto(GRAFANA_URL, timeout=180_000, wait_until="domcontentloaded")
    await page.wait_for_load_state("networkidle", timeout=180_000)
    await page.set_viewport_size({"width": 1920, "height": 1080})

# Función para hacer scraping de los datos de la página
async def scrape(page):
    data = {}
    # Scraping PM2.5
    pm25_stations = await page.query_selector_all("section[data-testid*='Material Particulado 2.5'] div[style*='text-align: center;']")
    pm25_values = await page.query_selector_all("section[data-testid*='Material Particulado 2.5'] span.flot-temp-elem")
    for s, v in zip(pm25_stations, pm25_values):
        name = (await s.inner_text()).strip()
        val = (await v.inner_text()).strip()
        data[name] = {"PM2.5": val}

    # Scraping PM10
    pm10_stations = await page.query_selector_all("section[data-testid*='Material Particulado 10'] div[style*='text-align: center;']")
    pm10_values = await page.query_selector_all("section[data-testid*='Material Particulado 10'] span.flot-temp-elem")
    for s, v in zip(pm10_stations, pm10_values):
        name = (await s.inner_text()).strip()
        val = (await v.inner_text()).strip()
        data.setdefault(name, {})
        data[name]["PM10"] = val

    # Scraping AQI
    try:
        aqi_values = await page.query_selector_all("div[data-testid='data-testid Bar gauge value'] span")
        for idx, name in enumerate(list(data.keys())):
            try:
                data[name]["AQI"] = int((await aqi_values[idx].inner_text()).strip())
            except Exception:
                data[name]["AQI"] = None
    except Exception as e:
        print("AQI scrape warn:", repr(e))

    return data

# Función para obtener o crear una estación
def get_or_create_estacion(nombre: str):
    nombre_n = normalize_station_name(nombre)
    r = supabase.table("estacion").select("*").eq("nombre", nombre_n).maybe_single().execute()
    row = r.data
    if not row:
        print(f"[INFO] Creando estación: {nombre_n}")  # Debugging log
        ins = supabase.table("estacion").insert({"nombre": nombre_n, "fuente": "AMDC"}).execute()
        row = ins.data[0]
    else:
        print(f"[INFO] Estación existente: {nombre_n}")  # Debugging log
    return row  # dict con id, nombre, etc.

# Función para obtener o crear un contaminante
def get_or_create_contaminante(nombre: str):
    r = supabase.table("contaminante").select("*").eq("nombre", nombre).maybe_single().execute()
    row = r.data
    if not row:
        print(f"[INFO] Creando contaminante: {nombre}")  # Debugging log
        ins = supabase.table("contaminante").insert({"nombre": nombre}).execute()
        row = ins.data[0]
    else:
        print(f"[INFO] Contaminante existente: {nombre}")  # Debugging log
    return row

# Función para crear una medición
def create_medicion(estacion_id: int, contaminante_id: int, valor):
    try:
        v = float(str(valor).replace(",", "."))
    except Exception as e:
        print(f"[ERROR] Valor inválido: {valor}, Error: {e}")  # Debugging log
        return
    now_utc = datetime.now().isoformat()
    print(f"[INFO] Insertando medición: Estación ID={estacion_id}, Contaminante ID={contaminante_id}, Valor={v}")  # Debugging log
    supabase.table("medicion").insert({
        "estacion_id": estacion_id,
        "contaminante_id": contaminante_id,
        "valor": v,
        "fecha": now_utc
    }).execute()

# Función principal que maneja el scraping y guarda en la base de datos
async def run():
    async with async_playwright() as p:
       
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page(ignore_https_errors=True)

        await load_grafana_and_grab(page)
        stations_data = await scrape(page)
        print("Stations scraped:", stations_data)

        # Guardar los datos en la base de datos
        for station_name, measures in stations_data.items():
            est = get_or_create_estacion(station_name)
            for contaminante_name, contaminante_value in measures.items():
                cont = get_or_create_contaminante(contaminante_name)
                if contaminante_value is not None:
                    create_medicion(est["id"], cont["id"], contaminante_value)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
