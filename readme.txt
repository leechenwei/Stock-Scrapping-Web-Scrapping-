Overview
The SGX Derivatives Data Downloader is a Python script that allows users to download historical data files from the SGX (Singapore Exchange) website. It supports downloading both today's data and historical files for specific dates. The script provides several configuration options and robust logging to assist in troubleshooting and auditing the download process.

Prerequisites
Before running the script, ensure you have the following installed:

Python 3.x - Install Python from https://www.python.org/downloads/.
Required Libraries:
requests: Used for sending HTTP requests to download the data.
selenium: Used for interacting with the SGX website and extracting data.
argparse: For handling command-line arguments.
logging: For logging the script's execution.
Firefox WebDriver (for Selenium) 

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
Setting up
1. Unzip the folder and save to a directory eg. Save it in /downloads
2. open the folder or cd to /downloads/DTLInterview
3. run the script "python3 scrapSGX.py --help" for starting an overview of script usage

Note:
1. To solution: A job to download the following files daily scheduled at 7:00A.M example from the SGX website use "python3 scrapSGX.py --auto --cron '0 7 0 0 0'"
2. crontab -l to check for the scheduled job
3. crontab -r to remove the scheduled job
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

Script Usage
The script can be run from the command line with various options. Here are the available command-line options:

1. --verbose or -v
Enable verbose logging to display detailed debug information during execution.

python script.py --verbose

2. --auto
Automatically select the latest available date for downloading data from SGX.

python script.py --auto

3. --retry
Define the number of retries for failed downloads. By default, the script will retry 3 times before giving up.


python script.py --retry 5

4. --date
Specify a specific date (in YYYYMMDD format) for downloading the data. If you want to download data for a past date, use this option.

python script.py --date 20250228

5. --cron
Provide a cron expression to schedule the script for automated execution on a server. For example, the following cron expression would run the script at 3 AM every day:

python script.py --cron '0 3 * * *'

For your information about cron job:
* * * * *
| | | | |
| | | | +----- Day of week (0 - 6) (Sunday=0)
| | | |------- Month (1 - 12)
| | |--------- Day of month (1 - 31)
| |----------- Hour (0 - 23)
|------------- Minute (0 - 59)


6. --config
Path to a JSON configuration file to specify settings like download directory, log file location, and retry attempts. This is optional.

python script.py --config /path/to/config.json

Example Command:

python script.py --verbose --date 20250228 --config /path/to/config.json

Configuration Options
Download Directory: Specify where downloaded files will be stored. This can be set via the configuration file or command-line argument --config.

Logging: Logs will be generated both on the console and in a log file. The log file will include details of every download attempt, retries, and any errors encountered.

Cron Scheduling: Use the --cron argument to automate this script using cron jobs for periodic execution (e.g., daily downloads).

Example JSON Configuration File
The optional JSON configuration file allows you to specify default settings like the download directory, retry attempts, and log file location. Here's an example configuration:

{
  "download_dir": "/path/to/download/directory",
  "log_file": "/path/to/logfile.log",
  "retries": 3
}

Error Handling and Recovery
The script is designed to handle errors and retry failed downloads automatically. If a download fails, the script will attempt to download the file again up to the specified retry limit (--retry). If the download continues to fail after all retries, the script will log the error and proceed with the next task.

You can also specify the --auto flag to download the latest available files without needing to manually specify a date.


Troubleshooting
Missing Files: If certain files are missing, check the logs for any errors related to downloading and retry attempts.
WebDriver Issues: Ensure that the appropriate WebDriver is installed for Selenium and correctly set up in your system's PATH.
Permission Issues: If the script fails to write downloaded files to the specified directory, check the permissions on that directory.