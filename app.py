from flask import Flask, request, jsonify
import stripe
import requests
import os

app = Flask(__name__)

# ENV Variables (Set these in Render later)
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
MAILCHIMP_API_KEY = os.getenv('MAILCHIMP_API_KEY')
MAILCHIMP_LIST_ID = os.getenv('MAILCHIMP_LIST_ID')
MAILCHIMP_SERVER_PREFIX = os.getenv('MAILCHIMP_SERVER_PREFIX')  # e.g., us10

# Stripe API Key
stripe.api_key = STRIPE_SECRET_KEY

@app.route('/')
def home():
    return 'Stripe to Mailchimp Webhook is Running!'

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        return jsonify({'error': 'Invalid signature'}), 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        email = session['customer_details']['email']
        name = session['customer_details']['name']
        amount = session['amount_total'] / 100  # Convert cents to dollars

        # Add to Mailchimp
        add_to_mailchimp(email, name, amount)

    return jsonify({'status': 'success'}), 200

def add_to_mailchimp(email, name, amount):
    url = f'https://{MAILCHIMP_SERVER_PREFIX}.api.mailchimp.com/3.0/lists/{MAILCHIMP_LIST_ID}/members'
    headers = {
        'Authorization': f'Bearer {MAILCHIMP_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        'email_address': email,
        'status': 'subscribed',
        'merge_fields': {
            'FNAME': name,
            'DONATION': amount
        }
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        print(f"Added {email} to Mailchimp.")
    else:
        print(f"Failed to add {email}: {response.text}")

if __name__ == '__main__':
    app.run(port=5000)
