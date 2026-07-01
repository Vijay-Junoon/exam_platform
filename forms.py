from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, ValidationError

class RegistrationForm(FlaskForm):
    """Teacher registration form."""
    name = StringField('Full Name', validators=[
        DataRequired(),
        Length(min=2, max=100, message="Name must be between 2 and 100 characters.")
    ])
    email = StringField('Email Address', validators=[
        DataRequired(),
        Email(message="Invalid email address.")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message="Password must be at least 6 characters.")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match.')
    ])
    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    """User login form (both admin and teacher)."""
    email = StringField('Email Address', validators=[
        DataRequired(),
        Email(message="Invalid email address.")
    ])
    password = PasswordField('Password', validators=[
        DataRequired()
    ])
    submit = SubmitField('Log In')


class QuestionForm(FlaskForm):
    """Form to manually add or edit questions (Admin only)."""
    question_text = TextAreaField('Question Text', validators=[DataRequired()])
    option_a = StringField('Option A', validators=[DataRequired(), Length(max=255)])
    option_b = StringField('Option B', validators=[DataRequired(), Length(max=255)])
    option_c = StringField('Option C', validators=[DataRequired(), Length(max=255)])
    option_d = StringField('Option D', validators=[DataRequired(), Length(max=255)])
    correct_answer = SelectField('Correct Answer', choices=[
        ('A', 'Option A'),
        ('B', 'Option B'),
        ('C', 'Option C'),
        ('D', 'Option D')
    ], validators=[DataRequired()])
    difficulty_level = SelectField('Difficulty Level', choices=[
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('complex', 'Complex'),
        ('very_complex', 'Very Complex')
    ], validators=[DataRequired()])
    subject = StringField('Subject/Category', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Save Question')


class ExamConfigForm(FlaskForm):
    """Form to configure exam settings (Admin only)."""
    total_questions = IntegerField('Total Exam Questions', validators=[
        DataRequired(),
        NumberRange(min=1, max=200, message="Exam must contain between 1 and 200 questions.")
    ])
    very_complex_percentage = IntegerField('Very Complex %', validators=[
        NumberRange(min=0, max=100)
    ])
    complex_percentage = IntegerField('Complex %', validators=[
        NumberRange(min=0, max=100)
    ])
    medium_percentage = IntegerField('Medium %', validators=[
        NumberRange(min=0, max=100)
    ])
    easy_percentage = IntegerField('Easy %', validators=[
        NumberRange(min=0, max=100)
    ])
    exam_duration = IntegerField('Exam Duration (minutes)', validators=[
        DataRequired(),
        NumberRange(min=1, max=300, message="Exam must last between 1 and 300 minutes.")
    ])
    submit = SubmitField('Update Configuration')

    def validate(self, extra_validators=None):
        """Custom validator to check if difficulty percentages sum to 100%."""
        initial_validation = super(ExamConfigForm, self).validate(extra_validators=extra_validators)
        if not initial_validation:
            return False

        vc = self.very_complex_percentage.data or 0
        c = self.complex_percentage.data or 0
        m = self.medium_percentage.data or 0
        e = self.easy_percentage.data or 0

        if (vc + c + m + e) != 100:
            self.very_complex_percentage.errors.append('Percentages must sum to exactly 100%.')
            return False
        return True


class AIQuestionGenerationForm(FlaskForm):
    """Form to trigger GROQ AI question generator (Admin only)."""
    subject = StringField('Subject/Topic Name', validators=[DataRequired(), Length(max=100)])
    topic_description = TextAreaField('Syllabus/Topic Description')
    pdf_file = FileField('Upload Syllabus/Topic PDF (Optional)', validators=[
        FileAllowed(['pdf'], 'Only PDF documents are allowed.')
    ])
    num_questions = IntegerField('Number of Questions to Generate', validators=[
        DataRequired(),
        NumberRange(min=1, max=20, message="Generate between 1 and 20 questions per call.")
    ])
    difficulty_level = SelectField('Difficulty Level', choices=[
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('complex', 'Complex'),
        ('very_complex', 'Very Complex')
    ], validators=[DataRequired()])
    submit = SubmitField('Generate Questions')

    def validate(self, extra_validators=None):
        """Ensure either topic_description or pdf_file is provided."""
        initial_validation = super(AIQuestionGenerationForm, self).validate(extra_validators=extra_validators)
        if not initial_validation:
            return False

        has_text = bool(self.topic_description.data and self.topic_description.data.strip())
        has_file = bool(self.pdf_file.data)

        if not has_text and not has_file:
            self.topic_description.errors.append('Please provide either a written topic description or upload a PDF file.')
            return False

        if has_text and not has_file and len(self.topic_description.data.strip()) < 10:
            self.topic_description.errors.append('Topic description must be at least 10 characters long.')
            return False

        return True
