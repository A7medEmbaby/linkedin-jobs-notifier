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
import os, time, json, re
import logging

# Suppress Selenium and WebDriver Manager logs
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('WDM').setLevel(logging.WARNING)

load_dotenv()
LINKEDIN_URL = os.getenv('LINKEDIN_URL')
LINKEDIN_KEYWORD_URLS = os.getenv('LINKEDIN_KEYWORD_URLS', '')
SELENIUM_USER_DATA_DIR = os.getenv('SELENIUM_USER_DATA_DIR')

# .NET Keywords
DOTNET_KEYWORDS = [
    ".net", "dotnet", "dot net", ". net",
    ".net core", "dotnet core", "dot net core",
    ".net framework", "dotnet framework",
    ".net 6", ".net 7", ".net 8", ".net 9",
    "dotnet6", "dotnet7", "dotnet8",
    "asp.net", "asp dotnet", "aspdotnet", "asp net",
    "asp.net core", "asp.net core", "aspnetcore",
    "asp.net mvc", "asp.net web api",
    "c#", "c sharp", "csharp", "c #",
    "entity framework", "ef core",
    "blazor", "razor", "wcf", "wpf", "xamarin", "maui",
    "visual studio", "nuget"
]

def init_driver():
    """Initialize Chrome driver with options"""
    options = Options()
    options.add_argument(f"user-data-dir={SELENIUM_USER_DATA_DIR}")
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    service = ChromeService(executable_path=ChromeDriverManager().install())
    service.log_path = os.devnull
    
    return webdriver.Chrome(options=options, service=service)

def check_keywords_in_text(text, return_details=False):
    """Check if any of the .NET keywords exist in the text"""
    if not text:
        if return_details:
            return False, [], {}
        return False
    
    text_lower = text.lower()
    matched_keywords = []
    search_locations = {}
    
    for keyword in DOTNET_KEYWORDS:
        keyword_lower = keyword.lower()
        if keyword_lower in text_lower:
            matched_keywords.append(keyword)
            index = text_lower.find(keyword_lower)
            context_start = max(0, index - 40)
            context_end = min(len(text), index + len(keyword) + 40)
            search_locations[keyword] = text[context_start:context_end]
    
    found = len(matched_keywords) > 0
    
    if return_details:
        return found, matched_keywords, search_locations
    return found

def get_job_description(driver, job_url, job_title, company_name, show_details=False):
    """Get job description from job details page"""
    try:
        if show_details:
            print(f"  Checking: {job_title} at {company_name}")
        
        driver.get(job_url)
        time.sleep(4)
        
        # Try to click "Show more" button
        try:
            show_more_selectors = [
                "button.show-more-less-html__button--more",
                "button.show-more-less-html__button",
                ".jobs-description__footer-button"
            ]
            
            for selector in show_more_selectors:
                try:
                    show_more_btn = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    driver.execute_script("arguments[0].scrollIntoView();", show_more_btn)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", show_more_btn)
                    time.sleep(1)
                    break
                except:
                    continue
        except:
            pass
        
        # Get job description
        description_text = ""
        description_selectors = [
            ".jobs-description__content",
            ".jobs-description-content__text",
            ".jobs-box__html-content",
            ".description__text",
            ".jobs-description",
            "div.jobs-box__html-content",
            "article.jobs-description__container"
        ]
        
        for selector in description_selectors:
            try:
                description_element = driver.find_element(By.CSS_SELECTOR, selector)
                description_text = description_element.text
                if description_text and len(description_text) > 50:
                    break
            except:
                continue
        
        if not description_text:
            return ""
        
        # Check keywords
        found, matched_keywords, locations = check_keywords_in_text(
            f"{job_title} {description_text}", 
            return_details=True
        )
        
        if show_details and found:
            print(f"    ✓ Found keywords: {', '.join(matched_keywords[:5])}")
        
        return description_text
        
    except Exception as e:
        if show_details:
            print(f"    ✗ Error: {str(e)}")
        return ""

def scroll_job_list_to_load_all(driver, show_details=False):
    """Aggressively scroll the job list to load all lazy-loaded jobs"""
    try:
        # Find the scrollable container
        scroll_container = driver.find_element(By.CSS_SELECTOR, ".jobs-search-results-list")
        
        # Get initial job count
        initial_positions = driver.find_elements(By.CSS_SELECTOR, "li.scaffold-layout__list-item")
        initial_count = len(initial_positions)
        
        if show_details:
            print(f"    Initial jobs loaded: {initial_count}")
        
        max_scroll_attempts = 15
        no_change_count = 0
        previous_count = initial_count
        
        for attempt in range(max_scroll_attempts):
            # Scroll to bottom of container
            driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight", 
                scroll_container
            )
            
            # Wait for content to load
            time.sleep(2)
            
            # Check if new jobs loaded
            current_positions = driver.find_elements(By.CSS_SELECTOR, "li.scaffold-layout__list-item")
            current_count = len(current_positions)
            
            if show_details:
                print(f"    Scroll {attempt + 1}: {current_count} jobs")
            
            if current_count == previous_count:
                no_change_count += 1
                if no_change_count >= 3:
                    # No new jobs after 3 attempts, we're done
                    if show_details:
                        print(f"    ✓ All jobs loaded: {current_count} total")
                    break
            else:
                no_change_count = 0
                previous_count = current_count
            
            # Small scroll up and down to trigger lazy load
            driver.execute_script("arguments[0].scrollTop -= 100", scroll_container)
            time.sleep(0.5)
        
        # Final count
        final_positions = driver.find_elements(By.CSS_SELECTOR, "li.scaffold-layout__list-item")
        return final_positions
        
    except Exception as e:
        if show_details:
            print(f"    ⚠ Scroll error: {str(e)}")
        # Return what we have
        try:
            return driver.find_elements(By.CSS_SELECTOR, "li.scaffold-layout__list-item")
        except:
            return []

def parse_job_listings(driver, positions, check_keywords=False, show_details=False):
    """Parse job listings and return roles"""
    roles = []
    skipped_no_keywords = 0
    skipped_no_content = 0
    
    for idx, position in enumerate(positions, 1):
        try:
            # Check if this is an empty placeholder (lazy load not completed)
            try:
                # Check if the list item has actual content
                job_card = position.find_element(By.CSS_SELECTOR, ".job-card-container")
                if not job_card:
                    skipped_no_content += 1
                    continue
            except:
                # No job card found, skip this placeholder
                skipped_no_content += 1
                continue

            # Get company name - FIXED SELECTORS
            company = None
            company_selectors = [
                ".mhmxTfSoLgBKBPGgosykrrZdkyMULGNzPc",  # Updated to match HTML
                ".artdeco-entity-lockup__subtitle",
                ".job-card-container__primary-description",
                "span[dir='ltr']"  # Fallback for company name in span
            ]
            
            for comp_sel in company_selectors:
                try:
                    company_elem = position.find_element(By.CSS_SELECTOR, comp_sel)
                    company = company_elem.text.strip()
                    if company and len(company) > 0:
                        break
                except:
                    continue
            
            if not company:
                if show_details:
                    print(f"    ⚠ Job {idx}: No company found")
                continue

            # Get job link - IMPROVED
            link = None
            link_selectors = [
                "a.job-card-container__link",
                "a[href*='/jobs/view/']",
                ".job-card-list__title--link"
            ]
            
            for link_sel in link_selectors:
                try:
                    link_element = position.find_element(By.CSS_SELECTOR, link_sel)
                    link = link_element.get_attribute('href')
                    if link:
                        # Clean up the URL (remove tracking parameters)
                        link = link.split('?')[0]
                        break
                except:
                    continue
            
            if not link:
                if show_details:
                    print(f"    ⚠ Job {idx}: No link found for {company}")
                continue

            # Get job title - IMPROVED
            title = None
            title_selectors = [
                "a.job-card-container__link strong",
                ".job-card-list__title--link strong",
                "a.job-card-container__link",
                ".artdeco-entity-lockup__title a"
            ]
            
            for title_sel in title_selectors:
                try:
                    title_element = position.find_element(By.CSS_SELECTOR, title_sel)
                    title = title_element.text.strip()
                    if title and len(title) > 0:
                        break
                except:
                    continue
            
            if not title:
                if show_details:
                    print(f"    ⚠ Job {idx}: No title found for {company}")
                continue

            # Check keywords if needed
            if check_keywords:
                description = get_job_description(driver, link, title, company, show_details)
                
                title_and_description = f"{title} {description}"
                found = check_keywords_in_text(title_and_description)
                
                if not found:
                    skipped_no_keywords += 1
                    if show_details:
                        print(f"    ✗ Job {idx}: {title} at {company} - No keywords")
                    continue
                elif show_details:
                    print(f"    ✓ Job {idx}: {title} at {company} - Keywords found")

            # Get company picture
            picture = None
            try:
                img_element = position.find_element(By.CSS_SELECTOR, "img")
                picture = img_element.get_attribute('src')
            except:
                picture = "https://via.placeholder.com/100"

            roles.append((company, title, link, picture))
            
            if show_details:
                print(f"    ✓ Job {idx}: Added '{title}' at {company}")
            
        except Exception as e:
            if show_details:
                print(f"    ✗ Job {idx}: Error - {str(e)}")
            continue
    
    if not show_details:
        summary = f"  Found {len(roles)} jobs"
        if skipped_no_content > 0:
            summary += f" (skipped {skipped_no_content} empty placeholders)"
        if skipped_no_keywords > 0:
            summary += f", filtered out {skipped_no_keywords}"
        print(summary)
    else:
        print(f"  Processed: {len(positions)} | Empty: {skipped_no_content} | No Keywords: {skipped_no_keywords} | Added: {len(roles)}")
    
    return roles

def scrape_url(url, check_keywords=False, show_details=False):
    """Scrape a single LinkedIn URL with pagination"""
    driver = init_driver()
    all_roles = []
    
    try:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        # Check if logged in
        driver.get(url)
        time.sleep(10)
        
        if "login" in driver.current_url.lower() or "authwall" in driver.current_url.lower():
            print("  ✗ Not logged in! Run: python log_in_to_linkedin.py")
            driver.quit()
            return []

        page_number = 1
        jobs_per_page = 25
        max_pages = 10
        
        while page_number <= max_pages:
            if not show_details:
                print(f"  Page {page_number}...", end=" ")
            else:
                print(f"\n  --- Page {page_number} ---")
            
            # Build URL for current page
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            
            if page_number > 1:
                query_params['start'] = [(page_number - 1) * jobs_per_page]
            elif 'start' in query_params:
                del query_params['start']
            
            new_query = urlencode(query_params, doseq=True)
            page_url = urlunparse((
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                parsed_url.params,
                new_query,
                parsed_url.fragment
            ))
            
            if page_number > 1:
                driver.get(page_url)
                time.sleep(5)
            
            # FIXED: Aggressively scroll to load ALL jobs
            if show_details:
                print("  Scrolling to load all jobs...")
            positions = scroll_job_list_to_load_all(driver, show_details)
            
            if not positions or len(positions) == 0:
                if not show_details:
                    print("No jobs")
                else:
                    print("  No jobs found")
                break

            # Parse job listings
            roles = parse_job_listings(driver, positions, check_keywords, show_details)
            all_roles.extend(roles)
            
            if len(roles) < jobs_per_page:
                if not show_details and page_number > 1:
                    print()
                break
            
            page_number += 1
        
        if not show_details:
            print(f"\n  ✓ Total: {len(all_roles)} jobs")
        else:
            print(f"\n  Total from all pages: {len(all_roles)}")
        
    except Exception as e:
        print(f"  ✗ Error: {str(e)}")
    finally:
        driver.quit()
    
    return all_roles

def get_recent_roles(show_details=False):
    """Get roles from all configured URLs"""
    all_roles = []
    
    print("\n" + "="*60)
    print("LinkedIn Job Search")
    print("="*60)
    
    # Scrape main URL
    if LINKEDIN_URL:
        print("\n📋 Main Search (all jobs)")
        roles = scrape_url(LINKEDIN_URL, check_keywords=False, show_details=show_details)
        all_roles.extend(roles)
    
    # Scrape additional URLs with keyword filtering
    if LINKEDIN_KEYWORD_URLS and LINKEDIN_KEYWORD_URLS.strip():
        keyword_urls = [url.strip() for url in LINKEDIN_KEYWORD_URLS.split(',') if url.strip()]
        
        if keyword_urls:
            for i, url in enumerate(keyword_urls, 1):
                print(f"\n🔍 Keyword Search {i}/{len(keyword_urls)} (.NET filtered)")
                roles = scrape_url(url, check_keywords=True, show_details=show_details)
                all_roles.extend(roles)
                
                if i < len(keyword_urls):
                    time.sleep(5)
    
    print("\n" + "="*60)
    print(f"✓ Search Complete: {len(all_roles)} total jobs found")
    print("="*60 + "\n")
    
    return all_roles

if __name__ == "__main__":
    import sys
    
    show_details = "--details" in sys.argv or "-d" in sys.argv
    
    roles = get_recent_roles(show_details=show_details)
    
    if show_details:
        print("\nResults:")
        print(json.dumps(roles, indent=2, ensure_ascii=False))