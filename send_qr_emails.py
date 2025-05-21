#!/usr/bin/env python
import os
import sys
import qrcode
import base64
from io import BytesIO


def setup_django():
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                          'Hamayesh_Negar_django.settings')

    import django
    django.setup()


def generate_qr_code(data, filename=None):
    """Generate QR code from data and save it if filename is provided"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    if filename:
        img.save(filename)

    buffered = BytesIO()
    img.save(buffered)
    return base64.b64encode(buffered.getvalue()).decode()


def send_qr_email(person):
    """Send email with QR code to person"""
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    from django.conf import settings

    if not person.email:
        print(f"No email for {person.get_full_name()}, skipping.")
        return False

    qr_dir = 'qr_codes'
    clean_email = person.email.split('@')[0] if person.email else 'user'
    file_name = f"{qr_dir}/{clean_email}_qrcode.png"
    qr_data = generate_qr_code(person.hashed_unique_code, file_name)

    context = {
        'first_name': person.first_name,
        'qr_code': qr_data,
        'person_name': person.get_full_name()
    }

    try:
        html_content = render_to_string('qr_email_template.html', context)
        text_content = strip_tags(html_content)
    except Exception as e:
        print(f"Error rendering email template: {str(e)}")
        return False

    subject = 'QR Code خلاقیت و نشاط'
    from_email = settings.DEFAULT_FROM_EMAIL
    to = person.email

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
    msg.attach_alternative(html_content, "text/html")

    try:
        with open(file_name, 'rb') as f:
            msg.attach(f"{clean_email}_qrcode.png", f.read(), 'image/png')
    except Exception as e:
        print(f"Error attaching QR code: {str(e)}")
        return False

    try:
        msg.send()
        print(
            f"Email sent successfully to {person.get_full_name()} ({person.email})")
        return True
    except Exception as e:
        print(f"Failed to send email to {person.email}: {str(e)}")
        return False


def create_email_template():
    """Create HTML template for the email if it doesn't exist"""
    template_dir = 'templates'
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)

    template_path = f"{template_dir}/qr_email_template.html"
    source_template = "qr_email_template.html"

    if not os.path.exists(source_template):
        print(f"Warning: Source template file '{source_template}' not found.")
        return False

    if (not os.path.exists(template_path) or
            os.path.getmtime(source_template) > os.path.getmtime(template_path)):
        import shutil
        shutil.copy2(source_template, template_path)
        print(f"Template copied to {template_path}")
    else:
        print(f"Template already exists at {template_path}")

    return True


def test_email_config(recipient_email):
    """Test the email configuration by sending a test email"""
    from django.core.mail import send_mail
    from django.conf import settings

    subject = "Test Email from QR Code System"
    message = "This is a test email to verify that the SMTP configuration is working correctly."
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [recipient_email]

    try:
        result = send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            fail_silently=False,
        )
        print(f"Test email sent successfully! Result: {result}")
        return True
    except Exception as e:
        print(f"Failed to send test email: {str(e)}")
        print("Check your email settings in settings.py")
        return False


def main():
    """Main function to send QR codes to all active persons"""
    from person.models import Person

    if not create_email_template():
        print("Error: Could not set up email template. Please make sure qr_email_template.html exists.")
        return

    qr_dir = 'qr_codes'
    if not os.path.exists(qr_dir):
        os.makedirs(qr_dir)
        print(f"Created QR code directory: {qr_dir}")

    try:
        persons = Person.objects.filter(is_active=True)
        print(f"Found {persons.count()} active persons")
    except Exception as e:
        print(f"Error retrieving persons: {str(e)}")
        return

    success_count = 0
    fail_count = 0

    for person in persons:
        if send_qr_email(person):
            success_count += 1
        else:
            fail_count += 1

    print(
        f"Email sending completed. Success: {success_count}, Failed: {fail_count}")


if __name__ == "__main__":
    setup_django()
    main()
