from sqlalchemy import create_engine, String, Text, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
class Base(DeclarativeBase): pass
class PersistedEvent(Base):
    __tablename__="audit_events"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    event_hash:Mapped[str]=mapped_column(String(64),unique=True,nullable=False)
    payload:Mapped[str]=mapped_column(Text,nullable=False)

def create_database(url):
    kwargs={"future":True}
    if url.startswith("sqlite"): kwargs["connect_args"]={"check_same_thread":False}
    engine=create_engine(url,**kwargs); Base.metadata.create_all(engine); return engine, sessionmaker(engine,expire_on_commit=False)
