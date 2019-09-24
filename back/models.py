import uuid
import time
from datetime import datetime
from hashlib import md5

import sqlalchemy as sqla
from sqlalchemy.schema import Column
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import create_engine
from sqlalchemy.ext.declarative import as_declarative


def model_query_to_dicts(q):
    return [m.to_dict() for m in q]


@as_declarative()
class Base:
    def to_dict(self):

        def prepare_val(val):
            if isinstance(val, datetime):
                return datetime.timestamp(val)
            return val

        return {column.name: prepare_val(getattr(self, column.name)) for column in self.__table__.columns}

    def __str__(self):
        return f'<{type(self).__name__} {" ".join(f"{k}={v}" for k, v in self.to_dict().items())}>'


class ConnectionDB:
    _meta = None
    _declarative_base = None
    _engine = None

    @classmethod
    def get_engine(cls, url=None, **kwargs):
        if not cls._engine:
            cls._engine = create_engine(url, **kwargs)

        return cls._engine

    @classmethod
    def get_meta(cls, url=None, **kwargs):
        if not cls._meta:
            cls._meta = sqla.MetaData(bind=cls.get_engine(url, **kwargs))

        return cls._meta


class TimeUUIDHashId():
    id = Column(
        sqla.String(32),
        default=lambda: md5(f"{time.time()}_{uuid.uuid4()}".encode()).hexdigest(),
        primary_key=True
    )


class Message(Base, TimeUUIDHashId):
    __tablename__ = 'messages'

    text = Column(sqla.String(4096), nullable=False)
    chat = Column(sqla.String(8), nullable=False)
    # created = Column(sqla.TIMESTAMP, default=lambda: str(datetime.utcnow()), nullable=False)
    created = Column(sqla.DATETIME, default=datetime.utcnow, nullable=False)
    author = Column(sqla.String, nullable=False)


class User(Base):
    __tablename__ = 'users'

    name = Column(sqla.String(16), primary_key=True)
    token = Column(sqla.String(32), nullable=False)


class Chat(Base, TimeUUIDHashId):
    __tablename__ = 'chats'

    name = Column(sqla.String(50), nullable=False)
    is_private = Column(sqla.Boolean, default=False, nullable=False)


class UserChat(Base, TimeUUIDHashId):
    __tablename__ = 'users_chats'

    user = Column(sqla.String(16), nullable=False)
    chat = Column(sqla.String(8), nullable=False)


def get_session(url: str = None, **kwargs):
    engine = ConnectionDB.get_engine(url, **kwargs)
    Base.metadata = ConnectionDB.get_meta()
    Base.metadata.reflect(engine)

    session = sessionmaker()
    session.configure(bind=engine)

    return session()
