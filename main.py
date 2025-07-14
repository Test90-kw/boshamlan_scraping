import asyncio
import json
import os
from datetime import datetime, timedelta
import pandas as pd
from OfficeCardScraper import OfficeCardScraper
from PropertyCardScraper import PropertyCardScraper
from SavingOnDrive import SavingOnDrive


class Main:
    def __init__(self, credentials_dict):
        """Initialize with Google Drive credentials."""
        self.credentials_dict = credentials_dict
        self.yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        self.drive_saver = SavingOnDrive(credentials_dict)

    async def scrape_and_save(self):
        """Scrape data for all sections, save to Excel, and upload to Google Drive."""
        print("Starting scraping process...")

        # Define URLs for each section
        sections = {
            'sale': 'https://www.boshamlan.com/search?c=1&t=1',
            'rent': 'https://www.boshamlan.com/search?c=1&t=2',
            'exchange': 'https://www.boshamlan.com/search?c=1&t=3',
            'offices': 'https://www.boshamlan.com/المكاتب'
        }

        excel_files = []

        # Scrape property sections (sale, rent, exchange)
        for section, url in sections.items():
            if section != 'offices':
                print(f"\nScraping {section} properties...")
                scraper = PropertyCardScraper(url)
                data = await scraper.scrape_cards()
                file_path = self.save_to_excel(data, section)
                if file_path:
                    excel_files.append(file_path)

        # Scrape offices
        print(f"\nScraping offices...")
        scraper = OfficeCardScraper(sections['offices'])
        data = await scraper.scrape_cards()
        file_path = self.save_to_excel(data, 'offices')
        if file_path:
            excel_files.append(file_path)

        # Upload files to Google Drive
        if excel_files:
            print("\nAuthenticating with Google Drive...")
            self.drive_saver.authenticate()
            print("Uploading files to Google Drive...")
            self.drive_saver.save_files(excel_files)
        else:
            print("No Excel files generated to upload.")

        print("Scraping and upload process completed.")

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


# Usage
if __name__ == "__main__":
    # Load Google Drive credentials from a JSON file
    # try:
    #     with open('path_to_service_account.json', 'r') as f:
    #         credentials_dict = json.load(f)
    # except Exception as e:
    #     print(f"Error loading credentials: {e}")
    #     exit(1)

    main = Main(credentials_dict)
    asyncio.run(main.scrape_and_save())
