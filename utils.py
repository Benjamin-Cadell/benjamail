

def get_email_content(message_detail):
    """ Extracts email content from a message detail object. """
    headers = message_detail.get("payload", {}).get("headers", [])
    subject = ""
    sender = ""
    for header in headers:
        header_name = header["name"].lower()
        if header_name == "subject":
            subject = header["value"]
        elif header_name == "from":
            sender = header["value"]

    # Combine sender, subject, and snippet for rule matching.
    email_content = (
        f"[NEXT MESSAGE] Sender: {sender}, Subject: {subject}, "
        f"Message: {message_detail.get('snippet', '')} [END MESSAGE]"
    )
    return email_content
