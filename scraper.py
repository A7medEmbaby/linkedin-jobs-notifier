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
import os, time, json

load_dotenv()
LINKEDIN_URL = os.getenv('LINKEDIN_URL')
SELENIUM_USER_DATA_DIR = os.getenv('SELENIUM_USER_DATA_DIR')

def get_recent_roles():
    options = Options()
    options.add_argument(f"user-data-dir={SELENIUM_USER_DATA_DIR}")
    driver = webdriver.Chrome(options=options, service=ChromeService(executable_path=ChromeDriverManager().install()))

    try:
        # Open LinkedIn URL
        driver.get(LINKEDIN_URL)
        print(f"Opened URL: {driver.current_url}")
        
        # Wait longer for page to load
        time.sleep(10) 
        
        # Check if we're on a login page
        if "login" in driver.current_url.lower() or "authwall" in driver.current_url.lower():
            print("ERROR: Not logged in! Run log_in_to_linkedin.py again")
            driver.quit()
            return []

        # Try multiple selectors for job cards
        positions = []
        selectors = [
            "li.jobs-search-results__list-item",
            ".scaffold-layout__list-item",
            ".job-card-container",
            "[data-job-id]"
        ]
        
        for selector in selectors:
            positions = driver.find_elements(By.CSS_SELECTOR, selector)
            if positions:
                print(f"Found {len(positions)} positions using selector: {selector}")
                break
        
        if not positions:
            print("ERROR: Could not find any job listings on the page")
            print(f"Current URL: {driver.current_url}")
            print("Try running debug_linkedin.py to diagnose the issue")
            driver.quit()
            return []

        # Scroll to load more postings
        try:
            scroll_container = driver.find_element(By.CSS_SELECTOR, ".jobs-search-results-list")
            for i in range(5):
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)
                time.sleep(1)
        except:
            # If scrolling fails, try alternative method
            for i in range(5):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)

        # Re-fetch positions after scrolling
        positions = driver.find_elements(By.CSS_SELECTOR, selector)
        print(f"After scrolling, found {len(positions)} positions")

        # Get roles
        roles = []
        for position in positions:
            try:
                # Check if promoted (try multiple selectors)
                promoted = False
                try:
                    footer = position.find_element(By.CSS_SELECTOR, ".job-card-container__footer-item")
                    if "Promoted" in footer.text or "promoted" in footer.text.lower():
                        promoted = True
                except:
                    # Try alternative promoted indicator
                    try:
                        promoted_tag = position.find_element(By.CSS_SELECTOR, "[data-promoted='true']")
                        promoted = True
                    except:
                        pass
                
                if promoted:
                    continue

                # Get company name (try multiple selectors)
                company = None
                company_selectors = [
                    ".job-card-container__primary-description",
                    ".job-card-container__company-name",
                    ".artdeco-entity-lockup__subtitle",
                    ".job-card-list__company-name"
                ]
                for comp_sel in company_selectors:
                    try:
                        company = position.find_element(By.CSS_SELECTOR, comp_sel).text
                        if company:
                            break
                    except:
                        continue
                
                if not company:
                    continue

                # Get job link (try multiple selectors)
                link = None
                link_selectors = [
                    "a.job-card-list__title",
                    "a.job-card-container__link",
                    "a[data-job-id]"
                ]
                for link_sel in link_selectors:
                    try:
                        link_element = position.find_element(By.CSS_SELECTOR, link_sel)
                        link = link_element.get_attribute('href').split('?')[0]
                        if link:
                            break
                    except:
                        continue
                
                if not link:
                    continue

                # Get job title
                title = None
                title_selectors = [
                    "a.job-card-list__title",
                    ".job-card-list__title",
                    ".artdeco-entity-lockup__title"
                ]
                for title_sel in title_selectors:
                    try:
                        title = position.find_element(By.CSS_SELECTOR, title_sel).text
                        if title:
                            break
                    except:
                        continue
                
                if not title:
                    continue

                # Get company picture
                picture = None
                try:
                    picture = position.find_element(By.CSS_SELECTOR, "img").get_attribute('src')
                except:
                    picture = "https://via.placeholder.com/100"  # Fallback image

                roles.append((company, title, link, picture))
                
            except Exception as e:
                print(f"Error parsing position: {str(e)}")
                continue

        print(f"Successfully parsed {len(roles)} roles")
        driver.quit()
        return roles
        
    except Exception as e:
        print(f"Fatal error in get_recent_roles: {str(e)}")
        driver.quit()
        return []

if __name__ == "__main__":
    roles = get_recent_roles()
    print(json.dumps(roles, indent=1))