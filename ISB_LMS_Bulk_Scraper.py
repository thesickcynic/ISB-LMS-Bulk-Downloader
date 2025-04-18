import os
import time
import re
import platform
from urllib.parse import urljoin, unquote
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- Configuration ---
LMS_DASHBOARD_URL = "https://elearn.isb.edu/my/"
# On macOS, Desktop is typically under /Users/YourUsername/Desktop
# os.path.expanduser('~') gets the home directory path
DOWNLOAD_BASE_DIR = os.path.join(os.path.expanduser('~'), 'Desktop', 'ISB_Coursepacks')
MANUAL_LOGIN_TIMEOUT = 90 # Seconds to wait for manual login

# --- Helper Functions ---

def sanitize_filename(filename):
    """Removes invalid characters for filenames and cleans up common issues."""
    try:
        filename = unquote(str(filename)) # Ensure it's a string before unquote
    except Exception:
        pass # Ignore decoding errors, proceed with original
    filename = filename.strip()
    filename = re.sub(r'[\\/*?:"<>|]+', "", filename)
    filename = re.sub(r'\s+', ' ', filename)
    filename = filename.replace('...', '').replace(':', ' -')
    while filename.endswith('.') or filename.endswith(' '):
         filename = filename[:-1]
    if not filename:
        filename = "downloaded_file"
    return filename

def ensure_dir_exists(dir_path):
    """Creates a directory if it doesn't exist."""
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path)
            print(f"   Created directory: {dir_path}")
        except OSError as e:
             print(f"   ERROR creating directory {dir_path}: {e}")
             raise # Re-raise the exception to stop processing for this course

# --- Main Script ---

print("Starting LMS PDF Downloader...")
print(f"Downloads will be saved to: {DOWNLOAD_BASE_DIR}")
ensure_dir_exists(DOWNLOAD_BASE_DIR) # Pass None for window argument

driver = None # Initialize driver
ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"

try:
    # Setup Selenium WebDriver
    print("Setting up browser driver...")
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"user-agent={ua}")

        service = ChromeService(executable_path=ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("Browser driver setup complete.")

    except Exception as e:
        print(f"\nFATAL ERROR setting up WebDriver: {e}")
        print("\nPlease ensure Google Chrome is installed and accessible.")
        exit()

    # --- Login Step ---
    print(f"\nNavigating to: {LMS_DASHBOARD_URL}")
    driver.get(LMS_DASHBOARD_URL)

    print(f"\n---> Please log in to the LMS in the browser window that just opened. <---")
    print(f"     You have {MANUAL_LOGIN_TIMEOUT} seconds to complete the login.")
    print("     The script will continue automatically after login detection OR after the timeout.")

    try:
        WebDriverWait(driver, MANUAL_LOGIN_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div#region-main, div.usermenu, nav#primary-nav, a[href*='login/logout.php']"))
        )
        print("Login detected or timeout reached. Assuming logged in, proceeding...")
    except Exception as e:
        print(f"WARNING: Did not detect logged-in state element after {MANUAL_LOGIN_TIMEOUT}s (Error: {e}).")
        print("Attempting to proceed anyway...")

    # --- Scrape Dashboard for Courses ---
    print("\nScraping dashboard for course list...")
    if "/my/" not in driver.current_url:
         print("Not on dashboard, redirecting...")
         driver.get(LMS_DASHBOARD_URL)
         time.sleep(5)

    courses_to_download = []
    try:
        dashboard_html = driver.page_source
        soup = BeautifulSoup(dashboard_html, 'html.parser')

        # --- Identify Term and Block Week Sections ---
        # Updated regex to find headers containing 'Term X' OR 'Block Week Y' (case-insensitive)
        section_header_pattern = re.compile(
            r'(Term\s+\d+|Block\s*Week[\s\d]*)',
            re.IGNORECASE
        )
        # Find elements likely to be section headers
        possible_headers = soup.find_all(
            ['h2', 'h3', 'h4', 'div', 'span'],
            string=section_header_pattern
        )

        if not possible_headers:
             print("WARNING: Could not find specific Term/Block Week headers. Trying fallback course link search.")
             course_links = soup.select('div.coursebox > div.info > h3.coursename > a, a.coursename[href*="/course/view.php"]')
             if not course_links:
                 print("ERROR: Could not find any course links on dashboard. Cannot proceed.")
                 if driver: driver.quit()
                 exit()
             print(f"Found {len(course_links)} potential courses (fallback).")
             for link in course_links:
                 course_name = link.get_text(strip=True)
                 course_url = link.get('href')
                 if course_name and course_url:
                      abs_url = urljoin(LMS_DASHBOARD_URL, course_url)
                      if not any(c['url'] == abs_url for c in courses_to_download):
                         section_folder_name = "Unknown_Section" # Use generic section name
                         courses_to_download.append({"term": section_folder_name, "name": sanitize_filename(course_name), "url": abs_url})
                         print(f"  Found Course (fallback): {course_name}")

        else:
             print(f"Found {len(possible_headers)} potential Term/Block Week sections.")
             processed_urls = set()
             for header_el in possible_headers:
                 header_text = header_el.get_text(strip=True)
                 match = section_header_pattern.search(header_text)
                 if match:
                     section_name_raw = match.group(1).strip()
                     section_folder_name = sanitize_filename(section_name_raw).replace(' ', '_')
                 else:
                     section_folder_name = sanitize_filename(header_text).replace(' ', '_')
                     if not section_folder_name: section_folder_name = "Unnamed_Section"

                 print(f" Processing Section: {section_folder_name} (from '{header_text}')")

                 # Find the container holding the course links
                 container = header_el.find_next_sibling(['ul', 'div'])
                 if not container: # If not immediate sibling, check siblings further down
                      current_el = header_el
                      while True:
                           next_s = current_el.find_next_sibling()
                           if not next_s or next_s.name in ['h2','h3','h4']: break
                           if next_s.name in ['ul','div']: container = next_s; break
                           current_el = next_s
                 if not container: container = header_el.parent # Fallback: check parent

                 if container:
                     links = container.select('a[href*="/course/view.php?id="]')
                     found_in_section = 0
                     for link in links:
                         if link in container.find_all('a', recursive=True):
                             course_name = link.get_text(strip=True)
                             course_url = link.get('href')
                             abs_course_url = urljoin(LMS_DASHBOARD_URL, course_url)
                             if course_name and course_url and abs_course_url not in processed_urls:
                                  print(f"  Found Course: {course_name}")
                                  courses_to_download.append({
                                      "term": section_folder_name, # Use extracted section name
                                      "name": sanitize_filename(course_name),
                                      "url": abs_course_url
                                  })
                                  processed_urls.add(abs_course_url)
                                  found_in_section +=1
                     if found_in_section == 0:
                          print(f"  No course links found directly within the identified container for '{section_folder_name}'.")
                 else:
                      print(f"  Warning: Could not find a likely container for course links under section '{section_folder_name}'.")


        if not courses_to_download:
            print("\nERROR: No courses found to process after checking dashboard.")
            if driver: driver.quit()
            exit()

        print(f"\nFound {len(courses_to_download)} unique courses across all sections.")

    except Exception as e:
        print(f"\nError scraping dashboard: {e}")
        if driver: driver.quit()
        exit()

    # --- Download PDFs for each course ---
    download_summary = {}
    session = requests.Session()
    selenium_cookies = driver.get_cookies()
    for cookie in selenium_cookies:
         try:
             session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain'), path=cookie.get('path', '/'))
         except Exception as cookie_err:
              print(f"   Warning: Skipping cookie '{cookie.get('name')}': {cookie_err}")
    session.headers.update({"User-Agent": ua})

    print("\n--- Starting PDF Downloads ---")
    for course in courses_to_download:
        section_name = course["term"] # This holds "Term_X" or "Block_Week_Y" etc.
        course_name = course["name"]
        course_url = course["url"]
        print(f"\nProcessing Course: {course_name} (Section: {section_name})")
        print(f" URL: {course_url}")

        course_folder = os.path.join(DOWNLOAD_BASE_DIR, section_name, course_name)
        try:
             ensure_dir_exists(course_folder) # Call original helper
        except Exception as dir_err:
             print(f"   ERROR: Cannot create/access course folder '{course_folder}'. Skipping course. Error: {dir_err}")
             continue

        course_key = f"{section_name} - {course_name}"
        download_summary[course_key] = {"downloaded": 0, "skipped": 0, "errors": 0, "files": []}

        try:
            # Navigate to course page
            print(f"   Navigating to course page...")
            driver.get(course_url)
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.course-content, ul.topics, ul.weeks"))
            )
            time.sleep(3)

            course_page_html = driver.page_source
            course_soup = BeautifulSoup(course_page_html, 'html.parser')

            # Update session cookies
            selenium_cookies = driver.get_cookies()
            for cookie in selenium_cookies:
                 try:
                     session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain'), path=cookie.get('path', '/'))
                 except Exception: pass

            # Find potential resources
            potential_resources = course_soup.select(
                'li.modtype_filewithwatermark .activityinstance > a.aalink, '
                'li.modtype_resource .activityinstance > a.aalink, '
                'a[href*=".pdf"]'
            )

            if not potential_resources:
                print("   No potential PDF links or resource pages found.")
                continue

            print(f"   Found {len(potential_resources)} potential links/resources. Checking...")
            processed_pdf_urls = set()

            for link in potential_resources:
                href = link.get('href')
                link_text_element = link.find('span', class_='instancename')
                link_text = link_text_element.get_text(strip=True) if link_text_element else link.get_text(strip=True)
                if not href: continue

                base_filename_from_link = sanitize_filename(link_text)
                pdf_url_to_download = None
                final_filename = None

                try: # Wrap individual link processing
                    # Case 1: Direct link
                    if href.lower().endswith(".pdf"):
                        pdf_url_to_download = urljoin(course_url, href)
                        filename_from_url = sanitize_filename(os.path.basename(pdf_url_to_download.split('?')[0]))
                        final_filename = base_filename_from_link if (not filename_from_url or filename_from_url.lower() == ".pdf") else filename_from_url
                        print(f"   + Direct PDF link found: {link_text}")

                    # Case 2: Intermediate page
                    elif '/mod/filewithwatermark/view.php' in href or '/mod/resource/view.php' in href:
                        resource_url = urljoin(course_url, href)
                        print(f"   ? Investigating resource: {link_text} ({resource_url})")
                        try:
                            res_page = session.get(resource_url, allow_redirects=True, timeout=30)
                            res_page.raise_for_status()
                            content_type = res_page.headers.get('content-type', '').lower()
                            content_disposition = res_page.headers.get('content-disposition', '')

                            if 'application/pdf' in content_type:
                                print("     -> Resource page redirected directly to PDF.")
                                pdf_url_to_download = res_page.url
                                if 'filename=' in content_disposition:
                                    disp_match = re.search(r'filename\*?=(?:UTF-8\'\')?([^\s;\"]+|\".*?\")', content_disposition, re.IGNORECASE)
                                    if disp_match: final_filename = sanitize_filename(disp_match.group(1).strip('"'))
                                if not final_filename:
                                    filename_from_url = sanitize_filename(os.path.basename(pdf_url_to_download.split('?')[0]))
                                    final_filename = base_filename_from_link if (not filename_from_url or filename_from_url.lower() == ".pdf") else filename_from_url
                            else:
                                res_soup = BeautifulSoup(res_page.content, 'html.parser')
                                actual_pdf_link_element = res_soup.select_one(
                                    'div.resourceworkaround a[href*=".pdf"], a.realworkaround[href*=".pdf"], '
                                    'div.resourcecontent a[href*=".pdf"], object[data*=".pdf"], embed[src*=".pdf"], '
                                    'div#region-main a[href*=".pdf"]'
                                )
                                if actual_pdf_link_element:
                                    pdf_href = actual_pdf_link_element.get('href') or actual_pdf_link_element.get('data') or actual_pdf_link_element.get('src')
                                    if pdf_href:
                                        pdf_url_to_download = urljoin(resource_url, pdf_href)
                                        filename_from_url = sanitize_filename(os.path.basename(pdf_url_to_download.split('?')[0]))
                                        final_filename = base_filename_from_link if (not filename_from_url or filename_from_url.lower() == ".pdf") else filename_from_url
                                        print(f"     -> Found PDF link on resource page: {final_filename}")
                                    else: print(f"     - Resource page link found, but couldn't extract PDF URL.")
                                else: print(f"     - Could not find direct PDF link on resource page HTML.")
                        except requests.exceptions.Timeout:
                            print(f"     ERROR accessing resource page (Timeout): {resource_url}")
                            download_summary[course_key]["errors"] += 1
                        except requests.exceptions.RequestException as req_err:
                            print(f"     ERROR accessing resource page {resource_url}: {req_err}")
                            download_summary[course_key]["errors"] += 1
                        except Exception as parse_err:
                            print(f"     ERROR parsing resource page {resource_url}: {parse_err}")
                            download_summary[course_key]["errors"] += 1

                    # --- Download if found ---
                    if pdf_url_to_download and final_filename:
                        if pdf_url_to_download in processed_pdf_urls:
                            continue
                        processed_pdf_urls.add(pdf_url_to_download)
                        if not final_filename.lower().endswith('.pdf'): final_filename += ".pdf"
                        filepath = os.path.join(course_folder, final_filename)

                        if os.path.exists(filepath):
                            print(f"   SKIPPING (exists): {final_filename}")
                            download_summary[course_key]["skipped"] += 1
                            download_summary[course_key]["files"].append(f"{final_filename} (Skipped)")
                            continue

                        print(f"   Downloading: {final_filename}...")
                        try:
                            response = session.get(pdf_url_to_download, stream=True, timeout=120)
                            response.raise_for_status()
                            with open(filepath, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            print(f"   SUCCESS: Saved {final_filename}")
                            download_summary[course_key]["downloaded"] += 1
                            download_summary[course_key]["files"].append(f"{final_filename} (Downloaded)")
                            time.sleep(0.5)

                        except requests.exceptions.Timeout:
                            print(f"   ERROR downloading {final_filename} (Timeout)")
                            download_summary[course_key]["errors"] += 1
                            download_summary[course_key]["files"].append(f"{final_filename} (Error: Timeout)")
                        except requests.exceptions.RequestException as req_err:
                            print(f"   ERROR downloading {final_filename}: {req_err}")
                            download_summary[course_key]["errors"] += 1
                            download_summary[course_key]["files"].append(f"{final_filename} (Error: {req_err})")
                        except Exception as e:
                            print(f"   ERROR saving {final_filename}: {e}")
                            download_summary[course_key]["errors"] += 1
                            download_summary[course_key]["files"].append(f"{final_filename} (Error: {e})")
                            if os.path.exists(filepath):
                                  try: os.remove(filepath)
                                  except: pass
                except Exception as inner_err:
                     print(f"   UNEXPECTED ERROR processing link '{link_text}': {inner_err}")
                     download_summary[course_key]["errors"] += 1
            # End loop through links
            time.sleep(1) # Delay between courses

        except Exception as e:
            print(f"   MAJOR ERROR processing course {course_name}: {e}")
            if course_key not in download_summary:
                 download_summary[course_key] = {"downloaded": 0, "skipped": 0, "errors": 0, "files": []}
            download_summary[course_key]["errors"] += 1
    # End loop through courses

finally:
    # --- Cleanup ---
    if driver:
        print("\nClosing browser...")
        driver.quit()
        print("Browser closed.")

    # --- Final Report ---
    print("\n--- Download Summary ---")
    total_downloaded = 0
    total_skipped = 0
    total_errors = 0
    total_courses_processed = 0
    # Sort summary by course key (Section Name - Course Name)
    sorted_summary = sorted(download_summary.items())

    for course_id, status in sorted_summary:
        total_courses_processed += 1
        print(f"\nCourse: {course_id}") # course_id includes section name
        print(f"  Downloaded: {status['downloaded']}")
        print(f"  Skipped:    {status['skipped']}")
        print(f"  Errors:     {status['errors']}")
        if status['files']:
             print("  Files Processed:")
             for file_status in sorted(status['files']):
                  print(f"   - {file_status}")
        total_downloaded += status['downloaded']
        total_skipped += status['skipped']
        total_errors += status['errors']

    print("\n--- Overall Totals ---")
    print(f"Courses Found: {len(courses_to_download)}")
    print(f"Courses Processed (attempted): {total_courses_processed}")
    print(f"Total PDFs Downloaded: {total_downloaded}")
    print(f"Total PDFs Skipped (already existed): {total_skipped}")
    print(f"Total Errors (pages/downloads): {total_errors}")
    print(f"\nDownloads attempted in: {DOWNLOAD_BASE_DIR}")
    print("\nScript finished.")