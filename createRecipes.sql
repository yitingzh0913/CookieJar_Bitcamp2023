DROP TABLE recipes;

CREATE TABLE recipes (
	id INT DEFAULT nextval('arecipes'),
	user_id INT,
	name VARCHAR,
	prep_time INT,
	servings INT,
	ingredient_key BIT(1000),
	ingredient_val VARCHAR,
	allergies VARCHAR,
	instructions VARCHAR,
	created TIMESTAMP
);