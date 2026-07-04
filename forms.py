from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, IntegerField, BooleanField, FloatField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, ValidationError, Optional

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
    subject = StringField('Subject/Category', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Save Question')


class ExamConfigForm(FlaskForm):
    """Form to configure exam settings (Admin only)."""
    total_questions = IntegerField('Total Exam Questions', validators=[
        DataRequired(),
        NumberRange(min=1, max=200, message="Exam must contain between 1 and 200 questions.")
    ])
    exam_duration = IntegerField('Exam Duration (minutes)', validators=[
        DataRequired(),
        NumberRange(min=1, max=300, message="Exam must last between 1 and 300 minutes.")
    ])
    pattern = SelectField('Exam Pattern', choices=[
        ('HR', 'HR Pattern (No negative marking)'),
        ('GATE', 'GATE Pattern (-1/3 negative marking)')
    ], validators=[DataRequired()])
    passing_marks = FloatField('Passing Marks', validators=[
        DataRequired(message="Please provide passing marks."),
        NumberRange(min=0.1, message="Passing marks must be greater than 0.")
    ])
    override_threshold = FloatField('Override Threshold', validators=[
        DataRequired(message="Please provide override threshold."),
        NumberRange(min=0.0, message="Threshold cannot be negative.")
    ])
    submit = SubmitField('Update Configuration')

    def validate_passing_marks(self, field):
        if self.total_questions.data is not None and field.data is not None:
            if field.data > self.total_questions.data:
                raise ValidationError("Passing marks cannot exceed total questions.")

    def validate_override_threshold(self, field):
        if self.passing_marks.data is not None and field.data is not None:
            if field.data > self.passing_marks.data:
                raise ValidationError("Override threshold cannot exceed passing marks.")


class AIQuestionGenerationForm(FlaskForm):
    """Form to trigger GROQ AI question generator (Admin only)."""
    subject = StringField('Subject/Topic Name', validators=[DataRequired(), Length(max=100)])
    topic_description = TextAreaField('Syllabus/Topic Description')
    pdf_file = FileField('Upload Syllabus/Topic PDF (Optional)', validators=[
        FileAllowed(['pdf'], 'Only PDF documents are allowed.')
    ])
    num_questions = IntegerField('Number of Questions to Generate', validators=[
        DataRequired(),
        NumberRange(min=1, max=40, message="Generate between 1 and 40 questions per call.")
    ])
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


class ExtractQuestionsPDFForm(FlaskForm):
    """Form to upload questions PDF and extract using GROQ AI (Admin only)."""
    pdf_file = FileField('Upload Questions PDF', validators=[
        FileRequired(message="Please select a PDF file to upload."),
        FileAllowed(['pdf'], 'Only PDF documents are allowed.')
    ])
    subject = StringField('Default Subject/Topic Name', validators=[
        DataRequired(),
        Length(max=100)
    ], default='General')
    submit = SubmitField('Extract & Import Questions')


class ExamForm(FlaskForm):
    """Form to create or edit examinations (Admin only)."""
    title = StringField('Exam Title', validators=[
        DataRequired(),
        Length(min=3, max=150, message="Title must be between 3 and 150 characters.")
    ])
    subject = SelectField('Subject/Category', choices=[], validators=[
        DataRequired(message="Please select a subject.")
    ])
    total_questions = IntegerField('Total Exam Questions', validators=[
        DataRequired(),
        NumberRange(min=1, max=200, message="Exam must contain between 1 and 200 questions.")
    ])
    exam_duration = IntegerField('Exam Duration (minutes)', validators=[
        DataRequired(),
        NumberRange(min=1, max=300, message="Exam must last between 1 and 300 minutes.")
    ])
    pattern = SelectField('Exam Pattern', choices=[
        ('HR', 'HR Pattern (No negative marking)'),
        ('GATE', 'GATE Pattern (-1/3 negative marking)')
    ], validators=[DataRequired()])
    passing_marks = FloatField('Passing Marks', validators=[
        DataRequired(message="Please provide passing marks."),
        NumberRange(min=0.1, message="Passing marks must be greater than 0.")
    ])
    override_threshold = FloatField('Override Threshold', validators=[
        DataRequired(message="Please provide override threshold."),
        NumberRange(min=0.0, message="Threshold cannot be negative.")
    ])
    submit = SubmitField('Save Exam')

    def validate_passing_marks(self, field):
        if self.total_questions.data is not None and field.data is not None:
            if field.data > self.total_questions.data:
                raise ValidationError("Passing marks cannot exceed total questions.")

    def validate_override_threshold(self, field):
        if self.passing_marks.data is not None and field.data is not None:
            if field.data > self.passing_marks.data:
                raise ValidationError("Override threshold cannot exceed passing marks.")
