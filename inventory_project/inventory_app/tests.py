import inspect
import io
import re
import shutil
import tempfile

from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import get_template, render_to_string
from django.test import Client, TestCase, override_settings
from PIL import Image

from inventory_app.models import Product

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


def make_image(name="test.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def valid_product_data(**overrides):
    data = {
        "name": "Laptop",
        "price": "999.99",
        "description": "A good laptop",
        "quantity": "5",
        "image": make_image(),
    }
    data.update(overrides)
    return data


def create_product(**overrides):
    fields = {
        "name": "Phone",
        "price": "100.00",
        "image": "products/phone.png",
        "description": "A phone",
        "quantity": 3,
    }
    fields.update(overrides)
    return Product.objects.create(**fields)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class InventoryTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        # Return 500 responses instead of raising, so crashes show up as failures
        self.client.raise_request_exception = False

    def log_in_user_without_permissions(self):
        user = User.objects.create_user(username="plainuser", password="pass12345")
        self.client.force_login(user)


# ---------------------------------------------------------------------------
# A. Security and access control
# ---------------------------------------------------------------------------


class ProductCreateAccessTest(InventoryTestCase):
    def test_anonymous_user_cannot_open_create_page(self):
        response = self.client.get("/create/")
        # POSSIBLE BUG: product_create has no @login_required, anyone sees the form
        self.assertNotEqual(response.status_code, 200)

    def test_anonymous_user_cannot_create_product(self):
        self.client.post("/create/", data=valid_product_data())
        # POSSIBLE BUG: product_create has no @login_required, anyone can add products
        self.assertEqual(Product.objects.count(), 0)

    def test_user_without_add_permission_cannot_create_product(self):
        self.log_in_user_without_permissions()
        self.client.post("/create/", data=valid_product_data())
        # POSSIBLE BUG: product_create does not check the add_product permission
        self.assertEqual(Product.objects.count(), 0)


class ProductUpdateAccessTest(InventoryTestCase):
    def test_anonymous_user_cannot_open_update_page(self):
        product = create_product()
        response = self.client.get(f"/update/{product.id}/")
        # POSSIBLE BUG: product_update has no @login_required
        self.assertNotEqual(response.status_code, 200)

    def test_anonymous_user_cannot_update_product(self):
        product = create_product(name="Phone")
        self.client.post(
            f"/update/{product.id}/",
            data={"name": "Hacked", "price": "1", "description": "x", "quantity": "1"},
        )
        product.refresh_from_db()
        # POSSIBLE BUG: product_update has no @login_required, anyone can edit
        self.assertEqual(product.name, "Phone")

    def test_user_without_change_permission_cannot_update_product(self):
        product = create_product(name="Phone")
        self.log_in_user_without_permissions()
        self.client.post(
            f"/update/{product.id}/",
            data={"name": "Hacked", "price": "1", "description": "x", "quantity": "1"},
        )
        product.refresh_from_db()
        # POSSIBLE BUG: product_update does not check the change_product permission
        self.assertEqual(product.name, "Phone")


class ProductDeleteAccessTest(InventoryTestCase):
    def test_anonymous_user_cannot_open_delete_page(self):
        product = create_product()
        response = self.client.get(f"/delete/{product.id}/")
        # POSSIBLE BUG: product_delete has no @login_required
        self.assertNotEqual(response.status_code, 200)

    def test_anonymous_user_cannot_delete_product(self):
        product = create_product()
        self.client.post(f"/delete/{product.id}/")
        # POSSIBLE BUG: product_delete has no @login_required, anyone can delete
        self.assertTrue(Product.objects.filter(id=product.id).exists())

    def test_user_without_delete_permission_cannot_delete_product(self):
        product = create_product()
        self.log_in_user_without_permissions()
        self.client.post(f"/delete/{product.id}/")
        # POSSIBLE BUG: product_delete does not check the delete_product permission
        self.assertTrue(Product.objects.filter(id=product.id).exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SendTestEmailAccessTest(InventoryTestCase):
    def test_anonymous_user_cannot_trigger_email(self):
        self.client.get("/send-test-email/")
        # POSSIBLE BUG: send_test_email is open to everyone, anyone can make the server send mail
        self.assertEqual(len(mail.outbox), 0)


class SecretsInSettingsTest(TestCase):
    def test_secret_key_is_not_the_insecure_default(self):
        # POSSIBLE BUG: SECRET_KEY is the hardcoded 'django-insecure-' key from settings.py
        self.assertFalse(settings.SECRET_KEY.startswith("django-insecure-"))

    def test_email_password_is_not_hardcoded_in_settings(self):
        from inventory_project import settings as settings_module

        source = inspect.getsource(settings_module)
        # POSSIBLE BUG: EMAIL_HOST_PASSWORD is written as a plain string in settings.py
        self.assertIsNone(re.search(r"^EMAIL_HOST_PASSWORD\s*=\s*['\"]", source, re.M))


# ---------------------------------------------------------------------------
# B. Crashes and missing input checks
# ---------------------------------------------------------------------------


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SendTestEmailTest(InventoryTestCase):
    def test_send_test_email_page_renders(self):
        response = self.client.get("/send-test-email/")
        # POSSIBLE BUG: view renders 'Email_Seent.html', but the file is 'email_sent.html'
        self.assertEqual(response.status_code, 200)

    def test_email_sent_page_shows_the_message(self):
        html = render_to_string(
            "email_sent.html", {"message": "Error sending email: connection refused"}
        )
        # POSSIBLE BUG: email_sent.html ignores {{ message }} and always says success
        self.assertIn("connection refused", html)
        self.assertNotIn("Email Sent Successfully!", html)

    def test_home_link_on_email_page_works(self):
        html = render_to_string("email_sent.html", {"message": ""})
        self.assertIn('href="/"', html)
        response = self.client.get("/")
        # POSSIBLE BUG: "Back to Home" links to "/", but no URL is defined for "/"
        self.assertNotEqual(response.status_code, 404)


class ProductWithoutImageTest(InventoryTestCase):
    def test_cannot_create_product_without_image(self):
        data = valid_product_data()
        del data["image"]
        self.client.post("/create/", data=data)
        # POSSIBLE BUG: image is required in the model, but the view saves without it
        self.assertEqual(Product.objects.count(), 0)

    def test_product_list_still_works_after_product_without_image(self):
        data = valid_product_data()
        del data["image"]
        self.client.post("/create/", data=data)
        response = self.client.get("/products/")
        # POSSIBLE BUG: product_list.html calls product.image.url on an empty image -> 500
        self.assertEqual(response.status_code, 200)

    def test_detail_page_works_for_product_without_image(self):
        product = create_product(image="")
        response = self.client.get(f"/product/{product.id}/")
        # POSSIBLE BUG: product_detail.html calls product.image.url on an empty image -> 500
        self.assertEqual(response.status_code, 200)

    def test_update_page_works_for_product_without_image(self):
        product = create_product(image="")
        response = self.client.get(f"/update/{product.id}/")
        # POSSIBLE BUG: product_update.html calls product.image.url on an empty image -> 500
        self.assertEqual(response.status_code, 200)


class ProductCreateValidationTest(InventoryTestCase):
    def test_empty_form_does_not_crash(self):
        response = self.client.post("/create/", data={})
        # POSSIBLE BUG: no validation, saving None into NOT NULL columns -> 500
        self.assertNotEqual(response.status_code, 500)

    def test_negative_quantity_does_not_crash(self):
        response = self.client.post("/create/", data=valid_product_data(quantity="-1"))
        # POSSIBLE BUG: -1 hits the database CHECK constraint -> IntegrityError -> 500
        self.assertNotEqual(response.status_code, 500)

    def test_text_price_does_not_crash(self):
        response = self.client.post("/create/", data=valid_product_data(price="abc"))
        # POSSIBLE BUG: "abc" is passed straight to DecimalField -> ValidationError -> 500
        self.assertNotEqual(response.status_code, 500)

    def test_negative_price_is_rejected(self):
        self.client.post("/create/", data=valid_product_data(price="-50.00"))
        # POSSIBLE BUG: no check on price, a negative price is saved
        self.assertEqual(Product.objects.count(), 0)

    def test_empty_name_is_rejected(self):
        self.client.post("/create/", data=valid_product_data(name=""))
        # POSSIBLE BUG: no check on name, an empty name is saved
        self.assertEqual(Product.objects.count(), 0)


class ProductUpdateValidationTest(InventoryTestCase):
    def test_update_with_missing_fields_does_not_crash(self):
        product = create_product()
        response = self.client.post(f"/update/{product.id}/", data={"name": "New name"})
        # POSSIBLE BUG: missing fields become None and are saved into NOT NULL columns -> 500
        self.assertNotEqual(response.status_code, 500)


# ---------------------------------------------------------------------------
# C. Checked: works correctly (these are expected to pass)
# ---------------------------------------------------------------------------


class CsrfProtectionTest(InventoryTestCase):
    def test_create_without_csrf_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post("/create/", data=valid_product_data())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Product.objects.count(), 0)

    def test_delete_without_csrf_token_is_rejected(self):
        product = create_product()
        client = Client(enforce_csrf_checks=True)
        response = client.post(f"/delete/{product.id}/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.filter(id=product.id).exists())


class DeleteByGetTest(InventoryTestCase):
    def test_get_on_delete_url_does_not_delete(self):
        product = create_product()
        self.client.get(f"/delete/{product.id}/")
        self.assertTrue(Product.objects.filter(id=product.id).exists())


class HtmlEscapingTest(InventoryTestCase):
    def test_product_name_is_escaped_on_list_page(self):
        create_product(name="<script>alert(1)</script>")
        response = self.client.get("/products/")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")


class TemplateFolderTest(TestCase):
    def test_templates_come_from_templates_folder_not_tamplates(self):
        for name in [
            "product_list.html",
            "product_detail.html",
            "product_create.html",
            "product_update.html",
            "product_delete.html",
        ]:
            origin = get_template(name).origin.name
            self.assertIn("templates", origin)
            self.assertNotIn("tamplates", origin)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailSenderTest(InventoryTestCase):
    def test_email_is_built_with_from_and_to_addresses(self):
        # Only checks the message Django builds; whether Gmail accepts a sender
        # different from EMAIL_HOST_USER cannot be checked locally.
        self.client.get("/send-test-email/")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, "boyroyal4853@gmail.com")
        self.assertEqual(mail.outbox[0].to, ["geuvizegebre-9696@yopmail.com"])
