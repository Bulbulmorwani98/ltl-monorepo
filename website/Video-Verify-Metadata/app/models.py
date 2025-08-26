from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Enum, Boolean, JSON
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from enum import Enum as PyEnum
from sqlalchemy.dialects.postgresql import UUID
import uuid

db = SQLAlchemy()

class PaymentStatusEnum(PyEnum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"

class User(db.Model):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    authid = Column(String(100), nullable=False)
    auth_type = Column(String(50), nullable=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    image_profile = Column(String(500), nullable=True)
    open_id = Column(String(100), nullable=False)
    stripe_customer_id = Column(String(100), nullable=False, unique=True)

class Product(db.Model):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True, autoincrement=True)
    price_id = Column(String(100), nullable=False, unique=True)
    product_id = Column(String(100), nullable=False, unique=True)
    product_name = Column(String(100), nullable=False)
    description = Column(String(100), nullable=True)
    product_price = Column(Float, nullable=False)
    price_type = Column(String(50), nullable=True)
    billing_scheme = Column(String(50), nullable=True)
    duration = Column(String(50), nullable=False)
    update_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_active = Column(Boolean, nullable=True, default=True)

class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(String(100), unique=True, nullable=False)
    auth_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    invoice_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    complete_date = Column(DateTime, nullable=True)
    total_amount = Column(Float, nullable=False)

class InvoiceDetails(db.Model):
    __tablename__ = 'invoice_details'

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    currency = Column(String(10), nullable=False)
    tax_id = Column(Integer, ForeignKey('tax_rates.id'), nullable=True)

class TaxRates(db.Model):
    __tablename__ = 'tax_rates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tax_id = Column(String(100), nullable=True, default=None)
    tax_name = Column(String(50), nullable=False)
    tax_rate = Column(Float, nullable=False)
    subscription_id = Column(String(100), nullable=True, default=None)

class Payment(db.Model):
    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    invoice_id = Column(Integer, ForeignKey('invoices.id'), nullable=False)
    payment_status = Column(String(15), default=PaymentStatusEnum.PENDING)
    payment_id = Column(String(100), unique=True, nullable=False)
    payment_date = Column(DateTime, default=datetime.utcnow)
    payment_amount = Column(Float, nullable=False)
    refund_status = Column(String(15), nullable=True, default=None)
    method_id = Column(Integer, ForeignKey('payment_methods.id'), nullable=False)
    status_id = Column(Integer, ForeignKey('payment_status.id'), nullable=False)
    subscription_id = Column(String(100), nullable=True, default=None)
    is_subscription = Column(Boolean, nullable=True, default=True)
    user = db.relationship('User', backref='user_payment')
    product = db.relationship('Product', backref='payments')

    status = db.relationship('PaymentStatus', backref='payment_status')

class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'

    id = Column(Integer, primary_key=True, autoincrement=True)
    method_id = Column(String(50), unique=True, nullable=True)
    method_name = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)

class PaymentStatus(db.Model):
    __tablename__ = 'payment_status'

    id = Column(Integer, primary_key=True, autoincrement=True)
    status_name = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    subscription_id = Column(String(100), nullable=True, default=None)
    
   
class PaymentLogs(db.Model):
    __tablename__ = 'payment_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    log_id = Column(Integer, unique=True, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    log_message = Column(String(255), nullable=True)
    payment_id = Column(Integer, ForeignKey('payments.id'), nullable=False)


class PaymentRefund(db.Model):
    __tablename__ = 'payment_refund'

    id = Column(Integer, primary_key=True, autoincrement=True)
    refund_id = Column(String(50), unique=True, nullable=True)
    charge_id = Column(String(50), nullable=True)
    refund_status = Column(String(50), nullable=False)
    balance_transaction = Column(String(100), nullable=True)
    inten_id = Column(String(50), nullable=False)
    reference_status = Column(String(50), nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    refund_date = Column(DateTime, nullable=True, default=datetime.utcnow)

class Usercontent(db.Model):
    _tablename_ = 'user_contents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    image_url = Column(String(500), nullable=True)
    video_url = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    meta_data = Column(JSON, nullable=True)

    user = db.relationship('User', backref='user_contents') 


class MetaConfiguration(db.Model):
    __tablename__ = 'meta_configuration'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    meta_info = Column(JSON, nullable=False)

    user = db.relationship('User', backref='meta_configuration')

class ImageStatus(db.Model):
    __tablename__ = 'image_status'

    id = Column(Integer, primary_key=True, autoincrement=True)
    image_name = Column(String(100), nullable=True)
    image_status = Column(String(50), nullable=True)
    upload_date = Column(DateTime, nullable=True, default=datetime.utcnow)
    image_url = Column(String(500), nullable=True)
    meta_data = Column(JSON, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    user = db.relationship('User', backref='image_status') 

class TaskLog(db.Model):
    """Model to store Celery task logs."""
    __tablename__ = 'image_task_logs'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    result = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)