from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
import os, sys, time, json, re, datetime
import logging

# Suppress Selenium and WebDriver Manager logs
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('WDM').setLevel(logging.WARNING)

load_dotenv()
LINKEDIN_URLS_UNFILTERED = os.getenv('LINKEDIN_URLS_UNFILTERED', '')
LINKEDIN_URLS_FILTERED = os.getenv('LINKEDIN_URLS_FILTERED', '')
SELENIUM_USER_DATA_DIR = os.getenv('SELENIUM_USER_DATA_DIR')

def load_keywords_from_env(env_var_name):
    """Loads keywords from a multi-line .env variable."""
    keywords_str = os.getenv(env_var_name, '')
    if not keywords_str:
        return []
    return [line.strip() for line in keywords_str.strip().splitlines() if line.strip()]

JOB_KEYWORDS = load_keywords_from_env('JOB_KEYWORDS')
EXCLUDED_KEYWORDS = load_keywords_from_env('EXCLUDED_KEYWORDS')


def parse_multiline_urls(url_string):
    """Parses a multi-line string of URLs, ignoring comments and empty lines."""
    parsed_urls = []
    if not url_string or not url_string.strip():
        return parsed_urls

    lines = url_string.strip().splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        parts = line.split('#', 1)
        url = parts[0].strip()
        note = parts[1].strip() if len(parts) > 1 else None
        
        if url:
            parsed_urls.append((url, note))
            
    return parsed_urls

def init_driver():
    """Initialize Chrome driver with options"""
    options = Options()
    options.add_argument(f"user-data-dir={SELENIUM_USER_DATA_DIR}")
    options.add_argument("--headless=new") 
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    service = ChromeService(executable_path=ChromeDriverManager().install())
    service.log_path = os.devnull
    
    return webdriver.Chrome(options=options, service=service)

def check_keywords_in_text(text, return_details=False):
    """Check if text contains any JOB_KEYWORDS and none of the EXCLUDED_KEYWORDS."""
    if not text:
        return (False, [], []) if return_details else False
    
    text_lower = text.lower()
    
    # Check for excluded keywords first
    excluded_found = []
    for keyword in EXCLUDED_KEYWORDS:
        if keyword.lower() in text_lower:
            excluded_found.append(keyword)
    
    if excluded_found:
        return (False, [], excluded_found) if return_details else False
    
    # Check for required keywords
    keywords_found = []
    for keyword in JOB_KEYWORDS:
        if keyword.lower() in text_lower:
            keywords_found.append(keyword)
    
    has_keywords = len(keywords_found) > 0
    
    if return_details:
        return (has_keywords, keywords_found, [])
    return has_keywords

def get_config():
    """Load config from config.json"""
    config_path = os.path.join(sys.path[0], 'config.json')
    
    try:
        with open(config_path) as f:
            config = json.load(f)
            if "last_job_per_source" not in config:
                config["last_job_per_source"] = {}
            if "posted" not in config:
                config["posted"] = {}
            return config
    except (FileNotFoundError, json.JSONDecodeError):
        # Return default config if file doesn't exist or is invalid
        return {
            "posted": {},
            "last_job_per_source": {}
        }

def get_stop_marker(url):
    """Get the stop marker (last job) for a LinkedIn URL if it exists."""
    config = get_config()
    last_job_per_source = config.get("last_job_per_source", {})
    
    if url not in last_job_per_source:
        return None
    
    marker_data = last_job_per_source[url]
    marker_link = marker_data.get("job_link")
    
    # Return the marker link directly - no need to verify it's in posted
    # The marker might be a job that didn't pass filters but is still valid as a stop point
    return marker_link if marker_link else None

def parse_job_listings(driver, check_keywords, show_details, stop_marker=None):
    """Parse job listings from current page. Returns (roles, hit_stop_marker, first_job_link_on_page)"""
    master_selector = "li.occludable-update"
    positions = driver.find_elements(By.CSS_SELECTOR, master_selector)
    num_positions = len(positions)
    
    if show_details:
        print(f"\n  --- Parsing {num_positions} Job Cards ---")
        if stop_marker:
            print(f"  - Stop marker active: {stop_marker}")
    
    roles = []
    promoted_included = 0
    skipped_no_keywords = 0
    hit_stop_marker = False
    first_job_link_on_page = None  # Track the very first job link we encounter

    # Iterate by index
    for i in range(num_positions):
        if show_details:
            print(f"\n  --- Processing Card {i+1}/{num_positions} ---")
        
        try:
            # Re-find elements on each iteration
            positions = driver.find_elements(By.CSS_SELECTOR, master_selector)
            if i >= len(positions):
                if show_details:
                    print(f"    - ✗ Card index {i+1} is out of bounds. Ending page parse.")
                break
            
            position = positions[i]

            # Scroll card into view
            driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });", position)
            time.sleep(0.3)

            # Check if promoted
            promoted = False
            try:
                footer_items = position.find_elements(By.CSS_SELECTOR, ".job-card-container__footer-item")
                for item in footer_items:
                    if "promoted" in item.text.lower():
                        promoted = True
                        promoted_included += 1
                        if show_details:
                            print("    - Status: Promoted")
                        break
            except:
                pass

            # Get company name
            company = "N/A"
            try:
                company = position.find_element(By.CSS_SELECTOR, ".artdeco-entity-lockup__subtitle").text.strip()
            except:
                try:
                    company = position.find_element(By.CSS_SELECTOR, ".job-card-container__primary-description").text.strip()
                except:
                    if show_details: 
                        print("    - ✗ Company name not found.")
            if show_details: 
                print(f"    - Company: {company}")

            # Get job link
            link = ""
            try:
                link_element = position.find_element(By.CSS_SELECTOR, "a[href*='/jobs/view/']")
                link = link_element.get_attribute('href').split('?')[0]
            except Exception as e:
                if show_details: 
                    print(f"    - ✗ Job link not found. Error: {e}")
                continue
            if show_details: 
                print(f"    - Link: {link}")
            
            # CRITICAL: Track the very first job link on the page (for stop marker)
            if first_job_link_on_page is None:
                first_job_link_on_page = link
            
            # CHECK FOR STOP MARKER - This is the key optimization!
            if stop_marker and link == stop_marker:
                if show_details:
                    print(f"    - ⚠️  STOP MARKER HIT! Stopping scrape at this job.")
                else:
                    print(f"\n  ⚠️  Stop marker hit! Ending scrape early.")
                hit_stop_marker = True
                break  # Stop immediately when we hit the marker
                
            # Get job title
            title = "N/A"
            try:
                title = position.find_element(By.CSS_SELECTOR, "a.job-card-container__link strong").text.strip()
            except:
                if show_details: 
                    print("    - ✗ Job title not found.")
            if show_details: 
                print(f"    - Title: {title}")

            # Get posted time
            posted_time = "N/A"
            try:
                posted_time = position.find_element(By.CSS_SELECTOR, "time").get_attribute("datetime")
            except:
                if show_details: 
                    print("    - ✗ Posted time not found.")

            # Keyword check if enabled
            if check_keywords:
                if show_details:
                    print("    - Checking keywords...")
                try:
                    # Get more detailed text for keyword matching
                    full_text = f"{title} {company}"
                    try:
                        desc = position.find_element(By.CSS_SELECTOR, ".job-card-container__job-insight-text").text
                        full_text += f" {desc}"
                    except:
                        pass
                    
                    found, keywords_found, excluded_found = check_keywords_in_text(full_text, return_details=True)
                    
                    if show_details:
                        if keywords_found:
                            print(f"      - ✓ Keywords found: {', '.join(keywords_found)}")
                        if excluded_found:
                            print(f"      - ✗ Excluded keywords found: {', '.join(excluded_found)}")
                        if not found and not excluded_found:
                            print(f"      - No matching keywords")
                    
                    if not found:
                        skipped_no_keywords += 1
                        if show_details:
                            print("    - Result: SKIPPED (keyword filter)")
                        continue
                        
                except Exception as e:
                    if show_details:
                        print(f"      - ✗ Error checking keywords: {e}")
                    # If we can't check keywords, skip this job to be safe
                    skipped_no_keywords += 1
                    continue

            # Get company picture
            picture = "https://via.placeholder.com/100"
            try:
                img_element = position.find_element(By.CSS_SELECTOR, "img")
                picture = img_element.get_attribute('src')
            except:
                pass

            roles.append((company, title, link, picture, posted_time))
            if show_details:
                print("    - Result: ADDED to list")
            
        except Exception as e:
            if show_details:
                print(f"    - ✗ UNEXPECTED ERROR parsing card {i+1}: {e}")
            continue
    
    if show_details:
        print("\n  --- Parsing Summary ---")
        summary = f"  Found {len(roles)} jobs from {num_positions} cards"
        if promoted_included > 0:
            summary += f" ({promoted_included} promoted)"
        if skipped_no_keywords > 0:
            summary += f", skipped {skipped_no_keywords} on keyword filter"
        if hit_stop_marker:
            summary += " [STOPPED EARLY]"
        print(summary)
    
    return roles, hit_stop_marker, first_job_link_on_page

def scrape_url(url, check_keywords=False, show_details=False):
    """Scrape a single LinkedIn URL with pagination and smart early stopping."""
    driver = init_driver()
    driver.set_page_load_timeout(300)
    all_roles = []
    first_job_link = None  # Track the first job we scrape
    
    # Get stop marker for this URL
    stop_marker = get_stop_marker(url)
    if stop_marker:
        if show_details:
            print(f"  ℹ️  Stop marker found for this URL")
        else:
            print(f"  ℹ️  Using stop marker for early stopping")
    
    try:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        driver.get(url)
        time.sleep(10)
        
        if "login" in driver.current_url.lower() or "authwall" in driver.current_url.lower():
            print("  ✗ Not logged in! Please run: python log_in_to_linkedin.py")
            driver.quit()
            return [], None

        page_number = 1
        jobs_per_page = 25
        max_pages = 10
        stopped_early = False
        
        while page_number <= max_pages:
            if show_details:
                print(f"\n  --- Page {page_number} ---")
            else:
                print(f"  Page {page_number}...", end=" ")

            # Navigate to the page
            if page_number > 1:
                parsed_url = urlparse(url)
                query_params = parse_qs(parsed_url.query)
                query_params['start'] = [(page_number - 1) * jobs_per_page]
                new_query = urlencode(query_params, doseq=True)
                page_url = urlunparse((
                    parsed_url.scheme,
                    parsed_url.netloc,
                    parsed_url.path,
                    parsed_url.params,
                    new_query,
                    parsed_url.fragment
                ))
                driver.get(page_url)
                time.sleep(5)
            
            # Scroll to load all jobs
            if show_details:
                print("  - Scrolling to load all jobs on the page...")
            else:
                print("Scrolling...", end=" ")

            try:
                scroll_container = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".scaffold-layout__list"))
                )
                
                last_height = driver.execute_script("return arguments[0].scrollHeight", scroll_container)
                scroll_attempts = 0
                max_scroll_attempts = 20

                while scroll_attempts < max_scroll_attempts:
                    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)
                    time.sleep(2.5)
                    new_height = driver.execute_script("return arguments[0].scrollHeight", scroll_container)
                    
                    if new_height == last_height:
                        break
                    last_height = new_height
                    scroll_attempts += 1
                
                if show_details:
                    print("  - Scrolling complete.")
                else:
                    print("Done.", end=" ")

            except Exception as e:
                if show_details:
                    print(f"    ✗ Could not find scroll container or scroll failed: {e}")
                else:
                    print("Scroll failed.", end=" ")

            # Get the actual number of job cards on this page
            positions = driver.find_elements(By.CSS_SELECTOR, "li.occludable-update")
            actual_jobs_on_page = len(positions)
            
            if show_details:
                print(f"  - Found {actual_jobs_on_page} job cards on this page")
            
            # Parse the jobs with stop marker check
            roles_on_page, hit_stop_marker, first_link_on_page = parse_job_listings(driver, check_keywords, show_details, stop_marker)
            all_roles.extend(roles_on_page)
            
            # Track the first job link we see on page 1 (for updating stop marker later)
            if page_number == 1 and first_link_on_page and not first_job_link:
                first_job_link = first_link_on_page
                if show_details:
                    print(f"  - Tracking first job on page 1 as future stop marker: {first_job_link}")
            
            if not show_details:
                promoted_count = sum(1 for pos in positions if 'promoted' in pos.text.lower())
                print(f"  Found {len(roles_on_page)} jobs ({promoted_count} promoted)")

            # Check if we hit the stop marker
            if hit_stop_marker:
                stopped_early = True
                if not show_details:
                    print(f"  ✓ Early stop: Found all new jobs!")
                break

            # Check if there are fewer job cards than expected (reached end)
            if actual_jobs_on_page < jobs_per_page:
                if show_details:
                    print(f"\n  - Reached the last page (only {actual_jobs_on_page} jobs found, expected {jobs_per_page}).")
                break
            
            # Check if next page button exists and is enabled
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, "button.jobs-search-pagination__button--next")
                if "disabled" in next_button.get_attribute("class") or not next_button.is_enabled():
                    if show_details:
                        print("\n  - Next button is disabled. Reached the last page.")
                    break
            except:
                if show_details:
                    print("\n  - Next button not found. Might be the last page.")
            
            page_number += 1
        
        if stopped_early:
            print(f"\n  ✓ Total from this URL: {len(all_roles)} jobs (stopped early at page {page_number})")
        else:
            print(f"\n  ✓ Total from this URL: {len(all_roles)} jobs")
        
    except Exception as e:
        print(f"  ✗ An error occurred during scraping: {e}")
    finally:
        driver.quit()
    
    return all_roles, first_job_link

def get_recent_roles(show_details=False):
    """Get roles from all configured URLs. Returns (all_roles, stop_markers_dict)"""
    all_roles = []
    stop_markers = {}  # Map URL -> first job link scraped
    
    log_mode = "(Detailed Log Mode)" if show_details else ""
    print("\n" + "="*60)
    print(f"LinkedIn Job Search {log_mode}")
    print("="*60)

    # Scrape unfiltered URLs
    unfiltered_urls = parse_multiline_urls(LINKEDIN_URLS_UNFILTERED)
    if unfiltered_urls:
        for i, (url, note) in enumerate(unfiltered_urls, 1):
            print(f"\n📋 Unfiltered Search {i}/{len(unfiltered_urls)}: {note or 'General'}")
            roles, first_job = scrape_url(url, check_keywords=False, show_details=show_details)
            all_roles.extend(roles)
            if first_job:
                stop_markers[url] = first_job
            if i < len(unfiltered_urls):
                time.sleep(5)

    # Scrape filtered URLs
    filtered_urls = parse_multiline_urls(LINKEDIN_URLS_FILTERED)
    if filtered_urls:
        for i, (url, note) in enumerate(filtered_urls, 1):
            print(f"\n🔍 Filtered Search {i}/{len(filtered_urls)}: {note or 'Keywords'}")
            roles, first_job = scrape_url(url, check_keywords=True, show_details=show_details)
            all_roles.extend(roles)
            if first_job:
                stop_markers[url] = first_job
            if i < len(filtered_urls):
                time.sleep(5)

    print("\n" + "="*60)
    print(f"✓ Search Complete: {len(all_roles)} total jobs found")
    print("="*60 + "\n")
    return all_roles, stop_markers

if __name__ == '__main__':
    show_details_arg = os.getenv('SHOW_DETAILED_LOGS', 'False').lower() == 'true'
    roles, markers = get_recent_roles(show_details=show_details_arg)
    print(f"\nStop markers for next run: {len(markers)} URLs tracked")