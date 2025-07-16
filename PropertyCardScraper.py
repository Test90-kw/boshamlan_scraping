# Import required modules
import asyncio  # For asynchronous programming
from playwright.async_api import async_playwright  # Asynchronous browser automation using Playwright
import json  # To serialize results
from datetime import datetime, timedelta  # To work with card dates
import nest_asyncio  # To allow nested event loops (important in environments like Jupyter)

# Patch asyncio to allow nested use
nest_asyncio.apply()

# Scraper class to collect property card data from a dynamic listing site
class PropertyCardScraper:
    def __init__(self, url):
        print("Initializing PropertyCardScraper...")
        self.url = url  # The URL to scrape
        self.browser = None  # Playwright browser instance
        self.context = None  # Browser context for isolated sessions

    # Main method to orchestrate scraping logic
    async def scrape_cards(self):
        print("Starting scrape_cards...")
        async with async_playwright() as p:
            print("Launching browser...")
            self.browser = await p.chromium.launch(headless=True)  # Headless browser launch
            self.context = await self.browser.new_context()  # Create a new browser context
            main_page = await self.context.new_page()  # Open a new tab/page

            try:
                print(f"Navigating to {self.url} ...")
                await main_page.goto(self.url)
                await main_page.wait_for_selector('.relative.min-h-48', timeout=60000)  # Wait for card area to load
                print("Main page loaded.")

                # Scroll to ensure all cards are loaded
                print("Scrolling to bottom to load all cards...")
                await self.scroll_to_bottom(main_page)

                print("Querying all card containers...")
                posts = await main_page.query_selector_all('.relative.w-full.rounded-lg.card-shadow')  # Select all cards
                if not posts:
                    print("No cards found on this page.")
                    return "No cards found on this page."

                result = []
                print("Processing all cards for logic...")
                pinned_done = False
                not_pinned_done = False
                consecutive_pinned_old = 0
                consecutive_not_pinned_old = 0

                # Yesterday’s date for age comparison
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

                for index, post in enumerate(posts):
                    # Check if the card is pinned (marked as "مميز")
                    pin_tag = await post.query_selector('div.bg-stickyTag')
                    is_pinned = False
                    if pin_tag:
                        text = await pin_tag.text_content()
                        if text and "مميز" in text:
                            is_pinned = True

                    # Get date from card
                    date_elem = await post.query_selector('.rounded.text-xs.flex.items-center.gap-1')
                    date_text = (await date_elem.text_content()).strip() if date_elem else ""

                    is_old = False
                    try:
                        card_date = datetime.strptime(date_text, "%Y-%m-%d")
                        if card_date < datetime.strptime(yesterday, "%Y-%m-%d"):
                            is_old = True
                    except ValueError:
                        # If not a standard date format, check for time-related keywords (means it's recent)
                        if not any(word in date_text for word in ['ساعة', 'دقيقة', 'ثانية']):
                            is_old = True

                    print(f"Card {index+1}: pinned={is_pinned}, date_text='{date_text}', is_old={is_old}, pinned_done={pinned_done}, not_pinned_done={not_pinned_done}")

                    # Logic to stop after 3 old pinned and 3 old not-pinned cards
                    if is_pinned and not pinned_done:
                        if is_old:
                            consecutive_pinned_old += 1
                        else:
                            consecutive_pinned_old = 0
                        if consecutive_pinned_old >= 3:
                            pinned_done = True
                            continue
                        if is_old:
                            continue
                        card_data = await self.scrape_card_data(post, index, main_page)
                        result.append(card_data)

                    elif not is_pinned and pinned_done and not not_pinned_done:
                        if is_old:
                            consecutive_not_pinned_old += 1
                        else:
                            consecutive_not_pinned_old = 0
                        if consecutive_not_pinned_old >= 3:
                            not_pinned_done = True
                            continue
                        if is_old:
                            continue
                        card_data = await self.scrape_card_data(post, index, main_page)
                        result.append(card_data)

                print(f"Total cards collected: {len(result)}")
                return json.dumps(result, ensure_ascii=False, indent=2)  # Convert to formatted JSON string

            finally:
                print("Closing browser...")
                await self.browser.close()

    # Extract all relevant card fields
    async def scrape_card_data(self, post, index, main_page):
        print(f"Scraping data for card {index+1}...")
        title = await self.scrape_text(post, '.font-bold.text-lg.text-dark.line-clamp-2.break-words')
        price = await self.scrape_text(post, '.rounded.font-bold.text-primary-dark')
        relative_date = await self.scrape_text(post, '.rounded.text-xs.flex.items-center.gap-1')
        description = await self.scrape_description(post)
        image_url = await self.scrape_image(post)
        pin_status = await self.scrape_pin_status(post)

        # Visit card to get extra details
        link, mobile_number, views_number = await self.scrape_link_and_details(post, index, main_page)

        card_data = {
            'title': title,
            'price': price,
            'relative_date': relative_date,
            'description': description,
            'image_url': image_url,
            'link': link,
            'mobile_number': mobile_number,
            'views_number': views_number,
            'pin_status': pin_status
        }
        print(f"Card {index+1} Data: {card_data}")
        return card_data

    # Visit the card detail page and extract link, phone, and views
    async def scrape_link_and_details(self, post, index, main_page):
        print(f"Clicking card {index+1} to get link and details (in-place navigation)...")
        try:
            old_url = main_page.url

            await post.scroll_into_view_if_needed()

            try:
                await asyncio.wait_for(main_page.wait_for_navigation(), timeout=5)
            except Exception:
                pass
            await post.click(force=True)

            # Wait until URL changes
            for _ in range(30):
                if main_page.url != old_url:
                    break
                await asyncio.sleep(0.2)
            detail_url = main_page.url

            # Extract phone number (tel:)
            mobile_number = None
            try:
                await main_page.wait_for_selector('.flex.gap-3.justify-center a', timeout=5000)
                mobile_element = await main_page.query_selector('.flex.gap-3.justify-center a')
                if mobile_element:
                    mobile_href = await mobile_element.get_attribute('href')
                    if mobile_href and mobile_href.startswith('tel:'):
                        mobile_number = mobile_href[4:]
            except Exception as e:
                print(f"Failed to get mobile: {e}")

            # Extract view count
            views_number = None
            try:
                await main_page.wait_for_selector(
                    '.flex.items-center.justify-center.gap-1.rounded.bg-whitish-transparent.py-1.px-1\\.5.text-xs.min-w-\\[62px\\] div', timeout=5000)
                views_element = await main_page.query_selector(
                    '.flex.items-center.justify-center.gap-1.rounded.bg-whitish-transparent.py-1.px-1\\.5.text-xs.min-w-\\[62px\\] div')
                if views_element:
                    views_number = await views_element.text_content()
            except Exception as e:
                print(f"Failed to get views: {e}")

            # Return to main listing page
            await main_page.go_back()
            await main_page.wait_for_selector('.relative.min-h-48', timeout=10000)

            return detail_url, mobile_number, views_number

        except Exception as e:
            print(f"Failed to click/get details for card {index+1}: {e}")
            try:
                await main_page.goto(self.url)
                await main_page.wait_for_selector('.relative.min-h-48', timeout=15000)
            except Exception as ee:
                print(f"Failed to recover main page: {ee}")
            return None, None, None

    # Generic method to extract text from a selector
    async def scrape_text(self, post, selector):
        try:
            element = await post.query_selector(selector)
            if element:
                text = await element.text_content()
                return text
        except Exception as e:
            print(f"Failed to scrape {selector}: {e}")
        return None

    # Description is the 2nd occurrence of line-clamp-2
    async def scrape_description(self, post):
        try:
            description_element = await post.query_selector('.line-clamp-2:nth-of-type(2)')
            if description_element:
                return await description_element.text_content()
        except Exception as e:
            print(f"Failed to scrape description: {e}")
        return None

    # Extract image from post
    async def scrape_image(self, post):
        try:
            img_element = await post.query_selector('img[alt="Post"]')
            if img_element:
                return await img_element.get_attribute('src')
        except Exception as e:
            print(f"Failed to scrape image: {e}")
        return None

    # Identify if card is pinned
    async def scrape_pin_status(self, post):
        try:
            pin_tag = await post.query_selector('div.bg-stickyTag')
            if pin_tag:
                text = await pin_tag.text_content()
                if text and "مميز" in text:
                    return "Pinned"
        except Exception as e:
            print(f"Failed to check pin status: {e}")
        return "Not pinned"

    # Scrolls page to load more cards and stop when enough old ones are found
    async def scroll_to_bottom(self, page):
        print("Starting scroll_to_bottom...")
        button_selector = (
            'button.text-base.shrink-0.select-none.whitespace-nowrap.transition-colors.'
            'disabled\\:opacity-50.h-12.font-bold.bg-primary.text-on-primary.active\\:bg-active-primary.'
            'w-full.cursor-pointer.z-20.max-w-2xl.py-3.md\\:py-4.px-8.rounded-full.flex.items-center.justify-center.gap-2\\.5'
        )

        try:
            button = await page.query_selector(button_selector)
            if button:
                is_disabled = await button.get_property('disabled')
                if not is_disabled:
                    await button.click()
                    await asyncio.sleep(10)
        except Exception as e:
            print(f"Could not click 'Show More' button: {e}")

        max_scrolls = 30
        for scroll_count in range(max_scrolls):
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(2)
            posts = await page.query_selector_all('.relative.w-full.rounded-lg.card-shadow')

            if posts and len(posts) >= 10:
                pinned_streak = 0
                not_pinned_streak = 0
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                in_pinned = True

                for i, post in enumerate(posts):
                    pin_tag = await post.query_selector('div.bg-stickyTag')
                    is_pinned = bool(pin_tag and "مميز" in (await pin_tag.text_content() or ""))
                    if not is_pinned:
                        in_pinned = False

                    date_elem = await post.query_selector('.rounded.text-xs.flex.items-center.gap-1')
                    date_text = (await date_elem.text_content()).strip() if date_elem else ""
                    is_old = False
                    try:
                        card_date = datetime.strptime(date_text, "%Y-%m-%d")
                        if card_date < datetime.strptime(yesterday, "%Y-%m-%d"):
                            is_old = True
                    except ValueError:
                        if not any(word in date_text for word in ['ساعة', 'دقيقة', 'ثانية']):
                            is_old = True

                    if is_pinned and is_old and in_pinned:
                        pinned_streak += 1
                    elif not is_pinned and is_old and not in_pinned:
                        not_pinned_streak += 1

                    if pinned_streak >= 3 and not_pinned_streak >= 3:
                        return
            else:
                print(f"Not enough cards loaded yet ({len(posts) if posts else 0}). Continuing scroll...")
        print("Reached max scrolls or detected enough cards.")

