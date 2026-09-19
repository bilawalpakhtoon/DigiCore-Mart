from datetime import datetime
import json
import os
from flask import Flask, Response, jsonify, request
import gspread
from google.oauth2.service_account import Credentials
import requests

app = Flask(__name__)

# --- ROOT & PING ROUTES FOR CRON-JOB ---
@app.route('/')
def home():
    return 'CoreCart WhatsApp Bot is running successfully!'


@app.route('/ping')
def ping():
    return 'Server is alive!', 200


# --- FULLY HARDCODED CONFIGURATIONS ---
WHATSAPP_API_URL = 'https://graph.facebook.com/v25.0'
PHONE_NUMBER_ID = '1247446061793133'
WABA_ID = '1721301722295525'
ACCESS_TOKEN = 'EAAPODuoaelgBSh5mPSTRFFqPZCmZB5wTzbgzwMtVLNJNTE0SelPSIqlZA9aVd4jrqMXlyZBO79dghZCM7ZBm1yELNQkvdZBZBaF8Q9yLOlZBlJgsuffoQZA2wTJ6afmYmKeHwPrrUVIqoKYgxlkKxuepvL2LiLvZAb7ZC7qUpVWT0OiM6YZAdv3OTxwJ7TrZCN8HqBi4le4gZDZD'
VERIFY_TOKEN = 'bilawalpakhtoon530'
WEBHOOK_URL = 'https://corecart-bot-d71de.containers.snapdeploy.app/webhook'

# --- GOOGLE SHEETS SETUP VIA GOOGLE-AUTH & ENVIRONMENT JSON ---
scope = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive',
]

sheet_obj = None
try:
    creds_json_str = os.getenv('GOOGLE_CREDENTIALS_JSON')
    if creds_json_str:
        creds_dict = json.loads(creds_json_str)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        SPREADSHEET_NAME = 'CoreCart_Orders'
        sheet_obj = client.open(SPREADSHEET_NAME)
        print('[GOOGLE SHEETS] Successfully connected to spreadsheet!')
    else:
        print('[GOOGLE SHEETS WARNING] GOOGLE_CREDENTIALS_JSON environment variable is missing!')
except Exception as e:
    print(f'[GOOGLE SHEETS INITIALIZATION ERROR]: {e}')


# --- 1. AUTOMATIC PHONE NUMBER FORMATTING (E.164 Standard) ---
def format_phone_number(raw_phone: str) -> str:
    if not raw_phone:
        return ''
    digits = ''.join(filter(str.isdigit, raw_phone))

    if digits.startswith('0') and len(digits) == 11:
        digits = '92' + digits[1:]
    elif len(digits) == 10:
        digits = '92' + digits

    return digits


# --- 2. DUPLICATE CHECKER VIA GSPREAD ---
def check_order_exists(order_id: str) -> bool:
    if not sheet_obj:
        return False
    try:
        for tab_name in ['Confirmed Orders', 'Cancelled Orders']:
            try:
                worksheet = sheet_obj.worksheet(tab_name)
                cell = worksheet.find(str(order_id))
                if cell:
                    return True
            except gspread.exceptions.CellNotFound:
                continue
            except Exception:
                pass
        return False
    except Exception as e:
        print(f'[GOOGLE SHEET CHECK ERROR]: {e}')
        return False


# --- 3. GOOGLE SHEET MANAGER VIA GSPREAD ---
def update_google_sheet(phone_number: str, order_id: str, status: str):
    if not sheet_obj:
        print('[GOOGLE SHEET ERROR] Sheet object is not initialized.')
        return
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        if status == 'Cancelled':
            worksheet = sheet_obj.worksheet('Cancelled Orders')
        else:
            worksheet = sheet_obj.worksheet('Confirmed Orders')

        worksheet.append_row(
            [str(order_id), str(phone_number), str(status), str(current_time)]
        )
        print(f"[GOOGLE SHEET SUCCESS] Order {order_id} recorded as '{status}'.")
    except Exception as e:
        print(f'[GOOGLE SHEET ERROR] Failed to update Google Sheet: {e}')


# --- 4. WHATSAPP TEMPLATE SENDER FUNCTIONS ---
def send_order_confirmation_button(
    phone_number: str, customer_name: str, order_id: str, total_amount: str
):
    print(f'[DEBUG] Sending confirmation button template to: {phone_number}')
    endpoint = f'{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages'

    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json',
    }

    payload = {
        'messaging_product': 'whatsapp',
        'to': phone_number,
        'type': 'template',
        'template': {
            'name': 'confirmation',
            'language': {'code': 'en'},
            'components': [{
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': str(customer_name)},
                    {'type': 'text', 'text': str(order_id)},
                    {'type': 'text', 'text': str(total_amount)},
                ],
            }],
        },
    }

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(f'[WHATSAPP SUCCESS] Confirmation template sent to {phone_number}')
    except Exception as e:
        print(f'[WHATSAPP ERROR] Failed to send message: {e}')
        if hasattr(e, 'response') and e.response is not None:
            print(f'[META ERROR DETAILS]: {e.response.text}')


def send_success_reply_template(
    phone_number: str, customer_name: str, order_id: str
):
    endpoint = f'{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages'
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json',
    }
    payload = {
        'messaging_product': 'whatsapp',
        'to': phone_number,
        'type': 'template',
        'template': {
            'name': 'confirm',
            'language': {'code': 'en'},
            'components': [{
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': str(customer_name)},
                    {'type': 'text', 'text': str(order_id)},
                ],
            }],
        },
    }
    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f'[WHATSAPP ERROR] Failed to send success reply: {e}')
        if hasattr(e, 'response') and e.response is not None:
            print(f'[META ERROR DETAILS]: {e.response.text}')


def send_cancel_reply_template(
    phone_number: str, customer_name: str, order_id: str
):
    endpoint = f'{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages'
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json',
    }
    payload = {
        'messaging_product': 'whatsapp',
        'to': phone_number,
        'type': 'template',
        'template': {
            'name': 'cancel',
            'language': {'code': 'en'},
            'components': [{
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': str(customer_name)},
                    {'type': 'text', 'text': str(order_id)},
                ],
            }],
        },
    }
    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f'[WHATSAPP ERROR] Failed to send cancel reply: {e}')
        if hasattr(e, 'response') and e.response is not None:
            print(f'[META ERROR DETAILS]: {e.response.text}')


def send_order_dispatch_template(
    phone_number: str,
    customer_name: str,
    order_id: str,
    amount: str,
    tracking_number: str,
    courier_name: str,
):
    endpoint = f'{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages'
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json',
    }

    body_parameters = [
        {'type': 'text', 'text': str(customer_name)},
        {'type': 'text', 'text': str(order_id)},
        {'type': 'text', 'text': str(amount)},
        {'type': 'text', 'text': str(tracking_number)},
        {'type': 'text', 'text': str(courier_name)},
    ]

    payload = {
        'messaging_product': 'whatsapp',
        'to': phone_number,
        'type': 'template',
        'template': {
            'name': 'dispatch',
            'language': {'code': 'en'},
            'components': [{
                'type': 'body',
                'parameters': body_parameters,
            }],
        },
    }

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(f'[WHATSAPP SUCCESS] Order Dispatch template sent to {phone_number}')
    except Exception as e:
        print(f'[WHATSAPP ERROR] Failed to send dispatch message: {e}')
        if hasattr(e, 'response') and e.response is not None:
            print(f'[META ERROR DETAILS]: {e.response.text}')


def send_delivery_feedback_template(
    phone_number: str, customer_name: str, order_id: str
):
    endpoint = f'{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages'
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json',
    }
    payload = {
        'messaging_product': 'whatsapp',
        'to': phone_number,
        'type': 'template',
        'template': {
            'name': 'feedback',
            'language': {'code': 'en'},
            'components': [{
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': str(customer_name)},
                    {'type': 'text', 'text': str(order_id)},
                ],
            }],
        },
    }
    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(f'[WHATSAPP SUCCESS] Feedback template sent to {phone_number}')
    except Exception as e:
        print(f'[WHATSAPP ERROR] Failed to send feedback message: {e}')
        if hasattr(e, 'response') and e.response is not None:
            print(f'[META ERROR DETAILS]: {e.response.text}')


# --- 5. INVALID TEXT MESSAGE HANDLER ---
def send_guidance_message(phone_number: str):
    endpoint = f'{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages'
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json',
    }
    payload = {
        'messaging_product': 'whatsapp',
        'to': phone_number,
        'type': 'text',
        'text': {
            'body': (
                "Kindly use the 'Confirm Order' or 'Cancel Order' buttons"
                ' provided in the message above to process your order. 😊'
            )
        },
    }
    try:
        requests.post(endpoint, json=payload, headers=headers, timeout=10)
        print(f'[GUIDANCE SENT] Sent helper text to {phone_number}')
    except Exception as e:
        print(f'[ERROR] Failed to send guidance text: {e}')


# --- 6. SMART TEST ROUTES FOR ALL TEMPLATES ---
@app.route('/test-confirmation', methods=['GET'])
def test_confirmation():
    phone = format_phone_number(request.args.get('phone', '923276878958'))
    name = request.args.get('name', 'Bilawal')
    order_id = request.args.get('order_id', 'Z-1001')
    total = request.args.get('total', '2999')

    if not phone:
        return jsonify({'status': 'error', 'message': 'Phone number is invalid or missing.'}), 400

    try:
        send_order_confirmation_button(phone, name, order_id, total)
        update_google_sheet(phone, order_id, 'Pending Test')
        return jsonify({'status': 'success', 'message': 'Confirmation template test sent!', 'order_id': order_id}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/test-confirm-reply', methods=['GET'])
def test_confirm_reply():
    phone = format_phone_number(request.args.get('phone', '923276878958'))
    name = request.args.get('name', 'Bilawal')
    order_id = request.args.get('order_id', 'Z-1001')

    try:
        send_success_reply_template(phone, name, order_id)
        update_google_sheet(phone, order_id, 'Confirmed')
        return jsonify({'status': 'success', 'message': 'Confirm reply template test sent!', 'order_id': order_id}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/test-cancel-reply', methods=['GET'])
def test_cancel_reply():
    phone = format_phone_number(request.args.get('phone', '923276878958'))
    name = request.args.get('name', 'Bilawal')
    order_id = request.args.get('order_id', 'Z-1001')

    try:
        send_cancel_reply_template(phone, name, order_id)
        update_google_sheet(phone, order_id, 'Cancelled')
        return jsonify({'status': 'success', 'message': 'Cancel reply template test sent!', 'order_id': order_id}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/test-dispatch', methods=['GET'])
def test_dispatch():
    phone = format_phone_number(request.args.get('phone', '923276878958'))
    name = request.args.get('name', 'Bilawal')
    order_id = request.args.get('order_id', 'Z-1001')
    amount = request.args.get('amount', '2500')
    tracking = request.args.get('tracking', '142334252345234')
    courier = request.args.get('courier', 'PostEx')

    try:
        send_order_dispatch_template(phone, name, order_id, amount, tracking, courier)
        update_google_sheet(phone, order_id, 'Dispatched')
        return jsonify({'status': 'success', 'message': 'Dispatch template test sent!', 'order_id': order_id}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/test-feedback', methods=['GET'])
def test_feedback():
    phone = format_phone_number(request.args.get('phone', '923276878958'))
    name = request.args.get('name', 'Bilawal')
    order_id = request.args.get('order_id', 'Z-1001')

    try:
        send_delivery_feedback_template(phone, name, order_id)
        update_google_sheet(phone, order_id, 'Delivered')
        return jsonify({'status': 'success', 'message': 'Feedback template test sent!', 'order_id': order_id}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


# --- 7. SHOPIFY WEBHOOK ROUTE ---
@app.route('/shopify-order', methods=['POST'])
def handle_shopify_order():
    order_data = request.get_json(silent=True)
    if not order_data:
        return jsonify({'status': 'error', 'message': 'No JSON payload received'}), 400

    try:
        customer_name = (
            order_data.get('customer', {}).get('first_name', 'Valued Customer')
        )
        raw_phone = order_data.get('shipping_address', {}).get('phone') or order_data.get(
            'customer', {}
        ).get('phone', '')

        phone_number = format_phone_number(raw_phone)
        order_id = str(order_data.get('name', 'Z-000000'))
        total_price = str(order_data.get('total_price', '0'))

        if phone_number:
            if check_order_exists(order_id):
                print(f'[DUPLICATE BLOCKED] Order {order_id} is already processed. Skipping message.')
            else:
                send_order_confirmation_button(phone_number, customer_name, order_id, total_price)
                update_google_sheet(phone_number, order_id, 'Pending Shopify')
        else:
            print('[WARNING] Phone number missing in Shopify order payload.')

    except Exception as e:
        print(f'[SHOPIFY ERROR] {e}')

    return jsonify({'status': 'received'}), 200


# --- 8. META WEBHOOK ROUTE ---
@app.route('/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        print(f'[WEBHOOK GET] Mode: {mode}, Token Received: {token}')

        if mode and token:
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                print('[VERIFY SUCCESS] Tokens matched perfectly!')
                return Response(str(challenge), status=200, mimetype='text/plain')
            else:
                print(f"[VERIFY FAILED] Expected '{VERIFY_TOKEN}', got '{token}'")
                return 'Verification failed: Token mismatch', 403
        return 'Verification failed: Missing parameters', 400

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'status': 'success'}), 200

    try:
        entries = data.get('entry', [])
        for entry in entries:
            for change in entry.get('changes', []):
                value = change.get('value', {})
                messages = value.get('messages', [])

                if not messages and 'statuses' in value:
                    continue

                for msg in messages:
                    sender_phone = msg.get('from')
                    msg_type = msg.get('type')
                    customer_name = (
                        value.get('contacts', [{}])[0]
                        .get('profile', {})
                        .get('name', 'Customer')
                    )

                    if msg_type == 'interactive':
                        reply_id = msg['interactive']['button_reply']['id']
                        print(f'[BUTTON CLICKED] ID: {reply_id} from {sender_phone}')

                        if reply_id.startswith('confirm_'):
                            order_id = reply_id.replace('confirm_', '')
                            update_google_sheet(sender_phone, order_id, 'Confirmed')
                            send_success_reply_template(sender_phone, customer_name, order_id)

                        elif reply_id.startswith('cancel_'):
                            order_id = reply_id.replace('cancel_', '')
                            update_google_sheet(sender_phone, order_id, 'Cancelled')
                            send_cancel_reply_template(sender_phone, customer_name, order_id)

                    elif msg_type == 'text':
                        print(f'[TEXT RECEIVED] Non-button text from {sender_phone}')
                        send_guidance_message(sender_phone)

    except Exception as e:
        print(f'[META WEBHOOK ERROR] {e}')

    return jsonify({'status': 'success'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

