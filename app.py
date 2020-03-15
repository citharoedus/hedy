from datetime import datetime
from functools import wraps
import hedy
import json
import jsonbin
import logging
import os
import requests
import uuid

# app.py
from flask import Flask, request, jsonify, render_template, session
from flask_compress import Compress

logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)-8s: %(message)s')

app = Flask(__name__, static_url_path='')

# Unique random key for sessions
app.config['SECRET_KEY'] = uuid.uuid4().hex

Compress(app)
logger = jsonbin.JsonBinLogger.from_env_vars()

@app.route('/levels-text/', methods=['GET'])
def levels():
    level = request.args.get("level", None)

    #read levels from file
    try:
        file = open("levels.json", "r")
        contents = str(file.read())
        response = (json.loads(contents))
        file.close()
    except Exception as E:
            print(f"error opening level {level}")
            response["Error"] = str(E)
    return jsonify(response)


@app.route('/parse/', methods=['GET'])
def parse():
    # Retrieve the name from url parameter
    code = request.args.get("code", None)
    level = request.args.get("level", None)

    # For debugging
    print(f"got code {code}")

    response = {}

    # Check if user sent code
    if not code:
        response["Error"] = "no code found, please send code."
    # is so, parse
    else:
        try:
            result = hedy.transpile(code, level)
            response["Code"] = result
        except hedy.HedyException as E:
            texts = load_texts()
            error_template = texts['HedyErrorMessages'][E.error_code]
            response["Error"] = error_template.format(**E.arguments)
        except Exception as E:
            print(f"error transpiling {code}")
            response["Error"] = str(E)

    logger.log({
        'session': session_id(),
        'date': str(datetime.now()),
        'level': level,
        'code': code,
        'server_error': response.get('Error')
    })

    return jsonify(response)

@app.route('/report_error', methods=['POST'])
def report_error():
    post_body = request.json

    logger.log({
        'session': session_id(),
        'date': str(datetime.now()),
        'level': post_body.get('level'),
        'code': post_body.get('code'),
        'client_error': post_body.get('client_error')
    })


# @app.route('/post/', methods=['POST'])
# for now we do not need a post but I am leaving it in for a potential future

# routing to index.html
@app.route('/index.html', methods=['GET'])
@app.route('/', methods=['GET'])
def index():
    session_id()  # Run this for the side effect of generating a session ID

    level = request.args.get("level", 1)
    level = int(level)
    lang = requested_lang()

    arguments_dict = {}
    arguments_dict['level'] = level
    arguments_dict['lang'] = lang

    try:
        with open("static/levels.json", "r") as file:
            response_levels = json.load(file)
        response_texts_lang = load_texts()
    except Exception as E:
        print(f"error opening level {level}")
        return jsonify({"Error": str(E)})

    arguments_dict['page_title'] = response_texts_lang['Page_Title']
    arguments_dict['run_button'] = response_texts_lang['Run_code_button']
    arguments_dict['advance_button'] = response_texts_lang['Advance_button']
    arguments_dict['enter_text'] = response_texts_lang['Enter_Text']
    arguments_dict['enter'] = response_texts_lang['Enter']

    level_and_lang_dict = [r for r in response_levels if int(r['Level']) == level and r['Language'] == lang][0]
    maxlevel = max(int(r['Level']) for r in response_levels)

    arguments_dict['commands'] = level_and_lang_dict['Commands']
    arguments_dict['introtext'] = level_and_lang_dict['Intro_text']
    arguments_dict['startcode'] = level_and_lang_dict['Start_code']

    next_level_available = level != maxlevel
    arguments_dict['nextlevel'] = level + 1 if next_level_available else None
    arguments_dict['latest'] = 'March 13th'

    return render_template("index.html", **arguments_dict)

@app.route('/error_messages.js', methods=['GET'])
def error():
    try:
        lang_texts = load_texts()
        error_messages = lang_texts["ClientErrorMessages"]
    except Exception as E:
        print(f"error opening texts.json")
        error_messages = {"Error": str(E)}

    return render_template("error_messages.js", error_messages=json.dumps(error_messages))


@app.errorhandler(500)
def internal_error(exception):
    import traceback
    print(traceback.format_exc())
    return "<h1>500 Internal Server Error</h1>"


def session_id():
    """Returns or sets the current session ID."""
    if 'session_id' not in session:
        session['session_id'] = uuid.uuid4().hex
    return session['session_id']


def requested_lang():
    """Return the user's requested language code."""
    return request.args.get("lang", 'Nl')


def load_texts():
    """Load the texts for the given language.

    If the language is unknown, default to English.
    """
    with open("static/texts.json", "r") as file:
        texts_file = json.load(file)
    texts = texts_file.get(requested_lang().lower())
    return texts if texts else texts_file.get('en')

if __name__ == '__main__':
    # Threaded option to enable multiple instances for multiple user access support
    app.run(threaded=True, port=5000)
