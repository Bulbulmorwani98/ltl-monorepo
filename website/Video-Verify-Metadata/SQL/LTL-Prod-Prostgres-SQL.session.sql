create TABLE IF NOT EXISTS "users" (
  "id" SERIAL PRIMARY KEY,
  "username" varchar(255) NOT NULL,
  "password" varchar(255) NOT NULL,
  "email" varchar(255) NOT NULL,
  "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (username, password, email) VALUES ('delme', 'clearly this should be encrypted', 'bridared@example.com')

Select * from users

