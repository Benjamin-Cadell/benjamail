#%% Imports

import sys, os, re, base64, pickle
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError
from base64 import urlsafe_b64decode, urlsafe_b64encode
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from mimetypes import guess_type as guess_mime_type
os.chdir("C:/Users/benja/Onedrive/Documents/Python Scripts/Gmail")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

#%% Authentication

def authenticate():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
      creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
      # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
      
    service = build("gmail", "v1", credentials=creds)
      
    return service

service = authenticate() # Global variable

#%% Main

def list_folders():
    
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])
    
    if not labels:
        print("No labels found.")
        return
    
    print("Labels:")
    for label in labels:
        print(label["name"])


def search_messages(query):
    result = service.users().messages().list(userId='me',q=query).execute()
    messages = []
    if 'messages' in result:
        messages.extend(result['messages'])
    while 'nextPageToken' in result:
        page_token = result['nextPageToken']
        result = service.users().messages().list(userId='me',q=query, pageToken=page_token).execute()
        if 'messages' in result:
            messages.extend(result['messages'])
    return messages

# list_folders()
messages = search_messages(query='label:Work')
print(messages)