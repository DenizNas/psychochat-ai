import smtplib
from email.mime.text import MIMEText
import logging
from src.core.config import settings

logger = logging.getLogger(__name__)

def send_reset_email(email: str, code: str) -> bool:
    subject = "PsikoChat Şifre Sıfırlama"
    body = f"Kodunuz: {code}\nBu kod 10 dakika geçerlidir."
    
    # Check if SMTP is configured
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        if settings.APP_ENV == "development":
            logger.info(f"SMTP not configured. [DEV ONLY] Logged Email to {email}:\nSubject: {subject}\nBody:\n{body}")
            print(f"\n[EMAIL MOCK] To: {email}\nSubject: {subject}\n{body}\n")
            return True
        else:
            logger.error(f"SMTP credentials missing in {settings.APP_ENV.upper()} environment! Cannot send reset email.")
            return False
            
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = email
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, [email], msg.as_string())
            
        if settings.APP_ENV == "development":
            logger.info(f"Reset email successfully sent to {email}. Code: {code}")
        else:
            logger.info(f"Reset email successfully sent to {email}.")
        return True
    except Exception as e:
        if settings.APP_ENV == "development":
            logger.error(f"Failed to send email to {email}: {e}")
        else:
            logger.error(f"Failed to send email to {email}")
        return False
