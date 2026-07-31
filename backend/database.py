from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from backend.config import config





# from this file i get engine ,session ,getdb,base




#database step
# load .env file with os
# -create engine
# -session maker
# base def 

# Create database engine
engine = create_engine(
    config.POSTGRES_DB_URL
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# #parent to all table in db
Base = declarative_base()

# Function to get database session
def get_db():
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


    
    Base.metadata.create_all(bind=engine)
    