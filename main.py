import asyncio
import pandas as pd
from PropertyCardScraper import PropertyCardScraper
from OfficeCardScraper import OfficeCardScraper
import json

class MainScraper:
    def __init__(self):
        self.property_urls = {
            "https://www.boshamlan.com/للايجار": "عقار للايجار",
            "https://www.boshamlan.com/للبيع": "عقار للبيع",
            "https://www.boshamlan.com/للبدل": "عقار للبدل"
        }
        self.office_url = "https://www.boshamlan.com/المكاتب"

    async def run(self):
        # Scrape property listings for each URL in the property_urls dictionary
        for url, file_name in self.property_urls.items():
            scraper = PropertyCardScraper(url)
            result = await scraper.scrape_cards()
            self.save_to_excel(result, file_name)

        # Scrape office listings
        scraper = OfficeCardScraper(self.office_url)
        result = await scraper.scrape_cards()
        self.save_to_excel(result, "المكاتب")

    def save_to_excel(self, data, file_name):
        """
        Save the scraped data into an Excel file.
        Assumes the data is in JSON format and needs to be converted to a DataFrame.
        """
        if data == "No cards found on this page.":
            print(f"No data found for {file_name}. Skipping Excel export.")
            return

        try:
            # Parse the data (assuming it's a JSON string)
            parsed_data = json.loads(data)

            # Convert to DataFrame
            df = pd.json_normalize(parsed_data)

            # Save DataFrame to Excel
            file_path = f"{file_name}.xlsx"
            df.to_excel(file_path, index=False, engine='openpyxl')

            print(f"Data for {file_name} saved to {file_path}")

        except Exception as e:
            print(f"Error while saving data to Excel for {file_name}: {e}")


# Usage
if __name__ == "__main__":
    main_scraper = MainScraper()
    asyncio.run(main_scraper.run())
