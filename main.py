import asyncio
import json
import os
from datetime import datetime, timedelta
import pandas as pd
from OfficeCardScraper import OfficeCardScraper  # Scraper for office listings
from PropertyCardScraper import PropertyCardScraper  # Scraper for property listings
from SavingOnDrive import SavingOnDrive  # Google Drive upload handler


class Main:
    def __init__(self, credentials_dict):
        """Initialize with Google Drive credentials."""
        self.credentials_dict = credentials_dict

        # Set the date for folder naming (yesterday's date)
        self.yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        # Initialize the Google Drive saving helper
        self.drive_saver = SavingOnDrive(credentials_dict)

        # List to collect file paths of Excel files to be uploaded
        self.excel_files = []

    async def scrape_and_save(self):
        """
        Coordinates scraping of all sections, saves them to Excel files,
        and uploads to Google Drive.
        """
        print("Starting scraping process...")

        # URLs to scrape for each section
        sections = {
            'sale': 'https://www.boshamlan.com/search?c=1&t=1',
            'rent': 'https://www.boshamlan.com/search?c=1&t=2',
            'exchange': 'https://www.boshamlan.com/search?c=1&t=3',
            'offices': 'https://www.boshamlan.com/المكاتب'
        }

        # Reset list of Excel files to avoid duplicates if reused
        self.excel_files = []

        # Scrape each property section (sale, rent, exchange)
        for section, url in sections.items():
            if section != 'offices':
                print(f"\nScraping {section} properties...")
                scraper = PropertyCardScraper(url)
                data = await scraper.scrape_cards()
                file_path = self.save_to_excel(data, section)
                if file_path:
                    self.excel_files.append(file_path)

        # Scrape the offices section separately using a different scraper
        print(f"\nScraping offices...")
        scraper = OfficeCardScraper(sections['offices'])
        data = await scraper.scrape_cards()
        file_path = self.save_to_excel(data, 'offices')
        if file_path:
            self.excel_files.append(file_path)

        # Upload collected Excel files to Google Drive
        self.upload_to_drive()

        print("Scraping and upload process completed.")

    def save_to_excel(self, data, file_name):
        """
        Converts JSON data to a DataFrame and saves it as an Excel file.
        Returns the file path if successful, None otherwise.
        """
        if data == "No cards found on this page.":
            print(f"No data found for {file_name}. Skipping Excel export.")
            return None

        try:
            # Parse JSON string into Python dict/list
            parsed_data = json.loads(data)

            # Flatten nested fields and create a DataFrame
            df = pd.json_normalize(parsed_data)

            # Create a folder with the name as the date (yesterday)
            folder_name = self.yesterday
            os.makedirs(folder_name, exist_ok=True)

            # Define full path for the Excel file
            file_path = os.path.join(folder_name, f"{file_name}.xlsx")

            # Save to Excel
            df.to_excel(file_path, index=False, engine='openpyxl')
            print(f"Data for {file_name} saved to {file_path}")
            return file_path

        except Exception as e:
            print(f"Error while saving data to Excel for {file_name}: {e}")
            return None

    def upload_to_drive(self):
        """
        Uploads all collected Excel files to two separate parent folders
        on Google Drive under a dated subfolder (yesterday's date).
        """
        if not self.excel_files:
            print("No Excel files to upload.")
            return

        # Validate that credentials exist in environment
        if 'BOSHAMLAN_GCLOUD_KEY_JSON' not in os.environ:
            raise EnvironmentError("BOSHAMLAN_GCLOUD_KEY_JSON not found.")

        # Load credentials again for upload step
        credentials_json = os.environ['BOSHAMLAN_GCLOUD_KEY_JSON']
        credentials_dict = json.loads(credentials_json)

        # Authenticate with Google Drive
        drive_saver = SavingOnDrive(credentials_dict)
        drive_saver.authenticate()

        # Target parent folders to upload to
        parent_folder_ids = [
            '17WpAimIo-q6xMhlnUfQ_t6NMnAICQrVw',  # First folder
            '1lL8iWCaCSFqHtsPdm35H8MC1WqQMjaPc'   # Second folder
        ]

        # Upload each file to a newly created subfolder in each parent folder
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


# Entry point when the script is run directly
if __name__ == "__main__":
    try:
        # Check and load Google Drive credentials from environment
        if 'BOSHAMLAN_GCLOUD_KEY_JSON' not in os.environ:
            raise EnvironmentError("BOSHAMLAN_GCLOUD_KEY_JSON environment variable not set.")
        credentials_json = os.environ['BOSHAMLAN_GCLOUD_KEY_JSON']
        credentials_dict = json.loads(credentials_json)
    except Exception as e:
        print(f"Error loading credentials from environment variable: {e}")
        exit(1)

    # Initialize and run the main process
    main = Main(credentials_dict)
    asyncio.run(main.scrape_and_save())
