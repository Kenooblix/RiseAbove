from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from flask_sqlalchemy import SQLAlchemy
import os


app = Flask(__name__)
app.secret_key = "HelloItsMe"

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Point SQLAlchemy to the SQLite database file'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///riseabove.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # disable warnings
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        """Generate and store a hash of the password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Compare a provided password with the stored hash."""
        return check_password_hash(self.password_hash, password)

class Skill(db.Model):
    __tablename__ = "skill"
    
    id = db.Column(db.Integer, primary_key=True)  # an auto-increment key
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    skillname = db.Column(db.String(100), nullable=False)
    xp = db.Column(db.Integer, default=0, nullable=False)

    db.UniqueConstraint('user_id', 'skillname', name='unique_skill_for_user')

    def __repr__(self):
        return f"<Skill {self.skillname} (XP={self.xp})>"

# Borrowed from cs50 finance
def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
@login_required
def home():
    # Query all skills for the logged-in user
    user_id = session.get("user_id")
    skills = Skill.query.filter_by(user_id=user_id).all()
    return render_template("home.html", skills=skills)

@app.route('/calendar')
@login_required
def calendar():
    return render_template('calendar.html')

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Retrieve form inputs
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Server-side validation
        errors = []
        if len(username) < 3:
            errors.append("Username must be at least 3 characters long.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters long.")

        if errors:
            # Display error messages and redirect back to the login form
            for error in errors:
                flash(error, "danger")
            return redirect(url_for("login"))
        else:
            # Authenticate user (e.g., check database)
            # If authentication passes:
            # Lookup user in database
            user = User.query.filter_by(username=username).first()

            if user and user.check_password(password):
                # Valid credentials
                session["user_id"] = user.id
                flash("Logged in successfully!", "success")
                return redirect(url_for("home"))
            else:
                # Invalid credentials
                flash("Invalid username or password", "danger")
                return redirect(url_for("login"))

    # If GET request or after redirect due to errors, render the form
    return render_template("login.html")

@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("password-confirm", "")

        # Basic validation
        errors = []
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        # Check if username exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            errors.append("Username is already taken.")

        # If any errors, flash and redirect
        if errors:
            for err in errors:
                flash(err, "danger")
            return redirect(url_for("register"))

        # Otherwise, create the user
        new_user = User(username=username)
        # Hash the password before storing
        new_user.password_hash = generate_password_hash(password)
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for("login"))
    else:
        # GET request, just render the registration form
        return render_template("register.html")

# from CS50 finance    
@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/save_xp", methods=["POST"])
def save_xp():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()
    updated_skills = data.get("skills", [])

    for item in updated_skills:
        skillname = item["skillname"]
        xp = item["xp"]
        
        skill = Skill.query.filter_by(user_id=user_id, skillname=skillname).first()
        if skill:
            skill.xp = xp
        else:
            new_skill = Skill(user_id=user_id, skillname=skillname, xp=xp)
            db.session.add(new_skill)

    db.session.commit()
    return jsonify({"message": "XP updated successfully"}), 200

@app.route("/add_skill", methods=["POST"])
def add_skill():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()
    skillname = data.get("skillname", "").strip()

    if not skillname:
        return jsonify({"error": "Skill name is required"}), 400
    
    existing = Skill.query.filter_by(user_id=user_id, skillname=skillname).first()
    if existing:
        return jsonify({"error": "Skill already exists"}), 400

    new_skill = Skill(user_id=user_id, skillname=skillname, xp=0)
    db.session.add(new_skill)
    db.session.commit()

    return jsonify({
        "message": "Skill added successfully",
        "skill": {
            "skillname": new_skill.skillname,
            "xp": new_skill.xp
        }
    }), 200


@app.route("/delete_skill", methods=["POST"])
def delete_skill():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()
    skillname = data.get("skillname")

    skill = Skill.query.filter_by(user_id=user_id, skillname=skillname).first()
    if not skill:
        return jsonify({"error": "Skill not found"}), 404

    db.session.delete(skill)
    db.session.commit()

    return jsonify({"message": "Skill deleted successfully"}), 200

if __name__ == '__main__':
    # 'with app.app_context()' ensures Flask knows which application we’re in
    with app.app_context():
        db.create_all()  # This creates tables based on the model(s) above if they don't exist
    app.run(debug=True)
