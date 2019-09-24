import pytest
from sqlalchemy import create_engine

from back.func import RPC
from back.models import Base, User, ConnectionDB, UserChat, Chat, Message


TEST_USER = 'test_user'
TEST_TOKEN = 'test_token'
DB_URI = 'sqlite:///'

@pytest.fixture
def rpc():
    engine = create_engine(DB_URI)
    ConnectionDB._engine = engine
    Base.metadata.create_all(bind=engine)

    RPC.init(DB_URI)

    user = User(name=TEST_USER, token=TEST_TOKEN)
    RPC.session.add(user)
    RPC.session.commit()

    RPC.user = user
    return RPC


def test__func_create_user_chat(rpc, test_chat_name="Chat 1"):
    chat_id = rpc.create_chat(test_chat_name)

    chat = rpc.session.query(Chat).get(chat_id)
    assert chat.name == test_chat_name

    user_chats = list(rpc.session.query(UserChat).filter(
        UserChat.user == rpc.user.name,
        UserChat.chat == chat_id
    ))

    assert len(user_chats) == 1


def test__func_list_chats(rpc):
    test_chat_names = {'chat 1', 'chat 2'}

    for name in test_chat_names:
        rpc.create_chat(name)

    for chat in rpc.list_chats():
        assert len(chat['id'])
        assert chat['name'] in test_chat_names


def test__func_create_message(rpc, test_chat_name='chat', test_text='text'):
    chat_id = RPC.create_chat(test_chat_name)

    msg_id = rpc.create_message(chat_id, test_text)

    msg = rpc.session.query(Message).get(msg_id)

    assert msg.text == test_text
    assert msg.chat == chat_id
    assert msg.author == rpc.user.name
