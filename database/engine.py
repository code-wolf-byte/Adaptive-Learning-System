from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .base import Base
from .models import *


class DatabaseEngine:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.Base = Base
        self.create_tables()

    def create_tables(self):
        self.Base.metadata.create_all(self.engine)

    def get_session(self):
        return self.Session()

    def get_base(self):
        return self.Base

    def add(self, obj):
        """Add or update an object in the database"""
        session = self.get_session()
        try:
            # If the object is already attached to a session, merge it
            if hasattr(obj, '_sa_instance_state') and obj._sa_instance_state.session is not None:
                obj = session.merge(obj)
            else:
                session.add(obj)
            session.commit()
        finally:
            session.close()

    def get(self, model, id):
        session = self.get_session()
        obj = session.query(model).get(id)
        session.close()
        return obj

    def get_all(self, model):
        session = self.get_session()
        objs = session.query(model).all()
        session.close()
        return objs

    def query(self, model):
        """Get a query object for the specified model"""
        return self.get_session().query(model)
