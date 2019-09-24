import os
import time
import uuid
import random
import logging
from datetime import datetime
from hashlib import md5
from typing import List, Dict, Union

import flask
from sqlalchemy import sql
from sqlalchemy.orm import Session
from nickname_generator import generate as generate_nick
from jsonrpc import JSONRPCResponseManager, Dispatcher

from .models import get_session, model_query_to_dicts, User, Chat, UserChat, Message

SYSTEM_USER = "__system"


class RPC:
    session: Session = None
    user: User = None

    @classmethod
    def init(cls, db_uri: str = None, engine_kwargs: dict = None, user_token: str = None):
        """
        Init func. init sqla session and user
        :return:
        """
        if db_uri is None:
            db_uri = os.environ.get(
                'DB_URI',
                'sqlite:////home/sanin/pycharm-projects/qua/db.sqlite'
                # 'bigquery://quachat/test_dataset?credentials_path=/home/sanin/pycharm-projects/qua/gcp-auth.json'
            )
        cls.session: Session = get_session(db_uri, **(engine_kwargs or {}))
        cls.user = cls.get_user(user_token) if user_token else None

    @classmethod
    def is_user_member(cls, chat: str) -> bool:
        """
        Check if the user is a member of the chat
        :param chat: chat id
        :return:
        """
        return cls.session.query(
            sql.exists().where(
                sql.and_(UserChat.user == cls.user.name, UserChat.chat == chat)
            )
        ).scalar()

    @classmethod
    def is_username_used(cls, name: str) -> bool:
        """
        Check if the username is used
        :param name: username
        :return:
        """
        return cls.session.query(
            sql.exists().where(
                sql.and_(User.name == name)
            )
        ).scalar()

    @classmethod
    def get_user(cls, token: str) -> User:
        """
        Get user model instance by token
        :param token: user secret token
        :return: user instance or None
        """
        return cls.session.query(User).filter(User.token == token).first()

    @classmethod
    def create_chat(cls, name: str) -> str:
        """
        Create chat & and join current user to it
        :param name: chat name
        :return: chat id
        """
        logging.debug(f"Create chat: {name}")
        chat = Chat(name=name)

        cls.session.add(chat)
        cls.session.commit()

        cls.session.add(UserChat(user=cls.user.name, chat=chat.id))

        cls.session.commit()
        cls.create_message(chat.id, f"Chat {name} created", system=True)
        return chat.id

    @classmethod
    def list_chats(cls) -> List[Dict]:
        """
        Returns chats list of current user
        :return:
        """
        chats = cls.session.query(Chat).\
            join(UserChat, UserChat.chat == Chat.id).\
            join(User, UserChat.user == cls.user.name).all()
        return [chat.to_dict() for chat in chats]

    @classmethod
    def create_message(cls, chat: str, text: str, system: bool = False) -> Union[str, Dict]:
        """
        Create message in chat
        :param chat: chat id
        :param text: message text
        :return: message id
        """
        if system:
            author = SYSTEM_USER
        else:
            if not cls.is_user_member(chat):
                return {"error": "Not Found"}
            author = cls.user.name

        msg = Message(text=text, chat=chat, author=author)
        cls.session.add(msg)
        cls.session.commit()
        return msg.id

    @classmethod
    def list_messages(cls, chat: str, start: int = None, end: int = None, last: int = None) -> Union[List[Dict], Dict]:
        """
        Returns chat messages
        :param chat: chat id
        :param start: start unixtimestamp
        :param end: end unixtimestamp
        :param last: if provided, returns last `last` messages
        :return:
        """
        if not cls.is_user_member(chat):
            return {"error": "Not Found"}

        filters = [Message.chat == chat]

        if last:
            query = cls.session.query(Message).\
                filter(*filters).\
                order_by(Message.created.desc()).\
                limit(last).all()
            return list(reversed(model_query_to_dicts(query)))

        if start:
            filters.append(
                Message.created >= str(datetime.utcfromtimestamp(start))
            )

        if end:
            filters.append(
                Message.created <= str(datetime.utcfromtimestamp(end))
            )

        return model_query_to_dicts(cls.session.query(Message).filter(*filters).order_by(Message.created))

    @classmethod
    def search_chats(cls, search_str: str) -> List[Dict]:
        return model_query_to_dicts(
            cls.session.query(Chat).filter(Chat.name.startswith(search_str), Chat.name.is_private == False)
        )

    @classmethod
    def join_chat(cls, chat: str) -> bool:
        """
        Join current user to chat
        :param chat: chat id
        :return:
        """
        if not cls.is_user_member(chat):
            cls.session.add(UserChat(chat=chat, user=cls.user.name))
            cls.create_message(chat, f"{cls.user.name} joined the chat", system=True)
        return True

    @classmethod
    def leave_chat(cls, chat: str) -> Union[bool, Dict]:
        if not cls.is_user_member(chat):
            return {"error": 'not found'}

        for uc in cls.session.query(UserChat).filter(UserChat.user == cls.user.name, UserChat.chat == chat):
            cls.session.delete(uc)

        cls.create_message(chat, f"{cls.user.name} left the chat", system=True)
        return True

    @staticmethod
    def generate_token(name: str) -> str:
        """
        Generates and returns user token
        :param name: username
        :return:
        """
        return md5(f"{name}_{time.time()}_{uuid.uuid4()}".encode()).hexdigest()

    @staticmethod
    def generate_name() -> str:
        """
        Generates random username
        :return:
        """
        name = generate_nick()
        if random.random() > 0.5:
            name = f"{name}{'_' if random.random() < 0.3 else ''}{generate_nick()}"

        if random.random() < 0.5:
            name = name.lower()

        if random.random() < 0.3:
            name = f"{name}{random.randint(0, 999)}"
        return name

    @classmethod
    def generate_unique_name(cls) -> str:
        """
        Generates unique username
        :return:
        """
        while True:
            name = cls.generate_name()
            if not cls.is_username_used(name):
                return name

    @classmethod
    def generate_unique_token(cls, name) -> str:
        """
        Generates unique token
        :param name: username
        :return:
        """
        while True:
            token = cls.generate_token(name)
            if not cls.get_user(token):
                return token

    @classmethod
    def register(cls, name: str = None) -> dict:
        """
        Register new user
        :param name:
        :return:
        """
        if name is None:
            name = cls.generate_unique_name()
        else:
            if cls.is_username_used(name) or name == SYSTEM_USER:
                return {"error": "USERNAME_USED"}

        usr = User(
            name=name,
            token=cls.generate_unique_token(name)
        )

        cls.session.add(usr)
        cls.session.commit()
        return usr.to_dict()

    @classmethod
    def get_username(cls):
        if cls.user:
            return cls.user.name
        return None


dispatcher = Dispatcher(
    {
        "create_chat": RPC.create_chat,
        "list_chats": RPC.list_chats,
        "create_message": RPC.create_message,
        "list_messages": lambda **kwargs: RPC.list_messages(
            kwargs["chat"], kwargs.get("start"), kwargs.get("end"), kwargs.get("last")
        ),
        "join_chat": RPC.join_chat,
        "register": RPC.register,
        "search_chats": RPC.search_chats,
        "get_username": RPC.get_username
    }
)


def entry_point(request: flask.Request = None):
    """
    Entrypoint rpc. flask view
    :param request:
    :return:
    """
    if not request:
        request = flask.request

    if request.method != "POST":
        return "only post"

    RPC.init(user_token=request.headers.get('Authorization'))
    logging.debug(f"Incoming data: {request.data}")

    return flask.jsonify(
        JSONRPCResponseManager.handle(request.data, dispatcher).data
    )
