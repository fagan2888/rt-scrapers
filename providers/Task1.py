# An example of provider definition

# Mandatory imports
from .Task import Task
from rfeed import *

# Optional imports
import requests, mimetypes, logging, re
logging.basicConfig(level=logging.INFO)
from bs4 import BeautifulSoup as bs
import humanfriendly

# Custom provider class inherit from the Provider one defined in providers/Provider.py file
#
# Inherited attributes:
# - output_format
# - tz
# - language
# - feed_base_url
# - docs_base_url
# - specs_base_url
# - options
#
# Inherited methods:
# - dt
#
# Specific methods to customize:
# - opts: using options from csv file properly
# - urls: extract single item urls from index page
# - item: extract and structure data from single item page
#
# WARNING: class name is also the value of provider column in elenco_albi.csv
#
class Task1(Task):

    # Scrape a single item page from its url and return structured data as Item() instance (from rfeed)
    def item(self,single_page_url):
        # From the url you can fetch the single item page and scrape data from it
        # You must return an Item() with structured data in it
        # Refer to Halley.py definition for more details
        single_page_response = requests.get(single_page_url)

        if single_page_response.status_code != 200:
            logging.warning("Single page %s unavailable!" % single_page_url)
            return None # None items are dropped in final feed

        single_page_soup = bs(single_page_response.content,"lxml")
        logging.debug("- Scraping %s" % single_page_url)

        single_page_table = single_page_soup.find("div", class_="info")

        description = self.clean_string(single_page_table.find("div", class_="etichettalunga").text)
        id = self.clean_string(re.search("N\. ([^ ]+)", description).group(1))
        labels = [self.clean_string(cell.text).strip(":") for cell in single_page_table.find_all("div", class_="etichetta")]
        values = [self.clean_string(cell.text) for cell in single_page_table.find_all("div", class_="valore")]
        record = dict(zip(labels,values))

        if not self.options["index_items"].get(id):
            self.options["index_items"][id] = {}
        self.options["index_items"][id].update(record)
        document = self.options["index_items"][id]

        # Return scraping data as an Item() instance
        return Item(
            title = document["Titolo"],
            link = single_page_url,
            description = description,
            pubDate = self.format_datetime(document.get("Esecutiva dal") or document.get("Data di pubblicazione") or document.get("Dal")),
            guid = Guid(single_page_url),
            categories = [
                c
                for c in [
                    Category(
                        domain = self.specs_base_url + "#" + "item-category-uid",
                        category = id
                    ),
                    Category(
                        domain = self.specs_base_url + "#" + "item-category-type",
                        category = document["Tipologia pubblicazione"]
                    ) if document.get("Tipologia pubblicazione") else None,
                    Category(
                        domain = self.specs_base_url + "#" + "item-category-pubStart",
                        category = self.format_datetime(document.get("Dal") or document.get("Data di pubblicazione") or document.get("Esecutiva dal"))
                    ),
                    Category(
                        domain = self.specs_base_url + "#" + "item-category-pubEnd",
                        category = self.format_datetime(document["Al"])
                    ) if document.get("Al") else None
                ]
                if c is not None
            ],
            enclosure = [
                Enclosure(
                    url = enclosure.find("a").get("href"),
                    length = humanfriendly.parse_size(
                        re.search(
                            "([\d\.]+ ?.B)",
                            self.clean_string(enclosure.find("div", class_="testokb").text)
                        ).group(1),
                        binary=True
                    ) if enclosure.find("div", class_="testokb") else 3000,
                    type = mimetypes.guess_type(enclosure.find("a").get("href"))[0] or "application/octet-stream"
                )
                for enclosure in single_page_soup.find_all("div", class_="testoallegato")
            ]
        )
