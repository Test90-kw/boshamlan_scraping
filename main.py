import asyncio
import os
import json
import pandas as pd
from datetime import datetime, timedelta
from PropertyCardScraper import PropertyCardScraper
from OfficeCardScraper import OfficeCardScraper
from SavingOnDrive import SavingOnDrive

class MainScraper:
    def __init__(self):
        self.property_urls = {
            "https://www.boshamlan.com/للايجار": "عقار للايجار",
            "https://www.boshamlan.com/للبيع": "عقار للبيع",
            "https://www.boshamlan.com/للبدل": "عقار للبدل"
        }
        self.office_url = "https://www.boshamlan.com/المكاتب"
        self.yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        self.excel_files = []

    async def run(self):
        # Scrape property listings for each URL in the property_urls dictionary
        for url, file_name in self.property_urls.items():
            scraper = PropertyCardScraper(url)
            result = await scraper.scrape_cards()
            file_path = self.save_to_excel(result, file_name)
            if file_path:
                self.excel_files.append(file_path)

        # Scrape office listings
        scraper = OfficeCardScraper(self.office_url)
        result = await scraper.scrape_cards()
        file_path = self.save_to_excel(result, "المكاتب")
        if file_path:
            self.excel_files.append(file_path)

        # Upload to Google Drive
        self.upload_to_drive()

    def save_to_excel(self, data, file_name):
        """
        Save the scraped data into an Excel file.
        Assumes the data is in JSON format and needs to be converted to a DataFrame.
        """
        if data == "No cards found on this page.":
            print(f"No data found for {file_name}. Skipping Excel export.")
            return None

        try:
            parsed_data = json.loads(data)
            df = pd.json_normalize(parsed_data)
            
            folder_name = self.yesterday
            os.makedirs(folder_name, exist_ok=True)
            file_path = os.path.join(folder_name, f"{file_name}.xlsx")
            
            df.to_excel(file_path, index=False, engine='openpyxl')
            print(f"Data for {file_name} saved to {file_path}")
            return file_path
        except Exception as e:
            print(f"Error while saving data to Excel for {file_name}: {e}")
            return None

    def upload_to_drive(self):
        """
        Upload saved Excel files to Google Drive in a folder named with yesterday's date.
        """
        if not self.excel_files:
            print("No Excel files to upload.")
            return

        # Initialize SavingOnDrive
        if 'BOSHAMLAN_GCLOUD_KEY_JSON' not in os.environ:
            raise EnvironmentError("BOSHAMLAN_GCLOUD_KEY_JSON not found.")

        credentials_json = os.environ['BOSHAMLAN_GCLOUD_KEY_JSON']
        credentials_dict = json.loads(credentials_json)

        drive_saver = SavingOnDrive(credentials_dict)
        drive_saver.authenticate()

        parent_folder_id = "11sji-ooCJdIx3t10rtr6mB0O9BntAJoF"
        folder_id = drive_saver.create_folder(self.yesterday, parent_folder_id)
        print(f"Created folder '{self.yesterday}' with ID: {folder_id}")

        for file in self.excel_files:
            drive_saver.upload_file(file, folder_id)
            print(f"Uploaded {file} to Google Drive.")

if __name__ == "__main__":
    main_scraper = MainScraper()
    asyncio.run(main_scraper.run())
