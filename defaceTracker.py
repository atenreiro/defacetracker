#!/usr/bin/python3
import argparse
import logging
import random
import sys
import time
from datetime import datetime
from typing import List, Dict
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
from colorama import Fore, Style, init

init(autoreset=True)

def setup_logging(log_file: str = "debug.log") -> None:
    """
    Sets up logging configuration.

    Args:
        log_file (str): The filename for the log file.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode='a', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def get_random_user_agent() -> str:
    """
    Returns a random User-Agent string from a predefined list.

    Returns:
        str: A User-Agent string.
    """
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/58.0.3029.110 Safari/537.3",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Firefox/89.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/14.0.3 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/88.0.4324.96 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/14.0 Mobile/15E148 Safari/604.1",
    ]
    selected_ua = random.choice(user_agents)
    logging.info(Fore.CYAN + "Selected a random User-Agent.")
    return selected_ua

def is_valid_fqdn(domain: str) -> bool:
    """
    Validates if the provided string is a valid Fully Qualified Domain Name (FQDN).

    Args:
        domain (str): The domain string to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    fqdn_regex = re.compile(
        r'^(?=.{1,253}$)'
        r'((?!-)[A-Za-z0-9-]{1,63}(?<!-)\.)+'  # Subdomain(s)
        r'[A-Za-z]{2,63}$'  # Top-level domain
    )
    return bool(fqdn_regex.match(domain))

def scrape_defacements(url: str) -> List[Dict[str, str]]:
    """
    Scrapes defacement data from the given URL.

    Args:
        url (str): The target URL to scrape.

    Returns:
        List[Dict[str, str]]: A list of dictionaries containing the scraped data.
    """
    headers = {
        "User-Agent": get_random_user_agent()
    }

    try:
        logging.info(Fore.CYAN + f"Sending GET request to {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
        logging.info(Fore.GREEN + f"✅ Successfully fetched content from {url}")
    except requests.exceptions.HTTPError as http_err:
        logging.error(Fore.RED + f"❌ HTTP error occurred: {http_err}")
        sys.exit(1)
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(Fore.RED + f"❌ Connection error occurred: {conn_err}")
        sys.exit(1)
    except requests.exceptions.Timeout as timeout_err:
        logging.error(Fore.RED + f"⏱️ Timeout error occurred: {timeout_err}")
        sys.exit(1)
    except requests.exceptions.RequestException as req_err:
        logging.error(Fore.RED + f"❌ An error occurred: {req_err}")
        sys.exit(1)

    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', {'class': lambda x: x and 'mirror' in x})

    if not table:
        logging.error(Fore.RED + "Could not find the table with class 'mirror-table'")
        sys.exit(1)
    else:
        logging.info(Fore.GREEN + "📊 Successfully located the target table")

    data = []

    for row in table.select('tbody tr'):
        cols = row.find_all('td')

        if len(cols) < 10:
            logging.warning(Fore.YELLOW + "⚠️ Skipping a row due to insufficient columns")
            continue  # Skip rows that don't have enough columns

        # Extract Date & Time and rename to Date (only date part)
        datetime_str = cols[0].get_text(strip=True)
        date = datetime_str.split(' ')[0] if ' ' in datetime_str else datetime_str

        # Extract Attacker
        attacker_tag = cols[1].find('a')
        attacker = attacker_tag.get_text(strip=True) if attacker_tag else cols[1].get_text(strip=True)

        # Extract Team
        team_tag = cols[2].find('a')
        team = team_tag.get_text(strip=True) if team_tag else cols[2].get_text(strip=True)

        # Extract URL
        url_affected = cols[8].get_text(strip=True)

        # Extract Mirror URL
        mirror_tag = cols[9].find('a')
        mirror_url = mirror_tag['href'] if mirror_tag and mirror_tag.has_attr('href') else ''

        # If the mirror_url is relative, prepend the base URL
        if mirror_url.startswith('/'):
            mirror_url = f"https://zone-xsec.com{mirror_url}"

        # Append the extracted data to the list
        data.append({
            'Date': date,
            'Attacker': attacker,
            'Team': team,
            'URL': url_affected,
            'Mirror': mirror_url
        })

    logging.info(Fore.GREEN + f"Total entries scraped from table: {len(data)}")
    return data

def save_data(data: List[Dict[str, str]], filename: str, file_format: str = "csv") -> None:
    """
    Saves the scraped data to a file in the specified format.

    Args:
        data (List[Dict[str, str]]): The data to save.
        filename (str): The name of the output file.
        file_format (str): The format to save the file ('csv' or 'json').
    """
    try:
        if file_format == "csv":
            df = pd.DataFrame(data)
            df.to_csv(filename, index=False, encoding='utf-8')
            logging.info(Fore.GREEN + f"📁 Data successfully written to {filename} in CSV format")
        elif file_format == "json":
            with open(filename, 'w', encoding='utf-8') as json_file:
                json.dump(data, json_file, ensure_ascii=False, indent=4)
            logging.info(Fore.GREEN + f"📁 Data successfully written to {filename} in JSON format")
        else:
            logging.error(Fore.RED + "Unsupported file format specified. Use 'csv' or 'json'.")
            sys.exit(1)
    except Exception as e:
        logging.error(Fore.RED + f"❌ Failed to write data to {filename}: {e}")
        sys.exit(1)

def main():
    """
    Main function to execute the scraping process.
    """
    print(Fore.GREEN + Style.BRIGHT + """
    ===============================================
    |        Deface Tracker v1.0.1                |
    |  (c) Andre Tenreiro                         |
    |  https://github.com/atenreiro/defacetracker |
    ===============================================
    """)

    parser = argparse.ArgumentParser(description=Fore.CYAN + "Defacement scraper for Zone-Xsec")

    # Create a mutually exclusive group for --tld and --domain
    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "--tld", "-t",
        type=str,
        default="archive",
        help=Fore.YELLOW + "Specify the TLD to scrape (e.g., MZ)"
    )

    group.add_argument(
        "--domain", "-d",
        type=str,
        help=Fore.YELLOW + "Specify the FQDN to search for (e.g., example.com)"
    )

    parser.add_argument(
        "--format", "-f",
        type=str,
        default="csv",
        choices=["csv", "json"],
        help=Fore.YELLOW + "Output format: csv or json"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help=Fore.YELLOW + "Output file name"
    )
    parser.add_argument(
        "--pages", "-p",
        type=int,
        default=1,
        choices=range(1, 6),
        help=Fore.YELLOW + "Number of pages to scrape (max 5)"
    )
    args = parser.parse_args()

    setup_logging()
    start_time = time.time()

    # Determine the base URL based on the provided arguments
    if args.domain:
        # Validate the domain format
        if not is_valid_fqdn(args.domain):
            logging.error(Fore.RED + f"❌ Invalid domain format: {args.domain}")
            sys.exit(1)
        base_url = f"https://zone-xsec.com/search/q={args.domain}"
        logging.info(Fore.CYAN + f"🔍 Searching for domain: {args.domain}")
    else:
        tld = args.tld.upper()
        base_url = f"https://zone-xsec.com/country/{tld}" if tld != "ARCHIVE" else "https://zone-xsec.com/archive"
        logging.info(Fore.CYAN + f"🌐 Scraping TLD: {tld}")

    if args.output:
        output_file = args.output
    else:
        date_str = datetime.now().strftime("%d%m%Y")
        identifier = args.domain if args.domain else tld.lower()
        output_file = f"{date_str}_{identifier}.{args.format}"

    logging.info(Fore.CYAN + "🚀 Starting the scraping process")

    all_data = []
    for page in range(1, args.pages + 1):
        url = f"{base_url}/page={page}" if page > 1 else base_url
        page_data = scrape_defacements(url)
        all_data.extend(page_data)

        # Check if there are more pages available
        try:
            response = requests.get(url, headers={"User-Agent": get_random_user_agent()}, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            pagination = soup.find('ul', {'class': lambda x: x and 'pagination' in x})
            if pagination:
                last_page = max([int(a.get_text()) for a in pagination.find_all('a') if a.get_text().isdigit()])
                if page >= last_page:
                    logging.info(Fore.GREEN + "📄 Reached the last available page.")
                    break
        except Exception as e:
            logging.warning(Fore.YELLOW + f"⚠️ Could not determine pagination: {e}")
            break

    save_data(all_data, output_file, args.format)

    end_time = time.time()
    total_time = end_time - start_time
    total_entries = len(all_data)

    logging.info(Fore.GREEN + f"🔢 Total number of entries scraped: {total_entries}")
    logging.info(Fore.GREEN + f"⏱️ Total running time: {total_time:.2f} seconds")

if __name__ == "__main__":
    main()
