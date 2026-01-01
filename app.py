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
    """Query OpenRouter with detailed debugging"""
    import requests
    
    # Get API key
    api_key = os.environ.get('OPENROUTER_API_KEY')
    
    print(f"=== DEBUG QUERY ===")
    print(f"Question: {question[:50]}...")
    print(f"Context length: {len(context)}")
    print(f"API Key exists: {bool(api_key)}")
    
    if not api_key:
        print("ERROR: No API key!")
        return "Error: No API key configured"
    
    print(f"API Key starts with: {api_key[:20]}")
    print(f"API Key length: {len(api_key)}")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://chatbot-ai-1jyr.onrender.com",
        "X-Title": "PDF Chatbot"
    }
    
    # Simple prompt
    prompt = f"Based on this: {context[:1000]}\n\nQuestion: {question}\nAnswer:"
    
    data = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200
    }
    
    try:
        print(f"Sending request to OpenRouter...")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response body: {response.text[:500]}")
        
        if response.status_code == 401:
            # Try to get more info
            try:
                error_data = response.json()
                print(f"Error details: {error_data}")
            except:
                pass
            
            return "Error 401: Unauthorized. The API key is invalid or expired."
        
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
        
    except requests.exceptions.RequestException as e:
        print(f"Request exception: {e}")
        return f"Network error: {str(e)}"
    except Exception as e:
        print(f"General exception: {e}")
        return f"Error: {str(e)}"

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

@app.route('/api/debug-env')
def debug_env():
    """Show all environment variables (hide values)"""
    env_vars = {}
    for key, value in os.environ.items():
        if 'key' in key.lower() or 'api' in key.lower() or 'secret' in key.lower():
            # Show first/last few chars of sensitive values
            if value:
                env_vars[key] = f"{value[:5]}...{value[-5:]}" if len(value) > 10 else "***"
            else:
                env_vars[key] = "EMPTY"
        else:
            env_vars[key] = "***"
    
    # Check PDFs
    pdfs = get_all_pdfs()
    
    return jsonify({
        "environment_variables": env_vars,
        "pdf_count": len(pdfs),
        "pdf_files": [os.path.basename(p) for p in pdfs],
        "app_running": True
    })

@app.route('/api/test-openrouter-simple')
def test_openrouter_simple():
    """Very simple OpenRouter test"""
    import requests
    
    # Get key from environment
    api_key = os.environ.get('OPENROUTER_API_KEY')
    
    if not api_key:
        return jsonify({"error": "No API key in environment"})
    
    # Print in logs
    print(f"Testing key: {api_key[:20]}...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Very simple request
    data = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [{"role": "user", "content": "Say hi"}],
        "max_tokens": 5
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        return jsonify({
            "status_code": response.status_code,
            "response_preview": response.text[:200],
            "headers_sent": {
                "authorization": f"Bearer {api_key[:10]}...",
                "content_type": "application/json"
            },
            "key_length": len(api_key),
            "key_starts_with": api_key[:10]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

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