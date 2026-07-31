

from sqlalchemy import Column, Integer, String,Text,JSON
from backend.database import Base,engine


class Document(Base):
    """
    Document table — stores metadata about uploaded documents.

    Columns:
        id       - Auto-incrementing primary key
        filename - Name of the file (e.g. "report.pdf" or "report (1).pdf")
        filepath - Full path to the file on disk (inside storage/ folder)
        filehash - SHA-256 hash of the file content (used for duplicate detection)
    """
    __tablename__ = "documents"
    #Allows SQLAlchemy to reuse the existing table metadata on app reloads
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    filename = Column(String(255), nullable=False, index=True)
    filepath = Column(String(500), nullable=False)
    filehash = Column(String(64), nullable=False, unique=True, index=True)

# Extracted data columns
    extracted_text = Column(Text, nullable=True)
    tables_json = Column(JSON, nullable=True, default=list)  # Stores extracted tables as JSON

    def __repr__(self):
        return f"<Document id={self.id} filename={self.filename}>"


# Create the table if it doesn't exist yet (does nothing if it already does).
Base.metadata.create_all(bind=engine)