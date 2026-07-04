import json
from groq import Groq

class GroqService:
    @staticmethod
    def generate_questions(subject, topic_description, num_questions, api_key):
        """
        Sends requests to the GROQ API to generate multiple-choice questions in a structured format.
        Ensures response is valid JSON and parses it.
        """
        if not api_key:
            return None, "GROQ API Key is missing. Please configure it in your settings or .env file."
        
        client = Groq(api_key=api_key)
        
        prompt = f"""
Generate {num_questions} multiple-choice questions (MCQs) for the subject "{subject}".
Topic/Syllabus description: {topic_description}

You MUST return a JSON object with a single key "questions" containing a list of question objects.
Each question object must match this schema:
{{
  "question": "The text of the question?",
  "option_a": "First option description",
  "option_b": "Second option description",
  "option_c": "Third option description",
  "option_d": "Fourth option description",
  "correct_answer": "A"
}}

Ensure that "correct_answer" is exactly one uppercase character: A, B, C, or D.
Do not include any intro, outtro, markdown backticks, or explanation. Only return valid raw JSON.
"""

        try:
            # Call GROQ API with json_object format to enforce parsing compliance
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional educational exam author. You generate strict JSON outputs containing list of questions. You never include introductory text, markdown formatting like ```json, or comments."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=8000,
                response_format={"type": "json_object"}
            )
            
            response_content = chat_completion.choices[0].message.content.strip()
            
            # Basic fallback cleanup of markdown wrappers in case model misbehaved
            if response_content.startswith("```json"):
                response_content = response_content[7:]
            if response_content.endswith("```"):
                response_content = response_content[:-3]
            response_content = response_content.strip()
            
            # Parse response
            data = json.loads(response_content)
            
            if not isinstance(data, dict) or "questions" not in data:
                return None, "Response is not in the correct JSON format (missing 'questions' key)."
                
            questions_list = data["questions"]
            if not isinstance(questions_list, list):
                return None, "JSON 'questions' field must be a list."
                
            # Sanitize and validate fields
            sanitized = []
            for idx, item in enumerate(questions_list):
                required = ["question", "option_a", "option_b", "option_c", "option_d", "correct_answer"]
                if not all(k in item for k in required):
                    continue
                
                correct = str(item["correct_answer"]).strip().upper()
                if correct not in ["A", "B", "C", "D"]:
                    correct = "A" # safe fallback
                    
                sanitized.append({
                    "question": item["question"],
                    "option_a": item["option_a"],
                    "option_b": item["option_b"],
                    "option_c": item["option_c"],
                    "option_d": item["option_d"],
                    "correct_answer": correct,
                    "subject": subject
                })
                
            if not sanitized:
                return None, f"Zero valid questions could be parsed from response. Raw response: {response_content[:200]}"
                
            return sanitized, None
            
        except json.JSONDecodeError as e:
            return None, f"Failed to parse JSON response from LLM: {str(e)}. Raw output: {response_content[:300]}"
        except Exception as e:
            return None, f"GROQ API Request error: {str(e)}"

    @staticmethod
    def extract_questions_from_text(pdf_text, subject, api_key):
        """
        Sends requests to the GROQ API to parse a text of questions and options,
        and output structured JSON questions.
        """
        if not api_key:
            return None, "GROQ API Key is missing. Please configure it in your settings or .env file."
        
        client = Groq(api_key=api_key)
        
        prompt = f"""
Analyze the following text extracted from a PDF document. Find and extract all multiple-choice questions (MCQs) contained within it.
For each question, identify:
1. The question text.
2. The options (Option A, Option B, Option C, Option D). If there are fewer than 4 options in the text, you must fill in logical options or leave placeholder descriptions, but exactly four options (A, B, C, D) are required.
3. The correct answer (A, B, C, or D). If the correct answer is indicated in the text (e.g. bolded, asterisked, annotated, or in an answer key at the end of the text), extract it. If it is not explicitly marked, try to solve the question and determine the correct option. If it cannot be determined, default to A.
4. The subject of the question. Use the default subject '{subject}' (or override it if a more specific subject is clear from the text).

You MUST return a JSON object with a single key "questions" containing a list of question objects.
Each question object must match this schema:
{{
  "question": "The text of the question?",
  "option_a": "First option description",
  "option_b": "Second option description",
  "option_c": "Third option description",
  "option_d": "Fourth option description",
  "correct_answer": "A",
  "subject": "subject_name"
}}

Ensure that "correct_answer" is exactly one uppercase character: A, B, C, or D.
Do not include any intro, outtro, markdown backticks, or explanation. Only return valid raw JSON.

Here is the extracted text:
---
{pdf_text}
---
"""

        try:
            # Call GROQ API with json_object format to enforce parsing compliance
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional educational exam extractor. You extract multiple-choice questions from text and format them in a strict JSON array. You never include introductory text, markdown formatting like ```json, or comments."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.3, # low temperature for high extraction fidelity
                max_tokens=8000,
                response_format={"type": "json_object"}
            )
            
            response_content = chat_completion.choices[0].message.content.strip()
            
            # Basic fallback cleanup of markdown wrappers in case model misbehaved
            if response_content.startswith("```json"):
                response_content = response_content[7:]
            if response_content.endswith("```"):
                response_content = response_content[:-3]
            response_content = response_content.strip()
            
            # Parse response
            data = json.loads(response_content)
            
            if not isinstance(data, dict) or "questions" not in data:
                return None, "Response is not in the correct JSON format (missing 'questions' key)."
                
            questions_list = data["questions"]
            if not isinstance(questions_list, list):
                return None, "JSON 'questions' field must be a list."
                
            # Sanitize and validate fields
            sanitized = []
            for idx, item in enumerate(questions_list):
                required = ["question", "option_a", "option_b", "option_c", "option_d", "correct_answer"]
                if not all(k in item for k in required):
                    continue
                
                correct = str(item["correct_answer"]).strip().upper()
                if correct not in ["A", "B", "C", "D"]:
                    correct = "A" # safe fallback
                    
                sub = item.get("subject", subject).strip()
                if not sub:
                    sub = subject
                    
                sanitized.append({
                    "question": item["question"],
                    "option_a": item["option_a"],
                    "option_b": item["option_b"],
                    "option_c": item["option_c"],
                    "option_d": item["option_d"],
                    "correct_answer": correct,
                    "subject": sub
                })
                
            if not sanitized:
                return None, f"Zero valid questions could be parsed from response. Raw response: {response_content[:200]}"
                
            return sanitized, None
            
        except json.JSONDecodeError as e:
            return None, f"Failed to parse JSON response from LLM: {str(e)}. Raw output: {response_content[:300]}"
        except Exception as e:
            return None, f"GROQ API Request error: {str(e)}"
