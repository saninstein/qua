import logging

import flask
from flask_cors import CORS, cross_origin

from back import func


logging.basicConfig(level=logging.DEBUG)

app = flask.Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.add_url_rule('/api', view_func=cross_origin()(func.entry_point), methods=["POST"])


if __name__ == '__main__':
    app.run(port=8008)
