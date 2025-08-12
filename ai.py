import os
import httpx
import asyncio
import re

API_KEY = os.getenv("API_KEY")
MODEL = "z-ai/glm-4.5-air:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "HTTP-Referer": "https://t.me/eldocenglish",
    "Content-Type": "application/json"
}

def extract_answers(text, num_questions):
    pattern = re.compile(r"Answer\s*[:\-]?\s*([A-D])", re.IGNORECASE)
    answers = pattern.findall(text)
    if len(answers) != num_questions:
        print(f"Warning: Expected {num_questions} answers, but got {len(answers)}")
    return answers

def extract_questions(text, num_questions):
    questions = []
    q_pattern = re.compile(r"\d+\..*?(?:A\).+?B\).+?C\).+?D\).+?)(?=^\d+\.|\Z)", re.DOTALL | re.MULTILINE)
    found = q_pattern.findall(text)
    for q in found:
        questions.append(q.strip())
    if len(questions) != num_questions:
        print(f"Warning: Expected {num_questions} questions, but got {len(questions)}")
    return questions

async def generate_placement_passage(level):
    # فقرة تحديد مستوى: نص قصير + 5 أسئلة فقط
    return await generate_paragraph(level, word_limit=200, num_questions=5)

async def generate_training_passage(level):
    # فقرة تدريبية: نص أطول + 8 أسئلة
    return await generate_paragraph(level, word_limit=400, num_questions=8)

async def generate_paragraph(level, word_limit, num_questions):
    prompt = f"""
Write an educational English paragraph suitable for a student at the {level} level.
- The paragraph must contain **at least {word_limit} words**.
- After the paragraph, include **{num_questions} multiple choice questions** (MCQs).
- Some questions must be **inference-based** and **challenging**.
- Format the questions exactly like this:

1. Question text?
A) Option A
B) Option B
C) Option C
D) Option D
Answer: A

- Do **not** include any explanations or extra instructions.
- Return only the paragraph and questions in the format above.
"""

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            text = result['choices'][0]['message']['content']
            print("=== API Response ===")
            print(text)
            print("====================")
            print("Status Code:", response.status_code)
    except Exception as e:
        print(f"Error generating paragraph: {e}")
        return None

    paragraph_split = re.split(r"\n\s*1\.", text, maxsplit=1)
    paragraph = paragraph_split[0].strip()
    questions_text = "1." + paragraph_split[1] if len(paragraph_split) > 1 else ""

    questions = extract_questions(questions_text, num_questions)
    answers = extract_answers(questions_text, num_questions)

    if len(answers) != num_questions or len(questions) != num_questions:
        print("❌ مشكلة في استخراج الأسئلة أو الإجابات من النص.")
        return None

    return {
        "paragraph": paragraph,
        "questions": questions,
        "answers": answers
    }
