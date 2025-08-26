import logging
import os
import stripe

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