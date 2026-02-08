import os
import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

class GenshinSmartScraper:
    def __init__(self, output_dir="data/raw"):
        self.base_url = "https://genshin-impact.fandom.com"
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        # Keep track of what we've seen so we don't scrape the same page twice
        self.visited_urls = set()

    def clean_text(self, soup):
        """
        Advanced cleaning: Handles Tables, Notes, and Junk.
        """
        # 1. REMOVE JUNK (Expanded list)
        junk_selectors = [
            "script", "style", "nav", "footer", "aside",
            ".navbox", ".wds-global-footer", ".reflist", 
            ".license-description", ".toc", ".mw-editsection", 
            "sup", # Citations [1]
            "#catlinks",
            ".caption", # Image captions often interrupt sentences
            "th.language-name", # Hides the language table headers
        ]
        
        for selector in junk_selectors:
            for element in soup.select(selector):
                element.decompose()

        # 2. LOCATE CONTENT
        content = soup.find("div", class_="mw-parser-output")
        if not content:
            return ""

        # 3. SMART TABLE HANDLING
        # We convert tables into a linear format: "Header: Cell, Header: Cell"
        for table in content.find_all("table"):
            # If it's a massive translation table, just kill it.
            if "wikitable" in table.get("class", []) and "width" in table.attrs:
                # Heuristic: Translation tables often have specific width attributes or specific headers
                headers = [th.get_text().strip() for th in table.find_all("th")]
                if "Language" in headers or "Chinese" in str(table):
                    table.decompose()
                    continue

            # Otherwise, preserve useful tables (like the Ancient Name list)
            rows = []
            headers = [th.get_text().strip() for th in table.find_all("th")]
            
            for tr in table.find_all("tr"):
                cells = [td.get_text(separator=" ").strip() for td in tr.find_all("td")]
                if cells:
                    # Pair header with cell if possible
                    row_str = " | ".join(cells)
                    rows.append(row_str)
            
            # Replace the HTML table with this text representation
            new_text = "\n".join(rows)
            table.replace_with(f"\n[TABLE_DATA]\n{new_text}\n[/TABLE_DATA]\n")

        # 4. REMOVE FOOTERS (References, etc)
        for header in content.find_all(['h2', 'h3']):
            header_text = header.get_text().strip().lower()
            if any(x in header_text for x in ["references", "navigation", "see also", "external links", "change history", "other languages", "notes"]):
                # Cut off everything after this header
                for sibling in header.find_next_siblings():
                    sibling.decompose()
                header.decompose()
                break

        # 5. TEXT EXTRACTION & REGEX CLEANING
        text = content.get_text(separator="\n")
        
        # Remove [Note 1], [1], etc.
        text = re.sub(r"\[\s*(Note\s*)?\d+\s*\]", "", text)
        # Remove the "↑" arrows from notes
        text = re.sub(r"↑", "", text)
        # Collapse whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text)
        
        return text.strip()

    def scrape_page(self, page_title):
        """
        Fetches page content via API, but filters out 'Junk' pages (Lists, Disambiguations).
        """
        api_url = urljoin(self.base_url, "/api.php")
        
        params = {
            "action": "parse",
            "page": page_title,
            "format": "json",
            "prop": "text|categories|properties",  # Request categories and properties too!
            "redirects": 1
        }
        
        print(f"📄 API Fetching: {page_title}...")
        
        try:
            response = requests.get(api_url, headers=self.headers, params=params)
            data = response.json()
            
            if "error" in data:
                print(f"⚠️ API Error: {data['error'].get('info')}")
                return
            
            # --- THE SMART FILTER ---
            # 1. Check Categories
            categories = data["parse"].get("categories", [])
            # Extract just the category names (hidden in the dict)
            cat_names = [c.get("*", "").lower() for c in categories]
            
            # Define "Banned" keywords
            banned_keywords = ["disambiguation", "list of", "navigation", "timeline", "overviews"]
            
            if any(keyword in cat_name for cat_name in cat_names for keyword in banned_keywords):
                print(f"🛑 Skipping '{page_title}' (It looks like a {cat_names})")
                return

            # 2. Check for "Disambiguation" Property (The official API flag)
            properties = data["parse"].get("properties", [])
            prop_names = [p.get("name") for p in properties]
            if "disambiguation" in prop_names:
                print(f"🛑 Skipping '{page_title}' (It is a Disambiguation page)")
                return
            # ------------------------

            # If we passed the checks, process the text!
            raw_html = data["parse"]["text"]["*"]
            soup = BeautifulSoup(raw_html, "html.parser")
            clean_content = self.clean_text(soup)

            # Extra Check: If text is too short, it's probably an empty stub
            if len(clean_content) < 500: 
                print(f"⚠️ Skipping '{page_title}' (Content too short: {len(clean_content)} chars)")
                return

            # Save file
            safe_filename = page_title.replace(" ", "_").replace("/", "_").replace(":", "_") + ".txt"
            filepath = os.path.join(self.output_dir, safe_filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(clean_content)
            
            print(f"✅ Saved {safe_filename}")
            time.sleep(1)

        except Exception as e:
            print(f"⚠️ Error processing {page_title}: {e}")

    def crawl_category(self, category_name, limit=50):
        """
        Smart Harvester: Uses the MediaWiki API to get category members.
        This bypasses HTML/CSS changes and JavaScript lazy-loading.
        """
        print(f"🔍 Asking API for Category: {category_name}...")
        
        # The hidden MediaWiki API endpoint
        api_url = urljoin(self.base_url, "/api.php")
        
        # API parameters to get category members
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category_name}",
            "cmlimit": limit,       # How many to fetch
            "cmnamespace": 0,       # Namespace 0 means "Main Articles" only (filters out User/Talk pages automatically!)
            "format": "json"
        }
        
        try:
            response = requests.get(api_url, headers=self.headers, params=params)
            data = response.json()
            
            members = data.get("query", {}).get("categorymembers", [])
            
            if not members:
                print(f"⚠️ API found 0 pages for '{category_name}'. Check the spelling!")
                return
                
            print(f"🔗 API found {len(members)} pages. Starting download...")
            
            # Loop through the results and scrape the actual text
            for page in members:
                page_title = page["title"]
                
                self.scrape_page(page_title)
                
            print(f"✅ Finished category '{category_name}'.")

        except Exception as e:
            print(f"⚠️ Failed to query API: {e}")

if __name__ == "__main__":
    scraper = GenshinSmartScraper()

    # These are the "Gold Mines" for lore.
    target_categories = [
        "Lore",
        "Book Collections",
        "Factions",
        "Gods"
    ]
    
    for cat in target_categories:
        scraper.crawl_category(cat, limit=10)