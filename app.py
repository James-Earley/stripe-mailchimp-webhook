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

        # Extract customer details
        email = session['customer_details']['email']
        full_name = session['customer_details']['name']
        address = session['customer_details']['address']
        amount = session['amount_total'] / 100  # Convert cents to dollars

        # Split full name into first and last name
        if full_name:
            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

        # Add to Mailchimp with full details
        add_to_mailchimp(email, first_name, last_name, amount, address)

        return jsonify({'status': 'success'}), 200

def add_to_mailchimp(email, first_name, last_name, amount, address):
    url = f'https://{MAILCHIMP_SERVER_PREFIX}.api.mailchimp.com/3.0/lists/{MAILCHIMP_LIST_ID}/members'
    headers = {
        'Authorization': f'Bearer {MAILCHIMP_API_KEY}',
        'Content-Type': 'application/json'
    }

    # Prepare the address for Mailchimp format
    mailchimp_address = {
        "addr1": address.get("line1", "N/A"),
        "addr2": address.get("line2", ""),
        "city": address.get("city", ""),
        "state": address.get("state", ""),
        "zip": address.get("postal_code", ""),
        "country": address.get("country", "UK")
    }

    data = {
        'email_address': email,
        'status': 'subscribed',
        'merge_fields': {
            'FNAME': first_name,
            'LNAME': last_name,
            'DONATION': amount,
            'ADDRESS': mailchimp_address
        }
    }

    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        print(f"Added {email} to Mailchimp.")
    else:
        print(f"Failed to add {email}: {response.text}")

if __name__ == '__main__':
    app.run(port=5000)
