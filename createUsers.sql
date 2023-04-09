DROP TABLE users;

CREATE TABLE users (
	id INT DEFAULT nextval('ausers'),
	username VARCHAR,
	password VARCHAR,
	created TIMESTAMP
);