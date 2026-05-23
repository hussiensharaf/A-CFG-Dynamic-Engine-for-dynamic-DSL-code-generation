from app.etl.data.remote.gee.google_earth_api_data_collector import GoogleEarthAPIDataCollector

collector = GoogleEarthAPIDataCollector(projectname="gee-project-495216")
df = collector.collect(
    satellite="ERA5",
    start_date="2023-01-01",
    end_date="2023-01-10",
    longitude=31.2357,
    latitude=30.0444,
    scale=1000
)
print(df)