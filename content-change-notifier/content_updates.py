"""Check for updates to URLs in spreadsheet

Requirements: In the header (row 1), there must be a column named 'URL' and a column named 'Last updated'.

Users can add and remove URLs, change the order of the URLs, change the order and number of columns.

This script performs the following:
1. Get a list or URLs from the 'URL' column
2. Get the content of those URLs and compare to the previously stored content
3. If the content matches, record the update
4. Write update time to the spreadsheet as necessary
"""

from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from slack_webhook import Slack
import requests
import string

from datetime import datetime
import pickle
import os.path

# Create an app at https://api.slack.com/apps/ and enable Webhooks, then put URL here
slack = Slack(url='https://hooks.slack.com/services/XX/YY/ZZ')

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# The ID and header range of the spreadsheet.
SPREADSHEET_ID = '102MGCpSBZ1IwZLP0IkERSz-JoRM5ltMGLnxEULEBTrA'
HEADER_RANGE = 'A1:Z1'

def main():
    """Check for updates to the URLs and update the spreadsheet accordingly"""
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    header = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=HEADER_RANGE
    ).execute().get('values')[0]
    urls = get_urls(header, sheet)
    updates, is_updated = get_updates(header, sheet, urls)
    write_updates(header, sheet, updates)
    notify_slack(urls, updates, is_updated)

def get_credentials():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def get_updates(header, sheet, urls):
    """Record when URLs were last updated
    
    prev_contents : dictionary
        Dictionary mapping URL to {'content': string, 'updated': datetime}
    last_updated : list
        List of strings of when URL was last udpated (parallel to URLs list)
    is_updated : list
        List of booleans of whether an URL was updated this run (parallel to URLs list)
    """
    if os.path.exists('prev_contents.pickle'):
        with open('prev_contents.pickle', 'rb') as prev_contents_f:
            prev_contents = pickle.load(prev_contents_f)
    else:
        prev_contents = {}
    last_updated = []
    is_updated = []
    curr_contents = {}
    for url in urls:
        if not url:
            last_updated.append([''])
            is_updated.append([''])
        else:
            curr_content = BeautifulSoup(requests.get(url).content, 'lxml').body.text
            prev_content = prev_contents.get(url)
            if prev_content is None or curr_content != prev_content['content']:
                url_updated = datetime.utcnow()
                is_updated.append(True)
            else:
                url_updated = prev_content['updated']
                is_updated.append(False)
            curr_contents[url] = {'content': curr_content, 'updated': url_updated}
            last_updated.append([url_updated.strftime("%m/%d/%Y, %H:%M:%S")])
    # Save current contents
    with open('prev_contents.pickle', 'wb') as prev_contents_f:
        pickle.dump(curr_contents, prev_contents_f)
    return last_updated, is_updated

def get_urls(header, sheet):
    # Get list of URLs from sheet
    url_col = string.ascii_uppercase[header.index('URL')]
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range='{0}2:{0}1000'.format(url_col)
    ).execute()
    urls = result.get('values', [])
    return [('' if not url else url[0]) for url in urls]

def write_updates(header, sheet, updates):
    # Write updates to sheet
    updates_col = string.ascii_uppercase[header.index('Last updated')]
    result = sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range='{0}2:{0}1000'.format(updates_col),
        valueInputOption='RAW',
        body={'values': updates}
    ).execute()

def notify_slack(urls, updates, is_updated):
    text = ""
    for url in urls:
        row_updated = is_updated.pop(0)
        timestamp = updates.pop(0)
        if row_updated:
            text = text + "Updated at " + str(timestamp[0]) + " " + str(url) + "\n"
    slack.post(text=text)
    
if __name__ == '__main__':
    main()