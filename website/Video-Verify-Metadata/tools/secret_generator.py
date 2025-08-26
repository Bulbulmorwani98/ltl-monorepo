import secrets

# Generate a random secret key
flask_secret_key = secrets.token_hex(32)
jwt_secret_key = secrets.token_hex(32)

print("FLASK_SECRET_KEY:", flask_secret_key)
print("JWT_SECRET_KEY:", jwt_secret_key)