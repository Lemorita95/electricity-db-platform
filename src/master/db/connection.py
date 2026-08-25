from sqlmodel import SQLModel, create_engine, Session
from master.config import DATABASE_URL


engine = create_engine(DATABASE_URL)


def get_session():
    with Session(engine) as session:
        yield session