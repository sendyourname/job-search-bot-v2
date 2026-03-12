"""Google Drive integration for storing job search outputs."""

import logging
import io
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

# Required scopes for Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']


class LocalFileStorage:
    """
    Fallback local file storage when Google Drive isn't available.
    Saves files to a local output directory.
    """

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def upload_job_package(
        self,
        company: str,
        job_title: str,
        cover_letter: str,
        hm_research: str,
        job_details: str,
        job_url: str,
    ) -> dict:
        """Save job package to local files."""
        timestamp = datetime.now().strftime("%Y%m%d")
        folder_name = self._sanitize_filename(f"{timestamp} - {company} - {job_title}")
        folder_path = self.output_dir / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)

        files = []

        if cover_letter:
            cl_path = folder_path / "Cover Letter.md"
            cl_path.write_text(cover_letter)
            files.append(str(cl_path))

        if hm_research:
            hm_path = folder_path / "Hiring Manager Research.md"
            hm_path.write_text(hm_research)
            files.append(str(hm_path))

        job_content = f"""# Job Details

**Company:** {company}
**Title:** {job_title}
**URL:** {job_url}
**Saved:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

{job_details}
"""
        job_path = folder_path / "Job Posting.md"
        job_path.write_text(job_content)
        files.append(str(job_path))

        logger.info(f"Saved job package to {folder_path}")

        return {
            "folder_id": str(folder_path),
            "folder_link": f"file://{folder_path.absolute()}",
            "files": files,
        }

    def _sanitize_filename(self, name: str) -> str:
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            name = name.replace(char, '-')
        return name[:100]


class GoogleDriveService:
    """
    Google Drive service for uploading job search results.

    Supports both regular Drive folders and Shared Drives.

    Setup for Shared Drive:
    1. Create a Google Cloud project
    2. Enable Google Drive API
    3. Create a service account
    4. Download credentials JSON
    5. Add the service account email as a member of the Shared Drive
       (with Content Manager or higher permissions)
    6. Use the Shared Drive folder ID

    Setup for regular Drive:
    1. Same as above, but share the folder with the service account email
    """

    def __init__(self, credentials_path: str, folder_id: str, use_shared_drive: bool = True):
        """
        Initialize Google Drive service.

        Args:
            credentials_path: Path to service account JSON credentials
            folder_id: ID of the target Drive folder (or Shared Drive folder)
            use_shared_drive: Whether to use Shared Drive API parameters
        """
        self.folder_id = folder_id
        self.use_shared_drive = use_shared_drive
        self.service = self._build_service(credentials_path)

    def _build_service(self, credentials_path: str):
        """Build the Drive API service."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=SCOPES
            )
            return build('drive', 'v3', credentials=credentials)
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive: {e}")
            raise

    def create_folder(self, name: str, parent_id: Optional[str] = None) -> str:
        """
        Create a folder in Drive.

        Args:
            name: Folder name
            parent_id: Parent folder ID (defaults to root folder_id)

        Returns:
            Created folder ID
        """
        parent = parent_id or self.folder_id

        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent]
        }

        create_params = {
            'body': file_metadata,
            'fields': 'id',
        }
        if self.use_shared_drive:
            create_params['supportsAllDrives'] = True

        folder = self.service.files().create(**create_params).execute()

        folder_id = folder.get('id')
        logger.info(f"Created folder '{name}' with ID: {folder_id}")
        return folder_id

    def upload_text_file(
        self,
        content: str,
        filename: str,
        folder_id: Optional[str] = None,
        mime_type: str = 'text/markdown'
    ) -> dict:
        """
        Upload a text file to Drive.

        Args:
            content: File content
            filename: File name
            folder_id: Target folder ID
            mime_type: MIME type of the file

        Returns:
            {
                "id": file_id,
                "name": filename,
                "webViewLink": shareable_link
            }
        """
        parent = folder_id or self.folder_id

        file_metadata = {
            'name': filename,
            'parents': [parent]
        }

        # Create file content
        fh = io.BytesIO(content.encode('utf-8'))
        media = MediaIoBaseUpload(fh, mimetype=mime_type, resumable=True)

        create_params = {
            'body': file_metadata,
            'media_body': media,
            'fields': 'id, name, webViewLink',
        }
        if self.use_shared_drive:
            create_params['supportsAllDrives'] = True

        file = self.service.files().create(**create_params).execute()

        logger.info(f"Uploaded file '{filename}' with ID: {file.get('id')}")
        return file

    def upload_job_package(
        self,
        company: str,
        job_title: str,
        cover_letter: str,
        hm_research: str,
        job_details: str,
        job_url: str,
    ) -> dict:
        """
        Upload a complete job application package.

        Creates a folder for the company/job and uploads:
        - Cover letter
        - Hiring manager research
        - Job details/snapshot

        Args:
            company: Company name
            job_title: Job title
            cover_letter: Cover letter content
            hm_research: Hiring manager research content
            job_details: Job posting details
            job_url: Original job URL

        Returns:
            {
                "folder_id": str,
                "folder_link": str,
                "files": [list of uploaded files]
            }
        """
        # Create folder for this job
        timestamp = datetime.now().strftime("%Y%m%d")
        folder_name = f"{timestamp} - {company} - {job_title}"
        folder_name = self._sanitize_filename(folder_name)

        folder_id = self.create_folder(folder_name)

        # Get folder link
        folder_link = f"https://drive.google.com/drive/folders/{folder_id}"

        files = []

        # Upload cover letter
        if cover_letter:
            cl_file = self.upload_text_file(
                content=cover_letter,
                filename="Cover Letter.md",
                folder_id=folder_id,
            )
            files.append(cl_file)

        # Upload hiring manager research
        if hm_research:
            hm_file = self.upload_text_file(
                content=hm_research,
                filename="Hiring Manager Research.md",
                folder_id=folder_id,
            )
            files.append(hm_file)

        # Upload job details
        job_content = f"""# Job Details

**Company:** {company}
**Title:** {job_title}
**URL:** {job_url}
**Saved:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

{job_details}
"""
        job_file = self.upload_text_file(
            content=job_content,
            filename="Job Posting.md",
            folder_id=folder_id,
        )
        files.append(job_file)

        logger.info(f"Created job package for {company}: {folder_link}")

        return {
            "folder_id": folder_id,
            "folder_link": folder_link,
            "files": files,
        }

    def _sanitize_filename(self, name: str) -> str:
        """Remove invalid characters from filename."""
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            name = name.replace(char, '-')
        return name[:100]  # Limit length

    def list_recent_folders(self, limit: int = 10) -> list:
        """
        List recent folders in the root folder.

        Args:
            limit: Maximum number of folders to return

        Returns:
            List of folder metadata
        """
        query = f"'{self.folder_id}' in parents and mimeType='application/vnd.google-apps.folder'"

        list_params = {
            'q': query,
            'pageSize': limit,
            'fields': "files(id, name, createdTime, webViewLink)",
            'orderBy': "createdTime desc",
        }
        if self.use_shared_drive:
            list_params['supportsAllDrives'] = True
            list_params['includeItemsFromAllDrives'] = True

        results = self.service.files().list(**list_params).execute()

        return results.get('files', [])
