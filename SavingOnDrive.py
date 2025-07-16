# Import standard and Google API libraries
import os
import json
from google.oauth2.service_account import Credentials  # For authentication using service account
from googleapiclient.discovery import build  # To create Google Drive service
from googleapiclient.http import MediaFileUpload  # For uploading files
from datetime import datetime, timedelta  # For handling folder names based on date

# Class to manage saving files to Google Drive using a service account
class SavingOnDrive:
    def __init__(self, credentials_dict):
        """
        Initializes the class with a dictionary of service account credentials.
        """
        self.credentials_dict = credentials_dict  # Service account JSON content (already parsed)
        self.scopes = ['https://www.googleapis.com/auth/drive']  # Scope for full access to Google Drive
        self.service = None  # Google Drive API client will be initialized later

    def authenticate(self):
        """
        Authenticates using the service account JSON and initializes the Drive service.
        """
        creds = Credentials.from_service_account_info(self.credentials_dict, scopes=self.scopes)
        self.service = build('drive', 'v3', credentials=creds)  # Build Google Drive API client

    def create_folder(self, folder_name, parent_folder_id=None):
        """
        Creates a folder with the given name.
        Optionally nests it inside a specified parent folder ID.
        """
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'  # MIME type for Drive folders
        }
        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]  # Set parent folder if provided

        # Create the folder and return its ID
        folder = self.service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

    def upload_file(self, file_name, folder_id):
        """
        Uploads a single file to the specified folder on Google Drive.
        """
        file_metadata = {'name': file_name, 'parents': [folder_id]}  # File name and destination folder
        media = MediaFileUpload(file_name, resumable=True)  # Prepare file for upload
        file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')  # Return the uploaded file ID

    def save_files(self, files):
        """
        Uploads a list of files to two predefined parent folders on Google Drive.
        Each file set is saved inside a subfolder named after yesterday's date.
        """
        parent_folder_ids = [
            '17WpAimIo-q6xMhlnUfQ_t6NMnAICQrVw',  # Example parent folder 1
            '1lL8iWCaCSFqHtsPdm35H8MC1WqQMjaPc'   # Example parent folder 2
        ]
        
        # Generate folder name as yesterday's date
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # For each parent folder, create a dated folder and upload files
        for parent_folder_id in parent_folder_ids:
            folder_id = self.create_folder(yesterday, parent_folder_id)
            for file_name in files:
                self.upload_file(file_name, folder_id)
            print(f"Files uploaded successfully to folder '{yesterday}' in parent folder ID '{parent_folder_id}' on Google Drive.")
