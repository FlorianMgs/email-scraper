import re
import csv
import asyncio
from typing import List, Tuple, Optional, Union
from aiohttp import ClientSession
from urllib.parse import urljoin, urlsplit
from googlesearch import search


class EmailScraper:

    ALREADY_PROCESSED = set()

    def __init__(self, keyword: str, country_code: str):
        """Initialize the email scraper with keyword and country code.

        Args:
            keyword (str): The keyword to search on Google.
            country_code (str): The country code to specify the search location.
        """
        self.keyword = keyword
        self.country_code = country_code

    @staticmethod
    async def fetch(url: str, session: ClientSession) -> Optional[str]:
        """Fetch the content of a given URL using aiohttp.

        Args:
            url (str): The URL to fetch the content from.
            session (ClientSession): The aiohttp session.

        Returns:
            str: The content of the fetched URL.
        """
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    print(f"Success fetching {url}")
                    return await response.text()
                else:
                    print(f"Error fetching {url}: {response.status}")
        except Exception as e:
            print(f"Error fetching {url}: {e}")

        return None

    @staticmethod
    def extract_homepage(url: str) -> str:
        """Extract the homepage from a given URL.

        Args:
            url (str): The input URL.

        Returns:
            str: The homepage URL.
        """
        parsed_url = urlsplit(url)
        homepage = f"{parsed_url.scheme}://{parsed_url.netloc}"
        return homepage

    async def search_keyword(self) -> List[str]:
        """Search for the keyword on Google and return the URLs of the resulting websites.

        Returns:
            List[str]: A list of website URLs.
        """
        urls = []
        query = self.keyword
        try:
            for url in search(query, lang=self.country_code, num_results=30):
                urls.append(url)
        except Exception as e:
            print(f"Error while searching keyword: {e}")

        print(urls)
        return urls

    async def find_email(self, content: str) -> Optional[str]:
        """Find an email address in the given content using regex.

        Args:
            content (str): The content to search for an email address.

        Returns:
            Optional[str]: The found email address, or None if not found.
        """
        if not content:
            return None
        pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        match = re.search(pattern, content)
        result = match.group() if match else None
        if result:
            for extension in ["png", "jpg", "jpeg", "gif", "svg", "bmp", "webp"]:
                if result.endswith(extension):
                    return None
            return result

    async def find_contact_urls(self, current_website_url: str, content: str) -> List[str]:
        """Find contact-related URLs in the given content using regex.

        Args:
            content (str): The content to search for contact-related URLs.

        Returns:
            List[str]: A list of contact-related URLs.
        """
        pattern = r'href="([^"]*)"'
        urls = re.findall(pattern, content)
        contact_urls = []

        for url in urls:
            if "mailto:" in url:
                email = url.replace("mailto:", "").split("?")[0]
                if email:
                    return [email]
            elif any(sub in url for sub in ["contact", "about", "terms"]):
                contact_urls.append(
                    urljoin(current_website_url, url) if "http" not in url else url
                )

        return contact_urls

    async def process_website(self, url: str, session: ClientSession) -> Union[None, Tuple[str, Union[str, Optional[str]]]]:
        """Process a website to find an email address.

        Args:
            url (str): The URL of the website.
            session (ClientSession): The aiohttp session.

        Returns:
            Union[None, Tuple[str, Union[str, Optional[str]]]]: A tuple containing the website URL and the found email address, or None if not found.
        """
        homepage = self.extract_homepage(url)
        if homepage not in self.ALREADY_PROCESSED:
            content = await self.fetch(homepage, session)
            self.ALREADY_PROCESSED.add(homepage)
            if not content:
                return (homepage, None)

            email = await self.find_email(content)
            if not email:
                contact_urls = await self.find_contact_urls(homepage, content)
                for contact_url in contact_urls:
                    if "@" in contact_url:
                        email = contact_url
                        break
                    content = await self.fetch(contact_url, session)
                    if not content:
                        continue

                    email = await self.find_email(content)
                    if email:
                        break

            return (homepage, email)

    async def scrape_emails(self) -> None:
        """Scrape emails from websites and save them in a CSV file."""

        urls = await self.search_keyword()
        async with ClientSession() as session:
            tasks = [self.process_website(url, session) for url in urls]
            results = await asyncio.gather(*tasks)

        with open("emails.csv", "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Website", "Email"])
            for url, email in results:
                if email:
                    writer.writerow([url, email])


if __name__ == "__main__":
    keyword = input("Enter a keyword: ")
    country_code = input("Enter a country code: ")

    scraper = EmailScraper(keyword, country_code)
    asyncio.run(scraper.scrape_emails())
