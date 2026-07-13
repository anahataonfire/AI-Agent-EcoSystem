import { NextRequest, NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";
import path from "path";

const execAsync = promisify(exec);

/**
 * Weather Trading API Route
 * 
 * Runs the Python weather scanner and returns results.
 */

export async function GET(request: NextRequest) {
    const searchParams = request.nextUrl.searchParams;
    const cities = searchParams.get("cities") || "nyc,london";
    const minEdge = searchParams.get("min_edge") || "0.15";
    const useLive = searchParams.get("live") === "true";

    try {
        if (useLive) {
            // Run the actual Python scanner
            // HARDCODED absolute path to verify backend location regardless of where frontend runs
            const projectRoot = "/Users/adamc/Documents/001 AI Agents/AI Agent EcoSystem 2.0";
            const venvPython = path.join(projectRoot, ".venv", "bin", "python");

            // Quote the executable path to handle spaces in "001 AI Agents"
            const cmd = `"${venvPython}" -c "
import json
import sys
import traceback

# Wrap entire script in try-except to always output valid JSON
try:
    sys.path.insert(0, '${projectRoot}')
    from src.weather_trading.forecaster import WeatherForecaster
    from src.weather_trading.browser_scraper import get_scraped_markets
    from src.weather_trading.edge_calculator import EdgeCalculator
    from src.weather_trading.config import WEATHER_CITIES
    from datetime import date, timedelta

    cities = '${cities}'.split(',')
    forecaster = WeatherForecaster()
    calculator = EdgeCalculator()

    # Get forecasts
    forecasts = []
    for city in cities:
        try:
            # Use str(date.today()) to get YYYY-MM-DD format
            fc = forecaster.get_daily_high_forecast(city, str(date.today()))
            if fc:
                forecasts.append({
                    'city': city,
                    'temp': round(fc.high_f),  # Use high_f
                    'unit': 'F',
                    'confidence': fc.confidence,
                    'ecmwf': fc.ecmwf_high,
                    'gfs': fc.gfs_high,
                    'nws': fc.nws_high
                })
            else:
                print(f'No forecasts found for {city} on {date.today()}', file=sys.stderr)
        except Exception as e:
            print(f'Error fetching forecast for {city}: {e}', file=sys.stderr)

    # Get markets
    try:
        scraped = get_scraped_markets()
    except Exception as e:
        print(f'Error scraping markets: {e}', file=sys.stderr)
        scraped = []

    opportunities = []
    today = str(date.today())

    for m in scraped:
        if m.city_key not in cities:
            continue
        
        # Skip resolved/past markets
        if m.target_date < today:
            continue
        
        # Skip TODAY's markets - by afternoon the temperature is known, market is resolved
        if m.target_date == today:
            continue
        
        # Skip effectively resolved markets (price near 0% or 100%)
        if m.yes_price < 0.02 or m.yes_price > 0.98:
            continue
        
        # Find matching forecast
        fc = next((f for f in forecasts if f['city'] == m.city_key), None)
        if not fc:
            continue
        
        # Normalize units (Forecast is F by default, Market might be C)
        forecast_temp = fc['temp']
        market_unit = m.bucket_unit
        
        if market_unit == 'C' and fc['unit'] == 'F':
            forecast_temp = (forecast_temp - 32) * 5 / 9
        
        # Get std deviation from model spread or use default
        std_dev = 3.0  # Default uncertainty
        if fc.get('ecmwf') and fc.get('gfs'):
            # Use model spread as uncertainty proxy
            spread = abs(fc.get('ecmwf', 0) - fc.get('gfs', 0))
            std_dev = max(2.0, min(8.0, spread / 2 + 1.5))
        elif fc.get('confidence', 0.7) < 0.7:
            std_dev = 4.0  # Higher uncertainty if low confidence
        
        # Calculate probability using normal distribution CDF
        import math
        def norm_cdf(x, mean, std):
            if std <= 0:
                return 1.0 if x >= mean else 0.0
            z = (x - mean) / (std * math.sqrt(2))
            return 0.5 * (1 + math.erf(z))
        
        # Handle -inf/inf bounds for 'or below'/'or above' buckets
        bucket_low = m.bucket_low if m.bucket_low != float('-inf') else forecast_temp - 50
        bucket_high = m.bucket_high if m.bucket_high != float('inf') else forecast_temp + 50
        
        # P(bucket_low <= temp <= bucket_high)
        prob_high = norm_cdf(bucket_high + 0.5, forecast_temp, std_dev)
        prob_low = norm_cdf(bucket_low - 0.5, forecast_temp, std_dev)
        calculated_prob = max(0.0, min(1.0, prob_high - prob_low))
        
        edge = calculated_prob - m.yes_price
        
        opportunities.append({
            'city': m.city_key,
            'city_name': WEATHER_CITIES.get(m.city_key, {}).get('name', m.city_key),
            'target_date': m.target_date,
            'bucket_low': m.bucket_low if m.bucket_low != float('-inf') else -999,
            'bucket_high': m.bucket_high if m.bucket_high != float('inf') else 999,
            'bucket_unit': m.bucket_unit,
            'forecast_temp': round(forecast_temp, 1),
            'forecast_confidence': fc['confidence'],
            'market_price': m.yes_price,
            'calculated_probability': calculated_prob,
            'edge': edge,
            'liquidity': m.liquidity,
            'hours_remaining': 24,
            'market_url': f'https://polymarket.com/market/{m.slug}'
        })

    result = {
        'scan_time': str(date.today()),
        'cities': cities,
        'forecasts': forecasts,
        'opportunities': sorted(opportunities, key=lambda x: -x['edge'])
    }
    print(json.dumps(result))

except Exception as e:
    # Output valid JSON even on error
    error_result = {
        'scan_time': str(date.today()) if 'date' in dir() else 'unknown',
        'cities': cities if 'cities' in dir() else [],
        'forecasts': forecasts if 'forecasts' in dir() else [],
        'opportunities': [],
        'error': str(e)
    }
    print(json.dumps(error_result))
"`;

            const { stdout, stderr } = await execAsync(cmd, {
                timeout: 120000,
                maxBuffer: 10 * 1024 * 1024
            });

            if (stderr && !stdout) {
                console.error("Scanner stderr:", stderr);
            }

            const data = JSON.parse(stdout.trim());
            return NextResponse.json(data);
        }

        // Demo data when not using live scanner
        const demoData = {
            scan_time: new Date().toISOString(),
            cities: cities.split(","),
            forecasts: [
                { city: "nyc", temp: 53, unit: "F", confidence: 0.9 },
                { city: "london", temp: 9, unit: "C", confidence: 0.7 },
            ].filter(f => cities.includes(f.city)),
            opportunities: [
                {
                    city: "nyc",
                    city_name: "New York City",
                    target_date: new Date().toISOString().split("T")[0],
                    bucket_low: 50,
                    bucket_high: 51,
                    bucket_unit: "F",
                    forecast_temp: 53,
                    forecast_confidence: 0.9,
                    market_price: 0.94,
                    calculated_probability: 0.45,
                    edge: -0.49,
                    liquidity: 560,
                    hours_remaining: 8.5,
                    market_url: "https://polymarket.com/event/highest-temp-nyc",
                },
                {
                    city: "london",
                    city_name: "London",
                    target_date: new Date().toISOString().split("T")[0],
                    bucket_low: 9,
                    bucket_high: 999,
                    bucket_unit: "C",
                    forecast_temp: 9,
                    forecast_confidence: 0.7,
                    market_price: 0.93,
                    calculated_probability: 0.70,
                    edge: -0.23,
                    liquidity: 1026,
                    hours_remaining: 12.2,
                    market_url: "https://polymarket.com/event/highest-temp-london",
                },
            ].filter(o => cities.includes(o.city)),
        };

        return NextResponse.json(demoData);
    } catch (error: any) {
        console.error("Scanner error:", error);
        return NextResponse.json(
            { error: error.message || "Failed to scan markets" },
            { status: 500 }
        );
    }
}

export const dynamic = 'force-dynamic';
export const maxDuration = 120;
