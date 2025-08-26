# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.contrib.auth.models import BaseUserManager,AbstractBaseUser,PermissionsMixin

class AlembicVersion(models.Model):
    version_num = models.CharField(primary_key=True, max_length=32)

    class Meta:
        managed = False
        db_table = 'alembic_version'

class Users(AbstractBaseUser):
    authid = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, max_length=100)
    open_id = models.CharField(max_length=100)
    stripe_customer_id = models.CharField(unique=True, max_length=100)
    auth_type = models.CharField(max_length=50, blank=True, null=True)
    image_profile = models.CharField(max_length=500, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    last_login = models.DateTimeField(blank=True, null=True)
    

    # You can add this if you need to support tokens like RefreshToken.for_user(user)
    password = models.CharField(max_length=128, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'
        managed = True  # Don't let Django try to create/alter this table

    def __str__(self):
        return self.email

class Usercontent(models.Model):
    user = models.ForeignKey('Users', models.DO_NOTHING)
    image_url = models.CharField(max_length=500, blank=True, null=True)
    video_url = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'usercontent'

class MetaConfiguration(models.Model):
    user = models.ForeignKey('Users', models.DO_NOTHING)
    meta_info = models.TextField()  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'meta_configuration'

class ImageStatus(models.Model):
    image_name = models.CharField(max_length=100, blank=True, null=True)
    image_status = models.CharField(max_length=50, blank=True, null=True)
    upload_date = models.DateTimeField(blank=True, null=True)
    user = models.ForeignKey('Users', models.DO_NOTHING)
    image_url = models.CharField(max_length=500, blank=True, null=True)
    meta_data = models.TextField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'image_status'


class ImageTaskLogs(models.Model):
    task_id = models.CharField(unique=True, max_length=50)
    status = models.CharField(max_length=20)
    result = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'image_task_logs'


class InvoiceDetails(models.Model):
    invoice = models.ForeignKey('Invoices', models.DO_NOTHING)
    product = models.ForeignKey('Products', models.DO_NOTHING)
    currency = models.CharField(max_length=10)
    tax = models.ForeignKey('TaxRates', models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'invoice_details'


class Invoices(models.Model):
    invoice_id = models.CharField(unique=True, max_length=100)
    auth = models.ForeignKey('Users', models.DO_NOTHING)
    invoice_date = models.DateTimeField()
    complete_date = models.DateTimeField(blank=True, null=True)
    total_amount = models.FloatField()

    class Meta:
        managed = False
        db_table = 'invoices'

class PaymentLogs(models.Model):
    log_id = models.IntegerField(unique=True)
    timestamp = models.DateTimeField()
    log_message = models.CharField(max_length=255, blank=True, null=True)
    payment = models.ForeignKey('Payments', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'payment_logs'


class PaymentMethods(models.Model):
    method_id = models.CharField(unique=True, max_length=50, blank=True, null=True)
    method_name = models.CharField(max_length=50)
    description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'payment_methods'


class PaymentRefund(models.Model):
    refund_id = models.CharField(unique=True, max_length=50, blank=True, null=True)
    charge_id = models.CharField(max_length=50, blank=True, null=True)
    refund_status = models.CharField(max_length=50)
    balance_transaction = models.CharField(max_length=100, blank=True, null=True)
    inten_id = models.CharField(max_length=50)
    reference_status = models.CharField(max_length=50, blank=True, null=True)
    user = models.ForeignKey('Users', models.DO_NOTHING)
    refund_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'payment_refund'


class PaymentStatus(models.Model):
    status_name = models.CharField(max_length=50)
    description = models.CharField(max_length=255, blank=True, null=True)
    subscription_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'payment_status'


class Payments(models.Model):
    user = models.ForeignKey('Users', models.DO_NOTHING)
    product = models.ForeignKey('Products', models.DO_NOTHING)
    invoice = models.ForeignKey(Invoices, models.DO_NOTHING)
    payment_status = models.CharField(max_length=15, blank=True, null=True)
    payment_id = models.CharField(unique=True, max_length=100)
    payment_date = models.DateTimeField(blank=True, null=True)
    payment_amount = models.FloatField()
    method = models.ForeignKey(PaymentMethods, models.DO_NOTHING)
    status = models.ForeignKey(PaymentStatus, models.DO_NOTHING)
    refund_status = models.CharField(max_length=15, blank=True, null=True)
    subscription_id = models.CharField(max_length=100, blank=True, null=True)
    is_subscription = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'payments'


class Products(models.Model):
    price_id = models.CharField(unique=True, max_length=100)
    product_id = models.CharField(unique=True, max_length=100)
    product_name = models.CharField(max_length=100)
    description = models.CharField(max_length=100, blank=True, null=True)
    product_price = models.FloatField()
    duration = models.CharField(max_length=50)
    update_date = models.DateTimeField()
    price_type = models.CharField(max_length=50, blank=True, null=True)
    billing_scheme = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'products'


class TaxRates(models.Model):
    tax_id = models.CharField(max_length=100, blank=True, null=True)
    tax_name = models.CharField(max_length=50)
    tax_rate = models.FloatField()
    subscription_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tax_rates'
