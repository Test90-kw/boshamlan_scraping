import time
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import nest_asyncio
import json
import asyncio
import re  # For regular expression handling

nest_asyncio.apply()


class OfficeCardScraper:
    def __init__(self, url):
        self.url = url

    async def scrape_cards(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                await page.goto(self.url)
                await page.wait_for_selector('div.max-w-2xl.mx-auto')
                # Wait for both selectors to be visible with a longer timeout
                await page.wait_for_selector('div.ps-3.overflow-hidden', timeout=60000)

                soup = BeautifulSoup(await page.content(), 'html.parser')
                container = soup.find('div', class_='max-w-2xl mx-auto')
                if not container:
                    return "No cards found on this page."

                cards = container.find_all('div', class_='relative w-full rounded-lg bg-main card-shadow flex p-3')

                result = []
                for index, card in enumerate(cards):
                    print(f"\nProcessing card {index + 1}...")

                    # Return to the main page for each new card
                    if index > 0:
                        await page.goto(self.url)
                        await page.wait_for_selector('div.max-w-2xl.mx-auto')
                        await page.wait_for_selector('div.ps-3.overflow-hidden')

                    card_data = self.extract_card_data(card)
                    link = await self.get_card_link(page, index)

                    if not link:
                        print(f"Skipping card {index + 1} due to missing link.")
                        continue

                    card_data['link'] = link

                    # Extract mobile number and add it to card data
                    mobile_number = self.extract_mobile_number(link)
                    card_data['mobile'] = mobile_number

                    result.append(card_data)

                return json.dumps(result, ensure_ascii=False, indent=2)

            finally:
                await browser.close()

    async def get_card_link(self, page, index):
        retries = 5  # Number of retries before giving up
        retry_delay = 2  # Delay between retries in seconds

        for attempt in range(retries):
            try:
                # Wait for all cards to be loaded
                await page.wait_for_selector('div.relative.w-full.rounded-lg.bg-main.card-shadow.flex.p-3')

                # Get the specific card by index
                cards = await page.query_selector_all('div.relative.w-full.rounded-lg.bg-main.card-shadow.flex.p-3')
                if index >= len(cards):
                    print(f"Card index {index} out of range")
                    return None

                card = cards[index]

                # Wait for the card to be ready
                await card.wait_for_element_state('visible')
                await card.wait_for_element_state('stable')
                await card.scroll_into_view_if_needed()

                # Store initial URL and click the card
                initial_url = page.url
                await card.click()

                try:
                    # Wait briefly for navigation
                    await page.wait_for_timeout(1000)  # Wait 1 second

                    # Get the new URL after click
                    current_url = page.url

                    # Check if URL changed and contains the expected pattern
                    if current_url != initial_url and (
                            '/%D8%A7%D9%84%D9%85%D9%83%D8%A7%D8%AA%D8%A8/' in current_url or '/المكاتب/' in current_url):
                        return current_url  # Successfully found the correct URL

                except Exception:
                    # If we got an error but the URL changed, still capture it
                    current_url = page.url
                    if current_url != initial_url and ('/%D8%A7%D9%84%D9%85%D9%83%D9%8A/' in current_url):
                        return current_url  # Successfully found the correct URL

            except Exception:
                # Retry after delay if error occurs
                pass

            # Retry after delay if the URL is not correct
            await asyncio.sleep(retry_delay)

        # If the link is not found after retries
        print(f"Failed to get link for card {index} after {retries} attempts.")
        return None

    def extract_card_data(self, card):
        return {
            'image': self.extract_image(card),
            'title': self.extract_title(card),
            'description': self.extract_description(card),
            'ads': self.extract_ads(card),
        }

    def extract_image(self, card):
        img_tag = card.find('div', class_='shrink-0').find('img', class_='rounded-lg')
        return img_tag['src'] if img_tag else None

    def extract_title(self, card):
        title_tag = card.find('div', class_='ps-3 overflow-hidden').find('div',
                                                                         class_='font-bold text-lg text-dark line-clamp-2 break-words')
        title_text = title_tag.text.strip() if title_tag else None
        return title_text

    def extract_description(self, card):
        ps_tag = card.find('div', class_='ps-3 overflow-hidden')
        if ps_tag:
            desc_tag = ps_tag.find_all('div', class_='line-clamp-2')
            if len(desc_tag) > 1:
                description_text = desc_tag[1].text.strip() if desc_tag[1] else None
            else:
                description_text = desc_tag[0].text.strip() if desc_tag else None
            return description_text
        return None

    def extract_ads(self, card):
        ad_tag = card.find('div', class_='text-base text-primary-dark font-bold')
        return ad_tag.text.strip() if ad_tag else None

    def extract_mobile_number(self, link):
        """Extracts the mobile number from the link by appending +965 to the last part."""
        # Use regex to extract the last segment of the URL
        if not link:
            print("Link is None, cannot extract mobile number.")
            return None
        match = re.search(r'/([^/]+)$', link)
        if match:
            mobile_number = match.group(1)  # The last part of the URL
            return f"+965{mobile_number}"
        return None


# # Usage
# scraper = CardScraper("https://www.boshamlan.com/المكاتب")
# result = asyncio.run(scraper.scrape_cards())
# print(result)
