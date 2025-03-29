#%%
import sys, os, re, csv, pandas as pd, numpy as np, utils, time, json
from tqdm import tqdm
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from openai import OpenAI
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

class benjamail:

    def __init__(self, keys_folder="Keys", credentials_file="credentials.json", token_file="token.json",
                 openai_key="openai_key.txt", project_key="project_key.txt", organization_key="organization_key.txt",
                 openai_instructions_file="instructions.txt", labels_file="labels.txt", examples_file="examples.txt",
                 openrouter_key="openrouter_key.txt", verbose=True):
        
        self.credentials_file         = f"{keys_folder}/{credentials_file}"
        self.token_file               = f"{keys_folder}/{token_file}"
        self.api_key                  = f"{keys_folder}/{openai_key}"
        self.project_key              = f"{keys_folder}/{project_key}"
        self.organization_key         = f"{keys_folder}/{organization_key}"
        self.openrouter_key           = f"{keys_folder}/{openrouter_key}"
        self.openai_instructions_file = openai_instructions_file
        self.labels_string            = open(labels_file, "r").read()
        self.examples_string          = open(examples_file, "r").read()
        self.verbose                  = verbose
        self.openai_models            = ["gpt-4o-mini", "o1-mini", "o3-mini"]
        self.openrouter_models        = ["deepseek/deepseek-r1:free"]
        self.assistant                = False
        # self.assistant_models = ["gpt-4o-mini", "o3-mini"] # Assistant models must be in self.openai_models
        self.authenticate_gmail()

    def authenticate_gmail(self):
        SCOPES = ["https://mail.google.com/"]
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        creds = None
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

    def authenticate_client(self, model):
        # Initiate OpenAI API based on model
        if model in self.openai_models:
            self.client = OpenAI(
                organization=open(self.organization_key, "r").read(),
                project=open(self.project_key, "r").read(),
                api_key = open(self.api_key, "r").read()
            )

            # Removes pre-existing assistants
            # my_assistants = self.client.beta.assistants.list(
            #     order="desc",
            #     limit="100",
            # )
            # try:
            #     for assistant in my_assistants:
            #         self.client.beta.assistants.delete(assistant.id)
            # except:
            #     pass  # This may look bad, but it's OpenAI's fault

        elif model in self.openrouter_models:
            self.client = OpenAI(
                base_url = "https://openrouter.ai/api/v1",
                api_key  = open(self.openrouter_key, "r").read()
            )
        else:
            raise Exception(f"Invalid model: {model}")

        # Read instructions from file
        with open(self.openai_instructions_file, "r") as f:
            instructions = f.read()
        formatted_instructions = instructions.format(labels=self.labels_string, examples=self.examples_string)
        self.formatted_instructions = formatted_instructions

        # Create a new assistant
        # if self.assistant:
        #     assistant = self.client.beta.assistants.create(
        #         instructions=formatted_instructions,
        #         name="Email Category Sorter",
        #         model=model,
        #     )

        #     # Create a new thread for the assisstant
        #     self.thread = self.client.beta.threads.create()

        #     self.client.beta.threads.messages.create(
        #         thread_id = self.thread.id,
        #         role = "developer",
        #         content = self.formatted_instructions
        #     )

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
        result = self.service.users().messages().list(userId='me', q=query, maxResults=self.max_emails).execute()
        messages = []
        if 'messages' in result:
            messages.extend(result['messages'])
        while 'nextPageToken' in result and len(messages) < self.max_emails:
            page_token = result['nextPageToken']
            result = self.service.users().messages().list(userId='me', q=query, pageToken=page_token,
                                                          maxResults=self.max_emails).execute()
            if 'messages' in result:
                messages.extend(result['messages'])

        if self.verbose:
            iterable = tqdm(messages, desc="Removing starred messages")
        else:
            iterable = messages
        filtered_messages = []
        for msg in iterable:
            message = self.service.users().messages().get(userId="me", id=msg["id"], format="metadata", metadataHeaders=["labels"]).execute()
            # If the message is not starred, add it to the filtered list
            if "STARRED" not in message.get("labelIds", []):
                filtered_messages.append(msg)

        if self.max_emails > len(filtered_messages):
            self.max_emails = len(filtered_messages)

        self.messages = filtered_messages[:self.max_emails]
        self.nmessages = len(self.messages)

    def get_label_id(self, label_name):
        """Returns the label ID for a given label name."""
        results = self.service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])
        for label in labels:
            if label["name"].lower() == label_name.lower():
                return label["id"]
        raise Exception(f"{label_name} doesnt exist")

    def move_messages(self, test):
        
        if len(self.messages) != len(self.full_responses):
            print(self.full_responses)
            raise Exception(f"Messages and results length do not match\n"
                            f"Msgs: {len(self.messages)}\nResults: {len(self.full_responses)}")

        if not test:
            log_add = ""
            for i, msg in enumerate(self.messages):

                # Special case for bin
                if self.full_responses[i] == "Bin":
                    self.service.users().messages().trash(userId="me", id=msg["id"]).execute()

                else:
                    # Get label id for gmail API
                    label_id = self.get_label_id(self.full_responses[i])
                    
                    # Move the message to correct folder
                    self.service.users().messages().modify(
                        userId="me",
                        id=msg["id"],
                        body={
                            "removeLabelIds": ["INBOX"],
                            "addLabelIds": [label_id]
                        }
                    ).execute()
        else:
            log_add = "Tests/"

        # Log movements for potential later analysis
        df = {
            "AI Response": self.full_responses,
            "Content": self.string_list, 
        }
        df = pd.DataFrame(df)
        time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        df.to_csv(f"Logs/{log_add}log-{time}.csv", index=True)

    def get_emails(self, older_than_days, newer_than_days, nemails, batch_size):
        # Search for emails in the inbox newer than {older_than_days} days.
        if newer_than_days and older_than_days:
            if self.verbose:
                print("Both newer than and older than requests activated, overriding to newer than request.")
        if older_than_days:
            query = f"in:inbox older_than:{older_than_days}d"
        if newer_than_days:  # Newer that search request overrides older than request for safety
            query = f"in:inbox newer_than:{newer_than_days}d"
        if nemails:
            query = f"in:inbox"
            self.max_emails = nemails
        if older_than_days is None and newer_than_days is None and nemails is None:
            raise Exception("Input something to for a number of emails")

        # Get self.messages
        self.search_messages(query=query)

        if not self.messages:
            print(f"No emails found with query: {query}.")
            return

        string_batch_list = []  # This will hold the big string for each batch.
        string_in_batch = f""    # Accumulates email content for the current batch.
        count = 0             # Counter for messages in the current batch.
        string_list = []        # List of all email content strings, similar to string_batch_list, but only single messages.
        if self.verbose:
            print("Messages to be used:", len(self.messages))
        for i, msg in enumerate(self.messages):
            try:
                # Retrieve full message details
                message_detail = self.service.users().messages().get(
                    userId="me", id=msg["id"], format="full"
                ).execute()

                # Extract headers for subject and sender.
                email_content = utils.get_email_content(message_detail, i+1)

                # Append the email content to the current batch.
                string_in_batch += email_content
                string_list.append(email_content)

                count += 1

                # When we've reached the batch size, add the giant string to the list.
                if count % batch_size == 0:
                    string_batch_list.append(string_in_batch)
                    string_in_batch = ""  # Reset for the next batch.

            except Exception as e:
                raise Exception(f"An error occurred processing message {msg['id']}: {e}")

        # If there are leftover messages that didn't fill a full batch, add them as well.
        if string_in_batch:
            string_batch_list.append(string_in_batch)

        self.batch_string_list = string_batch_list
        self.string_list = string_list
        self.nbatches = len(self.batch_string_list)

    def prompt_openai(self, message):
        # if self.assistant:
        #     thread_message = self.client.beta.threads.messages.create(
        #         thread_id = self.thread.id,
        #         role = "user",
        #         content = message
        #     )
        #     run = self.client.beta.threads.runs.create_and_poll(
        #         thread_id=self.thread.id,
        #         assistant_id=self.assistant.id
        #     )
        #     if run.status == "completed":
        #         messages = self.client.beta.threads.messages.list(thread_id=self.thread.id)
        #         first_message = messages.data[0]
        #         assert first_message.content[0].type == "text"
        #         response = first_message.content[0].text.value
        #         return response
        #     else:
        #         raise Exception(f"Assistant run did not complete successfully. Status: {run.status}")
        # else:
        if self.model == "deepseek/deepseek-r1:free":
            kwargs = {"temperature": 0.05}
        if self.model == "o3-mini":
            kwargs = dict(
                reasoning = {"effort": "low"},
                text = {
                    "format": {
                        "type": "json_schema",
                        "name": "folder_results",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "folders": {
                                    "type": "array",
                                    "items": {
                                        "type": "string"}
                                },
                            },
                            "required": ["folders"],
                            "additionalProperties": False  # So that it cant create extra keys
                        },
                        "strict": True
                    }
                },
            )

        response = self.client.responses.create(
            model = self.model,
            input = message,
            instructions = self.formatted_instructions,
            **kwargs,
        )
        folder_results = json.loads(response.output_text)["folders"]
        return folder_results

    def sort_emails(self, older_than_days=None, newer_than_days=None, nemails=None, batch_size=30, test=False, model="o3-mini",
                    max_emails=100, run_client=True):

        if model == "deepseek":
            model = "deepseek/deepseek-r1:free"

        # Authenticate AI client
        if model not in self.openai_models and model not in self.openrouter_models:
            raise Exception(f"Invalid model: {model}")
        # if model in self.assistant_models:
        #     self.assistant = True
        # else:
        #     self.assistant = False
        self.max_emails = max_emails
        self.model = model
        self.authenticate_client(model)

        # Get string_list and batch_string_list
        self.get_emails(older_than_days, newer_than_days, nemails, batch_size)

        if self.verbose:
                print(f"nmessages: {self.nmessages}")
                print(f"Max emails: {self.max_emails}")
                print(f"nbatches: {self.nbatches}")


        if run_client:
            # Iterate through the batch_string_list
            self.full_responses = []
            for string in tqdm(self.batch_string_list):
                response = self.prompt_openai(string)
                self.full_responses += response
            # Move emails based off labels
            self.move_messages(test)

if __name__ == "__main__":
    bm = benjamail(verbose=True)
    bm.sort_emails(
        # older_than_days = 14,
        # newer_than_days = 1,
        nemails         = 20,
        test            = False,
        run_client      = True,
        max_emails      = 3,
        batch_size      = 20,
    )


#%%

for string in bm.string_list:
    print(string)

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
