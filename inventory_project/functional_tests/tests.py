import os
import shutil
import tempfile

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from playwright.sync_api import sync_playwright

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

TEST_MEDIA_ROOT = tempfile.mkdtemp()

# Smallest valid GIF image, used for uploads.
SMALL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
    b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01"
    b"\x00\x00\x02\x02D\x01\x00;"
)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class NewProductTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.page = self.browser.new_page()
        self.image_dir = tempfile.mkdtemp()
        self.image_path = os.path.join(self.image_dir, "laptop.gif")
        with open(self.image_path, "wb") as f:
            f.write(SMALL_GIF)

    def tearDown(self):
        self.page.close()
        shutil.rmtree(self.image_dir, ignore_errors=True)

    def fill_product_form(self, name, price, description, quantity):
        self.page.fill("input[name=name]", name)
        self.page.fill("input[name=price]", price)
        self.page.fill("textarea[name=description]", description)
        self.page.fill("input[name=quantity]", quantity)

    def test_can_add_a_product_with_an_image(self):
        # Anna manages a small shop. She opens the product list
        self.page.goto(f"{self.live_server_url}/products/")
        self.assertIn("Product List", self.page.title())

        # She clicks "Add Product"
        self.page.click("text=Add Product")
        self.assertIn("Create Product", self.page.title())

        # She fills in a laptop, chooses a picture and saves
        self.fill_product_form("Laptop", "999.99", "A fast laptop", "5")
        self.page.set_input_files("input[name=image]", self.image_path)
        self.page.click("text=Save Product")

        # She is sent back to the list and sees her laptop there
        self.page.wait_for_url(f"{self.live_server_url}/products/")
        self.assertIn("Laptop", self.page.locator("h2").all_inner_texts())

    # POSSIBLE BUG: a product saved without an image makes product.image.url
    # crash in product_list.html, so the list page shows "Server Error (500)"
    def test_can_add_a_product_without_an_image(self):
        # Anna opens the "Add Product" page
        self.page.goto(f"{self.live_server_url}/create/")

        # She fills in a mouse but forgets to choose a picture, and saves
        self.fill_product_form("Mouse", "19.99", "A wireless mouse", "10")
        self.page.click("text=Save Product")

        # She expects to see the product list with her mouse in it
        self.page.wait_for_url(f"{self.live_server_url}/products/")
        self.assertNotIn("Server Error", self.page.content())
        self.assertIn("Mouse", self.page.locator("h2").all_inner_texts())
