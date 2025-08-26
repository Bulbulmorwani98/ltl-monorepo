import logging
import os
from flask import(
    session,
    redirect,
    url_for
) 
import stripe
from models import db
import models as user_models
from datetime import datetime


logger = logging.getLogger(__name__)


class StripeSubscriptionManager:
    def __init__(self):
        # Set up the Stripe client with your secret key
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        self.base_url = os.getenv("BASE_URL")

    def create_customer(self, email, name):
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
            )
            logger.info(f"Customer created: {customer.id}")
            return customer.id
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e.user_message}")
            return None

    def create_product_and_price(self):
        product = stripe.Product.create(name="Premium Subscription")
        price = stripe.Price.create(
            unit_amount=1000,  # Price in cents (e.g., $10.00)
            currency="usd",
            recurring={"interval": "month"},  # Monthly subscription
            product=product.id,
        )
        return price

    def get_price_list(self):
        try: 
            price_list = stripe.Price.list()
            logger.debug(f"Price list: {price_list}")

            active_prices = [price for price in price_list.data if price.active]
            logger.debug(f"Active prices: {active_prices}")

            for price in active_prices:
                if price.unit_amount is None:
                    logger.warning(f"Price {price.id} has unit_amount as None. Setting to 0.")
                    price.unit_amount = 0 #maybe this should error out instead?
            return active_prices, 200
        except stripe.error.StripeError as e:
            status_code = e.http_status
            logger.error(f"Stripe error: {e.user_message}")
            return None, status_code

    def get_product(self, product_id):
        try:
            product = stripe.Product.retrieve(product_id)
            logger.debug(f"Retrieved product: {product}")

            # Check if the product is active
            if not product.active:
                logger.warning(f"Product {product.id} is inactive.")
                return None, 200 # should this 404?  I think no?

            return product, 200
        except stripe.error.StripeError as e:
            status_code = e.http_status
            logger.error(f"Stripe error: {e.user_message}")
            return None, status_code

    def list_subscriptions(self):
        subscriptions = stripe.Subscription.list()
        for subscription in subscriptions.data:
            logger.info(
                f"Subscription ID: {subscription.id}, Status: {subscription.status}"
            )
        return subscriptions

    def create_checkout_session(self, customer_id, price_id):
        try:
            # Create a Checkout Session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                customer=customer_id,
                line_items=[
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                mode="subscription",  # This is for subscriptions
                success_url="https://dev.ltlprotect.com/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url="https://dev.ltlprotect.com/cancel",
            )
            logger.info(f"Checkout session created: {session.id}")
            return session
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e.user_message}")
            return None
          
    def retrieve_checkout_session(self, session_id):
        try:
            # Retrieve session details from Stripe using the session ID
            session = stripe.checkout.Session.retrieve(session_id)
            logger.info(f"Session ID: {session.id}")
            logger.info(f"Customer ID: {session.customer}")
            logger.info(f"Subscription ID: {session.subscription}")
            logger.info(f"Amount Total: {session.amount_total}")
            logger.info(f"Status: {session.payment_status}")
            return session
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving session: {e.user_message}")
            return None
    def get_invoice(self, invoice_id):
        invoice = stripe.Invoice.retrieve(invoice_id)
        return invoice


    def cancel_subscription(self, subscription_id):
        try:
            cancel_sub = stripe.Subscription.cancel(subscription_id)
            return cancel_sub
        except Exception as e:
            return None
    
    def refund_request(self, payment_id, user_email):
       
        stripe_refund, status = self.create_refund(intent_id=payment_id)
        if stripe_refund:
            transaction_id = stripe_refund.get("balance_transaction")
            charge_id = stripe_refund.get("charge")
            refund_id = stripe_refund.get("id")
            refund_status = stripe_refund.get("status")
            reference_status = (
                stripe_refund.get("destination_details").get("card").get("reference_status")
            )

            user = db.session.query(user_models.User).filter_by(email=user_email).first()

            db_refund = (
                db.session.query(user_models.PaymentRefund).filter_by(inten_id=payment_id).first()
            )
            if db_refund:
                db_refund.refund_status = refund_status
                db.session.commit()
            else:
                paymentrefund = user_models.PaymentRefund(
                    refund_id=refund_id,
                    charge_id=charge_id,
                    refund_status=refund_status,
                    balance_transaction=transaction_id,
                    inten_id=payment_id,
                    reference_status=reference_status,
                    user_id=user.id,
                    refund_date=datetime.utcnow()
                )
                db.session.add(paymentrefund)
                db.session.commit()

            # Find the existing payment record by payment_id
            db_payment = (
                db.session.query(user_models.Payment)
                .filter_by(payment_id=payment_id)
                .first()
            )

            if db_payment:
                # Update the refund_status
                db_payment.refund_status = refund_status
            else:
                # If no record exists, create a new one
                db_payment = user_models.Payment(
                    payment_id=payment_id, refund_status=refund_status
                )
                db.session.add(db_payment)

            # Commit the changes
            db.session.commit()
            return True
        else:
            return False
        
    def create_refund(self, intent_id):
        try:
            req_refund = stripe.Refund.create(payment_intent=intent_id)
            return req_refund, 200
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving session: {e.user_message}")
            return None, e.user_message
