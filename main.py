#%%
import sys, os, re, base64, pickle, csv, pandas as pd, numpy as np, utils
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
                 openai_key="openai_key.txt", project_key="project_key.txt", organization_key="organization_key.txt",
                 openai_instructions_file="instructions.txt"):
        self.credentials_file = f"{keys_folder}/{credentials_file}"
        self.token_file = f"{keys_folder}/{token_file}"
        self.api_key = f"{keys_folder}/{openai_key}"
        self.project_key = f"{keys_folder}/{project_key}"
        self.organization_key = f"{keys_folder}/{organization_key}"
        self.openai_instructions_file = openai_instructions_file
        self.authenticate_gmail()
        self.authenticate_openai()


    def authenticate_gmail(self):
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
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
            with open(self.token_file, "w") as token_to_write:
                token_to_write.write(creds.to_json())
        
        self.service = build("gmail", "v1", credentials=creds)
        return

    def authenticate_openai(self):
        # Initiate OpenAI API
        self.client = OpenAI(
            organization=open(self.organization_key, "r").read(),
            project=open(self.project_key, "r").read(),
            api_key = open(self.api_key, "r").read()
        )
        # Removes pre-existing assistants
        my_assistants = self.client.beta.assistants.list(
            order="desc",
            limit="100",
        )
        for assistant in my_assistants:
            print(assistant.id)
            self.client.beta.assistants.delete(assistant.id)
        
        # Create a new assistant
        self.assistant = self.client.beta.assistants.create(
            instructions=open(self.openai_instructions_file, "r").read(),
            name="Email Category Sorter",
            model="gpt-4o-mini",
        )

        # Create a new thread
        self.thread = self.client.beta.threads.create()

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
            result = self.service.users().messages().list(userId='me',q=query,pageToken=page_token).execute()
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

    def get_older_emails(self, older_than_days=7, batch_size=20):
        # Search for emails in the inbox newer than {older_than_days} days.
        query = f"in:inbox newer_than:{older_than_days}d"
        messages = self.search_messages(query=query)

        if not messages:
            print(f"No emails newer than {older_than_days} days found.")
            return

        string_batch_list = []  # This will hold the big string for each batch.
        string_in_batch = ""    # Accumulates email content for the current batch.
        count = 0             # Counter for messages in the current batch.

        print(len(messages), "messages found.")

        for msg in messages:
            try:
                # Retrieve full message details
                message_detail = self.service.users().messages().get(
                    userId="me", id=msg["id"], format="full"
                ).execute()

                # Extract headers for subject and sender.
                email_content = utils.get_email_content(message_detail)

                # Append the email content to the current batch.
                string_in_batch += email_content
                count += 1

                # When we've reached the batch size, add the giant string to the list.
                if count % batch_size == 0:
                    string_batch_list.append(string_in_batch)
                    string_in_batch = ""  # Reset for the next batch.

            except Exception as e:
                print(f"An error occurred processing message {msg['id']}: {e}")

        # If there are leftover messages that didn't fill a full batch, add them as well.
        if string_in_batch:
            string_batch_list.append(string_in_batch)

        self.string_list = string_batch_list
    
    def prompt_openai(self, message):
        message = self.client.beta.threads.messages.create(
            thread_id = self.thread.id,
            role = "user",
            content = message
        )
        run = self.client.beta.threads.runs.create_and_poll(
            thread_id=self.thread.id,
            assistant_id=self.assistant.id
        )
        if run.status == "completed":
            messages = self.client.beta.threads.messages.list(thread_id=self.thread.id)
            first_message = messages[0]
            assert first_message.content[0].type == "text"
            response = first_message.content[0].text.value
            return response
        else:
            raise Exception(f"Assistant run did not complete successfully. Status: {run.status}")
        
    def manage_emails(self):
        # Get string_list
        self.get_older_emails()

        # Iterate through the string_list
        for string in self.string_list:
            response = self.prompt_openai(string)
            print(response)


bm = benjamail()

#print(bm.search_messages("hi"))

# for rule in self.rules:
#     if rule["Word"] in email_content:
#         # Retrieve the label ID for the target folder
#         label_id = self.get_label_id(rule["Folder"])
#         if label_id:
#             # self.service.users().messages().modify(
#             #     userId="me",
#             #     id=msg["id"],
#             #     body={
#             #         "removeLabelIds": ["INBOX"],
#             #         "addLabelIds": [label_id]
#             #     }
#             # ).execute()
#             print(f"Moved message {msg['id']} to folder '{rule['Folder']}' because it contains '{rule['Word']}'.")
#             matched = True
#             break
#         else:
