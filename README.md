# Grafana Scraper to Supabase

This project scrapes data from a **Grafana** dashboard, processes the measurements (PM2.5, PM10, AQI), and inserts them into a **Supabase** database.

## Overview

- **Playwright** is used for browser automation, scraping the required data from a publicly accessible Grafana dashboard.
- The data (PM2.5, PM10, and AQI) is then stored in a **Supabase database**.
- **Browserless** is used for running headless browsers in the cloud to avoid the need to install and manage browsers locally.

## Features

- Scrapes **PM2.5**, **PM10**, and **AQI** data from Grafana.
- **Uploads** screenshots and HTML content to **Supabase Storage** (optional).
- Inserts the scraped data into a **Supabase database** (`medicion` table).
- Runs periodically via **cron jobs** in **Railway**.

## Prerequisites

1. **Supabase**: You need a **Supabase** project for storing data.
2. **Railway**: The service is deployed on **Railway** for cron job scheduling and hosting.
3. **Browserless**: For browser execution, the service is connected to **Browserless**, so the browser management is handled externally.

### Steps to Get Started

1. **Clone this repository**:

   ```bash
   git clone https://github.com/yourusername/grafana-scraper.git
   cd grafana-scraper
   ```

2. **Install the dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   Set the following environment variables:

   - **SUPABASE_URL**: The URL for your Supabase project.
   - **SUPABASE_KEY**: The Supabase service role key.
   - **BROWSER_PLAYWRIGHT_ENDPOINT**: The WebSocket URL for your Browserless instance.

   You can set these in a .env file or configure them directly in your Railway project.

   Example .env file:

   ```bash
   SUPABASE_URL=<your_supabase_url>
   SUPABASE_KEY=<your_supabase_service_key>
   BROWSER_PLAYWRIGHT_ENDPOINT=ws://<your_browserless_url>?token=<your_token>
   ```

4. **Deploy the Project on Railway**:

   - Push the project to your Railway account.
   - Set the cron schedule to run the script periodically. The current configuration runs the script every hour.

   Example railway.json configuration:

   ```bash
   {
    "$schema": "https://railway.com/railway.schema.json",
    "build": {
    "builder": "RAILPACK",
    "buildCommand": "pip install -r requirements.txt"
    },
    "deploy": {
    "startCommand": "python run.py",
    "cronSchedule": "0 \* \* \* \*"
    }
   }
   ```

5. **Check the Logs**:

   The script will print out logs, including the scraped data and any errors, which can be accessed in Railway Logs.

---

## How it Works

1. **Scraping Data**: The script uses Playwright to interact with a Grafana dashboard, wait for the page to load, and scrape PM2.5, PM10, and AQI values from the page.

2. **Saving to Supabase**:

   - The script checks if the station and contaminant exist in the Supabase database.
   - If they do not exist, they are created.
   - The measurements are inserted into the medicion table in Supabase with station_id, contaminant_id, and value.

3. **Uploading Debug Files** (Optional):

   - Screenshots and HTML dumps are optionally uploaded to Supabase Storage for debugging purposes.

4. **Cron Job**: The script is scheduled to run periodically (default: every hour) on Railway.

## Example Scraped Data

Once the data is scraped, it is formatted like this:

```bash
{
    "AMDC 21 de Octubre": {"PM2.5": "2", "PM10": "2", "AQI": 14},
    "AMDC Bomberos Juana Lainez": {"PM2.5": "9", "PM10": "9", "AQI": 24},
    "AMDC Kennedy": {"PM2.5": "3", "PM10": "3", "AQI": 25},
    "AMDC Planta Concepción": {"PM2.5": "0", "PM10": "0", "AQI": 0},
    "AMDC Planta Laureles": {"PM2.5": "6", "PM10": "7", "AQI": 23},
    "AMDC Planta Picacho": {"PM2.5": "1", "PM10": "2", "AQI": 3},
    "SAT AMDC: UMAPS": {"PM2.5": "7", "PM10": "8", "AQI": 33}
}
```

This data is inserted into the medicion table in Supabase, where each record corresponds to a station, contaminant, and measurement value.

## Troubleshooting

- **Missing Dependencies**: Ensure that all dependencies are listed in the requirements.txt file, including playwright, supabase, and httpx.
- **Environment Variables**: Double-check that the environment variables are correctly set in Railway or your local environment.
- **Logs**: Use railway logs to inspect logs and troubleshoot errors that occur during scraping.
