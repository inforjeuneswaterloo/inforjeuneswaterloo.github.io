import os
import json
import pdfkit # Assurez-vous que pdfkit est installé: pip install pdfkit
from datetime import datetime
import traceback # Pour les traces d'erreurs

# --- Configuration ---
# Chemin du fichier JSON temporaire créé par jobs.py
JOBS_DATA_FILE = os.path.join("scripts", "temp_jobs_for_pdf.json")
# Dossier de sortie pour le PDF
PDF_OUTPUT_DIR = os.path.join("assets", "downloads", "jobs", "archives") 
PDF_FILENAME = f"offres_emploi_du_jour_{datetime.now().strftime('%Y-%m-%d')}.pdf"
PDF_FULL_PATH = os.path.join(PDF_OUTPUT_DIR, PDF_FILENAME)

# --- Fonction de génération de PDF ---
def generate_pdf_from_jobs(jobs_data, pdf_output_path):
    """
    Génère un PDF à partir d'une liste de dictionnaires de données de jobs.
    Le contenu est d'abord formaté en HTML.
    """
    if not jobs_data:
        print("Aucune donnée de job fournie pour la génération du PDF.")
        return False

    # Créer le contenu HTML pour le PDF
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Offres d'emploi du {datetime.now().strftime('%d/%m/%Y')}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; text-align: center; }}
            .job-offer {{ border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; border-radius: 8px; }}
            .job-offer h2 {{ color: #007bff; margin-top: 0; font-size: 1.5em; }}
            .job-offer p {{ margin-bottom: 5px; }}
            .job-offer a {{ color: #007bff; text-decoration: none; }}
            .job-offer a:hover {{ text-decoration: underline; }}
            .footer {{ text-align: center; margin-top: 40px; font-size: 0.8em; color: #777; }}
        </style>
    </head>
    <body>
        <h1>Offres d'emploi du jour - {datetime.now().strftime('%d %B %Y')}</h1>
    """

    for job in jobs_data:
        title = job.get('title', 'Titre non disponible')
        description = job.get('description', 'Description non disponible')
        url_article_reference = job.get('url_article_reference')
        mastodon_url = job.get('mastodon_url')
        
        # Prioriser l'URL de l'article de référence, sinon le lien Mastodon
        primary_link = url_article_reference if url_article_reference else mastodon_url

        html_content += f"""
        <div class="job-offer">
            <h2>{title}</h2>
            <p>{description}</p>
            {"<p><a href='" + primary_link + "'>Consulter l'offre</a></p>" if primary_link else ""}
        </div>
        """
    
    html_content += f"""
        <div class="footer">
            Généré automatiquement le {datetime.now().strftime('%d/%m/%Y à %H:%M')}.
            Pour plus d'offres, visitez notre site web.
        </div>
    </body>
    </html>
    """

    # Créer le dossier de sortie si non existant (recursivement pour les sous-dossiers)
    os.makedirs(os.path.dirname(pdf_output_path), exist_ok=True)

    try:
        # pdfkit nécessite wkhtmltopdf. Assurez-vous qu'il est installé sur le runner.
        pdfkit.from_string(html_content, pdf_output_path)
        print(f"PDF généré avec succès: {pdf_output_path}")
        return True
    except Exception as e:
        print(f"Erreur lors de la génération du PDF: {e}")
        print("Veuillez vous assurer que 'wkhtmltopdf' est installé et accessible par pdfkit.")
        traceback.print_exc()
        return False

# --- Exécution principale ---
if __name__ == "__main__":
    # Charger les données des jobs
    if not os.path.exists(JOBS_DATA_FILE):
        print(f"Erreur: Fichier de données des jobs introuvable: {JOBS_DATA_FILE}. Impossible de générer le PDF.")
        exit(1) # Sortie avec erreur si le fichier source n'est pas là
    
    with open(JOBS_DATA_FILE, "r", encoding="utf-8") as f:
        jobs_data = json.load(f)

    if not jobs_data:
        print("Aucune offre d'emploi du jour à traiter pour le PDF. Pas de PDF généré.")
        exit(0) # Sortie normale si pas de jobs

    # Générer le PDF
    pdf_generated = generate_pdf_from_jobs(jobs_data, PDF_FULL_PATH)

    if not pdf_generated:
        print("La génération du PDF a échoué.")
        exit(1) # Sortie avec erreur si la génération échoue