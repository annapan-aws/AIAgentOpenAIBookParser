from openai import OpenAI
import json
import os
import re
from pathlib import Path
from docx import Document
from throttle import exponential_backoff  # your backoff function
import tiktoken

from dotenv import load_dotenv
load_dotenv()




# === CONFIGURATION ===
OPENAI_MODEL = "gpt-4.1-mini"  # or "gpt-4-turbo"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PROMPT_FILE = "prompt.txt"
DOCUMENT_FILE = "input_document.docx"
OUTPUT_DIR = "categorized_output"

# Token limits
MAX_TOTAL_TOKENS = 8192
RESERVED_TOKENS_FOR_RESPONSE = 1000
MAX_INPUT_TOKENS = MAX_TOTAL_TOKENS - RESERVED_TOKENS_FOR_RESPONSE

# === SETUP ===
os.makedirs(OUTPUT_DIR, exist_ok=True)
client = OpenAI(api_key=OPENAI_API_KEY)
# Fallback encoder for unsupported model names
def get_token_encoder(model: str):
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        print(f"⚠️ WARNING: Model '{model}' not recognized by tiktoken. Using 'cl100k_base' encoder as fallback.")
        return tiktoken.get_encoding("cl100k_base")

encoding = get_token_encoder(OPENAI_MODEL)

def num_tokens(text):
    return len(encoding.encode(text))

# === LOAD PROMPT TEXT ===
with open(PROMPT_FILE, "r", encoding="utf-8") as f:
    base_prompt = f.read()

# === LOAD AND EXTRACT TEXT FROM .DOCX FILE ===
def read_docx(filepath):
    doc = Document(filepath)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)

full_document = read_docx(DOCUMENT_FILE)

# === TOKEN-AWARE PARAGRAPH-BASED CHUNKING ===
paragraphs = full_document.split("\n\n")
chunks = []
current_chunk = ""
current_tokens = 0

for para in paragraphs:
    para = para.strip()
    if not para:
        continue

    para_tokens = num_tokens(para) + 2  # for spacing
    if current_tokens + para_tokens <= MAX_INPUT_TOKENS:
        current_chunk += para + "\n\n"
        current_tokens += para_tokens
    else:
        if current_chunk:
            chunks.append(current_chunk.strip())
        current_chunk = para + "\n\n"
        current_tokens = para_tokens

if current_chunk.strip():
    chunks.append(current_chunk.strip())

# === PROCESS CHUNKS ===
for i, chunk in enumerate(chunks):
    print(f"\n🔹 Processing chunk {i + 1} of {len(chunks)}...")
    input_text = f"{base_prompt}\n\nDocument Chunk:\n{chunk}"

    messages = [
        {"role": "system", "content": "You are an assistant that categorizes and extracts structured information from text."},
        {"role": "user", "content": input_text}
    ]

    try:
        response = exponential_backoff(
            lambda: client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=0.3,
                top_p=0.95,
                max_tokens=RESERVED_TOKENS_FOR_RESPONSE
            )
        )
        model_output = response.choices[0].message.content
    except Exception as e:
        print(f"❌ ERROR: OpenAI call failed. Reason: {e}")
        exit(1)

    print(model_output)

    # === CATEGORY OUTPUT PARSING ===
    section_pattern = r'\[(\d+)\]\s*\n+(.*?)(?=\[\d+\]|$)'
    sections = re.findall(section_pattern, model_output, re.DOTALL)

    for number, content in sections:
        if not content.strip():
            continue

        section_file = Path(OUTPUT_DIR) / f"{number}.txt"
        with open(section_file, "a", encoding="utf-8") as f:
            f.write(f"\n\n--- From chunk {i + 1} ---\n{content.strip()}\n")
            print(f"✅ Section {number}: {content[:50]}...")

print(f"\n✅ All {len(chunks)} chunks processed.\nCategorized text written to .txt files in `{OUTPUT_DIR}`")
