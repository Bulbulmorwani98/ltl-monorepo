import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
# SMTP Configuration
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

subject = "Email from LongtailLeopard"
def send_email(body, email=None, subject=subject):
    try:
        # Create the email message
        recevier_email =  RECIPIENT_EMAIL if not email else email
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = recevier_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        # Connect to the SMTP server
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure the connection
            server.login(SENDER_EMAIL, SENDER_PASSWORD)  # Login with credentials
            server.sendmail(SENDER_EMAIL, recevier_email, msg.as_string())  # Send email
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error: {e}")