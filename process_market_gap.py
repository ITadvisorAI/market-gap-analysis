import os
import traceback
import requests
from docx import Document
from pptx import Presentation
from pptx.util import Inches
from datetime import datetime

PUBLIC_URL_BASE = "https://market-gap-analysis.onrender.com/files"

TEMPLATES = {
    "docx": "templates/GAP_Market_Template.docx",
    "pptx": "templates/GAP_Market_Template.pptx"
}

def download_file(url, dest_path):
    try:
        print(f"⬇️ Downloading: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            f.write(response.content)
        print(f"✅ Downloaded to: {dest_path}")
    except Exception as e:
        print(f"❌ Download failed for {url}: {e}")
        traceback.print_exc()

def fill_word_template(doc_path, output_path, replacements):
    try:
        doc = Document(doc_path)
        for paragraph in doc.paragraphs:
            for key, val in replacements.items():
                if key in paragraph.text:
                    paragraph.text = paragraph.text.replace(key, val)
        doc.save(output_path)
        print(f"✅ Word report saved: {output_path}")
    except Exception as e:
        print(f"❌ Word generation error: {e}")
        traceback.print_exc()

def fill_ppt_template(ppt_path, output_path, replacements):
    try:
        prs = Presentation(ppt_path)
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for key, val in replacements.items():
                        if key in shape.text:
                            shape.text = shape.text.replace(key, val)
        prs.save(output_path)
        print(f"✅ PowerPoint report saved: {output_path}")
    except Exception as e:
        print(f"❌ PPTX generation error: {e}")
        traceback.print_exc()

def run_market_gap_analysis(session_id, email, files, session_folder):
    try:
        print(f"🚀 Running GAP analysis for: {session_id}")
        os.makedirs(session_folder, exist_ok=True)

        # === Download files from GPT2
        for f in files:
            local_path = os.path.join(session_folder, f['file_name'])
            download_file(f['file_url'], local_path)

        # === Define output paths
        word_output = os.path.join(session_folder, "GAP_Market_Report.docx")
        pptx_output = os.path.join(session_folder, "GAP_Market_Summary.pptx")
        folder_name = os.path.basename(session_folder)

        # === Mock replacements (to be enhanced later)
        replacements = {
            "<<SESSION_ID>>": session_id,
            "<<EMAIL>>": email,
            "<<DATE>>": datetime.now().strftime("%Y-%m-%d"),
            "<<SUMMARY>>": "Obsolete hardware detected across Tier 1 workloads.",
            "<<RECOMMENDATIONS>>": "Migrate to hybrid cloud with zero-trust architecture.",
        }

        # === Fill Templates
        fill_word_template(TEMPLATES["docx"], word_output, replacements)
        fill_ppt_template(TEMPLATES["pptx"], pptx_output, replacements)

        # === Public URLs
        def public_url(file_path):
            return f"{PUBLIC_URL_BASE}/{folder_name}/{os.path.basename(file_path)}"

        file_links = {
            "GAP_Market_Report.docx": public_url(word_output),
            "GAP_Market_Summary.pptx": public_url(pptx_output)
        }

        print("✅ Market GAP analysis complete. Generated files:")
        for name, link in file_links.items():
            print(f"• {name}: {link}")

        # Optionally: POST results to next GPT module

    except Exception as e:
        print(f"💥 Unhandled exception in market GAP analysis: {e}")
        traceback.print_exc()
