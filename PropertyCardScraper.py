import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime, timedelta
import nest_asyncio

nest_asyncio.apply()

class PropertyCardScraper:
    def __init__(self, url):
        print("Initializing PropertyCardScraper...")
        self.url = url
        self.browser = None
        self.context = None

    async def scrape_cards(self):
        print("Starting scrape_cards...")
        async with async_playwright() as p:
            print("Launching browser...")
            self.browser = await p.chromium.launch(headless=True)
            self.context = await self.browser.new_context()
            main_page = await self.context.new_page()
            try:
                print(f"Navigating to {self.url} ...")
                await main_page.goto(self.url)
                await main_page.wait_for_selector('.relative.min-h-48', timeout=60000)
                print("Main page loaded.")

                print("Scrolling to bottom to load all cards...")
                await self.scroll_to_bottom(main_page)

                print("Querying all card containers...")
                posts = await main_page.query_selector_all('.relative.w-full.rounded-lg.card-shadow')
                if not posts:
                    print("No cards found on this page.")
                    return "No cards found on this page."

                result = []
                print("Processing all cards for logic...")
                pinned_done = False
                not_pinned_done = False
                consecutive_pinned_old = 0
                consecutive_not_pinned_old = 0

                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

                for index, post in enumerate(posts):
                    pin_tag = await post.query_selector('div.bg-stickyTag')
                    is_pinned = False
                    if pin_tag:
                        text = await pin_tag.text_content()
                        if text and "مميز" in text:
                            is_pinned = True

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

                    print(f"Card {index+1}: pinned={is_pinned}, date_text='{date_text}', is_old={is_old}, pinned_done={pinned_done}, not_pinned_done={not_pinned_done}")

                    if is_pinned and not pinned_done:
                        if is_old:
                            consecutive_pinned_old += 1
                            print(f"Card {index+1}: consecutive_pinned_old = {consecutive_pinned_old}")
                        else:
                            consecutive_pinned_old = 0
                        if consecutive_pinned_old >= 3:
                            pinned_done = True
                            print("3 consecutive old pinned cards found. Stopping collecting pinned cards.")
                            continue
                        if is_old:
                            continue  # skip old cards
                        card_data = await self.scrape_card_data(post, index, main_page)
                        result.append(card_data)

                    elif not is_pinned and pinned_done and not not_pinned_done:
                        if is_old:
                            consecutive_not_pinned_old += 1
                            print(f"Card {index+1}: consecutive_not_pinned_old = {consecutive_not_pinned_old}")
                        else:
                            consecutive_not_pinned_old = 0
                        if consecutive_not_pinned_old >= 3:
                            not_pinned_done = True
                            print("3 consecutive old not-pinned cards found. Stopping collecting not-pinned cards.")
                            continue
                        if is_old:
                            continue  # skip old cards
                        card_data = await self.scrape_card_data(post, index, main_page)
                        result.append(card_data)
                    else:
                        continue

                print(f"Total cards collected: {len(result)}")
                return json.dumps(result, ensure_ascii=False, indent=2)

            finally:
                print("Closing browser...")
                await self.browser.close()

    async def scrape_card_data(self, post, index, main_page):
        print(f"Scraping data for card {index+1}...")
        title = await self.scrape_text(post, '.font-bold.text-lg.text-dark.line-clamp-2.break-words')
        price = await self.scrape_text(post, '.rounded.font-bold.text-primary-dark')
        relative_date = await self.scrape_text(post, '.rounded.text-xs.flex.items-center.gap-1')
        description = await self.scrape_description(post)
        image_url = await self.scrape_image(post)
        pin_status = await self.scrape_pin_status(post)

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

    async def scrape_link_and_details(self, post, index, main_page):
        """
        Clicks the card to open its details page in the same tab, extracts the URL and other details, then navigates back.
        """
        print(f"Clicking card {index+1} to get link and details (in-place navigation)...")
        try:
            # Get the old url before clicking (so we can detect change and come back)
            old_url = main_page.url
            print(f"Old main page URL: {old_url}")

            # Scroll card into view and click
            await post.scroll_into_view_if_needed()
            # Click and wait for navigation or content change
            try:
                # Try waiting for navigation (it may not be a full page load, so timeout quickly and fall back)
                await asyncio.wait_for(main_page.wait_for_navigation(), timeout=5)
            except Exception:
                pass
            await post.click(force=True)

            # Wait for URL to change or a unique detail page element to appear
            for _ in range(30):
                if main_page.url != old_url:
                    break
                await asyncio.sleep(0.2)
            detail_url = main_page.url
            print(f"Detail page URL: {detail_url}")

            # Extract mobile number
            mobile_number = None
            try:
                await main_page.wait_for_selector('.flex.gap-3.justify-center a', timeout=5000)
                mobile_element = await main_page.query_selector('.flex.gap-3.justify-center a')
                if mobile_element:
                    mobile_href = await mobile_element.get_attribute('href')
                    print(f"Mobile href: {mobile_href}")
                    if mobile_href and mobile_href.startswith('tel:'):
                        mobile_number = mobile_href[4:]
            except Exception as e:
                print(f"Failed to get mobile: {e}")

            # Extract views number
            views_number = None
            try:
                await main_page.wait_for_selector(
                    '.flex.items-center.justify-center.gap-1.rounded.bg-whitish-transparent.py-1.px-1\\.5.text-xs.min-w-\\[62px\\] div', timeout=5000)
                views_element = await main_page.query_selector(
                    '.flex.items-center.justify-center.gap-1.rounded.bg-whitish-transparent.py-1.px-1\\.5.text-xs.min-w-\\[62px\\] div')
                if views_element:
                    views_number = await views_element.text_content()
                    print(f"Views number: {views_number}")
            except Exception as e:
                print(f"Failed to get views: {e}")

            # Go back to the main listing page
            print("Navigating back to main page...")
            await main_page.go_back()
            await main_page.wait_for_selector('.relative.min-h-48', timeout=10000)
            print("Back to main page.")

            return detail_url, mobile_number, views_number

        except Exception as e:
            print(f"Failed to click/get details for card {index+1}: {e}")
            # Try to get back to main page if stuck
            try:
                await main_page.goto(self.url)
                await main_page.wait_for_selector('.relative.min-h-48', timeout=15000)
            except Exception as ee:
                print(f"Failed to recover main page: {ee}")
            return None, None, None

    async def scrape_text(self, post, selector):
        print(f"Scraping text with selector: {selector}")
        try:
            element = await post.query_selector(selector)
            if element:
                text = await element.text_content()
                print(f"Found text: {text}")
                return text
        except Exception as e:
            print(f"Failed to scrape {selector}: {e}")
        return None

    async def scrape_description(self, post):
        print("Scraping description...")
        try:
            description_element = await post.query_selector('.line-clamp-2:nth-of-type(2)')
            if description_element:
                desc = await description_element.text_content()
                print(f"Description found: {desc}")
                return desc
        except Exception as e:
            print(f"Failed to scrape description: {e}")
        return None

    async def scrape_image(self, post):
        print("Scraping image...")
        try:
            img_element = await post.query_selector('img[alt="Post"]')
            if img_element:
                src = await img_element.get_attribute('src')
                print(f"Image src: {src}")
                return src
        except Exception as e:
            print(f"Failed to scrape image: {e}")
        return None

    async def scrape_pin_status(self, post):
        print("Scraping pin status...")
        try:
            pin_tag = await post.query_selector('div.bg-stickyTag')
            if pin_tag:
                text = await pin_tag.text_content()
                if text and "مميز" in text:
                    print("Pin status: Pinned")
                    return "Pinned"
        except Exception as e:
            print(f"Failed to check pin status: {e}")
        print("Pin status: Not pinned")
        return "Not pinned"

    async def scroll_to_bottom(self, page):
        print("Starting scroll_to_bottom...")
        button_selector = (
            'button.text-base.shrink-0.select-none.whitespace-nowrap.transition-colors.'
            'disabled\\:opacity-50.h-12.font-bold.bg-primary.text-on-primary.active\\:bg-active-primary.'
            'w-full.cursor-pointer.z-20.max-w-2xl.py-3.md\\:py-4.px-8.rounded-full.flex.items-center.justify-center.gap-2\\.5'
        )
        try:
            print("Looking for 'Show More' button...")
            button = await page.query_selector(button_selector)
            if button:
                is_disabled = await button.get_property('disabled')
                if not is_disabled:
                    print("Clicking 'Show More' button...")
                    await button.click()
                    await asyncio.sleep(10)
        except Exception as e:
            print(f"Could not click 'Show More' button: {e}")

        max_scrolls = 30
        for scroll_count in range(max_scrolls):
            print(f"Scrolling down... (iteration {scroll_count+1})")
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(2)
            posts = await page.query_selector_all('.relative.w-full.rounded-lg.card-shadow')
            if posts and len(posts) >= 10:
                print(f"Cards loaded: {len(posts)}")
                pinned_streak = 0
                not_pinned_streak = 0
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                in_pinned = True
                for i, post in enumerate(posts):
                    pin_tag = await post.query_selector('div.bg-stickyTag')
                    is_pinned = False
                    if pin_tag:
                        text = await pin_tag.text_content()
                        if text and "مميز" in text:
                            is_pinned = True
                    else:
                        is_pinned = False
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
                        print("Sufficient cards for processing (3 consecutive old pinned and 3 consecutive old not pinned found).")
                        return
            else:
                print(f"Not enough cards loaded yet ({len(posts) if posts else 0}). Continuing scroll...")
        print("Reached max scrolls or detected enough cards.")

# async def main():
#     url = "https://www.boshamlan.com/search?c=1"
#     print("Creating scraper...")
#     scraper = PropertyCardScraper(url)
#     print("Begin scraping...")
#     result = await scraper.scrape_cards()
#     print("Final result:")
#     print(result)

# if __name__ == "__main__":
#     try:
#         loop = asyncio.get_event_loop()
#         loop.run_until_complete(main())
#     except RuntimeError:
#         asyncio.run(main())
