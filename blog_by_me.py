from flask import (
    Flask,
    render_template,
    flash,
    redirect,
    url_for,
    session,
    request,
)
from pymysql.cursors import DictCursor
import mysql.connector
from mysql.connector import Error
from wtforms import (
    Form,
    StringField,
    TextAreaField,
    PasswordField,
    validators,
    SubmitField,
)
from passlib.hash import sha256_crypt
import json
from functools import wraps
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired


# user login required decorator
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "logged_in" in session:
            return f(*args, **kwargs)
        else:
            flash("Unauthorized, Please login", "danger")
            return redirect(url_for("login"))

    return wrap


# user registration form
class RegisterForm(Form):
    name = StringField("Name", [validators.Length(min=1, max=50)])
    username = StringField("Username", [validators.Length(min=4, max=25)])
    email = StringField("Email", [validators.Email(message="Invalid email address")])
    password = PasswordField(
        "Password",
        [
            validators.DataRequired(),
            validators.EqualTo("confirm", message="Passwords do not match"),
        ],
    )
    confirm = PasswordField("Confirm Password")


# user login form
class LoginForm(Form):
    username = StringField("Username", [validators.Length(min=4, max=25)])
    password = PasswordField("Password", [validators.DataRequired()])


# article form
class ArticleForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    content = TextAreaField("Content", validators=[DataRequired()])
    submit = SubmitField("Update")


# Flask app
app = Flask(__name__)
app.secret_key = "super secret key"

# MySQL configurations
try:
    # Load MySQL connection details from the json file
    with open("Article Page with Flask\db_config.json") as config_file:
        config_data = json.load(config_file)

    # Establish MySQL connection using the loaded configuration
    mysql = mysql.connector.connect(
        host=config_data["host"],
        user=config_data["user"],
        password=config_data["password"],
        database=config_data["database"],
        port=config_data["port"],
    )

    if mysql.is_connected():
        db_Info = mysql.get_server_info()
        print("Connected to MySQL Server version ", db_Info)
        cursor = mysql.cursor()
        cursor.execute("select database();")
        record = cursor.fetchone()
        print("You're connected to database: ", record)

except Error as e:
    print("Error while connecting to MySQL", e)


# home page
@app.route("/")
def index():
    return render_template("index.html")


# about page
@app.route("/about")
def about():
    return render_template("about.html")


# article page
@app.route("/dashboard")
@login_required
def dashboard():
    cur = mysql.cursor()  # change this line
    query = "SELECT * FROM articles WHERE author = %s"
    cur.execute(query, [session["username"]])
    articles = cur.fetchall()

    if articles:
        return render_template("dashboard.html", articles=articles)
    else:
        msg = "No articles found"
        return render_template("dashboard.html", msg=msg)


# articles page
@app.route("/articles")
@login_required
def articles():
    cur = mysql.cursor()  # change this line
    query = "SELECT * FROM articles"
    cur.execute(query)
    articles = cur.fetchall()

    if articles:
        return render_template("articles.html", articles=articles)
    else:
        msg = "No articles found"
        return render_template("articles.html", msg=msg)


# user registration
@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm(request.form)

    if request.method == "POST" and form.validate():
        name = form.name.data
        username = form.username.data
        email = form.email.data
        password = sha256_crypt.encrypt(form.password.data)

        # Use cursor() instead of connection.cursor()
        cur = mysql.cursor()

        cur.execute(
            "INSERT INTO users(name,email,username,password) VALUES(%s,%s,%s,%s)",
            (name, email, username, password),
        )
        mysql.commit()
        cur.close()
        flash("You are now registered and can log in", "success")

        return redirect(url_for("login"))  # Change this line
    else:
        return render_template("register.html", form=form)


# user login
@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm(request.form)
    if request.method == "POST" and form.validate():
        username = form.username.data
        password_candidate = form.password.data

        cur = mysql.cursor()

        cur.execute("SELECT * FROM users WHERE username = %s", [username])
        data = cur.fetchone()

        if data is not None:
            password = data[4]

            if sha256_crypt.verify(password_candidate, password):
                flash("You are now logged in", "success")
                session["logged_in"] = True
                session["username"] = username
                return redirect(url_for("index"))
            else:
                flash("Invalid password", "danger")
                return redirect(url_for("login"))
        else:
            flash("Username not found", "danger")

        cur.close()

    return render_template("login.html", form=form)


# logout
@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You are now logged out", "info")
    return redirect(url_for("index"))


# add article
@app.route("/addarticle", methods=["GET", "POST"])
@login_required
def add_article():
    form = ArticleForm(request.form)
    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]

        cur = mysql.cursor()

        cur.execute(
            "INSERT INTO articles(title,content,author) VALUES(%s,%s,%s)",
            (title, content, session["username"]),
        )
        mysql.commit()
        cur.close()
        flash("Article created", "success")

        return redirect(url_for("dashboard"))
    else:
        return render_template("addarticle.html", form=form)


# details of an article
@app.route("/article/<string:id>", methods=["GET", "POST"])
def article_details(id):
    cur = mysql.cursor()
    query = "SELECT * FROM articles WHERE id = %s"
    cur.execute(query, [id])
    result = cur.fetchone()
    if result:
        return render_template("article_details.html", article=result)
    else:
        return render_template("article_details.html")


# delete article
@app.route("/deletearticle/<string:id>")
@login_required
def delete_article(id):
    cur = mysql.cursor()
    query = "DELETE FROM articles WHERE id = %s and author = %s"
    cur.execute(query, [id, session["username"]])

    if cur.rowcount > 0:
        mysql.commit()
        flash("Article deleted", "success")
    else:
        flash("No Article or Unauthorized", "danger")

    cur.close()
    return redirect(url_for("dashboard") if cur.rowcount > 0 else "index")


#Makale Güncelleme
@app.route("/edit/<string:id>", methods=["GET", "POST"])
@login_required
def update(id):
    if request.method == "GET":
        cursor = mysql.cursor()

        sorgu = "SELECT * FROM articles WHERE id = %s AND author = %s"
        result = cursor.execute(sorgu, (id, session["username"]))

        if result == 0:
            flash("No Article or Unauthorized", "danger")
            return redirect(url_for("index"))
        else:
            article = cursor.fetchone()
            form = ArticleForm()

            form.title.data = article[1]
            form.content.data = article[3]
            return render_template("update.html", form=form)

    else:
        # POST REQUEST
        form = ArticleForm(request.form)

        newTitle = form.title.data
        newContent = form.content.data

        sorgu2 = "UPDATE articles SET title = %s, content = %s WHERE id = %s"

        cursor = mysql.cursor()

        cursor.execute(sorgu2, (newTitle, newContent, id))

        mysql.commit()

        flash("Article Apdated Successfully", "success")

        return redirect(url_for("dashboard"))

#search aericle
@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "GET":
        return redirect(url_for("index"))
    else:
        keyword = request.form.get("keyword")

        cursor = mysql.cursor()

        sorgu = "SELECT * FROM articles WHERE title LIKE '%" + keyword + "%'"

        result = cursor.execute(sorgu)

        if result == 0:
            flash("No Article Found", "warning")
            return redirect(url_for("articles"))
        else:
            articles = cursor.fetchall()

            return render_template("articles.html", articles=articles)
    
if __name__ == "__main__":
    app.run(debug=True)
