import os
import io
import json
import base64

import streamlit as st
from PIL import Image
from groq import Groq  # Groq Python SDK

# ─── Streamlit UI Setup ────────────────────────────────────────────────────────
st.set_page_config(page_title="CP Question Explainer", layout="wide")
st.title("🏆 Competitive Programming Explainer & Solver")
st.write(
    "Upload one or more screenshots of a competitive programming problem. "
    "I’ll send them directly to the Meta Llama 4 Maverick multimodal model and then generate:\n"
    "1. A concise problem explanation\n"
    "2. Fully commented Python3 solution code\n"
    "3. Example input/output with detailed flow"
)

# File uploader: allow multiple images
uploaded_files = st.file_uploader(
    "📸 Upload screenshot(s)", 
    type=["png", "jpg", "jpeg"], 
    accept_multiple_files=True
)

if uploaded_files:
    # Read all files into memory once
    images = []
    for file in uploaded_files:
        data = file.read()
        mime = getattr(file, 'type', None) or f"image/{file.name.split('.')[-1].lower()}"
        images.append({"data": data, "mime": mime, "name": file.name})

    # Preview screenshots
    st.subheader("Preview Screenshots")
    for img in images:
        image = Image.open(io.BytesIO(img["data"]))
        st.image(image, caption=img["name"], use_container_width=True)

    if st.button("🚀 Generate Explanation & Code"):
        # ─── Prepare images for multimodal input ─────────────────────────────
        image_inputs = []
        for img in images:
            b64 = base64.b64encode(img["data"]).decode("utf-8")
            uri = f"data:{img['mime']};base64,{b64}"
            image_inputs.append({
                "type": "image_url",
                "image_url": {"url": uri}
            })

        # ─── Groq Vision API Call ────────────────────────────────────────────
        groq_key = "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"
        if not groq_key:
            st.error("❌ Please set the GROQ_API_KEY environment variable.")
        else:
            client = Groq(api_key=groq_key)
            # Instruction for JSON output
            system_msg = '''
You are a helpful assistant that takes one or more images of a competitive programming problem statement and outputs valid JSON with these keys:
{
  "explanation": "Clear, concise explanation of the problem.",
  "code": "Fully commented Python3 code solving the problem.",
  "examples": [
    {
      "input": "Example input",
      "output": "Corresponding output",
      "flow": "Step-by-step explanation of how the code produces that output"
    }
  ]
}
Respond strictly in JSON format.
'''
            user_content = [
                {"type": "text", "text": (
                    "Please analyze the following competitive programming problem screenshot(s) and output the JSON schema as described."
                )}
            ] + image_inputs

            with st.spinner("Generating via Meta Llama 4 Maverick…"):
                try:
                    resp = client.chat.completions.create(
                        model="meta-llama/llama-4-maverick-17b-128e-instruct",
                        messages=[
                            {"role": "system", "content": system_msg},
                            {"role": "user",   "content": user_content},
                        ],
                        response_format={"type": "json_object"},
                    )
                    raw = resp.choices[0].message.content
                    result = json.loads(raw) if isinstance(raw, str) else raw

                    explanation = result.get("explanation", "")
                    code = result.get("code", "")
                    examples = result.get("examples", [])

                    # ─── Display Results ──────────────────────────────────────────────
                    st.markdown("### 📜 Problem Explanation")
                    st.write(explanation)

                    st.markdown("### 💻 Solution Code")
                    st.code(code, language="python")

                    st.markdown("### 🔍 Example I/O & Flow")
                    for i, ex in enumerate(examples, start=1):
                        st.markdown(f"*Example {i}:*")
                        st.markdown(f"- *Input:*{ex.get('input','')}")
                        st.markdown(f"- *Output:*{ex.get('output','')}")
                        st.markdown(f"- *Flow:* {ex.get('flow','')}" )

                except Exception as e:
                    st.error(f"Error from Groq API: {e}")