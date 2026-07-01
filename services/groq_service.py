import json
from groq import Groq

class GroqService:
    @staticmethod
    def generate_questions(subject, topic_description, num_questions, difficulty_level, api_key):
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
Target difficulty level of all generated questions: {difficulty_level}

You MUST return a JSON object with a single key "questions" containing a list of question objects.
Each question object must match this schema:
{{
  "question": "The text of the question?",
  "option_a": "First option description",
  "option_b": "Second option description",
  "option_c": "Third option description",
  "option_d": "Fourth option description",
  "correct_answer": "A",
  "difficulty": "{difficulty_level}"
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
                model="llama-3.1-8b-instant",
                temperature=0.7,
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
                    "difficulty": item.get("difficulty", difficulty_level).lower(),
                    "subject": subject
                })
                
            if not sanitized:
                return None, f"Zero valid questions could be parsed from response. Raw response: {response_content[:200]}"
                
            return sanitized, None
            
        except json.JSONDecodeError as e:
            return None, f"Failed to parse JSON response from LLM: {str(e)}. Raw output: {response_content[:300]}"
        except Exception as e:
            return None, f"GROQ API Request error: {str(e)}"
