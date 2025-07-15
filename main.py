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
        self.excel_files = []  # Store Excel files for upload

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

        self.excel_files = []  # Reset excel_files list

        # Scrape property sections (sale, rent, exchange)
        for section, url in sections.items():
            if section != 'offices':
                print(f"\nScraping {section} properties...")
                scraper = PropertyCardScraper(url)
                data = await scraper.scrape_cards()
                file_path = self.save_to_excel(data, section)
                if file_path:
                    self.excel_files.append(file_path)

        # Scrape offices
        print(f"\nScraping offices...")
        scraper = OfficeCardScraper(sections['offices'])
        data = await scraper.scrape_cards()
        file_path = self.save_to_excel(data, 'offices')
        if file_path:
            self.excel_files.append(file_path)

        # Upload files to Google Drive
        self.upload_to_drive()

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

    def upload_to_drive(self):
        """
        Upload saved Excel files to Google Drive in a folder named with yesterday's date in two parent folders.
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
    
        parent_folder_ids = [
            "11sji-ooCJdIx3t10rtr6mB0O9BntAJoF",  # Existing parent folder
            "1FkFWACOrKJRzPl2v6OST_I8XDIzbwZ1x"   # New parent folder
        ]
    
        for parent_folder_id in parent_folder_ids:
            try:
                folder_id = drive_saver.create_folder(self.yesterday, parent_folder_id)
                print(f"Created folder '{self.yesterday}' with ID: {folder_id} in parent folder ID: {parent_folder_id}")
                
                for file in self.excel_files:
                    drive_saver.upload_file(file, folder_id)
                    print(f"Uploaded {file} to Google Drive in folder ID: {folder_id}.")
            except Exception as e:
                print(f"Error uploading to parent folder ID {parent_folder_id}: {e}")
                continue


# Usage
if __name__ == "__main__":
    # Load Google Drive credentials from environment variable
    try:
        if 'BOSHAMLAN_GCLOUD_KEY_JSON' not in os.environ:
            raise EnvironmentError("BOSHAMLAN_GCLOUD_KEY_JSON environment variable not set.")
        credentials_json = os.environ['BOSHAMLAN_GCLOUD_KEY_JSON']
        credentials_dict = json.loads(credentials_json)
    except Exception as e:
        print(f"Error loading credentials from environment variable: {e}")
        exit(1)

    main = Main(credentials_dict)
    asyncio.run(main.scrape_and_save())

