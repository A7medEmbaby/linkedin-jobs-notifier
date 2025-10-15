import discord, asyncio
import scraper
import wuzzuf_scraper
import os, sys, json
import urllib.parse
import datetime
from dotenv import load_dotenv
import logging

# Configure logging to reduce Discord.py verbosity
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)

# Set Discord logging to ERROR (only show errors, hide reconnection warnings)
logging.getLogger('discord').setLevel(logging.ERROR)
logging.getLogger('discord.gateway').setLevel(logging.ERROR)
logging.getLogger('discord.http').setLevel(logging.ERROR)
logging.getLogger('discord.client').setLevel(logging.ERROR)

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
NEW_POSTINGS_CHANNEL_ID = int(os.getenv('NEW_POSTINGS_CHANNEL_ID'))
DEBUG_CHANNEL_ID = int(os.getenv('DEBUG_CHANNEL_ID'))
COMPANIES_CHANNEL_ID = int(os.getenv('COMPANIES_CHANNEL_ID'))
WUZZUF_URLS_UNFILTERED = os.getenv('WUZZUF_URLS_UNFILTERED', '')
WUZZUF_URLS_FILTERED = os.getenv('WUZZUF_URLS_FILTERED', '')
POSTED_JOBS_EXPIRATION_PERIOD_HOURS = int(os.getenv('POSTED_JOBS_EXPIRATION_PERIOD_HOURS', 24))
SHOW_DETAILED_LOGS = os.getenv('SHOW_DETAILED_LOGS', 'False').lower() == 'true'


# Instantiated after bot is logged in
NEW_POSTINGS_CHANNEL = None
DEBUG_CHANNEL = None
COMPANIES_CHANNEL = None

# Flag to prevent multiple task instances
TASK_STARTED = False

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    global NEW_POSTINGS_CHANNEL, DEBUG_CHANNEL, COMPANIES_CHANNEL, TASK_STARTED
    
    print(f'✓ Bot logged in as {bot.user.name}')
    print('-' * 60)

    NEW_POSTINGS_CHANNEL = bot.get_channel(NEW_POSTINGS_CHANNEL_ID)
    DEBUG_CHANNEL = bot.get_channel(DEBUG_CHANNEL_ID)
    COMPANIES_CHANNEL = bot.get_channel(COMPANIES_CHANNEL_ID)

    # Only start the task once, even if bot reconnects
    if not TASK_STARTED:
        TASK_STARTED = True
        bot.loop.create_task(get_new_roles_postings_task())

@bot.event
async def on_disconnect():
    print("⚠️  Discord connection lost (normal during long scraping)")

@bot.event
async def on_resumed():
    print("✓ Discord connection restored")

@bot.event
async def on_message(message):
    async def add_to_blacklist(companies):
        config = get_config()
        blacklist = set(config["blacklist"])

        for company in companies:
            blacklist.add(company)

        confirmation_string = ""
        for company in blacklist.difference(set(config["blacklist"])):
            confirmation_string += company + ", "
        if not confirmation_string:
            confirmation_string = "No companies were added to the blacklist."
        else:
            confirmation_string = "Added " + confirmation_string[:-2] + " to the blacklist!"

        config["blacklist"] = list(blacklist)
        save_config(config)
        await COMPANIES_CHANNEL.send(confirmation_string)

    async def remove_from_blacklist(companies):
        config = get_config()
        blacklist = set(config["blacklist"])

        for company in companies:
            blacklist.discard(company)

        confirmation_string = ""
        for company in set(config["blacklist"]).difference(blacklist):
            confirmation_string += company + ", "
        if len(confirmation_string) == 0:
            confirmation_string = "No companies were removed from the blacklist."
        else:
            confirmation_string = "Removed " + confirmation_string[:-2] + " from the blacklist!"

        config["blacklist"] = list(blacklist)
        save_config(config)
        await COMPANIES_CHANNEL.send(confirmation_string)

    if message.author.bot:
        return

    if message.content.splitlines()[0] == "!blacklist":
        await add_to_blacklist(message.content.splitlines()[1:])

    elif message.content.splitlines()[0] == "!unblacklist":
        await remove_from_blacklist(message.content.splitlines()[1:])

async def safe_send(channel, content=None, embed=None, max_retries=3):
    """Send message with retry logic to handle disconnections"""
    for attempt in range(max_retries):
        try:
            if embed:
                return await channel.send(embed=embed)
            else:
                return await channel.send(content)
        except (discord.HTTPException, discord.ConnectionClosed) as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                print(f"⚠️  Failed to send message after {max_retries} attempts")
                return None
                
def prune_old_jobs():
    """Checks the config file and removes job links older than POSTED_JOBS_EXPIRATION_PERIOD_HOURS."""
    config = get_config()
    posted_jobs = config.get("posted", {})

    # --- Backward Compatibility: Convert old list format to new dict format ---
    if isinstance(posted_jobs, list):
        print("  - Updating config format for posted jobs...")
        new_posted = {link: datetime.datetime.now().isoformat() for link in posted_jobs}
        config["posted"] = new_posted
        save_config(config)
        # No pruning on first conversion, just update the format
        return
    # --- End Compatibility ---

    now = datetime.datetime.now()
    expiration_time = datetime.timedelta(hours=POSTED_JOBS_EXPIRATION_PERIOD_HOURS)
    
    # Create a new dictionary with only the non-expired jobs
    updated_posted_jobs = {}
    expired_count = 0
    for link, timestamp_str in posted_jobs.items():
        try:
            post_time = datetime.datetime.fromisoformat(timestamp_str)
            if now - post_time < expiration_time:
                updated_posted_jobs[link] = timestamp_str
            else:
                expired_count += 1
        except (ValueError, TypeError):
            # If timestamp is invalid, just drop it
            expired_count += 1

    if expired_count > 0:
        print(f"  - Pruned {expired_count} old job link(s) from history (older than {POSTED_JOBS_EXPIRATION_PERIOD_HOURS} hours).")
        config["posted"] = updated_posted_jobs
        save_config(config)


async def get_new_roles_postings_task():
    async def send_new_roles():
        async def send_companies_list(companies):
            companies_list_string = "Found jobs from these new companies:\n"
            for company in companies:
                companies_list_string += company + "\n"
            await safe_send(COMPANIES_CHANNEL, companies_list_string)

        def get_google_url(company):
            base = "https://www.google.com/search?q="
            return base + urllib.parse.quote_plus(company)

        # Prune old jobs before starting the scrape cycle
        prune_old_jobs()

        config = get_config()
        # 'posted' is now a dictionary, so we check against its keys
        posted_links = set(config.get("posted", {}).keys()) 
        blacklist = set(config["blacklist"])

        scrape_start_time = datetime.datetime.now()
        print(f"\n{'='*60}")
        print(f"[{scrape_start_time.strftime('%H:%M:%S')}] 🔍 Starting job search cycle...")
        print(f"{'='*60}")
        await safe_send(DEBUG_CHANNEL, f"🔍 **Starting job search cycle** at {scrape_start_time.strftime('%H:%M:%S')}")
        
        # Scrape LinkedIn
        print("Scraping LinkedIn...")
        await safe_send(DEBUG_CHANNEL, "⏳ Scraping LinkedIn...")
        linkedin_roles = scraper.get_recent_roles(show_details=SHOW_DETAILED_LOGS)

        # Scrape Wuzzuf if configured
        wuzzuf_roles = []
        if WUZZUF_URLS_UNFILTERED or WUZZUF_URLS_FILTERED:
            print("Scraping Wuzzuf...")
            await safe_send(DEBUG_CHANNEL, "⏳ Scraping Wuzzuf...")
            wuzzuf_roles = wuzzuf_scraper.get_wuzzuf_roles(show_details=SHOW_DETAILED_LOGS)
        
        # Combine and process
        all_roles = linkedin_roles + wuzzuf_roles
        
        unique_roles_to_post = []
        seen_links = set()
        
        if SHOW_DETAILED_LOGS and all_roles:
            print(f"--- Processing {len(all_roles)} total roles found ---")
        
        for role in all_roles:
            company, title, link, _, _ = role 
            
            if link in seen_links:
                if SHOW_DETAILED_LOGS: print(f"  - Skipping (duplicate link in this run): {title} at {company}")
                continue
            seen_links.add(link)

            if link in posted_links:
                if SHOW_DETAILED_LOGS: print(f"  - Skipping (already posted): {title} at {company}")
                continue

            if company in blacklist:
                if SHOW_DETAILED_LOGS: print(f"  - Skipping (blacklisted company): {title} at {company}")
                continue

            if SHOW_DETAILED_LOGS: print(f"  - ✓ Adding to post queue: {title} at {company}")
            unique_roles_to_post.append(role)
        
        if unique_roles_to_post:
             print(f"--- Found {len(unique_roles_to_post)} new, unique, non-blacklisted jobs to post ---")

        companies_for_this_run = set()
        
        for role in unique_roles_to_post:
            company, title, link, picture, posted_time = role
            
            companies_for_this_run.add(company)
            # Add new job to config with current timestamp
            config["posted"][link] = datetime.datetime.now().isoformat()

            source = "Wuzzuf" if "wuzzuf.net" in link else "LinkedIn"
            
            embed = discord.Embed(title=title, url=link, color=discord.Color.from_str("#378CCF"), timestamp=datetime.datetime.now())
            embed.set_author(name=company, url=get_google_url(company))
            embed.add_field(name="Posted", value=posted_time, inline=True)
            embed.add_field(name="Source", value=source, inline=True)
            embed.set_thumbnail(url=picture)
            await safe_send(NEW_POSTINGS_CHANNEL, embed=embed)
        
        scrape_end_time = datetime.datetime.now()
        scrape_duration = (scrape_end_time - scrape_start_time).total_seconds()
        
        print(f"\n{'='*60}")
        if unique_roles_to_post:
            await send_companies_list(companies_for_this_run)
            save_config(config)
            print(f"✓ Posted {len(unique_roles_to_post)} new jobs from {len(companies_for_this_run)} companies")
            print(f"⏱️  Scraping took {int(scrape_duration // 60)} minutes {int(scrape_duration % 60)} seconds")
            await safe_send(DEBUG_CHANNEL, f"✅ **Posted {len(unique_roles_to_post)} new jobs** from {len(companies_for_this_run)} companies\n⏱️ Scraping took {int(scrape_duration // 60)}m {int(scrape_duration % 60)}s")
        else:
            print(f"✓ No new jobs found to post.")
            print(f"⏱️  Scraping took {int(scrape_duration // 60)} minutes {int(scrape_duration % 60)} seconds")
            await safe_send(DEBUG_CHANNEL, f"ℹ️ No new jobs found to post\n⏱️ Scraping took {int(scrape_duration // 60)}m {int(scrape_duration % 60)}s")
        
        print(f"{'='*60}\n")

    cycle_number = 0
    while True:
        cycle_number += 1
        try:
            await send_new_roles()
            
            next_check_time = datetime.datetime.now() + datetime.timedelta(minutes=20)
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 😴 Waiting 20 minutes... (Cycle {cycle_number} complete)")
            print(f"[Next check at {next_check_time.strftime('%H:%M:%S')}]\n")
            await safe_send(DEBUG_CHANNEL, f'😴 **Waiting 20 minutes** before next check...\n⏰ Next check at: {next_check_time.strftime("%H:%M:%S")}')
            
            await asyncio.sleep(60 * 20)  # Wait 20 minutes
            
        except Exception as e:
            error_msg = f'Error occurred: {str(e)}'
            print(f"\n{'='*60}")
            print(f"✗ {error_msg}")
            print(f"{'='*60}\n")
            await safe_send(DEBUG_CHANNEL, f'❌ **Error occurred:** {error_msg}\n⏳ Retrying in 20 minutes...')
            await asyncio.sleep(60 * 20)

def get_config():
    with open(os.path.join(sys.path[0], 'config.json')) as f:
        config = json.load(f)
        return config

def save_config(config):
    with open(os.path.join(sys.path[0], 'config.json'), 'w') as f:
        f.seek(0)
        json.dump(config, f, indent=4)
        f.truncate()

print("Starting LinkedIn Jobs Notifier Bot...")
print("=" * 60)
bot.run(BOT_TOKEN, reconnect=True)