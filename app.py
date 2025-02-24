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
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400

    # Handle relevant Stripe events
    if event['type'] in ['checkout.session.completed', 'charge.succeeded']:
        session = event['data']['object']

        # Extract billing details
        billing_details = session.get('billing_details', {})
        address = billing_details.get('address', {})

        # Extract customer data
        email = billing_details.get('email', None)
        full_name = billing_details.get('name', 'Unknown')
        amount = session.get('amount', 0) / 100  # Convert from cents/pence to currency

        # Skip if email is missing
        if not email:
            print("⚠️ No email provided. Skipping Mailchimp addition.")
            return jsonify({'status': 'no email'}), 200

        # Split full name into first and last names
        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        # Prepare the address for Mailchimp
        mailchimp_address = {
            "addr1": address.get("line1", "N/A"),  # Required field
            "addr2": address.get("line2", ""),
            "city": address.get("city", ""),
            "state": address.get("state", ""),
            "zip": address.get("postal_code", ""),
            "country": address.get("country", "GB")  # Default to GB if missing
        }

        # Send data to Mailchimp
        add_to_mailchimp(email, first_name, last_name, amount, mailchimp_address)

        return jsonify({'status': 'success'}), 200

    return jsonify({'status': 'ignored event type'}), 200

def add_to_mailchimp(email, first_name, last_name, amount, address):
    url = f'https://{MAILCHIMP_SERVER_PREFIX}.api.mailchimp.com/3.0/lists/{MAILCHIMP_LIST_ID}/members'
    headers = {
        'Authorization': f'Bearer {MAILCHIMP_API_KEY}',
        'Content-Type': 'application/json'
    }

    # Prepare Mailchimp data payload
    data = {
        'email_address': email,
        'status': 'subscribed',
        'merge_fields': {
            'FNAME': first_name,
            'LNAME': last_name,
            'DONATION': amount,
            'ADDRESS': address
        }
    }

    # Send to Mailchimp
    response = requests.post(url, json=data, headers=headers)
    if response.status_code in [200, 204]:
        print(f"✅ Successfully added {email} to Mailchimp.")
    else:
        print(f"❌ Failed to add {email} to Mailchimp: {response.text}")

if __name__ == '__main__':
    app.run(port=5000)
