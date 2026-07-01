from models import db, Question

class QuestionService:
    @staticmethod
    def get_question_by_id(question_id):
        """Retrieves a single question by ID."""
        return Question.query.get(question_id)

    @staticmethod
    def get_all_questions(difficulty=None, subject=None):
        """Retrieves all questions from the database, filtered optionally by difficulty and subject."""
        query = Question.query
        if difficulty:
            query = query.filter_by(difficulty_level=difficulty)
        if subject:
            query = query.filter(Question.subject.ilike(f"%{subject}%"))
        return query.order_by(Question.created_at.desc()).all()

    @staticmethod
    def get_all_subjects():
        """Returns list of distinct subjects present in the question bank."""
        subjects = db.session.query(Question.subject).distinct().all()
        return [s[0] for s in subjects if s[0]]

    @staticmethod
    def create_question(question_text, option_a, option_b, option_c, option_d, correct_answer, difficulty_level, subject, creator_id):
        """Creates a single question in the question bank."""
        new_question = Question(
            question_text=question_text,
            option_a=option_a,
            option_b=option_b,
            option_c=option_c,
            option_d=option_d,
            correct_answer=correct_answer.upper(),
            difficulty_level=difficulty_level.lower(),
            subject=subject.strip(),
            created_by=creator_id
        )
        try:
            db.session.add(new_question)
            db.session.commit()
            return new_question, None
        except Exception as e:
            db.session.rollback()
            return None, f"Error saving question: {str(e)}"

    @staticmethod
    def update_question(question_id, question_text, option_a, option_b, option_c, option_d, correct_answer, difficulty_level, subject):
        """Updates an existing question."""
        question = Question.query.get(question_id)
        if not question:
            return None, "Question not found."
        
        question.question_text = question_text
        question.option_a = option_a
        question.option_b = option_b
        question.option_c = option_c
        question.option_d = option_d
        question.correct_answer = correct_answer.upper()
        question.difficulty_level = difficulty_level.lower()
        question.subject = subject.strip()

        try:
            db.session.commit()
            return question, None
        except Exception as e:
            db.session.rollback()
            return None, f"Error updating question: {str(e)}"

    @staticmethod
    def delete_question(question_id):
        """Deletes a question by ID."""
        question = Question.query.get(question_id)
        if not question:
            return False, "Question not found."
        try:
            db.session.delete(question)
            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, f"Error deleting question: {str(e)}"

    @staticmethod
    def bulk_insert_questions(questions_list, creator_id):
        """Inserts a list of dictionary questions directly into the database."""
        inserted_count = 0
        errors = []
        for q_data in questions_list:
            question = Question(
                question_text=q_data.get('question'),
                option_a=q_data.get('option_a'),
                option_b=q_data.get('option_b'),
                option_c=q_data.get('option_c'),
                option_d=q_data.get('option_d'),
                correct_answer=q_data.get('correct_answer').upper(),
                difficulty_level=q_data.get('difficulty', 'medium').lower(),
                subject=q_data.get('subject', 'General').strip(),
                created_by=creator_id
            )
            db.session.add(question)
            inserted_count += 1
            
        try:
            db.session.commit()
            return inserted_count, None
        except Exception as e:
            db.session.rollback()
            return 0, f"Error during bulk import: {str(e)}"
