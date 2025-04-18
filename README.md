# ISB LMS Bulk Downloader

This only works on MacOS. You need to have Chrome installed before using this. 

## One Click Way
1. Download the repository. (Code -> Download as Zip)
2. Double click the ISB_LMS_Bulk_Scraper file. (The one without the .py).
3. A Chrome browser window and a terminal should pop up. Quickly log in to LMS, it times out after 90 seconds.
4. The download should start automatically. Files will be stored on your desktop in a folder titled ISB_Coursepacks, organized by term. You can monitor the progress in the terminal window. 


## Recommended Way
1.  **Download/Clone the Repository:**
    * Make sure you have downloaded or cloned this repository's files onto your computer.

2.  **Open Terminal:**
    * Launch the **Terminal** app.

3.  **Navigate to Project Directory:**
    * Use the `cd` (change directory) command to navigate into the folder where you downloaded/cloned this repository. For example, if it's in your Downloads folder:
        ```bash
        cd ~/Downloads/ISB-LMS-Bulk-Downloader-main 
        ```

4.  **Install Required Libraries:**
    * Run the following command in the Terminal to install the necessary Python packages. This command uses `pip3`, the package installer for Python 3.
        ```bash
        pip3 install selenium beautifulsoup4 requests webdriver-manager
        ```
    * *Note:* If you encounter issues or have multiple Python versions, you might need to run the installer using `python3 -m pip install ...` instead:
        ```bash
        # Alternative install command if the above fails
        python3 -m pip install selenium beautifulsoup4 requests webdriver-manager
        ```
    * Wait for the installation process to complete.

## Running the Scraper

1.  **Run the Script:**
    * Make sure you are still in the project directory in your Terminal.
    * Execute the script using the `python3` command:
        ```bash
        python3 ISB_LMS_Bulk_Scraper.py 
        ```

2.  **Manual Login (Important!):**
    * The script will start, and you'll see output in the Terminal.
    * A **new Google Chrome window** will open automatically and navigate to the ISB LMS login page.
    * The script will pause, and the Terminal will display a message prompting you to log in (e.g., `---> Please log in to the LMS... <---`).
    * **You MUST log in using the specific Chrome window that the script opened.** Do this quickly (you have about 90 seconds by default).
    * Once you successfully log in *in that window*, the script will detect it and continue automatically. Do not close the automated Chrome window.

3.  **Monitor Progress:**
    * Watch the Terminal window for status updates. It will show which course sections (Terms, Block Weeks) and courses it's processing, and which files are being downloaded, skipped, or encountered errors.
    * *(You might see a warning related to "NotOpenSSLWarning" or "LibreSSL" - this can usually be ignored).*

4.  **Completion:**
    * The script will process all detected courses and print a final summary report in the Terminal.
    * The automated Chrome window will close by itself.

## Finding Your Downloads

* All downloaded PDF files will be saved in a folder named `ISB_Coursepacks` located on your **Desktop**.
* Inside `ISB_Coursepacks`, files are organized into subfolders first by the Section name (e.g., `Term_6`, `Block_Week_1`) and then by the Course name.
