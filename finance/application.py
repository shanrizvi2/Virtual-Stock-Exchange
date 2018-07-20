import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash
from passlib.apps import custom_app_context as pwd_context


from helpers import apology, login_required, lookup, usd

# Ensure environment variable is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    row = db.execute("SELECT * FROM portfolio WHERE id = :ids", ids = session["user_id"])
    # create a temporary variable to store TOTAL worth ( cash + share)
    total = 0
    # update each symbol prices and total
    for row in row:
        symbol = row["symbol"]
        shares = row["shares"]
        stock = lookup(symbol)
        totals = shares * stock["price"]
        total += totals
        db.execute("UPDATE portfolio SET price=:price, \
                    total=:total WHERE id=:id AND symbol=:symbol", \
                    price=usd(stock["price"]), \
                    total=usd(totals), id=session["user_id"], symbol=symbol)

    tot = db.execute("SELECT cash FROM users WHERE id = :cur", cur = session["user_id"])
    total += tot[0]["cash"]
    portfolio = db.execute("SELECT * from portfolio WHERE id=:id", id=session["user_id"])
    return render_template("title.html", row = portfolio, cash = usd(tot[0]["cash"]), total = usd(total))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        rows = lookup(request.form.get("symbol"))

        shares = int(request.form.get("shares"))

        if not rows:
            return apology("Stock does not exist", 403)

        if shares < 0:
            return apology("Input a positive number of shares to buy", 403)

        money = db.execute("SELECT cash FROM users WHERE id = :cur", cur = session["user_id"])

        if not money or float(money[0]["cash"]) < rows["price"] * shares:
            return apology("You cannot afford this stock", 403)

        user_shares = db.execute("SELECT * FROM portfolio \
                           WHERE id = :id AND symbol=:symbol", \
                           id=session["user_id"], symbol=rows["symbol"])

        # if user doesn't has shares of that symbol, create new stock object
        if not user_shares:
            db.execute("INSERT INTO portfolio (shares, price, total, symbol, id) \
                        VALUES(:shares, :price, :total, :symbol, :id)", \
                        shares=shares, price=usd(rows["price"]), \
                        total=usd(shares * rows["price"]), \
                        symbol=rows["symbol"], id=session["user_id"])

        # Else increment the shares count
        else:
            shares_total = user_shares[0]["shares"] + shares
            db.execute("UPDATE portfolio SET shares=:shares\
                        WHERE id=:id AND symbol=:symbol", \
                        shares=shares_total, id =session["user_id"], \
                        symbol=rows["symbol"])

        db.execute("INSERT INTO history (symbol, shares, price, id) \
                        VALUES(:symbol, :shares, :price, :id)", \
                        symbol=rows["symbol"], shares = shares, price=usd(rows["price"]), id=session["user_id"])

        db.execute("UPDATE users SET cash = :stock WHERE id = :cur", stock = (float(money[0]["cash"]) - (rows["price"] * shares)), cur = session["user_id"])

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    row = db.execute("SELECT * FROM history WHERE id = :ids", ids = session["user_id"])
    return render_template("history.html", row = row)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        rows = lookup(request.form.get("symbol"))

        if not rows:
            return apology("stock does not exist", 403)

        return render_template("quoted.html", stock=rows)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hashed)", username = request.form.get("username"), hashed = generate_password_hash(request.form.get("password")))

        if not result:
            return apology("username already exists, try a different one", 403)

        session["user_id"] = result

        return render_template("title.html")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        rows = lookup(request.form.get("symbol"))
        symbol = request.form.get("symbol").upper()
        shares = int(request.form.get("shares"))
        if not rows:
            return apology("Stock does not exist", 403)
        if shares < 0:
            return apology("Input a positive number of shares to buy", 403)
        select = db.execute("SELECT * FROM portfolio WHERE id = :cur AND symbol = :symbol", symbol = symbol, cur = session["user_id"])
        if not select:
            return apology("Stock does not exist in your portfolio", 403)
        if select[0]["shares"] < shares:
            return apology("You cannot sell more shares than you own", 403)
        upShares = int(select[0]["shares"]) - shares
        if upShares == 0:
            db.execute("DELETE FROM portfolio WHERE id = :cur AND symbol = :symbol", symbol = symbol, cur = session["user_id"])
        else:
            db.execute("UPDATE portfolio SET shares = :share WHERE id = :cur AND symbol = :symbol", share = upShares, symbol = symbol, cur = session["user_id"])
        sel = db.execute("SELECT * FROM users WHERE id = :cur", cur = session["user_id"])
        upCash = int(sel[0]["cash"]) + (shares * rows["price"])
        db.execute("UPDATE users SET cash = :cashes WHERE id = :cur", cashes = upCash, cur = session["user_id"])
        db.execute("INSERT INTO history (symbol, shares, price, id) \
                        VALUES(:symbol, :shares, :price, :id)", \
                        symbol=symbol, shares = -shares, price=usd(rows["price"]), id=session["user_id"])
        return redirect("/")
    else:
        return render_template("sell.html")

def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
