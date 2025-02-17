import logging
import azure.functions as func
from azure.storage.blob import BlobServiceClient
import fitz  # PyMuPDF for PDF handling
from pytesseract import image_to_string
from pdf2image import convert_from_path
import os
import requests
import json
import base64
import msal  # For Azure AD authentication
import openai

# Azure Blob Storage Configuration
AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=missingbillrates2;AccountKey=fnIDqTb5GFlH8P+BR3WKauqILGtxcS5jYpOZ/VxgxkuVYKL1xSoDk34Ko17uoJI1xdjt1g/ghpZz+ASta34CZg==;EndpointSuffix=core.windows.net"

# Explicit container names
NOTIFICATION_CONTAINER = "notifications"
CIRCULAR_CONTAINER = "circulars"

# OpenAI GPT Configuration
endpoint = "https://insightgen.openai.azure.com/"
deployment = "gpt-4o-mini"
api_version = "2024-02-15-preview"
api_key = "54de899334ca4850b3f71da993dd0346"

openai.api_type = "azure"
openai.api_key = api_key
openai.api_base = endpoint
openai.api_version = api_version

# Azure AD App credentials
CLIENT_ID = "ec4a61d1-d4a6-4a22-a4e2-25e20ef97891"
TENANT_ID = "7571a489-bd29-4f38-b9a6-7c880f8cddf0"
TOKEN_FILE = "token.json"

# Azure Function App Initialization
app = func.FunctionApp()

# @app.event_grid_trigger(arg_name="azeventgrid")
# def ProcessBlobEvent(azeventgrid: func.EventGridEvent):
#     logging.info("Python EventGrid trigger processed an event: %s", azeventgrid.get_json())

#     # Parse the Event Grid event data
#     event_data = azeventgrid.get_json()
#     blob_url = event_data.get("data", {}).get("url")
#     blob_name = blob_url.split("/")[-1]

#     # Manually check for container names
#     if NOTIFICATION_CONTAINER in event_data.get("subject", ""):
#         container_name = NOTIFICATION_CONTAINER
#     elif CIRCULAR_CONTAINER in event_data.get("subject", ""):
#         container_name = CIRCULAR_CONTAINER
#     else:
#         logging.error("Unknown container name in event data.")
#         return

#     # Temporary download path
#     download_path = f"/tmp/{blob_name}"

#     try:
#         # Step 1: Download the blob
#         download_blob(container_name, blob_name, download_path)

#         # Step 2: Extract text from the PDF
#         extracted_text = extract_text_from_pdf(download_path)

#         # Step 3: Generate a summary using GPT
#         summary = summarize_text(extracted_text, blob_name)
#         logging.info(f"Generated summary for {blob_name}: {summary}")

#         # Step 4: Send an email with the summary
#         tokens = refresh_access_token(CLIENT_ID, TENANT_ID)
#         access_token = tokens["access_token"]
#         recipient_emails = ["recipient@example.com"]
#         cc_emails = ["cc@example.com"]
#         subject = f"Summary for {blob_name}"
#         body = f"<p>Please find the summary for <b>{blob_name}</b> below:</p><p>{summary}</p>"
#         send_email(access_token, recipient_emails, cc_emails, subject, body, download_path)

#         logging.info("Email sent successfully.")
#     except Exception as e:
#         logging.error(f"Error processing blob {blob_name}: {e}")
#     finally:
#         if os.path.exists(download_path):
#             os.remove(download_path)



##Everything is working fine 21/01/2025
@app.event_grid_trigger(arg_name="azeventgrid")
def ProcessBlobEvent(azeventgrid: func.EventGridEvent):
    logging.info("Python EventGrid trigger processed an event: %s", azeventgrid.get_json())
    #logging.info("EventGrid trigger received an event.")

    # Parse the Event Grid event data
    event_data = azeventgrid.get_json()
    blob_url = event_data.get("data", {}).get("url")
    #blob_url = event_data.get("data", {}).get("url", "")
    blob_name = blob_url.split("/")[-1]

    # Manually check for container names
    if NOTIFICATION_CONTAINER in event_data.get("subject", ""):
        container_name = NOTIFICATION_CONTAINER
    elif CIRCULAR_CONTAINER in event_data.get("subject", ""):
        container_name = CIRCULAR_CONTAINER
    else:
        logging.error("Unknown container name in event data.")
        return

    # Temporary download path
    download_path = f"/tmp/{blob_name}"

    # try:
    #     # Step 1: Download the blob
    #     download_blob(container_name, blob_name, download_path)

    #     # Step 2: Extract text from the PDF
    #     extracted_text = extract_text_from_pdf(download_path)

    #     # Step 3: Generate a summary using GPT
    #     summary = summarize_text(extracted_text, blob_name)
    #     logging.info(f"Generated summary for {blob_name}: {summary}")

    #     # Step 4: Send an email with the summary
    #     tokens = refresh_access_token(CLIENT_ID, TENANT_ID)
    #     access_token = tokens["access_token"]
    #     recipient_emails = ["jagadeesh.bn@sonata-software.com"]
    #     cc_emails = ["jagadeesh.bn@sonata-software.com"]
    #     subject = f"Summary for {blob_name}"
    #     body = f"<p>Please find the summary for <b>{blob_name}</b> below:</p><p>{summary}</p>"
    #     send_email(access_token, recipient_emails, cc_emails, subject, body, download_path)

    #     logging.info("Email sent successfully.")
    # except Exception as e:
    #     logging.error(f"Error processing blob {blob_name}: {e}")
    # finally:
    #     if os.path.exists(download_path):
    #         os.remove(download_path)
    
    # Ensure the temporary directory exists
    os.makedirs(os.path.dirname(download_path), exist_ok=True)
    
    try:
        # Step 1: Download the blob
        logging.info(f"Attempting to download blob {blob_name} from container {container_name}")
        download_blob(container_name, blob_name, download_path)
        logging.info(f"Downloaded blob {blob_name} successfully.")

        # Step 2: Extract text from the PDF
        logging.info(f"Attempting to extract text from blob {blob_name}")
        extracted_text = extract_text_from_pdf(download_path)
        logging.info(f"Text extraction successful for blob {blob_name}")

        # Step 3: Generate a summary using GPT
        logging.info(f"Attempting to summarize text for blob {blob_name}")
        summary = summarize_text(extracted_text, blob_name)
        logging.info(f"Generated summary for blob {blob_name}: {summary}")

        try:
            logging.info(f"Attempting to send email for blob {blob_name}")
            tokens = refresh_access_token(CLIENT_ID, TENANT_ID)
            logging.info(f"Access Token: {tokens['access_token']}")
        except Exception as e:
            logging.error(f"Failed to refresh access token: {str(e)}")
        
        
        # # Step 4: Send an email with the summary
        # logging.info(f"Attempting to send email for blob {blob_name}")
        # tokens = refresh_access_token(CLIENT_ID, TENANT_ID)
        # logging.info(f"Access Token: {tokens['access_token']}")
        access_token = tokens["access_token"]
        recipient_emails = ["jagadeesh.bn@sonata-software.com"]
        cc_emails = ["jagadeesh.bn@sonata-software.com"]
        subject = f"Summary for {blob_name}"
        body = f"<p>Please find the summary for <b>{blob_name}</b> below:</p><p>{summary}</p>"
        send_email(access_token, recipient_emails, cc_emails, subject, body, download_path)
        logging.info(f"Email sent successfully for blob {blob_name}")
    except Exception as e:
        logging.error(f"Error processing blob {blob_name}: {str(e)}")
    finally:
        if os.path.exists(download_path):
            os.remove(download_path)



# @app.event_grid_trigger(arg_name="azeventgrid")
# def ProcessBlobEvent(azeventgrid: func.EventGridEvent):
#     logging.info("Python EventGrid trigger processed an event: %s", azeventgrid.get_json())

#     # Parse the Event Grid event data
#     event_data = azeventgrid.get_json()
#     blob_url = event_data.get("data", {}).get("url")
#     container_name = blob_url.split("/")[-2]  # Extract container name from URL
#     blob_name = blob_url.split("/")[-1]      # Extract blob name from URL

#     logging.info(f"Detected blob creation: {blob_name} in container: {container_name}")

#     # Temporary download path
#     download_path = f"/tmp/{blob_name}"

#     try:
#         # Step 1: Download the blob
#         download_blob(container_name, blob_name, download_path)

#         # Step 2: Process the blob (e.g., extract text, summarize, send email)
#         extracted_text = extract_text_from_pdf(download_path)
#         summary = summarize_text(extracted_text, blob_name)

#         # Send email with summary
#         tokens = refresh_access_token(CLIENT_ID, TENANT_ID)
#         access_token = tokens["access_token"]
#         send_email(
#             access_token,
#             recipient_emails=["jagadeesh.bn@sonata-software.com"],
#             cc_emails=["jagadeesh.bn@sonata-software.com"],
#             subject=f"Summary for {blob_name}",
#             body=f"<p>Summary for <b>{blob_name}</b>:</p><p>{summary}</p>",
#             attachment=download_path
#         )

#         logging.info("Blob processing completed successfully.")
#     except Exception as e:
#         logging.error(f"Error processing blob: {e}")
#     finally:
#         if os.path.exists(download_path):
#             os.remove(download_path)



# Function to download a blob locally
def download_blob(container_name, blob_name, download_path):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

        with open(download_path, "wb") as file:
            file.write(blob_client.download_blob().readall())

        logging.info(f"Downloaded {blob_name} to {download_path}")
        return download_path
    except Exception as e:
        logging.error(f"Error downloading blob {blob_name}: {e}")
        return None

# Function to extract text from PDF
def extract_text_from_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = "".join([page.get_text() for page in doc])
        return text.strip() if text.strip() else perform_ocr(pdf_path)
    except Exception as e:
        logging.error(f"Error extracting text from PDF {pdf_path}: {e}")
        return f"Error extracting text: {e}"

# Function to perform OCR on a PDF if no text is found
def perform_ocr(pdf_path):
    try:
        images = convert_from_path(pdf_path)
        return "".join([image_to_string(image, lang="eng+hin") for image in images]).strip()
    except Exception as e:
        logging.error(f"Error performing OCR on {pdf_path}: {e}")
        return f"Error performing OCR: {e}"

# Function to summarize text using GPT-4o-mini
def summarize_text(text, title):
    try:
        response = openai.ChatCompletion.create(
            engine=deployment,
            messages=[
                {"role": "system", "content": "You are a helpful assistant summarizing text from government circulars."},
                {"role": "user", "content": f"The AI identifies and extracts critical information, including compliance deadlines, tax rate changes, and jurisdiction-specific details. It generates clear, concise, and actionable summaries that highlight key points for efficient decision-making:\n\n{text}"}
            ],
            max_tokens=500,  # 4096 max tokens for GPT-4o-mini
            temperature=0.7
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"Error summarizing text: {e}")
        return f"Error summarizing text: {e}"

# Function to refresh the access token using `token.json`
def refresh_access_token(client_id, tenant_id):
    if not os.path.exists(TOKEN_FILE):
        raise Exception("No token file found. Please authenticate interactively first.")

    with open(TOKEN_FILE, "r") as token_file:
        tokens = json.load(token_file)

    if "refresh_token" not in tokens:
        raise Exception("Refresh token not found. Please authenticate interactively again.")

    authority_url = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.PublicClientApplication(client_id, authority=authority_url)

    result = app.acquire_token_by_refresh_token(tokens["refresh_token"], scopes=["Mail.Send"])

    if "access_token" in result:
        with open(TOKEN_FILE, "w") as token_file:
            json.dump(result, token_file)
        logging.info("Access token refreshed successfully.")
        return result
    else:
        raise Exception(f"Failed to refresh access token: {result}")

# Function to send an email with the summary
def send_email(access_token, recipient_emails, cc_emails, subject, body, attachment):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    to_recipients = [{"emailAddress": {"address": email}} for email in recipient_emails]
    cc_recipients = [{"emailAddress": {"address": email}} for email in cc_emails]

    email_message = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body
            },
            "toRecipients": to_recipients,
            "ccRecipients": cc_recipients,
            "attachments": []
        }
    }

    if attachment:
        try:
            with open(attachment, "rb") as file:
                content_bytes = base64.b64encode(file.read()).decode("utf-8")
                email_message["message"]["attachments"].append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": os.path.basename(attachment),
                    "contentBytes": content_bytes
                })
        except Exception as e:
            logging.error(f"Error attaching file {attachment}: {e}")
            raise

    response = requests.post(
        "https://graph.microsoft.com/v1.0/me/sendMail",
        headers=headers,
        json=email_message
    )

    if response.status_code == 202:
        logging.info("Email sent successfully!")
    else:
        logging.error(f"Failed to send email. Status: {response.status_code}, Response: {response.text}")
        raise Exception("Failed to send email.")
