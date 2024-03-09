import os
import requests
from bs4 import BeautifulSoup
import csv
import datetime
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse
import json
import logging
import matplotlib.pyplot as plt

# Constants
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
GRAPHQL_URL = 'https://www.gasbuddy.com/graphql'
HEADERS = {'User-Agent': USER_AGENT, 'Content-Type': 'application/json'}

# Initialize logging
logging.basicConfig(level=logging.DEBUG, filename='scraper.log', format='%(asctime)s - %(levelname)s - %(message)s')


# Welcome message and usage instructions
def welcome_message():
    print("Welcome to FuelMeUp4LessScraper! 0.5v by Malik Al-Musawi ")
    print("This tool still in-test helps you find the cheapest gas prices.")
    print("\nUsage:")
    print("h - Help")
    print("1 - Scrape Data")
    print("2 - Sort Data")
    print("3 - Graph Data")
    print("4 - All-In-One")
    print("5 - Cost to fill")
    print("6 - Exit")


# Function to display menu and get user choice
def get_menu_choice():
    print("\nPlease choose an option:")
    choice = input("Enter 'h' for help or a number between 1-6 to select an action: ").strip().lower()
    return choice


def file_exists(filename):
    return os.path.exists(filename)


# Function to get user input for scraping
def get_scraping_input():
    while True:
        city_or_postal_code = input("Enter city or postal code: ").strip()
        if not city_or_postal_code:
            print("City or postal code cannot be empty. Please try again.")
            continue
        break

    fuel_type = None
    while True:
        fuel_input = input(
            "Choose fuel type (1=Regular, 2=Midgrade, 3=Premium, 4=Diesel, 5=E85, 6=UNL88 or enter fuel name): ").strip().lower()
        fuel_dict = {'regular': '1', 'midgrade': '2', 'premium': '3', 'diesel': '4', 'e85': '5', 'unl88': '6'}
        fuel_type = fuel_dict.get(fuel_input, fuel_input)
        if fuel_type not in ['1', '2', '3', '4', '5', '6']:
            print("Invalid fuel type. Please enter a number between 1-6 or the corresponding fuel name.")
            continue
        break

    payment_method = None
    while True:
        payment_method = input("Choose payment method (all/credit): ").strip().lower()
        if payment_method not in ['all', 'credit']:
            print("Invalid payment method. Please enter 'all' or 'credit'.")
            continue
        break

    file_type = None
    while True:
        file_type = input("Choose output file type (csv/txt): ").strip().lower()
        if file_type not in ['csv', 'txt']:
            print("Invalid file type. Please enter 'csv' or 'txt'.")
            continue
        break

    total_pages = None
    while True:
        try:
            total_pages = int(input("Enter the total number of pages to fetch: ").strip())
            if total_pages < 0:
                raise ValueError
        except ValueError:
            print("Invalid input. Please enter a positive integer.")
            continue
        break

    return city_or_postal_code, fuel_type, payment_method, file_type, total_pages


# Function to handle the sorting of data
def handle_sorting(gas_prices):
    print("\nSorting Options:")
    print("1 - By Name")
    print("2 - By Price")
    print("3 - By Last Updated")
    sort_choice = input("Select an option to sort by (1-3): ").strip()

    sort_options = {
        '1': 'name',
        '2': 'price',
        '3': 'last_updated'
    }
    sort_by = sort_options.get(sort_choice, 'price')

    order_choice = input("Select order (1 for ascending, 2 for descending): ").strip()
    ascending = order_choice != '2'

    sorted_gas_prices = sort_gas_prices(gas_prices, sort_by=sort_by, ascending=ascending)
    return sorted_gas_prices


# Function to plot graph
def graph_data(gas_prices):
    plot_gas_prices(gas_prices)


# Function to perform all actions in one go
def all_in_one():
    city_or_postal_code, fuel_type, payment_method, file_type, total_pages = get_scraping_input()
    scraped_data = scrape_data(city_or_postal_code, fuel_type, payment_method, total_pages)

    if not scraped_data:
        print("No data scraped. Exiting All-In-One mode.")
        return

    filepath = save_to_file(scraped_data, file_type)
    if not filepath:
        print("Failed to save data. Exiting All-In-One mode.")
        return

    # Ask user for the sorting field and order
    print("\nSorting Options:")
    print("1 - By Name")
    print("2 - By Price")
    print("3 - By Last Updated")
    sort_choice = input("Select an option to sort by (1-3): ").strip()
    sort_options = {
        '1': 'name',
        '2': 'price',
        '3': 'last_updated'
    }
    sort_by = sort_options.get(sort_choice, 'price')
    order_choice = input("Select order (1 for ascending, 2 for descending): ").strip()
    ascending = order_choice == '1'

    # Convert price strings to float values
    for entry in scraped_data:
        entry['price'] = convert_price(entry['price'])

    # Sort the data
    sorted_data = sort_gas_prices(scraped_data, sort_by=sort_by, ascending=ascending)

    # Save the sorted data to a new file
    sorted_filepath = save_to_file(sorted_data, file_type, filename_prefix="sorted_gas_prices")
    if not sorted_filepath:
        print("Failed to save sorted data. Exiting All-In-One mode.")
        return

    print(f"Data sorted by {sort_by} and saved to {sorted_filepath}")

    # Graph the sorted data
    graph_data(sorted_data)


# Function to scrape data
def scrape_data(city_or_postal_code, fuel_type, payment_method, total_pages):
    all_gas_prices = []

    # Fetch and parse initial page
    initial_soup = fetch_initial_data(city_or_postal_code, fuel_type, payment_method)
    if initial_soup:
        initial_data = parse_initial_data(initial_soup)
        all_gas_prices.extend(initial_data)

        # Fetch and parse additional pages if requested
        if total_pages > 1:
            cursor = "40"  # Starting cursor for the second page
            for _ in range(2, total_pages + 1):
                json_data = fetch_additional_gas_prices(city_or_postal_code, fuel_type, cursor)
                if json_data:
                    additional_data, new_cursor = parse_additional_data(json_data)
                    all_gas_prices.extend(additional_data)
                    cursor = new_cursor  # Update cursor for the next iteration
                else:
                    break  # Exit loop if data fetching fails
    else:
        print("Failed to retrieve initial data. Please check your internet connection and try again.")
        return None

    return all_gas_prices


# Function to format last updated time
def format_last_updated(posted_time):
    posted_datetime = datetime.fromisoformat(posted_time.rstrip('Z')).replace(tzinfo=timezone.utc)
    now_datetime = datetime.now(timezone.utc)
    diff = now_datetime - posted_datetime
    if diff.days == 0:
        hours_ago = diff.seconds // 3600
        return f"{hours_ago} hours ago" if hours_ago > 0 else "Less than an hour ago"
    else:
        return posted_datetime.strftime("%Y-%m-%d")


# Sort gas prices
def sort_gas_prices(gas_prices, sort_by='price', ascending=True):
    # Filter out entries with None prices before sorting
    if sort_by == 'price':
        gas_prices = [entry for entry in gas_prices if entry['price'] is not None]

    # Sorting logic remains the same
    key_funcs = {
        'name': lambda x: x['name'],
        'price': lambda x: x['price'] or float('inf'),  # Handle None values by converting them to infinity
        'last_updated': lambda x: convert_last_updated(x['last_updated'])
    }
    return sorted(gas_prices, key=key_funcs[sort_by], reverse=not ascending)


# Plot gas prices
def plot_gas_prices(gas_prices):
    # Convert price strings to floats and filter out invalid entries
    valid_entries = [entry for entry in gas_prices if isinstance(entry['price'], float)]

    if not valid_entries:
        print("No valid prices available for graphing.")
        return

    names = [entry['name'] for entry in valid_entries]
    prices = [entry['price'] for entry in valid_entries]

    average_price = sum(prices) / len(prices)
    lowest_price = min(prices)

    plt.figure(figsize=(10, 5))
    plt.bar(names, prices, label='Price', color='skyblue')
    plt.axhline(y=average_price, color='r', linestyle='-', label=f'Average Price: {average_price:.2f}')
    plt.axhline(y=lowest_price, color='b', linestyle='-', label=f'Lowest Price: {lowest_price:.2f}')
    plt.xlabel('Station Names')
    plt.ylabel('Price in $')
    plt.title('Gas Prices Comparison')
    plt.xticks(rotation=90)
    plt.legend()
    plt.tight_layout()

    graph_filename = f"gas_prices_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    plt.savefig(graph_filename)
    print(f"Graph saved as {graph_filename}")
    plt.close()  # Close the plot to prevent display issues


# Fetch initial data with BeautifulSoup
def fetch_initial_data(city_or_postal_code, fuel_type, payment_method):
    url = f"https://www.gasbuddy.com/home?search={city_or_postal_code}&fuel={fuel_type}&method={payment_method}"
    response = requests.get(url, headers={'User-Agent': USER_AGENT})
    if response.status_code == 200:
        return BeautifulSoup(response.text, 'html.parser')
    else:
        logging.error(f"Failed to fetch initial data for {city_or_postal_code}, status code: {response.status_code}")
        return None


# Parse initial data from BeautifulSoup
def parse_initial_data(soup):
    gas_prices = []
    stations = soup.select('.GenericStationListItem-module__stationListItem___3Jmn4')
    for station in stations:
        name = station.select_one('.header__header3___1b1oq').text.strip()
        address = station.select_one('.StationDisplay-module__address___2_c7v').text.strip().replace(' \n', ', ')
        price = station.select_one('.StationDisplayPrice-module__price___3rARL').text.strip()
        last_updated_element = station.select_one('.ReportedBy-module__postedTime___J5H9Z')
        if last_updated_element is not None:
            last_updated = last_updated_element.text.strip()  # ISO formatted
        else:
            last_updated = "N/A"


        gas_prices.append({'name': name, 'address': address, 'price': price, 'last_updated': last_updated})
    return gas_prices


# Fetch additional data with GraphQL
def fetch_additional_gas_prices(city_or_postal_code, fuel_type, cursor="40"):
    payload = {
        "operationName": "LocationBySearchTerm",
        "variables": {
            "fuel": int(fuel_type),
            "search": city_or_postal_code,
            "cursor": cursor
        },
        "query": """query LocationBySearchTerm($brandId: Int, $cursor: String, $fuel: Int, $lat: Float, $lng: Float, $maxAge: Int, $search: String) {
  locationBySearchTerm(lat: $lat, lng: $lng, search: $search) {
    countryCode
    displayName
    latitude
    longitude
    regionCode
    stations(
      brandId: $brandId
      cursor: $cursor
      fuel: $fuel
      lat: $lat
      lng: $lng
      maxAge: $maxAge
    ) {
      count
      cursor {
        next
        __typename
      }
      results {
        address {
          country
          line1
          line2
          locality
          postalCode
          region
          __typename
        }
        badges {
          badgeId
          callToAction
          campaignId
          clickTrackingUrl
          description
          detailsImageUrl
          detailsImpressionTrackingUrls
          imageUrl
          impressionTrackingUrls
          targetUrl
          title
          __typename
        }
        brands {
          brandId
          brandingType
          imageUrl
          name
          __typename
        }
        distance
        emergencyStatus {
          hasDiesel {
            nickname
            reportStatus
            updateDate
            __typename
          }
          hasGas {
            nickname
            reportStatus
            updateDate
            __typename
          }
          hasPower {
            nickname
            reportStatus
            updateDate
            __typename
          }
          __typename
        }
        enterprise
        fuels
        hasActiveOutage
        id
        name
        offers {
          discounts {
            grades
            highlight
            pwgbDiscount
            receiptDiscount
            __typename
          }
          highlight
          id
          types
          use
          __typename
        }
        payStatus {
          isPayAvailable
          __typename
        }
        prices {
          cash {
            nickname
            postedTime
            price
            formattedPrice
            __typename
          }
          credit {
            nickname
            postedTime
            price
            formattedPrice
            __typename
          }
          discount
          fuelProduct
          __typename
        }
        priceUnit
        ratingsCount
        starRating
        __typename
      }
      __typename
    }
    trends {
      areaName
      country
      today
      todayLow
      trend
      __typename
    }
    __typename
  }
}
"""  # Insert the GraphQL query here
    }
    response = requests.post(GRAPHQL_URL, json=payload, headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"Failed to fetch additional data for {city_or_postal_code}, status code: {response.status_code}")
        return None


# Parse additional data from GraphQL
def parse_additional_data(json_data):
    gas_prices = []
    if 'data' in json_data and 'locationBySearchTerm' in json_data['data']:
        stations_data = json_data['data']['locationBySearchTerm']['stations']['results']
        for station in stations_data:
            name = station.get('name', 'N/A')
            address_components = [station['address'].get('line1', ''),
                                  station['address'].get('locality', ''),
                                  station['address'].get('region', ''),
                                  station['address'].get('postalCode', '')]
            address = ', '.join(filter(None, address_components))
            prices = station.get('prices', [])
            price_info, last_updated = 'N/A', 'N/A'
            for price in prices:
                if price.get('credit'):
                    # Ensure formattedPrice is not repeated
                    price_info = price['credit'].get('formattedPrice', 'N/A')
                    last_updated_iso = price['credit'].get('postedTime', '')
                    if last_updated_iso:
                        last_updated = format_last_updated(last_updated_iso)
                    break  # Assuming we're interested in the first credit price
            # If price_info ends with '¢' or '$', we don't append another '¢' or '$'
            if price_info and not price_info.endswith(('¢', '$')):
                price_info += '¢' if price_info.isdigit() else ''
            gas_prices.append({'name': name, 'address': address, 'price': price_info, 'last_updated': last_updated})
    next_cursor = json_data['data']['locationBySearchTerm']['stations']['cursor'].get('next', None)
    return gas_prices, next_cursor



# Save data to file
def save_to_file(gas_prices, file_type, filename_prefix="gas_prices"):
    # Extract the base name in case a full path is provided
    base_filename = os.path.basename(filename_prefix)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{base_filename}_{timestamp}.{file_type}"
    filepath = os.path.join(os.getcwd(), filename)  # Save in the current working directory
    try:
        if file_type == 'csv':
            with open(filepath, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=['name', 'address', 'price', 'last_updated'])
                writer.writeheader()
                writer.writerows(gas_prices)
        elif file_type == 'txt':
            with open(filepath, 'w', encoding='utf-8') as file:
                for gas_price in gas_prices:
                    file.write(
                        f"{gas_price['name']}, {gas_price['address']}, {gas_price['price']}, {gas_price['last_updated']}\n")
        print(f"Data successfully saved to {filename}")
        return filepath  # Return the full path to the saved file
    except IOError as e:
        logging.error(f"Failed to save data to file: {e}")
        return None


def format_last_updated(posted_time):
    # Parse the ISO formatted datetime
    posted_datetime = datetime.fromisoformat(posted_time.rstrip('Z')).replace(tzinfo=timezone.utc)
    # Get the current time in UTC
    now_datetime = datetime.now(timezone.utc)
    # Calculate the difference in time
    time_diff = now_datetime - posted_datetime
    # Convert the time difference to hours
    hours_diff = time_diff.total_seconds() / 3600

    # If the difference is less than 24 hours, return the number of hours
    if hours_diff < 24:
        # Round down to the nearest whole number
        hours_ago = int(hours_diff)
        return f"{hours_ago} hours ago" if hours_ago > 0 else "Less than an hour ago"
    else:
        # For periods longer than 24 hours, return the actual date
        return posted_datetime.strftime('%Y-%m-%d')


def read_gas_prices_from_file(file_type, filename):
    gas_prices = []
    try:
        with open(filename, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                row['price'] = convert_price(row['price'])
                gas_prices.append(row)
    except IOError as e:
        logging.error(f"Failed to read data from file: {e}")
    return gas_prices


# Function to sort data from a file
def sort_data_from_file():
    file_type = input("Enter the file type (csv/txt) you want to sort: ").strip().lower()
    # validate the file type
    if file_type not in ['csv', 'txt']:
        print("Invalid file type. Please enter 'csv' or 'txt'.")
        return
    filepath = input("Enter the filename (including path) of the data to sort: ").strip()

    if not file_exists(filepath):
        print(f"File {filepath} not found.")
        return

    filename = os.path.basename(filepath)  # Extract the base filename
    gas_prices = read_gas_prices_from_file(file_type, filepath)
    sort_choice = input("Choose the field to sort by (name/price/last_updated): ").strip().lower()
    ascending = input("Should the data be sorted in ascending order? (yes/no): ").strip().lower() == 'yes'
    sorted_gas_prices = sort_gas_prices(gas_prices, sort_by=sort_choice, ascending=ascending)

    # Saving the sorted file with the corrected filename
    sorted_filename = f"sorted_{filename}"
    save_to_file(sorted_gas_prices, file_type, sorted_filename)
    print(f"Data sorted by {sort_choice} and saved to '{sorted_filename}'.")


# Function to graph data from a file
def graph_data_from_file():
    file_type = input("Enter the file type (csv/txt) of the data to graph: ").strip().lower()
    # validate the file type
    if file_type not in ['csv', 'txt']:
        print("Invalid file type. Please enter 'csv' or 'txt'.")
        return
    
    filename = input("Enter the filename (including path) of the data to graph: ").strip()

    if not file_exists(filename):
        print(f"File {filename} not found.")
        return

    gas_prices = read_gas_prices_from_file(file_type, filename)
    plot_gas_prices(gas_prices)
    print("Graph generated successfully.")


# Function to display menu and get user choice
def get_menu_choice():
    while True:
        print("\nPlease choose an option:")
        choice = input("Enter 'h' for help or a number between 1-6 to select an action: ").strip().lower()
        if choice in ['h', '1', '2', '3', '4', '5', '6']:
            return choice
        else:
            print("Invalid input. Please enter 'h' for help or a number between 1-6.")


# Function to display menu and get user choice
def convert_price(price_str):
    try:
        # Remove any non-numeric characters before conversion
        price = float(''.join(filter(str.isdigit, price_str)))
        return price / 10  # it should return the price correclty so if it was 129.9 it should be returend as 129.9
    except ValueError:
        return None


# Function to convert last updated time to datetime object
def convert_last_updated(last_updated):
    try:
        # Directly return datetime object if already in ISO format
        if "-" in last_updated:
            return datetime.strptime(last_updated, "%Y-%m-%d")
        # Handle 'X hours ago' format by calculating the datetime
        elif "hours ago" in last_updated:
            hours = int(last_updated.split(" ")[0])
            return datetime.now() - timedelta(hours=hours)
    except Exception as e:
        # Log error and return a default date in case of parsing failure
        logging.error(f"Error converting last updated time: {e}")
        return datetime.min


# Function to calculate the total price to fill specific amount of fuel or tank provided by the user and add it to the csv file
def calculate_total_price_to_fill():
    file_type = input(
        "Enter the file type (csv/txt) of the data to calculate the total price to fill: ").strip().lower()
    # validate the file type
    if file_type not in ['csv', 'txt']:
        print("Invalid file type. Please enter 'csv' or 'txt'.")
        return
    filename = input("Enter the filename (including path) of the data to calculate the total price to fill: ").strip()

    if not file_exists(filename):
        print(f"File {filename} not found.")
        return

    # read the gas prices for the first row from the file and make sure if it is in dollars or cents by looking for the dollar sign, if there is no sign we assume it is in cents
    if file_type == 'csv':
        with open(filename, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if '$' in row['price']:
                    # assign a variable to know if the price is in dollars or cents
                    dollars = True
                    break
                else:
                    dollars = False
                    break
    # if the file type is txt we should read the first line and check if it is in dollars or cents
    else:
        with open(filename, 'r', encoding='utf-8') as file:
            first_line = file.readline()
            if '$' in first_line:
                dollars = True
            else:
                dollars = False

    gas_prices = read_gas_prices_from_file(file_type, filename)
    # calculate the total price to fill specific amount of fuel or tank
    total_price = 0
    while True:
        try:
            amount = float(input("Enter the amount of fuel or tank to fill: ").strip())
            if amount < 0:
                raise ValueError
            # ask user if it is in gallons or liters
            while True:
                try:
                    unit = input("Enter 'g' for gallons or 'l' for liters: ").strip().lower()
                    if unit not in ['g', 'l']:
                        raise ValueError
                    break
                except ValueError:
                    print("Invalid input. Please enter 'g' for gallons or 'l' for liters.")
                    # if it is in gallons we ask if it british or american and then we convert only britsh it to liters since us total price must be in gallons since the prices are per gallon
            if unit == 'g':
                while True:
                    try:
                        gallons = input("Enter 'b' for British gallons or 'a' for American gallons: ").strip().lower()
                        if gallons not in ['b', 'a']:
                            raise ValueError
                        break
                    except ValueError:
                        print("Invalid input. Please enter 'b' for British gallons or 'a' for American gallons.")
                    # we should add something to know if it us and insert gallon in the csv file
                if gallons == 'b':
                    amount = amount * 4.54609
                    unit = 'l'
                else:
                    unit = 'gal'
            break
        except ValueError:
            print("Invalid input. Please enter a positive number.")
    # ask the user where he lives to calculate the tax
    while True:
        try:
            tax = float(input("Enter the tax in your area: ").strip())
            if tax < 0:
                raise ValueError
            break
            if tax > 100:
                raise ValueError
        except ValueError:
            print("Invalid input. Please enter a positive number.")
    tax = tax / 100

    # Add the calculated total price to the csv file as a new column called "Total Price" and save it into a new file
    for entry in gas_prices:
        if dollars:
            # dvide the entry of price by 10 since there was an issue when reading it shows 26.6 instead of 2.66
            entry['price'] = entry['price'] / 10
            # add a dollar sign to the price
            entry['Total Price'] = amount * entry['price']
            entry['price'] = f"${entry['price']:.2f}"
            if unit == 'l':
                entry['Total Price'] = entry['Total Price'] / 3.78541
            entry['Total Price'] = entry['Total Price'] + (entry['Total Price'] * tax)
            entry['Total Price'] = f"${entry['Total Price']:.2f}"
        else:
            entry['Total Price'] = amount * entry['price']
            # add a cent sign to the price
            entry['price'] = f"{entry['price']}¢"
            if unit == 'l':
                entry['Total Price'] = entry['Total Price'] / 100
            entry['Total Price'] = entry['Total Price'] + (entry['Total Price'] * tax)
            entry['Total Price'] = f"${entry['Total Price']:.2f}"
        # calculate the tax
        entry['Tax'] = f"{tax * 100}%"  # Add tax as a percentage
        entry['Filled'] = f"{amount} {unit}"  # Add the amount and unit of fuel/tank

    # Saving the file with the new columns "Total Price", "Tax", and "Liters"
    total_price_filename = f"Total_Price_{filename}"
    try:
        # If the file type is CSV
        if file_type == 'csv':
            with open(total_price_filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=['name', 'address', 'price', 'last_updated', 'Tax', 'Filled',
                                                          'Total Price'])
                writer.writeheader()
                writer.writerows(gas_prices)

        # If the file type is TXT
        elif file_type == 'txt':
            with open(total_price_filename, 'w', encoding='utf-8') as file:
                for gas_price in gas_prices:
                    file.write(
                        f"{gas_price['name']}, {gas_price['address']}, {gas_price['price']}, {gas_price['last_updated']}, {gas_price['Tax']}, {gas_price['Filled']}, {gas_price['Total Price']}\n")

        print(f"Data successfully saved to {total_price_filename}")
        return total_price_filename  # Return the full path to the saved file

    # If an IOError occurs (e.g., the file cannot be opened)
    except IOError as e:
        logging.error(f"Failed to save data to file: {e}")
        return None


# Main function to orchestrate the scraping process
def main():
    welcome_message()
    while True:
        choice = get_menu_choice()

        if choice == 'h':
            welcome_message()
        elif choice == '1':
            # Scrape data and save it to a file
            city_or_postal_code, fuel_type, payment_method, file_type, total_pages = get_scraping_input()
            all_gas_prices = scrape_data(city_or_postal_code, fuel_type, payment_method, total_pages)
            if all_gas_prices:
                save_to_file(all_gas_prices, file_type, "scraped_gas_prices")
                print("Data scraped and saved successfully.")
        elif choice == '2':
            # Sort data from a file
            sort_data_from_file()
        elif choice == '3':
            # Graph data from a file
            graph_data_from_file()
        elif choice == '4':
            # All-In-One operation
            all_in_one()
        elif choice == '5':
            # Calculate the total price to fill specific amount of fuel or tank
            calculate_total_price_to_fill()
        elif choice == '6':
            print("Exiting the program.")
            break
        else:
            print("Invalid choice. Please enter 'h' for help or a number between 1-6 to select an action.")


if __name__ == "__main__":
    main()