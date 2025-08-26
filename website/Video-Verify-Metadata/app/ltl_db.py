from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv
import os

# Load environment variables from .env file
env = os.getenv('ENV')
if env == 'prod':
    load_dotenv('/app/prod.env')
else:
    load_dotenv('/app/dev.env')

# Database configuration
DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')

# Create engine
engine = create_engine(DATABASE_URI, echo=True)

# Create a configured "Session" class
Session = sessionmaker(bind=engine)

# Create a Session
session = scoped_session(Session)

# Base class for declarative class definitions
Base = declarative_base()

def test_db_connection():
    """
    Initialize the database connection.
    """
    try:
        # Test the database connection
        connection = engine.connect()
        connection.close()
        print("Database connection initialized successfully.")
    except Exception as e:
        print(f"Error initializing database connection: {e}")

def get_db_session():
    """
    Get a new database session.
    """
    return session()

def placeholder_db_call():
    """
    Placeholder function for calling the database.
    """
    db_session = get_db_session()
    # Perform database operations here
    # Example: db_session.query(YourModel).all()
    db_session.close()