import os 
from os import environ

import openai
from flask import Flask, redirect, render_template, request, url_for, session, jsonify, flash
import pyrebase
from functools import wraps
import time

# google login
import google.oauth2.id_token
from google.auth.transport import requests

# database tools
import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2 import service_account

app = Flask(__name__)
# openai.api_key = "HIDDEN"

config = {
  "apiKey": "HIDDEN",
  "authDomain": "ai-tutor-chat.firebaseapp.com",
  "projectId": "xxxxxx",
  "storageBucket": "ai-tutor-chat.appspot.com",
  "messagingSenderId": "166030352998",
  "appId": "xxxxxxxx",
  "measurementId": "G-L872X8M621",
  "databaseURL": ""
}

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()

# initialise firestore database
cred = credentials.Certificate('xxxxxxx.json')

FBapp = firebase_admin.initialize_app(cred)
db = firestore.client()

# save chatlogs to databse
def save_chat_log(user_email, user_input, ai_response):
    chat_log = {
        'user_email': user_email,
        'user_input': user_input,
        'ai_response': ai_response,
        'timestamp': firestore.SERVER_TIMESTAMP
    }

    # Save the chat log to Firestore under the 'chat_logs' collection
    db.collection('chat_logs').add(chat_log)

# save user data (subscriptions)
def create_new_user_in_firestore(email):
    user_doc_ref = db.collection('users').document(email)
    user_doc_ref.set({
        'email' : email,
        'subscription_status': 'non-subscribed',
        'daily_questions': 0,
        'reset_timestamp': int(time.time())
    })

# Helper functions to interact with the firestore (subscriptions)
def get_user_data_from_firestore(email):
    user_doc_ref = db.collection('users').document(email)
    user_data = user_doc_ref.get().to_dict()
    return user_data

def update_daily_question_count(email, daily_questions, reset_timestamp):
    user_doc_ref = db.collection('users').document(email)
    
    # If the reset timestamp has passed, reset the daily question count
    current_time = int(time.time())
    if current_time > reset_timestamp + 86400:
        daily_questions = 0
        reset_timestamp = current_time
    
    user_doc_ref.update({
        'daily_questions': daily_questions,
        'reset_timestamp': reset_timestamp
    })



# protect other routes by authentication
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('index', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# encrypt cookies
app.secret_key = 'secretkeyAItutor'

# needed to interpret line breaks
def nl2br(value):
    return value.replace('\n', '<br>')
app.jinja_env.filters['nl2br'] = nl2br

# Registration/ login page
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'user' in session:
        return redirect('/chat')

    if request.method == "POST":
        # if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        email = request.form.get('email')
        password = request.form.get('password')
        action = request.form.get('action')

        if action == "login":
            try:
                user = auth.sign_in_with_email_and_password(email, password)

                # Check if email is verified
                user_info = auth.get_account_info(user['idToken'])
                if not user_info['users'][0]['emailVerified']:
                    return jsonify({'status': 'error', 'message': 'Please register your email address.'}), 400

                # if it is, start a session and redirect
                session['user'] = email
                return jsonify({'status': 'success', 'message': 'Login successful.', 'redirect': '/chat'}), 200
                # return redirect('/chat')
            except:
                return jsonify({'status': 'error', 'message': 'Password or email is not correct.'}), 400
        elif action == "register":
            try:
                user = auth.create_user_with_email_and_password(email, password)
                auth.send_email_verification(user['idToken'])
                create_new_user_in_firestore(email)
                return jsonify({'status': 'success', 'message': 'Please check your email to verify your account.'}), 201
            except:
                return jsonify({'status': 'error', 'message': 'Failed to register.'}), 400
        # else:
        #     return render_template('home.html')

    return render_template('home.html')

@app.route('/logout')
def logout():
    session.pop('user')
    return redirect('/')


@app.route('/google_login', methods=['POST', 'GET'])
def google_login():
    id_token = request.form.get('id_token')
    try:
        # Verify the ID token
        claims = google.oauth2.id_token.verify_firebase_token(id_token, requests.Request())
        if not claims:
            return 'Invalid ID token', 401

        # Set the user's email in the session
        session['user'] = claims['email']
        return 'OK', 200
    except ValueError as e:
        return str(e), 401

# Chat Page with turbo
# https://www.twilio.com/blog/building-chatbot-chatgpt-api-twilio-programmable-sms-python

start_chat_log = [
    {"role": "system", "content": "You are a helpful math tutor who asks guiding questions to solve the exercises step-by-step, instead of giving the answer right away. You output all math in LaTeX interpretable code."},
    {"role": "assistant", "content": "What exercise would you like to solve together?"},
    {"role": "user", "content": "I need to solve the derivative of $$x^2cos(x)$$"},
    {"role": "assistant", "content": "Alright, let's tackle that question. Do you already have an idea how to start?"},
    {"role": "user", "content": "I'm done with that question, thanks for helping anyway, can you help me with another question?"},
    {"role": "assistant", "content": "Of course :D"},
]
chat_log = None
@app.route("/chat", methods=("GET", "POST"))
@login_required

def chat():
    global chat_log
    if chat_log is None:
        chat_log = start_chat_log
    
    # retrieve the user's email form the session and get its data from Firestore
    email = session['user']
    user_data = get_user_data_from_firestore(email)

    if request.method == "POST":
        # Check the user's subscription status and daily question count
        if user_data['subscription_status'] == 'non-subscribed':
            # If the user has reached their daily limit, return an error message
            if user_data['daily_questions'] >= 5:
                return render_template("chat.html", chat_log=chat_log[6:], limit_reached=True)

                # return redirect(url_for("chat"))

        question = request.form["question"]
        chat_log = chat_log + [{'role': 'user', 'content': question}]
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo', 
            messages=chat_log,
            temperature=0.9,
            max_tokens=250,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0.6,)
        answer = response.choices[0]['message']['content']
        chat_log = chat_log + [{'role': 'assistant', 'content': answer}]

        # Save chat log to Firestore
        user_email = session['user']
        save_chat_log(user_email, question, answer)

        # Update the user's daily question count and reset_timestamp in Firestore
        update_daily_question_count(email, user_data['daily_questions'] + 1, user_data['reset_timestamp'])

        return redirect(url_for("chat"))

    return render_template("chat.html", chat_log=chat_log[6:])


# Route handling feedback from the buttons
@app.route("/feedback", methods=["POST"])
@login_required
def feedback():
    data = request.get_json()
    feedback_type = data["feedback"]
    question = data["question"]
    response = data["response"]
    user_email = session['user']

    # Save feedback to the database
    save_feedback(user_email, question, response, feedback_type)

    return {"result": "success"}, 200

def save_feedback(user_email, question, response, feedback_type):
    feedback_data = {
        "user_email": user_email,
        "question": question,
        "response": response,
        "feedback": feedback_type,
        "timestamp": firestore.SERVER_TIMESTAMP
    }
    db.collection("feedback").add(feedback_data)


@app.route("/account")
@login_required
def account():
    email = session['user']
    user_data = get_user_data_from_firestore(email)
    return render_template("account.html", user_info=user_data)


@app.route('/upgrade')
@login_required
def upgrade():
    return render_template('upgrade.html')

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))