# Inventory App – Bug Report

**Date:** 2026-10-21
**Project:** `inventory/inventory_project` (Django)
**Test files:**
- Unit tests: `inventory_project/inventory_app/tests.py` (Django `TestCase` + test client)
- Functional test: `inventory_project/functional_tests/tests.py` (Playwright + `StaticLiveServerTestCase`)

**How to run:**

```
cd inventory/inventory_project
python manage.py test
```

**Result:** 28 tests ran. 23 fail because of the bugs below. 5 pass: these check normal behaviour (creating a product with valid data, viewing the list, deleting, sending the email, and adding a product with an image in the browser).

Every failing test is marked in the code with `# POSSIBLE BUG: ...`.
No application code was changed.

> Note on the tests: the unit tests use `Client(raise_request_exception=False)`. Because of this, a crash in the app comes back as a "500 Server Error" response, and the test **fails** with a clear message instead of stopping with an exception.

---

## Summary

| # | Bug | Severity | Where |
|---|-----|----------|-------|
| 1 | Email page uses a template name that doesn't exist, so it always crashes | High | `views.py` lines 77, 79 |
| 2 | Email page always says "success", even when sending failed | Medium | `email_sent.html` lines 93–94 |
| 3 | "Back to Home" link goes to a page that doesn't exist (404) | Low | `email_sent.html` line 97, `urls.py` |
| 4 | A product without an image breaks the list, detail and edit pages | **Critical** | `views.py` lines 23–33, templates |
| 5 | An empty or text price crashes the create page | High | `views.py` lines 22, 27 |
| 6 | An empty or text quantity crashes the create page | High | `views.py` lines 25, 27 |
| 7 | A negative quantity crashes the create page | Medium | `views.py` line 25, `models.py` line 9 |
| 8 | Empty name is accepted; a missing name crashes the page | Medium | `views.py` line 21 |
| 9 | The edit page has the same input problems (#5–#8) | High | `views.py` lines 45–53 |
| 10 | A price that is too big is saved, then the list page crashes | **Critical** | `views.py` line 22, `models.py` line 6 |

All file paths below are relative to `inventory/inventory_project/inventory_app/`.

---

## Confirmed bugs

### Bug 1 – The email page always crashes

**In simple words:** When you open `/send-test-email/`, you get a "Server Error (500)" page. The email is actually sent, but the page that should confirm it can't be found.

**Cause in code:** `views.py`, **line 77** and **line 79**:

```python
return render(request, 'Email_Seent.html', {...})
```

The template file is called `templates/email_sent.html`. The view asks for `Email_Seent.html`, which has a capital "E", a capital "S" and a typo ("Seent"). Django raises `TemplateDoesNotExist`. Line 77 is inside `try`, so the `except` catches the error and tries to render the error page on line 79, but that line uses the same wrong name, so it crashes again.

**Tests (fail):**
- `SendTestEmailTest.test_email_page_renders_without_server_error`: got `500`, expected `200`
- `SendTestEmailTest.test_email_page_uses_email_sent_template`: no template was used
- `SendTestEmailTest.test_email_error_page_renders_without_server_error`: got `500`, expected `200` (sending is made to fail on purpose with `mock.patch`)

**Suggested fix:** Use `'email_sent.html'` on lines 77 and 79.

---

### Bug 2 – The email page always says "Email Sent Successfully!"

**In simple words:** Even if the email fails to send, the page shows a green check mark and "Email Sent Successfully!". The user is told everything worked when it didn't.

**Cause in code:** The view passes a `message` to the template (`views.py` lines 77 and 79). It holds either a success text or `"Error sending email: ..."`. But `templates/email_sent.html` **never prints `{{ message }}`**. The success text is hard-coded on **lines 93–94**:

```html
<h1>Email Sent Successfully!</h1>
<p>Your test email has been sent successfully. ...</p>
```

**Tests (fail):** These render the template directly, so they don't depend on Bug 1.
- `EmailSentTemplateTest.test_template_shows_message_from_view`: the error message is not in the page
- `EmailSentTemplateTest.test_template_does_not_claim_success_when_sending_failed`: the page still says "Email Sent Successfully!"

**Suggested fix:** Show `{{ message }}` in the template. Better still, have the view pass a `success` true/false value and change the heading and icon based on it.

---

### Bug 3 – "Back to Home" link leads to a 404 page

**In simple words:** On the email page, the "Back to Home" button sends you to a "Page not found" error.

**Cause in code:** `templates/email_sent.html`, **line 97**: `<a href="/" ...>Back to Home</a>`. Neither `inventory_app/urls.py` nor `inventory_project/urls.py` has a URL pattern for `/`. The product list is at `/products/`.

**Test (fails):**
- `HomePageTest.test_home_page_link_target_exists`: `GET /` returns `404`

**Suggested fix:** Either add a route for `''`, for example one that redirects to `product_list`, or point the link to `{% url 'product_list' %}`.

---

### Bug 4 – A product without an image breaks the website

**In simple words:** If someone adds a product and doesn't choose a picture, the product still gets saved. After that, the **product list page crashes for everyone**, so no one can see any products until the bad product is removed through the admin. That product's detail and edit pages crash too.

**Cause in code:**
- `views.py`, **line 23**: `image = request.FILES.get('image')` returns `None` when no file is chosen.
- `views.py`, **lines 27–33**: `Product.objects.create(...)` saves it anyway. There is no form and no check, and the database stores an empty string for the image.
- The templates then call `product.image.url`, and that raises
  `ValueError: The 'image' attribute has no file associated with it.`
  - `templates/product_list.html`, **line 19**
  - `templates/product_detail.html`, **line 12**
  - `templates/product_update.html`, **line 24**

**Tests (fail):**
- `ProductWithoutImageTest.test_list_page_works_after_adding_product_without_image`: list page returns `500`
- `ProductWithoutImageTest.test_detail_page_works_for_product_without_image`: `500`
- `ProductWithoutImageTest.test_update_page_works_for_product_without_image`: `500`
- **Functional test (Playwright):** `NewProductTest.test_can_add_a_product_without_an_image`. The user fills in the form in a real browser, doesn't choose a picture and clicks "Save Product". The browser then shows **"Server Error (500)"** instead of the product list.

**Suggested fix:** Validate input with a Django `ModelForm` so the image is required, or allow `blank=True` on the field. Also guard the templates with `{% if product.image %}<img ...>{% endif %}`.

---

### Bug 5 – Empty or text price crashes the create page

**In simple words:** If the price field is empty, or contains letters (this can be sent without the browser form), the user sees "Server Error (500)" instead of a friendly "please enter a price" message.

**Cause in code:** `views.py`, **line 22**: `price = request.POST.get('price')` takes the raw text without checking it. **Line 27**: `Product.objects.create(...)` gives it to the `DecimalField`, which raises
`ValidationError: "'' value must be a decimal number."`. Nothing catches this error.

**Tests (fail):**
- `ProductCreateValidationTest.test_empty_price_does_not_crash`: `500`
- `ProductCreateValidationTest.test_text_price_does_not_crash`: `500`

**Suggested fix:** Use a Django `ModelForm` (`form.is_valid()`) and show the form again with error messages.

---

### Bug 6 – Empty or text quantity crashes the create page

**In simple words:** Same as Bug 5, but for the quantity field.

**Cause in code:** `views.py`, **line 25**: `quantity = request.POST.get('quantity')` is not checked. **Line 27** raises
`ValueError: Field 'quantity' expected a number but got ''.`

**Tests (fail):**
- `ProductCreateValidationTest.test_empty_quantity_does_not_crash`: `500`
- `ProductCreateValidationTest.test_text_quantity_does_not_crash`: `500`

**Suggested fix:** Same as Bug 5 (use a `ModelForm`).

---

### Bug 7 – Negative quantity crashes the create page

**In simple words:** Typing `-5` as the quantity gives "Server Error (500)". The HTML field allows negative numbers, so this is easy to do by accident.

**Cause in code:** `models.py`, **line 9**: `quantity = models.PositiveIntegerField()` makes the database reject negative numbers. `views.py` **line 25** doesn't check the value, so the database raises
`IntegrityError: CHECK constraint failed: quantity`, and nothing catches it.

**Test (fails):**
- `ProductCreateValidationTest.test_negative_quantity_does_not_crash`: `500`

**Suggested fix:** Use a `ModelForm`, which checks this automatically. Also add `min="0"` to the quantity input in the template.

---

### Bug 8 – Empty name is accepted; a missing name crashes

**In simple words:**
- With an empty name, a product with **no name** is saved and shows up in the list as a blank entry.
- If the `name` field is missing from the request entirely, the page crashes with a 500 error.

**Cause in code:** `views.py`, **line 21**: `name = request.POST.get('name')` has no check.
- An empty string `''` is saved as is. `CharField` only checks for blanks in forms, not in `objects.create()`.
- A missing field gives `None`, and the database raises `IntegrityError: NOT NULL constraint failed: inventory_app_product.name`.

**Tests (fail):**
- `ProductCreateValidationTest.test_empty_name_is_not_saved`: 1 product was saved, expected 0
- `ProductCreateValidationTest.test_missing_name_field_does_not_crash`: `500`

**Suggested fix:** Use a `ModelForm`. Adding `required` to the HTML input also helps users, but it isn't enough on its own.

---

### Bug 9 – The edit page has the same input problems

**In simple words:** Editing a product has the same problems as creating one. An empty price or quantity, or a negative quantity, gives a server error. An empty name **erases the product's real name**.

**Cause in code:** `views.py`, **lines 45–48** copy raw `request.POST` values straight onto the product, and **line 53** (`product.save()`) saves them without any check.

**Tests (fail):**
- `ProductUpdateValidationTest.test_empty_price_does_not_crash`: `500`
- `ProductUpdateValidationTest.test_empty_quantity_does_not_crash`: `500`
- `ProductUpdateValidationTest.test_negative_quantity_does_not_crash`: `500`
- `ProductUpdateValidationTest.test_empty_name_does_not_overwrite_product_name`: name became `''` instead of staying `'Phone'`

**Suggested fix:** Use the same `ModelForm` with `instance=product`.

---

### Bug 10 – A price that is too big breaks the list page

*(Found while testing; it wasn't in the original plan.)*

**In simple words:** If someone enters a price with more than 10 digits (for example `123456789012.99`), the app saves it without complaint. After that, **the product list page crashes for everyone**, just like Bug 4.

**Cause in code:**
- `models.py`, **line 6**: `price = models.DecimalField(max_digits=10, decimal_places=2)` allows at most 10 digits.
- `views.py`, **line 22 / line 27**: the view doesn't check this limit. SQLite doesn't enforce `max_digits` either, so the too-big value gets saved.
- When Django reads the product back, it tries to fit the number into 10 digits and raises `decimal.InvalidOperation`, so every page that loads products crashes.

**Tests (fail):**
- `ProductCreateValidationTest.test_too_large_price_is_not_saved`: 1 product was saved, expected 0
- `ProductCreateValidationTest.test_list_page_works_after_posting_too_large_price`: list page returns `500`

**Suggested fix:** Use a `ModelForm`. Its `DecimalField` checks `max_digits` and shows an error. Adding `max="99999999.99"` to the HTML input is also a good idea.

---

## Not confirmed

Every suspected bug from the plan was confirmed: each test failed for the expected reason. **Nothing in this section yet.**

If a bug from the list above is fixed later and its test passes, move it here with the reason the test passed.

---

## Other problems found (no failing test)

These are security or code-quality problems. They aren't functional bugs, so a failing test isn't a good fit for them.

1. **Email password stored in the code.** `inventory_project/settings.py` **lines 129–130** contain a real Gmail address and app password (`EMAIL_HOST_PASSWORD`). Anyone who can see the code (for example on GitHub) can use this account. **Fix:** revoke this app password in Google and load secrets from environment variables. The `SECRET_KEY` on line 23 has the same problem, and `DEBUG = True` (line 26) shouldn't be used in production.
2. **Sender address doesn't match the login.** `views.py` **line 72** uses `from_email = 'boyroyal4853@gmail.com'`, but the SMTP login is `chaudhary639@gmail.com`. Gmail may reject the message or rewrite the sender. **Fix:** use `settings.DEFAULT_FROM_EMAIL` / `EMAIL_HOST_USER`.
3. **Anyone can send email.** `/send-test-email/` sends an email on a simple GET request, with no login. Anyone (or any bot) who visits the URL sends an email from your account. There's also no login on create, edit or delete.
4. **Duplicate templates folder with a typo.** `inventory_app/tamplates/` ("tamplates") is a copy of `templates/` and Django never uses it. It's dead code and can cause confusion.
5. **Version mismatch.** The project was generated with Django 5.2 (see `settings.py` and the migration), but this machine runs Django 6.1.2. The tests run fine on 6.1.2. Adding a `requirements.txt` would pin the version.
