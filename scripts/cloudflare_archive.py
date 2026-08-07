import os
import requests
import csv
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr

# --- 1. CONFIGURATION VIA LES SECRETS GITHUB ---
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
SITE_TAG = "ed61bfd330604cadb9d0f0449087df59"  # Votre token de site Web Analytics

GMAIL_USER = "marc.griffon@inforjeuneswaterloo.be"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")  # Mot de passe d'application Google
RECIPIENT_EMAIL = "marc.griffon@inforjeuneswaterloo.be"

# --- 2. RÉCUPÉRATION DES DONNÉES CLOUDFLARE ---
end_date = datetime.utcnow().date()
start_date = end_date - timedelta(days=90)

url = "https://api.cloudflare.com/client/v4/graphql"

headers = {
    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
    "Content-Type": "application/json"
}

query = """
query GetAnalytics($accountTag: string!, $siteTag: string!, $datetimeStart: string!, $datetimeEnd: string!) {
  viewer {
    accounts(filter: {accountTag: $accountTag}) {
      rumPageloadEventsAdaptiveGroups(
        limit: 1000,
        filter: {
          siteTag: $siteTag,
          datetime_geq: $datetimeStart,
          datetime_leq: $datetimeEnd
        },
        orderBy: [datetimePeriod_ASC]
      ) {
        dimensions {
          datetimePeriod: date
        }
        count
      }
    }
  }
}
"""

variables = {
    "accountTag": ACCOUNT_ID,
    "siteTag": SITE_TAG,
    "datetimeStart": f"{start_date}T00:00:00Z",
    "datetimeEnd": f"{end_date}T23:59:59Z"
}

response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
data = response.json()

output_filename = f"cloudflare_stats_{start_date}_au_{end_date}.csv"

try:
    records = data["data"]["viewer"]["accounts"][0]["rumPageloadEventsAdaptiveGroups"]
    
    with open(output_filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Date", "Pages Vues / Visites"])
        for row in records:
            writer.writerow([row["dimensions"]["datetimePeriod"], row["count"]])
            
    print(f"✅ Fichier CSV généré avec succès : {output_filename}")

except Exception as e:
    print("❌ Erreur lors de la récupération des données Cloudflare :", e)
    print(data)
    exit(1)

# --- 3. ENVOI DE L'E-MAIL VIA GMAIL SMTP ---
try:
    msg = MIMEMultipart()
    msg['From'] = formataddr(("Robot Stats Infor Jeunes", GMAIL_USER))
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = f"Archives Statistiques Cloudflare - Trimestre du {start_date} au {end_date}"

    body = f"Bonjour Marc,\n\nVoici le fichier CSV d'archivage des statistiques Cloudflare pour la période du {start_date} au {end_date}.\n\nCe message est généré automatiquement par GitHub Actions."
    msg.attach(MIMEText(body, 'plain'))

    with open(output_filename, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename= {output_filename}")
        msg.attach(part)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())

    print("✅ E-mail envoyé avec succès à", RECIPIENT_EMAIL)

except Exception as e:
    print("❌ Erreur lors de l'envoi de l'e-mail :", e)