import logging
import os
import re
import imapclient
import email
from bs4 import BeautifulSoup
import requests
from owncloud import Client, HTTPResponseError
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


# Set your email and Nextcloud credentials
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
NEXTCLOUD_URL = os.environ.get("NEXTCLOUD_URL")
NEXTCLOUD_USERNAME = os.environ.get("NEXTCLOUD_USERNAME")
NEXTCLOUD_PASSWORD = os.environ.get("NEXTCLOUD_PASSWORD")
NEXTCLOUD_PATH = os.environ.get("NEXTCLOUD_PATH")

def get_pdf_link(email_body):
    soup = BeautifulSoup(email_body, "html.parser")
    links = [link.get("href") for link in soup.find_all("a")]
    pdf_links = [link for link in links if re.search(r"\.pdf$", link)]
    return pdf_links[1] if len(pdf_links) >= 2 else None

def get_pdf_link_plain_text(email_body):
    links = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', email_body)
    # pdf_links = [link for link in links if link.endswith('.pdf')]
    return links[2] if len(links) >= 2 else None

def move_email_to_folder_and_mark_as_read(imap, email_id, folder_name):
    imap.add_flags(email_id, [imapclient.SEEN])  # Mark as read
    imap.copy(email_id, folder_name)  # Copy email to the specified folder
    imap.delete_messages(email_id)  # Delete the original email from the current folder
    imap.expunge()  # Permanently remove the deleted email


def main():
    # Configure the logging settings
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                        )

    # Connect to the email account
    imap = imapclient.IMAPClient("imap.mail.me.com", ssl=True)
    imap.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

    # Search for emails from the specified recipient
    imap.select_folder("INBOX", readonly=True)
    messages = imap.search(["TO", "pottery.fatales_0o@icloud.com"])



    if messages:
        for current_message in messages:
            # Fetch the latest email
            response = imap.fetch(messages, ["BODY[]"])
            raw_email = response[current_message][b"BODY[]"]
            message = email.message_from_bytes(raw_email)

            # Find the second PDF link
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    email_body = part.get_payload(decode=True).decode('utf-8')
                    pdf_link = get_pdf_link_plain_text(email_body)
                    if pdf_link:
                        # Download the PDF
                        pdf_response = requests.get(pdf_link)
                        if pdf_response.status_code == 200:
                            # file_name = pdf_link.split("/")[-1]
                            file_name = datetime.today().strftime("%Y-%m-%d_%H:%M:%S")+".pdf"
                            current_year = datetime.now().strftime("%Y")
                            current_month = datetime.now().strftime("%m")

                            # Save the PDF to your Nextcloud instance
                            nextcloud = Client(NEXTCLOUD_URL)
                            nextcloud.login(NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD)
                            file_path = f"{NEXTCLOUD_PATH}/{current_year}/{current_month}/{file_name}"
                            try:
                                nc_result = nextcloud.put_file_contents(
                                    file_path,
                                    pdf_response.content,
                                )
                            except HTTPResponseError:
                                print(HTTPResponseError)
                            else:
                                if nc_result:
                                    logging.info(f"Saved PDF '{file_name}' to Nextcloud")
                                    # Move email to the "mpla" folder and mark as read
                                    imap.select_folder("INBOX", readonly=False)  # Change to read-write mode
                                    move_email_to_folder_and_mark_as_read(imap, current_message, "mpla")
                                    logging.info(f"Moved email to the 'mpla' folder and marked it as read")
                                else:
                                    logging.error(f"The PDF '{file_name}' was not saved to Nextcloud.")
                                break
                    else:
                        logging.info("No second PDF link found in the email")
    else:
        logging.info("No emails found from the specified recipient")

    imap.logout()

if __name__ == "__main__":
    main()