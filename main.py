# Reference: https://openai.github.io/openai-agents-python/
# https://www.youtube.com/watch?v=zOFxHmjIhvY

def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()


import boto3
from botocore.exceptions import ClientError
import json
import os
import re

from pathlib import Path
from docx import Document
from throttle import exponential_backoff

# === CONFIGURATION ===
REGION = "us-east-1"
MODEL_ID = "meta.llama3-70b-instruct-v1:0"
PROMPT_FILE = "prompt.txt"
DOCUMENT_FILE = "input_document.docx"
OUTPUT_DIR = "categorized_output"
MAX_CHARS_PER_CHUNK = 8000  #20000

# === SETUP ===
os.makedirs(OUTPUT_DIR, exist_ok=True)
bedrock = boto3.client("bedrock-runtime", region_name=REGION)

# === LOAD PROMPT TEXT ===
with open(PROMPT_FILE, "r", encoding="utf-8") as f:
    base_prompt = f.read()

# === LOAD AND EXTRACT TEXT FROM .DOCX FILE ===
def read_docx(filepath):
    doc = Document(filepath)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)

full_document = read_docx(DOCUMENT_FILE)

# === CHUNK LOGIC (PARAGRAPH-BASED) ===
paragraphs = full_document.split("\n\n")
chunks = []
current_chunk = ""

for para in paragraphs:
    if len(current_chunk) + len(para) + 2 <= MAX_CHARS_PER_CHUNK:
        current_chunk += para + "\n\n"
    else:
        chunks.append(current_chunk.strip())
        current_chunk = para + "\n\n"
if current_chunk.strip():
    chunks.append(current_chunk.strip())

# === PROCESS CHUNKS ===
for i, chunk in enumerate(chunks):
    prompt = f"\n\nHuman:  {base_prompt}\n\nDocument Chunk:\n{chunk}\n\nAssistant:"

  
    # Embed the prompt in Llama 3's instruction format.
    # formatted_prompt = f"""
    # <|begin_of_text|><|start_header_id|>user<|end_header_id|>
    # {prompt}
    # <|eot_id|>
    # <|start_header_id|>assistant<|end_header_id|>
    # """

    formatted_prompt = prompt
    payload = {
        "prompt": formatted_prompt,
        "temperature": 0.3,
        "top_p": 0.95,
        "max_gen_len": 1000, #got 'Validation Error at 5000'
        
    }

    print(f"Processing chunk {i + 1} of {len(chunks)}...")
    # print({json.dumps(payload)})
    try:
        # response = bedrock.invoke_model(
        #     modelId=MODEL_ID,
        #     body=json.dumps(payload),
        #     contentType="application/json",
        #     accept="application/json"
        # )

        response = exponential_backoff(
            lambda: bedrock.invoke_model(
                modelId=MODEL_ID,
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json"
            )
        )

        result = json.loads(response["body"].read())
        model_output = result.get("generation", "")
    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke '{MODEL_ID}'. Reason: {e}.  {e.__traceback__}")
        exit(1)
    print(model_output)

# === CATEGORY OUTPUT PARSING ===
    # Find all sections that start with [NUMBER]
    section_pattern = r'\[(\d+)\]\s*\n+(.*?)(?=\[\d+\]|$)'
    sections = re.findall(section_pattern, model_output, re.DOTALL)
    
    for number, content in sections:
        if not content.strip():
            continue
            
        # Create a file named after the number
        section_file = Path(OUTPUT_DIR) / f"{number}.txt"
        with open(section_file, "a", encoding="utf-8") as f:
            f.write(f"\n\n--- From chunk {i + 1} ---\n{content.strip()}\n")
            print(f"Section {number}: {content[:50]}...")

print(f"\n✅ All {len(chunks)} chunks processed.\nCategorized text written to .txt files in `{OUTPUT_DIR}`")
