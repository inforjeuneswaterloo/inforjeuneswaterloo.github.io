
import csv
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import requests

# --- 1. CONFIGURATION VIA LES SECRETS GITHUB ---
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")

# Site Tokens (siteTag Web Analytics)
SITES = {
    "yotm.be": "198bc079bff743349fa771a55c17edcf",
    "inforjeuneswaterloo.be": "d06fa83df0464be08a5d32825cf99f2b",
}

GMAIL_USER = os.environ.get("GMAIL_USER", "marc.griffon@inforjeuneswaterloo.be")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECIPIENT_EMAIL = os.environ.get(
    "RECIPIENT_EMAIL", "marc.griffon@inforjeuneswaterloo.be"
)

# Vérification des secrets indispensables
missing_vars = [
    var_name
    for var_name, var_val in [
        ("CLOUDFLARE_API_TOKEN", CLOUDFLARE_API_TOKEN),
        ("CLOUDFLARE_ACCOUNT_ID", ACCOUNT_ID),
        ("GMAIL_APP_PASSWORD", GMAIL_APP_PASSWORD),
    ]
    if not var_val
]

if missing_vars:
    print(
        f"❌ Erreur : Variables d'environnement manquantes :"
        f" {', '.join(missing_vars)}"
    )
    exit(1)

# --- 2. RÉCUPÉRATION ET COMPILATION DES DONNÉES CLOUDFLARE (30 jours) ---
end_date = datetime.now(timezone.utc).date()
start_date = end_date - timedelta(days=30)

str_start_date = start_date.strftime("%Y-%m-%d")
str_end_date = end_date.strftime("%Y-%m-%d")

url = "https://api.cloudflare.com/client/v4/graphql"

headers = {
    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
    "Content-Type": "application/json",
}

# Requete GraphQL Web Analytics avec dimensions date
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
        orderBy: [date_ASC]
      ) {
        dimensions {
          date
        }
        count
      }
    }
  }
}
"""

output_filename = f"cloudflare_stats_mensuel_{str_start_date}_au_{str_end_date}.csv"

try:
    with open(output_filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Date", "Site", "Pages Vues / Visites"])

        for site_name, site_tag in SITES.items():
            print(f"🔄 Récupération des données pour {site_name}...")

            variables = {
                "accountTag": ACCOUNT_ID,
                "siteTag": site_tag,
                "datetimeStart": f"{str_start_date}T00:00:00Z",
                "datetimeEnd": f"{str_end_date}T23:59:59Z",
            }

            response = requests.post(
                url,
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            if "errors" in data and data["errors"]:
                print(f"⚠️ Erreur API pour {site_name} : {data['errors']}")
                continue

            accounts = data.get("data", {}).get("viewer", {}).get("accounts", [])
            if not accounts:
                print(f"⚠️ Aucune donnée retournée pour {site_name}.")
                continue

            records = accounts[0].get("rumPageloadEventsAdaptiveGroups", [])

            for row in records:
                # Lecture de la dimension date ou datetimePeriod
                date_val = row["dimensions"].get("date") or row["dimensions"].get("datetimePeriod")
                writer.writerow([
                    date_val,
                    site_name,
                    row["count"],
                ])

            print(f"  └─ {len(records)} entrées ajoutées pour {site_name}")

    print(f"✅ Fichier CSV unique généré avec succès : {output_filename}")

except Exception as e:
    print("❌ Erreur lors de la récupération des données Cloudflare :", e)
    exit(1)

# --- 3. ENVOI DE L'E-MAIL VIA GMAIL SMTP ---
try:
    msg = MIMEMultipart()
    msg["From"] = formataddr(("Robot Stats Infor Jeunes", GMAIL_USER))
    msg["To"] = RECIPIENT_EMAIL
    
    msg["Subject"] = (
        f"Archives Statistiques Cloudflare - Rapport Mensuel du {str_start_date} au {str_end_date}"
    )

    body = (
        f"Bonjour Marc,\n\n"
        f"Voici le fichier CSV d'archivage des statistiques Cloudflare pour le rapport mensuel du {str_start_date} au {str_end_date}.\n\n"
        f"Le fichier comprend les données récapitulatives des sites suivants :\n"
        + "\n".join([f"- {site}" for site in SITES.keys()])
        + "\n\nCe message est généré automatiquement par GitHub Actions."
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with open(output_filename, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition", f'attachment; filename="{output_filename}"'
        )
        msg.attach(part)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())

    print("✅ E-mail envoyé avec succès à", RECIPIENT_EMAIL)

except Exception as e:
    print("❌ Erreur lors de l'envoi de l'e-mail :", e)
    exit(1)