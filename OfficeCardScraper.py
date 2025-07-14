import time
import asyncio
import json
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import nest_asyncio

nest_asyncio.apply()


class OfficeCardScraper:
    def __init__(self, url):
        self.url = url

    async def scrape_cards(self):
        async with async_playwright() as p:
            # Set a user-agent to mimic a real browser
            browser = await p.chromium.launch(headless=True)  # Set to False for debugging
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            page = await context.new_page()

            try:
                print(f"Navigating to {self.url}...")
                await page.goto(self.url, wait_until='networkidle', timeout=60000)

                # Wait for the main container to load
                await page.wait_for_selector('div.max-w-2xl.mx-auto', timeout=60000)
                print("Main container found.")

                # Scroll to load all cards
                await self.scroll_to_load_all_cards(page)

                # Parse the page content
                soup = BeautifulSoup(await page.content(), 'html.parser')
                container = soup.find('div', class_='max-w-2xl mx-auto')
                if not container:
                    print("No card container found.")
                    return "No cards found on this page."

                # Find all card elements
                cards = container.find_all('div', class_=re.compile('relative.*rounded-lg.*flex'))
                print(f"Found {len(cards)} cards on the page.")

                result = []
                for index, card in enumerate(cards):
                    print(f"\nProcessing card {index + 1}/{len(cards)}...")

                    card_data = self.extract_card_data(card)
                    link = await self.get_card_link(page, index)

                    if not link:
                        print(f"Skipping card {index + 1} due to missing link.")
                        continue

                    # Ensure the link is absolute
                    if link.startswith('/'):
                        link = f"https://www.boshamlan.com{link}"
                    card_data['link'] = link

                    mobile_number = self.extract_mobile_number(link)
                    card_data['mobile'] = mobile_number

                    result.append(card_data)

                return json.dumps(result, ensure_ascii=False, indent=2)

            except Exception as e:
                print(f"Error during scraping: {str(e)}")
                return f"Error: {str(e)}"

            finally:
                await browser.close()

    async def scroll_to_load_all_cards(self, page):
        """Scroll the page to load all cards dynamically."""
        last_height = await page.evaluate('document.body.scrollHeight')
        while True:
            print("Scrolling to load more cards...")
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(2000)
            new_height = await page.evaluate('document.body.scrollHeight')
            if new_height == last_height:
                print("No more cards to load.")
                break
            last_height = new_height

    async def get_card_link(self, page, index):
        """Click the card to get the link."""
        try:
            # Re-fetch cards to ensure we have the latest DOM
            cards = await page.query_selector_all('div.relative.w-full.rounded-lg.bg-main.card-shadow.flex.p-3')
            if index >= len(cards):
                print(f"Card index {index} out of range (total cards: {len(cards)})")
                return None

            card = cards[index]
            await card.scroll_into_view_if_needed()
            await card.wait_for_element_state('visible')

            # Store initial URL
            initial_url = page.url
            print(f"Initial URL for card {index + 1}: {initial_url}")

            # Click the card
            await card.click()
            print(f"Clicked card {index + 1}, waiting for navigation...")

            # Wait for potential navigation or content load
            await page.wait_for_timeout(3000)  # Increased wait time for dynamic content

            # Check for URL change
            current_url = page.url
            print(f"Current URL after click for card {index + 1}: {current_url}")

            if current_url != initial_url:
                print(f"Valid link found for card {index + 1}: {current_url}")
                await page.goto(self.url, wait_until='networkidle', timeout=60000)
                return current_url

            # Check for modals or dynamic content
            modal = await page.query_selector('div[role="dialog"], div.modal, div.popup')
            if modal:
                print(f"Modal detected for card {index + 1}, attempting to extract link from modal...")
                modal_content = await modal.inner_html()
                soup = BeautifulSoup(modal_content, 'html.parser')
                link_tag = soup.find('a', href=True)
                if link_tag and link_tag['href']:
                    print(f"Link found in modal for card {index + 1}: {link_tag['href']}")
                    await page.goto(self.url, wait_until='networkidle', timeout=60000)
                    return link_tag['href']

            print(f"No URL change or modal link found for card {index + 1}.")
            await page.goto(self.url, wait_until='networkidle', timeout=60000)
            return None

        except Exception as e:
            print(f"Error getting link for card {index + 1}: {str(e)}")
            await page.goto(self.url, wait_until='networkidle', timeout=60000)
            return None

    def extract_card_data(self, card):
        """Extract data from a single card."""
        return {
            'image': self.extract_image(card),
            'title': self.extract_title(card),
            'description': self.extract_description(card),
            'ads': self.extract_ads(card),
        }

    def extract_image(self, card):
        img_tag = card.find('div', class_=re.compile('shrink-0')).find('img', class_=re.compile('rounded-lg'))
        return img_tag['src'] if img_tag and img_tag.get('src') else None

    def extract_title(self, card):
        title_tag = card.find('div', class_=re.compile('ps-3.*overflow-hidden')).find('div', class_=re.compile('font-bold.*text-lg.*line-clamp-2'))
        return title_tag.text.strip() if title_tag else None

    def extract_description(self, card):
        ps_tag = card.find('div', class_=re.compile('ps-3.*overflow-hidden'))
        if ps_tag:
            desc_tags = ps_tag.find_all('div', class_=re.compile('line-clamp-2'))
            if len(desc_tags) > 1:
                return desc_tags[1].text.strip() if desc_tags[1] else None
            elif desc_tags:
                return desc_tags[0].text.strip()
        return "No Description Provided"

    def extract_ads(self, card):
        ad_tag = card.find('div', class_=re.compile('text-base.*text-primary-dark.*font-bold'))
        return ad_tag.text.strip() if ad_tag else None

    def extract_mobile_number(self, link):
        """Extracts the mobile number from the link by appending +965 to the last part."""
        if not link:
            print("Link is None, cannot extract mobile number.")
            return None
        match = re.search(r'/([^/]+)$', link)
        if match:
            mobile_number = match.group(1)
            return f"+965{mobile_number}"
        return None


# Usage
# if __name__ == "__main__":
#     scraper = OfficeCardScraper("https://www.boshamlan.com/المكاتب")
#     result = asyncio.run(scraper.scrape_cards())
#     print(result)
