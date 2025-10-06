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

# Set Discord logging to WARNING (only show warnings and errors)
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.ERROR)
logging.getLogger('discord.http').setLevel(logging.WARNING)

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
NEW_POSTINGS_CHANNEL_ID = int(os.getenv('NEW_POSTINGS_CHANNEL_ID'))
DEBUG_CHANNEL_ID = int(os.getenv('DEBUG_CHANNEL_ID'))
COMPANIES_CHANNEL_ID = int(os.getenv('COMPANIES_CHANNEL_ID'))
WUZZUF_URL = os.getenv('WUZZUF_URL', '')

# Instantiated after bot is logged in
NEW_POSTINGS_CHANNEL = None
DEBUG_CHANNEL = None
COMPANIES_CHANNEL = None

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f'✓ Bot logged in as {bot.user.name}')
    print('-' * 60)

    global NEW_POSTINGS_CHANNEL, DEBUG_CHANNEL, COMPANIES_CHANNEL
    NEW_POSTINGS_CHANNEL = bot.get_channel(NEW_POSTINGS_CHANNEL_ID)
    DEBUG_CHANNEL = bot.get_channel(DEBUG_CHANNEL_ID)
    COMPANIES_CHANNEL = bot.get_channel(COMPANIES_CHANNEL_ID)

    await get_new_roles_postings_task()

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

async def get_new_roles_postings_task():
    async def send_new_roles():
        async def send_companies_list(companies):
            companies_list_string = ""
            for company in companies:
                companies_list_string += company + "\n"
            await COMPANIES_CHANNEL.send(companies_list_string)

        def get_levels_url(company):
            base = "https://www.levels.fyi/internships/?track=Software%20Engineer&timeframe=2023%20%2F%202022&search="
            return base + urllib.parse.quote_plus(company)

        def get_google_url(company):
            base = "https://www.google.com/search?q="
            return base + urllib.parse.quote_plus(company)

        config = get_config()
        posted = set(config["posted"])
        blacklist = set(config["blacklist"])

        scrape_start_time = datetime.datetime.now()
        print(f"\n{'='*60}")
        print(f"[{scrape_start_time.strftime('%H:%M:%S')}] 🔍 Starting job search cycle...")
        print(f"{'='*60}")
        await DEBUG_CHANNEL.send(f"🔍 **Starting job search cycle** at {scrape_start_time.strftime('%H:%M:%S')}")
        
        # Scrape LinkedIn
        print("Scraping LinkedIn...")
        await DEBUG_CHANNEL.send("⏳ Scraping LinkedIn...")
        linkedin_roles = scraper.get_recent_roles()

        # Scrape Wuzzuf if configured
        wuzzuf_roles = []
        if WUZZUF_URL:
            print("Scraping Wuzzuf...")
            await DEBUG_CHANNEL.send("⏳ Scraping Wuzzuf...")
            wuzzuf_roles = wuzzuf_scraper.get_wuzzuf_roles()
        
        # Combine and deduplicate
        all_roles = linkedin_roles + wuzzuf_roles
        
        unique_roles = []
        seen_jobs = set()
        
        for role in all_roles:
            company, title, link, picture = role
            job_key = f"{company} - {title}"
            
            if job_key in seen_jobs or job_key in posted:
                continue
            
            seen_jobs.add(job_key)
            unique_roles.append(role)
        
        companies = set()
        new_roles_count = 0
        
        for role in unique_roles:
            company, title, link, picture = role
            company_and_title = f"{company} - {title}"
            
            if company in blacklist:
                continue

            companies.add(company)
            config["posted"].append(company_and_title)
            posted.add(company_and_title)
            new_roles_count += 1

            source = "Wuzzuf" if "wuzzuf.net" in link else "LinkedIn"
            
            embed = discord.Embed(title=title, url=link, color=discord.Color.from_str("#378CCF"), timestamp=datetime.datetime.now())
            embed.set_author(name=company, url=get_google_url(company))
            embed.add_field(name="Source", value=source, inline=True)
            embed.add_field(name="Levels.fyi Link", value=f"[{company} at Levels.fyi]({get_levels_url(company)})", inline=False)
            embed.set_thumbnail(url=picture)
            await NEW_POSTINGS_CHANNEL.send(embed=embed)
        
        scrape_end_time = datetime.datetime.now()
        scrape_duration = (scrape_end_time - scrape_start_time).total_seconds()
        
        print(f"\n{'='*60}")
        if companies:
            await send_companies_list(companies)
            save_config(config)
            print(f"✓ Posted {new_roles_count} new jobs from {len(companies)} companies")
            print(f"⏱️  Scraping took {int(scrape_duration // 60)} minutes {int(scrape_duration % 60)} seconds")
            await DEBUG_CHANNEL.send(f"✅ **Posted {new_roles_count} new jobs** from {len(companies)} companies\n⏱️ Scraping took {int(scrape_duration // 60)}m {int(scrape_duration % 60)}s")
        else:
            print(f"✓ No new jobs found")
            print(f"⏱️  Scraping took {int(scrape_duration // 60)} minutes {int(scrape_duration % 60)} seconds")
            await DEBUG_CHANNEL.send(f"ℹ️ No new jobs found\n⏱️ Scraping took {int(scrape_duration // 60)}m {int(scrape_duration % 60)}s")
        
        print(f"{'='*60}\n")

    cycle_number = 0
    while True:
        cycle_number += 1
        try:
            await send_new_roles()
            
            next_check_time = datetime.datetime.now() + datetime.timedelta(minutes=20)
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 😴 Waiting 20 minutes... (Cycle {cycle_number} complete)")
            print(f"[Next check at {next_check_time.strftime('%H:%M:%S')}]\n")
            await DEBUG_CHANNEL.send(f'😴 **Waiting 20 minutes** before next check...\n⏰ Next check at: {next_check_time.strftime("%H:%M:%S")}')
            
            await asyncio.sleep(60 * 20)  # Wait 20 minutes
            
        except Exception as e:
            error_msg = f'Error occurred: {str(e)}'
            print(f"\n{'='*60}")
            print(f"✗ {error_msg}")
            print(f"{'='*60}\n")
            await DEBUG_CHANNEL.send(f'❌ **Error occurred:** {error_msg}\n⏳ Retrying in 20 minutes...')
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
bot.run(BOT_TOKEN)