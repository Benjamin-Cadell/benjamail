import sys, os, re, base64, pickle, csv, pandas as pd, numpy as np
from google.oauth2 import service_account
from googleapiclient.discovery import build
from openai import OpenAI
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


class benjamail:

    def __init__(self, keys_folder="Keys", credentials_file="credentials.json", token_file="token.json",
                 openai_key="openai_key.txt", project_key="project_key.txt", organization_key="organization_key.txt"):
        self.credentials_file = f"{keys_folder}/{credentials_file}"
        self.token_file = f"{keys_folder}/{token_file}"
        self.api_key = f"{keys_folder}/{openai_key}"
        self.project_key = f"{keys_folder}/{project_key}"
        self.organization_key = f"{keys_folder}/{organization_key}"
        self.authenticate()

        # Initiate OpenAI API
        client = OpenAI(
            organization=self.organization_key,
            project=self.project_key,
            api_key = open(self.api_key, "r").read()
        )

        # completion = client.chat.completions.create(
        # model="gpt-4o-mini", # Models: gpt-4o-mini, o1-mini, o3-mini (not yet)
        # messages=[
        #     {"role": "user", "content": "Write the value of 8+10, nothing else"}
        # ]
        # )

        # print(completion.choices[0].message)

    def authenticate(self):
        SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
            with open("token.json", "w") as token_to_write:
                token_to_write.write(creds.to_json())
        
        self.service = build("gmail", "v1", credentials=creds)
        return

    def list_folders(self):
        
        results = self.service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])
        
        if not labels:
            print("No labels found.")
            return
        
        print("Labels:")
        for label in labels:
            print(label["name"])

    def search_messages(self, query):
        result = self.service.users().messages().list(userId='me',q=query).execute()
        messages = []
        if 'messages' in result:
            messages.extend(result['messages'])
        while 'nextPageToken' in result:
            page_token = result['nextPageToken']
            result = self.service.users().messages().list(userId='me',q=query, pageToken=page_token).execute()
            if 'messages' in result:
                messages.extend(result['messages'])
        return messages

    def get_label_id(self, label_name):
        """Returns the label ID for a given label name."""
        results = self.service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])
        for label in labels:
            if label["name"].lower() == label_name.lower():
                return label["id"]
        return None

    def load_moving_rules(self, csv_file="moving_rules.csv"):
        try:
            df = pd.read_csv(csv_file)
            # Ensure only the required columns are present
            rules = df[['Word', 'Folder']].to_dict(orient='records')
            return rules  # Return the rules so that process_old_emails gets a valid list.
        except Exception as e:
            raise Exception(f"Error reading {csv_file}: {e}")

    def process_old_emails(self, older_than_days=7, rules_file="moving_rules.csv"):
        # Search for emails in the inbox older than 7 days, newer_than or older_than
        query = f"in:inbox newer_than:{older_than_days}d"
        messages = self.search_messages(query=query)

        if not messages:
            print(f"No emails older than {older_than_days} days found.")
            return

        # Get the label ID for the labelling rules
        self.rules = self.load_moving_rules(rules_file)

        for msg in messages:
            try:
                # Retrieve full message details
                message_detail = self.service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
                
                # Extract headers to get the subject and use the snippet for additional context
                headers = message_detail.get("payload", {}).get("headers", [])
                subject = ""
                for header in headers:
                    if header["name"].lower() == "subject":
                        subject = header["value"]
                        break

                # Combine subject and snippet for rule matching
                email_content = subject + " " + message_detail.get("snippet", "")

                matched = False
                for rule in self.rules:
                    if rule["Word"] in email_content:
                        # Retrieve the label ID for the target folder
                        label_id = self.get_label_id(rule["Folder"])
                        if label_id:
                            # self.service.users().messages().modify(
                            #     userId="me",
                            #     id=msg["id"],
                            #     body={
                            #         "removeLabelIds": ["INBOX"],
                            #         "addLabelIds": [label_id]
                            #     }
                            # ).execute()
                            print(f"Moved message {msg['id']} to folder '{rule['Folder']}' because it contains '{rule['Word']}'.")
                            matched = True
                            break
                        else:
                            print(f"Label '{rule['Folder']}' not found for message {msg['id']}.")
                if not matched:
                    # If no rule matches, trash the email
                    # self.service.users().messages().trash(userId="me", id=msg["id"]).execute()
                    print(f"Trashed message {msg['id']} as no rules matched.")
            except Exception as e:
                print(f"An error occurred processing message {msg['id']}: {e}")


bm = benjamail()
bm.process_old_emails(1)
#print(bm.search_messages("hi"))
