import os
import glob
import PyPDF2
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configuration - Get API key from environment
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
PDF_FOLDER = "uploads"

# Ensure uploads folder exists
os.makedirs(PDF_FOLDER, exist_ok=True)

print(f"Starting PDF Chatbot...")
print(f"API Key exists: {bool(OPENROUTER_API_KEY)}")
if OPENROUTER_API_KEY:
    print(f"API Key starts with: {OPENROUTER_API_KEY[:15]}...")

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
    
    print(f"Found {len(pdf_files)} PDF files")
    
    for pdf_file in pdf_files:
        print(f"Processing: {os.path.basename(pdf_file)}")
        text = extract_text_from_pdf(pdf_file)
        if text:
            all_text += f"\n\n[Document: {os.path.basename(pdf_file)}]\n{text}\n"
    
    print(f"Total extracted text length: {len(all_text)} characters")
    return all_text.strip()
def query_gemma(question, context):
    """Query Google's Gemma 3 4B model - FIXED VERSION"""
    
    if not OPENROUTER_API_KEY:
        return "Error: OpenRouter API key not configured."
    
    print(f"\n=== GEMMA 3 4B QUERY ===")
    print(f"Question: {question}")
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://tahc-ok.onrender.com",
        "X-Title": "PDF Chatbot"
    }
    
    # Use Google Gemma 3 4B
    model = "google/gemma-3-4b-it:free"
    
    # SIMPLE PROMPT without system message
    # Put all instructions in the user message
    prompt = f"""You are a helpful assistant that answers questions about PDF documents.

PDF CONTENT:
{context[:2500]}

QUESTION: {question}

INSTRUCTIONS:
1. Answer based ONLY on the PDF content above
2. If the answer cannot be found in the PDF, say: "I cannot find this information in the documents"
3. Be concise and accurate
4. Do not make up information

ANSWER BASED ON PDF:"""
    
    # CHANGE TO:
    data = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}  # ONLY user message
        ],
            "temperature": 0.3,
            "max_tokens": 300
    }
    
    try:
        print(f"Calling {model}...")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
            print(f"Success! Answer length: {len(answer)} chars")
            return answer
        else:
            print(f"Error {response.status_code}: {response.text[:200]}")
            # Try even simpler prompt
            return try_simple_prompt(question, context)
            
    except Exception as e:
        print(f"Request failed: {e}")
        return f"Connection error: {str(e)}"

def try_simple_prompt(question, context):
    """Try with ultra-simple prompt"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Ultra simple prompt
    prompt = f"Based on: {context[:1500]}\n\nQuestion: {question}\nAnswer:"
    
    data = {
        "model": "google/gemma-3-4b-it:free",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 200
    }
    
    try:
        print("Trying ultra-simple prompt...")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            # Try a different model that allows system messages
            return try_mistral_model(question, context)
            
    except:
        return "AI service temporarily unavailable."

def try_mistral_model(question, context):
    """Try Mistral model which allows system messages"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"Context: {context[:1500]}\n\nQuestion: {question}\nAnswer:"
    
    data = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [
            {"role": "system", "content": "You answer questions about PDF documents."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 200
    }
    
    try:
        print("Trying Mistral 7B model...")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            return f"I found your PDFs but encountered an error with the AI service. Please try a different question."
            
    except:
        return "Service error. Please try again."
        


@app.route('/')
def home():
    """Render main page"""
    pdf_count = len(get_all_pdfs())
    return render_template('index.html', pdf_count=pdf_count)

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
        
        # Get answer from Gemma model
        answer = query_gemma(question, pdf_context)
        
        return jsonify({
            "answer": answer,
            "pdf_count": len(get_all_pdfs()),
            "success": True,
            "model": "google/gemma-3-4b-it:free"
        })
        
    except Exception as e:
        print(f"Error in ask_question: {e}")
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/check')
def check_status():
    """Check API and PDF status"""
    pdfs = get_all_pdfs()
    
    # Test OpenRouter API
    api_status = "Not configured"
    if OPENROUTER_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
            test_response = requests.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers=headers,
                timeout=10
            )
            api_status = f"Working ({test_response.status_code})" if test_response.status_code == 200 else f"Error ({test_response.status_code})"
        except Exception as e:
            api_status = f"Error: {str(e)}"
    
    return jsonify({
        "status": "running",
        "pdf_count": len(pdfs),
        "pdf_files": [os.path.basename(p) for p in pdfs],
        "api_key_configured": bool(OPENROUTER_API_KEY),
        "api_status": api_status,
        "timestamp": datetime.now().isoformat(),
        "model": "google/gemma-3-4b-it:free"
    })

@app.route('/api/pdfs')
def list_pdfs():
    """List all available PDFs"""
    pdfs = get_all_pdfs()
    return jsonify({
        "pdfs": [os.path.basename(p) for p in pdfs],
        "count": len(pdfs)
    })

@app.route('/api/test')
def test_api():
    """Test the OpenRouter API with Gemma 3"""
    if not OPENROUTER_API_KEY:
        return jsonify({"error": "API key not configured"})
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Test with Google Gemma 3 4B
    data = {
        "model": "google/gemma-3-4b-it:free",
        "messages": [{"role": "user", "content": "Say hello in one word"}],
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
            "response": response.json() if response.status_code == 200 else response.text[:200],
            "model": "google/gemma-3-4b-it:free"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n=== PDF CHATBOT STARTING ===")
    print(f"Port: {port}")
    print(f"PDF Folder: {PDF_FOLDER}")
    print(f"Found {len(get_all_pdfs())} PDF files")
    print(f"API Key: {'Configured' if OPENROUTER_API_KEY else 'NOT CONFIGURED'}")
    print(f"Model: google/gemma-3-4b-it:free")
    print(f"Server URL: http://localhost:{port}")
    print("=" * 30)
    
    app.run(host='0.0.0.0', port=port)