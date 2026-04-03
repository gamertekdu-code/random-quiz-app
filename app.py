from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'simple_secret_key_for_student_project'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Database Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(255), nullable=False)
    option1 = db.Column(db.String(100), nullable=False)
    option2 = db.Column(db.String(100), nullable=False)
    option3 = db.Column(db.String(100), nullable=False)
    option4 = db.Column(db.String(100), nullable=False)
    correct_option = db.Column(db.Integer, nullable=False) # 1, 2, 3, or 4

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)

    user = db.relationship('User', backref=db.backref('results', lazy=True))

with app.app_context():
    db.create_all()

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles new user registration."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash("Username already exists!")
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password)
        
        # Make the first registered user an admin automatically for easy setup
        is_admin = False
        if User.query.count() == 0:
            is_admin = True
            
        new_user = User(username=username, password_hash=hashed_password, is_admin=is_admin)
        db.session.add(new_user)
        db.session.commit()
        
        flash("Registration successful! Please login.")
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles basic authentication."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    """Simple admin page to add or delete questions."""
    if 'user_id' not in session or not session.get('is_admin'):
        flash("You do not have permission to access the admin page.")
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        text = request.form['text']
        opt1 = request.form['option1']
        opt2 = request.form['option2']
        opt3 = request.form['option3']
        opt4 = request.form['option4']
        correct = request.form['correct_option']
        
        try:
            new_q = Question(
                text=text, 
                option1=opt1, option2=opt2, option3=opt3, option4=opt4, 
                correct_option=int(correct)
            )
            db.session.add(new_q)
            db.session.commit()
            flash("Question added successfully!")
        except Exception as e:
            flash("Error adding question.")
        
    questions = Question.query.all()
    return render_template('admin.html', questions=questions)

@app.route('/admin/delete/<int:q_id>')
def delete_question(q_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))
        
    q = Question.query.get(q_id)
    if q:
        db.session.delete(q)
        db.session.commit()
        flash("Question deleted.")
    return redirect(url_for('admin'))

@app.route('/quiz_start')
def quiz_start():
    """Initializes the quiz session logic."""
    if 'user_id' not in session:
        flash("Please log in to take the quiz.")
        return redirect(url_for('login'))
        
    questions = Question.query.all()
    if not questions:
        flash("No questions available yet! Please ask the admin to add some.")
        return redirect(url_for('index'))
        
    # Store quiz state in session
    session['quiz_questions'] = [q.id for q in questions]
    session['current_q_index'] = 0
    session['score'] = 0
    
    return redirect(url_for('quiz'))

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    """Displays one question at a time and handles answers."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    q_index = session.get('current_q_index')
    q_ids = session.get('quiz_questions')
    
    if q_index is None or q_ids is None:
        return redirect(url_for('quiz_start'))
        
    if q_index >= len(q_ids):
        # Quiz finished! Save result.
        result = Result(user_id=session['user_id'], score=session['score'], total=len(q_ids))
        db.session.add(result)
        db.session.commit()
        
        # Cleanup session logic
        session.pop('quiz_questions', None)
        session.pop('current_q_index', None)
        
        return redirect(url_for('result', result_id=result.id))
        
    current_q_id = q_ids[q_index]
    question = Question.query.get(current_q_id)
    
    if request.method == 'POST':
        selected_option = request.form.get('option')
        if selected_option and int(selected_option) == question.correct_option:
            session['score'] += 1
            
        session['current_q_index'] += 1
        return redirect(url_for('quiz'))
        
    return render_template('quiz.html', question=question, q_num=q_index+1, total=len(q_ids))

@app.route('/result/<int:result_id>')
def result(result_id):
    """Displays final score to user."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    res = Result.query.get(result_id)
    if not res:
        return redirect(url_for('index'))
        
    return render_template('result.html', result=res)

@app.route('/leaderboard')
def leaderboard():
    """Displays top 10 scores."""
    top_results = Result.query.order_by(Result.score.desc()).limit(10).all()
    return render_template('leaderboard.html', results=top_results)

if __name__ == '__main__':
    app.run(debug=True)
