from flask import g, Flask, session, render_template, request, url_for, flash, redirect
from flask_session import Session
import json
import os
import psycopg2
from functools import wraps
import time

DATABASE_URL = os.environ["DATABASE_URL"]

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

CONN = psycopg2.connect(DATABASE_URL)


def getSQL(fname):
	with open(fname, "r") as file:
		return file.read()


def login_required(func):

	@wraps(func)
	def wrap(*args, **kwargs):
		if session.get("user") is not None:
			return func(*args, **kwargs)
		else:
			return redirect("/login")

	return wrap


@app.route("/profile")
def profile():
	return render_template("profile.html")


@app.route("/addRecipe", methods=["GET", "POST"])
@login_required
def addRecipe():
	if request.method == "GET":
		return render_template("addRecipe.html")
	elif request.method == "POST":
		# gets form input data
		dishname = str(request.form["dishname"]).strip()
		ingredients = [x.strip() for x in request.form["ingredients"].split("\n")]
		allergies = [x.strip() for x in request.form["allergies"].split(",")]
		prep_time = [int(x) for x in request.form["time"].split(":")]
		servings = int(request.form["servings"])
		instructions = [x.strip() for x in request.form["instructions"].split("\n")]

		# formats the ingredients as a string and a bit-array
		formatted_ingredients = []
		ingredient_key = 0
		for ingredient in ingredients:
			split = ingredient.split(":")
			type = split[0].strip().lower()
			count = split[1].strip().lower()
			formatted_ingredients.append(f"{count} {type}")

			with CONN.cursor() as curr:
				curr.execute(f"SELECT id FROM ingredients WHERE name='{type}'")
				query = curr.fetchone()

				# adds missing ingredients to the database
				if query is None:
					print("None")
					curr.execute(
					 f"INSERT INTO ingredients (name) VALUES ('{type}') RETURNING id")
					query = curr.fetchone()

				# toggles 'on' the proper bits denoting the ingredient id
				ingredient_key |= 1 << query[0]

		ingredient_string = ", ".join(formatted_ingredients)
		CONN.commit()

		# processes and formats the rest of the user's recipe data
		user_id = session["user"]
		ptime = prep_time[0] * 3600 + prep_time[1] * 60 + prep_time[0]
		allergies = json.dumps(allergies)
		instructions = json.dumps(instructions)
		ingredient_key = str(bin(ingredient_key)).replace("b", "").zfill(1000)

		# inserts the recipe into the database
		with CONN.cursor() as curr:
			curr.execute(
			 f"INSERT INTO recipes (user_id, name, prep_time, servings, ingredient_key, ingredient_val, allergies, instructions, created) VALUES ({user_id}, '{dishname}', {ptime}, {servings}, '{ingredient_key}', '{ingredient_string}', '{allergies}', '{instructions}', CURRENT_TIMESTAMP)"
			)

		CONN.commit()

		return redirect("/")


@app.route('/', methods=["GET", "POST"])
@login_required
def index():
	if request.method == "GET":
		with CONN.cursor() as curr:
			curr.execute("SELECT name, prep_time, servings, id FROM recipes")
			query = curr.fetchall()

			data = []
			for line in query:
				recipe = {}
				recipe["name"] = line[0]
				ptime = line[1]
				hours = int(ptime / 3600)
				mins = int((ptime - (hours * 3600)) / 60)
				secs = int(ptime - (hours * 3600) - (mins * 60))

				if ptime > 3600:
					recipe[
					 "prep_time"] = f"{str(hours).zfill(2)}:{str(mins).zfill(2)}:{str(secs).zfill(2)}"
				elif ptime > 60:
					recipe["prep_time"] = f"{str(mins).zfill(2)}:{str(secs).zfill(2)}"
				else:
					recipe["prep_time"] = f"{str(secs).zfill(2)}"

				recipe["servings"] = line[2]
				recipe["image"] = f"images/recipes/{line[3]}.jpg"
				data.append(recipe)
		return render_template("index.html", recipes=data, count=len(data))

	elif request.method == "POST":
		params = [x.strip().lower() for x in request.form["params"].split(",")]

		key_id = 0
		with CONN.cursor() as curr:
			for param in params:
				curr.execute(f"SELECT id FROM ingredients WHERE name='{param}'")
				query = curr.fetchone()

				if query is None:
					return redirect("/search")

				key_id |= 1 << query[0]

		saved_recipes = []
		with CONN.cursor() as curr:
			curr.execute("SELECT id, ingredient_key, name FROM recipes")
			query = curr.fetchall()

			for line in query:
				bitval = int(line[1], 2)
				if bitval & key_id == key_id:
					saved_recipes.append((line[0], line[2]))

		data = []
		with CONN.cursor() as curr:
			for rid in saved_recipes:
				curr.execute(
				 f"SELECT name, prep_time, servings, id FROM recipes WHERE id={rid[0]}")
				query = curr.fetchone()

				recipe = {}
				recipe["name"] = query[0]
				ptime = query[1]
				print(ptime)
				hours = int(ptime / 3600)
				mins = int((ptime - (hours * 3600)) / 60)
				secs = int(ptime - (hours * 3600) - (mins * 60))

				if ptime > 3600:
					recipe[
					 "prep_time"] = f"{str(hours).zfill(2)}:{str(mins).zfill(2)}:{str(secs).zfill(2)}"
				elif ptime > 60:
					recipe["prep_time"] = f"{str(mins).zfill(2)}:{str(secs).zfill(2)}"
				else:
					recipe["prep_time"] = f"{str(secs).zfill(2)}"

				recipe["servings"] = query[2]
				recipe["image"] = f"images/recipes/{query[3]}.jpg"
				data.append(recipe)

		return render_template("index.html", recipes=data, count=len(data))


@app.route("/login", methods=["GET", "POST"])
def login():
	if request.method == "GET":
		return render_template("login.html")

	elif request.method == "POST":
		# gets user form data
		username = str(request.form["username"]).strip()
		password = str(request.form["password"]).strip()

		with CONN.cursor() as curr:
			# queries the database to see if the user exists
			curr.execute(
			 f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
			)
			query = curr.fetchone()

			# checks if the user does not exist
			if query is None:
				return redirect("/login")

		# redirects valid user to the homepage
		print(query)
		session["user"] = query[0]
		return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
	if request.method == "GET":
		return render_template("register.html")

	elif request.method == "POST":
		# gets the user form data
		username = str(request.form["username"]).strip()
		password = str(request.form["password"]).strip()

		with CONN.cursor() as curr:
			# queries the database to see if the user exists
			curr.execute(f"SELECT * FROM users WHERE username='{username}'")
			query = curr.fetchone()

			# checks if the user exists
			if query is not None:
				# refereshes the page for new input
				return redirect("/register")  # TODO: Something went wrong!

			# adds new user to the database
			curr.execute(
			 f"INSERT INTO users (id, username, password, created) VALUES (DEFAULT, '{username}', '{password}', CURRENT_TIMESTAMP) RETURNING id"
			)
			query = curr.fetchone()
			CONN.commit()

		# redirects the user to the homepage
		session["user"] = query[0]
		return redirect("/")


app.run(host='0.0.0.0', port=81)
