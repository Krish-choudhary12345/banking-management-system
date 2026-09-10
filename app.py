from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)

# Used for login sessions
app.secret_key = "banking_system_secret_key"

DATABASE = "banking.db"


# ---------------- DATABASE CONNECTION ----------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- CREATE DATABASE TABLES ----------------

def init_db():

    conn = get_db()

    # Users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_no TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            balance REAL DEFAULT 0
        )
    """)

    # Transactions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_no TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# ---------------- LOGIN REQUIRED ----------------

def login_required(function):        

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "account_no" not in session:

            flash("Please login first.", "error")

            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


# ---------------- HOME PAGE ----------------

@app.route("/")
def index():

    return render_template("index.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]

        # Check empty fields
        if not name or not email or not password:

            flash("All fields are required.", "error")

            return redirect(url_for("register"))

        # Password validation
        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "error"
            )

            return redirect(url_for("register"))

        conn = get_db()

        # Find last account number
        last_user = conn.execute("""
            SELECT account_no
            FROM users
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        if last_user:

            account_no = str(
                int(last_user["account_no"]) + 1
            )

        else:

            account_no = "100001"

        # Hash password
        password_hash = generate_password_hash(password)

        try:

            conn.execute("""
                INSERT INTO users
                (account_no, name, email, password_hash, balance)
                VALUES (?, ?, ?, ?, ?)
            """, (
                account_no,
                name,
                email,
                password_hash,
                0
            ))

            conn.commit()

            flash(
                f"Account created successfully! "
                f"Your Account Number is {account_no}",
                "success"
            )

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:

            flash(
                "Email already exists.",
                "error"
            )

            return redirect(url_for("register"))

        finally:

            conn.close()

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        account_no = request.form["account_no"].strip()
        password = request.form["password"]

        conn = get_db()

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE account_no = ?
        """, (account_no,)).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):

            session["account_no"] = user["account_no"]
            session["name"] = user["name"]

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid account number or password.",
            "error"
        )

    return render_template("login.html")


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
@login_required
def dashboard():

    account_no = session["account_no"]

    conn = get_db()

    user = conn.execute("""
        SELECT *
        FROM users
        WHERE account_no = ?
    """, (account_no,)).fetchone()

    conn.close()

    return render_template(
        "dashboard.html",
        user=user
    )


# ---------------- DEPOSIT ----------------

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():

    if request.method == "POST":

        try:

            amount = float(
                request.form["amount"]
            )

        except ValueError:

            flash(
                "Enter a valid amount.",
                "error"
            )

            return redirect(
                url_for("deposit")
            )

        if amount <= 0:

            flash(
                "Amount must be greater than zero.",
                "error"
            )

            return redirect(
                url_for("deposit")
            )

        account_no = session["account_no"]

        conn = get_db()

        # Update balance
        conn.execute("""
            UPDATE users
            SET balance = balance + ?
            WHERE account_no = ?
        """, (amount, account_no))

        # Save transaction
        conn.execute("""
            INSERT INTO transactions
            (account_no, transaction_type, amount, description)
            VALUES (?, ?, ?, ?)
        """, (
            account_no,
            "Deposit",
            amount,
            "Money deposited"
        ))

        conn.commit()
        conn.close()

        flash(
            "Money deposited successfully.",
            "success"
        )

        return redirect(
            url_for("dashboard")
        )

    return render_template("deposit.html")


# ---------------- WITHDRAW ----------------

@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():

    if request.method == "POST":

        try:

            amount = float(
                request.form["amount"]
            )

        except ValueError:

            flash(
                "Enter a valid amount.",
                "error"
            )

            return redirect(
                url_for("withdraw")
            )

        if amount <= 0:

            flash(
                "Amount must be greater than zero.",
                "error"
            )

            return redirect(
                url_for("withdraw")
            )

        account_no = session["account_no"]

        conn = get_db()

        user = conn.execute("""
            SELECT balance
            FROM users
            WHERE account_no = ?
        """, (account_no,)).fetchone()

        # Check balance
        if amount > user["balance"]:

            conn.close()

            flash(
                "Insufficient balance.",
                "error"
            )

            return redirect(
                url_for("withdraw")
            )

        # Update balance
        conn.execute("""
            UPDATE users
            SET balance = balance - ?
            WHERE account_no = ?
        """, (amount, account_no))

        # Save transaction
        conn.execute("""
            INSERT INTO transactions
            (account_no, transaction_type, amount, description)
            VALUES (?, ?, ?, ?)
        """, (
            account_no,
            "Withdrawal",
            amount,
            "Money withdrawn"
        ))

        conn.commit()
        conn.close()

        flash(
            "Money withdrawn successfully.",
            "success"
        )

        return redirect(
            url_for("dashboard")
        )

    return render_template("withdraw.html")


# ---------------- TRANSFER ----------------

@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():

    if request.method == "POST":

        receiver = request.form[
            "receiver"
        ].strip()

        try:

            amount = float(
                request.form["amount"]
            )

        except ValueError:

            flash(
                "Enter a valid amount.",
                "error"
            )

            return redirect(
                url_for("transfer")
            )

        sender = session["account_no"]

        # Cannot transfer to yourself
        if receiver == sender:

            flash(
                "You cannot transfer money to yourself.",
                "error"
            )

            return redirect(
                url_for("transfer")
            )

        if amount <= 0:

            flash(
                "Amount must be greater than zero.",
                "error"
            )

            return redirect(
                url_for("transfer")
            )

        conn = get_db()

        # Sender
        sender_user = conn.execute("""
            SELECT balance
            FROM users
            WHERE account_no = ?
        """, (sender,)).fetchone()

        # Receiver
        receiver_user = conn.execute("""
            SELECT account_no
            FROM users
            WHERE account_no = ?
        """, (receiver,)).fetchone()

        # Check receiver
        if receiver_user is None:

            conn.close()

            flash(
                "Receiver account does not exist.",
                "error"
            )

            return redirect(
                url_for("transfer")
            )

        # Check sender balance
        if amount > sender_user["balance"]:

            conn.close()

            flash(
                "Insufficient balance.",
                "error"
            )

            return redirect(
                url_for("transfer")
            )

        # Remove money from sender
        conn.execute("""
            UPDATE users
            SET balance = balance - ?
            WHERE account_no = ?
        """, (amount, sender))

        # Add money to receiver
        conn.execute("""
            UPDATE users
            SET balance = balance + ?
            WHERE account_no = ?
        """, (amount, receiver))

        # Sender transaction
        conn.execute("""
            INSERT INTO transactions
            (account_no, transaction_type, amount, description)
            VALUES (?, ?, ?, ?)
        """, (
            sender,
            "Transfer",
            amount,
            f"Transferred to {receiver}"
        ))

        # Receiver transaction
        conn.execute("""
            INSERT INTO transactions
            (account_no, transaction_type, amount, description)
            VALUES (?, ?, ?, ?)
        """, (
            receiver,
            "Received",
            amount,
            f"Received from {sender}"
        ))

        conn.commit()
        conn.close()

        flash(
            "Money transferred successfully.",
            "success"
        )

        return redirect(
            url_for("dashboard")
        )

    return render_template("transfer.html")


# ---------------- TRANSACTION HISTORY ----------------

@app.route("/transactions")
@login_required
def transactions():

    account_no = session["account_no"]

    conn = get_db()

    transactions = conn.execute("""
        SELECT *
        FROM transactions
        WHERE account_no = ?
        ORDER BY id DESC
    """, (account_no,)).fetchall()

    conn.close()

    return render_template(
        "transactions.html",
        transactions=transactions
    )


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("index")
    )


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":

    init_db()

    app.run(debug=True)