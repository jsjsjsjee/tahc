import os
import glob
import PyPDF2
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configuration
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', 'your-api-key-here')
PDF_FOLDER = "uploads"

# Ensure uploads folder exists
os.makedirs(PDF_FOLDER, exist_ok=True)

def get_all_pdfs():
    """Get all PDF files from uploads folder"""
    return glob.glob(os.path.join(PDF_FOLDER, "*.pdf"))

def extract_text_from_pdf(pdf_path):
    """Extract text from a single PDF file"""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
        return text.strip()
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return ""

def extract_all_pdf_text():
    """Extract text from all PDFs in uploads folder"""
    all_text = ""
    pdf_files = get_all_pdfs()
    
    for pdf_file in pdf_files:
        text = extract_text_from_pdf(pdf_file)
        if text:
            all_text += f"\n\n--- Document: {os.path.basename(pdf_file)} ---\n\n"
            all_text += text
    
    return all_text.strip()

def query_openrouter(question, context):
    """Query OpenRouter API with PDF context"""
    if not context:
        return "No PDF content found. Please add PDF files to the uploads folder."
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_message = f"""You are a helpful assistant that answers questions based ONLY on the provided PDF documents.

CONTEXT FROM PDFs:
{context}

IMPORTANT RULES:
1. Answer based ONLY on the information in the PDFs above
2. If the answer is not in the PDFs, say: "I cannot find this information in the documents"
3. Do not make up information
4. Keep answers clear and concise"""

    data = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": question}
        ],
        "temperature": 0.3,
        "max_tokens": 500
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"OpenRouter API error: {e}")
        return f"I apologize, but I encountered an error while processing your request. Please try again."

@app.route('/')
def home():
    """Render main page"""
    return render_template('index.html')

@app.route('/api/ask', methods=['POST'])
def ask_question():
    """Ask a question about PDFs"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({"error": "Question is required"}), 400
        
        # Extract text from all PDFs
        pdf_context = extract_all_pdf_text()
        
        if not pdf_context:
            return jsonify({
                "answer": "No PDFs found in uploads folder. Please add PDF files to the uploads directory.",
                "pdf_count": 0
            })
        
        # Get answer from OpenRouter
        answer = query_openrouter(question, pdf_context)
        
        return jsonify({
            "answer": answer,
            "pdf_count": len(get_all_pdfs())
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/pdfs')
def list_pdfs():
    """List all available PDFs"""
    pdfs = get_all_pdfs()
    return jsonify({
        "pdfs": [os.path.basename(p) for p in pdfs],
        "count": len(pdfs)
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)