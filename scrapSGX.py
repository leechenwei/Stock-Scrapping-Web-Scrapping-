import requests
import logging
import argparse
import time
import os
import sys
import json
import subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from datetime import datetime
import shutil

# Set default download directory and log file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DOWNLOAD_DIR = os.path.join(BASE_DIR, "SgxDownload")
DEFAULT_LOG_FILE = os.path.join(BASE_DIR, "sgx_download.log")
DEFAULT_RETRIES = 3
DEFAULT_CRON = None
TEMP_DIR = os.path.join(os.getcwd(), "temp")
os.makedirs(TEMP_DIR, exist_ok=True)  # Create temp folder if not exists

# Define the base URL for file downloads
BASE_URL = "https://links.sgx.com/1.0.0/derivatives-historical"
TEMP_DIR = "./temp"
FILES_TO_DOWNLOAD = ["WEBPXTICK_DT.zip", "TickData_structure.dat", "TC_structure.dat"] #Only 3 files here because Initially i will download TC_*.txt to check for the right key mapping to the right date

# Define file types and their corresponding dropdown options
FILE_TYPES = {
    "Tick": "Tick",
    "Tick Data Structure": "Tick Data Structure",
    "Trade Cancellation": "Trade Cancellation",
    "Trade Cancellation Data Structure": "Trade Cancellation Data Structure"
}

# Set up argument parser
parser = argparse.ArgumentParser(description="SGX Derivatives Data Downloader")
parser.add_argument(
    "-v", 
    "--verbose", 
    action="store_true", 
    help="Enable verbose logging. When this flag is set, the script will log detailed debug information to both stdout and the log file. Without this flag, only essential information will be logged. Example: '-v' or '--verbose'."
)

parser.add_argument(
    "--auto", 
    action="store_true", 
    help="Automatically select the latest available date. This option will instruct the script to fetch the most recent data available on the website, without needing to specify a particular date. Example: '--auto'."
)

parser.add_argument(
    "--retry", 
    type=int, 
    default=DEFAULT_RETRIES, 
    help="Specify the number of retry attempts for failed downloads. If a download fails, the script will retry the specified number of times. Default is 3. Example: '--retry 5'."
)

parser.add_argument(
    "--date", 
    type=str, 
    help="Specify a specific date in the format YYYYMMDD to download the data files for that date. If the date is in the past, the script will try to download historical files. Example: '--date 20250228'."
)

parser.add_argument(
    "--cron", 
    type=str, 
    default=DEFAULT_CRON, 
    help="Provide a cron expression to schedule the script for automated execution. This option is useful for scheduling the download process on a server using cron jobs. Example: '--cron '0 3 * * *' (runs at 3 AM every day)."
)

parser.add_argument(
    "--config", 
    type=str, 
    help="Path to a JSON configuration file that contains user preferences such as download directory, log file location, and retry attempts. This is optional but allows users to externalize configuration. Example: '--config /path/to/config.json'."
)
args = parser.parse_args()

# Load configuration from config file if provided
config = {
    "download_dir": DEFAULT_DOWNLOAD_DIR,
    "log_file": DEFAULT_LOG_FILE,
    "retries": DEFAULT_RETRIES,
}

if args.config:
    with open(args.config, 'r') as config_file:
        config.update(json.load(config_file))

# Configure logging
log_level = logging.DEBUG if args.verbose else logging.INFO
logging.basicConfig(level=log_level,
                    format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[
                        logging.StreamHandler(sys.stdout),
                        logging.FileHandler(config['log_file'], mode="a")
                    ])

# Starting reference date (the first date in your data with a known key)
reference_date = "28 Feb 2025"
reference_key = 5888

# Function to calculate the key for a given date
def calculate_key_for_date(selected_date, latest_date, latest_key):
    """Maps the selected date to its corresponding SGX key dynamically."""
    ref_date_obj = datetime.strptime(reference_date, "%d %b %Y")
    latest_date_obj = datetime.strptime(latest_date, "%d %b %Y")
    selected_date_obj = datetime.strptime(selected_date, "%d %b %Y")

    # Compute the gap between the reference date and the latest available date
    ref_to_latest_days = (latest_date_obj - ref_date_obj).days
    latest_mapped_key = reference_key + ref_to_latest_days

    # Compute the gap between the reference date and the selected date
    ref_to_selected_days = (selected_date_obj - ref_date_obj).days

    # Adjust the key using the latest known key
    estimated_key = latest_key - (latest_mapped_key - reference_key - ref_to_selected_days)

    logging.info(f"📅 Selected Date: {selected_date} → Estimated Key: {estimated_key}")
    return estimated_key

def download_file(file_url, save_dir, retries=3):
    """Downloads a file and saves it with the actual name assigned by the server."""
    full_url = BASE_URL + file_url
    logging.info(f"📥 Downloading from {full_url}...")

    attempt = 0
    while attempt < retries:
        try:
            response = requests.get(full_url)
            if response.status_code == 404:
                logging.error(f"⚠️ File not found (URL: {full_url})")
                return None

            response.raise_for_status()

            # Extract filename from response headers (if available)
            content_disposition = response.headers.get("Content-Disposition", "")
            if "filename=" in content_disposition:
                file_name = content_disposition.split("filename=")[-1].strip('"')
            else:
                # If no filename is in headers, infer from the URL
                file_name = file_url.split("/")[-1]  # e.g., "/5888/TC.txt" → "TC.txt"

            full_file_path = os.path.join(save_dir, file_name)

            with open(full_file_path, "wb") as f:
                f.write(response.content)

            logging.info(f"✅ Downloaded {file_name} successfully to {full_file_path}")
            return file_name  # Return actual filename

        except Exception as e:
            attempt += 1
            logging.error(f"⚠️ Failed to download file (Attempt {attempt}): {e}")
            if attempt < retries:
                logging.info(f"🔄 Retrying... ({retries - attempt} attempts left)")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logging.error(f"❌ Failed to download after {retries} attempts")
                return None

    return None


def check_correct_file_exists(formatted_date):
    """Checks if any file in TEMP_DIR contains the correct date in its name."""
    for filename in os.listdir(TEMP_DIR):
        logging.info(f"🔍 Checking file: {filename}, Expected date: {formatted_date}")
        if filename.startswith("TC_") and formatted_date in filename:
            return filename  # Return the correct filename
    return None  # No valid file found

#Binary search to find correct date mapped with key
def binary_search_key(selected_date, left, right):
    """Finds the correct key using binary search, ensuring we pick the right file."""
    formatted_date = datetime.strptime(selected_date, "%d %b %Y").strftime("%Y%m%d")
    correct_key = None

    while left <= right:
        mid = left + (right - left) // 2
        logging.info(f"🔍 Checking key {mid} for date {selected_date}...")

        # Step 1: Download test file
        tc_file_url = f"/{mid}/TC.txt"
        downloaded_filename = download_file(tc_file_url, TEMP_DIR)

        # Step 2: Check if the correct filename exists
        correct_filename = check_correct_file_exists(formatted_date)
        if correct_filename:
            logging.info(f"✅ Found correct key: {mid} (File: {correct_filename} matches {formatted_date})")
            correct_key = mid

            # Move file to the correct folder
            os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
            shutil.move(os.path.join(TEMP_DIR, correct_filename), os.path.join(DEFAULT_DOWNLOAD_DIR, correct_filename))
            return correct_key  # ✅ Stop searching

        # List downloaded files in TEMP_DIR
        temp_files = os.listdir(TEMP_DIR)

        if len(temp_files) == 1 and temp_files[0] == "TC.txt":
            logging.warning(f"⚠️ Key {mid} returned a generic TC.txt, likely a FUTURE key. Moving LEFT...")
            right = mid - 1  # Move left (too far in future)
        else:
            logging.info(f"➡️ Key {mid} returned a past-dated file, moving RIGHT...")
            left = mid + 1  # Move right (too far in past)

        # Cleanup temp files
        for file in temp_files:
            os.remove(os.path.join(TEMP_DIR, file))

    logging.error("❌ Unable to find the correct key.")
    return None


def get_correct_key_for_date(selected_date, ref_key, ref_date, is_auto):
    """Finds the correct key using binary search, determining whether to move forward or backward."""
    if datetime.strptime(selected_date, "%d %b %Y") > datetime.strptime(ref_date, "%d %b %Y"):
        left, right = ref_key, ref_key + 50  # Move forward
        logging.info(f"🔄 Moving FORWARD from reference key {ref_key} (Ref Date: {ref_date})")
    else:
        left, right = max(1, ref_key - 50), ref_key  # Move backward
        logging.info(f"🔄 Moving BACKWARD from reference key {ref_key} (Ref Date: {ref_date})")

    return binary_search_key(selected_date, left, right)


def download_sgx_files_for_date(selected_date, latest_date, ref_key, ref_date, is_auto):
    """Downloads SGX files for a specific date by finding the correct key first."""
    if not latest_date or not ref_key or not ref_date:
        logging.error("❌ Unable to retrieve latest date or reference key. Exiting...")
        return

    formatted_date = datetime.strptime(selected_date, "%d %b %Y").strftime("%Y%m%d")

    # Ensure the selected date is within the available range
    if datetime.strptime(selected_date, "%d %b %Y") > datetime.strptime(latest_date, "%d %b %Y"):
        logging.error(f"❌ The selected date {selected_date} is later than the latest available date: {latest_date}")
        return

    # Step 1: Find the correct key using binary search
    key = get_correct_key_for_date(selected_date, ref_key, ref_date, is_auto)
    if not key:
        logging.error(f"❌ Could not find the correct key for {selected_date}. Exiting...")
        return

    logging.info(f"📅 Selected Date: {selected_date} → Confirmed Key: {key}")

    # Step 2: Download all required files using the confirmed key
    for file_name in FILES_TO_DOWNLOAD:
        file_url = f"/{key}/{file_name}"
        download_file(file_url, DEFAULT_DOWNLOAD_DIR)

    # Cleanup temp files
    for file in os.listdir(TEMP_DIR):
        os.remove(os.path.join(TEMP_DIR, file))

    logging.info("✅ All files downloaded successfully!")


# Start WebDriver in headless mode
options = Options()
options.set_preference("browser.download.folderList", 2)
options.set_preference("browser.download.dir", config["download_dir"])
options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/octet-stream")
options.set_preference("pdfjs.disabled", True)
options.add_argument("--headless")
driver = webdriver.Firefox(options=options)
driver.get("https://www.sgx.com/research-education/derivatives")
wait = WebDriverWait(driver, 10)

# Function to close cookie banner
def close_cookie_banner():
    try:
        cookie_banner = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "sgx-consent-banner-content")))
        close_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept')]")
        close_button.click()
        logging.info("✅ Closed Cookie Banner")
    except:
        logging.info("ℹ️ No Cookie Banner found, continuing...")

# Function to retrieve the latest available key
def get_latest_available_key(start_key):
    """Finds the latest available key, accounting for skipped dates."""
    key = start_key
    last_valid_key = key  # Track last successful key
    
    while True:
        test_url = f"{BASE_URL}/{key}/WEBPXTICK_DT.zip"
        response = requests.head(test_url)  # Faster than GET

        if response.status_code == 200:
            logging.info(f"✅ Found key {key} (Data available)")
            last_valid_key = key
            key += 1  # Keep checking next key
        else:
            logging.info(f"🔍 Key {key} not found. Latest available key: {last_valid_key}")
            return last_valid_key  # Return last valid key before failure
        
def get_latest_available_date():
    """Finds the latest available date from the SGX website with retry mechanism."""
    max_retries = 5  # Number of retries
    retry_delay = 2  # Seconds to wait between retries

    for attempt in range(max_retries):
        try:
            latest_date_element = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//*[@id='page-container']/template-base/div/div/section[1]/div/sgx-widgets-wrapper/widget-research-and-reports-download[1]/widget-reports-derivatives-tick-and-trade-cancellation/div/sgx-input-select[2]/label/span[2]/input")
            ))
            latest_date = latest_date_element.get_attribute('value')

            if latest_date:  # ✅ Ensure it's not empty
                logging.info(f"✅ Latest available date found: {latest_date}")
                return latest_date
            else:
                logging.warning(f"⚠️ Attempt {attempt+1}: Retrieved blank latest date. Retrying in {retry_delay} sec...")
                time.sleep(retry_delay)

        except Exception as e:
            logging.error(f"⚠️ Attempt {attempt+1}: Failed to retrieve latest available date: {e}")
            time.sleep(retry_delay)  # Wait before retrying

    logging.error("❌ Failed to retrieve latest available date after multiple attempts. Exiting...")
    return None  # Return None if all retries fail

# Function to select a type of data
def select_type_of_data(data_type):
    try:
        type_dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "//widget-reports-derivatives-tick-and-trade-cancellation//sgx-input-select[1]//input")))
        type_dropdown.click()
        logging.info(f"✅ Opened Type of Data dropdown for {data_type}")

        wait.until(EC.presence_of_element_located((By.ID, "sgx-select-dialog")))

        type_option = wait.until(EC.element_to_be_clickable((By.XPATH, f"//*[@id='sgx-select-dialog']//span[text()='{data_type}']")))
        type_option.click()
        logging.info(f"✅ Selected {data_type}")

    except Exception as e:
        logging.error(f"⚠️ Failed to select {data_type}: {e}")

#Cron job
def schedule_cron_job(cron_expression):
    """Schedules the script as a cron job with the given cron expression."""
    script_path = os.path.abspath(__file__)
    log_file_path = os.path.abspath("sgx_download.log")  # Use your actual config path
    python_path = "/usr/local/bin/python3"  # Ensure this is correct (use `which python3` to confirm)

    cron_command = f"{cron_expression} {python_path} {script_path} --auto >> {log_file_path} 2>&1"

    try:
        # Fetch existing cron jobs (handle empty crontab case)
        process = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing_cron = process.stdout.strip() if process.returncode == 0 else ""

        # Avoid duplicating cron jobs
        if cron_command in existing_cron:
            logging.info("✅ Cron job already exists.")
            return

        # Prepare new cron job entry
        new_cron = f"{existing_cron}\n{cron_command}\n" if existing_cron else f"{cron_command}\n"

        # Add the new cron job
        process = subprocess.run(["crontab", "-"], input=new_cron, text=True, capture_output=True)

        if process.returncode == 0:
            logging.info("✅ Cron job added successfully.")
        else:
            logging.error(f"⚠️ Failed to add cron job: {process.stderr}")

    except Exception as e:
        logging.error(f"⚠️ Error setting up cron job: {e}")
        
# Main function to execute the script
try:
    logging.info("🚀 Starting SGX Derivatives Data Download...")

    # Run the actual task first
    if args.auto:
        logging.info("Auto-mode: fetching latest available date...")
        latest_date = get_latest_available_date()
        if latest_date:
            selected_date = datetime.strptime(latest_date, "%d %b %Y").strftime("%d %b %Y")
            download_sgx_files_for_date(selected_date, latest_date, reference_key, reference_date, is_auto=True)

    elif args.date:
        selected_date = datetime.strptime(args.date, "%Y%m%d").strftime("%d %b %Y")
        logging.info(f"Checking if the provided date {selected_date} is valid...")
        latest_date = get_latest_available_date()
        if latest_date:
            download_sgx_files_for_date(selected_date, latest_date, reference_key, reference_date, is_auto=False)

    else:
        logging.error("No date provided, and auto mode not selected. Exiting...")

    # If --cron is provided, schedule the cron job AFTER running the task
    if args.cron:
        logging.info(f"🕒 Scheduling script as a cron job: {args.cron}")
        schedule_cron_job(args.cron)  # Calls function to add cron job

    logging.info("✅ All requested files downloaded successfully!")

except Exception as e:
    logging.error(f"⚠️ Unexpected error: {e}")

finally:
    if 'driver' in globals():
        driver.quit()