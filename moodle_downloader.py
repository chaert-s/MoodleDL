#!/usr/bin/env python3

import os
import re
import sys
import time
import json
import getpass
import argparse
import requests
import mimetypes
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from tqdm import tqdm


class MoodleDownloader:
    def __init__(self, base_url, username=None, password=None, download_dir=None, verbose=True, force_download=False):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.download_dir = download_dir or os.path.join(os.path.expanduser("~"), "Downloads", "MoodleContent")
        self.verbose = verbose
        self.force_download = force_download  # Add this line
        self.session = requests.Session()

        # Add headers to mimic a browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

        # Initialize mimetypes
        mimetypes.init()

    def log(self, message):
        """Print messages if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def login(self):
        """Log in to Moodle."""
        login_url = urljoin(self.base_url, "/login/index.php")

        # Get the login page to retrieve CSRF token
        response = self.session.get(login_url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Try different token field names used by various Moodle versions
        token = None
        for token_field in ["logintoken", "sesskey", "_csrf"]:
            token_input = soup.find("input", {"name": token_field})
            if token_input:
                token = token_input.get("value")
                token_name = token_field
                break

        # If we didn't find a token, proceed without it (some Moodle instances don't require it)
        if not token:
            token_name = "logintoken"
            token = ""

        # Get credentials if not provided
        if not self.username:
            self.username = input("Moodle Username: ")
        if not self.password:
            self.password = getpass.getpass("Moodle Password: ")

        # Prepare login data - include common fields used by different Moodle versions
        login_data = {
            "username": self.username,
            "password": self.password,
            token_name: token,
            "anchor": ""
        }

        # Submit login form
        response = self.session.post(login_url, data=login_data)

        # Check if login was successful by looking for common login page indicators
        if any(x in response.text for x in ["Log in to the site", "loginform", "Login to your account"]):
            self.log("Login failed. Please check your credentials.")
            sys.exit(1)

        self.log("Login successful!")
        return True

    def get_courses(self):
        """Get list of enrolled courses from various Moodle pages."""
        courses = []

        # Try multiple course list pages used by different Moodle versions
        course_pages = [
            "/my/courses.php",  # Dedicated courses page
            "/my/index.php",  # Dashboard
            "/course/index.php"  # All courses
        ]

        for page in course_pages:
            url = urljoin(self.base_url, page)
            self.log(f"Checking for courses at: {url}")

            try:
                response = self.session.get(url)
                courses_found = self._extract_courses_from_page(response.text)

                if courses_found:
                    courses.extend(courses_found)
                    self.log(f"Found {len(courses_found)} courses on {page}")
            except Exception as e:
                self.log(f"Error accessing {page}: {str(e)}")

        # Remove duplicates
        unique_courses = []
        seen_urls = set()

        for course in courses:
            if course["url"] not in seen_urls:
                seen_urls.add(course["url"])
                unique_courses.append(course)

        return unique_courses

    def _extract_courses_from_page(self, html_content):
        """Extract course information from HTML content using multiple selector methods."""
        courses = []
        soup = BeautifulSoup(html_content, "html.parser")

        # Method 1: Modern Moodle dashboard cards
        for card in soup.select(".dashboard-card, .coursebox, .course-info-container"):
            link = card.find("a", href=True)
            if link and "course/view.php" in link.get("href", ""):
                name_elem = card.select_one(".coursename, .card-title, .course-title, h3")
                name = name_elem.get_text(strip=True) if name_elem else link.get_text(strip=True)
                courses.append({
                    "url": link["href"],
                    "name": name or "Unnamed Course"
                })

        # Method 2: Direct course links
        if not courses:
            for link in soup.find_all("a", href=True):
                if "course/view.php" in link.get("href", ""):
                    courses.append({
                        "url": link["href"],
                        "name": link.get_text(strip=True) or "Unnamed Course"
                    })

        # Ensure all URLs are absolute
        for course in courses:
            if not course["url"].startswith(("http://", "https://")):
                course["url"] = urljoin(self.base_url, course["url"])

        return courses

    def get_file_extension(self, url, response_headers=None, original_filename=None):
        """Determine the file extension based on URL, headers, and original filename."""
        # Priority 1: Check if there's an extension in the original filename
        if original_filename:
            _, ext = os.path.splitext(original_filename)
            if ext:
                return ext

        # Priority 2: Try to extract from URL path
        path = unquote(urlparse(url).path)
        filename = os.path.basename(path)
        _, ext = os.path.splitext(filename)

        # If extension exists in URL and is reasonable length, use it
        if ext and len(ext) <= 10:
            return ext

        # Priority 3: Use content-type header
        if response_headers and 'Content-Type' in response_headers:
            content_type = response_headers['Content-Type'].split(';')[0].strip()
            ext = mimetypes.guess_extension(content_type)
            if ext:
                return ext

        # Priority 4: Check for common file patterns in URL
        pdf_pattern = re.search(r'pdf=(\d+)', url)
        if pdf_pattern:
            return '.pdf'

        doc_pattern = re.search(r'doc=(\d+)', url)
        if doc_pattern:
            return '.doc'

        # Check if there's a common format mentioned in the URL
        common_formats = {
            # Documents
            'pdf': '.pdf',
            'docx': '.docx',
            'doc': '.doc',
            'pptx': '.pptx',
            'ppt': '.ppt',
            'xlsx': '.xlsx',
            'xls': '.xls',
            'txt': '.txt',
            'rtf': '.rtf',
            'odt': '.odt',
            'ods': '.ods',
            'odp': '.odp',

            # Images
            'jpg': '.jpg',
            'jpeg': '.jpeg',
            'png': '.png',
            'gif': '.gif',
            'svg': '.svg',
            'bmp': '.bmp',
            'tiff': '.tiff',
            'tif': '.tif',

            # Audio
            'mp3': '.mp3',
            'wav': '.wav',
            'aac': '.aac',
            'flac': '.flac',
            'ogg': '.ogg',
            'm4a': '.m4a',

            # Video
            'mp4': '.mp4',
            'mov': '.mov',
            'avi': '.avi',
            'wmv': '.wmv',
            'webm': '.webm',
            'mkv': '.mkv',
            'flv': '.flv',
            'm4v': '.m4v',

            # Archives
            'zip': '.zip',
            'rar': '.rar',
            '7z': '.7z',
            'tar': '.tar',
            'gz': '.gz',
            'tgz': '.tgz',

            # Programming/Code
            'py': '.py',
            'java': '.java',
            'html': '.html',
            'htm': '.htm',
            'css': '.css',
            'js': '.js',
            'php': '.php',
            'sql': '.sql',
            'r': '.r',
            'm': '.m',
            'c': '.c',
            'cpp': '.cpp',
            'h': '.h',
            'ipynb': '.ipynb',

            # Special Formats
            'tex': '.tex',
            'epub': '.epub',
            'mobi': '.mobi',
            'srt': '.srt',
            'vtt': '.vtt',
            'xml': '.xml',
            'json': '.json',
            'csv': '.csv',
            'mm': '.mm',
            'xmind': '.xmind',

            # Learning-specific and others
            'h5p': '.h5p',
            'psd': '.psd',
            'ai': '.ai',
            'dwg': '.dwg',
            'dxf': '.dxf',
            'mus': '.mus',
            'sib': '.sib',
            'cdx': '.cdx',
            'ggb': '.ggb'
        }

        for format_name, extension in common_formats.items():
            if format_name in url.lower():
                return extension

        # Final fallback - return a sensible default
        return '.bin'

    def download_file(self, url, path, filename=None):
        """Download a file with progress bar. Skips if file already exists."""
        try:
            # Ensure the URL is absolute
            if not url.startswith(("http://", "https://")):
                url = urljoin(self.base_url, url)

            # Make a HEAD request first to get headers without downloading content
            head_response = self.session.head(url, allow_redirects=True)

            # If the request was redirected to a login page, login has expired
            if "login" in head_response.url and "login" not in url:
                self.log("Session expired. Logging in again...")
                self.login()
                return self.download_file(url, path, filename)

            # Now make a streaming request for the actual download
            response = self.session.get(url, stream=True)

            # Get filename from Content-Disposition header or URL if not provided
            original_filename = None
            if not filename:
                if 'Content-Disposition' in response.headers:
                    cd = response.headers.get('Content-Disposition')
                    filename_match = re.findall('filename="(.+?)"', cd)
                    if filename_match:
                        original_filename = filename_match[0]
                        filename = original_filename
                    else:
                        original_filename = os.path.basename(urlparse(url).path)
                        filename = original_filename
                else:
                    original_filename = os.path.basename(urlparse(url).path)
                    filename = original_filename

                # Clean up filename if it contains query parameters
                if '?' in filename:
                    filename = filename.split('?')[0]

            # Check if filename already has an extension
            _, ext = os.path.splitext(filename)
            if not ext or len(ext) <= 1:
                # Get extension from headers, URL, or content
                new_ext = self.get_file_extension(url, response.headers, original_filename)
                if new_ext:
                    filename = f"{filename}{new_ext}"
                    self.log(f"Added extension to file: {filename}")

            # Create full path
            full_path = os.path.join(path, self.sanitize_filename(filename))

            # Ensure directory exists
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # Check if file already exists and has content
            if not self.force_download and os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                # Get size of existing file
                existing_size = os.path.getsize(full_path)

                # Get expected file size
                expected_size = int(response.headers.get('content-length', 0))

                # If file exists and either matches expected size or expected size is unknown (0)
                if expected_size == 0 or abs(
                        existing_size - expected_size) < 100:  # Allow small difference due to network issues
                    self.log(f"Skipping existing file: {filename} ({existing_size} bytes)")
                    return full_path
                else:
                    self.log(f"File exists but size differs. Re-downloading: {filename}")
                    # Continue with download to replace the file

            # Get file size for progress bar
            total_size = int(response.headers.get('content-length', 0))

            # Skip empty files
            if total_size == 0:
                self.log(f"Skipping empty file: {filename}")
                return None

            # Download with progress bar
            with open(full_path, 'wb') as f:
                with tqdm(
                        desc=filename,
                        total=total_size,
                        unit='B',
                        unit_scale=True,
                        unit_divisor=1024,
                        disable=not self.verbose
                ) as bar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            size = f.write(chunk)
                            bar.update(size)

            return full_path
        except Exception as e:
            self.log(f"Error downloading {url}: {str(e)}")
            return None

    def sanitize_filename(self, filename):
        """Make a string safe for use as a filename."""
        # Replace problematic characters
        s = re.sub(r'[\\/*?:"<>|]', "_", filename)
        # Trim to reasonable length and remove trailing dots/spaces
        return s.strip(". ")[0:100]

    def process_course(self, course):
        """Process a single course and download all its content."""
        self.log(f"\nProcessing course: {course['name']}")

        # Create course directory
        course_dir = os.path.join(self.download_dir, self.sanitize_filename(course['name']))
        os.makedirs(course_dir, exist_ok=True)

        # Get course page
        response = self.session.get(course['url'])
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract course ID for potential API calls
        course_id = None
        try:
            course_id = parse_qs(urlparse(course['url']).query).get('id', [None])[0]
        except:
            pass

        # Try to get sections
        sections = self._get_course_sections(soup, course_id)

        if not sections:
            # If no sections found, treat the entire page as one section
            sections = [{
                'name': 'Main Content',
                'content': soup
            }]

        # Process each section
        for section in sections:
            section_name = section.get('name', 'Unnamed Section')
            section_soup = section.get('content')

            # Skip empty sections
            if not section_soup:
                continue

            # Create section directory
            section_dir = os.path.join(course_dir, self.sanitize_filename(section_name))
            os.makedirs(section_dir, exist_ok=True)

            # Process all resource types
            self._process_resources(section_soup, section_dir)
            self._process_folders(section_soup, section_dir)
            self._process_assignments(section_soup, section_dir)

        self.log(f"Completed processing course: {course['name']}")

    def _get_course_sections(self, soup, course_id=None):
        """Extract course sections from the page."""
        sections = []

        # Try different section selectors used by various Moodle themes
        section_elements = soup.select("li.section, div.section, .topics .topic")

        if section_elements:
            for section in section_elements:
                # Try to find section name
                name_elem = section.select_one("h3.sectionname, .content h3, .sectionname")
                name = name_elem.get_text(strip=True) if name_elem else f"Section {len(sections) + 1}"

                sections.append({
                    'name': name,
                    'content': section
                })

        return sections

    def _is_resource_link(self, link):
        """Check if a link is likely a downloadable resource."""
        href = link.get("href", "")

        # Direct file downloads or resource pages
        if any(x in href for x in ["pluginfile.php", "resource/view.php"]):
            # Exclude common non-file links
            if not any(x in href for x in ["forum", "page/view", "edit", "delete", "index"]):
                return True

        return False

    def _process_resources(self, soup, directory):
        """Process and download resource files."""
        # Find resource links - multiple selectors for different Moodle versions
        resource_links = [link for link in soup.find_all("a", href=True) if self._is_resource_link(link)]

        for link in resource_links:
            try:
                url = link["href"]
                name = link.get_text(strip=True)

                # Skip empty resources or buttons
                if not name or name.lower() in ["edit", "delete", "move"]:
                    continue

                self.log(f"Found resource: {name}")

                # Handle direct file downloads
                if "pluginfile.php" in url:
                    downloaded_file = self.download_file(url, directory, name)
                    if downloaded_file:
                        self.log(f"Downloaded: {downloaded_file}")
                # Handle resource view pages that need additional processing
                elif "resource/view.php" in url:
                    downloaded_file = self._process_resource_page(url, directory, name)
                    if downloaded_file:
                        self.log(f"Downloaded: {downloaded_file}")
                    else:
                        self.log(f"Warning: Could not extract file from resource page: {name}")
            except Exception as e:
                self.log(f"Error processing resource link: {str(e)}")

    def _process_resource_page(self, url, directory, name=None):
        """Process a resource view page to find the actual download link."""
        try:
            # Ensure URL is absolute
            if not url.startswith(("http://", "https://")):
                url = urljoin(self.base_url, url)

            self.log(f"Fetching resource page: {url}")

            # Extract resource ID for potential direct download
            resource_id = None
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            if 'id' in query_params:
                resource_id = query_params['id'][0]

            # Try direct download URL pattern first (this works on many Moodle instances)
            # Format: /mod/resource/view.php?id=XXX&redirect=1
            if resource_id and 'resource/view.php' in url:
                direct_url = f"{self.base_url}/mod/resource/view.php?id={resource_id}&redirect=1"
                self.log(f"Trying direct download URL: {direct_url}")

                # Follow redirects to get the actual file
                response = self.session.get(direct_url, allow_redirects=False)

                # If we got a redirect, follow it to the file
                if response.status_code in (301, 302, 303, 307, 308) and 'Location' in response.headers:
                    file_url = response.headers['Location']
                    if not file_url.startswith(("http://", "https://")):
                        file_url = urljoin(self.base_url, file_url)

                    self.log(f"Redirected to file: {file_url}")
                    return self.download_file(file_url, directory, name)

            # If direct download didn't work, fetch the page and analyze it
            response = self.session.get(url)
            soup = BeautifulSoup(response.text, "html.parser")

            # Debug info about the page
            self.log(f"Page title: {soup.title.string if soup.title else 'No title'}")

            # Method 1: Look for a download button or link
            download_links = []
            download_links.extend(soup.select("a.downloadbutton, .resourceworkaround a, .resourcecontent a"))
            download_links.extend([a for a in soup.find_all('a', href=True) if 'download' in a.get('href', '')])
            download_links.extend([a for a in soup.find_all('a', href=True) if 'pluginfile.php' in a.get('href', '')])

            for link in download_links:
                href = link.get("href", "")
                if href:
                    # Ensure URL is absolute
                    if not href.startswith(("http://", "https://")):
                        href = urljoin(self.base_url, href)

                    self.log(f"Found download link: {href}")
                    return self.download_file(href, directory, name)

            # Method 2: Check for embedded content
            embedded_sources = []
            for tag in soup.find_all(['iframe', 'embed', 'object'], src=True):
                src = tag.get('src') or tag.get('data')
                if src:
                    embedded_sources.append(src)

            for tag in soup.find_all(['source', 'video', 'audio'], src=True):
                embedded_sources.append(tag.get('src'))

            for src in embedded_sources:
                if src and ('pluginfile.php' in src or 'file.php' in src):
                    if not src.startswith(("http://", "https://")):
                        src = urljoin(self.base_url, src)
                    self.log(f"Found embedded content: {src}")
                    return self.download_file(src, directory, name)

            # Method 3: Extract URLs from JavaScript
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string:
                    # Look for file URLs in JavaScript
                    matches = re.findall(r'(https?://[^"\']*(?:pluginfile\.php|file\.php)[^"\'\s]*)', script.string)
                    matches.extend(re.findall(r'(\/[^"\']*(?:pluginfile\.php|file\.php)[^"\'\s]*)', script.string))

                    for match in matches:
                        url_to_try = match
                        if not url_to_try.startswith(("http://", "https://")):
                            url_to_try = urljoin(self.base_url, url_to_try)

                        self.log(f"Found URL in script: {url_to_try}")
                        result = self.download_file(url_to_try, directory, name)
                        if result:
                            return result

            # Method 4: Try the "resource/content" endpoint with the resource ID
            if resource_id:
                content_url = f"{self.base_url}/mod/resource/content.php?id={resource_id}"
                self.log(f"Trying content endpoint: {content_url}")
                return self.download_file(content_url, directory, name)

            # Method 5: Last resort, check for any link with common file extensions
            file_extensions = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.zip', '.rar', '.7z', '.mp3',
                               '.mp4', '.avi', '.mov', '.jpg', '.jpeg', '.png', '.gif']
            for link in soup.find_all('a', href=True):
                href = link.get("href", "")
                if any(href.lower().endswith(ext) for ext in file_extensions):
                    if not href.startswith(("http://", "https://")):
                        href = urljoin(self.base_url, href)
                    self.log(f"Found file link by extension: {href}")
                    return self.download_file(href, directory, name)

            # Method 6: Try to parse an "alternative download" link
            alt_links = soup.select(".resourcelinkdetails a, .urlworkaround a")
            for link in alt_links:
                href = link.get("href", "")
                if href:
                    if not href.startswith(("http://", "https://")):
                        href = urljoin(self.base_url, href)
                    self.log(f"Found alternative link: {href}")
                    return self.download_file(href, directory, name)

            # Method 7: Advanced - try to extract parameters for a direct download URL
            # Some Moodle instances use a different URL structure or have additional protections
            # This method attempts to construct a direct URL based on extracted parameters

            cmid = None
            for meta in soup.find_all('meta', attrs={'name': 'course-id'}):
                cmid = meta.get('content')

            if not cmid:
                # Try to find it in the URL or body
                cmid_matches = re.search(r'cmid=(\d+)', response.text)
                if cmid_matches:
                    cmid = cmid_matches.group(1)

            if cmid and resource_id:
                # Try various direct download URL patterns
                url_patterns = [
                    f"{self.base_url}/pluginfile.php/{cmid}/mod_resource/content/1/resource_{resource_id}",
                    f"{self.base_url}/pluginfile.php/mod_resource/content/{resource_id}",
                    f"{self.base_url}/mod/resource/view.php?id={resource_id}&forcedownload=1",
                    f"{self.base_url}/mod/resource/view.php?id={resource_id}&redirect=1"
                ]

                for pattern in url_patterns:
                    self.log(f"Trying pattern: {pattern}")
                    result = self.download_file(pattern, directory, name)
                    if result:
                        return result

            # No file found
            self.log(f"Could not extract file from resource page. Resource name: {name}, URL: {url}")

            # Save the HTML for debugging
            debug_file = os.path.join(directory, f"{self.sanitize_filename(name or 'resource')}_debug.html")
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            self.log(f"Saved HTML for debugging to: {debug_file}")

            return None

        except Exception as e:
            self.log(f"Error processing resource page {url}: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            return None

    def _process_folders(self, soup, directory):
        """Process folder modules and download contents."""
        folder_links = [link for link in soup.find_all("a", href=True)
                        if "folder/view.php" in link.get("href", "")]

        for link in folder_links:
            try:
                url = link["href"]
                folder_name = link.get_text(strip=True)

                if not folder_name:
                    folder_name = f"Folder_{len(os.listdir(directory)) + 1}"

                self.log(f"Processing folder: {folder_name}")

                # Create folder directory
                folder_dir = os.path.join(directory, self.sanitize_filename(folder_name))
                os.makedirs(folder_dir, exist_ok=True)

                # Get folder page
                response = self.session.get(url)
                folder_soup = BeautifulSoup(response.text, "html.parser")

                # Find all files in the folder
                for file_link in folder_soup.find_all("a", href=True):
                    href = file_link.get("href", "")
                    if "pluginfile.php" in href:
                        file_name = file_link.get_text(strip=True)
                        self.download_file(href, folder_dir, file_name)
            except Exception as e:
                self.log(f"Error processing folder {link.get('href', '')}: {str(e)}")

    def _process_assignments(self, soup, directory):
        """Process assignment pages and download any attachments."""
        assignment_links = [link for link in soup.find_all("a", href=True)
                            if "assign/view.php" in link.get("href", "")]

        for link in assignment_links:
            try:
                url = link["href"]
                name = link.get_text(strip=True)

                if not name:
                    continue

                self.log(f"Processing assignment: {name}")

                # Create assignment directory
                assign_dir = os.path.join(directory, self.sanitize_filename(name))
                os.makedirs(assign_dir, exist_ok=True)

                # Get assignment page
                response = self.session.get(url)
                assign_soup = BeautifulSoup(response.text, "html.parser")

                # Save assignment description
                desc_div = assign_soup.select_one(".assignmentinfo, .descriptionbox, .assign-intro")
                if desc_div:
                    desc_text = desc_div.get_text(strip=True)
                    if desc_text:
                        with open(os.path.join(assign_dir, "description.txt"), 'w', encoding='utf-8') as f:
                            f.write(desc_text)

                # Download any attached files
                for file_link in assign_soup.find_all("a", href=True):
                    href = file_link.get("href", "")
                    if "pluginfile.php" in href:
                        file_name = file_link.get_text(strip=True)
                        self.download_file(href, assign_dir, file_name)
            except Exception as e:
                self.log(f"Error processing assignment {link.get('href', '')}: {str(e)}")

    def run(self):
        """Main execution function."""
        self.log("Moodle Content Downloader")
        self.log("------------------------")

        # Create base download directory
        os.makedirs(self.download_dir, exist_ok=True)

        # Login to Moodle
        self.login()

        # Get available courses
        courses = self.get_courses()

        if not courses:
            self.log("No courses found! Please check your Moodle setup.")
            return

        self.log(f"\nFound {len(courses)} courses:")
        for i, course in enumerate(courses, 1):
            self.log(f"{i}. {course['name']}")

        # Ask which courses to download
        selection = input("\nEnter course numbers to download (comma-separated, or 'all'): ")

        if selection.lower() == 'all':
            selected_courses = courses
        else:
            try:
                indices = [int(idx.strip()) - 1 for idx in selection.split(',')]
                selected_courses = [courses[idx] for idx in indices if 0 <= idx < len(courses)]
            except ValueError:
                self.log("Invalid selection. Downloading all courses.")
                selected_courses = courses

        # Download each selected course
        for course in selected_courses:
            self.process_course(course)

        self.log("\nDownload complete! Files saved to: " + self.download_dir)


def main():
    parser = argparse.ArgumentParser(description="Download content from Moodle courses")
    parser.add_argument("-u", "--url", required=True, help="Moodle base URL (e.g., https://moodle.university.edu)")
    parser.add_argument("-n", "--username", help="Moodle username")
    parser.add_argument("-p", "--password", help="Moodle password")
    parser.add_argument("-d", "--directory", help="Download directory")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode (less output)")
    parser.add_argument("-f", "--force", action="store_true", help="Force re-download of existing files")

    args = parser.parse_args()

    downloader = MoodleDownloader(
        base_url=args.url,
        username=args.username,
        password=args.password,
        download_dir=args.directory,
        verbose=not args.quiet,
        force_download=args.force  # Add this parameter
    )

    try:
        downloader.run()
    except KeyboardInterrupt:
        print("\nDownload interrupted by user.")
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
